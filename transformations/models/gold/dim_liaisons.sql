-- DIMENSION liaisons : une ligne par liaison (gare de depart -> gare d'arrivee).
-- Decrit le "qui" des faits ; deduite des donnees, jamais saisie a la main.

select
    id_liaison,
    gare_depart,
    gare_arrivee,
    min(mois)           as premier_mois,
    max(mois)           as dernier_mois,
    count(*)            as nb_mois_publies
from {{ ref('int_liaisons_mensuelles') }}
group by id_liaison, gare_depart, gare_arrivee
