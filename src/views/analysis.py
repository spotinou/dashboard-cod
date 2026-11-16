"""Dashboard-level analyses built on the metric tables (advice, cross tables, summaries, export)."""
from __future__ import annotations

import pandas as pd
from io import BytesIO

from .formatting import DASH, SENSITIVE_COLUMNS, format_table, is_known_value, money, no_reliable_message, pct, reliable_rows, safe_ratio, sort_for_display


def global_metrics_table(metrics: dict) -> pd.DataFrame:
    rows = [
        ("Commandes reçues", metrics["orders_received"]),
        ("Confirmées nettes", metrics["orders_confirmed_net"]),
        ("Taux confirmation", pct(metrics["confirmation_rate"])),
        ("Annulées avant expédition", metrics["orders_cancelled"]),
        ("Taux annulation avant expédition", pct(metrics["cancellation_rate"])),
        ("Confirmées non expédiées", metrics["orders_preparation"]),
        ("Expédiées", metrics["orders_sent"]),
        ("Taux expédition", pct(metrics["shipping_rate_global"])),
        ("En dispatch", metrics.get("orders_dispatch", 0)),
        ("En cours livraison", metrics["orders_in_delivery"]),
        ("En cours logistique", metrics.get("orders_logistics", metrics.get("orders_dispatch", 0) + metrics["orders_in_delivery"])),
        ("Taux en cours logistique", pct(metrics.get("logistics_rate_on_sent"))),
        ("Taux en cours livraison", pct(metrics["in_delivery_rate_on_sent"])),
        ("Livrées finalisées", metrics["orders_delivered"]),
        ("Retours / échecs", metrics["orders_returned_failed"]),
        ("Taux livraison finalisée hors en cours", pct(metrics["delivery_finalized_rate"])),
        ("Taux livraison sur exp\u00e9di\u00e9es", pct(metrics["delivery_total_rate_on_sent"])),
        ("Taux retour", pct(metrics["return_rate_on_sent"])),
        ("Taux transformation réel", pct(metrics["transformation_real_rate"])),
        ("CA livré finalisé", money(metrics["ca_delivered"])),
        ("CA en dispatch", money(metrics.get("ca_dispatch", 0))),
        ("CA en cours livraison", money(metrics["ca_in_delivery"])),
        ("CA en cours logistique", money(metrics.get("ca_logistics", metrics.get("ca_dispatch", 0) + metrics["ca_in_delivery"]))),
        ("CA confirmé non expédié", money(metrics["ca_preparation"])),
        ("Perte CA retours", money(metrics["ca_returned_failed"])),
    ]
    return pd.DataFrame(rows, columns=["Indicateur", "Valeur"])


def amount_totals(df: pd.DataFrame, metrics: dict) -> dict[str, float | None]:
    order_amounts = (
        df.groupby("order_id", dropna=False)
        .agg(ca_total=("ca_total", "max"), is_confirmed_net=("is_confirmed_net", "max"))
        if {"order_id", "ca_total", "is_confirmed_net"}.issubset(df.columns)
        else pd.DataFrame(columns=["ca_total", "is_confirmed_net"])
    )
    total_ca = float(order_amounts["ca_total"].sum())
    confirmed_ca = float(order_amounts.loc[order_amounts["is_confirmed_net"].fillna(False), "ca_total"].sum())
    received = metrics.get("orders_received", 0)
    delivered = metrics.get("orders_delivered", 0)
    returned = metrics.get("orders_returned_failed", 0)
    return {
        "ca_total_orders": total_ca,
        "ca_confirmed": confirmed_ca,
        "panier_moyen_livre": safe_ratio(metrics.get("ca_delivered", 0), delivered),
        "ca_logistics": metrics.get("ca_logistics", metrics.get("ca_dispatch", 0) + metrics.get("ca_in_delivery", 0)),
        "panier_moyen_commande": safe_ratio(total_ca, received),
        "valeur_moyenne_retour": safe_ratio(metrics.get("ca_returned_failed", 0), returned),
    }


def product_wilaya_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = grouped_advice_metrics(df, ["Nom produit", "Wilaya"])
    if out.empty:
        return out.rename(columns={"Nom produit": "produit", "Wilaya": "wilaya"})
    orders = orders_for_advice(df)
    if not orders.empty and {"Nom produit", "Wilaya", "Livreur"}.issubset(orders.columns):
        counts = orders.groupby(["Nom produit", "Wilaya", "Livreur"], dropna=False).size().reset_index(name="n")
        idx = counts.groupby(["Nom produit", "Wilaya"])["n"].idxmax()
        dominant = counts.loc[idx, ["Nom produit", "Wilaya", "Livreur"]].rename(columns={"Livreur": "livreur_dominant"})
        out = out.merge(dominant, on=["Nom produit", "Wilaya"], how="left")
    if "livreur_dominant" not in out.columns:
        out["livreur_dominant"] = DASH
    return out.rename(columns={"Nom produit": "produit", "Wilaya": "wilaya"})


def livreur_wilaya_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = grouped_advice_metrics(df, ["Wilaya", "Livreur"])
    if out.empty:
        return out.rename(columns={"Wilaya": "wilaya", "Livreur": "livreur"})
    return out.rename(columns={"Wilaya": "wilaya", "Livreur": "livreur"})


def volume_reliability(value, volume_min: int) -> str:
    volume = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
    return "Volume suffisant" if volume >= volume_min else "Echantillon faible"


