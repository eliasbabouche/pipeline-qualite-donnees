"""Fabrication de donnees de test, partagee entre les fichiers de tests."""

import pandas as pd

from src.contrat import COLONNES_SOURCE


def ligne(mois="2026-06", depart="LILLE", service="National", **modifs) -> dict:
    """Une ligne conforme et coherente, telle que la lecture la produit (tout en texte)."""
    valeurs = {
        "date": mois, "service": service, "gare_depart": depart, "gare_arrivee": "PARIS NORD",
        "duree_moyenne": "60", "nb_train_prevu": "100", "nb_annulation": "2",
        "nb_train_depart_retard": "10", "retard_moyen_depart": "5.5",
        "retard_moyen_tous_trains_depart": "0.8", "nb_train_retard_arrivee": "20",
        "retard_moyen_arrivee": "12.5", "retard_moyen_tous_trains_arrivee": "2.1",
        "nb_train_retard_sup_15": "10", "retard_moyen_trains_retard_sup15": "25.0",
        "nb_train_retard_sup_30": "5", "nb_train_retard_sup_60": "2",
        "prct_cause_externe": "50", "prct_cause_infra": "50", "prct_cause_gestion_trafic": "0",
        "prct_cause_materiel_roulant": "0", "prct_cause_gestion_gare": "0",
        "prct_cause_prise_en_charge_voyageurs": "0",
    }
    valeurs.update(modifs)
    return {c: valeurs.get(c) for c in COLONNES_SOURCE}


def tableau(*lignes) -> pd.DataFrame:
    return pd.DataFrame(list(lignes), columns=list(COLONNES_SOURCE))


def export_csv(*lignes) -> bytes:
    """Un export au format de la source SNCF : point-virgule, UTF-8 avec BOM."""
    return tableau(*lignes).to_csv(sep=";", index=False).encode("utf-8-sig")
