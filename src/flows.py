"""COD funnel and revenue waterfall built from the existing global metrics.

Nothing here classifies orders again: every figure comes from
``compute_global_metrics`` / ``amount_totals``. When a breakdown does not
add up exactly to the gap between two steps (e.g. odd multi-row orders),
the difference is shown as its own "Autres" line instead of being hidden.
"""
from __future__ import annotations

from .cleaning import safe_divide
from .trends import exclusive_confirmed

# Waterfall tones: lost for good, still pending (can still turn into cash), secured.
LOST, PENDING, SECURED, BASE = "lost", "pending", "secured", "base"


def _int(metrics: dict, key: str) -> int:
    return int(metrics.get(key, 0) or 0)


def _float(values: dict, key: str) -> float:
    return float(values.get(key, 0) or 0)


def _breakdown(gap: float, items: list[tuple[str, float]], others_label: str, tolerance: float = 0.0) -> list[tuple[str, float]]:
    """Non-zero items, plus the unexplained remainder; empty if the items overshoot the gap."""
    items = [(label, value) for label, value in items if value]
    remainder = gap - sum(value for _, value in items)
    if remainder < -tolerance:
        return []
    if remainder > tolerance:
        items.append((others_label, remainder))
    return items


def funnel_stages(metrics: dict) -> list[dict]:
    """Four nested COD stages with what is lost or waiting between each of them.

    Stage counts are the ones shown on the "Parcours COD" cards: confirmed
    orders exclude those still being confirmed."""
    received = _int(metrics, "orders_received")
    confirmed = exclusive_confirmed(metrics)
    sent = _int(metrics, "orders_sent")
    delivered = _int(metrics, "orders_delivered")
    values = [received, confirmed, sent, delivered]
    gaps = [
        [
            ("annulées", _int(metrics, "orders_cancelled")),
            ("encore en confirmation", _int(metrics, "orders_in_confirmation")),
            ("non classées", _int(metrics, "orders_unclassified")),
        ],
        [("en préparation (pas encore expédiées)", _int(metrics, "orders_preparation"))],
        [
            ("retours / échecs", _int(metrics, "orders_returned_failed")),
            ("encore en livraison", _int(metrics, "orders_logistics")),
        ],
    ]
    labels = ["Commandes reçues", "Confirmées", "Expédiées", "Livrées"]
    stages = []
    for index, (label, value) in enumerate(zip(labels, values)):
        stage = {
            "label": label,
            "value": value,
            "share_of_received": safe_divide(float(value), float(received)),
            "step_rate": safe_divide(float(value), float(values[index - 1])) if index else None,
            "loss_to_next": None,
            "loss_breakdown": [],
        }
        if index < len(values) - 1:
            gap = max(value - values[index + 1], 0)
            stage["loss_to_next"] = gap
            stage["loss_breakdown"] = [(name, int(count)) for name, count in _breakdown(gap, gaps[index], "autres")]
        stages.append(stage)
    return stages


def revenue_waterfall(metrics: dict, amounts: dict) -> list[dict]:
    """From the revenue of all orders received down to the delivered revenue.

    Steps: total, then each deduction (cancelled, in confirmation, preparation,
    in delivery, returns, unexplained remainder if any), then delivered revenue.
    The steps always close exactly on ``ca_delivered``."""
    total = _float(amounts, "ca_total_orders")
    delivered = _float(metrics, "ca_delivered")
    cancelled = max(total - _float(amounts, "ca_confirmed"), 0.0)
    deductions = [
        ("Annulées", cancelled, LOST),
        ("Encore en confirmation", _float(metrics, "ca_in_confirmation"), PENDING),
        ("En préparation", _float(metrics, "ca_preparation"), PENDING),
        ("En cours de livraison", _float(metrics, "ca_logistics"), PENDING),
        ("Retours / échecs", _float(metrics, "ca_returned_failed"), LOST),
    ]
    remainder = total - delivered - sum(value for _, value, _ in deductions)
    if abs(remainder) >= 1:  # below 1 DA: rounding only
        deductions.append(("Autres / non classées", remainder, PENDING))
    steps = [{"label": "CA des commandes reçues", "value": total, "start": 0.0, "end": total, "tone": BASE, "share": safe_divide(total, total)}]
    level = total
    for label, value, tone in deductions:
        if not value:
            continue
        steps.append({"label": label, "value": -value, "start": level - value, "end": level, "tone": tone, "share": safe_divide(value, total)})
        level -= value
    steps.append({"label": "CA livré", "value": delivered, "start": 0.0, "end": delivered, "tone": SECURED, "share": safe_divide(delivered, total)})
    return steps


def waterfall_summary(steps: list[dict]) -> dict:
    """Totals per tone, as shares of the revenue received."""
    total = steps[0]["value"] if steps else 0.0
    summary = {}
    for tone in (LOST, PENDING, SECURED):
        amount = sum(abs(step["value"]) for step in steps[1:] if step["tone"] == tone)
        summary[tone] = (amount, safe_divide(amount, total) if total else None)
    return summary
