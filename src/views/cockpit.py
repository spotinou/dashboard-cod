"""Parcours COD: the order journey in big numbers (orders received, confirmed, cancelled, shipped,
delivered, returned), each with its rate, base, objective and the value of the previous period.

Every figure comes from compute_global_metrics (same values as before); only the layout changes.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..health import BAD, GOOD, WARN, average_delivery_days, health_summary, vital_signs
from ..metrics import compute_global_metrics
from ..trends import cac_multiplier, compute_period_comparison, exclusive_confirmed, net_transformation_rate
from .evolution import format_metric_value, previous_period_frame
from .formatting import format_count, format_date, format_period_range, help_icon, html_text, money, pct
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
    note = comparison_note(date_context, window)
    return {row["key"]: row for row in rows}, note, previous


def comparison_note(date_context: dict, window: tuple) -> str:
    """Says exactly which dates are analysed and which dates « avant » refers to."""
    current = format_period_range(date_context.get("start_date"), date_context.get("end_date"))
    previous = format_period_range(window[0], window[1])
    return f"Période analysée : {current}. « Avant » = même durée juste avant : {previous}."


def before_html(text: str, row: dict | None, arrow: bool = True) -> str:
    """'avant : …', green when better, red when worse. No 'points' jargon."""
    if not text:
        return ""
    tone = (row or {}).get("tone", "neutral")
    arrow = {"up": "▲ ", "down": "▼ "}.get((row or {}).get("direction"), "") if arrow else ""
    provisional = " (provisoire, colis encore en route)" if (row or {}).get("provisional") else ""
    return f'<div style="font-size:12px;font-weight:700;color:{DELTA_COLORS.get(tone, DELTA_COLORS["neutral"])};margin-top:6px">{arrow}avant : {html_text(text)}{provisional}</div>'


def delta_html(row: dict | None) -> str:
    """Previous value of a comparison row, as 'avant : …'."""
    if not row or row.get("delta") is None:
        return ""
    return before_html(format_metric_value(row["previous"], row["kind"]), row)


def gauge_html(sign: dict) -> str:
    """Thin bar of the rate with a black tick at the objective."""
    value = sign["value"]
    width = 0.0 if value is None or pd.isna(value) else max(min(float(value), 1.0), 0.0) * 100
    objective = sign["objective"] * 100
    fill = {GOOD: "#16a34a", WARN: "#f59e0b", BAD: "#dc2626"}.get(sign["verdict"], "#94a3b8")
    symbol = "≥" if sign["higher_is_better"] else "≤"
    return (
        '<div style="position:relative;height:8px;background:#eef2f7;border-radius:4px;margin:10px 0 3px">'
        f'<div style="width:{width:.1f}%;height:8px;background:{fill};border-radius:4px"></div>'
        f'<div style="position:absolute;left:{objective:.1f}%;top:-4px;width:2px;height:16px;background:#0f172a"></div></div>'
        f'<div style="font-size:11px;color:#475569">objectif {symbol} {html_text(pct(sign["objective"]))}</div>'
    )


def flow_card_html(title: str, big: str, detail: str = "", sign: dict | None = None, extra: str = "",
                   before: str = "", accent: str | None = None, background: str | None = None) -> str:
    badge = ""
    if sign is not None and sign.get("verdict") in VERDICT_BADGE:
        label, bg, fg = VERDICT_BADGE[sign["verdict"]]
        badge = f'<span style="background:{bg};color:{fg};border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800;white-space:nowrap">{label}</span>'
    style = CARD_STYLE + (f";border-left:5px solid {accent}" if accent else "") + (f";background:{background}" if background else "")
    return (
        f'<div style="{style}">'
        '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">'
        f'<span style="font-size:14px;font-weight:800;color:#0f172a">{html_text(title)}{help_icon(title)}</span>{badge}</div>'
        f'<div style="font-size:30px;font-weight:850;color:#0f172a;line-height:1.1;margin-top:4px">{html_text(big)}</div>'
        f'<div style="font-size:12.5px;color:#334155;margin-top:2px">{detail}</div>'
        f"{gauge_html(sign) if sign is not None else ''}{extra}{before}</div>"
    )


def received_card_html(metrics: dict, row: dict | None) -> str:
    return flow_card_html("Commandes reçues", format_count(metrics.get("orders_received", 0)), "Base de la période", before=delta_html(row))


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


def _count_before(previous: dict | None, count, row: dict | None) -> str:
    """Previous count and, when a rate row is given, previous rate; coloured by the rate
    (the judged figure). No arrow: the count and the rate can move in opposite directions."""
    if not previous:
        return ""
    value = count(previous) if callable(count) else previous.get(count, 0)
    text = format_count(value)
    if row and row.get("previous") is not None:
        text += f" · {pct(row['previous'])}"
    return before_html(text, row, arrow=False)


def pending_card_html(title: str, count: int, detail: str, ca: float, before: str, accent: str, background: str) -> str:
    """Orders waiting in a step (not a rate: no objective, no verdict)."""
    extra = f'<div style="font-size:12px;color:#475569;margin-top:6px">CA en attente : <b>{html_text(money(ca))}</b></div>'
    return flow_card_html(title, format_count(count), detail, extra=extra, before=before, accent=accent, background=background)


def journey_cards(df: pd.DataFrame, metrics: dict, thresholds: dict[str, float], rows: dict, previous: dict | None) -> list[str]:
    """The 10 cards, in the order of the order journey."""
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
    dispatch = int(metrics.get("orders_dispatch", 0) or 0)
    in_delivery = int(metrics.get("orders_in_delivery", 0) or 0)
    logistics = int(metrics.get("orders_logistics", dispatch + in_delivery) or 0)
    finished = delivered + returned
    delay = average_delivery_days(df)

    delivered_extra = (
        f'<div style="font-size:12px;color:#334155;margin-top:6px;border-top:1px dashed #e2e8f0;padding-top:5px;line-height:1.5">'
        f"Sur colis terminés : <b>{html_text(pct(metrics.get('delivery_finalized_rate')))}</b> ({format_count(delivered)} sur {format_count(finished)} livrés ou revenus)"
        + (f"<br>Délai moyen de livraison : <b>{delay['days']:.1f} jours</b>".replace(".", ",") if delay.get("days") is not None else "")
        + "</div>"
    )
    net = net_transformation_rate(metrics)
    brute_extra = (
        f'<div style="font-size:12px;color:#334155;margin-top:6px;border-top:1px dashed #e2e8f0;padding-top:5px">'
        f"Nette (hors annulées) : <b>{html_text(pct(net))}</b> ({format_count(delivered)} sur {format_count(confirmed_net)})</div>"
    )
    return [
        received_card_html(metrics, rows.get("orders_received")),
        flow_card_html(
            "Confirmées", format_count(confirmed),
            f"<b>{html_text(pct(confirmed / received if received else None))}</b> des {format_count(received)} reçues · {format_count(in_confirmation)} encore en confirmation",
            signs["confirmation"], before=_count_before(previous, exclusive_confirmed, rows.get("confirmation_display_rate")),
        ),
        flow_card_html(
            "Annulées", format_count(cancelled),
            f"<b>{html_text(pct(metrics.get('cancellation_rate')))}</b> des {format_count(received)} reçues",
            signs["cancellation"], before=_count_before(previous, "orders_cancelled", rows.get("cancellation_rate")),
        ),
        flow_card_html(
            "Expédiées", format_count(sent),
            f"sur {format_count(confirmed)} confirmées · {format_count(preparation)} encore en préparation",
            before=_count_before(previous, "orders_sent", None),
        ),
        flow_card_html(
            "Livrées", format_count(delivered),
            f"<b>{html_text(pct(metrics.get('delivery_total_rate_on_sent')))}</b> des {format_count(sent)} expédiées",
            signs["delivery"], extra=delivered_extra, before=_count_before(previous, "orders_delivered", rows.get("delivery_total_rate_on_sent")),
        ),
        flow_card_html(
            "Retours", format_count(returned),
            f"<b>{html_text(pct(metrics.get('return_rate_on_sent')))}</b> des {format_count(sent)} expédiées",
            signs["return"], before=_count_before(previous, "orders_returned_failed", rows.get("return_rate_on_sent")),
        ),
        flow_card_html(
            "Transformation brute", pct(metrics.get("transformation_real_rate")),
            f"{format_count(delivered)} livrées sur {format_count(received)} reçues",
            signs["transformation"], extra=brute_extra, before=delta_html(rows.get("transformation_real_rate")), accent="#16a34a",
        ),
        pending_card_html(
            "En cours de confirmation", in_confirmation,
            f"<b>{html_text(pct(in_confirmation / received if received else None))}</b> des {format_count(received)} reçues · pas encore confirmées ni annulées",
            float(metrics.get("ca_in_confirmation", 0) or 0),
            _count_before(previous, "orders_in_confirmation", None), "#f59e0b", "#fffbeb",
        ),
        pending_card_html(
            "En cours de livraison", logistics,
            f"<b>{html_text(pct(logistics / sent if sent else None))}</b> des {format_count(sent)} expédiées · {format_count(dispatch)} dispatchées, {format_count(in_delivery)} chez le livreur",
            float(metrics.get("ca_logistics", 0) or 0),
            _count_before(previous, "orders_logistics", None), "#0ea5e9", "#f0f9ff",
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
        rows, note, previous = comparison_rows(loaded_df, date_context, metrics)
        cards = journey_cards(df, metrics, thresholds, rows, previous)
        st.markdown(
            '<div class="section-tight">Parcours COD</div>'
            f'<div class="section-subtitle">De la réception à la livraison. Trait noir = ton objectif (réglable dans la barre latérale). {html_text(note)}</div>'
            f'<div style="font-size:14px;font-weight:800;color:#0f172a;margin:2px 0 8px">{html_text(summary_text(metrics, thresholds))}</div>'
            f'<div style="display:flex;gap:12px;flex-wrap:wrap">{"".join(cards)}</div>',
            unsafe_allow_html=True,
        )
    except Exception as exc:  # never let the section break the dashboard
        st.warning(f"Parcours COD indisponible pour ce fichier : {exc}")
