-- Gold : la regularite de l'ensemble du reseau TGV, mois par mois.
-- nb_liaisons_en_quarantaine signale les mois ou des liaisons manquent au calcul :
-- un taux calcule sur 103 liaisons au lieu de 121 ne se compare pas sans le savoir.

with liaisons_quarantaine as (

    select
        mois,
        count(distinct gare_depart || ' > ' || gare_arrivee) as nb_liaisons_en_quarantaine
    from {{ ref('stg_quarantaine') }}
    group by mois

),

national as (

    select
        mois,
        annee,
        count(*)                                        as nb_liaisons,
        cast(sum(nb_trains_prevus) as bigint)           as nb_trains_prevus,
        cast(sum(nb_annulations) as bigint)             as nb_annulations,
        cast(sum(nb_trains_circules) as bigint)         as nb_trains_circules,
        cast(sum(nb_trains_retard_arrivee) as bigint)   as nb_trains_retard_arrivee,
        cast(sum(nb_trains_retard_sup_15) as bigint)    as nb_trains_retard_sup_15,
        sum(retard_moyen_tous_trains_min * nb_trains_circules)
            / nullif(sum(nb_trains_circules), 0) as retard_moyen_tous_trains_min
    from {{ ref('int_liaisons_mensuelles') }}
    group by mois, annee

)

select
    n.mois,
    n.annee,
    n.nb_liaisons,
    coalesce(q.nb_liaisons_en_quarantaine, 0)                       as nb_liaisons_en_quarantaine,
    n.nb_trains_prevus,
    n.nb_annulations,
    n.nb_trains_circules,
    n.nb_trains_retard_arrivee,
    n.nb_annulations / nullif(n.nb_trains_prevus, 0)                as taux_annulation,
    n.nb_trains_retard_arrivee / nullif(n.nb_trains_circules, 0)    as taux_retard_arrivee,
    n.nb_trains_retard_sup_15 / nullif(n.nb_trains_circules, 0)     as taux_retard_sup_15,
    n.retard_moyen_tous_trains_min
from national as n
left join liaisons_quarantaine as q on q.mois = n.mois
