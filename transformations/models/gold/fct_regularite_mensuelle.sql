-- Table de FAITS du modele en etoile : une ligne par liaison et par mois (le "grain").
-- Elle ne contient que des cles vers les dimensions (id_liaison, mois) et des mesures ;
-- les descriptions (noms des gares, annee, libelle du mois) vivent dans les dimensions.
-- Les taux ne sont calcules que si des trains etaient prevus (2020 : liaisons suspendues).

select
    id_liaison_mois,
    id_liaison,                     -- cle etrangere vers dim_liaisons
    mois,                           -- cle etrangere vers dim_mois
    nb_lignes_source,
    nb_trains_prevus,
    nb_annulations,
    nb_trains_circules,
    nb_trains_retard_arrivee,
    nb_trains_retard_sup_15,
    duree_moyenne_min,
    retard_moyen_tous_trains_min,
    retard_moyen_trains_en_retard_min,
    nb_annulations / nullif(nb_trains_prevus, 0)              as taux_annulation,
    nb_trains_retard_arrivee / nullif(nb_trains_circules, 0)  as taux_retard_arrivee,
    nb_trains_retard_sup_15 / nullif(nb_trains_circules, 0)   as taux_retard_sup_15
from {{ ref('int_liaisons_mensuelles') }}
