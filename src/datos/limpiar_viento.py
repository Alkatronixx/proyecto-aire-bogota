"""Limpia los Excel mensuales de velocidad y dirección del viento de RMCAB.
Lee las hojas de data/raw/viento y contrasta estructura, resúmenes y estaciones.
Conserva mediciones ausentes como NaN y resuelve duplicados solo a favor de un dato.
Produce data/interim/viento_largo.parquet y data/processed/cobertura_viento.csv.
"""

import calendar
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "viento"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
GEO_PATH = PROJECT_ROOT / "data" / "raw" / "geografia" / "estacion_calida_aire.geojson"
AIR_PATH = INTERIM_DIR / "aire_largo.parquet"
RE_FECHA = re.compile(r"^(\d{1,2}-\d{1,2}-\d{4})(?:\s+.*)?$")
SUMMARY_LABELS = {
    "Summary:", "Minimum", "MinDate", "MinTime", "Maximum", "MaxDate",
    "MaxTime", "Avg", "Num", "DataPrecent", "STD",
}
MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}
VARIABLES = {"Vel": "vel_viento", "Dir": "dir_viento"}
UNIDADES = {"m/s", "Grados"}
FECHA_EXCLUIR_INICIO = pd.Timestamp("2025-08-04")
FECHA_EXCLUIR_FIN = pd.Timestamp("2025-10-16")


def normalizar_id(nombre: str) -> str:
    """Normaliza el nombre de estación a snake_case sin tildes.

    Parámetros: nombre original. Devuelve el identificador estable de estación.
    """
    texto = unicodedata.normalize("NFKD", nombre)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()
    texto = re.sub(r"[\s\-]+", "_", texto)
    return re.sub(r"[^a-z0-9_]", "", texto)


def _fecha_de_celda(valor):
    """Extrae solo dd-mm-aaaa de una celda textual y lo convierte a fecha.

    Parámetros: valor crudo de columna A. Devuelve Timestamp o None.
    """
    if not isinstance(valor, str):
        return None
    coincidencia = RE_FECHA.match(valor.strip())
    if not coincidencia:
        return None
    try:
        return pd.to_datetime(coincidencia.group(1), format="%d-%m-%Y")
    except ValueError:
        return None


def _leer_geojson():
    """Lee nombres de estaciones del GeoJSON con fallbacks de codificación.

    Parámetros: ninguno. Devuelve nombres de estación y codificación usada.
    """
    contenido = GEO_PATH.read_bytes()
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            texto = contenido.decode(encoding)
            geo = json.loads(texto)
            return [f["properties"].get("estacion", "").strip() for f in geo["features"]], encoding
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    texto = contenido.decode("utf-8", errors="replace")
    geo = json.loads(texto)
    return [f["properties"].get("estacion", "").strip() for f in geo["features"]], "utf-8 con reemplazo"


def _etiquetas_y_estaciones(hoja):
    """Lee pares estación-variable-unidad propagando las celdas combinadas.

    Parámetros: hoja Excel. Devuelve columnas válidas, estaciones del libro y errores.
    """
    columnas, estaciones, errores = [], [], []
    estacion = None
    for col in range(2, hoja.max_column + 1):
        if hoja.cell(3, col).value is not None:
            estacion = str(hoja.cell(3, col).value).strip()
        etiqueta = hoja.cell(4, col).value
        if col % 2 == 0 and estacion:
            estaciones.append(estacion)
        if etiqueta is None:
            continue
        original = str(etiqueta).strip()
        unidad = str(hoja.cell(5, col).value or "").strip()
        prefijo = "Vel" if original.startswith("Vel") else "Dir" if original.startswith("Dir") else None
        if prefijo is None or unidad not in UNIDADES:
            errores.append((col, original, unidad))
            continue
        columnas.append({
            "col_idx": col,
            "estacion": estacion,
            "variable": VARIABLES[prefijo],
            "variable_original": original,
            "unidad": unidad,
        })
    return columnas, estaciones, errores


