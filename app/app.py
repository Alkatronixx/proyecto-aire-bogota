"""Configura la navegación y carga inicial de las siete páginas de la app.
El Ridge v2 se carga de forma diferida al abrir Simulador o Modelo, con caché.
Las páginas activas leen datos publicados mediante cargadores con caché.
Los componentes compartidos mantienen consistentes el tema y la presentación.
"""
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
# Streamlit antepone el directorio app/ al importar páginas; la raíz primero evita
# que app/app.py tape al paquete app usado por los imports compartidos.
for ruta in (str(ROOT_DIR), str(APP_DIR)):
    if ruta in sys.path:
        sys.path.remove(ruta)
sys.path[:0] = [str(ROOT_DIR), str(APP_DIR)]

import streamlit as st

PAGES_DIR = APP_DIR / "pages"

st.set_page_config(
    page_title="Aire Bogotá | PM2.5",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

paginas = [
    st.Page(PAGES_DIR / "portada.py", title="Portada", icon="🌿", default=True),
    st.Page(PAGES_DIR / "contexto.py", title="Contexto", icon="🏙️"),
    st.Page(PAGES_DIR / "mapa.py", title="Mapa", icon="🗺️"),
    st.Page(PAGES_DIR / "factores.py", title="Factores", icon="🔎"),
    st.Page(PAGES_DIR / "simulador.py", title="Simulador", icon="🎛️"),
    st.Page(PAGES_DIR / "modelo.py", title="Modelo", icon="📈"),
    st.Page(PAGES_DIR / "datos_metodologia.py", title="Datos y metodología", icon="📚"),
]
pagina = st.navigation(paginas)
pagina.run()
