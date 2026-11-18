"""Parcours COD: every rate shown once, with its objective, verdict and change vs the previous period.

Replaces three blocks that repeated the same rates (former Parcours COD cards,
"Santé de mon business" and "Comparaison avec la période précédente").
Values come from the same functions as before; only the layout changes.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..health import average_delivery_days, health_summary, vital_signs
from ..metrics import compute_global_metrics
from ..trends import cac_multiplier, compute_period_comparison
from .evolution import format_delta, format_metric_value, previous_period_frame
from .formatting import format_count, format_date, html_text
from .health_view import delivery_time_html, overall_text, vital_sign_html
from .overview import big_rate_card_html, cac_multiplier_card_html, owner_kpi_sections

# vital sign key -> comparison key
COMPARISON_KEY = {
    "confirmation": "confirmation_display_rate",
    "delivery": "delivery_total_rate_on_sent",
    "delivery_finalized": "delivery_finalized_rate",
    "transformation": "transformation_real_rate",
    "net_transformation": "net_transformation_rate",
    "return": "return_rate_on_sent",
    "cancellation": "cancellation_rate",
}
DELTA_COLORS = {"good": "#166534", "bad": "#991b1b", "neutral": "#475569"}


def delta_html(row: dict | None) -> str:
    """One short line: change vs the previous period (or why there is none)."""
    if not row or row.get("delta") is None:
        return ""
    color = DELTA_COLORS.get(row.get("tone"), DELTA_COLORS["neutral"])
    text = f"{format_delta(row)} vs avant ({format_metric_value(row['previous'], row['kind'])})"
    if row.get("provisional"):
        text += " · ⏳ provisoire"
    return f'<div style="font-size:12px;font-weight:700;color:{color};margin-top:6px">{html_text(text)}</div>'


def comparison_rows(loaded_df: pd.DataFrame, date_context: dict, metrics: dict) -> tuple[dict, str]:
    """Comparison rows by key, and a one-line note about the previous period."""
    prev_df, window = previous_period_frame(loaded_df, date_context)
    if window is None:
        return {}, ""
    if prev_df is None:
        return {}, "Pas de comparaison : la période précédente n'est pas (entièrement) dans le fichier."
    rows = compute_period_comparison(metrics, compute_global_metrics(prev_df))
    note = f"Écarts comparés à la même durée juste avant ({format_date(window[0])} → {format_date(window[1])}). Vert = mieux, rouge = moins bien."
    return {row["key"]: row for row in rows}, note


def received_card_html(metrics: dict, row: dict | None) -> str:
    from .health_view import CARD_STYLE

    return (
        f'<div style="{CARD_STYLE}">'
        '<div style="font-size:14px;font-weight:800;color:#0f172a">\U0001f6d2 Commandes reçues</div>'
        f'<div style="font-size:28px;font-weight:850;color:#0f172a;margin-top:4px;line-height:1.1">{format_count(metrics.get("orders_received", 0))}</div>'
        f"{delta_html(row)}</div>"
    )


def render_cockpit(df: pd.DataFrame, loaded_df: pd.DataFrame, date_context: dict, metrics: dict, thresholds: dict[str, float]) -> None:
    try:
        rows, note = comparison_rows(loaded_df, date_context, metrics)
        signs = vital_signs(metrics, thresholds)
        by_key = {s["key"]: s for s in signs}
        st.markdown(
            '<div class="section-tight">Parcours COD</div>'
            f'<div class="section-subtitle">Chaque taux une seule fois. Trait noir = ton objectif (barre latérale, rubrique Seuils). {html_text(note)}</div>'
            f'<div style="font-size:15px;font-weight:800;color:#0f172a;margin:2px 0 8px">{html_text(overall_text(health_summary(signs)))}</div>',
            unsafe_allow_html=True,
        )
        # 1. The key result and what it costs in ads
        brute_card = next(card for card in owner_kpi_sections(metrics, thresholds) if card[0] == "Taux de transformation brute")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(big_rate_card_html(brute_card, thresholds.get("transformation_green"), delta_html(rows.get("transformation_real_rate"))), unsafe_allow_html=True)
        with col2:
            st.markdown(cac_multiplier_card_html(cac_multiplier(metrics), thresholds.get("ad_cost_per_purchase", 0.0)), unsafe_allow_html=True)
        # 2. Every other rate, once
        order = ["confirmation", "delivery", "delivery_finalized", "net_transformation", "return", "cancellation"]
        cards = [vital_sign_html(by_key[k], delta_html(rows.get(COMPARISON_KEY[k])), show_sentence=False) for k in order if k in by_key]
        cards.append(delivery_time_html(average_delivery_days(df)))
        cards.append(received_card_html(metrics, rows.get("orders_received")))
        st.markdown(f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:12px">{"".join(cards)}</div>', unsafe_allow_html=True)
    except Exception as exc:  # never let the new section break the dashboard
        st.warning(f"Parcours COD indisponible pour ce fichier : {exc}")
