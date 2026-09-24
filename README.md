# pipeline-qualite-donnees

[![Tests](https://github.com/eliasbabouche/NOM-DU-DEPOT/actions/workflows/tests.yml/badge.svg)](https://github.com/eliasbabouche/NOM-DU-DEPOT/actions/workflows/tests.yml)
[![Démo](https://img.shields.io/badge/démo-en%20ligne-brightgreen)](LIEN-DE-LA-DEMO)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/eliasbabouche/NOM-DU-DEPOT/blob/main/notebooks/01_restitution.ipynb)

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

## Licence

MIT — voir [LICENSE](LICENSE).

