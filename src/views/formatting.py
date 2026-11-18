"""Formatting helpers: numbers, money, rates, colours and table preparation."""
from __future__ import annotations

import pandas as pd
from html import escape
from pandas.api.types import is_object_dtype, is_scalar


SENSITIVE_COLUMNS = {"Client", "Email", "Téléphone", "Téléphone 2", "Adresse"}


DISPLAY_COLUMNS = {
    "confirmatrice": "Confirmatrice",
    "livreur": "Livreur",
    "produit": "Produit",
    "wilaya": "Wilaya",
    "commandes_recues": "Commandes reçues",
    "commandes_annulees": "Annulées avant expédition",
    "commandes_confirmees_nettes": "Confirmées nettes",
    "commandes_envoyees": "Expédiées",
    "livrees": "Livrées finalisées",
    "en_preparation": "En pr\u00e9paration",
    "en_dispatch": "En dispatch",
    "en_livraison": "En cours livraison",
    "en_cours_logistique": "En cours logistique",
    "retours": "Retours / échecs",
    "taux_confirmation": "Taux non annulé",
    "taux_annulation": "Taux annulation avant expédition",
    "taux_preparation": "Taux en pr\u00e9paration",
    "taux_dispatch": "Taux en dispatch",
    "taux_en_livraison": "Taux en cours de livraison",
    "taux_livraison_finalisees": "Taux livraison finalisée hors en cours",
    "taux_livraison_total": "Taux livraison sur exp\u00e9di\u00e9es",
    "taux_en_cours_livraison": "Taux en cours livraison",
    "taux_en_cours_logistique": "Taux en cours logistique",
    "taux_retour": "Taux retour",
    "taux_transformation_reel": "Taux transformation brute",
    "taux_transformation_brute": "Taux transformation brute",
    "taux_transformation_nette": "Taux transformation nette",
    "ca_livre": "CA livré finalisé",
    "ca_dispatch": "CA en dispatch",
    "ca_bloque_livraison": "CA en cours livraison",
    "ca_en_cours_logistique": "CA en cours logistique",
    "ca_preparation": "CA confirmé non expédié",
    "ca_retours": "Perte CA retours",
    "ca_par_commande_confirmee": "CA par commande confirmée",
    "panier_moyen_livre": "Panier moyen livré",
    "decision_auto": "Décision",
    "probleme_probable": "Problème probable",
    "cause_probable": "Cause probable",
    "action_recommandee": "Action recommandée",
    "produit_dominant": "Produit dominant",
    "livreur_dominant": "Livreur dominant",
    "controle": "Contrôle",
    "valeur": "Valeur",
    "attendu": "Attendu",
    "statut": "Statut",
    "details": "Details",
    "priorite": "Priorité",
    "objet": "Objet",
    "probleme_detecte": "Problème détecté",
    "recommandation_concrete": "Recommandation concrète",
    "preuve_data": "Preuve data",
    "impact_estime": "Impact estimé",
    "niveau_confiance": "Niveau de confiance",
    "diagnostic": "Diagnostic",
    "action_recommandee": "Action recommandée",
    "source": "Source",
    "sku_produit": "SKU produit",
    "produit_associe": "Produit associé",
    "livreur_actuel": "Livreur actuel / dominant",
    "expediees_actuel": "Expédiées actuel",
    "taux_livraison_total_actuel": "Taux livraison sur exp\u00e9di\u00e9es actuel",
    "taux_retour_actuel": "Taux retour actuel",
    "meilleur_livreur_alternatif": "Meilleur livreur alternatif",
    "expediees_alternatif": "Expédiées alternatif",
    "taux_livraison_total_alternatif": "Taux livraison sur exp\u00e9di\u00e9es alternatif",
    "taux_retour_alternatif": "Taux retour alternatif",
    "ecart_livraison": "Écart livraison",
    "ecart_retour": "Écart retour",
    "volume": "Volume",
    "wilayas_problematiques": "Wilayas les plus problématiques",
}


TEXT_LIKE_COLUMNS = {
    "Valeur",
    "valeur",
    "Détail",
    "Détails",
    "Detail",
    "details",
    "Calcul",
    "calcul",
    "Formule",
    "formule",
    "Explication",
    "explication",
    "Description",
    "description",
    "Libellé",
    "libellé",
    "Label",
    "label",
    "KPI",
    "kpi",
}


