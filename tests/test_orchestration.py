"""Tests de l'orchestration : graphe complet, et politique d'echec (reessayer ou s'arreter)."""

import dagster as dg

from src import orchestration, silver
from src.contrat import ErreurContrat


def cles(*chemins: str) -> set[dg.AssetKey]:
    return {dg.AssetKey(c.split("/")) for c in chemins}


def test_les_definitions_se_chargent():
    orchestration.defs.validate_loadable(orchestration.defs)


def test_graphe_relie_bronze_silver_et_dbt():
    graphe = orchestration.defs.resolve_asset_graph()

    assert graphe.get(orchestration.CLE_SILVER).parent_keys == cles("bronze/export_sncf")
    # La source dbt "silver" est raccordee a l'asset Python du meme nom.
    assert graphe.get(dg.AssetKey("stg_trajets_mensuels")).parent_keys == cles(
        "silver/trajets_mensuels"
    )
    assert cles(
        "regularite_liaisons_mensuelle",
        "regularite_nationale_mensuelle",
        "regularite_liaisons_annuelle",
    ) <= graphe.get_all_asset_keys()


def test_groupes_suivent_les_couches():
    graphe = orchestration.defs.resolve_asset_graph()
    groupe = {
        cle.to_user_string(): graphe.get(cle).group_name for cle in graphe.get_all_asset_keys()
    }

    assert groupe["bronze/export_sncf"] == "bronze"
    assert groupe["silver/trajets_mensuels"] == "silver"
    assert groupe["stg_trajets_mensuels"] == "staging"
    assert groupe["int_liaisons_mensuelles"] == "intermediaire"
    assert groupe["regularite_nationale_mensuelle"] == "gold"
    assert "default" not in groupe.values()


def test_reessais_reserves_au_telechargement():
    assert orchestration.bronze_export_sncf.op.retry_policy.max_retries == 3
    assert orchestration.silver_trajets_mensuels.op.retry_policy is None


def test_erreur_de_contrat_arrete_le_pipeline_avec_son_message(monkeypatch):
    def silver_qui_echoue(*args, **kwargs):
        raise ErreurContrat("Colonne(s) obligatoire(s) absente(s) : nb_train_prevu.")

    monkeypatch.setattr(silver, "construire_silver", silver_qui_echoue)
    resultat = dg.materialize([orchestration.silver_trajets_mensuels], raise_on_error=False)

    assert not resultat.success
    echec = resultat.get_step_failure_events()[0]
    assert "nb_train_prevu" in echec.step_failure_data.user_failure_data.description


def test_planning_mensuel_heure_de_paris():
    planning = orchestration.planning_mensuel
    assert planning.cron_schedule == "0 6 10 * *"
    assert planning.execution_timezone == "Europe/Paris"
