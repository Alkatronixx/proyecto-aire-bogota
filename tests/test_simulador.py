"""Comprueba predicciones, límites de entrada y calibración del simulador.
Verifica la coincidencia del Ridge v2 con las predicciones de prueba publicadas.
Ejecuta también las páginas Simulador y Modelo con Streamlit AppTest.
"""
import time

import joblib
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app.utils.datos import ROOT, cargar_aire, cargar_tabla_maestra, rutas_lectura_app
from app.utils.simulador import (
    crear_preset, estadisticas_entrenamiento, escenario_referencia,
    predecir_anomalia, predecir_escenario, reconstruir_prueba_v2,
)


@pytest.fixture(scope="module")
def contexto() -> dict:
    """Carga los datos y el modelo v2 una sola vez para las pruebas funcionales."""
    datos = cargar_aire()
    modelo = joblib.load(ROOT / "models" / "modelo_anomalia_v2.joblib")
    asignacion = cargar_tabla_maestra("asignacion_estaciones.csv")
    asignacion["estacion_id"] = asignacion.estacion_id.astype(str)
    estadisticas = estadisticas_entrenamiento(datos)
    return {"datos": datos, "modelo": modelo, "asignacion": asignacion,
            "estadisticas": estadisticas}


def test_prediccion_intervalo_finito_para_las_19_estaciones(contexto: dict) -> None:
    """El piso del intervalo y la predicción son válidos en cada estación."""
    stats = contexto["estadisticas"]
    estaciones = contexto["asignacion"].estacion_id.tolist()
    assert len(estaciones) == 19
    for estacion in estaciones:
        escenario = escenario_referencia(stats, estacion, 6, contexto["asignacion"])
        resultado = predecir_escenario(escenario, contexto["modelo"], stats,
                                       contexto["asignacion"])
        assert np.isfinite(resultado["prediccion"])
        assert resultado["limite_inferior"] >= 0
        assert resultado["limite_inferior"] <= resultado["prediccion"]
        assert resultado["prediccion"] <= resultado["limite_superior"]


@pytest.mark.parametrize("variable", [
    "vel_ciudad_ms", "precip_mm", "precip_1d_antes", "tmax_c", "tmin_c",
])
def test_rechaza_entradas_fuera_de_percentiles(variable: str, contexto: dict) -> None:
    """La API rechaza valores fuera de p1-p99 aunque la interfaz ya los limite."""
    stats = contexto["estadisticas"]
    estacion = "centro_de_alto_rendimiento"
    escenario = escenario_referencia(stats, estacion, 6, contexto["asignacion"])
    escenario[variable] = stats["cotas_entrada"][variable][1] + 1
    with pytest.raises(ValueError, match="p1-p99"):
        predecir_escenario(escenario, contexto["modelo"], stats,
                           contexto["asignacion"])


def test_rechaza_temperatura_maxima_menor_que_minima(contexto: dict) -> None:
    """La validación conserva el orden físico mínimo-máximo del escenario."""
    stats = contexto["estadisticas"]
    escenario = escenario_referencia(stats, "centro_de_alto_rendimiento", 6,
                                     contexto["asignacion"])
    escenario["tmax_c"] = escenario["tmin_c"] - .1
    with pytest.raises(ValueError, match="mayor o igual"):
        predecir_escenario(escenario, contexto["modelo"], stats,
                           contexto["asignacion"])


def test_los_tres_presets_tienen_predicciones_distintas(contexto: dict) -> None:
    """Los presets cambian entradas a cuantiles observados y generan salidas distintas."""
    stats = contexto["estadisticas"]
    asignacion = contexto["asignacion"]
    base = escenario_referencia(stats, "centro_de_alto_rendimiento", 6, asignacion)
    nombres = ["Día laborable sin viento", "Fin de semana seco y ventoso",
               "Día laborable lluvioso"]
    valores = [predecir_escenario(crear_preset(n, base, stats), contexto["modelo"],
                                  stats, asignacion)["prediccion"] for n in nombres]
    assert len({round(valor, 8) for valor in valores}) == 3


def test_prediccion_reproduce_las_primeras_20_filas_de_prueba(contexto: dict) -> None:
    """El Ridge y el orden de 12 variables reproducen el archivo de evaluación v2."""
    prueba = reconstruir_prueba_v2(contexto["datos"]).head(20)
    artefacto = contexto["modelo"]
    predicciones = pd.read_parquet(ROOT / "data" / "processed" / "app" / "predicciones_prueba_v2.parquet").head(20)
    assert prueba[["fecha", "estacion_id"]].reset_index(drop=True).equals(
        predicciones[["fecha", "estacion_id"]].reset_index(drop=True)
    )
    anomalia = predecir_anomalia(artefacto, prueba[artefacto["features"]])
    assert np.allclose(anomalia, predicciones.anomalia_predicha, atol=1e-6, rtol=0)
    pm25_final = np.maximum(0, predicciones.clim.to_numpy()+anomalia)
    assert np.allclose(pm25_final, predicciones.pm25_predicho, atol=1e-6, rtol=0)


def test_prediccion_caliente_tarda_menos_de_200_ms(contexto: dict) -> None:
    """Mide una inferencia después del calentamiento de importaciones y caché."""
    stats = contexto["estadisticas"]
    escenario = escenario_referencia(stats, "centro_de_alto_rendimiento", 6,
                                     contexto["asignacion"])
    predecir_escenario(escenario, contexto["modelo"], stats, contexto["asignacion"])
    inicio = time.perf_counter()
    predecir_escenario(escenario, contexto["modelo"], stats, contexto["asignacion"])
    assert time.perf_counter() - inicio < .2


def test_la_app_no_lee_artefactos_predictivo_ni_explicativo() -> None:
    """Mantiene los dos modelos grandes o ajenos al simulador fuera de los cargadores."""
    rutas = [ruta.name for ruta in rutas_lectura_app()]
    assert "modelo_anomalia_v2.joblib" in rutas
    assert "modelo_predictivo.joblib" not in rutas
    assert "modelo_explicativo.joblib" not in rutas


@pytest.mark.parametrize("pagina", ["simulador.py", "modelo.py"])
def test_app_test_carga_simulador_y_modelo(pagina: str) -> None:
    """Renderiza cada página final por separado para capturar fallos de interfaz."""
    ruta = ROOT / "app" / "pages" / pagina
    resultado = AppTest.from_file(str(ruta), default_timeout=45).run()
    assert not resultado.exception, f"Excepción en {pagina}: {resultado.exception}"
