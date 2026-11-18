import pandas as pd
import src.ui as ui

from src.ui import (
    prepare_dataframe_for_display,
    render_data_table,
    format_table,
    style_metric_table,
    build_amount_bar_figure,
    build_confirmation_rate_figure,
    build_percent_bar_figure,
    confirmation_summary,
    data_quality_has_warning,
    reliable_rows,
    add_product_advice,
    compute_dimension_performance,
    compute_livreur_wilaya_arbitrage,
    compute_priority_actions,
    global_metrics_table,
    amount_totals,
    owner_kpi_sections,
    owner_money_sections,
    owner_priority,
    preparation_metrics_by_dimension,
    top_label,
    apply_date_filter,
    available_date_bounds,
    normalize_date_range,
    normalize_analysis_period,
    period_from_preset,
    initialize_analysis_period_selector,
    apply_analysis_period_selection,
    summarize_missing_dates,
    sort_for_display,
    sanitize_multiselect_state,
    ANALYSIS_PERIOD_PRESET_KEY,
    ANALYSIS_PERIOD_DRAFT_KEY,
    ANALYSIS_PERIOD_VALUE_KEY,
    ANALYSIS_PERIOD_FILE_KEY,
)


def test_confirmation_chart_handles_all_missing_delivery_rate():
    df = pd.DataFrame(
        {
            "confirmatrice": ["Rayan conf", "Rayane Manager"],
            "commandes_recues": [36, 21],
            "taux_confirmation": [1.0, 1.0],
            "taux_livraison_finalisees": [None, None],
        }
    )
    fig = build_confirmation_rate_figure(df)
    assert fig is not None


def test_confirmation_chart_returns_none_when_no_numeric_rate():
    df = pd.DataFrame(
        {
            "confirmatrice": ["Rayan conf"],
            "commandes_recues": [36],
            "taux_confirmation": [None],
            "taux_livraison_finalisees": [None],
        }
    )
    assert build_confirmation_rate_figure(df) is None


def test_percent_bar_handles_empty_or_missing_columns():
    assert build_percent_bar_figure(pd.DataFrame(), "livreur", "taux_retour", "Test") is None
    assert build_percent_bar_figure(pd.DataFrame({"livreur": ["Yalidine"]}), "livreur", "taux_retour", "Test") is None


def test_amount_bar_handles_empty_or_missing_columns():
    assert build_amount_bar_figure(pd.DataFrame(), "produit", "ca_livre", "Test") is None
    assert build_amount_bar_figure(pd.DataFrame({"produit": ["P1"]}), "produit", "ca_livre", "Test") is None


def test_format_table_formats_all_rate_like_columns_and_invalid_values():
    df = pd.DataFrame(
        {
            "taux_confirmation": [0.703645],
            "delivery_rate": [0.296355],
            "ratio_test": [0.599462],
            "pourcentage_test": [1.0],
            "ecart_livraison": [0.081],
            "taux_livraison_total": [None],
            "taux_retour": [float("inf")],
        }
    )
    formatted = format_table(df)
    assert formatted["Taux non annulé"].iloc[0] == "70.4 %"
    assert formatted["delivery_rate"].iloc[0] == "29.6 %"
    assert formatted["ratio_test"].iloc[0] == "59.9 %"
    assert formatted["pourcentage_test"].iloc[0] == "100.0 %"
    assert formatted["\u00c9cart livraison"].iloc[0] == "8.1 %"
    assert formatted["Taux livraison sur exp\u00e9di\u00e9es"].iloc[0] == "\u2014"
    assert formatted["Taux retour"].iloc[0] == "\u2014"


def test_styled_metric_table_uses_display_values_not_raw_ratios():
    df = pd.DataFrame(
        {
            "livreur": ["Yalidine"],
            "taux_livraison_finalisees": [0.723022],
            "taux_livraison_total": [0.659016],
            "taux_retour": [0.252459],
            "ca_livre": [739500],
            "decision_auto": ["\u00c0 surveiller"],
        }
    )
    thresholds = {
        "delivery_green": 0.75,
        "delivery_orange": 0.65,
        "return_orange": 0.15,
        "return_red": 0.25,
    }
    styled = style_metric_table(df, thresholds)
    rendered = styled.data
    assert rendered["taux_livraison_finalisees"].iloc[0] == "72.3 %"
    assert rendered["taux_livraison_total"].iloc[0] == "65.9 %"
    assert rendered["taux_retour"].iloc[0] == "25.2 %"
    assert rendered["ca_livre"].iloc[0] == "739 500 DA"
    assert df["taux_livraison_total"].iloc[0] == 0.659016


