import pandas as pd
import pytest

from src.data_loader import prepare_dataframe, validate_columns
from src.metrics import compute_confirmation_metrics, compute_global_metrics, compute_livreur_metrics, compute_wilaya_metrics
from src.validation import compute_validation_checks


def build_df():
    return pd.DataFrame(
        [
            {"Référence commande": "A", "Statut commande": "Annulée", "Confirmée le": "2026-01-01 10:00:00", "Annulée le": "2026-01-02 10:00:00", "Total commande": "1000", "Nom produit": "P1", "Wilaya": "Alger", "Livreur": "", "Affectée à": "Rayan", "Crée le": "2026-01-01"},
            {"Référence commande": "B", "Statut commande": "En préparation", "Total commande": "2000", "Nom produit": "P1", "Wilaya": "Alger", "Livreur": "yalidin colis", "Affectée à": "Rayan", "Crée le": "2026-01-01", "Confirmée le": "2026-01-01"},
            {"Référence commande": "C", "Statut commande": "Livrée", "Expédiée le": "2026-01-01", "Livrée le": "2026-01-03", "Total commande": "3000", "Nom produit": "P2", "Wilaya": "Oran", "Livreur": "yalidin colis", "Affectée à": "Rayan", "Crée le": "2026-01-01"},
            {"Référence commande": "D", "Statut commande": "Encaissée", "Expédiée le": "2026-01-01", "Encaissée le": "2026-01-03", "Total commande": "4000", "Nom produit": "P2", "Wilaya": "Oran", "Livreur": "HHD 01", "Affectée à": "Rayan", "Crée le": "2026-01-01"},
            {"Référence commande": "E", "Statut commande": "En retour", "Expédiée le": "2026-01-01", "Total commande": "5000", "Nom produit": "P2", "Wilaya": "Oran", "Livreur": "HHD 01", "Affectée à": "Rayan", "Crée le": "2026-01-01"},
            {"Référence commande": "F", "Statut commande": "En livraison", "Expédiée le": "2026-01-01", "Echouée le": "2026-01-04", "Total commande": "6 000", "Nom produit": "P2", "Wilaya": "Oran", "Livreur": "HHD 01", "Affectée à": "Rayan", "Crée le": "01/01/2026"},
        ]
    )


def test_cod_classification_and_rates():
    df = prepare_dataframe(build_df())
    metrics = compute_global_metrics(df)
    assert metrics["orders_received"] == 6
    assert metrics["orders_cancelled"] == 1
    assert metrics["orders_confirmed_net"] == 5
    assert metrics["orders_preparation"] == 1
    assert metrics["orders_sent"] == 4
    assert metrics["orders_delivered"] == 2
    assert metrics["orders_returned_failed"] == 2
    assert metrics["delivery_finalized_rate"] == 0.5
    assert metrics["return_rate_on_sent"] == 0.5
    assert metrics["ca_delivered"] == 7000


def test_yalidine_preparation_is_excluded_from_livreur_kpis():
    df = prepare_dataframe(build_df())
    livreurs = compute_livreur_metrics(df)
    yalidine = livreurs[livreurs["livreur"] == "Yalidine"].iloc[0]
    assert yalidine["commandes_envoyees"] == 1
    assert yalidine["livrees"] == 1


def test_parsing_text_numbers_dates_and_missing_values():
    df = prepare_dataframe(build_df())
    assert df.loc[df["order_id"] == "F", "ca_total"].iloc[0] == 6000
    assert pd.notna(df.loc[df["order_id"] == "F", "Crée le"].iloc[0])
    assert df.loc[df["order_id"] == "A", "Livreur"].iloc[0] == "Non renseigné"


def test_validation_checks_cod_equalities():
    df = prepare_dataframe(build_df())
    metrics = compute_global_metrics(df)
    checks = compute_validation_checks(df, metrics)
    required = checks[checks["controle"].str.contains("=")]
    assert set(required["statut"]) == {"OK"}


