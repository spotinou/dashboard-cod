"""Original bar charts (kept for compatibility)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from .formatting import money, pct, reliable_rows


def build_percent_bar_figure(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None):
    needed = [x, y] + ([color] if color else [])
    if df.empty or any(col not in df.columns for col in needed):
        return None
    chart_df = df[needed].copy()
    chart_df[y] = pd.to_numeric(chart_df[y], errors="coerce")
    chart_df = chart_df.dropna(subset=[x, y])
    if chart_df.empty:
        return None
    chart_df = chart_df.sort_values(y, ascending=False).head(10)
    fig = px.bar(
        chart_df,
        x=x,
        y=y,
        color=color,
        text=chart_df[y].map(pct),
        title=title,
    )
    fig.update_traces(textposition="outside")
    max_value = float(chart_df[y].max()) if not chart_df.empty else 1.0
    fig.update_layout(
        yaxis_tickformat=".0%",
        yaxis_range=[0, min(1, max(0.05, max_value * 1.2))],
        height=280,
    )
    return fig


def percent_bar(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None):
    fig = build_percent_bar_figure(df, x, y, title, color)
    if fig is None:
        st.info("Pas assez de donnees calculables pour afficher ce graphique.")
        return
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def build_amount_bar_figure(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    chart_df = df[[x, y]].copy()
    chart_df[y] = pd.to_numeric(chart_df[y], errors="coerce")
    chart_df = chart_df.dropna(subset=[x, y])
    if chart_df.empty:
        return None
    chart_df = chart_df.sort_values(y, ascending=False).head(10)
    fig = px.bar(chart_df, x=x, y=y, text=chart_df[y].map(money), title=title)
    fig.update_traces(textposition="outside")
    fig.update_layout(height=280)
    return fig


def amount_bar(df: pd.DataFrame, x: str, y: str, title: str):
    fig = build_amount_bar_figure(df, x, y, title)
    if fig is None:
        st.info("Pas assez de donnees calculables pour afficher ce graphique.")
        return
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def build_confirmation_rate_figure(confirmation: pd.DataFrame, volume_min: int = 0):
    required = {"confirmatrice", "commandes_recues", "taux_confirmation", "taux_livraison_finalisees"}
    if confirmation.empty or not required.issubset(confirmation.columns):
        return None
    chart_df = reliable_rows(confirmation, "confirmatrice", "commandes_recues", volume_min)
    if chart_df.empty:
        return None
    chart_df = chart_df.sort_values("commandes_recues", ascending=False).head(10).copy()
    chart_long = chart_df.melt(
        id_vars=["confirmatrice"],
        value_vars=["taux_confirmation", "taux_livraison_finalisees"],
        var_name="Indicateur",
        value_name="Taux",
    )
    chart_long["Taux"] = pd.to_numeric(chart_long["Taux"], errors="coerce")
    chart_long = chart_long.dropna(subset=["confirmatrice", "Taux"])
    if chart_long.empty:
        return None
    fig = px.bar(
        chart_long,
        x="confirmatrice",
        y="Taux",
        color="Indicateur",
        barmode="group",
        text=chart_long["Taux"].map(pct),
        title="Confirmation vs livraison finalisee",
        labels={"confirmatrice": "Confirmatrice"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis_tickformat=".0%", yaxis_range=[0, 1], height=280)
    return fig
