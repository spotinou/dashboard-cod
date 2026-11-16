import pandas as pd
import pytest

from src.data_loader import prepare_dataframe
from src.metrics import compute_confirmation_metrics, compute_global_metrics, compute_livreur_metrics, compute_product_metrics, compute_wilaya_metrics
from src.rankings import (
    OTHERS_LABEL,
    amount_concentration,
    amount_ranking_rows,
    pooled_rate,
    rate_ranking_reading,
    rate_ranking_rows,
    rate_tone,
)
from src.ui import build_amount_ranking_figure, build_rate_ranking_figure


def order(ref, status, livreur, wilaya, produit, total="1000", **extra):
    row = {
        "Référence commande": ref,
        "Statut commande": status,
        "Crée le": "2026-01-01",
        "Total commande": total,
        "Nom produit": produit,
        "Wilaya": wilaya,
        "Livreur": livreur,
        "Affectée à": extra.pop("confirmatrice", "Rayan"),
    }
    if status in {"Livrée", "En retour", "En livraison"}:
        row["Expédiée le"] = "2026-01-01"
    if status == "Livrée":
        row["Livrée le"] = "2026-01-03"
    row.update(extra)
    return row


def build_df():
    rows = []
    # HHD 01 : 4 shipped, 3 delivered (75 %)
    rows += [order(f"H{i}", "Livrée", "HHD 01", "Alger", "P1", "3000") for i in range(3)]
    rows += [order("H3", "En retour", "HHD 01", "Alger", "P1", "3000")]
    # ZR : 4 shipped, 1 delivered (25 %)
    rows += [order("Z0", "Livrée", "ZR Express", "Oran", "P2", "2000")]
    rows += [order(f"Z{i}", "En retour", "ZR Express", "Oran", "P2", "2000") for i in range(1, 4)]
    # Yalidine : 1 shipped only (below volume_min)
    rows += [order("Y0", "Livrée", "Yalidine", "Sétif", "P3", "5000", confirmatrice="Sara")]
    rows += [order("A0", "Annulée", "", "Alger", "P1")]
    return prepare_dataframe(pd.DataFrame(rows))


def test_pooled_average_equals_global_kpis():
    df = build_df()
    metrics = compute_global_metrics(df)
    livreurs = compute_livreur_metrics(df)
    wilayas = compute_wilaya_metrics(df)
    confirmation = compute_confirmation_metrics(df)
    products = compute_product_metrics(df)
    assert pooled_rate(livreurs, "livrees", "commandes_envoyees") == pytest.approx(metrics["delivery_total_rate_on_sent"])
    assert pooled_rate(wilayas, "livrees", "commandes_envoyees") == pytest.approx(metrics["delivery_total_rate_on_sent"])
    assert pooled_rate(confirmation, "livrees", "commandes_recues") == pytest.approx(metrics["transformation_real_rate"])
    assert pooled_rate(products, "retours", "commandes_envoyees") == pytest.approx(metrics["return_rate_on_sent"])


def test_rate_ranking_shows_best_and_worst_and_hides_low_volume():
    livreurs = compute_livreur_metrics(build_df())
    rows, hidden_low, hidden_middle = rate_ranking_rows(livreurs, "livreur", "taux_livraison_total", "commandes_envoyees", volume_min=2)
    assert list(rows["livreur"]) == ["HHD 01", "ZR Express"]  # best first, worst last
    assert hidden_low == 1  # Yalidine: 1 parcel only
    assert hidden_middle == 0
    reading = rate_ranking_reading(rows, "livreur", "taux_livraison_total")
    assert reading["best"] == ("HHD 01", 0.75)
    assert reading["worst"] == ("ZR Express", 0.25)


def test_rate_ranking_lower_is_better_sorts_ascending():
    products = compute_product_metrics(build_df())
    rows, _, _ = rate_ranking_rows(products, "produit", "taux_retour", "commandes_envoyees", volume_min=2, higher_is_better=False)
    assert list(rows["produit"]) == ["P1", "P2"]


def test_rate_ranking_keeps_both_ends_when_too_many_rows():
    table = pd.DataFrame({"nom": [f"N{i:02d}" for i in range(30)], "taux": [i / 100 for i in range(30)], "volume": [50] * 30})
    rows, _, hidden_middle = rate_ranking_rows(table, "nom", "taux", "volume", volume_min=1, max_rows=10)
    assert len(rows) == 10 and hidden_middle == 20
    assert list(rows["nom"][:5]) == ["N29", "N28", "N27", "N26", "N25"]
    assert list(rows["nom"][-5:]) == ["N04", "N03", "N02", "N01", "N00"]


def test_rate_ranking_ignores_unknown_labels():
    table = pd.DataFrame({"livreur": ["A", "Non renseigné", "", "B"], "taux": [0.5, 0.9, 0.9, 0.7], "volume": [10] * 4})
    rows, _, _ = rate_ranking_rows(table, "livreur", "taux", "volume", volume_min=1)
    assert list(rows["livreur"]) == ["B", "A"]


def test_rate_tone_against_average():
    assert rate_tone(0.80, 0.70, True) == "good"
    assert rate_tone(0.60, 0.70, True) == "bad"
    assert rate_tone(0.71, 0.70, True) == "neutral"
    assert rate_tone(0.10, 0.30, False) == "good"
    assert rate_tone(None, 0.30, True) == "neutral"


def test_amount_ranking_shares_add_up_to_total():
    table = pd.DataFrame({"produit": [f"P{i}" for i in range(13)] + ["Non renseigné"], "ca": [1000 * (13 - i) for i in range(13)] + [500]})
    rows, total = amount_ranking_rows(table, "produit", "ca", max_rows=10)
    assert total == pytest.approx(table["ca"].sum())
    assert rows["ca"].sum() == pytest.approx(total)
    assert rows["part"].sum() == pytest.approx(1.0)
    assert list(rows["produit"][:3]) == ["P0", "P1", "P2"]
    others = rows.iloc[-1]
    assert others["produit"] == OTHERS_LABEL and others["nb_regroupes"] == 4  # P10-P12 + unknown
    assert amount_concentration(rows, "produit", "ca", total) == pytest.approx((13000 + 12000 + 11000) / total)


def test_amount_ranking_drops_zero_amounts():
    table = pd.DataFrame({"livreur": ["A", "B", "C"], "ca": [0, 300, 100]})
    rows, total = amount_ranking_rows(table, "livreur", "ca")
    assert list(rows["livreur"]) == ["B", "C"]
    assert total == 400


def test_ranking_figures():
    livreurs = compute_livreur_metrics(build_df())
    rows, _, _ = rate_ranking_rows(livreurs, "livreur", "taux_livraison_total", "commandes_envoyees", volume_min=2)
    fig = build_rate_ranking_figure(rows, "livreur", "taux_livraison_total", "commandes_envoyees", "expédiées", average=0.5)
    assert fig.data[0].orientation == "h"
    assert list(fig.data[0].marker.color) == ["#16a34a", "#dc2626"]
    assert fig.data[0].text[0] == "75.0 % · 4 expédiées"
    assert fig.layout.showlegend is False
    assert build_rate_ranking_figure(rows.iloc[0:0], "livreur", "taux_livraison_total", "commandes_envoyees", "expédiées", 0.5) is None

    amounts, _ = amount_ranking_rows(livreurs, "livreur", "ca_retours")
    fig = build_amount_ranking_figure(amounts, "livreur", "ca_retours", "#ef4444")
    assert list(fig.data[0].y) == ["ZR Express", "HHD 01"]