def test_livreur_metrics_keep_columns_when_no_sent_orders():
    df = prepare_dataframe(build_df())
    filtered = df[df["is_preparation"]]
    livreurs = compute_livreur_metrics(filtered)
    assert livreurs.empty
    assert list(livreurs.columns) == [
        "livreur",
        "commandes_envoyees",
        "livrees",
        "en_dispatch",
        "en_livraison",
        "en_cours_logistique",
        "retours",
        "taux_livraison_finalisees",
        "taux_livraison_total",
        "taux_en_cours_logistique",
        "taux_retour",
        "ca_livre",
        "ca_dispatch",
        "ca_bloque_livraison",
        "ca_en_cours_logistique",
        "ca_retours",
        "panier_moyen_livre",
        "decision_auto",
    ]



def test_new_priority_one_kpis_are_computed():
    df = prepare_dataframe(build_df())
    metrics = compute_global_metrics(df)
    assert metrics["shipping_rate_global"] == 4 / 5
    assert metrics["delivery_total_rate_on_sent"] == 2 / 4
    assert metrics["in_delivery_rate_on_sent"] == 0 / 4
    assert metrics["transformation_real_rate"] == 2 / 6
    assert metrics["ca_returned_failed"] == 11000

    livreurs = compute_livreur_metrics(df)
    hhd = livreurs[livreurs["livreur"] == "HHD 01"].iloc[0]
    assert hhd["ca_retours"] == 11000
    assert hhd["panier_moyen_livre"] == 4000


def test_sku_and_source_are_normalized_for_filters():
    raw = build_df()
    raw["SKU produit"] = ["", "SKU-1", None, "SKU-2", "SKU-2", "SKU-3"]
    raw["Source"] = ["", "Google Sheet", None, "Facebook", "Facebook", ""]
    df = prepare_dataframe(raw)
    assert "SKU produit" in df.columns
    assert df.loc[df["order_id"] == "A", "SKU produit"].iloc[0] == "Non renseign\u00e9"
    assert df.loc[df["order_id"] == "C", "Source"].iloc[0] == "Non renseign\u00e9"


def test_transformation_real_rate_is_exposed_in_business_tables():
    df = prepare_dataframe(build_df())

    confirmation = compute_confirmation_metrics(df)
    rayan = confirmation[confirmation["confirmatrice"] == "Rayan"].iloc[0]
    assert rayan["taux_livraison_total"] == 2 / 4
    assert rayan["taux_transformation_reel"] == 2 / 6

    wilayas = compute_wilaya_metrics(df)
    oran = wilayas[wilayas["wilaya"] == "Oran"].iloc[0]
    assert oran["taux_livraison_total"] == 2 / 4
    assert oran["taux_transformation_reel"] == 2 / 4


def test_date_columns_fallback_to_excel_ag_ak_positions():
    raw = build_df().drop(columns=["Crée le"]).copy()
    creation_values = ["2026-02-01"] * len(raw)
    while len(raw.columns) < 32:
        raw[f"unused_{len(raw.columns)}"] = None
    raw.insert(32, "Legacy AG", creation_values)
    df = prepare_dataframe(raw)
    assert pd.notna(df["Crée le"]).all()
    assert df["Crée le"].dt.date.astype(str).iloc[0] == "2026-02-01"


def test_confirmed_net_is_received_minus_cancelled_and_unknown_is_unclassified():
    raw = build_df()
    raw.loc[len(raw)] = {
        "R\u00e9f\u00e9rence commande": "G",
        "Statut commande": "Statut nouveau",
        "Total commande": "7000",
        "Nom produit": "P3",
        "Wilaya": "Alger",
        "Livreur": "",
        "Affect\u00e9e \u00e0": "Rayan",
        "Cr\u00e9e le": "2026-01-01",
    }
    df = prepare_dataframe(raw)
    metrics = compute_global_metrics(df)
    assert metrics["orders_received"] == 7
    assert metrics["orders_cancelled"] == 1
    assert metrics["orders_confirmed_net"] == 6
    assert metrics["orders_unclassified"] == 1
    assert metrics["orders_confirmed_net"] == metrics["orders_sent"] + metrics["orders_preparation"] + metrics["orders_unclassified"]