def quick_read(row: pd.Series, kind: str, volume_col: str, volume_min: int, thresholds: dict[str, float]) -> str:
    if volume_reliability(row.get(volume_col, 0), volume_min) != "Volume suffisant":
        return "Echantillon faible"
    confirmation = row.get("taux_confirmation")
    transformation = row.get("taux_transformation_reel")
    delivery = row.get("taux_livraison_total")
    returns = row.get("taux_retour")
    ca = row.get("ca_livre", 0) or 0
    in_delivery = (row.get("en_dispatch", 0) or 0) + (row.get("en_livraison", 0) or 0)
    sent = row.get("commandes_envoyees", 0) or 0
    if returns is not None and pd.notna(returns) and returns >= thresholds["return_red"]:
        if kind == "sku":
            return "SKU retour eleve"
        return "Retour eleve"
    if confirmation is not None and pd.notna(confirmation) and confirmation < thresholds["confirmation_orange"]:
        return "Confirmation faible"
    if transformation is not None and pd.notna(transformation) and transformation < thresholds["delivery_orange"] and kind in {"source", "sku", "confirmatrice_produit", "source_produit"}:
        return "Transformation faible"
    if delivery is not None and pd.notna(delivery) and delivery < thresholds["delivery_orange"]:
        return "Livraison faible"
    if sent and safe_ratio(in_delivery, sent) and safe_ratio(in_delivery, sent) > 0.30:
        return "En cours eleve"
    if ca > 0 and delivery is not None and pd.notna(delivery) and delivery >= thresholds["delivery_green"] and (returns is None or pd.isna(returns) or returns <= thresholds["return_orange"]):
        if kind == "sku":
            return "SKU solide"
        if kind in {"source", "source_produit"}:
            return "Source propre"
        if kind == "product_wilaya":
            return "Bon volume / bonne zone"
        return "Livraison correcte"
    if ca > 0:
        return "CA interessant"
    return "A surveiller"


def add_volume_reading(df: pd.DataFrame, volume_col: str, volume_min: int, kind: str, thresholds: dict[str, float]) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["fiabilite_volume"] = pd.Series(dtype=object)
        out["lecture_rapide"] = pd.Series(dtype=object)
        return out
    out["fiabilite_volume"] = out[volume_col].apply(lambda value: volume_reliability(value, volume_min)) if volume_col in out.columns else "Echantillon faible"
    out["lecture_rapide"] = out.apply(lambda row: quick_read(row, kind, volume_col, volume_min, thresholds), axis=1)
    return out


def cross_performance(df: pd.DataFrame, group_cols: list[str], rename: dict[str, str], volume_col: str, volume_min: int, kind: str, thresholds: dict[str, float]) -> pd.DataFrame:
    out = grouped_advice_metrics(df, group_cols)
    if out.empty:
        return pd.DataFrame(columns=list(rename.values()))
    out = out.rename(columns=rename)
    return add_volume_reading(out, volume_col, volume_min, kind, thresholds)


