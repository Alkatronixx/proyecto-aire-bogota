"""
test_aire.py — Pruebas mínimas sobre data/interim/aire_largo.parquet.

Ejecutar:
  pytest tests/test_aire.py -v -s
"""

from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARQUET_PATH = PROJECT_ROOT / "data" / "interim" / "aire_largo.parquet"


@pytest.fixture(scope="module")
def df():
    """Carga el parquet una sola vez para todos los tests del módulo."""
    if not PARQUET_PATH.exists():
        pytest.skip(f"Parquet no encontrado: {PARQUET_PATH}")
    return pd.read_parquet(PARQUET_PATH)


def test_sin_duplicados(df):
    """No hay duplicados (fecha, estacion_id, contaminante) en el parquet."""
    dup_key = ["fecha", "estacion_id", "contaminante"]
    dups = df[df.duplicated(subset=dup_key, keep=False)]
    if not dups.empty:
        muestra = dups.head(20).to_string(index=False)
        pytest.fail(
            f"Hay {len(dups)} filas duplicadas.\n"
            f"Muestra:\n{muestra}"
        )


def test_fechas_en_rango(df):
    """Las fechas están entre 2023-10-24 y 2026-10-24.

    Reporta las que caigan fuera, pero NO las borra.
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
        print(f"\n⚠ Fechas fuera de rango ({len(fuera)} filas):")
        print(detalle.head(40).to_string(index=False))

        pytest.fail(
            f"Hay {len(fuera)} filas con fechas fuera de rango: "
            f"{fuera['fecha'].min().date()} — {fuera['fecha'].max().date()}"
        )


def test_contaminantes_validos(df):
    """La columna contaminante solo contiene PM10 y PM2.5."""
    validos = {"PM10", "PM2.5"}
    encontrados = set(df["contaminante"].unique())

    inesperados = encontrados - validos
    assert not inesperados, (
        f"Contaminantes inesperados: {inesperados}. Esperados: {validos}"
    )

    faltantes = validos - encontrados
    if faltantes:
        print(f"\nContaminantes esperados no encontrados: {faltantes}")


def test_sin_huecos_fechas(df):
    """No hay huecos en la union de fechas entre 2023-10-24 y 2026-10-23."""
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

        detalle = "\n".join(
            f"  {ini} -- {fi} ({n} dias)" for ini, fi, n in rangos
        )
        pytest.fail(
            f"Hay {len(faltantes)} fechas faltantes en el parquet:\n{detalle}"
        )


def test_sin_archivos_duplicados():
    """No hay dos archivos .xlsx en data/raw/aire/ con contenido identico."""
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
        detalle = "\n".join(
            f"  Hash {h[:16]}: {files}" for h, files in duplicados.items()
        )
        pytest.fail(
            f"Hay archivos con contenido identico:\n{detalle}"
        )
