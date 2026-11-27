"""Products tab: compare every product on confirmation and delivery, with one funnel per product.

Rates use the same rules as the cockpit cards:
- Taux confirmé = card_confirmation_rate (reçues - en confirmation - annulées) / reçues
- Livraison = livrées / expédiées
- Taux réel = livrées / reçues (transformation brute)
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..trends import card_confirmation_rate
from .components import cockpit_heading, render_data_table, render_section_kpis, selected_index, show_drilldown, tab_header
from .formatting import format_count, html_text, is_known_value, money, pct, safe_ratio, tone_class

TONE_TEXT = {"good": "#15803d", "warn": "#b45309", "bad": "#b91c1c", "neutral": "#334155"}
TONE_BG = {"good": "#dcfce7", "warn": "#fef3c7", "bad": "#fee2e2", "neutral": "#f1f5f9"}

VERDICT_GOOD = "✅ Bon partout"
VERDICT_WATCH = "🟠 Correct, à surveiller"
VERDICT_CONFIRM = "📞 Confirme mal"
VERDICT_DELIVERY = "🚚 Se livre mal"
VERDICT_BAD = "❌ Mauvais partout"
VERDICT_LOW = "🔍 Pas assez de commandes"
VERDICT_WAIT = "⏳ Pas encore livré"
VERDICT_TONE = {
    VERDICT_GOOD: "good", VERDICT_WATCH: "warn", VERDICT_CONFIRM: "bad", VERDICT_DELIVERY: "bad",
    VERDICT_BAD: "bad", VERDICT_LOW: "neutral", VERDICT_WAIT: "neutral",
}

COMPARISON_LABELS = {
    "produit": "Produit",
    "verdict": "Verdict",
    "commandes_recues": "Reçues",
    "taux_confirme": "Taux confirmé",
    "taux_annulation": "Taux annulé",
    "taux_livraison_total": "Livraison",
    "taux_transformation_reel": "Taux réel",
    "en_cours_logistique": "En route",
    "ca_en_cours_logistique": "Argent en route",
}


def _num(row, col: str) -> float:
    value = pd.to_numeric(pd.Series([row.get(col, 0)]), errors="coerce").fillna(0).iloc[0]
    return float(value)


def product_metrics_dict(row) -> dict:
    """Translate one product row into the keys used by the global helpers (funnel, card rates)."""
    return {
        "orders_received": int(_num(row, "commandes_recues")),
        "orders_confirmed_net": int(_num(row, "commandes_confirmees_nettes")),
        "orders_in_confirmation": int(_num(row, "en_confirmation")),
        "orders_unclassified": int(_num(row, "commandes_non_classees")),
        "orders_cancelled": int(_num(row, "commandes_annulees")),
        "orders_sent": int(_num(row, "commandes_envoyees")),
        "orders_delivered": int(_num(row, "livrees")),
        "orders_returned_failed": int(_num(row, "retours")),
        "orders_logistics": int(_num(row, "en_cours_logistique")),
    }


def product_verdict(confirmation: float | None, delivery: float | None, received: int, volume_min: int, thresholds: dict) -> str:
    """One plain verdict: does the product confirm well, deliver well, both or neither?"""
    if received < volume_min:
        return VERDICT_LOW
    if delivery is None or pd.isna(delivery):
        return VERDICT_WAIT
    conf_tone = tone_class(confirmation, "confirmation", thresholds)
    deliv_tone = tone_class(delivery, "delivery", thresholds)
    conf_bad, deliv_bad = conf_tone == "bad", deliv_tone == "bad"
    if conf_bad and deliv_bad:
        return VERDICT_BAD
    if conf_bad:
        return VERDICT_CONFIRM
    if deliv_bad:
        return VERDICT_DELIVERY
    if conf_tone == "good" and deliv_tone == "good":
        return VERDICT_GOOD
    return VERDICT_WATCH


def product_comparison(products: pd.DataFrame, volume_min: int, thresholds: dict) -> pd.DataFrame:
    """One row per known product with the KPIs chosen for the comparison table."""
    columns = list(COMPARISON_LABELS)
    if products.empty or "produit" not in products.columns:
        return pd.DataFrame(columns=columns)
    rows = products[products["produit"].apply(is_known_value)].copy()
    if rows.empty:
        return pd.DataFrame(columns=columns)
    rows["taux_confirme"] = rows.apply(lambda r: card_confirmation_rate(product_metrics_dict(r)), axis=1)
    rows["verdict"] = rows.apply(
        lambda r: product_verdict(r["taux_confirme"], r.get("taux_livraison_total"), int(_num(r, "commandes_recues")), volume_min, thresholds),
        axis=1,
    )
    for col in columns:
        if col not in rows.columns:
            rows[col] = None
    return rows[columns].sort_values("commandes_recues", ascending=False).reset_index(drop=True)


def product_funnel_steps(row) -> list[dict]:
    """Reçues → Confirmées → Expédiées → Livrées for one product, with % of received and % of previous step."""
    metrics = product_metrics_dict(row)
    received = metrics["orders_received"]
    # Same count as the "Taux confirmé" card: received minus cancelled minus still in confirmation.
    confirmed = max(received - metrics["orders_in_confirmation"] - metrics["orders_cancelled"], 0)
    values = [received, confirmed, metrics["orders_sent"], metrics["orders_delivered"]]
    labels = ["Reçues", "Confirmées", "Expédiées", "Livrées"]
    steps = []
    for index, (label, value) in enumerate(zip(labels, values)):
        steps.append({
            "label": label,
            "value": value,
            "share_of_received": safe_ratio(value, received),
            "step_rate": safe_ratio(value, values[index - 1]) if index else None,
        })
    return steps


def comparison_summary(comparison: pd.DataFrame) -> list[str]:
    """Three short sentences: who confirms worst, who delivers worst, who is the best product."""
    reliable = comparison[~comparison["verdict"].isin([VERDICT_LOW, VERDICT_WAIT])]
    if reliable.empty:
        return ["Aucun produit n'a encore assez de commandes pour une comparaison fiable."]
    bullets = []
    best = reliable.dropna(subset=["taux_transformation_reel"]).sort_values("taux_transformation_reel", ascending=False)
    if not best.empty:
        row = best.iloc[0]
        bullets.append(f"🏆 Meilleur produit : **{row['produit']}**, sur 100 commandes reçues, {round(row['taux_transformation_reel'] * 100)} finissent livrées.")
    confirm = reliable.dropna(subset=["taux_confirme"]).sort_values("taux_confirme")
    if len(confirm) > 1:
        row = confirm.iloc[0]
        bullets.append(f"📞 Confirme le moins bien : **{row['produit']}** ({pct(row['taux_confirme'])} confirmées). Piste : qualité des leads (pub, page produit, prix).")
    delivery = reliable.dropna(subset=["taux_livraison_total"]).sort_values("taux_livraison_total")
    if len(delivery) > 1:
        row = delivery.iloc[0]
        bullets.append(f"🚚 Se livre le moins bien : **{row['produit']}** ({pct(row['taux_livraison_total'])} des colis livrés). Piste : promesse produit, délai, refus à la porte.")
    return bullets


# ---------------------------------------------------------------------------
# Rendering


def _rate_style(value, kind: str, thresholds: dict) -> str:
    tone = tone_class(value, kind, thresholds)
    if tone == "neutral":
        return ""
    return f"background-color: {TONE_BG[tone]}; color: {TONE_TEXT[tone]}; font-weight: 700"


def style_comparison(comparison: pd.DataFrame, thresholds: dict):
    raw = comparison.reset_index(drop=True)
    display = pd.DataFrame({
        "produit": raw["produit"].astype(str),
        "verdict": raw["verdict"],
        "commandes_recues": raw["commandes_recues"].map(lambda v: format_count(v or 0)),
        "taux_confirme": raw["taux_confirme"].map(pct),
        "taux_annulation": raw["taux_annulation"].map(pct),
        "taux_livraison_total": raw["taux_livraison_total"].map(pct),
        "taux_transformation_reel": raw["taux_transformation_reel"].map(pct),
        "en_cours_logistique": raw["en_cours_logistique"].map(lambda v: format_count(v or 0)),
        "ca_en_cours_logistique": raw["ca_en_cours_logistique"].map(money),
    })
    kinds = {
        "taux_confirme": "confirmation",
        "taux_annulation": "cancellation",
        "taux_livraison_total": "delivery",
        "taux_transformation_reel": "transformation",
    }

    def style_column(series: pd.Series) -> list[str]:
        col = label_to_key[series.name]
        if col in kinds:
            return [_rate_style(raw.at[i, col], kinds[col], thresholds) for i in series.index]
        if col == "verdict":
            return [f"color: {TONE_TEXT[VERDICT_TONE.get(v, 'neutral')]}; font-weight: 700" for v in raw["verdict"]]
        if col == "produit":
            return ["font-weight: 700" for _ in series.index]
        return ["" for _ in series.index]

    # Streamlit shows the DataFrame's own column names, so label them before styling.
    label_to_key = {COMPARISON_LABELS[c]: c for c in display.columns}
    display = display.rename(columns=COMPARISON_LABELS)
    styled = display.style.apply(style_column, axis=0)
    numeric = [label for label, key in label_to_key.items() if key not in {"produit", "verdict"}]
    return styled.set_properties(subset=numeric, **{"text-align": "right"})


def render_product_kpis(metrics: dict, thresholds: dict) -> None:
    confirmation = card_confirmation_rate(metrics)
    cancellation = metrics.get("cancellation_rate")
    delivery = metrics.get("delivery_total_rate_on_sent")
    real = metrics.get("transformation_real_rate")
    logistics = int(metrics.get("orders_logistics", 0) or 0)

    def per_100(value) -> str:
        return "—" if value is None else str(round(value * 100))

    render_section_kpis([
        ("Taux confirmé", pct(confirmation), f"Sur 100 reçues, {per_100(confirmation)} confirmées", tone_class(confirmation, "confirmation", thresholds)),
        ("Taux annulé", pct(cancellation), f"{format_count(metrics.get('orders_cancelled', 0) or 0)} commandes annulées", tone_class(cancellation, "cancellation", thresholds)),
        ("Livraison (sur expédiées)", pct(delivery), f"Sur 100 colis expédiés, {per_100(delivery)} livrés", tone_class(delivery, "delivery", thresholds)),
        ("Taux réel (sur reçues)", pct(real), f"Sur 100 reçues, {per_100(real)} livrées", tone_class(real, "transformation", thresholds)),
        ("Colis en route", format_count(logistics), f"{money(metrics.get('ca_logistics', 0))} en attente", "info"),
    ])


def _funnel_card_html(name: str, verdict: str, steps: list[dict]) -> str:
    colors = ["#94a3b8", "#3b82f6", "#6366f1", "#16a34a"]
    bars = []
    for step, color in zip(steps, colors):
        share = step["share_of_received"] or 0
        width = max(share * 100, 2 if step["value"] else 0)
        step_note = f"<span style='color:#64748b'> · {pct(step['step_rate'])} de l'étape d'avant</span>" if step["step_rate"] is not None else ""
        bars.append(
            f"""<div style="margin:6px 0">
              <div style="font-size:11.5px;color:#334155;display:flex;justify-content:space-between;gap:6px">
                <span><b>{html_text(step['label'])}</b> {format_count(step['value'])}</span><span><b>{pct(share)}</b></span>
              </div>
              <div style="background:#f1f5f9;border-radius:4px;height:12px;margin-top:2px">
                <div style="width:{width:.1f}%;background:{color};height:12px;border-radius:4px"></div>
              </div>
              <div style="font-size:10.5px;line-height:1.3">{step_note}</div>
            </div>"""
        )
    tone = VERDICT_TONE.get(verdict, "neutral")
    return f"""<div style="border:1px solid #d7dee8;border-radius:8px;background:#fff;padding:10px 12px;margin-bottom:10px">
      <div style="font-size:14px;font-weight:850;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{html_text(name)}">{html_text(name)}</div>
      <div style="display:inline-block;margin-top:3px;font-size:11px;font-weight:800;padding:1px 8px;border-radius:999px;background:{TONE_BG[tone]};color:{TONE_TEXT[tone]}">{html_text(verdict)}</div>
      {''.join(bars)}
    </div>"""


def render_product_funnels(products: pd.DataFrame, comparison: pd.DataFrame, per_row: int = 4, limit: int = 12) -> None:
    if comparison.empty:
        st.info("Aucun produit avec les filtres actuels.")
        return
    by_name = products.set_index("produit")
    names = comparison["produit"].tolist()[:limit]
    verdicts = dict(zip(comparison["produit"], comparison["verdict"]))
    for start in range(0, len(names), per_row):
        cols = st.columns(per_row)
        for col, name in zip(cols, names[start:start + per_row]):
            row = by_name.loc[name]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            with col:
                st.markdown(_funnel_card_html(name, verdicts.get(name, ""), product_funnel_steps(row)), unsafe_allow_html=True)
    if len(comparison) > limit:
        st.caption(f"{limit} produits affichés sur {len(comparison)} (ceux qui reçoivent le plus de commandes). Utilise le filtre Produit pour voir les autres.")


DETAIL_VIEWS = {
    "📍 Par wilaya": ("product_wilaya_detail", "wilaya", ["produit", "wilaya", "fiabilite_volume", "commandes_recues", "taux_confirmation", "commandes_envoyees", "livrees", "taux_livraison_total", "taux_transformation_reel", "en_cours_logistique", "retours", "taux_retour", "livreur_dominant"], ["produit", "commandes_envoyees"]),
    "🚚 Par livreur": ("product_livreur_detail", "livreur", ["produit", "livreur", "fiabilite_volume", "commandes_envoyees", "livrees", "taux_livraison_total", "en_cours_logistique", "retours", "taux_retour"], ["produit", "commandes_envoyees"]),
    "📣 Par source": ("source_product_detail", "source", ["produit", "source", "fiabilite_volume", "commandes_recues", "taux_confirmation", "commandes_envoyees", "livrees", "taux_transformation_reel", "en_cours_logistique", "taux_retour"], ["produit", "commandes_recues"]),
    "🏷️ Par SKU": ("sku_product_detail", "sku_produit", ["produit", "sku_produit", "fiabilite_volume", "commandes_recues", "taux_confirmation", "commandes_envoyees", "livrees", "taux_transformation_reel", "en_cours_logistique", "taux_retour"], ["produit", "commandes_recues"]),
    "📋 Tout le détail": ("products_advice", None, None, ["commandes_recues"]),
}


def render_detail_explorer(ctx: dict, product_names: list[str]) -> None:
    thresholds = ctx["thresholds"]
    with st.expander("🔎 Analyse détaillée (wilaya, livreur, source, SKU)", expanded=False):
        st.caption("Choisis un angle, et éventuellement un produit, pour voir où un produit marche bien ou mal.")
        col_view, col_product = st.columns([3, 2])
        with col_view:
            choice = st.radio("Angle d'analyse", list(DETAIL_VIEWS), horizontal=True, key="product_detail_view", label_visibility="collapsed")
        with col_product:
            product = st.selectbox("Produit", ["Tous les produits", *product_names], key="product_detail_product", label_visibility="collapsed")
        ctx_key, _dimension, columns, sort_by = DETAIL_VIEWS[choice]
        table = ctx.get(ctx_key)
        if table is None or not isinstance(table, pd.DataFrame) or table.empty:
            st.info("Aucune donnée disponible pour cet angle (colonne absente du fichier ou filtres trop serrés).")
            return
        if product != "Tous les produits" and "produit" in table.columns:
            table = table[table["produit"].astype(str) == product]
        render_data_table(table, columns or list(table.columns), thresholds, "Aucune donnée pour ce produit avec les filtres actuels.", sort_by=sort_by)
        if "taux_confirmation" in (columns or []):
            st.caption("Ici « Taux non annulé » = commandes ni annulées ni perdues ÷ reçues (inclut celles encore en confirmation).")


def render_products_tab_v2(ctx: dict) -> None:
    df = ctx["df"]
    products = ctx["products_ui"]
    thresholds = ctx["thresholds"]
    volume_product = int(ctx["volume_product"])
    tab_header("Produits", "Mes produits se confirment-ils bien ? Se livrent-ils bien ? Lequel marche le mieux ?")

    render_product_kpis(ctx["global_metrics"], thresholds)

    comparison = product_comparison(products, volume_product, thresholds)
    cockpit_heading(
        "Comparaison de mes produits",
        f"Vert = objectif atteint · orange = à surveiller · rouge = problème. Verdict calculé dès {volume_product} commandes reçues. Clique une ligne pour voir ses commandes retournées.",
    )
    if comparison.empty:
        st.info("Aucun produit disponible avec les filtres actuels.")
        return
    event = st.dataframe(
        style_comparison(comparison, thresholds), width="stretch", hide_index=True,
        height=min(38 + 35 * len(comparison), 460), on_select="rerun", selection_mode="single-row", key="product_comparison_table",
    )
    for bullet in comparison_summary(comparison):
        st.markdown(f"- {bullet}")
    idx = selected_index(event)
    if idx is not None and idx < len(comparison):
        show_drilldown(df, "produit", "Nom produit", comparison.iloc[idx]["produit"], "Retours / echecs", "produit")

    cockpit_heading(
        "Entonnoir par produit",
        "Sur toutes les commandes reçues d'un produit : combien sont confirmées, expédiées, puis livrées. La barre qui chute montre l'étape qui pose problème.",
    )
    render_product_funnels(products, comparison)

    render_detail_explorer(ctx, comparison["produit"].tolist())
