"""
limpiar_aire.py — Limpieza de datos de calidad del aire (PM10, PM2.5) de la RMCAB.

Lee todos los .xlsx de data/raw/aire/, construye un DataFrame largo y guarda:
  - data/interim/aire_largo.parquet
  - data/processed/cobertura_aire.csv

Ejecutar:
  python src/datos/limpiar_aire.py
"""

import re
import unicodedata
import calendar
import hashlib
import json
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import openpyxl

# ── Constantes ─────────────────────────────────────────────────────────────────

# "24:00" en los datos crudos representa el promedio de cierre de ese mismo
# día calendario.  NO se suma un día.  Constante documentada para referencia.
HORA_CIERRE_DOC = (
    "24:00 se interpreta como el cierre del mismo día calendario, "
    "no como la medianoche del día siguiente."
)

# Patrón para extraer la porción de fecha de cadenas como "24-10-2023 24:00".
RE_FECHA = re.compile(
    r"^(\d{1,2}-\d{1,2}-\d{4})(?:\s+(.+))?$"
)

# Etiquetas que identifican las filas de resumen al final de cada hoja.
SUMMARY_LABELS = {
    "MaxTime", "Avg", "Num", "DataPrecent", "STD",
    "Summary:", "Minimum", "MinDate", "MinTime", "Maximum", "MaxDate",
}

# ── Rutas ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "aire"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
GEO_PATH = (
    PROJECT_ROOT / "data" / "raw" / "geografia" / "estacion_calida_aire.geojson"
)


# ── Funciones auxiliares ───────────────────────────────────────────────────────


def normalizar_id(nombre: str) -> str:
    """Convierte un nombre de estación a snake_case sin tildes.

    Ejemplo: "Centro de Alto Rendimiento" -> "centro_de_alto_rendimiento"
    """
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    resultado = sin_tildes.lower().strip()
    resultado = re.sub(r"[\s\-]+", "_", resultado)
    resultado = re.sub(r"[^a-z0-9_]", "", resultado)
    return resultado


def _leer_encabezado(ws):
    """Lee las filas 3-5 del encabezado y devuelve la lista de columnas.

    Retorna
    -------
    columnas : list[dict] | None
        Cada dict tiene: col_idx (1-based), estacion, contaminante, unidad.
    error : str | None
        Mensaje de error si la estructura no es válida.
    """
    max_col = ws.max_column

    # Fila 3: nombres de estación (celdas combinadas → ffill a la derecha)
    row3 = [ws.cell(row=3, column=c).value for c in range(1, max_col + 1)]
    # Fila 4: contaminante (PM10 / PM2.5)
    row4 = [ws.cell(row=4, column=c).value for c in range(1, max_col + 1)]
    # Fila 5: unidad (µg/m3)
    row5 = [ws.cell(row=5, column=c).value for c in range(1, max_col + 1)]

    # Verificar que A3 sea "DateTime"
    a3 = str(row3[0]).strip() if row3[0] is not None else ""
    if a3 != "DateTime":
        return None, f"A3 != 'DateTime', encontré {row3[0]!r}"

    # Propagar nombres de estación hacia la derecha (ffill)
    for i in range(2, len(row3)):
        if row3[i] is None:
            row3[i] = row3[i - 1]

    # Construir info de columnas (saltar col A = DateTime)
    columnas = []
    for i in range(1, len(row3)):
        estacion = row3[i]
        contaminante = row4[i]
        unidad = row5[i]

        if estacion is None or contaminante is None:
            continue

        estacion = str(estacion).strip()
        contaminante = str(contaminante).strip()
        unidad = str(unidad).strip() if unidad else ""

        columnas.append(
            {
                "col_idx": i + 1,           # índice 1-based en la hoja
                "estacion": estacion,
                "contaminante": contaminante,
                "unidad": unidad,
            }
        )

    if not columnas:
        return None, "No se encontraron columnas de datos en filas 3-5."

    return columnas, None


