"""Orchestration Dagster : le pipeline complet, de bronze a gold, en un seul graphe d'assets.

Un asset est une donnee produite (table, fichier), declaree avec ses dependances :
Dagster en deduit l'ordre d'execution. Les modeles dbt deviennent eux aussi des assets,
relies automatiquement a l'asset Python silver par le nom de la source dbt.

Interface web : dagster dev -m src.orchestration
Execution directe : dagster job execute -m src.orchestration -j pipeline_mensuel
"""

import os
import sys
from pathlib import Path

import dagster as dg
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

from src import config, ingestion, silver
from src.contrat import ErreurContrat


def chemin_dbt() -> str:
    """L'executable dbt installe a cote du Python courant (venv actif ou non), sinon 'dbt'."""
    voisin = Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")
    return str(voisin) if voisin.exists() else "dbt"


# --- Projet dbt ---
projet_dbt = DbtProject(
    project_dir=config.RACINE / "transformations",
    profiles_dir=config.RACINE / "transformations",
)
dbt = DbtCliResource(project_dir=projet_dbt, dbt_executable=chemin_dbt())

# Le manifeste (description compilee du projet dbt) est genere s'il n'existe pas encore :
# c'est lui que Dagster lit pour connaitre les modeles et leurs dependances.
if not projet_dbt.manifest_path.exists():
    dbt.cli(["parse"], target_path=projet_dbt.target_path).wait()

CLE_BRONZE = dg.AssetKey(["bronze", "export_sncf"])
# Memes noms que la source dbt "silver" : c'est ce qui relie les deux graphes.
CLE_SILVER = dg.AssetKey(["silver", "trajets_mensuels"])
CLE_QUARANTAINE = dg.AssetKey(["silver", "trajets_mensuels_quarantaine"])


def echec_definitif(erreur: ErreurContrat) -> dg.Failure:
    """Une erreur de contrat ne se reessaie pas : le meme fichier donnerait la meme erreur."""
    return dg.Failure(description=str(erreur), allow_retries=False)


@dg.asset(
    key=CLE_BRONZE,
    group_name="bronze",
    description="Export SNCF archive tel quel, un dossier horodate par contenu different.",
    # Reessais reserves au reseau : site lent, coupure momentanee.
    retry_policy=dg.RetryPolicy(max_retries=3, delay=60),
)
def bronze_export_sncf() -> dg.MaterializeResult:
    try:
        resultat = ingestion.ingerer()
    except ingestion.ErreurIngestion as erreur:
        raise dg.Failure(description=str(erreur), allow_retries=False) from erreur
    return dg.MaterializeResult(
        metadata={
            "statut": resultat.statut,
            "millesime": resultat.dossier.name,
            "empreinte_sha256": resultat.empreinte,
        }
    )


@dg.multi_asset(
    specs=[
        dg.AssetSpec(CLE_SILVER, deps=[CLE_BRONZE], group_name="silver",
                     description="Donnees validees et typees, Parquet partitionne par mois."),
        dg.AssetSpec(CLE_QUARANTAINE, deps=[CLE_BRONZE], group_name="silver",
                     description="Lignes ecartees par la validation, avec leur motif."),
    ]
)
def silver_trajets_mensuels():
    try:
        resultat = silver.construire_silver()
    except ErreurContrat as erreur:
        raise echec_definitif(erreur) from erreur

    yield dg.MaterializeResult(
        asset_key=CLE_SILVER,
        metadata={
            "statut": resultat.statut,
            "millesime_source": resultat.extrait_le,
            "lignes_valides": resultat.lignes_valides,
            "avertissements": "\n".join(resultat.avertissements) or "aucun",
        },
    )
    yield dg.MaterializeResult(
        asset_key=CLE_QUARANTAINE,
        metadata={"lignes_en_quarantaine": resultat.lignes_quarantaine},
    )


class TraducteurDbt(DagsterDbtTranslator):
    """Range chaque modele dbt dans le groupe de son dossier : staging, intermediaire, gold."""

    def get_group_name(self, dbt_resource_props) -> str:
        # fqn = ["transformations", "<dossier>", "<modele>"]
        return dbt_resource_props["fqn"][1]


@dbt_assets(manifest=projet_dbt.manifest_path, dagster_dbt_translator=TraducteurDbt())
def modeles_dbt(context: dg.AssetExecutionContext, dbt: DbtCliResource):
    # dbt build : chaque modele est construit puis teste ; un test en echec bloque la suite.
    yield from dbt.cli(["build"], context=context).stream()


pipeline_mensuel = dg.define_asset_job(
    "pipeline_mensuel",
    selection=dg.AssetSelection.all(),
    description="Ingestion, validation, silver, puis modeles et tests dbt.",
)

planning_mensuel = dg.ScheduleDefinition(
    job=pipeline_mensuel,
    cron_schedule="0 6 10 * *",  # le 10 de chaque mois a 6 h
    execution_timezone="Europe/Paris",
    default_status=dg.DefaultScheduleStatus.RUNNING,
)

defs = dg.Definitions(
    assets=[bronze_export_sncf, silver_trajets_mensuels, modeles_dbt],
    jobs=[pipeline_mensuel],
    schedules=[planning_mensuel],
    resources={"dbt": dbt},
)
