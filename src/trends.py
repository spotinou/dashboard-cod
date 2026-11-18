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
    "taux_livraison_total",
    "taux_retour",
    "taux_transformation_reel",
    "commandes_confirmees_nettes",
    "taux_transformation_nette",
    "ca_livre",
    "ca_livre_cumule",
    "periode_fin",
    "periode_incomplete",
    "colis_en_route",
    "part_en_route",
]

# A period whose shipped parcels are still more than this share "on the road" has
# delivery figures that will still move: it is shown as provisional on the charts.
PROVISIONAL_IN_TRANSIT_SHARE = 0.15


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
    if days <= 14:
        return "Jour"
    if days <= 120:
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


def period_end(period_start: pd.Timestamp, granularity: str) -> pd.Timestamp:
    freq = GRANULARITY_FREQ.get(granularity, "D")
    if freq == "D":
        return period_start
    return pd.Timestamp(period_start).to_period(freq).end_time.normalize()


def compute_trend(df: pd.DataFrame, date_col: str | None, granularity: str = "Jour", start=None, end=None) -> pd.DataFrame:
    """One row per period. ``start``/``end`` (the analysis window) flag periods that are cut by it."""
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
                "taux_livraison_total": m["delivery_total_rate_on_sent"],
                "taux_retour": m["return_rate_on_sent"],
                "taux_transformation_reel": m["transformation_real_rate"],
                "commandes_confirmees_nettes": m["orders_confirmed_net"],
                "taux_transformation_nette": net_transformation_rate(m),
                "ca_livre": m["ca_delivered"],
                "periode_fin": period_end(pd.Timestamp(period), granularity),
                "colis_en_route": max(int(m["orders_sent"]) - int(m["orders_delivered"]) - int(m["orders_returned_failed"]), 0),
            }
        )
    out = pd.DataFrame(rows)
    out["ca_livre_cumule"] = out["ca_livre"].cumsum()
    incomplete = pd.Series(False, index=out.index)
    if start is not None:
        incomplete |= out["periode"] < pd.Timestamp(start)
    if end is not None:
        incomplete |= out["periode_fin"] > pd.Timestamp(end)
    out["periode_incomplete"] = incomplete
    out["part_en_route"] = [
        safe_divide(float(c), float(s)) for c, s in zip(out["colis_en_route"], out["commandes_envoyees"])
    ]
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
    ("delivery_total_rate_on_sent", "Taux livré (sur expédiées)", "rate", True),
    ("delivery_finalized_rate", "Taux livré (sur colis terminés)", "rate", True),
    ("transformation_real_rate", "Taux de transformation brute", "rate", True),
    ("net_transformation_rate", "Taux de transformation nette", "rate", True),
    ("return_rate_on_sent", "Taux retour", "rate", False),
    ("cancellation_rate", "Taux annulé", "rate", False),
]
# Indicators that keep moving while parcels are still on the road.
DELIVERY_DEPENDENT = {"delivery_total_rate_on_sent", "delivery_finalized_rate", "return_rate_on_sent", "transformation_real_rate", "net_transformation_rate"}


def in_transit_share(metrics: dict) -> float | None:
    """Share of shipped parcels that are neither delivered nor returned yet."""
    sent = int(metrics.get("orders_sent", 0) or 0)
    done = int(metrics.get("orders_delivered", 0) or 0) + int(metrics.get("orders_returned_failed", 0) or 0)
    return safe_divide(float(max(sent - done, 0)), float(sent))


def net_transformation_rate(metrics: dict) -> float | None:
    """Taux de transformation nette: delivered / (received - cancelled) = delivered / net confirmed."""
    return safe_divide(float(metrics.get("orders_delivered", 0) or 0), float(metrics.get("orders_confirmed_net", 0) or 0))


def card_confirmation_rate(metrics: dict) -> float | None:
    """The "Taux confirmé" exactly as the KPI card shows it.

    Same rule as ``displayed_reception_rates``: confirmed + in confirmation +
    cancelled are rounded to add up to exactly 100.0 %."""
    received = int(metrics.get("orders_received", 0) or 0)
    if received == 0:
        return None
    pending_tenths = round(int(metrics.get("orders_in_confirmation", 0) or 0) / received * 1000)
    cancelled_tenths = round(int(metrics.get("orders_cancelled", 0) or 0) / received * 1000)
    return max(0, 1000 - pending_tenths - cancelled_tenths) / 1000


def comparison_values(metrics: dict) -> dict:
    values = dict(metrics)
    values["confirmation_display_rate"] = card_confirmation_rate(metrics)
    values["net_transformation_rate"] = net_transformation_rate(metrics)
    return values


