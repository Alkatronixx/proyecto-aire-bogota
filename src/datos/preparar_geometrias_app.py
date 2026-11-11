"""Prepara GeoJSON compactos para las capas del mapa de la aplicación.
Lee estaciones y localidades de data/raw/geografia y los IDs de la tabla maestra.
Transforma localidades a WGS84, simplifica con topología preservada y redondea.
Escribe únicamente estaciones.geojson y localidades.geojson en data/processed/geo.
"""
import json
from pathlib import Path
import re
import unicodedata

import pandas as pd
import shapely
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Point, Polygon, mapping

ROOT = Path(__file__).resolve().parents[2]
FUENTE_GEO = ROOT / "data" / "raw" / "geografia"
SALIDA_GEO = ROOT / "data" / "processed" / "geo"
TOLERANCIA_GRADOS = 0.0005
PRECISION_GRADOS = 0.00001


def normalizar_nombre(nombre: str) -> str:
    """Normaliza acentos y signos para enlazar nombres de estación con su ID."""
    plano = "".join(c for c in unicodedata.normalize("NFKD", str(nombre))
                    if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", plano.lower())


def geojson(coleccion: str, features: list[dict]) -> dict:
    """Envuelve entidades como una colección GeoJSON declarada en WGS84."""
    return {
        "type": "FeatureCollection",
        "name": coleccion,
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }


def preparar_estaciones(maestro: pd.DataFrame) -> dict:
    """Añade estacion_id a los puntos y redondea coordenadas a cinco decimales."""
    ids = {normalizar_nombre(fila.estacion): fila.estacion_id
           for fila in maestro.itertuples(index=False)}
    origen = json.loads((FUENTE_GEO / "estacion_calida_aire.geojson").read_text(encoding="utf-8"))
    features = []
    encontrados = set()
    for entidad in origen["features"]:
        props = entidad["properties"]
        nombre = props["estacion"].strip()
        estacion_id = ids.get(normalizar_nombre(nombre))
        if estacion_id is None or estacion_id in encontrados:
            raise ValueError(f"No se pudo enlazar de forma única la estación {nombre!r}")
        encontrados.add(estacion_id)
        punto = shapely.set_precision(Point(entidad["geometry"]["coordinates"]), PRECISION_GRADOS)
        features.append({
            "type": "Feature",
            "properties": {"estacion_id": estacion_id, "estacion": nombre,
                           "es_movil": estacion_id.startswith("movil_")},
            "geometry": mapping(punto),
        })
    if encontrados != set(ids.values()):
        raise ValueError(f"Estaciones sin geometría: {sorted(set(ids.values()) - encontrados)}")
    return geojson("estaciones", features)


def area_firmada(anillo: list[list[float]]) -> float:
    """Usa la orientación de los anillos ArcGIS para separar exteriores y huecos."""
    return sum(anillo[i][0] * anillo[i + 1][1] - anillo[i + 1][0] * anillo[i][1]
               for i in range(len(anillo) - 1)) / 2


def poligono_arcgis(anillos: list[list[list[float]]]) -> Polygon | MultiPolygon:
    """Convierte anillos ArcGIS en polígonos con sus interiores asociados."""
    exteriores = [anillo for anillo in anillos if area_firmada(anillo) < 0]
    interiores = [anillo for anillo in anillos if area_firmada(anillo) >= 0]
    partes = [Polygon(exterior) for exterior in exteriores]
    for interior in interiores:
        poligono_hueco = Polygon(interior)
        candidatos = [(parte.area, indice) for indice, parte in enumerate(partes)
                      if parte.contains(poligono_hueco.representative_point())]
        if not candidatos:
            raise ValueError("Un anillo interior ArcGIS no quedó contenido en un exterior")
        _, indice = min(candidatos)
        partes[indice] = Polygon(partes[indice].exterior.coords,
                                 [*partes[indice].interiors, interior])
    return partes[0] if len(partes) == 1 else MultiPolygon(partes)


def preparar_localidades() -> dict:
    """Reproyecta, simplifica preservando topología y ajusta precisión de polígonos."""
    origen = json.loads((FUENTE_GEO / "localidades.geojson").read_text(encoding="utf-8"))
    transformar = Transformer.from_crs("EPSG:4686", "EPSG:4326", always_xy=True)

    def reproyectar(coordenadas):
        """Transforma lotes de coordenadas MAGNA-SIRGAS a longitud/latitud WGS84."""
        lon, lat = transformar.transform(coordenadas[:, 0], coordenadas[:, 1])
        import numpy as np
        return np.column_stack((lon, lat))

    features = []
    for entidad in origen["features"]:
        attrs = entidad["attributes"]
        geometria = poligono_arcgis(entidad["geometry"]["rings"])
        geometria = shapely.transform(geometria, reproyectar)
        geometria = geometria.simplify(TOLERANCIA_GRADOS, preserve_topology=True)
        geometria = shapely.set_precision(geometria, PRECISION_GRADOS, mode="valid_output")
        if geometria.is_empty or not geometria.is_valid:
            raise ValueError(f"La geometría de {attrs.get('LocNombre')} no es válida tras simplificar")
        features.append({
            "type": "Feature",
            "properties": {"localidad": attrs.get("LocNombre"),
                           "codigo": str(attrs.get("LocCodigo"))},
            "geometry": mapping(geometria),
        })
    return geojson("localidades", features)


def main() -> None:
    """Escribe las dos colecciones compactas sin tocar otras tablas o fuentes."""
    maestro = pd.read_parquet(ROOT / "data" / "processed" / "aire_bogota_diario.parquet",
                              columns=["estacion_id", "estacion"])
    maestro = maestro.drop_duplicates()
    SALIDA_GEO.mkdir(parents=True, exist_ok=True)
    colecciones = {"estaciones.geojson": preparar_estaciones(maestro),
                   "localidades.geojson": preparar_localidades()}
    for nombre, contenido in colecciones.items():
        destino = SALIDA_GEO / nombre
        destino.write_text(json.dumps(contenido, ensure_ascii=False, separators=(",", ":")),
                           encoding="utf-8")
        print(f"{destino.relative_to(ROOT)}: {destino.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
