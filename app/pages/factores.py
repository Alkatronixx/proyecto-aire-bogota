"""Presenta el estado de construcción de la página de factores."""
import streamlit as st
from app.components.ui import cargar_estilos, encabezado_pagina

cargar_estilos()
encabezado_pagina("Factores asociados", "Comparaciones descriptivas de meteorología, calendario y PM2.5.")
st.info("En construcción. Las comparaciones futuras se mostrarán como asociaciones descriptivas, no como causalidad.", icon="🚧")
