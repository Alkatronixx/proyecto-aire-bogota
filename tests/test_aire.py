"""
test_aire.py — Pruebas de calidad e integridad sobre data/interim/aire_largo.parquet.

Qué hace:
    Verifica mediante aserciones automatizadas de pytest que la tabla integrada cumpla
    con las reglas de negocio: sin duplicados de clave única, fechas acotadas al periodo
    oficial, únicamente contaminantes válidos (PM10 y PM2.5), serie temporal continua
    sin días faltantes en el calendario y ausencia de archivos crudos idénticos.

Qué lee:
    - Tabla intermedia consolidada: data/interim/aire_largo.parquet
    - Archivos crudos de entrada: data/raw/aire/*.xlsx

Qué produce:
    - Reportes y aserciones en consola mediante el runner pytest.

Cómo se ejecuta:
    pytest tests/test_aire.py -v -s
"""

from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARQUET_PATH = PROJECT_ROOT / "data" / "interim" / "aire_largo.parquet"


@pytest.fixture(scope="module")
def df():
    """Carga el parquet una sola vez para todos los tests del módulo.

    Retorna
    -------
    pd.DataFrame
        DataFrame de aire en formato largo cargado desde data/interim/aire_largo.parquet.
        Si el archivo no existe, omite (skip) los tests que dependen de él.
    """
    if not PARQUET_PATH.exists():
        pytest.skip(f"Parquet no encontrado: {PARQUET_PATH}")
    return pd.read_parquet(PARQUET_PATH)


def test_sin_duplicados(df):
    """Verifica que no existan duplicados para la clave (fecha, estacion_id, contaminante).

    SUPUESTO: Regla de deduplicación: la clave primaria (fecha, estacion_id, contaminante)
    debe ser estrictamente única en el dataset consolidado.
    """
    dup_key = ["fecha", "estacion_id", "contaminante"]
    dups = df[df.duplicated(subset=dup_key, keep=False)]
    if not dups.empty:
        muestra = dups.head(20).to_string(index=False)
        pytest.fail(
            f"Hay {len(dups)} filas duplicadas.\r\n"
            f"Muestra:\r\n{muestra}"
        )


def test_fechas_en_rango(df):
    """Verifica que las fechas se encuentren dentro del rango temporal 2023-10-24 a 2026-10-24.

    SUPUESTO: Periodo oficial definido para el análisis: 2023-10-24 a 2026-10-23 (con margen
    del día 24 para evaluar cierres de archivo). Reporta las fechas fuera de rango si existen.
    """
    fecha_min = pd.Timestamp("2023-10-24")
    fecha_max = pd.Timestamp("2026-10-24")

    fuera = df[(df["fecha"] < fecha_min) | (df["fecha"] > fecha_max)]

    if not fuera.empty:
        detalle = (
            fuera.groupby(["fecha", "estacion", "contaminante"])
            .size()
            .reset_index(name="n")
            .sort_values("fecha")
        )
        print(f"\r\n⚠ Fechas fuera de rango ({len(fuera)} filas):")
        print(detalle.head(40).to_string(index=False))

        pytest.fail(
            f"Hay {len(fuera)} filas con fechas fuera de rango: "
            f"{fuera['fecha'].min().date()} — {fuera['fecha'].max().date()}"
        )


def test_contaminantes_validos(df):
    """Verifica que la columna contaminante contenga única y exclusivamente PM10 y PM2.5.

    Garantiza que no existan contaminantes inesperados, errores tipográficos ni valores espurios.
    """
    validos = {"PM10", "PM2.5"}
    encontrados = set(df["contaminante"].unique())

    inesperados = encontrados - validos
    assert not inesperados, (
        f"Contaminantes inesperados: {inesperados}. Esperados: {validos}"
    )

    faltantes = validos - encontrados
    if faltantes:
        print(f"\r\nContaminantes esperados no encontrados: {faltantes}")


def test_sin_huecos_fechas(df):
    """Valida que no existan fechas faltantes en el calendario continuo entre 2023-10-24 y 2026-10-23.

    SUPUESTO: Continuidad temporal: aunque existan periodos con valores en NaN (como el hueco
    institucional de la RMCAB entre 2025-08-04 y 2025-10-16), todos los 1.096 días calendario
    deben existir como filas indexadas en la unión de fechas del dataset consolidado.
    """
    from datetime import date, timedelta

    fecha_inicio = date(2023, 10, 24)
    fecha_fin = date(2026, 10, 23)

    esperadas = set()
    d = fecha_inicio
    while d <= fecha_fin:
        esperadas.add(d)
        d += timedelta(days=1)

    presentes = set(df["fecha"].dt.date.unique())
    faltantes = sorted(esperadas - presentes)

    if faltantes:
        # Agrupar en rangos continuos
        rangos = []
        inicio = faltantes[0]
        fin = faltantes[0]
        for f in faltantes[1:]:
            if f == fin + timedelta(days=1):
                fin = f
            else:
                rangos.append((inicio, fin, (fin - inicio).days + 1))
                inicio = f
                fin = f
        rangos.append((inicio, fin, (fin - inicio).days + 1))

        detalle = "\r\n".join(
            f"  {ini} -- {fi} ({n} dias)" for ini, fi, n in rangos
        )
        pytest.fail(
            f"Hay {len(faltantes)} fechas faltantes en el parquet:\r\n{detalle}"
        )


def test_sin_archivos_duplicados():
    """Comprueba que no existan dos archivos .xlsx en data/raw/aire/ con contenido binario idéntico.

    Utiliza el hash SHA-256 para corroborar que no se hayan descargado archivos repetidos bajo nombres distintos.
    """
    import hashlib

    raw_dir = PROJECT_ROOT / "data" / "raw" / "aire"
    archivos = sorted(raw_dir.glob("**/*.xlsx"))
    archivos = [a for a in archivos if not a.name.startswith("~")]

    if not archivos:
        pytest.skip("No hay archivos .xlsx en data/raw/aire/")

    hashes: dict[str, list[str]] = {}
    for filepath in archivos:
        h = hashlib.sha256(filepath.read_bytes()).hexdigest()
        hashes.setdefault(h, []).append(filepath.name)

    duplicados = {h: files for h, files in hashes.items() if len(files) > 1}
    if duplicados:
        detalle = "\r\n".join(
            f"  Hash {h[:16]}: {files}" for h, files in duplicados.items()
        )
        pytest.fail(
            f"Hay archivos con contenido identico:\r\n{detalle}"
        )
