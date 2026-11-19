import pandas as pd
import pytest

from src.alerts import DEFAULT_THRESHOLDS
from src.data_loader import prepare_dataframe
from src.health import BAD, GOOD, WARN, health_summary, reference_date, stuck_orders, verdict, vital_signs
from src.metrics import compute_global_metrics
from src.ui import build_metric_trend_figure, compute_trend, confirmation_funnel_counts, overall_text, stuck_orders_table, vital_sign_html


def build_df():
    rows = [
        # waiting for confirmation since Jan 1 (14 days before the last date) -> stuck
        {"Référence commande": "A", "Statut commande": "En confirmation", "Crée le": "2026-01-01", "Affectée à": "Sara"},
        # waiting for confirmation since Jan 14 (1 day) -> not stuck
        {"Référence commande": "B", "Statut commande": "En confirmation", "Crée le": "2026-01-14", "Affectée à": "Rayan"},
        # in preparation since confirmation on Jan 10 (5 days) -> stuck
        {"Référence commande": "C", "Statut commande": "En préparation", "Crée le": "2026-01-09", "Confirmée le": "2026-01-10", "Affectée à": "Rayan"},
        # in delivery since Jan 2 (13 days) -> stuck at ZR
        {"Référence commande": "D", "Statut commande": "En livraison", "Crée le": "2026-01-01", "Expédiée le": "2026-01-02", "Livreur": "ZR Express"},
        # in delivery since Jan 12 (3 days) -> not stuck
        {"Référence commande": "E", "Statut commande": "En livraison", "Crée le": "2026-01-11", "Expédiée le": "2026-01-12", "Livreur": "HHD 01"},
        # delivered: sets the last date of the file to Jan 15
        {"Référence commande": "F", "Statut commande": "Livrée", "Crée le": "2026-01-10", "Expédiée le": "2026-01-11", "Livrée le": "2026-01-15", "Livreur": "HHD 01"},
        {"Référence commande": "G", "Statut commande": "Annulée", "Crée le": "2026-01-10"},
        {"Référence commande": "H", "Statut commande": "En retour", "Crée le": "2026-01-03", "Expédiée le": "2026-01-04", "Livreur": "ZR Express"},
    ]
    for row in rows:
        row.setdefault("Affectée à", "Rayan")
        row.setdefault("Livreur", "")
        row.update({"Total commande": "1000", "Nom produit": "P1", "Wilaya": "Alger"})
    return prepare_dataframe(pd.DataFrame(rows))


def test_vital_signs_use_card_figures_and_sidebar_objectives():
    metrics = compute_global_metrics(build_df())
    signs = {s["key"]: s for s in vital_signs(metrics, DEFAULT_THRESHOLDS)}
    _, card_confirmation, _ = confirmation_funnel_counts(metrics)
    assert signs["confirmation"]["value"] == pytest.approx(card_confirmation)
    assert signs["delivery"]["value"] == pytest.approx(metrics["delivery_total_rate_on_sent"])
    assert signs["return"]["value"] == pytest.approx(metrics["return_rate_on_sent"])
    assert signs["cancellation"]["value"] == pytest.approx(metrics["cancellation_rate"])
    assert signs["delivery"]["objective"] == DEFAULT_THRESHOLDS["delivery_green"]
    assert signs["return"]["objective"] == DEFAULT_THRESHOLDS["return_orange"]


def test_verdict_levels():
    # higher is better: objective 70 %, alert 60 %
    assert verdict(0.75, 0.70, 0.60, True) == GOOD
    assert verdict(0.65, 0.70, 0.60, True) == WARN
    assert verdict(0.50, 0.70, 0.60, True) == BAD
    # lower is better: objective 10 %, alert 20 %
    assert verdict(0.08, 0.10, 0.20, False) == GOOD
    assert verdict(0.15, 0.10, 0.20, False) == WARN
    assert verdict(0.30, 0.10, 0.20, False) == BAD