def _leer_archivo(filepath: Path, ref_header):
    """Lee un archivo Excel y devuelve (df_largo, header, advertencias).

    Parameters
    ----------
    filepath : Path
        Ruta al archivo .xlsx.
    ref_header : list[dict] | None
        Encabezado de referencia del primer archivo leído.  Si es None,
        este archivo se usa como referencia.

    Returns
    -------
    df : pd.DataFrame | None
        DataFrame en formato largo, o None si el archivo fue descartado.
    header : list[dict] | None
        Encabezado parseado del archivo.
    warnings : list[str]
        Lista de advertencias generadas.
    """
    warnings: list[str] = []
    nombre = filepath.name

    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=False)
    ws = wb[wb.sheetnames[0]]

    # ── Encabezado ──
    columnas, error = _leer_encabezado(ws)
    if error:
        wb.close()
        return None, None, [f"SALTADO {nombre}: {error}"]

    # ── Validación estructural contra referencia ──
    if ref_header is not None:
        ref_sig = [(c["estacion"], c["contaminante"]) for c in ref_header]
        cur_sig = [(c["estacion"], c["contaminante"]) for c in columnas]
        if ref_sig != cur_sig:
            diff = set(ref_sig).symmetric_difference(set(cur_sig))
            warnings.append(
                f"SALTADO {nombre}: estructura difiere del archivo de "
                f"referencia. Diferencias: {diff}"
            )
            wb.close()
            return None, columnas, warnings

    # ── Leer filas de datos y fila Num ──
    data_rows: list[dict] = []
    num_values: dict[int, int | None] = {}
    horas_encontradas: set[str] = set()

    for r in range(6, ws.max_row + 1):
        a_val = ws.cell(row=r, column=1).value
        if a_val is None:
            continue

        a_str = str(a_val).strip()

        # Fila Num → para validación cruzada
        if a_str == "Num":
            for ci in columnas:
                v = ws.cell(row=r, column=ci["col_idx"]).value
                try:
                    num_values[ci["col_idx"]] = int(float(str(v)))
                except (ValueError, TypeError):
                    num_values[ci["col_idx"]] = None
            continue

        # Otras filas de resumen → descartar
        if a_str in SUMMARY_LABELS:
            continue

        # Intentar extraer fecha
        match = RE_FECHA.match(a_str)
        if not match:
            warnings.append(f"  Fila {r} no coincide con patrón de fecha: {a_str!r}")
            continue

        date_str = match.group(1)
        time_part = match.group(2)  # puede ser None, "24:00", u otra cosa

        if time_part is not None:
            horas_encontradas.add(time_part.strip())

        try:
            fecha = pd.to_datetime(date_str, dayfirst=True).normalize()
        except Exception as e:
            warnings.append(f"  Fila {r} fecha no parseable: {date_str!r} → {e}")
            continue

        row_dict: dict = {"fecha": fecha}
        for ci in columnas:
            row_dict[ci["col_idx"]] = ws.cell(row=r, column=ci["col_idx"]).value
        data_rows.append(row_dict)

    wb.close()

    # Reportar horas encontradas
    if horas_encontradas:
        warnings.append(
            f"  Fechas traen hora: {sorted(horas_encontradas)} "
            f"→ normalizado a fecha (día). ({HORA_CIERRE_DOC})"
        )

    if not data_rows:
        warnings.append(f"  Sin filas de datos en {nombre}")
        return None, columnas, warnings

    # ── Validación cruzada con fila Num ──
    for ci in columnas:
        col_idx = ci["col_idx"]
        n_numeric = sum(
            1
            for row in data_rows
            if (
                isinstance(row.get(col_idx), (int, float))
                and not isinstance(row.get(col_idx), bool)
            )
        )
        n_expected = num_values.get(col_idx)
        if n_expected is not None and n_numeric != n_expected:
            warnings.append(
                f"  Validacion Num: {ci['estacion']} {ci['contaminante']} -- "
                f"parseados={n_numeric}, Num={n_expected}"
            )

    # ── Construir filas en formato largo ──
    long_rows = []
    for row_dict in data_rows:
        fecha = row_dict["fecha"]
        for ci in columnas:
            long_rows.append(
                {
                    "fecha": fecha,
                    "estacion": ci["estacion"],
                    "contaminante": ci["contaminante"],
                    "valor": row_dict.get(ci["col_idx"]),
                    "archivo_origen": nombre,
                }
            )

    df = pd.DataFrame(long_rows)
    return df, columnas, warnings


def _convertir_valores(df: pd.DataFrame):
    """Convierte la columna valor a numérico; reporta textos no numéricos.

    Retorna
    -------
    df : pd.DataFrame  (modificado in-place y también retornado)
    textos : dict[str, int]  texto → conteo
    """
    # Encontrar valores que son cadenas antes de la conversión
    mask_str = df["valor"].apply(lambda x: isinstance(x, str))
    textos: dict[str, int] = {}
    if mask_str.any():
        textos = df.loc[mask_str, "valor"].value_counts().to_dict()

    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df, textos


