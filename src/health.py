"""Business health: vital rates against the sidebar objectives, and orders stuck too long.

Vital rates are read from ``compute_global_metrics`` (same figures as the KPI
cards); objectives are the thresholds the user already sets in the sidebar.
Stuck orders use the existing order flags (is_in_confirmation, is_preparation,
is_dispatch, is_in_delivery) and the order dates: nothing is reclassified.
"""
from __future__ import annotations

import pandas as pd

from .trends import card_confirmation_rate, net_transformation_rate

GOOD, WARN, BAD, UNKNOWN = "good", "warn", "bad", "neutral"

# key, label, plain sentence ({n} = value per 100), higher_is_better, threshold keys (objective, alert)
VITAL_SIGNS = [
    ("confirmation", "Taux confirmé", "Sur 100 commandes reçues, {n} sont confirmées", True, ("confirmation_green", "confirmation_orange")),
    ("delivery", "Taux livré (sur expédiées)", "Sur 100 colis expédiés, {n} sont livrés", True, ("delivery_green", "delivery_orange")),
    ("delivery_finalized", "Taux livré (sur colis terminés)", "Sur 100 colis arrivés au bout (livrés ou revenus), {n} sont livrés", True, ("delivery_green", "delivery_orange")),
    ("transformation", "Taux de transformation brute", "Sur 100 commandes reçues, {n} sont livrées", True, ("transformation_green", "transformation_orange")),
    ("net_transformation", "Taux de transformation nette", "Sur 100 commandes reçues hors annulées, {n} sont livrées", True, ("net_transformation_green", "net_transformation_orange")),
    ("return", "Taux retour", "Sur 100 colis expédiés, {n} reviennent", False, ("return_orange", "return_red")),
    ("cancellation", "Taux annulé", "Sur 100 commandes reçues, {n} sont annulées", False, ("cancellation_orange", "cancellation_red")),
]

# Days after which an order waiting at a step is considered stuck.
STUCK_LIMIT_DAYS = {"confirmation": 3, "preparation": 2, "delivery": 7}


def vital_rate(metrics: dict, key: str) -> float | None:
    if key == "confirmation":
        return card_confirmation_rate(metrics)
    return {
        "delivery": metrics.get("delivery_total_rate_on_sent"),
        "delivery_finalized": metrics.get("delivery_finalized_rate"),
        "transformation": metrics.get("transformation_real_rate"),
        "net_transformation": net_transformation_rate(metrics),
        "return": metrics.get("return_rate_on_sent"),
        "cancellation": metrics.get("cancellation_rate"),
    }[key]


def verdict(value, objective: float, alert: float, higher_is_better: bool) -> str:
    """good = objective reached, warn = between objective and alert level, bad = beyond alert level."""
    if value is None or pd.isna(value):
        return UNKNOWN
    if higher_is_better:
        return GOOD if value >= objective else WARN if value >= alert else BAD
    return GOOD if value <= objective else WARN if value <= alert else BAD


def vital_signs(metrics: dict, thresholds: dict[str, float]) -> list[dict]:
    signs = []
    for key, label, explanation, higher_is_better, (objective_key, alert_key) in VITAL_SIGNS:
        value = vital_rate(metrics, key)
        objective, alert = float(thresholds[objective_key]), float(thresholds[alert_key])
        signs.append(
            {
                "key": key,
                "label": label,
                "explanation": explanation,
                "value": value,
                "objective": objective,
                "alert": alert,
                "higher_is_better": higher_is_better,
                "verdict": verdict(value, objective, alert, higher_is_better),
            }
        )
    return signs


def health_summary(signs: list[dict]) -> dict:
    counts = {tone: sum(1 for s in signs if s["verdict"] == tone) for tone in (GOOD, WARN, BAD, UNKNOWN)}
    overall = BAD if counts[BAD] else WARN if counts[WARN] else GOOD if counts[GOOD] else UNKNOWN
    return {"overall": overall, "counts": counts, "to_watch": [s for s in signs if s["verdict"] in (BAD, WARN)]}


# ---------------------------------------------------------------------------
# Orders stuck too long at one step
# ---------------------------------------------------------------------------

DATE_COLUMNS = ["Crée le", "Affectée le", "Confirmée le", "Dispatchée le", "Expédiée le", "Livrée le", "Encaissée le", "Echouée le", "Retournée le", "Annulée le"]


