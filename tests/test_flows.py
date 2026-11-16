import pandas as pd
import pytest

from src.data_loader import prepare_dataframe
from src.flows import funnel_stages, order_status_split
from src.metrics import compute_global_metrics
from src.ui import confirmation_funnel_counts, order_status_cards_html


def build_df():
    rows = [
        {"Référence commande": "A", "Statut commande": "Annulée", "Total commande": "1000"},
        {"Référence commande": "B", "Statut commande": "En confirmation", "Total commande": "1500"},
        {"Référence commande": "C", "Statut commande": "En préparation", "Total commande": "2000", "Confirmée le": "2026-01-01"},
        {"Référence commande": "D", "Statut commande": "Livrée", "Expédiée le": "2026-01-01", "Livrée le": "2026-01-03", "Total commande": "3000"},
        {"Référence commande": "E", "Statut commande": "Encaissée", "Expédiée le": "2026-01-01", "Encaissée le": "2026-01-03", "Total commande": "4000"},
        {"Référence commande": "F", "Statut commande": "En retour", "Expédiée le": "2026-01-01", "Total commande": "5000"},
        {"Référence commande": "G", "Statut commande": "En livraison", "Expédiée le": "2026-01-01", "Total commande": "6000"},
    ]
    for row in rows:
        row.update({"Crée le": "2026-01-01", "Nom produit": "P1", "Wilaya": "Alger", "Livreur": "HHD 01", "Affectée à": "Rayan"})
    return prepare_dataframe(pd.DataFrame(rows))


def test_funnel_matches_parcours_cards():
    metrics = compute_global_metrics(build_df())
    stages = funnel_stages(metrics)
    confirmed, _, _ = confirmation_funnel_counts(metrics)
    assert [s["value"] for s in stages] == [metrics["orders_received"], confirmed, metrics["orders_sent"], metrics["orders_delivered"]]
    assert [s["value"] for s in stages] == [7, 5, 4, 2]
    assert stages[-1]["share_of_received"] == pytest.approx(metrics["transformation_real_rate"])
    assert stages[3]["step_rate"] == pytest.approx(metrics["delivery_total_rate_on_sent"])


def test_funnel_losses_add_up():
    stages = funnel_stages(compute_global_metrics(build_df()))
    assert stages[0]["loss_to_next"] == 2
    assert dict(stages[0]["loss_breakdown"]) == {"annulées": 1, "encore en confirmation": 1}
    assert dict(stages[1]["loss_breakdown"]) == {"en préparation (pas encore expédiées)": 1}
    assert dict(stages[2]["loss_breakdown"]) == {"retours / échecs": 1, "encore en livraison": 1}
    for stage in stages[:-1]:
        assert sum(count for _, count in stage["loss_breakdown"]) == stage["loss_to_next"]
    assert stages[-1]["loss_to_next"] is None


def test_funnel_shows_unexplained_gap_as_autres():
    metrics = compute_global_metrics(build_df())
    metrics["orders_returned_failed"] = 0  # breakdown now explains only 1 of the 2 missing parcels
    stages = funnel_stages(metrics)
    assert dict(stages[2]["loss_breakdown"]) == {"encore en livraison": 1, "autres": 1}


def test_order_status_split_adds_up_to_orders_received():
    metrics = compute_global_metrics(build_df())
    split = order_status_split(metrics)
    assert split["received"] == metrics["orders_received"] == 7
    assert split["delivered"]["count"] == metrics["orders_delivered"] == 2
    assert dict(split["in_progress"]["detail"]) == {"en confirmation": 1, "en préparation": 1, "en livraison": 1}
    assert dict(split["lost"]["detail"]) == {"annulées": 1, "retours": 1}
    total = split["delivered"]["count"] + split["in_progress"]["count"] + split["lost"]["count"]
    assert total == split["received"]
    assert split["delivered"]["share"] + split["in_progress"]["share"] + split["lost"]["share"] == pytest.approx(1.0)
    assert split["delivered"]["share"] == pytest.approx(metrics["transformation_real_rate"])


def test_order_status_split_keeps_unexplained_orders_in_progress():
    metrics = compute_global_metrics(build_df())
    metrics["orders_returned_failed"] = 0  # 1 shipped parcel now unexplained
    split = order_status_split(metrics)
    assert dict(split["in_progress"]["detail"])["autres"] == 1
    assert split["delivered"]["count"] + split["in_progress"]["count"] + split["lost"]["count"] == split["received"]


def test_order_status_cards_html():
    html = order_status_cards_html(order_status_split(compute_global_metrics(build_df())))
    assert "Livrées" in html and "En cours" in html and "Perdues" in html
    assert "1 annulées" in html and "1 en livraison" in html
