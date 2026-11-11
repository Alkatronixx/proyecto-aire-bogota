"""Calcula resúmenes pequeños para la portada con caché de Streamlit.
Lee solo la tabla maestra ya publicada por el cargador autorizado.
Devuelve series agregadas y cifras idénticas a las operaciones descriptivas originales.
No altera observaciones ni aplica umbrales de calidad del aire.
"""
import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False)
def resumir_portada(df: pd.DataFrame) -> dict:
    """Agrega KPIs, estación-mes y comparaciones de calendario para mostrar."""
    ultima_fecha = df.fecha.max().normalize()
    inicio_ultimo_anio = ultima_fecha - pd.DateOffset(years=1) + pd.Timedelta(days=1)
    ultimo_anio = df.loc[df.fecha.between(inicio_ultimo_anio, ultima_fecha) & df.pm25.notna()]
    mensual = (
        df.loc[df.pm25.notna()]
        .assign(mes=lambda x: x.fecha.dt.to_period("M").dt.to_timestamp())
        .groupby("mes", as_index=False).pm25.mean()
    )
    estaciones_ultimo = (
        ultimo_anio.groupby(["estacion_id", "estacion"], as_index=False)
        .agg(pm25_medio=("pm25", "mean"), lat=("lat", "first"), lon=("lon", "first"))
        .dropna(subset=["lat", "lon", "pm25_medio"])
    )
    viento = df.dropna(subset=["vel_ciudad_ms", "pm25"])
    if len(viento):
        q25, q75 = viento.vel_ciudad_ms.quantile([.25, .75])
        bajo = viento.loc[viento.vel_ciudad_ms <= q25, "pm25"].mean()
        alto = viento.loc[viento.vel_ciudad_ms >= q75, "pm25"].mean()
        texto_viento = (f"En el cuartil más bajo de viento de ciudad (≤ {q25:.2f} m/s), PM2.5 promedió "
                        f"{bajo:.1f} µg/m³; en el más alto (≥ {q75:.2f} m/s), {alto:.1f} µg/m³. "
                        f"Diferencia descriptiva: {alto-bajo:+.1f} µg/m³.")
    else:
        texto_viento = "No hay suficientes pares de viento y PM2.5 para resumir esta asociación."
    laboral = df.loc[df.pm25.notna() & df.es_fin_semana.eq(False), "pm25"].mean()
    fin_semana = df.loc[df.pm25.notna() & df.es_fin_semana.eq(True), "pm25"].mean()
    if pd.isna(laboral) or pd.isna(fin_semana):
        texto_calendario = "No hay datos suficientes para comparar laboral y fin de semana."
    else:
        texto_calendario = (f"El promedio observado fue {laboral:.1f} µg/m³ en días laborales y "
                            f"{fin_semana:.1f} µg/m³ en fines de semana; diferencia laboral menos fin de semana: "
                            f"{laboral-fin_semana:+.1f} µg/m³.")
    por_estacion = df.loc[df.pm25.notna()].groupby("estacion").pm25.mean().sort_values()
    if len(por_estacion):
        baja_nombre, alta_nombre = por_estacion.index[0], por_estacion.index[-1]
        texto_estaciones = (f"En todo el periodo, {alta_nombre} registró el promedio más alto "
                            f"({por_estacion.iloc[-1]:.1f} µg/m³) y {baja_nombre} el más bajo "
                            f"({por_estacion.iloc[0]:.1f} µg/m³). Diferencia descriptiva: "
                            f"{por_estacion.iloc[-1]-por_estacion.iloc[0]:.1f} µg/m³.")
    else:
        texto_estaciones = "No hay promedios por estación disponibles."
    return {
        "ultima_fecha": ultima_fecha,
        "inicio_ultimo_anio": inicio_ultimo_anio,
        "media_ultimo_anio": ultimo_anio.pm25.mean(),
        "estaciones": int(df.estacion_id.nunique()),
        "dias": int(df.fecha.nunique()),
        "cobertura": 100 * df.pm25.notna().sum() / len(df) if len(df) else float("nan"),
        "fecha_minima": df.fecha.min(),
        "estaciones_ultimo": estaciones_ultimo,
        "mensual": mensual,
        "texto_viento": texto_viento,
        "texto_calendario": texto_calendario,
        "texto_estaciones": texto_estaciones,
    }