def test_validation_reports_unknown_status_unclassified_and_duplicate_ids():
    raw = build_df()
    raw.loc[len(raw)] = {
        "R\u00e9f\u00e9rence commande": "G",
        "Statut commande": "Statut nouveau",
        "Total commande": "7000",
        "Nom produit": "P3",
        "Wilaya": "Alger",
        "Livreur": "",
        "Affect\u00e9e \u00e0": "Rayan",
        "Cr\u00e9e le": "2026-01-01",
    }
    raw.loc[len(raw)] = raw.iloc[1].copy()
    df = prepare_dataframe(raw)
    metrics = compute_global_metrics(df)
    checks = compute_validation_checks(df, metrics)
    values = dict(zip(checks["controle"], checks["valeur"]))
    statuses = dict(zip(checks["controle"], checks["statut"]))
    assert values["Statuts inconnus"] == 1
    assert statuses["Statuts inconnus"] == "Critique"
    assert values["Commandes non classees / statut a verifier"] == 1
    assert statuses["Doublons ID commande"] == "Critique"
    duplicate_details = checks.loc[checks["controle"].eq("Doublons ID commande"), "details"].iloc[0]
    assert "KPI CA/produit/SKU" in duplicate_details


def test_validation_reports_date_fallback_usage():
    raw = build_df().drop(columns=["Cr\u00e9e le"]).copy()
    while len(raw.columns) < 32:
        raw[f"unused_{len(raw.columns)}"] = None
    raw.insert(32, "Legacy AG", ["2026-02-01"] * len(raw))
    df = prepare_dataframe(raw)
    metrics = compute_global_metrics(df)
    checks = compute_validation_checks(df, metrics)
    row = checks[checks["controle"].eq("Mapping dates AG-AK")].iloc[0]
    assert row["valeur"] >= 1
    assert row["statut"] == "A verifier"
    assert "positions AG-AK" in row["details"]


def test_validate_columns_reports_date_fallback_source():
    raw = build_df().drop(columns=["Crée le"]).copy()
    while len(raw.columns) < 32:
        raw[f"unused_{len(raw.columns)}"] = None
    raw.insert(32, "Legacy AG", ["2026-02-01"] * len(raw))
    warnings = validate_columns(raw.head(2))
    assert any("Crée le" in warning and "Legacy AG" in warning for warning in warnings)




def dispatch_raw_orders() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Reference commande": "D1", "Statut commande": "En dispatch", "Total commande": "1000", "Nom produit": "P1", "Wilaya": "Alger", "Livreur": "Yalidine", "Affectee a": "Rayan", "Cree le": "2026-07-01"},
            {"Reference commande": "D2", "Statut commande": "en_dispatch", "Total commande": "2000", "Nom produit": "P1", "Wilaya": "Alger", "Livreur": "Yalidine", "Affectee a": "Rayan", "Cree le": "2026-07-01"},
            {"Reference commande": "D3", "Statut commande": "En dispach.", "Total commande": "3000", "Nom produit": "P1", "Wilaya": "Alger", "Livreur": "Yalidine", "Affectee a": "Rayan", "Cree le": "2026-07-01"},
        ]
    )


def test_dispatch_status_variants_are_known_and_sent_not_finalized():
    df = prepare_dataframe(dispatch_raw_orders())
    metrics = compute_global_metrics(df)
    checks = compute_validation_checks(df, metrics)

    assert set(df["status_norm"]) == {"dispatch"}
    assert df["is_status_known"].all()
    assert df["is_dispatch"].all()
    assert df["is_sent"].all()
    assert not df["is_cancelled"].any()
    assert not df["is_preparation"].any()
    assert not df["is_delivered"].any()
    assert not df["is_return_or_failed"].any()
    assert not df["is_unclassified"].any()
    assert metrics["orders_received"] == 3
    assert metrics["orders_confirmed_net"] == 3
    assert metrics["orders_dispatch"] == 3
    assert metrics["orders_sent"] == 3
    assert metrics["orders_unclassified"] == 0
    assert metrics["ca_dispatch"] == 6000
    assert checks.loc[checks["controle"].eq("Statuts inconnus"), "valeur"].iloc[0] == 0


