import pandas as pd

from src.data_loader import prepare_dataframe
from src.metrics import compute_livreur_metrics, compute_product_metrics, compute_wilaya_metrics
from src.ui import compute_loss_tables


def build_loss_raw(statuses):
    rows = []
    for idx, status in enumerate(statuses, start=1):
        rows.append(
            {
                "Référence commande": f"CMD-{idx}",
                "Statut commande": status,
                "Total commande": str(1000 * idx),
                "Nom produit": "P1" if idx <= 2 else "P2",
                "Wilaya": "Alger" if idx <= 2 else "Oran",
                "Livreur": "Yalidine" if idx <= 2 else "HHD 01",
                "Affectée à": "Rayan",
                "Crée le": "2026-07-01",
                "Expédiée le": "2026-07-02",
            }
        )
    return pd.DataFrame(rows)


def build_loss_inputs(statuses):
    df = prepare_dataframe(build_loss_raw(statuses))
    return (
        compute_product_metrics(df, volume_min=1),
        compute_wilaya_metrics(df, volume_min=1),
        compute_livreur_metrics(df),
        df,
    )


def assert_empty_loss_tables(product_losses, wilaya_losses, livreur_losses):
    assert product_losses.empty
    assert wilaya_losses.empty
    assert livreur_losses.empty
    assert list(product_losses.columns) == ["produit", "retours", "ca_retours", "taux_retour", "action_recommandee"]
    assert list(wilaya_losses.columns) == ["wilaya", "retours", "ca_retours", "taux_retour", "livreur_dominant", "action_recommandee"]
    assert list(livreur_losses.columns) == ["livreur", "retours", "ca_retours", "taux_retour", "wilayas_problematiques", "action_recommandee"]


def test_compute_loss_tables_with_no_returns_returns_stable_empty_tables():
    product_losses, wilaya_losses, livreur_losses = compute_loss_tables(*build_loss_inputs(["Livrée", "Encaissée", "Livrée"]))
    assert_empty_loss_tables(product_losses, wilaya_losses, livreur_losses)


def test_compute_loss_tables_with_only_in_delivery_does_not_merge_anonymous_series():
    product_losses, wilaya_losses, livreur_losses = compute_loss_tables(*build_loss_inputs(["En livraison", "En livraison", "En livraison"]))
    assert_empty_loss_tables(product_losses, wilaya_losses, livreur_losses)


def test_compute_loss_tables_with_empty_dataframe_returns_stable_empty_tables():
    empty = pd.DataFrame()
    product_losses, wilaya_losses, livreur_losses = compute_loss_tables(empty, empty, empty, empty)
    assert_empty_loss_tables(product_losses, wilaya_losses, livreur_losses)


def test_compute_loss_tables_with_returns_keeps_expected_loss_rows():
    product_losses, wilaya_losses, livreur_losses = compute_loss_tables(*build_loss_inputs(["Livrée", "Retournée", "En retour"]))

    assert not product_losses.empty
    assert not wilaya_losses.empty
    assert not livreur_losses.empty
    assert product_losses["ca_retours"].max() > 0
    assert wilaya_losses["ca_retours"].max() > 0
    assert livreur_losses["ca_retours"].max() > 0
    assert "wilayas_problematiques" in livreur_losses.columns
    assert livreur_losses["wilayas_problematiques"].astype(str).str.len().gt(0).all()
