"""Rapport d'execution lisible par un non-technicien, au format Markdown.

Fonctions pures : elles recoivent les informations deja collectees et renvoient du texte.
La collecte (lancer le pipeline, lire les fichiers) est dans src/executer.py.
"""

import re
from dataclasses import dataclass, field

# Regles techniques pandera -> phrase comprehensible. Les regles de coherence ont deja
# un nom en francais (voir src/validation.py) et passent telles quelles.
TRADUCTIONS = [
    (r"^(\w+) : greater_than_or_equal_to\(0\)$", "valeur négative dans « {0} »"),
    (r"^(\w+) : in_range\(0, 100\)$", "pourcentage hors de 0-100 dans « {0} »"),
    (r"^(\w+) : str_matches\(.*\)$", "format de mois invalide dans « {0} »"),
    (r"^(\w+) : isin\(.*\)$", "valeur non autorisée dans « {0} »"),
    (r"^(\w+) : not_nullable$", "valeur manquante dans « {0} »"),
    (r"^(\w+) : coerce_dtype\(.*\)$", "« {0} » n'est pas un nombre"),
]


def traduire_motif(motif: str) -> str:
    for modele, phrase in TRADUCTIONS:
        correspondance = re.match(modele, motif)
        if correspondance:
            return phrase.format(*correspondance.groups())
    return motif


@dataclass
class Execution:
    succes: bool
    debut: str  # horodatage lisible
    duree_s: float
    statut_source: str | None = None  # "nouveau" / "inchange"
    silver: dict | None = None  # metadonnees.json de silver
    chiffres_cles: dict | None = None  # dernier mois, issus de gold
    etape_en_echec: str | None = None
    message_erreur: str | None = None
    avertissements: list[str] = field(default_factory=list)


def pourcentage(valeur: float | None) -> str:
    """Format francais : 0.168 -> '16,8 %'."""
    return "n.d." if valeur is None else f"{valeur * 100:.1f} %".replace(".", ",")


def rediger(execution: Execution) -> str:
    lignes = []
    if execution.succes:
        lignes.append("# ✅ Pipeline réussi")
    else:
        lignes.append("# ❌ Pipeline arrêté")
    lignes.append(f"\nExécution du {execution.debut}, durée {execution.duree_s:.0f} s.\n")

    if not execution.succes:
        lignes += [
            "## Ce qui s'est passé",
            f"L'étape **{execution.etape_en_echec}** a échoué :",
            f"\n```\n{execution.message_erreur}\n```\n",
            "## Ce qu'il faut faire",
            "- Rien n'a été écrit : les données de l'exécution précédente restent intactes "
            "et consultables.",
            "- Si le message parle de colonne, d'encodage, de clé ou de mois disparus, la source "
            "SNCF a changé de format : adapter `src/contrat.py` et `docs/contrat_donnees.md`, "
            "puis relancer.",
            "- Si le message parle de réseau ou de téléchargement, relancer plus tard suffit.",
        ]
        return "\n".join(lignes) + "\n"

    source = {"nouveau": "nouvelle publication archivée",
              "inchange": "aucune nouvelle publication depuis le dernier passage"}
    lignes.append("## Source")
    lignes.append(f"- SNCF : {source.get(execution.statut_source, execution.statut_source)}")

    if execution.silver:
        s = execution.silver
        lignes += [
            f"- Millésime traité : `{s['extrait_le']}`",
            f"- Période couverte : {s['mois'][0]} → {s['mois'][-1]} ({len(s['mois'])} mois)",
            "",
            "## Contrôle qualité",
            "| | Lignes |",
            "|---|---:|",
            f"| Lues | {s['lignes_lues']:,} |".replace(",", " "),
            f"| Retenues | {s['lignes_valides']:,} |".replace(",", " "),
            f"| Écartées (quarantaine) | {s['lignes_quarantaine']:,} |".replace(",", " "),
        ]
        if s["motifs_quarantaine"]:
            lignes.append("\nMotifs des lignes écartées :\n")
            for motif, nombre in s["motifs_quarantaine"].items():
                lignes.append(f"- {nombre} × {traduire_motif(motif)}")

    if execution.chiffres_cles:
        c = execution.chiffres_cles
        lignes += [
            "",
            f"## Chiffres clés — {c['mois']}",
            f"- Trains en retard à l'arrivée : **{pourcentage(c['taux_retard_arrivee'])}** "
            f"(même mois un an plus tôt : {pourcentage(c.get('taux_retard_un_an_avant'))})",
            f"- Trains annulés : {pourcentage(c['taux_annulation'])}",
            f"- Liaisons prises en compte : {c['nb_liaisons']}",
        ]
        if c["nb_liaisons_en_quarantaine"]:
            lignes.append(
                f"- ⚠ {c['nb_liaisons_en_quarantaine']} liaison(s) écartée(s) ce mois-ci : "
                "les taux portent sur les autres."
            )

    if execution.avertissements:
        lignes += ["", "## Avertissements"] + [f"- {a}" for a in execution.avertissements]
    return "\n".join(lignes) + "\n"
