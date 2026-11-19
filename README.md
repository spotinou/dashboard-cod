# Dashboard opérationnel COD

Application Streamlit locale pour analyser un export Excel CRM/ERP de commandes COD.

## Réglages par défaut

- Période affichée à l'ouverture d'un fichier : 30 derniers jours.
- Objectifs : confirmé ≥ 70 %, livré ≥ 70 %, transformation brute ≥ 40 %, transformation nette ≥ 50 %, retour ≤ 25 %, annulé ≤ 15 % (modifiables dans la barre latérale).

## Définitions

- Taux de transformation brute = livrées ÷ reçues (sur 100 commandes reçues, combien sont livrées).
- Taux de transformation nette = livrées ÷ (reçues − annulées) : même chose sans les annulées (faux numéros, doublons, refus).

## Connexion à l'API EcoManager (recommandé)

Le dashboard lit les commandes directement depuis EcoManager, sans export Excel.

1. Dans EcoManager, ouvre la page « Configuration de la boutique » et copie ton token API.
2. Sur share.streamlit.io, ouvre ton app → Settings → Secrets, colle ceci et enregistre :

   ```toml
   [[ecomanager.shops]]
   name = "Maison Luxelle"
   token = "TOKEN_BOUTIQUE_1"
   base_url = "https://maisonluxelle.ecomanager.dz"

   [[ecomanager.shops]]
   name = "ELBARAKA"
   token = "TOKEN_BOUTIQUE_2"
   base_url = "https://ADRESSE-BOUTIQUE-2.ecomanager.dz"
   ```

   Un bloc `[[ecomanager.shops]]` par boutique. Les commandes de toutes les boutiques sont additionnées ;
   le filtre « Boutique » de la barre latérale permet de les voir séparément.

3. L'app redémarre : choisis « API EcoManager » dans la barre latérale.

Le token n'est jamais écrit dans le code ni sur GitHub. Les commandes sont gardées en mémoire 15 minutes
(bouton « Rafraîchir maintenant » pour forcer). La lecture respecte les limites de l'API (50 appels / minute) ;
65 jours d'historique ≈ 100 appels ≈ 2 minutes la première fois. Le fichier Excel reste disponible en secours.

En local : même contenu dans `.streamlit/secrets.toml` (ignoré par git).

## Lancer

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Ce que le dashboard affiche

- Santé de mon business : taux confirmé, taux livré (sur expédiées et sur colis terminés), taux retour et taux annulé comparés à tes objectifs (seuils de la barre latérale), plus le délai moyen de livraison.
- À traiter aujourd'hui : commandes bloquées trop longtemps en confirmation (> 3 j), en préparation (> 2 j) ou en livraison (> 7 j), avec qui les détient et la liste.
- Vue globale : reçues, confirmées nettes, annulées, préparation, envoyées, livrées, retours, CA livré et CA bloqué.
- Où sont mes commandes : toutes les commandes reçues réparties en livrées / en cours / perdues, avec le détail.
- Comparaison avec la période précédente et évolution : taux confirmé, taux livré (sur expédiées / sur colis terminés), commandes reçues.
- Classements : confirmatrices (taux confirmé, taux livré), livreurs (taux livré sur expédiées et sur colis terminés), produits (taux retour, CA livré).
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
- `src/ecomanager.py` : lecture des commandes depuis l'API EcoManager (même format que l'export Excel).
- `src/data_loader.py` : lecture Excel, mapping flexible des colonnes.
- `src/cleaning.py` : nettoyage texte, montants, dates, normalisations.
- `src/classification.py` : classification COD.
- `src/metrics.py` : agrégations et KPI.
- `src/validation.py` : contrôles de cohérence des chiffres.
- `src/alerts.py` : alertes décisionnelles.
- `src/health.py` : santé (taux vitaux vs objectifs) et commandes bloquées.
- `src/flows.py` : répartition des commandes (livrées / en cours / perdues).
- `src/rankings.py` : classements (livreurs, confirmatrices, produits, wilayas).
- `src/trends.py` : évolution dans le temps et comparaison avec la période précédente.

Affichage (`src/views/`, un fichier par thème) :

- `app.py` : lancement de l'app, chargement du fichier, calcul des tableaux (`compute_dashboard_data`).
- `tabs.py` : une fonction par onglet (`render_global_tab`, `render_confirmation_tab`…).
- `filters.py` : période d'analyse, type de date et filtres de la barre latérale.
- `analysis.py` : analyses du dashboard (conseils produits, croisements, résumés, export Excel).
- `overview.py` : cartes KPI de la Vue globale.
- `health_view.py` : « Santé de mon business » et « À traiter aujourd'hui ».
- `evolution.py`, `ranking_charts.py`, `flow_charts.py` : évolution et comparaison, classements, « Où sont mes commandes ».
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
