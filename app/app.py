"""Configura el tema y la navegación multipágina de la aplicación.
Registra siete páginas de la app y deja Portada como página inicial.
Cada página completa sus propias lecturas mediante los cargadores con caché.
Los cinco módulos todavía no construidos muestran un aviso explícito.
"""
from pathlib import Path
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
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
