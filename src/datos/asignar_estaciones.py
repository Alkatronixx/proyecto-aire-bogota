"""Asigna las estaciones IDEAM con cobertura suficiente a estaciones de aire.
Lee los parquets interim, el catálogo IDEAM y los GeoJSON de estaciones/localidades.
Produce data/processed/asignacion_estaciones.csv y reportes de cobertura espacial.
Las geometrías se interpretan en memoria; los archivos de origen permanecen intactos.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
AIR_GEO = RAW_DIR / "geografia" / "estacion_calida_aire.geojson"
LOCALITY_GEO = RAW_DIR / "geografia" / "localidades.geojson"
AIR_PARQUET = INTERIM_DIR / "aire_largo.parquet"
WIND_CITY_PARQUET = INTERIM_DIR / "viento_ciudad.parquet"
IDEAM_PARQUET = INTERIM_DIR / "ideam_largo.parquet"
IDEAM_CATALOG = PROCESSED_DIR / "estaciones_ideam.csv"
ASSIGNMENT_CSV = PROCESSED_DIR / "asignacion_estaciones.csv"
INICIO = pd.Timestamp("2023-10-24")
FIN = pd.Timestamp("2026-10-23")
# SUPUESTO/criterio del equipo: se exige al menos 85% de cobertura en los días
# con PM2.5 válido para reducir asignaciones cercanas con series demasiado incompletas.
UMBRAL_COBERTURA = 0.85
GRUPOS = {"precip": ("precip_mm",), "temp": ("tmax_c", "tmin_c")}
ESPERADO = {
    "precip": {
        "nueva_generacion": ["bolivia", "colina", "guaymaral", "suba"],
        "jardin_botanico": ["carvajal_sevillana", "centro_de_alto_rendimiento", "fontibon", "jazmin", "kennedy", "las_ferias", "minambiente", "movil_7ma", "movil_fontibon", "puente_aranda", "usaquen"],
        "colegio_san_cayetano": ["ciudad_bolivar", "san_cristobal", "tunal", "usme"],
    },
    "temp": {
        "nueva_generacion": ["bolivia", "centro_de_alto_rendimiento", "colina", "fontibon", "guaymaral", "las_ferias", "movil_fontibon", "suba", "usaquen"],
        "colegio_san_cayetano": ["carvajal_sevillana", "ciudad_bolivar", "jazmin", "kennedy", "minambiente", "movil_7ma", "puente_aranda", "san_cristobal", "tunal", "usme"],
    },
}


def normalizar_id(nombre: object) -> str:
    """Normaliza nombre de estación como los IDs del parquet de aire.

    Parámetros: nombre visible. Devuelve snake_case sin tildes ni signos.
    """
    texto = unicodedata.normalize("NFKD", str(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()
    texto = re.sub(r"[\s\-]+", "_", texto)
    return re.sub(r"[^a-z0-9_]", "", texto)


def _leer_json(ruta: Path) -> dict:
    """Lee JSON con fallbacks de codificación sin alterar el archivo fuente.

    Parámetros: ruta del GeoJSON. Devuelve el documento decodificado.
    """
    for codificacion in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return json.loads(ruta.read_bytes().decode(codificacion))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError(f"No se pudo decodificar {ruta}")


def _area_firmada(anillo: list[list[float]]) -> float:
    """Calcula el signo de orientación de un anillo del polígono.

    Parámetros: coordenadas del anillo. Devuelve el área firmada en grados cuadrados.
    """
    return sum(anillo[i][0] * anillo[(i + 1) % len(anillo)][1] - anillo[(i + 1) % len(anillo)][0] * anillo[i][1] for i in range(len(anillo))) / 2


def _en_anillo(lon: float, lat: float, anillo: list[list[float]]) -> bool:
    """Prueba inclusión punto-anillo por ray casting e incluye bordes.

    Parámetros: punto y anillo GeoJSON. Devuelve True si el punto cae en el anillo.
    """
    dentro = False
    for i in range(len(anillo) - 1):
        x1, y1 = anillo[i][:2]
        x2, y2 = anillo[i + 1][:2]
        cruz = (lon - x1) * (y2 - y1) - (lat - y1) * (x2 - x1)
        if abs(cruz) < 1e-12 and min(x1, x2) - 1e-12 <= lon <= max(x1, x2) + 1e-12 and min(y1, y2) - 1e-12 <= lat <= max(y1, y2) + 1e-12:
            return True
        if (y1 > lat) != (y2 > lat):
            x_corte = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < x_corte:
                dentro = not dentro
    return dentro


def _localidad_punto(lon: float, lat: float, localidades: list[dict]) -> str | float:
    """Busca la localidad cuyo polígono contiene el punto.

    Parámetros: coordenadas y polígonos ArcGIS. Devuelve nombre o NaN fuera de polígonos.
    """
    for lugar in localidades:
        anillos = lugar["anillos"]
        exteriores = [a for a in anillos if _area_firmada(a) < 0]
        huecos = [a for a in anillos if _area_firmada(a) >= 0]
        esta_dentro = any(_en_anillo(lon, lat, a) for a in exteriores)
        esta_en_hueco = any(_en_anillo(lon, lat, a) for a in huecos)
        if esta_dentro and not esta_en_hueco:
            return lugar["nombre"]
    return np.nan


def _leer_localidades() -> list[dict]:
    """Prepara polígonos de localidades desde el GeoJSON de Esri.

    Parámetros: ninguno. Devuelve nombre y anillos por localidad.
    """
    geo = _leer_json(LOCALITY_GEO)
    return [{"nombre": f["attributes"].get("LocNombre"), "anillos": f["geometry"].get("rings", [])} for f in geo.get("features", [])]


def _leer_aire(localidades: list[dict]) -> tuple[pd.DataFrame, list[str]]:
    """Lee los 19 puntos de aire y extrae altitud/localidad sin inferencias.

    Parámetros: polígonos de localidades. Devuelve estaciones y IDs sin altura.
    """
    geo = _leer_json(AIR_GEO)
    filas, sin_altura = [], []
    for feature in geo.get("features", []):
        props = feature.get("properties", {})
        nombre = str(props.get("estacion", "")).strip()
        lon, lat = feature["geometry"]["coordinates"][:2]
        raw_alt = props.get("altura")
        altitud = pd.to_numeric(pd.Series([raw_alt]), errors="coerce").iloc[0]
        codigo = normalizar_id(nombre)
        if pd.isna(altitud):
            sin_altura.append(nombre)
        filas.append({
            "estacion_id": codigo,
            "estacion": nombre,
            "es_movil": codigo in {"movil_7ma", "movil_fontibon"},
            "lat": float(lat),
            "lon": float(lon),
            "localidad": _localidad_punto(float(lon), float(lat), localidades),
            "altitud_m": float(altitud) if pd.notna(altitud) else np.nan,
        })
    return pd.DataFrame(filas), sin_altura


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia de gran círculo entre dos coordenadas.

    Parámetros: latitud-longitud de ambos puntos en grados. Devuelve kilómetros.
    """
    radio = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radio * math.asin(math.sqrt(a))


