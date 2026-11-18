"""Compact view for a phone: only the key figures, the rest on demand."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..health import reference_date, stuck_orders
from ..trends import cac_multiplier
from .components import mini_card
from .formatting import format_count
from .overview import big_rate_card_html, cac_multiplier_card_html, owner_kpi_sections

# Cards of the "Parcours COD" kept in the compact view, by title.
MOBILE_CARDS = ["Taux confirmé", "Taux livré", "Taux de transformation nette"]


def stuck_summary_card(df: pd.DataFrame, loaded_df: pd.DataFrame) -> tuple[str, str, str, str] | None:
    today = reference_date(loaded_df)
    if today is None:
        return None
    steps = stuck_orders(df, today)
    if not steps:
        return None
    total = sum(s["late"] for s in steps)
    note = "\n".join(f"{format_count(s['late'])} {s['title'].split(' (')[0].lower()} (> {s['limit_days']} j)" for s in steps)
    return ("Commandes bloquées", format_count(total), note, "bad" if total else "good")


def render_mobile_summary(df: pd.DataFrame, loaded_df: pd.DataFrame, metrics: dict, thresholds: dict[str, float]) -> None:
    """Key figures stacked for a small screen. Same values as the full view."""
    journey = {card[0]: card for card in owner_kpi_sections(metrics, thresholds)}
    st.markdown(cac_multiplier_card_html(cac_multiplier(metrics), thresholds.get("ad_cost_per_purchase", 0.0)), unsafe_allow_html=True)
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.markdown(big_rate_card_html(journey["Taux de transformation brute"], thresholds.get("transformation_green")), unsafe_allow_html=True)
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    cards = [journey[t] for t in MOBILE_CARDS if t in journey]
    stuck = stuck_summary_card(df, loaded_df)
    if stuck:
        cards.append(stuck)
    for title, value, note, tone in cards:
        mini_card(title, str(value), note, tone=tone)
