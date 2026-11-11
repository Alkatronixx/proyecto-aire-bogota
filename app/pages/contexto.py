"""Presenta el contexto documentado, las estaciones y los datos de superación.
Lee la tabla maestra y la ficha oficial publicada para la aplicación.
Las cifras normativas y de contexto proceden del módulo de fuentes verificadas.
Resume y grafica observaciones por estación y mes sin imputar faltantes.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pydeck as pdk
import streamlit as st
from streamlit.errors import StreamlitPageNotFoundError

from app.components.paleta import ACENTO
from app.components.tema_graficos import aplicar_tema
from app.components.ui import cargar_estilos, encabezado_pagina
from app.utils.datos import cargar_aire, cargar_ficha_estaciones
from app.utils.contexto import agregar_mensual, calcular_superaciones, normalizar_texto
from app.utils.fuentes_contexto import (
    POBLACION_BOGOTA_2025, ESTACIONES_SDA, MICROSENSORES_SDA,
    DIAMETRO_PM25_MICROMETROS, DIAMETRO_PM10_MICROMETROS,
    OMS_DIAS_EXCEDENCIA_24H, OMS_PM25_ANUAL, OMS_PM25_24H,
    OMS_PM10_ANUAL, OMS_PM10_24H, OMS_ANIO_GUIA,
    COLOMBIA_ANIO_RESOLUCION,
    COLOMBIA_ANIO_INICIO_NORMA, COLOMBIA_ANIO_FIN_NORMA,
    COLOMBIA_FECHA_INICIO_24H, COLOMBIA_PM25_ANUAL_2018_2029,
    COLOMBIA_PM25_24H_2018_2029, COLOMBIA_PM10_ANUAL_2018_2029,
    COLOMBIA_PM10_24H_2018_2029, COLOMBIA_PM25_ANUAL_2030,
    COLOMBIA_PM10_ANUAL_2030, COLOMBIA_PM25_PREVENCION,
    COLOMBIA_PM25_ALERTA, COLOMBIA_PM25_EMERGENCIA,
    DIAS_MINIMOS_PROMEDIO_ANUAL, TEXTO_SALUD_OMS, FUENTES,
    URL_ESTACIONES_SDA, URL_GUIAS_OMS, URL_RESOLUCION_2254,
    URL_INVERSION_TERMICA_SDA, URL_FACTORES_INTERNOS_EXTERNOS_SDA,
    URL_REGIMEN_LLUVIA_BOGOTA, DIAS_ANO_REFERENCIA,
    ICA_24H_PM, COLORES_ICA, NOTA_ERRATA_IDEAM_ICA,
    URL_IDEAM_ICA_24H, URL_SALUD_PM25_AIRQ, TEXTO_METODOLOGIA_SALUD_PM25,
    RIESGOS_RELATIVOS_PM25, NOTA_INTERPRETACION_SALUD_PM25,
    TEXTO_PRESENTACION_ICA_24H,
)

COLORES_TIPO = {
    "de fondo": [0, 194, 168],
    "de tráfico": [243, 185, 72],
    "tráfico/industrial": [231, 76, 60],
    "industrial": [142, 68, 173],
    "residencial": [52, 152, 219],
}


def _mapa_estaciones(ficha: pd.DataFrame, datos: pd.DataFrame) -> None:
    """Dibuja los 19 puntos coloreados por tipo oficial de estación."""
    puntos = (
        datos.groupby("estacion_id", as_index=False)
        .agg(estacion=("estacion", "first"), lat=("lat", "first"), lon=("lon", "first"))
        .merge(ficha, on="estacion_id", how="inner", validate="one_to_one")
    )
    puntos["color"] = puntos.tipo_estacion.map(COLORES_TIPO)
    capa = pdk.Layer(
        "ScatterplotLayer", data=puntos, get_position="[lon, lat]",
        get_fill_color="color", get_line_color=[240, 244, 248, 220],
        stroked=True, filled=True, radius_min_pixels=6, radius_max_pixels=13,
        get_radius=110, pickable=True, line_width_min_pixels=1,
    )
    centro = datos[["lat", "lon"]].dropna().mean()
    vista = pdk.ViewState(
        latitude=float(centro.lat), longitude=float(centro.lon),
        zoom=10.2, pitch=0,
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=[capa], initial_view_state=vista,
            map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
            tooltip={"text": "{estacion}\n{localidad_sda} · {tipo_estacion}\n{altitud_m} m"},
        ),
        width="stretch",
    )
    leyenda = " · ".join(
        f'<span style="color:rgb({r},{g},{b})">●</span> {tipo}'
        for tipo, (r, g, b) in COLORES_TIPO.items()
    )
    st.markdown(leyenda, unsafe_allow_html=True)


def _enlace_pagina(ruta: str, texto: str, icono: str, url_respaldo: str) -> None:
    """Enlaza una página registrada y mantiene un enlace simple en AppTest aislado."""
    try:
        st.page_link(ruta, label=texto, icon=icono)
    except StreamlitPageNotFoundError:
        # AppTest carga archivos sueltos sin registrar st.navigation; en la app real
        # se usa la ruta relativa al entrypoint y el enlace de esta rama no se activa.
        st.markdown(f"[{texto}](/{url_respaldo})")


def _grafico_excedencias(tabla: pd.DataFrame, columna_15: str, columna_37: str, titulo: str) -> None:
    """Muestra porcentajes por estación con referencias de frecuencia OMS."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=tabla.estacion_id, x=tabla[columna_15], name=f"PM2.5 > {OMS_PM25_24H} µg/m³",
        orientation="h", marker_color="#E67E22",
    ))
    fig.add_trace(go.Bar(
        y=tabla.estacion_id, x=tabla[columna_37], name=f"PM2.5 > {COLOMBIA_PM25_24H_2018_2029} µg/m³",
        orientation="h", marker_color="#8E44AD",
    ))
    for dias in OMS_DIAS_EXCEDENCIA_24H:
        fig.add_vline(
        x=dias / DIAS_ANO_REFERENCIA * 100, line_dash="dot", line_color="#DDE2EA",
            annotation_text=f"{dias}/{DIAS_ANO_REFERENCIA} días", annotation_position="top",
        )
    fig.update_layout(
        title=titulo, barmode="group", height=690,
        xaxis_title="% de días con dato sobre el umbral", yaxis_title="",
        legend_title="Referencia de 24 h",
    )
    st.plotly_chart(aplicar_tema(fig), width="stretch", config={"displayModeBar": False})


