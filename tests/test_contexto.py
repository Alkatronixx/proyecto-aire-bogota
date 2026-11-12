"""Verifica la ficha de estaciones y los resúmenes normativos de Contexto.
Lee exclusivamente los productos procesados y las constantes oficiales publicadas.
Comprueba la correspondencia de IDs y los porcentajes de superación por estación.
Ejecuta la página en el motor de pruebas de Streamlit para detectar errores de render.
"""

import pandas as pd
from streamlit.testing.v1 import AppTest

from app.utils.contexto import calcular_superaciones
from app.utils.datos import ROOT, cargar_aire, cargar_ficha_estaciones
from app.utils import fuentes_contexto as fuentes


IDS_MAESTROS = {
    "guaymaral", "usaquen", "suba", "bolivia", "las_ferias",
    "centro_de_alto_rendimiento", "movil_7ma", "minambiente", "fontibon",
    "puente_aranda", "kennedy", "carvajal_sevillana", "tunal",
    "san_cristobal", "jazmin", "usme", "ciudad_bolivar", "colina",
    "movil_fontibon",
}


def test_ficha_tiene_las_19_estaciones_maestras() -> None:
    """Exige una fila por estación real y conserva la bandera de Las Ferias."""
    ficha = cargar_ficha_estaciones()
    aire = cargar_aire()
    ids = set(aire.estacion_id.astype(str).unique())
    assert len(ficha) == 19
    assert ids == IDS_MAESTROS
    assert set(ficha.estacion_id) == ids
    assert ficha.loc[ficha.estacion_id.eq("las_ferias"), "verificar"].iloc[0]


def test_porcentajes_de_superacion_se_mantienen_entre_cero_y_cien() -> None:
    """Valida los cuatro porcentajes por estación calculados con datos observados."""
    resumen = calcular_superaciones(cargar_aire(), fuentes.DIAS_MINIMOS_PROMEDIO_ANUAL)
    columnas = [
        "pct_pm25_mayor_15_periodo", "pct_pm25_mayor_37_periodo",
        "pct_pm25_mayor_15_12m", "pct_pm25_mayor_37_12m",
    ]
    for columna in columnas:
        valores = resumen[columna].dropna()
        assert valores.between(0, 100).all()


def test_constantes_oficiales_coinciden_con_las_cifras_verificadas() -> None:
    """Fija los valores proporcionados y verificados para evitar alteraciones casuales."""
    assert fuentes.POBLACION_BOGOTA_2025 == 7_937_898
    assert (fuentes.ESTACIONES_SDA, fuentes.MICROSENSORES_SDA) == (19, 70)
    assert (
        fuentes.OMS_PM25_ANUAL, fuentes.OMS_PM25_24H,
        fuentes.OMS_PM10_ANUAL, fuentes.OMS_PM10_24H,
    ) == (5, 15, 15, 45)
    assert (
        fuentes.COLOMBIA_PM25_ANUAL_2018_2029,
        fuentes.COLOMBIA_PM25_24H_2018_2029,
        fuentes.COLOMBIA_PM10_ANUAL_2018_2029,
        fuentes.COLOMBIA_PM10_24H_2018_2029,
    ) == (25, 37, 50, 75)
    assert (
        fuentes.COLOMBIA_PM25_ANUAL_2030,
        fuentes.COLOMBIA_PM10_ANUAL_2030,
        fuentes.COLOMBIA_PM25_PREVENCION,
        fuentes.COLOMBIA_PM25_ALERTA,
        fuentes.COLOMBIA_PM25_EMERGENCIA,
    ) == (15, 30, "38–55", "56–150", "≥151")
    assert (
        fuentes.OMS_ANIO_GUIA,
        fuentes.COLOMBIA_ANIO_RESOLUCION,
        fuentes.COLOMBIA_ANIO_INICIO_NORMA,
        fuentes.COLOMBIA_ANIO_FIN_NORMA,
        fuentes.COLOMBIA_FECHA_INICIO_24H,
    ) == (2021, 2017, 2018, 2029, "2018-07-01")
    assert fuentes.OMS_DIAS_EXCEDENCIA_24H == (3, 4)
    assert fuentes.DIAS_MINIMOS_PROMEDIO_ANUAL == 274
    assert fuentes.FUENTES and all(fuente["url"].startswith("https://") for fuente in fuentes.FUENTES)
    assert [fila["Categoría"] for fila in fuentes.ICA_24H_PM] == [
        "Buena", "Aceptable", "Dañina a grupos sensibles", "Dañina a la salud",
        "Muy dañina", "Peligrosa",
    ]
    assert [fila["PM2.5 24 h (µg/m³)"] for fila in fuentes.ICA_24H_PM] == [
        "0–12", "13–37", "38–55", "56–150", "151–250", "251–500",
    ]
    assert [fila["PM10 24 h (µg/m³)"] for fila in fuentes.ICA_24H_PM] == [
        "0–54", "55–154", "155–254", "255–354", "355–424", "425–604",
    ]
    assert fuentes.URL_IDEAM_ICA_24H in [f["url"] for f in fuentes.FUENTES]
    assert fuentes.URL_SALUD_PM25_AIRQ in [f["url"] for f in fuentes.FUENTES]
    assert all(f["fecha_consulta"] == "2026-11-11" for f in fuentes.FUENTES[-3:])
    assert [fila["Riesgo relativo (IC 95 %)"] for fila in fuentes.RIESGOS_RELATIVOS_PM25] == [
        "1,08 (1,06–1,09)", "1,11 (1,09–1,14)", "1,10 (1,03–1,18)",
    ]
    assert "no implican que la concentración de un día concreto cause" in fuentes.NOTA_INTERPRETACION_SALUD_PM25


