import pandas as pd
import pytest

from src.data_loader import prepare_dataframe
from src.flows import LOST, PENDING, SECURED, funnel_stages, revenue_waterfall, waterfall_summary
from src.metrics import compute_global_metrics
from src.ui import amount_totals, build_revenue_waterfall_figure, confirmation_funnel_counts, funnel_html


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


def test_waterfall_closes_on_delivered_revenue():
    df = build_df()
    metrics = compute_global_metrics(df)
    steps = revenue_waterfall(metrics, amount_totals(df, metrics))
    labels = [s["label"] for s in steps]
    assert labels == ["CA des commandes reçues", "Annulées", "Encore en confirmation", "En préparation", "En cours de livraison", "Retours / échecs", "CA livré"]
    assert steps[0]["value"] == 22500
    assert [-s["value"] for s in steps[1:-1]] == [1000, 1500, 2000, 6000, 5000]
    assert steps[-1]["value"] == metrics["ca_delivered"] == 7000
    # the last deduction ends exactly where the delivered revenue bar ends
    assert steps[-2]["start"] == pytest.approx(steps[-1]["end"])
    assert steps[0]["value"] + sum(s["value"] for s in steps[1:-1]) == pytest.approx(steps[-1]["value"])


def test_waterfall_summary_by_tone():
    df = build_df()
    metrics = compute_global_metrics(df)
    summary = waterfall_summary(revenue_waterfall(metrics, amount_totals(df, metrics)))
    assert summary[LOST][0] == 6000  # cancelled + returns
    assert summary[PENDING][0] == 9500  # confirmation + preparation + in delivery
    assert summary[SECURED][0] == 7000
    assert sum(summary[tone][1] for tone in (LOST, PENDING, SECURED)) == pytest.approx(1.0)


def test_waterfall_shows_remainder_instead_of_hiding_it():
    metrics = {"ca_delivered": 1000, "ca_in_confirmation": 0, "ca_preparation": 0, "ca_logistics": 0, "ca_returned_failed": 500}
    amounts = {"ca_total_orders": 2000, "ca_confirmed": 2000}
    steps = revenue_waterfall(metrics, amounts)
    assert [s["label"] for s in steps] == ["CA des commandes reçues", "Retours / échecs", "Autres / non classées", "CA livré"]
    assert steps[2]["value"] == -500


def test_flow_rendering_helpers():
    df = build_df()
    metrics = compute_global_metrics(df)
    html = funnel_html(funnel_stages(metrics))
    assert "Commandes reçues" in html and "1 annulées" in html and "sortent ici" in html
    fig = build_revenue_waterfall_figure(revenue_waterfall(metrics, amount_totals(df, metrics)))
    assert fig.data[0].orientation == "h"
    assert fig.data[0].text[1].startswith("− 1 000 DA")
    assert build_revenue_waterfall_figure([]) is None
