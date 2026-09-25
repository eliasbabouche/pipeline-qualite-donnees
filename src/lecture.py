"""Lecture d'un export brut : des octets de bronze a un tableau pandas.

Cette etape attrape les anomalies de FORME (encodage, separateur, colonnes) avant
toute autre. Toutes les colonnes sont lues comme du texte : la conversion en nombres
se fait a la validation, ligne par ligne, pour qu'une valeur aberrante envoie sa
ligne en quarantaine au lieu de faire echouer tout le fichier.
"""

import io
from dataclasses import dataclass, field

import pandas as pd

from src.contrat import (
    COLONNES_OBLIGATOIRES,
    COLONNES_SOURCE,
    SEPARATEURS_ACCEPTES,
    ErreurContrat,
)

NOMS_SEPARATEURS = {";": "point-virgule", ",": "virgule", "\t": "tabulation"}


@dataclass
class ExportLu:
    donnees: pd.DataFrame
    separateur: str
    avertissements: list[str] = field(default_factory=list)


def decoder(contenu: bytes) -> str:
    """UTF-8 strict (BOM retire s'il existe). Aucun autre encodage n'est devine."""
    try:
        return contenu.decode("utf-8-sig")
    except UnicodeDecodeError as erreur:
        extrait = contenu[max(erreur.start - 20, 0) : erreur.start + 20]
        raise ErreurContrat(
            f"Le fichier n'est pas en UTF-8 : octet invalide 0x{contenu[erreur.start]:02X} "
            f"en position {erreur.start} (contexte : {extrait!r}). "
            "La source a probablement change d'encodage (latin-1 / Windows-1252). "
            "Aucune conversion automatique : deviner l'encodage risquerait de corrompre "
            "les accents sans erreur visible."
        ) from None


def detecter_separateur(texte: str) -> str:
    """Le separateur qui donne toutes les colonnes obligatoires sur la ligne d'en-tete."""
    en_tete = texte.split("\n", 1)[0].rstrip("\r")
    if not en_tete.strip():
        raise ErreurContrat("Le fichier est vide ou sa premiere ligne (en-tete) est vide.")

    for separateur in SEPARATEURS_ACCEPTES:
        colonnes = {c.strip().strip('"') for c in en_tete.split(separateur)}
        if set(COLONNES_OBLIGATOIRES) <= colonnes:
            return separateur

    # Aucun separateur ne convient : c'est un probleme de colonnes, pas de separateur.
    # On diagnostique avec le separateur du contrat pour nommer les colonnes en cause.
    colonnes = [c.strip().strip('"') for c in en_tete.split(SEPARATEURS_ACCEPTES[0])]
    verifier_colonnes(colonnes)
    # Garde-fou, en theorie inatteignable : verifier_colonnes vient de lever une erreur.
    raise ErreurContrat(f"En-tete illisible : {en_tete[:200]!r}")


def verifier_colonnes(colonnes: list[str]) -> list[str]:
    """Bloque si une colonne obligatoire manque ; renvoie les avertissements sinon."""
    manquantes = [c for c in COLONNES_OBLIGATOIRES if c not in colonnes]
    inconnues = [c for c in colonnes if c not in COLONNES_SOURCE]
    if manquantes:
        message = f"Colonne(s) obligatoire(s) absente(s) : {', '.join(manquantes)}."
        if inconnues:
            message += (
                f" Colonne(s) inconnue(s) presente(s) : {', '.join(inconnues)}"
                " -- renommage probable cote source."
            )
        raise ErreurContrat(message)
    if inconnues:
        return [f"Colonne(s) non prevue(s) par le contrat, ignoree(s) : {', '.join(inconnues)}."]
    return []


def lire_export(contenu: bytes) -> ExportLu:
    texte = decoder(contenu)
    separateur = detecter_separateur(texte)

    avertissements = []
    if separateur != SEPARATEURS_ACCEPTES[0]:
        avertissements.append(
            f"Separateur {NOMS_SEPARATEURS[separateur]} au lieu du point-virgule prevu "
            "par le contrat : lecture adaptee, colonnes verifiees."
        )

    donnees = pd.read_csv(
        io.StringIO(texte),
        sep=separateur,
        dtype=str,  # tout en texte : le typage est fait a la validation
        keep_default_na=False,  # "NA" ou "null" restent du texte...
        na_values=[""],  # ...seule une cellule vide est une valeur manquante
    )
    donnees.columns = [c.strip() for c in donnees.columns]
    avertissements += verifier_colonnes(list(donnees.columns))

    # Colonnes remises dans l'ordre du contrat : l'ordre de la source n'a aucun effet.
    # Une colonne facultative absente est ajoutee vide plutot que de faire echouer.
    donnees = donnees.reindex(columns=list(COLONNES_SOURCE))
    return ExportLu(donnees, separateur, avertissements)
