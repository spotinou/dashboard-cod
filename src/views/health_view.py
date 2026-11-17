"""Business health at a glance: vital rates vs objectives, and orders stuck too long."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..health import BAD, GOOD, WARN, health_summary, reference_date, stuck_orders, vital_signs
from .formatting import format_count, format_date, html_text, pct

VERDICT_STYLE = {
    GOOD: ("\U0001f7e2 Bon", "#16a34a", "#dcfce7", "#166534"),
    WARN: ("\U0001f7e0 À surveiller", "#f59e0b", "#fef3c7", "#92400e"),
    BAD: ("\U0001f534 Problème", "#dc2626", "#fee2e2", "#991b1b"),
    "neutral": ("— Pas de données", "#94a3b8", "#e2e8f0", "#334155"),
}


def overall_text(summary: dict) -> str:
    counts = summary["counts"]
    if summary["overall"] == GOOD:
        return "\U0001f7e2 Tout va bien : tous tes taux atteignent leur objectif."
    parts = []
    if counts[BAD]:
        parts.append(f"{counts[BAD]} problème{'s' if counts[BAD] > 1 else ''}")
    if counts[WARN]:
        parts.append(f"{counts[WARN]} point{'s' if counts[WARN] > 1 else ''} à surveiller")
    icon = "\U0001f534" if counts[BAD] else "\U0001f7e0"
    return f"{icon} {' et '.join(parts)} : " + ", ".join(s["label"] for s in summary["to_watch"]) + "."


def vital_sign_html(sign: dict) -> str:
    """One rate as a gauge 0-100 % with a black tick at the objective."""
    label, fill, pill_bg, pill_fg = VERDICT_STYLE.get(sign["verdict"], VERDICT_STYLE["neutral"])
    value = sign["value"]
    width = 0.0 if value is None or pd.isna(value) else max(min(float(value), 1.0), 0.0) * 100
    objective = sign["objective"] * 100
    sign_text = "≥" if sign["higher_is_better"] else "≤"
    sentence = sign["explanation"].format(n=f"{round(value * 100)}" if value is not None and not pd.isna(value) else "—")
    return (
        '<div style="flex:1;min-width:220px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;padding:12px 14px">'
        '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">'
        f'<span style="font-size:14px;font-weight:800;color:#0f172a">{html_text(sign["label"])}</span>'
        f'<span style="background:{pill_bg};color:{pill_fg};border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:800;white-space:nowrap">{label}</span></div>'
        f'<div style="font-size:28px;font-weight:850;color:#0f172a;margin-top:4px;line-height:1.1">{html_text(pct(value))}</div>'
        f'<div style="font-size:12.5px;color:#475569;margin-top:2px">{html_text(sentence)}</div>'
        '<div style="position:relative;height:10px;background:#eef2f7;border-radius:5px;margin:14px 0 4px">'
        f'<div style="width:{width:.1f}%;height:10px;background:{fill};border-radius:5px"></div>'
        f'<div style="position:absolute;left:{objective:.1f}%;top:-5px;width:2px;height:20px;background:#0f172a"></div></div>'
        f'<div style="position:relative;height:16px;font-size:11px;color:#0f172a;font-weight:700">'
        f'<span style="position:absolute;left:{objective:.1f}%;transform:translateX(-50%);white-space:nowrap">objectif {sign_text} {html_text(pct(sign["objective"]))}</span></div>'
        "</div>"
    )


def render_health_section(metrics: dict, thresholds: dict[str, float]) -> None:
    try:
        signs = vital_signs(metrics, thresholds)
        summary = health_summary(signs)
        st.markdown(
            '<div class="section-tight">\U0001fa7a Santé de mon business</div>'
            '<div class="section-subtitle">Tes 4 taux vitaux. Le trait noir = ton objectif (réglable dans la barre latérale, rubrique Seuils).</div>'
            f'<div style="font-size:15px;font-weight:800;color:#0f172a;margin:2px 0 8px">{html_text(overall_text(summary))}</div>'
            f'<div style="display:flex;gap:12px;flex-wrap:wrap">{"".join(vital_sign_html(s) for s in signs)}</div>',
            unsafe_allow_html=True,
        )
    except Exception as exc:  # never let the new section break the dashboard
        st.warning(f"Section santé indisponible pour ce fichier : {exc}")


STEP_ICONS = {"confirmation": "\U0001f4de", "preparation": "\U0001f4e6", "delivery": "\U0001f69a"}


def stuck_card_html(step: dict) -> str:
    late = step["late"]
    border, background = ("#dc2626", "#fff1f2") if late else ("#16a34a", "#f0fdf4")
    owners = " · ".join(f"{format_count(count)} {html_text(name)}" for name, count in step["owners"])
    owners_html = f'<div style="font-size:12.5px;color:#334155;margin-top:4px">dont {owners}</div>' if owners and late else ""
    status = (
        f'<span style="font-size:30px;font-weight:850;color:#0f172a;line-height:1.1">{format_count(late)}</span>'
        f'<span style="font-size:13px;color:#475569"> bloquée{"s" if late > 1 else ""} depuis plus de {step["limit_days"]} jours</span>'
        if late
        else '<span style="font-size:16px;font-weight:800;color:#166534">✔ Rien de bloqué</span>'
    )
    return (
        f'<div style="flex:1;min-width:220px;border:1px solid #e2e8f0;border-left:5px solid {border};background:{background};border-radius:8px;padding:12px 14px">'
        f'<div style="font-size:14px;font-weight:800;color:#0f172a">{STEP_ICONS.get(step["key"], "")} {html_text(step["title"])}</div>'
        f'<div style="margin-top:4px">{status}</div>'
        f'<div style="font-size:12px;color:#64748b;margin-top:2px">{format_count(step["waiting"])} en attente au total</div>'
        f"{owners_html}</div>"
    )


def stuck_orders_table(steps: list[dict]) -> pd.DataFrame:
    frames = []
    for step in steps:
        late = step["late_orders"]
        if late.empty:
            continue
        cols = [c for c in ["Référence commande", "Statut commande", "jours", "Affectée à", "Livreur", "Wilaya", "Nom produit"] if c in late.columns]
        part = late[cols].copy()
        part.insert(0, "Étape", step["title"])
        frames.append(part)
    if not frames:
        return pd.DataFrame()
    table = pd.concat(frames, ignore_index=True)
    return table.rename(columns={"jours": "Bloquée depuis (jours)", "Affectée à": "Confirmatrice", "Nom produit": "Produit", "Référence commande": "Commande", "Statut commande": "Statut"})


def render_stuck_orders_section(df: pd.DataFrame, loaded_df: pd.DataFrame) -> None:
    try:
        today = reference_date(loaded_df)
        if today is None:
            return
        steps = stuck_orders(df, today)
        if not steps:
            return
        st.markdown(
            '<div class="section-tight">\U0001f6a8 À traiter aujourd\'hui</div>'
            f'<div class="section-subtitle">Commandes qui attendent trop longtemps à une étape, au {format_date(today)} (dernière date du fichier).</div>'
            f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:6px">{"".join(stuck_card_html(s) for s in steps)}</div>',
            unsafe_allow_html=True,
        )
        table = stuck_orders_table(steps)
        if not table.empty:
            with st.expander(f"Voir les {format_count(len(table))} commandes bloquées", expanded=False):
                st.dataframe(table, hide_index=True, width="stretch")
    except Exception as exc:  # never let the new section break the dashboard
        st.warning(f"Section « à traiter » indisponible pour ce fichier : {exc}")
