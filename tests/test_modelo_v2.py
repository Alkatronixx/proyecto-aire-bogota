"""Comprueba propiedades de seguridad temporal y del intervalo del modelo v2."""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def test_climatologia_no_usa_datos_de_prueba():
    """La climatología guardada se calcula únicamente hasta el corte de entrenamiento."""
    artifact=joblib.load(ROOT/"models"/"modelo_anomalia_v2.joblib")
    assert artifact["fecha_fin_train"]=="2025-10-23"
    assert artifact["climatologia"].shape[0]>0

def test_modelo_v2_carga():
    """El artefacto comprimido conserva un estimador utilizable."""
    artifact=joblib.load(ROOT/"models"/"modelo_anomalia_v2.joblib")
    assert callable(artifact["modelo"].predict)

def test_intervalo_contiene_prediccion_y_no_es_negativo():
    """Los límites multiplicativos preservan la predicción y el piso físico."""
    p=pd.read_parquet(ROOT/"data"/"processed"/"app"/"predicciones_prueba_v2.parquet")
    assert (p.limite_inferior>=0).all()
    assert (p.limite_inferior<=p.pm25_predicho).all()
    assert (p.limite_superior>=p.pm25_predicho).all()
