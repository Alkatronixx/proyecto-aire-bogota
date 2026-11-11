"""Funciones de agregación para el contexto y la ficha de superaciones.
Lee las mediciones procesadas recibidas por parámetro y no accede a archivos.
Calcula porcentajes por estación excluyendo días marcados como hueco.
Mantiene los resúmenes en caché para que la página responda con rapidez.
"""

import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

from app.utils.fuentes_contexto import (
    OMS_PM25_24H, COLOMBIA_PM25_24H_2018_2029,
)


def normalizar_texto(valor: object) -> str:
    """Normaliza acentos y caja para contrastar nombres sin tocar su texto original."""
    texto = unicodedata.normalize("NFKD", str(valor))
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter)).strip().casefold()


@st.cache_data(show_spinner=False)
def calcular_superaciones(datos: pd.DataFrame, umbral_274: int) -> pd.DataFrame:
    """Resume excedencias y media de 12 meses por estación sobre datos observados."""
    columnas = ["fecha", "estacion_id", "estacion", "pm25"]
    filas = datos[columnas + ["hueco_pm_2025"]].copy()
    filas["fecha"] = pd.to_datetime(filas.fecha)
    total = filas.loc[~filas.hueco_pm_2025.fillna(False)]
    fin = filas.fecha.max().normalize()
    inicio_12m = fin - pd.DateOffset(years=1) + pd.Timedelta(days=1)
    reciente = filas.loc[filas.fecha.between(inicio_12m, fin) & ~filas.hueco_pm_2025.fillna(False)]
    registros = []
    for estacion_id, estacion in filas[["estacion_id", "estacion"]].drop_duplicates().itertuples(index=False, name=None):
        completo = total.loc[total.estacion_id.eq(estacion_id), "pm25"].dropna()
        ultimo = reciente.loc[reciente.estacion_id.eq(estacion_id), "pm25"].dropna()
        media_12m = float(ultimo.mean()) if len(ultimo) >= umbral_274 else np.nan
        registros.append({
            "estacion_id": estacion_id,
            "estacion": estacion,
            "n_dias_periodo": int(len(completo)),
            "pct_pm25_mayor_15_periodo": float(completo.gt(OMS_PM25_24H).mean() * 100) if len(completo) else np.nan,
            "pct_pm25_mayor_37_periodo": float(completo.gt(COLOMBIA_PM25_24H_2018_2029).mean() * 100) if len(completo) else np.nan,
            "n_dias_12m": int(len(ultimo)),
            "pct_pm25_mayor_15_12m": float(ultimo.gt(OMS_PM25_24H).mean() * 100) if len(ultimo) else np.nan,
            "pct_pm25_mayor_37_12m": float(ultimo.gt(COLOMBIA_PM25_24H_2018_2029).mean() * 100) if len(ultimo) else np.nan,
            "pm25_medio_12m": media_12m,
            "estado_media_12m": "con datos suficientes" if len(ultimo) >= umbral_274 else "sin datos suficientes",
        })
    return pd.DataFrame(registros).sort_values("estacion_id").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def agregar_mensual(datos: pd.DataFrame) -> pd.DataFrame:
    """Agrega PM y precipitación por día y por mes calendario."""
    diario = datos.groupby("fecha", as_index=False).agg(
        pm25=("pm25", "mean"), precipitacion=("precip_mm", "mean")
    )
    diario["mes"] = pd.to_datetime(diario.fecha).dt.to_period("M").dt.to_timestamp()
    return diario.groupby("mes", as_index=False).agg(
        pm25_medio=("pm25", "mean"), lluvia_media=("precipitacion", "mean")
    )
