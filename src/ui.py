from __future__ import annotations

from datetime import timedelta
from html import escape
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pandas.api.types import is_object_dtype, is_scalar

from .alerts import DEFAULT_THRESHOLDS, generate_alerts
from .data_loader import load_excel, validate_columns
from .metrics import (
    compute_confirmation_metrics,
    compute_global_metrics,
    compute_livreur_metrics,
    compute_livreur_wilaya_alerts,
    compute_product_metrics,
    compute_product_wilaya_alerts,
    compute_wilaya_metrics,
)
from .flows import funnel_stages, revenue_waterfall, waterfall_summary
from .rankings import (
    OTHERS_LABEL,
    amount_concentration,
    amount_ranking_rows,
    pooled_rate,
    rate_ranking_reading,
    rate_ranking_rows,
    rate_tone,
)
from .trends import (
    GRANULARITY_FREQ,
    TREND_CHARTS,
    auto_granularity,
    compute_period_comparison,
    compute_trend,
    previous_period,
    provisional_mask,
    trend_reading,
)
from .validation import compute_validation_checks

SENSITIVE_COLUMNS = {"Client", "Email", "Téléphone", "Téléphone 2", "Adresse"}

DATE_TYPE_OPTIONS = [
    "Date de création",
    "Date d'affectation",
    "Date de confirmation",
    "Date d'expédition",
]
DATE_TYPE_COLUMNS = {
    "Date de création": "Crée le",
    "Date d'affectation": "Affectée le",
    "Date de confirmation": "Confirmée le",
    "Date d'expédition": "Expédiée le",
}

ANALYSIS_DATE_TYPE_KEY = "analysis_date_type"
ANALYSIS_PERIOD_PRESET_KEY = "analysis_period_preset"
ANALYSIS_PERIOD_DRAFT_KEY = "analysis_period_draft"
ANALYSIS_PERIOD_VALUE_KEY = "analysis_period_value"
ANALYSIS_PERIOD_FILE_KEY = "analysis_period_file_signature"
ANALYSIS_PERIOD_NOTICE_KEY = "analysis_period_notice"
ANALYSIS_PERIOD_FORM_KEY = "analysis_period_form"

PERIOD_PRESET_OPTIONS = (
    "Toute la p\u00e9riode",
    "Aujourd'hui",
    "Hier",
    "7 derniers jours",
    "14 derniers jours",
    "30 derniers jours",
    "60 derniers jours",
    "90 derniers jours",
    "180 derniers jours",
    "Personnalis\u00e9e",
)
PERIOD_PRESET_DAYS = {
    "7 derniers jours": 7,
    "14 derniers jours": 14,
    "30 derniers jours": 30,
    "60 derniers jours": 60,
    "90 derniers jours": 90,
    "180 derniers jours": 180,
}

FILTER_DEFINITIONS = (
    ("Boutique", "Boutique", "filter_boutique"),
    ("Produit", "Nom produit", "filter_product"),
    ("SKU produit", "SKU produit", "filter_sku"),
    ("Source", "Source", "filter_source"),
    ("Méthode de livraison", "Méthode de livraison", "filter_delivery_method"),
    ("Livreur", "Livreur", "filter_delivery_partner"),
    ("Confirmatrice", "Affect\u00e9e \u00e0", "filter_confirmatrice"),
    ("Wilaya", "Wilaya", "filter_wilaya"),
    ("Statut commande", "Statut commande", "filter_order_status"),
)

DISPLAY_COLUMNS = {
    "confirmatrice": "Confirmatrice",
    "livreur": "Livreur",
    "produit": "Produit",
    "wilaya": "Wilaya",
    "commandes_recues": "Commandes reçues",
    "commandes_annulees": "Annulées avant expédition",
    "commandes_confirmees_nettes": "Confirmées nettes",
    "commandes_envoyees": "Expédiées",
    "livrees": "Livrées finalisées",
    "en_preparation": "En pr\u00e9paration",
    "en_dispatch": "En dispatch",
    "en_livraison": "En cours livraison",
    "en_cours_logistique": "En cours logistique",
    "retours": "Retours / échecs",
    "taux_confirmation": "Taux confirmation",
    "taux_annulation": "Taux annulation avant expédition",
    "taux_preparation": "Taux en pr\u00e9paration",
    "taux_dispatch": "Taux en dispatch",
    "taux_en_livraison": "Taux en cours de livraison",
    "taux_livraison_finalisees": "Taux livraison finalisée hors en cours",
    "taux_livraison_total": "Taux livraison sur exp\u00e9di\u00e9es",
    "taux_en_cours_livraison": "Taux en cours livraison",
    "taux_en_cours_logistique": "Taux en cours logistique",
    "taux_retour": "Taux retour",
    "taux_transformation_reel": "Taux transformation réel",
    "ca_livre": "CA livré finalisé",
    "ca_dispatch": "CA en dispatch",
    "ca_bloque_livraison": "CA en cours livraison",
    "ca_en_cours_logistique": "CA en cours logistique",
    "ca_preparation": "CA confirmé non expédié",
    "ca_retours": "Perte CA retours",
    "ca_par_commande_confirmee": "CA par commande confirmée",
    "panier_moyen_livre": "Panier moyen livré",
    "decision_auto": "Décision",
    "probleme_probable": "Problème probable",
    "cause_probable": "Cause probable",
    "action_recommandee": "Action recommandée",
    "produit_dominant": "Produit dominant",
    "livreur_dominant": "Livreur dominant",
    "controle": "Contrôle",
    "valeur": "Valeur",
    "attendu": "Attendu",
    "statut": "Statut",
    "details": "Details",
    "priorite": "Priorité",
    "objet": "Objet",
    "probleme_detecte": "Problème détecté",
    "recommandation_concrete": "Recommandation concrète",
    "preuve_data": "Preuve data",
    "impact_estime": "Impact estimé",
    "niveau_confiance": "Niveau de confiance",
    "diagnostic": "Diagnostic",
    "action_recommandee": "Action recommandée",
    "source": "Source",
    "sku_produit": "SKU produit",
    "produit_associe": "Produit associé",
    "livreur_actuel": "Livreur actuel / dominant",
    "expediees_actuel": "Expédiées actuel",
    "taux_livraison_total_actuel": "Taux livraison sur exp\u00e9di\u00e9es actuel",
    "taux_retour_actuel": "Taux retour actuel",
    "meilleur_livreur_alternatif": "Meilleur livreur alternatif",
    "expediees_alternatif": "Expédiées alternatif",
    "taux_livraison_total_alternatif": "Taux livraison sur exp\u00e9di\u00e9es alternatif",
    "taux_retour_alternatif": "Taux retour alternatif",
    "ecart_livraison": "Écart livraison",
    "ecart_retour": "Écart retour",
    "volume": "Volume",
    "wilayas_problematiques": "Wilayas les plus problématiques",
}

TEXT_LIKE_COLUMNS = {
    "Valeur",
    "valeur",
    "Détail",
    "Détails",
    "Detail",
    "details",
    "Calcul",
    "calcul",
    "Formule",
    "formule",
    "Explication",
    "explication",
    "Description",
    "description",
    "Libellé",
    "libellé",
    "Label",
    "label",
    "KPI",
    "kpi",
}


def prepare_table_for_streamlit(data):
    if not isinstance(data, pd.DataFrame):
        return data

    safe = data.copy()

    for col in safe.columns:
        series = safe[col]

        if col in TEXT_LIKE_COLUMNS:
            safe[col] = series.astype("string")
            continue

        if is_object_dtype(series):
            non_null = series.dropna()
            has_text = non_null.map(lambda x: isinstance(x, str)).any()
            has_non_text = non_null.map(lambda x: not isinstance(x, str)).any()

            if has_text and has_non_text:
                safe[col] = series.astype("string")

    return safe