cargar_estilos()
encabezado_pagina(
    "Contexto de Bogotá",
    "La red de monitoreo y las mediciones diarias de PM2.5 y PM10 que analiza este proyecto.",
)
datos = cargar_aire()
ficha = cargar_ficha_estaciones()

st.subheader("El problema")
st.markdown(
    f"PM2.5 y PM10 describen material particulado con diámetro igual o menor a "
    f"{str(DIAMETRO_PM25_MICROMETROS).replace('.', ',')} y {DIAMETRO_PM10_MICROMETROS:g} micrómetros. "
    "La vigilancia registra su concentración en el aire y permite compararla con valores guía y normas."
)
st.info(f"{TEXTO_SALUD_OMS} [OMS: guías de calidad del aire]({URL_GUIAS_OMS})")

st.subheader("Bogotá y su red")
ficha["altitud_m"] = pd.to_numeric(ficha.altitud_m, errors="coerce")
alt_min = ficha.altitud_m.min()
alt_max = ficha.altitud_m.max()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Población proyectada · 2025", f"{POBLACION_BOGOTA_2025:,}".replace(",", "."))
k2.metric("Estaciones en esta app", f"{datos.estacion_id.nunique():,}".replace(",", "."))
k3.metric("Microsensores citados por SDA", f"{MICROSENSORES_SDA:,}".replace(",", "."))
k4.metric("Altitud de estaciones del proyecto", f"{alt_min:.0f}–{alt_max:.0f} m")
st.caption(
    f"La red pertenece a la Secretaría Distrital de Ambiente. La SDA reporta {ESTACIONES_SDA} estaciones "
    f"y {MICROSENSORES_SDA} microsensores; la página de estaciones incluye Bosa, que no está en los archivos del proyecto. "
    f"[Población: SDS/DANE]({FUENTES[1]['url']}) · [Red: comunicado SDA]({FUENTES[2]['url']}) · "
    f"[Ficha de estaciones]({URL_ESTACIONES_SDA})."
)
_mapa_estaciones(ficha, datos)
maestro_localidad = (
    datos.groupby("estacion_id", as_index=False)
    .agg(localidad_maestra=("localidad", "first"))
)
comparacion = ficha.merge(maestro_localidad, on="estacion_id", how="left", validate="one_to_one")
comparacion["localidad_coincide"] = comparacion.apply(
    lambda fila: normalizar_texto(fila.localidad_sda) == normalizar_texto(fila.localidad_maestra),
    axis=1,
)
diferencias = comparacion.loc[~comparacion.localidad_coincide, ["estacion_id", "localidad_sda", "localidad_maestra"]]
st.markdown("**Localidad SDA frente al cruce espacial del proyecto**")
if diferencias.empty:
    st.caption("Las localidades coinciden para todas las estaciones.")