def test_prepare_dataframe_for_display_keeps_internal_dataframe_numeric():
    df = pd.DataFrame({"Taux livraison sur exp\u00e9di\u00e9es": [0.659016], "ratio_test": [0.252459]})
    rendered = prepare_dataframe_for_display(df, rename_columns=False)
    assert rendered["Taux livraison sur exp\u00e9di\u00e9es"].iloc[0] == "65.9 %"
    assert rendered["ratio_test"].iloc[0] == "25.2 %"
    assert df["Taux livraison sur exp\u00e9di\u00e9es"].iloc[0] == 0.659016


def test_reliable_rows_excludes_unknown_and_low_volume():
    df = pd.DataFrame(
        {
            "confirmatrice": ["Non renseign\u00e9", "Rayan", "Rayane"],
            "commandes_recues": [100, 2, 20],
            "taux_confirmation": [1.0, 1.0, 0.8],
        }
    )
    reliable = reliable_rows(df, "confirmatrice", "commandes_recues", 10)
    assert reliable["confirmatrice"].tolist() == ["Rayane"]


def test_confirmation_summary_uses_reliable_rows_only():
    df = pd.DataFrame(
        {
            "confirmatrice": ["Non renseign\u00e9", "Tiny", "Reliable"],
            "commandes_recues": [100, 2, 20],
            "commandes_annulees": [0, 0, 3],
            "taux_confirmation": [1.0, 1.0, 0.85],
            "taux_retour": [0.0, 0.0, 0.1],
        }
    )
    summary = confirmation_summary(df, 10)
    assert any("Reliable" in item for item in summary)
    assert not any("Non renseign\u00e9" in item for item in summary)
    assert not any("Tiny" in item for item in summary)


def test_data_quality_warning_detects_watched_controls():
    checks = pd.DataFrame(
        {
            "controle": ["Commandes sans wilaya", "Lignes Excel"],
            "valeur": [2, 100],
            "statut": ["\u00c0 v\u00e9rifier", "OK"],
        }
    )
    assert data_quality_has_warning(checks) is True
    checks.loc[0, "valeur"] = 0
    assert data_quality_has_warning(checks) is False


def test_display_column_names_are_business_readable():
    df = pd.DataFrame({"commandes_recues": [10], "ca_retours": [1000], "decision_auto": ["Stable"]})
    rendered = prepare_dataframe_for_display(df, rename_columns=True)
    assert "Commandes re\u00e7ues" in rendered.columns
    assert "Perte CA retours" in rendered.columns
    assert "D\u00e9cision" in rendered.columns


def build_advice_orders():
    return pd.DataFrame(
        [
            {"order_id": "a1", "Wilaya": "Alger", "Livreur": "Yalidine", "Nom produit": "P1", "Source": "Meta", "SKU produit": "SKU1", "Affect\u00e9e \u00e0": "Rayan", "is_confirmed_net": True, "is_sent": True, "is_delivered": True, "is_in_delivery": False, "is_return_or_failed": False, "ca_delivered": 1000, "ca_in_delivery": 0, "ca_preparation": 0, "ca_returned_failed": 0},
            {"order_id": "a2", "Wilaya": "Alger", "Livreur": "Yalidine", "Nom produit": "P1", "Source": "Meta", "SKU produit": "SKU1", "Affect\u00e9e \u00e0": "Rayan", "is_confirmed_net": True, "is_sent": True, "is_delivered": False, "is_in_delivery": False, "is_return_or_failed": True, "ca_delivered": 0, "ca_in_delivery": 0, "ca_preparation": 0, "ca_returned_failed": 1000},
            {"order_id": "a3", "Wilaya": "Alger", "Livreur": "HHD 01", "Nom produit": "P1", "Source": "Meta", "SKU produit": "SKU1", "Affect\u00e9e \u00e0": "Rayan", "is_confirmed_net": True, "is_sent": True, "is_delivered": True, "is_in_delivery": False, "is_return_or_failed": False, "ca_delivered": 1000, "ca_in_delivery": 0, "ca_preparation": 0, "ca_returned_failed": 0},
            {"order_id": "a4", "Wilaya": "Alger", "Livreur": "HHD 01", "Nom produit": "P1", "Source": "Meta", "SKU produit": "SKU1", "Affect\u00e9e \u00e0": "Rayan", "is_confirmed_net": True, "is_sent": True, "is_delivered": True, "is_in_delivery": False, "is_return_or_failed": False, "ca_delivered": 1000, "ca_in_delivery": 0, "ca_preparation": 0, "ca_returned_failed": 0},
            {"order_id": "a5", "Wilaya": "Alger", "Livreur": "Yalidine", "Nom produit": "P1", "Source": "Meta", "SKU produit": "SKU1", "Affect\u00e9e \u00e0": "Rayan", "is_confirmed_net": True, "is_sent": True, "is_delivered": False, "is_in_delivery": False, "is_return_or_failed": True, "ca_delivered": 0, "ca_in_delivery": 0, "ca_preparation": 0, "ca_returned_failed": 1000},
        ]
    )


