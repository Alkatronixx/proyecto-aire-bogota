"""
diagnostico_aire.py -- Diagnostico de solo lectura sobre los datos de aire.

Lee los archivos crudos y el parquet generado para investigar discrepancias.
NO modifica ningun archivo.

Ejecutar:
  python src/datos/diagnostico_aire.py
"""

import re
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
import numpy as np
import openpyxl

# ── Rutas ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "aire"
PARQUET_PATH = PROJECT_ROOT / "data" / "interim" / "aire_largo.parquet"

RE_FECHA = re.compile(r"^(\d{1,2}-\d{1,2}-\d{4})(?:\s+(.+))?$")


def _leer_archivo_crudo(filepath: Path):
    """Lee un archivo Excel SIN deduplicar. Devuelve lista de (fecha, fila_excel, raw_values_dict)."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=False)
    ws = wb[wb.sheetnames[0]]
    max_col = ws.max_column

    # Leer encabezado
    row3 = [ws.cell(row=3, column=c).value for c in range(1, max_col + 1)]
    row4 = [ws.cell(row=4, column=c).value for c in range(1, max_col + 1)]

    # ffill estaciones
    for i in range(2, len(row3)):
        if row3[i] is None:
            row3[i] = row3[i - 1]

    # Construir info de columnas
    columnas = []
    for i in range(1, len(row3)):
        est = row3[i]
        cont = row4[i]
        if est is None or cont is None:
            continue
        columnas.append({
            "col_idx": i + 1,
            "estacion": str(est).strip(),
            "contaminante": str(cont).strip(),
        })

    # Leer TODAS las filas (no filtrar sumario todavia)
    filas = []
    for r in range(6, ws.max_row + 1):
        a_val = ws.cell(row=r, column=1).value
        if a_val is None:
            continue
        a_str = str(a_val).strip()
        match = RE_FECHA.match(a_str)
        if not match:
            continue  # no es fecha

        date_str = match.group(1)
        try:
            fecha = pd.to_datetime(date_str, dayfirst=True).normalize().date()
        except Exception:
            continue

        # Leer valores crudos
        vals = {}
        for ci in columnas:
            v = ws.cell(row=r, column=ci["col_idx"]).value
            vals[(ci["estacion"], ci["contaminante"])] = v
        filas.append({"fecha": fecha, "fila_excel": r, "valores": vals})

    wb.close()
    return filas, columnas


def _agrupar_rangos(fechas_sorted):
    """Agrupa una lista de dates ordenadas en rangos contiguos."""
    if not fechas_sorted:
        return []
    rangos = []
    inicio = fechas_sorted[0]
    fin = fechas_sorted[0]
    for f in fechas_sorted[1:]:
        if f == fin + timedelta(days=1):
            fin = f
        else:
            rangos.append((inicio, fin))
            inicio = f
            fin = f
    rangos.append((inicio, fin))
    return rangos


def main():
    print("=" * 70)
    print("DIAGNOSTICO DE DATOS DE AIRE")
    print("=" * 70)

    archivos = sorted(RAW_DIR.glob("**/*.xlsx"))
    archivos = [a for a in archivos if not a.name.startswith("~")]

    # ================================================================
    # 1. Por archivo crudo: filas, rango, fechas repetidas
    # ================================================================
    print("\n" + "=" * 70)
    print("1. DETALLE POR ARCHIVO CRUDO (sin deduplicar)")
    print("=" * 70)

    todas_fechas_por_archivo = {}  # nombre -> lista de fechas (con repeticiones)
    datos_por_archivo = {}  # nombre -> lista de filas crudas

    for filepath in archivos:
        nombre = filepath.name
        filas, columnas = _leer_archivo_crudo(filepath)
        fechas = [f["fecha"] for f in filas]
        todas_fechas_por_archivo[nombre] = fechas
        datos_por_archivo[nombre] = filas

        # Contar repetidas
        conteo = defaultdict(int)
        for f in fechas:
            conteo[f] += 1
        repetidas = {f: c for f, c in conteo.items() if c > 1}

        primera = min(fechas) if fechas else None
        ultima = max(fechas) if fechas else None

        print(f"\n  {nombre}")
        print(f"    Filas de datos: {len(filas)}")
        print(f"    Rango: {primera} -- {ultima}")
        if repetidas:
            print(f"    Fechas repetidas ({len(repetidas)}):")
            for f in sorted(repetidas):
                print(f"      {f} x{repetidas[f]}")
        else:
            print(f"    Fechas repetidas: ninguna")

    # ================================================================
    # 2. Fechas faltantes en el parquet
    # ================================================================
    print("\n" + "=" * 70)
    print("2. FECHAS FALTANTES EN aire_largo.parquet")
    print("=" * 70)

    df = pd.read_parquet(PARQUET_PATH)
    df["fecha"] = pd.to_datetime(df["fecha"])

    fecha_inicio = date(2023, 10, 24)
    fecha_fin = date(2026, 10, 23)
    todas_esperadas = set()
    d = fecha_inicio
    while d <= fecha_fin:
        todas_esperadas.add(d)
        d += timedelta(days=1)

    fechas_en_parquet = set(df["fecha"].dt.date.unique())
    faltantes = sorted(todas_esperadas - fechas_en_parquet)

    print(f"\n  Dias esperados: {len(todas_esperadas)}")
    print(f"  Dias en parquet: {len(fechas_en_parquet)}")
    print(f"  Dias faltantes: {len(faltantes)}")

    if faltantes:
        rangos = _agrupar_rangos(faltantes)
        print(f"  Rangos faltantes ({len(rangos)}):")

        # Para cada rango, buscar que archivo deberia cubrirlo
        for inicio, fin in rangos:
            n_dias = (fin - inicio).days + 1
            # Buscar archivos que cubren este rango
            archivos_cubren = []
            for nombre, fechas in todas_fechas_por_archivo.items():
                if fechas:
                    f_min = min(fechas)
                    f_max = max(fechas)
                    if f_min <= inicio and f_max >= fin:
                        archivos_cubren.append((nombre, len(fechas)))
                    elif f_min <= fin and f_max >= inicio:  # overlap parcial
                        archivos_cubren.append((nombre, len(fechas)))

            print(f"    {inicio} -- {fin}  ({n_dias} dias)")
            if archivos_cubren:
                for nombre, n_filas in archivos_cubren:
                    print(f"      Archivo candidato: {nombre} ({n_filas} filas datos)")
            else:
                print(f"      Sin archivo candidato encontrado")

    # ================================================================
    # 3. Fechas donde TODAS las estaciones son NaN
    # ================================================================
    print("\n" + "=" * 70)
    print("3. FECHAS DONDE TODAS LAS ESTACIONES SON NaN")
    print("=" * 70)

    for cont in ["PM2.5", "PM10"]:
        sub = df[df["contaminante"] == cont]
        pivot = sub.pivot_table(index="fecha", columns="estacion_id",
                                values="valor", aggfunc="first")
        # Fechas donde TODAS las columnas son NaN
        todas_nan = pivot[pivot.isna().all(axis=1)].index
        fechas_nan = sorted([f.date() for f in todas_nan])

        print(f"\n  {cont}: {len(fechas_nan)} fechas con todas las estaciones NaN")
        if fechas_nan:
            rangos = _agrupar_rangos(fechas_nan)
            for inicio, fin in rangos:
                n = (fin - inicio).days + 1
                print(f"    {inicio} -- {fin}  ({n} dias)")

    # ================================================================
    # 4. Grupos con dos valores NUMERICOS distintos
    # ================================================================
    print("\n" + "=" * 70)
    print("4. DUPLICADOS CON DOS VALORES NUMERICOS DISTINTOS (esperado: 0)")
    print("=" * 70)

    # Necesitamos volver a los datos crudos antes de deduplicar
    # Reconstruir todos los registros en formato largo sin deduplicar
    registros = []
    for nombre, filas in datos_por_archivo.items():
        for fila in filas:
            fecha = fila["fecha"]
            for (est, cont), val in fila["valores"].items():
                registros.append({
                    "fecha": fecha,
                    "estacion": est,
                    "contaminante": cont,
                    "valor_raw": val,
                    "archivo": nombre,
                    "fila_excel": fila["fila_excel"],
                })

    df_raw = pd.DataFrame(registros)
    df_raw["valor_num"] = pd.to_numeric(df_raw["valor_raw"], errors="coerce")

    # Buscar grupos con >1 valor numerico distinto
    key_cols = ["fecha", "estacion", "contaminante"]
    conflictos = []

    for key, group in df_raw.groupby(key_cols):
        nums = group["valor_num"].dropna()
        if len(nums) >= 2:
            unicos = nums.unique()
            if len(unicos) > 1:
                conflictos.append({
                    "fecha": key[0],
                    "estacion": key[1],
                    "contaminante": key[2],
                    "valores": sorted(unicos.tolist()),
                    "archivos": group["archivo"].tolist(),
                    "filas": group["fila_excel"].tolist(),
                })

    print(f"\n  Grupos con 2+ valores numericos distintos: {len(conflictos)}")
    if conflictos:
        print(f"  Primeros {min(20, len(conflictos))}:")
        for c in conflictos[:20]:
            print(f"    {c['fecha']} / {c['estacion']} / {c['contaminante']}")
            print(f"      valores={c['valores']}, archivos={c['archivos']}, filas_excel={c['filas']}")

    # ================================================================
    # 5. Patron "fila con datos + fila NaN con la misma fecha"
    # ================================================================
    print("\n" + "=" * 70)
    print("5. PATRON: FILA CON DATOS + FILA NaN EN LA MISMA FECHA")
    print("=" * 70)

    # Agrupar por archivo y fecha
    patron_por_archivo = defaultdict(list)

    for nombre, filas in datos_por_archivo.items():
        # Agrupar filas por fecha
        por_fecha = defaultdict(list)
        for fila in filas:
            por_fecha[fila["fecha"]].append(fila)

        for fecha, grupo in sorted(por_fecha.items()):
            if len(grupo) < 2:
                continue
            # Revisar si una fila tiene datos y otra es todo NaN/----
            for i, f1 in enumerate(grupo):
                for f2 in grupo[i + 1:]:
                    # Contar cuantas columnas tienen valor numerico en cada fila
                    def _count_numeric(vals):
                        n = 0
                        for v in vals.values():
                            if isinstance(v, (int, float)) and not isinstance(v, bool):
                                n += 1
                        return n

                    n1 = _count_numeric(f1["valores"])
                    n2 = _count_numeric(f2["valores"])
                    # Patron: una tiene datos, la otra no
                    if (n1 > 0 and n2 == 0) or (n1 == 0 and n2 > 0):
                        patron_por_archivo[nombre].append({
                            "fecha": fecha,
                            "fila_datos": f1["fila_excel"] if n1 > 0 else f2["fila_excel"],
                            "fila_nan": f2["fila_excel"] if n1 > 0 else f1["fila_excel"],
                            "n_datos": max(n1, n2),
                        })

    total_patron = sum(len(v) for v in patron_por_archivo.values())
    print(f"\n  Archivos con este patron: {len(patron_por_archivo)}")
    print(f"  Total ocurrencias: {total_patron}")

    for nombre in sorted(patron_por_archivo):
        ocurrencias = patron_por_archivo[nombre]
        print(f"\n  {nombre} ({len(ocurrencias)} fecha(s)):")
        for occ in ocurrencias:
            print(f"    {occ['fecha']}  fila_datos={occ['fila_datos']}  "
                  f"fila_nan={occ['fila_nan']}  cols_con_dato={occ['n_datos']}/38")

    # Tambien reportar archivos con fechas repetidas que NO siguen este patron
    print(f"\n  --- Fechas repetidas que NO siguen el patron datos+NaN ---")
    otros_repetidos = 0
    for nombre, filas in datos_por_archivo.items():
        por_fecha = defaultdict(list)
        for fila in filas:
            por_fecha[fila["fecha"]].append(fila)

        for fecha, grupo in sorted(por_fecha.items()):
            if len(grupo) < 2:
                continue
            # Verificar si esta en el patron datos+NaN
            es_patron = any(
                p["fecha"] == fecha for p in patron_por_archivo.get(nombre, [])
            )
            if not es_patron:
                def _count_numeric(vals):
                    return sum(1 for v in vals.values()
                               if isinstance(v, (int, float)) and not isinstance(v, bool))
                nums = [_count_numeric(f["valores"]) for f in grupo]
                print(f"  {nombre}: {fecha} x{len(grupo)} "
                      f"(cols numericas por fila: {nums})")
                otros_repetidos += 1

    if otros_repetidos == 0:
        print(f"  (ninguno)")

    # ================================================================
    # 6. PM2.5 > PM10 en la misma estacion y fecha
    # ================================================================
    print("\n" + "=" * 70)
    print("6. PM2.5 > PM10 EN LA MISMA ESTACION Y FECHA")
    print("=" * 70)

    pm25 = df[df["contaminante"] == "PM2.5"][["fecha", "estacion_id", "estacion", "valor"]].rename(
        columns={"valor": "pm25"})
    pm10 = df[df["contaminante"] == "PM10"][["fecha", "estacion_id", "valor"]].rename(
        columns={"valor": "pm10"})
    merged = pm25.merge(pm10, on=["fecha", "estacion_id"], how="inner")
    # Solo donde ambos son no-NaN
    merged = merged.dropna(subset=["pm25", "pm10"])
    invertidos = merged[merged["pm25"] > merged["pm10"]]

    print(f"\n  Pares (fecha, estacion) con ambos valores no-NaN: {len(merged)}")
    print(f"  De esos, PM2.5 > PM10: {len(invertidos)} ({len(invertidos)/len(merged)*100:.1f}%)")

    if not invertidos.empty:
        print(f"\n  Por estacion:")
        conteo_est = invertidos.groupby("estacion").size().sort_values(ascending=False)
        for est, n in conteo_est.items():
            total_est = len(merged[merged["estacion"] == est])
            print(f"    {est:30s}  {n:4d} / {total_est:4d}  ({n/total_est*100:.1f}%)")

        print(f"\n  Muestra (primeras 15 filas):")
        muestra = invertidos.sort_values("fecha").head(15)
        for _, row in muestra.iterrows():
            diff = row["pm25"] - row["pm10"]
            print(f"    {row['fecha'].date()} / {row['estacion']:25s}  "
                  f"PM2.5={row['pm25']:6.1f}  PM10={row['pm10']:6.1f}  "
                  f"diff={diff:+.1f}")

    print(f"\n{'=' * 70}")
    print("FIN DEL DIAGNOSTICO")
    print("=" * 70)


if __name__ == "__main__":
    main()