else:
    st.dataframe(diferencias, hide_index=True, width="stretch")

st.subheader("Qué miden los datos")
st.markdown(
    "PM2.5 y PM10 son promedios de 24 horas por estación. La tabla maestra cubre "
    f"{datos.fecha.min():%Y-%m-%d} a {datos.fecha.max():%Y-%m-%d}, con una fila por estación y día."
)
_enlace_pagina("pages/datos_metodologia.py", "Ver Datos y metodología", "📚", "datos_metodologia")

st.subheader("Qué dicen las normas")
normas = pd.DataFrame([
    {
        "Referencia": f"OMS {OMS_ANIO_GUIA}",
        "PM2.5 anual (µg/m³)": OMS_PM25_ANUAL,
        "PM2.5 24 h (µg/m³)": OMS_PM25_24H,
        "PM10 anual (µg/m³)": OMS_PM10_ANUAL,
        "PM10 24 h (µg/m³)": OMS_PM10_24H,
        "Aplicación": "Guía",
    },
    {
        "Referencia": f"Colombia · {COLOMBIA_ANIO_INICIO_NORMA} a {COLOMBIA_ANIO_FIN_NORMA}",
        "PM2.5 anual (µg/m³)": COLOMBIA_PM25_ANUAL_2018_2029,
        "PM2.5 24 h (µg/m³)": COLOMBIA_PM25_24H_2018_2029,
        "PM10 anual (µg/m³)": COLOMBIA_PM10_ANUAL_2018_2029,
        "PM10 24 h (µg/m³)": COLOMBIA_PM10_24H_2018_2029,
        "Aplicación": f"Resolución 2254 de {COLOMBIA_ANIO_RESOLUCION}",
    },
    {
        "Referencia": "Colombia · desde 2030",
        "PM2.5 anual (µg/m³)": COLOMBIA_PM25_ANUAL_2030,
        "PM2.5 24 h (µg/m³)": pd.NA,
        "PM10 anual (µg/m³)": COLOMBIA_PM10_ANUAL_2030,
        "PM10 24 h (µg/m³)": pd.NA,
        "Aplicación": f"Resolución 2254 de {COLOMBIA_ANIO_RESOLUCION}",
    },
])
st.dataframe(normas, hide_index=True, width="stretch")
niveles = pd.DataFrame([{
    "Contaminante / periodo": "PM2.5 · 24 h",
    "Prevención (µg/m³)": COLOMBIA_PM25_PREVENCION,
    "Alerta (µg/m³)": COLOMBIA_PM25_ALERTA,
    "Emergencia (µg/m³)": COLOMBIA_PM25_EMERGENCIA,
}])
st.dataframe(niveles, hide_index=True, width="stretch")
st.warning(
    "La norma exige evaluar el cumplimiento por cada estación; el promedio de la ciudad no sirve para esa evaluación. "
    f"[OMS]({URL_GUIAS_OMS}) · [Resolución 2254 de {COLOMBIA_ANIO_RESOLUCION}]({URL_RESOLUCION_2254}); "
    f"los valores diarios colombianos rigen desde {COLOMBIA_FECHA_INICIO_24H}."
)

