# Dashboard opérationnel COD

Application Streamlit locale pour analyser un export Excel CRM/ERP de commandes COD.

## Lancer

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Ce que le dashboard affiche

- Vue globale : reçues, confirmées nettes, annulées, préparation, envoyées, livrées, retours, CA livré et CA bloqué.
- Entonnoir et argent : entonnoir reçues → confirmées → expédiées → livrées avec ce qui sort à chaque étape, et cascade du CA reçu jusqu'au CA livré (perdu / en attente / livré).
- Évolution : comparaison avec la période précédente de même durée (mêmes filtres) et courbes jour / semaine / mois des volumes, des taux clés et du CA livré cumulé.
- Confirmation : performance par personne affectée.
- Livraison & livreurs : KPI calculés uniquement sur les commandes réellement envoyées.
- Produits : décisions automatiques à pousser, surveiller, corriger ou échantillon faible.
- Wilayas & alertes : opportunités, zones à risque et recommandations prioritaires.
- Données nettoyées / export : aperçu sans colonnes sensibles par défaut et export Excel multi-feuilles.

## Règle métier importante

Les commandes en préparation ne sont jamais comptées dans la performance livreur. Une commande Yalidine en préparation reste un blocage interne.

## Structure

Calculs (aucun affichage) :

- `app.py` : point d'entrée Streamlit.
- `src/data_loader.py` : lecture Excel, mapping flexible des colonnes.
- `src/cleaning.py` : nettoyage texte, montants, dates, normalisations.
- `src/classification.py` : classification COD.
- `src/metrics.py` : agrégations et KPI.
- `src/validation.py` : contrôles de cohérence des chiffres.
- `src/alerts.py` : alertes décisionnelles.
- `src/flows.py` : entonnoir COD et cascade du chiffre d'affaires.
- `src/rankings.py` : classements (livreurs, confirmatrices, produits, wilayas).
- `src/trends.py` : évolution dans le temps et comparaison avec la période précédente.

Affichage (`src/views/`, un fichier par thème) :

- `app.py` : lancement de l'app, chargement du fichier, calcul des tableaux (`compute_dashboard_data`).
- `tabs.py` : une fonction par onglet (`render_global_tab`, `render_confirmation_tab`…).
- `filters.py` : période d'analyse, type de date et filtres de la barre latérale.
- `analysis.py` : analyses du dashboard (conseils produits, croisements, résumés, export Excel).
- `overview.py` : cartes KPI de la Vue globale.
- `evolution.py`, `ranking_charts.py`, `flow_charts.py` : graphiques d'évolution, classements, entonnoir et cascade.
- `charts.py` : anciens graphiques en barres (conservés).
- `components.py` : briques réutilisables (cartes, titres, tableaux).
- `formatting.py` : formats (DA, %, dates), couleurs et préparation des tableaux.
- `styles.py` : CSS du dashboard.

`src/ui.py` réexporte tout (compatibilité : `from src.ui import ...` fonctionne toujours).

Tests : `tests/` (un fichier par module).

## Tests

```bash
pytest
```
