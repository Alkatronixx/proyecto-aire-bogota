"""Presenta indicadores descriptivos, un mapa y asociaciones observadas.
Lee la tabla maestra procesada con el cargador de caché de la app.
Resume el último año disponible y el periodo histórico cerrado.
No clasifica por umbrales ni atribuye relaciones causales.
"""
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from app.components.paleta import ACENTO, color_rgb_cuantil, escala_plotly
from app.components.tema_graficos import aplicar_tema
from app.components.ui import cargar_estilos, caja_hallazgo, encabezado_pagina, nota_metodologica, tarjeta_kpi
from app.utils.datos import cargar_aire

cargar_estilos()
df = cargar_aire()
encabezado_pagina(
    "El aire de Bogotá, día a día",
    "¿Cómo varía el PM2.5 entre estaciones y condiciones meteorológicas, y qué sabemos de los datos que lo describen?",
)

ultima_fecha = df.fecha.max().normalize()
inicio_ultimo_anio = ultima_fecha - pd.DateOffset(years=1) + pd.Timedelta(days=1)
ultimo_anio = df.loc[df.fecha.between(inicio_ultimo_anio, ultima_fecha) & df.pm25.notna()].copy()
estaciones = int(df.estacion_id.nunique())
dias = int(df.fecha.nunique())
cobertura = 100 * df.pm25.notna().sum() / len(df) if len(df) else float("nan")
media_ultimo_anio = ultimo_anio.pm25.mean()

kpis = st.columns(4)
with kpis[0]: tarjeta_kpi("PM2.5 medio · últimos 12 meses", f"{media_ultimo_anio:.1f} µg/m³", f"{inicio_ultimo_anio:%d %b %Y} – {ultima_fecha:%d %b %Y}")
with kpis[1]: tarjeta_kpi("Estaciones", f"{estaciones}", "Estaciones con registros en la tabla maestra")
with kpis[2]: tarjeta_kpi("Días analizados", f"{dias:,}".replace(",", "."), f"{df.fecha.min():%d %b %Y} – {ultima_fecha:%d %b %Y}")
with kpis[3]: tarjeta_kpi("Cobertura PM2.5", f"{cobertura:.1f}%", "Filas estación-día con PM2.5 observado")

izq, der = st.columns([1, 1.35], gap="large")
with izq:
    st.subheader("Estaciones · último año")
    estaciones_ultimo = (
        ultimo_anio.groupby(["estacion_id", "estacion"], as_index=False)
        .agg(pm25_medio=("pm25", "mean"), lat=("lat", "first"), lon=("lon", "first"))
        .dropna(subset=["lat", "lon", "pm25_medio"])
    )
    estaciones_ultimo["color"] = estaciones_ultimo.pm25_medio.map(
        lambda valor: color_rgb_cuantil(valor, estaciones_ultimo.pm25_medio)
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=estaciones_ultimo,
        get_position="[lon, lat]",
        get_fill_color="color",
        get_line_color=[12, 17, 23, 230],
        get_radius=450,
        radius_min_pixels=7,
        radius_max_pixels=18,
        line_width_min_pixels=1,
        pickable=True,
        stroked=True,
    )
    view = pdk.ViewState(latitude=4.65, longitude=-74.08, zoom=10.1, pitch=0)
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip={"text": "{estacion}\nPM2.5 medio: {pm25_medio} µg/m³"},
        map_style=None,
    )
    st.pydeck_chart(deck, use_container_width=True)
    st.caption("Color continuo según cuantiles de PM2.5 del último año; no representa categorías regulatorias.")

with der:
    st.subheader("Promedio mensual de la ciudad")
    mensual = (
        df.loc[df.pm25.notna()]
        .assign(mes=lambda x: x.fecha.dt.to_period("M").dt.to_timestamp())
        .groupby("mes", as_index=False).pm25.mean()
    )
    fig = go.Figure(go.Scatter(
        x=mensual.mes, y=mensual.pm25, mode="lines+markers", name="PM2.5 medio",
        line={"color": ACENTO, "width": 2.7}, marker={"size": 5},
        hovertemplate="%{x|%b %Y}<br>%{y:.1f} µg/m³<extra></extra>",
    ))
    fig.add_vrect(x0="2025-08-04", x1="2025-10-16", fillcolor="#778395", opacity=.25, line_width=0, layer="below")
    fig.add_annotation(x="2025-09-10", y=1, yref="paper", text="sin mediciones de PM", showarrow=False,
                       font={"color": "#DDE2EA", "size": 11}, bgcolor="rgba(26,31,43,.88)")
    fig.update_layout(title="Media de los valores diarios disponibles", xaxis_title="Mes", yaxis_title="PM2.5 (µg/m³)",
                      hovermode="x unified", showlegend=False)
    st.plotly_chart(aplicar_tema(fig), use_container_width=True, config={"displayModeBar": False})
    nota_metodologica("El promedio mensual usa las mediciones disponibles. El sombreado señala el hueco documentado; no se interpolan concentraciones.")

st.subheader("Tres asociaciones descriptivas")
h1, h2, h3 = st.columns(3, gap="medium")
viento = df.dropna(subset=["vel_ciudad_ms", "pm25"])
if len(viento):
    q25, q75 = viento.vel_ciudad_ms.quantile([.25, .75])
    bajo = viento.loc[viento.vel_ciudad_ms <= q25, "pm25"].mean()
    alto = viento.loc[viento.vel_ciudad_ms >= q75, "pm25"].mean()
    texto_viento = f"En el cuartil más bajo de viento de ciudad (≤ {q25:.2f} m/s), PM2.5 promedió {bajo:.1f} µg/m³; en el más alto (≥ {q75:.2f} m/s), {alto:.1f} µg/m³. Diferencia descriptiva: {alto-bajo:+.1f} µg/m³."
else:
    texto_viento = "No hay suficientes pares de viento y PM2.5 para resumir esta asociación."
laboral = df.loc[df.pm25.notna() & df.es_fin_semana.eq(False), "pm25"].mean()
fin_semana = df.loc[df.pm25.notna() & df.es_fin_semana.eq(True), "pm25"].mean()
if pd.isna(laboral) or pd.isna(fin_semana):
    texto_calendario = "No hay datos suficientes para comparar laboral y fin de semana."
else:
    texto_calendario = f"El promedio observado fue {laboral:.1f} µg/m³ en días laborales y {fin_semana:.1f} µg/m³ en fines de semana; diferencia laboral menos fin de semana: {laboral-fin_semana:+.1f} µg/m³."
por_estacion = df.loc[df.pm25.notna()].groupby("estacion").pm25.mean().sort_values()
if len(por_estacion):
    baja_nombre, alta_nombre = por_estacion.index[0], por_estacion.index[-1]
    texto_estaciones = f"En todo el periodo, {alta_nombre} registró el promedio más alto ({por_estacion.iloc[-1]:.1f} µg/m³) y {baja_nombre} el más bajo ({por_estacion.iloc[0]:.1f} µg/m³). Diferencia descriptiva: {por_estacion.iloc[-1]-por_estacion.iloc[0]:.1f} µg/m³."
else:
    texto_estaciones = "No hay promedios por estación disponibles."
with h1: caja_hallazgo(texto_viento)
with h2: caja_hallazgo(texto_calendario)
with h3: caja_hallazgo(texto_estaciones)

st.caption("Las asociaciones describen los datos observados; no estiman efectos causales.")
