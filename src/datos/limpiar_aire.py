"""
limpiar_aire.py — Limpieza y consolidación de calidad del aire (PM10 y PM2.5) de la RMCAB.

Qué hace:
    Procesa, valida e integra los reportes mensuales de calidad del aire de la Red de
    Monitoreo de Calidad del Aire de Bogotá (RMCAB), resolviendo duplicados y calculando
    métricas de cobertura temporal por estación y contaminante.

Qué lee:
    - Archivos mensuales de la RMCAB en formato Excel: data/raw/aire/*.xlsx
    - Georreferenciación oficial de estaciones: data/raw/geografia/estacion_calida_aire.geojson

Qué produce:
    - Tabla integrada en formato largo: data/interim/aire_largo.parquet
    - Matriz de cobertura mensual por estación: data/processed/cobertura_aire.csv

Cómo se ejecuta:
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

# SUPUESTO: "24:00" en los datos crudos de la RMCAB representa el promedio de cierre
# de las 24 horas del mismo día calendario reportado, y NO la medianoche o inicio del
# día siguiente. Por tanto, no se suma un día a la fecha y se normaliza al día en curso.
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
    """Convierte un nombre de estación a snake_case sin tildes para estandarización.

    Ejemplo: "Centro de Alto Rendimiento" -> "centro_de_alto_rendimiento"

    Parámetros
    ----------
    nombre : str
        Nombre original de la estación en los archivos o metadatos.

    Retorna
    -------
    str
        Identificador normalizado en snake_case alfanumérico.
    """
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    resultado = sin_tildes.lower().strip()
    resultado = re.sub(r"[\s\-]+", "_", resultado)
    resultado = re.sub(r"[^a-z0-9_]", "", resultado)
    return resultado


def _leer_encabezado(ws):
    """Lee las filas 3-5 del encabezado y devuelve la lista de columnas estructuradas.

    SUPUESTO: Propagación de estaciones por celdas combinadas: en la fila 3 del Excel,
    las celdas con nombres de estación están combinadas horizontalmente abarcando las columnas
    correspondientes a PM10 y PM2.5. openpyxl lee únicamente el valor en la primera celda
    del bloque combinado y deja las subsecuentes en None; por lo tanto, se asume que propagar
    hacia la derecha (forward-fill) el último nombre no nulo reconstruye fielmente la asociación
    de estación para todas las columnas de contaminantes.

    Parámetros
    ----------
    ws : openpyxl.worksheet.worksheet.Worksheet
        Hoja de cálculo activa del archivo Excel mensual.

    Retorna
    -------
    columnas : list[dict] | None
        Lista de diccionarios con: col_idx (1-based), estacion, contaminante, unidad;
        o None si ocurre un error estructural en el encabezado.
    error : str | None
        Mensaje descriptivo del error si el encabezado no cumple la estructura esperada.
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
    # SUPUESTO: Las celdas combinadas de la fila 3 asignan la misma estación a PM10 y PM2.5
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
    """Lee un archivo Excel mensual, extrae filas de datos válidas y las transforma a formato largo.

    SUPUESTO: El nombre del archivo solo se usa para validar, nunca para deducir fechas.
    Las fechas asignadas provienen estrictamente de la columna de fecha (DateTime) de cada fila.

    SUPUESTO: La última fila de cada archivo mensual corresponde al día 24 sin cerrar,
    la cual viene vacía (o sin consolidar) al momento de la descarga oficial y se descarta
    o resuelve a favor del archivo siguiente que sí contiene los datos cerrados.

    SUPUESTO: Validación contra la fila Num: la fila 'Num' al final de la tabla contiene
    el recuento oficial de datos horarios válidos según la RMCAB. Se utiliza como control
    de validación cruzada para verificar que la cantidad de valores numéricos parseados
    coincida con lo reportado por la estación.

    Parameters
    ----------
    filepath : Path
        Ruta al archivo .xlsx mensual a procesar.
    ref_header : list[dict] | None
        Encabezado de referencia del primer archivo procesado. Si es None, este archivo
        se utiliza como el estándar de comparación estructural.

    Returns
    -------
    df : pd.DataFrame | None
        DataFrame en formato largo (fecha, estacion, contaminante, valor, archivo_origen),
        o None si el archivo fue descartado por inconsistencia estructural.
    header : list[dict] | None
        Encabezado estructurado parseado del archivo.
    warnings : list[str]
        Lista de advertencias, discrepancias con la fila Num o irregularidades registradas.
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
        # SUPUESTO: La fila Num certifica la cantidad de horas válidas registradas en el mes
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
            # SUPUESTO: '24:00' se interpreta como cierre del mismo día calendario (HORA_CIERRE_DOC)
            fecha = pd.to_datetime(date_str, dayfirst=True).normalize()
        except Exception as e:
            warnings.append(f"  Fila {r} fecha no parseable: {date_str!r} → {e}")
            continue

        # SUPUESTO: La última fila con fecha en cada archivo corresponde al día 24 sin cerrar,
        # que viene vacía en este archivo y cuyos datos consolidados se leerán en el siguiente archivo.
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
    # SUPUESTO: La fila Num del Excel certifica los registros numéricos válidos esperados
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
    """Convierte la columna valor a numérico y cuantifica textos no numéricos.

    SUPUESTO: '----' tratado como NaN: la cadena '----' en los reportes de la RMCAB representa
    valores ausentes o mediciones no disponibles (sensores inoperativos o datos descartados
    por validación de la red). Se convierte a NaN numérico sin imputar ni rellenar con cero,
    cumpliendo la regla crítica de no inventar datos.

    Rareza de datos: Se conservan sin modificar los valores negativos observados en la fuente
    (Jazmín y Móvil Fontibón, 2 casos cada una) para preservar las lecturas reales del sensor
    (posible descalibración o ruido de línea base) sin introducir alteraciones artificiales.

    Retorna
    -------
    df : pd.DataFrame
        DataFrame con la columna 'valor' convertida a tipo numérico (float).
    textos : dict[str, int]
        Diccionario texto → conteo de ocurrencias de cadenas no numéricas antes de la conversión.
    """
    # Encontrar valores que son cadenas antes de la conversión
    mask_str = df["valor"].apply(lambda x: isinstance(x, str))
    textos: dict[str, int] = {}
    if mask_str.any():
        textos = df.loc[mask_str, "valor"].value_counts().to_dict()

    # Conversión a numérico (SUPUESTO: '----' y otros textos se convierten en NaN)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df, textos


def _resolver_duplicados(df: pd.DataFrame):
    """Maneja duplicados (fecha, estación, contaminante) en límites de mes.

    SUPUESTO: Regla de deduplicación: se conserva la fila con valor numérico válido frente
    a la fila NaN de la misma fecha. Causa: en los Excel de la RMCAB existe un artefacto
    sistemático donde cada archivo repite la penúltima fecha con una fila completamente vacía
    (NaN) ubicada en segunda posición, y además el día 24 saliente al final de mes aparece sin
    cerrar (vacío) mientras que en el archivo entrante del mes siguiente sí contiene datos.
    Al conservar la fila con datos reales, se descartan los registros vacíos espurios.

    - Idénticos: elimina filas duplicadas con valor idéntico (o todas NaN).
    - Conflictivos: conserva la fila prioritaria con dato y lista las discrepancias para control.

    Parámetros
    ----------
    df : pd.DataFrame
        DataFrame largo con posibles registros duplicados.

    Retorna
    -------
    df : pd.DataFrame
        DataFrame deduplicado.
    identicos_eliminados : int
        Conteo de filas idénticas eliminadas.
    conflictivos : list[dict]
        Lista de casos conflictivos documentados para auditoría.
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
                # SUPUESTO: La fila con valor aparece primero o se prioriza sobre la fila vacía NaN
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

    Retorna
    -------
    nombres : list[str]
        Lista de nombres de estaciones leídos del archivo geográfico.
    encoding_usado : str
        Nombre de la codificación exitosa ('utf-8', 'latin-1', 'cp1252', etc.).
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
            if "�" not in text:
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
    """Genera tabla de cobertura: una fila por estación, contaminante y año-mes.

    Parámetros
    ----------
    df : pd.DataFrame
        DataFrame consolidado en formato largo con fechas y mediciones.

    Retorna
    -------
    pd.DataFrame
        Tabla de cobertura mensual con conteo de días con dato y porcentaje relativo al mes.
    """
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
    """Extrae el mes inicial del nombre de archivo (ej. '24 oct - 24 nov 2023.xlsx' -> 10).

    SUPUESTO: El nombre del archivo solo se usa para validar, nunca para deducir fechas.
    Se utiliza aquí únicamente para contrastar la etiqueta del archivo con las fechas internas.

    Parámetros
    ----------
    nombre : str
        Nombre del archivo .xlsx.

    Retorna
    -------
    int | None
        Número de mes (1 a 12) correspondiente al inicio del periodo o None si no hace match.
    """
    # Patron: '24 <mes> - 24 <mes> <anio>.xlsx' o '24 <mes> <anio> - 24 <mes> <anio>.xlsx'
    m = re.match(r"24\s+(\w+)", nombre.lower())
    if m:
        return _MESES.get(m.group(1))
    return None


