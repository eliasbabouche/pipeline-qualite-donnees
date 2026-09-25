"""Garde-fous sur la configuration : les parametres de lecture doivent rester explicites."""

from src import config


def test_racine_contient_le_readme():
    assert (config.RACINE / "README.md").exists()


def test_parametres_lecture_explicites():
    # Un separateur ou un encodage laisse implicite fait lire la source de travers.
    assert config.SEPARATEUR_SOURCE == ";"
    assert config.ENCODAGE_SOURCE == "utf-8-sig"


def test_couches_dans_le_dossier_donnees():
    for couche in (config.BRONZE, config.SILVER, config.GOLD):
        assert couche.parent == config.DOSSIER_DONNEES
