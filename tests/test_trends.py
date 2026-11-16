from datetime import date

import pandas as pd
import pytest

from src.data_loader import prepare_dataframe
from src.metrics import compute_global_metrics
from src.trends import (
    auto_granularity,
    compute_period_comparison,
    compute_trend,
    previous_period,
)
from src.ui import (
    apply_filter_values,
    build_cumulative_ca_figure,
    build_trend_rate_figure,
    build_trend_volume_figure,
    comparison_cards,
    format_delta,
    previous_period_frame,
)


def order(ref, status, created, total="1000", **extra):
    row = {
        "Référence commande": ref,
        "Statut commande": status,
        "Crée le": created,
        "Total commande": total,
        "Nom produit": extra.pop("produit", "P1"),
        "Wilaya": "Alger",
        "Livreur": "HHD 01",
        "Affectée à": "Rayan",
    }
    row.update(extra)
    return row


def build_df():
    return prepare_dataframe(
        pd.DataFrame(
            [
                # Period 1 : 2026-01-01 -> 2026-01-02
                order("A", "Livrée", "2026-01-01", "3000", **{"Expédiée le": "2026-01-01", "Livrée le": "2026-01-03"}),
                order("B", "Annulée", "2026-01-01"),
                order("C", "En retour", "2026-01-02", "2000", **{"Expédiée le": "2026-01-02"}),
                # Period 2 : 2026-01-03 -> 2026-01-04
                order("D", "Livrée", "2026-01-03", "4000", **{"Expédiée le": "2026-01-03", "Livrée le": "2026-01-05"}),
                order("E", "Encaissée", "2026-01-04", "5000", produit="P2", **{"Expédiée le": "2026-01-04", "Encaissée le": "2026-01-06"}),
                order("F", "En livraison", "2026-01-04", "1000", **{"Expédiée le": "2026-01-04"}),
            ]
        )
    )


def test_trend_matches_global_metrics_totals():
    df = build_df()
    trend = compute_trend(df, "Crée le", "Jour")
    metrics = compute_global_metrics(df)
    assert list(trend["periode"].dt.date) == [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)]
    assert trend["commandes_recues"].sum() == metrics["orders_received"]
    assert trend["livrees"].sum() == metrics["orders_delivered"]
    assert trend["retours"].sum() == metrics["orders_returned_failed"]
    assert trend["ca_livre"].sum() == metrics["ca_delivered"]
    assert trend["ca_livre_cumule"].iloc[-1] == metrics["ca_delivered"]


def test_trend_rates_per_period():
    trend = compute_trend(build_df(), "Crée le", "Jour").set_index("periode")
    day1 = trend.loc[pd.Timestamp("2026-01-01")]
    assert day1["commandes_recues"] == 2
    assert day1["taux_confirmation"] == 0.5
    assert day1["taux_livraison_finalisees"] == 1.0
    day4 = trend.loc[pd.Timestamp("2026-01-04")]
    assert day4["livrees"] == 1
    assert day4["taux_retour"] == 0.0


def test_trend_weekly_and_monthly_grouping():
    df = build_df()
    weekly = compute_trend(df, "Crée le", "Semaine")
    assert weekly["commandes_recues"].sum() == 6
    # 2026-01-01 is a Thursday: Jan 1-4 fall in the week starting Monday 2025-12-29
    assert list(weekly["periode"].dt.date) == [date(2025, 12, 29)]
    monthly = compute_trend(df, "Crée le", "Mois")
    assert list(monthly["periode"].dt.date) == [date(2026, 1, 1)]


def test_trend_handles_missing_column_and_empty_frame():
    df = build_df()
    assert compute_trend(df, "Colonne absente").empty
    assert compute_trend(df.iloc[0:0], "Crée le").empty
    assert compute_trend(df, None).empty


