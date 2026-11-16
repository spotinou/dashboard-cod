"""One rendering function per dashboard tab. Each receives the dict built by ``run_app``."""
from __future__ import annotations

import streamlit as st

from .formatting import SENSITIVE_COLUMNS, TREND_ACCENT, adaptive_height, is_known_value, money, pct, prepare_dataframe_for_display, safe_ratio, sort_for_display, tone_class, top_label, weighted_rate
from .components import cockpit_heading, decision_summary, render_data_table, render_quality_badge, render_section_kpis, render_selectable_data_table, selected_index, show_drilldown, tab_header
from .filters import render_active_filters_banner, render_date_context
from .analysis import build_export, confirmation_summary, delivery_summary, product_summary, validation_summary, validation_value, wilaya_summary
from .overview import confirmation_funnel_counts, displayed_reception_rates, render_owner_global_dashboard
from .evolution import render_trend_section
from .ranking_charts import render_amount_ranking, render_rate_ranking
from .flow_charts import render_cod_flow_section


def render_global_tab(ctx: dict) -> None:
    date_context = ctx["date_context"]
    df = ctx["df"]
    global_metrics = ctx["global_metrics"]
    loaded_df = ctx["loaded_df"]
    priority_actions = ctx["priority_actions"]
    thresholds = ctx["thresholds"]
    validation_checks = ctx["validation_checks"]
    tab_header("Vue globale", "Les chiffres essentiels pour piloter rapidement votre activite COD.")
    render_quality_badge(validation_checks)
    render_date_context(date_context)
    render_active_filters_banner(date_context)
    render_owner_global_dashboard(df, global_metrics, thresholds, priority_actions)
    cockpit_heading("Entonnoir et argent", "Où se perdent les commandes et le chiffre d'affaires, de la réception à la livraison.")
    render_cod_flow_section(df, global_metrics)
    render_trend_section(df, loaded_df, date_context, global_metrics, thresholds)


