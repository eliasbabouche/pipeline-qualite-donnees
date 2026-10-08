"""Point d'entree unique : lance le pipeline Dagster, ecrit le journal et le rapport.

Lancement : python -m src.executer
- le rapport lisible est ecrit dans donnees/rapport_execution.md ;
- dans GitHub Actions, il est aussi affiche en tete de la page de l'execution ;
- le code de sortie vaut 1 en cas d'echec, pour que la CI passe au rouge.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd

from src import config, silver
from src.rapport import Execution, rediger

RAPPORT = config.DOSSIER_DONNEES / "rapport_execution.md"
JOURNAL = config.DOSSIER_DONNEES / "journal.jsonl"


class FormatJson(logging.Formatter):
    """Une ligne JSON par evenement : filtrable par un programme, pas seulement lisible."""

    def format(self, enregistrement: logging.LogRecord) -> str:
        return json.dumps({
            "horodatage": datetime.fromtimestamp(enregistrement.created, timezone.utc).isoformat(),
            "niveau": enregistrement.levelname,
            "module": enregistrement.name,
            "message": enregistrement.getMessage(),
        }, ensure_ascii=False)


def configurer_journal() -> None:
    config.DOSSIER_DONNEES.mkdir(exist_ok=True)
    fichier = logging.FileHandler(JOURNAL, encoding="utf-8")
    fichier.setFormatter(FormatJson())
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    for module in ("src", "__main__"):
        journal = logging.getLogger(module)
        journal.setLevel(logging.INFO)
        journal.addHandler(fichier)
        journal.addHandler(console)


def chiffres_cles() -> dict | None:
    """Les indicateurs du dernier mois publie, lus dans gold."""
    chemin = config.GOLD / "regularite_nationale_mensuelle.parquet"
    if not chemin.exists():
        return None
    national = pd.read_parquet(chemin).sort_values("mois").set_index("mois")
    dernier = national.index[-1]
    un_an_avant = f"{int(dernier[:4]) - 1}{dernier[4:]}"
    ligne = national.loc[dernier]
    return {
        "mois": dernier,
        "taux_retard_arrivee": ligne["taux_retard_arrivee"],
        "taux_annulation": ligne["taux_annulation"],
        "nb_liaisons": int(ligne["nb_liaisons"]),
        "nb_liaisons_en_quarantaine": int(ligne["nb_liaisons_en_quarantaine"]),
        "taux_retard_un_an_avant": (
            national.loc[un_an_avant, "taux_retard_arrivee"]
            if un_an_avant in national.index else None
        ),
    }


def executer() -> Execution:
    # Import tardif : charger les definitions Dagster prepare le projet dbt.
    from src.orchestration import defs

    debut = datetime.now()
    chrono = time.monotonic()
    resultat = defs.get_job_def("pipeline_mensuel").execute_in_process(raise_on_error=False)
    execution = Execution(
        succes=resultat.success,
        debut=debut.strftime("%d/%m/%Y à %H:%M"),
        duree_s=time.monotonic() - chrono,
    )

    for evenement in resultat.get_asset_materialization_events():
        materialisation = evenement.event_specific_data.materialization
        if materialisation.asset_key.path == ["bronze", "export_sncf"]:
            execution.statut_source = materialisation.metadata["statut"].value

    if resultat.success:
        execution.silver = silver.lire_metadonnees(config.SILVER)
        execution.avertissements = execution.silver["avertissements"]
        execution.chiffres_cles = chiffres_cles()
    else:
        echec = resultat.get_step_failure_events()[0]
        donnees = echec.step_failure_data
        execution.etape_en_echec = echec.step_key
        execution.message_erreur = (
            donnees.user_failure_data.description if donnees.user_failure_data
            else donnees.error.message.strip()
        )
    return execution


def publier(texte: str) -> None:
    RAPPORT.write_text(texte, encoding="utf-8")
    # GitHub Actions fournit ce fichier : son contenu s'affiche en tete de l'execution.
    resume_github = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume_github:
        with open(resume_github, "a", encoding="utf-8") as resume:
            resume.write(texte)


if __name__ == "__main__":
    configurer_journal()
    execution = executer()
    texte = rediger(execution)
    publier(texte)
    print(texte)
    sys.exit(0 if execution.succes else 1)
