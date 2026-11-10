"""Presenta el estado de construcción del mapa exploratorio."""
import streamlit as st
from app.components.ui import cargar_estilos, encabezado_pagina

cargar_estilos()
encabezado_pagina("Mapa de estaciones", "Explora concentraciones observadas por ubicación y periodo.")
st.info("En construcción. La portada ya incluye una vista pequeña de las 19 estaciones.", icon="🚧")
