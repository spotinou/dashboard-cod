from datetime import date

import pandas as pd
import pytest

from src.data_loader import prepare_dataframe
from src.metrics import compute_global_metrics
from src.trends import (
    TREND_CHARTS,
    auto_granularity,
    provisional_mask,
    trend_average,
    trend_reading,
    compute_period_comparison,
    compute_trend,
    previous_period,
)
from src.ui import (
    apply_filter_values,
    build_metric_trend_figure,
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
    assert auto_granularity(date(2026, 1, 1), date(2026, 1, 14)) == "Jour"
    assert auto_granularity(date(2026, 1, 1), date(2026, 1, 30)) == "Semaine"
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
    # Confirmation 100 % vs 66.7 % (card value, rounded like the card) -> +33.3 pts, good
    assert rows["confirmation_display_rate"]["previous"] == 0.667
    assert rows["confirmation_display_rate"]["delta"] == pytest.approx(0.333)
    assert rows["confirmation_display_rate"]["tone"] == "good"
    # Return rate 0 % vs 50 % -> going down, but 1 of the 3 parcels (33 %) is still
    # on the road: the delivery figures are provisional and not judged
    # Taux livré on finished parcels: 100 % vs 50 % -> up, but provisional (not judged)
    assert rows["delivery_finalized_rate"]["direction"] == "up"
    assert rows["delivery_finalized_rate"]["provisional"] is True
    assert rows["delivery_finalized_rate"]["tone"] == "neutral"
    assert rows["delivery_finalized_rate"]["in_transit_share"] == pytest.approx(1 / 3)
    assert rows["delivery_total_rate_on_sent"]["provisional"] is True
    assert rows["confirmation_display_rate"]["provisional"] is False
    assert [r["key"] for r in compute_period_comparison(current, previous)] == [
        "orders_received", "confirmation_display_rate", "delivery_total_rate_on_sent", "delivery_finalized_rate",
        "transformation_real_rate", "net_transformation_rate",
    ]


def test_period_comparison_judges_delivery_once_parcels_are_back():
    df = build_df()
    df = df[df["order_id"] != "F"]  # drop the parcel still on the road
    dates = pd.to_datetime(df["Crée le"]).dt.date
    current = compute_global_metrics(df[dates >= date(2026, 1, 3)])
    previous = compute_global_metrics(df[dates < date(2026, 1, 3)])
    rows = {row["key"]: row for row in compute_period_comparison(current, previous)}
    # Taux livré 100 % vs 50 % (same definition as the "Taux livré" card)
    assert rows["delivery_total_rate_on_sent"]["value"] == pytest.approx(current["delivery_total_rate_on_sent"])
    assert rows["delivery_total_rate_on_sent"]["delta"] == pytest.approx(0.5)
    assert rows["delivery_total_rate_on_sent"]["provisional"] is False
    assert rows["delivery_total_rate_on_sent"]["tone"] == "good"
    assert rows["delivery_finalized_rate"]["value"] == pytest.approx(current["delivery_finalized_rate"])
    assert rows["delivery_finalized_rate"]["tone"] == "good"


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


def test_trend_figures_one_metric_per_chart():
    trend = compute_trend(build_df(), "Crée le", "Jour")
    for key, _, _, kind, _, form, depends in TREND_CHARTS:
        fig = build_metric_trend_figure(trend, key, kind, form, depends, "Jour", average=trend_average(trend, key))
        assert fig is not None
        assert fig.layout.showlegend is False
        assert len(fig.layout.shapes) == 1  # the average line
    bars = build_metric_trend_figure(trend, "commandes_recues", "count", "bar", False)
    assert [trace.type for trace in bars.data] == ["bar"]
    assert list(bars.data[0].y) == [2, 1, 1, 2]
    rate = build_metric_trend_figure(trend, "taux_confirmation", "rate", "line", False)
    assert rate.layout.yaxis.tickformat == ".0%"
    assert build_metric_trend_figure(trend.head(1), "commandes_recues", "count", "bar", False) is None


def test_trend_flags_incomplete_and_in_transit_periods():
    df = build_df()
    trend = compute_trend(df, "Crée le", "Semaine", start=date(2026, 1, 1), end=date(2026, 1, 4))
    # The week of 2025-12-29 starts before the analysis window and ends after it
    assert bool(trend["periode_incomplete"].iloc[0]) is True
    daily = compute_trend(df, "Crée le", "Jour", start=date(2026, 1, 1), end=date(2026, 1, 4))
    assert not daily["periode_incomplete"].any()
    day4 = daily.set_index("periode").loc[pd.Timestamp("2026-01-04")]
    assert day4["colis_en_route"] == 1  # F is still "En livraison"
    assert day4["part_en_route"] == 0.5
    mask = provisional_mask(daily, depends_on_delivery=True)
    assert list(mask) == [False, False, False, True]
    assert not provisional_mask(daily, depends_on_delivery=False).any()


def test_rate_average_is_pooled_like_global_kpis():
    df = build_df()
    trend = compute_trend(df, "Crée le", "Jour")
    metrics = compute_global_metrics(df)
    assert trend_average(trend, "taux_livraison_finalisees") == pytest.approx(metrics["delivery_finalized_rate"])
    assert trend_average(trend, "taux_retour") == pytest.approx(metrics["return_rate_on_sent"])
    assert trend_average(trend, "commandes_recues") == pytest.approx(1.5)


def test_trend_reading_uses_last_reliable_period():
    trend = compute_trend(build_df(), "Crée le", "Jour", start=date(2026, 1, 1), end=date(2026, 1, 4))
    reading = trend_reading(trend, "taux_livraison_finalisees", "rate", True, True)
    # Jan 4 is provisional (parcel in transit), so the reading stops at Jan 3
    assert reading["last_period"] == pd.Timestamp("2026-01-03")
    assert reading["provisional_count"] == 1
    assert reading["last_value"] == 1.0
    assert reading["direction"] == "up" and reading["tone"] == "good"
    returns = trend_reading(trend, "taux_retour", "rate", False, True)
    assert returns["direction"] == "down" and returns["tone"] == "good"


def test_previous_period_partially_before_file_is_not_compared():
    df = build_df()
    # Current = Jan 3 -> Jan 4, previous = Jan 1 -> Jan 2: fully inside the file -> compared
    context = {"selected_date_type": "Date de création", "start_date": date(2026, 1, 3), "end_date": date(2026, 1, 4)}
    prev_df, _ = previous_period_frame(df, context)
    assert prev_df is not None
    # Current = Jan 2 -> Jan 4, previous = Dec 30 -> Jan 1: only 1 of 3 days in the file -> not compared
    context["start_date"] = date(2026, 1, 2)
    prev_df, window = previous_period_frame(df, context)
    assert prev_df is None and window == (date(2025, 12, 30), date(2026, 1, 1))


def test_trend_taux_livre_matches_the_card():
    df = build_df()
    trend = compute_trend(df, "Crée le", "Jour")
    metrics = compute_global_metrics(df)
    assert [spec[0] for spec in TREND_CHARTS] == [
        "taux_confirmation", "taux_livraison_total", "taux_livraison_finalisees",
        "taux_transformation_reel", "taux_transformation_nette", "commandes_recues",
    ]
    assert trend_average(trend, "taux_transformation_reel") == pytest.approx(metrics["transformation_real_rate"])
    assert trend_average(trend, "taux_transformation_nette") == pytest.approx(metrics["orders_delivered"] / metrics["orders_confirmed_net"])
    assert trend_average(trend, "taux_livraison_finalisees") == pytest.approx(metrics["delivery_finalized_rate"])
    assert trend_average(trend, "taux_livraison_total") == pytest.approx(metrics["delivery_total_rate_on_sent"])
    assert trend_average(trend, "taux_retour") == pytest.approx(metrics["return_rate_on_sent"])


def test_cac_multiplier_owner_example():
    from src.trends import cac_multiplier
    from src.ui import cac_multiplier_card_html

    # 100 received, 25 cancelled -> 75 confirmed; 50 delivered, 25 returned -> x 2
    metrics = {"orders_received": 100, "orders_cancelled": 25, "orders_in_confirmation": 0, "orders_delivered": 50,
               "delivery_finalized_rate": 50 / 75}
    mult = cac_multiplier(metrics)
    assert mult["real"] == pytest.approx(2.0)
    assert mult["estimated"] == pytest.approx(2.0)  # 1 / (75 % x 66.7 %)
    html = cac_multiplier_card_html(mult, ad_cost=1.0)
    assert "× 2,00" in html and "2,00 €" in html
    assert cac_multiplier({"orders_received": 10, "orders_delivered": 0})["real"] is None
    # real factor = 1 / taux de transformation brute
    df = build_df()
    m = compute_global_metrics(df)
    assert cac_multiplier(m)["real"] == pytest.approx(1 / m["transformation_real_rate"])