def _resolver_duplicados(df: pd.DataFrame):
    """Maneja duplicados (fecha, estación, contaminante) en límites de mes.

    - Idénticos: elimina uno.
    - Conflictivos: conserva el primero y los lista.
    """
    dup_key = ["fecha", "estacion", "contaminante"]
    mask_dup = df.duplicated(subset=dup_key, keep=False)
    duplicados = df[mask_dup]

    identicos_eliminados = 0
    conflictivos: list[dict] = []
    indices_a_borrar: list = []

    if not duplicados.empty:
        for _key, group in duplicados.groupby(dup_key):
            if group["valor"].nunique(dropna=False) <= 1:
                # Valores idénticos (o todos NaN) → conservar el primero
                indices_a_borrar.extend(group.index[1:].tolist())
                identicos_eliminados += len(group) - 1
            else:
                # Valores conflictivos → conservar el primero, reportar
                conflictivos.append(
                    {
                        "fecha": group["fecha"].iloc[0],
                        "estacion": group["estacion"].iloc[0],
                        "contaminante": group["contaminante"].iloc[0],
                        "valores": group["valor"].tolist(),
                        "archivos": group["archivo_origen"].tolist(),
                    }
                )
                indices_a_borrar.extend(group.index[1:].tolist())

        df = df.drop(index=indices_a_borrar).reset_index(drop=True)

    return df, identicos_eliminados, conflictivos


def _leer_geojson():
    """Lee el GeoJSON de estaciones corrigiendo posibles problemas de encoding.

    Retorna (nombres, encoding_usado).
    """
    raw_bytes = GEO_PATH.read_bytes()

    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            text = raw_bytes.decode(enc)
            gj = json.loads(text)
            nombres = [
                feat["properties"].get("estacion", "").strip()
                for feat in gj["features"]
            ]
            # Si utf-8 decodifica sin reemplazo, verificar que no haya U+FFFD
            if "\ufffd" not in text:
                return nombres, enc
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

    # Fallback: utf-8 con reemplazo
    text = raw_bytes.decode("utf-8", errors="replace")
    gj = json.loads(text)
    nombres = [
        feat["properties"].get("estacion", "").strip()
        for feat in gj["features"]
    ]
    return nombres, "utf-8 (con reemplazo)"


def _generar_cobertura(df: pd.DataFrame) -> pd.DataFrame:
    """Genera tabla de cobertura: una fila por estación, contaminante y año-mes."""
    df_tmp = df.copy()
    df_tmp["anio_mes"] = df_tmp["fecha"].dt.to_period("M")

    cob = (
        df_tmp.groupby(["estacion", "estacion_id", "contaminante", "anio_mes"])
        .agg(n_dias_con_dato=("valor", "count"))     # count ignora NaN
        .reset_index()
    )

    cob["n_dias_del_mes"] = cob["anio_mes"].apply(
        lambda p: calendar.monthrange(p.year, p.month)[1]
    )
    cob["porcentaje"] = (
        cob["n_dias_con_dato"] / cob["n_dias_del_mes"] * 100
    ).round(1)
    cob["anio_mes"] = cob["anio_mes"].astype(str)

    return cob


# ── Validacion de integridad de archivos ───────────────────────────────────────


# Mapa de abreviatura de mes en nombre de archivo -> numero de mes
_MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


def _extraer_mes_inicio_nombre(nombre: str):
    """Extrae el mes inicial del nombre de archivo (ej. '24 oct - 24 nov 2023.xlsx' -> 10)."""
    # Patron: '24 <mes> - 24 <mes> <anio>.xlsx' o '24 <mes> <anio> - 24 <mes> <anio>.xlsx'
    m = re.match(r"24\s+(\w+)", nombre.lower())
    if m:
        return _MESES.get(m.group(1))
    return None


