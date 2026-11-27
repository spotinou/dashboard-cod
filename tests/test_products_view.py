import pytest

from src.alerts import DEFAULT_THRESHOLDS
from src.metrics import compute_global_metrics, compute_product_metrics
from src.trends import card_confirmation_rate
from src.views.products_view import (
    VERDICT_BAD,
    VERDICT_CONFIRM,
    VERDICT_DELIVERY,
    VERDICT_GOOD,
    VERDICT_LOW,
    VERDICT_WAIT,
    VERDICT_WATCH,
    comparison_summary,
    product_comparison,
    product_funnel_steps,
    product_metrics_dict,
    product_verdict,
)
from tests.test_rankings import build_df

T = dict(DEFAULT_THRESHOLDS)


@pytest.mark.parametrize(
    "confirmation, delivery, expected",
    [
        (0.80, 0.80, VERDICT_GOOD),
        (0.65, 0.80, VERDICT_WATCH),
        (0.40, 0.80, VERDICT_CONFIRM),
        (0.80, 0.40, VERDICT_DELIVERY),
        (0.40, 0.40, VERDICT_BAD),
        (0.80, None, VERDICT_WAIT),
    ],
)
def test_product_verdict(confirmation, delivery, expected):
    assert product_verdict(confirmation, delivery, received=50, volume_min=10, thresholds=T) == expected


def test_product_verdict_low_volume_wins():
    assert product_verdict(0.1, 0.1, received=3, volume_min=10, thresholds=T) == VERDICT_LOW


def test_comparison_uses_card_rules_and_sorts_by_volume():
    products = compute_product_metrics(build_df())
    comparison = product_comparison(products, volume_min=1, thresholds=T)
    assert comparison["produit"].tolist()[0] == "P1"  # 5 orders received, the most
    p1 = comparison.set_index("produit").loc["P1"]
    assert p1["commandes_recues"] == 5
    assert p1["taux_annulation"] == pytest.approx(0.2)
    assert p1["taux_confirme"] == pytest.approx(0.8)
    assert p1["taux_livraison_total"] == pytest.approx(0.75)
    assert p1["taux_transformation_reel"] == pytest.approx(0.6)


def test_single_product_matches_global_cockpit():
    df = build_df()
    df = df[df["Nom produit"] == "P1"]
    row = compute_product_metrics(df).iloc[0]
    assert card_confirmation_rate(product_metrics_dict(row)) == card_confirmation_rate(compute_global_metrics(df))


def test_funnel_steps():
    products = compute_product_metrics(build_df()).set_index("produit")
    steps = product_funnel_steps(products.loc["P1"])
    assert [s["label"] for s in steps] == ["Reçues", "Confirmées", "Expédiées", "Livrées"]
    assert [s["value"] for s in steps] == [5, 4, 4, 3]
    assert steps[3]["share_of_received"] == pytest.approx(0.6)
    assert steps[3]["step_rate"] == pytest.approx(0.75)
    assert steps[0]["step_rate"] is None


def test_summary_names_best_and_worst():
    comparison = product_comparison(compute_product_metrics(build_df()), volume_min=1, thresholds=T)
    text = " ".join(comparison_summary(comparison))
    assert "Meilleur produit : **P3**" in text
    assert "Se livre le moins bien : **P2**" in text


def test_empty_products():
    comparison = product_comparison(compute_product_metrics(build_df()).iloc[0:0], volume_min=1, thresholds=T)
    assert comparison.empty