def test_livreur_wilaya_arbitrage_recommends_only_with_real_comparison():
    thresholds = {"delivery_orange": 0.65, "return_red": 0.25}
    out = compute_livreur_wilaya_arbitrage(build_advice_orders(), 2, thresholds)
    alger = out[out["wilaya"] == "Alger"].iloc[0]
    assert alger["meilleur_livreur_alternatif"] == "HHD 01"
    assert "D\u00e9l\u00e9guer" in alger["recommandation"]
    assert alger["expediees_alternatif"] == 2


def test_product_advice_adds_action_without_changing_numeric_values():
    products = pd.DataFrame({"produit": ["P1"], "commandes_recues": [20], "commandes_envoyees": [10], "taux_confirmation": [0.8], "taux_livraison_total": [0.5], "taux_retour": [0.1], "ca_livre": [10000], "ca_retours": [1000]})
    thresholds = {"confirmation_orange": 0.65, "confirmation_green": 0.75, "delivery_orange": 0.65, "delivery_green": 0.75, "return_orange": 0.15, "return_red": 0.25}
    out = add_product_advice(products, 10, thresholds)
    assert out["taux_livraison_total"].iloc[0] == 0.5
    assert out["action_recommandee"].iloc[0].startswith("V\u00e9rifier wilayas")


def test_source_and_sku_performance_are_volume_guarded():
    thresholds = {"confirmation_orange": 0.65, "confirmation_green": 0.75, "delivery_orange": 0.65, "delivery_green": 0.75, "return_orange": 0.15, "return_red": 0.25}
    source = compute_dimension_performance(build_advice_orders(), ["Source"], 3, thresholds)
    sku = compute_dimension_performance(build_advice_orders(), ["SKU produit"], 3, thresholds)
    assert source["source"].iloc[0] == "Meta"
    assert sku["sku_produit"].iloc[0] == "SKU1"
    assert "action_recommandee" in source.columns
    assert "produit_associe" in sku.columns


def test_priority_actions_have_required_advice_columns():
    thresholds = {"return_red": 0.25}
    products = pd.DataFrame({"produit": ["P1"], "commandes_recues": [20], "taux_retour": [0.3], "ca_retours": [5000]})
    actions = compute_priority_actions(products, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()), 10, 5, thresholds)
    assert set(["priorite", "objet", "probleme_detecte", "recommandation_concrete", "preuve_data", "impact_estime", "niveau_confiance"]).issubset(actions.columns)
    assert actions.iloc[0]["priorite"] == "Rouge"


def test_business_delivery_labels_are_unambiguous():
    rendered = prepare_dataframe_for_display(pd.DataFrame({"taux_livraison_total": [0.4167], "taux_transformation_reel": [0.2353]}), rename_columns=True)
    assert "Taux livraison sur exp\u00e9di\u00e9es" in rendered.columns
    assert "Taux transformation brute" in rendered.columns
    assert rendered["Taux livraison sur exp\u00e9di\u00e9es"].iloc[0] == "41.7 %"
    assert rendered["Taux transformation brute"].iloc[0] == "23.5 %"


def test_global_metrics_table_uses_distinct_delivery_and_transformation_labels():
    metrics = {
        "orders_received": 85,
        "orders_confirmed_net": 48,
        "confirmation_rate": 48 / 85,
        "orders_cancelled": 37,
        "cancellation_rate": 37 / 85,
        "orders_preparation": 0,
        "orders_sent": 48,
        "shipping_rate_global": 1.0,
        "orders_in_delivery": 0,
        "in_delivery_rate_on_sent": 0.0,
        "orders_delivered": 20,
        "orders_returned_failed": 28,
        "delivery_finalized_rate": 20 / 48,
        "delivery_total_rate_on_sent": 20 / 48,
        "return_rate_on_sent": 28 / 48,
        "transformation_real_rate": 20 / 85,
        "ca_delivered": 0,
        "ca_in_delivery": 0,
        "ca_preparation": 0,
        "ca_returned_failed": 0,
    }
    table = global_metrics_table(metrics)
    values = dict(zip(table["Indicateur"], table["Valeur"]))
    assert values["Taux livraison sur exp\u00e9di\u00e9es"] == "41.7 %"
    assert values["Taux transformation brute"] == "23.5 %"


def test_source_and_sku_performance_include_real_transformation_rate():
    thresholds = {"confirmation_orange": 0.65, "confirmation_green": 0.75, "delivery_orange": 0.65, "delivery_green": 0.75, "return_orange": 0.15, "return_red": 0.25}
    source = compute_dimension_performance(build_advice_orders(), ["Source"], 3, thresholds)
    sku = compute_dimension_performance(build_advice_orders(), ["SKU produit"], 3, thresholds)
    assert source["taux_livraison_total"].iloc[0] == 3 / 5
    assert source["taux_transformation_reel"].iloc[0] == 3 / 5
    assert sku["taux_transformation_reel"].iloc[0] == 3 / 5


