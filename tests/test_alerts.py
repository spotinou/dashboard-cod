import pandas as pd

from src.alerts import DEFAULT_THRESHOLDS, generate_alerts


def test_delivery_alert_uses_delivery_total_rate_on_sent():
    alerts = generate_alerts(
        {
            "preparation_blockage_rate": 0.0,
            "cancellation_rate": 0.0,
            "delivery_finalized_rate": 1.0,
            "delivery_total_rate_on_sent": 0.5,
            "return_rate_on_sent": 0.0,
            "orders_preparation": 0,
        },
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(columns=["commandes_envoyees", "taux_retour", "taux_livraison_total"]),
        pd.DataFrame(columns=["taux_confirmation", "taux_retour"]),
        {"delivery_orange": 0.65},
    )
    delivery_alert = [alert for alert in alerts if alert["titre"] == "Livraison faible"]
    assert delivery_alert
    assert "sur expédiées" in delivery_alert[0]["message"]


def test_livreur_alert_uses_total_delivery_rate_column():
    alerts = generate_alerts(
        {
            "preparation_blockage_rate": 0.0,
            "cancellation_rate": 0.0,
            "delivery_total_rate_on_sent": 1.0,
            "return_rate_on_sent": 0.0,
            "orders_preparation": 0,
        },
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame({"livreur": ["Yalidine"], "commandes_envoyees": [10], "taux_retour": [0.0], "taux_livraison_total": [0.4]}),
        pd.DataFrame(columns=["taux_confirmation", "taux_retour"]),
        {"delivery_orange": 0.65, "volume_sent": 5},
    )
    assert any(alert["titre"] == "Livreur problématique" for alert in alerts)



def test_default_sidebar_rate_thresholds_are_lowered_by_five_points():
    assert DEFAULT_THRESHOLDS["confirmation_green"] == 0.70
    assert DEFAULT_THRESHOLDS["confirmation_orange"] == 0.60
    assert DEFAULT_THRESHOLDS["cancellation_orange"] == 0.15
    assert DEFAULT_THRESHOLDS["cancellation_red"] == 0.25
    assert DEFAULT_THRESHOLDS["delivery_green"] == 0.70
    assert DEFAULT_THRESHOLDS["delivery_orange"] == 0.60
    assert DEFAULT_THRESHOLDS["return_orange"] == 0.25
    assert DEFAULT_THRESHOLDS["return_red"] == 0.35
    assert DEFAULT_THRESHOLDS["preparation_orange"] == 0.05
    assert DEFAULT_THRESHOLDS["preparation_red"] == 0.15
