"""Comprueba que las páginas carguen y que las rutas de lectura sean explícitas."""
from pathlib import Path
from datetime import date
import pytest
from streamlit.testing.v1 import AppTest
from app.utils.datos import ROOT, cargar_aire, cargar_geojson_app, rutas_lectura_app

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


def test_mapa_carga_con_filtros_por_defecto() -> None:
    """Comprueba el render del mapa con su rango y selección iniciales."""
    ruta = ROOT / "app" / "pages" / "mapa.py"
    resultado = AppTest.from_file(str(ruta), default_timeout=30).run()
    assert not resultado.exception, str(resultado.exception)


def test_mapa_sin_datos_muestra_aviso_sin_excepcion() -> None:
    """El hueco completo permite probar filtros válidos sin mediciones PM."""
    ruta = ROOT / "app" / "pages" / "mapa.py"
    resultado = AppTest.from_file(str(ruta), default_timeout=30).run()
    resultado.date_input[0].set_value((date(2025, 8, 4), date(2025, 10, 16)))
    resultado.run()
    assert not resultado.exception, str(resultado.exception)
    assert any("No hay mediciones" in elemento.value for elemento in resultado.info)


def test_mapa_vista_mes_a_mes_carga() -> None:
    """Comprueba el selector mensual además de la vista promedio predeterminada."""
    ruta = ROOT / "app" / "pages" / "mapa.py"
    resultado = AppTest.from_file(str(ruta), default_timeout=30).run()
    resultado.radio[0].set_value("Mes a mes")
    resultado.run()
    assert not resultado.exception, str(resultado.exception)


def test_factores_carga_con_filtros_por_defecto() -> None:
    """Comprueba el render de gráficos y agregados descriptivos por defecto."""
    ruta = ROOT / "app" / "pages" / "factores.py"
    resultado = AppTest.from_file(str(ruta), default_timeout=30).run()
    assert not resultado.exception, str(resultado.exception)


def test_geojson_estaciones_enlaza_las_19_estaciones_maestras() -> None:
    """Evita que el mapa publique puntos faltantes o estaciones sin ID maestro."""
    geojson = cargar_geojson_app("estaciones.geojson")
    ids_geo = {f["properties"]["estacion_id"] for f in geojson["features"]}
    ids_maestro = set(cargar_aire().estacion_id.unique())
    assert len(geojson["features"]) == 19
    assert ids_geo == ids_maestro
