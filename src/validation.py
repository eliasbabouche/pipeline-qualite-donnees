"""Validation d'un export lu, selon le contrat (docs/contrat_donnees.md, sections 2 et 3).

Deux familles de controles :
- ligne par ligne (types, valeurs, coherence entre colonnes), via un schema pandera :
  une ligne fautive part en QUARANTAINE avec son motif, les autres continuent ;
- sur le fichier entier (cle en double, mois manquants, volume, taux de quarantaine) :
  une anomalie est BLOQUANTE et leve ErreurContrat.
"""

from dataclasses import dataclass, field

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from src import config
from src.contrat import CLE_UNICITE, COLONNES_SOURCE, SERVICES_AUTORISES, ErreurContrat

TYPES_PANDAS = {"mois": str, "texte": str, "entier": "Int64", "decimal": "Float64"}
MOTIF_MOIS = r"^\d{4}-(0[1-9]|1[0-2])$"

# Colonnes dont la valeur ne peut pas etre negative (contrat, tableau 3.2).
POSITIFS = [
    "duree_moyenne", "nb_train_prevu", "nb_annulation", "nb_train_depart_retard",
    "retard_moyen_depart", "nb_train_retard_arrivee", "retard_moyen_arrivee",
    "nb_train_retard_sup_15", "nb_train_retard_sup_30", "nb_train_retard_sup_60",
]
POURCENTAGES = [c for c in COLONNES_SOURCE if c.startswith("prct_cause_")]


def regle(nom: str, test) -> pa.Check:
    """Regle de coherence entre colonnes. Son nom devient le motif de quarantaine."""
    return pa.Check(test, name=nom, error=nom)


def colonne(nom: str, type_contrat: str, obligatoire: bool) -> pa.Column:
    verifications = []
    if nom in POSITIFS:
        verifications.append(pa.Check.ge(0))
    if nom in POURCENTAGES:
        verifications.append(pa.Check.in_range(0, 100))
    if type_contrat == "mois":
        verifications.append(pa.Check.str_matches(MOTIF_MOIS))
    if nom == "service":
        verifications.append(pa.Check.isin(SERVICES_AUTORISES))
    return pa.Column(
        TYPES_PANDAS[type_contrat], checks=verifications, nullable=not obligatoire, coerce=True
    )


SCHEMA_LIGNES = pa.DataFrameSchema(
    {nom: colonne(nom, type_c, oblig) for nom, (type_c, oblig) in COLONNES_SOURCE.items()},
    checks=[
        regle("gare de depart = gare d'arrivee",
              lambda d: d["gare_depart"] != d["gare_arrivee"]),
        regle("plus d'annulations que de trains prevus",
              lambda d: (d["nb_train_prevu"] == 0) | (d["nb_annulation"] <= d["nb_train_prevu"])),
        regle("plus de trains en retard que de trains prevus",
              lambda d: d["nb_train_retard_arrivee"] <= d["nb_train_prevu"]),
        regle("plus de trains a +15 min que de trains en retard",
              lambda d: d["nb_train_retard_sup_15"] <= d["nb_train_retard_arrivee"]),
        regle("plus de trains a +30 min qu'a +15 min",
              lambda d: d["nb_train_retard_sup_30"] <= d["nb_train_retard_sup_15"]),
    ],
    strict=True,  # aucune colonne hors contrat a ce stade (la lecture les a deja retirees)
)


@dataclass
class ResultatValidation:
    valides: pd.DataFrame  # lignes conformes, typees
    quarantaine: pd.DataFrame  # lignes rejetees, telles que lues, + motif_rejet
    avertissements: list[str] = field(default_factory=list)


def verifier_cle_unique(donnees: pd.DataFrame) -> None:
    doublons = donnees[donnees.duplicated(CLE_UNICITE, keep=False)]
    if not doublons.empty:
        exemples = doublons[CLE_UNICITE].drop_duplicates().head(3).to_dict("records")
        raise ErreurContrat(
            f"{len(doublons)} lignes partagent une meme cle {' + '.join(CLE_UNICITE)}, "
            f"par exemple : {exemples}. Republication partielle ou nouveau decoupage de la "
            "source ? Aucun dedoublonnage automatique : choisir une ligne inventerait la donnee."
        )


