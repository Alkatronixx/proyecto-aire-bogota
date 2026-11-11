"""Comprueba límites temporales, rezagos y carga del simulador."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.modelo.entrenar import preparar, INICIO_TRAIN, FIN_TRAIN, INICIO_TEST, FIN_TEST


def test_particion_temporal_no_se_solapa():
    """La última fecha de entrenamiento antecede al primer día de prueba."""
    assert FIN_TRAIN < INICIO_TEST
    assert INICIO_TRAIN <= FIN_TRAIN < INICIO_TEST <= FIN_TEST


def test_rezago_ayer_coincide_con_fecha_anterior_original():
    """El rezago se toma de la fila del día previo en la serie original por estación."""
    original=pd.read_parquet(ROOT/"data"/"processed"/"aire_bogota_diario.parquet")
    preparado,_=preparar(original)
    p=preparado.sort_values(["estacion_id","fecha"])
    muestra=p.loc[p.pm25_ayer.notna()].iloc[0]
    anterior=p.loc[(p.estacion_id==muestra.estacion_id)&(p.fecha<muestra.fecha)].sort_values("fecha").iloc[-1]
    assert muestra.pm25_ayer == anterior.pm25
    assert anterior.fecha < muestra.fecha


def test_modelos_app_cargan_y_simulador_es_finito():
    """Los artefactos versionados cargan y el simulador devuelve un intervalo válido."""
    import joblib
    from app.utils.datos import cargar_aire, cargar_tabla_maestra
    from app.utils.simulador import (
        estadisticas_entrenamiento, escenario_referencia, predecir_escenario,
    )
    # El explicativo de 51 MB se excluye intencionalmente; no debe ser requisito del clon desplegable.
    joblib.load(ROOT/"models"/"modelo_predictivo.joblib")
    artefacto = joblib.load(ROOT/"models"/"modelo_anomalia_v2.joblib")
    datos = cargar_aire()
    asignacion = cargar_tabla_maestra("asignacion_estaciones.csv")
    asignacion["estacion_id"] = asignacion.estacion_id.astype(str)
    estadisticas = estadisticas_entrenamiento(datos)
    estacion = asignacion.estacion_id.iloc[0]
    escenario = escenario_referencia(estadisticas, estacion, 7, asignacion)
    salida = predecir_escenario(escenario, artefacto, estadisticas, asignacion)
    pred=salida["prediccion"]; bajo=salida["limite_inferior"]; alto=salida["limite_superior"]
    assert np.isfinite(pred) and np.isfinite(bajo) and np.isfinite(alto)
    assert bajo <= pred <= alto
