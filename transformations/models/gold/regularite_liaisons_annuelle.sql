-- Gold : la regularite de chaque liaison sur une annee, pour comparer et classer.
-- nb_mois indique si l'annee est complete (2026 ne l'est pas encore).

select
    annee || ' | ' || gare_depart || ' > ' || gare_arrivee                 as id_liaison_annee,
    annee,
    gare_depart,
    gare_arrivee,
    count(*)                                                                as nb_mois,
    cast(sum(nb_trains_prevus) as bigint)                                   as nb_trains_prevus,
    cast(sum(nb_trains_circules) as bigint)                                 as nb_trains_circules,
    sum(nb_annulations) / nullif(sum(nb_trains_prevus), 0)                  as taux_annulation,
    sum(nb_trains_retard_arrivee) / nullif(sum(nb_trains_circules), 0)      as taux_retard_arrivee,
    sum(nb_trains_retard_sup_15) / nullif(sum(nb_trains_circules), 0)       as taux_retard_sup_15,
    sum(retard_moyen_tous_trains_min * nb_trains_circules)
        / nullif(sum(nb_trains_circules), 0)                                as retard_moyen_tous_trains_min
from {{ ref('int_liaisons_mensuelles') }}
group by annee, gare_depart, gare_arrivee
