# pipeline-qualite-donnees

[![Tests](https://github.com/eliasbabouche/pipeline-qualite-donnees/actions/workflows/tests.yml/badge.svg)](https://github.com/eliasbabouche/pipeline-qualite-donnees/actions/workflows/tests.yml)
[![Démo](https://img.shields.io/badge/démo-en%20ligne-brightgreen)](LIEN-DE-LA-DEMO)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/eliasbabouche/pipeline-qualite-donnees/blob/main/notebooks/01_restitution.ipynb)

> Pipeline de données mensuel en couches bronze/silver/gold sur la régularité des TGV : ingestion idempotente, validation pandera, dbt, Dagster

<!--
  Ordre imposé : le résultat AVANT la méthode. Un lecteur donne 20 secondes à ce fichier.
  Remplacer chaque section, puis supprimer ces commentaires.
-->

## Résultat

<!--
  Un résultat NUANCÉ et chiffré, pas un slogan. « 9 villes sur 10, mais résultat contrasté
  sur les maisons, avec deux exceptions » est crédible ; « les prix explosent » ne l'est pas.
  Les chiffres cités ici doivent être EXACTEMENT ceux du notebook et du dashboard.
-->

![Aperçu](docs/apercu.png)

**Démo en ligne** : <lien Streamlit Cloud ou Hugging Face Spaces>

**Notebook de restitution** : [`notebooks/01_restitution.ipynb`](notebooks/01_restitution.ipynb)
— lisible directement sur GitHub, graphiques compris.

## Données

| | |
|---|---|
| Source | <nom + lien> |
| Millésime | <version figée, ex. 2025-12 — jamais « latest »> |
| Volume | <nombre de lignes / poids> |
| Période | <plage temporelle couverte> |
| Licence | <Licence Ouverte / CC-BY / …> |

Les données brutes ne sont pas versionnées. Pour les récupérer :

```bash
python src/telecharger_donnees.py
```

### Entonnoir du nettoyage

<!--
  Le tableau qui montre combien de lignes survivent à chaque filtre. C'est la preuve
  visible du travail de nettoyage, et le garde-fou contre une perte massive non vue.
-->

| Étape | Lignes restantes | % du départ |
|---|---:|---:|
| Données brutes | | 100 % |
| <filtre 1> | | |
| <filtre 2> | | |
| **Retenu pour l'analyse** | | |

## Méthode

1. <étape>
2. <étape>
3. <étape>

## Deux choix de méthode qui changent le résultat

<!--
  Les réponses d'entretien, écrites en AFFIRMATIONS à puces, pas en questions.
  Prendre les deux décisions qui, si on les avait prises autrement, auraient donné
  un résultat différent. C'est ce qu'un recruteur technique va creuser.
-->

**<Le premier choix>**

- <ce qui a été décidé, et pourquoi>
- <ce que donnerait l'autre option, chiffré si possible>

**<Le second choix>**

- <idem>

## Limites connues

- <biais des données, période non couverte, hypothèse fragile>

## Ce qui a été difficile, et ce que j'en retiens

<!--
  Section courte et honnête. Elle vaut autant que le code : elle montre qu'on a
  rencontré le réel, pas suivi un tutoriel.
-->

- <la difficulté, comment elle a été résolue, ce qu'elle a appris>

## Exécution

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
pytest
```

## Structure

```
app.py        point d'entrée de l'application (à la RACINE : sinon l'import de src échoue)
src/          code métier, une responsabilité par module
tests/        tests unitaires
notebooks/    restitution : importe depuis src/, ne contient pas de logique métier
donnees/      brut/ et traite/ non versionnés ; reference/ et agrege/ versionnés (petits)
```

Le code vit dans `src/` et reste testable ; le notebook importe depuis `src/` et raconte
l'histoire. Ses sorties sont volontairement conservées dans le fichier pour que les
graphiques s'affichent sur GitHub sans rien exécuter.

## Questions fréquentes

<details>
<summary><b>Pourquoi la clé d'unicité inclut-elle la colonne <code>service</code> ?</b></summary>

J'ai d'abord supposé qu'une ligne était identifiée par le mois, la gare de départ et la gare
d'arrivée. En le vérifiant, j'ai trouvé 42 lignes qui violaient cette règle, toutes sur juillet,
août et septembre 2025 : pendant ces trois mois, la SNCF a découpé certaines liaisons en deux
lignes, trafic national et trafic international, avant de revenir au format habituel. Ce
n'étaient pas des doublons mais deux moitiés d'une même liaison : Dijon → Paris Lyon en
juillet 2025, c'est 186 trains « International » plus 220 « National ».

Sans cette vérification, le pipeline aurait soit échoué sans explication, soit, pire, dédoublonné
en silence et retiré environ 7 000 trains des statistiques. La clé
`date + gare_depart + gare_arrivee + service` (zéro conflit sur 12 544 lignes) est donc écrite
dans le contrat de données, et un test d'unicité fait échouer le pipeline au lieu de corriger en
douce.

</details>

<details>
<summary><b>Qu'est-ce que l'exploration manuelle de la source a changé au code ?</b></summary>

Quatre constats, chacun avec une conséquence directe :

- **Le fichier commence par un BOM UTF-8.** Il est lu en `utf-8-sig` ; sinon la première colonne
  s'appelle `﻿date` et tout accès à `date` échoue.
- **La colonne `date` est un mois (`2025-07`), pas une date.** Elle reste une période mensuelle
  et sert de clé de partition ; la convertir en date inventerait un « 1er du mois » absent des
  données.
- **Les commentaires contiennent des retours à la ligne entre guillemets.** Le fichier fait
  15 062 lignes physiques pour 12 544 lignes de données : les lignes ne se comptent jamais à la
  main, seulement via un lecteur CSV qui gère les guillemets.
- **Chaque export contient tout l'historique depuis 2018.** C'est un *snapshot*, pas un *delta* :
  chaque téléchargement est archivé tel quel en bronze, et silver est reconstruit à partir du
  plus récent.

</details>

<details>
<summary><b>Pourquoi certaines anomalies arrêtent le pipeline et d'autres non ?</b></summary>

Parce qu'une anomalie sur le fichier et une anomalie sur une ligne ne disent pas la même chose.
Le [contrat de données](docs/contrat_donnees.md) distingue trois niveaux :

- **Bloquant** quand c'est la structure qui casse : encodage illisible, colonne absente ou
  renommée, clé en double, mois disparus de l'historique. Continuer produirait des chiffres faux
  sur tout le jeu de données : le pipeline s'arrête avec un message qui nomme le problème.
- **Quarantaine** quand une ligne isolée est incohérente : la ligne est écartée, conservée avec
  son motif de rejet, et comptée dans le rapport. Exemple réel : de janvier à mars 2025, la
  source publie 43 nombres de trains **négatifs** (jusqu'à −44). Bloquer tout le pipeline pour
  ça rendrait l'historique inexploitable ; les laisser passer fausserait les moyennes.
- **Avertissement** quand l'écart est sans conséquence : colonnes dans un ordre différent,
  séparateur changé mais sans ambiguïté.

Le garde-fou qui relie les deux premiers niveaux : au-delà de 2 % de lignes en quarantaine, le
pipeline bloque, parce qu'une anomalie massive n'est plus une erreur de saisie mais un
changement de format. Aujourd'hui, 79 lignes sur 12 544 sont écartées, soit 0,63 %.

</details>

<details>
<summary><b>Comment l'ingestion garantit-elle qu'on peut la relancer sans risque ?</b></summary>

Par deux propriétés, chacune prouvée par un test.

**Idempotence : relancer ne duplique rien.** Chaque export téléchargé est résumé par son
empreinte SHA-256, enregistrée dans les métadonnées du millésime. Au passage suivant, le
pipeline compare l'empreinte du nouveau téléchargement à celle du dernier millésime : identique,
il n'écrit rien ; différente, il archive un nouveau millésime sans toucher aux précédents.
J'ai d'abord vérifié que l'export SNCF est déterministe (trois téléchargements successifs, même
empreinte) : sinon chaque passage aurait semblé nouveau et l'idempotence par empreinte aurait
été impossible.

**Atomicité : un échec ne laisse jamais un état à moitié écrit.** Un millésime est écrit dans
un dossier temporaire, puis renommé en une seule opération : il existe entièrement ou pas du
tout. Le fichier de métadonnées est écrit en dernier et sert de certificat de complétude. Si le
processus est tué en plein milieu, le dossier temporaire restant est supprimé au lancement
suivant. Les tests simulent un disque plein au moment du renommage et une interruption brutale,
puis vérifient que bronze ne contient rien de partiel.

Bronze conserve le CSV d'origine plutôt qu'une conversion en Parquet : un fichier illisible doit
pouvoir être archivé, justement pour prouver ce que la source a envoyé.

</details>

## Licence

MIT — voir [LICENSE](LICENSE).