def compute_period_comparison(current: dict, previous: dict | None) -> list[dict]:
    """Return one row per comparison metric with the current value, previous value and delta.

    For rates the delta is in percentage points; for counts and money it is a relative change.
    ``direction`` is 'up', 'down', 'flat' or None (no comparable previous value);
    ``tone`` is 'good', 'bad' or 'neutral' according to whether higher is better.
    ``provisional`` is True for delivery figures while too many parcels of the current
    period are still on the road: their delta is shown but not judged (neutral tone).
    """
    cur = comparison_values(current)
    in_transit = in_transit_share(current)
    still_moving = in_transit is not None and in_transit > PROVISIONAL_IN_TRANSIT_SHARE
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
        provisional = key in DELIVERY_DEPENDENT and still_moving
        if provisional:
            tone = "neutral"
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
                "provisional": provisional,
                "in_transit_share": in_transit if provisional else None,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Reading helpers for the evolution charts (one chart = one metric).
# ---------------------------------------------------------------------------

# key, title, explanation, kind, higher_is_better, chart form, depends on delivery outcome
TREND_CHARTS = [
    ("taux_confirmation", "Taux confirmé", "", "rate", True, "line", False),
    ("taux_livraison_total", "Taux livré (sur expédiées)", "", "rate", True, "line", True),
    ("taux_transformation_reel", "Taux de transformation brute", "", "rate", True, "line", True),
    ("commandes_recues", "Commandes reçues", "", "count", True, "bar", False),
]

# Rates are averaged as total numerator / total denominator (not a mean of daily rates),
# exactly like the global KPI cards.
RATE_PARTS = {
    "taux_confirmation": ("commandes_confirmees", ["commandes_recues"]),
    "taux_livraison_finalisees": ("livrees", ["livrees", "retours"]),
    "taux_livraison_total": ("livrees", ["commandes_envoyees"]),
    "taux_retour": ("retours", ["commandes_envoyees"]),
    "taux_transformation_reel": ("livrees", ["commandes_recues"]),
    "taux_transformation_nette": ("livrees", ["commandes_confirmees_nettes"]),
}

# Below these changes vs the average, the last period is read as "stable".
STABLE_RATE_PTS = 0.02
STABLE_RELATIVE = 0.10


def provisional_mask(trend: pd.DataFrame, depends_on_delivery: bool) -> pd.Series:
    """True for periods whose value is not final: cut by the analysis window, or
    (for delivery figures) with too many parcels still on the road."""
    if trend.empty:
        return pd.Series(dtype=bool)
    mask = trend["periode_incomplete"].fillna(False).astype(bool)
    if depends_on_delivery:
        in_transit = pd.to_numeric(trend["part_en_route"], errors="coerce").fillna(0)
        mask = mask | in_transit.gt(PROVISIONAL_IN_TRANSIT_SHARE)
    return mask


def trend_average(trend: pd.DataFrame, key: str, mask: pd.Series | None = None):
    """Average over the given rows (all rows when mask is None)."""
    rows = trend if mask is None else trend[mask]
    if rows.empty:
        return None
    if key in RATE_PARTS:
        numerator, denominators = RATE_PARTS[key]
        return safe_divide(float(rows[numerator].sum()), float(rows[denominators].sum().sum()))
    values = pd.to_numeric(rows[key], errors="coerce").dropna()
    return float(values.mean()) if not values.empty else None


def trend_reading(trend: pd.DataFrame, key: str, kind: str, higher_is_better: bool, depends_on_delivery: bool) -> dict:
    """Plain-language reading: last reliable period vs the average of reliable periods."""
    provisional = provisional_mask(trend, depends_on_delivery)
    reliable = ~provisional
    reading = {"average": None, "last_value": None, "last_period": None, "direction": None, "tone": "neutral", "provisional_count": int(provisional.sum())}
    if trend.empty or not reliable.any():
        return reading
    average = trend_average(trend, key, reliable)
    last = trend[reliable].iloc[-1]
    last_value = last[key]
    reading.update({"average": average, "last_value": last_value, "last_period": last["periode"]})
    if average is None or last_value is None or pd.isna(last_value) or int(reliable.sum()) < 2:
        return reading
    gap = float(last_value) - float(average)
    stable = abs(gap) < STABLE_RATE_PTS if kind == "rate" else (abs(gap) < STABLE_RELATIVE * abs(float(average)) if average else gap == 0)
    if stable:
        reading.update({"direction": "flat", "tone": "neutral"})
    else:
        reading["direction"] = "up" if gap > 0 else "down"
        reading["tone"] = "good" if (gap > 0) == higher_is_better else "bad"
    return reading


def cac_multiplier(metrics: dict) -> dict:
    """Factor to apply to the ad cost per purchase to get the real cost per delivered customer.

    real  = received / delivered (inverse of the gross transformation rate);
    estimated = 1 / (taux confirmé x taux livré sur colis terminés): what the real
    factor should become once every parcel still on the road is delivered or returned."""
    received = float(metrics.get("orders_received", 0) or 0)
    delivered = float(metrics.get("orders_delivered", 0) or 0)
    confirmed = card_confirmation_rate(metrics)
    finalized = metrics.get("delivery_finalized_rate")
    expected = confirmed * finalized if confirmed and finalized else None
    return {
        "real": safe_divide(received, delivered),
        "estimated": safe_divide(1.0, expected) if expected else None,
        "received": int(received),
        "delivered": int(delivered),
    }
