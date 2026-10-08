-- Vue fine sur silver : on choisit, renomme et type les colonnes, sans aucun calcul.
-- Tous les modeles suivants partent d'ici, jamais directement de la source.

select
    cast(mois as varchar)               as mois,
    service,
    gare_depart,
    gare_arrivee,
    duree_moyenne                       as duree_moyenne_min,
    nb_train_prevu                      as nb_trains_prevus,
    nb_annulation                       as nb_annulations,
    nb_train_retard_arrivee             as nb_trains_retard_arrivee,
    retard_moyen_arrivee                as retard_moyen_trains_en_retard_min,
    retard_moyen_tous_trains_arrivee    as retard_moyen_tous_trains_min,
    nb_train_retard_sup_15              as nb_trains_retard_sup_15,
    nb_train_retard_sup_30              as nb_trains_retard_sup_30,
    nb_train_retard_sup_60              as nb_trains_retard_sup_60,
    prct_cause_externe,
    prct_cause_infra,
    prct_cause_gestion_trafic,
    prct_cause_materiel_roulant,
    prct_cause_gestion_gare,
    prct_cause_prise_en_charge_voyageurs,
    extrait_le
from {{ source('silver', 'trajets_mensuels') }}