def test_date_filter_uses_selected_business_date_without_changing_rates():
    df = pd.DataFrame(
        {
            "order_id": ["A", "B", "C"],
            "Crée le": pd.to_datetime(["2026-07-01", "2026-07-01", "2026-07-02"]),
            "Confirmée le": pd.to_datetime(["2026-07-05", None, "2026-07-06"]),
            "Expédiée le": pd.to_datetime([None, None, "2026-07-07"]),
        }
    )
    filtered, context = apply_date_filter(df, "Date de confirmation", pd.Timestamp("2026-07-05").date(), pd.Timestamp("2026-07-05").date())
    assert filtered["order_id"].tolist() == ["A"]
    assert context["missing_date_count"] == 1


def test_missing_date_summary_counts_invalid_dates_as_missing():
    df = pd.DataFrame(
        {
            "Crée le": ["2026-07-01", "date invalide"],
            "Affectée le": [None, "2026-07-02"],
            "Confirmée le": [None, None],
            "Expédiée le": ["2026-07-03", None],
        }
    )
    summary = summarize_missing_dates(df)
    values = dict(zip(summary["controle"], summary["valeur"]))
    assert values["Commandes sans date de création"] == 1
    assert values["Commandes sans date de confirmation"] == 2


def test_data_quality_warning_detects_p1_controls():
    checks = pd.DataFrame({"controle": ["Statuts inconnus"], "valeur": [1], "statut": ["Critique"]})
    assert data_quality_has_warning(checks) is True


def test_p2_amount_display_detects_price_total_panier_and_value_columns():
    df = pd.DataFrame(
        {
            "prix_unitaire": [14900],
            "Total commande": [29800],
            "panier_moyen_livre": [7450],
            "valeur_moyenne_retour": [1200],
            "valeur": [3],
        }
    )
    rendered = prepare_dataframe_for_display(df, rename_columns=False)
    assert rendered["prix_unitaire"].iloc[0] == "14 900 DA"
    assert rendered["Total commande"].iloc[0] == "29 800 DA"
    assert rendered["panier_moyen_livre"].iloc[0] == "7 450 DA"
    assert rendered["valeur_moyenne_retour"].iloc[0] == "1 200 DA"
    assert rendered["valeur"].iloc[0] == "3"


def test_p2_delivery_finalized_label_is_explicit():
    rendered = prepare_dataframe_for_display(pd.DataFrame({"taux_livraison_finalisees": [0.723]}), rename_columns=True)
    assert "Taux livraison finalisée hors en cours" in rendered.columns
    assert rendered["Taux livraison finalisée hors en cours"].iloc[0] == "72.3 %"


def test_p2_date_summary_can_label_full_and_filtered_scopes():
    df = pd.DataFrame({"Crée le": ["2026-07-01", None]})
    summary = summarize_missing_dates(df, "Fichier complet")
    row = summary[summary["controle"].eq("Commandes sans date de création")].iloc[0]
    assert row["valeur"] == 1
    assert row["details"].startswith("Fichier complet - 1 / 2")


def test_date_range_state_keeps_valid_custom_period_when_date_type_changes():
    df = pd.DataFrame(
        {
            "Crée le": pd.to_datetime(["2026-07-01", "2026-07-10"]),
            "Confirmée le": pd.to_datetime(["2026-07-20", "2026-07-21"]),
            "Expédiée le": pd.to_datetime(["2026-07-22", None]),
        }
    )
    min_date, max_date = available_date_bounds(df)
    saved = (pd.Timestamp("2026-07-01").date(), pd.Timestamp("2026-07-07").date())

    normalized, message = normalize_date_range(saved, min_date, max_date)

    assert normalized == saved
    assert message is None


def test_date_range_state_adjusts_only_when_outside_global_widget_limits():
    min_date = pd.Timestamp("2026-07-01").date()
    max_date = pd.Timestamp("2026-07-31").date()
    saved = (pd.Timestamp("2026-06-01").date(), pd.Timestamp("2026-08-01").date())

    normalized, message = normalize_date_range(saved, min_date, max_date)

    assert normalized == (min_date, max_date)
    assert "limites techniques" in message


def test_date_filter_does_not_reset_when_new_date_type_has_no_orders_in_period():
    df = pd.DataFrame(
        {
            "order_id": ["A", "B"],
            "Crée le": pd.to_datetime(["2026-07-01", "2026-07-02"]),
            "Confirmée le": pd.to_datetime(["2026-07-20", "2026-07-21"]),
        }
    )
    start = pd.Timestamp("2026-07-01").date()
    end = pd.Timestamp("2026-07-07").date()

    filtered, context = apply_date_filter(df, "Date de confirmation", start, end)

    assert filtered.empty
    assert context["start_date"] == start
    assert context["end_date"] == end
    assert context["kept_rows"] == 0


