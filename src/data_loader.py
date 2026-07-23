from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from .classification import add_classification_columns
from .cleaning import (
    compact_key,
    display_text,
    normalize_boutique,
    normalize_livreur,
    normalize_source,
    normalize_status,
    parse_date,
    parse_number,
)

CANONICAL_COLUMNS = [
    "Boutique",
    "Référence commande",
    "Tracking",
    "N°commande",
    "Type",
    "Méthode de livraison",
    "Statut commande",
    "Client",
    "Email",
    "Téléphone",
    "Téléphone 2",
    "Wilaya",
    "Commune",
    "Adresse",
    "Source",
    "Référent",
    "SKU produit",
    "Nom produit",
    "Option",
    "Quantité",
    "Prix d'affiliation",
    "Prix de vente",
    "Prix d'achat",
    "Total produit",
    "Réduction",
    "Frais de livraison",
    "Total échange",
    "Frais livreur",
    "Total commande",
    "Livreur",
    "Remarque",
    "Affectée à",
    "Crée le",
    "Affectée le",
    "Confirmée le",
    "Dispatchée le",
    "Expédiée le",
    "Livrée le",
    "Encaissée le",
    "Echouée le",
    "Retournée le",
    "Annulée le",
]

ALIASES = {
    "referencecommande": "Référence commande",
    "refcommande": "Référence commande",
    "tracking": "Tracking",
    "ncommande": "N°commande",
    "numerocommande": "N°commande",
    "statutcommande": "Statut commande",
    "totalcommande": "Total commande",
    "nomproduit": "Nom produit",
    "produit": "Nom produit",
    "wilaya": "Wilaya",
    "livreur": "Livreur",
    "affecteea": "Affectée à",
    "confirmatrice": "Affectée à",
    "creele": "Crée le",
    "confirmeele": "Confirmée le",
    "expedieele": "Expédiée le",
    "livreele": "Livrée le",
    "encaisseele": "Encaissée le",
    "echoueele": "Echouée le",
    "retourneele": "Retournée le",
    "annuleele": "Annulée le",
}

DATE_COLUMNS = [
    "Crée le",
    "Affectée le",
    "Confirmée le",
    "Dispatchée le",
    "Expédiée le",
    "Livrée le",
    "Encaissée le",
    "Echouée le",
    "Retournée le",
    "Annulée le",
]
POSITIONAL_DATE_FALLBACKS = {
    "Crée le": 32,        # Excel AG
    "Affectée le": 33,    # Excel AH
    "Confirmée le": 34,   # Excel AI
    "Dispatchée le": 35,  # Excel AJ
    "Expédiée le": 36,    # Excel AK
}
NUMBER_COLUMNS = [
    "Quantité",
    "Prix d'affiliation",
    "Prix de vente",
    "Prix d'achat",
    "Total produit",
    "Réduction",
    "Frais de livraison",
    "Total échange",
    "Frais livreur",
    "Total commande",
]
TEXT_COLUMNS = [
    "Boutique",
    "Référence commande",
    "Tracking",
    "N°commande",
    "Statut commande",
    "Wilaya",
    "Source",
    "SKU produit",
    "Nom produit",
    "Livreur",
    "Affectée à",
]
MINIMAL_REQUIRED = [
    "Statut commande",
    "Total commande",
    "Nom produit",
    "Wilaya",
    "Livreur",
    "Affectée à",
    "Crée le",
]


def _canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        key = compact_key(col)
        if key in ALIASES:
            mapping[col] = ALIASES[key]
        else:
            for canonical in CANONICAL_COLUMNS:
                if compact_key(canonical) == key:
                    mapping[col] = canonical
                    break
    return df.rename(columns=mapping)


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in CANONICAL_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    return out


def _apply_positional_date_fallback(raw: pd.DataFrame, canonicalized: pd.DataFrame) -> pd.DataFrame:
    out = canonicalized.copy()
    fallback_columns = {}
    for canonical, position in POSITIONAL_DATE_FALLBACKS.items():
        if position >= len(raw.columns):
            continue
        source_col = raw.columns[position]
        if canonical not in out.columns or out[canonical].isna().all():
            out[canonical] = raw[source_col]
            fallback_columns[canonical] = str(source_col)
    out.attrs["date_fallback_columns"] = fallback_columns
    return out


def load_excel(file: str | Path | BinaryIO) -> pd.DataFrame:
    raw = pd.read_excel(file, dtype=object)
    if raw.empty:
        raise ValueError("Le fichier est vide.")
    return prepare_dataframe(raw)


def prepare_dataframe(raw: pd.DataFrame) -> pd.DataFrame:
    canonicalized = _apply_positional_date_fallback(raw, _canonicalize_columns(raw))
    fallback_columns = canonicalized.attrs.get("date_fallback_columns", {})
    df = _ensure_columns(canonicalized)
    df.attrs["date_fallback_columns"] = fallback_columns
    missing_ids = all(df[col].isna().all() for col in ["Référence commande", "Tracking", "N°commande"])
    if missing_ids:
        df["Référence commande"] = [f"ORD-{i + 1}" for i in range(len(df))]

    for col in NUMBER_COLUMNS:
        df[col] = df[col].apply(parse_number)
    for col in DATE_COLUMNS:
        df[col] = df[col].apply(parse_date)
    for col in TEXT_COLUMNS:
        df[col] = df[col].apply(display_text)

    df["Boutique"] = df["Boutique"].apply(normalize_boutique)
    df["Livreur"] = df["Livreur"].apply(normalize_livreur)
    df["Source"] = df["Source"].apply(normalize_source)
    df["Statut commande"] = df["Statut commande"].apply(display_text)
    df["status_norm"] = df["Statut commande"].apply(normalize_status)
    df["order_id"] = df.apply(_build_order_id, axis=1)
    df = add_classification_columns(df)
    return df


def _build_order_id(row: pd.Series) -> str:
    for col in ["Référence commande", "Tracking", "N°commande"]:
        value = display_text(row.get(col))
        if value != "Non renseigné":
            return value
    return f"ORD-{row.name + 1}"


def validate_columns(df: pd.DataFrame) -> list[str]:
    warnings = []
    canonicalized = _canonicalize_columns(df)
    available = set(canonicalized.columns)
    for col in MINIMAL_REQUIRED:
        if col not in available:
            warnings.append(f"Colonne importante manquante : {col}")
    if not any(col in available for col in ["Référence commande", "Tracking", "N°commande"]):
        warnings.append("Aucun identifiant commande trouvé : un identifiant technique sera créé.")
    for canonical, position in POSITIONAL_DATE_FALLBACKS.items():
        if canonical in available:
            continue
        if position < len(df.columns):
            source_col = df.columns[position]
            warnings.append(
                f"Colonne date non reconnue par nom : {canonical}. "
                f"Fallback positionnel AG-AK disponible via : {source_col}."
            )
        else:
            warnings.append(f"Colonne date introuvable : {canonical}.")
    return warnings