def _valor_numerico(valor):
    """Convierte una celda numérica o textual a float y deja el resto como NaN.

    Parámetros: valor crudo de Excel. Devuelve float o NaN.
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return np.nan
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    try:
        return float(str(valor).strip().replace(",", "."))
    except ValueError:
        return np.nan


def _extraer_mes_nombre(nombre):
    """Extrae el mes inicial del patrón de nombres mensuales.

    Parámetros: nombre de archivo. Devuelve número de mes o None.
    """
    match = re.match(r"24\s+(\w+)", nombre.lower())
    return MESES.get(match.group(1)[:3]) if match else None


def _auditar_estructura(archivos):
    """Lista frecuencias de etiquetas/unidades y diferencias de estaciones.

    Parámetros: libros a inspeccionar. Devuelve conteos y estaciones por archivo.
    """
    etiquetas, unidades, errores = Counter(), Counter(), []
    estaciones_por_archivo = {}
    for ruta in archivos:
        wb = openpyxl.load_workbook(ruta, data_only=True, read_only=False)
        hoja = wb[wb.sheetnames[0]]
        cols, estaciones, errs = _etiquetas_y_estaciones(hoja)
        estaciones_por_archivo[ruta.name] = estaciones
        for col in range(2, hoja.max_column + 1):
            etiqueta = hoja.cell(4, col).value
            if etiqueta is not None:
                etiquetas[str(etiqueta).strip()] += 1
                unidades[str(hoja.cell(5, col).value or "").strip()] += 1
        errores.extend((ruta.name, *e) for e in errs)
        wb.close()
    print("\n--- Etiquetas distintas de fila 4 (frecuencia) ---")
    for etiqueta, cuenta in sorted(etiquetas.items()):
        print(f"  {etiqueta}: {cuenta}")
    print("--- Unidades distintas de fila 5 (frecuencia) ---")
    for unidad, cuenta in sorted(unidades.items()):
        print(f"  {unidad or '(vacía)'}: {cuenta}")
    if errores:
        print("ETIQUETAS/UNIDADES NO PROCESADAS:")
        for error in errores:
            print(f"  {error}")
    else:
        print("Etiquetas y unidades inesperadas: ninguna.")
    todas = set().union(*(set(v) for v in estaciones_por_archivo.values()))
    base = set.intersection(*(set(v) for v in estaciones_por_archivo.values()))
    print(f"\nEstaciones por archivo ({len(estaciones_por_archivo)} libros):")
    for nombre, estaciones in estaciones_por_archivo.items():
        aparecen = sorted(set(estaciones) - base)
        faltan = sorted(todas - set(estaciones))
        print(f"  {nombre}: {', '.join(estaciones)}")
        if aparecen or faltan:
            print(f"    aparecen respecto al conjunto común={aparecen}; faltan={faltan}")
    return estaciones_por_archivo, errores


def _validar_integridad(archivos):
    """Comprueba rangos, fecha inicial, días compartidos y hashes de libros.

    Parámetros: lista de rutas Excel. Devuelve un bloque de inconsistencias.
    """
    inconsistencias, info = [], []
    for ruta in archivos:
        contenido = ruta.read_bytes()
        wb = openpyxl.load_workbook(ruta, data_only=True, read_only=False)
        hoja = wb[wb.sheetnames[0]]
        fechas = []
        resumen_iniciado = False
        for fila in range(6, hoja.max_row + 1):
            a_crudo = hoja.cell(fila, 1).value
            if isinstance(a_crudo, str) and a_crudo.strip() in SUMMARY_LABELS:
                resumen_iniciado = True
                continue
            if resumen_iniciado:
                fecha_fuera = _fecha_de_celda(a_crudo)
                if fecha_fuera is not None:
                    n_datos = sum(
                        isinstance(hoja.cell(fila, c).value, (int, float))
                        and not isinstance(hoja.cell(fila, c).value, bool)
                        for c in range(2, hoja.max_column + 1)
                    )
                    inconsistencias.append(
                        f"{ruta.name}: fila {fila} con fecha {fecha_fuera.date()} después del resumen "
                        f"(se ignora; {n_datos} celdas numéricas)."
                    )
                continue
            fecha = _fecha_de_celda(a_crudo)
            if fecha is not None:
                fechas.append((fila, fecha))
        wb.close()
        fechas_unicas = sorted({f for _, f in fechas})
        item = {
            "nombre": ruta.name,
            "hash": hashlib.sha256(contenido).hexdigest(),
            "fechas": set(fechas_unicas),
            "primera": fechas_unicas[0] if fechas_unicas else None,
            "ultima": fechas_unicas[-1] if fechas_unicas else None,
        }
        info.append(item)
        print(f"  {ruta.name}: {item['primera']} a {item['ultima']} ({len(fechas_unicas)} fechas únicas), sha256={item['hash'][:16]}")
        if item["primera"] is None:
            inconsistencias.append(f"{ruta.name}: no contiene fechas interpretables.")
            continue
        if item["primera"].day != 24:
            inconsistencias.append(f"{ruta.name}: primera fecha no es día 24 ({item['primera'].date()}).")
        mes_nombre = _extraer_mes_nombre(ruta.name)
        if mes_nombre and item["primera"].month != mes_nombre:
            inconsistencias.append(f"{ruta.name}: mes inicial en fechas difiere del nombre del archivo.")
    for i, a in enumerate(info):
        for b in info[i + 1:]:
            compartidas = a["fechas"] & b["fechas"]
            if compartidas:
                inconsistencias.append(f"{a['nombre']} y {b['nombre']} comparten {len(compartidas)} fechas: {sorted(str(x.date()) for x in compartidas)}")
    por_hash = defaultdict(list)
    for item in info:
        por_hash[item["hash"]].append(item["nombre"])
    for digest, nombres in por_hash.items():
        if len(nombres) > 1:
            inconsistencias.append(f"Archivos idénticos (sha256 {digest[:16]}): {nombres}")
    print("\nINCONSISTENCIAS")
    if inconsistencias:
        for texto in inconsistencias:
            print(f"  - {texto}")
    else:
        print("  Ninguna en rango, día 24/mes, fechas compartidas ni hashes.")
    return info, inconsistencias


def _leer_archivo(ruta, errores_globales, textos_no_numericos):
    """Lee las observaciones, cuenta Num y registra repeticiones por libro.

    Parámetros: ruta Excel y colector de errores. Devuelve filas largas y metadatos.
    """
    wb = openpyxl.load_workbook(ruta, data_only=True, read_only=False)
    hoja = wb[wb.sheetnames[0]]
    columnas, estaciones, errores = _etiquetas_y_estaciones(hoja)
    errores_globales.extend((ruta.name, *e) for e in errores)
    fila_num = next((r for r in range(6, hoja.max_row + 1) if hoja.cell(r, 1).value == "Num"), None)
    num_esperado = {}
    for col in columnas:
        valor = hoja.cell(fila_num, col["col_idx"]).value if fila_num else None
        num_esperado[col["col_idx"]] = 0 if valor == "-" else _valor_numerico(valor)

    filas, por_fecha = [], defaultdict(list)
    fechas_con_datos = []
    for fila in range(6, hoja.max_row + 1):
        crudo = hoja.cell(fila, 1).value
        if isinstance(crudo, str) and crudo.strip() in SUMMARY_LABELS:
            break
        if crudo is None:
            continue
        fecha = _fecha_de_celda(crudo)
        if fecha is None:
            if str(crudo).strip():
                errores_globales.append((ruta.name, "fila sin fecha reconocible", fila, crudo))
            continue
        parsed = []
        for col in columnas:
            crudo_valor = hoja.cell(fila, col["col_idx"]).value
            valor = _valor_numerico(crudo_valor)
            if isinstance(crudo_valor, str) and crudo_valor.strip() and np.isnan(valor):
                textos_no_numericos[crudo_valor.strip()] += 1
            parsed.append((col, valor, crudo_valor))
            filas.append({
                "fecha": fecha,
                "estacion": col["estacion"],
                "estacion_id": normalizar_id(col["estacion"]),
                "variable": col["variable"],
                "variable_original": col["variable_original"],
                "valor": valor,
                "archivo_origen": ruta.name,
            })
        if any(not np.isnan(v) for _, v, _ in parsed):
            fechas_con_datos.append(fecha)
        por_fecha[fecha].append((fila, parsed, crudo))

    discrepancias_num = []
    numeric_counts = Counter()
    for registro in filas:
        if not pd.isna(registro["valor"]):
            # Conteo por estación y variable, equivalente a la columna original.
            numeric_counts[(registro["estacion"], registro["variable"], registro["variable_original"])] += 1
    for col in columnas:
        contado = sum(
            1 for r in filas
            if r["estacion"] == col["estacion"] and r["variable_original"] == col["variable_original"]
            and not pd.isna(r["valor"])
        )
        esperado = num_esperado[col["col_idx"]]
        if pd.isna(esperado) or esperado is None:
            etiqueta_error = "Num vacío" if hoja.cell(fila_num, col["col_idx"]).value is None else "Num no numérico"
            errores_globales.append((ruta.name, etiqueta_error, col["estacion"], col["variable_original"], esperado))
        elif contado != int(esperado):
            discrepancias_num.append((col["estacion"], col["variable_original"], contado, int(esperado)))

    repeticiones = []
    for fecha, registros in por_fecha.items():
        if len(registros) > 1:
            for fila, parsed, raw_date in registros:
                nnum = sum(not np.isnan(valor) for _, valor, _ in parsed)
                repeticiones.append((fecha, fila, raw_date, nnum))

    wb.close()
    return filas, columnas, estaciones, discrepancias_num, repeticiones, fechas_con_datos


def _resolver_duplicados(df):
    """Elige el valor disponible frente a NaN y lista conflictos numéricos.

    Parámetros: datos largos antes de deduplicar. Devuelve tabla única y reportes.
    """
    clave = ["fecha", "estacion_id", "variable"]
    conflictos, duplicados_identicos = [], 0
    conservar = []
    for _, grupo in df.groupby(clave, sort=False, dropna=False):
        valores = grupo["valor"].dropna().unique()
        if len(valores) > 1:
            conflictos.append({
                "fecha": grupo["fecha"].iloc[0],
                "estacion": grupo["estacion"].iloc[0],
                "variable": grupo["variable"].iloc[0],
                "valores": valores.tolist(),
                "archivos": grupo["archivo_origen"].tolist(),
            })
            conservar.append(grupo.iloc[0])
        else:
            con_dato = grupo[grupo["valor"].notna()]
            if len(con_dato):
                conservar.append(con_dato.iloc[0])
            else:
                conservar.append(grupo.iloc[0])
            duplicados_identicos += len(grupo) - 1
    return pd.DataFrame(conservar).reset_index(drop=True), duplicados_identicos, conflictos


def _rellenar_grilla(df, estaciones):
    """Completa cada combinación fecha-estación-variable para conservar NaN.

    Parámetros: observaciones deduplicadas y estaciones. Devuelve grilla diaria completa.
    """
    fechas = pd.date_range(df["fecha"].min(), df["fecha"].max(), freq="D")
    variables = ["vel_viento", "dir_viento"]
    base = pd.MultiIndex.from_product(
        [fechas, estaciones, variables], names=["fecha", "estacion", "variable"]
    ).to_frame(index=False)
    base["estacion_id"] = base["estacion"].map(normalizar_id)
    return base.merge(
        df[["fecha", "estacion_id", "estacion", "variable", "variable_original", "valor", "archivo_origen"]],
        on=["fecha", "estacion_id", "estacion", "variable"], how="left", validate="one_to_one",
    )


def _cobertura(df):
    """Calcula días con observación y porcentaje mensual por estación y variable.

    Parámetros: grilla completa. Devuelve cobertura en formato de entrega.
    """
    temporal = df.copy()
    temporal["anio_mes"] = temporal["fecha"].dt.to_period("M")
    cobertura = temporal.groupby(["estacion", "variable", "anio_mes"], as_index=False).agg(
        dias_con_dato=("valor", "count")
    )
    cobertura["dias_del_mes"] = cobertura["anio_mes"].apply(lambda p: calendar.monthrange(p.year, p.month)[1])
    cobertura["porcentaje_mes"] = (100 * cobertura["dias_con_dato"] / cobertura["dias_del_mes"]).round(1)
    cobertura["anio_mes"] = cobertura["anio_mes"].astype(str)
    return cobertura[["estacion", "variable", "anio_mes", "dias_con_dato", "porcentaje_mes"]]


def _rangos_dias(fechas):
    """Agrupa fechas consecutivas en rangos legibles.

    Parámetros: colección de fechas. Devuelve pares de fechas inicial y final.
    """
    fechas = sorted(pd.Timestamp(x).normalize() for x in fechas)
    if not fechas:
        return []
    rangos, inicio, anterior = [], fechas[0], fechas[0]
    for fecha in fechas[1:]:
        if fecha != anterior + pd.Timedelta(days=1):
            rangos.append((inicio, anterior))
            inicio = fecha
        anterior = fecha
    rangos.append((inicio, anterior))
    return rangos


def _reportar(df, cobertura, conflictos, n_dup):
    """Imprime controles físicos, cobertura faltante, GeoJSON e integridad de tabla.

    Parámetros: tabla resultante, cobertura y reportes de duplicados.
    """
    print("\n--- Duplicados ---")
    print(f"Duplicados equivalentes o repetidos eliminados: {n_dup}")
    print(f"Conflictos numéricos reales: {len(conflictos)}")
    for conflicto in conflictos:
        print(f"  {conflicto}")

    print("\n--- Control de fila Num por archivo y columna ---")
    print("Cada discrepancia se informa en la lectura por archivo; no se aborta el proceso.")

    print("\n--- Controles de rango (solo reporte) ---")
    for variable, mascara in [
        ("vel_viento < 0", (df["variable"] == "vel_viento") & (df["valor"] < 0)),
        ("vel_viento > 30", (df["variable"] == "vel_viento") & (df["valor"] > 30)),
        ("dir_viento < 0", (df["variable"] == "dir_viento") & (df["valor"] < 0)),
        ("dir_viento > 360", (df["variable"] == "dir_viento") & (df["valor"] > 360)),
    ]:
        print(f"  {variable}: {int(mascara.sum())}")
    direccion = df[df["variable"] == "dir_viento"]["valor"]
    print(f"  dirección exactamente 0: {int((direccion == 0).sum())}")
    print(f"  dirección exactamente 360: {int((direccion == 360).sum())}")

    print("\n--- Faltantes por estación y variable ---")
    for (estacion, variable), grupo in df.groupby(["estacion", "variable"]):
        pct = 100 * grupo["valor"].isna().mean()
        incluidos = ~grupo["fecha"].between(FECHA_EXCLUIR_INICIO, FECHA_EXCLUIR_FIN)
        pct_sin_intervalo = 100 * grupo.loc[incluidos, "valor"].isna().mean()
        print(f"  {estacion} / {variable}: periodo={pct:.1f}%; excluyendo 2025-08-04..2025-10-16={pct_sin_intervalo:.1f}%")

    print("\n--- Meses con 0% de cobertura y rangos continuos ---")
    for (estacion, variable), grupo in cobertura.groupby(["estacion", "variable"]):
        meses = grupo.loc[grupo["porcentaje_mes"] == 0, "anio_mes"].tolist()
        if meses:
            print(f"  {estacion} / {variable}: {', '.join(meses)}")
        fechas_sin = df.loc[(df["estacion"] == estacion) & (df["variable"] == variable) & df["valor"].isna(), "fecha"]
        # Solo se listan rangos sin dato de meses completos para no ocultar faltantes parciales.
        if meses:
            dias = df.loc[(df["estacion"] == estacion) & (df["variable"] == variable) & df["fecha"].dt.to_period("M").astype(str).isin(meses), "fecha"]
            for inicio, fin in _rangos_dias(dias):
                print(f"    rango: {inicio.date()} a {fin.date()}")

    print("\n--- Fechas con todas las estaciones en NaN, por variable ---")
    en_intervalo = 0
    for variable, grupo in df.groupby("variable"):
        por_dia = grupo.groupby("fecha")["valor"].apply(lambda valores: valores.isna().all())
        dias = por_dia[por_dia].index
        rangos = _rangos_dias(dias)
        n_intervalo = sum(
            max(0, (min(fin, FECHA_EXCLUIR_FIN) - max(inicio, FECHA_EXCLUIR_INICIO)).days + 1)
            for inicio, fin in rangos
        )
        en_intervalo += n_intervalo
        print(f"  {variable}: {len(dias)} días; {n_intervalo} caen en 2025-08-04..2025-10-16")
        for inicio, fin in rangos:
            print(f"    {inicio.date()} a {fin.date()}")
    print(f"  Total en intervalo indicado (sumando variables): {en_intervalo}")

    print("\n--- Comparación con estaciones de aire y GeoJSON ---")
    viento = {normalizar_id(x): x for x in df["estacion"].drop_duplicates()}
    if AIR_PATH.exists():
        aire_df = pd.read_parquet(AIR_PATH)
        aire = {normalizar_id(x): x for x in aire_df["estacion"].dropna().unique()}
        print(f"  Aire y viento: coinciden={len(set(aire) & set(viento))}; solo aire={sorted(set(aire)-set(viento))}; solo viento={sorted(set(viento)-set(aire))}")
    else:
        print("  No existe aire_largo.parquet; se omite comparación aire-viento.")
    if GEO_PATH.exists():
        geo_nombres, encoding = _leer_geojson()
        geo = {normalizar_id(x): x for x in geo_nombres}
        print(f"  GeoJSON ({encoding}): coinciden={len(set(geo)&set(viento))}; solo viento={sorted(set(viento)-set(geo))}; solo GeoJSON={sorted(set(geo)-set(viento))}")


def main():
    """Ejecuta auditoría, limpieza, validaciones y escritura de productos.

    Parámetros: ninguno. Escribe parquet y CSV e imprime los diagnósticos reales.
    """
    archivos = sorted(RAW_DIR.glob("*.xlsx"))
    if not archivos:
        raise FileNotFoundError(f"No hay archivos Excel en {RAW_DIR}")
    print(f"Libros encontrados: {len(archivos)}")
    estaciones_por_archivo, errores_etiqueta = _auditar_estructura(archivos)
    info, inconsistencias = _validar_integridad(archivos)

    filas, discrepancias, repeticiones, errores_globales = [], [], [], []
    textos_no_numericos = Counter()
    estaciones_union = set().union(*(set(x) for x in estaciones_por_archivo.values()))
    for ruta in archivos:
        datos, columnas, estaciones, nums, reps, _ = _leer_archivo(ruta, errores_globales, textos_no_numericos)
        filas.extend(datos)
        if nums:
            discrepancias.append((ruta.name, nums))
        for fecha, fila, raw_date, nnum in reps:
            repeticiones.append((ruta.name, fecha, fila, raw_date, nnum))
    print("\n--- Fechas repetidas dentro de cada archivo ---")
    if repeticiones:
        repetidas_por_archivo = defaultdict(list)
        for nombre, fecha, fila, raw_date, nnum in repeticiones:
            repetidas_por_archivo[(nombre, fecha)].append((fila, raw_date, nnum))
        for (nombre, fecha), registros in repetidas_por_archivo.items():
            detalle = "; ".join(f"fila {fila}: {nnum} numéricos, A={raw_date!r}" for fila, raw_date, nnum in registros)
            print(f"  {nombre}: {fecha.date()} — {detalle}")
    else:
        print("  Ninguna.")

    print("\n--- Discrepancias contra Num ---")
    if discrepancias:
        for nombre, detalles in discrepancias:
            for estacion, etiqueta, contado, esperado in detalles:
                print(f"  {nombre} | {estacion} | {etiqueta}: parseados={contado}, Num={esperado}")
    else:
        print("  Ninguna.")
    if errores_globales:
        print("\n--- Celdas/filas no interpretadas ---")
        for error in errores_globales:
            print(f"  {error}")
    print("\n--- Textos no numéricos convertidos a NaN ---")
    if textos_no_numericos:
        for texto, cuenta in sorted(textos_no_numericos.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {texto!r}: {cuenta}")
    else:
        print("  Ninguno.")

    df = pd.DataFrame(filas)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df, n_dup, conflictos = _resolver_duplicados(df)
    df = _rellenar_grilla(df, sorted(estaciones_union))
    df = df[["fecha", "estacion", "estacion_id", "variable", "variable_original", "valor", "archivo_origen"]]
    cobertura = _cobertura(df)

    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    parquet = INTERIM_DIR / "viento_largo.parquet"
    csv = PROCESSED_DIR / "cobertura_viento.csv"
    df.to_parquet(parquet, index=False, engine="pyarrow")
    cobertura.to_csv(csv, index=False)

    print("\n--- Resultado de tabla ---")
    fechas = sorted(df["fecha"].drop_duplicates())
    print(f"Filas: {len(df):,}; fechas únicas: {len(fechas):,}; rango: {fechas[0].date()} a {fechas[-1].date()}")
    huecos = pd.date_range(fechas[0], fechas[-1], freq="D").difference(pd.DatetimeIndex(fechas))
    print(f"Fechas faltantes en unión: {len(huecos)}; estaciones: {df['estacion'].nunique()}; variables: {sorted(df['variable'].unique())}")
    print(f"Filas esperadas por especificación (1096 × 17 × 2): 37,264; diferencia: {len(df)-37264:+,}")
    _reportar(df, cobertura, conflictos, n_dup)

    aire_viento = set(df["estacion_id"])
    if AIR_PATH.exists():
        aire_ids = {normalizar_id(x) for x in pd.read_parquet(AIR_PATH)["estacion"].dropna().unique()}
        print(f"\nAire ausente en viento: {sorted(aire_ids-aire_viento)}; viento ausente en aire: {sorted(aire_viento-aire_ids)}")
    print(f"\nParquet: {parquet}\nCobertura: {csv}")
    print("\n--- Resumen de inconsistencias ---")
    if inconsistencias or errores_etiqueta or errores_globales or discrepancias or conflictos:
        print(f"  Integridad={len(inconsistencias)}, etiquetas={len(errores_etiqueta)}, filas/celdas={len(errores_globales)}, archivos con discrepancia Num={len(discrepancias)}, conflictos numéricos={len(conflictos)}")
    else:
        print("  No se encontraron inconsistencias en los controles configurados.")


if __name__ == "__main__":
    main()
