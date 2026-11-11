"""Genera una matriz compacta de cobertura mensual para la aplicación.
Lee fecha, estación y PM2.5 de la tabla maestra procesada.
Escribe una matriz de 19 estaciones por mes en data/processed/app.
Compara celda por celda con la tabla larga previa antes de reemplazarla.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MAESTRA = ROOT / "data" / "processed" / "aire_bogota_diario.parquet"
DESTINO = ROOT / "data" / "processed" / "app" / "cobertura_estacion_mes.csv"


def calcular_matriz() -> pd.DataFrame:
    """Calcula porcentaje observado por estación y mes usando solo datos existentes."""
    aire = pd.read_parquet(MAESTRA, columns=["fecha", "estacion_id", "pm25"])
    aire["fecha"] = pd.to_datetime(aire["fecha"])
    aire["año_mes"] = aire.fecha.dt.to_period("M").astype(str)
    larga = (
        aire.groupby(["estacion_id", "año_mes"], sort=True).pm25
        .apply(lambda valores: 100 * valores.notna().mean())
        .rename("pct_dias_pm25").reset_index()
    )
    matriz = larga.pivot(index="estacion_id", columns="año_mes", values="pct_dias_pm25")
    meses = pd.period_range(aire.fecha.min().to_period("M"), aire.fecha.max().to_period("M"), freq="M").astype(str)
    return matriz.reindex(index=sorted(matriz.index.astype(str)), columns=meses).round(6)


def verificar_matriz_anterior(nueva: pd.DataFrame) -> int:
    """Exige que la matriz nueva coincida con el producto app previo antes de escribir."""
    if not DESTINO.exists():
        return int(nueva.size)
    anterior = pd.read_csv(DESTINO)
    if {"estacion_id", "año_mes", "pct_dias_pm25"}.issubset(anterior.columns):
        anterior["año_mes"] = anterior["año_mes"].astype(str)
        anterior = anterior.pivot(index="estacion_id", columns="año_mes", values="pct_dias_pm25")
    else:
        anterior = anterior.set_index("estacion_id")
        anterior.columns = anterior.columns.astype(str)
    anterior = anterior.reindex(index=nueva.index, columns=nueva.columns)
    iguales = np.isclose(anterior.to_numpy(dtype=float), nueva.to_numpy(dtype=float), rtol=0, atol=1e-6, equal_nan=True)
    if not iguales.all():
        diferencias = int((~iguales).sum())
        raise ValueError(f"La cobertura difiere en {diferencias} celdas; no se reemplaza el archivo.")
    return int(iguales.size)


def main() -> None:
    """Verifica igualdad de cobertura y publica el formato compacto."""
    matriz = calcular_matriz()
    celdas = verificar_matriz_anterior(matriz)
    matriz.rename_axis("estacion_id").to_csv(DESTINO, float_format="%.6f")
    print(f"Matriz guardada: {matriz.shape[0]} estaciones × {matriz.shape[1]} meses; {celdas} celdas coinciden.")
    print(f"Archivo: {DESTINO} ({DESTINO.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
