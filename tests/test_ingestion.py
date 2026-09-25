"""Tests de l'ingestion bronze : idempotence, atomicite, reprise apres echec.

Aucun test n'utilise le reseau : la fonction telecharger est remplacee par une
fausse source dont on controle le contenu.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src import config, ingestion

URL = "https://exemple.test/export.csv"
LUNDI = datetime(2026, 9, 21, 8, 0, 0, tzinfo=timezone.utc)
MARDI = datetime(2026, 9, 22, 8, 0, 0, tzinfo=timezone.utc)
EXPORT_V1 = "date;service\n2026-06;National\n".encode("utf-8-sig")
EXPORT_V2 = "date;service\n2026-06;National\n2026-07;National\n".encode("utf-8-sig")


@pytest.fixture
def source(monkeypatch):
    """Fausse source SNCF : le test choisit ce qu'elle renvoie via source['contenu']."""
    etat = {"contenu": EXPORT_V1}
    monkeypatch.setattr(ingestion, "telecharger", lambda url: etat["contenu"])
    return etat


def millesimes(bronze: Path) -> list[str]:
    return sorted(d.name for d in bronze.iterdir())


def test_premiere_execution_archive_le_fichier_tel_quel(tmp_path, source):
    resultat = ingestion.ingerer(tmp_path, URL, LUNDI)

    assert resultat.statut == "nouveau"
    assert millesimes(tmp_path) == ["extrait_le=2026-09-21T080000Z"]
    # Octet pour octet, BOM compris : bronze ne transforme rien.
    assert (resultat.dossier / config.NOM_FICHIER_BRUT).read_bytes() == EXPORT_V1
    metadonnees = ingestion.lire_metadonnees(resultat.dossier)
    assert metadonnees["sha256"] == ingestion.calculer_empreinte(EXPORT_V1)
    assert metadonnees["url"] == URL


def test_idempotence_deux_executions_meme_source(tmp_path, source):
    ingestion.ingerer(tmp_path, URL, LUNDI)
    second = ingestion.ingerer(tmp_path, URL, MARDI)

    assert second.statut == "inchange"
    assert millesimes(tmp_path) == ["extrait_le=2026-09-21T080000Z"]


def test_nouvelle_publication_ajoute_un_millesime_sans_toucher_au_precedent(tmp_path, source):
    premier = ingestion.ingerer(tmp_path, URL, LUNDI)
    source["contenu"] = EXPORT_V2
    second = ingestion.ingerer(tmp_path, URL, MARDI)

    assert second.statut == "nouveau"
    assert len(millesimes(tmp_path)) == 2
    assert (premier.dossier / config.NOM_FICHIER_BRUT).read_bytes() == EXPORT_V1
    assert ingestion.dernier_millesime(tmp_path) == second.dossier


def test_retour_a_un_contenu_anterieur_cree_un_millesime(tmp_path, source):
    # On compare au DERNIER millesime seulement : une source qui revient en arriere
    # est un evenement a tracer, pas a ignorer.
    ingestion.ingerer(tmp_path, URL, LUNDI)
    source["contenu"] = EXPORT_V2
    ingestion.ingerer(tmp_path, URL, MARDI)
    source["contenu"] = EXPORT_V1
    troisieme = ingestion.ingerer(tmp_path, URL, datetime(2026, 9, 23, tzinfo=timezone.utc))

    assert troisieme.statut == "nouveau"
    assert len(millesimes(tmp_path)) == 3


def test_export_vide_refuse_sans_rien_ecrire(tmp_path, source):
    source["contenu"] = b"  \n"
    with pytest.raises(ingestion.ErreurIngestion, match="vide"):
        ingestion.ingerer(tmp_path, URL, LUNDI)
    assert millesimes(tmp_path) == []


def test_plantage_pendant_l_ecriture_ne_laisse_aucun_millesime(tmp_path, source, monkeypatch):
    def rename_qui_plante(self, cible):
        raise OSError("disque plein (simule)")

    monkeypatch.setattr(Path, "rename", rename_qui_plante)
    with pytest.raises(OSError, match="disque plein"):
        ingestion.ingerer(tmp_path, URL, LUNDI)

    # Ni millesime final, ni dossier temporaire oublie.
    assert millesimes(tmp_path) == []


def test_reprise_apres_interruption_brutale(tmp_path, source):
    # Une coupure de courant empeche meme le nettoyage : un dossier temporaire reste.
    reste = tmp_path / (ingestion.PREFIXE_TEMPORAIRE + "extrait_le=2026-09-20T080000Z")
    reste.mkdir()
    (reste / config.NOM_FICHIER_BRUT).write_bytes(b"moitie de fich")

    resultat = ingestion.ingerer(tmp_path, URL, LUNDI)

    assert resultat.statut == "nouveau"
    assert millesimes(tmp_path) == ["extrait_le=2026-09-21T080000Z"]


def test_millesime_sans_metadonnees_est_ignore(tmp_path, source):
    incomplet = tmp_path / "extrait_le=2026-09-30T080000Z"
    incomplet.mkdir()
    (incomplet / config.NOM_FICHIER_BRUT).write_bytes(EXPORT_V1)

    assert ingestion.dernier_millesime(tmp_path) is None
