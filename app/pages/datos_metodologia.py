"""Documenta fuentes, cobertura, decisiones e incidentes de calidad.
Lee los documentos aprobados y CSV procesados a través de datos.py.
Muestra el periodo y tamaño reales de la tabla maestra.
Expone limitaciones y el hueco de PM sin rellenar sus valores.
"""
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from app.components.paleta import escala_plotly
from app.components.tema_graficos import aplicar_tema
from app.components.ui import cargar_estilos, caja_pendiente, encabezado_pagina
from app.utils.datos import cargar_aire, cargar_csv_app, cargar_markdown, tabla_decisiones_vigentes, tabla_fuentes

cargar_estilos()
encabezado_pagina("Datos y metodología", "Fuentes, cobertura temporal, decisiones vigentes y límites de interpretación.")
df = cargar_aire()

fuentes = tabla_fuentes(cargar_markdown("fuentes"))
st.subheader("Fuentes documentadas")
st.dataframe(fuentes, hide_index=True, use_container_width=True)

st.subheader("Cobertura y estructura")
c1, c2, c3 = st.columns(3)
c1.metric("Periodo", f"{df.fecha.min():%Y-%m-%d} — {df.fecha.max():%Y-%m-%d}")
c2.metric("Grano", "Una fila por estación y día")
c3.metric("Filas", f"{len(df):,}".replace(",", "."))

st.markdown("#### Cobertura de PM2.5 · estación × mes")
cobertura = cargar_csv_app("cobertura_estacion_mes.csv")
cobertura["año_mes"] = cobertura["año_mes"].astype(str)
meses = pd.period_range(df.fecha.min().to_period("M"), df.fecha.max().to_period("M"), freq="M").astype(str).tolist()
estaciones = sorted(cobertura.estacion_id.astype(str).unique())
matriz = cobertura.pivot_table(index="estacion_id", columns="año_mes", values="pct_dias_pm25", aggfunc="mean")
matriz = matriz.reindex(index=estaciones, columns=meses)
fig = px.imshow(
    matriz,
    x=meses,
    y=estaciones,
    aspect="auto",
    zmin=0,
    zmax=100,
    color_continuous_scale=escala_plotly(cobertura.pct_dias_pm25),
    labels={"x": "Año-mes", "y": "Estación", "color": "% días con PM2.5"},
    origin="upper",
)
fig.update_layout(title="Porcentaje de días del mes con PM2.5 observado", coloraxis_colorbar={"ticksuffix": "%"})
fig.update_xaxes(tickangle=-60, dtick=2)
# El área se marca sobre las columnas del periodo de ausencia documentado, sin cambiar sus valores.
if "2025-08" in meses and "2025-10" in meses:
    fig.add_vrect(x0=meses.index("2025-08")-.5, x1=meses.index("2025-10")+.5,
                  fillcolor="#7B8492", opacity=.18, line_width=0, layer="below")
    fig.add_annotation(x=meses.index("2025-09"), y=-.7, xref="x", yref="y", text="hueco de PM",
                       showarrow=False, font={"color": "#DDE2EA", "size": 10})
st.plotly_chart(aplicar_tema(fig), use_container_width=True, config={"displayModeBar": False})
st.caption("El hueco oficial de PM2.5 va del 2025-08-04 al 2025-10-16. Los faltantes permanecen como faltantes.")

texto_decisiones = cargar_markdown("decisiones")
decisiones = tabla_decisiones_vigentes(texto_decisiones)
st.subheader("Decisiones vigentes")
st.dataframe(decisiones, hide_index=True, use_container_width=True)

st.subheader("Incidentes y controles de calidad documentados")
incidentes = decisiones.loc[decisiones.ID.isin(["DV-04", "DV-05", "DV-07", "DV-10"]), ["ID", "Tema", "Decisión vigente"]]
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
st.dataframe(incidentes, hide_index=True, use_container_width=True)

st.subheader("Limitaciones")
limitaciones = [
    "El PM2.5 medio baja en las 19 estaciones al comparar entrenamiento y prueba; la causa no está determinada.",
    "Once de las 19 estaciones comparten información de precipitación de Jardín Botánico.",
    "La dirección del viento se excluye del modelo base: su promedio diario y su coherencia entre estaciones tienen limitaciones documentadas.",
    "Aproximadamente el 97% de los datos IDEAM tiene nivel preliminar.",
    "2023 y 2026 son años parciales dentro del periodo analizado.",
    "La página de la SDA lista 20 estaciones, incluida Bosa, que no está en nuestros archivos.",
]
for texto in limitaciones:
    st.markdown(f"- {texto}")
caja_pendiente("Los umbrales oficiales de calidad del aire siguen pendientes de una fuente oficial citada.")
