"""Ranking charts (livreurs, confirmatrices, produits, wilayas)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..rankings import OTHERS_LABEL, amount_ranking_rows, pooled_rate, rate_ranking_rows, rate_tone
from .formatting import TREND_AVERAGE_COLOR, html_text, money, pct
from .components import render_chart_header


RANK_TONE_COLORS = {"good": "#16a34a", "bad": "#dc2626", "neutral": "#94a3b8"}


RANK_LABEL_MAX = 26


def short_label(value, limit: int = RANK_LABEL_MAX) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _ranking_layout(fig, rows_count: int, x_max: float):
    fig.update_layout(
        height=max(140, 34 * rows_count + 40),
        showlegend=False,
        hovermode="closest",
        separators=", ",
        bargap=0.3,
        barcornerradius=4,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"bgcolor": "#ffffff", "font": {"color": "#0f172a", "size": 12}},
    )
    fig.update_xaxes(visible=False, range=[0, x_max])
    fig.update_yaxes(autorange="reversed", showgrid=False, ticks="", tickfont={"size": 12, "color": "#334155"})
    return fig


def build_rate_ranking_figure(rows: pd.DataFrame, label_col: str, rate_col: str, volume_col: str, volume_label: str, average, higher_is_better: bool = True):
    """Every reliable entry as one horizontal bar, best on top, coloured against the average."""
    if rows.empty:
        return None
    rates = pd.to_numeric(rows[rate_col], errors="coerce")
    tones = [rate_tone(value, average, higher_is_better) for value in rates]
    volumes = pd.to_numeric(rows[volume_col], errors="coerce").fillna(0).astype(int)
    fig = go.Figure()
    fig.add_bar(
        x=rates,
        y=[short_label(value) for value in rows[label_col]],
        orientation="h",
        marker_color=[RANK_TONE_COLORS[tone] for tone in tones],
        text=[f"{pct(rate)} · {volume} {volume_label}" for rate, volume in zip(rates, volumes)],
        textposition="outside",
        textfont={"color": "#334155", "size": 12},
        cliponaxis=False,
        hovertext=[f"<b>{html_text(label)}</b><br>{pct(rate)}<br>{volume} {volume_label}" for label, rate, volume in zip(rows[label_col], rates, volumes)],
        hoverinfo="text",
    )
    if average is not None and not pd.isna(average):
        fig.add_vline(x=float(average), line_color=TREND_AVERAGE_COLOR, line_width=1, line_dash="dash", layer="below")
    top = max(float(rates.max()) if not rates.dropna().empty else 0.0, float(average or 0.0))
    return _ranking_layout(fig, len(rows), max(top * 1.55, 0.1))


def build_amount_ranking_figure(rows: pd.DataFrame, label_col: str, value_col: str, color: str):
    """Biggest amounts first, with their share of the total; the tail is one grey "Autres" bar."""
    if rows.empty:
        return None
    values = pd.to_numeric(rows[value_col], errors="coerce").fillna(0)
    is_others = rows[label_col].eq(OTHERS_LABEL)
    labels = [
        f"{OTHERS_LABEL} ({int(n)})" if other else short_label(label)
        for label, other, n in zip(rows[label_col], is_others, rows.get("nb_regroupes", pd.Series(0, index=rows.index)))
    ]
    fig = go.Figure()
    fig.add_bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=[RANK_TONE_COLORS["neutral"] if other else color for other in is_others],
        text=[f"{money(value)} · {pct(part)}" for value, part in zip(values, rows["part"])],
        textposition="outside",
        textfont={"color": "#334155", "size": 12},
        cliponaxis=False,
        hovertext=[f"<b>{html_text(label)}</b><br>{money(value)}<br>{pct(part)} du total" for label, value, part in zip(rows[label_col], values, rows["part"])],
        hoverinfo="text",
    )
    return _ranking_layout(fig, len(rows), max(float(values.max()) * 1.6, 1.0))


def render_rate_ranking(
    table: pd.DataFrame,
    label_col: str,
    rate_col: str,
    numerator_col: str,
    denominator_col: str,
    volume_col: str,
    volume_label: str,
    volume_min: int,
    title: str,
    explanation: str,
    higher_is_better: bool,
    key: str,
    average=None,
) -> None:
    """Ranking of a rate: best and worst visible, volume next to each value, company average as reference."""
    try:
        # The reference is the team / company rate; a caller can pass the exact KPI card value.
        if average is None:
            average = pooled_rate(table, numerator_col, denominator_col)
        rows, hidden_low, hidden_middle = rate_ranking_rows(table, label_col, rate_col, volume_col, volume_min, higher_is_better)
        better = "plus haut = mieux" if higher_is_better else "plus bas = mieux"
        legend = (
            f'{better} \u00b7 <span style="color:{RANK_TONE_COLORS["good"]}">\u25a0</span> mieux que la moyenne '
            f'\u00b7 <span style="color:{RANK_TONE_COLORS["bad"]}">\u25a0</span> moins bien'
        )
        render_chart_header(title, legend, f"Moyenne {pct(average)}")
        fig = build_rate_ranking_figure(rows, label_col, rate_col, volume_col, volume_label, average, higher_is_better)
        if fig is None:
            st.info(f"Pas assez de volume pour classer (minimum {volume_min} {volume_label}).")
        else:
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)
        notes = []
        if hidden_middle:
            notes.append(f"{hidden_middle} du milieu du classement masqu\u00e9s.")
        if hidden_low:
            notes.append(f"{hidden_low} non affich\u00e9(s) : moins de {volume_min} {volume_label}.")
        if notes:
            st.caption(" ".join(notes))
    except Exception as exc:  # a chart must never break the tab
        st.warning(f"Graphique indisponible : {exc}")


def render_amount_ranking(table: pd.DataFrame, label_col: str, value_col: str, title: str, explanation: str, color: str, key: str) -> None:
    """Ranking of an amount (CA): biggest first, share of total, tail grouped in "Autres"."""
    try:
        rows, total = amount_ranking_rows(table, label_col, value_col)
        if rows.empty:
            render_chart_header(title, "Aucun montant sur le p\u00e9rim\u00e8tre.", f"Total {money(0)}")
            return
        render_chart_header(title, "Du plus gros au plus petit \u00b7 % = part du total", f"Total {money(total)}")
        st.plotly_chart(build_amount_ranking_figure(rows, label_col, value_col, color), width="stretch", config={"displayModeBar": False}, key=key)
    except Exception as exc:  # a chart must never break the tab
        st.warning(f"Graphique indisponible : {exc}")
