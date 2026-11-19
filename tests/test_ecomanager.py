from datetime import datetime

import pandas as pd
import pytest
import requests

from src.data_loader import prepare_dataframe
from src.ecomanager import ORDER_STATE_NAMES, EcoManagerError, RateLimiter, fetch_orders, orders_to_dataframe, orders_to_rows

STATE_IDS = {name: state_id for state_id, name in ORDER_STATE_NAMES.items()}
from src.metrics import compute_global_metrics, compute_livreur_metrics


def doc_order(order_id, state, created, **extra):
    """An order shaped like the 'Retrieve a single order' example of the EcoManager documentation."""
    order = {
        "id": order_id, "reference": f"DEM{order_id}", "tracking": None, "is_stopdesk": 0,
        "order_state_id": STATE_IDS.get(state), "order_state_name": state, "confirmation_state_name": None,
        "full_name": "Client", "email": None, "telephone": "0666666666", "telephone_2": None,
        "wilaya": "Alger", "commune": "Draria", "address": "Appartement 4", "note": None, "api_source": None,
        "items": [{"sku": "ABD1234", "title": "iPhone 13 Pro", "title_fr": "iPhone 13 Pro", "option_name": "Noir", "selling_price": "1500", "quantity": 1}],
        "total_products": "1500", "total_shipping": "600", "total_discount": "0", "total": "2100",
        "confirmer": {"id": 12, "name": "Amine"}, "carrier": {"id": 3, "name": "Yalidine"},
        "assigned_at": None, "confirmed_at": None, "dispatched_at": None, "shipped_at": None,
        "delivered_at": None, "failed_at": None, "canceled_at": None, "paid_at": None, "returned_at": None,
        "created_at": created, "updated_at": created,
    }
    order.update(extra)
    return order


class FakeResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status_code, self._payload, self.headers = status, payload or {}, headers or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "params": dict(params or {})})
        return self.responses.pop(0)


class NoWait(RateLimiter):
    def wait(self):
        pass


def page(orders, next_cursor=None):
    return FakeResponse(200, {"data": orders, "meta": {"next_cursor": next_cursor}})


def test_fetch_reads_pages_newest_first_and_stops_at_start_date():
    session = FakeSession([
        page([doc_order(3, "Livrée", "2026-11-10 10:00:00"), doc_order(2, "En livraison", "2026-11-05 10:00:00")], "c2"),
        page([doc_order(1, "Annulée", "2026-11-01 10:00:00"), doc_order(0, "Annulée", "2026-10-01 10:00:00")], "c3"),
        page([doc_order(-1, "Annulée", "2026-09-01 10:00:00")]),  # must never be requested
    ])
    orders = fetch_orders("https://shop.ecomanager.dz/", "TOKEN", datetime(2026, 10, 15), session=session, limiter=NoWait())
    assert [o["id"] for o in orders] == [3, 2, 1]
    assert len(session.calls) == 3  # the 3rd page (only old orders, no next page) ends the reading
    first = session.calls[0]
    assert first["url"] == "https://shop.ecomanager.dz/api/shop/v2/orders"
    assert first["headers"]["Authorization"] == "Bearer TOKEN"
    assert first["params"] == {"per_page": 100, "sort_direction": "desc"}
    assert session.calls[1]["params"]["cursor"] == "c2"


def test_fetch_waits_on_429_then_continues():
    waits = []
    session = FakeSession([FakeResponse(429, headers={"Retry-After": "7"}), page([doc_order(1, "Livrée", "2026-11-10 10:00:00")])])
    orders = fetch_orders("https://x", "T", datetime(2026, 1, 1), session=session, limiter=NoWait(), sleep=waits.append)
    assert waits == [7.0] and len(orders) == 1


def test_fetch_errors_are_readable():
    with pytest.raises(EcoManagerError, match="401"):
        fetch_orders("https://x", "BAD", datetime(2026, 1, 1), session=FakeSession([FakeResponse(401)]), limiter=NoWait())
    with pytest.raises(EcoManagerError, match="429"):
        fetch_orders("https://x", "T", datetime(2026, 1, 1), session=FakeSession([FakeResponse(429)] * 4), limiter=NoWait(), sleep=lambda s: None)
    with pytest.raises(EcoManagerError, match="clé API"):
        fetch_orders("https://x", "", datetime(2026, 1, 1), session=FakeSession([]), limiter=NoWait())

    class Broken:
        def get(self, *a, **k):
            raise requests.ConnectionError("down")

    with pytest.raises(EcoManagerError, match="joindre"):
        fetch_orders("https://x", "T", datetime(2026, 1, 1), session=Broken(), limiter=NoWait())


def test_rate_limiter_keeps_under_quota():
    now = [0.0]
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(per_minute=45, min_interval=0.25, clock=lambda: now[0], sleep=sleep)
    for _ in range(46):
        limiter.wait()
    # 45 calls spaced by 0.25 s, then a wait until the first call leaves the 60 s window
    assert now[0] >= 60
    assert all(b - a >= 0.25 - 1e-9 for a, b in zip(list(limiter.calls)[:-1], list(limiter.calls)[1:]))


