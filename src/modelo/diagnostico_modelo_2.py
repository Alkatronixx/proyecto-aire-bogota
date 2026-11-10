"""Audita modelos, climatologías y cambios de nivel de PM2.5/PM10.
Lee los artefactos y la tabla procesada sin reescribirlos ni reentrenarlos en disco.
Reajusta en memoria el RF temporal, compara periodos y audita los códigos de entrenamiento.
Imprime tablas completas y escribe solo CSV nuevos con prefijo diagnostico_modelo_2_.
"""
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
DATA=ROOT/"data"/"processed"; APP=DATA/"app"; MODELS=ROOT/"models"
TRAIN_START=pd.Timestamp("2023-10-24"); TRAIN_END=pd.Timestamp("2025-10-23")
TEST_START=pd.Timestamp("2025-10-24"); TEST_END=pd.Timestamp("2026-10-23")
GAP_END=pd.Timestamp("2025-10-16"); PRE_GAP_END=pd.Timestamp("2025-08-03"); RESTART=pd.Timestamp("2025-10-17")

def score(y, p):
    """Calcula métricas de regresión para observaciones y predicciones alineadas."""
    return {"n":len(y),"MAE":mean_absolute_error(y,p),"RMSE":mean_squared_error(y,p)**.5,"R2":r2_score(y,p),"sesgo":float(np.mean(np.asarray(p)-np.asarray(y)))}

def print_save(frame, name, index=False):
    """Imprime la tabla completa y la escribe en el directorio autorizado."""
    print(f"\n{name} (n={len(frame)}):\n{frame.to_string(index=index)}")
    frame.to_csv(APP/f"diagnostico_modelo_2_{name.lower().replace(' ','_')}.csv",index=index)

