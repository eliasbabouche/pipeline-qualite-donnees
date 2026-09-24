"""Test minimal, presente surtout pour que la CI demarre au vert des le premier commit.

A remplacer par de vrais tests du code metier : en priorite ceux qui verifient le
format des exports (colonnes attendues, encodage, separateur) et le comportement
sur donnees d'entree degradees.
"""

from src import config


def test_racine_contient_le_readme():
    assert (config.RACINE / "README.md").exists()


def test_parametres_export_explicites():
    # Un separateur ou un encodage laisse implicite casse l'import en aval.
    assert config.SEPARATEUR_EXPORT in (";", ",", "\t")
    assert config.ENCODAGE_EXPORT.startswith("utf-8")