def test_health_summary_and_text():
    signs = vital_signs(compute_global_metrics(build_df()), DEFAULT_THRESHOLDS)
    summary = health_summary(signs)
    assert sum(summary["counts"].values()) == 7
    assert summary["overall"] in {GOOD, WARN, BAD}
    text = overall_text(summary)
    for sign in summary["to_watch"]:
        assert sign["label"].split(" (")[0] in text
    assert text.count("Taux livré") <= 1
    good = health_summary([{"verdict": GOOD, "label": "x"}] * 7)
    assert overall_text(good).startswith("🟢 Tout va bien")


def test_vital_sign_html_has_objective_tick():
    signs = vital_signs(compute_global_metrics(build_df()), DEFAULT_THRESHOLDS)
    html = vital_sign_html(signs[1])
    assert "objectif ≥ 70.0 %" in html
    assert "Sur 100 colis expédiés" in html


def test_stuck_orders_by_step():
    df = build_df()
    today = reference_date(df)
    assert today == pd.Timestamp("2026-01-15")
    steps = {s["key"]: s for s in stuck_orders(df, today)}
    assert steps["confirmation"]["waiting"] == 2 and steps["confirmation"]["late"] == 1
    assert steps["confirmation"]["owners"] == [("Sara", 1)]
    assert steps["preparation"]["waiting"] == 1 and steps["preparation"]["late"] == 1
    assert list(steps["preparation"]["late_orders"]["jours"]) == [5]
    assert steps["delivery"]["waiting"] == 2 and steps["delivery"]["late"] == 1
    assert steps["delivery"]["owners"] == [("ZR Express", 1)]
    # waiting counts are the card figures
    metrics = compute_global_metrics(df)
    assert steps["confirmation"]["waiting"] == metrics["orders_in_confirmation"]
    assert steps["preparation"]["waiting"] == metrics["orders_preparation"]
    assert steps["delivery"]["waiting"] == metrics["orders_logistics"]


def test_stuck_orders_table_lists_late_orders_only():
    df = build_df()
    table = stuck_orders_table(stuck_orders(df, reference_date(df)))
    assert sorted(table["Commande"]) == ["A", "C", "D"]
    assert "Bloquée depuis (jours)" in table.columns


def test_trend_figure_draws_objective_and_average_lines():
    trend = compute_trend(build_df(), "Crée le", "Jour")
    fig = build_metric_trend_figure(trend, "taux_livraison_total", "rate", "line", True, "Jour", average=0.5, objective=0.7)
    assert len(fig.layout.shapes) == 2
    assert [a.text for a in fig.layout.annotations] == ["moyenne", "objectif"]
    assert fig.layout.yaxis.range[1] >= 0.7


def test_confirmation_rate_is_exactly_the_card_value():
    from src.trends import card_confirmation_rate
    from src.ui import displayed_reception_rates

    # 970 received, 41 in confirmation, 203 cancelled: raw 74.8 %, card 74.9 %
    metrics = {"orders_received": 970, "orders_in_confirmation": 41, "orders_cancelled": 203, "orders_confirmed_net": 767}
    card, _, _ = displayed_reception_rates(metrics, None)
    assert card_confirmation_rate(metrics) == card == 0.749
    assert vital_signs(metrics | {"delivery_total_rate_on_sent": None, "return_rate_on_sent": None, "cancellation_rate": 203 / 970}, DEFAULT_THRESHOLDS)[0]["value"] == card
    for df in [build_df()]:
        m = compute_global_metrics(df)
        assert card_confirmation_rate(m) == displayed_reception_rates(m, None)[0]


def test_average_delivery_days():
    from src.health import average_delivery_days

    # F: shipped Jan 11, delivered Jan 15 -> 4 days (the only delivered order)
    delay = average_delivery_days(build_df())
    assert delay == {"days": 4.0, "orders": 1, "without_dates": 0}
    assert average_delivery_days(build_df().iloc[0:0])["days"] is None


def test_finished_parcels_delivery_rate_matches_global_figure():
    from src.metrics import compute_livreur_metrics
    from src.rankings import pooled_rate

    df = build_df()
    metrics = compute_global_metrics(df)
    signs = {s["key"]: s for s in vital_signs(metrics, DEFAULT_THRESHOLDS)}
    # F delivered, H returned -> 1 / 2
    assert signs["delivery_finalized"]["value"] == metrics["delivery_finalized_rate"] == 0.5
    livreurs = compute_livreur_metrics(df)
    finished = livreurs.assign(colis_termines=livreurs["livrees"] + livreurs["retours"])
    assert pooled_rate(finished, "livrees", "colis_termines") == pytest.approx(metrics["delivery_finalized_rate"])


