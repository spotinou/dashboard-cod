"""Evolution over time and comparison with the previous period."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..metrics import compute_global_metrics
from ..trends import TREND_CHARTS, auto_granularity, compute_period_comparison, compute_trend, previous_period, provisional_mask, trend_reading
from .formatting import DASH, TREND_ACCENT, TREND_ACCENT_LIGHT, TREND_AVERAGE_COLOR, TREND_GRID_COLOR, TREND_TONE_COLORS, format_date, help_icon, html_text, money, pct
from .components import cockpit_heading, render_section_kpis
from .filters import DATE_TYPE_OPTIONS, apply_date_filter, apply_filter_values, date_series, detect_date_columns, get_date_column


TREND_TICK_FORMAT = {"Jour": "%d/%m", "Semaine": "%d/%m", "Mois": "%m/%Y"}
TREND_OBJECTIVE_COLOR = "#16a34a"
# Rate chart -> sidebar threshold used as objective (same as the health gauges)
TREND_OBJECTIVES = {
    "taux_confirmation": "confirmation_green",
    "taux_livraison_total": "delivery_green",
    "taux_livraison_finalisees": "delivery_green",
    "taux_retour": "return_orange",
    "taux_transformation_reel": "transformation_green",
    "taux_transformation_nette": "net_transformation_green",
}


def first_available_date(loaded_df: pd.DataFrame, date_context: dict):
    date_col = get_date_column(date_context.get("selected_date_type", DATE_TYPE_OPTIONS[0]), detect_date_columns(loaded_df))
    if not date_col:
        return None
    parsed = date_series(loaded_df, date_col).dropna()
    return parsed.min().date() if not parsed.empty else None


def previous_period_covered(loaded_df: pd.DataFrame, date_context: dict, window: tuple) -> bool:
    """The previous window must start on or after the first date of the file, otherwise
    it would hold fewer days of data than the current one and the comparison would be wrong."""
    first = first_available_date(loaded_df, date_context)
    return first is not None and window[0] >= first


def previous_period_frame(loaded_df: pd.DataFrame, date_context: dict) -> tuple[pd.DataFrame | None, tuple | None]:
    """Orders of the same-length period just before the active one, with the same filters."""
    window = previous_period(date_context.get("start_date"), date_context.get("end_date"))
    if window is None:
        return None, None
    if not previous_period_covered(loaded_df, date_context, window):
        return None, window
    prev_df, _ = apply_date_filter(loaded_df, date_context.get("selected_date_type", DATE_TYPE_OPTIONS[0]), window[0], window[1])
    prev_df = apply_filter_values(prev_df, date_context.get("applied_filter_values"))
    if prev_df.empty:
        return None, window
    return prev_df, window


def format_delta(row: dict) -> str:
    delta = row.get("delta")
    if delta is None:
        return "Pas de comparaison"
    arrow = {"up": "▲", "down": "▼"}.get(row.get("direction"), "=")
    if row.get("kind") == "rate":
        return f"{arrow} {delta * 100:+.1f} pts".replace(".", ",")
    return f"{arrow} {delta * 100:+.1f} %".replace(".", ",")


def format_metric_value(value, kind: str) -> str:
    if kind == "rate":
        return pct(value)
    if kind == "money":
        return money(value)
    if value is None or pd.isna(value):
        return DASH
    return f"{float(value):,.0f}".replace(",", " ")


def comparison_cards(rows: list[dict], window: tuple | None) -> list[tuple[str, str, str, str]]:
    cards = []
    for row in rows:
        value = format_metric_value(row["value"], row["kind"])
        if row["delta"] is None:
            note = "Pas de données avant"
        else:
            note = f"{format_delta(row)} (avant : {format_metric_value(row['previous'], row['kind'])})"
            if row.get("provisional"):
                note += f"\n\u23f3 Provisoire : {pct(row.get('in_transit_share'))} des colis encore en route"
        cards.append((row["label"], value, note, row["tone"]))
    return cards


def format_period_label(value, granularity: str) -> str:
    if value is None or pd.isna(value):
        return DASH
    ts = pd.Timestamp(value)
    if granularity == "Semaine":
        return f"semaine du {ts.strftime('%d/%m')}"
    if granularity == "Mois":
        return ts.strftime("%m/%Y")
    return ts.strftime("%d/%m/%Y")


def trend_reading_text(reading: dict, kind: str, higher_is_better: bool, objective=None) -> tuple[str, str, str]:
    """(pill label, pill tone, one short line) for a chart header."""
    better = "plus haut = mieux" if higher_is_better else "plus bas = mieux"
    if objective is not None:
        symbol = "\u2265" if higher_is_better else "\u2264"
        better = f"Objectif : <b>{symbol} {html_text(pct(objective))}</b>"
    if reading.get("last_period") is None:
        return "\u00c0 confirmer", "neutral", f"Pas encore assez de semaines termin\u00e9es \u00b7 {better}"
    label = {"up": "\u25b2 En hausse", "down": "\u25bc En baisse", "flat": "= Stable"}.get(reading.get("direction"), "\u2014")
    average = html_text(format_metric_value(reading.get("average"), kind))
    return label, reading.get("tone", "neutral"), f"Moyenne : <b>{average}</b> \u00b7 {better}"


def render_trend_card_header(title: str, higher_is_better: bool, reading: dict, kind: str, objective=None) -> None:
    pill, tone, sentence = trend_reading_text(reading, kind, higher_is_better, objective)
    bg, fg = TREND_TONE_COLORS.get(tone, TREND_TONE_COLORS["neutral"])
    st.markdown(
        f"""
        <div style="margin:6px 0 0">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
            <span style="font-size:15px;font-weight:850;color:#0f172a">{html_text(title)}{help_icon(title)}</span>
            <span style="background:{bg};color:{fg};border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:800;white-space:nowrap">{html_text(pill)}</span>
          </div>
          <div style="font-size:12.5px;color:#475569;margin-top:2px">{sentence}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _hover_values(trend: pd.DataFrame, key: str, kind: str, provisional: pd.Series, granularity: str) -> list[str]:
    labels = []
    for (_, row), is_provisional in zip(trend.iterrows(), provisional):
        text = f"<b>{format_period_label(row['periode'], granularity)}</b><br>{format_metric_value(row[key], kind)}"
        if is_provisional:
            if bool(row.get("periode_incomplete")):
                text += "<br><i>Période incomplète</i>"
            else:
                text += f"<br><i>Provisoire : {pct(row.get('part_en_route'))} des colis encore en route</i>"
        labels.append(text)
    return labels