def _validar_integridad_archivos(archivos: list[Path]):
    """Valida integridad de archivos crudos antes de procesarlos.

    Reporta (sin abortar):
      a) Primera y ultima fecha con datos numericos, dias unicos.
      b) Si la primera fecha cae en dia 24 y su mes coincide con el nombre.
      c) Si comparte mas de 2 fechas con otro archivo.
      d) Hashes identicos entre archivos.
    """
    print("\n" + "=" * 70)
    print("VALIDACION DE INTEGRIDAD DE ARCHIVOS")
    print("=" * 70)

    info_archivos: list[dict] = []
    inconsistencias: list[str] = []

    for filepath in archivos:
        nombre = filepath.name
        # Hash del contenido
        contenido = filepath.read_bytes()
        file_hash = hashlib.sha256(contenido).hexdigest()[:16]

        wb = openpyxl.load_workbook(filepath, data_only=True, read_only=False)
        ws = wb[wb.sheetnames[0]]
        max_col = ws.max_column

        # Leer fechas y contar columnas numericas por fila
        fechas_unicas: set = set()
        primera_num = None
        ultima_num = None

        for r in range(6, ws.max_row + 1):
            a_val = ws.cell(row=r, column=1).value
            if a_val is None:
                continue
            a_str = str(a_val).strip()
            if a_str in SUMMARY_LABELS:
                continue
            match = RE_FECHA.match(a_str)
            if not match:
                continue

            date_str = match.group(1)
            try:
                fecha = pd.to_datetime(date_str, dayfirst=True).normalize().date()
            except Exception:
                continue

            fechas_unicas.add(fecha)

            # Contar columnas numericas
            n_num = 0
            for c in range(2, max_col + 1):
                v = ws.cell(row=r, column=c).value
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    n_num += 1

            if n_num > 0:
                if primera_num is None:
                    primera_num = fecha
                ultima_num = fecha

        wb.close()

        fechas_sorted = sorted(fechas_unicas)
        n_dias = len(fechas_sorted)

        info = {
            "nombre": nombre,
            "hash": file_hash,
            "fechas": fechas_unicas,
            "n_dias": n_dias,
            "primera": fechas_sorted[0] if fechas_sorted else None,
            "ultima": fechas_sorted[-1] if fechas_sorted else None,
            "primera_num": primera_num,
            "ultima_num": ultima_num,
        }
        info_archivos.append(info)

        # Imprimir detalle
        print(f"\n  {nombre}")
        print(f"    Dias unicos: {n_dias}  "
              f"Rango: {info['primera']} -- {info['ultima']}")
        print(f"    Primer dia con datos num: {primera_num}  "
              f"Ultimo dia con datos num: {ultima_num}")
        print(f"    Hash: {file_hash}")

        # (b) Verificar dia 24 y mes coincide con nombre
        if info["primera"] is not None:
            mes_nombre = _extraer_mes_inicio_nombre(nombre)
            dia_primera = info["primera"].day
            mes_primera = info["primera"].month

            if dia_primera != 24:
                msg = (f"{nombre}: primera fecha es dia {dia_primera}, "
                       f"no dia 24.")
                inconsistencias.append(msg)
                print(f"    [!] {msg}")

            if mes_nombre is not None and mes_primera != mes_nombre:
                msg = (f"{nombre}: mes de primera fecha ({mes_primera}) "
                       f"no coincide con mes del nombre ({mes_nombre}).")
                inconsistencias.append(msg)
                print(f"    [!] {msg}")

    # (c) Fechas compartidas entre archivos (mas de 2)
    print(f"\n--- Fechas compartidas entre archivos ---")
    hay_compartidas = False
    for i, a in enumerate(info_archivos):
        for j, b in enumerate(info_archivos):
            if j <= i:
                continue
            compartidas = a["fechas"] & b["fechas"]
            if len(compartidas) > 2:
                msg = (f"{a['nombre']} y {b['nombre']} comparten "
                       f"{len(compartidas)} fechas "
                       f"(max esperado: 2).")
                inconsistencias.append(msg)
                print(f"  [!] {msg}")
                hay_compartidas = True
    if not hay_compartidas:
        print("  Ninguna pareja comparte mas de 2 fechas.")

    # (d) Hashes identicos
    print(f"\n--- Hashes de contenido ---")
    hash_to_files: dict[str, list[str]] = defaultdict(list)
    for info in info_archivos:
        hash_to_files[info["hash"]].append(info["nombre"])

    hay_duplicados_hash = False
    for h, files in hash_to_files.items():
        if len(files) > 1:
            msg = (f"Archivos con contenido identico (hash {h}): "
                   f"{files}")
            inconsistencias.append(msg)
            print(f"  [!] {msg}")
            hay_duplicados_hash = True
    if not hay_duplicados_hash:
        print("  Todos los archivos tienen hash unico.")

    # Bloque final de inconsistencias
    print(f"\n{'=' * 70}")
    if inconsistencias:
        print(f"INCONSISTENCIAS ({len(inconsistencias)}):")
        for inc in inconsistencias:
            print(f"  - {inc}")
    else:
        print("INCONSISTENCIAS: ninguna")
    print("=" * 70)

    return info_archivos


