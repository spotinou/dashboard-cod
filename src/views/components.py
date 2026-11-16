"""Reusable Streamlit building blocks: cards, headings, tables and drill-downs."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .formatting import DASH, TREND_TONE_COLORS, adaptive_height, display_subset, html_text, money, prepare_table_for_streamlit, style_metric_table
from .analysis import data_quality_has_warning


def kpi(label: str, value: str, color: str = "#111827") -> None:
    st.markdown(
        f"""
        <div class="kpi">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value" style="color:{color}">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def cockpit_heading(title: str, subtitle: str | None = None) -> None:
    sub = f'<div class="section-subtitle">{html_text(subtitle)}</div>' if subtitle else ""
    st.markdown(f'<div class="section-tight">{html_text(title)}</div>{sub}', unsafe_allow_html=True)


def tab_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="tab-header"><div class="tab-title">{html_text(title)}</div><div class="tab-subtitle">{html_text(subtitle)}</div></div>',
        unsafe_allow_html=True,
    )


def render_kpi_stack(items: list[tuple[str, str, str, str]]) -> None:
    for title, value, note, tone in items:
        mini_card(title, str(value), note, tone=tone)


def render_quality_badge(validation_checks: pd.DataFrame) -> None:
    failed = validation_checks[validation_checks["statut"] != "OK"] if not validation_checks.empty and "statut" in validation_checks.columns else pd.DataFrame()
    if failed.empty and not data_quality_has_warning(validation_checks):
        label = "Donn\u00e9es propres"
        css = "quality-ok"
    else:
        count = len(failed) if not failed.empty else 1
        label = f"{count} point(s) \u00e0 v\u00e9rifier - Voir Validation chiffres"
        css = "quality-warn"
    st.markdown(f'<div class="quality-badge {css}">{html_text(label)}</div>', unsafe_allow_html=True)


