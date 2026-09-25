"""Le contrat de donnees (docs/contrat_donnees.md), traduit en code.

Source unique de verite sur les colonnes : la lecture et la validation lisent toutes
les deux cette liste, pour qu'elles ne puissent jamais diverger.
"""

# Colonne de la source -> (type attendu, obligatoire)
# Types : "mois" (AAAA-MM), "texte", "entier", "decimal".
COLONNES_SOURCE: dict[str, tuple[str, bool]] = {
    "date": ("mois", True),
    "service": ("texte", True),
    "gare_depart": ("texte", True),
    "gare_arrivee": ("texte", True),
    "duree_moyenne": ("entier", True),
    "nb_train_prevu": ("entier", True),
    "nb_annulation": ("entier", True),
    "commentaire_annulation": ("texte", False),
    "nb_train_depart_retard": ("entier", True),
    "retard_moyen_depart": ("decimal", True),
    "retard_moyen_tous_trains_depart": ("decimal", True),
    "commentaire_retards_depart": ("texte", False),
    "nb_train_retard_arrivee": ("entier", True),
    "retard_moyen_arrivee": ("decimal", True),
    "retard_moyen_tous_trains_arrivee": ("decimal", True),
    "commentaires_retard_arrivee": ("texte", False),
    "nb_train_retard_sup_15": ("entier", True),
    "retard_moyen_trains_retard_sup15": ("decimal", True),
    "nb_train_retard_sup_30": ("entier", True),
    "nb_train_retard_sup_60": ("entier", True),
    "prct_cause_externe": ("decimal", True),
    "prct_cause_infra": ("decimal", True),
    "prct_cause_gestion_trafic": ("decimal", True),
    "prct_cause_materiel_roulant": ("decimal", True),
    "prct_cause_gestion_gare": ("decimal", True),
    "prct_cause_prise_en_charge_voyageurs": ("decimal", True),
}

COLONNES_OBLIGATOIRES = [nom for nom, (_, obligatoire) in COLONNES_SOURCE.items() if obligatoire]

CLE_UNICITE = ["date", "gare_depart", "gare_arrivee", "service"]
SERVICES_AUTORISES = ["National", "International"]

# Separateurs essayes, dans l'ordre. Le premier est celui du contrat.
SEPARATEURS_ACCEPTES = [";", ",", "\t"]


class ErreurContrat(Exception):
    """Anomalie bloquante : le fichier ne respecte pas le contrat, rien n'est ecrit."""
