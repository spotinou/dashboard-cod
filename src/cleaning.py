from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

MISSING_LABEL = "Non renseigné"


def strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def compact_key(value: str) -> str:
    value = strip_accents(str(value)).lower().strip()
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def clean_text(value: Any, missing: str | None = None) -> str | None:
    if pd.isna(value):
        return missing
    text = re.sub(r"\s+", " ", str(value)).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return missing
    return text


def display_text(value: Any) -> str:
    return clean_text(value, MISSING_LABEL) or MISSING_LABEL


def parse_number(value: Any) -> float:
    if pd.isna(value) or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    text = text.replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", ".", "-", "-."}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_date(value: Any) -> pd.Timestamp:
    if pd.isna(value) or str(value).strip() == "":
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"]
    text = str(value).strip()
    for fmt in formats:
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")
        if not pd.isna(parsed):
            return parsed
    return pd.to_datetime(text, errors="coerce", dayfirst=True)


def normalize_status(value: Any) -> str:
    text = strip_accents(display_text(value)).lower()
    if "annul" in text or "cancel" in text:
        return "annulee"
    if "confirm" in text:
        return "en_confirmation"
    if "preparation" in text:
        return "preparation"
    if "dispatch" in text or "dispach" in text:
        return "dispatch"
    if "encaiss" in text or "paye" in text or "payee" in text:
        return "encaissee"
    if "livr" in text and "livraison" not in text:
        return "livree"
    if "retour" in text:
        return "retournee" if "retournee" in text else "en_retour"
    if "echou" in text:
        return "retournee"
    if "livraison" in text:
        return "en_livraison"
    return "inconnu"


def normalize_livreur(value: Any) -> str:
    text = display_text(value)
    key = strip_accents(text).lower()
    if key in {"yalidin colis", "yalidine", "yalidin"}:
        return "Yalidine"
    return text


def normalize_boutique(value: Any) -> str:
    text = display_text(value)
    if compact_key(text) == "maisonluxelle":
        return "Maison Luxelle"
    if compact_key(text) == "elbaraka":
        return "ELBARAKA"
    return text


def normalize_source(value: Any) -> str:
    text = display_text(value)
    if compact_key(text) == "lightfunnels":
        return "Lightfunnels"
    return text


def safe_divide(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator
