"""Chemins et parametres du projet, centralises en un seul endroit.

Aucun chemin en dur ailleurs dans le code : quand la structure bouge, une seule
ligne change ici.
"""

from pathlib import Path

# Racine du projet, deduite de l'emplacement de ce fichier (jamais un chemin absolu
# machine : le code doit tourner chez quelqu'un d'autre et dans la CI).
RACINE = Path(__file__).resolve().parent.parent

DOSSIER_DONNEES = RACINE / "donnees"
DONNEES_BRUT = DOSSIER_DONNEES / "brut"
DONNEES_TRAITE = DOSSIER_DONNEES / "traite"

# --- Format des exports ---
# Ces trois parametres sont la cause la plus frequente d'un import casse en aval.
# Les fixer explicitement, ne jamais se reposer sur les valeurs par defaut de pandas.
ENCODAGE_EXPORT = "utf-8-sig"  # utf-8-sig pour qu'Excel affiche correctement les accents
SEPARATEUR_EXPORT = ";"  # convention francaise
FORMAT_DATE = "%Y-%m-%d"


def creer_dossiers() -> None:
    """Cree l'arborescence de donnees si elle n'existe pas encore."""
    for dossier in (DONNEES_BRUT, DONNEES_TRAITE):
        dossier.mkdir(parents=True, exist_ok=True)
