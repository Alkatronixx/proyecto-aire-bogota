"""Configura la navegación multipágina de la aplicación.
Registra siete páginas y prepara el Ridge v2 una sola vez al arrancar.
Cada página lee los datos publicados mediante cargadores con caché.
Las páginas aún no desarrolladas muestran un aviso explícito.
"""
from pathlib import Path
import streamlit as st
from utils.datos import cargar_modelo_anomalia

APP_DIR = Path(__file__).resolve().parent
PAGES_DIR = APP_DIR / "pages"

st.set_page_config(
    page_title="Aire Bogotá | PM2.5",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# La primera importación de scikit-learn añade varios segundos; se hace al inicio
# para que abrir el simulador o la evaluación después de la portada no espere esa carga.
cargar_modelo_anomalia()

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