def _id_catalogo(valor: object) -> str:
    """Convierte códigos numéricos del CSV o strings parquet a texto comparable.

    Parámetros: código crudo. Devuelve identificador sin sufijo decimal.
    """
    try:
        return str(int(float(valor)))
    except (TypeError, ValueError):
        return str(valor).strip()


def _candidatos(catalogo: pd.DataFrame, diario: pd.DataFrame, fechas_pm: set[pd.Timestamp], grupo: str) -> list[dict]:
    """Calcula cobertura válida por candidata IDEAM para el grupo solicitado.

    Parámetros: catálogo, serie larga, días de PM2.5 y grupo. Devuelve candidatas completas.
    """
    variables = GRUPOS[grupo]
    subconjunto = diario.loc[diario.variable.isin(variables)].copy()
    subconjunto["estacion_ideam_id"] = subconjunto["estacion_ideam_id"].map(_id_catalogo)
    subconjunto["fecha"] = pd.to_datetime(subconjunto["fecha"]).dt.normalize()
    validas = subconjunto["valor"].notna() & subconjunto["flag_calidad"].fillna("").eq("")
    subconjunto["valor_valido"] = subconjunto["valor"].where(validas)
    tabla = subconjunto.pivot_table(index="fecha", columns=["estacion_ideam_id", "variable"], values="valor_valido", aggfunc="first")
    estaciones = catalogo.copy()
    estaciones["_id"] = estaciones["id"].map(_id_catalogo)
    estaciones["variables_disponibles"] = estaciones["variables_disponibles"].fillna("").map(lambda x: set(str(x).split(",")))
    filas = []
    for station in estaciones.to_dict("records"):
        codigo = station["_id"]
        if not bool(station["en_bogota"]) or not all(v in station["variables_disponibles"] for v in variables):
            continue
        if len(fechas_pm) == 0:
            cobertura = 0.0
        else:
            fechas_orden = sorted(fechas_pm)
            columnas = [(codigo, variable) for variable in variables]
            if any(col not in tabla.columns for col in columnas):
                cobertura = 0.0
            else:
                por_dia = tabla.reindex(fechas_orden)[columnas].notna().all(axis=1)
                cobertura = float(por_dia.mean())
        filas.append({**station, "cobertura": cobertura})
    return filas


