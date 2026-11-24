"""Parcours COD: the order journey in big numbers (orders received, confirmed, cancelled, shipped,
delivered, returned), each with its rate, base, objective and the value of the previous period.

Every figure comes from compute_global_metrics (same values as before); only the layout changes.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..health import BAD, GOOD, WARN, health_summary, vital_signs
from ..metrics import compute_global_metrics
from ..trends import cac_multiplier, compute_period_comparison, exclusive_confirmed, net_transformation_rate
from .evolution import format_metric_value, previous_period_frame
from .formatting import format_count, format_date, help_icon, html_text, pct
from .health_view import CARD_STYLE
from .overview import format_factor

# vital sign key -> comparison key (kept for other modules and tests)
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
# Verdict badges: words only, no coloured dots.
VERDICT_BADGE = {
    GOOD: ("Objectif atteint", "#dcfce7", "#166534"),
    WARN: ("Proche de l'objectif", "#fef3c7", "#92400e"),
    BAD: ("Sous l'objectif", "#fee2e2", "#991b1b"),
}


def comparison_rows(loaded_df: pd.DataFrame, date_context: dict, metrics: dict) -> tuple[dict, str, dict | None]:
    """Comparison rows by key, a one-line note, and the previous period's metrics (or None)."""
    prev_df, window = previous_period_frame(loaded_df, date_context)
    if window is None:
        return {}, "", None
    if prev_df is None:
        return {}, "Pas de comparaison : la période précédente n'est pas (entièrement) dans les données.", None
    previous = compute_global_metrics(prev_df)
    rows = compute_period_comparison(metrics, previous)
    note = f"« Avant » = même durée juste avant ({format_date(window[0])} → {format_date(window[1])})."
    return {row["key"]: row for row in rows}, note, previous


def gauge_html(sign: dict | None, value=None) -> str:
    """Progress bar with the rate written inside; colour = verdict, black tick = objective."""
    if sign is not None and value is None:
        value = sign["value"]
    ok = value is not None and not pd.isna(value)
    width = max(min(float(value), 1.0), 0.0) * 100 if ok else 0.0
    fill = {GOOD: "#16a34a", WARN: "#f59e0b", BAD: "#dc2626"}.get((sign or {}).get("verdict"), "#64748b")
    tick = ""
    if sign is not None:
        tick = f'<div style="position:absolute;left:{sign["objective"] * 100:.1f}%;top:-3px;width:2px;height:28px;background:#0f172a"></div>'
    label = html_text(pct(value)) if ok else "–"
    return (
        '<div style="position:relative;height:22px;background:#eef2f7;border-radius:999px;margin:10px 0 2px">'
        f'<div style="width:{width:.1f}%;min-width:44px;height:22px;background:{fill};border-radius:999px;'
        f'display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:800">{label}</div>{tick}</div>'
    )


def flow_card_html(title: str, big: str, detail: str = "", sign: dict | None = None, extra: str = "",
                   accent: str | None = None, background: str | None = None, rate=None) -> str:
    style = CARD_STYLE + (f";border-left:5px solid {accent}" if accent else "") + (f";background:{background}" if background else "")
    bar = gauge_html(sign, rate) if sign is not None or rate is not None else ""
    return (
        f'<div style="{style}">'
        f'<div style="font-size:14px;font-weight:800;color:#0f172a">{html_text(title)}{help_icon(title)}</div>'
        f'<div style="font-size:30px;font-weight:850;color:#0f172a;line-height:1.1;margin-top:4px">{html_text(big)}</div>'
        f'<div style="font-size:12.5px;color:#334155;margin-top:2px">{detail}</div>'
        f"{bar}{extra}</div>"
    )


def received_card_html(metrics: dict, row: dict | None = None) -> str:
    return flow_card_html("Commandes reçues", format_count(metrics.get("orders_received", 0)), "Base de la période")


def multiplier_card_html(mult: dict, ad_cost: float = 0.0) -> str:
    """Acquisition cost multiplier, same size as the other cards."""
    real, estimated = mult.get("real"), mult.get("estimated")
    detail = f"{format_count(mult['received'])} reçues ÷ {format_count(mult['delivered'])} livrées"
    extra = ""
    if estimated is not None:
        extra += f'<div style="font-size:12px;color:#475569;margin-top:6px">Estimé quand tous les colis seront arrivés : <b>{html_text(format_factor(estimated))}</b></div>'
    if ad_cost and real is not None:
        cost = f"{ad_cost * real:.2f}".replace(".", ",") + " €"
        extra += f'<div style="font-size:12px;color:#475569;margin-top:2px">Vrai coût par client livré : <b>{html_text(cost)}</b></div>'
    return flow_card_html("Multiplicateur CAC", format_factor(real), detail, extra=extra, accent="#7c3aed", background="#faf5ff")


