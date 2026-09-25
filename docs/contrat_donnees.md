# Contrat de données

Ce document fixe ce que le pipeline **accepte en entrée** et ce qu'il **garantit en sortie**.
Chaque règle est vérifiée dans le code : une règle écrite ici sans test correspondant est un
défaut à corriger.

Les chiffres cités ont été mesurés sur l'export du 24 septembre 2026 (janvier 2018 → juin 2026,
12 544 lignes).

---

## 1. Source

| | |
|---|---|
| Jeu de données | [Régularité mensuelle TGV par liaisons](https://ressources.data.sncf.com/explore/dataset/regularite-mensuelle-tgv-aqst/) (SNCF Voyageurs, open data) |
| Identifiant | `regularite-mensuelle-tgv-aqst` |
| URL d'export | `https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/regularite-mensuelle-tgv-aqst/exports/csv` |
| Nature de l'export | **snapshot** : chaque téléchargement contient tout l'historique depuis janvier 2018 |
| Rythme de publication | mensuel, avec environ un mois de décalage |
| Licence | Licence Ouverte / Open Licence (Etalab) |

## 2. Principe : trois niveaux de réaction

Toutes les anomalies ne se valent pas. Le pipeline distingue :

| Niveau | Quand | Réaction |
|---|---|---|
| **Bloquant** | le fichier lui-même est illisible ou n'a pas la structure attendue | le pipeline s'arrête avec un message explicite ; rien n'est écrit en silver ni en gold |
| **Quarantaine** | une ligne isolée viole une règle métier | la ligne est écartée de silver, conservée dans une table de quarantaine avec le motif, et comptée dans le rapport d'exécution |
| **Avertissement** | un écart sans conséquence sur les chiffres (colonne en trop, séparateur différent mais sans ambiguïté) | le pipeline continue et le signale dans le rapport |

Garde-fou : **si plus de 2 % des lignes partent en quarantaine, l'exécution devient bloquante**.
Une anomalie isolée est une erreur de saisie ; une anomalie massive signale une source qui a
changé de format, et continuer produirait des chiffres faux.

## 3. Contrat d'entrée (fichier brut → bronze)

### 3.1 Format du fichier

| Règle | Attendu | Si non respecté |
|---|---|---|
| Encodage | UTF-8, avec ou sans BOM (lu en `utf-8-sig`) | **bloquant** — aucune tentative de deviner un autre encodage : un mauvais choix produirait des accents corrompus sans erreur |
| Séparateur | `;` | `,` ou tabulation reconnus sans ambiguïté (l'en-tête donne exactement les colonnes attendues) : **avertissement** ; sinon **bloquant** |
| Guillemets | champs contenant `;` ou un retour à la ligne entourés de `"` | lu par un lecteur CSV standard ; le nombre de lignes n'est jamais compté sur le fichier texte |
| En-tête | présent, première ligne | **bloquant** s'il manque |

### 3.2 Colonnes attendues

Les colonnes sont toujours lues **par leur nom, jamais par leur position**. Un changement
d'ordre est donc sans effet.

| Colonne | Type | Obligatoire | Règle |
|---|---|---|---|
| `date` | texte `AAAA-MM` | oui | mois valide, pas dans le futur |
| `service` | texte | oui | `National` ou `International` |
| `gare_depart` | texte | oui | non vide |
| `gare_arrivee` | texte | oui | non vide, différente de `gare_depart` |
| `duree_moyenne` | entier (min) | oui | ≥ 0 |
| `nb_train_prevu` | entier | oui | ≥ 0 |
| `nb_annulation` | entier | oui | ≥ 0 ; ≤ `nb_train_prevu` quand `nb_train_prevu` > 0 |
| `commentaire_annulation` | texte | non | aucune (vide à 100 % aujourd'hui) |
| `nb_train_depart_retard` | entier | oui | ≥ 0 |
| `retard_moyen_depart` | décimal (min) | oui | ≥ 0 |
| `retard_moyen_tous_trains_depart` | décimal (min) | oui | aucune (négatif possible : trains en avance) |
| `commentaire_retards_depart` | texte | non | aucune (vide à 100 % aujourd'hui) |
| `nb_train_retard_arrivee` | entier | oui | ≥ 0 ; ≤ `nb_train_prevu` |
| `retard_moyen_arrivee` | décimal (min) | oui | ≥ 0 |
| `retard_moyen_tous_trains_arrivee` | décimal (min) | oui | aucune (négatif possible) |
| `commentaires_retard_arrivee` | texte | non | aucune (rempli seulement en 2018-2019) |
| `nb_train_retard_sup_15` | entier | oui | ≥ 0 ; ≤ `nb_train_retard_arrivee` |
| `retard_moyen_trains_retard_sup15` | décimal (min) | oui | aucune |
| `nb_train_retard_sup_30` | entier | oui | ≥ 0 ; ≤ `nb_train_retard_sup_15` |
| `nb_train_retard_sup_60` | entier | oui | ≥ 0 |
| `prct_cause_externe` | décimal (%) | oui | entre 0 et 100 |
| `prct_cause_infra` | décimal (%) | oui | entre 0 et 100 |
| `prct_cause_gestion_trafic` | décimal (%) | oui | entre 0 et 100 |
| `prct_cause_materiel_roulant` | décimal (%) | oui | entre 0 et 100 |
| `prct_cause_gestion_gare` | décimal (%) | oui | entre 0 et 100 |
| `prct_cause_prise_en_charge_voyageurs` | décimal (%) | oui | entre 0 et 100 |

- **Colonne obligatoire absente ou renommée** : **bloquant**, avec le nom de la colonne
  manquante et, si possible, la colonne inconnue qui pourrait la remplacer.
- **Colonne en plus** : **avertissement** ; elle est archivée en bronze mais ignorée ensuite.
- **Type incorrect** (du texte dans une colonne numérique) : la ligne part en **quarantaine**.
- **Règle de valeur violée** (colonne « Règle » ci-dessus) : la ligne part en **quarantaine**.

### 3.3 Clé d'unicité

```
date + gare_depart + gare_arrivee + service
```

Une ligne décrit **une liaison, pour un mois, pour un type de service**. Toute clé en double est
**bloquante** : on ne dédoublonne jamais en silence, car choisir laquelle des deux lignes
garder reviendrait à inventer la donnée.

Pourquoi `service` en fait partie : de juillet à septembre 2025, la SNCF a publié 14 liaisons
en deux lignes (National et International). Sans `service`, ces 42 lignes apparaissent en
double ; ce ne sont pas des doublons mais deux moitiés d'une même liaison.

### 3.4 Règles sur le fichier entier

| Règle | Seuil | Si non respecté | Ce que ça protège |
|---|---|---|---|
| Couverture de l'historique | le nouvel export contient **au moins tous les mois** du précédent | **bloquant** | une republication partielle ou tronquée qui ferait disparaître des mois |
| Volume par mois | au moins 100 lignes pour chaque mois présent | **bloquant** | un mois publié à moitié (observé : 121 à 135) |
| Continuité | aucun mois manquant entre le premier et le dernier | **bloquant** | un trou dans la série |

## 4. Anomalies connues de la source

Mesurées sur l'export de référence. Elles sont traitées par les règles ci-dessus, et
documentées ici pour que personne ne les découvre deux fois.

| Anomalie | Lignes | Période | Traitement |
|---|---:|---|---|
| `nb_train_retard_sup_30` **négatif** (jusqu'à −44) | 43 | janvier → mars 2025 | quarantaine |
| `retard_moyen_arrivee` négatif (moyenne des trains en retard) | 2 | novembre 2019 | quarantaine |
| `nb_train_retard_sup_15` > `nb_train_retard_arrivee` (plus de trains à +15 min que de trains en retard) | 31 | 2018 → 2020 | quarantaine |
| `nb_train_retard_sup_30` > `nb_train_retard_sup_15` | 3 | — | quarantaine |
| `nb_train_prevu` = 0 et `duree_moyenne` = 0 | 73 | 2020 (crise sanitaire) | **conservées** : liaison non assurée ce mois-là ; exclues des taux en gold (division par zéro) |
| `nb_annulation` > `nb_train_prevu` | 63 | 2020, toutes avec `nb_train_prevu` = 0 | conservées (même cas que ci-dessus) |
| Somme des `prct_cause_*` nulle alors qu'il y a des retards | 78 | — | conservées ; causes considérées comme non renseignées |
| Découpage National / International | 42 | juillet → septembre 2025 | normal, couvert par la clé ; agrégé en gold |

Taux de quarantaine sur l'export de référence, toutes règles combinées (une ligne peut en
violer plusieurs) : **79 lignes sur 12 544, soit 0,63 %**, sous le seuil de 2 %.

**Ambiguïté non résolue** : `nb_train_retard_sup_60` dépasse `nb_train_retard_sup_30` sur 354
lignes. Si les deux colonnes étaient emboîtées (« plus de 30 min » contient « plus de 60 min »),
c'est impossible ; la documentation de la source ne tranche pas. Aucune règle n'est donc posée
entre ces deux colonnes, et aucun indicateur gold ne s'appuie sur leur différence.

## 5. Contrat de sortie

### 5.1 Bronze

- Un dossier par téléchargement : `bronze/extrait_le=AAAA-MM-JJ/`, contenant le fichier reçu
  **tel quel**, plus un fichier de métadonnées (URL, date et heure, empreinte SHA-256, taille).
- Jamais modifié, jamais écrasé.
- Si l'empreinte est identique à celle du dernier millésime, rien n'est ajouté : la source n'a
  pas changé.

### 5.2 Silver

Table `trajets_mensuels`, en Parquet partitionné par `mois`.

- Mêmes colonnes que l'entrée, avec les types du tableau 3.2, sauf :
  - `date` est renommée **`mois`** : c'est une période mensuelle, pas une date ;
  - les deux colonnes de commentaires vides à 100 % ne sont pas reprises (elles restent en
    bronze) ;
  - ajout de **`extrait_le`** : le millésime bronze d'origine, pour tracer chaque ligne jusqu'à
    son fichier source.
- Construite à partir du **dernier millésime** uniquement.
- Clé unique garantie : `mois + gare_depart + gare_arrivee + service`.
- Les lignes rejetées vont dans `trajets_mensuels_quarantaine`, avec les colonnes d'origine plus
  `motif_rejet`.

### 5.3 Gold

Détaillé à l'étape dbt. Engagements dès maintenant :

- une ligne par **liaison et par mois**, National et International additionnés ;
- les retards moyens combinés sont **pondérés par le nombre de trains**, jamais moyennés
  directement ;
- les taux (annulation, retard) ne sont calculés que si `nb_train_prevu` > 0.

## 6. Engagements du pipeline

- **Idempotence** : relancer le pipeline sur les mêmes données produit exactement les mêmes
  tables, sans doublon.
- **Écriture atomique** : chaque table est écrite dans un emplacement temporaire puis mise en
  place en une seule opération. Un échec au milieu laisse l'état précédent intact, jamais un
  état à moitié écrit.
- **Rapport d'exécution** à chaque passage : lignes lues, lignes en quarantaine par motif,
  avertissements, millésime traité.
