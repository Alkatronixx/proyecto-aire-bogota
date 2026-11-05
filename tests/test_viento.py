"""Pruebas de integridad de data/interim/viento_largo.parquet.
Comprueba la llave diaria y el rango acordado para viento de RMCAB.
Verifica que la serie no tenga huecos y use solo las dos variables previstas.
Ejecutar con: pytest tests/test_viento.py -v -s.
"""

from pathlib import Path

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARQUET_PATH = PROJECT_ROOT / "data" / "interim" / "viento_largo.parquet"


@pytest.fixture(scope="module")
def df():
    """Carga el parquet una vez para las pruebas del módulo.

    Parámetros: ninguno. Devuelve la tabla o marca las pruebas como omitidas.
    """
    if not PARQUET_PATH.exists():
        pytest.skip(f"Parquet no encontrado: {PARQUET_PATH}")
    return pd.read_parquet(PARQUET_PATH)


def test_sin_duplicados_fecha_estacion_variable(df):
    """La llave fecha-estación-variable aparece como máximo una vez.

    Parámetros: df de la fixture. Devuelve None; falla si hay claves repetidas.
    """
    llave = ["fecha", "estacion_id", "variable"]
    duplicados = df[df.duplicated(llave, keep=False)]
    assert duplicados.empty, duplicados.head(20).to_string(index=False)


def test_fechas_en_rango_esperado(df):
    """Todas las filas cubren el intervalo diario indicado por el proyecto.

    Parámetros: df de la fixture. Devuelve None; falla al salir del rango.
    """
    inicio, fin = pd.Timestamp("2023-10-24"), pd.Timestamp("2026-10-23")
    fuera = df[(df["fecha"] < inicio) | (df["fecha"] > fin)]
    assert fuera.empty, fuera[["fecha", "archivo_origen"]].head(20).to_string(index=False)
    assert df["fecha"].min() == inicio
    assert df["fecha"].max() == fin


def test_sin_huecos_en_union_de_fechas(df):
    """La unión contiene todos los días desde 2023-10-24 hasta 2026-10-23.

    Parámetros: df de la fixture. Devuelve None; falla si falta un día.
    """
    esperadas = pd.date_range("2023-10-24", "2026-10-23", freq="D")
    presentes = pd.DatetimeIndex(df["fecha"].drop_duplicates().sort_values())
    faltantes = esperadas.difference(presentes)
    assert len(esperadas) == 1096
    assert len(faltantes) == 0, f"Fechas faltantes: {faltantes.tolist()}"


def test_variables_validas(df):
    """Solo se conservan velocidad y dirección del viento.

    Parámetros: df de la fixture. Devuelve None; falla si aparece otra variable.
    """
    assert set(df["variable"].dropna().unique()) == {"vel_viento", "dir_viento"}


def test_grilla_completa_esperada(df):
    """La grilla completa conserva las 17 estaciones por 2 variables y 1096 días.

    Parámetros: df de la fixture. Devuelve None; falla si el tamaño difiere.
    """
    assert df["estacion_id"].nunique() == 17
    assert len(df) == 37_264
