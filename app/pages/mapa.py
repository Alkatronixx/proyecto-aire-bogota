"""Explora PM por estación sobre geometrías generalizadas para la app.
Lee la tabla maestra y GeoJSON livianos publicados en data/processed.
Agrega las observaciones antes de enviarlas a Plotly o PyDeck.
No completa el hueco de mediciones ni asigna categorías regulatorias.
"""
from datetime import date
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from app.components.paleta import color_rgb_cuantil, escala_plotly
from app.components.tema_graficos import aplicar_tema
from app.components.ui import cargar_estilos, caja_pendiente, encabezado_pagina, nota_metodologica
from app.utils.datos import cargar_aire, cargar_geojson_app

INICIO_PERIODO = date(2023, 10, 24)
FIN_PERIODO = date(2026, 10, 23)
INICIO_HUECO = pd.Timestamp("2025-08-04")
FIN_HUECO = pd.Timestamp("2025-10-16")
UMBRAL_COBERTURA_BAJA = 0.50  # El umbral de visibilidad se mantiene explícito para interpretar el mapa.


@st.cache_data(show_spinner=False)
def agregar_mapa(df: pd.DataFrame, inicio: date, fin: date, variable: str,
                 localidades: tuple[str, ...], incluir_moviles: bool) -> pd.DataFrame:
    """Resume valor y cobertura por estación dentro de los filtros recibidos."""
    filas = df.loc[df.fecha.between(pd.Timestamp(inicio), pd.Timestamp(fin))].copy()
    filas = filas.loc[filas.localidad.isin(localidades)]
    if not incluir_moviles:
        filas = filas.loc[~filas.es_movil]
    return (filas.groupby(["estacion_id", "estacion", "localidad", "es_movil"], as_index=False)
            .agg(valor_medio=(variable, "mean"), dias_con_dato=(variable, "count"),
                 lat=("lat", "first"), lon=("lon", "first")))


@st.cache_data(show_spinner=False)
def serie_semanal(df: pd.DataFrame, inicio: date, fin: date, variable: str,
                  localidades: tuple[str, ...], incluir_moviles: bool,
                  estacion_id: str) -> pd.DataFrame:
    """Calcula medias semanales de una estación y mediana diaria de ciudad."""
    periodo = df.fecha.between(pd.Timestamp(inicio), pd.Timestamp(fin))
    # La referencia de ciudad incluye todas las estaciones, aunque el mapa se filtre por localidad.
    filas_ciudad = df.loc[periodo].copy()
    filas = filas_ciudad.copy()
    if localidades:
        filas = filas.loc[filas.localidad.isin(localidades)]
    if not incluir_moviles:
        filas = filas.loc[~filas.es_movil]
    filas["semana"] = filas.fecha.dt.to_period("W").dt.start_time
    diaria = filas_ciudad.groupby("fecha")[variable].median().rename("mediana_ciudad")
    ciudad = diaria.rename_axis("fecha").reset_index()
    ciudad["semana"] = ciudad.fecha.dt.to_period("W").dt.start_time
    ciudad = ciudad.groupby("semana", as_index=False).mediana_ciudad.mean()
    elegida = (filas.loc[filas.estacion_id.eq(estacion_id)]
               .groupby("semana", as_index=False)[variable].mean()
               .rename(columns={variable: "estacion"}))
    return ciudad.merge(elegida, on="semana", how="outer").sort_values("semana")


def preparar_estaciones(resumen: pd.DataFrame, geojson: dict, dias_rango: int,
                        referencia: pd.Series, estacion_destacada: str,
                        solo_elegida: bool) -> list[dict]:
    """Une las estadísticas a puntos procesados y codifica cobertura en opacidad."""
    datos = resumen.set_index("estacion_id", drop=False)
    salida = []
    for feature in geojson["features"]:
        eid = feature["properties"]["estacion_id"]
        fila = datos.loc[eid] if eid in datos.index else None
        coords = feature["geometry"]["coordinates"]
        if fila is None:
            registro = {"estacion_id": eid, "estacion": feature["properties"]["estacion"],
                        "localidad": "", "es_movil": feature["properties"]["es_movil"],
                        "valor_medio": None, "dias_con_dato": 0, "cobertura": 0.0,
                        "lon": coords[0], "lat": coords[1], "color": [110, 120, 135, 55],
                        "borde": [110, 120, 135, 120], "nota": "sin datos"}
        else:
            cobertura = float(fila.dias_con_dato / dias_rango) if dias_rango else 0.0
            bajo = cobertura < UMBRAL_COBERTURA_BAJA
            color = color_rgb_cuantil(float(fila.valor_medio), referencia) if pd.notna(fila.valor_medio) else [110, 120, 135]
            transparencia = 90 if bajo else 235
            registro = {"estacion_id": eid, "estacion": fila.estacion, "localidad": fila.localidad,
                        "es_movil": bool(fila.es_movil), "valor_medio": None if pd.isna(fila.valor_medio) else round(float(fila.valor_medio), 2),
                        "dias_con_dato": int(fila.dias_con_dato), "cobertura": round(100*cobertura, 1),
                        "lon": coords[0], "lat": coords[1], "color": [*color, transparencia],
                        "borde": [255, 255, 255, 235] if fila.es_movil else [15, 20, 28, 230],
                        "nota": "cobertura baja" if bajo else ""}
        if not solo_elegida or eid == estacion_destacada:
            salida.append(registro)
    return salida


