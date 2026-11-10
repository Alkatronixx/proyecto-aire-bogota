"""Predice PM2.5 bajo un escenario meteorológico indicado por el usuario.
Lee el artefacto explicativo generado por entrenar.py y sus metadatos.
Valida las entradas antes de armar una fila con las columnas esperadas.
Devuelve una predicción y el intervalo residual 10-90 % de la prueba temporal.
"""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "modelo_explicativo.joblib"


def predecir_escenario(estacion_id, mes, dia_semana, es_festivo, precip_mm,
                       precip_1d_antes, vel_ciudad_ms, tmax_c, tmin_c) -> dict:
    """Predice concentración e intervalo para un día; día_semana usa lunes=0."""
    rangos = {"mes":(1,12),"dia_semana":(0,6),"precip_mm":(0,150),"precip_1d_antes":(0,150),"vel_ciudad_ms":(0,30),"tmax_c":(-20,50),"tmin_c":(-30,40)}
    for nombre,(bajo,alto) in rangos.items():
        valor=locals()[nombre]
        if not np.isfinite(float(valor)) or not bajo <= float(valor) <= alto:
            raise ValueError(f"{nombre} debe estar entre {bajo} y {alto}; recibido {valor!r}.")
    modelo=joblib.load(MODEL_PATH); meta=modelo._air_metadata
    cats=meta["categories"]["estacion_id"]
    if str(estacion_id) not in cats:
        raise ValueError(f"estacion_id desconocida; opciones: {', '.join(cats)}")
    medias=meta["medias_anomalia"]
    asignacion=pd.read_csv(ROOT/"data"/"processed"/"asignacion_estaciones.csv",dtype={"estacion_id":str})
    ubicacion=asignacion.loc[asignacion.estacion_id.astype(str).eq(str(estacion_id))]
    if ubicacion.empty: raise ValueError(f"No existe asignación para estación {estacion_id}.")
    ubicacion=ubicacion.iloc[0]
    estacion_ideam=int(ubicacion["temp_estacion_id"])
    # SUPUESTO: el formulario no recibe acumulado a tres días ni conteo de estaciones lluviosas;
    # el pipeline completa esos dos valores con medianas calculadas durante el ajuste del modelo.
    row={c:np.nan for c in meta["columns"]}
    row.update({"estacion_id":str(estacion_id),"mes":int(mes),"dia_semana":int(dia_semana),"es_festivo":int(bool(es_festivo)),"es_fin_semana":int(int(dia_semana)>=5),"es_movil":int(bool(ubicacion["es_movil"])),"lat":float(ubicacion["lat"]),"lon":float(ubicacion["lon"]),"precip_mm":float(precip_mm),"precip_1d_antes":float(precip_1d_antes),"llueve":float(precip_mm>=1),"vel_ciudad_ms":float(vel_ciudad_ms),"tmax_anom":float(tmax_c)-float(medias["tmax_c"].get(estacion_ideam,np.nan)),"tmin_anom":float(tmin_c)-float(medias["tmin_c"].get(estacion_ideam,np.nan)),"amplitud_c":float(tmax_c)-float(tmin_c)})
    # Se mantienen faltantes no configurables; el pipeline usa medianas aprendidas en entrenamiento.
    p=float(modelo.predict(pd.DataFrame([row],columns=meta["columns"]))[0])
    return {"prediccion":p,"intervalo_10_90":(p+meta["residuos_q10"],p+meta["residuos_q90"])}


