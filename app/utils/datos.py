"""Carga datos y artefactos permitidos por la aplicación con caché.
Usa rutas relativas a la raíz del proyecto y solo accede a datos publicados,
documentación del proyecto y al modelo v2 del simulador y la evaluación.
No lee fuentes sin procesar ni crea o modifica archivos de datos.
"""
from pathlib import Path
import json
import joblib
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
APP_DATA = PROCESSED / "app"
GEO_DATA = PROCESSED / "geo"


def rutas_lectura_app() -> tuple[Path, ...]:
    """Devuelve las rutas de datos que esta app tiene permitido consultar."""
    return (
        PROCESSED / "aire_bogota_diario.parquet",
        PROCESSED / "asignacion_estaciones.csv",
        PROCESSED / "cobertura_maestra.csv",
        APP_DATA / "cobertura_estacion_mes.csv",
        APP_DATA / "metricas_modelos.csv",
        APP_DATA / "resumen_exploratorio.csv",
        APP_DATA / "predicciones_prueba_v2.parquet",
        APP_DATA / "diagnostico_modelo_metricas_v2.csv",
        APP_DATA / "diagnostico_modelo_mae_estacion_v2.csv",
        APP_DATA / "diagnostico_modelo_ablacion_v2.csv",
        APP_DATA / "diagnostico_modelo_permutacion_grupos_v2.csv",
        APP_DATA / "diagnostico_modelo_dependencia_parcial_v2.csv",
        APP_DATA / "diagnostico_modelo_cobertura_estacion_v2.csv",
        APP_DATA / "diagnostico_modelo_2_comparacion_climatologia_misma_prueba.csv",
        APP_DATA / "diagnostico_modelo_2_rf_guardado_sesgo_mae_estacion.csv",
        APP_DATA / "diagnostico_modelo_2_auditoria_filtraciones.csv",
        APP_DATA / "metricas_desglosadas.csv",
        GEO_DATA / "estaciones.geojson",
        GEO_DATA / "localidades.geojson",
        GEO_DATA / "estaciones_rmcab_ficha.csv",
        ROOT / "data" / "docs" / "fuentes.md",
        ROOT / "docs" / "decisiones.md",
        ROOT / "models" / "modelo_anomalia_v2.joblib",
        ROOT / "app" / "assets" / "style.css",
    )


@st.cache_data(show_spinner=False)
def cargar_aire() -> pd.DataFrame:
    """Lee una vez la tabla maestra procesada y normaliza su columna de fecha."""
    frame = pd.read_parquet(PROCESSED / "aire_bogota_diario.parquet")
    frame["fecha"] = pd.to_datetime(frame["fecha"])
    return frame