def build_metric_trend_figure(trend: pd.DataFrame, key: str, kind: str, form: str, depends_on_delivery: bool, granularity: str = "Jour", average=None, objective=None):
    """A single-metric chart: one series, its average, provisional periods shown lighter."""
    if trend.empty or len(trend) < 2 or key not in trend.columns:
        return None
    values = pd.to_numeric(trend[key], errors="coerce")
    provisional = provisional_mask(trend, depends_on_delivery).to_numpy()
    hover = _hover_values(trend, key, kind, provisional, granularity)
    fig = go.Figure()
    if form == "bar":
        fig.add_bar(
            x=trend["periode"], y=values,
            marker_color=[TREND_ACCENT_LIGHT if p else TREND_ACCENT for p in provisional],
            hovertext=hover, hoverinfo="text",
        )
        fig.update_layout(bargap=0.35, barcornerradius=4)
    else:
        solid = values.where(~provisional)
        # Light dotted line through every point, so provisional periods stay connected but read as "not final".
        fig.add_scatter(x=trend["periode"], y=values, mode="lines", line={"color": TREND_ACCENT_LIGHT, "width": 2, "dash": "dot"}, hoverinfo="skip")
        fig.add_scatter(x=trend["periode"], y=solid, mode="lines", line={"color": TREND_ACCENT, "width": 2.5}, connectgaps=False, hoverinfo="skip")
        fig.add_scatter(
            x=trend["periode"], y=values, mode="markers",
            marker={
                "size": 8,
                "color": ["#ffffff" if p else TREND_ACCENT for p in provisional],
                "line": {"color": [TREND_ACCENT_LIGHT if p else "#ffffff" for p in provisional], "width": 2},
            },
            hovertext=hover, hoverinfo="text",
        )
    references = []  # (value, label, colour, dash): labelled in the right margin so they never hide a point
    if average is not None and not pd.isna(average):
        references.append((float(average), "moyenne", TREND_AVERAGE_COLOR, "dash"))
    if objective is not None and not pd.isna(objective):
        references.append((float(objective), "objectif", TREND_OBJECTIVE_COLOR, "solid"))
    for index, (y, label, color, dash) in enumerate(references):
        fig.add_hline(y=y, line_color=color, line_width=1.5 if label == "objectif" else 1, line_dash=dash)
        close = index == 1 and abs(references[0][0] - y) < 0.03
        fig.add_annotation(
            x=1, xref="paper", xanchor="left", y=y, yref="y", text=label, showarrow=False,
            font={"size": 11, "color": color}, xshift=4, yshift=(-9 if y < references[0][0] else 9) if close else 0,
        )
    if kind == "rate":
        finite = values.dropna()
        bounds = [y for y, _, _, _ in references]
        low = float(min([finite.min()] + bounds)) if not finite.empty else 0.0
        high = float(max([finite.max()] + bounds)) if not finite.empty else 1.0
        pad = max(0.05, (high - low) * 0.25)
        fig.update_yaxes(tickformat=".0%", range=[max(0.0, low - pad), min(1.0, high + pad)])
    elif kind == "money":
        fig.update_yaxes(tickformat="~s", ticksuffix=" DA", rangemode="tozero")
    else:
        fig.update_yaxes(tickformat=",d", rangemode="tozero")
    fig.update_layout(
        height=230,
        showlegend=False,
        hovermode="closest",
        separators=", ",
        margin={"l": 8, "r": 64, "t": 10, "b": 8},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"bgcolor": "#ffffff", "font": {"color": "#0f172a", "size": 12}},
    )
    fig.update_xaxes(tickformat=TREND_TICK_FORMAT.get(granularity, "%d/%m"), showgrid=False, linecolor="#cbd5e1", nticks=8)
    fig.update_yaxes(showgrid=True, gridcolor=TREND_GRID_COLOR, gridwidth=1, zeroline=False, title=None, nticks=5)
    return fig