st.subheader("Índice de Calidad del Aire (ICA) · 24 horas")
st.markdown(
    f"{TEXTO_PRESENTACION_ICA_24H} [IDEAM]({URL_IDEAM_ICA_24H}) y "
    f"[MADS]({URL_RESOLUCION_2254})."
)
tabla_ica = pd.DataFrame(ICA_24H_PM)
tabla_ica_estilada = tabla_ica.style.map(
    lambda color: (
        f"background-color: {COLORES_ICA[color]}; "
        f"color: {'#111111' if color in {'Amarillo', 'Naranja'} else '#FFFFFF'}"
    ),
    subset=["Color"],
)
st.dataframe(tabla_ica_estilada, hide_index=True, width="stretch")
st.info(NOTA_ERRATA_IDEAM_ICA)

st.subheader("Salud: estimaciones poblacionales")
st.markdown(
    f"{TEXTO_METODOLOGIA_SALUD_PM25} [Ficha técnica de la Secretaría Distrital de Salud]({URL_SALUD_PM25_AIRQ})."
)
st.dataframe(pd.DataFrame(RIESGOS_RELATIVOS_PM25), hide_index=True, width="stretch")
st.caption(NOTA_INTERPRETACION_SALUD_PM25)

st.subheader("Qué tan seguido se superan los valores de 24 horas")
superaciones = calcular_superaciones(datos, DIAS_MINIMOS_PROMEDIO_ANUAL)
fin_periodo = datos.fecha.max().normalize()
inicio_12m = fin_periodo - pd.DateOffset(years=1) + pd.Timedelta(days=1)
st.markdown(
    f"Los porcentajes se calculan por estación sobre los días con dato: periodo completo "
    f"({datos.fecha.min():%Y-%m-%d} a {fin_periodo:%Y-%m-%d}, excluyendo el hueco marcado en los datos) "
    f"y últimos 12 meses ({inicio_12m:%Y-%m-%d} a {fin_periodo:%Y-%m-%d})."
)
_grafico_excedencias(
    superaciones, "pct_pm25_mayor_15_periodo", "pct_pm25_mayor_37_periodo",
    "Días sobre los valores de 24 h · periodo completo",
)
_grafico_excedencias(
    superaciones, "pct_pm25_mayor_15_12m", "pct_pm25_mayor_37_12m",
    "Días sobre los valores de 24 h · últimos 12 meses",
)
st.caption(
    f"La banda punteada representa {OMS_DIAS_EXCEDENCIA_24H[0]}–{OMS_DIAS_EXCEDENCIA_24H[1]} días de excedencia por año, "
    "asociados al percentil 99 de la guía de 24 h de la OMS. El porcentaje es descriptivo, no prueba incumplimiento; "
    "cada porcentaje se calcula por estación, nunca promediando estaciones."
)
fig_anual = go.Figure()
graficables = superaciones.loc[superaciones.pm25_medio_12m.notna()].sort_values("pm25_medio_12m")
fig_anual.add_trace(go.Bar(
    x=graficables.pm25_medio_12m, y=graficables.estacion_id, orientation="h",
    marker_color=ACENTO, name="Media de 12 meses",
))
fig_anual.add_vline(x=OMS_PM25_ANUAL, line_dash="dash", line_color="#F1C40F",
                    annotation_text=f"OMS anual · {OMS_PM25_ANUAL}", annotation_position="top")
fig_anual.add_vline(x=COLOMBIA_PM25_ANUAL_2018_2029, line_dash="dash", line_color="#E67E22",
                    annotation_text=f"Norma {COLOMBIA_ANIO_INICIO_NORMA}–{COLOMBIA_ANIO_FIN_NORMA} · {COLOMBIA_PM25_ANUAL_2018_2029}", annotation_position="top")
fig_anual.update_layout(
    title="PM2.5 medio en últimos 12 meses por estación",
    xaxis_title="PM2.5 medio (µg/m³)", yaxis_title="", height=690,
)
st.plotly_chart(aplicar_tema(fig_anual), width="stretch", config={"displayModeBar": False})
tabla_superaciones = superaciones.copy()
for columna in (
    "pct_pm25_mayor_15_periodo", "pct_pm25_mayor_37_periodo",
    "pct_pm25_mayor_15_12m", "pct_pm25_mayor_37_12m",
):
    tabla_superaciones[columna] = tabla_superaciones[columna].map(lambda valor: f"{valor:.1f}%" if pd.notna(valor) else "sin datos")
