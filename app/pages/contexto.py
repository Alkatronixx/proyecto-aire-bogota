"""Presenta el estado de construcción de la página de contexto."""
import streamlit as st
from app.components.ui import cargar_estilos, encabezado_pagina

cargar_estilos()
encabezado_pagina("Contexto de Bogotá", "Calidad del aire, estaciones y pregunta de negocio.")
st.info("En construcción. Esta página incorporará el contexto del problema y su relación con las fuentes documentadas.", icon="🚧")