def verifier_mois(donnees: pd.DataFrame, lignes_min_par_mois: int) -> None:
    if donnees.empty:
        raise ErreurContrat("Aucune ligne valide : toutes les lignes sont en quarantaine.")
    mois = pd.PeriodIndex(donnees["date"], freq="M")
    attendus = pd.period_range(mois.min(), mois.max(), freq="M")
    manquants = attendus.difference(mois.unique())
    if len(manquants):
        raise ErreurContrat(
            f"Mois absents de l'historique : {', '.join(map(str, manquants))}."
        )
    par_mois = donnees.groupby("date").size()
    trop_petits = par_mois[par_mois < lignes_min_par_mois]
    if not trop_petits.empty:
        raise ErreurContrat(
            f"Mois publie(s) incomplet(s) (moins de {lignes_min_par_mois} lignes) : "
            f"{trop_petits.to_dict()}."
        )


def motifs_par_ligne(erreurs: SchemaErrors) -> pd.Series:
    """Index de ligne -> motif(s) de rejet lisible(s), separes par ' | '."""
    cas = erreurs.failure_cases.dropna(subset=["index"])
    # Regle entre colonnes (niveau tableau) : son nom suffit.
    # Regle sur une colonne : on precise la colonne et la valeur fautive.
    motifs = cas.apply(
        lambda c: c["check"] if c["schema_context"] == "DataFrameSchema"
        else f"{c['column']} : {c['check']} (valeur {c['failure_case']!r})",
        axis=1,
    )
    return motifs.groupby(cas["index"].astype(int)).agg(lambda m: " | ".join(sorted(set(m))))


def valider(donnees: pd.DataFrame,
            lignes_min_par_mois: int = config.LIGNES_MIN_PAR_MOIS,
            taux_max_quarantaine: float = config.TAUX_MAX_QUARANTAINE) -> ResultatValidation:
    # 1. Controles bloquants sur le fichier entier, avant toute mise a l'ecart de lignes :
    #    un doublon de cle est un probleme de structure, pas une erreur de saisie.
    verifier_cle_unique(donnees)

    # 2. Controles ligne par ligne. lazy=True : toutes les erreurs d'un coup,
    #    pas seulement la premiere.
    try:
        valides = SCHEMA_LIGNES.validate(donnees, lazy=True)
        motifs = pd.Series(dtype=str)
    except SchemaErrors as erreurs:
        motifs = motifs_par_ligne(erreurs)
        if len(motifs) == 0:  # erreur sans ligne identifiable : structure, donc bloquant
            raise ErreurContrat(f"Schema non respecte : {erreurs}") from None
        # Les lignes restantes repassent le schema, pour obtenir leur version typee.
        valides = SCHEMA_LIGNES.validate(donnees.drop(index=motifs.index))

    quarantaine = donnees.loc[motifs.index].assign(motif_rejet=motifs)

    # 3. Garde-fou : une anomalie massive n'est plus une erreur de saisie.
    taux = len(quarantaine) / len(donnees)
    if taux > taux_max_quarantaine:
        principaux = quarantaine["motif_rejet"].value_counts().head(3).to_dict()
        raise ErreurContrat(
            f"{len(quarantaine)} lignes sur {len(donnees)} en quarantaine ({taux:.1%}), "
            f"au-dela du seuil de {taux_max_quarantaine:.0%} : la source a probablement "
            f"change de format. Motifs principaux : {principaux}"
        )

    # 4. Continuite et volume des mois, sur les lignes conservees.
    verifier_mois(valides, lignes_min_par_mois)

    avertissements = []
    if len(quarantaine):
        avertissements.append(
            f"{len(quarantaine)} ligne(s) en quarantaine sur {len(donnees)} ({taux:.2%})."
        )
    return ResultatValidation(valides.reset_index(drop=True), quarantaine, avertissements)
