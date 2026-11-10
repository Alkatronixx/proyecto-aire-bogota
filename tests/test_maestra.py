"""Pruebas de integridad para la tabla maestra diaria de aire."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "data" / "processed" / "aire_bogota_diario.parquet"
ASIGNACION = ROOT / "data" / "processed" / "asignacion_estaciones.csv"
DICCIONARIO = ROOT / "data" / "docs" / "diccionario_datos.md"
INICIO = pd.Timestamp("2023-10-24")
FIN = pd.Timestamp("2026-10-23")


def _maestra() -> pd.DataFrame:
    """Carga la tabla integrada creada por el script reproducible."""
    return pd.read_parquet(PARQUET)


def test_llave_unica_y_malla_completa():
    """Comprueba la cantidad de filas y continuidad diaria por estación."""
    datos = _maestra()
    calendario = pd.date_range(INICIO, FIN, freq="D")
    assert len(datos) == 20_824
    assert not datos.duplicated(["fecha", "estacion_id"]).any()
    assert datos.estacion_id.nunique() == 19
    for _, grupo in datos.groupby("estacion_id"):
        assert pd.DatetimeIndex(grupo.fecha.sort_values()).equals(calendario)


def test_rangos_y_banderas_de_particulas():
    """Verifica limpieza PM, temperatura, precipitación y viento de ciudad."""
    datos = _maestra()
    assert datos.fecha.min() == INICIO
    assert datos.fecha.max() == FIN
    assert not datos.pm25.lt(0).any()
    assert not datos.pm10.lt(0).any()
    assert not (datos.tmax_c.notna() & datos.tmin_c.notna() & datos.tmax_c.lt(datos.tmin_c)).any()
    assert not datos.precip_mm.lt(0).any()
    assert datos.vel_ciudad_ms.dropna().between(0, 5).all()
    assert datos.pm25_faltante.equals(datos.pm25.isna())


def test_distancias_y_diccionario_completos():
    """Verifica radio de asignación y documentación de todas las columnas."""
    datos = _maestra()
    asignacion = pd.read_csv(ASIGNACION)
    assert asignacion.precip_dist_km.dropna().le(15).all()
    assert asignacion.temp_dist_km.dropna().le(15).all()
    texto = DICCIONARIO.read_text(encoding="utf-8")
    columnas = {line.split("|", 2)[1].strip().strip("`") for line in texto.splitlines() if line.startswith("| `")}
    assert set(datos.columns).issubset(columnas)
