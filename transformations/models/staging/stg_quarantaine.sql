-- Lignes ecartees par la validation : on ne garde que ce qui sert a les compter.
-- Gold s'en sert pour signaler les mois ou des liaisons manquent au calcul.

select
    cast("date" as varchar)  as mois,
    gare_depart,
    gare_arrivee,
    service,
    motif_rejet
from {{ source('silver', 'trajets_mensuels_quarantaine') }}
