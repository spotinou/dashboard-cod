"""Ranking helpers for the "classement" charts (livreurs, confirmatrices, produits, wilayas).

These functions only select, sort and summarise rows that the existing metric
tables already contain: they never recompute a COD figure.
"""
from __future__ import annotations

import pandas as pd

from .cleaning import safe_divide

# Same "unknown" values as ui.is_known_value, plus a few harmless extras.
UNKNOWN_LABELS = {"", "non renseigné", "non renseign\u00c3\u00a9", "non renseigne", "nan", "none", "-", "—"}

# Within this gap from the average, a rate is read as "in the average" (grey).
NEAR_AVERAGE_PTS = 0.02
MAX_RATE_ROWS = 20
MAX_AMOUNT_ROWS = 10
OTHERS_LABEL = "Autres"


def is_known_label(value) -> bool:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return False
    return str(value).strip().lower() not in UNKNOWN_LABELS


def pooled_rate(df: pd.DataFrame, numerator_col: str, denominator_col: str) -> float | None:
    """Company-wide rate over every row: total numerator / total denominator.

    Summing the per-row numerators and denominators gives back the same figure
    as the global KPI cards (e.g. total delivered / total shipped)."""
    if df.empty or numerator_col not in df.columns or denominator_col not in df.columns:
        return None
    numerator = pd.to_numeric(df[numerator_col], errors="coerce").fillna(0).sum()
    denominator = pd.to_numeric(df[denominator_col], errors="coerce").fillna(0).sum()
    return safe_divide(float(numerator), float(denominator))


def rate_tone(value, average, higher_is_better: bool) -> str:
    if value is None or average is None or pd.isna(value) or pd.isna(average):
        return "neutral"
    gap = float(value) - float(average)
    if abs(gap) < NEAR_AVERAGE_PTS:
        return "neutral"
    return "good" if (gap > 0) == higher_is_better else "bad"


def rate_ranking_rows(
    df: pd.DataFrame,
    label_col: str,
    rate_col: str,
    volume_col: str,
    volume_min: int,
    higher_is_better: bool = True,
    max_rows: int = MAX_RATE_ROWS,
) -> tuple[pd.DataFrame, int, int]:
    """Rows to draw, best first.

    Returns (rows, hidden_low_volume, hidden_middle):
    - rows below ``volume_min`` are left out (too few orders to judge) and counted;
    - beyond ``max_rows`` the best and worst halves are kept and the middle is counted.
    """
    needed = {label_col, rate_col, volume_col}
    if df.empty or not needed.issubset(df.columns):
        return pd.DataFrame(columns=[label_col, rate_col, volume_col]), 0, 0
    rows = df[df[label_col].apply(is_known_label)].copy()
    rows[rate_col] = pd.to_numeric(rows[rate_col], errors="coerce")
    rows[volume_col] = pd.to_numeric(rows[volume_col], errors="coerce").fillna(0)
    rows = rows.dropna(subset=[rate_col])
    enough = rows[volume_col].ge(volume_min)
    hidden_low_volume = int((~enough).sum())
    rows = rows[enough]
    rows = rows.sort_values([rate_col, volume_col], ascending=[not higher_is_better, False]).reset_index(drop=True)
    hidden_middle = 0
    if len(rows) > max_rows:
        half = max_rows // 2
        hidden_middle = len(rows) - 2 * half
        rows = pd.concat([rows.head(half), rows.tail(half)]).reset_index(drop=True)
    return rows, hidden_low_volume, hidden_middle


def amount_ranking_rows(df: pd.DataFrame, label_col: str, value_col: str, max_rows: int = MAX_AMOUNT_ROWS) -> tuple[pd.DataFrame, float]:
    """Biggest amounts first, the tail folded into one "Autres" row so shares add up to 100 %.

    Returns (rows with ``part`` = share of total, total)."""
    if df.empty or label_col not in df.columns or value_col not in df.columns:
        return pd.DataFrame(columns=[label_col, value_col, "part", "nb_regroupes"]), 0.0
    rows = df[[label_col, value_col]].copy()
    rows[value_col] = pd.to_numeric(rows[value_col], errors="coerce").fillna(0)
    rows = rows[rows[value_col] > 0]
    total = float(rows[value_col].sum())
    known = rows[rows[label_col].apply(is_known_label)].sort_values(value_col, ascending=False)
    unknown_total = float(rows.loc[~rows[label_col].apply(is_known_label), value_col].sum())
    top = known.head(max_rows).copy()
    top["nb_regroupes"] = 0
    tail = known.iloc[max_rows:]
    others_total = float(tail[value_col].sum()) + unknown_total
    if others_total > 0:
        others = pd.DataFrame([{label_col: OTHERS_LABEL, value_col: others_total, "nb_regroupes": len(tail) + int(unknown_total > 0)}])
        top = pd.concat([top, others], ignore_index=True)
    top["part"] = [safe_divide(float(v), total) for v in top[value_col]]
    return top.reset_index(drop=True), total


def rate_ranking_reading(rows: pd.DataFrame, label_col: str, rate_col: str) -> dict:
    """Best and weakest entries (rows must already be sorted best first)."""
    if rows.empty:
        return {"best": None, "worst": None}
    best, worst = rows.iloc[0], rows.iloc[-1]
    return {
        "best": (best[label_col], best[rate_col]),
        "worst": (worst[label_col], worst[rate_col]) if len(rows) > 1 else None,
    }


def amount_concentration(rows: pd.DataFrame, label_col: str, value_col: str, total: float, top_n: int = 3) -> float | None:
    """Share of the total held by the ``top_n`` biggest named entries."""
    if rows.empty or not total:
        return None
    named = rows[rows[label_col] != OTHERS_LABEL]
    return safe_divide(float(named[value_col].head(top_n).sum()), float(total))