def product_livreur_performance(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    out = cross_performance(df, ["Nom produit", "Livreur"], {"Nom produit": "produit", "Livreur": "livreur"}, "commandes_envoyees", volume_min, "product_livreur", thresholds)
    if not out.empty and "livrees" in out.columns:
        out["panier_moyen_livre"] = out.apply(lambda row: safe_ratio(row.get("ca_livre", 0), row.get("livrees", 0)), axis=1)
    return out


def source_product_performance(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    if "Source" not in df.columns:
        return pd.DataFrame()
    return cross_performance(df, ["Source", "Nom produit"], {"Source": "source", "Nom produit": "produit"}, "commandes_recues", volume_min, "source_produit", thresholds)


def sku_product_performance(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    if "SKU produit" not in df.columns:
        return pd.DataFrame()
    return cross_performance(df, ["SKU produit", "Nom produit"], {"SKU produit": "sku_produit", "Nom produit": "produit"}, "commandes_recues", volume_min, "sku", thresholds)


def confirmatrice_product_performance(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    col = "Affect\u00e9e \u00e0"
    if col not in df.columns:
        return pd.DataFrame()
    return cross_performance(df, [col, "Nom produit"], {col: "confirmatrice", "Nom produit": "produit"}, "commandes_recues", volume_min, "confirmatrice_produit", thresholds)


def wilaya_livreur_comparison(df: pd.DataFrame, volume_min: int) -> pd.DataFrame:
    metrics = livreur_wilaya_performance(df)
    if metrics.empty:
        return pd.DataFrame()
    rows = []
    for wilaya, group in metrics.groupby("wilaya", dropna=False):
        if not is_known_value(wilaya):
            continue
        ranked = group.sort_values("commandes_envoyees", ascending=False).copy()
        dominant = ranked.iloc[0]
        alternatives = ranked.iloc[1:]
        alternative = alternatives.iloc[0] if not alternatives.empty else None
        dominant_reliable = int(dominant.get("commandes_envoyees", 0)) >= volume_min
        alternative_reliable = alternative is not None and int(alternative.get("commandes_envoyees", 0)) >= volume_min
        delivery_gap = None
        return_gap = None
        lecture = "Donnees insuffisantes"
        if alternative is not None:
            delivery_gap = (alternative.get("taux_livraison_total") or 0) - (dominant.get("taux_livraison_total") or 0)
            return_gap = (dominant.get("taux_retour") or 0) - (alternative.get("taux_retour") or 0)
            if dominant_reliable and alternative_reliable:
                if abs(delivery_gap) < 0.05 and abs(return_gap) < 0.05:
                    lecture = "Ecart faible"
                elif delivery_gap > 0.05 or return_gap > 0.05:
                    lecture = "Alternative meilleure"
                else:
                    lecture = "Dominant meilleur"
        rows.append(
            {
                "wilaya": wilaya,
                "livreur_dominant": dominant.get("livreur", DASH),
                "expediees_dominant": int(dominant.get("commandes_envoyees", 0)),
                "taux_livraison_dominant": dominant.get("taux_livraison_total"),
                "taux_retour_dominant": dominant.get("taux_retour"),
                "livreur_alternatif": alternative.get("livreur", DASH) if alternative is not None else DASH,
                "expediees_alternatif": int(alternative.get("commandes_envoyees", 0)) if alternative is not None else 0,
                "taux_livraison_alternatif": alternative.get("taux_livraison_total") if alternative is not None else None,
                "taux_retour_alternatif": alternative.get("taux_retour") if alternative is not None else None,
                "ecart_livraison": delivery_gap,
                "ecart_retour": return_gap,
                "fiabilite_comparaison": "Volume suffisant" if dominant_reliable and (alternative is None or alternative_reliable) else "Donnees insuffisantes",
                "lecture_rapide": lecture,
            }
        )
    return pd.DataFrame(rows)


def validation_value(validation_checks: pd.DataFrame, control_contains: str, default=0):
    if validation_checks.empty:
        return default
    row = validation_checks[validation_checks["controle"].astype(str).str.contains(control_contains, case=False, na=False)]
    if row.empty:
        return default
    value = row.iloc[0].get("valeur", default)
    parsed = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(parsed) else int(parsed)


def data_quality_has_warning(validation_checks: pd.DataFrame) -> bool:
    watched = [
        "Commandes sans wilaya",
        "Commandes sans produit",
        "Commandes sans statut",
        "Doublons lignes par commande",
        "Doublons ID commande",
        "Statuts inconnus",
        "Commandes non class",
        "Mapping dates AG-AK",
        "Commandes avec montant",
    ]
    if validation_checks.empty:
        return False
    for _, row in validation_checks.iterrows():
        control = str(row.get("controle", ""))
        if not any(item.lower() in control.lower() for item in watched):
            continue
        value = pd.to_numeric(row.get("valeur"), errors="coerce")
        if pd.notna(value) and value > 0:
            return True
    return False


def orders_for_advice(df: pd.DataFrame) -> pd.DataFrame:
    affectee_col = "Affect\u00e9e \u00e0"
    aggregations = {
        "Source": "first",
        "SKU produit": "first",
        "Nom produit": "first",
        "Wilaya": "first",
        "Livreur": "first",
        affectee_col: "first",
        "is_cancelled": "max",
        "is_confirmed_net": "max",
        "is_in_confirmation": "max",
        "is_preparation": "max",
        "is_dispatch": "max",
        "is_sent": "max",
        "is_delivered": "max",
        "is_in_delivery": "max",
        "is_return_or_failed": "max",
        "ca_delivered": "max",
        "ca_in_confirmation": "max",
        "ca_dispatch": "max",
        "ca_in_delivery": "max",
        "ca_preparation": "max",
        "ca_returned_failed": "max",
    }
    available = {col: agg for col, agg in aggregations.items() if col in df.columns}
    return df.groupby("order_id", dropna=False).agg(available).reset_index()


def dominant_value(frame: pd.DataFrame, group_col: str, value_col: str, fallback: str = "Non renseign\u00e9") -> pd.Series:
    if frame.empty or group_col not in frame.columns or value_col not in frame.columns:
        return pd.Series(dtype=object)
    counts = frame.groupby([group_col, value_col], dropna=False).size().reset_index(name="n")
    idx = counts.groupby(group_col)["n"].idxmax()
    return counts.loc[idx].set_index(group_col)[value_col].fillna(fallback)


def grouped_advice_metrics(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    orders = orders_for_advice(df)
    if orders.empty or any(col not in orders.columns for col in group_cols):
        return pd.DataFrame()
    rows = []
    for keys, group in orders.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        received = len(group)
        confirmed = int(group["is_confirmed_net"].sum())
        sent = int(group["is_sent"].sum())
        in_confirmation = int(group["is_in_confirmation"].sum()) if "is_in_confirmation" in group.columns else 0
        preparation = int(group["is_preparation"].sum()) if "is_preparation" in group.columns else 0
        dispatch = int(group["is_dispatch"].sum()) if "is_dispatch" in group.columns else 0
        in_delivery = int(group["is_in_delivery"].sum())
        logistics = dispatch + in_delivery
        delivered = int(group["is_delivered"].sum())
        returned = int(group["is_return_or_failed"].sum())
        row = {col: value for col, value in zip(group_cols, keys)}
        row.update({
            "commandes_recues": received,
            "commandes_confirmees_nettes": confirmed,
            "en_confirmation": in_confirmation,
            "en_preparation": preparation,
            "taux_preparation": safe_ratio(preparation, confirmed),
            "commandes_envoyees": sent,
            "livrees": delivered,
            "en_dispatch": dispatch,
            "taux_dispatch": safe_ratio(dispatch, sent),
            "en_livraison": in_delivery,
            "taux_en_livraison": safe_ratio(in_delivery, sent),
            "en_cours_logistique": logistics,
            "retours": returned,
            "taux_confirmation": safe_ratio(int(group["is_confirmed_net"].sum()), received),
            "taux_livraison_total": safe_ratio(delivered, sent),
            "taux_en_cours_logistique": safe_ratio(logistics, sent),
            "taux_transformation_reel": safe_ratio(delivered, received),
            "taux_retour": safe_ratio(returned, sent),
            "ca_livre": float(group["ca_delivered"].sum()),
            "ca_dispatch": float(group["ca_dispatch"].sum()) if "ca_dispatch" in group.columns else 0.0,
            "ca_bloque_livraison": float(group["ca_in_delivery"].sum()),
            "ca_en_cours_logistique": (float(group["ca_dispatch"].sum()) if "ca_dispatch" in group.columns else 0.0) + float(group["ca_in_delivery"].sum()),
            "ca_retours": float(group["ca_returned_failed"].sum()),
            "panier_moyen_livre": safe_ratio(float(group["ca_delivered"].sum()), delivered),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def preparation_metrics_by_dimension(df: pd.DataFrame, group_col: str, label_col: str) -> pd.DataFrame:
    metrics = grouped_advice_metrics(df, [group_col])
    columns = [label_col, "en_preparation", "taux_preparation"]
    if metrics.empty:
        return pd.DataFrame(columns=columns)
    return metrics.rename(columns={group_col: label_col})[columns].copy()


def confidence_label(volume: int, volume_min: int, gap: float = 0.0) -> str:
    if volume < volume_min:
        return "Non exploitable"
    if volume >= volume_min * 2 and gap >= 0.10:
        return "\u00c9lev\u00e9"
    if gap >= 0.05 or volume >= volume_min * 2:
        return "Moyen"
    return "Faible"


def product_action(row: pd.Series, volume_min: int, thresholds: dict[str, float]) -> tuple[str, str, str]:
    if row.get("commandes_recues", 0) < volume_min:
        return "\u00c9chantillon faible", "Attendre plus de donn\u00e9es", "Faible"
    confirmation = row.get("taux_confirmation")
    delivery = row.get("taux_livraison_total")
    transformation = row.get("taux_transformation_reel")
    returns = row.get("taux_retour")
    ca = row.get("ca_livre", 0)
    loss = row.get("ca_retours", 0)
    if confirmation is not None and confirmation < thresholds["confirmation_orange"]:
        return "Confirmation faible", "Corriger offre, prix, page produit, script confirmation ou qualit\u00e9 source", "Moyen"
    if delivery is not None and delivery < thresholds["delivery_orange"] and (confirmation is None or confirmation >= thresholds["confirmation_orange"]):
        return "Livraison faible", "V\u00e9rifier wilayas et livreur dominant avant de couper le produit", "Moyen"
    if returns is not None and returns >= thresholds["return_red"]:
        action = "Limiter temporairement ou stop test" if ca <= loss else "V\u00e9rifier promesse publicitaire, qualit\u00e9 produit, attentes client, SAV"
        return "Retour \u00e9lev\u00e9", action, "\u00c9lev\u00e9" if row.get("commandes_envoyees", 0) >= volume_min * 2 else "Moyen"
    if ca > 0 and delivery is not None and delivery >= thresholds["delivery_green"] and returns is not None and returns <= thresholds["return_orange"]:
        return "Produit fiable", "Augmenter le volume progressivement", "\u00c9lev\u00e9" if row.get("commandes_envoyees", 0) >= volume_min * 2 else "Moyen"
    return "Performance moyenne", "Maintenir et surveiller par source, SKU, wilaya et livreur", "Moyen"


def add_product_advice(products: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    out = products.copy()
    if out.empty:
        return out
    advice = out.apply(lambda row: product_action(row, volume_min, thresholds), axis=1)
    out["diagnostic"] = advice.apply(lambda item: item[0])
    out["action_recommandee"] = advice.apply(lambda item: item[1])
    out["niveau_confiance"] = advice.apply(lambda item: item[2])
    return out


def compute_confirmatrice_quality(df: pd.DataFrame, confirmation: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    affectee_col = "Affect\u00e9e \u00e0"
    losses = grouped_advice_metrics(df, [affectee_col])
    if not losses.empty:
        losses = losses.rename(columns={affectee_col: "confirmatrice"})[["confirmatrice", "ca_retours"]]
    out = confirmation.merge(losses, on="confirmatrice", how="left") if not losses.empty else confirmation.copy()
    out["ca_retours"] = out.get("ca_retours", 0).fillna(0)
    rows = []
    for _, row in out.iterrows():
        volume = int(row.get("commandes_recues", 0))
        confirmation_rate = row.get("taux_confirmation")
        delivery = row.get("taux_livraison_total")
        returns = row.get("taux_retour")
        if volume < volume_min or not is_known_value(row.get("confirmatrice")):
            diagnostic, action, confiance = "\u00c9chantillon faible", "Attendre plus de donn\u00e9es", "Non exploitable"
        elif confirmation_rate is not None and confirmation_rate >= thresholds["confirmation_green"] and delivery is not None and delivery < thresholds["delivery_orange"]:
            diagnostic, action, confiance = "Confirmation trop permissive possible", "Auditer appels, objections client, promesse produit et qualit\u00e9 des leads", "Moyen"
        elif confirmation_rate is not None and confirmation_rate < thresholds["confirmation_orange"]:
            diagnostic, action, confiance = "Faible conversion confirmation", "V\u00e9rifier script, timing d'appel, prix, offre et objections", "Moyen"
        elif returns is not None and returns >= thresholds["return_red"]:
            diagnostic, action, confiance = "Mauvaise qualit\u00e9 de confirmation possible", "Contr\u00f4ler si les clients sont r\u00e9ellement qualifi\u00e9s avant exp\u00e9dition", "\u00c9lev\u00e9"
        elif confirmation_rate is not None and confirmation_rate >= thresholds["confirmation_green"] and delivery is not None and delivery >= thresholds["delivery_green"] and returns is not None and returns <= thresholds["return_orange"]:
            diagnostic, action, confiance = "Confirmatrice fiable", "Lui attribuer plus de commandes si capacit\u00e9 disponible", "\u00c9lev\u00e9"
        else:
            diagnostic, action, confiance = "\u00c0 surveiller", "Suivre livraison sur exp\u00e9di\u00e9es, retours et CA livr\u00e9 avant de r\u00e9allouer plus de volume", "Moyen"
        rows.append({**row.to_dict(), "diagnostic": diagnostic, "action_recommandee": action, "niveau_confiance": confiance})
    cols = ["confirmatrice", "commandes_recues", "taux_confirmation", "taux_livraison_total", "taux_transformation_reel", "taux_retour", "ca_livre", "ca_retours", "diagnostic", "action_recommandee", "niveau_confiance"]
    return pd.DataFrame(rows)[cols] if rows else pd.DataFrame(columns=cols)


def compute_livreur_wilaya_arbitrage(df: pd.DataFrame, volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    metrics = grouped_advice_metrics(df, ["Wilaya", "Livreur"])
    if metrics.empty:
        return pd.DataFrame()
    metrics = metrics[metrics["Livreur"].apply(is_known_value)].copy()
    orders = orders_for_advice(df)
    products = dominant_value(orders, "Wilaya", "Nom produit")
    rows = []
    for wilaya, group in metrics.groupby("Wilaya", dropna=False):
        if not is_known_value(wilaya):
            continue
        reliable = group[group["commandes_envoyees"].ge(volume_min)].copy()
        current = group.sort_values("commandes_envoyees", ascending=False).iloc[0]
        base = {"wilaya": wilaya, "produit_dominant": products.get(wilaya, "Non renseign\u00e9"), "livreur_actuel": current["Livreur"], "expediees_actuel": int(current["commandes_envoyees"]), "taux_livraison_total_actuel": current.get("taux_livraison_total"), "taux_retour_actuel": current.get("taux_retour")}
        if reliable.empty or int(current["commandes_envoyees"]) < volume_min:
            rows.append({**base, "meilleur_livreur_alternatif": "-", "expediees_alternatif": 0, "taux_livraison_total_alternatif": None, "taux_retour_alternatif": None, "ecart_livraison": None, "ecart_retour": None, "recommandation": "Pas assez de volume pour recommander un changement de livreur.", "niveau_confiance": "Non exploitable"})
            continue
        alternatives = reliable[reliable["Livreur"] != current["Livreur"]].copy()
        if alternatives.empty:
            rows.append({**base, "meilleur_livreur_alternatif": "-", "expediees_alternatif": 0, "taux_livraison_total_alternatif": None, "taux_retour_alternatif": None, "ecart_livraison": None, "ecart_retour": None, "recommandation": f"Garder {current['Livreur']} sur cette wilaya.", "niveau_confiance": "Moyen"})
            continue
        alternatives["_score"] = alternatives["taux_livraison_total"].fillna(0) - alternatives["taux_retour"].fillna(0)
        alt = alternatives.sort_values("_score", ascending=False).iloc[0]
        delivery_gap = (alt.get("taux_livraison_total") or 0) - (current.get("taux_livraison_total") or 0)
        return_gap = (current.get("taux_retour") or 0) - (alt.get("taux_retour") or 0)
        if delivery_gap >= 0.08 or return_gap >= 0.05:
            recommendation = f"D\u00e9l\u00e9guer cette wilaya \u00e0 {alt['Livreur']}, car il performe mieux que {current['Livreur']} sur cette wilaya."
        elif (current.get("taux_livraison_total") or 0) < thresholds["delivery_orange"] and (current.get("taux_retour") or 0) >= thresholds["return_red"]:
            recommendation = "Aucun livreur fiable identifi\u00e9 sur cette wilaya. Limiter le volume ou v\u00e9rifier la qualit\u00e9 des commandes."
        else:
            recommendation = f"Garder {current['Livreur']} sur cette wilaya."
        rows.append({**base, "meilleur_livreur_alternatif": alt["Livreur"], "expediees_alternatif": int(alt["commandes_envoyees"]), "taux_livraison_total_alternatif": alt.get("taux_livraison_total"), "taux_retour_alternatif": alt.get("taux_retour"), "ecart_livraison": delivery_gap, "ecart_retour": return_gap, "recommandation": recommendation, "niveau_confiance": confidence_label(min(int(current["commandes_envoyees"]), int(alt["commandes_envoyees"])), volume_min, abs(delivery_gap))})
    return pd.DataFrame(rows).sort_values(["niveau_confiance", "expediees_actuel"], ascending=[True, False]).head(20)


# P2 note: the business aggregation helpers below stay in ui.py for this pass to avoid a broad refactor.
def compute_dimension_performance(df: pd.DataFrame, group_cols: list[str], volume_min: int, thresholds: dict[str, float]) -> pd.DataFrame:
    out = grouped_advice_metrics(df, group_cols)
    if out.empty:
        return out
    if "SKU produit" in group_cols:
        orders = orders_for_advice(df)
        products = dominant_value(orders, "SKU produit", "Nom produit")
        out["produit_associe"] = out["SKU produit"].map(products).fillna("Non renseign\u00e9")
    advice = out.apply(lambda row: product_action(row, volume_min, thresholds), axis=1)
    out["diagnostic"] = advice.apply(lambda item: item[0])
    out["action_recommandee"] = advice.apply(lambda item: item[1])
    out["niveau_confiance"] = advice.apply(lambda item: item[2])
    return out.rename(columns={"Source": "source", "SKU produit": "sku_produit"})


def compute_loss_tables(products: pd.DataFrame, wilayas: pd.DataFrame, livreurs: pd.DataFrame, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    product_cols = ["produit", "retours", "ca_retours", "taux_retour", "action_recommandee"]
    wilaya_cols = ["wilaya", "retours", "ca_retours", "taux_retour", "livreur_dominant", "action_recommandee"]
    livreur_cols = ["livreur", "retours", "ca_retours", "taux_retour", "wilayas_problematiques", "action_recommandee"]

    def with_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        out = frame.copy()
        for col in columns:
            if col not in out.columns:
                out[col] = pd.NA
        return out[columns]

    if products.empty or "ca_retours" not in products.columns:
        product_loss = pd.DataFrame(columns=product_cols)
    else:
        product_loss = products[pd.to_numeric(products["ca_retours"], errors="coerce").fillna(0).gt(0)].copy()
        product_loss = sort_for_display(product_loss, ["ca_retours"]).head(5)
        product_loss["action_recommandee"] = "V\u00e9rifier promesse, qualit\u00e9 produit, ciblage et SAV avant scale"

    if wilayas.empty or "ca_retours" not in wilayas.columns:
        wilaya_loss = pd.DataFrame(columns=wilaya_cols)
    else:
        wilaya_loss = wilayas[pd.to_numeric(wilayas["ca_retours"], errors="coerce").fillna(0).gt(0)].copy()
        wilaya_loss = sort_for_display(wilaya_loss, ["ca_retours"]).head(5)
        wilaya_loss["action_recommandee"] = "Comparer livreurs et limiter le volume tant que les retours restent \u00e9lev\u00e9s"

    if df.empty or "order_id" not in df.columns:
        by_livreur_wilaya = pd.DataFrame()
    else:
        by_livreur_wilaya = grouped_advice_metrics(df, ["Livreur", "Wilaya"])
    if not by_livreur_wilaya.empty and {"Livreur", "Wilaya", "ca_retours"}.issubset(by_livreur_wilaya.columns):
        problematic = by_livreur_wilaya[pd.to_numeric(by_livreur_wilaya["ca_retours"], errors="coerce").fillna(0).gt(0)].sort_values("ca_retours", ascending=False)
    else:
        problematic = pd.DataFrame(columns=["Livreur", "Wilaya", "ca_retours"])
    if problematic.empty:
        top_wilayas = pd.DataFrame(columns=["Livreur", "wilayas_problematiques"])
    else:
        top_wilayas = (
            problematic.groupby("Livreur")["Wilaya"]
            .apply(lambda s: ", ".join(s.head(3).astype(str)))
            .rename("wilayas_problematiques")
            .reset_index()
        )

    if livreurs.empty or "ca_retours" not in livreurs.columns or "livreur" not in livreurs.columns:
        livreur_loss = pd.DataFrame(columns=livreur_cols)
    else:
        livreur_loss = livreurs[pd.to_numeric(livreurs["ca_retours"], errors="coerce").fillna(0).gt(0)].copy()
        if not livreur_loss.empty:
            livreur_loss = livreur_loss.merge(top_wilayas, left_on="livreur", right_on="Livreur", how="left")
            livreur_loss = livreur_loss.drop(columns=["Livreur"], errors="ignore")
        if "wilayas_problematiques" not in livreur_loss.columns:
            livreur_loss["wilayas_problematiques"] = pd.NA
        livreur_loss["wilayas_problematiques"] = livreur_loss["wilayas_problematiques"].fillna("\u2014")
        livreur_loss["action_recommandee"] = "Auditer les wilayas probl\u00e9matiques et tester un arbitrage livreur"
        livreur_loss = sort_for_display(livreur_loss, ["ca_retours"]).head(5)

    return with_columns(product_loss, product_cols), with_columns(wilaya_loss, wilaya_cols), with_columns(livreur_loss, livreur_cols)


def compute_opportunities(products: pd.DataFrame, wilayas: pd.DataFrame, product_wilaya: pd.DataFrame, volume_min_product: int, volume_min_sent: int, thresholds: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prod = products[products["commandes_recues"].ge(volume_min_product) & products["taux_confirmation"].ge(thresholds["confirmation_green"]) & products["taux_livraison_total"].ge(thresholds["delivery_green"]) & products["taux_retour"].le(thresholds["return_orange"]) & products["ca_livre"].gt(0)].copy()
    prod["objet"] = prod.get("produit", "")
    prod["volume"] = prod.get("commandes_recues", 0)
    prod["recommandation"] = "Augmenter progressivement le volume"
    wil = wilayas[wilayas["commandes_envoyees"].ge(volume_min_sent) & wilayas["taux_livraison_total"].ge(thresholds["delivery_green"]) & wilayas["taux_retour"].le(thresholds["return_orange"]) & wilayas["ca_livre"].gt(0)].copy()
    wil["objet"] = wil.get("wilaya", "")
    wil["volume"] = wil.get("commandes_envoyees", 0)
    wil["recommandation"] = "Augmenter progressivement le volume sur cette wilaya"
    pw = product_wilaya.copy()
    if not pw.empty and "taux_livraison_total" not in pw.columns and "taux_livraison_finalisees" in pw.columns:
        pw["taux_livraison_total"] = pw["taux_livraison_finalisees"]
    needed = {"commandes_envoyees", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour"}
    if not needed.issubset(pw.columns):
        pw = pd.DataFrame()
    else:
        pw = pw[pw["commandes_envoyees"].ge(volume_min_sent) & pw["taux_livraison_total"].ge(thresholds["delivery_green"]) & pw["taux_retour"].le(thresholds["return_orange"])].copy()
        if not pw.empty:
            pw["objet"] = pw["produit"].astype(str) + " \u00d7 " + pw["wilaya"].astype(str)
            pw["volume"] = pw["commandes_envoyees"]
            pw["ca_livre"] = 0.0
            pw["recommandation"] = "Pousser ce produit dans cette wilaya, \u00e9viter les zones faibles"
    cols = ["objet", "volume", "taux_confirmation", "taux_livraison_total", "taux_en_cours_logistique", "taux_retour", "ca_livre", "recommandation"]
    return sort_for_display(prod, ["ca_livre"]).head(5)[[c for c in cols if c in prod.columns]], sort_for_display(wil, ["ca_livre"]).head(5)[[c for c in cols if c in wil.columns]], sort_for_display(pw, ["volume"]).head(5)[[c for c in cols if c in pw.columns]] if not pw.empty else pd.DataFrame(columns=cols)


def compute_priority_actions(products: pd.DataFrame, wilayas: pd.DataFrame, confirmation_quality: pd.DataFrame, arbitrage: pd.DataFrame, opportunities: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame], volume_min_product: int, volume_min_sent: int, thresholds: dict[str, float]) -> pd.DataFrame:
    rows = []
    for _, row in sort_for_display(products[products["ca_retours"].gt(0)], ["ca_retours"]).head(3).iterrows():
        if row.get("commandes_recues", 0) < volume_min_product:
            continue
        priority = "Rouge" if (row.get("taux_retour") or 0) >= thresholds["return_red"] else "Orange"
        rows.append({"priorite": priority, "objet": f"Produit {row['produit']}", "probleme_detecte": "Retour \u00e9lev\u00e9 apr\u00e8s exp\u00e9dition", "recommandation_concrete": "Stopper le scale et v\u00e9rifier promesse publicitaire + qualit\u00e9 produit", "preuve_data": f"Taux retour {pct(row.get('taux_retour'))}, perte CA retours {money(row.get('ca_retours'))}", "impact_estime": "\u00c9vite d'augmenter une perte d\u00e9j\u00e0 visible", "niveau_confiance": confidence_label(int(row.get("commandes_recues", 0)), volume_min_product, row.get("taux_retour") or 0), "_impact": row.get("ca_retours", 0)})
    if not arbitrage.empty:
        for _, row in arbitrage[arbitrage["recommandation"].astype(str).str.contains("D\u00e9l\u00e9guer", case=False, na=False)].head(2).iterrows():
            rows.append({"priorite": "Rouge", "objet": f"Wilaya {row['wilaya']}", "probleme_detecte": f"{row['livreur_actuel']} performe moins bien que {row['meilleur_livreur_alternatif']}", "recommandation_concrete": row["recommandation"], "preuve_data": f"{row['meilleur_livreur_alternatif']} = {pct(row['taux_livraison_total_alternatif'])} livraison sur exp\u00e9di\u00e9es vs {row['livreur_actuel']} = {pct(row['taux_livraison_total_actuel'])}", "impact_estime": "R\u00e9duction probable des retours / meilleure finalisation", "niveau_confiance": row["niveau_confiance"], "_impact": abs(row.get("ecart_livraison") or 0) * row.get("expediees_actuel", 0)})
    bad_conf = confirmation_quality[confirmation_quality["diagnostic"].astype(str).str.contains("permissive|Mauvaise", case=False, na=False)] if not confirmation_quality.empty else pd.DataFrame()
    for _, row in sort_for_display(bad_conf, ["ca_retours"]).head(1).iterrows():
        rows.append({"priorite": "Orange", "objet": f"Confirmatrice {row['confirmatrice']}", "probleme_detecte": row["diagnostic"], "recommandation_concrete": row["action_recommandee"], "preuve_data": f"Confirmation {pct(row.get('taux_confirmation'))}, livraison sur exp\u00e9di\u00e9es {pct(row.get('taux_livraison_total'))}, retour {pct(row.get('taux_retour'))}", "impact_estime": "Am\u00e9liore la qualit\u00e9 des commandes exp\u00e9di\u00e9es", "niveau_confiance": row["niveau_confiance"], "_impact": row.get("ca_retours", 0)})
    opp_products, opp_wilayas, _ = opportunities
    for _, row in pd.concat([opp_products.head(1), opp_wilayas.head(1)], ignore_index=True).iterrows():
        rows.append({"priorite": "Vert", "objet": str(row.get("objet")), "probleme_detecte": "Opportunit\u00e9 fiable \u00e0 pousser", "recommandation_concrete": row.get("recommandation", "Augmenter progressivement le volume"), "preuve_data": f"Volume {int(row.get('volume', 0))}, livraison sur exp\u00e9di\u00e9es {pct(row.get('taux_livraison_total'))}, retour {pct(row.get('taux_retour'))}, CA livr\u00e9 {money(row.get('ca_livre', 0))}", "impact_estime": "Zone ou produit exploitable", "niveau_confiance": confidence_label(int(row.get("volume", 0)), volume_min_sent, row.get("taux_livraison_total") or 0), "_impact": row.get("ca_livre", 0)})
    if not rows:
        return pd.DataFrame([{"priorite": "Info", "objet": "Donn\u00e9es", "probleme_detecte": "Donn\u00e9es insuffisantes", "recommandation_concrete": "Pas assez de donn\u00e9es pour recommander une action fiable.", "preuve_data": "Aucun segment fiable ne d\u00e9passe les seuils actifs", "impact_estime": "Non estimable", "niveau_confiance": "Non exploitable", "_impact": 0}]).drop(columns="_impact")
    priority_order = {"Rouge": 0, "Orange": 1, "Vert": 2, "Info": 3}
    out = pd.DataFrame(rows)
    out["_priority_order"] = out["priorite"].map(priority_order).fillna(9)
    return out.sort_values(["_priority_order", "_impact"], ascending=[True, False]).head(7).drop(columns=["_impact", "_priority_order"])


def build_export(metrics: dict, tables: dict[str, pd.DataFrame], clean_df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        global_metrics_table(metrics).to_excel(writer, sheet_name="Resume_Global", index=False)
        for sheet, table in tables.items():
            format_table(table).to_excel(writer, sheet_name=sheet[:31], index=False)
        clean_df.drop(columns=[c for c in SENSITIVE_COLUMNS if c in clean_df.columns], errors="ignore").to_excel(
            writer, sheet_name="Donnees_Nettoyees", index=False
        )
    return output.getvalue()


def confirmation_summary(confirmation: pd.DataFrame, volume_min: int) -> list[str]:
    if confirmation.empty:
        return ["Aucune donn\u00e9e de confirmation avec les filtres actuels."]
    reliable = reliable_rows(confirmation, "confirmatrice", "commandes_recues", volume_min)
    if reliable.empty:
        return [no_reliable_message()]
    best = reliable.sort_values("taux_confirmation", ascending=False).iloc[0]
    most_cancel = reliable.sort_values("commandes_annulees", ascending=False).iloc[0]
    high_return = reliable.dropna(subset=["taux_retour"]).sort_values("taux_retour", ascending=False)
    bullets = [
        f"Meilleur taux de confirmation fiable : {best['confirmatrice']} avec {pct(best['taux_confirmation'])}.",
        f"Plus gros volume d'annulations fiable : {most_cancel['confirmatrice']} avec {int(most_cancel['commandes_annulees'])} commandes annul\u00e9es.",
    ]
    if not high_return.empty:
        row = high_return.iloc[0]
        bullets.append(f"Retour le plus sensible apr\u00e8s envoi : {row['confirmatrice']} avec {pct(row['taux_retour'])}.")
    return bullets


def delivery_summary(livreurs: pd.DataFrame, volume_min: int) -> list[str]:
    if livreurs.empty:
        return ["Aucune commande envoy\u00e9e avec les filtres actuels."]
    reliable = reliable_rows(livreurs, "livreur", "commandes_envoyees", volume_min)
    if reliable.empty:
        return [no_reliable_message()]
    most_sent = reliable.sort_values("commandes_envoyees", ascending=False).iloc[0]
    highest_return = reliable.dropna(subset=["taux_retour"]).sort_values("taux_retour", ascending=False)
    bullets = [
        f"Livreur principal fiable : {most_sent['livreur']} avec {int(most_sent['commandes_envoyees'])} commandes exp\u00e9di\u00e9es.",
        "Les commandes en pr\u00e9paration restent exclues des KPI livreur.",
    ]
    if not highest_return.empty:
        row = highest_return.iloc[0]
        bullets.insert(1, f"Retour le plus \u00e9lev\u00e9 : {row['livreur']} avec {pct(row['taux_retour'])}.")
    return bullets


def product_summary(products: pd.DataFrame, volume_min: int) -> list[str]:
    if products.empty:
        return ["Aucun produit disponible avec les filtres actuels."]
    reliable = reliable_rows(products, "produit", "commandes_recues", volume_min)
    if reliable.empty:
        return [no_reliable_message()]
    weak = products[products["commandes_recues"] < volume_min]
    bullets = [f"{len(reliable)} produit(s) ont un volume fiable ; {len(weak)} restent en \u00e9chantillon faible."]
    push = reliable[reliable["decision_auto"].astype(str).str.contains("pousser|scaler", case=False, na=False)]
    problems = reliable[reliable["decision_auto"].astype(str).str.contains("surveiller|corriger", case=False, na=False)].sort_values(["ca_retours", "commandes_recues"], ascending=False)
    if not push.empty:
        row = push.sort_values("ca_livre", ascending=False).iloc[0]
        bullets.append(f"Produit le plus int\u00e9ressant \u00e0 pousser : {row['produit']} avec {money(row['ca_livre'])} de CA livr\u00e9.")
    if not problems.empty:
        row = problems.iloc[0]
        bullets.append(f"Vrai probl\u00e8me prioritaire : {row['produit']} avec {money(row['ca_retours'])} de perte CA retours.")
    return bullets


def wilaya_summary(wilayas: pd.DataFrame, volume_min: int) -> list[str]:
    if wilayas.empty:
        return ["Aucune wilaya disponible avec les filtres actuels."]
    reliable = reliable_rows(wilayas, "wilaya", "commandes_envoyees", volume_min)
    if reliable.empty:
        return [no_reliable_message()]
    push = reliable[reliable["decision_auto"].astype(str).str.contains("pousser", case=False, na=False)]
    problems = reliable[reliable["decision_auto"].astype(str).str.contains("surveiller|corriger", case=False, na=False)].sort_values(["ca_retours", "commandes_envoyees"], ascending=False)
    bullets = []
    if not push.empty:
        row = push.sort_values("ca_livre", ascending=False).iloc[0]
        bullets.append(f"Wilaya \u00e0 pousser en priorit\u00e9 : {row['wilaya']} avec {money(row['ca_livre'])} de CA livr\u00e9.")
    if not problems.empty:
        row = problems.iloc[0]
        bullets.append(f"Wilaya \u00e0 traiter : {row['wilaya']} avec {money(row['ca_retours'])} de perte CA retours.")
    return bullets or ["Pas de probl\u00e8me wilaya marqu\u00e9 avec les seuils actuels."]


def validation_summary(validation_checks: pd.DataFrame) -> list[str]:
    failed = validation_checks[validation_checks["statut"] != "OK"]
    if failed.empty:
        return ["Les \u00e9galit\u00e9s COD et contr\u00f4les principaux sont valid\u00e9s."]
    return [f"{len(failed)} contr\u00f4le(s) demandent v\u00e9rification : " + ", ".join(failed["controle"].head(3).tolist())]
