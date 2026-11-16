"""Time-based analysis: evolution over time and comparison with the previous period.

Every per-period figure is produced by ``compute_global_metrics`` on the orders of
that period, so the trend and comparison numbers follow exactly the same COD
rules as the existing KPI cards.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from .cleaning import safe_divide
from .metrics import compute_global_metrics

GRANULARITY_FREQ = {"Jour": "D", "Semaine": "W", "Mois": "M"}

TREND_COLUMNS = [
    "periode",
    "commandes_recues",
    "commandes_confirmees",
    "commandes_annulees",
    "commandes_envoyees",
    "livrees",
    "retours",
    "taux_confirmation",
    "taux_livraison_finalisees",
    "taux_retour",
    "taux_transformation_reel",
    "ca_livre",
    "ca_livre_cumule",
]


def exclusive_confirmed(metrics: dict) -> int:
    """Confirmed orders as shown on the 'Taux confirmé' card (excludes pending confirmation)."""
    confirmed_net = int(metrics.get("orders_confirmed_net", 0) or 0)
    in_confirmation = int(metrics.get("orders_in_confirmation", 0) or 0)
    unclassified = int(metrics.get("orders_unclassified", 0) or 0)
    return max(confirmed_net - in_confirmation - unclassified, 0)


def auto_granularity(start, end) -> str:
    if start is None or end is None:
        return "Jour"
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    if days <= 45:
        return "Jour"
    if days <= 200:
        return "Semaine"
    return "Mois"


def order_period_keys(df: pd.DataFrame, date_col: str, granularity: str) -> pd.Series:
    """Map each row to the start of its order's period (an order = its earliest date)."""
    if df.empty or date_col not in df.columns or "order_id" not in df.columns:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    parsed = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    order_date = parsed.groupby(df["order_id"], dropna=False).transform("min")
    freq = GRANULARITY_FREQ.get(granularity, "D")
    if freq == "D":
        return order_date.dt.normalize()
    return order_date.dt.to_period(freq).dt.start_time


def compute_trend(df: pd.DataFrame, date_col: str | None, granularity: str = "Jour") -> pd.DataFrame:
    if df.empty or not date_col or date_col not in df.columns:
        return pd.DataFrame(columns=TREND_COLUMNS)
    keys = order_period_keys(df, date_col, granularity)
    valid = keys.notna()
    if not valid.any():
        return pd.DataFrame(columns=TREND_COLUMNS)
    rows = []
    for period, part in df[valid].groupby(keys[valid], sort=True):
        m = compute_global_metrics(part)
        confirmed = exclusive_confirmed(m)
        rows.append(
            {
                "periode": pd.Timestamp(period),
                "commandes_recues": m["orders_received"],
                "commandes_confirmees": confirmed,
                "commandes_annulees": m["orders_cancelled"],
                "commandes_envoyees": m["orders_sent"],
                "livrees": m["orders_delivered"],
                "retours": m["orders_returned_failed"],
                "taux_confirmation": safe_divide(float(confirmed), float(m["orders_received"])),
                "taux_livraison_finalisees": m["delivery_finalized_rate"],
                "taux_retour": m["return_rate_on_sent"],
                "taux_transformation_reel": m["transformation_real_rate"],
                "ca_livre": m["ca_delivered"],
            }
        )
    out = pd.DataFrame(rows)
    out["ca_livre_cumule"] = out["ca_livre"].cumsum()
    return out[TREND_COLUMNS]


def previous_period(start, end) -> tuple[date, date] | None:
    """Same-length window ending the day before ``start``."""
    if start is None or end is None:
        return None
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    if end_ts < start_ts:
        return None
    length = (end_ts - start_ts).days + 1
    prev_end = start_ts - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    return prev_start.date(), prev_end.date()


# Changes smaller than this are shown as stable (neutral colour) to avoid noise.
RATE_NOISE_PTS = 0.01  # 1 percentage point
RELATIVE_NOISE = 0.02  # 2 %

# (key, label, kind, higher_is_better)
COMPARISON_METRICS = [
    ("orders_received", "Commandes reçues", "count", True),
    ("confirmation_display_rate", "Taux confirmé", "rate", True),
    ("delivery_finalized_rate", "Taux livraison finalisée", "rate", True),
    ("return_rate_on_sent", "Taux retour (sur expédiées)", "rate", False),
    ("transformation_real_rate", "Transformation brute", "rate", True),
    ("ca_delivered", "CA livré", "money", True),
]


def comparison_values(metrics: dict) -> dict:
    values = dict(metrics)
    received = int(metrics.get("orders_received", 0) or 0)
    values["confirmation_display_rate"] = safe_divide(float(exclusive_confirmed(metrics)), float(received))
    return values


def compute_period_comparison(current: dict, previous: dict | None) -> list[dict]:
    """Return one row per comparison metric with the current value, previous value and delta.

    For rates the delta is in percentage points; for counts and money it is a relative change.
    ``direction`` is 'up', 'down', 'flat' or None (no comparable previous value);
    ``tone`` is 'good', 'bad' or 'neutral' according to whether higher is better.
    """
    cur = comparison_values(current)
    prev = comparison_values(previous) if previous and int(previous.get("orders_received", 0) or 0) > 0 else None
    rows = []
    for key, label, kind, higher_is_better in COMPARISON_METRICS:
        value = cur.get(key)
        prev_value = prev.get(key) if prev else None
        delta = None
        if value is not None and prev_value is not None and not pd.isna(value) and not pd.isna(prev_value):
            if kind == "rate":
                delta = float(value) - float(prev_value)
            else:
                delta = safe_divide(float(value) - float(prev_value), float(prev_value)) if float(prev_value) else None
        if delta is None:
            direction, tone = None, "neutral"
        elif abs(delta) < (RATE_NOISE_PTS if kind == "rate" else RELATIVE_NOISE):
            direction, tone = "flat", "neutral"
        else:
            direction = "up" if delta > 0 else "down"
            tone = "good" if (delta > 0) == higher_is_better else "bad"
        rows.append(
            {
                "key": key,
                "label": label,
                "kind": kind,
                "value": value,
                "previous": prev_value,
                "delta": delta,
                "direction": direction,
                "tone": tone,
            }
        )
    return rows
