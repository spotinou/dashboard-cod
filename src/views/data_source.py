"""Where the orders come from: the EcoManager API (when a token is configured) or an Excel export."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from ..data_loader import load_excel, validate_columns
from ..ecomanager import EcoManagerError, fetch_orders, history_start, orders_to_dataframe
from .filters import uploaded_file_signature

DEFAULT_BASE_URL = "https://maisonluxelle.ecomanager.dz"
API_SOURCE, EXCEL_SOURCE = "API EcoManager", "Fichier Excel"
HISTORY_OPTIONS = [35, 65, 95]  # days; 65 covers 30 days + the previous 30 days for comparisons
CACHE_SECONDS = 15 * 60


def api_settings() -> dict | None:
    """Base URL and token from Streamlit secrets ([ecomanager] token = "..."), or None."""
    try:
        section = st.secrets.get("ecomanager", {})
    except Exception:  # no secrets file at all
        return None
    token = (section or {}).get("token")
    if not token:
        return None
    return {"base_url": (section.get("base_url") or DEFAULT_BASE_URL), "token": token}


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_api_orders(base_url: str, token: str, days: int) -> tuple[pd.DataFrame, datetime, int]:
    """Orders of the last `days` days, cached 15 minutes to respect the API quota."""
    orders = fetch_orders(base_url, token, history_start(days))
    return orders_to_dataframe(orders), datetime.now(), len(orders)


def _load_from_api(settings: dict) -> tuple[pd.DataFrame, tuple] | None:
    days = st.sidebar.selectbox(
        "Historique chargé", HISTORY_OPTIONS, index=1, format_func=lambda d: f"{d} derniers jours",
        help="Plus l'historique est long, plus la première lecture est lente (limite de l'API : 50 appels / minute).",
    )
    if st.sidebar.button("\U0001f504 Rafraîchir maintenant"):
        load_api_orders.clear()
    try:
        with st.spinner("Lecture des commandes EcoManager… (1 à 3 minutes la première fois, ensuite instantané)"):
            df, fetched_at, count = load_api_orders(settings["base_url"], settings["token"], int(days))
    except EcoManagerError as exc:
        st.error(str(exc))
        return None
    st.sidebar.caption(f"✅ {count} commandes · mis à jour à {fetched_at:%H:%M} (actualisation auto toutes les 15 min)")
    return df, ("api", int(days))


def _load_from_excel() -> tuple[pd.DataFrame, tuple] | None:
    uploaded = st.sidebar.file_uploader("Upload Excel CRM/ERP", type=["xlsx", "xls"])
    if uploaded is None:
        st.info("Upload un export Excel pour afficher les KPI COD.")
        return None
    try:
        raw_preview = pd.read_excel(uploaded, nrows=5, dtype=object)
        uploaded.seek(0)
        for warning in validate_columns(raw_preview):
            st.warning(warning)
        df = load_excel(uploaded)
    except Exception as exc:
        st.error(f"Impossible de lire le fichier : {exc}")
        return None
    return df, uploaded_file_signature(uploaded)


def load_orders() -> tuple[pd.DataFrame, tuple] | None:
    """Sidebar choice of the source; returns (orders table, signature) or None."""
    settings = api_settings()
    if settings is None:
        return _load_from_excel()
    source = st.sidebar.radio("Source des données", [API_SOURCE, EXCEL_SOURCE], horizontal=True)
    return _load_from_api(settings) if source == API_SOURCE else _load_from_excel()
