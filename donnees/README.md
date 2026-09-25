# Données

Ce dossier est vide sur GitHub : les données ne sont jamais versionnées. Le pipeline le
remplit en trois couches :

| Dossier | Contenu |
|---|---|
| `bronze/extrait_le=.../` | l'export SNCF reçu, octet pour octet, avec ses métadonnées (URL, horodatage, empreinte SHA-256) |
| `silver/` | les données validées et typées, en Parquet partitionné par mois |
| `gold/` | les agrégats prêts à lire |

Source : [Régularité mensuelle TGV par liaisons](https://ressources.data.sncf.com/explore/dataset/regularite-mensuelle-tgv-aqst/)
(SNCF Voyageurs, Licence Ouverte).
