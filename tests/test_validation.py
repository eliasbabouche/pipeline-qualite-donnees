"""Tests de validation : quarantaine ligne par ligne et controles bloquants."""

import pytest

from src.contrat import ErreurContrat
from src.validation import valider
from tests.outils import ligne, tableau


def valider_souple(donnees):
    """Sans les garde-fous de volume, pour tester une regle sur quelques lignes."""
    return valider(donnees, lignes_min_par_mois=1, taux_max_quarantaine=1.0)


def test_lignes_conformes_typees_sans_quarantaine():
    resultat = valider_souple(tableau(ligne(depart="LILLE"), ligne(depart="DOUAI")))

    assert len(resultat.valides) == 2
    assert resultat.quarantaine.empty
    assert resultat.valides["nb_train_prevu"].dtype == "Int64"
    assert resultat.valides["retard_moyen_arrivee"].dtype == "Float64"


# --- Quarantaine : une ligne fautive est ecartee, les autres continuent ---

@pytest.mark.parametrize("modif, motif_attendu", [
    ({"nb_train_retard_sup_30": "-44"}, "nb_train_retard_sup_30"),  # anomalie reelle 2025
    ({"retard_moyen_arrivee": "-30.5"}, "retard_moyen_arrivee"),  # anomalie reelle 2019
    ({"nb_train_prevu": "cent"}, "nb_train_prevu"),  # du texte dans un nombre
    ({"nb_train_prevu": None}, "nb_train_prevu"),  # obligatoire vide
    ({"service": "Regional"}, "service"),
    ({"date": "2026-13"}, "date"),
    ({"prct_cause_infra": "140"}, "prct_cause_infra"),
    ({"nb_train_retard_sup_15": "25"}, "plus de trains a +15 min que de trains en retard"),
    ({"nb_train_retard_sup_30": "12"}, "plus de trains a +30 min qu'a +15 min"),
    ({"nb_annulation": "150"}, "plus d'annulations que de trains prevus"),
    ({"gare_arrivee": "LILLE"}, "gare de depart = gare d'arrivee"),
])
def test_ligne_incoherente_part_en_quarantaine_avec_son_motif(modif, motif_attendu):
    resultat = valider_souple(tableau(ligne(depart="DOUAI"), ligne(depart="LILLE", **modif)))

    assert list(resultat.valides["gare_depart"]) == ["DOUAI"]
    assert len(resultat.quarantaine) == 1
    assert motif_attendu in resultat.quarantaine["motif_rejet"].iloc[0]


def test_quarantaine_conserve_la_ligne_telle_que_lue():
    resultat = valider_souple(tableau(ligne(depart="DOUAI"), ligne(nb_train_prevu="cent")))
    assert resultat.quarantaine["nb_train_prevu"].iloc[0] == "cent"


def test_toutes_les_lignes_rejetees_bloque_avec_message_clair():
    with pytest.raises(ErreurContrat, match="Aucune ligne valide"):
        valider_souple(tableau(ligne(nb_train_prevu="cent")))


def test_liaison_non_assuree_en_2020_est_conservee():
    # Crise sanitaire : 0 train prevu mais des annulations. Pas une erreur de la source.
    covid = ligne(mois="2020-04", nb_train_prevu="0", duree_moyenne="0", nb_annulation="12",
                  nb_train_depart_retard="0", nb_train_retard_arrivee="0",
                  nb_train_retard_sup_15="0", nb_train_retard_sup_30="0",
                  nb_train_retard_sup_60="0")
    resultat = valider_souple(tableau(covid))
    assert resultat.quarantaine.empty


def test_commentaire_facultatif_vide_accepte():
    resultat = valider_souple(tableau(ligne(commentaires_retard_arrivee=None)))
    assert resultat.quarantaine.empty


# --- Piege 4 : doublons introduits par une republication partielle ---

def test_cle_en_double_bloque_sans_dedoublonner():
    with pytest.raises(ErreurContrat, match="meme cle.*Aucun dedoublonnage"):
        valider_souple(tableau(ligne(depart="LILLE"), ligne(depart="LILLE", nb_train_prevu="90")))


def test_meme_liaison_national_et_international_n_est_pas_un_doublon():
    resultat = valider_souple(tableau(ligne(service="National"), ligne(service="International")))
    assert len(resultat.valides) == 2


# --- Controles sur le fichier entier ---

def test_trop_de_quarantaine_bloque():
    lignes = [ligne(depart=f"GARE {i}") for i in range(97)]
    lignes += [ligne(depart=f"FAUSSE {i}", nb_train_prevu="x") for i in range(3)]
    with pytest.raises(ErreurContrat, match="3 lignes sur 100.*seuil de 2%"):
        valider(tableau(*lignes), lignes_min_par_mois=1)


def test_quarantaine_sous_le_seuil_acceptee():
    lignes = [ligne(depart=f"GARE {i}") for i in range(98)]
    lignes += [ligne(depart=f"FAUSSE {i}", nb_train_prevu="x") for i in range(2)]
    resultat = valider(tableau(*lignes), lignes_min_par_mois=1)
    assert len(resultat.quarantaine) == 2


def test_mois_manquant_bloque():
    with pytest.raises(ErreurContrat, match="Mois absents.*2026-05"):
        valider_souple(tableau(ligne(mois="2026-04"), ligne(mois="2026-06")))


def test_mois_publie_a_moitie_bloque():
    lignes = [ligne(mois="2026-05", depart=f"GARE {i}") for i in range(3)]
    lignes += [ligne(mois="2026-06", depart="GARE 0")]
    with pytest.raises(ErreurContrat, match="incomplet.*2026-06"):
        valider(tableau(*lignes), lignes_min_par_mois=2, taux_max_quarantaine=1.0)