def reference_date(df: pd.DataFrame):
    """Latest date found in the file: the day the export was taken, at the earliest."""
    dates = [pd.to_datetime(df[c], errors="coerce", dayfirst=True) for c in DATE_COLUMNS if c in df.columns]
    if not dates:
        return None
    latest = pd.concat(dates).max()
    return None if pd.isna(latest) else latest.normalize()


def _first_date(orders: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series(pd.NaT, index=orders.index, dtype="datetime64[ns]")
    for col in columns:
        if col in orders.columns:
            result = result.fillna(pd.to_datetime(orders[col], errors="coerce", dayfirst=True))
    return result


STUCK_STEPS = [
    # key, title, flag columns, date columns (first available), owner column
    ("confirmation", "En attente de confirmation", ["is_in_confirmation"], ["Crée le", "Affectée le"], "Affectée à"),
    ("preparation", "En préparation (pas encore expédiées)", ["is_preparation"], ["Confirmée le", "Affectée le", "Crée le"], None),
    ("delivery", "En livraison", ["is_dispatch", "is_in_delivery"], ["Expédiée le", "Dispatchée le"], "Livreur"),
]
DETAIL_COLUMNS = ["Référence commande", "Statut commande", "Affectée à", "Livreur", "Wilaya", "Nom produit"]


def stuck_orders(df: pd.DataFrame, today, limits: dict[str, int] | None = None) -> list[dict]:
    """For each waiting step: how many orders wait, how many wait longer than the limit, and who holds them."""
    limits = limits or STUCK_LIMIT_DAYS
    steps = []
    if df.empty or "order_id" not in df.columns:
        return steps
    flag_cols = sorted({flag for _, _, flags, _, _ in STUCK_STEPS for flag in flags if flag in df.columns})
    first_cols = [c for c in set(DATE_COLUMNS + DETAIL_COLUMNS) if c in df.columns and c != "order_id"]
    agg = {flag: "max" for flag in flag_cols}
    agg.update({c: "first" for c in first_cols})
    orders = df.groupby("order_id", dropna=False).agg(agg)
    for key, title, flags, date_cols, owner_col in STUCK_STEPS:
        present = [f for f in flags if f in orders.columns]
        if not present:
            continue
        waiting = orders[orders[present].fillna(False).astype(bool).any(axis=1)].copy()
        since = _first_date(waiting, date_cols)
        waiting["jours"] = (pd.Timestamp(today) - since.dt.normalize()).dt.days if today is not None else pd.NA
        limit = int(limits[key])
        late = waiting[pd.to_numeric(waiting["jours"], errors="coerce").gt(limit)].sort_values("jours", ascending=False)
        owners = []
        if owner_col and owner_col in late.columns and not late.empty:
            owners = [(str(name), int(count)) for name, count in late[owner_col].value_counts().head(3).items()]
        steps.append(
            {
                "key": key,
                "title": title,
                "limit_days": limit,
                "waiting": int(len(waiting)),
                "late": int(len(late)),
                "no_date": int(since.isna().sum()),
                "owners": owners,
                "late_orders": late.reset_index(),
            }
        )
    return steps


# ---------------------------------------------------------------------------
# Average delivery time
# ---------------------------------------------------------------------------


def average_delivery_days(df: pd.DataFrame) -> dict:
    """Average number of days between shipping and delivery, over delivered orders.

    Delivery date = "Livrée le", or "Encaissée le" when the delivery date is missing.
    Orders without both dates (or with a delivery before shipping) are left out and counted."""
    result = {"days": None, "orders": 0, "without_dates": 0}
    if df.empty or "order_id" not in df.columns or "is_delivered" not in df.columns:
        return result
    cols = [c for c in ["is_delivered", "Expédiée le", "Livrée le", "Encaissée le"] if c in df.columns]
    agg = {c: ("max" if c == "is_delivered" else "first") for c in cols}
    orders = df.groupby("order_id", dropna=False).agg(agg)
    delivered = orders[orders["is_delivered"].fillna(False).astype(bool)]
    if delivered.empty:
        return result
    shipped = _first_date(delivered, ["Expédiée le"])
    arrived = _first_date(delivered, ["Livrée le", "Encaissée le"])
    days = (arrived.dt.normalize() - shipped.dt.normalize()).dt.days
    valid = days[days.notna() & days.ge(0)]
    result.update({"days": float(valid.mean()) if not valid.empty else None, "orders": int(len(valid)), "without_dates": int(len(delivered) - len(valid))})
    return result
