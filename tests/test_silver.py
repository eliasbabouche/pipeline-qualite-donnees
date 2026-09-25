"""Tests de construction de silver : resultat, idempotence, backfill, echecs sans degat."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from src import ingestion, silver
from src.contrat import ErreurContrat
from tests.outils import export_csv, ligne

SOUPLE = {"lignes_min_par_mois": 1, "taux_max_quarantaine": 1.0}
EXPORT_MAI_JUIN = export_csv(
    ligne(mois="2026-05", depart="LILLE"),
    ligne(mois="2026-06", depart="LILLE"),
    ligne(mois="2026-06", depart="DOUAI", nb_train_retard_sup_30="-4"),  # anomalie 2025
)


@pytest.fixture
def dossiers(tmp_path):
    return tmp_path / "bronze", tmp_path / "silver"


def publier(bronze, contenu: bytes, jour: int):
    """Depose un millesime en bronze, comme le ferait l'ingestion."""
    quand = datetime(2026, 9, jour, 8, 0, tzinfo=timezone.utc)
    ingestion.ecrire_millesime(bronze, contenu, ingestion.calculer_empreinte(contenu), "url", quand)


def construire(dossiers, **options):
    bronze, dossier_silver = dossiers
    return silver.construire_silver(bronze, dossier_silver, options_validation=SOUPLE, **options)


def test_silver_construit_partitionne_par_mois(dossiers):
    bronze, dossier_silver = dossiers
    publier(bronze, EXPORT_MAI_JUIN, jour=21)

    resultat = construire(dossiers)

    assert resultat.statut == "construit"
    assert (resultat.lignes_valides, resultat.lignes_quarantaine) == (2, 1)
    partitions = sorted(p.name for p in (dossier_silver / silver.TABLE).iterdir())
    assert partitions == ["mois=2026-05", "mois=2026-06"]

    trajets = pd.read_parquet(dossier_silver / silver.TABLE)
    assert "date" not in trajets.columns and "mois" in trajets.columns
    assert not set(silver.COLONNES_ABANDONNEES) & set(trajets.columns)
    assert set(trajets["extrait_le"]) == {"2026-09-21T080000Z"}


def test_quarantaine_ecrite_a_cote_avec_son_motif(dossiers):
    bronze, dossier_silver = dossiers
    publier(bronze, EXPORT_MAI_JUIN, jour=21)
    construire(dossiers)

    quarantaine = pd.read_parquet(dossier_silver / silver.TABLE_QUARANTAINE)
    assert list(quarantaine["gare_depart"]) == ["DOUAI"]
    assert "nb_train_retard_sup_30" in quarantaine["motif_rejet"].iloc[0]


def test_idempotence_meme_millesime_rien_n_est_refait(dossiers):
    bronze, dossier_silver = dossiers
    publier(bronze, EXPORT_MAI_JUIN, jour=21)
    construire(dossiers)
    avant = silver.lire_metadonnees(dossier_silver)

    resultat = construire(dossiers)

    assert resultat.statut == "inchange"
    assert silver.lire_metadonnees(dossier_silver) == avant  # meme construit_le


def test_backfill_forcer_reconstruit_depuis_bronze(dossiers):
    bronze, dossier_silver = dossiers
    publier(bronze, EXPORT_MAI_JUIN, jour=21)
    construire(dossiers)
    avant = silver.lire_metadonnees(dossier_silver)["construit_le"]

    resultat = construire(dossiers, forcer=True)

    assert resultat.statut == "construit"
    assert silver.lire_metadonnees(dossier_silver)["construit_le"] != avant


def test_nouveau_millesime_remplace_silver(dossiers):
    bronze, dossier_silver = dossiers
    publier(bronze, EXPORT_MAI_JUIN, jour=21)
    construire(dossiers)
    publier(bronze, export_csv(
        ligne(mois="2026-05"), ligne(mois="2026-06"), ligne(mois="2026-07")), jour=22)

    resultat = construire(dossiers)

    assert resultat.extrait_le == "2026-09-22T080000Z"
    assert silver.lire_metadonnees(dossier_silver)["mois"] == ["2026-05", "2026-06", "2026-07"]


# --- Echecs : l'ancien silver doit rester intact ---

def test_republication_tronquee_bloque_et_garde_l_ancien_silver(dossiers):
    bronze, dossier_silver = dossiers
    publier(bronze, EXPORT_MAI_JUIN, jour=21)
    construire(dossiers)
    avant = silver.lire_metadonnees(dossier_silver)
    publier(bronze, export_csv(ligne(mois="2026-06")), jour=22)  # mai a disparu

    with pytest.raises(ErreurContrat, match="ont disparu : 2026-05"):
        construire(dossiers)
    assert silver.lire_metadonnees(dossier_silver) == avant


def test_source_invalide_bloque_et_garde_l_ancien_silver(dossiers):
    bronze, dossier_silver = dossiers
    publier(bronze, EXPORT_MAI_JUIN, jour=21)
    construire(dossiers)
    avant = silver.lire_metadonnees(dossier_silver)
    export_latin1 = export_csv(
        ligne(mois="2026-05"), ligne(mois="2026-06", depart="NÎMES")
    ).decode("utf-8-sig").encode("latin-1")
    publier(bronze, export_latin1, jour=22)

    with pytest.raises(ErreurContrat, match="pas en UTF-8"):
        construire(dossiers)
    assert silver.lire_metadonnees(dossier_silver) == avant


def test_plantage_pendant_l_ecriture_garde_l_ancien_silver(dossiers, monkeypatch):
    bronze, dossier_silver = dossiers
    publier(bronze, EXPORT_MAI_JUIN, jour=21)
    construire(dossiers)
    avant = silver.lire_metadonnees(dossier_silver)

    def to_parquet_qui_plante(self, *args, **kwargs):
        raise OSError("disque plein (simule)")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", to_parquet_qui_plante)
    with pytest.raises(OSError):
        construire(dossiers, forcer=True)

    en_cours, ancien = silver.emplacements(dossier_silver)
    assert not en_cours.exists() and not ancien.exists()
    assert silver.lire_metadonnees(dossier_silver) == avant


def test_interruption_entre_les_deux_renommages_est_reparee(dossiers):
    bronze, dossier_silver = dossiers
    publier(bronze, EXPORT_MAI_JUIN, jour=21)
    construire(dossiers)
    avant = silver.lire_metadonnees(dossier_silver)
    # Etat laisse par une coupure juste apres "silver -> ancien" : plus de silver du tout.
    _, ancien = silver.emplacements(dossier_silver)
    dossier_silver.rename(ancien)

    resultat = construire(dossiers)

    assert resultat.statut == "inchange"  # l'ancien a ete restaure, il etait a jour
    assert silver.lire_metadonnees(dossier_silver) == avant


def test_bronze_vide_bloque_avec_la_marche_a_suivre(dossiers):
    with pytest.raises(ErreurContrat, match="python -m src.ingestion"):
        construire(dossiers)