def build_dispatch_audit_like_dataset() -> pd.DataFrame:
    rows = []

    def add(status: str, count: int, amount: int = 1000):
        for _ in range(count):
            idx = len(rows) + 1
            row = {
                "Reference commande": f"ORD-{idx}",
                "Statut commande": status,
                "Total commande": str(amount),
                "Nom produit": "P1",
                "Wilaya": "Alger",
                "Livreur": "Yalidine",
                "Affectee a": "Rayan",
                "Cree le": "2026-07-01",
            }
            if status in {"Livree", "Encaissee", "En retour", "Retournee", "En livraison"}:
                row["Expediee le"] = "2026-07-02"
            rows.append(row)

    add("Annulee", 2)
    add("En preparation", 38)
    add("En dispatch", 60)
    add("En livraison", 17)
    add("Livree", 254)
    add("En retour", 115)
    return pd.DataFrame(rows)


def test_dispatch_audit_like_dataset_matches_expected_funnel():
    df = prepare_dataframe(build_dispatch_audit_like_dataset())
    metrics = compute_global_metrics(df)
    checks = compute_validation_checks(df, metrics)

    assert metrics["orders_received"] == 486
    assert metrics["orders_cancelled"] == 2
    assert metrics["orders_confirmed_net"] == 484
    assert metrics["orders_preparation"] == 38
    assert metrics["orders_dispatch"] == 60
    assert metrics["orders_sent"] == 446
    assert metrics["orders_delivered"] == 254
    assert metrics["orders_in_delivery"] == 17
    assert metrics["orders_returned_failed"] == 115
    assert metrics["orders_unclassified"] == 0
    assert round(metrics["shipping_rate_global"], 3) == round(446 / 484, 3)
    assert round(metrics["delivery_total_rate_on_sent"], 3) == round(254 / 446, 3)
    assert round(metrics["return_rate_on_sent"], 3) == round(115 / 446, 3)
    assert round(metrics["transformation_real_rate"], 3) == round(254 / 486, 3)
    assert checks.loc[checks["controle"].eq("Statuts inconnus"), "valeur"].iloc[0] == 0
    assert checks.loc[checks["controle"].eq("Commandes non classees / statut a verifier"), "valeur"].iloc[0] == 0
    equality_statuses = checks[checks["controle"].str.contains("=", regex=False)]["statut"].tolist()
    assert set(equality_statuses) == {"OK"}


def test_dispatch_status_filter_recomputes_kpis_without_crashing():
    df = prepare_dataframe(build_dispatch_audit_like_dataset())
    filtered = df[df["Statut commande"].eq("En dispatch")]
    metrics = compute_global_metrics(filtered)

    assert metrics["orders_received"] == 60
    assert metrics["orders_confirmed_net"] == 60
    assert metrics["orders_dispatch"] == 60
    assert metrics["orders_sent"] == 60
    assert metrics["orders_preparation"] == 0
    assert metrics["orders_delivered"] == 0
    assert metrics["orders_returned_failed"] == 0
    assert metrics["orders_unclassified"] == 0



def build_full_funnel_dataset() -> pd.DataFrame:
    statuses = [
        ("En confirmation", 1),
        ("En preparation", 2),
        ("En dispatch", 3),
        ("En livraison", 4),
        ("Livree", 5),
        ("Encaissee", 6),
        ("En retour", 7),
        ("Retournee", 8),
        ("Annulee", 9),
    ]
    rows = []
    for i, (status, amount) in enumerate(statuses, start=1):
        row = {
            "Reference commande": f"F{i}",
            "Statut commande": status,
            "Total commande": str(amount * 1000),
            "Nom produit": "P1",
            "Wilaya": "Alger",
            "Livreur": "Yalidine",
            "Affectee a": "Rayan",
            "Cree le": "2026-07-01",
        }
        if status in {"En livraison", "Livree", "Encaissee", "En retour", "Retournee"}:
            row["Expediee le"] = "2026-07-02"
        rows.append(row)
    return pd.DataFrame(rows)


