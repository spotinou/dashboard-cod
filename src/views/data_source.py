"""Where the orders come from: the EcoManager API (when a token is configured) or an Excel export."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from ..data_loader import load_excel, validate_columns
from ..ecomanager import EcoManagerError, fetch_orders, history_start, shops_to_dataframe
from .filters import uploaded_file_signature

DEFAULT_BASE_URL = "https://maisonluxelle.ecomanager.dz"
API_SOURCE, EXCEL_SOURCE = "API EcoManager", "Fichier Excel"
HISTORY_OPTIONS = [35, 65, 95]  # days; 65 covers 30 days + the previous 30 days for comparisons
CACHE_SECONDS = 15 * 60


def api_shops() -> list[dict]:
    """Shops configured in Streamlit secrets.

    Several shops:            One shop (older format, still accepted):
      [[ecomanager.shops]]      [ecomanager]
      name = "Maison Luxelle"   token = "..."
      token = "..."
      base_url = "https://..."
    """
    try:
        section = st.secrets.get("ecomanager", {}) or {}
    except Exception:  # no secrets file at all
        return []
    shops = []
    for index, shop in enumerate(section.get("shops", []) or []):
        if shop.get("token"):
            shops.append({
                "name": shop.get("name") or f"Boutique {index + 1}",
                "base_url": shop.get("base_url") or DEFAULT_BASE_URL,
                "token": shop["token"],
            })
    if not shops and section.get("token"):
        shops.append({"name": section.get("name"), "base_url": section.get("base_url") or DEFAULT_BASE_URL, "token": section["token"]})
    return shops


def api_settings() -> dict | None:
    """First configured shop (kept for compatibility), or None."""
    shops = api_shops()
    return shops[0] if shops else None


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_api_orders(shops: tuple, days: int) -> tuple[pd.DataFrame, datetime, dict]:
    """Orders of the last `days` days for every shop, cached 15 minutes to respect the API quota.

    `shops` is a tuple of (name, base_url, token); each shop has its own token and quota."""
    start = history_start(days)
    orders_by_shop, counts = [], {}
    for name, base_url, token in shops:
        try:
            orders = fetch_orders(base_url, token, start)
        except EcoManagerError as exc:
            raise EcoManagerError(f"{name or 'Boutique'} : {exc}") from exc
        orders_by_shop.append((name, orders))
        counts[name or "Boutique"] = len(orders)
    return shops_to_dataframe(orders_by_shop), datetime.now(), counts


def _load_from_api(shops: list[dict]) -> tuple[pd.DataFrame, tuple] | None:
    days = st.sidebar.selectbox(
        "Historique chargé", HISTORY_OPTIONS, index=1, format_func=lambda d: f"{d} derniers jours",
        help="Plus l'historique est long, plus la première lecture est lente (limite de l'API : 50 appels / minute).",
    )
    if st.sidebar.button("\U0001f504 Rafraîchir maintenant"):
        load_api_orders.clear()
    try:
        with st.spinner("Lecture des commandes EcoManager… (1 à 3 minutes la première fois, ensuite instantané)"):
            key = tuple((shop["name"], shop["base_url"], shop["token"]) for shop in shops)
            df, fetched_at, counts = load_api_orders(key, int(days))
    except EcoManagerError as exc:
        st.error(str(exc))
        return None
    detail = " · ".join(f"{name} : {count}" for name, count in counts.items()) if len(counts) > 1 else f"{sum(counts.values())} commandes"
    st.sidebar.caption(f"✅ {detail} · mis à jour à {fetched_at:%H:%M} (actualisation auto toutes les 15 min)")
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
    shops = api_shops()
    if not shops:
        return _load_from_excel()
    source = st.sidebar.radio("Source des données", [API_SOURCE, EXCEL_SOURCE], horizontal=True)
    return _load_from_api(shops) if source == API_SOURCE else _load_from_excel()
