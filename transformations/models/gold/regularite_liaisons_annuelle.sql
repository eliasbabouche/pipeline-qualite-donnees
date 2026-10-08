-- Agregat construit sur l'etoile : la regularite de chaque liaison sur une annee, pour
-- comparer et classer. Les faits sont joints a leurs deux dimensions.
-- nb_mois indique si l'annee est complete (2026 ne l'est pas encore).

select
    m.annee || ' | ' || f.id_liaison                                            as id_liaison_annee,
    m.annee,
    l.gare_depart,
    l.gare_arrivee,
    count(*)                                                                    as nb_mois,
    cast(sum(f.nb_trains_prevus) as bigint)                                     as nb_trains_prevus,
    cast(sum(f.nb_trains_circules) as bigint)                                   as nb_trains_circules,
    sum(f.nb_annulations) / nullif(sum(f.nb_trains_prevus), 0)                  as taux_annulation,
    sum(f.nb_trains_retard_arrivee) / nullif(sum(f.nb_trains_circules), 0)      as taux_retard_arrivee,
    sum(f.nb_trains_retard_sup_15) / nullif(sum(f.nb_trains_circules), 0)       as taux_retard_sup_15,
    sum(f.retard_moyen_tous_trains_min * f.nb_trains_circules)
        / nullif(sum(f.nb_trains_circules), 0)                                  as retard_moyen_tous_trains_min
from {{ ref('fct_regularite_mensuelle') }} as f
join {{ ref('dim_mois') }} as m on m.mois = f.mois
join {{ ref('dim_liaisons') }} as l on l.id_liaison = f.id_liaison
group by m.annee, f.id_liaison, l.gare_depart, l.gare_arrivee
