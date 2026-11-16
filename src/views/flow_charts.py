"""COD funnel and revenue waterfall."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..flows import funnel_stages, revenue_waterfall, waterfall_summary
from .formatting import format_count, html_text, money, pct
from .components import render_chart_header
from .analysis import amount_totals


FLOW_COLORS = {"base": "#2563eb", "lost": "#dc2626", "pending": "#f59e0b", "secured": "#16a34a"}


FLOW_TONE_TEXT = {"lost": "perdu", "pending": "en attente", "secured": "livré", "base": "reçu"}


def funnel_html(stages: list[dict]) -> str:
    """Nested bars (width = share of orders received) with the losses written between steps."""
    parts = []
    last = len(stages) - 1
    for index, stage in enumerate(stages):
        share = stage["share_of_received"] or 0.0
        color = FLOW_COLORS["secured"] if index == last else FLOW_COLORS["base"]
        width = max(share * 100, 1.5)
        step = f" · {html_text(pct(stage['step_rate']))} de l'étape d'avant" if stage["step_rate"] is not None else ""
        parts.append(
            f'<div style="display:flex;align-items:center;gap:10px;margin:2px 0">'
            f'<div style="width:132px;flex:none;font-size:13px;font-weight:800;color:#0f172a">{html_text(stage["label"])}</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="width:{width:.1f}%;background:{color};height:26px;border-radius:0 4px 4px 0"></div>'
            f'</div>'
            f'<div style="width:150px;flex:none;font-size:12.5px;color:#334155;line-height:1.25">'
            f'<b style="font-size:15px;color:#0f172a">{format_count(stage["value"])}</b> · {html_text(pct(share))}'
            f'<div style="font-size:11px;color:#64748b">{step.replace(" · ", "", 1)}</div></div>'
            f'</div>'
        )
        if stage["loss_to_next"]:
            detail = " · ".join(f"{format_count(count)} {html_text(name)}" for name, count in stage["loss_breakdown"])
            parts.append(
                f'<div style="margin:2px 0 8px 142px;font-size:12px;color:#991b1b">'
                f'▼ <b>{format_count(stage["loss_to_next"])}</b> sortent ici'
                f'{" : " + detail if detail else ""}</div>'
            )
    return "".join(parts)


def build_revenue_waterfall_figure(steps: list[dict]):
    """Horizontal waterfall: each deduction floats where it is taken from, coloured by lost / pending / secured."""
    if not steps or not steps[0]["value"]:
        return None
    labels = [step["label"] for step in steps]
    fig = go.Figure()
    fig.add_bar(
        y=labels,
        x=[step["end"] - step["start"] for step in steps],
        base=[step["start"] for step in steps],
        orientation="h",
        marker_color=[FLOW_COLORS[step["tone"]] for step in steps],
        text=[
            f"{'− ' if step['value'] < 0 else ''}{money(abs(step['value']))} · {pct(step['share'])}"
            for step in steps
        ],
        textposition="outside",
        textfont={"color": "#334155", "size": 12},
        cliponaxis=False,
        hovertext=[
            f"<b>{html_text(step['label'])}</b><br>{money(abs(step['value']))}<br>{pct(step['share'])} du CA reçu ({FLOW_TONE_TEXT[step['tone']]})"
            for step in steps
        ],
        hoverinfo="text",
    )
    total = steps[0]["value"]
    fig.update_layout(
        height=max(200, 38 * len(steps) + 30),
        showlegend=False,
        separators=", ",
        bargap=0.3,
        barcornerradius=4,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"bgcolor": "#ffffff", "font": {"color": "#0f172a", "size": 12}},
    )
    fig.update_xaxes(visible=False, range=[0, total * 1.75])
    fig.update_yaxes(autorange="reversed", showgrid=False, ticks="", tickfont={"size": 12, "color": "#334155"})
    return fig


def render_cod_flow_section(df: pd.DataFrame, metrics: dict) -> None:
    """Funnel + revenue waterfall. Purely additive: reads the existing metrics, changes none of them."""
    try:
        stages = funnel_stages(metrics)
        steps = revenue_waterfall(metrics, amount_totals(df, metrics))
        summary = waterfall_summary(steps)
        received = stages[0]["value"]
        col1, col2 = st.columns(2, gap="large")
        with col1:
            delivered_share = stages[-1]["share_of_received"]
            per_100 = f"{(delivered_share or 0) * 100:.0f}"
            render_chart_header(
                "Entonnoir des commandes",
                "Barres = part des commandes reçues qui arrivent à chaque étape · en rouge : ce qui sort entre deux étapes",
                f"{format_count(received)} reçues",
                f"Sur 100 commandes reçues, <b>{per_100}</b> sont livrées.",
                min_height=70,
            )
            if received:
                st.markdown(funnel_html(stages), unsafe_allow_html=True)
            else:
                st.info("Aucune commande sur le périmètre.")
        with col2:
            lost, pending, secured = summary["lost"], summary["pending"], summary["secured"]
            render_chart_header(
                "Où part l'argent",
                "Du CA de toutes les commandes reçues jusqu'au CA livré · "
                f'<b style="color:{FLOW_COLORS["lost"]}">rouge = perdu</b>, '
                f'<b style="color:#b45309">orange = encore en attente</b>, '
                f'<b style="color:{FLOW_COLORS["secured"]}">vert = livré</b>',
                f"Total {money(steps[0]['value'])}",
                f"Livré : <b>{html_text(pct(secured[1]))}</b> · Perdu : <b>{html_text(pct(lost[1]))}</b> ({html_text(money(lost[0]))})"
                f" · En attente : <b>{html_text(pct(pending[1]))}</b> ({html_text(money(pending[0]))})",
                min_height=70,
            )
            fig = build_revenue_waterfall_figure(steps)
            if fig is None:
                st.info("Aucun montant sur le périmètre.")
            else:
                st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="revenue_waterfall")
    except Exception as exc:  # never let the new section break the existing dashboard
        st.warning(f"Entonnoir indisponible pour ce fichier : {exc}")
