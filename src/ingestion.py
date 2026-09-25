"""Ingestion de l'export SNCF dans la couche bronze.

Bronze archive le fichier recu octet pour octet, sans le lire ni le modifier : meme
un fichier illisible doit pouvoir etre conserve, pour prouver ce que la source a
envoye et tout rejouer plus tard.

Deux garanties :
- idempotence : si le contenu est identique au dernier millesime (meme empreinte
  SHA-256), rien n'est ecrit ;
- atomicite : un millesime est ecrit dans un dossier temporaire puis renomme en une
  seule operation. Un plantage au milieu ne laisse jamais un millesime a moitie ecrit.

Lancement : python -m src.ingestion
"""

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from src import config

logger = logging.getLogger(__name__)

PREFIXE_MILLESIME = "extrait_le="
PREFIXE_TEMPORAIRE = ".en_cours_"


class ErreurIngestion(Exception):
    """Le fichier recu ne peut pas etre archive (vide, telechargement en echec...)."""


@dataclass
class ResultatIngestion:
    statut: str  # "nouveau" ou "inchange"
    dossier: Path  # millesime ecrit, ou dernier millesime si rien n'a change
    empreinte: str


def telecharger(url: str) -> bytes:
    """Renvoie le contenu brut de l'export. Isolee pour etre remplacee dans les tests."""
    reponse = requests.get(url, timeout=config.DELAI_TELECHARGEMENT)
    reponse.raise_for_status()
    return reponse.content


def calculer_empreinte(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def dernier_millesime(bronze: Path) -> Path | None:
    """Le millesime complet le plus recent, ou None si bronze est vide.

    Les noms contiennent un horodatage ISO : l'ordre alphabetique est l'ordre
    chronologique. Un dossier sans fichier de metadonnees est ignore, car ce fichier
    est ecrit en dernier : son absence signale un millesime incomplet.
    """
    if not bronze.exists():
        return None
    complets = [
        d
        for d in bronze.iterdir()
        if d.is_dir()
        and d.name.startswith(PREFIXE_MILLESIME)
        and (d / config.NOM_METADONNEES).exists()
    ]
    return max(complets, default=None)


def lire_metadonnees(millesime: Path) -> dict:
    return json.loads((millesime / config.NOM_METADONNEES).read_text(encoding="utf-8"))


def nettoyer_restes(bronze: Path) -> None:
    """Supprime les dossiers temporaires laisses par une execution interrompue."""
    if not bronze.exists():
        return
    for dossier in bronze.glob(PREFIXE_TEMPORAIRE + "*"):
        logger.warning("Suppression d'un reste d'execution interrompue : %s", dossier.name)
        shutil.rmtree(dossier)


def ecrire_millesime(bronze: Path, contenu: bytes, empreinte: str, url: str,
                     maintenant: datetime) -> Path:
    nom = PREFIXE_MILLESIME + maintenant.strftime("%Y-%m-%dT%H%M%SZ")
    final = bronze / nom
    if final.exists():
        raise ErreurIngestion(f"Le millesime {nom} existe deja : deux executions simultanees ?")

    temporaire = bronze / (PREFIXE_TEMPORAIRE + nom)
    temporaire.mkdir(parents=True)
    try:
        (temporaire / config.NOM_FICHIER_BRUT).write_bytes(contenu)
        metadonnees = {
            "url": url,
            "extrait_le": maintenant.isoformat(),
            "sha256": empreinte,
            "taille_octets": len(contenu),
        }
        # Ecrites en dernier : leur presence certifie que le millesime est complet.
        (temporaire / config.NOM_METADONNEES).write_text(
            json.dumps(metadonnees, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporaire.rename(final)
    except Exception:
        shutil.rmtree(temporaire, ignore_errors=True)
        raise
    return final


def ingerer(bronze: Path = config.BRONZE, url: str = config.URL_SOURCE,
            maintenant: datetime | None = None) -> ResultatIngestion:
    """Telecharge l'export et l'archive en bronze s'il a change depuis le dernier millesime."""
    maintenant = maintenant or datetime.now(timezone.utc)
    nettoyer_restes(bronze)

    contenu = telecharger(url)
    if not contenu.strip():
        raise ErreurIngestion(f"Export vide recu depuis {url}")
    empreinte = calculer_empreinte(contenu)

    precedent = dernier_millesime(bronze)
    if precedent is not None and lire_metadonnees(precedent)["sha256"] == empreinte:
        logger.info("Source inchangee depuis %s : rien a ecrire.", precedent.name)
        return ResultatIngestion("inchange", precedent, empreinte)

    dossier = ecrire_millesime(bronze, contenu, empreinte, url, maintenant)
    logger.info("Nouveau millesime %s (%d octets).", dossier.name, len(contenu))
    return ResultatIngestion("nouveau", dossier, empreinte)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    resultat = ingerer()
    print(f"{resultat.statut} : {resultat.dossier.relative_to(config.RACINE)}")
