"""COD funnel and "where are my orders" split, built from the existing global metrics.

Nothing here classifies orders again: every figure comes from
``compute_global_metrics``. When a breakdown does not
add up exactly to the gap between two steps (e.g. odd multi-row orders),
the difference is shown as its own "Autres" line instead of being hidden.
"""
from __future__ import annotations

from .cleaning import safe_divide
from .trends import exclusive_confirmed

def _int(metrics: dict, key: str) -> int:
    return int(metrics.get(key, 0) or 0)


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


def order_status_split(metrics: dict) -> dict:
    """Where every order received is now: delivered, still in progress, or lost.

    Built from the funnel gaps, so the three groups always add up to the
    orders received. Labels are the ones of the "Parcours COD" cards."""
    stages = funnel_stages(metrics)
    received = stages[0]["value"]
    lost, in_progress = [], []
    lost_labels = {"annulées": "annulées", "retours / échecs": "retours"}
    progress_labels = {
        "encore en confirmation": "en confirmation",
        "en préparation (pas encore expédiées)": "en préparation",
        "encore en livraison": "en livraison",
    }
    others = 0
    for stage in stages[:-1]:
        for name, count in stage["loss_breakdown"]:
            if name in lost_labels:
                lost.append((lost_labels[name], count))
            elif name in progress_labels:
                in_progress.append((progress_labels[name], count))
            else:  # "non classées" / "autres": not delivered, not lost for sure
                others += count
    if others:
        in_progress.append(("autres", others))
    delivered = stages[-1]["value"]

    def group(items, total):
        return {"count": total, "share": safe_divide(float(total), float(received)), "detail": items}

    return {
        "received": received,
        "delivered": group([], delivered),
        "in_progress": group(in_progress, sum(c for _, c in in_progress)),
        "lost": group(lost, sum(c for _, c in lost)),
    }
