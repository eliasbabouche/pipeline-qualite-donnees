"""Construction de la couche silver a partir du dernier millesime bronze.

Chaine : bronze -> lecture -> validation -> mise en forme -> Parquet partitionne par mois.

Garanties :
- idempotence : si silver a deja ete construit depuis ce millesime, rien n'est refait
  (sauf forcer=True, pour rejouer apres une correction : c'est le backfill) ;
- remplacement atomique : le nouveau silver est construit a cote, puis mis en place par
  renommage. Si une etape echoue, l'ancien silver reste intact.

Lancement : python -m src.silver [--forcer]
"""

import json
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src import config, ingestion
from src.contrat import ErreurContrat
from src.lecture import lire_export
from src.validation import valider

logger = logging.getLogger(__name__)

TABLE = "trajets_mensuels"
TABLE_QUARANTAINE = "trajets_mensuels_quarantaine.parquet"
NOM_METADONNEES = "metadonnees.json"
# Colonnes vides a 100 % : conservees en bronze, pas reprises en silver (contrat, 5.2).
COLONNES_ABANDONNEES = ["commentaire_annulation", "commentaire_retards_depart"]


@dataclass
class ResultatSilver:
    statut: str  # "construit" ou "inchange"
    extrait_le: str  # millesime bronze d'origine
    lignes_valides: int
    lignes_quarantaine: int
    avertissements: list[str] = field(default_factory=list)


def emplacements(silver: Path) -> tuple[Path, Path]:
    """Dossiers de travail, a cote de silver : (en construction, ancienne version)."""
    return silver.with_name(".silver_en_cours"), silver.with_name(".silver_ancien")


def lire_metadonnees(silver: Path) -> dict | None:
    chemin = silver / NOM_METADONNEES
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else None


def reparer(silver: Path) -> None:
    """Remet silver dans un etat coherent apres une execution interrompue."""
    en_cours, ancien = emplacements(silver)
    if en_cours.exists():
        logger.warning("Suppression d'un silver en construction abandonne.")
        shutil.rmtree(en_cours)
    if ancien.exists():
        if silver.exists():
            shutil.rmtree(ancien)  # le remplacement avait abouti, reste a nettoyer
        else:
            logger.warning("Interruption pendant le remplacement : ancien silver restaure.")
            ancien.rename(silver)


def verifier_couverture(mois_nouveaux: list[str], precedent: dict | None) -> None:
    """Contrat 3.4 : le nouvel export contient au moins tous les mois du precedent."""
    if precedent is None:
        return
    disparus = sorted(set(precedent["mois"]) - set(mois_nouveaux))
    if disparus:
        apercu = ", ".join(disparus[:12]) + (" ..." if len(disparus) > 12 else "")
        raise ErreurContrat(
            f"{len(disparus)} mois presents dans le millesime precedent "
            f"({precedent['extrait_le']}) ont disparu : {apercu}. "
            "Republication partielle ou tronquee de la source ?"
        )


def mettre_en_forme(valides: pd.DataFrame, extrait_le: str) -> pd.DataFrame:
    return (
        valides.drop(columns=COLONNES_ABANDONNEES)
        .rename(columns={"date": "mois"})  # une periode mensuelle, pas une date
        .assign(extrait_le=extrait_le)  # tracabilite : chaque ligne -> son fichier source
        .sort_values(["mois", "gare_depart", "gare_arrivee", "service"])
        .reset_index(drop=True)
    )


def ecrire(silver: Path, trajets: pd.DataFrame, quarantaine: pd.DataFrame,
           metadonnees: dict) -> None:
    en_cours, ancien = emplacements(silver)
    en_cours.mkdir(parents=True)
    try:
        trajets.to_parquet(en_cours / TABLE, partition_cols=["mois"], index=False)
        quarantaine.to_parquet(en_cours / TABLE_QUARANTAINE, index=False)
        (en_cours / NOM_METADONNEES).write_text(
            json.dumps(metadonnees, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(en_cours, ignore_errors=True)
        raise

    # Remplacement : l'ancien est mis de cote, le nouveau prend sa place, l'ancien part.
    # Une interruption entre les deux renommages est rattrapee par reparer().
    if silver.exists():
        silver.rename(ancien)
    en_cours.rename(silver)
    shutil.rmtree(ancien, ignore_errors=True)


def construire_silver(bronze: Path = config.BRONZE, silver: Path = config.SILVER,
                      forcer: bool = False, options_validation: dict | None = None
                      ) -> ResultatSilver:
    reparer(silver)

    millesime = ingestion.dernier_millesime(bronze)
    if millesime is None:
        raise ErreurContrat(
            "Bronze est vide : lancer d'abord l'ingestion (python -m src.ingestion)."
        )

    extrait_le = millesime.name.removeprefix(ingestion.PREFIXE_MILLESIME)

    precedent = lire_metadonnees(silver)
    if precedent and precedent["extrait_le"] == extrait_le and not forcer:
        logger.info("Silver deja construit depuis le millesime %s : rien a refaire.", extrait_le)
        return ResultatSilver("inchange", extrait_le, precedent["lignes_valides"],
                              precedent["lignes_quarantaine"], precedent["avertissements"])

    export = lire_export((millesime / config.NOM_FICHIER_BRUT).read_bytes())
    validation = valider(export.donnees, **(options_validation or {}))
    trajets = mettre_en_forme(validation.valides, extrait_le)

    mois = sorted(trajets["mois"].unique())
    verifier_couverture(mois, precedent)

    avertissements = export.avertissements + validation.avertissements
    metadonnees = {
        "extrait_le": extrait_le,
        "sha256_source": ingestion.lire_metadonnees(millesime)["sha256"],
        "construit_le": datetime.now(timezone.utc).isoformat(),
        "lignes_lues": len(export.donnees),
        "lignes_valides": len(trajets),
        "lignes_quarantaine": len(validation.quarantaine),
        "motifs_quarantaine": validation.quarantaine["motif_rejet"]
        .str.replace(r" \(valeur .*?\)", "", regex=True).value_counts().to_dict(),
        "mois": mois,
        "avertissements": avertissements,
    }
    quarantaine = validation.quarantaine.assign(extrait_le=extrait_le)
    ecrire(silver, trajets, quarantaine, metadonnees)

    for message in avertissements:
        logger.warning(message)
    logger.info("Silver construit depuis le millesime %s : %d lignes, %d en quarantaine.",
                extrait_le, len(trajets), len(quarantaine))
    return ResultatSilver("construit", extrait_le, len(trajets), len(quarantaine),
                          avertissements)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    resultat = construire_silver(forcer="--forcer" in sys.argv)
    print(f"{resultat.statut} : {resultat.lignes_valides} lignes valides, "
          f"{resultat.lignes_quarantaine} en quarantaine (source {resultat.extrait_le})")
