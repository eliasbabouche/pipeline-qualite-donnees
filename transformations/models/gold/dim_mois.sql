-- DIMENSION calendrier : une ligne par mois present dans les donnees.
-- Decrit le "quand" des faits : annee, trimestre, libelle lisible pour les graphiques.

with mois as (

    select distinct mois
    from {{ ref('int_liaisons_mensuelles') }}

)

select
    mois,
    cast(left(mois, 4) as integer)                      as annee,
    cast(right(mois, 2) as integer)                     as numero_mois,
    (cast(right(mois, 2) as integer) + 2) // 3          as trimestre,
    case cast(right(mois, 2) as integer)
        when 1 then 'janvier'   when 2 then 'février'   when 3 then 'mars'
        when 4 then 'avril'     when 5 then 'mai'       when 6 then 'juin'
        when 7 then 'juillet'   when 8 then 'août'      when 9 then 'septembre'
        when 10 then 'octobre'  when 11 then 'novembre' when 12 then 'décembre'
    end || ' ' || left(mois, 4)                         as libelle
from mois
