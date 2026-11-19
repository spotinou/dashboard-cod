"""Read orders from the EcoManager shop API and turn them into the same table as the Excel export.

API: GET {base_url}/api/shop/v2/orders, Bearer token, cursor pagination.
The API has no date filter, so orders are read newest first and reading stops
once a page is older than the requested start date.

Rate limits (documentation): 5 / second, 50 / minute, 1000 / hour, 10000 / day.
Repeatedly exceeding them can get the IP banned, so requests are spaced and a
429 answer is waited out instead of retried immediately.

The token is never stored in the code: it is read from Streamlit secrets.
"""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timedelta
from typing import Callable, Iterable

import pandas as pd
import requests

from .data_loader import prepare_dataframe

ORDERS_PATH = "/api/shop/v2/orders"
PER_PAGE = 100
MAX_PAGES = 400  # safety net: 40 000 orders
MAX_PER_MINUTE = 45  # stay under the 50 / minute quota
MIN_INTERVAL_SECONDS = 0.25  # stay under the 5 / second quota
MAX_429_RETRIES = 3
TIMEOUT_SECONDS = 30


class EcoManagerError(RuntimeError):
    """Readable error for the dashboard (bad token, quota, network...)."""


class RateLimiter:
    """Keeps requests under N per minute and one every `min_interval` seconds."""

    def __init__(self, per_minute: int = MAX_PER_MINUTE, min_interval: float = MIN_INTERVAL_SECONDS,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.per_minute, self.min_interval, self.clock, self.sleep = per_minute, min_interval, clock, sleep
        self.calls: deque[float] = deque()

    def wait(self) -> None:
        now = self.clock()
        while self.calls and now - self.calls[0] >= 60:
            self.calls.popleft()
        if len(self.calls) >= self.per_minute:
            self.sleep(60 - (now - self.calls[0]) + 0.1)
        elif self.calls and now - self.calls[-1] < self.min_interval:
            self.sleep(self.min_interval - (now - self.calls[-1]))
        self.calls.append(self.clock())


def _retry_after_seconds(response) -> float:
    headers = getattr(response, "headers", {}) or {}
    for key in ("Retry-After", "X-RateLimit-Reset"):
        value = headers.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        # X-RateLimit-Reset may be an epoch timestamp
        return max(number - time.time(), 1.0) if number > 10**9 else max(number, 1.0)
    return 60.0


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return pd.Timestamp(value).to_pydatetime()
    except (ValueError, TypeError):
        return None


def fetch_orders(
    base_url: str,
    token: str,
    since: datetime,
    session=None,
    limiter: RateLimiter | None = None,
    sleep: Callable[[float], None] = time.sleep,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """All orders created on or after `since` (newest first)."""
    if not token:
        raise EcoManagerError("Aucune clé API EcoManager configurée (Secrets Streamlit).")
    session = session or requests.Session()
    limiter = limiter or RateLimiter(sleep=sleep)
    url = base_url.rstrip("/") + ORDERS_PATH
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
    params: dict = {"per_page": PER_PAGE, "sort_direction": "desc"}
    orders: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        for attempt in range(MAX_429_RETRIES + 1):
            limiter.wait()
            try:
                response = session.get(url, headers=headers, params=params, timeout=TIMEOUT_SECONDS)
            except requests.RequestException as exc:
                raise EcoManagerError(f"Impossible de joindre EcoManager : {exc.__class__.__name__}.") from exc
            if response.status_code != 429:
                break
            if attempt == MAX_429_RETRIES:
                raise EcoManagerError("Quota de l'API EcoManager dépassé (429). Réessaie dans quelques minutes.")
            sleep(_retry_after_seconds(response))
        if response.status_code == 401:
            raise EcoManagerError("Clé API EcoManager refusée (401). Vérifie le token dans les Secrets Streamlit.")
        if response.status_code == 503:
            raise EcoManagerError("EcoManager est en maintenance (503). Réessaie plus tard.")
        if response.status_code != 200:
            raise EcoManagerError(f"Erreur de l'API EcoManager ({response.status_code}).")
        payload = response.json()
        batch = payload.get("data") or []
        reached_older = False
        for order in batch:
            created = _parse_dt(order.get("created_at"))
            if created is not None and created < since:
                reached_older = True
                continue
            orders.append(order)
        if progress:
            progress(page, len(orders))
        next_cursor = (payload.get("meta") or {}).get("next_cursor")
        if reached_older or not batch or not next_cursor:
            return orders
        params = {"per_page": PER_PAGE, "sort_direction": "desc", "cursor": next_cursor}
    return orders


def _name(value) -> str | None:
    if isinstance(value, dict):
        return value.get("name")
    return value


def orders_to_rows(orders: Iterable[dict], shop: str | None = None, prefix_reference: bool = False) -> list[dict]:
    """One row per product line, with the Excel export column names.

    With several shops, references are prefixed by the shop name so that two
    orders with the same reference in two shops are never merged."""
    rows = []
    for order in orders:
        reference = order.get("reference")
        if prefix_reference and shop and reference:
            reference = f"{shop} \u00b7 {reference}"
        common = {
            "Boutique": shop,
            "Référence commande": reference,
            "Tracking": order.get("tracking"),
            "N°commande": f"{shop}-{order.get('id')}" if prefix_reference and shop else order.get("id"),
            "Méthode de livraison": "Stop desk" if order.get("is_stopdesk") in (True, 1, "1") else "Domicile",
            "Statut commande": order.get("order_state_name"),
            "Client": order.get("full_name"),
            "Email": order.get("email"),
            "Téléphone": order.get("telephone"),
            "Téléphone 2": order.get("telephone_2"),
            "Wilaya": order.get("wilaya"),
            "Commune": order.get("commune"),
            "Adresse": order.get("address"),
            "Source": order.get("api_source"),
            "Total produit": order.get("total_products"),
            "Réduction": order.get("total_discount"),
            "Frais de livraison": order.get("total_shipping"),
            "Total commande": order.get("total"),
            "Livreur": _name(order.get("carrier")),
            "Remarque": order.get("note"),
            "Affectée à": _name(order.get("confirmer")),
            "Crée le": order.get("created_at"),
            "Affectée le": order.get("assigned_at"),
            "Confirmée le": order.get("confirmed_at"),
            "Dispatchée le": order.get("dispatched_at"),
            "Expédiée le": order.get("shipped_at"),
            "Livrée le": order.get("delivered_at"),
            "Encaissée le": order.get("paid_at"),
            "Echouée le": order.get("failed_at"),
            "Retournée le": order.get("returned_at"),
            "Annulée le": order.get("canceled_at"),
        }
        items = order.get("items") or [{}]
        for item in items:
            rows.append(
                {
                    **common,
                    "SKU produit": item.get("sku"),
                    "Nom produit": item.get("title_fr") or item.get("title"),
                    "Option": item.get("option_name"),
                    "Quantité": item.get("quantity"),
                    "Prix de vente": item.get("selling_price"),
                }
            )
    return rows


def orders_to_dataframe(orders: Iterable[dict], shop: str | None = None) -> pd.DataFrame:
    """Same cleaned table as `load_excel`, so every dashboard calculation is unchanged."""
    return shops_to_dataframe([(shop, list(orders))])


def shops_to_dataframe(orders_by_shop: list[tuple[str | None, list[dict]]]) -> pd.DataFrame:
    """One table for one or several shops (column "Boutique" tells them apart)."""
    several = len(orders_by_shop) > 1
    rows = [row for shop, orders in orders_by_shop for row in orders_to_rows(orders, shop, prefix_reference=several)]
    if not rows:
        raise EcoManagerError("Aucune commande trouvée sur la période chargée.")
    return prepare_dataframe(pd.DataFrame(rows))


def history_start(days: int, now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    return (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