def money(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "\u2014"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "\u2014"
    if pd.isna(number) or number in {float("inf"), float("-inf")}:
        return "\u2014"
    return f"{number:,.0f}".replace(",", " ") + " DA"


def pct(value: float | None) -> str:
    if not is_scalar(value):
        return "\u2014"
    if value is None or pd.isna(value):
        return "\u2014"
    if isinstance(value, str) and value.strip().lower() in {"", "nan", "nan%", "none", "inf", "-inf"}:
        return "\u2014"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "\u2014"
    if pd.isna(number) or number in {float("inf"), float("-inf")}:
        return "\u2014"
    return f"{number * 100:.1f} %"


def is_rate_column(col: str) -> bool:
    normalized = str(col).lower()
    return any(token in normalized for token in ("taux", "rate", "ratio", "pourcentage", "ecart"))


def is_money_column(col: str) -> bool:
    normalized = str(col).lower().strip()
    if is_rate_column(normalized):
        return False
    if normalized in {"valeur"}:
        return False
    money_tokens = ("montant", "prix", "total", "panier")
    if normalized.startswith("ca_") or normalized.startswith("ca ") or "perte ca" in normalized:
        return True
    if any(token in normalized for token in money_tokens):
        return True
    return "valeur" in normalized and any(token in normalized for token in ("moyenne", "commande", "retour", "livre"))


def style_level(value: float | None, kind: str, thresholds: dict[str, float]) -> str:
    if value is None or pd.isna(value):
        return "#6b7280"
    if kind in {"confirmation", "delivery"}:
        return "#16a34a" if value >= thresholds[f"{kind}_green"] else "#f59e0b" if value >= thresholds[f"{kind}_orange"] else "#dc2626"
    if kind == "return":
        return "#16a34a" if value <= thresholds["return_orange"] else "#f59e0b" if value <= thresholds["return_red"] else "#dc2626"
    if kind == "cancellation":
        return "#16a34a" if value <= thresholds["cancellation_orange"] else "#f59e0b" if value <= thresholds["cancellation_red"] else "#dc2626"
    if kind == "preparation":
        return "#16a34a" if value <= thresholds["preparation_orange"] else "#f59e0b" if value <= thresholds["preparation_red"] else "#dc2626"
    return "#111827"


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




DASH = "\u2014"


def html_text(value) -> str:
    return escape(str(value if value is not None else DASH))


def tone_class(value: float | None, kind: str, thresholds: dict[str, float]) -> str:
    if value is None or pd.isna(value):
        return "neutral"
    if kind in {"confirmation", "delivery", "transformation"}:
        return "good" if value >= thresholds["delivery_green"] else "warn" if value >= thresholds["delivery_orange"] else "bad"
    if kind == "return":
        return "good" if value <= thresholds["return_orange"] else "warn" if value <= thresholds["return_red"] else "bad"
    if kind == "cancellation":
        return "good" if value <= thresholds["cancellation_orange"] else "warn" if value <= thresholds["cancellation_red"] else "bad"
    if kind == "preparation":
        return "good" if value <= thresholds["preparation_orange"] else "warn" if value <= thresholds["preparation_red"] else "bad"
    if kind == "risk":
        return "good" if value == 0 else "warn" if value < 50 else "bad"
    return "neutral"


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


def render_funnel_compact(metrics: dict) -> None:
    cockpit_heading("Funnel COD", "Les sous-textes montrent imm\u00e9diatement la perte ou le blocage entre deux \u00e9tapes.")
    received = int(metrics["orders_received"])
    confirmed = int(metrics["orders_confirmed_net"])
    sent = int(metrics["orders_sent"])
    delivered = int(metrics["orders_delivered"])
    leaks = [
        ("annulations", int(metrics["orders_cancelled"]), 0.0),
        ("non exp\u00e9di\u00e9es", int(metrics["orders_preparation"]), float(metrics.get("ca_preparation", 0))),
        ("retours / \u00e9checs", int(metrics["orders_returned_failed"]), float(metrics.get("ca_returned_failed", 0))),
    ]
    leak_name, leak_count, leak_amount = max(leaks, key=lambda item: item[1])
    amount_text = f", {money(leak_amount)}" if leak_amount else ""
    st.markdown(
        f'<div class="leak-banner"><b>Fuite principale :</b> {html_text(leak_name)} - {leak_count} commandes{html_text(amount_text)}</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns([1, 0.12, 1, 0.12, 1, 0.12, 1])
    funnel_items = [
        ("Commandes re\u00e7ues", received, "Base p\u00e9riode", "neutral"),
        ("Confirm\u00e9es nettes", confirmed, f"{pct(metrics['confirmation_rate'])} des re\u00e7ues - Perte : {int(metrics['orders_cancelled'])} annul\u00e9es", "info"),
        ("Exp\u00e9di\u00e9es", sent, f"{pct(metrics['shipping_rate_global'])} des confirm\u00e9es - Blocage : {int(metrics['orders_preparation'])} non exp\u00e9di\u00e9es", "warn"),
        ("Livr\u00e9es finalis\u00e9es", delivered, f"{pct(metrics['delivery_total_rate_on_sent'])} des exp\u00e9di\u00e9es - Transformation : {pct(metrics['transformation_real_rate'])}", "good"),
    ]
    for i, (title, value, note, tone) in enumerate(funnel_items):
        with cols[i * 2]:
            mini_card(title, str(value), note, tone=tone)
        if i < 3:
            with cols[i * 2 + 1]:
                st.markdown('<div class="funnel-arrow">&rarr;</div>', unsafe_allow_html=True)


def render_secondary_kpis(metrics: dict, thresholds: dict[str, float]) -> None:
    with st.expander("Voir d\u00e9tails op\u00e9rationnels", expanded=False):
        groups = [
            (
                "Commandes",
                [
                    ("Confirm\u00e9es nettes", metrics["orders_confirmed_net"], "Hors annulations"),
                    ("Taux confirmation", pct(metrics["confirmation_rate"]), "Confirm\u00e9es / re\u00e7ues"),
                    ("Annul\u00e9es avant exp\u00e9dition", metrics["orders_cancelled"], "Sorties avant exp\u00e9dition"),
                    ("Taux annulation", pct(metrics["cancellation_rate"]), "Annul\u00e9es / re\u00e7ues"),
                ],
            ),
            (
                "Exp\u00e9dition / livraison",
                [
                    ("Confirm\u00e9es non exp\u00e9di\u00e9es", metrics["orders_preparation"], "Blocage interne"),
                    ("Exp\u00e9di\u00e9es", metrics["orders_sent"], "Chez livreur"),
                    ("Taux exp\u00e9dition", pct(metrics["shipping_rate_global"]), "Exp\u00e9di\u00e9es / confirm\u00e9es"),
                    ("En dispatch", metrics.get("orders_dispatch", 0), "Expediees non finalisees"),
                    ("En cours livraison", metrics["orders_in_delivery"], "CA pas encore s\u00e9curis\u00e9"),
                    ("Taux en cours livraison", pct(metrics["in_delivery_rate_on_sent"]), "En cours / exp\u00e9di\u00e9es"),
                    ("Livr\u00e9es finalis\u00e9es", metrics["orders_delivered"], "Livr\u00e9es ou encaiss\u00e9es"),
                    ("Taux livraison sur exp\u00e9di\u00e9es", pct(metrics["delivery_total_rate_on_sent"]), "Livr\u00e9es / exp\u00e9di\u00e9es"),
                    ("Retours / \u00e9checs", metrics["orders_returned_failed"], "Perte apr\u00e8s exp\u00e9dition"),
                    ("Taux retour", pct(metrics["return_rate_on_sent"]), "Retours / exp\u00e9di\u00e9es"),
                ],
            ),
            (
                "Argent",
                [
                    ("CA livr\u00e9 finalis\u00e9", money(metrics["ca_delivered"]), "Argent s\u00e9curis\u00e9"),
                    ("CA en dispatch", money(metrics.get("ca_dispatch", 0)), "Expedie non finalise"),
                    ("CA en cours livraison", money(metrics["ca_in_delivery"]), "Encore \u00e0 transformer"),
                    ("CA confirm\u00e9 non exp\u00e9di\u00e9", money(metrics["ca_preparation"]), "Blocage pr\u00e9paration"),
                    ("Perte CA retours", money(metrics["ca_returned_failed"]), "Perdu apr\u00e8s exp\u00e9dition"),
                ],
            ),
        ]
        for title, items in groups:
            st.markdown(f'<div class="detail-title">{html_text(title)}</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for index, (label, value, note) in enumerate(items):
                with cols[index % 4]:
                    mini_card(label, str(value), note, tone="detail")

def deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or not df.columns.duplicated().any():
        return df
    return df.loc[:, ~df.columns.duplicated()].copy()


def unique_existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    seen = set()
    selected = []
    for col in columns:
        if col in df.columns and col not in seen:
            selected.append(col)
            seen.add(col)
    return selected


def prepare_dataframe_for_display(df: pd.DataFrame, rename_columns: bool = True) -> pd.DataFrame:
    out = deduplicate_columns(df.copy())
    invalid_values = [float("inf"), float("-inf"), "nan", "NaN", "nan%", "None", "none", "inf", "-inf"]
    for col in out.columns:
        if is_rate_column(col):
            out[col] = out[col].apply(pct)
        elif is_money_column(col):
            out[col] = out[col].apply(money)
    out = out.replace(invalid_values, pd.NA).fillna("\u2014")
    if rename_columns:
        out = out.rename(columns=DISPLAY_COLUMNS)
    return prepare_table_for_streamlit(out)


def format_table(df: pd.DataFrame) -> pd.DataFrame:
    return prepare_dataframe_for_display(df, rename_columns=True)


def metric_color(value, col: str, thresholds: dict[str, float]) -> str:
    if value is None or pd.isna(value):
        return ""
    kind = None
    if col == "taux_confirmation":
        kind = "confirmation"
    elif col in {"taux_livraison_finalisees", "taux_livraison_total", "taux_en_cours_livraison"}:
        kind = "delivery"
    elif col == "taux_retour":
        kind = "return"
    elif col == "taux_annulation":
        kind = "cancellation"
    if kind is None:
        return ""
    return f"color: {style_level(float(value), kind, thresholds)}; font-weight: 700"


def style_metric_table(df: pd.DataFrame, thresholds: dict[str, float]):
    raw = deduplicate_columns(df.copy())
    display = prepare_dataframe_for_display(raw, rename_columns=False)
    style_cols = list(raw.columns)

    def style_cell(value, col: str) -> str:
        normalized = str(value).lower()
        if col == "decision_auto":
            if "pousser" in normalized:
                return "color: #16a34a; font-weight: 700"
            if "surveiller" in normalized or "corriger" in normalized:
                return "color: #dc2626; font-weight: 700"
            if "chantillon" in normalized:
                return "color: #6b7280; font-weight: 700"
        if col == "statut" and value != "OK":
            return "color: #dc2626; font-weight: 700"
        return metric_color(value, col, thresholds)

    def style_column(series: pd.Series) -> list[str]:
        col = series.name
        return [style_cell(raw.at[idx, col], col) if col in raw.columns and idx in raw.index else "" for idx in series.index]

    styled = display.style.apply(style_column, axis=0)
    numeric_cols = [col for col in style_cols if col not in {"confirmatrice", "livreur", "produit", "wilaya", "decision_auto", "produit_dominant", "livreur_dominant", "controle", "attendu", "statut", "probleme_probable", "cause_probable", "action_recommandee"}]
    styled = styled.set_properties(subset=numeric_cols, **{"text-align": "right"})
    styled = styled.set_properties(subset=[col for col in style_cols if col not in numeric_cols], **{"text-align": "left"})
    return styled.relabel_index([DISPLAY_COLUMNS.get(col, col) for col in style_cols], axis=1)


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


def global_metrics_table(metrics: dict) -> pd.DataFrame:
    rows = [
        ("Commandes reçues", metrics["orders_received"]),
        ("Confirmées nettes", metrics["orders_confirmed_net"]),
        ("Taux confirmation", pct(metrics["confirmation_rate"])),
        ("Annulées avant expédition", metrics["orders_cancelled"]),
        ("Taux annulation avant expédition", pct(metrics["cancellation_rate"])),
        ("Confirmées non expédiées", metrics["orders_preparation"]),
        ("Expédiées", metrics["orders_sent"]),
        ("Taux expédition", pct(metrics["shipping_rate_global"])),
        ("En dispatch", metrics.get("orders_dispatch", 0)),
        ("En cours livraison", metrics["orders_in_delivery"]),
        ("En cours logistique", metrics.get("orders_logistics", metrics.get("orders_dispatch", 0) + metrics["orders_in_delivery"])),
        ("Taux en cours logistique", pct(metrics.get("logistics_rate_on_sent"))),
        ("Taux en cours livraison", pct(metrics["in_delivery_rate_on_sent"])),
        ("Livrées finalisées", metrics["orders_delivered"]),
        ("Retours / échecs", metrics["orders_returned_failed"]),
        ("Taux livraison finalisée hors en cours", pct(metrics["delivery_finalized_rate"])),
        ("Taux livraison sur exp\u00e9di\u00e9es", pct(metrics["delivery_total_rate_on_sent"])),
        ("Taux retour", pct(metrics["return_rate_on_sent"])),
        ("Taux transformation réel", pct(metrics["transformation_real_rate"])),
        ("CA livré finalisé", money(metrics["ca_delivered"])),
        ("CA en dispatch", money(metrics.get("ca_dispatch", 0))),
        ("CA en cours livraison", money(metrics["ca_in_delivery"])),
        ("CA en cours logistique", money(metrics.get("ca_logistics", metrics.get("ca_dispatch", 0) + metrics["ca_in_delivery"]))),
        ("CA confirmé non expédié", money(metrics["ca_preparation"])),
        ("Perte CA retours", money(metrics["ca_returned_failed"])),
    ]
    return pd.DataFrame(rows, columns=["Indicateur", "Valeur"])


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


def is_known_value(value) -> bool:
    return str(value).strip().lower() not in {"", "non renseign\u00e9", "non renseign\u00c3\u00a9", "none", "nan", "-"}


def reliable_rows(df: pd.DataFrame, label_col: str, volume_col: str, volume_min: int) -> pd.DataFrame:
    if df.empty or label_col not in df.columns or volume_col not in df.columns:
        return df.iloc[0:0].copy()
    out = df[df[label_col].apply(is_known_value)].copy()
    out = out[pd.to_numeric(out[volume_col], errors="coerce").fillna(0).ge(volume_min)]
    return out



def detect_date_columns(df: pd.DataFrame) -> dict[str, str]:
    return {label: col for label, col in DATE_TYPE_COLUMNS.items() if col in df.columns}


def get_date_column(selected_date_type: str, available: dict[str, str] | None = None) -> str | None:
    available = available or DATE_TYPE_COLUMNS
    if selected_date_type in available:
        return available[selected_date_type]
    return available.get(DATE_TYPE_OPTIONS[0])


def date_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(pd.NaT, index=df.index)
    return pd.to_datetime(df[column], errors="coerce", dayfirst=True)


def available_date_bounds(df: pd.DataFrame) -> tuple[object | None, object | None]:
    parts = []
    for col in DATE_TYPE_COLUMNS.values():
        if col not in df.columns:
            continue
        parsed = date_series(df, col).dropna()
        if not parsed.empty:
            parts.append(parsed)
    if not parts:
        return None, None
    all_dates = pd.concat(parts)
    return all_dates.min().date(), all_dates.max().date()


def normalize_date_range(value, min_date, max_date) -> tuple[tuple[object, object], str | None]:
    if min_date is None or max_date is None:
        return (None, None), None
    message = None
    if isinstance(value, tuple) and len(value) == 2:
        start, end = value
    elif isinstance(value, list) and len(value) == 2:
        start, end = value[0], value[1]
    else:
        start, end = min_date, max_date
        message = "Periode initialisee sur les limites disponibles du fichier."
    if start is None or end is None:
        start, end = min_date, max_date
        message = "Periode incomplete : elle a ete ajustee aux limites disponibles du fichier."
    if start > end:
        start, end = end, start
        message = "Periode inversee : debut et fin ont ete remis dans le bon ordre."
    adjusted_start = max(start, min_date)
    adjusted_end = min(end, max_date)
    if adjusted_start != start or adjusted_end != end:
        message = "Periode ajustee car elle depassait les limites techniques des dates disponibles."
    if adjusted_start > adjusted_end:
        adjusted_start, adjusted_end = min_date, max_date
        message = "Periode invalide : elle a ete ajustee aux limites disponibles du fichier."
    return (adjusted_start, adjusted_end), message


def uploaded_file_signature(uploaded) -> tuple[str, int | None]:
    name = getattr(uploaded, "name", "uploaded")
    size = getattr(uploaded, "size", None)
    if size is None:
        try:
            size = len(uploaded.getbuffer())
        except Exception:
            size = None
    return str(name), size


def normalize_analysis_period(value, min_date, max_date) -> tuple[tuple[object, object], str | None]:
    return normalize_date_range(value, min_date, max_date)


def period_from_preset(preset: str, min_date, max_date) -> tuple[object, object]:
    """Build a data-aware quick range anchored on the latest date in the export."""
    if preset == "Toute la p\u00e9riode":
        return min_date, max_date
    if preset == "Aujourd'hui":
        return max_date, max_date
    if preset == "Hier":
        yesterday = max_date - timedelta(days=1)
        return max(min_date, yesterday), max(min_date, yesterday)
    days = PERIOD_PRESET_DAYS.get(preset)
    if days:
        return max(min_date, max_date - timedelta(days=days - 1)), max_date
    return min_date, max_date


def initialize_analysis_period_selector(state, file_signature, min_date, max_date) -> tuple[tuple[object, object], str | None]:
    """Initialize the active value and form draft before the form widgets are created."""
    if min_date is None or max_date is None:
        return (None, None), None

    is_new_file = state.get(ANALYSIS_PERIOD_FILE_KEY) != file_signature
    candidate = (min_date, max_date) if is_new_file else state.get(ANALYSIS_PERIOD_VALUE_KEY)
    if candidate is None:
        candidate = (min_date, max_date)
    normalized, message = normalize_analysis_period(candidate, min_date, max_date)

    state[ANALYSIS_PERIOD_FILE_KEY] = file_signature
    state[ANALYSIS_PERIOD_VALUE_KEY] = normalized
    if is_new_file or ANALYSIS_PERIOD_DRAFT_KEY not in state:
        state[ANALYSIS_PERIOD_DRAFT_KEY] = normalized
    if is_new_file or ANALYSIS_PERIOD_PRESET_KEY not in state:
        state[ANALYSIS_PERIOD_PRESET_KEY] = "Toute la p\u00e9riode"
    if is_new_file:
        state.pop(ANALYSIS_PERIOD_NOTICE_KEY, None)
    return normalized, message


def apply_analysis_period_selection(state, min_date, max_date) -> tuple[tuple[object, object], str | None]:
    """Commit the form draft. Called only by the Apply button callback."""
    active, _ = normalize_analysis_period(state.get(ANALYSIS_PERIOD_VALUE_KEY), min_date, max_date)
    draft, _ = normalize_analysis_period(state.get(ANALYSIS_PERIOD_DRAFT_KEY, active), min_date, max_date)
    preset = state.get(ANALYSIS_PERIOD_PRESET_KEY, "Toute la p\u00e9riode")

    if preset != "Personnalis\u00e9e" and draft == active:
        candidate = period_from_preset(preset, min_date, max_date)
    else:
        candidate = draft
        state[ANALYSIS_PERIOD_PRESET_KEY] = "Personnalis\u00e9e"

    normalized, message = normalize_analysis_period(candidate, min_date, max_date)
    state[ANALYSIS_PERIOD_VALUE_KEY] = normalized
    # Form callbacks run before the next script pass, so the picker is synchronized safely.
    state[ANALYSIS_PERIOD_DRAFT_KEY] = normalized
    if message:
        state[ANALYSIS_PERIOD_NOTICE_KEY] = message
    else:
        state.pop(ANALYSIS_PERIOD_NOTICE_KEY, None)
    return normalized, message


def render_analysis_period_selector(file_signature, min_date, max_date) -> tuple[tuple[object, object], str | None]:
    active_period, initialization_message = initialize_analysis_period_selector(
        st.session_state,
        file_signature,
        min_date,
        max_date,
    )

    def apply_period() -> None:
        apply_analysis_period_selection(st.session_state, min_date, max_date)

    active_label = f"\U0001f4c5 {format_date(active_period[0])} - {format_date(active_period[1])}"
    _, selector_col = st.columns([4.2, 1.3])
    with selector_col:
        with st.popover(active_label):
            st.markdown("**P\u00e9riode d'analyse**")
            with st.form(ANALYSIS_PERIOD_FORM_KEY, border=False):
                st.selectbox("Choix rapide", PERIOD_PRESET_OPTIONS, key=ANALYSIS_PERIOD_PRESET_KEY)
                st.date_input(
                    "Dates personnalis\u00e9es",
                    min_value=min_date,
                    max_value=max_date,
                    key=ANALYSIS_PERIOD_DRAFT_KEY,
                )
                st.caption("Les raccourcis utilisent la derni\u00e8re date disponible du fichier.")
                st.form_submit_button("Appliquer", on_click=apply_period)

    active_period = st.session_state.get(ANALYSIS_PERIOD_VALUE_KEY, active_period)
    notice = st.session_state.get(ANALYSIS_PERIOD_NOTICE_KEY)
    if initialization_message or notice:
        st.info(initialization_message or notice)
    return active_period, initialization_message or notice


def format_date(value) -> str:
    if value is None or pd.isna(value):
        return DASH
    return pd.Timestamp(value).strftime("%Y/%m/%d")


def apply_date_filter(df: pd.DataFrame, selected_date_type: str, start_date, end_date) -> tuple[pd.DataFrame, dict]:
    available = detect_date_columns(df)
    date_col = get_date_column(selected_date_type, available)
    fallback_columns = df.attrs.get("date_fallback_columns", {}) or {}
    context = {
        "selected_date_type": selected_date_type,
        "date_column": date_col,
        "date_fallback_used": bool(date_col and date_col in fallback_columns),
        "date_fallback_source": fallback_columns.get(date_col),
        "start_date": start_date,
        "end_date": end_date,
        "missing_date_count": len(df),
        "input_rows": len(df),
        "kept_rows": 0,
    }
    if not date_col:
        return df.iloc[0:0].copy(), context
    parsed = date_series(df, date_col)
    valid = parsed.notna()
    context["missing_date_count"] = int((~valid).sum())
    if not valid.any():
        return df.iloc[0:0].copy(), context
    if start_date is None or end_date is None:
        filtered = df[valid].copy()
    else:
        date_values = parsed.dt.date
        mask = valid & date_values.ge(start_date) & date_values.le(end_date)
        filtered = df[mask].copy()
    context["kept_rows"] = len(filtered)
    return filtered, context


def summarize_missing_dates(df: pd.DataFrame, scope_label: str | None = None) -> pd.DataFrame:
    rows = []
    total = len(df)
    scope = f"{scope_label} - " if scope_label else ""
    for label, col in DATE_TYPE_COLUMNS.items():
        parsed = date_series(df, col)
        missing = int(parsed.isna().sum())
        rows.append(
            {
                "controle": f"Commandes sans {label.lower()}",
                "valeur": missing,
                "attendu": "0 si la date est obligatoire pour ce mode",
                "statut": "OK" if missing == 0 else "A auditer",
                "details": f"{scope}{missing} / {total} commandes exclues si ce type de date est choisi",
            }
        )
    return pd.DataFrame(rows)


def render_date_context(date_context: dict) -> None:
    label = date_context.get("selected_date_type", DATE_TYPE_OPTIONS[0])
    start = format_date(date_context.get("start_date"))
    end = format_date(date_context.get("end_date"))
    missing = int(date_context.get("missing_date_count", 0) or 0)
    kept_after_date = int(date_context.get("kept_rows", 0) or 0)
    kept_after_filters = int(date_context.get("kept_rows_after_filters", kept_after_date) or 0)
    total = int(date_context.get("input_rows", kept_after_date) or kept_after_date)
    column = date_context.get("date_column", DASH)
    active_filters = date_context.get("active_secondary_filters", []) or []
    st.caption(
        f"Cohorte : {label} - colonne utilisee : {column} - periode : {start} - {end} - "
        f"apres filtre date : {kept_after_date} / {total} commandes - "
        f"apres filtres actifs : {kept_after_filters} commandes."
    )
    if active_filters:
        chunks = []
        for item in active_filters:
            values = item.get("values", [])
            sample = ", ".join(str(value) for value in values[:3])
            suffix = f" ({sample})" if sample else ""
            chunks.append(f"{item.get('label', 'Filtre')}: {item.get('count', len(values))}{suffix}")
        st.caption("Filtres secondaires actifs : " + "; ".join(chunks) + ".")
    else:
        st.caption("Aucun filtre secondaire actif.")
    if date_context.get("date_fallback_used"):
        source = date_context.get("date_fallback_source", DASH)
        st.warning(f"Mapping des dates base sur les positions AG-AK car les noms de colonnes n'ont pas ete reconnus. Colonne utilisee : {column} <= {source}. Verifier que le format d'export n'a pas change.")
    if missing:
        st.info(f"{missing} commande(s) exclue(s) car la date {label.lower()} est manquante ou invalide.")
    if label == "Date de confirmation":
        st.warning("Mode Date de confirmation : le taux confirmation est moins adapte pour mesurer la conversion des commandes recues. Utiliser Date de creation ou Date d'affectation pour mesurer la vraie conversion confirmation.")


def build_active_filters_summary(date_context: dict) -> str:
    label = date_context.get("selected_date_type", DATE_TYPE_OPTIONS[0])
    start = format_date(date_context.get("start_date"))
    end = format_date(date_context.get("end_date"))
    parts = [f"Date d'analyse : {label}", f"Periode : {start} - {end}"]
    active_filters = date_context.get("active_secondary_filters", []) or []
    if active_filters:
        for item in active_filters:
            values = item.get("values", [])
            if not values:
                continue
            shown = ", ".join(str(value) for value in values[:3])
            if len(values) > 3:
                shown += f" +{len(values) - 3}"
            parts.append(f"{item.get('label', 'Filtre')} : {shown}")
    else:
        parts.append("aucun filtre secondaire")
    return "Filtres actifs : " + " - ".join(parts)


def render_active_filters_banner(date_context: dict) -> None:
    st.markdown(f'<div class="filter-banner">{html_text(build_active_filters_summary(date_context))}</div>', unsafe_allow_html=True)


def amount_totals(df: pd.DataFrame, metrics: dict) -> dict[str, float | None]:
    order_amounts = (
        df.groupby("order_id", dropna=False)
        .agg(ca_total=("ca_total", "max"), is_confirmed_net=("is_confirmed_net", "max"))
        if {"order_id", "ca_total", "is_confirmed_net"}.issubset(df.columns)
        else pd.DataFrame(columns=["ca_total", "is_confirmed_net"])
    )
    total_ca = float(order_amounts["ca_total"].sum())
    confirmed_ca = float(order_amounts.loc[order_amounts["is_confirmed_net"].fillna(False), "ca_total"].sum())
    received = metrics.get("orders_received", 0)
    delivered = metrics.get("orders_delivered", 0)
    returned = metrics.get("orders_returned_failed", 0)
    return {
        "ca_total_orders": total_ca,
        "ca_confirmed": confirmed_ca,
        "panier_moyen_livre": safe_ratio(metrics.get("ca_delivered", 0), delivered),
        "ca_logistics": metrics.get("ca_logistics", metrics.get("ca_dispatch", 0) + metrics.get("ca_in_delivery", 0)),
        "panier_moyen_commande": safe_ratio(total_ca, received),
        "valeur_moyenne_retour": safe_ratio(metrics.get("ca_returned_failed", 0), returned),
    }


def owner_money_sections(metrics: dict, amounts: dict[str, float | None]) -> list[tuple[str, str, str, str]]:
    total_ca = float(amounts.get("ca_total_orders", 0) or 0)

    def note(count: int, amount: float, label: str = "commandes") -> str:
        share = safe_ratio(amount, total_ca)
        return f"{count} {label} \u00b7 {pct(share)} du CA re\u00e7u" if share is not None else f"{count} {label}"

    delivered = int(metrics.get("orders_delivered", 0) or 0)
    return [
        ("CA total des commandes re\u00e7ues", money(total_ca), f"{int(metrics.get('orders_received', 0) or 0)} commandes re\u00e7ues", "neutral"),
        ("CA confirm\u00e9", money(amounts.get("ca_confirmed")), note(int(metrics.get("orders_confirmed_net", 0) or 0), float(amounts.get("ca_confirmed", 0) or 0)), "info"),
        ("CA en pr\u00e9paration", money(metrics.get("ca_preparation")), note(int(metrics.get("orders_preparation", 0) or 0), float(metrics.get("ca_preparation", 0) or 0)), "warn"),
        ("CA en dispatch", money(metrics.get("ca_dispatch")), note(int(metrics.get("orders_dispatch", 0) or 0), float(metrics.get("ca_dispatch", 0) or 0)), "warn"),
        ("CA en cours de livraison", money(metrics.get("ca_in_delivery")), note(int(metrics.get("orders_in_delivery", 0) or 0), float(metrics.get("ca_in_delivery", 0) or 0)), "warn"),
        ("CA livr\u00e9 finalis\u00e9", money(metrics.get("ca_delivered")), note(delivered, float(metrics.get("ca_delivered", 0) or 0)), "good"),
        ("Perte CA retours", money(metrics.get("ca_returned_failed")), note(int(metrics.get("orders_returned_failed", 0) or 0), float(metrics.get("ca_returned_failed", 0) or 0)), "loss"),
        ("Panier moyen livr\u00e9", money(amounts.get("panier_moyen_livre")), f"{delivered} commandes livr\u00e9es finalis\u00e9es", "neutral"),
    ]


def confirmation_funnel_counts(metrics: dict) -> tuple[int, float | None, float | None]:
    """Return the exclusive confirmed stage used by the visual COD funnel."""
    received = int(metrics.get("orders_received", 0) or 0)
    confirmed_net = int(metrics.get("orders_confirmed_net", 0) or 0)
    in_confirmation = int(metrics.get("orders_in_confirmation", 0) or 0)
    unclassified = int(metrics.get("orders_unclassified", 0) or 0)
    confirmed = max(confirmed_net - in_confirmation - unclassified, 0)
    return confirmed, safe_ratio(confirmed, received), safe_ratio(int(metrics.get("orders_preparation", 0) or 0), confirmed)


def displayed_reception_rates(metrics: dict, confirmation_rate: float | None) -> tuple[float | None, float | None, float | None]:
    """Keep the three exclusive reception outcomes at exactly 100.0% on cards."""
    received = int(metrics.get("orders_received", 0) or 0)
    if received == 0:
        return None, None, None
    in_confirmation_rate = safe_ratio(int(metrics.get("orders_in_confirmation", 0) or 0), received)
    cancellation_rate = safe_ratio(int(metrics.get("orders_cancelled", 0) or 0), received)
    pending_tenths = round((in_confirmation_rate or 0) * 1000)
    cancelled_tenths = round((cancellation_rate or 0) * 1000)
    confirmed_display_rate = max(0, 1000 - pending_tenths - cancelled_tenths) / 1000
    return confirmed_display_rate, in_confirmation_rate, cancellation_rate


def owner_kpi_sections(metrics: dict, thresholds: dict[str, float]) -> list[tuple[str, str, str, str]]:
    received = int(metrics.get("orders_received", 0) or 0)
    confirmed, confirmation_rate, preparation_rate = confirmation_funnel_counts(metrics)
    confirmation_display_rate, in_confirmation_rate, cancellation_display_rate = displayed_reception_rates(metrics, confirmation_rate)
    in_confirmation = int(metrics.get("orders_in_confirmation", 0) or 0)
    preparation = int(metrics.get("orders_preparation", 0) or 0)
    sent = int(metrics.get("orders_sent", 0) or 0)
    dispatch = int(metrics.get("orders_dispatch", 0) or 0)
    in_delivery = int(metrics.get("orders_in_delivery", 0) or 0)
    delivered = int(metrics.get("orders_delivered", 0) or 0)
    cancelled = int(metrics.get("orders_cancelled", 0) or 0)

    dispatch_rate = safe_ratio(dispatch, sent)
    in_delivery_rate = safe_ratio(in_delivery, sent)

    return [
        ("Commandes reçues", str(received), "Base de la période", "neutral"),
        ("Taux confirmé", pct(confirmation_display_rate), f"{confirmed} commandes confirmées\nBase : {received} reçues", tone_class(confirmation_rate, "confirmation", thresholds)),
        ("Taux en cours de confirmation", pct(in_confirmation_rate), f"{in_confirmation} commandes en confirmation\nBase : {received} reçues", tone_class(in_confirmation_rate, "preparation", thresholds)),
        ("Taux en préparation", pct(preparation_rate), f"{preparation} commandes en préparation\nBase : {confirmed} confirmées", tone_class(preparation_rate, "preparation", thresholds)),
        ("Taux en dispatch", pct(dispatch_rate), f"{dispatch} commandes en dispatch\nBase : {sent} expédiées", "warn" if dispatch else "good"),
        ("Taux en cours de livraison", pct(in_delivery_rate), f"{in_delivery} commandes en livraison\nBase : {sent} expédiées", "warn" if in_delivery else "good"),
        ("Taux livré", pct(metrics.get("delivery_total_rate_on_sent")), f"{delivered} commandes livrées\nBase : {sent} expédiées", tone_class(metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
        ("Taux de transformation brute", pct(metrics.get("transformation_real_rate")), f"{delivered} livrées / {received} reçues", tone_class(metrics.get("transformation_real_rate"), "transformation", thresholds)),
        ("Taux annulé", pct(cancellation_display_rate), f"{cancelled} commandes annulées\nBase : {received} reçues", tone_class(metrics.get("cancellation_rate"), "cancellation", thresholds)),
    ]


def owner_priority(metrics: dict) -> tuple[str, int, float]:
    priorities = [
        ("commandes non envoy\u00e9es", int(metrics.get("orders_preparation", 0) or 0), float(metrics.get("ca_preparation", 0) or 0)),
        ("commandes en cours logistique", int(metrics.get("orders_logistics", 0) or 0), float(metrics.get("ca_logistics", 0) or 0)),
        ("retours / \u00e9checs", int(metrics.get("orders_returned_failed", 0) or 0), float(metrics.get("ca_returned_failed", 0) or 0)),
    ]
    return max(priorities, key=lambda item: item[1])


def render_owner_global_dashboard(
    df: pd.DataFrame,
    metrics: dict,
    thresholds: dict[str, float],
    priority_actions: pd.DataFrame | None = None,
) -> None:
    cockpit_heading(
        "Parcours COD",
        "Réception : confirmées + en cours de confirmation + annulées = 100,0 %. Les étapes suivantes utilisent leur base affichée.",
    )
    journey = owner_kpi_sections(metrics, thresholds)
    render_stage_kpis("1. Reception", "Ce qui entre dans le funnel et ce qui en sort avant expedition.", journey[:4])
    render_stage_kpis("2. Execution", "Les commandes confirmees progressent vers une livraison finalisee.", journey[4:8])
    render_stage_kpis("3. Resultat", "La transformation brute replace la livraison dans le volume recu.", journey[8:])
    cockpit_heading(
        "Argent / Chiffre d'affaires",
        "CA potentiel, bloqu\u00e9, s\u00e9curis\u00e9 ou perdu sur le p\u00e9rim\u00e8tre actif.",
    )
    render_section_kpis(owner_money_sections(metrics, amount_totals(df, metrics)), max_per_row=4)
    if priority_actions is not None:
        render_priority_focus(priority_actions)


def top_known(df: pd.DataFrame, label_col: str, sort_col: str, limit: int = 5) -> pd.DataFrame:
    if df.empty or label_col not in df.columns or sort_col not in df.columns:
        return df.iloc[0:0].copy()
    out = df[df[label_col].apply(is_known_value)].copy()
    out = out[pd.to_numeric(out[sort_col], errors="coerce").fillna(0).gt(0)]
    return sort_for_display(out, [sort_col]).head(limit)


def render_global_business_kpis(metrics: dict, thresholds: dict[str, float]) -> None:
    dispatch = int(metrics.get("orders_dispatch", 0) or 0)
    in_delivery = int(metrics.get("orders_in_delivery", 0) or 0)
    logistics = int(metrics.get("orders_logistics", dispatch + in_delivery) or 0)
    risk_orders = int(metrics["orders_preparation"] + dispatch + in_delivery + metrics["orders_returned_failed"])
    hero_items = [
        ("Commandes recues", str(metrics["orders_received"]), f"Base cohorte - {pct(metrics['confirmation_rate'])} confirmees", "neutral", "Volume"),
        ("Taux confirmation", pct(metrics["confirmation_rate"]), f"{metrics['orders_confirmed_net']} confirmees / {metrics['orders_received']} recues", tone_class(metrics.get("confirmation_rate"), "confirmation", thresholds), "Conf."),
        ("Transformation reelle", pct(metrics["transformation_real_rate"]), f"{metrics['orders_delivered']} livrees / {metrics['orders_received']} recues", tone_class(metrics.get("transformation_real_rate"), "transformation", thresholds), "Ratio"),
        ("CA livre finalise", money(metrics["ca_delivered"]), f"{metrics['orders_delivered']} livrees - panier moyen {money(safe_ratio(metrics.get('ca_delivered', 0), metrics.get('orders_delivered', 0)))}", "good", "CA"),
        ("Livraison / expediees", pct(metrics["delivery_total_rate_on_sent"]), f"{metrics['orders_delivered']} livrees / {metrics['orders_sent']} expediees", tone_class(metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds), "Livr."),
        ("En cours logistique", str(logistics), f"{pct(metrics.get('logistics_rate_on_sent'))} des expediees - Dispatch : {dispatch} - Livraison : {in_delivery}", "warn", "Cours"),
        ("Taux retour", pct(metrics["return_rate_on_sent"]), f"{metrics['orders_returned_failed']} retours / {metrics['orders_sent']} expediees", tone_class(metrics.get("return_rate_on_sent"), "return", thresholds), "Retour"),
        ("Perte CA retours", money(metrics["ca_returned_failed"]), f"{metrics['orders_returned_failed']} retours - valeur moyenne {money(safe_ratio(metrics.get('ca_returned_failed', 0), metrics.get('orders_returned_failed', 0)))}", tone_class(metrics.get("return_rate_on_sent"), "return", thresholds), "Perte"),
        ("Commandes a risque", str(risk_orders), f"{pct(safe_ratio(risk_orders, metrics.get('orders_confirmed_net', 0)))} des confirmees - prep + dispatch + livraison + retours", tone_class(risk_orders, "risk", thresholds), "Risque"),
    ]
    for start in range(0, len(hero_items), 4):
        cols = st.columns(4)
        for col, (title, value, subtitle, tone, badge) in zip(cols, hero_items[start:start + 4]):
            with col:
                hero_card(title, value, subtitle, tone, badge)


def render_global_kpi_blocks(metrics: dict, thresholds: dict[str, float], money_details: dict[str, float | None]) -> None:
    dispatch = int(metrics.get("orders_dispatch", 0) or 0)
    in_delivery = int(metrics.get("orders_in_delivery", 0) or 0)
    logistics = int(metrics.get("orders_logistics", dispatch + in_delivery) or 0)
    col_orders, col_delivery, col_money = st.columns(3)
    with col_orders:
        cockpit_heading("Commandes", "Confirmation et blocage avant expedition.")
        render_kpi_stack([
            ("Commandes recues", metrics["orders_received"], f"{metrics['orders_confirmed_net']} confirmees - {metrics['orders_cancelled']} annulees", "neutral"),
            ("Annulees avant expedition", metrics["orders_cancelled"], f"{pct(metrics.get('cancellation_rate'))} des recues", tone_class(metrics.get("cancellation_rate"), "return", thresholds)),
            ("En confirmation", metrics.get("orders_in_confirmation", 0), f"{pct(safe_ratio(metrics.get('orders_in_confirmation', 0), metrics.get('orders_received', 0)))} des recues", "warn"),
            ("Confirmees nettes", metrics["orders_confirmed_net"], f"{pct(metrics['confirmation_rate'])} des recues - {metrics['orders_cancelled']} annulees", "info"),
            ("Confirmees non expediees", metrics["orders_preparation"], f"{pct(metrics.get('preparation_blockage_rate'))} des confirmees", tone_class(metrics.get("preparation_blockage_rate"), "return", thresholds)),
        ])
    with col_delivery:
        cockpit_heading("Expedition / livraison", "Performance apres remise au livreur.")
        render_kpi_stack([
            ("Expediees", metrics["orders_sent"], f"{pct(metrics['shipping_rate_global'])} des confirmees", "neutral"),
            ("En dispatch", dispatch, f"{pct(safe_ratio(dispatch, metrics.get('orders_sent', 0)))} des expediees", "warn"),
            ("En cours livraison", in_delivery, f"{pct(metrics.get('in_delivery_rate_on_sent'))} des expediees", "warn"),
            ("En cours logistique", logistics, f"{pct(metrics.get('logistics_rate_on_sent'))} des expediees - Dispatch : {dispatch} - Livraison : {in_delivery}", "warn"),
            ("Livraison / expediees", pct(metrics["delivery_total_rate_on_sent"]), f"{metrics['orders_delivered']} livrees / {metrics['orders_sent']} expediees", tone_class(metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
            ("Taux retour", pct(metrics["return_rate_on_sent"]), f"{metrics['orders_returned_failed']} retours / {metrics['orders_sent']} expediees", tone_class(metrics.get("return_rate_on_sent"), "return", thresholds)),
        ])
    with col_money:
        cockpit_heading("Argent", "CA securise, bloque ou perdu.")
        render_kpi_stack([
            ("CA livre finalise", money(metrics["ca_delivered"]), f"{metrics['orders_delivered']} livrees - panier moyen {money(money_details.get('panier_moyen_livre'))}", "good"),
            ("CA en dispatch", money(metrics.get("ca_dispatch", 0)), f"{dispatch} commandes dispatch", "warn"),
            ("CA en cours livraison", money(metrics["ca_in_delivery"]), f"{in_delivery} commandes livraison", "warn"),
            ("CA en cours logistique", money(metrics.get("ca_logistics", metrics.get("ca_dispatch", 0) + metrics["ca_in_delivery"])), f"{logistics} commandes non finalisees", "warn"),
            ("CA confirme non expedie", money(metrics["ca_preparation"]), f"{metrics['orders_preparation']} commandes preparation", "warn"),
            ("Perte CA retours", money(metrics["ca_returned_failed"]), f"{metrics['orders_returned_failed']} retours - valeur moyenne {money(money_details.get('valeur_moyenne_retour'))}", "loss"),
        ])

def render_global_mini_tables(products: pd.DataFrame, wilayas: pd.DataFrame, confirmation: pd.DataFrame, livreurs: pd.DataFrame, thresholds: dict[str, float]) -> None:
    cockpit_heading("Performance detaillee", "Top 5 par tableau, sans recommandations longues.")
    top_confirmation = top_known(confirmation, "confirmatrice", "commandes_recues")
    top_livreurs = top_known(livreurs, "livreur", "ca_livre")
    blocks = [
        ("Top produits par CA livre", top_known(products, "produit", "ca_livre"), ["produit", "commandes_recues", "taux_transformation_reel", "taux_retour", "ca_livre"], "Aucun produit avec CA livre."),
        ("Top produits par perte CA retours", top_known(products, "produit", "ca_retours"), ["produit", "retours", "taux_retour", "ca_retours"], "Aucune perte produit visible."),
        ("Top wilayas par CA livre", top_known(wilayas, "wilaya", "ca_livre"), ["wilaya", "commandes_recues", "taux_transformation_reel", "taux_retour", "ca_livre"], "Aucune wilaya avec CA livre."),
        ("Top wilayas par perte CA retours", top_known(wilayas, "wilaya", "ca_retours"), ["wilaya", "retours", "taux_retour", "ca_retours"], "Aucune perte wilaya visible."),
        ("Performance confirmatrices", top_confirmation, ["confirmatrice", "commandes_recues", "taux_confirmation", "taux_transformation_reel", "ca_livre"], "Aucune confirmatrice exploitable."),
        ("Performance livreurs", top_livreurs, ["livreur", "commandes_envoyees", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_retours"], "Aucun livreur exploitable."),
    ]
    for start in range(0, len(blocks), 3):
        cols = st.columns(3)
        for col, (title, frame, columns, empty) in zip(cols, blocks[start:start + 3]):
            with col:
                st.markdown(f"**{title}**")
                render_data_table(frame, columns, thresholds, empty, height=240)

def no_reliable_message() -> str:
    return "Aucun \u00e9l\u00e9ment fiable \u00e0 classer avec les seuils actuels."


def sort_for_display(df: pd.DataFrame, columns: list[str], ascending: bool = False) -> pd.DataFrame:
    if df.empty:
        return df
    available = [col for col in columns if col in df.columns]
    if not available:
        return df
    return df.sort_values(available, ascending=[ascending] * len(available))


def adaptive_height(df: pd.DataFrame, min_height: int = 132, max_height: int = 360) -> int:
    if df.empty:
        return min_height
    return max(min_height, min(max_height, 42 + len(df) * 34))


def existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return unique_existing_columns(df, columns)


def display_subset(df: pd.DataFrame, columns: list[str], sort_by: list[str] | str | None = None, ascending: bool = False) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    if sort_by:
        sort_cols = [sort_by] if isinstance(sort_by, str) else sort_by
        out = sort_for_display(out, sort_cols, ascending=ascending)
    cols = existing_columns(out, columns)
    return out[cols].copy() if cols else out


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


def top_label(df: pd.DataFrame, label_col: str, sort_col: str, volume_col: str | None = None, volume_min: int = 0) -> str:
    if df.empty or label_col not in df.columns or sort_col not in df.columns:
        return DASH
    reliable = df[df[label_col].apply(is_known_value)].copy()
    if volume_col and volume_col in reliable.columns:
        reliable = reliable[pd.to_numeric(reliable[volume_col], errors="coerce").fillna(0).ge(volume_min)]
    if reliable.empty:
        return DASH
    return str(reliable.sort_values(sort_col, ascending=False).iloc[0].get(label_col, DASH))


def weighted_rate(df: pd.DataFrame, numerator_col: str, denominator_col: str) -> float | None:
    if df.empty or numerator_col not in df.columns or denominator_col not in df.columns:
        return None
    numerator = pd.to_numeric(df[numerator_col], errors="coerce").fillna(0).sum()
    denominator = pd.to_numeric(df[denominator_col], errors="coerce").fillna(0).sum()
    return safe_ratio(numerator, denominator)


def product_wilaya_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = grouped_advice_metrics(df, ["Nom produit", "Wilaya"])
    if out.empty:
        return out.rename(columns={"Nom produit": "produit", "Wilaya": "wilaya"})
    orders = orders_for_advice(df)
    if not orders.empty and {"Nom produit", "Wilaya", "Livreur"}.issubset(orders.columns):
        counts = orders.groupby(["Nom produit", "Wilaya", "Livreur"], dropna=False).size().reset_index(name="n")
        idx = counts.groupby(["Nom produit", "Wilaya"])["n"].idxmax()
        dominant = counts.loc[idx, ["Nom produit", "Wilaya", "Livreur"]].rename(columns={"Livreur": "livreur_dominant"})
        out = out.merge(dominant, on=["Nom produit", "Wilaya"], how="left")
    if "livreur_dominant" not in out.columns:
        out["livreur_dominant"] = DASH
    return out.rename(columns={"Nom produit": "produit", "Wilaya": "wilaya"})


def livreur_wilaya_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = grouped_advice_metrics(df, ["Wilaya", "Livreur"])
    if out.empty:
        return out.rename(columns={"Wilaya": "wilaya", "Livreur": "livreur"})
    return out.rename(columns={"Wilaya": "wilaya", "Livreur": "livreur"})



def volume_reliability(value, volume_min: int) -> str:
    volume = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
    return "Volume suffisant" if volume >= volume_min else "Echantillon faible"


def quick_read(row: pd.Series, kind: str, volume_col: str, volume_min: int, thresholds: dict[str, float]) -> str:
    if volume_reliability(row.get(volume_col, 0), volume_min) != "Volume suffisant":
        return "Echantillon faible"
    confirmation = row.get("taux_confirmation")
    transformation = row.get("taux_transformation_reel")
    delivery = row.get("taux_livraison_total")
    returns = row.get("taux_retour")
    ca = row.get("ca_livre", 0) or 0
    in_delivery = (row.get("en_dispatch", 0) or 0) + (row.get("en_livraison", 0) or 0)
    sent = row.get("commandes_envoyees", 0) or 0
    if returns is not None and pd.notna(returns) and returns >= thresholds["return_red"]:
        if kind == "sku":
            return "SKU retour eleve"
        return "Retour eleve"
    if confirmation is not None and pd.notna(confirmation) and confirmation < thresholds["confirmation_orange"]:
        return "Confirmation faible"
    if transformation is not None and pd.notna(transformation) and transformation < thresholds["delivery_orange"] and kind in {"source", "sku", "confirmatrice_produit", "source_produit"}:
        return "Transformation faible"
    if delivery is not None and pd.notna(delivery) and delivery < thresholds["delivery_orange"]:
        return "Livraison faible"
    if sent and safe_ratio(in_delivery, sent) and safe_ratio(in_delivery, sent) > 0.30:
        return "En cours eleve"
    if ca > 0 and delivery is not None and pd.notna(delivery) and delivery >= thresholds["delivery_green"] and (returns is None or pd.isna(returns) or returns <= thresholds["return_orange"]):
        if kind == "sku":
            return "SKU solide"
        if kind in {"source", "source_produit"}:
            return "Source propre"
        if kind == "product_wilaya":
            return "Bon volume / bonne zone"
        return "Livraison correcte"
    if ca > 0:
        return "CA interessant"
    return "A surveiller"


def add_volume_reading(df: pd.DataFrame, volume_col: str, volume_min: int, kind: str, thresholds: dict[str, float]) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["fiabilite_volume"] = pd.Series(dtype=object)
        out["lecture_rapide"] = pd.Series(dtype=object)
        return out
    out["fiabilite_volume"] = out[volume_col].apply(lambda value: volume_reliability(value, volume_min)) if volume_col in out.columns else "Echantillon faible"
    out["lecture_rapide"] = out.apply(lambda row: quick_read(row, kind, volume_col, volume_min, thresholds), axis=1)
    return out


def cross_performance(df: pd.DataFrame, group_cols: list[str], rename: dict[str, str], volume_col: str, volume_min: int, kind: str, thresholds: dict[str, float]) -> pd.DataFrame:
    out = grouped_advice_metrics(df, group_cols)
    if out.empty:
        return pd.DataFrame(columns=list(rename.values()))
    out = out.rename(columns=rename)
    return add_volume_reading(out, volume_col, volume_min, kind, thresholds)


def product_livreur_performance(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    out = cross_performance(df, ["Nom produit", "Livreur"], {"Nom produit": "produit", "Livreur": "livreur"}, "commandes_envoyees", volume_min, "product_livreur", thresholds)
    if not out.empty and "livrees" in out.columns:
        out["panier_moyen_livre"] = out.apply(lambda row: safe_ratio(row.get("ca_livre", 0), row.get("livrees", 0)), axis=1)
    return out


def source_product_performance(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    if "Source" not in df.columns:
        return pd.DataFrame()
    return cross_performance(df, ["Source", "Nom produit"], {"Source": "source", "Nom produit": "produit"}, "commandes_recues", volume_min, "source_produit", thresholds)


def sku_product_performance(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    if "SKU produit" not in df.columns:
        return pd.DataFrame()
    return cross_performance(df, ["SKU produit", "Nom produit"], {"SKU produit": "sku_produit", "Nom produit": "produit"}, "commandes_recues", volume_min, "sku", thresholds)


def confirmatrice_product_performance(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    col = "Affect\u00e9e \u00e0"
    if col not in df.columns:
        return pd.DataFrame()
    return cross_performance(df, [col, "Nom produit"], {col: "confirmatrice", "Nom produit": "produit"}, "commandes_recues", volume_min, "confirmatrice_produit", thresholds)


def wilaya_livreur_comparison(df: pd.DataFrame, volume_min: int) -> pd.DataFrame:
    metrics = livreur_wilaya_performance(df)
    if metrics.empty:
        return pd.DataFrame()
    rows = []
    for wilaya, group in metrics.groupby("wilaya", dropna=False):
        if not is_known_value(wilaya):
            continue
        ranked = group.sort_values("commandes_envoyees", ascending=False).copy()
        dominant = ranked.iloc[0]
        alternatives = ranked.iloc[1:]
        alternative = alternatives.iloc[0] if not alternatives.empty else None
        dominant_reliable = int(dominant.get("commandes_envoyees", 0)) >= volume_min
        alternative_reliable = alternative is not None and int(alternative.get("commandes_envoyees", 0)) >= volume_min
        delivery_gap = None
        return_gap = None
        lecture = "Donnees insuffisantes"
        if alternative is not None:
            delivery_gap = (alternative.get("taux_livraison_total") or 0) - (dominant.get("taux_livraison_total") or 0)
            return_gap = (dominant.get("taux_retour") or 0) - (alternative.get("taux_retour") or 0)
            if dominant_reliable and alternative_reliable:
                if abs(delivery_gap) < 0.05 and abs(return_gap) < 0.05:
                    lecture = "Ecart faible"
                elif delivery_gap > 0.05 or return_gap > 0.05:
                    lecture = "Alternative meilleure"
                else:
                    lecture = "Dominant meilleur"
        rows.append(
            {
                "wilaya": wilaya,
                "livreur_dominant": dominant.get("livreur", DASH),
                "expediees_dominant": int(dominant.get("commandes_envoyees", 0)),
                "taux_livraison_dominant": dominant.get("taux_livraison_total"),
                "taux_retour_dominant": dominant.get("taux_retour"),
                "livreur_alternatif": alternative.get("livreur", DASH) if alternative is not None else DASH,
                "expediees_alternatif": int(alternative.get("commandes_envoyees", 0)) if alternative is not None else 0,
                "taux_livraison_alternatif": alternative.get("taux_livraison_total") if alternative is not None else None,
                "taux_retour_alternatif": alternative.get("taux_retour") if alternative is not None else None,
                "ecart_livraison": delivery_gap,
                "ecart_retour": return_gap,
                "fiabilite_comparaison": "Volume suffisant" if dominant_reliable and (alternative is None or alternative_reliable) else "Donnees insuffisantes",
                "lecture_rapide": lecture,
            }
        )
    return pd.DataFrame(rows)

def validation_value(validation_checks: pd.DataFrame, control_contains: str, default=0):
    if validation_checks.empty:
        return default
    row = validation_checks[validation_checks["controle"].astype(str).str.contains(control_contains, case=False, na=False)]
    if row.empty:
        return default
    value = row.iloc[0].get("valeur", default)
    parsed = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(parsed) else int(parsed)

def data_quality_has_warning(validation_checks: pd.DataFrame) -> bool:
    watched = [
        "Commandes sans wilaya",
        "Commandes sans produit",
        "Commandes sans statut",
        "Doublons lignes par commande",
        "Doublons ID commande",
        "Statuts inconnus",
        "Commandes non class",
        "Mapping dates AG-AK",
        "Commandes avec montant",
    ]
    if validation_checks.empty:
        return False
    for _, row in validation_checks.iterrows():
        control = str(row.get("controle", ""))
        if not any(item.lower() in control.lower() for item in watched):
            continue
        value = pd.to_numeric(row.get("valeur"), errors="coerce")
        if pd.notna(value) and value > 0:
            return True
    return False


def orders_for_advice(df: pd.DataFrame) -> pd.DataFrame:
    affectee_col = "Affect\u00e9e \u00e0"
    aggregations = {
        "Source": "first",
        "SKU produit": "first",
        "Nom produit": "first",
        "Wilaya": "first",
        "Livreur": "first",
        affectee_col: "first",
        "is_cancelled": "max",
        "is_confirmed_net": "max",
        "is_in_confirmation": "max",
        "is_preparation": "max",
        "is_dispatch": "max",
        "is_sent": "max",
        "is_delivered": "max",
        "is_in_delivery": "max",
        "is_return_or_failed": "max",
        "ca_delivered": "max",
        "ca_in_confirmation": "max",
        "ca_dispatch": "max",
        "ca_in_delivery": "max",
        "ca_preparation": "max",
        "ca_returned_failed": "max",
    }
    available = {col: agg for col, agg in aggregations.items() if col in df.columns}
    return df.groupby("order_id", dropna=False).agg(available).reset_index()


def dominant_value(frame: pd.DataFrame, group_col: str, value_col: str, fallback: str = "Non renseign\u00e9") -> pd.Series:
    if frame.empty or group_col not in frame.columns or value_col not in frame.columns:
        return pd.Series(dtype=object)
    counts = frame.groupby([group_col, value_col], dropna=False).size().reset_index(name="n")
    idx = counts.groupby(group_col)["n"].idxmax()
    return counts.loc[idx].set_index(group_col)[value_col].fillna(fallback)


def safe_ratio(value: float, total: float) -> float | None:
    if not total:
        return None
    return float(value) / float(total)


def grouped_advice_metrics(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    orders = orders_for_advice(df)
    if orders.empty or any(col not in orders.columns for col in group_cols):
        return pd.DataFrame()
    rows = []
    for keys, group in orders.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        received = len(group)
        confirmed = int(group["is_confirmed_net"].sum())
        sent = int(group["is_sent"].sum())
        in_confirmation = int(group["is_in_confirmation"].sum()) if "is_in_confirmation" in group.columns else 0
        preparation = int(group["is_preparation"].sum()) if "is_preparation" in group.columns else 0
        dispatch = int(group["is_dispatch"].sum()) if "is_dispatch" in group.columns else 0
        in_delivery = int(group["is_in_delivery"].sum())
        logistics = dispatch + in_delivery
        delivered = int(group["is_delivered"].sum())
        returned = int(group["is_return_or_failed"].sum())
        row = {col: value for col, value in zip(group_cols, keys)}
        row.update({
            "commandes_recues": received,
            "commandes_confirmees_nettes": confirmed,
            "en_confirmation": in_confirmation,
            "en_preparation": preparation,
            "taux_preparation": safe_ratio(preparation, confirmed),
            "commandes_envoyees": sent,
            "livrees": delivered,
            "en_dispatch": dispatch,
            "taux_dispatch": safe_ratio(dispatch, sent),
            "en_livraison": in_delivery,
            "taux_en_livraison": safe_ratio(in_delivery, sent),
            "en_cours_logistique": logistics,
            "retours": returned,
            "taux_confirmation": safe_ratio(int(group["is_confirmed_net"].sum()), received),
            "taux_livraison_total": safe_ratio(delivered, sent),
            "taux_en_cours_logistique": safe_ratio(logistics, sent),
            "taux_transformation_reel": safe_ratio(delivered, received),
            "taux_retour": safe_ratio(returned, sent),
            "ca_livre": float(group["ca_delivered"].sum()),
            "ca_dispatch": float(group["ca_dispatch"].sum()) if "ca_dispatch" in group.columns else 0.0,
            "ca_bloque_livraison": float(group["ca_in_delivery"].sum()),
            "ca_en_cours_logistique": (float(group["ca_dispatch"].sum()) if "ca_dispatch" in group.columns else 0.0) + float(group["ca_in_delivery"].sum()),
            "ca_retours": float(group["ca_returned_failed"].sum()),
            "panier_moyen_livre": safe_ratio(float(group["ca_delivered"].sum()), delivered),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def preparation_metrics_by_dimension(df: pd.DataFrame, group_col: str, label_col: str) -> pd.DataFrame:
    metrics = grouped_advice_metrics(df, [group_col])
    columns = [label_col, "en_preparation", "taux_preparation"]
    if metrics.empty:
        return pd.DataFrame(columns=columns)
    return metrics.rename(columns={group_col: label_col})[columns].copy()


def confidence_label(volume: int, volume_min: int, gap: float = 0.0) -> str:
    if volume < volume_min:
        return "Non exploitable"
    if volume >= volume_min * 2 and gap >= 0.10:
        return "\u00c9lev\u00e9"
    if gap >= 0.05 or volume >= volume_min * 2:
        return "Moyen"
    return "Faible"


def product_action(row: pd.Series, volume_min: int, thresholds: dict[str, float]) -> tuple[str, str, str]:
    if row.get("commandes_recues", 0) < volume_min:
        return "\u00c9chantillon faible", "Attendre plus de donn\u00e9es", "Faible"
    confirmation = row.get("taux_confirmation")
    delivery = row.get("taux_livraison_total")
    transformation = row.get("taux_transformation_reel")
    returns = row.get("taux_retour")
    ca = row.get("ca_livre", 0)
    loss = row.get("ca_retours", 0)
    if confirmation is not None and confirmation < thresholds["confirmation_orange"]:
        return "Confirmation faible", "Corriger offre, prix, page produit, script confirmation ou qualit\u00e9 source", "Moyen"
    if delivery is not None and delivery < thresholds["delivery_orange"] and (confirmation is None or confirmation >= thresholds["confirmation_orange"]):
        return "Livraison faible", "V\u00e9rifier wilayas et livreur dominant avant de couper le produit", "Moyen"
    if returns is not None and returns >= thresholds["return_red"]:
        action = "Limiter temporairement ou stop test" if ca <= loss else "V\u00e9rifier promesse publicitaire, qualit\u00e9 produit, attentes client, SAV"
        return "Retour \u00e9lev\u00e9", action, "\u00c9lev\u00e9" if row.get("commandes_envoyees", 0) >= volume_min * 2 else "Moyen"
    if ca > 0 and delivery is not None and delivery >= thresholds["delivery_green"] and returns is not None and returns <= thresholds["return_orange"]:
        return "Produit fiable", "Augmenter le volume progressivement", "\u00c9lev\u00e9" if row.get("commandes_envoyees", 0) >= volume_min * 2 else "Moyen"
    return "Performance moyenne", "Maintenir et surveiller par source, SKU, wilaya et livreur", "Moyen"


def add_product_advice(products: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    out = products.copy()
    if out.empty:
        return out
    advice = out.apply(lambda row: product_action(row, volume_min, thresholds), axis=1)
    out["diagnostic"] = advice.apply(lambda item: item[0])
    out["action_recommandee"] = advice.apply(lambda item: item[1])
    out["niveau_confiance"] = advice.apply(lambda item: item[2])
    return out


def compute_confirmatrice_quality(df: pd.DataFrame, confirmation: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    affectee_col = "Affect\u00e9e \u00e0"
    losses = grouped_advice_metrics(df, [affectee_col])
    if not losses.empty:
        losses = losses.rename(columns={affectee_col: "confirmatrice"})[["confirmatrice", "ca_retours"]]
    out = confirmation.merge(losses, on="confirmatrice", how="left") if not losses.empty else confirmation.copy()
    out["ca_retours"] = out.get("ca_retours", 0).fillna(0)
    rows = []
    for _, row in out.iterrows():
        volume = int(row.get("commandes_recues", 0))
        confirmation_rate = row.get("taux_confirmation")
        delivery = row.get("taux_livraison_total")
        returns = row.get("taux_retour")
        if volume < volume_min or not is_known_value(row.get("confirmatrice")):
            diagnostic, action, confiance = "\u00c9chantillon faible", "Attendre plus de donn\u00e9es", "Non exploitable"
        elif confirmation_rate is not None and confirmation_rate >= thresholds["confirmation_green"] and delivery is not None and delivery < thresholds["delivery_orange"]:
            diagnostic, action, confiance = "Confirmation trop permissive possible", "Auditer appels, objections client, promesse produit et qualit\u00e9 des leads", "Moyen"
        elif confirmation_rate is not None and confirmation_rate < thresholds["confirmation_orange"]:
            diagnostic, action, confiance = "Faible conversion confirmation", "V\u00e9rifier script, timing d'appel, prix, offre et objections", "Moyen"
        elif returns is not None and returns >= thresholds["return_red"]:
            diagnostic, action, confiance = "Mauvaise qualit\u00e9 de confirmation possible", "Contr\u00f4ler si les clients sont r\u00e9ellement qualifi\u00e9s avant exp\u00e9dition", "\u00c9lev\u00e9"
        elif confirmation_rate is not None and confirmation_rate >= thresholds["confirmation_green"] and delivery is not None and delivery >= thresholds["delivery_green"] and returns is not None and returns <= thresholds["return_orange"]:
            diagnostic, action, confiance = "Confirmatrice fiable", "Lui attribuer plus de commandes si capacit\u00e9 disponible", "\u00c9lev\u00e9"
        else:
            diagnostic, action, confiance = "\u00c0 surveiller", "Suivre livraison sur exp\u00e9di\u00e9es, retours et CA livr\u00e9 avant de r\u00e9allouer plus de volume", "Moyen"
        rows.append({**row.to_dict(), "diagnostic": diagnostic, "action_recommandee": action, "niveau_confiance": confiance})
    cols = ["confirmatrice", "commandes_recues", "taux_confirmation", "taux_livraison_total", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_retours", "diagnostic", "action_recommandee", "niveau_confiance"]
    return pd.DataFrame(rows)[cols] if rows else pd.DataFrame(columns=cols)


def compute_livreur_wilaya_arbitrage(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    metrics = grouped_advice_metrics(df, ["Wilaya", "Livreur"])
    if metrics.empty:
        return pd.DataFrame()
    metrics = metrics[metrics["Livreur"].apply(is_known_value)].copy()
    orders = orders_for_advice(df)
    products = dominant_value(orders, "Wilaya", "Nom produit")
    rows = []
    for wilaya, group in metrics.groupby("Wilaya", dropna=False):
        if not is_known_value(wilaya):
            continue
        reliable = group[group["commandes_envoyees"].ge(volume_min)].copy()
        current = group.sort_values("commandes_envoyees", ascending=False).iloc[0]
        base = {"wilaya": wilaya, "produit_dominant": products.get(wilaya, "Non renseign\u00e9"), "livreur_actuel": current["Livreur"], "expediees_actuel": int(current["commandes_envoyees"]), "taux_livraison_total_actuel": current.get("taux_livraison_total"), "taux_retour_actuel": current.get("taux_retour")}
        if reliable.empty or int(current["commandes_envoyees"]) < volume_min:
            rows.append({**base, "meilleur_livreur_alternatif": "-", "expediees_alternatif": 0, "taux_livraison_total_alternatif": None, "taux_retour_alternatif": None, "ecart_livraison": None, "ecart_retour": None, "recommandation": "Pas assez de volume pour recommander un changement de livreur.", "niveau_confiance": "Non exploitable"})
            continue
        alternatives = reliable[reliable["Livreur"] != current["Livreur"]].copy()
        if alternatives.empty:
            rows.append({**base, "meilleur_livreur_alternatif": "-", "expediees_alternatif": 0, "taux_livraison_total_alternatif": None, "taux_retour_alternatif": None, "ecart_livraison": None, "ecart_retour": None, "recommandation": f"Garder {current['Livreur']} sur cette wilaya.", "niveau_confiance": "Moyen"})
            continue
        alternatives["_score"] = alternatives["taux_livraison_total"].fillna(0) - alternatives["taux_retour"].fillna(0)
        alt = alternatives.sort_values("_score", ascending=False).iloc[0]
        delivery_gap = (alt.get("taux_livraison_total") or 0) - (current.get("taux_livraison_total") or 0)
        return_gap = (current.get("taux_retour") or 0) - (alt.get("taux_retour") or 0)
        if delivery_gap >= 0.08 or return_gap >= 0.05:
            recommendation = f"D\u00e9l\u00e9guer cette wilaya \u00e0 {alt['Livreur']}, car il performe mieux que {current['Livreur']} sur cette wilaya."
        elif (current.get("taux_livraison_total") or 0) < thresholds["delivery_orange"] and (current.get("taux_retour") or 0) >= thresholds["return_red"]:
            recommendation = "Aucun livreur fiable identifi\u00e9 sur cette wilaya. Limiter le volume ou v\u00e9rifier la qualit\u00e9 des commandes."
        else:
            recommendation = f"Garder {current['Livreur']} sur cette wilaya."
        rows.append({**base, "meilleur_livreur_alternatif": alt["Livreur"], "expediees_alternatif": int(alt["commandes_envoyees"]), "taux_livraison_total_alternatif": alt.get("taux_livraison_total"), "taux_retour_alternatif": alt.get("taux_retour"), "ecart_livraison": delivery_gap, "ecart_retour": return_gap, "recommandation": recommendation, "niveau_confiance": confidence_label(min(int(current["commandes_envoyees"]), int(alt["commandes_envoyees"])), volume_min, abs(delivery_gap))})
    return pd.DataFrame(rows).sort_values(["niveau_confiance", "expediees_actuel"], ascending=[True, False]).head(20)


# P2 note: the business aggregation helpers below stay in ui.py for this pass to avoid a broad refactor.
def compute_dimension_performance(df: pd.DataFrame, group_cols: list[str], volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    out = grouped_advice_metrics(df, group_cols)
    if out.empty:
        return out
    if "SKU produit" in group_cols:
        orders = orders_for_advice(df)
        products = dominant_value(orders, "SKU produit", "Nom produit")
        out["produit_associe"] = out["SKU produit"].map(products).fillna("Non renseign\u00e9")
    advice = out.apply(lambda row: product_action(row, volume_min, thresholds), axis=1)
    out["diagnostic"] = advice.apply(lambda item: item[0])
    out["action_recommandee"] = advice.apply(lambda item: item[1])
    out["niveau_confiance"] = advice.apply(lambda item: item[2])
    return out.rename(columns={"Source": "source", "SKU produit": "sku_produit"})


def compute_loss_tables(products: pd.DataFrame, wilayas: pd.DataFrame, livreurs: pd.DataFrame, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    product_cols = ["produit", "retours", "ca_retours", "taux_retour", "action_recommandee"]
    wilaya_cols = ["wilaya", "retours", "ca_retours", "taux_retour", "livreur_dominant", "action_recommandee"]
    livreur_cols = ["livreur", "retours", "ca_retours", "taux_retour", "wilayas_problematiques", "action_recommandee"]

    def with_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        out = frame.copy()
        for col in columns:
            if col not in out.columns:
                out[col] = pd.NA
        return out[columns]

    if products.empty or "ca_retours" not in products.columns:
        product_loss = pd.DataFrame(columns=product_cols)
    else:
        product_loss = products[pd.to_numeric(products["ca_retours"], errors="coerce").fillna(0).gt(0)].copy()
        product_loss = sort_for_display(product_loss, ["ca_retours"]).head(5)
        product_loss["action_recommandee"] = "V\u00e9rifier promesse, qualit\u00e9 produit, ciblage et SAV avant scale"

    if wilayas.empty or "ca_retours" not in wilayas.columns:
        wilaya_loss = pd.DataFrame(columns=wilaya_cols)
    else:
        wilaya_loss = wilayas[pd.to_numeric(wilayas["ca_retours"], errors="coerce").fillna(0).gt(0)].copy()
        wilaya_loss = sort_for_display(wilaya_loss, ["ca_retours"]).head(5)
        wilaya_loss["action_recommandee"] = "Comparer livreurs et limiter le volume tant que les retours restent \u00e9lev\u00e9s"

    if df.empty or "order_id" not in df.columns:
        by_livreur_wilaya = pd.DataFrame()
    else:
        by_livreur_wilaya = grouped_advice_metrics(df, ["Livreur", "Wilaya"])
    if not by_livreur_wilaya.empty and {"Livreur", "Wilaya", "ca_retours"}.issubset(by_livreur_wilaya.columns):
        problematic = by_livreur_wilaya[pd.to_numeric(by_livreur_wilaya["ca_retours"], errors="coerce").fillna(0).gt(0)].sort_values("ca_retours", ascending=False)
    else:
        problematic = pd.DataFrame(columns=["Livreur", "Wilaya", "ca_retours"])
    if problematic.empty:
        top_wilayas = pd.DataFrame(columns=["Livreur", "wilayas_problematiques"])
    else:
        top_wilayas = (
            problematic.groupby("Livreur")["Wilaya"]
            .apply(lambda s: ", ".join(s.head(3).astype(str)))
            .rename("wilayas_problematiques")
            .reset_index()
        )

    if livreurs.empty or "ca_retours" not in livreurs.columns or "livreur" not in livreurs.columns:
        livreur_loss = pd.DataFrame(columns=livreur_cols)
    else:
        livreur_loss = livreurs[pd.to_numeric(livreurs["ca_retours"], errors="coerce").fillna(0).gt(0)].copy()
        if not livreur_loss.empty:
            livreur_loss = livreur_loss.merge(top_wilayas, left_on="livreur", right_on="Livreur", how="left")
            livreur_loss = livreur_loss.drop(columns=["Livreur"], errors="ignore")
        if "wilayas_problematiques" not in livreur_loss.columns:
            livreur_loss["wilayas_problematiques"] = pd.NA
        livreur_loss["wilayas_problematiques"] = livreur_loss["wilayas_problematiques"].fillna("\u2014")
        livreur_loss["action_recommandee"] = "Auditer les wilayas probl\u00e9matiques et tester un arbitrage livreur"
        livreur_loss = sort_for_display(livreur_loss, ["ca_retours"]).head(5)

    return with_columns(product_loss, product_cols), with_columns(wilaya_loss, wilaya_cols), with_columns(livreur_loss, livreur_cols)


def compute_opportunities(products: pd.DataFrame, wilayas: pd.DataFrame, product_wilaya: pd.DataFrame, volume_min_product: int, volume_min_sent: int, thresholds: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prod = products[products["commandes_recues"].ge(volume_min_product) & products["taux_confirmation"].ge(thresholds["confirmation_green"]) & products["taux_livraison_total"].ge(thresholds["delivery_green"]) & products["taux_retour"].le(thresholds["return_orange"]) & products["ca_livre"].gt(0)].copy()
    prod["objet"] = prod.get("produit", "")
    prod["volume"] = prod.get("commandes_recues", 0)
    prod["recommandation"] = "Augmenter progressivement le volume"
    wil = wilayas[wilayas["commandes_envoyees"].ge(volume_min_sent) & wilayas["taux_livraison_total"].ge(thresholds["delivery_green"]) & wilayas["taux_retour"].le(thresholds["return_orange"]) & wilayas["ca_livre"].gt(0)].copy()
    wil["objet"] = wil.get("wilaya", "")
    wil["volume"] = wil.get("commandes_envoyees", 0)
    wil["recommandation"] = "Augmenter progressivement le volume sur cette wilaya"
    pw = product_wilaya.copy()
    if not pw.empty and "taux_livraison_total" not in pw.columns and "taux_livraison_finalisees" in pw.columns:
        pw["taux_livraison_total"] = pw["taux_livraison_finalisees"]
    needed = {"commandes_envoyees", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour"}
    if not needed.issubset(pw.columns):
        pw = pd.DataFrame()
    else:
        pw = pw[pw["commandes_envoyees"].ge(volume_min_sent) & pw["taux_livraison_total"].ge(thresholds["delivery_green"]) & pw["taux_retour"].le(thresholds["return_orange"])].copy()
        if not pw.empty:
            pw["objet"] = pw["produit"].astype(str) + " \u00d7 " + pw["wilaya"].astype(str)
            pw["volume"] = pw["commandes_envoyees"]
            pw["ca_livre"] = 0.0
            pw["recommandation"] = "Pousser ce produit dans cette wilaya, \u00e9viter les zones faibles"
    cols = ["objet", "volume", "taux_confirmation", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "recommandation"]
    return sort_for_display(prod, ["ca_livre"]).head(5)[[c for c in cols if c in prod.columns]], sort_for_display(wil, ["ca_livre"]).head(5)[[c for c in cols if c in wil.columns]], sort_for_display(pw, ["volume"]).head(5)[[c for c in cols if c in pw.columns]] if not pw.empty else pd.DataFrame(columns=cols)


def compute_priority_actions(products: pd.DataFrame, wilayas: pd.DataFrame, confirmation_quality: pd.DataFrame, arbitrage: pd.DataFrame, opportunities: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame], volume_min_product: int, volume_min_sent: int, thresholds: dict[str, float]) -> pd.DataFrame:
    rows = []
    for _, row in sort_for_display(products[products["ca_retours"].gt(0)], ["ca_retours"]).head(3).iterrows():
        if row.get("commandes_recues", 0) < volume_min_product:
            continue
        priority = "Rouge" if (row.get("taux_retour") or 0) >= thresholds["return_red"] else "Orange"
        rows.append({"priorite": priority, "objet": f"Produit {row['produit']}", "probleme_detecte": "Retour \u00e9lev\u00e9 apr\u00e8s exp\u00e9dition", "recommandation_concrete": "Stopper le scale et v\u00e9rifier promesse publicitaire + qualit\u00e9 produit", "preuve_data": f"Taux retour {pct(row.get('taux_retour'))}, perte CA retours {money(row.get('ca_retours'))}", "impact_estime": "\u00c9vite d'augmenter une perte d\u00e9j\u00e0 visible", "niveau_confiance": confidence_label(int(row.get("commandes_recues", 0)), volume_min_product, row.get("taux_retour") or 0), "_impact": row.get("ca_retours", 0)})
    if not arbitrage.empty:
        for _, row in arbitrage[arbitrage["recommandation"].astype(str).str.contains("D\u00e9l\u00e9guer", case=False, na=False)].head(2).iterrows():
            rows.append({"priorite": "Rouge", "objet": f"Wilaya {row['wilaya']}", "probleme_detecte": f"{row['livreur_actuel']} performe moins bien que {row['meilleur_livreur_alternatif']}", "recommandation_concrete": row["recommandation"], "preuve_data": f"{row['meilleur_livreur_alternatif']} = {pct(row['taux_livraison_total_alternatif'])} livraison sur exp\u00e9di\u00e9es vs {row['livreur_actuel']} = {pct(row['taux_livraison_total_actuel'])}", "impact_estime": "R\u00e9duction probable des retours / meilleure finalisation", "niveau_confiance": row["niveau_confiance"], "_impact": abs(row.get("ecart_livraison") or 0) * row.get("expediees_actuel", 0)})
    bad_conf = confirmation_quality[confirmation_quality["diagnostic"].astype(str).str.contains("permissive|Mauvaise", case=False, na=False)] if not confirmation_quality.empty else pd.DataFrame()
    for _, row in sort_for_display(bad_conf, ["ca_retours"]).head(1).iterrows():
        rows.append({"priorite": "Orange", "objet": f"Confirmatrice {row['confirmatrice']}", "probleme_detecte": row["diagnostic"], "recommandation_concrete": row["action_recommandee"], "preuve_data": f"Confirmation {pct(row.get('taux_confirmation'))}, livraison sur exp\u00e9di\u00e9es {pct(row.get('taux_livraison_total'))}, retour {pct(row.get('taux_retour'))}", "impact_estime": "Am\u00e9liore la qualit\u00e9 des commandes exp\u00e9di\u00e9es", "niveau_confiance": row["niveau_confiance"], "_impact": row.get("ca_retours", 0)})
    opp_products, opp_wilayas, _ = opportunities
    for _, row in pd.concat([opp_products.head(1), opp_wilayas.head(1)], ignore_index=True).iterrows():
        rows.append({"priorite": "Vert", "objet": str(row.get("objet")), "probleme_detecte": "Opportunit\u00e9 fiable \u00e0 pousser", "recommandation_concrete": row.get("recommandation", "Augmenter progressivement le volume"), "preuve_data": f"Volume {int(row.get('volume', 0))}, livraison sur exp\u00e9di\u00e9es {pct(row.get('taux_livraison_total'))}, retour {pct(row.get('taux_retour'))}, CA livr\u00e9 {money(row.get('ca_livre', 0))}", "impact_estime": "Zone ou produit exploitable", "niveau_confiance": confidence_label(int(row.get("volume", 0)), volume_min_sent, row.get("taux_livraison_total") or 0), "_impact": row.get("ca_livre", 0)})
    if not rows:
        return pd.DataFrame([{"priorite": "Info", "objet": "Donn\u00e9es", "probleme_detecte": "Donn\u00e9es insuffisantes", "recommandation_concrete": "Pas assez de donn\u00e9es pour recommander une action fiable.", "preuve_data": "Aucun segment fiable ne d\u00e9passe les seuils actifs", "impact_estime": "Non estimable", "niveau_confiance": "Non exploitable", "_impact": 0}]).drop(columns="_impact")
    priority_order = {"Rouge": 0, "Orange": 1, "Vert": 2, "Info": 3}
    out = pd.DataFrame(rows)
    out["_priority_order"] = out["priorite"].map(priority_order).fillna(9)
    return out.sort_values(["_priority_order", "_impact"], ascending=[True, False]).head(7).drop(columns=["_impact", "_priority_order"])


def build_percent_bar_figure(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None):
    needed = [x, y] + ([color] if color else [])
    if df.empty or any(col not in df.columns for col in needed):
        return None
    chart_df = df[needed].copy()
    chart_df[y] = pd.to_numeric(chart_df[y], errors="coerce")
    chart_df = chart_df.dropna(subset=[x, y])
    if chart_df.empty:
        return None
    chart_df = chart_df.sort_values(y, ascending=False).head(10)
    fig = px.bar(
        chart_df,
        x=x,
        y=y,
        color=color,
        text=chart_df[y].map(pct),
        title=title,
    )
    fig.update_traces(textposition="outside")
    max_value = float(chart_df[y].max()) if not chart_df.empty else 1.0
    fig.update_layout(
        yaxis_tickformat=".0%",
        yaxis_range=[0, min(1, max(0.05, max_value * 1.2))],
        height=280,
    )
    return fig


def percent_bar(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None):
    fig = build_percent_bar_figure(df, x, y, title, color)
    if fig is None:
        st.info("Pas assez de donnees calculables pour afficher ce graphique.")
        return
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def build_amount_bar_figure(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    chart_df = df[[x, y]].copy()
    chart_df[y] = pd.to_numeric(chart_df[y], errors="coerce")
    chart_df = chart_df.dropna(subset=[x, y])
    if chart_df.empty:
        return None
    chart_df = chart_df.sort_values(y, ascending=False).head(10)
    fig = px.bar(chart_df, x=x, y=y, text=chart_df[y].map(money), title=title)
    fig.update_traces(textposition="outside")
    fig.update_layout(height=280)
    return fig


def amount_bar(df: pd.DataFrame, x: str, y: str, title: str):
    fig = build_amount_bar_figure(df, x, y, title)
    if fig is None:
        st.info("Pas assez de donnees calculables pour afficher ce graphique.")
        return
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def build_confirmation_rate_figure(confirmation: pd.DataFrame, volume_min: int = 0):
    required = {"confirmatrice", "commandes_recues", "taux_confirmation", "taux_livraison_finalisees"}
    if confirmation.empty or not required.issubset(confirmation.columns):
        return None
    chart_df = reliable_rows(confirmation, "confirmatrice", "commandes_recues", volume_min)
    if chart_df.empty:
        return None
    chart_df = chart_df.sort_values("commandes_recues", ascending=False).head(10).copy()
    chart_long = chart_df.melt(
        id_vars=["confirmatrice"],
        value_vars=["taux_confirmation", "taux_livraison_finalisees"],
        var_name="Indicateur",
        value_name="Taux",
    )
    chart_long["Taux"] = pd.to_numeric(chart_long["Taux"], errors="coerce")
    chart_long = chart_long.dropna(subset=["confirmatrice", "Taux"])
    if chart_long.empty:
        return None
    fig = px.bar(
        chart_long,
        x="confirmatrice",
        y="Taux",
        color="Indicateur",
        barmode="group",
        text=chart_long["Taux"].map(pct),
        title="Confirmation vs livraison finalisee",
        labels={"confirmatrice": "Confirmatrice"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis_tickformat=".0%", yaxis_range=[0, 1], height=280)
    return fig


def sanitize_multiselect_state(state, key: str, options: list) -> list:
    current = state.get(key, [])
    if not isinstance(current, (list, tuple, set)):
        current = []
    current_values = list(current)
    valid_values = [value for value in current_values if value in options]
    if valid_values != current_values:
        state[key] = valid_values
    return valid_values


def filter_dataframe(df: pd.DataFrame, file_signature=None) -> tuple[pd.DataFrame, dict[str, float], dict]:
    st.sidebar.header("Filtres")
    date_options = DATE_TYPE_OPTIONS
    selected_date_type = st.sidebar.selectbox("Type de date d'analyse", date_options, index=0, key=ANALYSIS_DATE_TYPE_KEY)
    date_col = get_date_column(selected_date_type, detect_date_columns(df))
    global_min_date, global_max_date = available_date_bounds(df)
    date_context = {
        "selected_date_type": selected_date_type,
        "date_column": date_col,
        "start_date": None,
        "end_date": None,
        "missing_date_count": len(df),
        "input_rows": len(df),
        "kept_rows": 0,
    }

    if global_min_date is not None and global_max_date is not None:
        active_period, _ = render_analysis_period_selector(
            file_signature,
            global_min_date,
            global_max_date,
        )
        start_date, end_date = active_period
        df, date_context = apply_date_filter(df, selected_date_type, start_date, end_date)
        if df.empty:
            st.sidebar.info("Aucune commande disponible sur cette periode avec ce type de date.")
    else:
        st.sidebar.warning("Aucune date exploitable pour ce fichier.")
        df = df.iloc[0:0].copy()

    active_filters = []
    applied_filter_values = []
    for label, col, key in FILTER_DEFINITIONS:
        if col not in df.columns:
            st.session_state.pop(key, None)
            continue
        options = sorted(df[col].dropna().unique().tolist(), key=lambda value: str(value))
        sanitize_multiselect_state(st.session_state, key, options)
        selected = st.sidebar.multiselect(label, options, key=key)
        if selected:
            selected_values = list(selected)
            active_filters.append({"label": label, "count": len(selected_values), "values": [str(value) for value in selected_values]})
            applied_filter_values.append((col, selected_values))
            df = df[df[col].isin(selected_values)]

    st.sidebar.header("Seuils")
    volume_product = st.sidebar.number_input("Volume min produit", 1, 1000, int(DEFAULT_THRESHOLDS["volume_product"]))
    volume_sent = st.sidebar.number_input("Volume min wilaya/livreur", 1, 1000, int(DEFAULT_THRESHOLDS["volume_sent"]))
    thresholds = {
        **DEFAULT_THRESHOLDS,
        "volume_product": volume_product,
        "volume_sent": volume_sent,
        "confirmation_green": st.sidebar.slider("Confirmation vert >= ", 0.0, 1.0, DEFAULT_THRESHOLDS["confirmation_green"], 0.01),
        "confirmation_orange": st.sidebar.slider("Confirmation orange >= ", 0.0, 1.0, DEFAULT_THRESHOLDS["confirmation_orange"], 0.01),
        "cancellation_orange": st.sidebar.slider("Annulation orange > ", 0.0, 1.0, DEFAULT_THRESHOLDS["cancellation_orange"], 0.01),
        "cancellation_red": st.sidebar.slider("Annulation rouge > ", 0.0, 1.0, DEFAULT_THRESHOLDS["cancellation_red"], 0.01),
        "delivery_green": st.sidebar.slider("Livraison vert >= ", 0.0, 1.0, DEFAULT_THRESHOLDS["delivery_green"], 0.01),
        "delivery_orange": st.sidebar.slider("Livraison orange >= ", 0.0, 1.0, DEFAULT_THRESHOLDS["delivery_orange"], 0.01),
        "return_orange": st.sidebar.slider("Retour orange > ", 0.0, 1.0, DEFAULT_THRESHOLDS["return_orange"], 0.01),
        "return_red": st.sidebar.slider("Retour rouge > ", 0.0, 1.0, DEFAULT_THRESHOLDS["return_red"], 0.01),
        "preparation_orange": st.sidebar.slider("Preparation orange > ", 0.0, 1.0, DEFAULT_THRESHOLDS["preparation_orange"], 0.01),
        "preparation_red": st.sidebar.slider("Preparation rouge > ", 0.0, 1.0, DEFAULT_THRESHOLDS["preparation_red"], 0.01),
    }
    date_context["kept_rows_after_filters"] = len(df)
    date_context["active_secondary_filters"] = active_filters
    date_context["applied_filter_values"] = applied_filter_values
    return df, thresholds, date_context

TREND_ACCENT = "#2563eb"
TREND_ACCENT_LIGHT = "#bfdbfe"
TREND_AVERAGE_COLOR = "#64748b"
TREND_GRID_COLOR = "#eef2f7"
TREND_TONE_COLORS = {"good": ("#dcfce7", "#166534"), "bad": ("#fee2e2", "#991b1b"), "neutral": ("#e2e8f0", "#334155")}
TREND_GRANULARITY_KEY = "trend_granularity"
TREND_PERIOD_KEY = "trend_granularity_period"
TREND_TICK_FORMAT = {"Jour": "%d/%m", "Semaine": "%d/%m", "Mois": "%m/%Y"}


def apply_filter_values(df: pd.DataFrame, applied_filter_values) -> pd.DataFrame:
    """Re-apply the sidebar multiselect filters (column, values) to another frame."""
    out = df
    for col, values in applied_filter_values or []:
        if col in out.columns:
            out = out[out[col].isin(list(values))]
    return out


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


RANK_TONE_COLORS = {"good": "#16a34a", "bad": "#dc2626", "neutral": "#94a3b8"}
RANK_LABEL_MAX = 26


def short_label(value, limit: int = RANK_LABEL_MAX) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_chart_header(title: str, explanation: str, pill: str, sentence_html: str, min_height: int = 92) -> None:
    bg, fg = TREND_TONE_COLORS["neutral"]
    st.markdown(
        f"""
        <div style="margin:6px 0 0;min-height:{min_height}px">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
            <span style="font-size:15px;font-weight:850;color:#0f172a">{html_text(title)}</span>
            <span style="background:{bg};color:{fg};border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:800;white-space:nowrap">{html_text(pill)}</span>
          </div>
          <div style="font-size:11.5px;color:#64748b;margin-top:1px">{explanation}</div>
          <div style="font-size:12.5px;color:#334155;margin-top:4px;line-height:1.45">{sentence_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
) -> None:
    """Ranking of a rate: best and worst visible, volume next to each value, company average as reference."""
    try:
        average = pooled_rate(table, numerator_col, denominator_col)
        rows, hidden_low, hidden_middle = rate_ranking_rows(table, label_col, rate_col, volume_col, volume_min, higher_is_better)
        reading = rate_ranking_reading(rows, label_col, rate_col)
        better = "plus haut = mieux" if higher_is_better else "plus bas = mieux"
        if reading["best"] is None:
            sentence = "Pas assez de volume pour classer."
        else:
            sentence = f"Meilleur : <b>{html_text(reading['best'][0])}</b> ({html_text(pct(reading['best'][1]))})"
            if reading["worst"] is not None:
                sentence += f"<br>Moins bon : <b>{html_text(reading['worst'][0])}</b> ({html_text(pct(reading['worst'][1]))})"
        render_chart_header(title, f"{html_text(explanation)} · <b>{better}</b>", f"Moyenne {pct(average)}", sentence)
        fig = build_rate_ranking_figure(rows, label_col, rate_col, volume_col, volume_label, average, higher_is_better)
        if fig is None:
            st.info(f"Aucune ligne avec au moins {volume_min} {volume_label} : pas assez de volume pour un classement fiable.")
        else:
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)
        notes = ["Vert = mieux que la moyenne, rouge = moins bien, gris = dans la moyenne (±2 pts). Ligne grise = moyenne."]
        if hidden_middle:
            notes.append(f"{hidden_middle} lignes du milieu du classement masquées (voir le tableau).")
        if hidden_low:
            notes.append(f"{hidden_low} non affiché(s) : moins de {volume_min} {volume_label}, pas assez pour juger.")
        st.caption(" ".join(notes))
    except Exception as exc:  # a chart must never break the tab
        st.warning(f"Graphique indisponible : {exc}")


def render_amount_ranking(table: pd.DataFrame, label_col: str, value_col: str, title: str, explanation: str, color: str, key: str) -> None:
    """Ranking of an amount (CA): biggest first, share of total, tail grouped in "Autres"."""
    try:
        rows, total = amount_ranking_rows(table, label_col, value_col)
        if rows.empty:
            render_chart_header(title, html_text(explanation), f"Total {money(0)}", "Aucun montant sur le périmètre.")
            return
        first = rows.iloc[0]
        top3 = amount_concentration(rows, label_col, value_col, total)
        sentence = f"Plus gros : <b>{html_text(first[label_col])}</b> ({html_text(money(first[value_col]))}, {html_text(pct(first['part']))})"
        if top3 is not None and int((rows[label_col] != OTHERS_LABEL).sum()) > 3:
            sentence += f"<br>Les 3 premiers = <b>{html_text(pct(top3))}</b> du total"
        render_chart_header(title, html_text(explanation), f"Total {money(total)}", sentence)
        st.plotly_chart(build_amount_ranking_figure(rows, label_col, value_col, color), width="stretch", config={"displayModeBar": False}, key=key)
    except Exception as exc:  # a chart must never break the tab
        st.warning(f"Graphique indisponible : {exc}")


FLOW_COLORS = {"base": "#2563eb", "lost": "#dc2626", "pending": "#f59e0b", "secured": "#16a34a"}
FLOW_TONE_TEXT = {"lost": "perdu", "pending": "en attente", "secured": "livré", "base": "reçu"}


def format_count(value) -> str:
    return f"{int(value):,}".replace(",", " ")


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


def build_export(metrics: dict, tables: dict[str, pd.DataFrame], clean_df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        global_metrics_table(metrics).to_excel(writer, sheet_name="Resume_Global", index=False)
        for sheet, table in tables.items():
            format_table(table).to_excel(writer, sheet_name=sheet[:31], index=False)
        clean_df.drop(columns=[c for c in SENSITIVE_COLUMNS if c in clean_df.columns], errors="ignore").to_excel(
            writer, sheet_name="Donnees_Nettoyees", index=False
        )
    return output.getvalue()


def confirmation_summary(confirmation: pd.DataFrame, volume_min: int) -> list[str]:
    if confirmation.empty:
        return ["Aucune donn\u00e9e de confirmation avec les filtres actuels."]
    reliable = reliable_rows(confirmation, "confirmatrice", "commandes_recues", volume_min)
    if reliable.empty:
        return [no_reliable_message()]
    best = reliable.sort_values("taux_confirmation", ascending=False).iloc[0]
    most_cancel = reliable.sort_values("commandes_annulees", ascending=False).iloc[0]
    high_return = reliable.dropna(subset=["taux_retour"]).sort_values("taux_retour", ascending=False)
    bullets = [
        f"Meilleur taux de confirmation fiable : {best['confirmatrice']} avec {pct(best['taux_confirmation'])}.",
        f"Plus gros volume d'annulations fiable : {most_cancel['confirmatrice']} avec {int(most_cancel['commandes_annulees'])} commandes annul\u00e9es.",
    ]
    if not high_return.empty:
        row = high_return.iloc[0]
        bullets.append(f"Retour le plus sensible apr\u00e8s envoi : {row['confirmatrice']} avec {pct(row['taux_retour'])}.")
    return bullets


def delivery_summary(livreurs: pd.DataFrame, volume_min: int) -> list[str]:
    if livreurs.empty:
        return ["Aucune commande envoy\u00e9e avec les filtres actuels."]
    reliable = reliable_rows(livreurs, "livreur", "commandes_envoyees", volume_min)
    if reliable.empty:
        return [no_reliable_message()]
    most_sent = reliable.sort_values("commandes_envoyees", ascending=False).iloc[0]
    highest_return = reliable.dropna(subset=["taux_retour"]).sort_values("taux_retour", ascending=False)
    bullets = [
        f"Livreur principal fiable : {most_sent['livreur']} avec {int(most_sent['commandes_envoyees'])} commandes exp\u00e9di\u00e9es.",
        "Les commandes en pr\u00e9paration restent exclues des KPI livreur.",
    ]
    if not highest_return.empty:
        row = highest_return.iloc[0]
        bullets.insert(1, f"Retour le plus \u00e9lev\u00e9 : {row['livreur']} avec {pct(row['taux_retour'])}.")
    return bullets


def product_summary(products: pd.DataFrame, volume_min: int) -> list[str]:
    if products.empty:
        return ["Aucun produit disponible avec les filtres actuels."]
    reliable = reliable_rows(products, "produit", "commandes_recues", volume_min)
    if reliable.empty:
        return [no_reliable_message()]
    weak = products[products["commandes_recues"] < volume_min]
    bullets = [f"{len(reliable)} produit(s) ont un volume fiable ; {len(weak)} restent en \u00e9chantillon faible."]
    push = reliable[reliable["decision_auto"].astype(str).str.contains("pousser|scaler", case=False, na=False)]
    problems = reliable[reliable["decision_auto"].astype(str).str.contains("surveiller|corriger", case=False, na=False)].sort_values(["ca_retours", "commandes_recues"], ascending=False)
    if not push.empty:
        row = push.sort_values("ca_livre", ascending=False).iloc[0]
        bullets.append(f"Produit le plus int\u00e9ressant \u00e0 pousser : {row['produit']} avec {money(row['ca_livre'])} de CA livr\u00e9.")
    if not problems.empty:
        row = problems.iloc[0]
        bullets.append(f"Vrai probl\u00e8me prioritaire : {row['produit']} avec {money(row['ca_retours'])} de perte CA retours.")
    return bullets


def wilaya_summary(wilayas: pd.DataFrame, volume_min: int) -> list[str]:
    if wilayas.empty:
        return ["Aucune wilaya disponible avec les filtres actuels."]
    reliable = reliable_rows(wilayas, "wilaya", "commandes_envoyees", volume_min)
    if reliable.empty:
        return [no_reliable_message()]
    push = reliable[reliable["decision_auto"].astype(str).str.contains("pousser", case=False, na=False)]
    problems = reliable[reliable["decision_auto"].astype(str).str.contains("surveiller|corriger", case=False, na=False)].sort_values(["ca_retours", "commandes_envoyees"], ascending=False)
    bullets = []
    if not push.empty:
        row = push.sort_values("ca_livre", ascending=False).iloc[0]
        bullets.append(f"Wilaya \u00e0 pousser en priorit\u00e9 : {row['wilaya']} avec {money(row['ca_livre'])} de CA livr\u00e9.")
    if not problems.empty:
        row = problems.iloc[0]
        bullets.append(f"Wilaya \u00e0 traiter : {row['wilaya']} avec {money(row['ca_retours'])} de perte CA retours.")
    return bullets or ["Pas de probl\u00e8me wilaya marqu\u00e9 avec les seuils actuels."]


def validation_summary(validation_checks: pd.DataFrame) -> list[str]:
    failed = validation_checks[validation_checks["statut"] != "OK"]
    if failed.empty:
        return ["Les \u00e9galit\u00e9s COD et contr\u00f4les principaux sont valid\u00e9s."]
    return [f"{len(failed)} contr\u00f4le(s) demandent v\u00e9rification : " + ", ".join(failed["controle"].head(3).tolist())]


def run_app() -> None:
    st.set_page_config(page_title="Dashboard COD", layout="wide")
    st.markdown(
        """
        <style>
        .main .block-container{max-width:1680px;padding-top:1.1rem;padding-left:2.2rem;padding-right:2.2rem}
        h1{font-size:2.05rem;margin-bottom:.35rem;color:#0f172a;font-weight:850}.stTabs [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid #d7dee8}.stTabs [data-baseweb="tab"]{height:38px;padding:0 12px;border-radius:8px 8px 0 0;font-weight:700;color:#334155}.stTabs [aria-selected="true"]{background:#f8fafc;color:#dc2626;border-bottom:2px solid #ef4444}
        .kpi{border:1px solid #e5e7eb;border-radius:8px;padding:11px 12px;background:#fff;margin-bottom:6px}.kpi-label{font-size:12px;color:#64748b}.kpi-value{font-size:24px;font-weight:800;color:#0f172a}
        .alert{border-radius:8px;padding:10px 12px;margin-bottom:7px;border:1px solid #e5e7eb;background:#fff}.success{border-left:6px solid #16a34a}.warning{border-left:6px solid #f59e0b}.danger{border-left:6px solid #dc2626}.info{border-left:6px solid #2563eb}
        .quality-badge{display:inline-flex;align-items:center;gap:8px;border:1px solid #334155;border-radius:999px;padding:5px 11px;background:#0f172a;color:#e5e7eb;font-size:12.5px;margin-bottom:8px}.quality-ok{border-color:#15803d;background:#052e16;color:#bbf7d0}.quality-warn{border-color:#991b1b;background:#2f1111;color:#fecaca}
        .tab-header{border:1px solid #dbe3ef;border-left:5px solid #334155;background:#f8fafc;border-radius:8px;padding:10px 13px;margin:4px 0 12px}.tab-title{font-size:19px;font-weight:850;color:#0f172a}.tab-subtitle{font-size:12.5px;color:#64748b;margin-top:2px;line-height:1.35}
        .card-topline,.mini-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.status-pill,.mini-badge{border-radius:999px;padding:2px 7px;font-size:10.5px;font-weight:850}.status-pill.good,.mini-badge.good,.mini-badge.opportunity{background:#dcfce7;color:#166534}.status-pill.warn,.mini-badge.warn{background:#fef3c7;color:#92400e}.status-pill.bad,.mini-badge.bad,.mini-badge.loss{background:#fee2e2;color:#991b1b}.status-pill.neutral,.mini-badge.neutral,.mini-badge.info{background:#dbeafe;color:#1e40af}
        .hero-card{border:1px solid #243244;border-left-width:5px;border-radius:8px;background:linear-gradient(135deg,#101827,#172033);color:#f9fafb;padding:11px 13px;min-height:104px;margin-bottom:8px;box-shadow:0 6px 18px rgba(15,23,42,.10)}.hero-card.good{border-left-color:#22c55e}.hero-card.warn{border-left-color:#f59e0b}.hero-card.bad{border-left-color:#ef4444}.hero-card.neutral{border-left-color:#3b82f6}.hero-title{font-size:10.5px;color:#cbd5e1;text-transform:uppercase;letter-spacing:.04em}.hero-value{font-size:25px;font-weight:850;margin-top:6px;line-height:1.05}.hero-sub{font-size:12px;color:#cbd5e1;margin-top:5px;line-height:1.25}
        .mini-card{border:1px solid #d7dee8;border-left-width:4px;border-radius:8px;background:#fff;padding:9px 11px;min-height:80px;margin-bottom:7px;box-shadow:0 1px 2px rgba(15,23,42,.035)}.mini-card.good,.mini-card.opportunity{border-left-color:#22c55e;background:#f0fdf4}.mini-card.warn{border-left-color:#f59e0b;background:#fffbeb}.mini-card.loss,.mini-card.bad{border-left-color:#ef4444;background:#fff1f2}.mini-card.info,.mini-card.neutral{border-left-color:#3b82f6}.mini-card.detail{min-height:68px;padding:7px 9px}.mini-title{font-size:11.5px;color:#475569;font-weight:800}.mini-value{font-size:19px;font-weight:850;color:#0f172a;margin-top:4px;line-height:1.08}.mini-note{font-size:11.5px;color:#64748b;line-height:1.22;margin-top:4px;white-space:pre-line}.mini-card.detail .mini-value{font-size:16px}.mini-card.detail .mini-note{font-size:10.8px}
        .leak-banner{border:1px solid #fecaca;background:#fff1f2;color:#7f1d1d;border-radius:8px;padding:7px 11px;margin:3px 0 8px;font-size:12.5px}.funnel-arrow{text-align:center;color:#64748b;font-size:20px;font-weight:900;padding-top:30px}
        .section-tight{margin-top:18px;margin-bottom:4px;font-weight:850;font-size:16px;color:#0f172a}.section-subtitle{font-size:12px;color:#64748b;margin-bottom:7px}.detail-title{font-weight:850;margin:10px 0 5px;color:#0f172a}.filter-banner{border:1px solid #cbd5e1;border-radius:8px;background:#f8fafc;color:#334155;padding:7px 10px;margin:4px 0 10px;font-size:12px;line-height:1.3}.stage-heading{display:flex;align-items:baseline;gap:9px;margin:11px 0 6px;padding-left:10px;border-left:3px solid #2563eb;color:#0f172a;font-size:13px;font-weight:850}.stage-heading small{font-size:11.5px;font-weight:500;color:#64748b}.focus-card{border:1px solid #d7dee8;border-left:5px solid #2563eb;border-radius:8px;background:#fff;padding:11px 13px;margin:12px 0 4px;box-shadow:0 1px 2px rgba(15,23,42,.04)}.focus-card.good{border-left-color:#16a34a;background:#f0fdf4}.focus-card.warn{border-left-color:#f59e0b;background:#fffbeb}.focus-card.bad{border-left-color:#dc2626;background:#fff1f2}.focus-kicker{font-size:10.5px;font-weight:850;text-transform:uppercase;letter-spacing:.04em;color:#64748b}.focus-title{font-size:15px;font-weight:850;color:#0f172a;margin-top:2px}.focus-problem{font-size:12px;color:#334155;margin-top:2px}.focus-action{font-size:12.5px;font-weight:700;color:#0f172a;margin-top:7px}.focus-proof{font-size:11.5px;color:#64748b;margin-top:5px}
        div[data-testid="stDataFrame"]{border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;box-shadow:0 1px 2px rgba(15,23,42,.025)}div[data-testid="stDataFrame"] *{font-size:12px}div[data-testid="stExpander"]{border-color:#e2e8f0;border-radius:8px}.stAlert{padding:.6rem .75rem}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Dashboard opérationnel COD")
    uploaded = st.sidebar.file_uploader("Upload Excel CRM/ERP", type=["xlsx", "xls"])
    if uploaded is None:
        st.info("Upload un export Excel pour afficher les KPI COD.")
        return

    file_signature = uploaded_file_signature(uploaded)

    try:
        raw_preview = pd.read_excel(uploaded, nrows=5, dtype=object)
        uploaded.seek(0)
        for warning in validate_columns(raw_preview):
            st.warning(warning)
        df = load_excel(uploaded)
    except Exception as exc:
        st.error(f"Impossible de lire le fichier : {exc}")
        return

    loaded_df = df.copy()
    df, thresholds, date_context = filter_dataframe(df, file_signature=file_signature)
    date_audit_full = summarize_missing_dates(loaded_df, "Fichier complet")
    date_audit_filtered = summarize_missing_dates(df, "Perimetre filtre")
    if df.empty:
        st.warning("Aucune donnée avec ces filtres.")
        return

    volume_product = int(thresholds["volume_product"])
    volume_sent = int(thresholds["volume_sent"])
    volume_confirmatrice = volume_sent
    global_metrics = compute_global_metrics(df)
    validation_checks = compute_validation_checks(df, global_metrics)
    confirmation = compute_confirmation_metrics(df)
    livreurs = compute_livreur_metrics(df)
    products = compute_product_metrics(df, volume_product)
    wilayas = compute_wilaya_metrics(df, volume_sent)
    product_wilaya = compute_product_wilaya_alerts(df, volume_sent)
    livreur_wilaya = compute_livreur_wilaya_alerts(df, volume_sent)
    alerts = generate_alerts(global_metrics, products, wilayas, livreurs, confirmation, thresholds)
    products_advice = add_product_advice(products, volume_product, thresholds)
    confirmation_quality = compute_confirmatrice_quality(df, confirmation, volume_confirmatrice, thresholds)
    arbitrage_livreur = compute_livreur_wilaya_arbitrage(df, volume_sent, thresholds)
    opportunities = compute_opportunities(
        products,
        wilayas,
        product_wilaya,
        volume_product,
        volume_sent,
        thresholds,
    )
    priority_actions = compute_priority_actions(
        products,
        wilayas,
        confirmation_quality,
        arbitrage_livreur,
        opportunities,
        volume_product,
        volume_sent,
        thresholds,
    )
    source_performance = compute_dimension_performance(df, ["Source"], volume_product, thresholds)
    sku_performance = compute_dimension_performance(df, ["SKU produit"], volume_product, thresholds)
    confirmation_display = confirmation.merge(
        confirmation_quality[["confirmatrice", "ca_retours"]] if not confirmation_quality.empty and "ca_retours" in confirmation_quality.columns else pd.DataFrame(columns=["confirmatrice", "ca_retours"]),
        on="confirmatrice",
        how="left",
    )
    confirmation_display["ca_retours"] = confirmation_display.get("ca_retours", 0).fillna(0)
    confirmation_preparation = preparation_metrics_by_dimension(df, "Affect\u00e9e \u00e0", "confirmatrice")
    confirmation_display = confirmation_display.merge(confirmation_preparation, on="confirmatrice", how="left")
    confirmation_display[["en_preparation", "taux_preparation"]] = confirmation_display[["en_preparation", "taux_preparation"]].fillna({"en_preparation": 0})
    confirmation_display = add_volume_reading(confirmation_display, "commandes_recues", volume_confirmatrice, "confirmatrice", thresholds)
    livreur_preparation = preparation_metrics_by_dimension(df, "Livreur", "livreur")
    livreurs = livreurs.merge(livreur_preparation, on="livreur", how="left")
    livreurs[["en_preparation", "taux_preparation"]] = livreurs[["en_preparation", "taux_preparation"]].fillna({"en_preparation": 0})
    livreurs_ui = add_volume_reading(livreurs, "commandes_envoyees", volume_sent, "livreur", thresholds)
    products_ui = add_volume_reading(products, "commandes_recues", volume_product, "produit", thresholds)
    product_wilaya_detail = add_volume_reading(product_wilaya_performance(df), "commandes_envoyees", volume_sent, "product_wilaya", thresholds)
    wilaya_livreur_detail = add_volume_reading(livreur_wilaya_performance(df), "commandes_envoyees", volume_sent, "wilaya_livreur", thresholds)
    wilayas_ui = add_volume_reading(wilayas, "commandes_envoyees", volume_sent, "wilaya", thresholds)
    reliable_livreurs = reliable_rows(livreurs_ui, "livreur", "commandes_envoyees", volume_sent)
    reliable_products = reliable_rows(products_ui, "produit", "commandes_recues", volume_product)
    reliable_wilayas = reliable_rows(wilayas_ui, "wilaya", "commandes_envoyees", volume_sent)
    product_livreur_detail = product_livreur_performance(df, volume_sent, thresholds)
    source_product_detail = source_product_performance(df, volume_product, thresholds)
    sku_product_detail = sku_product_performance(df, volume_product, thresholds)
    confirmatrice_product_detail = confirmatrice_product_performance(df, volume_product, thresholds)
    wilaya_livreur_compare = wilaya_livreur_comparison(df, volume_sent)


    tabs = st.tabs(["Vue globale", "Confirmation", "Livraison & livreurs", "Produits", "Wilayas & alertes", "Validation chiffres", "Donnees nettoyees / export"])

    with tabs[0]:
        tab_header("Vue globale", "Les chiffres essentiels pour piloter rapidement votre activite COD.")
        render_quality_badge(validation_checks)
        render_date_context(date_context)
        render_active_filters_banner(date_context)
        render_owner_global_dashboard(df, global_metrics, thresholds, priority_actions)
        cockpit_heading("Entonnoir et argent", "Où se perdent les commandes et le chiffre d'affaires, de la réception à la livraison.")
        render_cod_flow_section(df, global_metrics)
        render_trend_section(df, loaded_df, date_context, global_metrics, thresholds)

    with tabs[1]:
        tab_header("Confirmation", "Qualite des confirmatrices et transformation reelle par cohorte.")
        funnel_confirmed, funnel_confirmation_rate, funnel_preparation_rate = confirmation_funnel_counts(global_metrics)
        funnel_confirmation_display_rate, funnel_in_confirmation_rate, funnel_cancellation_display_rate = displayed_reception_rates(global_metrics, funnel_confirmation_rate)
        render_section_kpis(
            [
                ("Commandes reçues", global_metrics["orders_received"], "Base de la période", "neutral"),
                ("Taux confirmé", pct(funnel_confirmation_display_rate), f"{funnel_confirmed} commandes confirmées\nBase : {global_metrics['orders_received']} reçues", tone_class(funnel_confirmation_rate, "confirmation", thresholds)),
                ("Taux en cours de confirmation", pct(funnel_in_confirmation_rate), f"{global_metrics.get('orders_in_confirmation', 0)} commandes en confirmation\nBase : {global_metrics['orders_received']} reçues", tone_class(funnel_in_confirmation_rate, "preparation", thresholds)),
                ("Taux en préparation", pct(funnel_preparation_rate), f"{global_metrics['orders_preparation']} commandes en préparation\nBase : {funnel_confirmed} confirmées", tone_class(funnel_preparation_rate, "preparation", thresholds)),
                ("Taux livré", pct(global_metrics["delivery_total_rate_on_sent"]), f"{global_metrics['orders_delivered']} commandes livrées\nBase : {global_metrics['orders_sent']} expédiées", tone_class(global_metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
                ("Taux de transformation brute", pct(global_metrics["transformation_real_rate"]), f"{global_metrics['orders_delivered']} livrées / {global_metrics['orders_received']} reçues", tone_class(global_metrics.get("transformation_real_rate"), "transformation", thresholds)),
                ("Taux annulé", pct(funnel_cancellation_display_rate), f"{global_metrics['orders_cancelled']} commandes annulées\nBase : {global_metrics['orders_received']} reçues", tone_class(global_metrics.get("cancellation_rate"), "cancellation", thresholds)),
            ],
            max_per_row=3,
        )

        cockpit_heading("Performance detaillee", "Clique sur une ligne pour afficher les commandes concernees.")
        confirmation_cols = ["confirmatrice", "fiabilite_volume", "commandes_recues", "commandes_annulees", "commandes_confirmees_nettes", "taux_confirmation", "en_preparation", "taux_preparation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_livraison_total", "retours", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours"]
        event, confirmation_view = render_selectable_data_table(confirmation_display, confirmation_cols, "confirmation_table", thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_recues")
        idx = selected_index(event)
        if idx is not None and idx < len(confirmation_view):
            row = confirmation_view.iloc[idx]
            show_drilldown(df, "confirmatrice", "Affectée à", row["confirmatrice"], "Commandes annulees", "confirmation")

        render_rate_ranking(
            confirmation_display, "confirmatrice", "taux_transformation_reel", "livrees", "commandes_recues",
            "commandes_recues", "reçues", volume_confirmatrice,
            "Classement des confirmatrices", "Sur 100 commandes reçues, combien finissent livrées", True, "rank_confirmatrice",
        )
        with st.expander("Analyse Confirmatrice x Produit", expanded=False):
            cp_cols = ["confirmatrice", "produit", "fiabilite_volume", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "en_preparation", "taux_preparation", "commandes_envoyees", "livrees", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_retours", "lecture_rapide"]
            render_data_table(confirmatrice_product_detail, cp_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by=["confirmatrice", "commandes_recues"])

        with st.expander("Voir detail complet confirmation", expanded=False):
            render_data_table(confirmation_display, list(confirmation_display.columns), thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_recues")
        decision_summary("Résumé décisionnel", confirmation_summary(confirmation_display, volume_confirmatrice))

    with tabs[2]:
        tab_header("Livraison & livreurs", "Performance apres expedition, retours et CA bloque chez les livreurs.")
        render_section_kpis(
            [
                ("Commandes exp\u00e9di\u00e9es", global_metrics["orders_sent"], "Base des KPI logistiques", "neutral"),
                ("Taux en pr\u00e9paration", pct(global_metrics.get("preparation_blockage_rate")), f"{global_metrics['orders_preparation']} commandes en pr\u00e9paration\nBase : {global_metrics['orders_confirmed_net']} confirm\u00e9es", tone_class(global_metrics.get("preparation_blockage_rate"), "preparation", thresholds)),
                ("Taux en dispatch", pct(safe_ratio(global_metrics.get("orders_dispatch", 0), global_metrics["orders_sent"])), f"{global_metrics.get('orders_dispatch', 0)} commandes en dispatch\nBase : {global_metrics['orders_sent']} exp\u00e9di\u00e9es", "warn" if global_metrics.get("orders_dispatch", 0) else "good"),
                ("Taux en cours de livraison", pct(global_metrics.get("in_delivery_rate_on_sent")), f"{global_metrics['orders_in_delivery']} commandes en livraison\nBase : {global_metrics['orders_sent']} exp\u00e9di\u00e9es", "warn" if global_metrics.get("orders_in_delivery", 0) else "good"),
                ("Taux livr\u00e9", pct(global_metrics["delivery_total_rate_on_sent"]), f"{global_metrics['orders_delivered']} commandes livr\u00e9es\nBase : {global_metrics['orders_sent']} exp\u00e9di\u00e9es", tone_class(global_metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
                ("Taux de transformation brute", pct(global_metrics["transformation_real_rate"]), f"{global_metrics['orders_delivered']} livr\u00e9es / {global_metrics['orders_received']} re\u00e7ues", tone_class(global_metrics.get("transformation_real_rate"), "transformation", thresholds)),
                ("Taux retour", pct(global_metrics["return_rate_on_sent"]), f"{global_metrics['orders_returned_failed']} retours / \u00e9checs\nBase : {global_metrics['orders_sent']} exp\u00e9di\u00e9es", tone_class(global_metrics.get("return_rate_on_sent"), "return", thresholds)),
            ],
            max_per_row=3,
        )
        st.info("La pr\u00e9paration est affich\u00e9e comme blocage interne avant remise au livreur ; elle reste exclue de la performance logistique individuelle.")

        cockpit_heading("Performance detaillee", "Livraison, retours et CA par livreur.")
        livreur_cols = ["livreur", "fiabilite_volume", "en_preparation", "taux_preparation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_bloque_livraison", "ca_en_cours_logistique", "ca_retours", "panier_moyen_livre"]
        event, livreurs_view = render_selectable_data_table(livreurs_ui, livreur_cols, "livreur_table", thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_envoyees")
        idx = selected_index(event)
        if idx is not None and idx < len(livreurs_view):
            row = livreurs_view.iloc[idx]
            show_drilldown(df, "livreur", "Livreur", row["livreur"], "Retours / echecs", "livreur")

        cockpit_heading("Wilaya x livreur", "Lecture croisee pour isoler les zones faibles.")
        wilaya_livreur_cols = ["livreur", "wilaya", "fiabilite_volume", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "panier_moyen_livre", "lecture_rapide"]
        render_data_table(wilaya_livreur_detail, wilaya_livreur_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by=["wilaya", "commandes_envoyees"])

        with st.expander("Comparaison livreurs par wilaya", expanded=False):
            compare_cols = ["wilaya", "livreur_dominant", "expediees_dominant", "taux_livraison_dominant", "taux_retour_dominant", "livreur_alternatif", "expediees_alternatif", "taux_livraison_alternatif", "taux_retour_alternatif", "ecart_livraison", "ecart_retour", "fiabilite_comparaison", "lecture_rapide"]
            render_data_table(wilaya_livreur_compare, compare_cols, thresholds, "Aucune comparaison disponible avec les filtres actuels.", sort_by="wilaya")

        col1, col2 = st.columns(2, gap="medium")
        with col1:
            render_rate_ranking(
                livreurs_ui, "livreur", "taux_livraison_total", "livrees", "commandes_envoyees",
                "commandes_envoyees", "expédiées", volume_sent,
                "Taux de livraison par livreur", "Sur 100 colis expédiés, combien livrés", True, "rank_livreur",
            )
        with col2:
            render_amount_ranking(livreurs_ui, "livreur", "ca_retours", "Perte CA retours par livreur", "Montant des colis revenus, par livreur", "#ef4444", "amount_livreur_retours")
        with st.expander("Voir detail complet livreurs", expanded=False):
            render_data_table(livreurs_ui, list(livreurs_ui.columns), thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_envoyees")
        decision_summary("Résumé décisionnel", delivery_summary(livreurs_ui, volume_sent))

    with tabs[3]:
        tab_header("Produits", "Produits qui encaissent, produits qui perdent et segments a surveiller.")
        product_count = int(products_ui["produit"].apply(is_known_value).sum()) if not products_ui.empty and "produit" in products_ui.columns else 0
        main_product = top_label(products_ui, "produit", "ca_livre", "commandes_recues", volume_product)
        render_section_kpis([
            ("Nombre de produits", product_count, "produits exploitables", "neutral"),
            ("Produit principal", main_product, "meilleur CA livre", "info"),
            ("CA livre total", money(products["ca_livre"].sum() if "ca_livre" in products.columns else 0), f"{int(products['livrees'].sum()) if 'livrees' in products.columns else 0} livrees", "good"),
            ("En cours logistique", int(products["en_cours_logistique"].sum()) if "en_cours_logistique" in products.columns else 0, f"{pct(weighted_rate(products, 'en_cours_logistique', 'commandes_envoyees'))} des expediees", "warn"),
            ("Perte CA retours", money(products["ca_retours"].sum() if "ca_retours" in products.columns else 0), f"{int(products['retours'].sum()) if 'retours' in products.columns else 0} retours", "loss"),
            ("Transformation reelle", pct(weighted_rate(products, "livrees", "commandes_recues")), "livrees / recues", tone_class(weighted_rate(products, "livrees", "commandes_recues"), "transformation", thresholds)),
        ])

        cockpit_heading("Performance detaillee", "Produit par produit, avec CA livre et pertes retours.")
        product_cols = ["produit", "fiabilite_volume", "decision_auto", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_livraison_total", "retours", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "ca_bloque_livraison", "panier_moyen_livre"]
        event, products_view = render_selectable_data_table(products_ui, product_cols, "product_table", thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="ca_livre")
        idx = selected_index(event)
        if idx is not None and idx < len(products_view):
            row = products_view.iloc[idx]
            show_drilldown(df, "produit", "Nom produit", row["produit"], "Retours / echecs", "produit")

        cockpit_heading("Produit x Wilaya", "Segments prioritaires par zone.")
        product_wilaya_cols = ["produit", "wilaya", "fiabilite_volume", "commandes_recues", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_transformation_reel", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "livreur_dominant", "lecture_rapide"]
        render_data_table(product_wilaya_detail, product_wilaya_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by=["ca_livre", "ca_retours"])

        with st.expander("Produit x Livreur", expanded=False):
            product_livreur_cols = ["produit", "livreur", "fiabilite_volume", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "panier_moyen_livre", "lecture_rapide"]
            render_data_table(product_livreur_detail, product_livreur_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by=["ca_retours", "commandes_envoyees"])

        with st.expander("Source x Produit", expanded=False):
            source_product_cols = ["source", "produit", "fiabilite_volume", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "lecture_rapide"]
            render_data_table(source_product_detail, source_product_cols, thresholds, "Aucune donnee Source exploitable.", sort_by=["commandes_recues", "ca_retours"])

        with st.expander("SKU x Produit", expanded=False):
            sku_product_cols = ["sku_produit", "produit", "fiabilite_volume", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "lecture_rapide"]
            render_data_table(sku_product_detail, sku_product_cols, thresholds, "Aucune donnee SKU exploitable.", sort_by="ca_livre")

        with st.expander("Voir performances Source et SKU agregees", expanded=False):
            source_cols = ["source", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours"]
            render_data_table(source_performance, source_cols, thresholds, "Aucune donnee Source exploitable.", sort_by="ca_livre")
            sku_cols = ["sku_produit", "produit_associe", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours"]
            render_data_table(sku_performance, sku_cols, thresholds, "Aucune donnee SKU exploitable.", sort_by="ca_livre")

        col1, col2 = st.columns(2, gap="medium")
        with col1:
            render_amount_ranking(products_ui, "produit", "ca_livre", "CA livré par produit", "Montant des colis livrés, par produit", TREND_ACCENT, "amount_produit_livre")
        with col2:
            render_amount_ranking(products_ui, "produit", "ca_retours", "Perte CA retours par produit", "Montant des colis revenus, par produit", "#ef4444", "amount_produit_retours")
        render_rate_ranking(
            products_ui, "produit", "taux_retour", "retours", "commandes_envoyees",
            "commandes_envoyees", "expédiées", volume_product,
            "Taux de retour par produit", "Sur 100 colis expédiés, combien reviennent", False, "rank_produit_retour",
        )
        with st.expander("Voir detail complet produits", expanded=False):
            render_data_table(products_advice, list(products_advice.columns), thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="ca_livre")
        decision_summary("Résumé décisionnel", product_summary(products_ui, volume_product))

    with tabs[4]:
        tab_header("Wilayas & alertes", "Zones fortes, zones a risque et alertes operationnelles.")
        active_wilayas = int(wilayas["wilaya"].apply(is_known_value).sum()) if not wilayas.empty and "wilaya" in wilayas.columns else 0
        best_wilaya = top_label(wilayas_ui, "wilaya", "ca_livre", "commandes_envoyees", volume_sent)
        loss_wilaya = top_label(wilayas_ui, "wilaya", "ca_retours", "commandes_envoyees", volume_sent)
        render_section_kpis([
            ("Wilayas actives", active_wilayas, "zones avec donnees", "neutral"),
            ("Meilleure wilaya", best_wilaya, "meilleur CA livre", "good"),
            ("Plus forte perte", loss_wilaya, "perte CA retours", "loss"),
            ("En cours logistique", global_metrics.get("orders_logistics", 0), f"{pct(global_metrics.get('logistics_rate_on_sent'))} des expediees", "warn"),
            ("Livraison / expediees", pct(global_metrics["delivery_total_rate_on_sent"]), f"{global_metrics['orders_delivered']} livrees / {global_metrics['orders_sent']} expediees", tone_class(global_metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
        ])

        render_rate_ranking(
            wilayas_ui, "wilaya", "taux_livraison_total", "livrees", "commandes_envoyees",
            "commandes_envoyees", "expédiées", volume_sent,
            "Taux de livraison par wilaya", "Sur 100 colis expédiés, combien livrés", True, "rank_wilaya",
        )

        cockpit_heading("Top CA livre", "Wilayas qui securisent le plus de CA.")
        top_wilaya_cols = ["wilaya", "commandes_recues", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_livraison_total", "taux_retour", "ca_livre", "ca_dispatch", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
        render_data_table(sort_for_display(reliable_wilayas, ["ca_livre"]).head(10), top_wilaya_cols, thresholds, "Aucune wilaya avec un volume suffisant pour un classement fiable.")

        cockpit_heading("Top pertes", "Wilayas qui concentrent les retours et pertes CA.")
        loss_wilaya_cols = ["wilaya", "commandes_envoyees", "retours", "taux_retour", "ca_retours", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
        render_data_table(sort_for_display(reliable_wilayas, ["ca_retours"]).head(10), loss_wilaya_cols, thresholds, "Aucune wilaya avec un volume suffisant pour un classement fiable.")

        col_retour, col_livraison = st.columns(2)
        with col_retour:
            cockpit_heading("Retours eleves", "Zones a surveiller avant d augmenter le volume.")
            high_return = sort_for_display(reliable_wilayas, ["taux_retour"], ascending=False).head(10)
            return_cols = ["wilaya", "commandes_envoyees", "retours", "taux_retour", "ca_retours", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
            render_data_table(high_return, return_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.")
        with col_livraison:
            cockpit_heading("Bon taux livraison", "Zones qui supportent mieux le volume.")
            good_delivery = sort_for_display(reliable_wilayas, ["taux_livraison_total", "ca_livre"]).head(10)
            delivery_cols = ["wilaya", "commandes_envoyees", "livrees", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
            render_data_table(good_delivery, delivery_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.")

        cockpit_heading("Performance detaillee", "Vue complete par wilaya.")
        wilaya_cols = ["wilaya", "commandes_recues", "commandes_confirmees_nettes", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_transformation_reel", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
        render_data_table(wilayas_ui, wilaya_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="ca_livre")

        cockpit_heading("Wilaya x livreur", "Lecture croisee pour isoler les zones faibles.")
        wilaya_livreur_cols = ["wilaya", "livreur", "fiabilite_volume", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "lecture_rapide"]
        render_data_table(wilaya_livreur_detail, wilaya_livreur_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_envoyees")

        with st.expander("Produits dominants par wilaya", expanded=False):
            dominant_cols = ["wilaya", "produit_dominant", "livreur_dominant", "commandes_recues", "commandes_envoyees", "livrees", "taux_transformation_reel", "ca_livre", "fiabilite_volume"]
            render_data_table(wilayas_ui, dominant_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="ca_livre")

        with st.expander("Alertes simples", expanded=False):
            if alerts:
                for alert in alerts:
                    st.markdown(f"<div class='alert {alert['niveau']}'><b>{alert['titre']}</b><br>{alert['message']}</div>", unsafe_allow_html=True)
            else:
                st.info("Aucune alerte critique detectee avec les seuils actifs.")
        decision_summary("Résumé décisionnel", wilaya_summary(wilayas_ui, volume_sent))

    with tabs[5]:
        tab_header("Validation chiffres", "Controle qualite du fichier, anomalies et coherence des egalites COD.")
        failed_checks = validation_checks[validation_checks["statut"] != "OK"]
        total_lines = validation_value(validation_checks, "Lignes Excel")
        duplicates = validation_value(validation_checks, "Doublons")
        missing_important = sum(validation_value(validation_checks, name) for name in ["sans wilaya", "sans produit", "sans statut"])
        valid_lines = max(total_lines - duplicates - missing_important, 0)
        render_section_kpis([
            ("Lignes fichier", total_lines, "lignes importees", "neutral"),
            ("Lignes valides", valid_lines, "hors doublons / manquants cles", "good" if failed_checks.empty else "warn"),
            ("Anomalies", len(failed_checks), "controles - verifier", "good" if failed_checks.empty else "loss"),
            ("Valeurs manquantes", missing_important, "wilaya / produit / statut", "good" if missing_important == 0 else "warn"),
            ("Doublons", duplicates, "lignes en doublon", "good" if duplicates == 0 else "warn"),
        ])
        cockpit_heading("Audit dates - fichier complet")
        render_data_table(date_audit_full, ["controle", "valeur", "attendu", "statut", "details"], thresholds, "Aucun controle date disponible.", height=adaptive_height(date_audit_full, max_height=280))
        cockpit_heading("Audit dates - perimetre filtre")
        render_data_table(date_audit_filtered, ["controle", "valeur", "attendu", "statut", "details"], thresholds, "Aucun controle date disponible.", height=adaptive_height(date_audit_filtered, max_height=280))
        cockpit_heading("Validation des donnees")
        validation_view = validation_checks.assign(_sort=validation_checks["statut"].eq("OK").astype(int)).sort_values("_sort").drop(columns="_sort")
        render_data_table(validation_view, ["controle", "valeur", "attendu", "statut", "details"], thresholds, "Aucun controle de validation disponible.", sort_by="statut", height=adaptive_height(validation_view, max_height=520))
        with st.expander("Voir tous les controles", expanded=False):
            render_data_table(validation_checks, list(validation_checks.columns), thresholds, "Aucun controle de validation disponible.")
        decision_summary("Résumé décisionnel", validation_summary(validation_checks))

    with tabs[6]:
        tab_header("Donnees nettoyees / export", "Apercu nettoye et exports operationnels sans donnees sensibles.")
        safe_df = df.drop(columns=[c for c in SENSITIVE_COLUMNS if c in df.columns], errors="ignore")
        render_section_kpis([
            ("Lignes nettoyees", len(safe_df), "apres import", "neutral"),
            ("Commandes uniques", safe_df["order_id"].nunique(dropna=False) if "order_id" in safe_df.columns else 0, "base COD", "info"),
            ("Colonnes visibles", len(safe_df.columns), "hors donnees sensibles", "neutral"),
        ])
        cockpit_heading("Donnees nettoyees")
        st.dataframe(prepare_dataframe_for_display(safe_df.head(200), rename_columns=True), width="stretch", hide_index=True, height=360)
        tables = {
            "Confirmation": confirmation,
            "Livreurs": livreurs,
            "Produits": products,
            "Wilayas": wilayas,
            "Alertes_Produit_Wilaya": product_wilaya,
            "Alertes_Livreur_Wilaya": livreur_wilaya,
            "Source": source_performance,
            "SKU_Produit": sku_performance,
            "Validation": validation_checks,
        }
        st.download_button("Exporter les resultats Excel", build_export(global_metrics, tables, df), file_name="dashboard_cod_resultats.xlsx")
        st.download_button("Exporter donnees nettoyees CSV", safe_df.to_csv(index=False).encode("utf-8-sig"), file_name="donnees_nettoyees_cod.csv")