tabla_superaciones["pm25_medio_12m"] = tabla_superaciones.apply(
    lambda fila: f"{fila.pm25_medio_12m:.2f} µg/m³" if fila.estado_media_12m == "con datos suficientes" else "sin datos suficientes",
    axis=1,
)
st.dataframe(tabla_superaciones, hide_index=True, width="stretch")
st.caption(
    f"La media anual descriptiva se presenta solo con al menos {DIAS_MINIMOS_PROMEDIO_ANUAL} días con dato, "
    f"según la ficha de indicador SDA. [Ficha del indicador]({FUENTES[6]['url']})."
)

st.subheader("Qué pasa en Bogotá")
st.markdown(
    f"La SDA describe factores internos —emisiones del parque automotor y de la industria— y externos, "
    f"como material particulado de incendios forestales de otras regiones. La inversión térmica limita la dispersión "
    f"de contaminantes y, según la SDA, suele presentarse en los primeros meses del año o entre agosto y octubre. "
    f"([SDA: factores]({URL_FACTORES_INTERNOS_EXTERNOS_SDA}) · "
    f"[SDA: inversión térmica]({URL_INVERSION_TERMICA_SDA}).)"
)
hueco = datos.loc[datos.hueco_pm_2025.fillna(False), "fecha"]
if not hueco.empty:
    st.caption(
        f"El hueco de mediciones del proyecto va del {hueco.min():%Y-%m-%d} al {hueco.max():%Y-%m-%d}; "
        "estas fechas caen dentro del intervalo referido por la SDA."
    )
st.markdown(
    f"El régimen de lluvias de Bogotá es bimodal, con picos en abril–mayo y octubre–noviembre, y periodos de menos lluvia "
    f"en diciembre–febrero y julio–septiembre ([IDIGER / IDEAM]({URL_REGIMEN_LLUVIA_BOGOTA})). "
    "La siguiente serie muestra agregados del proyecto por mes calendario."
)
mensual = agregar_mensual(datos)
fig_mensual = make_subplots(specs=[[{"secondary_y": True}]])
fig_mensual.add_trace(
    go.Scatter(x=mensual.mes, y=mensual.pm25_medio, mode="lines+markers",
               name="PM2.5 medio (µg/m³)", line={"color": ACENTO}),
    secondary_y=False,
)
fig_mensual.add_trace(
    go.Scatter(x=mensual.mes, y=mensual.lluvia_media, mode="lines+markers",
               name="Lluvia media (mm)", line={"color": "#5DADE2"}),
    secondary_y=True,
)
fig_mensual.update_layout(title="Medias mensuales de PM2.5 y precipitación", hovermode="x unified")
fig_mensual.update_xaxes(title_text="Mes")
fig_mensual.update_yaxes(title_text="PM2.5 (µg/m³)", secondary_y=False)
fig_mensual.update_yaxes(title_text="Precipitación (mm)", secondary_y=True)
st.plotly_chart(aplicar_tema(fig_mensual), width="stretch", config={"displayModeBar": False})

st.subheader("Factores evaluados y pregunta del proyecto")
st.markdown(
    "Evaluamos viento, lluvia, temperatura, calendario y ubicación para describir cómo varían las mediciones de PM2.5. "
    "La pregunta del proyecto es qué variables se asocian más con las concentraciones y cómo cambian las predicciones "
    "en escenarios meteorológicos y de calendario. La información puede servir a autoridades y ciudadanos; "
    "el análisis no establece relaciones causales."
)
_enlace_pagina("pages/factores.py", "Explorar Factores", "🔎", "factores")
_enlace_pagina("pages/simulador.py", "Probar escenarios en Simulador", "🎛️", "simulador")

st.subheader("Fuentes oficiales")
for fuente in FUENTES:
    consulta = f" · consulta {fuente['fecha_consulta']}" if "fecha_consulta" in fuente else ""
    st.markdown(f"- [{fuente['nombre']}]({fuente['url']}){consulta}")