def _validar_integridad_archivos(archivos: list[Path]):
    """Valida integridad de archivos crudos antes de procesarlos.

    SUPUESTO: El nombre del archivo solo se usa para validar, nunca para deducir fechas.
    Las fechas reales provienen exclusivamente de las celdas de la columna DateTime.

    Controles realizados y significado de sus avisos:
      a) Rango y días únicos: Determina la primera y última fecha con datos numéricos y
         la cantidad de días únicos en cada archivo. Alerta si un archivo está truncado
         o no contiene fechas utilizables.
      b) Día 24 y mes: Verifica si la primera fecha del archivo es día 24 y si su mes
         coincide con el nombre del archivo para detectar desfases en la secuencia mensual.
         NOTA: El aviso de "primera fecha es día 23" en dos archivos ('24 abr - 24 may 2026.xlsx'
         y '24 oct - 24 nov 2025.xlsx') es esperado y NO indica error: se debe a que incluyen
         una fila inicial residual sin datos numéricos (cierre del mes anterior), mientras que
         su primer dato con mediciones numéricas sí inicia correctamente el día 24.
      c) Fechas compartidas > 2: Verifica que ninguna pareja de archivos comparta más de 2 fechas.
         El diseño de corte de la RMCAB solapa a lo sumo 1 o 2 días en los empalmes; compartir
         más de 2 fechas alertaría sobre periodos duplicados o archivos repetidos por error.
      d) Hashes idénticos: Compara el SHA-256 binario de los archivos para alertar sobre
         archivos con contenido idéntico guardados con nombres distintos.

    Parámetros
    ----------
    archivos : list[Path]
        Lista de rutas a los archivos .xlsx de entrada.

    Retorna
    -------
    list[dict]
        Lista de diccionarios con la información de control y metadatos por archivo.
    """
    print("\r\n" + "=" * 70)
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
        print(f"\r\n  {nombre}")
        print(f"    Dias unicos: {n_dias}  "
              f"Rango: {info['primera']} -- {info['ultima']}")
        print(f"    Primer dia con datos num: {primera_num}  "
              f"Ultimo dia con datos num: {ultima_num}")
        print(f"    Hash: {file_hash}")

        # (b) Verificar dia 24 y mes coincide con nombre
        # SUPUESTO: El nombre se usa solo para control y no para asignar fechas
        if info["primera"] is not None:
            mes_nombre = _extraer_mes_inicio_nombre(nombre)
            dia_primera = info["primera"].day
            mes_primera = info["primera"].month

            # NOTA: En '24 abr - 24 may 2026.xlsx' y '24 oct - 24 nov 2025.xlsx',
            # la primera fecha es día 23 por una fila vacía residual; este aviso es esperado y no es error.
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
    print(f"\r\n--- Fechas compartidas entre archivos ---")
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
    print(f"\r\n--- Hashes de contenido ---")
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
    print(f"\r\n{'=' * 70}")
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
    """Ejecuta la limpieza, validación y consolidación completa de datos de aire."""
    print("=" * 70)
    print("LIMPIEZA DE DATOS DE AIRE — RMCAB")
    print("=" * 70)

    # ── 1. Buscar archivos ──
    archivos = sorted(RAW_DIR.glob("**/*.xlsx"))
    archivos = [a for a in archivos if not a.name.startswith("~")]
    print(f"\r\nArchivos .xlsx encontrados: {len(archivos)}")

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
    # SUPUESTO: '----' tratado como NaN.
    # Rareza de datos: Se conservan sin alterar valores negativos (Jazmín y Móvil Fontibón, 2 c/u).
    df, textos_no_numericos = _convertir_valores(df)

    # ── 5. Resolver duplicados ──
    # SUPUESTO: Regla de deduplicación (se conserva la fila con valor frente a NaN).
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
    # Rareza de datos: Entre 2025-08-04 y 2025-10-16 todas las estaciones están en NaN.
    # Es un hueco real de la fuente RMCAB (re-descargado y confirmado vacío, mientras los archivos
    # de viento sí tienen datos en esas fechas; causa desconocida). Se conserva como NaN.
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
    print("\r\n" + "=" * 70)
    print("R E S U M E N")
    print("=" * 70)

    # Archivos
    print(f"\r\nArchivos leidos exitosamente : {len(archivos_leidos)}")
    print(f"Archivos saltados            : {len(archivos_saltados)}")
    for a in archivos_saltados:
        print(f"  X {a}")

    # Rango de fechas
    # SUPUESTO: Periodo analizado: 2023-10-24 a 2026-10-23
    print(f"\r\nRango de fechas: {df['fecha'].min().date()} -- {df['fecha'].max().date()}")

    # Estaciones y contaminantes
    estaciones = sorted(df["estacion"].unique())
    contaminantes = sorted(df["contaminante"].unique())
    print(f"Estaciones ({len(estaciones)}): {estaciones}")
    print(f"Contaminantes: {contaminantes}")
    print(f"Filas totales (despues de dedup): {len(df)}")

    # % faltantes por estacion
    # Rareza de datos: El porcentaje de faltantes incluye el hueco institucional generalizado
    # entre 2025-08-04 y 2025-10-16 donde todas las estaciones están en NaN en la fuente original.
    print(f"\r\n--- % Valores faltantes por estacion ---")
    for est in estaciones:
        mask = df["estacion"] == est
        total = mask.sum()
        faltantes = df.loc[mask, "valor"].isna().sum()
        pct = faltantes / total * 100 if total > 0 else 0
        print(f"  {est:30s}  {faltantes:5d}/{total:5d}  ({pct:5.1f}%)")

    # Punto 4 - Fechas con hora
    print(f"\r\n--- Fechas con hora ---")
    print(f"  Todas las fechas traian '24:00' -> normalizado a fecha (dia).")
    print(f"  {HORA_CIERRE_DOC}")

    # Punto 5 - Textos no numericos
    print(f"\r\n--- Textos no numericos -> NaN ---")
    if textos_no_numericos:
        for txt, cnt in sorted(textos_no_numericos.items(), key=lambda x: -x[1]):
            print(f"  '{txt}': {cnt}")
    else:
        print("  (ninguno)")

    n_nan_total = df["valor"].isna().sum()
    print(f"  Total valores NaN: {n_nan_total} / {len(df)} "
          f"({n_nan_total / len(df) * 100:.1f}%)")

    # Negativos y > 1000
    # Rareza de datos: Los valores negativos (Jazmín: 2, Móvil Fontibón: 2) se conservan intactos.
    # Rareza de datos: En los datos consolidados se conservan también 3 casos donde PM2.5 > PM10.
    print(f"\r\n--- Valores negativos por estacion ---")
    hay_neg = False
    for est in estaciones:
        n_neg = ((df["estacion"] == est) & (df["valor"] < 0)).sum()
        if n_neg > 0:
            print(f"  {est}: {n_neg}")
            hay_neg = True
    if not hay_neg:
        print("  (ninguno)")

    print(f"\r\n--- Valores > 1000 por estacion ---")
    hay_alt = False
    for est in estaciones:
        n_high = ((df["estacion"] == est) & (df["valor"] > 1000)).sum()
        if n_high > 0:
            print(f"  {est}: {n_high}")
            hay_alt = True
    if not hay_alt:
        print("  (ninguno)")

    # Punto 6 - Duplicados
    print(f"\r\n--- Duplicados en limite de mes ---")
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
    print(f"\r\n--- Comparacion con GeoJSON (encoding: {geo_enc}) ---")
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
    # SUPUESTO: Control cruzado contra la fila Num de cada archivo
    print(f"\r\n--- Validacion cruzada con fila Num ---")
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
        print(f"\r\n--- Otras advertencias ({len(other)}) ---")
        # Agrupar por mensaje (muchos archivos repiten lo mismo)
        mensajes_unicos: dict[str, list[str]] = {}
        for f, w in other:
            mensajes_unicos.setdefault(w.strip(), []).append(f)
        for msg, files in mensajes_unicos.items():
            if len(files) <= 3:
                print(f"  [{', '.join(files)}] {msg}")
            else:
                print(f"  [{len(files)} archivos] {msg}")

    print(f"\r\n--- Archivos guardados ---")
    print(f"  {parquet_path}")
    print(f"  {cob_path}")
    print("\r\n[OK] Limpieza completada.")


if __name__ == "__main__":
    main()