def render_metric_trend(trend: pd.DataFrame, spec: tuple, granularity: str, thresholds: dict[str, float] | None = None) -> None:
    key, title, explanation, kind, higher_is_better, form, depends_on_delivery = spec
    objective_key = TREND_OBJECTIVES.get(key)
    objective = float(thresholds[objective_key]) if thresholds and objective_key in thresholds else None
    reading = trend_reading(trend, key, kind, higher_is_better, depends_on_delivery)
    render_trend_card_header(title, higher_is_better, reading, kind, objective)
    fig = build_metric_trend_figure(trend, key, kind, form, depends_on_delivery, granularity, reading.get("average"), objective)
    if fig is None:
        st.info("Pas assez de données pour ce graphique.")
        return
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"trend_{key}")


def render_trend_section(df: pd.DataFrame, loaded_df: pd.DataFrame, date_context: dict, global_metrics: dict, thresholds: dict[str, float]) -> None:
    """Evolution over time + comparison with the previous period. Purely additive: never alters existing KPIs."""
    try:
        prev_df, window = previous_period_frame(loaded_df, date_context)
        window_text = f" ({format_date(window[0])} → {format_date(window[1])})" if window else ""
        cockpit_heading(
            "Comparaison avec la période précédente",
            f"M\u00eame dur\u00e9e juste avant{window_text}. Vert = mieux qu'avant, rouge = moins bien.",
        )
        if window is None:
            st.caption("Comparaison indisponible : aucune période d'analyse définie.")
        elif prev_df is None:
            first = first_available_date(loaded_df, date_context)
            if first is not None and window[0] < first:
                st.info(
                    f"Comparaison non affichée : ton fichier commence le {format_date(first)}, la période précédente "
                    "ne serait couverte qu'en partie et les écarts seraient faux. Choisis une période plus courte (ex. 30 derniers jours)."
                )
            else:
                st.caption("Aucune commande sur la période précédente.")
        else:
            rows = compute_period_comparison(global_metrics, compute_global_metrics(prev_df))
            render_section_kpis(comparison_cards(rows, window), max_per_row=6)

        granularity = auto_granularity(date_context.get("start_date"), date_context.get("end_date"))
        unit = {"Jour": "jour", "Semaine": "semaine", "Mois": "mois"}[granularity]
        cockpit_heading(
            "\u00c9volution de mes taux",
            f"Un point par {unit}. Ligne verte = ton objectif, ligne grise = ta moyenne. En clair = {unit} pas encore termin\u00e9 ou colis encore en route.",
        )
        trend = compute_trend(df, date_context.get("date_column"), granularity, date_context.get("start_date"), date_context.get("end_date"))
        if len(trend) < 2:
            st.info("Pas assez de donn\u00e9es pour tracer une \u00e9volution : choisis une p\u00e9riode plus longue.")
            return
        for start in range(0, len(TREND_CHARTS), 2):
            cols = st.columns(2, gap="large")
            for col, spec in zip(cols, TREND_CHARTS[start:start + 2]):
                with col:
                    render_metric_trend(trend, spec, granularity, thresholds)
    except Exception as exc:  # never let the new section break the existing dashboard
        st.warning(f"Section évolution indisponible pour ce fichier : {exc}")
