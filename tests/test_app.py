"""Comprueba que las páginas carguen y que las rutas de lectura sean explícitas."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from app.utils.datos import ROOT, rutas_lectura_app

PAGES = [
    "portada.py",
    "contexto.py",
    "mapa.py",
    "factores.py",
    "simulador.py",
    "modelo.py",
    "datos_metodologia.py",
]


@pytest.mark.parametrize("page", PAGES)
def test_cada_pagina_carga_sin_excepciones(page: str) -> None:
    """Ejecuta cada página por separado para capturar errores de renderizado."""
    ruta = ROOT / "app" / "pages" / page
    resultado = AppTest.from_file(str(ruta), default_timeout=20).run()
    assert not resultado.exception, f"Excepción en {page}: {resultado.exception}"


def test_navegacion_registra_las_siete_paginas() -> None:
    """Verifica que el punto de entrada multipágina arranque sin excepciones."""
    resultado = AppTest.from_file(str(ROOT / "app" / "app.py"), default_timeout=20).run()
    assert not resultado.exception, str(resultado.exception)


def test_rutas_de_lectura_pertenecen_a_las_carpetas_autorizadas() -> None:
    """Restringe los cargadores a procesados, documentación, modelos y CSS local."""
    permitidas = (
        ROOT / "data" / "processed",
        ROOT / "data" / "docs",
        ROOT / "docs",
        ROOT / "models",
        ROOT / "app" / "assets",
    )
    for ruta in rutas_lectura_app():
        assert any(ruta.is_relative_to(base) for base in permitidas), ruta
    nombres = {ruta.name for ruta in rutas_lectura_app()}
    assert "modelo_explicativo.joblib" not in nombres


def test_loader_no_acepta_archivos_arbitrarios() -> None:
    """El cargador de CSV rechaza nombres que permitirían salir de processed."""
    from app.utils.datos import cargar_csv_app
    with pytest.raises(ValueError):
        cargar_csv_app("../../raw/secret.csv")
