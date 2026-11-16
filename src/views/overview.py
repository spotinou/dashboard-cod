"""KPI cards of the global view (COD journey and money)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .formatting import html_text, money, pct, safe_ratio, tone_class, top_known
from .components import cockpit_heading, hero_card, mini_card, render_data_table, render_kpi_stack, render_priority_focus, render_section_kpis, render_stage_kpis
from .analysis import amount_totals


def render_funnel_compact(metrics: dict) -> None:
    cockpit_heading("Funnel COD", "Les sous-textes montrent imm\u00e9diatement la perte ou le blocage entre deux \u00e9tapes.")
    received = int(metrics["orders_received"])
    confirmed = int(metrics["orders_confirmed_net"])
    sent = int(metrics["orders_sent"])
    delivered = int(metrics["orders_delivered"])
    leaks = [
        ("annulations", int(metrics["orders_cancelled"]), 0.0),
        ("non exp\u00e9di\u00e9es", int(metrics["orders_preparation"]), float(metrics.get("ca_preparation", 0))),
        ("retours / \u00e9checs", int(metrics["orders_returned_failed"]), float(metrics.get("ca_returned_failed", 0))),
    ]
    leak_name, leak_count, leak_amount = max(leaks, key=lambda item: item[1])
    amount_text = f", {money(leak_amount)}" if leak_amount else ""
    st.markdown(
        f'<div class="leak-banner"><b>Fuite principale :</b> {html_text(leak_name)} - {leak_count} commandes{html_text(amount_text)}</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns([1, 0.12, 1, 0.12, 1, 0.12, 1])
    funnel_items = [
        ("Commandes re\u00e7ues", received, "Base p\u00e9riode", "neutral"),
        ("Confirm\u00e9es nettes", confirmed, f"{pct(metrics['confirmation_rate'])} des re\u00e7ues - Perte : {int(metrics['orders_cancelled'])} annul\u00e9es", "info"),
        ("Exp\u00e9di\u00e9es", sent, f"{pct(metrics['shipping_rate_global'])} des confirm\u00e9es - Blocage : {int(metrics['orders_preparation'])} non exp\u00e9di\u00e9es", "warn"),
        ("Livr\u00e9es finalis\u00e9es", delivered, f"{pct(metrics['delivery_total_rate_on_sent'])} des exp\u00e9di\u00e9es - Transformation : {pct(metrics['transformation_real_rate'])}", "good"),
    ]
    for i, (title, value, note, tone) in enumerate(funnel_items):
        with cols[i * 2]:
            mini_card(title, str(value), note, tone=tone)
        if i < 3:
            with cols[i * 2 + 1]:
                st.markdown('<div class="funnel-arrow">&rarr;</div>', unsafe_allow_html=True)


def render_secondary_kpis(metrics: dict, thresholds: dict[str, float]) -> None:
    with st.expander("Voir d\u00e9tails op\u00e9rationnels", expanded=False):
        groups = [
            (
                "Commandes",
                [
                    ("Confirm\u00e9es nettes", metrics["orders_confirmed_net"], "Hors annulations"),
                    ("Taux confirmation", pct(metrics["confirmation_rate"]), "Confirm\u00e9es / re\u00e7ues"),
                    ("Annul\u00e9es avant exp\u00e9dition", metrics["orders_cancelled"], "Sorties avant exp\u00e9dition"),
                    ("Taux annulation", pct(metrics["cancellation_rate"]), "Annul\u00e9es / re\u00e7ues"),
                ],
            ),
            (
                "Exp\u00e9dition / livraison",
                [
                    ("Confirm\u00e9es non exp\u00e9di\u00e9es", metrics["orders_preparation"], "Blocage interne"),
                    ("Exp\u00e9di\u00e9es", metrics["orders_sent"], "Chez livreur"),
                    ("Taux exp\u00e9dition", pct(metrics["shipping_rate_global"]), "Exp\u00e9di\u00e9es / confirm\u00e9es"),
                    ("En dispatch", metrics.get("orders_dispatch", 0), "Expediees non finalisees"),
                    ("En cours livraison", metrics["orders_in_delivery"], "CA pas encore s\u00e9curis\u00e9"),
                    ("Taux en cours livraison", pct(metrics["in_delivery_rate_on_sent"]), "En cours / exp\u00e9di\u00e9es"),
                    ("Livr\u00e9es finalis\u00e9es", metrics["orders_delivered"], "Livr\u00e9es ou encaiss\u00e9es"),
                    ("Taux livraison sur exp\u00e9di\u00e9es", pct(metrics["delivery_total_rate_on_sent"]), "Livr\u00e9es / exp\u00e9di\u00e9es"),
                    ("Retours / \u00e9checs", metrics["orders_returned_failed"], "Perte apr\u00e8s exp\u00e9dition"),
                    ("Taux retour", pct(metrics["return_rate_on_sent"]), "Retours / exp\u00e9di\u00e9es"),
                ],
            ),
            (
                "Argent",
                [
                    ("CA livr\u00e9 finalis\u00e9", money(metrics["ca_delivered"]), "Argent s\u00e9curis\u00e9"),
                    ("CA en dispatch", money(metrics.get("ca_dispatch", 0)), "Expedie non finalise"),
                    ("CA en cours livraison", money(metrics["ca_in_delivery"]), "Encore \u00e0 transformer"),
                    ("CA confirm\u00e9 non exp\u00e9di\u00e9", money(metrics["ca_preparation"]), "Blocage pr\u00e9paration"),
                    ("Perte CA retours", money(metrics["ca_returned_failed"]), "Perdu apr\u00e8s exp\u00e9dition"),
                ],
            ),
        ]
        for title, items in groups:
            st.markdown(f'<div class="detail-title">{html_text(title)}</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for index, (label, value, note) in enumerate(items):
                with cols[index % 4]:
                    mini_card(label, str(value), note, tone="detail")


def owner_money_sections(metrics: dict, amounts: dict[str, float | None]) -> list[tuple[str, str, str, str]]:
    total_ca = float(amounts.get("ca_total_orders", 0) or 0)

    def note(count: int, amount: float, label: str = "commandes") -> str:
        share = safe_ratio(amount, total_ca)
        return f"{count} {label} \u00b7 {pct(share)} du CA re\u00e7u" if share is not None else f"{count} {label}"

    delivered = int(metrics.get("orders_delivered", 0) or 0)
    return [
        ("CA total des commandes re\u00e7ues", money(total_ca), f"{int(metrics.get('orders_received', 0) or 0)} commandes re\u00e7ues", "neutral"),
        ("CA confirm\u00e9", money(amounts.get("ca_confirmed")), note(int(metrics.get("orders_confirmed_net", 0) or 0), float(amounts.get("ca_confirmed", 0) or 0)), "info"),
        ("CA en pr\u00e9paration", money(metrics.get("ca_preparation")), note(int(metrics.get("orders_preparation", 0) or 0), float(metrics.get("ca_preparation", 0) or 0)), "warn"),
        ("CA en dispatch", money(metrics.get("ca_dispatch")), note(int(metrics.get("orders_dispatch", 0) or 0), float(metrics.get("ca_dispatch", 0) or 0)), "warn"),
        ("CA en cours de livraison", money(metrics.get("ca_in_delivery")), note(int(metrics.get("orders_in_delivery", 0) or 0), float(metrics.get("ca_in_delivery", 0) or 0)), "warn"),
        ("CA livr\u00e9 finalis\u00e9", money(metrics.get("ca_delivered")), note(delivered, float(metrics.get("ca_delivered", 0) or 0)), "good"),
        ("Perte CA retours", money(metrics.get("ca_returned_failed")), note(int(metrics.get("orders_returned_failed", 0) or 0), float(metrics.get("ca_returned_failed", 0) or 0)), "loss"),
        ("Panier moyen livr\u00e9", money(amounts.get("panier_moyen_livre")), f"{delivered} commandes livr\u00e9es finalis\u00e9es", "neutral"),
    ]


def confirmation_funnel_counts(metrics: dict) -> tuple[int, float | None, float | None]:
    """Return the exclusive confirmed stage used by the visual COD funnel."""
    received = int(metrics.get("orders_received", 0) or 0)
    confirmed_net = int(metrics.get("orders_confirmed_net", 0) or 0)
    in_confirmation = int(metrics.get("orders_in_confirmation", 0) or 0)
    unclassified = int(metrics.get("orders_unclassified", 0) or 0)
    confirmed = max(confirmed_net - in_confirmation - unclassified, 0)
    return confirmed, safe_ratio(confirmed, received), safe_ratio(int(metrics.get("orders_preparation", 0) or 0), confirmed)


def displayed_reception_rates(metrics: dict, confirmation_rate: float | None) -> tuple[float | None, float | None, float | None]:
    """Keep the three exclusive reception outcomes at exactly 100.0% on cards."""
    received = int(metrics.get("orders_received", 0) or 0)
    if received == 0:
        return None, None, None
    in_confirmation_rate = safe_ratio(int(metrics.get("orders_in_confirmation", 0) or 0), received)
    cancellation_rate = safe_ratio(int(metrics.get("orders_cancelled", 0) or 0), received)
    pending_tenths = round((in_confirmation_rate or 0) * 1000)
    cancelled_tenths = round((cancellation_rate or 0) * 1000)
    confirmed_display_rate = max(0, 1000 - pending_tenths - cancelled_tenths) / 1000
    return confirmed_display_rate, in_confirmation_rate, cancellation_rate


def owner_kpi_sections(metrics: dict, thresholds: dict[str, float]) -> list[tuple[str, str, str, str]]:
    received = int(metrics.get("orders_received", 0) or 0)
    confirmed, confirmation_rate, preparation_rate = confirmation_funnel_counts(metrics)
    confirmation_display_rate, in_confirmation_rate, cancellation_display_rate = displayed_reception_rates(metrics, confirmation_rate)
    in_confirmation = int(metrics.get("orders_in_confirmation", 0) or 0)
    preparation = int(metrics.get("orders_preparation", 0) or 0)
    sent = int(metrics.get("orders_sent", 0) or 0)
    dispatch = int(metrics.get("orders_dispatch", 0) or 0)
    in_delivery = int(metrics.get("orders_in_delivery", 0) or 0)
    delivered = int(metrics.get("orders_delivered", 0) or 0)
    cancelled = int(metrics.get("orders_cancelled", 0) or 0)

    dispatch_rate = safe_ratio(dispatch, sent)
    in_delivery_rate = safe_ratio(in_delivery, sent)

    return [
        ("Commandes reçues", str(received), "Base de la période", "neutral"),
        ("Taux confirmé", pct(confirmation_display_rate), f"{confirmed} commandes confirmées\nBase : {received} reçues", tone_class(confirmation_rate, "confirmation", thresholds)),
        ("Taux en cours de confirmation", pct(in_confirmation_rate), f"{in_confirmation} commandes en confirmation\nBase : {received} reçues", tone_class(in_confirmation_rate, "preparation", thresholds)),
        ("Taux en préparation", pct(preparation_rate), f"{preparation} commandes en préparation\nBase : {confirmed} confirmées", tone_class(preparation_rate, "preparation", thresholds)),
        ("Taux en dispatch", pct(dispatch_rate), f"{dispatch} commandes en dispatch\nBase : {sent} expédiées", "warn" if dispatch else "good"),
        ("Taux en cours de livraison", pct(in_delivery_rate), f"{in_delivery} commandes en livraison\nBase : {sent} expédiées", "warn" if in_delivery else "good"),
        ("Taux livré", pct(metrics.get("delivery_total_rate_on_sent")), f"{delivered} commandes livrées\nBase : {sent} expédiées", tone_class(metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
        ("Taux de transformation brute", pct(metrics.get("transformation_real_rate")), f"{delivered} livrées / {received} reçues", tone_class(metrics.get("transformation_real_rate"), "transformation", thresholds)),
        ("Taux annulé", pct(cancellation_display_rate), f"{cancelled} commandes annulées\nBase : {received} reçues", tone_class(metrics.get("cancellation_rate"), "cancellation", thresholds)),
    ]


def owner_priority(metrics: dict) -> tuple[str, int, float]:
    priorities = [
        ("commandes non envoy\u00e9es", int(metrics.get("orders_preparation", 0) or 0), float(metrics.get("ca_preparation", 0) or 0)),
        ("commandes en cours logistique", int(metrics.get("orders_logistics", 0) or 0), float(metrics.get("ca_logistics", 0) or 0)),
        ("retours / \u00e9checs", int(metrics.get("orders_returned_failed", 0) or 0), float(metrics.get("ca_returned_failed", 0) or 0)),
    ]
    return max(priorities, key=lambda item: item[1])


def render_owner_global_dashboard(
    df: pd.DataFrame,
    metrics: dict,
    thresholds: dict[str, float],
    priority_actions: pd.DataFrame | None = None,
) -> None:
    cockpit_heading(
        "Parcours COD",
        "Réception : confirmées + en cours de confirmation + annulées = 100,0 %. Les étapes suivantes utilisent leur base affichée.",
    )
    journey = owner_kpi_sections(metrics, thresholds)
    render_stage_kpis("1. Reception", "Ce qui entre dans le funnel et ce qui en sort avant expedition.", journey[:4])
    render_stage_kpis("2. Execution", "Les commandes confirmees progressent vers une livraison finalisee.", journey[4:8])
    render_stage_kpis("3. Resultat", "La transformation brute replace la livraison dans le volume recu.", journey[8:])
    cockpit_heading(
        "Argent / Chiffre d'affaires",
        "CA potentiel, bloqu\u00e9, s\u00e9curis\u00e9 ou perdu sur le p\u00e9rim\u00e8tre actif.",
    )
    render_section_kpis(owner_money_sections(metrics, amount_totals(df, metrics)), max_per_row=4)
    if priority_actions is not None:
        render_priority_focus(priority_actions)


def render_global_business_kpis(metrics: dict, thresholds: dict[str, float]) -> None:
    dispatch = int(metrics.get("orders_dispatch", 0) or 0)
    in_delivery = int(metrics.get("orders_in_delivery", 0) or 0)
    logistics = int(metrics.get("orders_logistics", dispatch + in_delivery) or 0)
    risk_orders = int(metrics["orders_preparation"] + dispatch + in_delivery + metrics["orders_returned_failed"])
    hero_items = [
        ("Commandes recues", str(metrics["orders_received"]), f"Base cohorte - {pct(metrics['confirmation_rate'])} confirmees", "neutral", "Volume"),
        ("Taux confirmation", pct(metrics["confirmation_rate"]), f"{metrics['orders_confirmed_net']} confirmees / {metrics['orders_received']} recues", tone_class(metrics.get("confirmation_rate"), "confirmation", thresholds), "Conf."),
        ("Transformation reelle", pct(metrics["transformation_real_rate"]), f"{metrics['orders_delivered']} livrees / {metrics['orders_received']} recues", tone_class(metrics.get("transformation_real_rate"), "transformation", thresholds), "Ratio"),
        ("CA livre finalise", money(metrics["ca_delivered"]), f"{metrics['orders_delivered']} livrees - panier moyen {money(safe_ratio(metrics.get('ca_delivered', 0), metrics.get('orders_delivered', 0)))}", "good", "CA"),
        ("Livraison / expediees", pct(metrics["delivery_total_rate_on_sent"]), f"{metrics['orders_delivered']} livrees / {metrics['orders_sent']} expediees", tone_class(metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds), "Livr."),
        ("En cours logistique", str(logistics), f"{pct(metrics.get('logistics_rate_on_sent'))} des expediees - Dispatch : {dispatch} - Livraison : {in_delivery}", "warn", "Cours"),
        ("Taux retour", pct(metrics["return_rate_on_sent"]), f"{metrics['orders_returned_failed']} retours / {metrics['orders_sent']} expediees", tone_class(metrics.get("return_rate_on_sent"), "return", thresholds), "Retour"),
        ("Perte CA retours", money(metrics["ca_returned_failed"]), f"{metrics['orders_returned_failed']} retours - valeur moyenne {money(safe_ratio(metrics.get('ca_returned_failed', 0), metrics.get('orders_returned_failed', 0)))}", tone_class(metrics.get("return_rate_on_sent"), "return", thresholds), "Perte"),
        ("Commandes a risque", str(risk_orders), f"{pct(safe_ratio(risk_orders, metrics.get('orders_confirmed_net', 0)))} des confirmees - prep + dispatch + livraison + retours", tone_class(risk_orders, "risk", thresholds), "Risque"),
    ]
    for start in range(0, len(hero_items), 4):
        cols = st.columns(4)
        for col, (title, value, subtitle, tone, badge) in zip(cols, hero_items[start:start + 4]):
            with col:
                hero_card(title, value, subtitle, tone, badge)


def render_global_kpi_blocks(metrics: dict, thresholds: dict[str, float], money_details: dict[str, float | None]) -> None:
    dispatch = int(metrics.get("orders_dispatch", 0) or 0)
    in_delivery = int(metrics.get("orders_in_delivery", 0) or 0)
    logistics = int(metrics.get("orders_logistics", dispatch + in_delivery) or 0)
    col_orders, col_delivery, col_money = st.columns(3)
    with col_orders:
        cockpit_heading("Commandes", "Confirmation et blocage avant expedition.")
        render_kpi_stack([
            ("Commandes recues", metrics["orders_received"], f"{metrics['orders_confirmed_net']} confirmees - {metrics['orders_cancelled']} annulees", "neutral"),
            ("Annulees avant expedition", metrics["orders_cancelled"], f"{pct(metrics.get('cancellation_rate'))} des recues", tone_class(metrics.get("cancellation_rate"), "return", thresholds)),
            ("En confirmation", metrics.get("orders_in_confirmation", 0), f"{pct(safe_ratio(metrics.get('orders_in_confirmation', 0), metrics.get('orders_received', 0)))} des recues", "warn"),
            ("Confirmees nettes", metrics["orders_confirmed_net"], f"{pct(metrics['confirmation_rate'])} des recues - {metrics['orders_cancelled']} annulees", "info"),
            ("Confirmees non expediees", metrics["orders_preparation"], f"{pct(metrics.get('preparation_blockage_rate'))} des confirmees", tone_class(metrics.get("preparation_blockage_rate"), "return", thresholds)),
        ])
    with col_delivery:
        cockpit_heading("Expedition / livraison", "Performance apres remise au livreur.")
        render_kpi_stack([
            ("Expediees", metrics["orders_sent"], f"{pct(metrics['shipping_rate_global'])} des confirmees", "neutral"),
            ("En dispatch", dispatch, f"{pct(safe_ratio(dispatch, metrics.get('orders_sent', 0)))} des expediees", "warn"),
            ("En cours livraison", in_delivery, f"{pct(metrics.get('in_delivery_rate_on_sent'))} des expediees", "warn"),
            ("En cours logistique", logistics, f"{pct(metrics.get('logistics_rate_on_sent'))} des expediees - Dispatch : {dispatch} - Livraison : {in_delivery}", "warn"),
            ("Livraison / expediees", pct(metrics["delivery_total_rate_on_sent"]), f"{metrics['orders_delivered']} livrees / {metrics['orders_sent']} expediees", tone_class(metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
            ("Taux retour", pct(metrics["return_rate_on_sent"]), f"{metrics['orders_returned_failed']} retours / {metrics['orders_sent']} expediees", tone_class(metrics.get("return_rate_on_sent"), "return", thresholds)),
        ])
    with col_money:
        cockpit_heading("Argent", "CA securise, bloque ou perdu.")
        render_kpi_stack([
            ("CA livre finalise", money(metrics["ca_delivered"]), f"{metrics['orders_delivered']} livrees - panier moyen {money(money_details.get('panier_moyen_livre'))}", "good"),
            ("CA en dispatch", money(metrics.get("ca_dispatch", 0)), f"{dispatch} commandes dispatch", "warn"),
            ("CA en cours livraison", money(metrics["ca_in_delivery"]), f"{in_delivery} commandes livraison", "warn"),
            ("CA en cours logistique", money(metrics.get("ca_logistics", metrics.get("ca_dispatch", 0) + metrics["ca_in_delivery"])), f"{logistics} commandes non finalisees", "warn"),
            ("CA confirme non expedie", money(metrics["ca_preparation"]), f"{metrics['orders_preparation']} commandes preparation", "warn"),
            ("Perte CA retours", money(metrics["ca_returned_failed"]), f"{metrics['orders_returned_failed']} retours - valeur moyenne {money(money_details.get('valeur_moyenne_retour'))}", "loss"),
        ])


def render_global_mini_tables(products: pd.DataFrame, wilayas: pd.DataFrame, confirmation: pd.DataFrame, livreurs: pd.DataFrame, thresholds: dict[str, float]) -> None:
    cockpit_heading("Performance detaillee", "Top 5 par tableau, sans recommandations longues.")
    top_confirmation = top_known(confirmation, "confirmatrice", "commandes_recues")
    top_livreurs = top_known(livreurs, "livreur", "ca_livre")
    blocks = [
        ("Top produits par CA livre", top_known(products, "produit", "ca_livre"), ["produit", "commandes_recues", "taux_transformation_reel", "taux_retour", "ca_livre"], "Aucun produit avec CA livre."),
        ("Top produits par perte CA retours", top_known(products, "produit", "ca_retours"), ["produit", "retours", "taux_retour", "ca_retours"], "Aucune perte produit visible."),
        ("Top wilayas par CA livre", top_known(wilayas, "wilaya", "ca_livre"), ["wilaya", "commandes_recues", "taux_transformation_reel", "taux_retour", "ca_livre"], "Aucune wilaya avec CA livre."),
        ("Top wilayas par perte CA retours", top_known(wilayas, "wilaya", "ca_retours"), ["wilaya", "retours", "taux_retour", "ca_retours"], "Aucune perte wilaya visible."),
        ("Performance confirmatrices", top_confirmation, ["confirmatrice", "commandes_recues", "taux_confirmation", "taux_transformation_reel", "ca_livre"], "Aucune confirmatrice exploitable."),
        ("Performance livreurs", top_livreurs, ["livreur", "commandes_envoyees", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_retours"], "Aucun livreur exploitable."),
    ]
    for start in range(0, len(blocks), 3):
        cols = st.columns(3)
        for col, (title, frame, columns, empty) in zip(cols, blocks[start:start + 3]):
            with col:
                st.markdown(f"**{title}**")
                render_data_table(frame, columns, thresholds, empty, height=240)