def test_full_funnel_statuses_are_classified_without_unclassified_known_statuses():
    df = prepare_dataframe(build_full_funnel_dataset())
    metrics = compute_global_metrics(df)
    checks = compute_validation_checks(df, metrics)

    assert metrics["orders_received"] == 9
    assert metrics["orders_cancelled"] == 1
    assert metrics["orders_confirmed_net"] == 8
    assert metrics["orders_in_confirmation"] == 1
    assert metrics["orders_preparation"] == 1
    assert metrics["orders_dispatch"] == 1
    assert metrics["orders_in_delivery"] == 1
    assert metrics["orders_delivered"] == 2
    assert metrics["orders_returned_failed"] == 2
    assert metrics["orders_sent"] == 6
    assert metrics["orders_logistics"] == 2
    assert metrics["orders_unclassified"] == 0
    assert metrics["orders_sent"] == metrics["orders_dispatch"] + metrics["orders_in_delivery"] + metrics["orders_delivered"] + metrics["orders_returned_failed"]
    assert metrics["orders_logistics"] == metrics["orders_dispatch"] + metrics["orders_in_delivery"]
    assert metrics["logistics_rate_on_sent"] == 2 / 6
    assert metrics["ca_logistics"] == metrics["ca_dispatch"] + metrics["ca_in_delivery"]
    assert not df[df["status_norm"].eq("dispatch")]["is_delivered"].any()
    assert not df[df["status_norm"].eq("dispatch")]["is_return_or_failed"].any()
    assert checks.loc[checks["controle"].eq("Statuts inconnus"), "valeur"].iloc[0] == 0
    assert checks.loc[checks["controle"].eq("Commandes non classees / statut a verifier"), "valeur"].iloc[0] == 0


def test_status_filters_for_known_funnel_steps_keep_equalities_stable():
    df = prepare_dataframe(build_full_funnel_dataset())
    for status in ["En confirmation", "En preparation", "En dispatch", "En livraison", "Livree", "En retour"]:
        filtered = df[df["Statut commande"].eq(status)]
        metrics = compute_global_metrics(filtered)
        checks = compute_validation_checks(filtered, metrics)
        equality_rows = checks[checks["controle"].str.contains("=", regex=False)]
        assert set(equality_rows["statut"]) == {"OK"}
        assert metrics["orders_unclassified"] == 0


def test_global_metric_table_contains_count_and_rate_logistics_context():
    from src.ui import global_metrics_table

    df = prepare_dataframe(build_full_funnel_dataset())
    metrics = compute_global_metrics(df)
    table = global_metrics_table(metrics)
    indicators = set(table["Indicateur"])

    assert "En cours logistique" in indicators
    assert "Taux en cours logistique" in indicators
    assert "CA en cours logistique" in indicators


@pytest.mark.parametrize(
    ("status", "expected_flag"),
    [
        ("En livraison", "is_in_delivery"),
        ("En dispatch", "is_dispatch"),
        ("Livree", "is_delivered"),
        ("En retour", "is_return_or_failed"),
        ("Payee", "is_delivered"),
        ("Echouee", "is_return_or_failed"),
    ],
)
def test_post_shipping_status_without_shipping_date_is_sent_not_preparation(status, expected_flag):
    raw = pd.DataFrame(
        [
            {
                "Reference commande": "POST-1",
                "Statut commande": status,
                "Total commande": "1000",
                "Nom produit": "P1",
                "Wilaya": "Alger",
                "Livreur": "Yalidine",
                "Affectee a": "Rayan",
                "Cree le": "2026-07-01",
            }
        ]
    )
    df = prepare_dataframe(raw)
    row = df.iloc[0]
    metrics = compute_global_metrics(df)

    assert bool(row["is_sent"]) is True
    assert bool(row[expected_flag]) is True
    assert bool(row["is_preparation"]) is False
    assert metrics["orders_sent"] == 1
    assert metrics["orders_preparation"] == 0
