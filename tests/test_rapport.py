"""Tests du rapport d'execution : contenu en cas de succes et d'echec, traduction des motifs."""

import pytest

from src import executer, ingestion, silver
from src.contrat import ErreurContrat
from src.rapport import Execution, pourcentage, rediger, traduire_motif

SILVER = {
    "extrait_le": "2026-10-08T190844Z",
    "mois": ["2018-01", "2026-09"],
    "lignes_lues": 12907,
    "lignes_valides": 12828,
    "lignes_quarantaine": 79,
    "motifs_quarantaine": {"nb_train_retard_sup_30 : greater_than_or_equal_to(0)": 43},
}
CHIFFRES = {
    "mois": "2026-09", "taux_retard_arrivee": 0.168, "taux_annulation": 0.005,
    "nb_liaisons": 103, "nb_liaisons_en_quarantaine": 18, "taux_retard_un_an_avant": None,
}


@pytest.mark.parametrize("motif, phrase", [
    ("nb_train_retard_sup_30 : greater_than_or_equal_to(0)",
     "valeur négative dans « nb_train_retard_sup_30 »"),
    ("prct_cause_infra : in_range(0, 100)", "pourcentage hors de 0-100 dans « prct_cause_infra »"),
    ("nb_train_prevu : coerce_dtype('Int64')", "« nb_train_prevu » n'est pas un nombre"),
    ("plus de trains a +15 min que de trains en retard",
     "plus de trains a +15 min que de trains en retard"),  # deja lisible : inchange
])
def test_motifs_traduits_en_francais(motif, phrase):
    assert traduire_motif(motif) == phrase


def test_pourcentage_au_format_francais():
    assert pourcentage(0.168) == "16,8 %"
    assert pourcentage(None) == "n.d."


def test_rapport_de_succes():
    texte = rediger(Execution(succes=True, debut="08/10/2026 à 21:28", duree_s=13,
                              statut_source="nouveau", silver=SILVER, chiffres_cles=CHIFFRES))

    assert texte.startswith("# ✅ Pipeline réussi")
    assert "nouvelle publication archivée" in texte
    assert "| Lues | 12 907 |" in texte
    assert "43 × valeur négative" in texte
    assert "**16,8 %**" in texte
    assert "18 liaison(s) écartée(s)" in texte  # le lecteur sait que le taux est partiel


def test_rapport_d_echec_dit_quoi_faire():
    texte = rediger(Execution(succes=False, debut="08/10/2026 à 21:28", duree_s=2,
                              etape_en_echec="silver_trajets_mensuels",
                              message_erreur="Colonne(s) obligatoire(s) absente(s) : service."))

    assert texte.startswith("# ❌ Pipeline arrêté")
    assert "Colonne(s) obligatoire(s) absente(s) : service." in texte
    assert "restent intactes" in texte
    assert "## Ce qu'il faut faire" in texte


def test_executer_remonte_l_erreur_de_contrat(monkeypatch, tmp_path):
    # Aucun reseau : l'ingestion est simulee, silver echoue sur une rupture de contrat.
    monkeypatch.setattr(ingestion, "ingerer", lambda: ingestion.ResultatIngestion(
        "inchange", tmp_path / "extrait_le=2026-10-08T190844Z", "abc"))

    def silver_qui_echoue(*args, **kwargs):
        raise ErreurContrat("Le fichier n'est pas en UTF-8 : octet invalide 0xE9.")

    monkeypatch.setattr(silver, "construire_silver", silver_qui_echoue)

    execution = executer.executer()

    assert not execution.succes
    assert execution.etape_en_echec == "silver_trajets_mensuels"
    assert "pas en UTF-8" in execution.message_erreur
    assert execution.statut_source == "inchange"
