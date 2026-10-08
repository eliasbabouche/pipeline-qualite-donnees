-- Test singulier : aucune agregation ne doit perdre ni dupliquer un train.
-- Le total des trains prevus doit etre identique a chaque etage de la chaine.
-- Une jointure mal ecrite (lignes dupliquees) ou un filtre oublie ferait echouer ce test.

with totaux as (

    select 'staging' as etage, sum(nb_trains_prevus) as trains
    from {{ ref('stg_trajets_mensuels') }}
    union all
    select 'intermediaire', sum(nb_trains_prevus) from {{ ref('int_liaisons_mensuelles') }}
    union all
    select 'gold liaisons', sum(nb_trains_prevus) from {{ ref('regularite_liaisons_mensuelle') }}
    union all
    select 'gold national', sum(nb_trains_prevus) from {{ ref('regularite_nationale_mensuelle') }}
    union all
    select 'gold annuel', sum(nb_trains_prevus) from {{ ref('regularite_liaisons_annuelle') }}

)

select *
from totaux
where trains <> (select trains from totaux where etage = 'staging')
