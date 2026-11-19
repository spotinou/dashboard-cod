from __future__ import annotations

import pandas as pd

from .cleaning import safe_divide


def _orders(df: pd.DataFrame) -> pd.DataFrame:
    aggregations = {
        "Boutique": "first",
        "Affectée à": "first",
        "Livreur": "first",
        "Wilaya": "first",
        "Nom produit": "first",
        "Crée le": "first",
        "is_cancelled": "max",
        "is_confirmed_net": "max",
        "is_in_confirmation": "max",
        "is_preparation": "max",
        "is_dispatch": "max",
        "is_sent": "max",
        "is_delivered": "max",
        "is_in_delivery": "max",
        "is_non_finalized_sent": "max",
        "is_return_or_failed": "max",
        "is_delivery_finalized": "max",
        "is_unclassified": "max",
        "ca_total": "max",
        "ca_delivered": "max",
        "ca_in_confirmation": "max",
        "ca_dispatch": "max",
        "ca_in_delivery": "max",
        "ca_preparation": "max",
        "ca_returned_failed": "max",
    }
    return df.groupby("order_id", dropna=False).agg(aggregations).reset_index()


def _rate(live: float, total: float) -> float | None:
    return safe_divide(float(live), float(total))


def _finalized_rate(group: pd.DataFrame) -> float | None:
    delivered = int(group["is_delivered"].sum())
    returned = int(group["is_return_or_failed"].sum())
    return _rate(delivered, delivered + returned)


def compute_global_metrics(df: pd.DataFrame) -> dict:
    o = _orders(df)
    received = len(o)
    confirmed = int(o["is_confirmed_net"].sum())
    cancelled = int(o["is_cancelled"].sum())
    in_confirmation = int(o["is_in_confirmation"].sum())
    preparation = int(o["is_preparation"].sum())
    sent = int(o["is_sent"].sum())
    dispatch = int(o["is_dispatch"].sum())
    delivered = int(o["is_delivered"].sum())
    in_delivery = int(o["is_in_delivery"].sum())
    logistics = dispatch + in_delivery
    returned = int(o["is_return_or_failed"].sum())
    unclassified = int(o["is_unclassified"].sum()) if "is_unclassified" in o.columns else 0
    return {
        "orders_received": received,
        "orders_confirmed_net": confirmed,
        "confirmation_rate": _rate(confirmed, received),
        "orders_cancelled": cancelled,
        "cancellation_rate": _rate(cancelled, received),
        "orders_in_confirmation": in_confirmation,
        "orders_preparation": preparation,
        "preparation_blockage_rate": _rate(preparation, confirmed),
        "shipping_rate_global": _rate(sent, confirmed),
        "orders_sent": sent,
        "orders_dispatch": dispatch,
        "orders_delivered": delivered,
        "orders_in_delivery": in_delivery,
        "orders_logistics": logistics,
        "orders_returned_failed": returned,
        "orders_unclassified": unclassified,
        "delivery_finalized_rate": _rate(delivered, delivered + returned),
        "delivery_total_rate_on_sent": _rate(delivered, sent),
        "in_delivery_rate_on_sent": _rate(in_delivery, sent),
        "logistics_rate_on_sent": _rate(logistics, sent),
        "return_rate_on_sent": _rate(returned, sent),
        "transformation_real_rate": _rate(delivered, received),
        "ca_delivered": float(o["ca_delivered"].sum()),
        "ca_in_confirmation": float(o["ca_in_confirmation"].sum()),
        "ca_dispatch": float(o["ca_dispatch"].sum()),
        "ca_in_delivery": float(o["ca_in_delivery"].sum()),
        "ca_logistics": float(o["ca_dispatch"].sum() + o["ca_in_delivery"].sum()),
        "ca_preparation": float(o["ca_preparation"].sum()),
        "ca_returned_failed": float(o["ca_returned_failed"].sum()),
    }


GROUP_METRIC_COLUMNS = [
    "commandes_recues",
    "commandes_annulees",
    "commandes_confirmees_nettes",
    "en_confirmation",
    "taux_confirmation",
    "taux_annulation",
    "commandes_envoyees",
    "livrees",
    "en_dispatch",
    "en_livraison",
    "en_cours_logistique",
    "retours",
    "commandes_non_classees",
    "taux_livraison_finalisees",
    "taux_livraison_total",
    "taux_en_cours_logistique",
    "taux_retour",
    "ca_livre",
    "ca_dispatch",
    "ca_bloque_livraison",
    "ca_en_cours_logistique",
    "ca_preparation",
    "ca_retours",
    "panier_moyen_livre",
    "taux_transformation_reel",
]


CA_COLUMNS = ["ca_total", "ca_delivered", "ca_in_confirmation", "ca_dispatch", "ca_in_delivery", "ca_preparation", "ca_returned_failed"]