def construir_asignacion() -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    """Asigna la estación válida más cercana y crea auditorías geográficas.

    Parámetros: ninguno. Devuelve asignación, catálogo geolocalizado, alturas faltantes y fuera de localidad.
    """
    localidades = _leer_localidades()
    aire, sin_altura = _leer_aire(localidades)
    catalogo = pd.read_csv(IDEAM_CATALOG)
    catalogo["id"] = catalogo["id"].map(_id_catalogo)
    catalogo_georef = catalogo.copy()
    catalogo_georef["localidad"] = catalogo_georef.apply(lambda r: _localidad_punto(float(r["lon"]), float(r["lat"]), localidades), axis=1)
    ideam = pd.read_parquet(IDEAM_PARQUET)
    pm = pd.read_parquet(AIR_PARQUET)
    pm["fecha"] = pd.to_datetime(pm["fecha"]).dt.normalize()
    pm25 = pm.loc[pm["contaminante"].astype(str).str.upper().eq("PM2.5")].copy()
    pm25["valor"] = pd.to_numeric(pm25["valor"], errors="coerce")
    pm25 = pm25.loc[pm25["valor"].ge(0) & pm25["valor"].notna() & pm25["fecha"].between(INICIO, FIN)]
    fechas_por_aire = pm25.groupby("estacion_id")["fecha"].apply(lambda s: set(s.tolist())).to_dict()
    resultados, no_asignadas = [], []
    for air in aire.to_dict("records"):
        air_id = air["estacion_id"]
        dias_pm = fechas_por_aire.get(air_id, set())
        fila = dict(air)
        for grupo in ("precip", "temp"):
            candidatos = _candidatos(catalogo, ideam, dias_pm, grupo)
            con_distancia = []
            for candidate in candidatos:
                candidate_lat = pd.to_numeric(pd.Series([candidate["lat"]]), errors="coerce").iloc[0]
                candidate_lon = pd.to_numeric(pd.Series([candidate["lon"]]), errors="coerce").iloc[0]
                distancia = haversine(air["lat"], air["lon"], float(candidate_lat), float(candidate_lon))
                con_distancia.append((distancia, candidate))
            validas = sorted((item for item in con_distancia if item[1]["cobertura"] >= UMBRAL_COBERTURA), key=lambda item: (item[0], item[1]["_id"]))
            if not validas:
                fila.update({f"{grupo}_estacion_id": np.nan, f"{grupo}_estacion": np.nan, f"{grupo}_dist_km": np.nan, f"{grupo}_cobertura_pct": np.nan})
                if grupo == "temp":
                    fila["elev_ideam_temp_m"] = np.nan
                no_asignadas.append((air_id, grupo, len(dias_pm), len(con_distancia)))
                continue
            distancia, escogida = validas[0]
            fila.update({
                f"{grupo}_estacion_id": escogida["_id"],
                f"{grupo}_estacion": escogida["nombre"],
                f"{grupo}_dist_km": distancia,
                f"{grupo}_cobertura_pct": 100 * escogida["cobertura"],
            })
            if grupo == "temp":
                fila["elev_ideam_temp_m"] = pd.to_numeric(pd.Series([escogida["elevacion"]]), errors="coerce").iloc[0]
        resultados.append(fila)
    asignacion = pd.DataFrame(resultados)
    orden = [
        "estacion_id", "estacion", "es_movil", "lat", "lon", "localidad", "altitud_m",
        "precip_estacion_id", "precip_estacion", "precip_dist_km", "precip_cobertura_pct",
        "temp_estacion_id", "temp_estacion", "temp_dist_km", "temp_cobertura_pct", "elev_ideam_temp_m",
    ]
    asignacion = asignacion[orden]
    fuera_localidad_aire = aire.loc[aire["localidad"].isna(), "estacion_id"].tolist()
    fuera_localidad_ideam = catalogo_georef.loc[catalogo_georef["localidad"].isna(), "id"].astype(str).tolist()
    print("\nLOCALIDAD Y en_bogota POR ESTACION IDEAM")
    print(catalogo_georef[["id", "nombre", "en_bogota", "localidad"]].to_string(index=False))
    print(f"\nEstaciones IDEAM fuera de cualquier localidad: {fuera_localidad_ideam or 'ninguna'}")
    print(f"Estaciones de aire fuera de cualquier localidad: {fuera_localidad_aire or 'ninguna'}")
    print(f"Altitud ausente en GeoJSON para estaciones de aire: {sin_altura or 'ninguna'}")
    print("\nASIGNACION COMPLETA")
    print(asignacion.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    if no_asignadas:
        print("\nSIN ASIGNACION CON UMBRAL DE COBERTURA")
        for air_id, grupo, n_pm, n_candidatas in no_asignadas:
            print(f"{air_id} / {grupo}: {n_candidatas} candidatas con variable; {n_pm} días PM2.5 válidos")
    ids_a_aire = {normalizar_id(nombre): air_id for air_id, nombre in zip(asignacion.estacion_id, asignacion.estacion)}
    inversas = {}
    for grupo in ("precip", "temp"):
        inversas[grupo] = {}
        for row in asignacion.itertuples(index=False):
            station = getattr(row, f"{grupo}_estacion_id")
            if pd.notna(station):
                inversas[grupo].setdefault(str(station), []).append(row.estacion_id)
        report_map = {station_name: sorted(ids_a_aire[x] for x in air_ids if x in ids_a_aire) for station_name, air_ids in ESPERADO[grupo].items()}
        for station_name, expected_air in report_map.items():
            actual_id = next((sid for sid, air_ids in inversas[grupo].items() if any(normalizar_id(x) == station_name for x in catalogo.loc[catalogo.id.eq(sid), "nombre"].tolist())), None)
            actual_air = sorted(inversas[grupo].get(actual_id, [])) if actual_id else []
            if actual_air != sorted(expected_air):
                print(f"DIFERENCIA VS ESPERADO {grupo} / {station_name}: esperado={sorted(expected_air)}; regla={actual_air}")
    return asignacion, catalogo_georef, sin_altura, fuera_localidad_ideam


def main() -> None:
    """Ejecuta la asignación IDEAM y escribe el CSV de salida.

    Parámetros: ninguno. Imprime mapas y escribe asignacion_estaciones.csv.
    """
    asignacion, _, _, _ = construir_asignacion()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    asignacion.to_csv(ASSIGNMENT_CSV, index=False, encoding="utf-8-sig")
    print(f"\nEscrito: {ASSIGNMENT_CSV}")


if __name__ == "__main__":
    main()
