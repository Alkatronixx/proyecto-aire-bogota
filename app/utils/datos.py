"""Carga datos y artefactos permitidos por la aplicación con caché.
Usa rutas relativas a la raíz del proyecto y solo accede a datos publicados,
documentación del proyecto y al modelo v2 del simulador y la evaluación.
No lee fuentes sin procesar ni crea o modifica archivos de datos.
"""
from pathlib import Path
import json
import re
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
        APP_DATA / "cobertura_estacion_mes.png",
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
def cargar_fechas_aire() -> pd.DataFrame:
    """Lee solo la fecha para páginas que necesitan periodo y conteo de filas."""
    # La página metodológica no analiza contaminantes; la proyección evita materializar 36 columnas innecesarias.
    frame = pd.read_parquet(PROCESSED / "aire_bogota_diario.parquet", columns=["fecha"])
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
def preparar_cobertura_estacion_mes() -> tuple[pd.DataFrame, list[str], list[str], pd.DataFrame]:
    """Lee la matriz compacta estación-mes precalculada para la figura."""
    matriz = cargar_csv_app("cobertura_estacion_mes.csv").set_index("estacion_id")
    matriz.index = matriz.index.astype(str)
    meses = matriz.columns.astype(str).tolist()
    estaciones = matriz.index.tolist()
    cobertura = matriz.rename_axis("estacion_id").reset_index()
    return cobertura, meses, estaciones, matriz


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


def rutas_markdown(tipo: str) -> tuple[Path, ...]:
    """Devuelve las rutas de documentación que alimentan la página metodológica."""
    rutas = {
        "fuentes": (ROOT / "data" / "docs" / "fuentes.md",),
        # El registro detallado contiene decisiones recientes; el documento raíz conserva el consolidado.
        "decisiones": (ROOT / "docs" / "decisiones.md", ROOT / "data" / "docs" / "decisiones.md"),
    }
    if tipo not in rutas:
        raise ValueError(f"Documento no permitido: {tipo}")
    return rutas[tipo]


def firma_markdown(tipo: str) -> tuple[int, ...]:
    """Forma una clave de caché que cambia cuando se modifica un documento fuente."""
    firma: list[int] = []
    for ruta in rutas_markdown(tipo):
        estado = ruta.stat()
        firma.extend((estado.st_mtime_ns, estado.st_size))
    return tuple(firma)


@st.cache_data(show_spinner=False)
def cargar_markdown(tipo: str, firma: tuple[int, ...] = ()) -> str:
    """Lee documentación aprobada; la firma invalida caché sin reiniciar la app."""
    return "\n\n".join(ruta.read_text(encoding="utf-8") for ruta in rutas_markdown(tipo))


@st.cache_resource(show_spinner=False)
def cargar_modelo_anomalia() -> dict:
    """Carga el Ridge v2 y su climatología para el futuro simulador."""
    # El RF v1 es grande, está ajustado con prueba y no se carga en la aplicación.
    return joblib.load(ROOT / "models" / "modelo_anomalia_v2.joblib")


@st.cache_data(show_spinner=False)
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


@st.cache_data(show_spinner=False)
def entradas_decisiones(texto: str) -> tuple[pd.DataFrame, list[str]]:
    """Extrae decisiones fechadas con distintos estilos Markdown y señala secciones incompletas."""
    patron = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2}):\s*(.+?)\s*$")
    secciones: list[tuple[str, str, list[str]]] = []
    avisos: list[str] = []
    fecha_actual: str | None = None
    titulo_actual: str | None = None
    cuerpo: list[str] = []

    def guardar() -> None:
        if fecha_actual is not None and titulo_actual is not None:
            secciones.append((fecha_actual, titulo_actual, cuerpo.copy()))

    for linea in texto.splitlines():
        if linea.startswith("## "):
            guardar()
            match = patron.match(linea.strip())
            if match:
                fecha_actual, titulo_actual = match.group(1), match.group(2).strip()
                cuerpo = []
            else:
                fecha_actual = titulo_actual = None
                cuerpo = []
                if re.match(r"^##\s+\d{4}-\d{2}-\d{2}", linea):
                    avisos.append(linea.strip())
            continue
        if fecha_actual is not None:
            cuerpo.append(linea)
    guardar()

    filas: list[dict[str, str]] = []
    vistos: set[tuple[str, str]] = set()
    for fecha, titulo, contenido in secciones:
        clave = (fecha, titulo.casefold())
        if clave in vistos:
            continue
        vistos.add(clave)
        decision = ""
        for linea in contenido:
            normalizada = re.sub(r"[*_`]+", "", linea).strip()
            match = re.match(r"^-\s*Decisión\s*:\s*(.+)$", normalizada, flags=re.IGNORECASE)
            if match:
                decision = match.group(1).strip()
                break
        if decision:
            filas.append({"Fecha": fecha, "Título": titulo, "Decisión": decision})
        else:
            avisos.append(f"{fecha}: {titulo}")

    tabla = pd.DataFrame(filas, columns=["Fecha", "Título", "Decisión"])
    if not tabla.empty:
        tabla = tabla.sort_values(["Fecha", "Título"], kind="stable").reset_index(drop=True)
    return tabla, avisos


@st.cache_data(show_spinner=False)
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