def test_prepare_dataframe_for_display_handles_duplicate_rate_columns():
    df = pd.DataFrame([[0.723022, 0.659016, 739500]], columns=["taux_livraison_total", "taux_livraison_total", "ca_livre"])

    rendered = prepare_dataframe_for_display(df, rename_columns=False)

    assert rendered.columns.tolist() == ["taux_livraison_total", "ca_livre"]
    assert rendered["taux_livraison_total"].iloc[0] == "72.3 %"
    assert rendered["ca_livre"].iloc[0] == "739 500 DA"


def test_render_data_table_with_duplicate_requested_columns_does_not_crash(monkeypatch):
    captured = {}

    def fake_dataframe(data, **kwargs):
        captured["data"] = data.data if hasattr(data, "data") else data
        return "rendered"

    monkeypatch.setattr(ui.st, "dataframe", fake_dataframe)
    monkeypatch.setattr(ui.st, "info", lambda message: None)
    df = pd.DataFrame(
        {
            "wilaya": ["Alger"],
            "commandes_envoyees": [10],
            "taux_en_cours_logistique": [0.1],
            "taux_livraison_total": [0.72],
            "ca_livre": [10000],
        }
    )
    columns = ["wilaya", "taux_en_cours_logistique", "taux_livraison_total", "taux_en_cours_logistique", "ca_livre"]

    result = render_data_table(df, columns, {"delivery_green": 0.75, "delivery_orange": 0.65}, "empty")

    assert result == "rendered"
    rendered = captured["data"]
    assert rendered.columns.tolist().count("taux_en_cours_logistique") == 1
    assert rendered["taux_en_cours_logistique"].iloc[0] == "10.0 %"
    assert rendered["taux_livraison_total"].iloc[0] == "72.0 %"
    assert rendered["ca_livre"].iloc[0] == "10 000 DA"


def test_top_wilayas_display_path_does_not_create_duplicate_columns(monkeypatch):
    captured = {}

    def fake_dataframe(data, **kwargs):
        captured["data"] = data.data if hasattr(data, "data") else data
        return "rendered"

    monkeypatch.setattr(ui.st, "dataframe", fake_dataframe)
    monkeypatch.setattr(ui.st, "info", lambda message: None)
    wilayas_ui = pd.DataFrame(
        {
            "wilaya": ["Alger", "Oran"],
            "commandes_recues": [20, 10],
            "commandes_envoyees": [15, 8],
            "livrees": [10, 4],
            "en_dispatch": [1, 1],
            "en_livraison": [2, 1],
            "en_cours_logistique": [3, 2],
            "taux_en_cours_logistique": [0.2, 0.25],
            "taux_transformation_reel": [0.5, 0.4],
            "taux_livraison_total": [0.67, 0.5],
            "taux_retour": [0.13, 0.25],
            "ca_livre": [20000, 10000],
            "ca_dispatch": [1000, 500],
            "produit_dominant": ["P1", "P2"],
            "livreur_dominant": ["Yalidine", "HHD 01"],
            "fiabilite_volume": ["OK", "OK"],
        }
    )
    top_wilaya_cols = ["wilaya", "commandes_recues", "commandes_envoyees", "livrees", "en_dispatch", "en_livraison", "en_cours_logistique", "taux_en_cours_logistique", "taux_transformation_reel", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "ca_dispatch", "produit_dominant", "livreur_dominant", "fiabilite_volume"]

    result = render_data_table(sort_for_display(wilayas_ui, ["ca_livre"]).head(10), top_wilaya_cols, {"delivery_green": 0.75, "delivery_orange": 0.65, "return_orange": 0.15, "return_red": 0.25}, "empty")

    assert result == "rendered"
    rendered = captured["data"]
    assert rendered.columns.tolist().count("taux_en_cours_logistique") == 1
    assert rendered["taux_en_cours_logistique"].iloc[0] == "20.0 %"


def test_analysis_period_selector_initializes_active_value_and_form_draft_for_first_file():
    state = {}
    min_date = pd.Timestamp("2026-06-01").date()
    max_date = pd.Timestamp("2026-07-06").date()

    period, message = initialize_analysis_period_selector(state, ("export.xlsx", 123), min_date, max_date)

    # Default period: the last 30 days of the file
    last_30 = period_from_preset("30 derniers jours", min_date, max_date)
    assert period == last_30
    assert message is None
    assert state[ANALYSIS_PERIOD_VALUE_KEY] == last_30
    assert state[ANALYSIS_PERIOD_DRAFT_KEY] == last_30
    assert state[ANALYSIS_PERIOD_PRESET_KEY] == "30 derniers jours"
    assert state[ANALYSIS_PERIOD_FILE_KEY] == ("export.xlsx", 123)


