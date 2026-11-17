"""Analysis period, date type and sidebar filters."""
from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import timedelta

from ..alerts import DEFAULT_THRESHOLDS
from .formatting import DASH, format_date, html_text


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


# Period shown when a file is opened (the owner checks the last 30 days by default).
DEFAULT_PERIOD_PRESET = "30 derniers jours"

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
    default_period = period_from_preset(DEFAULT_PERIOD_PRESET, min_date, max_date)
    candidate = default_period if is_new_file else state.get(ANALYSIS_PERIOD_VALUE_KEY)
    if candidate is None:
        candidate = default_period
    normalized, message = normalize_analysis_period(candidate, min_date, max_date)

    state[ANALYSIS_PERIOD_FILE_KEY] = file_signature
    state[ANALYSIS_PERIOD_VALUE_KEY] = normalized
    if is_new_file or ANALYSIS_PERIOD_DRAFT_KEY not in state:
        state[ANALYSIS_PERIOD_DRAFT_KEY] = normalized
    if is_new_file or ANALYSIS_PERIOD_PRESET_KEY not in state:
        state[ANALYSIS_PERIOD_PRESET_KEY] = DEFAULT_PERIOD_PRESET
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
    ad_cost = st.sidebar.number_input("Co\u00fbt par achat Meta Ads (\u20ac)", 0.0, 1000.0, 0.0, 0.1, help="Facultatif : pour afficher ton vrai co\u00fbt d'acquisition client.")
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
        "transformation_green": st.sidebar.slider("Transformation brute objectif >= ", 0.0, 1.0, DEFAULT_THRESHOLDS["transformation_green"], 0.01),
        "net_transformation_green": st.sidebar.slider("Transformation nette objectif >= ", 0.0, 1.0, DEFAULT_THRESHOLDS["net_transformation_green"], 0.01),
        "preparation_orange": st.sidebar.slider("Preparation orange > ", 0.0, 1.0, DEFAULT_THRESHOLDS["preparation_orange"], 0.01),
        "preparation_red": st.sidebar.slider("Preparation rouge > ", 0.0, 1.0, DEFAULT_THRESHOLDS["preparation_red"], 0.01),
    }
    thresholds["ad_cost_per_purchase"] = float(ad_cost)
    # Alert level for the transformation rates: 5 points under the objective.
    thresholds["transformation_orange"] = max(thresholds["transformation_green"] - 0.05, 0.0)
    thresholds["net_transformation_orange"] = max(thresholds["net_transformation_green"] - 0.05, 0.0)
    date_context["kept_rows_after_filters"] = len(df)
    date_context["active_secondary_filters"] = active_filters
    date_context["applied_filter_values"] = applied_filter_values
    return df, thresholds, date_context


def apply_filter_values(df: pd.DataFrame, applied_filter_values) -> pd.DataFrame:
    """Re-apply the sidebar multiselect filters (column, values) to another frame."""
    out = df
    for col, values in applied_filter_values or []:
        if col in out.columns:
            out = out[out[col].isin(list(values))]
    return out