@st.cache_data(show_spinner=False)
def cargar_geojson_app(nombre: str) -> dict:
    """Lee geometrías generalizadas publicadas en processed/geo, nunca data/raw."""
    permitidos = {"estaciones.geojson", "localidades.geojson"}
    if nombre not in permitidos:
        raise ValueError(f"GeoJSON de app no permitido: {nombre}")
    return json.loads((GEO_DATA / nombre).read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def cargar_csv_app(nombre: str) -> pd.DataFrame:
    """Lee un CSV de app de una lista explícita para evitar rutas arbitrarias."""
    permitidos = {
        "cobertura_estacion_mes.csv",
        "metricas_modelos.csv",
        "resumen_exploratorio.csv",
        "diferencia_laboral_fin_semana.csv",
        "diagnostico_modelo_metricas_v2.csv",
        "diagnostico_modelo_mae_estacion_v2.csv",
        "diagnostico_modelo_ablacion_v2.csv",
        "diagnostico_modelo_permutacion_grupos_v2.csv",
        "diagnostico_modelo_dependencia_parcial_v2.csv",
        "diagnostico_modelo_cobertura_estacion_v2.csv",
        "diagnostico_modelo_2_comparacion_climatologia_misma_prueba.csv",
        "diagnostico_modelo_2_rf_guardado_sesgo_mae_estacion.csv",
        "diagnostico_modelo_2_auditoria_filtraciones.csv",
        "metricas_desglosadas.csv",
    }
    if nombre not in permitidos:
        raise ValueError(f"CSV de app no permitido: {nombre}")
    return pd.read_csv(APP_DATA / nombre)


@st.cache_data(show_spinner=False)
def cargar_parquet_app(nombre: str) -> pd.DataFrame:
    """Lee la evaluación v2 desde una lista cerrada de parquets publicados."""
    permitidos = {"predicciones_prueba_v2.parquet"}
    if nombre not in permitidos:
        raise ValueError(f"Parquet de app no permitido: {nombre}")
    return pd.read_parquet(APP_DATA / nombre)


@st.cache_data(show_spinner=False)
def cargar_tabla_maestra(nombre: str) -> pd.DataFrame:
    """Lee uno de los dos catálogos CSV disponibles en processed."""
    permitidos = {"asignacion_estaciones.csv", "cobertura_maestra.csv"}
    if nombre not in permitidos:
        raise ValueError(f"Catálogo no permitido: {nombre}")
    return pd.read_csv(PROCESSED / nombre)


@st.cache_data(show_spinner=False)
def cargar_ficha_estaciones() -> pd.DataFrame:
    """Lee la ficha SDA de las 19 estaciones, publicada como CSV nuevo de la app."""
    return pd.read_csv(GEO_DATA / "estaciones_rmcab_ficha.csv", dtype={"estacion_id": str})


@st.cache_data(show_spinner=False)
def cargar_markdown(tipo: str) -> str:
    """Lee solo los dos documentos aprobados para la metodología de la app."""
    rutas = {
        "fuentes": ROOT / "data" / "docs" / "fuentes.md",
        "decisiones": ROOT / "docs" / "decisiones.md",
    }
    if tipo not in rutas:
        raise ValueError(f"Documento no permitido: {tipo}")
    return rutas[tipo].read_text(encoding="utf-8")


@st.cache_resource(show_spinner=False)
def cargar_modelo_anomalia() -> dict:
    """Carga el Ridge v2 y su climatología para el futuro simulador."""
    # El RF v1 es grande, está ajustado con prueba y no se carga en la aplicación.
    return joblib.load(ROOT / "models" / "modelo_anomalia_v2.joblib")


def tabla_decisiones_vigentes(texto: str) -> pd.DataFrame:
    """Extrae la tabla consolidada DV-01... del comienzo de decisiones.md."""
    filas = []
    dentro = False
    for linea in texto.splitlines():
        limpia = linea.strip()
        if limpia.startswith("# Decisiones vigentes"):
            dentro = True
        if dentro and limpia.startswith("## "):
            break
        if not dentro or not limpia.startswith("|"):
            continue
        celdas = [celda.strip() for celda in limpia.strip("|").split("|")]
        if not celdas or celdas[0] in {"ID", "---"} or set(celdas[0]) <= {"-", ":"}:
            continue
        if celdas[0].startswith("DV-"):
            filas.append(celdas)
    columnas = ["ID", "Tema", "Decisión vigente", "Motivo", "Fecha original"]
    return pd.DataFrame(filas, columns=columnas) if filas else pd.DataFrame(columns=columnas)


def tabla_fuentes(texto: str) -> pd.DataFrame:
    """Convierte los campos etiquetados de fuentes.md en una tabla de lectura."""
    filas = []
    actual = None
    campos = {"Fuente": "Fuente", "Archivos": "Archivos", "Estructura": "Estructura", "Unidades observadas": "Unidades", "Transformación": "Transformación"}
    for linea in texto.splitlines():
        limpia = linea.strip()
        if limpia.startswith("# "):
            if actual:
                filas.append(actual)
            actual = {"Fuente": limpia[2:], "Archivos": "", "Estructura": "", "Unidades": "", "Transformación": ""}
        elif actual and limpia.startswith("- **"):
            clave, _, valor = limpia[4:].partition(":**")
            destino = campos.get(clave)
            if destino:
                actual[destino] = valor.strip()
    if actual:
        filas.append(actual)
    return pd.DataFrame(filas, columns=["Fuente", "Archivos", "Estructura", "Unidades", "Transformación"])