def test_mapping_to_excel_columns_one_row_per_product():
    order = doc_order(15759, "Livrée", "2021-05-31 17:02:46", shipped_at="2021-06-02 14:19:50", delivered_at="2021-07-29 11:18:39",
                      items=[{"sku": "A", "title_fr": "Produit A", "quantity": 1, "selling_price": 1000},
                             {"sku": "B", "title_fr": "Produit B", "quantity": 2, "selling_price": 250}])
    rows = orders_to_rows([order])
    assert [r["Nom produit"] for r in rows] == ["Produit A", "Produit B"]
    assert rows[0]["Statut commande"] == "Livrée" and rows[0]["Livreur"] == "Yalidine" and rows[0]["Affectée à"] == "Amine"
    assert rows[0]["Expédiée le"] == "2021-06-02 14:19:50" and rows[0]["Livrée le"] == "2021-07-29 11:18:39"
    assert rows[0]["Total commande"] == "2100"


def test_api_and_excel_give_the_same_figures():
    orders = [
        doc_order(1, "Livrée", "2026-11-01 10:00:00", shipped_at="2026-11-02 10:00:00", delivered_at="2026-11-04 10:00:00"),
        doc_order(2, "Encaissée", "2026-11-01 11:00:00", shipped_at="2026-11-02 10:00:00", delivered_at="2026-11-04 10:00:00", paid_at="2026-11-06 10:00:00"),
        doc_order(3, "En livraison", "2026-11-02 10:00:00", shipped_at="2026-11-03 10:00:00"),
        doc_order(4, "Retournée", "2026-11-02 11:00:00", shipped_at="2026-11-03 10:00:00", returned_at="2026-11-08 10:00:00"),
        doc_order(5, "En dispatch", "2026-11-03 10:00:00", confirmed_at="2026-11-03 12:00:00", dispatched_at="2026-11-03 13:00:00"),
        doc_order(6, "En préparation", "2026-11-03 11:00:00", confirmed_at="2026-11-03 12:00:00"),
        doc_order(7, "En confirmation", "2026-11-04 10:00:00", confirmation_state_name="Ne répond pas"),
        doc_order(8, "Annulée", "2026-11-04 11:00:00", canceled_at="2026-11-04 12:00:00"),
        doc_order(9, "En retour", "2026-11-04 12:00:00", shipped_at="2026-11-05 10:00:00"),
    ]
    api_df = orders_to_dataframe(orders)
    excel_df = prepare_dataframe(pd.DataFrame(orders_to_rows(orders)))  # same rows, as if read from an export
    api_metrics, excel_metrics = compute_global_metrics(api_df), compute_global_metrics(excel_df)
    assert api_metrics == excel_metrics
    # the 9 EcoManager states are all understood: nothing unclassified
    assert api_metrics["orders_unclassified"] == 0
    assert api_metrics["orders_received"] == 9
    assert api_metrics["orders_cancelled"] == 1
    assert api_metrics["orders_in_confirmation"] == 1
    assert api_metrics["orders_preparation"] == 1
    assert api_metrics["orders_delivered"] == 2
    assert api_metrics["orders_returned_failed"] == 2  # Retournée + En retour
    assert api_metrics["orders_sent"] == 6  # dispatch, en livraison, livrées, retours
    livreurs = compute_livreur_metrics(api_df)
    assert livreurs.set_index("livreur").loc["Yalidine", "commandes_envoyees"] == 6


def test_empty_api_answer_is_a_clear_error():
    with pytest.raises(EcoManagerError, match="Aucune commande"):
        orders_to_dataframe([])


def test_api_dates_are_not_swapped():
    # "2026-03-04" is 4 March in the API format, never 3 April
    df = orders_to_dataframe([doc_order(1, "Livrée", "2026-03-04 08:06:38", shipped_at="2026-03-05 10:00:00", delivered_at="2026-03-07 09:00:00")])
    assert df["Crée le"].iloc[0] == pd.Timestamp("2026-03-04 08:06:38")
    assert df["Livrée le"].iloc[0] == pd.Timestamp("2026-03-07 09:00:00")


def test_two_shops_are_combined_without_merging_orders():
    from src.ecomanager import shops_to_dataframe

    shop_a = [doc_order(1, "Livrée", "2026-11-01 10:00:00", shipped_at="2026-11-02 10:00:00", delivered_at="2026-11-04 10:00:00"),
              doc_order(2, "Annulée", "2026-11-01 11:00:00")]
    # same ids / references as shop A on purpose
    shop_b = [doc_order(1, "En livraison", "2026-11-02 10:00:00", shipped_at="2026-11-03 10:00:00")]
    df = shops_to_dataframe([("Maison Luxelle", shop_a), ("ELBARAKA", shop_b)])
    metrics = compute_global_metrics(df)
    assert metrics["orders_received"] == 3  # 2 + 1, nothing merged
    assert metrics["orders_delivered"] == 1 and metrics["orders_cancelled"] == 1 and metrics["orders_sent"] == 2
    assert sorted(df["Boutique"].unique()) == ["ELBARAKA", "Maison Luxelle"]
    assert df["order_id"].nunique() == 3
    # one shop alone: references are left untouched
    single = orders_to_dataframe(shop_a, shop="Maison Luxelle")
    assert set(single["Référence commande"]) == {"DEM1", "DEM2"}
    assert set(single["Boutique"]) == {"Maison Luxelle"}


