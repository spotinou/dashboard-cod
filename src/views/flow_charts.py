"""Où sont mes commandes : every order received, split into delivered / in progress / lost."""
from __future__ import annotations

import streamlit as st

from ..flows import order_status_split
from .formatting import format_count, html_text, pct

ORDER_GROUPS = [
    # key, icon, title, border colour, background
    ("delivered", "✅", "Livrées", "#16a34a", "#f0fdf4"),
    ("in_progress", "⏳", "En cours", "#f59e0b", "#fffbeb"),
    ("lost", "❌", "Perdues", "#dc2626", "#fff1f2"),
]


def order_status_cards_html(split: dict) -> str:
    cards = []
    for key, icon, title, border, background in ORDER_GROUPS:
        group = split[key]
        detail = " · ".join(f"{format_count(count)} {html_text(name)}" for name, count in group["detail"] if count)
        detail_html = f'<div style="font-size:13px;color:#334155;margin-top:6px">{detail}</div>' if detail else ""
        cards.append(
            f'<div style="flex:1;min-width:200px;border:1px solid #e2e8f0;border-left:5px solid {border};background:{background};'
            f'border-radius:8px;padding:12px 14px">'
            f'<div style="font-size:14px;font-weight:800;color:#0f172a">{icon} {html_text(title)}</div>'
            f'<div style="display:flex;align-items:baseline;gap:8px;margin-top:4px">'
            f'<span style="font-size:30px;font-weight:850;color:#0f172a;line-height:1.1">{format_count(group["count"])}</span>'
            f'<span style="font-size:15px;font-weight:700;color:#475569">{html_text(pct(group["share"]))}</span></div>'
            f"{detail_html}</div>"
        )
    return f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin:4px 0 6px">{"".join(cards)}</div>'


def render_order_status_section(metrics: dict) -> None:
    """Purely additive: reads the existing metrics, changes none of them."""
    try:
        split = order_status_split(metrics)
        st.markdown(
            '<div class="section-tight">Où sont mes commandes</div>'
            f'<div class="section-subtitle">Les {format_count(split["received"])} commandes reçues de la période, selon où elles en sont aujourd\'hui.</div>',
            unsafe_allow_html=True,
        )
        if split["received"]:
            st.markdown(order_status_cards_html(split), unsafe_allow_html=True)
        else:
            st.info("Aucune commande sur le périmètre.")
    except Exception as exc:  # never let the new section break the existing dashboard
        st.warning(f"Section indisponible pour ce fichier : {exc}")
