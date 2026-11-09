"""Diagnostica faltantes y rarezas de la serie limpia de viento.
Lee los parquets existentes, los Excel crudos de viento y el GeoJSON de estaciones.
No altera datos de origen ni productos limpios; solo calcula estadísticas descriptivas.
Escribe el informe reproducible en data/interim/diagnostico_viento_resultados.txt.
"""

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
WIND_PARQUET = ROOT / "data" / "interim" / "viento_largo.parquet"
AIR_PARQUET = ROOT / "data" / "interim" / "aire_largo.parquet"
WIND_RAW = ROOT / "data" / "raw" / "viento"
GEO_DIR = ROOT / "data" / "raw" / "geografia"
REPORT_PATH = ROOT / "data" / "interim" / "diagnostico_viento_resultados.txt"
DATE_START = pd.Timestamp("2023-10-24")
DATE_END = pd.Timestamp("2026-10-23")
EXCL_START = pd.Timestamp("2025-08-04")
EXCL_END = pd.Timestamp("2025-10-16")
DATE_RE = re.compile(r"^(\d{1,2}-\d{1,2}-\d{4})(?:\s+.*)?$")
SUMMARY_LABELS = {
    "Summary:", "Minimum", "MinDate", "MinTime", "Maximum", "MaxDate",
    "MaxTime", "Avg", "Num", "DataPrecent", "STD",
}
MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}
EARTH_KM = 6371.0088