def render_confirmation_tab(ctx: dict) -> None:
    confirmation_display = ctx["confirmation_display"]
    confirmatrice_product_detail = ctx["confirmatrice_product_detail"]
    df = ctx["df"]
    global_metrics = ctx["global_metrics"]
    thresholds = ctx["thresholds"]
    volume_confirmatrice = ctx["volume_confirmatrice"]
    tab_header("Confirmation", "Qualite des confirmatrices et transformation reelle par cohorte.")
    funnel_confirmed, funnel_confirmation_rate, funnel_preparation_rate = confirmation_funnel_counts(global_metrics)
    funnel_confirmation_display_rate, funnel_in_confirmation_rate, funnel_cancellation_display_rate = displayed_reception_rates(global_metrics, funnel_confirmation_rate)
    render_section_kpis(
        [
            ("Commandes reçues", global_metrics["orders_received"], "Base de la période", "neutral"),
            ("Taux confirmé", pct(funnel_confirmation_display_rate), f"{funnel_confirmed} commandes confirmées\nBase : {global_metrics['orders_received']} reçues", tone_class(funnel_confirmation_rate, "confirmation", thresholds)),
            ("Taux en cours de confirmation", pct(funnel_in_confirmation_rate), f"{global_metrics.get('orders_in_confirmation', 0)} commandes en confirmation\nBase : {global_metrics['orders_received']} reçues", tone_class(funnel_in_confirmation_rate, "preparation", thresholds)),
            ("Taux en préparation", pct(funnel_preparation_rate), f"{global_metrics['orders_preparation']} commandes en préparation\nBase : {funnel_confirmed} confirmées", tone_class(funnel_preparation_rate, "preparation", thresholds)),
            ("Taux livré", pct(global_metrics["delivery_total_rate_on_sent"]), f"{global_metrics['orders_delivered']} commandes livrées\nBase : {global_metrics['orders_sent']} expédiées", tone_class(global_metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
            ("Taux de transformation brute", pct(global_metrics["transformation_real_rate"]), f"{global_metrics['orders_delivered']} livrées / {global_metrics['orders_received']} reçues", tone_class(global_metrics.get("transformation_real_rate"), "transformation", thresholds)),
            ("Taux annulé", pct(funnel_cancellation_display_rate), f"{global_metrics['orders_cancelled']} commandes annulées\nBase : {global_metrics['orders_received']} reçues", tone_class(global_metrics.get("cancellation_rate"), "cancellation", thresholds)),
        ],
        max_per_row=3,
    )

    cockpit_heading("Performance detaillee", "Clique sur une ligne pour afficher les commandes concernees.")
    confirmation_cols = ["confirmatrice", "fiabilite_volume", "commandes_recues", "commandes_annulees", "commandes_confirmees_nettes", "taux_confirmation", "en_preparation", "taux_preparation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_livraison_total", "retours", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours"]
    event, confirmation_view = render_selectable_data_table(confirmation_display, confirmation_cols, "confirmation_table", thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_recues")
    idx = selected_index(event)
    if idx is not None and idx < len(confirmation_view):
        row = confirmation_view.iloc[idx]
        show_drilldown(df, "confirmatrice", "Affectée à", row["confirmatrice"], "Commandes annulees", "confirmation")

    render_rate_ranking(
        confirmation_display, "confirmatrice", "taux_transformation_reel", "livrees", "commandes_recues",
        "commandes_recues", "reçues", volume_confirmatrice,
        "Classement des confirmatrices", "Sur 100 commandes reçues, combien finissent livrées", True, "rank_confirmatrice",
    )
    with st.expander("Analyse Confirmatrice x Produit", expanded=False):
        cp_cols = ["confirmatrice", "produit", "fiabilite_volume", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "en_preparation", "taux_preparation", "commandes_envoyees", "livrees", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_retours", "lecture_rapide"]
        render_data_table(confirmatrice_product_detail, cp_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by=["confirmatrice", "commandes_recues"])

    with st.expander("Voir detail complet confirmation", expanded=False):
        render_data_table(confirmation_display, list(confirmation_display.columns), thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_recues")
    decision_summary("Résumé décisionnel", confirmation_summary(confirmation_display, volume_confirmatrice))


def render_delivery_tab(ctx: dict) -> None:
    df = ctx["df"]
    global_metrics = ctx["global_metrics"]
    livreurs_ui = ctx["livreurs_ui"]
    thresholds = ctx["thresholds"]
    volume_sent = ctx["volume_sent"]
    wilaya_livreur_compare = ctx["wilaya_livreur_compare"]
    wilaya_livreur_detail = ctx["wilaya_livreur_detail"]
    tab_header("Livraison & livreurs", "Performance apres expedition, retours et CA bloque chez les livreurs.")
    render_section_kpis(
        [
            ("Commandes exp\u00e9di\u00e9es", global_metrics["orders_sent"], "Base des KPI logistiques", "neutral"),
            ("Taux en pr\u00e9paration", pct(global_metrics.get("preparation_blockage_rate")), f"{global_metrics['orders_preparation']} commandes en pr\u00e9paration\nBase : {global_metrics['orders_confirmed_net']} confirm\u00e9es", tone_class(global_metrics.get("preparation_blockage_rate"), "preparation", thresholds)),
            ("Taux en dispatch", pct(safe_ratio(global_metrics.get("orders_dispatch", 0), global_metrics["orders_sent"])), f"{global_metrics.get('orders_dispatch', 0)} commandes en dispatch\nBase : {global_metrics['orders_sent']} exp\u00e9di\u00e9es", "warn" if global_metrics.get("orders_dispatch", 0) else "good"),
            ("Taux en cours de livraison", pct(global_metrics.get("in_delivery_rate_on_sent")), f"{global_metrics['orders_in_delivery']} commandes en livraison\nBase : {global_metrics['orders_sent']} exp\u00e9di\u00e9es", "warn" if global_metrics.get("orders_in_delivery", 0) else "good"),
            ("Taux livr\u00e9", pct(global_metrics["delivery_total_rate_on_sent"]), f"{global_metrics['orders_delivered']} commandes livr\u00e9es\nBase : {global_metrics['orders_sent']} exp\u00e9di\u00e9es", tone_class(global_metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
            ("Taux de transformation brute", pct(global_metrics["transformation_real_rate"]), f"{global_metrics['orders_delivered']} livr\u00e9es / {global_metrics['orders_received']} re\u00e7ues", tone_class(global_metrics.get("transformation_real_rate"), "transformation", thresholds)),
            ("Taux retour", pct(global_metrics["return_rate_on_sent"]), f"{global_metrics['orders_returned_failed']} retours / \u00e9checs\nBase : {global_metrics['orders_sent']} exp\u00e9di\u00e9es", tone_class(global_metrics.get("return_rate_on_sent"), "return", thresholds)),
        ],
        max_per_row=3,
    )
    st.info("La pr\u00e9paration est affich\u00e9e comme blocage interne avant remise au livreur ; elle reste exclue de la performance logistique individuelle.")

    cockpit_heading("Performance detaillee", "Livraison, retours et CA par livreur.")
    livreur_cols = ["livreur", "fiabilite_volume", "en_preparation", "taux_preparation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_bloque_livraison", "ca_en_cours_logistique", "ca_retours", "panier_moyen_livre"]
    event, livreurs_view = render_selectable_data_table(livreurs_ui, livreur_cols, "livreur_table", thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_envoyees")
    idx = selected_index(event)
    if idx is not None and idx < len(livreurs_view):
        row = livreurs_view.iloc[idx]
        show_drilldown(df, "livreur", "Livreur", row["livreur"], "Retours / echecs", "livreur")

    cockpit_heading("Wilaya x livreur", "Lecture croisee pour isoler les zones faibles.")
    wilaya_livreur_cols = ["livreur", "wilaya", "fiabilite_volume", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "panier_moyen_livre", "lecture_rapide"]
    render_data_table(wilaya_livreur_detail, wilaya_livreur_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by=["wilaya", "commandes_envoyees"])

    with st.expander("Comparaison livreurs par wilaya", expanded=False):
        compare_cols = ["wilaya", "livreur_dominant", "expediees_dominant", "taux_livraison_dominant", "taux_retour_dominant", "livreur_alternatif", "expediees_alternatif", "taux_livraison_alternatif", "taux_retour_alternatif", "ecart_livraison", "ecart_retour", "fiabilite_comparaison", "lecture_rapide"]
        render_data_table(wilaya_livreur_compare, compare_cols, thresholds, "Aucune comparaison disponible avec les filtres actuels.", sort_by="wilaya")

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        render_rate_ranking(
            livreurs_ui, "livreur", "taux_livraison_total", "livrees", "commandes_envoyees",
            "commandes_envoyees", "expédiées", volume_sent,
            "Taux de livraison par livreur", "Sur 100 colis expédiés, combien livrés", True, "rank_livreur",
        )
    with col2:
        render_amount_ranking(livreurs_ui, "livreur", "ca_retours", "Perte CA retours par livreur", "Montant des colis revenus, par livreur", "#ef4444", "amount_livreur_retours")
    with st.expander("Voir detail complet livreurs", expanded=False):
        render_data_table(livreurs_ui, list(livreurs_ui.columns), thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_envoyees")
    decision_summary("Résumé décisionnel", delivery_summary(livreurs_ui, volume_sent))


def render_products_tab(ctx: dict) -> None:
    df = ctx["df"]
    product_livreur_detail = ctx["product_livreur_detail"]
    product_wilaya_detail = ctx["product_wilaya_detail"]
    products = ctx["products"]
    products_advice = ctx["products_advice"]
    products_ui = ctx["products_ui"]
    sku_performance = ctx["sku_performance"]
    sku_product_detail = ctx["sku_product_detail"]
    source_performance = ctx["source_performance"]
    source_product_detail = ctx["source_product_detail"]
    thresholds = ctx["thresholds"]
    volume_product = ctx["volume_product"]
    tab_header("Produits", "Produits qui encaissent, produits qui perdent et segments a surveiller.")
    product_count = int(products_ui["produit"].apply(is_known_value).sum()) if not products_ui.empty and "produit" in products_ui.columns else 0
    main_product = top_label(products_ui, "produit", "ca_livre", "commandes_recues", volume_product)
    render_section_kpis([
        ("Nombre de produits", product_count, "produits exploitables", "neutral"),
        ("Produit principal", main_product, "meilleur CA livre", "info"),
        ("CA livre total", money(products["ca_livre"].sum() if "ca_livre" in products.columns else 0), f"{int(products['livrees'].sum()) if 'livrees' in products.columns else 0} livrees", "good"),
        ("En cours logistique", int(products["en_cours_logistique"].sum()) if "en_cours_logistique" in products.columns else 0, f"{pct(weighted_rate(products, 'en_cours_logistique', 'commandes_envoyees'))} des expediees", "warn"),
        ("Perte CA retours", money(products["ca_retours"].sum() if "ca_retours" in products.columns else 0), f"{int(products['retours'].sum()) if 'retours' in products.columns else 0} retours", "loss"),
        ("Transformation reelle", pct(weighted_rate(products, "livrees", "commandes_recues")), "livrees / recues", tone_class(weighted_rate(products, "livrees", "commandes_recues"), "transformation", thresholds)),
    ])

    cockpit_heading("Performance detaillee", "Produit par produit, avec CA livre et pertes retours.")
    product_cols = ["produit", "fiabilite_volume", "decision_auto", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_livraison_total", "retours", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "ca_bloque_livraison", "panier_moyen_livre"]
    event, products_view = render_selectable_data_table(products_ui, product_cols, "product_table", thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="ca_livre")
    idx = selected_index(event)
    if idx is not None and idx < len(products_view):
        row = products_view.iloc[idx]
        show_drilldown(df, "produit", "Nom produit", row["produit"], "Retours / echecs", "produit")

    cockpit_heading("Produit x Wilaya", "Segments prioritaires par zone.")
    product_wilaya_cols = ["produit", "wilaya", "fiabilite_volume", "commandes_recues", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_transformation_reel", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "livreur_dominant", "lecture_rapide"]
    render_data_table(product_wilaya_detail, product_wilaya_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by=["ca_livre", "ca_retours"])

    with st.expander("Produit x Livreur", expanded=False):
        product_livreur_cols = ["produit", "livreur", "fiabilite_volume", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "panier_moyen_livre", "lecture_rapide"]
        render_data_table(product_livreur_detail, product_livreur_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by=["ca_retours", "commandes_envoyees"])

    with st.expander("Source x Produit", expanded=False):
        source_product_cols = ["source", "produit", "fiabilite_volume", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "lecture_rapide"]
        render_data_table(source_product_detail, source_product_cols, thresholds, "Aucune donnee Source exploitable.", sort_by=["commandes_recues", "ca_retours"])

    with st.expander("SKU x Produit", expanded=False):
        sku_product_cols = ["sku_produit", "produit", "fiabilite_volume", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "lecture_rapide"]
        render_data_table(sku_product_detail, sku_product_cols, thresholds, "Aucune donnee SKU exploitable.", sort_by="ca_livre")

    with st.expander("Voir performances Source et SKU agregees", expanded=False):
        source_cols = ["source", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours"]
        render_data_table(source_performance, source_cols, thresholds, "Aucune donnee Source exploitable.", sort_by="ca_livre")
        sku_cols = ["sku_produit", "produit_associe", "commandes_recues", "commandes_confirmees_nettes", "taux_confirmation", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours"]
        render_data_table(sku_performance, sku_cols, thresholds, "Aucune donnee SKU exploitable.", sort_by="ca_livre")

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        render_amount_ranking(products_ui, "produit", "ca_livre", "CA livré par produit", "Montant des colis livrés, par produit", TREND_ACCENT, "amount_produit_livre")
    with col2:
        render_amount_ranking(products_ui, "produit", "ca_retours", "Perte CA retours par produit", "Montant des colis revenus, par produit", "#ef4444", "amount_produit_retours")
    render_rate_ranking(
        products_ui, "produit", "taux_retour", "retours", "commandes_envoyees",
        "commandes_envoyees", "expédiées", volume_product,
        "Taux de retour par produit", "Sur 100 colis expédiés, combien reviennent", False, "rank_produit_retour",
    )
    with st.expander("Voir detail complet produits", expanded=False):
        render_data_table(products_advice, list(products_advice.columns), thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="ca_livre")
    decision_summary("Résumé décisionnel", product_summary(products_ui, volume_product))


def render_wilayas_tab(ctx: dict) -> None:
    alerts = ctx["alerts"]
    global_metrics = ctx["global_metrics"]
    reliable_wilayas = ctx["reliable_wilayas"]
    thresholds = ctx["thresholds"]
    volume_sent = ctx["volume_sent"]
    wilaya_livreur_detail = ctx["wilaya_livreur_detail"]
    wilayas = ctx["wilayas"]
    wilayas_ui = ctx["wilayas_ui"]
    tab_header("Wilayas & alertes", "Zones fortes, zones a risque et alertes operationnelles.")
    active_wilayas = int(wilayas["wilaya"].apply(is_known_value).sum()) if not wilayas.empty and "wilaya" in wilayas.columns else 0
    best_wilaya = top_label(wilayas_ui, "wilaya", "ca_livre", "commandes_envoyees", volume_sent)
    loss_wilaya = top_label(wilayas_ui, "wilaya", "ca_retours", "commandes_envoyees", volume_sent)
    render_section_kpis([
        ("Wilayas actives", active_wilayas, "zones avec donnees", "neutral"),
        ("Meilleure wilaya", best_wilaya, "meilleur CA livre", "good"),
        ("Plus forte perte", loss_wilaya, "perte CA retours", "loss"),
        ("En cours logistique", global_metrics.get("orders_logistics", 0), f"{pct(global_metrics.get('logistics_rate_on_sent'))} des expediees", "warn"),
        ("Livraison / expediees", pct(global_metrics["delivery_total_rate_on_sent"]), f"{global_metrics['orders_delivered']} livrees / {global_metrics['orders_sent']} expediees", tone_class(global_metrics.get("delivery_total_rate_on_sent"), "delivery", thresholds)),
    ])

    render_rate_ranking(
        wilayas_ui, "wilaya", "taux_livraison_total", "livrees", "commandes_envoyees",
        "commandes_envoyees", "expédiées", volume_sent,
        "Taux de livraison par wilaya", "Sur 100 colis expédiés, combien livrés", True, "rank_wilaya",
    )

    cockpit_heading("Top CA livre", "Wilayas qui securisent le plus de CA.")
    top_wilaya_cols = ["wilaya", "commandes_recues", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_livraison_total", "taux_retour", "ca_livre", "ca_dispatch", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
    render_data_table(sort_for_display(reliable_wilayas, ["ca_livre"]).head(10), top_wilaya_cols, thresholds, "Aucune wilaya avec un volume suffisant pour un classement fiable.")

    cockpit_heading("Top pertes", "Wilayas qui concentrent les retours et pertes CA.")
    loss_wilaya_cols = ["wilaya", "commandes_envoyees", "retours", "taux_retour", "ca_retours", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
    render_data_table(sort_for_display(reliable_wilayas, ["ca_retours"]).head(10), loss_wilaya_cols, thresholds, "Aucune wilaya avec un volume suffisant pour un classement fiable.")

    col_retour, col_livraison = st.columns(2)
    with col_retour:
        cockpit_heading("Retours eleves", "Zones a surveiller avant d augmenter le volume.")
        high_return = sort_for_display(reliable_wilayas, ["taux_retour"], ascending=False).head(10)
        return_cols = ["wilaya", "commandes_envoyees", "retours", "taux_retour", "ca_retours", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
        render_data_table(high_return, return_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.")
    with col_livraison:
        cockpit_heading("Bon taux livraison", "Zones qui supportent mieux le volume.")
        good_delivery = sort_for_display(reliable_wilayas, ["taux_livraison_total", "ca_livre"]).head(10)
        delivery_cols = ["wilaya", "commandes_envoyees", "livrees", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
        render_data_table(good_delivery, delivery_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.")

    cockpit_heading("Performance detaillee", "Vue complete par wilaya.")
    wilaya_cols = ["wilaya", "commandes_recues", "commandes_confirmees_nettes", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_transformation_reel", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "produit_dominant", "livreur_dominant", "fiabilite_volume"]
    render_data_table(wilayas_ui, wilaya_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="ca_livre")

    cockpit_heading("Wilaya x livreur", "Lecture croisee pour isoler les zones faibles.")
    wilaya_livreur_cols = ["wilaya", "livreur", "fiabilite_volume", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "retours", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "ca_en_cours_logistique", "ca_retours", "lecture_rapide"]
    render_data_table(wilaya_livreur_detail, wilaya_livreur_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="commandes_envoyees")

    with st.expander("Produits dominants par wilaya", expanded=False):
        dominant_cols = ["wilaya", "produit_dominant", "livreur_dominant", "commandes_recues", "commandes_envoyees", "livrees", "taux_transformation_reel", "ca_livre", "fiabilite_volume"]
        render_data_table(wilayas_ui, dominant_cols, thresholds, "Aucune donnee disponible avec les filtres actuels.", sort_by="ca_livre")

    with st.expander("Alertes simples", expanded=False):
        if alerts:
            for alert in alerts:
                st.markdown(f"<div class='alert {alert['niveau']}'><b>{alert['titre']}</b><br>{alert['message']}</div>", unsafe_allow_html=True)
        else:
            st.info("Aucune alerte critique detectee avec les seuils actifs.")
    decision_summary("Résumé décisionnel", wilaya_summary(wilayas_ui, volume_sent))


def render_validation_tab(ctx: dict) -> None:
    date_audit_filtered = ctx["date_audit_filtered"]
    date_audit_full = ctx["date_audit_full"]
    thresholds = ctx["thresholds"]
    validation_checks = ctx["validation_checks"]
    tab_header("Validation chiffres", "Controle qualite du fichier, anomalies et coherence des egalites COD.")
    failed_checks = validation_checks[validation_checks["statut"] != "OK"]
    total_lines = validation_value(validation_checks, "Lignes Excel")
    duplicates = validation_value(validation_checks, "Doublons")
    missing_important = sum(validation_value(validation_checks, name) for name in ["sans wilaya", "sans produit", "sans statut"])
    valid_lines = max(total_lines - duplicates - missing_important, 0)
    render_section_kpis([
        ("Lignes fichier", total_lines, "lignes importees", "neutral"),
        ("Lignes valides", valid_lines, "hors doublons / manquants cles", "good" if failed_checks.empty else "warn"),
        ("Anomalies", len(failed_checks), "controles - verifier", "good" if failed_checks.empty else "loss"),
        ("Valeurs manquantes", missing_important, "wilaya / produit / statut", "good" if missing_important == 0 else "warn"),
        ("Doublons", duplicates, "lignes en doublon", "good" if duplicates == 0 else "warn"),
    ])
    cockpit_heading("Audit dates - fichier complet")
    render_data_table(date_audit_full, ["controle", "valeur", "attendu", "statut", "details"], thresholds, "Aucun controle date disponible.", height=adaptive_height(date_audit_full, max_height=280))
    cockpit_heading("Audit dates - perimetre filtre")
    render_data_table(date_audit_filtered, ["controle", "valeur", "attendu", "statut", "details"], thresholds, "Aucun controle date disponible.", height=adaptive_height(date_audit_filtered, max_height=280))
    cockpit_heading("Validation des donnees")
    validation_view = validation_checks.assign(_sort=validation_checks["statut"].eq("OK").astype(int)).sort_values("_sort").drop(columns="_sort")
    render_data_table(validation_view, ["controle", "valeur", "attendu", "statut", "details"], thresholds, "Aucun controle de validation disponible.", sort_by="statut", height=adaptive_height(validation_view, max_height=520))
    with st.expander("Voir tous les controles", expanded=False):
        render_data_table(validation_checks, list(validation_checks.columns), thresholds, "Aucun controle de validation disponible.")
    decision_summary("Résumé décisionnel", validation_summary(validation_checks))


def render_data_tab(ctx: dict) -> None:
    confirmation = ctx["confirmation"]
    df = ctx["df"]
    global_metrics = ctx["global_metrics"]
    livreur_wilaya = ctx["livreur_wilaya"]
    livreurs = ctx["livreurs"]
    product_wilaya = ctx["product_wilaya"]
    products = ctx["products"]
    sku_performance = ctx["sku_performance"]
    source_performance = ctx["source_performance"]
    validation_checks = ctx["validation_checks"]
    wilayas = ctx["wilayas"]
    tab_header("Donnees nettoyees / export", "Apercu nettoye et exports operationnels sans donnees sensibles.")
    safe_df = df.drop(columns=[c for c in SENSITIVE_COLUMNS if c in df.columns], errors="ignore")
    render_section_kpis([
        ("Lignes nettoyees", len(safe_df), "apres import", "neutral"),
        ("Commandes uniques", safe_df["order_id"].nunique(dropna=False) if "order_id" in safe_df.columns else 0, "base COD", "info"),
        ("Colonnes visibles", len(safe_df.columns), "hors donnees sensibles", "neutral"),
    ])
    cockpit_heading("Donnees nettoyees")
    st.dataframe(prepare_dataframe_for_display(safe_df.head(200), rename_columns=True), width="stretch", hide_index=True, height=360)
    tables = {
        "Confirmation": confirmation,
        "Livreurs": livreurs,
        "Produits": products,
        "Wilayas": wilayas,
        "Alertes_Produit_Wilaya": product_wilaya,
        "Alertes_Livreur_Wilaya": livreur_wilaya,
        "Source": source_performance,
        "SKU_Produit": sku_performance,
        "Validation": validation_checks,
    }
    st.download_button("Exporter les resultats Excel", build_export(global_metrics, tables, df), file_name="dashboard_cod_resultats.xlsx")
    st.download_button("Exporter donnees nettoyees CSV", safe_df.to_csv(index=False).encode("utf-8-sig"), file_name="donnees_nettoyees_cod.csv")