def _product_orders(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (order, product): an order with 2 products counts for both products.

    Order statuses are the order's. Amounts are the order's, split between its products
    in proportion to price x quantity (equal split when prices are missing), so the sum
    over products still equals the order total."""
    o = _orders(df).drop(columns=["Nom produit"])
    lines = df.copy()
    price = pd.to_numeric(lines.get("Prix de vente"), errors="coerce").fillna(0) if "Prix de vente" in lines else 0
    qty = pd.to_numeric(lines.get("Quantité"), errors="coerce").fillna(1) if "Quantité" in lines else 1
    lines["_line_value"] = (price * qty).clip(lower=0) if not isinstance(price, int) else 0.0
    per_product = lines.groupby(["order_id", "Nom produit"], dropna=False)["_line_value"].sum().reset_index()
    order_value = per_product.groupby("order_id", dropna=False)["_line_value"].transform("sum")
    n_products = per_product.groupby("order_id", dropna=False)["_line_value"].transform("size")
    per_product["_share"] = (per_product["_line_value"] / order_value).where(order_value > 0, 1.0 / n_products)
    out = per_product.merge(o, on="order_id", how="left")
    for col in CA_COLUMNS:
        if col in out.columns:
            out[col] = out[col] * out["_share"]
    return out.drop(columns=["_line_value", "_share"])


def _group_metrics(df: pd.DataFrame, group_col: str, sent_only: bool = False, orders: pd.DataFrame | None = None) -> pd.DataFrame:
    o = _orders(df) if orders is None else orders
    if sent_only:
        o = o[o["is_sent"]]
    rows = []
    for name, g in o.groupby(group_col, dropna=False):
        received = len(g)
        sent = int(g["is_sent"].sum())
        in_confirmation = int(g["is_in_confirmation"].sum())
        dispatch = int(g["is_dispatch"].sum())
        in_delivery = int(g["is_in_delivery"].sum())
        logistics = dispatch + in_delivery
        delivered = int(g["is_delivered"].sum())
        returned = int(g["is_return_or_failed"].sum())
        unclassified = int(g["is_unclassified"].sum()) if "is_unclassified" in g.columns else 0
        rows.append(
            {
                group_col: name,
                "commandes_recues": received,
                "commandes_annulees": int(g["is_cancelled"].sum()),
                "commandes_confirmees_nettes": int(g["is_confirmed_net"].sum()),
                "en_confirmation": in_confirmation,
                "taux_confirmation": _rate(g["is_confirmed_net"].sum(), received),
                "taux_annulation": _rate(g["is_cancelled"].sum(), received),
                "commandes_envoyees": sent,
                "livrees": delivered,
                "en_dispatch": dispatch,
                "en_livraison": in_delivery,
                "en_cours_logistique": logistics,
                "retours": returned,
                "commandes_non_classees": unclassified,
                "taux_livraison_finalisees": _rate(delivered, delivered + returned),
                "taux_livraison_total": _rate(delivered, sent),
                "taux_en_cours_logistique": _rate(logistics, sent),
                "taux_retour": _rate(returned, sent),
                "ca_livre": float(g["ca_delivered"].sum()),
                "ca_dispatch": float(g["ca_dispatch"].sum()),
                "ca_bloque_livraison": float(g["ca_in_delivery"].sum()),
                "ca_en_cours_logistique": float(g["ca_dispatch"].sum() + g["ca_in_delivery"].sum()),
                "ca_preparation": float(g["ca_preparation"].sum()),
                "ca_retours": float(g["ca_returned_failed"].sum()),
                "panier_moyen_livre": _rate(float(g["ca_delivered"].sum()), delivered),
                "taux_transformation_reel": _rate(delivered, received),
            }
        )
    if not rows:
        return pd.DataFrame(columns=[group_col, *GROUP_METRIC_COLUMNS])
    return pd.DataFrame(rows)


def _decision_confirmation(row: pd.Series, volume_min: int = 10) -> str:
    if row["commandes_recues"] < volume_min:
        return "Échantillon faible"
    if (
        (row.get("taux_confirmation") is not None and row.get("taux_confirmation") >= 0.75)
        and (row.get("taux_livraison_total") is not None and row.get("taux_livraison_total") >= 0.75)
        and (row.get("taux_retour") is not None and row.get("taux_retour") <= 0.25)
    ):
        return "À pousser"
    if (row.get("taux_confirmation") is not None and row.get("taux_confirmation") < 0.65) or (
        row.get("taux_retour") is not None and row.get("taux_retour") >= 0.30
    ):
        return "À corriger"
    return "À surveiller"


def _decision_livreur(row: pd.Series, volume_min: int = 5) -> str:
    if row["commandes_envoyees"] < volume_min:
        return "Échantillon faible"
    if (
        row.get("taux_livraison_total") is not None
        and row.get("taux_livraison_total") >= 0.75
        and row.get("taux_retour") is not None
        and row.get("taux_retour") <= 0.25
    ):
        return "Garder / pousser"
    if (row.get("taux_retour") is not None and row.get("taux_retour") >= 0.30) or (
        row.get("taux_livraison_total") is not None and row.get("taux_livraison_total") < 0.65
    ):
        return "Limiter / vérifier"
    return "À surveiller"


def _product_problem(row: pd.Series, volume_min: int = 10) -> tuple[str, str]:
    if row["commandes_recues"] < volume_min:
        return "Échantillon faible", "Volume faible"
    if (
        row.get("taux_confirmation") is not None
        and row.get("taux_confirmation") >= 0.75
        and row.get("taux_livraison_total") is not None
        and row.get("taux_livraison_total") >= 0.75
        and row.get("taux_retour") is not None
        and row.get("taux_retour") <= 0.25
        and row.get("ca_livre", 0) > 0
    ):
        return "À scaler", "OK"
    if row.get("taux_confirmation") is not None and row.get("taux_confirmation") < 0.65:
        return "À corriger", "Confirmation faible"
    if row.get("taux_livraison_total") is not None and row.get("taux_livraison_total") < 0.65:
        return "À corriger", "Livraison faible"
    if row.get("taux_retour") is not None and row.get("taux_retour") >= 0.30:
        return "À corriger", "Retour élevé"
    return "À surveiller", "Performance moyenne"


def _wilaya_cause_action(row: pd.Series, volume_min: int = 5) -> tuple[str, str]:
    if row["commandes_envoyees"] < volume_min:
        return "Volume faible", "Attendre plus de données"
    if row.get("taux_retour") is not None and row.get("taux_retour") >= 0.30:
        return "Retour élevé", "Vérifier produit dominant + livreur dominant"
    if row.get("taux_livraison_total") is not None and row.get("taux_livraison_total") < 0.65:
        return "Livraison faible", "Tester autre livreur ou limiter la zone"
    if row.get("taux_en_cours_livraison") is not None and row.get("taux_en_cours_livraison") > 0.25:
        return "Commandes bloquées en livraison", "Suivre les colis avant d'augmenter le volume"
    return "Performance moyenne", "Surveiller"


def compute_confirmation_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = _group_metrics(df, "Affectée à").rename(columns={"Affectée à": "confirmatrice"})
    out["decision_auto"] = out.apply(_decision_confirmation, axis=1)
    out["ca_par_commande_confirmee"] = out.apply(
        lambda r: _rate(float(r["ca_livre"]), int(r["commandes_confirmees_nettes"])), axis=1
    )
    cols = [
        "confirmatrice",
        "commandes_recues",
        "commandes_annulees",
        "commandes_confirmees_nettes",
        "taux_confirmation",
        "taux_annulation",
        "commandes_envoyees",
        "livrees",
        "en_dispatch",
        "en_livraison",
        "en_cours_logistique",
        "retours",
        "taux_livraison_finalisees",
        "taux_livraison_total",
        "taux_en_cours_logistique",
        "taux_transformation_reel",
        "taux_retour",
        "ca_livre",
        "ca_dispatch",
        "ca_en_cours_logistique",
        "ca_par_commande_confirmee",
        "decision_auto",
    ]
    return out[cols].sort_values("commandes_recues", ascending=False)


def compute_livreur_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = _group_metrics(df, "Livreur", sent_only=True).rename(columns={"Livreur": "livreur"})
    out["decision_auto"] = out.apply(_decision_livreur, axis=1)
    cols = [
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
    return out[cols].sort_values("commandes_envoyees", ascending=False)


def _decision(row: pd.Series, volume_col: str, volume_min: int) -> str:
    if row[volume_col] < volume_min:
        return "Échantillon faible"
    confirmation = row.get("taux_confirmation")
    delivery = row.get("taux_livraison_finalisees")
    returns = row.get("taux_retour")
    if (confirmation is None or confirmation >= 0.75) and (delivery is not None and delivery >= 0.75) and (returns is not None and returns <= 0.15):
        return "À pousser"
    if (delivery is not None and delivery < 0.65) or (returns is not None and returns > 0.25):
        return "À corriger"
    if (confirmation is not None and confirmation < 0.65) or (returns is not None and returns > 0.15):
        return "À surveiller"
    return "Stable"


def compute_product_metrics(df: pd.DataFrame, volume_min: int = 10) -> pd.DataFrame:
    out = _group_metrics(df, "Nom produit", orders=_product_orders(df)).rename(columns={"Nom produit": "produit"})
    decisions = out.apply(lambda r: _product_problem(r, volume_min), axis=1)
    out["decision_auto"] = decisions.apply(lambda x: x[0])
    out["probleme_probable"] = decisions.apply(lambda x: x[1])
    cols = [
        "produit",
        "commandes_recues",
        "commandes_confirmees_nettes",
        "taux_confirmation",
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
        "ca_retours",
        "ca_dispatch",
        "ca_bloque_livraison",
        "ca_en_cours_logistique",
        "panier_moyen_livre",
        "taux_transformation_reel",
        "decision_auto",
        "probleme_probable",
    ]
    return out[cols].sort_values(["ca_livre", "commandes_recues"], ascending=False)


def _dominant(df: pd.DataFrame, group_col: str, value_col: str) -> pd.Series:
    counts = df.groupby([group_col, value_col]).size().reset_index(name="n")
    idx = counts.groupby(group_col)["n"].idxmax()
    return counts.loc[idx].set_index(group_col)[value_col]


def compute_wilaya_metrics(df: pd.DataFrame, volume_min: int = 5) -> pd.DataFrame:
    out = _group_metrics(df, "Wilaya").rename(columns={"Wilaya": "wilaya"})
    sent_orders = _orders(df)
    products = _dominant(sent_orders, "Wilaya", "Nom produit")
    livreurs = _dominant(sent_orders, "Wilaya", "Livreur")
    out["produit_dominant"] = out["wilaya"].map(products).fillna("Non renseigné")
    out["livreur_dominant"] = out["wilaya"].map(livreurs).fillna("Non renseigné")
    out["decision_auto"] = out.apply(lambda r: _decision(r, "commandes_envoyees", volume_min), axis=1)
    out["taux_en_cours_livraison"] = out.apply(lambda r: _rate(r["en_livraison"], r["commandes_envoyees"]), axis=1)
    cause_action = out.apply(lambda r: _wilaya_cause_action(r, volume_min), axis=1)
    out["cause_probable"] = cause_action.apply(lambda x: x[0])
    out["action_recommandee"] = cause_action.apply(lambda x: x[1])
    cols = [
        "wilaya",
        "commandes_recues",
        "commandes_confirmees_nettes",
        "commandes_envoyees",
        "livrees",
        "en_dispatch",
        "en_livraison",
        "en_cours_logistique",
        "retours",
        "taux_livraison_finalisees",
        "taux_livraison_total",
        "taux_en_cours_logistique",
        "taux_transformation_reel",
        "taux_retour",
        "produit_dominant",
        "livreur_dominant",
        "ca_livre",
        "ca_dispatch",
        "ca_bloque_livraison",
        "ca_en_cours_logistique",
        "ca_retours",
        "cause_probable",
        "action_recommandee",
        "decision_auto",
    ]
    return out[cols].sort_values("commandes_envoyees", ascending=False)


def _pair_alerts(df: pd.DataFrame, first: str, second: str, volume_min: int) -> pd.DataFrame:
    o = _orders(df)
    rows = []
    for keys, g in o.groupby([first, second], dropna=False):
        sent = int(g["is_sent"].sum())
        dispatch = int(g["is_dispatch"].sum())
        in_delivery = int(g["is_in_delivery"].sum())
        logistics = dispatch + in_delivery
        delivered = int(g["is_delivered"].sum())
        returned = int(g["is_return_or_failed"].sum())
        row = {
            first: keys[0],
            second: keys[1],
            "commandes_envoyees": sent,
            "livrees": delivered,
            "en_dispatch": dispatch,
            "en_livraison": in_delivery,
            "en_cours_logistique": logistics,
            "retours": returned,
            "taux_livraison_finalisees": _rate(delivered, delivered + returned),
            "taux_en_cours_logistique": _rate(logistics, sent),
            "taux_retour": _rate(returned, sent),
        }
        row["decision_auto"] = _decision(pd.Series(row), "commandes_envoyees", volume_min)
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    important = out["commandes_envoyees"].ge(volume_min) & out["decision_auto"].isin(["À pousser", "À surveiller", "À corriger"])
    return out[important].sort_values(["decision_auto", "commandes_envoyees"], ascending=[True, False])


def compute_product_wilaya_alerts(df: pd.DataFrame, volume_min: int = 5) -> pd.DataFrame:
    return _pair_alerts(df, "Nom produit", "Wilaya", volume_min).rename(
        columns={"Nom produit": "produit", "Wilaya": "wilaya"}
    )


def compute_livreur_wilaya_alerts(df: pd.DataFrame, volume_min: int = 5) -> pd.DataFrame:
    return _pair_alerts(df, "Livreur", "Wilaya", volume_min).rename(
        columns={"Livreur": "livreur", "Wilaya": "wilaya"}
    )
