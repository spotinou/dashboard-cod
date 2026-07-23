import pandas as pd

from src.data_loader import prepare_dataframe, validate_columns
from src.metrics import compute_global_metrics
from src.ui import apply_date_filter, build_active_filters_summary, prepare_dataframe_for_display
from src.validation import compute_validation_checks


def p3_raw_orders():
    return pd.DataFrame(
        [
            {
                "Référence commande": "A",
                "Statut commande": "Annulée",
                "Total commande": "1000",
                "Nom produit": "P1",
                "Wilaya": "Alger",
                "Livreur": "",
                "Affectée à": "Rayan",
                "Crée le": "2026-07-01",
            },
            {
                "Référence commande": "B",
                "Statut commande": "Livrée",
                "Total commande": "2000",
                "Nom produit": "P1",
                "Wilaya": "Alger",
                "Livreur": "Yalidine",
                "Affectée à": "Rayan",
                "Crée le": "2026-07-01",
                "Expédiée le": "2026-07-02",
                "Livrée le": "2026-07-03",
            },
            {
                "Référence commande": "C",
                "Statut commande": "Statut nouveau",
                "Total commande": "3000",
                "Nom produit": "P2",
                "Wilaya": "Oran",
                "Livreur": "",
                "Affectée à": "Rayane",
                "Crée le": "2026-07-01",
            },
        ]
    )


def test_p3_unknown_status_stays_received_and_is_critical_validation():
    df = prepare_dataframe(p3_raw_orders())
    metrics = compute_global_metrics(df)
    checks = compute_validation_checks(df, metrics)
    unknown = df[df["order_id"].eq("C")].iloc[0]

    assert metrics["orders_received"] == 3
    assert metrics["orders_confirmed_net"] == 2
    assert bool(unknown["is_confirmed_net"]) is True
    assert bool(unknown["is_cancelled"]) is False
    assert bool(unknown["is_delivered"]) is False
    assert bool(unknown["is_return_or_failed"]) is False
    assert bool(unknown["is_sent"]) is False
    row = checks[checks["controle"].eq("Statuts inconnus")].iloc[0]
    assert row["valeur"] == 1
    assert row["statut"] == "Critique"


def test_p3_confirmed_net_equals_received_minus_cancelled():
    df = prepare_dataframe(p3_raw_orders())
    metrics = compute_global_metrics(df)
    assert metrics["orders_received"] == metrics["orders_cancelled"] + metrics["orders_confirmed_net"]


def test_p3_duplicate_order_id_is_reported_without_dropping_rows():
    raw = p3_raw_orders()
    raw.loc[len(raw)] = raw.iloc[1].copy()
    df = prepare_dataframe(raw)
    metrics = compute_global_metrics(df)
    checks = compute_validation_checks(df, metrics)

    assert len(df) == 4
    duplicate = checks[checks["controle"].eq("Doublons ID commande")].iloc[0]
    assert duplicate["valeur"] == 1
    assert duplicate["statut"] == "Critique"


def test_p3_date_fallback_ag_ak_works_and_warns():
    raw = p3_raw_orders().drop(columns=["Crée le"]).copy()
    while len(raw.columns) < 32:
        raw[f"unused_{len(raw.columns)}"] = None
    raw.insert(32, "Legacy AG", ["2026-07-05"] * len(raw))

    warnings = validate_columns(raw.head(2))
    df = prepare_dataframe(raw)

    assert pd.notna(df["Crée le"]).all()
    assert df.attrs.get("date_fallback_columns", {}).get("Crée le") == "Legacy AG"
    assert any("Legacy AG" in warning for warning in warnings)


def test_p3_missing_selected_dates_are_filtered_and_counted():
    df = pd.DataFrame(
        {
            "order_id": ["A", "B", "C"],
            "Crée le": pd.to_datetime(["2026-07-01", "2026-07-02", "2026-07-03"]),
            "Confirmée le": pd.to_datetime(["2026-07-05", None, "2026-07-07"]),
        }
    )

    filtered, context = apply_date_filter(
        df,
        "Date de confirmation",
        pd.Timestamp("2026-07-05").date(),
        pd.Timestamp("2026-07-06").date(),
    )

    assert filtered["order_id"].tolist() == ["A"]
    assert context["missing_date_count"] == 1
    assert context["kept_rows"] == 1


def test_p3_display_formats_rates_amounts_and_invalid_values():
    rendered = prepare_dataframe_for_display(
        pd.DataFrame(
            {
                "taux_test": [0.472, None, float("inf")],
                "ca_livre": [1828500, None, float("inf")],
            }
        ),
        rename_columns=False,
    )

    assert rendered["taux_test"].tolist() == ["47.2 %", "—", "—"]
    assert rendered["ca_livre"].tolist() == ["1 828 500 DA", "—", "—"]


def test_p3_active_filter_summary_is_compact_and_lists_selected_filters():
    context = {
        "selected_date_type": "Date de confirmation",
        "start_date": pd.Timestamp("2026-07-01").date(),
        "end_date": pd.Timestamp("2026-07-07").date(),
        "active_secondary_filters": [
            {"label": "Produit", "values": ["Porte chaussure M"], "count": 1},
            {"label": "Source", "values": ["Facebook"], "count": 1},
        ],
    }

    summary = build_active_filters_summary(context)

    assert summary.startswith("Filtres actifs :")
    assert "Date d'analyse : Date de confirmation" in summary
    assert "Periode : 2026/07/01 - 2026/07/07" in summary
    assert "Produit : Porte chaussure M" in summary
    assert "Source : Facebook" in summary


def test_p3_active_filter_summary_handles_no_secondary_filter():
    summary = build_active_filters_summary(
        {
            "selected_date_type": "Date de création",
            "start_date": pd.Timestamp("2026-07-01").date(),
            "end_date": pd.Timestamp("2026-07-07").date(),
            "active_secondary_filters": [],
        }
    )
    assert "aucun filtre secondaire" in summary