def test_previous_period_same_length():
    assert previous_period(date(2026, 1, 3), date(2026, 1, 4)) == (date(2026, 1, 1), date(2026, 1, 2))
    assert previous_period(date(2026, 1, 10), date(2026, 1, 10)) == (date(2026, 1, 9), date(2026, 1, 9))
    assert previous_period(None, date(2026, 1, 10)) is None


def test_auto_granularity():
    assert auto_granularity(date(2026, 1, 1), date(2026, 1, 30)) == "Jour"
    assert auto_granularity(date(2026, 1, 1), date(2026, 4, 30)) == "Semaine"
    assert auto_granularity(date(2025, 1, 1), date(2026, 1, 1)) == "Mois"


def test_period_comparison_deltas_and_tones():
    df = build_df()
    dates = pd.to_datetime(df["Crée le"]).dt.date
    current = compute_global_metrics(df[dates >= date(2026, 1, 3)])
    previous = compute_global_metrics(df[dates < date(2026, 1, 3)])
    rows = {row["key"]: row for row in compute_period_comparison(current, previous)}

    assert rows["orders_received"]["delta"] == 0.0
    assert rows["orders_received"]["direction"] == "flat"
    # Confirmation 100 % vs 66.7 % -> +33.3 pts, good
    assert rows["confirmation_display_rate"]["delta"] == pytest.approx(1 / 3)
    assert rows["confirmation_display_rate"]["tone"] == "good"
    # Return rate 0 % vs 50 % -> going down is good
    assert rows["return_rate_on_sent"]["direction"] == "down"
    assert rows["return_rate_on_sent"]["tone"] == "good"
    # CA livré 9000 vs 3000 -> +200 %
    assert rows["ca_delivered"]["delta"] == pytest.approx(2.0)


def test_period_comparison_without_previous_data():
    rows = compute_period_comparison(compute_global_metrics(build_df()), None)
    assert all(row["delta"] is None and row["tone"] == "neutral" for row in rows)
    cards = comparison_cards(rows, None)
    assert len(cards) == len(rows)
    assert all("Pas de données" in note for _, _, note, _ in cards)


def test_format_delta():
    assert format_delta({"delta": 0.0321, "direction": "up", "kind": "rate"}) == "▲ +3,2 pts"
    assert format_delta({"delta": -0.25, "direction": "down", "kind": "money"}) == "▼ -25,0 %"
    assert format_delta({"delta": None}) == "Pas de comparaison"


def test_previous_period_frame_reapplies_filters():
    df = build_df()
    context = {
        "selected_date_type": "Date de création",
        "start_date": date(2026, 1, 3),
        "end_date": date(2026, 1, 4),
        "applied_filter_values": [("Nom produit", ["P1"])],
    }
    prev_df, window = previous_period_frame(df, context)
    assert window == (date(2026, 1, 1), date(2026, 1, 2))
    assert set(prev_df["order_id"]) == {"A", "B", "C"}

    context["start_date"], context["end_date"] = date(2026, 1, 1), date(2026, 1, 4)
    prev_df, window = previous_period_frame(df, context)
    assert prev_df is None and window == (date(2025, 12, 28), date(2025, 12, 31))


def test_apply_filter_values_ignores_missing_columns():
    df = build_df()
    assert len(apply_filter_values(df, [("Colonne absente", ["x"])])) == len(df)
    assert set(apply_filter_values(df, [("Nom produit", ["P2"])])["order_id"]) == {"E"}


def test_trend_figures():
    trend = compute_trend(build_df(), "Crée le", "Jour")
    volume = build_trend_volume_figure(trend)
    assert [trace.name for trace in volume.data] == ["Reçues", "Confirmées", "Livrées", "Retours / échecs"]
    rates = build_trend_rate_figure(trend, thresholds={"delivery_green": 0.7})
    assert rates.layout.yaxis.tickformat == ".0%"
    assert len(rates.layout.shapes) == 1
    ca = build_cumulative_ca_figure(trend)
    assert list(ca.data[1].y)[-1] == 12000
    assert build_trend_volume_figure(trend.head(1)) is None