def journey_cards(df: pd.DataFrame, metrics: dict, thresholds: dict[str, float], rows: dict | None = None, previous: dict | None = None) -> list[str]:
    """The 8 cards, in the order of the order journey."""
    signs = {s["key"]: s for s in vital_signs(metrics, thresholds)}
    received = int(metrics.get("orders_received", 0) or 0)
    confirmed = exclusive_confirmed(metrics)
    cancelled = int(metrics.get("orders_cancelled", 0) or 0)
    sent = int(metrics.get("orders_sent", 0) or 0)
    delivered = int(metrics.get("orders_delivered", 0) or 0)
    returned = int(metrics.get("orders_returned_failed", 0) or 0)
    in_confirmation = int(metrics.get("orders_in_confirmation", 0) or 0)
    preparation = int(metrics.get("orders_preparation", 0) or 0)
    confirmed_net = int(metrics.get("orders_confirmed_net", 0) or 0)
    finished = delivered + returned
    in_delivery = int(metrics.get("orders_in_delivery", 0) or 0)

    def pending_pill(count: int, label: str, bg: str, fg: str) -> str:
        return (f'<div style="margin-top:8px"><span style="background:{bg};color:{fg};border-radius:999px;padding:3px 10px;'
                f'font-size:12.5px;font-weight:800">{format_count(count)} {label}</span></div>')

    delivered_extra = (
        f'<div style="font-size:12px;color:#334155;margin-top:6px;border-top:1px dashed #e2e8f0;padding-top:5px">'
        f"Sur colis terminés : <b>{html_text(pct(metrics.get('delivery_finalized_rate')))}</b></div>"
        + pending_pill(in_delivery, "en cours de livraison", "#ede9fe", "#5b21b6")
    )
    net = net_transformation_rate(metrics)
    brute_extra = (
        f'<div style="font-size:12px;color:#334155;margin-top:6px;border-top:1px dashed #e2e8f0;padding-top:5px">'
        f"Nette (hors annulées) : <b>{html_text(pct(net))}</b> ({format_count(delivered)} sur {format_count(confirmed_net)})</div>"
    )
    return [
        received_card_html(metrics),
        flow_card_html(
            "Confirmées", format_count(confirmed),
            f"sur {format_count(received)} reçues · {format_count(in_confirmation)} encore en confirmation", signs["confirmation"],
            rate=confirmed / received if received else None,
        ),
        flow_card_html("Annulées", format_count(cancelled), f"sur {format_count(received)} reçues", signs["cancellation"]),
        flow_card_html(
            "Expédiées", format_count(sent),
            f"sur {format_count(confirmed)} confirmées",
            rate=sent / confirmed if confirmed else None, extra=pending_pill(preparation, "en cours de préparation", "#e0f2fe", "#075985"),
        ),
        flow_card_html("Livrées", format_count(delivered), f"sur {format_count(sent)} expédiées", signs["delivery"], extra=delivered_extra),
        flow_card_html("Retours", format_count(returned), f"sur {format_count(sent)} expédiées", signs["return"]),
        flow_card_html(
            "Transformation brute", pct(metrics.get("transformation_real_rate")), f"{format_count(delivered)} livrées sur {format_count(received)} reçues",
            signs["transformation"], extra=brute_extra, accent="#16a34a",
        ),
        multiplier_card_html(cac_multiplier(metrics), thresholds.get("ad_cost_per_purchase", 0.0)),
    ]


def summary_text(metrics: dict, thresholds: dict[str, float]) -> str:
    """One plain sentence: which figures are below their objective (no dots, no jargon)."""
    names = {"confirmation": "confirmées", "delivery": "livrées", "delivery_finalized": "livrées",
             "return": "retours", "cancellation": "annulées", "transformation": "transformation brute",
             "net_transformation": "transformation nette"}
    watch = list(dict.fromkeys(names[s["key"]] for s in health_summary(vital_signs(metrics, thresholds))["to_watch"]))
    if not watch:
        return "Tous les chiffres atteignent leur objectif."
    return "Sous l'objectif ou proche : " + ", ".join(watch) + "."


def render_cockpit(df: pd.DataFrame, loaded_df: pd.DataFrame, date_context: dict, metrics: dict, thresholds: dict[str, float]) -> None:
    try:
        cards = journey_cards(df, metrics, thresholds)
        st.markdown(
            '<div class="section-tight">Parcours COD</div>'
            f'<div class="section-subtitle">De la réception à la livraison. Trait noir = ton objectif (réglable dans la barre latérale). Couleur : vert = objectif atteint, orange = proche, rouge = sous l’objectif.</div>'
            f'<div style="display:flex;gap:12px;flex-wrap:wrap">{"".join(cards)}</div>',
            unsafe_allow_html=True,
        )
    except Exception as exc:  # never let the section break the dashboard
        st.warning(f"Parcours COD indisponible pour ce fichier : {exc}")
