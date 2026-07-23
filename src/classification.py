from __future__ import annotations

import pandas as pd

CONFIRMED_STATUSES = {
    "en_confirmation",
    "preparation",
    "dispatch",
    "en_livraison",
    "livree",
    "encaissee",
    "en_retour",
    "retournee",
}
SENT_STATUSES = {"dispatch", "en_livraison", "livree", "encaissee", "en_retour", "retournee"}
KNOWN_STATUSES = {"annulee", *CONFIRMED_STATUSES}

LIVREE_LE = "Livr\u00e9e le"
ENCAISSEE_LE = "Encaiss\u00e9e le"
ECHOUEE_LE = "Echou\u00e9e le"
RETOURNEE_LE = "Retourn\u00e9e le"
EXPEDIEE_LE = "Exp\u00e9di\u00e9e le"


def add_classification_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["is_status_known"] = out["status_norm"].isin(KNOWN_STATUSES)
    out["is_cancelled"] = out["status_norm"] == "annulee"
    out["is_confirmed_net"] = ~out["is_cancelled"]
    out["is_in_confirmation"] = out["is_status_known"] & (~out["is_cancelled"]) & (out["status_norm"] == "en_confirmation")
    out["is_dispatch"] = out["is_status_known"] & (~out["is_cancelled"]) & (out["status_norm"] == "dispatch")
    out["is_delivered"] = out["is_status_known"] & (~out["is_cancelled"]) & (
        out["status_norm"].isin({"livree", "encaissee"})
        | out[LIVREE_LE].notna()
        | out[ENCAISSEE_LE].notna()
    )
    out["is_return_or_failed"] = out["is_status_known"] & (~out["is_cancelled"]) & (~out["is_delivered"]) & (
        out["status_norm"].isin({"en_retour", "retournee"})
        | out[ECHOUEE_LE].notna()
        | out[RETOURNEE_LE].notna()
    )
    out["is_preparation"] = out["is_status_known"] & (~out["is_cancelled"]) & (
        (out["status_norm"] == "preparation")
        | (
            out["is_confirmed_net"]
            & out[EXPEDIEE_LE].isna()
            & ~out["is_in_confirmation"]
            & ~out["status_norm"].isin(SENT_STATUSES)
            & ~out["is_delivered"]
            & ~out["is_return_or_failed"]
        )
    )
    out["is_sent"] = out["is_status_known"] & (~out["is_cancelled"]) & (~out["is_preparation"]) & (
        out[EXPEDIEE_LE].notna() | out["status_norm"].isin(SENT_STATUSES)
    )
    out["is_in_delivery"] = out["is_sent"] & (out["status_norm"] == "en_livraison") & ~out["is_delivered"] & ~out["is_return_or_failed"]
    out["is_non_finalized_sent"] = out["is_sent"] & ~out["is_delivered"] & ~out["is_return_or_failed"]
    out["is_unclassified"] = out["is_confirmed_net"] & ~out["is_in_confirmation"] & ~out["is_preparation"] & ~out["is_sent"]
    out["is_delivery_finalized"] = out["is_delivered"] | out["is_return_or_failed"]
    out["ca_total"] = out["Total commande"].astype(float)
    out["ca_delivered"] = out["ca_total"].where(out["is_delivered"], 0.0)
    out["ca_in_confirmation"] = out["ca_total"].where(out["is_in_confirmation"], 0.0)
    out["ca_dispatch"] = out["ca_total"].where(out["is_dispatch"], 0.0)
    out["ca_in_delivery"] = out["ca_total"].where(out["is_in_delivery"], 0.0)
    out["ca_preparation"] = out["ca_total"].where(out["is_preparation"], 0.0)
    out["ca_returned_failed"] = out["ca_total"].where(out["is_return_or_failed"], 0.0)
    return out