def test_analysis_period_quick_presets_are_anchored_on_latest_export_date():
    min_date = pd.Timestamp("2026-06-01").date()
    max_date = pd.Timestamp("2026-07-06").date()

    assert period_from_preset("Aujourd'hui", min_date, max_date) == (max_date, max_date)
    assert period_from_preset("Hier", min_date, max_date) == (pd.Timestamp("2026-07-05").date(), pd.Timestamp("2026-07-05").date())
    assert period_from_preset("7 derniers jours", min_date, max_date) == (pd.Timestamp("2026-06-30").date(), max_date)
    assert period_from_preset("30 derniers jours", min_date, max_date) == (pd.Timestamp("2026-06-07").date(), max_date)
    assert period_from_preset("Toute la p\u00e9riode", min_date, max_date) == (min_date, max_date)


def test_analysis_period_apply_commits_a_quick_preset_without_changing_date_type_state():
    min_date = pd.Timestamp("2026-06-01").date()
    max_date = pd.Timestamp("2026-07-06").date()
    state = {
        ANALYSIS_PERIOD_FILE_KEY: ("export.xlsx", 123),
        ANALYSIS_PERIOD_VALUE_KEY: (min_date, max_date),
        ANALYSIS_PERIOD_DRAFT_KEY: (min_date, max_date),
        ANALYSIS_PERIOD_PRESET_KEY: "7 derniers jours",
    }

    period, message = apply_analysis_period_selection(state, min_date, max_date)
    rerun_period, rerun_message = initialize_analysis_period_selector(state, ("export.xlsx", 123), min_date, max_date)

    expected = (pd.Timestamp("2026-06-30").date(), max_date)
    assert period == expected
    assert state[ANALYSIS_PERIOD_VALUE_KEY] == expected
    assert state[ANALYSIS_PERIOD_DRAFT_KEY] == expected
    assert rerun_period == expected
    assert message is None
    assert rerun_message is None


def test_analysis_period_apply_uses_the_calendar_draft_as_a_custom_period():
    min_date = pd.Timestamp("2026-06-01").date()
    max_date = pd.Timestamp("2026-07-06").date()
    custom = (pd.Timestamp("2026-06-20").date(), pd.Timestamp("2026-06-30").date())
    state = {
        ANALYSIS_PERIOD_FILE_KEY: ("export.xlsx", 123),
        ANALYSIS_PERIOD_VALUE_KEY: (min_date, max_date),
        ANALYSIS_PERIOD_DRAFT_KEY: custom,
        ANALYSIS_PERIOD_PRESET_KEY: "Toute la p\u00e9riode",
    }

    period, message = apply_analysis_period_selection(state, min_date, max_date)

    assert period == custom
    assert state[ANALYSIS_PERIOD_VALUE_KEY] == custom
    assert state[ANALYSIS_PERIOD_DRAFT_KEY] == custom
    assert state[ANALYSIS_PERIOD_PRESET_KEY] == "Personnalis\u00e9e"
    assert message is None


def test_analysis_period_selector_survives_rerun_and_resets_only_for_a_new_file():
    min_date = pd.Timestamp("2026-06-01").date()
    max_date = pd.Timestamp("2026-07-06").date()
    custom = (pd.Timestamp("2026-06-20").date(), pd.Timestamp("2026-06-30").date())
    state = {
        ANALYSIS_PERIOD_FILE_KEY: ("export.xlsx", 123),
        ANALYSIS_PERIOD_VALUE_KEY: custom,
        ANALYSIS_PERIOD_DRAFT_KEY: custom,
        ANALYSIS_PERIOD_PRESET_KEY: "Personnalis\u00e9e",
    }

    rerun_period, _ = initialize_analysis_period_selector(state, ("export.xlsx", 123), min_date, max_date)
    new_file_period, _ = initialize_analysis_period_selector(state, ("new.xlsx", 456), min_date, max_date)

    assert rerun_period == custom
    assert new_file_period == period_from_preset("30 derniers jours", min_date, max_date)
    assert state[ANALYSIS_PERIOD_PRESET_KEY] == "30 derniers jours"


def test_analysis_period_invalid_saved_value_is_adjusted_before_form_widgets():
    min_date = pd.Timestamp("2026-06-01").date()
    max_date = pd.Timestamp("2026-07-06").date()
    state = {
        ANALYSIS_PERIOD_FILE_KEY: ("export.xlsx", 123),
        ANALYSIS_PERIOD_VALUE_KEY: (pd.Timestamp("2026-05-01").date(), pd.Timestamp("2026-08-01").date()),
        ANALYSIS_PERIOD_DRAFT_KEY: (pd.Timestamp("2026-05-01").date(), pd.Timestamp("2026-08-01").date()),
        ANALYSIS_PERIOD_PRESET_KEY: "Personnalis\u00e9e",
    }

    period, message = initialize_analysis_period_selector(state, ("export.xlsx", 123), min_date, max_date)

    assert period == (min_date, max_date)
    assert state[ANALYSIS_PERIOD_VALUE_KEY] == (min_date, max_date)
    assert "limites techniques" in message


