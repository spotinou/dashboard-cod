"""Evolution over time and comparison with the previous period."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..metrics import compute_global_metrics
from ..trends import GRANULARITY_FREQ, TREND_CHARTS, auto_granularity, compute_period_comparison, compute_trend, previous_period, provisional_mask, trend_reading
from .formatting import DASH, TREND_ACCENT, TREND_ACCENT_LIGHT, TREND_AVERAGE_COLOR, TREND_GRID_COLOR, TREND_TONE_COLORS, format_date, html_text, money, pct
from .components import cockpit_heading, render_data_table, render_section_kpis
from .filters import DATE_TYPE_OPTIONS, apply_date_filter, apply_filter_values, date_series, detect_date_columns, get_date_column


TREND_GRANULARITY_KEY = "trend_granularity"


TREND_PERIOD_KEY = "trend_granularity_period"


TREND_TICK_FORMAT = {"Jour": "%d/%m", "Semaine": "%d/%m", "Mois": "%m/%Y"}


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
            note = "Pas de données sur la période précédente"
        else:
            note = f"{format_delta(row)}\nAvant : {format_metric_value(row['previous'], row['kind'])}"
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


def trend_reading_text(reading: dict, kind: str, granularity: str) -> tuple[str, str, str]:
    """(pill label, pill tone, sentence) explaining the chart in one line."""
    average = format_metric_value(reading.get("average"), kind)
    if reading.get("last_period") is None:
        return "À confirmer", "neutral", "Pas encore assez de périodes complètes pour juger."
    last = f"{html_text(format_metric_value(reading.get('last_value'), kind))} ({html_text(format_period_label(reading['last_period'], granularity))})"
    average = html_text(average)
    label = {"up": "▲ En hausse", "down": "▼ En baisse", "flat": "= Stable"}.get(reading.get("direction"), "—")
    return label, reading.get("tone", "neutral"), f"Dernière période complète : <b>{last}</b><br>Moyenne (ligne grise) : <b>{average}</b>"


def render_trend_card_header(title: str, explanation: str, higher_is_better: bool, reading: dict, kind: str, granularity: str) -> None:
    pill, tone, sentence = trend_reading_text(reading, kind, granularity)
    bg, fg = TREND_TONE_COLORS.get(tone, TREND_TONE_COLORS["neutral"])
    better = "plus haut = mieux" if higher_is_better else "plus bas = mieux"
    st.markdown(
        f"""
        <div style="margin:6px 0 0;min-height:92px">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
            <span style="font-size:15px;font-weight:850;color:#0f172a">{html_text(title)}</span>
            <span style="background:{bg};color:{fg};border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:800;white-space:nowrap">{html_text(pill)}</span>
          </div>
          <div style="font-size:11.5px;color:#64748b;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{html_text(explanation)}">{html_text(explanation)} · <b>{html_text(better)}</b></div>
          <div style="font-size:12.5px;color:#334155;margin-top:4px;line-height:1.45">{sentence}</div>
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


def build_metric_trend_figure(trend: pd.DataFrame, key: str, kind: str, form: str, depends_on_delivery: bool, granularity: str = "Jour", average=None):
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
    if average is not None and not pd.isna(average):
        fig.add_hline(y=float(average), line_color=TREND_AVERAGE_COLOR, line_width=1, line_dash="dash")
    if kind == "rate":
        finite = values.dropna()
        low = float(min(finite.min(), average if average is not None else finite.min())) if not finite.empty else 0.0
        high = float(max(finite.max(), average if average is not None else finite.max())) if not finite.empty else 1.0
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
        margin={"l": 8, "r": 8, "t": 10, "b": 8},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"bgcolor": "#ffffff", "font": {"color": "#0f172a", "size": 12}},
    )
    fig.update_xaxes(tickformat=TREND_TICK_FORMAT.get(granularity, "%d/%m"), showgrid=False, linecolor="#cbd5e1", nticks=8)
    fig.update_yaxes(showgrid=True, gridcolor=TREND_GRID_COLOR, gridwidth=1, zeroline=False, title=None, nticks=5)
    return fig


def render_metric_trend(trend: pd.DataFrame, spec: tuple, granularity: str) -> None:
    key, title, explanation, kind, higher_is_better, form, depends_on_delivery = spec
    reading = trend_reading(trend, key, kind, higher_is_better, depends_on_delivery)
    render_trend_card_header(title, explanation, higher_is_better, reading, kind, granularity)
    fig = build_metric_trend_figure(trend, key, kind, form, depends_on_delivery, granularity, reading.get("average"))
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
            f"Même durée juste avant{window_text}, mêmes filtres. Vert = mieux qu'avant, rouge = moins bien.",
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
            st.caption("Sur une période récente, des colis sont encore en route : le CA livré et la transformation brute peuvent encore monter.")

        cockpit_heading(
            "Évolution dans le temps",
            "Un graphique par indicateur. Barres et points clairs = période pas encore définitive (incomplète ou colis encore en route). Ligne grise = moyenne.",
        )
        options = list(GRANULARITY_FREQ)
        default = auto_granularity(date_context.get("start_date"), date_context.get("end_date"))
        period_signature = (date_context.get("start_date"), date_context.get("end_date"))
        if st.session_state.get(TREND_GRANULARITY_KEY) not in options or st.session_state.get(TREND_PERIOD_KEY) != period_signature:
            st.session_state[TREND_GRANULARITY_KEY] = default
            st.session_state[TREND_PERIOD_KEY] = period_signature
        granularity = st.radio("Regrouper par", options, horizontal=True, key=TREND_GRANULARITY_KEY)
        trend = compute_trend(df, date_context.get("date_column"), granularity, date_context.get("start_date"), date_context.get("end_date"))
        if len(trend) < 2:
            st.info("Pas assez de périodes pour tracer une évolution : choisis une période plus longue ou un regroupement plus fin.")
            return
        for start in range(0, len(TREND_CHARTS), 3):
            cols = st.columns(3, gap="medium")
            for col, spec in zip(cols, TREND_CHARTS[start:start + 3]):
                with col:
                    render_metric_trend(trend, spec, granularity)
        with st.expander("Voir le tableau d'évolution", expanded=False):
            table = trend.drop(columns=["ca_livre_cumule", "periode_fin", "periode_incomplete", "part_en_route"]).copy()
            table["periode"] = table["periode"].map(lambda value: format_period_label(value, granularity))
            table = table.rename(columns={"periode": "Période", "commandes_confirmees": "Confirmées", "colis_en_route": "Colis encore en route"})
            render_data_table(table, list(table.columns), thresholds, "Aucune donnée.")
    except Exception as exc:  # never let the new section break the existing dashboard
        st.warning(f"Section évolution indisponible pour ce fichier : {exc}")
