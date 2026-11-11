"""Documenta fuentes, cobertura, decisiones e incidentes de calidad.
Lee los documentos aprobados y CSV procesados a través de datos.py.
Muestra el periodo y tamaño reales de la tabla maestra.
Expone limitaciones y el hueco de PM sin rellenar sus valores.
"""
import streamlit as st
from app.components.ui import cargar_estilos, encabezado_pagina
from app.utils.datos import (
    cargar_fechas_aire, cargar_markdown, entradas_decisiones, firma_markdown,
    preparar_cobertura_estacion_mes, tabla_decisiones_vigentes, tabla_fuentes,
)
from app.utils.fuentes_contexto import ESTACIONES_LISTADAS_SDA, TEXTO_DATOS_ICA
from app.utils.graficos import figura_cobertura_estacion_mes

cargar_estilos()
encabezado_pagina("Datos y metodología", "Fuentes, cobertura temporal, decisiones vigentes y límites de interpretación.")
df = cargar_fechas_aire()

fuentes = tabla_fuentes(cargar_markdown("fuentes"))
st.subheader("Fuentes documentadas")
st.dataframe(fuentes, hide_index=True, width="stretch", lazy=True)
st.download_button(
    "Descargar fuentes en CSV", fuentes.to_csv(index=False).encode("utf-8-sig"),
    file_name="fuentes_documentadas.csv", mime="text/csv",
)

st.subheader("Cobertura y estructura")
c1, c2, c3 = st.columns(3)
c1.metric("Periodo", f"{df.fecha.min():%Y-%m-%d} — {df.fecha.max():%Y-%m-%d}")
c2.metric("Grano", "Una fila por estación y día")
c3.metric("Filas", f"{len(df):,}".replace(",", "."))

with st.expander("Cobertura de PM2.5 · estación × mes", on_change="rerun", key="expander_cobertura_metodologia") as bloque_cobertura:
    if bloque_cobertura.open:
        with st.spinner("Cargando cobertura mensual de las estaciones…"):
            cobertura, meses, estaciones, matriz = preparar_cobertura_estacion_mes()
            fig = figura_cobertura_estacion_mes(matriz, meses, estaciones)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.caption("El hueco oficial de PM2.5 va del 2025-08-04 al 2025-10-16. Los faltantes permanecen como faltantes.")
            st.download_button(
                "Descargar cobertura mensual completa",
                cobertura.to_csv(index=False).encode("utf-8-sig"),
                file_name="cobertura_estacion_mes.csv", mime="text/csv",
            )

decisiones_texto = cargar_markdown("decisiones", firma_markdown("decisiones"))
entradas, avisos_decisiones = entradas_decisiones(decisiones_texto)
st.subheader("Registro de decisiones fechadas")
st.caption(f"Entradas interpretadas: {len(entradas)}")
if not entradas.empty:
    ultimas = entradas.tail(5).iloc[::-1]
    st.markdown("**Últimas 5 entradas:** " + " · ".join(
        f"{fila.Fecha}: {fila.Título}" for fila in ultimas.itertuples(index=False)
    ))
if avisos_decisiones:
    st.warning("No se pudo interpretar la decisión o el encabezado de estas entradas: "
               + "; ".join(avisos_decisiones))

with st.expander("Decisiones vigentes e incidentes de calidad", on_change="rerun", key="expander_decisiones_metodologia") as bloque_decisiones:
    if bloque_decisiones.open:
        with st.spinner("Leyendo la tabla de decisiones y los incidentes…"):
            import pandas as pd

            decisiones = tabla_decisiones_vigentes(decisiones_texto)
            st.subheader("Decisiones vigentes")
            st.dataframe(decisiones, hide_index=True, width="stretch", lazy=True)
            st.download_button(
                "Descargar decisiones vigentes en CSV",
                decisiones.to_csv(index=False).encode("utf-8-sig"),
                file_name="decisiones_vigentes.csv", mime="text/csv",
            )
            st.subheader("Detalle de decisiones fechadas")
            st.dataframe(entradas, hide_index=True, width="stretch", lazy=True)
            st.subheader("Incidentes y controles de calidad documentados")
            incidentes = decisiones.loc[
                decisiones.ID.isin(["DV-04", "DV-05", "DV-07", "DV-10"]),
                ["ID", "Tema", "Decisión vigente"],
            ]
            incidentes = pd.concat(
                [
                    incidentes,
                    pd.DataFrame([{
                        "ID": "AL-01",
                        "Tema": "Día meteorológico del IDEAM",
                        "Decisión vigente": "Posible desfase de un día, comprobado con desplazamientos de -2 a +2; se mantiene la alineación original.",
                    }]),
                ],
                ignore_index=True,
            )
            st.dataframe(incidentes, hide_index=True, width="stretch", lazy=True)
            st.download_button(
                "Descargar incidentes de calidad en CSV",
                incidentes.to_csv(index=False).encode("utf-8-sig"),
                file_name="incidentes_calidad.csv", mime="text/csv",
            )

st.subheader("Limitaciones")
limitaciones = [
    "El PM2.5 medio baja en las 19 estaciones al comparar entrenamiento y prueba; la causa no está determinada.",
    "Once de las 19 estaciones comparten información de precipitación de Jardín Botánico.",
    "La dirección del viento se excluye del modelo base: su promedio diario y su coherencia entre estaciones tienen limitaciones documentadas.",
    "Aproximadamente el 97% de los datos IDEAM tiene nivel preliminar.",
    "2023 y 2026 son años parciales dentro del periodo analizado.",
    f"La página de la SDA lista {ESTACIONES_LISTADAS_SDA} estaciones, incluida Bosa, que no está en nuestros archivos.",
]
for texto in limitaciones:
    st.markdown(f"- {texto}")
st.caption(TEXTO_DATOS_ICA)
