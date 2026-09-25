"""Tests de lecture sur des exports volontairement degrades : un test par piege."""

import pytest

from src.contrat import COLONNES_SOURCE, ErreurContrat
from src.lecture import lire_export

COLONNES = list(COLONNES_SOURCE)


def ligne(date: str, depart: str, commentaire: str = "") -> list[str]:
    valeurs = {c: "1" for c in COLONNES}
    valeurs.update(
        date=date, service="National", gare_depart=depart, gare_arrivee="PARIS LYON",
        commentaire_annulation="", commentaire_retards_depart="",
        commentaires_retard_arrivee=commentaire,
    )
    return [valeurs[c] for c in COLONNES]


def fabriquer_csv(colonnes=COLONNES, lignes=None, separateur=";") -> str:
    lignes = lignes or [ligne("2026-05", "LYON PART DIEU"), ligne("2026-06", "DIJON VILLE")]
    texte = [separateur.join(colonnes)]
    for valeurs in lignes:
        # Guillemets autour de toute valeur contenant le separateur ou un retour a la ligne.
        texte.append(separateur.join(
            f'"{v}"' if (separateur in v or "\n" in v) else v for v in valeurs
        ))
    return "\n".join(texte) + "\n"


def test_export_conforme_avec_bom():
    lu = lire_export(fabriquer_csv().encode("utf-8-sig"))

    assert list(lu.donnees.columns) == COLONNES  # "date", pas "﻿date"
    assert len(lu.donnees) == 2
    assert lu.avertissements == []


def test_export_conforme_sans_bom():
    lu = lire_export(fabriquer_csv().encode("utf-8"))
    assert list(lu.donnees.columns) == COLONNES


# --- Piege 1 : encodage ---

def test_encodage_latin1_bloque_avec_message_explicite():
    contenu = fabriquer_csv(lignes=[ligne("2026-06", "NÎMES")]).encode("latin-1")
    with pytest.raises(ErreurContrat, match="pas en UTF-8.*0xCE"):
        lire_export(contenu)


# --- Piege 2 : separateur ---

def test_separateur_virgule_lu_avec_avertissement():
    lu = lire_export(fabriquer_csv(separateur=",").encode("utf-8"))

    assert lu.separateur == ","
    assert len(lu.donnees) == 2
    assert lu.donnees.loc[0, "gare_depart"] == "LYON PART DIEU"
    assert any("virgule" in a for a in lu.avertissements)


# --- Piege 3 : colonne renommee, supprimee ou deplacee ---

def test_colonne_renommee_bloque_en_nommant_les_deux_colonnes():
    colonnes = [("nb_trains_prevus" if c == "nb_train_prevu" else c) for c in COLONNES]
    with pytest.raises(ErreurContrat) as erreur:
        lire_export(fabriquer_csv(colonnes=colonnes).encode("utf-8"))

    message = str(erreur.value)
    assert "nb_train_prevu" in message  # ce qui manque
    assert "nb_trains_prevus" in message  # ce qui l'a probablement remplace


def test_colonne_obligatoire_supprimee_bloque():
    colonnes = [c for c in COLONNES if c != "service"]
    lignes = [[v for c, v in zip(COLONNES, ligne("2026-06", "LILLE")) if c != "service"]]
    with pytest.raises(ErreurContrat, match="absente.*service"):
        lire_export(fabriquer_csv(colonnes=colonnes, lignes=lignes).encode("utf-8"))


def test_colonnes_deplacees_sans_effet():
    inverse = list(reversed(COLONNES))
    lignes = [list(reversed(ligne("2026-06", "LILLE")))]
    lu = lire_export(fabriquer_csv(colonnes=inverse, lignes=lignes).encode("utf-8"))

    assert list(lu.donnees.columns) == COLONNES
    assert lu.donnees.loc[0, "gare_depart"] == "LILLE"
    assert lu.donnees.loc[0, "date"] == "2026-06"


def test_colonne_en_plus_ignoree_avec_avertissement():
    colonnes = COLONNES + ["nouvelle_colonne"]
    lignes = [ligne("2026-06", "LILLE") + ["x"]]
    lu = lire_export(fabriquer_csv(colonnes=colonnes, lignes=lignes).encode("utf-8"))

    assert "nouvelle_colonne" not in lu.donnees.columns
    assert any("nouvelle_colonne" in a for a in lu.avertissements)


# --- Cas limites ---

def test_commentaire_sur_plusieurs_lignes_ne_decale_rien():
    lignes = [
        ligne("2026-05", "LYON PART DIEU", commentaire="Le 1er : tempete ;\nLe 3 : greve"),
        ligne("2026-06", "DIJON VILLE"),
    ]
    lu = lire_export(fabriquer_csv(lignes=lignes).encode("utf-8"))

    assert len(lu.donnees) == 2  # et non 3 : le retour a la ligne est dans un champ
    assert lu.donnees.loc[1, "gare_depart"] == "DIJON VILLE"


def test_valeur_texte_na_n_est_pas_une_valeur_manquante():
    lu = lire_export(fabriquer_csv(lignes=[ligne("2026-06", "NA")]).encode("utf-8"))
    assert lu.donnees.loc[0, "gare_depart"] == "NA"


def test_fichier_vide_bloque():
    with pytest.raises(ErreurContrat, match="vide"):
        lire_export(b"")
