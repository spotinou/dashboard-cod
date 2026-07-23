from __future__ import annotations

from typing import Any

import pandas as pd


DEFAULT_THRESHOLDS = {
    "confirmation_green": 0.70,
    "confirmation_orange": 0.60,
    "cancellation_orange": 0.15,
    "cancellation_red": 0.25,
    "delivery_green": 0.70,
    "delivery_orange": 0.60,
    "return_orange": 0.10,
    "return_red": 0.20,
    "preparation_orange": 0.05,
    "preparation_red": 0.15,
    "volume_product": 10,
    "volume_sent": 5,
}


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def _add(alerts: list[dict[str, str]], niveau: str, titre: str, message: str, action: str) -> None:
    alerts.append({"niveau": niveau, "titre": titre, "message": message, "action": action})


def generate_alerts(
    global_metrics: dict[str, Any],
    product_metrics: pd.DataFrame,
    wilaya_metrics: pd.DataFrame,
    livreur_metrics: pd.DataFrame,
    confirmation_metrics: pd.DataFrame,
    thresholds: dict[str, float] | None = None,
) -> list[dict[str, str]]:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    alerts: list[dict[str, str]] = []

    prep_rate = global_metrics.get("preparation_blockage_rate")
    if prep_rate is not None and prep_rate > t["preparation_orange"]:
        level = "danger" if prep_rate > t["preparation_red"] else "warning"
        _add(
            alerts,
            level,
            "Blocage interne",
            f"{global_metrics['orders_preparation']} commandes confirmées ne sont pas encore envoyées.",
            "Vérifier stock, préparation, emballage et dispatch. Ce n'est pas un problème livreur.",
        )

    cancel_rate = global_metrics.get("cancellation_rate")
    if cancel_rate is not None and cancel_rate > t["cancellation_orange"]:
        level = "danger" if cancel_rate > t["cancellation_red"] else "warning"
        _add(
            alerts,
            level,
            "Annulation élevée",
            f"Taux d'annulation : {_pct(cancel_rate)}.",
            "Revoir qualité des leads, prix, frais de livraison, page produit et script d'appel.",
        )

    delivery_rate = global_metrics.get("delivery_total_rate_on_sent")
    if delivery_rate is not None and delivery_rate < t["delivery_orange"]:
        _add(
            alerts,
            "danger",
            "Livraison faible",
            f"Taux livraison sur expédiées : {_pct(delivery_rate)}.",
            "Analyser les livreurs, wilayas faibles, suivi client et qualité de confirmation.",
        )

    return_rate = global_metrics.get("return_rate_on_sent")
    if return_rate is not None and return_rate > t["return_orange"]:
        level = "danger" if return_rate > t["return_red"] else "warning"
        _add(
            alerts,
            level,
            "Retours élevés",
            f"Taux de retour sur envoyées : {_pct(return_rate)}.",
            "Identifier produit, wilaya et livreur avant d'augmenter le budget.",
        )

    for _, row in product_metrics.head(10).iterrows():
        if row.get("decision_auto") == "À pousser":
            _add(alerts, "success", "Produit à pousser", f"{row['produit']} confirme et se livre bien.", "Augmenter prudemment le budget sur les wilayas fortes.")
            break
    for _, row in product_metrics.head(20).iterrows():
        if row.get("decision_auto") in {"À surveiller", "À corriger"}:
            _add(alerts, "warning", "Produit à surveiller", f"{row['produit']} perd trop après expédition ou confirme mal.", "Vérifier promesse, prix, ciblage, confirmation et SAV.")
            break

    for _, row in wilaya_metrics.iterrows():
        if row.get("decision_auto") == "À pousser":
            _add(alerts, "success", "Wilaya à pousser", f"{row['wilaya']} a une bonne qualité de livraison.", "Prioriser cette wilaya pour les produits qui performent.")
            break
    for _, row in wilaya_metrics.iterrows():
        if row.get("decision_auto") in {"À surveiller", "À corriger"}:
            _add(alerts, "warning", "Wilaya à réduire/surveiller", f"{row['wilaya']} présente un risque livraison élevé.", "Réduire le volume ou renforcer le suivi client.")
            break

    bad_livreurs = livreur_metrics[
        (livreur_metrics["commandes_envoyees"] >= t["volume_sent"])
        & (
            (livreur_metrics["taux_retour"].fillna(0) > t["return_red"])
            | (livreur_metrics["taux_livraison_total"].fillna(1) < t["delivery_orange"])
        )
    ]
    if not bad_livreurs.empty:
        row = bad_livreurs.iloc[0]
        _add(alerts, "warning", "Livreur problématique", f"Vérifier {row['livreur']} sur ses wilayas faibles.", "Comparer les wilayas et isoler les zones à risque.")

    bad_conf = confirmation_metrics[
        (confirmation_metrics["taux_confirmation"].fillna(1) < t["confirmation_orange"])
        | (confirmation_metrics["taux_retour"].fillna(0) > t["return_red"])
    ]
    if not bad_conf.empty:
        row = bad_conf.iloc[0]
        _add(alerts, "warning", "Confirmation à revoir", f"Revoir le script ou la qualification pour {row['confirmatrice']}.", "Contrôler timing d'appel, objections et clients faibles confirmés.")

    return alerts[:10]
