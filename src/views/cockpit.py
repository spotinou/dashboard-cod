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
from .formatting import format_count, format_date, help_icon, html_text, pct
from .health_view import CARD_STYLE, overall_text, vital_sign_html
from .overview import format_factor

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
    return (
        f'<div style="{CARD_STYLE}">'
        '<div style="font-size:14px;font-weight:800;color:#0f172a">\U0001f6d2 Commandes re\u00e7ues</div>'
        f'<div style="font-size:28px;font-weight:850;color:#0f172a;margin-top:4px;line-height:1.1">{format_count(metrics.get("orders_received", 0))}</div>'
        f"{delta_html(row)}</div>"
    )


def multiplier_card_html(mult: dict, ad_cost: float = 0.0) -> str:
    """Acquisition cost multiplier, same size as the other cards."""
    real, estimated = mult.get("real"), mult.get("estimated")
    lines = f"{format_count(mult['received'])} re\u00e7ues \u00f7 {format_count(mult['delivered'])} livr\u00e9es"
    if estimated is not None:
        lines += f"<br>Estim\u00e9 colis arriv\u00e9s : <b>{html_text(format_factor(estimated))}</b>"
    if ad_cost and real is not None:
        cost = f"{ad_cost * real:.2f}".replace(".", ",") + " \u20ac"
        lines += f"<br>Vrai co\u00fbt client : <b>{html_text(cost)}</b>"
    return (
        f'<div style="{CARD_STYLE};border-left:5px solid #7c3aed;background:#faf5ff">'
        f'<div style="font-size:14px;font-weight:800;color:#0f172a">\U0001f4b8 Multiplicateur CAC{help_icon("multiplicateur")}</div>'
        f'<div style="font-size:28px;font-weight:850;color:#0f172a;margin-top:4px;line-height:1.1">{html_text(format_factor(real))}</div>'
        f'<div style="font-size:12px;color:#475569;margin-top:6px;line-height:1.45">{lines}</div></div>'
    )


def finished_parcels_html(sign: dict | None, row: dict | None, delay: dict) -> str:
    """Second line of the "Taux livré" card: the same rate on finished parcels, and the delivery time."""
    parts = []
    if sign is not None:
        dot = {"good": "\U0001f7e2", "warn": "\U0001f7e0", "bad": "\U0001f534"}.get(sign["verdict"], "\u26aa")
        delta = ""
        if row and row.get("delta") is not None:
            color = DELTA_COLORS.get(row.get("tone"), DELTA_COLORS["neutral"])
            delta = f' <span style="color:{color};font-weight:700">{html_text(format_delta(row))}</span>'
        parts.append(f"{dot} Sur colis termin\u00e9s : <b>{html_text(pct(sign['value']))}</b>{delta}")
    if delay.get("days") is not None:
        parts.append(f"\U0001f69a D\u00e9lai moyen : <b>{delay['days']:.1f} j</b>".replace(".", ","))
    if not parts:
        return ""
    return f'<div style="font-size:12px;color:#334155;margin-top:6px;line-height:1.5;border-top:1px dashed #e2e8f0;padding-top:5px">{"<br>".join(parts)}</div>'


def render_cockpit(df: pd.DataFrame, loaded_df: pd.DataFrame, date_context: dict, metrics: dict, thresholds: dict[str, float]) -> None:
    try:
        rows, note = comparison_rows(loaded_df, date_context, metrics)
        signs = vital_signs(metrics, thresholds)
        by_key = {s["key"]: s for s in signs}

        def card(key: str, **kwargs) -> str:
            return vital_sign_html(by_key[key], kwargs.pop("extra", "") or delta_html(rows.get(COMPARISON_KEY[key])), show_sentence=False, **kwargs)

        delivery_extra = delta_html(rows.get(COMPARISON_KEY["delivery"])) + finished_parcels_html(
            by_key.get("delivery_finalized"), rows.get(COMPARISON_KEY["delivery_finalized"]), average_delivery_days(df)
        )
        cards = [
            card("transformation", highlight="#16a34a", title="\u2b50 Transformation brute"),
            multiplier_card_html(cac_multiplier(metrics), thresholds.get("ad_cost_per_purchase", 0.0)),
            card("confirmation"),
            card("delivery", extra=delivery_extra, title="Taux livr\u00e9"),
            card("net_transformation", title="Transformation nette"),
            card("return"),
            card("cancellation"),
            received_card_html(metrics, rows.get("orders_received")),
        ]
        st.markdown(
            '<div class="section-tight">Parcours COD</div>'
            f'<div class="section-subtitle">Trait noir = ton objectif (r\u00e9glable dans la barre lat\u00e9rale). {html_text(note)}</div>'
            f'<div style="font-size:14px;font-weight:800;color:#0f172a;margin:2px 0 8px">{html_text(overall_text(health_summary(signs)))}</div>'
            f'<div style="display:flex;gap:12px;flex-wrap:wrap">{"".join(cards)}</div>',
            unsafe_allow_html=True,
        )
    except Exception as exc:  # never let the new section break the dashboard
        st.warning(f"Parcours COD indisponible pour ce fichier : {exc}")