def main():
    """Ejecuta comparaciones in-memory y emite evidencia numérica y de código."""
    from src.modelo.entrenar import preparar, BASE_NUM, CAT, SEMILLA
    raw=pd.read_parquet(DATA/"aire_bogota_diario.parquet")
    d,medias=preparar(raw.copy()); d.fecha=pd.to_datetime(d.fecha)
    expcols=BASE_NUM+CAT
    complete=d.pm25.notna() & d[expcols].notna().all(axis=1)
    z=d.loc[complete].copy()
    train=z.loc[z.fecha.between(TRAIN_START,TRAIN_END)].copy()
    test=z.loc[z.fecha.between(TEST_START,TEST_END)].copy()
    XCOLS=expcols; NUM=[c for c in expcols if c not in CAT]
    saved_exp=joblib.load(MODELS/"modelo_explicativo.joblib")
    saved_pred=joblib.load(MODELS/"modelo_predictivo.joblib")
    v2=joblib.load(MODELS/"modelo_anomalia_v2.joblib")

    # 1. Prueba temporal RF y evaluación del artefacto final sobre las mismas filas.
    saved_rf=saved_exp.named_steps["rf"]
    rf_params=saved_rf.get_params(deep=False)
    temporal=Pipeline([("pre",__import__("src.modelo.entrenar",fromlist=["preprocesador"]).preprocesador(NUM)),("rf",RandomForestRegressor(**rf_params))])
    temporal.fit(train[XCOLS],train.pm25)
    p_trainfit=temporal.predict(test[XCOLS]); p_saved=saved_exp.predict(test[XCOLS])
    print("\nPARTE 1. Filas comunes completas: train=",len(train),"test=",len(test),"fechas train",train.fecha.min(),train.fecha.max(),"test",test.fecha.min(),test.fecha.max())
    print("Objeto del diagnóstico previo: models/modelo_explicativo.joblib, ajustado en all_exp (train + test + demás fechas completas), no el rfpipe temporal.")
    print("RF hiperparámetros recuperados del artefacto:",rf_params)
    print("RF reentrenado solo train:",score(test.pm25,p_trainfit))
    print("RF guardado aplicado a las mismas filas test:",score(test.pm25,p_saved))
    for tag,p in (("RF temporal",p_trainfit),("RF guardado",p_saved)):
        tab=test[["estacion_id","estacion","pm25"]].copy(); tab["pred"]=p; tab["sesgo"]=tab.pred-tab.pm25
        out=tab.groupby(["estacion_id","estacion"],as_index=False).agg(n=("pm25","size"),sesgo=("sesgo","mean"))
        # La agregación explícita de MAE evita confundir sesgo absoluto con error absoluto medio.
        out["MAE"]=tab.groupby(["estacion_id","estacion"]).apply(lambda g:mean_absolute_error(g.pm25,g.pred),include_groups=False).to_numpy()
        print_save(out,f"{tag}_sesgo_mae_estacion")

    # 2. Inspección de composición, hiperparámetros, dimensiones y filas ajustadas de artefactos.
    def inspect_pipeline(label,obj):
        """Resume estimador y estados de ajuste internos de un pipeline guardado."""
        final=obj.steps[-1][1] if isinstance(obj,Pipeline) else obj
        print(f"\nARTEFACTO {label}: clase final={type(final).__module__}.{type(final).__name__}; parámetros={final.get_params(deep=False)}; bytes={(MODELS/label).stat().st_size}")
        if isinstance(obj,Pipeline):
            print("  pasos:",[(n,type(est).__name__) for n,est in obj.steps])
            pre=obj.named_steps.get("pre")
            if pre is not None:
                print("  columnas numéricas:",pre.transformers_[0][2]); print("  categorías one-hot:",pre.named_transformers_["cat"].categories_)
                numeric=pre.named_transformers_["num"]
                for nm,est in numeric.steps:
                    if hasattr(est,"statistics_"): print("  imputación",nm,"medianas",dict(zip(pre.transformers_[0][2],est.statistics_)))
                    if hasattr(est,"n_samples_seen_"): print("  escalador",nm,"n_samples_seen_",est.n_samples_seen_)
            if hasattr(final,"estimators_samples_"):
                print("  RF filas de bootstrap por árbol:",len(final.estimators_samples_[0]),"estimadores:",len(final.estimators_))
            if hasattr(final,"n_samples_seen_"): print("  muestras del estimador:",final.n_samples_seen_)
        return final
    print("\nPARTE 2. Artefactos y metadatos:")
    exp_final=inspect_pipeline("modelo_explicativo.joblib",saved_exp)
    pred_final=inspect_pipeline("modelo_predictivo.joblib",saved_pred)
    v2model=v2["modelo"]
    inspect_pipeline("modelo_anomalia_v2.joblib",v2model)
    print("  explicativo metadata:",saved_exp._air_metadata)
    print("  predictivo metadata:",saved_pred._air_metadata)
    print("  anomaly-v2 keys:",list(v2.keys()),"tipo",v2.get("tipo"),"features",v2.get("features"),"n_climatologías",len(v2["climatologia"]),"suma cuentas clima",int(v2["climatologia"]["count"].sum()),"n_samples scaler",getattr(v2model.named_steps.get("standardscaler"),"n_samples_seen_",None),"q10/q90",v2.get("q10_razon"),v2.get("q90_razon"),"fin train",v2.get("fecha_fin_train"))
    all_exp=d.loc[d.pm25.notna() & d[expcols].notna().all(axis=1)]
    predcols=BASE_NUM+["pm25_ayer","pm25_media_3d"]+CAT
    all_pred=d.loc[d.pm25.notna() & d[predcols].notna().all(axis=1)]
    print("Filas ajuste reconstituidas de entrenar.py: app explicativo",len(all_exp),"última fecha",all_exp.fecha.max(),"app predictivo",len(all_pred),"última fecha",all_pred.fecha.max())
    # Ridge ajusta en scaler: su contador informa exactamente cuántas filas procesó.
    print("Predictivo es Ridge:",type(pred_final).__name__,"alpha",getattr(pred_final,"alpha",None),"; modelo guardado vs selección de prueba: entrenar.py selecciona alpha por CV temporal dentro train, mientras RF fue ganador de MAE test 3.223 frente a Ridge 3.332.")

    # 3. Climatologías en la misma máscara y las mismas 5,410 filas.
    train_clim=train.groupby(["estacion_id","mes"]).pm25.agg(["mean","count"])
    station_mean=train.groupby("estacion_id").pm25.mean(); global_mean=float(train.pm25.mean())
    simple=train.groupby(["estacion_id","mes"]).pm25.mean()
    pred_simple=np.array([simple.get((e,m),global_mean) for e,m in zip(test.estacion_id,test.mes)])
    pred_fallback=[]; low_count=0; absent_pair=0; absent_station=0
    for e,m in zip(test.estacion_id,test.mes):
        if (e,m) in train_clim.index:
            row=train_clim.loc[(e,m)]
            if row["count"]>=10: pred_fallback.append(row["mean"])
            else: pred_fallback.append(station_mean.get(e,global_mean)); low_count+=1
        else:
            absent_pair+=1
            if e in station_mean.index: pred_fallback.append(station_mean[e])
            else: pred_fallback.append(global_mean); absent_station+=1
    pred_fallback=np.asarray(pred_fallback)
    print("\nPARTE 3. Climatologías, test simple groupby n=",len(test),"v2 n=",len(test))
    climate_compare=pd.DataFrame([{"metodo":"groupby estación-mes; par ausente -> global",**score(test.pm25,pred_simple)},{"metodo":"v2: n<10 -> media estación; estación ausente -> global",**score(test.pm25,pred_fallback)}])
    print_save(climate_compare,"comparacion_climatologia_misma_prueba")
    print("Predicciones v2 por fallback: pares presentes con n<10",low_count,"pares inexistentes",absent_pair,"estaciones ausentes con fallback global",absent_station)

    # 4a. Medias de PM y razón mensual por año calendario.
    air=raw.copy(); air.fecha=pd.to_datetime(air.fecha)
    air=air.loc[air.fecha.dt.year.isin([2024,2025,2026])].copy()
    air["year"]=air.fecha.dt.year; air["month"]=air.fecha.dt.month
    monthly=air.groupby(["month","year"])[["pm25","pm10"]].mean().unstack("year")
    monthly.columns=[f"{col}_{year}" for col,year in monthly.columns]
    # Cada indicador ocupa una tabla mes por año para facilitar su lectura y comparación.
    pm25tab=air.pivot_table(index="month",columns="year",values="pm25",aggfunc="mean").reindex(range(1,13))
    pm10tab=air.pivot_table(index="month",columns="year",values="pm10",aggfunc="mean").reindex(range(1,13))
    print("\nPARTE 4a. PM2.5 mensual global (mes x año):"); print_save(pm25tab.reset_index(),"pm25_mes_anio",False)
    print("PM10 mensual global (mes x año):"); print_save(pm10tab.reset_index(),"pm10_mes_anio",False)
    # Diferencias de meses emparejados en años consecutivos solicitados.
    eq=[]
    for pollutant,tab,months,a,b in (("pm25",pm25tab,range(10,13),2024,2025),("pm10",pm10tab,range(10,13),2024,2025),("pm25",pm25tab,range(1,10),2025,2026),("pm10",pm10tab,range(1,10),2025,2026)):
        for m in months: eq.append({"variable":pollutant,"mes":m,"periodo_a":a,"media_a":tab.loc[m,a],"periodo_b":b,"media_b":tab.loc[m,b],"diferencia_b_menos_a":tab.loc[m,b]-tab.loc[m,a]})
    print_save(pd.DataFrame(eq),"comparacion_meses_iguales")
    air["razon_pm25_pm10"]=air.pm25/air.pm10.where(air.pm10>0)
    rat_month=air.groupby(["month","year"]).razon_pm25_pm10.median().unstack("year").reindex(range(1,13))
    print_save(rat_month.reset_index(),"razon_mediana_mes_anio")
    # Station-wise concentration ratio before/after 2025-10-17.
    raw2=raw.copy(); raw2.fecha=pd.to_datetime(raw2.fecha); raw2["razon_pm25_pm10"]=raw2.pm25/raw2.pm10.where(raw2.pm10>0)
    raw2["periodo"]=np.where(raw2.fecha<RESTART,"antes_2025-10-17","desde_2025-10-17")
    ratio_station=raw2.groupby(["estacion_id","estacion","periodo"]).razon_pm25_pm10.median().unstack("periodo").reset_index()
    print_save(ratio_station,"razon_mediana_estacion_antes_despues")

    # 4c. Promedio semanal como media de promedios diarios de ciudad (cada día igual peso).
    city=raw2.loc[raw2.fecha.between("2025-06-01","2025-12-31") & raw2.pm25.notna()]
    daily=city.groupby("fecha").agg(pm25_ciudad=("pm25","mean"),estaciones=("estacion_id","nunique"))
    daily["semana"]=daily.index.to_period("W-SUN").start_time
    weekly=daily.groupby("semana").agg(pm25_medio_semanal=("pm25_ciudad","mean"),estaciones_media_diaria=("estaciones","mean"),dias_con_dato=("estaciones","size"))
    weekly["estaciones_con_dato"]=city.assign(semana=city.fecha.dt.to_period("W-SUN").dt.start_time).groupby("semana").estacion_id.nunique()
    weeks=pd.date_range("2025-05-26","2025-12-29",freq="7D")
    # Incluye semanas vacías para mostrar explícitamente el hueco como ausencia y no como concentración cero.
    weekly=weekly.reindex(weeks); weekly.estaciones_media_diaria=weekly.estaciones_media_diaria.fillna(0); weekly.estaciones_con_dato=weekly.estaciones_con_dato.fillna(0); weekly.dias_con_dato=weekly.dias_con_dato.fillna(0)
    print("\nPARTE 4c. Media semanal ciudad; número de estaciones es promedio diario, días con observación en columna separada.")
    print_save(weekly.reset_index(names="semana_inicio"),"pm25_semanal_ciudad")

    # 4d. Ventanas antes del hueco y tras la reanudación, para contaminantes y clima.
    for c in ("tmax_c","tmin_c"):
        mu=raw2.loc[raw2.fecha.le(TRAIN_END)].groupby("temp_estacion_id")[c].mean(); raw2[c.replace("_c","_anom")]=raw2[c]-raw2.temp_estacion_id.map(mu)
    window_pre=raw2.fecha.le(PRE_GAP_END); window_post=raw2.fecha.ge(RESTART)
    fields=["pm25","pm10","vel_ciudad_ms","precip_mm","tmax_anom"]
    stats=[]
    for period,mask in (("antes_hueco_hasta_2025-08-03",window_pre),("desde_reanudacion_2025-10-17",window_post)):
        sub=raw2.loc[mask]
        means=sub.groupby(["estacion_id","estacion"])[fields].mean()
        means.columns=pd.MultiIndex.from_product([[period],means.columns]); stats.append(means)
    by_station=pd.concat(stats,axis=1)
    for c in fields: by_station[("diferencia_post_menos_pre",c)]=by_station[("desde_reanudacion_2025-10-17",c)]-by_station[("antes_hueco_hasta_2025-08-03",c)]
    by_station.columns=["__".join(map(str,c)) for c in by_station.columns]
    print("\nPARTE 4d. Medias por estación antes del hueco y tras reanudación, diferencia post-pre:")
    print_save(by_station.reset_index(),"medias_estacion_pre_post_hueco")

    # 4e. Registro de retorno por estación a partir del 17-oct.
    returns=[]
    for e,g in raw2.groupby(["estacion_id","estacion"]):
        post=g.loc[g.fecha.ge(RESTART) & g.pm25.notna(),"fecha"]
        october=g.loc[g.fecha.between(RESTART,"2025-10-31") & g.pm25.notna(),"fecha"]
        pre_count=g.loc[g.fecha.le(PRE_GAP_END),"pm25"].notna().sum()
        gap_count=g.loc[g.fecha.between("2025-08-04",GAP_END),"pm25"].notna().sum()
        returns.append({"estacion_id":e[0],"estacion":e[1],"pm25_antes_hueco":pre_count,"pm25_en_hueco":gap_count,"dias_pm25_octubre_17_31":len(october),"primera_fecha_post_hueco":post.min() if len(post) else pd.NaT,"retorno":"octubre" if len(october) else ("posterior" if len(post) else "sin retorno al fin del periodo")})
    print("\nPARTE 4e. Retorno PM2.5 por estación:"); print_save(pd.DataFrame(returns),"retorno_estacion_hueco")
    # Consolidado descriptivo pregunta si la razón se mantiene semejante entre ventanas.
    for label,mask in (("pre_hueco",window_pre),("post_hueco",window_post)):
        g=raw2.loc[mask]
        print("\nPARTE 4f.",label,"medias PM2.5, PM10 y razón mediana:",g[["pm25","pm10"]].mean().to_dict(),"razón mediana",g.razon_pm25_pm10.median())

    # 5. Auditoría estática basada en líneas impresas de los dos scripts protegidos.
    audit=pd.DataFrame([
      ["entrenar.py","36","medias tmax/tmin por estación IDEAM","solo train: fechas 2023-10-24..2025-10-23","sí"],
      ["entrenar.py","39-40","rezagos PM2.5","shift/rolling por estación ordenada; solo observaciones previas de cada fila","no usa futuro; véase hueco de cobertura"],
      ["entrenar.py","46-49, 91-92, 117-128","medianas, StandardScaler, categorías OneHotEncoder en evaluación CV/test","fit ocurre en cada train fold o train final, no en test","sí durante evaluación"],
      ["entrenar.py","65-67, 70-94","cortes CV, alpha Ridge y parámetros RF","bloques cronológicos expansivos dentro de filas train","sí"],
      ["entrenar.py","105-107","máscara complete-case y cortes train/test","filtra por disponibilidad, luego corta fechas","sí"],
      ["entrenar.py","110-112","climatología groupby estación-mes","z contiene train y test antes del groupby","NO: fuga test"],
      ["entrenar.py","117-128","Ridge y RF de evaluación temporal","fit xtr/ytr solamente","sí"],
      ["entrenar.py","138-145","RF de ablación","fit sel_train (solo entrenamiento); evalúa sel_test","sí"],
      ["entrenar.py","165-176","importancia por permutación","usa test para interpretar; no reajusta modelo","no es ajuste predictivo"],
      ["entrenar.py","181-187","bootstrap de coeficientes","máscara explícita train; bloques semanales de train","sí"],
      ["entrenar.py","190-194","dependencia parcial","predictores de test y modelo fit train","no reajusta"],
      ["entrenar.py","196-200","RF/Ridge de app; preprocesador y one-hot final","all_exp/all_pred incluyen fechas train y test; metadatos categories usa d completa","NO, final app usa todos los datos por diseño"],
      ["entrenar.py","198","cuantiles residuales del modelo explicativo","residuo sobre test para intervalo en metadata","usa test para calibrar intervalo, no estimador"],
      ["entrenar_v2.py","37-39","medias temperatura para anomalías","d.fecha <= 2025-10-23","sí"],
      ["entrenar_v2.py","47-55","climatología estación-mes/estación/global y anomalías","train explícito; respaldo n<10 por estación y global si no existe estación","sí"],
      ["entrenar_v2.py","64-87","imputación, escalado, Ridge/HGB CV, elección entre modelos","fit por pliegues temporales train; selección por CV train","sí"],
      ["entrenar_v2.py","86-88","modelos candidatos finalistas","fit xtr/ytr, fechas solo hasta 2025-10-23","sí"],
      ["entrenar_v2.py","99-105","cuantiles q10/q90 de observado/predicción","calculados en prueba para calibrar intervalo","usa test para intervalo, no entrenamiento del estimador"],
      ["entrenar_v2.py","111-118","ablación Ridge","se ajusta con todo xtr/ytr de entrenamiento","sí"],
      ["entrenar_v2.py","120-129","permutación agrupada","usa test para medir importancia; no hace fit","no es ajuste"],
      ["entrenar_v2.py","131-136","dependencia parcial","usa xte y modelo ya fit en train","no reajusta"],
      ["entrenar_v2.py","138-145","serialización modelo anomalia","guarda bestmodel ajustado train; climatología y cuantiles asociados","estimador sí; cuantiles usan test"],
    ],columns=["archivo","linea","paso","evidencia","usa_test_al_ajustar"])
    print("\nPARTE 5. Auditoría de filtraciones (fit vs test/calibración):"); print_save(audit,"auditoria_filtraciones")
    print("\nRezagos: al ordenar por estación/fecha y aplicar shift(1), un registro de entrenamiento no incorpora filas futuras del conjunto de prueba; media rolling también se desplaza una posición. El lag es observación previa, no necesariamente día calendario previo si hay huecos.")
    print("CV: entrenar.py (líneas 65-67) crea train con bloques anteriores y valida el siguiente; entrenar_v2.py (29-30) hace lo mismo sobre fechas de train. Los dos son expansivos por fecha.")

if __name__=="__main__": main()