cargar_estilos()
df = cargar_aire()
encabezado_pagina("Mapa de estaciones", "Explora promedios observados por ubicación y periodo.")
localidades_disponibles = sorted(df.localidad.dropna().unique().tolist())
with st.sidebar:
    st.subheader("Filtros del mapa")
    contaminante = st.selectbox("Contaminante", ["PM2.5", "PM10"], key="mapa_contaminante")
    variable = "pm25" if contaminante == "PM2.5" else "pm10"
    fechas = st.date_input("Rango de fechas", value=(date(2025, 10, 24), FIN_PERIODO),
                           min_value=INICIO_PERIODO, max_value=FIN_PERIODO,
                           format="DD/MM/YYYY", key="mapa_fechas")
    seleccion_localidades = st.multiselect("Localidades", localidades_disponibles,
                                           default=localidades_disponibles, key="mapa_localidades")
    incluir_moviles = st.toggle("Incluir estaciones móviles", value=True, key="mapa_moviles")
    vista = st.radio("Vista", ["Promedio del rango", "Mes a mes", "Estación elegida"], key="mapa_vista")
    nombre_estacion = st.selectbox("Estación elegida", sorted(df.estacion.dropna().unique()), key="mapa_estacion")

if isinstance(fechas, (tuple, list)) and len(fechas) == 2:
    inicio, fin = fechas
else:
    inicio, fin = fechas, fechas
if inicio > fin:
    st.warning("La fecha inicial debe ser anterior a la final.")
    st.stop()
estaciones_geo = cargar_geojson_app("estaciones.geojson")
localidades_geo = cargar_geojson_app("localidades.geojson")
se_hueco = pd.Timestamp(inicio) <= FIN_HUECO and pd.Timestamp(fin) >= INICIO_HUECO
if se_hueco:
    st.info("El rango incluye parte del hueco del 04-ago al 16-oct-2025; esos días no tienen mediciones y quedan fuera de los promedios.")

meses = pd.period_range(pd.Timestamp(inicio).to_period("M"), pd.Timestamp(fin).to_period("M"), freq="M")
if vista == "Mes a mes" and len(meses):
    if len(meses) > 1:
        opciones_meses = [str(mes) for mes in meses]
        mes_elegido = st.select_slider("Mes del mapa", options=opciones_meses,
                                       value=opciones_meses[-1], key="mapa_mes")
    else:
        mes_elegido = str(meses[0])
        st.caption("El rango seleccionado contiene un único mes.")
    periodo = pd.Period(mes_elegido, freq="M")
    inicio_vista = max(inicio, periodo.start_time.date())
    fin_vista = min(fin, periodo.end_time.date())
    st.caption(f"Mes seleccionado: {periodo.strftime('%B %Y')}. El control permite recorrer el periodo mes a mes.")
else:
    inicio_vista, fin_vista = inicio, fin

resumen = agregar_mapa(df, inicio_vista, fin_vista, variable,
                       tuple(seleccion_localidades), incluir_moviles)
if resumen.empty or resumen.valor_medio.notna().sum() == 0:
    st.info("No hay mediciones del contaminante seleccionado con estos filtros. Prueba otro rango o localidad.")