def test_contexto_carga_sin_excepciones() -> None:
    """Renderiza Contexto con AppTest para comprobar mapas, tablas y gráficos."""
    ruta = ROOT / "app" / "pages" / "contexto.py"
    resultado = AppTest.from_file(str(ruta), default_timeout=30).run()
    assert not resultado.exception, str(resultado.exception)
    textos = "\n".join(elemento.value for elemento in resultado.markdown)
    assert "Se muestran ambas asignaciones" not in textos
    assert "coinciden con la tabla maestra" not in textos
    assert "Fila marcada para verificación" not in textos
    assert "Cifra pendiente de fuente oficial" not in textos
    assert any("errata (16-150)" in elemento.value for elemento in resultado.info)
    assert any(fuentes.NOTA_INTERPRETACION_SALUD_PM25 == elemento.value for elemento in resultado.caption)


def test_bloque_compara_estandares_con_medias_calculadas() -> None:
    """El texto compara normas oficiales con medias derivadas de la tabla maestra."""
    datos = cargar_aire()
    media_train = datos.loc[datos.fecha.le("2025-10-23"), "pm25"].mean()
    media_test = datos.loc[datos.fecha.ge("2025-10-24"), "pm25"].mean()
    carvajal = datos.loc[
        datos.estacion_id.eq("carvajal_sevillana") & datos.fecha.le("2025-10-23"), "pm25"
    ].mean()
    media_train = f"{media_train:.2f}".replace(".", ",")
    media_test = f"{media_test:.2f}".replace(".", ",")
    carvajal = f"{carvajal:.2f}".replace(".", ",")
    ruta = ROOT / "app" / "pages" / "contexto.py"
    resultado = AppTest.from_file(str(ruta), default_timeout=45).run()
    assert not resultado.exception, str(resultado.exception)
    textos = "\n".join(elemento.value for elemento in resultado.markdown)
    assert any("¿Está bien el aire de Bogotá? Depende del estándar" in e.value for e in resultado.subheader)
    assert f"{media_train} µg/m³ en entrenamiento y {media_test}" in textos
    assert f"Carvajal-Sevillana ({carvajal} en entrenamiento)" in textos
    assert fuentes.URL_RESOLUCION_2254 in textos
    assert fuentes.URL_GUIAS_OMS in textos
