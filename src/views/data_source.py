"""Where the orders come from: the EcoManager API (when a token is configured) or an Excel export."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from ..data_loader import load_excel, validate_columns
from ..ecomanager import MAX_PAGES, EcoManagerError, RateLimiter, fetch_orders, history_start, shops_to_dataframe
from .filters import uploaded_file_signature

DEFAULT_BASE_URL = "https://maisonluxelle.ecomanager.dz"
API_SOURCE, EXCEL_SOURCE = "API EcoManager", "Fichier Excel"
HISTORY_OPTIONS = [35, 65, 95]  # days; 65 covers 30 days + the previous 30 days for comparisons
CACHE_SECONDS = 15 * 60
REFRESH_COOLDOWN_SECONDS = 120
LAST_REFRESH_KEY = "ecomanager_last_manual_refresh"
LAST_GOOD_KEY = "ecomanager_last_good_data"


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

    `shops` is a tuple of (name, base_url, token). One rate limiter is shared by all shops:
    if EcoManager counts calls per IP address, two shops read one after the other must not
    exceed the quota together."""
    start = history_start(days)
    limiter = RateLimiter()
    orders_by_shop, reports = [], {}
    for name, base_url, token in shops:
        report: dict = {}
        try:
            orders = fetch_orders(base_url, token, start, limiter=limiter, report=report)
        except EcoManagerError as exc:
            raise EcoManagerError(f"{name or 'Boutique'} : {exc}") from exc
        orders_by_shop.append((name, orders))
        reports[name or "Boutique"] = {**report, "orders": len(orders)}
    return shops_to_dataframe(orders_by_shop), datetime.now(), reports


def _refresh_button() -> None:
    """Manual refresh, at most once every REFRESH_COOLDOWN_SECONDS (protects the API quota)."""
    last = st.session_state.get(LAST_REFRESH_KEY)
    wait = 0 if last is None else REFRESH_COOLDOWN_SECONDS - (datetime.now() - last).total_seconds()
    if st.sidebar.button("\U0001f504 Rafra\u00eechir maintenant", disabled=wait > 0,
                         help="Possible une fois toutes les 2 minutes, pour ne pas d\u00e9passer le quota de l'API." if wait > 0 else None):
        load_api_orders.clear()
        st.session_state[LAST_REFRESH_KEY] = datetime.now()


def _load_from_api(shops: list[dict]) -> tuple[pd.DataFrame, tuple] | None:
    days = st.sidebar.selectbox(
        "Historique charg\u00e9", HISTORY_OPTIONS, index=1, format_func=lambda d: f"{d} derniers jours",
        help="Commandes cr\u00e9\u00e9es pendant cette dur\u00e9e. Plus c'est long, plus la premi\u00e8re lecture est lente (limite de l'API : 50 appels / minute).",
    )
    _refresh_button()
    key = tuple((shop["name"], shop["base_url"], shop["token"]) for shop in shops)
    try:
        with st.spinner("Lecture des commandes EcoManager\u2026 (1 \u00e0 3 minutes la premi\u00e8re fois, ensuite instantan\u00e9)"):
            df, fetched_at, reports = load_api_orders(key, int(days))
    except EcoManagerError as exc:
        # Keep the dashboard usable with the last good data, clearly marked as old.
        backup = st.session_state.get(LAST_GOOD_KEY)
        if backup and backup["key"] == (key, int(days)):
            st.warning(f"\u26a0\ufe0f Lecture de l'API impossible ({exc}). Affichage des derni\u00e8res donn\u00e9es r\u00e9ussies, de {backup['fetched_at']:%H:%M}.")
            return backup["df"], ("api", int(days))
        st.error(str(exc))
        return None
    st.session_state[LAST_GOOD_KEY] = {"key": (key, int(days)), "df": df, "fetched_at": fetched_at}
    counts = {name: r["orders"] for name, r in reports.items()}
    detail = " \u00b7 ".join(f"{name} : {count}" for name, count in counts.items()) if len(counts) > 1 else f"{sum(counts.values())} commandes"
    st.sidebar.caption(
        f"\u2705 {detail} \u00b7 cr\u00e9\u00e9es depuis le {history_start(int(days)):%d/%m} \u00b7 mis \u00e0 jour \u00e0 {fetched_at:%H:%M} (auto toutes les 15 min)"
    )
    incomplete = [name for name, r in reports.items() if not r.get("complete")]
    if incomplete:
        st.warning(
            f"\u26a0\ufe0f Lecture incompl\u00e8te pour {', '.join(incomplete)} : limite de s\u00e9curit\u00e9 atteinte "
            f"({MAX_PAGES * 100} commandes). Les chiffres peuvent \u00eatre sous-estim\u00e9s : choisis un historique plus court."
        )
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