def prepare_table_for_streamlit(data):
    if not isinstance(data, pd.DataFrame):
        return data

    safe = data.copy()

    for col in safe.columns:
        series = safe[col]

        if col in TEXT_LIKE_COLUMNS:
            safe[col] = series.astype("string")
            continue

        if is_object_dtype(series):
            non_null = series.dropna()
            has_text = non_null.map(lambda x: isinstance(x, str)).any()
            has_non_text = non_null.map(lambda x: not isinstance(x, str)).any()

            if has_text and has_non_text:
                safe[col] = series.astype("string")

    return safe


def money(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "\u2014"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "\u2014"
    if pd.isna(number) or number in {float("inf"), float("-inf")}:
        return "\u2014"
    return f"{number:,.0f}".replace(",", " ") + " DA"


def pct(value: float | None) -> str:
    if not is_scalar(value):
        return "\u2014"
    if value is None or pd.isna(value):
        return "\u2014"
    if isinstance(value, str) and value.strip().lower() in {"", "nan", "nan%", "none", "inf", "-inf"}:
        return "\u2014"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "\u2014"
    if pd.isna(number) or number in {float("inf"), float("-inf")}:
        return "\u2014"
    return f"{number * 100:.1f} %"


def is_rate_column(col: str) -> bool:
    normalized = str(col).lower()
    return any(token in normalized for token in ("taux", "rate", "ratio", "pourcentage", "ecart"))


def is_money_column(col: str) -> bool:
    normalized = str(col).lower().strip()
    if is_rate_column(normalized):
        return False
    if normalized in {"valeur"}:
        return False
    money_tokens = ("montant", "prix", "total", "panier")
    if normalized.startswith("ca_") or normalized.startswith("ca ") or "perte ca" in normalized:
        return True
    if any(token in normalized for token in money_tokens):
        return True
    return "valeur" in normalized and any(token in normalized for token in ("moyenne", "commande", "retour", "livre"))


def style_level(value: float | None, kind: str, thresholds: dict[str, float]) -> str:
    if value is None or pd.isna(value):
        return "#6b7280"
    if kind in {"confirmation", "delivery", "transformation", "net_transformation"} and f"{kind}_green" in thresholds:
        return "#16a34a" if value >= thresholds[f"{kind}_green"] else "#f59e0b" if value >= thresholds[f"{kind}_orange"] else "#dc2626"
    if kind == "return":
        return "#16a34a" if value <= thresholds["return_orange"] else "#f59e0b" if value <= thresholds["return_red"] else "#dc2626"
    if kind == "cancellation":
        return "#16a34a" if value <= thresholds["cancellation_orange"] else "#f59e0b" if value <= thresholds["cancellation_red"] else "#dc2626"
    if kind == "preparation":
        return "#16a34a" if value <= thresholds["preparation_orange"] else "#f59e0b" if value <= thresholds["preparation_red"] else "#dc2626"
    return "#111827"


DASH = "\u2014"


def html_text(value) -> str:
    return escape(str(value if value is not None else DASH))


# Hover bubble ("ⓘ") shown next to any title that contains one of these terms.
GLOSSARY = {
    "taux confirmé": "Sur 100 commandes reçues, combien sont confirmées (hors celles encore en confirmation).",
    "livré (sur expédiées)": "Sur 100 colis expédiés, combien sont livrés. Les colis encore en route font baisser ce taux.",
    "livré (sur colis terminés)": "Sur 100 colis arrivés au bout (livrés ou revenus), combien sont livrés. Ignore les colis encore en route.",
    "taux retour": "Sur 100 colis expédiés, combien reviennent (retour ou échec de livraison).",
    "taux annulé": "Sur 100 commandes reçues, combien sont annulées.",
    "transformation brute": (
        "Sur 100 commandes reçues, combien sont livrées au client. "
        "Calcul : livrées ÷ reçues. C'est le taux de bout en bout : il compte tout, même les annulations."
    ),
    "transformation nette": (
        "Comme la brute, mais sans les commandes annulées (faux numéros, doublons, refus au téléphone). "
        "Calcul : livrées ÷ (reçues − annulées)."
    ),
}


def help_icon(title: str) -> str:
    """HTML hover bubble for a title that names a glossary term, else an empty string."""
    lowered = str(title).lower()
    for term, text in GLOSSARY.items():
        if term in lowered:
            return f'<span class="help-tip" data-tip="{html_text(text)}">\u24d8</span>'
    return ""


def tone_class(value: float | None, kind: str, thresholds: dict[str, float]) -> str:
    if value is None or pd.isna(value):
        return "neutral"
    if kind in {"transformation", "net_transformation"} and f"{kind}_green" in thresholds:
        return "good" if value >= thresholds[f"{kind}_green"] else "warn" if value >= thresholds[f"{kind}_orange"] else "bad"
    if kind == "confirmation" and "confirmation_green" in thresholds:
        return "good" if value >= thresholds["confirmation_green"] else "warn" if value >= thresholds["confirmation_orange"] else "bad"
    if kind in {"confirmation", "delivery", "transformation"}:
        return "good" if value >= thresholds["delivery_green"] else "warn" if value >= thresholds["delivery_orange"] else "bad"
    if kind == "return":
        return "good" if value <= thresholds["return_orange"] else "warn" if value <= thresholds["return_red"] else "bad"
    if kind == "cancellation":
        return "good" if value <= thresholds["cancellation_orange"] else "warn" if value <= thresholds["cancellation_red"] else "bad"
    if kind == "preparation":
        return "good" if value <= thresholds["preparation_orange"] else "warn" if value <= thresholds["preparation_red"] else "bad"
    if kind == "risk":
        return "good" if value == 0 else "warn" if value < 50 else "bad"
    return "neutral"


def deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or not df.columns.duplicated().any():
        return df
    return df.loc[:, ~df.columns.duplicated()].copy()


def unique_existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    seen = set()
    selected = []
    for col in columns:
        if col in df.columns and col not in seen:
            selected.append(col)
            seen.add(col)
    return selected


def prepare_dataframe_for_display(df: pd.DataFrame, rename_columns: bool = True) -> pd.DataFrame:
    out = deduplicate_columns(df.copy())
    invalid_values = [float("inf"), float("-inf"), "nan", "NaN", "nan%", "None", "none", "inf", "-inf"]
    for col in out.columns:
        if is_rate_column(col):
            out[col] = out[col].apply(pct)
        elif is_money_column(col):
            out[col] = out[col].apply(money)
    out = out.replace(invalid_values, pd.NA).fillna("\u2014")
    if rename_columns:
        out = out.rename(columns=DISPLAY_COLUMNS)
    return prepare_table_for_streamlit(out)


def format_table(df: pd.DataFrame) -> pd.DataFrame:
    return prepare_dataframe_for_display(df, rename_columns=True)


def metric_color(value, col: str, thresholds: dict[str, float]) -> str:
    if value is None or pd.isna(value):
        return ""
    kind = None
    if col == "taux_confirmation":
        kind = "confirmation"
    elif col in {"taux_livraison_finalisees", "taux_livraison_total", "taux_en_cours_livraison"}:
        kind = "delivery"
    elif col in {"taux_transformation_reel", "taux_transformation_brute"}:
        kind = "transformation"
    elif col == "taux_transformation_nette":
        kind = "net_transformation"
    elif col == "taux_retour":
        kind = "return"
    elif col == "taux_annulation":
        kind = "cancellation"
    if kind is None:
        return ""
    return f"color: {style_level(float(value), kind, thresholds)}; font-weight: 700"


def style_metric_table(df: pd.DataFrame, thresholds: dict[str, float]):
    raw = deduplicate_columns(df.copy())
    display = prepare_dataframe_for_display(raw, rename_columns=False)
    style_cols = list(raw.columns)

    def style_cell(value, col: str) -> str:
        normalized = str(value).lower()
        if col == "decision_auto":
            if "pousser" in normalized:
                return "color: #16a34a; font-weight: 700"
            if "surveiller" in normalized or "corriger" in normalized:
                return "color: #dc2626; font-weight: 700"
            if "chantillon" in normalized:
                return "color: #6b7280; font-weight: 700"
        if col == "statut" and value != "OK":
            return "color: #dc2626; font-weight: 700"
        return metric_color(value, col, thresholds)

    def style_column(series: pd.Series) -> list[str]:
        col = series.name
        return [style_cell(raw.at[idx, col], col) if col in raw.columns and idx in raw.index else "" for idx in series.index]

    styled = display.style.apply(style_column, axis=0)
    numeric_cols = [col for col in style_cols if col not in {"confirmatrice", "livreur", "produit", "wilaya", "decision_auto", "produit_dominant", "livreur_dominant", "controle", "attendu", "statut", "probleme_probable", "cause_probable", "action_recommandee"}]
    styled = styled.set_properties(subset=numeric_cols, **{"text-align": "right"})
    styled = styled.set_properties(subset=[col for col in style_cols if col not in numeric_cols], **{"text-align": "left"})
    return styled.relabel_index([DISPLAY_COLUMNS.get(col, col) for col in style_cols], axis=1)


def is_known_value(value) -> bool:
    return str(value).strip().lower() not in {"", "non renseign\u00e9", "non renseign\u00c3\u00a9", "none", "nan", "-"}


def reliable_rows(df: pd.DataFrame, label_col: str, volume_col: str, volume_min: int) -> pd.DataFrame:
    if df.empty or label_col not in df.columns or volume_col not in df.columns:
        return df.iloc[0:0].copy()
    out = df[df[label_col].apply(is_known_value)].copy()
    out = out[pd.to_numeric(out[volume_col], errors="coerce").fillna(0).ge(volume_min)]
    return out


def format_date(value) -> str:
    if value is None or pd.isna(value):
        return DASH
    return pd.Timestamp(value).strftime("%Y/%m/%d")


def top_known(df: pd.DataFrame, label_col: str, sort_col: str, limit: int = 5) -> pd.DataFrame:
    if df.empty or label_col not in df.columns or sort_col not in df.columns:
        return df.iloc[0:0].copy()
    out = df[df[label_col].apply(is_known_value)].copy()
    out = out[pd.to_numeric(out[sort_col], errors="coerce").fillna(0).gt(0)]
    return sort_for_display(out, [sort_col]).head(limit)


def no_reliable_message() -> str:
    return "Aucun \u00e9l\u00e9ment fiable \u00e0 classer avec les seuils actuels."


def sort_for_display(df: pd.DataFrame, columns: list[str], ascending: bool = False) -> pd.DataFrame:
    if df.empty:
        return df
    available = [col for col in columns if col in df.columns]
    if not available:
        return df
    return df.sort_values(available, ascending=[ascending] * len(available))


def adaptive_height(df: pd.DataFrame, min_height: int = 132, max_height: int = 360) -> int:
    if df.empty:
        return min_height
    return max(min_height, min(max_height, 42 + len(df) * 34))


def existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return unique_existing_columns(df, columns)


def display_subset(df: pd.DataFrame, columns: list[str], sort_by: list[str] | str | None = None, ascending: bool = False) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    if sort_by:
        sort_cols = [sort_by] if isinstance(sort_by, str) else sort_by
        out = sort_for_display(out, sort_cols, ascending=ascending)
    cols = existing_columns(out, columns)
    return out[cols].copy() if cols else out


def top_label(df: pd.DataFrame, label_col: str, sort_col: str, volume_col: str | None = None, volume_min: int = 0) -> str:
    if df.empty or label_col not in df.columns or sort_col not in df.columns:
        return DASH
    reliable = df[df[label_col].apply(is_known_value)].copy()
    if volume_col and volume_col in reliable.columns:
        reliable = reliable[pd.to_numeric(reliable[volume_col], errors="coerce").fillna(0).ge(volume_min)]
    if reliable.empty:
        return DASH
    return str(reliable.sort_values(sort_col, ascending=False).iloc[0].get(label_col, DASH))


def weighted_rate(df: pd.DataFrame, numerator_col: str, denominator_col: str) -> float | None:
    if df.empty or numerator_col not in df.columns or denominator_col not in df.columns:
        return None
    numerator = pd.to_numeric(df[numerator_col], errors="coerce").fillna(0).sum()
    denominator = pd.to_numeric(df[denominator_col], errors="coerce").fillna(0).sum()
    return safe_ratio(numerator, denominator)


def safe_ratio(value: float, total: float) -> float | None:
    if not total:
        return None
    return float(value) / float(total)


TREND_ACCENT = "#2563eb"


TREND_ACCENT_LIGHT = "#bfdbfe"


TREND_AVERAGE_COLOR = "#64748b"


TREND_GRID_COLOR = "#eef2f7"


TREND_TONE_COLORS = {"good": ("#dcfce7", "#166534"), "bad": ("#fee2e2", "#991b1b"), "neutral": ("#e2e8f0", "#334155")}


def format_count(value) -> str:
    return f"{int(value):,}".replace(",", " ")
