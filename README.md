# Dashboard opérationnel COD

Application Streamlit locale pour analyser un export Excel CRM/ERP de commandes COD.

## Lancer

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Ce que le dashboard affiche

- Vue globale : reçues, confirmées nettes, annulées, préparation, envoyées, livrées, retours, CA livré et CA bloqué.
- Évolution : comparaison avec la période précédente de même durée (mêmes filtres) et courbes jour / semaine / mois des volumes, des taux clés et du CA livré cumulé.
- Confirmation : performance par personne affectée.
- Livraison & livreurs : KPI calculés uniquement sur les commandes réellement envoyées.
- Produits : décisions automatiques à pousser, surveiller, corriger ou échantillon faible.
- Wilayas & alertes : opportunités, zones à risque et recommandations prioritaires.
- Données nettoyées / export : aperçu sans colonnes sensibles par défaut et export Excel multi-feuilles.

## Règle métier importante

Les commandes en préparation ne sont jamais comptées dans la performance livreur. Une commande Yalidine en préparation reste un blocage interne.

## Structure

- `app.py` : point d'entrée Streamlit.
- `src/data_loader.py` : lecture Excel, mapping flexible des colonnes.
- `src/cleaning.py` : nettoyage texte, montants, dates, normalisations.
- `src/classification.py` : classification COD.
- `src/metrics.py` : agrégations et KPI.
- `src/alerts.py` : alertes décisionnelles.
- `src/trends.py` : évolution dans le temps et comparaison avec la période précédente.
- `src/ui.py` : interface Streamlit et exports.
- `tests/test_metrics.py` : tests unitaires métier.

## Tests

```bash
pytest
```