def test_normalize_analysis_period_does_not_mutate_state():
    min_date = pd.Timestamp("2026-06-01").date()
    max_date = pd.Timestamp("2026-07-06").date()

    period, message = normalize_analysis_period(
        (pd.Timestamp("2026-06-20").date(), pd.Timestamp("2026-06-30").date()),
        min_date,
        max_date,
    )

    assert period == (pd.Timestamp("2026-06-20").date(), pd.Timestamp("2026-06-30").date())
    assert message is None


def test_filter_state_drops_a_status_that_is_unavailable_in_the_new_period():
    state = {"filter_order_status": ["Livr\u00e9e"]}

    selected = sanitize_multiselect_state(state, "filter_order_status", ["En pr\u00e9paration"])

    assert selected == []
    assert state["filter_order_status"] == []


def test_filter_state_preserves_values_that_remain_available():
    state = {"filter_order_status": ["En livraison"]}

    selected = sanitize_multiselect_state(
        state,
        "filter_order_status",
        ["En livraison", "En pr\u00e9paration"],
    )

    assert selected == ["En livraison"]
    assert state["filter_order_status"] == ["En livraison"]



def test_amount_totals_counts_each_order_once_and_excludes_cancelled_from_confirmed_ca():
    frame = pd.DataFrame(
        {
            "order_id": ["A", "A", "B"],
            "ca_total": [100_000, 100_000, 50_000],
            "is_confirmed_net": [True, True, False],
        }
    )
    totals = amount_totals(
        frame,
        {"orders_received": 2, "orders_delivered": 1, "orders_returned_failed": 0, "ca_delivered": 100_000},
    )

    assert totals["ca_total_orders"] == 150_000
    assert totals["ca_confirmed"] == 100_000
    assert totals["panier_moyen_livre"] == 100_000


def test_owner_money_sections_are_compact_ordered_and_based_on_received_ca():
    metrics = {
        "orders_received": 100,
        "orders_confirmed_net": 90,
        "orders_preparation": 10,
        "orders_dispatch": 15,
        "orders_in_delivery": 5,
        "orders_delivered": 50,
        "orders_returned_failed": 10,
        "ca_preparation": 100_000,
        "ca_dispatch": 150_000,
        "ca_in_delivery": 50_000,
        "ca_delivered": 500_000,
        "ca_returned_failed": 100_000,
    }
    amounts = {
        "ca_total_orders": 1_000_000,
        "ca_confirmed": 900_000,
        "panier_moyen_livre": 10_000,
    }

    sections = owner_money_sections(metrics, amounts)
    assert [title for title, _, _, _ in sections] == [
        "CA total des commandes re\u00e7ues",
        "CA confirm\u00e9",
        "CA en pr\u00e9paration",
        "CA en dispatch",
        "CA en cours de livraison",
        "CA livr\u00e9 finalis\u00e9",
        "Perte CA retours",
        "Panier moyen livr\u00e9",
    ]

    cards = {title: (value, note) for title, value, note, _ in sections}
    assert cards["CA confirm\u00e9"] == ("900 000 DA", "90 commandes \u00b7 90.0 % du CA re\u00e7u")
    assert cards["CA en pr\u00e9paration"] == ("100 000 DA", "10 commandes \u00b7 10.0 % du CA re\u00e7u")
    assert cards["CA livr\u00e9 finalis\u00e9"] == ("500 000 DA", "50 commandes \u00b7 50.0 % du CA re\u00e7u")
    assert cards["Perte CA retours"] == ("100 000 DA", "10 commandes \u00b7 10.0 % du CA re\u00e7u")
    assert cards["Panier moyen livr\u00e9"] == ("10 000 DA", "50 commandes livr\u00e9es finalis\u00e9es")
    assert sum(metrics[key] for key in ("ca_preparation", "ca_dispatch", "ca_in_delivery", "ca_delivered", "ca_returned_failed")) == amounts["ca_confirmed"]

