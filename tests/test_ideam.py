"""Pruebas de integridad del producto diario limpio del IDEAM.
Lee ideam_largo.parquet y el catálogo estaciones_ideam.csv.
Comprueba clave, periodo, variables y coordenadas de estaciones en la caja de Bogotá.
Ejecutar con: pytest tests/test_ideam.py -v.
"""

from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "data" / "interim" / "ideam_largo.parquet"
CATALOGO = ROOT / "data" / "processed" / "estaciones_ideam.csv"


@pytest.fixture(scope="module")
def datos():
    """Carga parquet y catálogo una vez; omite si no se ejecutó el proceso.

    Parámetros: ninguno. Devuelve tabla diaria y catálogo de estaciones.
    """
    if not PARQUET.exists() or not CATALOGO.exists():
        pytest.skip("Ejecutar src/datos/limpiar_ideam.py antes de estas pruebas")
    return pd.read_parquet(PARQUET), pd.read_csv(CATALOGO)


def test_clave_unica_fecha_estacion_variable(datos):
    """No hay más de un valor diario por estación IDEAM y variable."""
    tabla, _ = datos
    assert not tabla.duplicated(["fecha", "estacion_ideam_id", "variable"]).any()


def test_fechas_en_periodo(datos):
    """Todas las fechas pertenecen al intervalo vigente del proyecto."""
    tabla, _ = datos
    fechas = pd.to_datetime(tabla.fecha)
    assert fechas.between("2023-10-24", "2026-10-23").all()


def test_variables_permitidas(datos):
    """El parquet principal contiene solo precipitación y temperaturas."""
    tabla, _ = datos
    assert set(tabla.variable.unique()) <= {"precip_mm", "tmax_c", "tmin_c"}
    assert set(tabla.variable.unique()) == {"precip_mm", "tmax_c", "tmin_c"}


def test_coordenadas_numericas_y_en_rango_para_bogota(datos):
    """Las coordenadas catalogadas dentro de Bogotá son numéricas y válidas."""
    _, catalogo = datos
    bogota = catalogo.loc[catalogo.en_bogota.astype(str).str.lower().eq("true")]
    assert pd.api.types.is_numeric_dtype(bogota.lat)
    assert pd.api.types.is_numeric_dtype(bogota.lon)
    assert bogota.lat.between(4.3, 5.0).all()
    assert bogota.lon.between(-74.4, -73.8).all()
