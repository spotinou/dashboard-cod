from __future__ import annotations

import pandas as pd


def _status(ok: bool) -> str:
    return "OK" if ok else "A verifier"


def _examples(values: pd.Series, limit: int = 5) -> str:
    clean = [str(value) for value in values.dropna().tolist() if str(value).strip()]
    return ", ".join(clean[:limit]) if clean else "?"


def _is_missing_text(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip().str.lower()
    return normalized.str.startswith("non renseign", na=False)


def compute_validation_checks(df: pd.DataFrame, global_metrics: dict) -> pd.DataFrame:
    """Return operational checks that help validate COD totals."""
    rows = []

    def add(control: str, valeur: int | float | str, attendu: str, ok: bool, statut: str | None = None, details: str = "") -> None:
        rows.append(
            {
                "controle": control,
                "valeur": valeur,
                "attendu": attendu,
                "statut": statut if statut is not None else _status(ok),
                "details": details,
            }
        )

    line_count = len(df)
    unique_orders = df["order_id"].nunique(dropna=False)
    duplicate_lines = int(line_count - unique_orders)
    duplicate_counts = df["order_id"].value_counts(dropna=False)
    duplicated_ids = duplicate_counts[duplicate_counts > 1]
    duplicated_orders = int(len(duplicated_ids))
    duplicated_rows = int(duplicated_ids.sum()) if not duplicated_ids.empty else 0
    duplicate_examples = _examples(duplicated_ids.index.to_series())

    missing_status = int(_is_missing_text(df["Statut commande"]).sum())
    missing_product = int(_is_missing_text(df["Nom produit"]).sum())
    missing_wilaya = int(_is_missing_text(df["Wilaya"]).sum())
    missing_livreur = int(_is_missing_text(df["Livreur"]).sum())
    zero_amount = int(df["ca_total"].eq(0).sum())

    unknown_mask = df["status_norm"].eq("inconnu") if "status_norm" in df.columns else pd.Series(False, index=df.index)
    unknown_orders = int(df.loc[unknown_mask, "order_id"].nunique(dropna=False))
    unknown_breakdown = df.loc[unknown_mask, "Statut commande"].value_counts(dropna=False)
    unknown_details = "; ".join(f"{status}: {count}" for status, count in unknown_breakdown.items()) if not unknown_breakdown.empty else ""
    status_distribution = df["status_norm"].value_counts(dropna=False) if "status_norm" in df.columns else pd.Series(dtype=int)
    status_distribution_details = "; ".join(f"{status}: {count}" for status, count in status_distribution.items())

    unclassified_mask = df["is_unclassified"] if "is_unclassified" in df.columns else pd.Series(False, index=df.index)
    unclassified_orders = int(df.loc[unclassified_mask, "order_id"].nunique(dropna=False))

    fallback_columns = df.attrs.get("date_fallback_columns", {}) or {}
    fallback_details = ", ".join(f"{target} <= {source}" for target, source in fallback_columns.items())

    received = int(global_metrics["orders_received"])
    cancelled = int(global_metrics["orders_cancelled"])
    confirmed = int(global_metrics["orders_confirmed_net"])
    in_confirmation = int(global_metrics.get("orders_in_confirmation", 0))
    preparation = int(global_metrics["orders_preparation"])
    sent = int(global_metrics["orders_sent"])
    dispatch = int(global_metrics.get("orders_dispatch", 0))
    delivered = int(global_metrics["orders_delivered"])
    in_delivery = int(global_metrics["orders_in_delivery"])
    logistics = int(global_metrics.get("orders_logistics", dispatch + in_delivery))
    returned = int(global_metrics["orders_returned_failed"])
    unclassified = int(global_metrics.get("orders_unclassified", unclassified_orders))

    add("Lignes Excel", line_count, "Information", line_count > 0)
    add("Commandes uniques", unique_orders, "Doit correspondre aux commandes recues", unique_orders == received)
    add("Doublons lignes par commande", duplicate_lines, "0 si une ligne = une commande", duplicate_lines == 0)
    add(
        "Doublons ID commande",
        duplicated_orders,
        "0 commande concernee",
        duplicated_orders == 0,
        statut="Critique" if duplicated_orders else "OK",
        details=(
            "L'export semble contenir plusieurs lignes pour une meme commande. "
            f"Lignes doublonnees: {duplicated_rows}. Exemples ID: {duplicate_examples}. "
            "Les KPI CA/produit/SKU peuvent etre fausses."
        ) if duplicated_orders else "",
    )
    add("Commandes sans statut", missing_status, "0 recommande", missing_status == 0)
    add("Repartition statuts normalises", status_distribution_details, "Information", True)
    add(
        "Statuts inconnus",
        unknown_orders,
        "0 commande avec statut non reconnu",
        unknown_orders == 0,
        statut="Critique" if unknown_orders else "OK",
        details=(
            "Ces commandes sont incluses dans les recues mais non classees correctement dans le funnel COD. "
            f"Detail statuts: {unknown_details}"
        ) if unknown_orders else "",
    )
    add(
        "Commandes non classees / statut a verifier",
        unclassified_orders,
        "0 commande confirmee nette hors preparation/expedition",
        unclassified_orders == 0,
        statut="Critique" if unclassified_orders else "OK",
        details="Ces commandes restent dans les recues et confirmees nettes, mais ne sont pas affectees a une categorie operationnelle.",
    )
    add(
        "Mapping dates AG-AK",
        len(fallback_columns),
        "0 fallback positionnel utilise",
        not fallback_columns,
        statut="A verifier" if fallback_columns else "OK",
        details=(
            "Mapping des dates base sur les positions AG-AK car les noms de colonnes n'ont pas ete reconnus. "
            f"Verifier que le format d'export n'a pas change. {fallback_details}"
        ) if fallback_columns else "",
    )
    add("Commandes sans produit", missing_product, "0 recommande", missing_product == 0)
    add("Commandes sans wilaya", missing_wilaya, "0 recommande", missing_wilaya == 0)
    add("Commandes sans livreur", missing_livreur, "Peut etre normal si annulees/non envoyees", True)
    add("Commandes avec montant a 0", zero_amount, "A surveiller", True)
    add(
        "Statuts reconnus",
        "Annulee, En confirmation, En preparation, En dispatch, En livraison, Livree, Encaissee, En retour, Retournee, Echouee",
        "Referentiel COD attendu",
        True,
    )

    dispatch_mask = df["status_norm"].eq("dispatch") if "status_norm" in df.columns else pd.Series(False, index=df.index)
    dispatch_orders = int(df.loc[dispatch_mask, "order_id"].nunique(dropna=False))
    dispatch_ca = float(df.loc[dispatch_mask, "ca_total"].sum()) if "ca_total" in df.columns else 0.0
    dispatch_bad = False
    if dispatch_orders:
        dispatch_bad = bool(
            (~df.loc[dispatch_mask, "is_sent"]).any()
            or df.loc[dispatch_mask, "is_preparation"].any()
            or df.loc[dispatch_mask, "is_delivered"].any()
            or df.loc[dispatch_mask, "is_return_or_failed"].any()
            or df.loc[dispatch_mask, "is_unclassified"].any()
        )
    add(
        "Commandes en dispatch reconnues",
        f"{dispatch_orders} commandes / {dispatch_ca:.0f} DA",
        "Expediees non finalisees, ni preparation, ni livrees, ni retours",
        not dispatch_bad,
        statut="Critique" if dispatch_bad else "OK",
    )
    add(
        "Recues = confirmees nettes + annulees",
        f"{received} = {confirmed} + {cancelled}",
        "Egalite obligatoire",
        received == confirmed + cancelled,
    )
    add(
        "Confirmees nettes = confirmation + preparation + envoyees + non classees",
        f"{confirmed} = {in_confirmation} + {preparation} + {sent} + {unclassified}",
        "Egalite obligatoire",
        confirmed == in_confirmation + preparation + sent + unclassified,
    )
    add(
        "Envoyees = dispatch + livrees + en livraison + retours",
        f"{sent} = {dispatch} + {delivered} + {in_delivery} + {returned}",
        "Egalite obligatoire",
        sent == dispatch + delivered + in_delivery + returned,
    )
    add(
        "En cours logistique = dispatch + en livraison",
        f"{logistics} = {dispatch} + {in_delivery}",
        "Egalite obligatoire",
        logistics == dispatch + in_delivery,
    )
    risk = preparation + dispatch + in_delivery + returned
    add(
        "Commandes a risque = preparation + dispatch + livraison + retours",
        f"{risk} = {preparation} + {dispatch} + {in_delivery} + {returned}",
        "Definition retenue : risque post-confirmation",
        True,
    )
    return pd.DataFrame(rows)
