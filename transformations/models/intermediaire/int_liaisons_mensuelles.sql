-- Une ligne par liaison et par mois : les lignes National et International d'une meme
-- liaison (juillet a septembre 2025) sont fusionnees.
--
-- Regle : on additionne les comptes, puis on recalcule les moyennes a partir des sommes.
-- Une moyenne de moyennes donnerait le meme poids a 20 trains qu'a 400.

with trajets as (

    select
        *,
        -- Plancher a 0 : en 2020, des liaisons a 0 train prevu comptent des annulations
        -- (63 lignes). Sans plancher, on obtiendrait un nombre de trains negatif.
        greatest(nb_trains_prevus - nb_annulations, 0) as nb_trains_circules
    from {{ ref('stg_trajets_mensuels') }}

)

select
    mois || ' | ' || gare_depart || ' > ' || gare_arrivee   as id_liaison_mois,
    gare_depart || ' > ' || gare_arrivee                    as id_liaison,
    mois,
    cast(left(mois, 4) as integer)                          as annee,
    gare_depart,
    gare_arrivee,
    count(*)                                                as nb_lignes_source,

    -- Sommes en bigint : DuckDB somme en entier 128 bits, que Parquet stockerait en decimal.
    cast(sum(nb_trains_prevus) as bigint)                   as nb_trains_prevus,
    cast(sum(nb_annulations) as bigint)                     as nb_annulations,
    cast(sum(nb_trains_circules) as bigint)                 as nb_trains_circules,
    cast(sum(nb_trains_retard_arrivee) as bigint)           as nb_trains_retard_arrivee,
    cast(sum(nb_trains_retard_sup_15) as bigint)            as nb_trains_retard_sup_15,

    -- Moyennes ponderees : chaque moyenne d'origine est remultipliee par son effectif.
    sum(duree_moyenne_min * nb_trains_prevus)
        / nullif(sum(nb_trains_prevus), 0)                  as duree_moyenne_min,
    sum(retard_moyen_tous_trains_min * nb_trains_circules)
        / nullif(sum(nb_trains_circules), 0)                as retard_moyen_tous_trains_min,
    sum(retard_moyen_trains_en_retard_min * nb_trains_retard_arrivee)
        / nullif(sum(nb_trains_retard_arrivee), 0)          as retard_moyen_trains_en_retard_min

from trajets
group by mois, gare_depart, gare_arrivee