def test_secrets_formats(monkeypatch):
    import src.views.data_source as ds

    monkeypatch.setattr(ds.st, "secrets", {"ecomanager": {"shops": [
        {"name": "Maison Luxelle", "token": "A", "base_url": "https://maisonluxelle.ecomanager.dz"},
        {"name": "ELBARAKA", "token": "B", "base_url": "https://elbaraka.ecomanager.dz"},
        {"name": "Sans clé"},
    ]}})
    shops = ds.api_shops()
    assert [s["name"] for s in shops] == ["Maison Luxelle", "ELBARAKA"]
    assert shops[1]["base_url"] == "https://elbaraka.ecomanager.dz"
    monkeypatch.setattr(ds.st, "secrets", {"ecomanager": {"token": "X"}})  # older one-shop format
    assert ds.api_shops() == [{"name": None, "base_url": ds.DEFAULT_BASE_URL, "token": "X"}]
    monkeypatch.setattr(ds.st, "secrets", {})
    assert ds.api_shops() == []


def test_one_old_order_among_recent_ones_does_not_stop_the_reading():
    """Real case: pages are ordered by id; an exchange / restored order with an old creation date
    sits among recent orders. Reading used to stop there and lose every order after it."""
    report = {}
    session = FakeSession([
        page([doc_order(10, "Livrée", "2026-11-15 10:00:00"), doc_order(9, "Livrée", "2025-01-01 10:00:00"),
              doc_order(8, "Annulée", "2026-11-10 10:00:00")], "c2"),
        page([doc_order(7, "Livrée", "2026-10-20 10:00:00"), doc_order(6, "Livrée", "2026-09-30 10:00:00")], "c3"),
        page([doc_order(5, "Livrée", "2026-09-01 10:00:00")], "c4"),   # 1st page with only old orders
        page([doc_order(4, "Livrée", "2026-08-01 10:00:00")], "c5"),   # 2nd -> stop
        page([doc_order(3, "Livrée", "2026-11-01 10:00:00")]),         # never requested
    ])
    orders = fetch_orders("https://x", "T", datetime(2026, 10, 1), session=session, limiter=NoWait(), report=report)
    assert [o["id"] for o in orders] == [10, 8, 7]
    assert len(session.calls) == 4
    assert report == {"pages": 4, "skipped_old": 4, "duplicates": 0, "complete": True}


def test_duplicate_orders_across_pages_are_counted_once():
    report = {}
    session = FakeSession([
        page([doc_order(3, "Livrée", "2026-11-15 10:00:00"), doc_order(2, "Livrée", "2026-11-14 10:00:00")], "c2"),
        page([doc_order(2, "Livrée", "2026-11-14 10:00:00"), doc_order(1, "Livrée", "2026-11-13 10:00:00")]),
    ])
    orders = fetch_orders("https://x", "T", datetime(2026, 10, 1), session=session, limiter=NoWait(), report=report)
    assert [o["id"] for o in orders] == [3, 2, 1] and report["duplicates"] == 1


def test_state_id_wins_over_translated_name():
    arabic = doc_order(1, "Livrée", "2026-11-01 10:00:00", order_state_name="تم التسليم",
                       shipped_at="2026-11-02 10:00:00", delivered_at="2026-11-04 10:00:00")
    assert orders_to_rows([arabic])[0]["Statut commande"] == "Livrée"
    m = compute_global_metrics(orders_to_dataframe([arabic]))
    assert m["orders_delivered"] == 1 and m["orders_unclassified"] == 0
    unknown_id = doc_order(2, "Livrée", "2026-11-01 10:00:00", order_state_id=None)
    assert orders_to_rows([unknown_id])[0]["Statut commande"] == "Livrée"  # falls back to the name


def test_unexpected_payloads_are_clear_errors():
    with pytest.raises(EcoManagerError, match="inattendue"):
        fetch_orders("https://x", "T", datetime(2026, 1, 1), session=FakeSession([FakeResponse(200, {"message": "oops"})]), limiter=NoWait())

    class NotJson(FakeResponse):
        def json(self):
            raise ValueError("no json")

    with pytest.raises(EcoManagerError, match="illisible"):
        fetch_orders("https://x", "T", datetime(2026, 1, 1), session=FakeSession([NotJson(200)]), limiter=NoWait())
