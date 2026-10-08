-- Test generique maison : toute valeur non nulle doit etre comprise entre deux bornes.
-- Comme tout test dbt, la requete renvoie les lignes FAUTIVES : zero ligne = test reussi.
-- Usage dans un .yml :  - entre_bornes: {arguments: {min_value: 0, max_value: 1}}

{% test entre_bornes(model, column_name, min_value, max_value) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} < {{ min_value }}
   or {{ column_name }} > {{ max_value }}

{% endtest %}
