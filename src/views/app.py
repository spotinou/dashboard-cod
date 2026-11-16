"""Streamlit entry point."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..alerts import generate_alerts
from ..data_loader import load_excel, validate_columns
from ..metrics import compute_confirmation_metrics, compute_global_metrics, compute_livreur_metrics, compute_livreur_wilaya_alerts, compute_product_metrics, compute_product_wilaya_alerts, compute_wilaya_metrics
from ..validation import compute_validation_checks
from .formatting import reliable_rows
from .filters import filter_dataframe, summarize_missing_dates, uploaded_file_signature
from .analysis import add_product_advice, add_volume_reading, compute_confirmatrice_quality, compute_dimension_performance, compute_livreur_wilaya_arbitrage, compute_opportunities, compute_priority_actions, confirmatrice_product_performance, livreur_wilaya_performance, preparation_metrics_by_dimension, product_livreur_performance, product_wilaya_performance, sku_product_performance, source_product_performance, wilaya_livreur_comparison
from .styles import DASHBOARD_CSS
from .tabs import render_global_tab, render_confirmation_tab, render_delivery_tab, render_products_tab, render_wilayas_tab, render_validation_tab, render_data_tab


def compute_dashboard_data(df: pd.DataFrame, thresholds: dict[str, float]) -> dict:
    """Every table and indicator the tabs display, computed once for the filtered orders."""
    volume_product = int(thresholds["volume_product"])
    volume_sent = int(thresholds["volume_sent"])
    volume_confirmatrice = volume_sent
    global_metrics = compute_global_metrics(df)
    validation_checks = compute_validation_checks(df, global_metrics)
    confirmation = compute_confirmation_metrics(df)
    livreurs = compute_livreur_metrics(df)
    products = compute_product_metrics(df, volume_product)
    wilayas = compute_wilaya_metrics(df, volume_sent)
    product_wilaya = compute_product_wilaya_alerts(df, volume_sent)
    livreur_wilaya = compute_livreur_wilaya_alerts(df, volume_sent)
    alerts = generate_alerts(global_metrics, products, wilayas, livreurs, confirmation, thresholds)
    products_advice = add_product_advice(products, volume_product, thresholds)
    confirmation_quality = compute_confirmatrice_quality(df, confirmation, volume_confirmatrice, thresholds)
    arbitrage_livreur = compute_livreur_wilaya_arbitrage(df, volume_sent, thresholds)
    opportunities = compute_opportunities(
        products,
        wilayas,
        product_wilaya,
        volume_product,
        volume_sent,
        thresholds,
    )
    priority_actions = compute_priority_actions(
        products,
        wilayas,
        confirmation_quality,
        arbitrage_livreur,
        opportunities,
        volume_product,
        volume_sent,
        thresholds,
    )
    source_performance = compute_dimension_performance(df, ["Source"], volume_product, thresholds)
    sku_performance = compute_dimension_performance(df, ["SKU produit"], volume_product, thresholds)
    confirmation_display = confirmation.merge(
        confirmation_quality[["confirmatrice", "ca_retours"]] if not confirmation_quality.empty and "ca_retours" in confirmation_quality.columns else pd.DataFrame(columns=["confirmatrice", "ca_retours"]),
        on="confirmatrice",
        how="left",
    )
    confirmation_display["ca_retours"] = confirmation_display.get("ca_retours", 0).fillna(0)
    confirmation_preparation = preparation_metrics_by_dimension(df, "Affect\u00e9e \u00e0", "confirmatrice")
    confirmation_display = confirmation_display.merge(confirmation_preparation, on="confirmatrice", how="left")
    confirmation_display[["en_preparation", "taux_preparation"]] = confirmation_display[["en_preparation", "taux_preparation"]].fillna({"en_preparation": 0})
    confirmation_display = add_volume_reading(confirmation_display, "commandes_recues", volume_confirmatrice, "confirmatrice", thresholds)
    livreur_preparation = preparation_metrics_by_dimension(df, "Livreur", "livreur")
    livreurs = livreurs.merge(livreur_preparation, on="livreur", how="left")
    livreurs[["en_preparation", "taux_preparation"]] = livreurs[["en_preparation", "taux_preparation"]].fillna({"en_preparation": 0})
    livreurs_ui = add_volume_reading(livreurs, "commandes_envoyees", volume_sent, "livreur", thresholds)
    products_ui = add_volume_reading(products, "commandes_recues", volume_product, "produit", thresholds)
    product_wilaya_detail = add_volume_reading(product_wilaya_performance(df), "commandes_envoyees", volume_sent, "product_wilaya", thresholds)
    wilaya_livreur_detail = add_volume_reading(livreur_wilaya_performance(df), "commandes_envoyees", volume_sent, "wilaya_livreur", thresholds)
    wilayas_ui = add_volume_reading(wilayas, "commandes_envoyees", volume_sent, "wilaya", thresholds)
    reliable_livreurs = reliable_rows(livreurs_ui, "livreur", "commandes_envoyees", volume_sent)
    reliable_products = reliable_rows(products_ui, "produit", "commandes_recues", volume_product)
    reliable_wilayas = reliable_rows(wilayas_ui, "wilaya", "commandes_envoyees", volume_sent)
    product_livreur_detail = product_livreur_performance(df, volume_sent, thresholds)
    source_product_detail = source_product_performance(df, volume_product, thresholds)
    sku_product_detail = sku_product_performance(df, volume_product, thresholds)
    confirmatrice_product_detail = confirmatrice_product_performance(df, volume_product, thresholds)
    wilaya_livreur_compare = wilaya_livreur_comparison(df, volume_sent)
    return {
        "alerts": alerts,
        "arbitrage_livreur": arbitrage_livreur,
        "confirmation": confirmation,
        "confirmation_display": confirmation_display,
        "confirmation_preparation": confirmation_preparation,
        "confirmation_quality": confirmation_quality,
        "confirmatrice_product_detail": confirmatrice_product_detail,
        "global_metrics": global_metrics,
        "livreur_preparation": livreur_preparation,
        "livreur_wilaya": livreur_wilaya,
        "livreurs": livreurs,
        "livreurs_ui": livreurs_ui,
        "opportunities": opportunities,
        "priority_actions": priority_actions,
        "product_livreur_detail": product_livreur_detail,
        "product_wilaya": product_wilaya,
        "product_wilaya_detail": product_wilaya_detail,
        "products": products,
        "products_advice": products_advice,
        "products_ui": products_ui,
        "reliable_livreurs": reliable_livreurs,
        "reliable_products": reliable_products,
        "reliable_wilayas": reliable_wilayas,
        "sku_performance": sku_performance,
        "sku_product_detail": sku_product_detail,
        "source_performance": source_performance,
        "source_product_detail": source_product_detail,
        "validation_checks": validation_checks,
        "volume_confirmatrice": volume_confirmatrice,
        "volume_product": volume_product,
        "volume_sent": volume_sent,
        "wilaya_livreur_compare": wilaya_livreur_compare,
        "wilaya_livreur_detail": wilaya_livreur_detail,
        "wilayas": wilayas,
        "wilayas_ui": wilayas_ui,
    }


def run_app() -> None:
    st.set_page_config(page_title="Dashboard COD", layout="wide")
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)
    st.title("Dashboard opérationnel COD")
    uploaded = st.sidebar.file_uploader("Upload Excel CRM/ERP", type=["xlsx", "xls"])
    if uploaded is None:
        st.info("Upload un export Excel pour afficher les KPI COD.")
        return

    file_signature = uploaded_file_signature(uploaded)

    try:
        raw_preview = pd.read_excel(uploaded, nrows=5, dtype=object)
        uploaded.seek(0)
        for warning in validate_columns(raw_preview):
            st.warning(warning)
        df = load_excel(uploaded)
    except Exception as exc:
        st.error(f"Impossible de lire le fichier : {exc}")
        return

    loaded_df = df.copy()
    df, thresholds, date_context = filter_dataframe(df, file_signature=file_signature)
    date_audit_full = summarize_missing_dates(loaded_df, "Fichier complet")
    date_audit_filtered = summarize_missing_dates(df, "Perimetre filtre")
    if df.empty:
        st.warning("Aucune donnée avec ces filtres.")
        return

    data = compute_dashboard_data(df, thresholds)
    ctx = {
        "date_audit_filtered": date_audit_filtered,
        "date_audit_full": date_audit_full,
        "date_context": date_context,
        "df": df,
        "loaded_df": loaded_df,
        "thresholds": thresholds,
        **data,
    }

    tabs = st.tabs(["Vue globale", "Confirmation", "Livraison & livreurs", "Produits", "Wilayas & alertes", "Validation chiffres", "Donnees nettoyees / export"])
    with tabs[0]:
        render_global_tab(ctx)
    with tabs[1]:
        render_confirmation_tab(ctx)
    with tabs[2]:
        render_delivery_tab(ctx)
    with tabs[3]:
        render_products_tab(ctx)
    with tabs[4]:
        render_wilayas_tab(ctx)
    with tabs[5]:
        render_validation_tab(ctx)
    with tabs[6]:
        render_data_tab(ctx)
