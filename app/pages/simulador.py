"""Presenta el estado de construcción del simulador explicativo v2."""
import streamlit as st
from app.components.ui import cargar_estilos, encabezado_pagina

cargar_estilos()
encabezado_pagina("Simulador de escenarios", "Explora predicciones del modelo de anomalías v2.")
st.info("En construcción. El futuro simulador usará el Ridge v2 y su climatología; no cargará el RF v1.", icon="🚧")