def normalizar_id(nombre):
    """Normaliza nombres para comparar etiquetas con y sin tildes.

    Parámetros: nombre crudo. Devuelve identificador en minúsculas y sin tildes.
    """
    texto = unicodedata.normalize("NFKD", str(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()
    texto = re.sub(r"[\s\-]+", "_", texto)
    return re.sub(r"[^a-z0-9_]", "", texto)


def fecha_cruda(valor):
    """Interpreta la parte dd-mm-aaaa de una fecha cruda de Excel.

    Parámetros: valor de columna A. Devuelve Timestamp o None.
    """
    if not isinstance(valor, str):
        return None
    match = DATE_RE.match(valor.strip())
    if not match:
        return None
    try:
        return pd.to_datetime(match.group(1), format="%d-%m-%Y")
    except ValueError:
        return None


def es_numero(valor):
    """Identifica celdas realmente numéricas, sin contar booleanos.

    Parámetros: valor de celda. Devuelve True si Excel entrega número.
    """
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def leer_geojson_estaciones():
    """Carga estaciones e intenta reparar problemas de codificación en memoria.

    Parámetros: ninguno. Devuelve lista de propiedades y método de decodificación.
    """
    ruta = GEO_DIR / "estacion_calida_aire.geojson"
    datos = ruta.read_bytes()
    candidatos = [("utf-8", "utf-8"), ("cp1252", "cp1252"), ("latin-1", "latin-1")]
    ultimo_error = None
    for encoding, etiqueta in candidatos:
        try:
            texto = datos.decode(encoding)
            geo = json.loads(texto)
            nombres = [str(f.get("properties", {}).get("estacion", "")).strip() for f in geo.get("features", [])]
            if "\ufffd" in texto or any("�" in nombre for nombre in nombres):
                continue
            return geo.get("features", []), etiqueta
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            ultimo_error = error
    # Fallback visible: el informe revela si el reemplazo dejó caracteres dañados.
    texto = datos.decode("utf-8", errors="replace")
    geo = json.loads(texto)
    if ultimo_error:
        return geo.get("features", []), f"utf-8 con reemplazo ({ultimo_error})"
    return geo.get("features", []), "utf-8 con reemplazo"


def coordenadas(features):
    """Construye mapa estación→(longitud, latitud) desde puntos GeoJSON.

    Parámetros: features de GeoJSON. Devuelve etiquetas originales y coordenadas.
    """
    resultado = {}
    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [])
        if geom.get("type") == "Point" and len(coords) >= 2:
            nombre = str(props.get("estacion", "")).strip()
            resultado[normalizar_id(nombre)] = (nombre, float(coords[0]), float(coords[1]))
    return resultado


def haversine_km(lon1, lat1, lon2, lat2):
    """Calcula distancia de círculo máximo usando coordenadas en grados.

    Parámetros: dos pares longitud/latitud. Devuelve kilómetros.
    """
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def rangos_nan(fechas, umbral=7):
    """Agrupa NaN consecutivos y devuelve solo tramos que alcanzan el umbral.

    Parámetros: serie diaria booleana y duración mínima. Devuelve tuplas de inicio, fin, días.
    """
    fechas = pd.DatetimeIndex(sorted(pd.Timestamp(x).normalize() for x in fechas))
    if len(fechas) == 0:
        return []
    resultado, inicio, anterior = [], fechas[0], fechas[0]
    for fecha in fechas[1:]:
        if fecha != anterior + pd.Timedelta(days=1):
            dias = (anterior - inicio).days + 1
            if dias >= umbral:
                resultado.append((inicio, anterior, dias))
            inicio = fecha
        anterior = fecha
    dias = (anterior - inicio).days + 1
    if dias >= umbral:
        resultado.append((inicio, anterior, dias))
    return resultado


def encabezado_viento(hoja, estacion_objetivo):
    """Encuentra las columnas velocidad/dirección de una estación en una hoja.

    Parámetros: hoja y estación a localizar. Devuelve mapa variable→columna.
    """
    columnas, estacion = {}, None
    objetivo = normalizar_id(estacion_objetivo)
    for col in range(2, hoja.max_column + 1):
        if hoja.cell(3, col).value is not None:
            estacion = str(hoja.cell(3, col).value).strip()
        if not estacion or normalizar_id(estacion) != objetivo:
            continue
        etiqueta = str(hoja.cell(4, col).value or "").strip()
        if etiqueta.startswith("Vel"):
            columnas["vel_viento"] = col
        elif etiqueta.startswith("Dir"):
            columnas["dir_viento"] = col
    return columnas


def filas_datos_excel(hoja):
    """Obtiene fechas de datos anteriores a la primera fila de resumen.

    Parámetros: hoja Excel. Devuelve filas con fecha y la primera fila resumen.
    """
    filas, fila_resumen = [], None
    for fila in range(6, hoja.max_row + 1):
        valor_a = hoja.cell(fila, 1).value
        if isinstance(valor_a, str) and valor_a.strip() in SUMMARY_LABELS:
            fila_resumen = fila
            break
        fecha = fecha_cruda(valor_a)
        if fecha is not None:
            filas.append((fila, fecha))
    return filas, fila_resumen


def informe_faltantes(viento):
    """Crea tabla completa de faltantes, media de velocidad y tramos NaN largos.

    Parámetros: tabla larga de viento. Devuelve texto detallado por estación-variable.
    """
    fechas = pd.date_range(DATE_START, DATE_END, freq="D")
    estaciones = sorted(viento["estacion"].dropna().unique())
    excluidas = (fechas < EXCL_START) | (fechas > EXCL_END)
    velocidad_media = (
        viento[viento["variable"] == "vel_viento"]
        .groupby("estacion")["valor"].mean().to_dict()
    )
    filas = []
    for estacion in estaciones:
        for variable in ("vel_viento", "dir_viento"):
            serie = (
                viento[(viento["estacion"] == estacion) & (viento["variable"] == variable)]
                .set_index("fecha")["valor"].reindex(fechas)
            )
            faltante = serie.isna()
            pct_todo = 100 * faltante.mean()
            pct_fuera = 100 * faltante[excluidas].mean()
            tramos = rangos_nan(fechas[faltante.to_numpy()], 7)
            texto_tramos = "; ".join(
                f"{ini:%Y-%m-%d}..{fin:%Y-%m-%d} ({dias} d)" for ini, fin, dias in tramos
            ) or "ninguno"
            filas.append({
                "estacion": estacion,
                "variable": variable,
                "faltantes_%_periodo": pct_todo,
                "faltantes_%_sin_hueco": pct_fuera,
                "velocidad_media_m_s": velocidad_media.get(estacion, np.nan),
                "rangos_nan_7d_o_mas": texto_tramos,
            })
    tabla = pd.DataFrame(filas).sort_values(
        ["faltantes_%_sin_hueco", "estacion", "variable"], ascending=[False, True, True]
    )
    tabla["faltantes_%_periodo"] = tabla["faltantes_%_periodo"].map(lambda x: f"{x:.2f}")
    tabla["faltantes_%_sin_hueco"] = tabla["faltantes_%_sin_hueco"].map(lambda x: f"{x:.2f}")
    tabla["velocidad_media_m_s"] = tabla["velocidad_media_m_s"].map(lambda x: "NaN" if pd.isna(x) else f"{x:.3f}")
    return "\n".join([
        "1. FALTANTES POR ESTACIÓN (34 filas; velocidad media repetida por estación)",
        f"Denominadores: periodo={len(fechas)} días; excluyendo intervalo={int(excluidas.sum())} días.",
        tabla.to_string(index=False),
    ])


def informe_tres_libros(viento):
    """Inspecciona filas tras resúmenes y compara recuentos/promedios con el parquet.

    Parámetros: tabla larga limpia. Devuelve informe por archivo raro.
    """
    casos = [
        ("24 abr 2026- 24 may 2026.xlsx", "Puente Aranda"),
        ("24 ene 2026- 24 feb 2026.xlsx", "Carvajal - Sevillana"),
        ("24 oct 2025- 24 nov 2025.xlsx", "Colina"),
    ]
    bloques = ["2. TRES ARCHIVOS CON RAREZAS"]
    for nombre, estacion in casos:
        ruta = WIND_RAW / nombre
        wb = openpyxl.load_workbook(ruta, data_only=True, read_only=False)
        hoja = wb[wb.sheetnames[0]]
        filas, fila_resumen = filas_datos_excel(hoja)
        cols = encabezado_viento(hoja, estacion)
        bloque = [f"\n{nombre} | estación afectada: {estacion} | resumen comienza en fila {fila_resumen}"]
        fechas_sueltas = []
        for fila in range((fila_resumen or hoja.max_row) + 1, hoja.max_row + 1):
            a = hoja.cell(fila, 1).value
            fecha = fecha_cruda(a)
            if fecha is None:
                continue
            n_num = sum(es_numero(hoja.cell(fila, col).value) for col in range(2, hoja.max_column + 1))
            no_vacios = [(openpyxl.utils.get_column_letter(col), hoja.cell(fila, col).value)
                         for col in range(2, hoja.max_column + 1) if hoja.cell(fila, col).value is not None]
            fechas_sueltas.append((fila, a, n_num, no_vacios))
        if fechas_sueltas:
            for fila, a, n_num, no_vacios in fechas_sueltas:
                bloque.append(f"  a) Fila {fila}: A={a!r}; celdas numéricas={n_num}; otras celdas no vacías={no_vacios}")
            bloque.append("     Vacía numéricamente: " + ("sí en todas las filas fechadas; no son mediciones numéricas." if all(x[2] == 0 for x in fechas_sueltas) else "NO: hay mediciones; revisar con prioridad."))
        else:
            bloque.append("  a) No se encontraron filas con fecha después del resumen.")

        rango_fechas = [fecha for _, fecha in filas]
        inicio, fin = min(rango_fechas), max(rango_fechas)
        fila_avg = next((r for r in range(6, hoja.max_row + 1) if hoja.cell(r, 1).value == "Avg"), None)
        para = []
        for variable in ("vel_viento", "dir_viento"):
            col = cols.get(variable)
            valores_crudos = [hoja.cell(fila, col).value for fila, _ in filas] if col else []
            numericos = [float(x) for x in valores_crudos if es_numero(x)]
            promedio_crudo = float(np.mean(numericos)) if numericos else np.nan
            valor_avg = hoja.cell(fila_avg, col).value if fila_avg and col else None
            valores_limpios = viento.loc[
                (viento["estacion_id"] == normalizar_id(estacion))
                & (viento["variable"] == variable)
                & viento["fecha"].between(inicio, fin), "valor"
            ].dropna()
            promedio_parquet = float(valores_limpios.mean()) if len(valores_limpios) else np.nan
            num_crudo, num_parquet = len(numericos), int(valores_limpios.count())
            diferencia = promedio_parquet - float(valor_avg) if es_numero(valor_avg) and not pd.isna(promedio_parquet) else np.nan
            coincide = num_crudo == num_parquet
            avg_ok = es_numero(valor_avg) and not pd.isna(diferencia) and abs(diferencia) <= 0.05
            estado_avg = "N/A (Avg vacío)" if not es_numero(valor_avg) else "sí" if avg_ok else "no"
            para.append(
                f"    {variable}: b) Excel={num_crudo}, parquet en {inicio.date()}..{fin.date()}={num_parquet}, "
                f"coinciden={coincide}; c) media Excel={promedio_crudo:.6g}, Avg Excel={valor_avg!r}, "
                f"media parquet={promedio_parquet:.6g}, delta(parquet-Avg)={diferencia:.6g}, tolerancia 0.05={estado_avg}"
            )
        bloque.extend(para)
        wb.close()
        bloques.extend(bloque)
    return "\n".join(bloques)


def informe_negativos(viento):
    """Lista velocidades negativas con contexto diario y concentración.

    Parámetros: tabla de viento. Devuelve detalle por observación y conteos.
    """
    pivot = viento.pivot(index=["fecha", "estacion_id", "estacion"], columns="variable", values="valor").reset_index()
    negativos = pivot[pivot["vel_viento"] < 0].copy().sort_values(["fecha", "estacion"])
    por_clave = pivot.set_index(["fecha", "estacion_id"])
    lineas = [f"\n3. VELOCIDADES NEGATIVAS ({len(negativos)})"]
    for _, fila in negativos.iterrows():
        sid, fecha = fila["estacion_id"], fila["fecha"]
        anterior = por_clave.loc[(fecha - pd.Timedelta(days=1), sid), "vel_viento"]
        siguiente = por_clave.loc[(fecha + pd.Timedelta(days=1), sid), "vel_viento"]
        origen = viento.loc[
            (viento.fecha == fecha) & (viento.estacion_id == sid) & (viento.variable == "vel_viento"),
            "archivo_origen",
        ].iloc[0]
        fmt = lambda x: "NaN" if pd.isna(x) else f"{x:g}"
        lineas.append(
            f"  {fecha:%Y-%m-%d} | {fila['estacion']} | {fila['vel_viento']:g} m/s | {origen} | "
            f"viento día anterior={fmt(anterior)}, posterior={fmt(siguiente)}, dirección ese día={fmt(fila['dir_viento'])}"
        )
    lineas.append("Concentración por estación: " + str(negativos["estacion"].value_counts().to_dict()))
    lineas.append("Concentración por año-mes: " + str(negativos["fecha"].dt.to_period("M").astype(str).value_counts().sort_index().to_dict()))
    return "\n".join(lineas)


def informe_direcciones_y_calma(viento):
    """Lista direcciones 0/360 y resume la codificación de velocidad cero.

    Parámetros: tabla de viento. Devuelve observaciones y conteos de calma.
    """
    pivot = viento.pivot(index=["fecha", "estacion_id", "estacion"], columns="variable", values="valor").reset_index()
    lineas = ["\n4. DIRECCIONES 0 Y 360"]
    cero = pivot[pivot["dir_viento"] == 0].sort_values(["fecha", "estacion"])
    trescientos_sesenta = pivot[pivot["dir_viento"] == 360].sort_values(["fecha", "estacion"])
    fmt = lambda x: "NaN" if pd.isna(x) else f"{x:g}"
    lineas.append(f"Dirección 0 ({len(cero)}):")
    for _, fila in cero.iterrows():
        lineas.append(f"  {fila.fecha:%Y-%m-%d} | {fila.estacion} | dir=0 | vel={fmt(fila.vel_viento)}")
    cero_con_vel_cero_o_nan = int((cero["vel_viento"].isna() | (cero["vel_viento"] == 0)).sum())
    lineas.append(f"Direcciones 0 con velocidad 0 o NaN: {cero_con_vel_cero_o_nan}/{len(cero)}")
    lineas.append(f"Dirección 360 ({len(trescientos_sesenta)}):")
    for _, fila in trescientos_sesenta.iterrows():
        lineas.append(f"  {fila.fecha:%Y-%m-%d} | {fila.estacion} | dir=360 | vel={fmt(fila.vel_viento)}")

    velocidades_cero = pivot[pivot["vel_viento"] == 0]
    conteos_direccion = {
        "NaN": int(velocidades_cero["dir_viento"].isna().sum()),
        "0": int((velocidades_cero["dir_viento"] == 0).sum()),
        "otro valor": int((velocidades_cero["dir_viento"].notna() & (velocidades_cero["dir_viento"] != 0)).sum()),
    }
    lineas.append(f"En todo el parquet: días-estación con vel_viento exactamente 0={len(velocidades_cero)}; dirección={conteos_direccion}")
    return "\n".join(lineas)


def informe_proximidad(viento, aire, coords):
    """Estima candidatas por distancia, cobertura coincidente y correlación espacial.

    Parámetros: viento, aire y mapa de coordenadas. Devuelve tablas y resumen por distancia.
    """
    lineas = ["\n5. VIENTO PARA MOVIL FONTIBON Y USME"]
    geo_lons = [v[1] for v in coords.values()]
    geo_lats = [v[2] for v in coords.values()]
    coordenadas_validas = all(-180 <= x <= 180 for x in geo_lons) and all(-90 <= y <= 90 for y in geo_lats)
    lineas.append(
        f"GeoJSON estaciones: longitudes {min(geo_lons):.6f}..{max(geo_lons):.6f}; "
        f"latitudes {min(geo_lats):.6f}..{max(geo_lats):.6f}; "
        f"orden de geometry.coordinates=[longitud, latitud]; en grados y rangos válidos={coordenadas_validas}."
    )
    id_to_name = {normalizar_id(est): est for est in viento["estacion"].unique()}
    id_to_coords = {sid: val for sid, val in coords.items()}
    estaciones_wind = sorted(id_to_name)
    dates = pd.date_range(DATE_START, DATE_END, freq="D")
    excl = ~dates.to_series(index=dates).between(EXCL_START, EXCL_END)
    mask_all = pd.Series(True, index=dates)
    mask_out = dates.to_series(index=dates).apply(lambda d: not (EXCL_START <= d <= EXCL_END))
    wind_wide = viento[viento["variable"] == "vel_viento"].pivot(index="fecha", columns="estacion_id", values="valor").reindex(dates)

    for objetivo in ("Movil Fontibon", "Usme"):
        target_id = normalizar_id(objetivo)
        if target_id not in id_to_coords:
            lineas.append(f"\n{objetivo}: no aparece en GeoJSON; distancias no calculables.")
            continue
        _, lon_t, lat_t = id_to_coords[target_id]
        distancias = []
        for sid in estaciones_wind:
            if sid not in id_to_coords:
                continue
            _, lon, lat = id_to_coords[sid]
            distancias.append((haversine_km(lon_t, lat_t, lon, lat), sid))
        candidatas = sorted(distancias)[:3]
        aire_obj = aire[(aire["estacion_id"] == target_id) & (aire["contaminante"].astype(str).str.upper().isin(["PM2.5", "PM2,5"]))]
        dias_pm = set(aire_obj.loc[aire_obj["valor"].notna(), "fecha"].dt.normalize())
        lineas.append(f"\n{objetivo}: coordenadas longitud={lon_t:.6f}, latitud={lat_t:.6f}; días con PM2.5={len(dias_pm)}.")
        for distancia, sid in candidatas:
            serie = wind_wide[sid]
            pct_todo = 100 * serie.notna().mean()
            pct_sin_hueco = 100 * serie.loc[mask_out].notna().mean()
            coinciden_pm = sorted(dias_pm)
            n_candidato = int(serie.reindex(coinciden_pm).notna().sum()) if coinciden_pm else 0
            pct_pm = 100 * n_candidato / len(coinciden_pm) if coinciden_pm else np.nan
            lineas.append(
                f"  {id_to_name[sid]}: {distancia:.3f} km; viento disponible periodo={pct_todo:.2f}%; "
                f"excluyendo hueco={pct_sin_hueco:.2f}%; coincide con PM2.5={n_candidato}/{len(coinciden_pm)} ({pct_pm:.2f}%)."
            )

    # Las distancias se calculan entre pares de estaciones de viento con coordenadas.
    pares = []
    for i, sid_a in enumerate(estaciones_wind):
        if sid_a not in id_to_coords:
            continue
        _, lon_a, lat_a = id_to_coords[sid_a]
        for sid_b in estaciones_wind[i + 1:]:
            if sid_b not in id_to_coords:
                continue
            _, lon_b, lat_b = id_to_coords[sid_b]
            distancia = haversine_km(lon_a, lat_a, lon_b, lat_b)
            valores = wind_wide[[sid_a, sid_b]].dropna()
            correlacion = valores[sid_a].corr(valores[sid_b]) if len(valores) >= 2 else np.nan
            pares.append((distancia, correlacion, sid_a, sid_b, len(valores)))
    lineas.append("\nCorrelación diaria de velocidad por distancia (parejas de estaciones; correlación Pearson, días completos por pareja):")
    bins = [
        (0, 3, "0–3 km"), (3, 6, "3–6 km"), (6, 10, "6–10 km"),
        (10, 15, "10–15 km"), (15, np.inf, ">15 km"),
    ]
    for minimo, maximo, etiqueta in bins:
        en_bin = [p for p in pares if minimo <= p[0] < maximo]
        validas = [p[1] for p in en_bin if not pd.isna(p[1])]
        media = float(np.mean(validas)) if validas else np.nan
        media_texto = f"{media:.4f}" if not pd.isna(media) else "NaN"
        lineas.append(f"  {etiqueta}: correlación media={media_texto}; parejas={len(en_bin)}; correlaciones válidas={len(validas)}")
    return "\n".join(lineas)


def main():
    """Calcula el informe de lectura y lo guarda sin tocar fuentes ni productos existentes.

    Parámetros: ninguno. Devuelve None e imprime/escribe el diagnóstico completo.
    """
    viento = pd.read_parquet(WIND_PARQUET)
    aire = pd.read_parquet(AIR_PARQUET)
    viento["fecha"] = pd.to_datetime(viento["fecha"]).dt.normalize()
    aire["fecha"] = pd.to_datetime(aire["fecha"]).dt.normalize()
    features, encoding = leer_geojson_estaciones()
    coords = coordenadas(features)
    secciones = [
        f"DIAGNÓSTICO DE VIENTO — decodificación GeoJSON: {encoding}",
        informe_faltantes(viento),
        informe_tres_libros(viento),
        informe_negativos(viento),
        informe_direcciones_y_calma(viento),
        informe_proximidad(viento, aire, coords),
        "\n5 LÍNEAS: DIFERENCIAS O DECISIONES HUMANAS",
        "1. Revisar los 14 valores de velocidad negativos y decidir si se documentan como errores crudos o como lecturas del sensor.",
        "2. Evaluar el uso de velocidades Guaymaral: el rótulo crudo de 2023 es 10M y puede afectar comparabilidad con otros sensores.",
        "3. Decidir si direcciones 0/360 deben interpretarse como norte o si combinadas con velocidad 0/NaN codifican calma.",
        "4. Movil Fontibon y Usme no tienen sensor de viento propio; decidir si usar una estación cercana según distancia, cobertura y PM2.5 coincidente.",
        "5. Revisar si la correlación espacial por distancia respalda compartir viento entre estaciones; el informe muestra los tamaños de muestra por rango.",
    ]
    informe = "\n\n".join(secciones) + "\n"
    REPORT_PATH.write_text(informe, encoding="utf-8")
    print(informe, end="")
    print(f"\nInforme completo guardado en: {REPORT_PATH}")


if __name__ == "__main__":
    main()
