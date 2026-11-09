"""Pruebas de calidad para los nuevos productos de viento de ciudad.
Lee viento_limpio.parquet y viento_ciudad.parquet generados por viento_ciudad.py.
Comprueba rangos físicos, llave y coherencia entre cobertura e índice.
Ejecutar con: pytest tests/test_viento_ciudad.py -v.
"""

from pathlib import Path

import pandas as pd
import pytest


INTERIM = Path(__file__).resolve().parents[1] / "data" / "interim"


@pytest.fixture(scope="module")
def tablas():
    """Carga los dos productos; omite si aún no se ha ejecutado el proceso.

    Parámetros: ninguno. Devuelve par limpio e índice.
    """
    limpia, indice = INTERIM / "viento_limpio.parquet", INTERIM / "viento_ciudad.parquet"
    if not limpia.exists() or not indice.exists():
        pytest.skip("Ejecutar src/datos/viento_ciudad.py antes de estas pruebas")
    return pd.read_parquet(limpia), pd.read_parquet(indice)


def test_velocidades_no_negativas(tablas):
    """No quedan velocidades negativas después de limpieza."""
    limpia, _ = tablas
    vel = limpia.loc[limpia.variable.eq("vel_viento"), "valor"].dropna()
    assert (vel >= 0).all()


def test_direcciones_en_rango(tablas):
    """Las direcciones conservadas quedan entre cero y 360 grados."""
    limpia, _ = tablas
    dir_ = limpia.loc[limpia.variable.eq("dir_viento"), "valor"].dropna()
    assert dir_.between(0, 360).all()


def test_llave_unica(tablas):
    """Cada fecha, estación y variable identifica una sola fila."""
    limpia, _ = tablas
    assert not limpia.duplicated(["fecha", "estacion_id", "variable"]).any()


def test_indice_en_rango(tablas):
    """El índice informado queda dentro del intervalo de control físico."""
    _, indice = tablas
    valores = indice.vel_ciudad_ms.dropna()
    assert valores.between(0, 5).all()


def test_cobertura_minima_para_indice(tablas):
    """Un índice calculado cuenta al menos tres estaciones ese día."""
    _, indice = tablas
    assert (indice.loc[indice.vel_ciudad_ms.notna(), "n_estaciones"] >= 3).all()
