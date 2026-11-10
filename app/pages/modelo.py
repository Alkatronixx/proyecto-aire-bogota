"""Muestra métricas publicadas y deja explícito que la página está en desarrollo.
Lee la tabla de métricas versionadas y el Ridge predictivo pequeño solo aquí.
No carga el modelo explicativo v1 ni usa el Ridge predictivo en el simulador.
El modelo de anomalías v2 queda reservado a la página de escenarios futura.
"""
import streamlit as st
from app.components.ui import cargar_estilos, encabezado_pagina, nota_metodologica
from app.utils.datos import cargar_csv_app, cargar_modelo_predictivo

cargar_estilos()
encabezado_pagina("Modelo", "Evaluación temporal y alcance de los modelos disponibles.")
st.info("En construcción. Se presenta el resumen temporal existente; todavía no hay una vista completa de evaluación.", icon="🚧")
modelo = cargar_modelo_predictivo()
estimador = modelo.named_steps["ridge"]
metricas = cargar_csv_app("metricas_modelos.csv")
temporal = metricas.loc[metricas.version.isin(["predictivo", "explicativo"]) & metricas.modelo.isin(["línea base", "Ridge", "Random Forest"])].copy()
st.caption(f"Artefacto predictivo guardado: Ridge, alpha={estimador.alpha}. Se carga solo en esta página para identificar el modelo asociado a la evaluación.")
st.dataframe(temporal, hide_index=True, use_container_width=True)
nota_metodologica("La línea base explicativa publicada usa promedios estación-mes que incluyen filas del periodo de prueba; debe leerse con esa limitación. La app no carga el RF v1.")