# ── Funcion principal ──────────────────────────────────────────────────────────


def main():
    """Ejecuta la limpieza completa de datos de aire."""
    print("=" * 70)
    print("LIMPIEZA DE DATOS DE AIRE — RMCAB")
    print("=" * 70)

    # ── 1. Buscar archivos ──
    archivos = sorted(RAW_DIR.glob("**/*.xlsx"))
    archivos = [a for a in archivos if not a.name.startswith("~")]
    print(f"\nArchivos .xlsx encontrados: {len(archivos)}")

    if not archivos:
        print(f"ERROR: No se encontraron archivos .xlsx en {RAW_DIR}")
        return

    # ── 1b. Validar integridad de archivos ──
    _validar_integridad_archivos(archivos)

    # ── 2. Leer archivos ──
    all_dfs: list[pd.DataFrame] = []
    all_warnings: list[tuple[str, str]] = []
    ref_header = None
    archivos_leidos: list[str] = []
    archivos_saltados: list[str] = []

    for filepath in archivos:
        df_file, header, warns = _leer_archivo(filepath, ref_header)
        all_warnings.extend([(filepath.name, w) for w in warns])

        if df_file is not None and not df_file.empty:
            all_dfs.append(df_file)
            archivos_leidos.append(filepath.name)
            if ref_header is None:
                ref_header = header
        else:
            if any("SALTADO" in w for w in warns):
                archivos_saltados.append(filepath.name)

    if not all_dfs:
        print("ERROR: No se pudieron leer datos de ningún archivo.")
        return

    # ── 3. Concatenar ──
    df = pd.concat(all_dfs, ignore_index=True)
    filas_pre_dedup = len(df)
    print(f"Filas totales (antes de dedup): {filas_pre_dedup}")

    # ── 4. Convertir valores a numérico ──
    df, textos_no_numericos = _convertir_valores(df)

    # ── 5. Resolver duplicados ──
    df, n_identicos, conflictivos = _resolver_duplicados(df)

    # ── 6. Crear estacion_id ──
    df["estacion_id"] = df["estacion"].apply(normalizar_id)

    # ── 7. Asegurar tipo datetime ──
    df["fecha"] = pd.to_datetime(df["fecha"])

    # ── 8. Guardar parquet ──
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    parquet_path = INTERIM_DIR / "aire_largo.parquet"
    df.to_parquet(parquet_path, index=False, engine="pyarrow")

    # ── 9. Cobertura ──
    cob = _generar_cobertura(df)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    cob_path = PROCESSED_DIR / "cobertura_aire.csv"
    cob.to_csv(cob_path, index=False)

    # ── 10. Comparación con GeoJSON ──
    geo_nombres, geo_enc = _leer_geojson()
    geo_map = {normalizar_id(n): n for n in geo_nombres}   # id → original
    aire_map = dict(
        zip(df["estacion_id"], df["estacion"])
    )  # id → original (último visto)
    # Reconstruir con drop_duplicates para obtener un mapeo limpio
    aire_map = (
        df[["estacion_id", "estacion"]]
        .drop_duplicates(subset="estacion_id")
        .set_index("estacion_id")["estacion"]
        .to_dict()
    )

    geo_ids = set(geo_map.keys())
    aire_ids = set(aire_map.keys())

    coinciden = sorted(geo_ids & aire_ids)
    solo_aire = sorted(aire_ids - geo_ids)
    solo_geo = sorted(geo_ids - aire_ids)

    # ====================================================================
    #                          R E S U M E N
    # ====================================================================
    print("\n" + "=" * 70)
    print("R E S U M E N")
    print("=" * 70)

    # Archivos
    print(f"\nArchivos leidos exitosamente : {len(archivos_leidos)}")
    print(f"Archivos saltados            : {len(archivos_saltados)}")
    for a in archivos_saltados:
        print(f"  X {a}")

    # Rango de fechas
    print(f"\nRango de fechas: {df['fecha'].min().date()} -- {df['fecha'].max().date()}")

    # Estaciones y contaminantes
    estaciones = sorted(df["estacion"].unique())
    contaminantes = sorted(df["contaminante"].unique())
    print(f"Estaciones ({len(estaciones)}): {estaciones}")
    print(f"Contaminantes: {contaminantes}")
    print(f"Filas totales (despues de dedup): {len(df)}")

    # % faltantes por estacion
    print(f"\n--- % Valores faltantes por estacion ---")
    for est in estaciones:
        mask = df["estacion"] == est
        total = mask.sum()
        faltantes = df.loc[mask, "valor"].isna().sum()
        pct = faltantes / total * 100 if total > 0 else 0
        print(f"  {est:30s}  {faltantes:5d}/{total:5d}  ({pct:5.1f}%)")

    # Punto 4 - Fechas con hora
    print(f"\n--- Fechas con hora ---")
    print(f"  Todas las fechas traian '24:00' -> normalizado a fecha (dia).")
    print(f"  {HORA_CIERRE_DOC}")

    # Punto 5 - Textos no numericos
    print(f"\n--- Textos no numericos -> NaN ---")
    if textos_no_numericos:
        for txt, cnt in sorted(textos_no_numericos.items(), key=lambda x: -x[1]):
            print(f"  '{txt}': {cnt}")
    else:
        print("  (ninguno)")

    n_nan_total = df["valor"].isna().sum()
    print(f"  Total valores NaN: {n_nan_total} / {len(df)} "
          f"({n_nan_total / len(df) * 100:.1f}%)")

    # Negativos y > 1000
    print(f"\n--- Valores negativos por estacion ---")
    hay_neg = False
    for est in estaciones:
        n_neg = ((df["estacion"] == est) & (df["valor"] < 0)).sum()
        if n_neg > 0:
            print(f"  {est}: {n_neg}")
            hay_neg = True
    if not hay_neg:
        print("  (ninguno)")

    print(f"\n--- Valores > 1000 por estacion ---")
    hay_alt = False
    for est in estaciones:
        n_high = ((df["estacion"] == est) & (df["valor"] > 1000)).sum()
        if n_high > 0:
            print(f"  {est}: {n_high}")
            hay_alt = True
    if not hay_alt:
        print("  (ninguno)")

    # Punto 6 - Duplicados
    print(f"\n--- Duplicados en limite de mes ---")
    print(f"  Identicos eliminados: {n_identicos}")
    print(f"  Conflictivos (se conservo el primero):")
    if conflictivos:
        for c in conflictivos:
            print(
                f"    {c['fecha']} / {c['estacion']} / {c['contaminante']}: "
                f"valores={c['valores']}, archivos={c['archivos']}"
            )
    else:
        print("    (ninguno)")

    # Punto 8 - GeoJSON
    print(f"\n--- Comparacion con GeoJSON (encoding: {geo_enc}) ---")
    print(f"  Coinciden ({len(coinciden)}):")
    for sid in coinciden:
        print(f"    {sid:35s}  aire='{aire_map[sid]}', "
              f"geo='{geo_map[sid]}'")
    print(f"  Solo en aire ({len(solo_aire)}):")
    for sid in solo_aire:
        print(f"    {sid:35s}  nombre='{aire_map[sid]}'")
    print(f"  Solo en GeoJSON ({len(solo_geo)}):")
    for sid in solo_geo:
        print(f"    {sid:35s}  nombre='{geo_map[sid]}'")

    # Validacion cruzada con Num
    print(f"\n--- Validacion cruzada con fila Num ---")
    num_warns = [w for (_, w) in all_warnings if "Validacion Num" in w
                 or "Num" in w]
    if num_warns:
        for w in num_warns:
            print(f"  {w}")
    else:
        print("  OK en todos los archivos y columnas.")

    # Otras advertencias
    other = [
        (f, w)
        for (f, w) in all_warnings
        if "Num" not in w and "SALTADO" not in w
    ]
    if other:
        print(f"\n--- Otras advertencias ({len(other)}) ---")
        # Agrupar por mensaje (muchos archivos repiten lo mismo)
        mensajes_unicos: dict[str, list[str]] = {}
        for f, w in other:
            mensajes_unicos.setdefault(w.strip(), []).append(f)
        for msg, files in mensajes_unicos.items():
            if len(files) <= 3:
                print(f"  [{', '.join(files)}] {msg}")
            else:
                print(f"  [{len(files)} archivos] {msg}")

    print(f"\n--- Archivos guardados ---")
    print(f"  {parquet_path}")
    print(f"  {cob_path}")
    print("\n[OK] Limpieza completada.")


if __name__ == "__main__":
    main()
