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
    """Los artefactos existen y un escenario devuelve predicción e intervalo válido."""
    import joblib
    from src.modelo.simular import predecir_escenario
    for nombre in ("modelo_explicativo.joblib","modelo_predictivo.joblib"):
        joblib.load(ROOT/"models"/nombre)
    est=pd.read_csv(ROOT/"data"/"processed"/"asignacion_estaciones.csv",dtype={"estacion_id":str}).estacion_id.iloc[0]
    salida=predecir_escenario(est,7,5,False,0,0,1.5,22,8)
    pred=salida["prediccion"]; bajo,alto=salida["intervalo_10_90"]
    assert np.isfinite(pred) and np.isfinite(bajo) and np.isfinite(alto)
    assert bajo <= pred <= alto