else:
    valores = resumen.valor_medio.dropna()
    dias_rango = (pd.Timestamp(fin_vista)-pd.Timestamp(inicio_vista)).days+1
    solo_elegida = vista == "Estación elegida"
    datos_puntos = preparar_estaciones(resumen, estaciones_geo, dias_rango, valores,
                                       df.loc[df.estacion.eq(nombre_estacion), "estacion_id"].iloc[0], solo_elegida)
    features_loc = [f for f in localidades_geo["features"]
                    if f["properties"]["localidad"] in seleccion_localidades]
    capas = [pdk.Layer("GeoJsonLayer", data={"type": "FeatureCollection", "features": features_loc},
                       pickable=True, stroked=True, filled=True,
                       get_fill_color=[98, 111, 128, 30], get_line_color=[135, 149, 168, 100],
                       line_width_min_pixels=1, get_line_width=1)]
    capas.append(pdk.Layer("ScatterplotLayer", data=datos_puntos,
                           get_position="[lon, lat]", get_fill_color="color", get_line_color="borde",
                           get_radius=220, radius_min_pixels=7, radius_max_pixels=7,
                           line_width_min_pixels=2, stroked=True, pickable=True))
    deck = pdk.Deck(layers=capas,
                    initial_view_state=pdk.ViewState(latitude=4.65, longitude=-74.08, zoom=10, pitch=0),
                    tooltip={"html": "<b>{estacion}</b><br/>Localidad: {localidad}<br/>"+
                                     contaminante+" medio: {valor_medio} µg/m³<br/>"+
                                     "Días con dato: {dias_con_dato}<br/>Cobertura: {cobertura}%<br/>{nota}"},
                    map_style=None)
    st.pydeck_chart(deck, width="stretch")
    paradas_escala = escala_plotly(valores)
    gradiente = ", ".join(f"{color} {posicion*100:.2f}%" for posicion, color in paradas_escala)
    st.markdown(
        f'<div style="height:10px;border-radius:8px;background:linear-gradient(90deg,{gradiente});"></div>'
        f'<small>Escala continua por cuantiles · mínimo {valores.min():.2f} y máximo {valores.max():.2f} µg/m³ · '
        f"círculos con cobertura menor al {UMBRAL_COBERTURA_BAJA:.0%}: cobertura baja y transparencia</small>",
        unsafe_allow_html=True,
    )
    caja_pendiente("Los umbrales oficiales para interpretar qué es un valor alto siguen pendientes de fuente verificable.")
    nota_metodologica("El radio de los puntos es fijo. El borde blanco identifica estaciones móviles; el porcentaje de cobertura usa todos los días del rango, incluido el hueco sin mediciones.")

    st.subheader("Ranking de estaciones")
    ranking = resumen.dropna(subset=["valor_medio"]).sort_values("valor_medio")
    barras = go.Figure(go.Bar(y=ranking.estacion, x=ranking.valor_medio, orientation="h",
                              marker_color=[f"rgb{tuple(color_rgb_cuantil(v, valores))}" for v in ranking.valor_medio],
                              hovertemplate="%{y}<br>Media: %{x:.2f} µg/m³<extra></extra>"))
    barras.update_layout(title=f"{contaminante} medio por estación", xaxis_title="µg/m³", yaxis_title="")
    st.plotly_chart(aplicar_tema(barras), width="stretch", config={"displayModeBar": False})

    st.subheader(f"Serie semanal · {nombre_estacion}")
    estacion_id = df.loc[df.estacion.eq(nombre_estacion), "estacion_id"].iloc[0]
    semanal = serie_semanal(df, inicio, fin, variable, tuple(seleccion_localidades),
                            incluir_moviles, estacion_id)
    if semanal.empty or (semanal.estacion.isna().all() and semanal.mediana_ciudad.isna().all()):
        st.info("No hay una serie semanal disponible para la estación y los filtros seleccionados.")
    else:
        linea = go.Figure()
        linea.add_trace(go.Scatter(x=semanal.semana, y=semanal.estacion, mode="lines+markers",
                                   name=nombre_estacion, line={"color": "#00C2A8"}))
        linea.add_trace(go.Scatter(x=semanal.semana, y=semanal.mediana_ciudad, mode="lines",
                                   name="Mediana semanal ciudad", line={"color": "#F1C40F", "dash": "dot"}))
        linea.add_vrect(x0=INICIO_HUECO, x1=FIN_HUECO, fillcolor="#778395", opacity=.22,
                        line_width=0, layer="below")
        linea.update_layout(title=f"{contaminante} semanal observado", xaxis_title="Semana", yaxis_title="µg/m³", hovermode="x unified")
        st.plotly_chart(aplicar_tema(linea), width="stretch", config={"displayModeBar": False})
