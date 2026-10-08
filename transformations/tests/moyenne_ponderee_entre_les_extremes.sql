-- Test singulier : une moyenne ponderee est toujours comprise entre la plus petite et la
-- plus grande des valeurs qu'elle combine. Si ce n'est pas le cas, la ponderation est fausse
-- (mauvais poids, division par le mauvais total).
-- Verifie sur les liaisons fusionnees National + International.

with origine as (

    select
        mois,
        gare_depart,
        gare_arrivee,
        min(retard_moyen_tous_trains_min) as minimum,
        max(retard_moyen_tous_trains_min) as maximum
    from {{ ref('stg_trajets_mensuels') }}
    group by mois, gare_depart, gare_arrivee
    having count(*) > 1

)

select f.id_liaison_mois, f.retard_moyen_tous_trains_min, o.minimum, o.maximum
from {{ ref('int_liaisons_mensuelles') }} as f
join origine as o using (mois, gare_depart, gare_arrivee)
where f.retard_moyen_tous_trains_min < o.minimum - 1e-9
   or f.retard_moyen_tous_trains_min > o.maximum + 1e-9
