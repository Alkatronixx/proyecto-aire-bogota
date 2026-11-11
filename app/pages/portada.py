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
from app.utils.portada import resumir_portada

cargar_estilos()
df = cargar_aire()
encabezado_pagina(
    "El aire de Bogotá, día a día",
    "¿Cómo varía el PM2.5 entre estaciones y condiciones meteorológicas, y qué sabemos de los datos que lo describen?",
)

resumen = resumir_portada(df)
ultima_fecha = resumen["ultima_fecha"]
inicio_ultimo_anio = resumen["inicio_ultimo_anio"]
estaciones = resumen["estaciones"]
dias = resumen["dias"]
cobertura = resumen["cobertura"]
media_ultimo_anio = resumen["media_ultimo_anio"]

kpis = st.columns(4)
with kpis[0]: tarjeta_kpi("PM2.5 medio · últimos 12 meses", f"{media_ultimo_anio:.1f} µg/m³", f"{inicio_ultimo_anio:%d %b %Y} – {ultima_fecha:%d %b %Y}")
with kpis[1]: tarjeta_kpi("Estaciones", f"{estaciones}", "Estaciones con registros en la tabla maestra")
with kpis[2]: tarjeta_kpi("Días analizados", f"{dias:,}".replace(",", "."), f"{df.fecha.min():%d %b %Y} – {ultima_fecha:%d %b %Y}")
with kpis[3]: tarjeta_kpi("Cobertura PM2.5", f"{cobertura:.1f}%", "Filas estación-día con PM2.5 observado")

izq, der = st.columns([1, 1.35], gap="large")
with izq:
    st.subheader("Estaciones · último año")
    estaciones_ultimo = resumen["estaciones_ultimo"]
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
    st.pydeck_chart(deck, width="stretch")
    st.caption("Color continuo según cuantiles de PM2.5 del último año; no representa categorías regulatorias.")

with der:
    st.subheader("Promedio mensual de la ciudad")
    mensual = resumen["mensual"]
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
    st.plotly_chart(aplicar_tema(fig), width="stretch", config={"displayModeBar": False})
    nota_metodologica("El promedio mensual usa las mediciones disponibles. El sombreado señala el hueco documentado; no se interpolan concentraciones.")

st.subheader("Tres asociaciones descriptivas")
h1, h2, h3 = st.columns(3, gap="medium")
texto_viento = resumen["texto_viento"]
texto_calendario = resumen["texto_calendario"]
texto_estaciones = resumen["texto_estaciones"]
with h1: caja_hallazgo(texto_viento)
with h2: caja_hallazgo(texto_calendario)
with h3: caja_hallazgo(texto_estaciones)

st.caption("Las asociaciones describen los datos observados; no estiman efectos causales.")
