"""Inspecciona y transforma los libros diarios y horarios del IDEAM.
Lee Excel de precipitación, temperaturas y humedad, más la geografía y aire.
Produce tablas IDEAM, cobertura, catálogo de estaciones y asignaciones espaciales.
La inspección completa se valida antes de escribir cualquier producto limpio.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
GEO_PATH = RAW_DIR / "geografia" / "estacion_calida_aire.geojson"
AIR_PATH = INTERIM_DIR / "aire_largo.parquet"
INICIO = pd.Timestamp("2023-10-24")
FIN = pd.Timestamp("2026-10-23")
VARIABLES_CARPETA = {
    "precipitacion": "precip_mm",
    "temperatura_max": "tmax_c",
    "temperatura_min": "tmin_c",
}
CARPETAS = (*VARIABLES_CARPETA, "humedad")
ETIQUETAS_META = {
    "nombre estacion": "nombre_estacion",
    "latitud": "lat",
    "longitud": "lon",
    "elevacion": "elevacion",
    "categoria de estacion": "categoria",
    "variable": "variable_fuente",
    "parametro": "parametro",
    "frecuencia": "frecuencia",
    "unidad medida": "unidad",
    "municipio": "municipio",
    "departamento": "departamento",
    "fecha consulta": "fecha_consulta",
}


def normalizar(texto: object) -> str:
    """Normaliza texto español para comparar campos y nombres.

    Parámetros: valor de una celda o nombre. Devuelve texto sin tildes y minúsculo.
    """
    valor = unicodedata.normalize("NFKD", str(texto))
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", valor.lower().strip().rstrip(":"))


def estacion_id(codigo: object) -> str:
    """Devuelve el código IDEAM como identificador estable.

    Parámetros: código de estación. Devuelve una cadena para preservar ceros.
    """
    return str(codigo).strip()


def _normalizar_id_aire(nombre: str) -> str:
    """Normaliza nombre geográfico igual que los identificadores de aire.

    Parámetros: nombre de estación de aire. Devuelve ID snake_case sin signos.
    """
    texto = re.sub(r"[\s\-]+", "_", normalizar(nombre))
    return re.sub(r"[^a-z0-9_]", "", texto)


def _parse_fecha_cruda(valor: object) -> pd.Timestamp:
    """Parsea fechas ISO explícitamente y el resto con la convención día primero.

    Parámetros: fecha cruda Excel. Devuelve Timestamp o NaT si no se reconoce.
    """
    if isinstance(valor, pd.Timestamp):
        return valor
    texto = str(valor).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}(?:\s|$)", texto):
        for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                # El formato ISO fija el orden año-mes-día; las fechas restantes
                # siguen la convención dayfirst=True establecida para el proyecto.
                return pd.to_datetime(texto, format=formato, dayfirst=True, errors="raise")
            except (ValueError, TypeError):
                continue
    return pd.to_datetime(texto, dayfirst=True, errors="coerce")


def _leer_metadatos(hoja) -> dict[str, object]:
    """Lee etiquetas terminadas en dos puntos y su siguiente valor a la derecha.

    Parámetros: hoja Excel. Devuelve los metadatos reconocidos por etiqueta.
    """
    metadatos = {}
    for fila in hoja.iter_rows():
        for celda in fila:
            if not isinstance(celda.value, str) or not celda.value.strip().endswith(":"):
                continue
            clave = ETIQUETAS_META.get(normalizar(celda.value))
            if clave is None:
                continue
            for derecha in fila[celda.column:]:
                if derecha.value is not None and str(derecha.value).strip():
                    metadatos[clave] = derecha.value
                    break
    return metadatos


def _leer_libro(ruta: Path) -> tuple[dict[str, object], list[dict[str, object]], list[str]]:
    """Lee metadatos y filas de datos con encabezado ubicado por contenido.

    Parámetros: ruta del libro. Devuelve metadatos, registros y errores estructurales.
    """
    errores = []
    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hoja = libro[libro.sheetnames[0]]
    # SUPUESTO técnico: varios Excel declaran A1 como dimensión usada aunque
    # contienen datos hasta miles de filas y seis columnas; se restablece el rango.
    hoja.reset_dimensions()
    metadatos = _leer_metadatos(hoja)
    fila_encabezado, encabezados = None, None
    filas = list(hoja.iter_rows(values_only=True))
    for numero, fila in enumerate(filas, start=1):
        if any(normalizar(v) == "fecha" for v in fila if v is not None):
            fila_encabezado = numero
            encabezados = [normalizar(v) if v is not None else "" for v in fila]
            break
    if fila_encabezado is None:
        libro.close()
        return metadatos, [], [f"No se encontró encabezado Fecha: {ruta}"]
    col_fecha = encabezados.index("fecha")
    col_valor = next((i for i, v in enumerate(encabezados) if v == "valor"), None)
    col_nivel = next((i for i, v in enumerate(encabezados) if v == "nivel de aprobacion"), None)
    if col_valor is None or col_nivel is None:
        libro.close()
        return metadatos, [], [f"Encabezado incompleto en {ruta}: {encabezados}"]
    registros = []
    for fila in filas[fila_encabezado:]:
        if not fila or all(v is None for v in fila):
            continue
        fecha = fila[col_fecha] if col_fecha < len(fila) else None
        if fecha is None:
            continue
        registros.append({
            "fecha_cruda": fecha,
            "valor_crudo": fila[col_valor] if col_valor < len(fila) else None,
            "nivel_aprobacion": fila[col_nivel] if col_nivel < len(fila) else None,
        })
    libro.close()
    return metadatos, registros, errores


def _archivo_info(ruta: Path, carpeta: str, metadatos: dict, registros: list[dict]) -> dict:
    """Completa campos derivados y resume rango observado del libro.

    Parámetros: ruta, carpeta, metadatos y filas leídas. Devuelve registro de inspección.
    """
    fechas = pd.DatetimeIndex([_parse_fecha_cruda(r["fecha_cruda"]) for r in registros])
    buenas = fechas[~pd.isna(fechas)]
    nombre = str(metadatos.get("nombre_estacion", "")).strip()
    nombre = re.sub(r"\s*\[\d+\]\s*$", "", nombre).strip()
    codigo = ruta.stem
    lat_texto, lon_texto = str(metadatos.get("lat", "")), str(metadatos.get("lon", ""))
    return {
        **metadatos,
        "archivo": ruta.name,
        "ruta": ruta,
        "carpeta": carpeta,
        "estacion_ideam_id": estacion_id(codigo),
        "estacion": nombre,
        "lat_original": lat_texto,
        "lon_original": lon_texto,
        "lat_coma_decimal": "," in lat_texto,
        "lon_coma_decimal": "," in lon_texto,
        "fecha_inicio_dato": buenas.min() if len(buenas) else pd.NaT,
        "fecha_fin_dato": buenas.max() if len(buenas) else pd.NaT,
        "fechas": fechas,
        "registros": registros,
    }


def _inspeccionar() -> tuple[list[dict], list[dict], dict[str, int]]:
    """Imprime inspección completa y detiene el proceso ante fallas de lectura.

    Parámetros: ninguno. Devuelve archivos inspeccionados, filas crudas y conteos.
    """
    archivos, errores, hashes = [], [], defaultdict(list)
    aprobaciones, no_numericos = Counter(), Counter()
    con_hora = Counter()
    filas_muestra = {}
    for carpeta in CARPETAS:
        rutas = sorted((RAW_DIR / carpeta).glob("*.xlsx"))
        print(f"\nCARPETA {carpeta}: {len(rutas)} archivos; patrón {carpeta}/<código>.xlsx; ejemplos {[p.name for p in rutas[:5]]}")
        for ruta in rutas:
            hashes[hashlib.sha256(ruta.read_bytes()).hexdigest()].append(str(ruta.relative_to(PROJECT_ROOT)))
            meta, registros, problemas = _leer_libro(ruta)
            errores.extend(problemas)
            if problemas:
                continue
            info = _archivo_info(ruta, carpeta, meta, registros)
            archivos.append(info)
            filas_muestra.setdefault(carpeta, (info, registros[:3], registros[-3:]))
            for registro in registros:
                if re.search(r"\b\d{1,2}:\d{2}\b", str(registro["fecha_cruda"])):
                    con_hora[carpeta] += 1
                nivel = registro["nivel_aprobacion"]
                aprobaciones["(vacío)" if nivel is None else str(nivel)] += 1
                valor = registro["valor_crudo"]
                if valor is not None:
                    try:
                        float(str(valor).strip().replace(",", "."))
                    except (TypeError, ValueError):
                        no_numericos[str(valor)] += 1
            fecha_mala = [r["fecha_cruda"] for r, d in zip(registros, info["fechas"]) if pd.isna(d)]
            if fecha_mala:
                errores.append(f"Fechas irreconocibles en {ruta}: {fecha_mala[:5]}")
            esperado = "maxima" if carpeta == "temperatura_max" else "minima" if carpeta == "temperatura_min" else None
            if esperado and esperado not in normalizar(meta.get("parametro", "")):
                errores.append(f"Parametro no coincide con {carpeta} en {ruta}: {meta.get('parametro')}")
            unidad = normalizar(meta.get("unidad", ""))
            unidades_validas = {"mm", "degc"} if carpeta != "humedad" else {"%", "porcentaje"}
            if unidad not in unidades_validas:
                errores.append(f"Unidad inesperada en {ruta}: {meta.get('unidad')}")
    duplicados = [grupo for grupo in hashes.values() if len(grupo) > 1]
    print("\nMETADATOS POR ARCHIVO")
    campos = ["estacion", "estacion_ideam_id", "categoria", "lat_original", "lon_original", "elevacion", "variable_fuente", "parametro", "frecuencia", "unidad", "municipio", "fecha_consulta", "fecha_inicio_dato", "fecha_fin_dato"]
    for info in archivos:
        print(" | ".join(str(info.get(c, "")) for c in campos))
    print("\nPARAMETROS COMPLETOS")
    for carpeta in ("precipitacion", "temperatura_max", "temperatura_min"):
        encontrados = sorted({str(a.get("parametro", "")) for a in archivos if a["carpeta"] == carpeta})
        print(f"{carpeta}: " + " || ".join(encontrados))
    print("\nMUESTRA DE FECHAS CRUDAS: primeras y últimas tres por carpeta")
    for carpeta, (info, primeras, ultimas) in filas_muestra.items():
        for etiqueta, grupo in (("primeras", primeras), ("ultimas", ultimas)):
            print(carpeta, etiqueta, [(repr(r["fecha_cruda"]), type(r["fecha_cruda"]).__name__) for r in grupo])
    print("\nNIVELES DE APROBACION", dict(aprobaciones))
    print("VALORES NO NUMERICOS", dict(no_numericos))
    print("FILAS FECHA CON HORA", dict(con_hora), "(en diarios es 00:00; en humedad son marcas horarias)")
    print("HASHES DUPLICADOS", duplicados)
    # La etiqueta 'Día pluviométrico (convencional)' no indica una hora concreta.
    print("UNIDADES UNICAS", {c: sorted({str(a.get('unidad')) for a in archivos if a['carpeta'] == c}) for c in CARPETAS})
    print("\nCOMPARACION FECHA CONSULTA vs DATOS")
    for info in archivos:
        rango = str(info.get("fecha_consulta", ""))
        consultadas = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", rango)
        if len(consultadas) == 2:
            c_ini, c_fin = pd.to_datetime(consultadas, dayfirst=True)
            if info["fecha_inicio_dato"].normalize() != c_ini.normalize() or info["fecha_fin_dato"].normalize() != c_fin.normalize():
                print(f"{info['archivo']}: consulta {c_ini.date()}..{c_fin.date()}, datos {info['fecha_inicio_dato'].date()}..{info['fecha_fin_dato'].date()}")
    if errores:
        print("\nBLOQUEOS DE INSPECCION")
        for error in errores:
            print(f"- {error}")
        raise RuntimeError("Etapa 1 detectó un bloqueo; no se escribió ningún producto.")
    return archivos, [r for a in archivos for r in a["registros"]], {"aprobaciones": sum(aprobaciones.values())}


def _cargar_datos(archivos: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Convierte filas de las fuentes diarias y horarias a tablas internas.

    Parámetros: lista inspeccionada. Devuelve tabla diaria, humedad horaria y contadores.
    """
    diarios, humedades = [], []
    fuera = Counter()
    for info in archivos:
        humedad = info["carpeta"] == "humedad"
        variable = VARIABLES_CARPETA.get(info["carpeta"])
        for registro, fecha in zip(info["registros"], info["fechas"]):
            if pd.isna(fecha):
                continue
            fecha = pd.Timestamp(fecha)
            valor_original = registro["valor_crudo"]
            texto_valor = valor_original if isinstance(valor_original, str) else str(valor_original)
            valor = pd.to_numeric(pd.Series([texto_valor.replace(",", ".")]), errors="coerce").iloc[0]
            if not INICIO <= fecha.normalize() <= FIN:
                fuera["humedad" if humedad else variable] += 1
                continue
            if humedad:
                humedades.append({
                    "fecha_hora": fecha, "estacion_ideam_id": info["estacion_ideam_id"],
                    "estacion": info["estacion"], "humedad_original": valor_original,
                    "humedad_pct": valor, "archivo_origen": info["archivo"],
                })
            else:
                diarios.append({
                    "fecha": fecha.normalize(), "estacion_ideam_id": info["estacion_ideam_id"],
                    "estacion": info["estacion"], "variable": variable, "valor": valor,
                    "valor_original": valor_original, "nivel_aprobacion": registro["nivel_aprobacion"],
                    "flag_calidad": "", "archivo_origen": info["archivo"],
                })
    print("\nFILAS FUERA DEL PERIODO", dict(fuera))
    diario = pd.DataFrame(diarios)
    humedad_horaria = pd.DataFrame(humedades)
    return diario, humedad_horaria, dict(fuera)