def test_confirmation_is_stuck_after_three_days():
    from src.health import STUCK_LIMIT_DAYS

    assert STUCK_LIMIT_DAYS == {"confirmation": 3, "preparation": 2, "delivery": 7}
    df = build_df()
    steps = {s["key"]: s for s in stuck_orders(df, pd.Timestamp("2026-01-04"))}
    # A created Jan 1 -> 3 days on Jan 4: not stuck yet (limit is "more than 3 days")
    assert steps["confirmation"]["late"] == 0
    steps = {s["key"]: s for s in stuck_orders(df, pd.Timestamp("2026-01-05"))}
    assert steps["confirmation"]["late"] == 1


def test_transformation_rates():
    from src.trends import net_transformation_rate
    from src.rankings import group_card_rates, pooled_rate

    df = build_df()
    metrics = compute_global_metrics(df)
    # 8 received, 1 cancelled (G), 1 delivered (F)
    assert metrics["orders_received"] == 8 and metrics["orders_cancelled"] == 1 and metrics["orders_delivered"] == 1
    assert metrics["transformation_real_rate"] == pytest.approx(1 / 8)  # brute: delivered / received
    assert net_transformation_rate(metrics) == pytest.approx(1 / 7)  # nette: delivered / (received - cancelled)
    signs = {s["key"]: s for s in vital_signs(metrics, DEFAULT_THRESHOLDS)}
    assert signs["transformation"]["value"] == pytest.approx(1 / 8)
    assert signs["transformation"]["objective"] == 0.40
    assert signs["net_transformation"]["value"] == pytest.approx(1 / 7)
    assert signs["net_transformation"]["objective"] == 0.50
    rates = group_card_rates(df, "Affectée à", "confirmatrice")
    assert pooled_rate(rates, "livrees", "commandes_recues") == pytest.approx(metrics["transformation_real_rate"])
    assert pooled_rate(rates, "livrees", "commandes_confirmees_nettes") == pytest.approx(net_transformation_rate(metrics))


def test_mobile_stuck_summary_card():
    from src.views.mobile_view import stuck_summary_card

    df = build_df()
    title, value, note, tone = stuck_summary_card(df, df)
    # A (confirmation), C (préparation), D (livraison) are stuck on Jan 15
    assert (title, value, tone) == ("Commandes bloquées", "3", "bad")
    assert "1 en attente de confirmation (> 3 j)" in note


def test_cockpit_shows_each_rate_once(monkeypatch):
    import src.views.cockpit as cockpit

    shown = []
    monkeypatch.setattr(cockpit.st, "markdown", lambda html, **_: shown.append(html))
    monkeypatch.setattr(cockpit.st, "columns", lambda n: [__import__("contextlib").nullcontext()] * n)
    df = build_df()
    context = {"selected_date_type": "Date de création", "start_date": pd.Timestamp("2026-01-08").date(), "end_date": pd.Timestamp("2026-01-15").date()}
    cockpit.render_cockpit(df, df, context, compute_global_metrics(df), {**DEFAULT_THRESHOLDS, "ad_cost_per_purchase": 0.0})
    page = "".join(shown)
    for title in ["⭐ Transformation brute<", "Multiplicateur CAC", "Taux confirmé<", "Taux livré<", "Sur colis terminés",
                  "Transformation nette<", "Taux retour<", "Taux annulé<", "Commandes reçues<"]:
        assert page.count(title) == 1, title
    # the two delivery rates share one card
    assert "Taux livré (sur" not in page


def test_multiplier_card_with_ad_cost():
    from src.views.cockpit import multiplier_card_html

    html = multiplier_card_html({"real": 2.35, "estimated": 2.06, "received": 970, "delivered": 413}, ad_cost=1.5)
    assert "× 2,35" in html and "× 2,06" in html and "3,53 €" in html  # 1,5 × 2,35 = 3,525
    assert "Vrai coût" not in multiplier_card_html({"real": 2.0, "estimated": None, "received": 2, "delivered": 1})
