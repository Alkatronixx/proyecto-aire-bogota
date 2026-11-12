"""Genera la imagen estática de cobertura mensual que consume la aplicación.
Lee la matriz publicada y los nombres de estación de la tabla maestra.
Escribe un PNG de 19 estaciones por mes y comprueba dos píxeles de datos.
Con --actualizar-matriz también recalcula y valida la matriz CSV existente.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MAESTRA = ROOT / "data" / "processed" / "aire_bogota_diario.parquet"
DESTINO = ROOT / "data" / "processed" / "app" / "cobertura_estacion_mes.csv"
IMAGEN = ROOT / "data" / "processed" / "app" / "cobertura_estacion_mes.png"


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


def cargar_matriz_publicada() -> pd.DataFrame:
    """Lee el CSV compacto ya publicado y valida su forma estación-mes."""
    matriz = pd.read_csv(DESTINO).set_index("estacion_id")
    matriz.index = matriz.index.astype(str)
    matriz.columns = matriz.columns.astype(str)
    if matriz.shape != (19, 37):
        raise ValueError(f"La matriz publicada debe ser 19 × 37; llegó {matriz.shape}.")
    return matriz.astype(float)


def generar_imagen(matriz: pd.DataFrame, destino: Path = IMAGEN) -> int:
    """Renderiza la matriz con viridis y confirma que los colores representan los valores."""
    nombres = pd.read_parquet(MAESTRA, columns=["estacion_id", "estacion"])
    nombres = nombres.drop_duplicates("estacion_id").set_index("estacion_id").estacion.to_dict()
    etiquetas = [str(nombres.get(estacion, estacion.replace("_", " ").title())) for estacion in matriz.index]
    meses = matriz.columns.tolist()
    valores = matriz.to_numpy(dtype=float)

    figura, eje = plt.subplots(figsize=(10, 7), dpi=150)
    imagen = eje.imshow(valores, cmap="viridis", vmin=0, vmax=100, aspect="auto", interpolation="nearest")
    eje.set_title("Cobertura de PM2.5 por estación y mes", fontsize=13, pad=35)
    eje.set_xlabel("Año-mes", fontsize=10)
    eje.set_ylabel("Estación", fontsize=10)
    eje.set_yticks(np.arange(len(etiquetas)), labels=etiquetas, fontsize=8)
    marcas = np.arange(0, len(meses), 3)
    eje.set_xticks(marcas, labels=[meses[i] for i in marcas], rotation=45, ha="right", fontsize=8)
    eje.tick_params(axis="both", length=0)
    eje.set_xlim(-.5, len(meses) - .5)

    # La banda abarca los meses afectados; la etiqueta conserva las fechas exactas de la fuente.
    if "2025-08" in meses and "2025-10" in meses:
        inicio, fin = meses.index("2025-08"), meses.index("2025-10")
        eje.axvspan(inicio - .5, fin + .5, color="#303846", alpha=.3, zorder=2)
        eje.text(
            (inicio + fin) / 2, 1.015,
            "Hueco de la fuente\n2025-08-04 a 2025-10-16",
            transform=eje.get_xaxis_transform(), ha="center", va="bottom", fontsize=7.5,
            color="#20242b", bbox={"facecolor": "white", "edgecolor": "#687080", "alpha": .95, "pad": 2},
        )

    barra = figura.colorbar(imagen, ax=eje, pad=.025, fraction=.04)
    barra.set_label("% de días con dato", fontsize=9)
    barra.ax.tick_params(labelsize=8)
    figura.subplots_adjust(left=.20, right=.89, bottom=.17, top=.84)
    figura.savefig(destino, format="png", dpi=150, facecolor="white")

    # Se muestrean celdas fuera de la banda en el PNG ya escrito, no solo en la figura en memoria.
    figura.canvas.draw()
    with Image.open(destino) as archivo_png:
        pixels = np.asarray(archivo_png.convert("RGB"))
    altura = pixels.shape[0]
    muestras = []
    for estacion, mes in ((matriz.index[0], meses[0]), (matriz.index[0], "2024-02")):
        if mes not in meses:
            continue
        fila, columna = matriz.index.get_loc(estacion), meses.index(mes)
        x, y = eje.transData.transform((columna, fila))
        rgb = pixels[altura - 1 - round(y), round(x), :3].astype(float)
        esperado = np.asarray(plt.get_cmap("viridis")(valores[fila, columna])[:3]) * 255
        if not np.allclose(rgb, esperado, atol=2):
            plt.close(figura)
            raise ValueError(f"El píxel de {estacion}/{mes} no corresponde a la matriz CSV.")
        muestras.append(f"{estacion}/{mes}={valores[fila, columna]:.6f}%")
    plt.close(figura)
    print("Celdas reconstruidas en el PNG: " + "; ".join(muestras))
    return destino.stat().st_size


def main() -> None:
    """Genera el PNG desde la matriz publicada; permite regenerar el CSV explícitamente."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actualizar-matriz", action="store_true", help="Recalcula la matriz CSV desde la tabla maestra.")
    argumentos = parser.parse_args()
    if argumentos.actualizar_matriz:
        matriz = calcular_matriz()
        celdas = verificar_matriz_anterior(matriz)
        matriz.rename_axis("estacion_id").to_csv(DESTINO, float_format="%.6f")
        print(f"Matriz: {matriz.shape[0]} × {matriz.shape[1]}; {celdas} celdas verificadas.")
    matriz = cargar_matriz_publicada()
    peso = generar_imagen(matriz)
    print(f"PNG: {IMAGEN} ({peso:,} bytes, 10 × 7 pulgadas, 150 dpi)")

    menores = matriz.stack().rename("pct_dias_pm25").sort_values(kind="stable").head(3)
    print("Tres coberturas menores:")
    for (estacion, mes), valor in menores.items():
        print(f"  {estacion} / {mes}: {valor:.6f}%")


if __name__ == "__main__":
    main()
