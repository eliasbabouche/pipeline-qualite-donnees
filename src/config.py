"""Chemins et parametres du projet, centralises en un seul endroit.

Aucun chemin en dur ailleurs dans le code : quand la structure bouge, une seule
ligne change ici.
"""

from pathlib import Path

# Racine du projet, deduite de l'emplacement de ce fichier (jamais un chemin absolu
# machine : le code doit tourner chez quelqu'un d'autre et dans la CI).
RACINE = Path(__file__).resolve().parent.parent

# --- Source ---
# Export complet (snapshot) : chaque telechargement contient tout l'historique.
URL_SOURCE = (
    "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/"
    "regularite-mensuelle-tgv-aqst/exports/csv"
)
DELAI_TELECHARGEMENT = 60  # secondes

# --- Format attendu de la source (voir docs/contrat_donnees.md) ---
# utf-8-sig : lit l'UTF-8 et retire le BOM s'il est present, sans rien faire sinon.
ENCODAGE_SOURCE = "utf-8-sig"
SEPARATEUR_SOURCE = ";"

# --- Couches de donnees (architecture medallion) ---
DOSSIER_DONNEES = RACINE / "donnees"
BRONZE = DOSSIER_DONNEES / "bronze"  # fichiers recus tels quels, un dossier par millesime
SILVER = DOSSIER_DONNEES / "silver"  # donnees validees et typees, en Parquet
GOLD = DOSSIER_DONNEES / "gold"  # agregats prets a lire

NOM_FICHIER_BRUT = "source.csv"
NOM_METADONNEES = "metadonnees.json"