def _resolver_duplicados(diario: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Elimina duplicados no conflictivos y conserva valor frente a NaN.

    Parámetros: tabla diaria larga. Devuelve filas únicas y conflictos sin resolver.
    """
    llave = ["fecha", "estacion_ideam_id", "variable"]
    conservadas, conflictos = [], []
    for clave, grupo in diario.groupby(llave, dropna=False, sort=False):
        validas = grupo.loc[grupo["valor"].notna()]
        distintos = validas["valor"].drop_duplicates()
        if len(distintos) > 1:
            conflictos.append({**dict(zip(llave, clave)), "valores": sorted(distintos.tolist()), "archivos": ", ".join(validas["archivo_origen"].astype(str).unique())})
            conservadas.extend(grupo.to_dict("records"))
        elif len(validas):
            conservadas.append(validas.iloc[0].to_dict())
        else:
            conservadas.append(grupo.iloc[0].to_dict())
    return pd.DataFrame(conservadas), pd.DataFrame(conflictos)


def _aplicar_banderas(diario: pd.DataFrame) -> pd.DataFrame:
    """Añade banderas sin alterar los valores numéricos recibidos.

    Parámetros: tabla diaria deduplicada. Devuelve la tabla con flag_calidad.
    """
    salida = diario.copy()
    for indice, fila in salida.iterrows():
        valor, variable = fila["valor"], fila["variable"]
        if pd.isna(valor):
            continue
        banderas = []
        if valor <= -99 or valor >= 9999:
            banderas.append("centinela")
        if variable == "precip_mm":
            if valor < 0:
                banderas.append("precipitacion_negativa")
            if valor > 150:
                banderas.append("precipitacion_mayor_150")
        elif variable in {"tmax_c", "tmin_c"} and (valor < -5 or valor > 35):
            banderas.append("temperatura_fuera_rango")
        salida.at[indice, "flag_calidad"] = ";".join(banderas)
    maximos = salida.loc[salida.variable.eq("tmax_c")].set_index(["fecha", "estacion_ideam_id"])["valor"]
    minimos = salida.loc[salida.variable.eq("tmin_c")].set_index(["fecha", "estacion_ideam_id"])["valor"]
    pares = pd.concat([maximos.rename("max"), minimos.rename("min")], axis=1).dropna()
    mal = pares.index[pares["max"] < pares["min"]]
    for variable in ("tmax_c", "tmin_c"):
        mascara = salida.variable.eq(variable) & pd.MultiIndex.from_frame(salida[["fecha", "estacion_ideam_id"]]).isin(mal)
        salida.loc[mascara, "flag_calidad"] = salida.loc[mascara, "flag_calidad"].map(lambda x: ";".join(filter(None, [x, "tmax_menor_tmin"])))
    return salida


def _rangos_faltantes(fechas: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """Agrupa fechas consecutivas faltantes en rangos de al menos siete días.

    Parámetros: índice diario de faltantes. Devuelve inicio, fin y duración.
    """
    if len(fechas) == 0:
        return []
    dias = sorted(pd.DatetimeIndex(fechas).normalize().unique())
    rangos, inicio, previo = [], dias[0], dias[0]
    for dia in dias[1:]:
        if dia != previo + pd.Timedelta(days=1):
            n = (previo - inicio).days + 1
            if n >= 7:
                rangos.append((inicio, previo, n))
            inicio = dia
        previo = dia
    n = (previo - inicio).days + 1
    if n >= 7:
        rangos.append((inicio, previo, n))
    return rangos


def _cobertura(diario: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula cobertura mensual y resumen de NaN y huecos largos.

    Parámetros: tabla diaria larga. Devuelve tabla mensual y tabla resumen impresa.
    """
    fechas = pd.date_range(INICIO, FIN, freq="D")
    mensual, resumen = [], []
    for (codigo, variable), grupo in diario.groupby(["estacion_ideam_id", "variable"]):
        serie = grupo.drop_duplicates("fecha").set_index("fecha")["valor"].reindex(fechas)
        nombre = grupo["estacion"].iloc[0]
        for periodo in pd.period_range(INICIO, FIN, freq="M"):
            dias_mes = pd.date_range(max(periodo.start_time.normalize(), INICIO), min(periodo.end_time.normalize(), FIN), freq="D")
            datos = int(serie.reindex(dias_mes).notna().sum())
            mensual.append({"estacion_ideam_id": codigo, "estacion": nombre, "variable": variable, "anio_mes": str(periodo), "dias_con_dato": datos, "porcentaje_mes": 100 * datos / len(dias_mes)})
        disponibles = serie.dropna().index
        faltantes = serie.index[serie.isna()]
        rangos = _rangos_faltantes(faltantes)
        resumen.append({
            "estacion_ideam_id": codigo, "estacion": nombre, "variable": variable,
            "porcentaje_nan": 100 * float(serie.isna().mean()),
            "primera_fecha_con_dato": disponibles.min() if len(disponibles) else pd.NaT,
            "ultima_fecha_con_dato": disponibles.max() if len(disponibles) else pd.NaT,
            "rangos_sin_dato_7d": "; ".join(f"{a.date()}..{b.date()} ({n} d)" for a, b, n in rangos) or "ninguno",
        })
    return pd.DataFrame(mensual), pd.DataFrame(resumen)


def _leer_geojson() -> list[dict]:
    """Lee estaciones de aire intentando codificaciones comunes en memoria.

    Parámetros: ninguno. Devuelve nombre, identificador y coordenadas por estación.
    """
    texto = None
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = GEO_PATH.read_bytes().decode(codificacion)
            geo = json.loads(texto)
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    if texto is None:
        raise ValueError(f"No se pudo leer {GEO_PATH} con las codificaciones previstas")
    estaciones = []
    for feature in geo["features"]:
        nombre = feature["properties"].get("estacion", "").strip()
        lon, lat = feature["geometry"]["coordinates"][:2]
        estaciones.append({"estacion_aire": nombre, "estacion_aire_id": _normalizar_id_aire(nombre), "lat_aire": float(lat), "lon_aire": float(lon)})
    return estaciones


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distancia de gran círculo en kilómetros.

    Parámetros: dos pares latitud-longitud en grados. Devuelve km.
    """
    radio = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radio * math.asin(math.sqrt(a))


def _asignaciones(archivos: list[dict], diario: pd.DataFrame) -> pd.DataFrame:
    """Imprime tres estaciones IDEAM por variable para cada estación de aire.

    Parámetros: metadatos IDEAM y tabla diaria. Devuelve asignaciones con cobertura.
    """
    aires = _leer_geojson()
    aire = pd.read_parquet(AIR_PATH)
    aire["fecha"] = pd.to_datetime(aire["fecha"]).dt.normalize()
    aire = aire.loc[aire["contaminante"].astype(str).str.upper().eq("PM2.5") & aire["valor"].notna()]
    coord_por_id = {a["estacion_aire_id"]: a for a in aires}
    for air_id in aire["estacion_id"].unique():
        if air_id not in coord_por_id:
            nombre = aire.loc[aire.estacion_id.eq(air_id), "estacion"].iloc[0]
            coord_por_id[air_id] = {"estacion_aire": nombre, "estacion_aire_id": air_id, "lat_aire": np.nan, "lon_aire": np.nan}
    catalogo = {}
    for info in archivos:
        codigo = info["estacion_ideam_id"]
        catalogo[codigo] = info
    fechas_aire = aire.groupby("estacion_id")["fecha"].apply(set).to_dict()
    series = diario.pivot_table(index="fecha", columns=["estacion_ideam_id", "variable"], values="valor", aggfunc="first")
    asignadas = []
    for air_id, fechas_pm in fechas_aire.items():
        air_meta = coord_por_id[air_id]
        for variable in VARIABLES_CARPETA.values():
            disponibles = []
            for codigo, meta in catalogo.items():
                if not any(a["estacion_ideam_id"] == codigo and VARIABLES_CARPETA.get(a["carpeta"]) == variable for a in archivos):
                    continue
                lat, lon = pd.to_numeric(meta.get("lat"), errors="coerce"), pd.to_numeric(meta.get("lon"), errors="coerce")
                if pd.isna(lat) or pd.isna(lon) or pd.isna(air_meta["lat_aire"]):
                    continue
                dist = _haversine(float(air_meta["lat_aire"]), float(air_meta["lon_aire"]), float(lat), float(lon))
                col = (codigo, variable)
                valores = series[col] if col in series.columns else pd.Series(dtype=float)
                # El denominador incluye todos los días de PM2.5, también cuando
                # el archivo IDEAM termina antes y ya no contiene filas para esas fechas.
                pct = 100 * valores.reindex(list(fechas_pm)).notna().mean() if fechas_pm else 0.0
                disponibles.append((dist, codigo, meta, pct, len(fechas_pm)))
            for rango, (dist, codigo, meta, pct, ndias) in enumerate(sorted(disponibles)[:3], start=1):
                asignadas.append({"estacion_aire_id": air_id, "estacion_aire": air_meta["estacion_aire"], "variable": variable, "rango": rango, "estacion_ideam_id": codigo, "estacion_ideam": meta["estacion"], "distancia_km": dist, "porcentaje_dato_en_dias_pm25": pct, "dias_pm25_comparables": ndias})
    resultado = pd.DataFrame(asignadas)
    print("\nTRES ESTACIONES IDEAM MAS CERCANAS POR ESTACION AIRE Y VARIABLE")
    for (air, var), grupo in resultado.groupby(["estacion_aire", "variable"], sort=True):
        texto = "; ".join(f"{r.estacion_ideam} ({r.distancia_km:.2f} km, {r.porcentaje_dato_en_dias_pm25:.1f}% cobertura)" for r in grupo.itertuples())
        print(f"{air} / {var}: {texto}")
    return resultado


def _correlaciones_parejas(diario: pd.DataFrame, archivos: list[dict]) -> pd.DataFrame:
    """Resume correlaciones diarias entre estaciones IDEAM por distancia.

    Parámetros: tabla diaria y metadatos. Devuelve promedios y medianas de pares.
    """
    datos = diario.pivot_table(index="fecha", columns=["estacion_ideam_id", "variable"], values="valor", aggfunc="first")
    coordenadas = {}
    for meta in archivos:
        coordenadas[meta["estacion_ideam_id"]] = (float(str(meta["lat"]).replace(",", ".")), float(str(meta["lon"]).replace(",", ".")))
    bins = [(0, 3, "0-3 km"), (3, 6, "3-6 km"), (6, 10, "6-10 km"), (10, 15, "10-15 km"), (15, math.inf, ">15 km")]
    salida = []
    for variable in VARIABLES_CARPETA.values():
        codigos = [c for c in coordenadas if (c, variable) in datos.columns]
        medidas = [("valor", False)] + ([ ("lluvia_ge_1mm", True) ] if variable == "precip_mm" else [])
        if variable == "precip_mm":
            for codigo in codigos:
                precipitacion = datos[(codigo, variable)]
                datos[(codigo, "lluvia_ge_1mm")] = precipitacion.ge(1).where(precipitacion.notna()).astype(float)
        for medida, es_lluvia in medidas:
            por_bin = defaultdict(list)
            for i, codigo_a in enumerate(codigos):
                for codigo_b in codigos[i + 1:]:
                    lat1, lon1 = coordenadas[codigo_a]; lat2, lon2 = coordenadas[codigo_b]
                    distancia = _haversine(lat1, lon1, lat2, lon2)
                    colname = "lluvia_ge_1mm" if es_lluvia else variable
                    a, b = datos[(codigo_a, colname)], datos[(codigo_b, colname)]
                    pares = pd.concat([a, b], axis=1).dropna()
                    if len(pares) < 2:
                        continue
                    r = pares.iloc[:, 0].corr(pares.iloc[:, 1])
                    if pd.isna(r):
                        continue
                    for inferior, superior, etiqueta in bins:
                        if distancia > inferior and distancia <= superior:
                            por_bin[etiqueta].append((r, len(pares)))
                            break
            for _, _, etiqueta in bins:
                muestras = por_bin[etiqueta]
                salida.append({"variable": variable, "medida": medida, "rango_distancia": etiqueta,
                               "correlacion_media": np.mean([x[0] for x in muestras]) if muestras else np.nan,
                               "correlacion_mediana": np.median([x[0] for x in muestras]) if muestras else np.nan,
                               "n_parejas": len(muestras), "dias_comparables_suma": sum(x[1] for x in muestras)})
    resultado = pd.DataFrame(salida)
    print("\nCORRELACIONES ENTRE PAREJAS IDEAM POR DISTANCIA")
    print(resultado.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    return resultado


def _catalogo_estaciones(archivos: list[dict]) -> pd.DataFrame:
    """Crea catálogo único y marca estaciones dentro de la caja de Bogotá.

    Parámetros: metadatos de archivos. Devuelve catálogo deduplicado por código.
    """
    por_codigo = {}
    for info in archivos:
        codigo = info["estacion_ideam_id"]
        if codigo not in por_codigo:
            lat = pd.to_numeric(pd.Series([info.get("lat")]).str.replace(",", ".", regex=False), errors="coerce").iloc[0]
            lon = pd.to_numeric(pd.Series([info.get("lon")]).str.replace(",", ".", regex=False), errors="coerce").iloc[0]
            elev = pd.to_numeric(pd.Series([info.get("elevacion")]).str.replace(",", ".", regex=False), errors="coerce").iloc[0]
            por_codigo[codigo] = {"id": codigo, "nombre": info["estacion"], "categoria": info.get("categoria"), "lat": lat, "lon": lon, "elevacion": elev, "municipio": info.get("municipio"), "variables": set()}
        variable = VARIABLES_CARPETA.get(info["carpeta"], "humedad")
        por_codigo[codigo]["variables"].add(variable)
    filas = []
    for item in por_codigo.values():
        lat, lon = item["lat"], item["lon"]
        # SUPUESTO: en_bogota usa la caja de coordenadas exigida por controles,
        # porque Nazareth aparece en metadatos IDEAM como municipio Bogotá pero
        # queda fuera de esa caja; no se infiere un límite administrativo.
        en_bogota = bool(pd.notna(lat) and pd.notna(lon) and 4.3 <= lat <= 5.0 and -74.4 <= lon <= -73.8)
        filas.append({**item, "variables_disponibles": ",".join(sorted(item["variables"])), "en_bogota": en_bogota})
    catalogo = pd.DataFrame(filas).drop(columns="variables")
    return catalogo


def _humedad_diaria(horaria: pd.DataFrame) -> pd.DataFrame:
    """Agrega humedad horaria por estación y día solo para exploración.

    Parámetros: observaciones horarias crudas convertidas. Devuelve resumen diario.
    """
    if horaria.empty:
        return pd.DataFrame(columns=["fecha", "estacion_ideam_id", "estacion", "media", "minimo", "maximo", "n_horas_con_dato"])
    datos = horaria.copy()
    datos["fecha"] = datos["fecha_hora"].dt.normalize()
    return datos.groupby(["fecha", "estacion_ideam_id", "estacion"], as_index=False).agg(
        media=("humedad_pct", "mean"), minimo=("humedad_pct", "min"), maximo=("humedad_pct", "max"),
        n_horas_con_dato=("humedad_pct", "count"),
    )


def main() -> None:
    """Ejecuta inspección, control de duplicados y productos IDEAM reproducibles.

    Parámetros: ninguno. Imprime diagnósticos y escribe parquets/CSV en interim/processed.
    """
    archivos, _, _ = _inspeccionar()
    diario, humedad_horaria, fuera = _cargar_datos(archivos)
    filas_antes_duplicados = len(diario)
    diario, conflictos = _resolver_duplicados(diario)
    print(f"\nFILAS DUPLICADAS NO CONFLICTIVAS RETIRADAS: {filas_antes_duplicados - len(diario)}")
    if not conflictos.empty:
        print("\nCONFLICTOS NUMERICOS REALES (no resueltos)")
        print(conflictos.to_string(index=False))
        raise RuntimeError("Hay conflictos numéricos que no se resolverán automáticamente; no se escribieron productos.")
    print("CONFLICTOS NUMERICOS REALES: ninguno")
    diario = _aplicar_banderas(diario)
    cob, resumen = _cobertura(diario)
    catalogo = _catalogo_estaciones(archivos)
    humedad_diaria = _humedad_diaria(humedad_horaria)
    print("\nCOBERTURA POR ESTACION Y VARIABLE")
    print(resumen.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print("\nBANDERAS DE CALIDAD (una fila puede tener más de una)")
    print(diario.assign(_bandera=diario.flag_calidad.str.split(";")).explode("_bandera").query("_bandera != ''").groupby(["variable", "_bandera"]).size().to_string())
    print("\nHUMEDAD 2025 Y COBERTURA POR ESTACION")
    if humedad_diaria.empty:
        print("Sin observaciones horarias dentro del periodo.")
    else:
        for codigo, grupo in humedad_diaria.groupby("estacion_ideam_id"):
            anios = sorted(grupo.loc[grupo.n_horas_con_dato.gt(0), "fecha"].dt.year.unique().tolist())
            print(f"{codigo} {grupo.estacion.iloc[0]}: años={anios}; datos 2025={bool((grupo.fecha.dt.year == 2025).any())}")
    _asignaciones(archivos, diario)
    _correlaciones_parejas(diario, archivos)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    diario[["fecha", "estacion_ideam_id", "estacion", "variable", "valor", "valor_original", "nivel_aprobacion", "flag_calidad", "archivo_origen"]].to_parquet(INTERIM_DIR / "ideam_largo.parquet", index=False, engine="pyarrow")
    humedad_diaria.to_parquet(INTERIM_DIR / "ideam_humedad_diaria.parquet", index=False, engine="pyarrow")
    catalogo[["id", "nombre", "categoria", "lat", "lon", "elevacion", "municipio", "variables_disponibles", "en_bogota"]].to_csv(PROCESSED_DIR / "estaciones_ideam.csv", index=False, encoding="utf-8-sig")
    cob.to_csv(PROCESSED_DIR / "cobertura_ideam.csv", index=False, encoding="utf-8-sig")
    print(f"\nFilas diarias IDEAM: {len(diario)}; filas humedad diaria: {len(humedad_diaria)}; filas fuera del periodo: {fuera}")
    print(f"Escritos: {INTERIM_DIR / 'ideam_largo.parquet'}; {INTERIM_DIR / 'ideam_humedad_diaria.parquet'}; {PROCESSED_DIR / 'estaciones_ideam.csv'}; {PROCESSED_DIR / 'cobertura_ideam.csv'}")


if __name__ == "__main__":
    main()