def test_owner_kpi_sections_follow_cod_funnel_and_show_denominators():
    metrics = {
        "orders_received": 700,
        "orders_confirmed_net": 580,
        "confirmation_rate": 580 / 700,
        "orders_cancelled": 120,
        "cancellation_rate": 120 / 700,
        "orders_in_confirmation": 60,
        "orders_preparation": 70,
        "preparation_blockage_rate": 70 / 520,
        "orders_sent": 450,
        "orders_dispatch": 30,
        "orders_in_delivery": 50,
        "orders_delivered": 300,
        "delivery_total_rate_on_sent": 300 / 450,
        "transformation_real_rate": 300 / 700,
    }
    thresholds = {
        "confirmation_green": 0.70,
        "confirmation_orange": 0.60,
        "cancellation_orange": 0.15,
        "cancellation_red": 0.25,
        "delivery_green": 0.70,
        "delivery_orange": 0.60,
        "preparation_orange": 0.05,
        "preparation_red": 0.15,
    }

    sections = owner_kpi_sections(metrics, thresholds)
    assert [title for title, _, _, _ in sections] == [
        "Commandes re\u00e7ues",
        "Taux confirm\u00e9",
        "Taux en cours de confirmation",
        "Taux en pr\u00e9paration",
        "Taux en dispatch",
        "Taux en cours de livraison",
        "Taux livr\u00e9",
        "Taux de transformation brute",
        "Taux de transformation nette",
        "Taux annul\u00e9",
    ]

    cards = {title: (value, note) for title, value, note, _ in sections}
    assert cards["Taux confirm\u00e9"] == ("74.3 %", "520 commandes confirm\u00e9es\nBase : 700 re\u00e7ues")
    assert cards["Taux en cours de confirmation"] == ("8.6 %", "60 commandes en confirmation\nBase : 700 re\u00e7ues")
    assert cards["Taux en pr\u00e9paration"] == ("13.5 %", "70 commandes en pr\u00e9paration\nBase : 520 confirm\u00e9es")
    assert cards["Taux en dispatch"] == ("6.7 %", "30 commandes en dispatch\nBase : 450 exp\u00e9di\u00e9es")
    assert cards["Taux en cours de livraison"] == ("11.1 %", "50 commandes en livraison\nBase : 450 exp\u00e9di\u00e9es")
    assert cards["Taux livr\u00e9"] == ("66.7 %", "300 commandes livr\u00e9es\nBase : 450 exp\u00e9di\u00e9es")
    assert cards["Taux de transformation brute"] == ("42.9 %", "300 livr\u00e9es / 700 re\u00e7ues")
    # nette: 300 delivered / (700 received - 120 cancelled = 580)
    assert cards["Taux de transformation nette"] == ("51.7 %", "300 livr\u00e9es / 580 re\u00e7ues hors annul\u00e9es")
    assert cards["Taux annul\u00e9"] == ("17.1 %", "120 commandes annul\u00e9es\nBase : 700 re\u00e7ues")
    assert sum(float(cards[title][0].replace(" %", "")) for title in ("Taux confirm\u00e9", "Taux en cours de confirmation", "Taux annul\u00e9")) == 100.0


def test_owner_kpi_reception_cards_are_exclusive_and_total_exactly_100_percent():
    metrics = {
        "orders_received": 38,
        "orders_confirmed_net": 30,
        "orders_in_confirmation": 8,
        "orders_unclassified": 0,
        "orders_cancelled": 8,
        "orders_preparation": 2,
        "orders_sent": 20,
        "orders_dispatch": 0,
        "orders_in_delivery": 20,
        "orders_delivered": 0,
        "confirmation_rate": 30 / 38,
        "cancellation_rate": 8 / 38,
        "delivery_total_rate_on_sent": 0,
        "transformation_real_rate": 0,
    }
    thresholds = {
        "confirmation_green": 0.70,
        "confirmation_orange": 0.60,
        "cancellation_orange": 0.15,
        "cancellation_red": 0.25,
        "delivery_green": 0.70,
        "delivery_orange": 0.60,
        "preparation_orange": 0.05,
        "preparation_red": 0.15,
    }

    cards = {title: value for title, value, _, _ in owner_kpi_sections(metrics, thresholds)}

    assert cards["Taux confirmé"] == "57.8 %"
    assert cards["Taux en cours de confirmation"] == "21.1 %"
    assert cards["Taux annulé"] == "21.1 %"
    assert sum(float(cards[title].replace(" %", "")) for title in ("Taux confirmé", "Taux en cours de confirmation", "Taux annulé")) == 100.0


def test_preparation_metrics_by_dimension_keeps_numeric_rates():
    frame = build_advice_orders().copy()
    frame["is_preparation"] = [True, False, False, False, False]
    frame["is_sent"] = [False, True, True, True, True]
    result = preparation_metrics_by_dimension(frame, "Affect\u00e9e \u00e0", "confirmatrice")

    rayan = result.loc[result["confirmatrice"].eq("Rayan")].iloc[0]
    assert rayan["en_preparation"] == 1
    assert rayan["taux_preparation"] == 0.2

def test_owner_priority_selects_the_largest_operational_blockage():
    label, count, amount = owner_priority(
        {
            "orders_preparation": 12,
            "ca_preparation": 120_000,
            "orders_logistics": 25,
            "ca_logistics": 250_000,
            "orders_returned_failed": 8,
            "ca_returned_failed": 80_000,
        }
    )
    assert (label, count, amount) == ("commandes en cours logistique", 25, 250_000)


def test_top_label_excludes_weak_samples():
    frame = pd.DataFrame(
        {
            "produit": ["Petit echantillon", "Produit fiable"],
            "commandes_recues": [2, 12],
            "ca_livre": [200_000, 150_000],
        }
    )
    assert top_label(frame, "produit", "ca_livre", "commandes_recues", 10) == "Produit fiable"