def hero_card(title: str, value: str, subtitle: str, tone: str = "neutral", badge: str = "Info") -> None:
    st.markdown(
        f"""
        <div class="hero-card {tone}">
          <div class="card-topline"><span class="hero-title">{html_text(title)}</span><span class="status-pill {tone}">{html_text(badge)}</span></div>
          <div class="hero-value">{html_text(value)}</div>
          <div class="hero-sub">{html_text(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def mini_card(title: str, value: str, note: str = "", tone: str = "neutral", badge: str | None = None) -> None:
    badge_html = f'<span class="mini-badge {tone}">{html_text(badge)}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="mini-card {tone}">
          <div class="mini-head"><div class="mini-title">{html_text(title)}</div>{badge_html}</div>
          <div class="mini-value">{html_text(value)}</div>
          <div class="mini-note">{html_text(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def safe_orders(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "order_id",
        "Boutique",
        "R\u00e9f\u00e9rence commande",
        "Tracking",
        "Statut commande",
        "Wilaya",
        "Commune",
        "Nom produit",
        "Livreur",
        "Affect\u00e9e \u00e0",
        "Cr\u00e9e le",
        "Total commande",
    ]
    out = df[[c for c in cols if c in df.columns]].copy()
    out = out.rename(columns={"R\u00e9f\u00e9rence commande": "Reference commande", "Affect\u00e9e \u00e0": "Affectee a", "Cr\u00e9e le": "Cree le"})
    if "Total commande" in out.columns:
        out["Total commande"] = out["Total commande"].apply(money)
    return out


def filter_orders(df: pd.DataFrame, group_col: str, group_value: str, metric: str) -> pd.DataFrame:
    subset = df[df[group_col] == group_value]
    masks = {
        "Commandes recues": pd.Series(True, index=subset.index),
        "Commandes annulees": subset["is_cancelled"],
        "Confirmees nettes": subset["is_confirmed_net"],
        "En confirmation": subset["is_in_confirmation"] if "is_in_confirmation" in subset.columns else pd.Series(False, index=subset.index),
        "Commandes envoyees": subset["is_sent"],
        "Livrees / encaissees": subset["is_delivered"],
        "En dispatch": subset["is_dispatch"] if "is_dispatch" in subset.columns else pd.Series(False, index=subset.index),
        "En livraison": subset["is_in_delivery"],
        "En cours logistique": (subset["is_dispatch"] if "is_dispatch" in subset.columns else pd.Series(False, index=subset.index)) | subset["is_in_delivery"],
        "Retours / echecs": subset["is_return_or_failed"],
        "Preparation": subset["is_preparation"],
    }
    return subset[masks.get(metric, masks["Commandes recues"])]


def show_drilldown(df: pd.DataFrame, label: str, group_col: str, group_value: str, default_metric: str, key: str) -> None:
    metrics = ["Commandes recues", "Commandes annulees", "Confirmees nettes", "En confirmation", "Commandes envoyees", "Livrees / encaissees", "En dispatch", "En livraison", "En cours logistique", "Retours / echecs", "Preparation"]
    st.markdown(f"**Commandes concernees : {label} = {group_value}**")
    metric = st.selectbox("Statistique a inspecter", metrics, index=metrics.index(default_metric), key=f"{key}_metric")
    details = filter_orders(df, group_col, group_value, metric)
    st.caption(f"{len(details)} commande(s) trouvee(s).")
    orders_display = prepare_table_for_streamlit(safe_orders(details))
    st.dataframe(orders_display, width="stretch", hide_index=True)


def selected_index(event) -> int | None:
    try:
        rows = event.selection.rows
    except Exception:
        return None
    return rows[0] if rows else None


def formula_note(text: str) -> None:
    st.caption(f"Formule : {text}")


def decision_summary(title: str, bullets: list[str]) -> None:
    cleaned = [b for b in bullets if b]
    if not cleaned:
        return
    st.markdown("---")
    st.markdown(f"**{title}**")
    for bullet in cleaned:
        st.markdown(f"- {bullet}")


def render_section_kpis(items: list[tuple[str, str, str, str]], max_per_row: int = 5) -> None:
    for start in range(0, len(items), max_per_row):
        row_items = items[start:start + max_per_row]
        cols = st.columns(len(row_items))
        for col, (title, value, note, tone) in zip(cols, row_items):
            with col:
                mini_card(title, str(value), note, tone=tone)


def render_stage_kpis(title: str, subtitle: str, items: list[tuple[str, str, str, str]]) -> None:
    """Render one readable stage of the COD journey without altering its KPIs."""
    st.markdown(
        f'<div class="stage-heading"><span>{html_text(title)}</span><small>{html_text(subtitle)}</small></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    for col, (label, value, note, tone) in zip(cols, items):
        with col:
            mini_card(label, str(value), note, tone=tone)


def render_priority_focus(priority_actions: pd.DataFrame) -> None:
    """Surface the first reliable action already produced by the analysis layer."""
    if priority_actions.empty:
        return
    action = priority_actions.iloc[0]
    priority = str(action.get("priorite", "Info")).lower()
    tone = {"rouge": "bad", "orange": "warn", "vert": "good"}.get(priority, "neutral")
    st.markdown(
        f'''<div class="focus-card {tone}">
            <div class="focus-kicker">Priorite operationnelle</div>
            <div class="focus-title">{html_text(action.get("objet", DASH))}</div>
            <div class="focus-problem">{html_text(action.get("probleme_detecte", DASH))}</div>
            <div class="focus-action">{html_text(action.get("recommandation_concrete", DASH))}</div>
            <div class="focus-proof">{html_text(action.get("preuve_data", ""))} · Confiance : {html_text(action.get("niveau_confiance", DASH))}</div>
        </div>''',
        unsafe_allow_html=True,
    )


def render_data_table(df: pd.DataFrame, columns: list[str], thresholds: dict[str, float], empty_message: str, sort_by: list[str] | str | None = None, height: int | None = None):
    view = display_subset(df, columns, sort_by=sort_by)
    if view.empty:
        st.info(empty_message)
        return None
    return st.dataframe(style_metric_table(view, thresholds), width="stretch", hide_index=True, height=height or adaptive_height(view))


def render_selectable_data_table(df: pd.DataFrame, columns: list[str], key: str, thresholds: dict[str, float], empty_message: str, sort_by: list[str] | str | None = None):
    view = display_subset(df, columns, sort_by=sort_by)
    if view.empty:
        st.info(empty_message)
        return None, view
    event = st.dataframe(style_metric_table(view, thresholds), width="stretch", hide_index=True, height=adaptive_height(view), on_select="rerun", selection_mode="single-row", key=key)
    return event, view


def render_chart_header(title: str, explanation: str, pill: str, sentence_html: str = "", min_height: int = 0) -> None:
    """Chart title with a grey badge on the right and one short line under it."""
    bg, fg = TREND_TONE_COLORS["neutral"]
    sentence = f'<div style="font-size:12.5px;color:#334155;margin-top:4px;line-height:1.45">{sentence_html}</div>' if sentence_html else ""
    st.markdown(
        f"""
        <div style="margin:6px 0 4px;min-height:{min_height}px">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
            <span style="font-size:15px;font-weight:850;color:#0f172a">{html_text(title)}</span>
            <span style="background:{bg};color:{fg};border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:800;white-space:nowrap">{html_text(pill)}</span>
          </div>
          <div style="font-size:12.5px;color:#475569;margin-top:2px">{explanation}</div>
          {sentence}
        </div>
        """,
        unsafe_allow_html=True,
    )
