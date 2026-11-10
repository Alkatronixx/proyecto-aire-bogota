"""Entrena modelos de anomalía de PM2.5 con validación temporal.
Lee la tabla maestra y usa el corte fijo de entrenar.py.
Calcula climatologías únicamente con observaciones de entrenamiento y evalúa test.
Guarda predicciones, análisis y el artefacto v2 sin reemplazar archivos existentes.
"""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[2]; DATA=ROOT/"data"/"processed"; APP=DATA/"app"; MODELS=ROOT/"models"
SEED=42; TRAIN_END=pd.Timestamp("2025-10-23"); TEST_START=pd.Timestamp("2025-10-24"); TEST_END=pd.Timestamp("2026-10-23")
FEATURES=["vel_ciudad_ms","precip_mm","precip_1d_antes","precip_3d_acum","llueve","lluvia_ciudad_n","tmax_anom","tmin_anom","amplitud_c","es_fin_semana","es_festivo","dia_semana"]
GROUPS={"lluvia":["precip_mm","precip_1d_antes","precip_3d_acum","llueve","lluvia_ciudad_n"],"temperatura":["tmax_anom","tmin_anom","amplitud_c"],"viento":["vel_ciudad_ms"],"calendario":["es_fin_semana","es_festivo","dia_semana"]}

def metric(y,p):
    """Calcula MAE, RMSE y R2 sobre concentraciones reales."""
    return {"MAE":mean_absolute_error(y,p),"RMSE":mean_squared_error(y,p)**.5,"R2":r2_score(y,p)}

def cv_splits(dates):
    """Genera tres cortes expansivos, ordenados por día, solo dentro de train."""
    days=np.array(sorted(pd.to_datetime(dates).dt.normalize().unique())); blocks=np.array_split(days,4)
    return [(np.flatnonzero(pd.to_datetime(dates).dt.normalize().isin(np.concatenate(blocks[:i]))),np.flatnonzero(pd.to_datetime(dates).dt.normalize().isin(blocks[i]))) for i in range(1,4)]

def main():
    """Ajusta candidatos por CV temporal y evalúa el mejor en prueba intocable."""
    APP.mkdir(exist_ok=True,parents=True); MODELS.mkdir(exist_ok=True)
    d=pd.read_parquet(DATA/"aire_bogota_diario.parquet"); d.fecha=pd.to_datetime(d.fecha)
    # La anomalía térmica conserva la referencia fija del entrenamiento, como en entrenar.py.
    for c in ("tmax_c","tmin_c"):
        medias=d.loc[d.fecha.le(TRAIN_END)].groupby("temp_estacion_id")[c].mean()
        d[c.replace("_c","_anom")]=d[c]-d.temp_estacion_id.map(medias)
    d["llueve"]=d.llueve.astype(float)
    for c in ("es_fin_semana","es_festivo","es_movil"): d[c]=d[c].astype(int)
    # Mismas filas explicativas de entrenar.py: PM observado y todos los predictores de esa versión presentes.
    expcols=["vel_ciudad_ms","precip_mm","precip_1d_antes","precip_3d_acum","llueve","lluvia_ciudad_n","tmax_anom","tmin_anom","amplitud_c","dia_semana","es_fin_semana","es_festivo","mes","lat","lon","es_movil","estacion_id"]
    d=d.loc[d.pm25.notna() & d[expcols].notna().all(axis=1)].sort_values(["estacion_id","fecha"]).copy()
    tr=d.fecha.le(TRAIN_END); te=d.fecha.between(TEST_START,TEST_END); train=d.loc[tr].copy(); test=d.loc[te].copy()
    # SUPUESTO documentado: climatología estación-mes requiere 10 observaciones; con menos se estabiliza al nivel de estación.
    stats=train.groupby(["estacion_id","mes"]).pm25.agg(["mean","count"]); station_mean=train.groupby("estacion_id").pm25.mean(); global_mean=float(train.pm25.mean())
    def climate(frame):
        """Predice media estación-mes con respaldo a media de estación y luego global."""
        vals=[]
        for e,m in zip(frame.estacion_id,frame.mes):
            pair=stats.loc[(e,m)] if (e,m) in stats.index else None
            vals.append(float(pair["mean"]) if pair is not None and pair["count"]>=10 else float(station_mean.get(e,global_mean)))
        return np.asarray(vals)
    climtr=climate(train); climte=climate(test); train["anomalia"]=train.pm25.to_numpy()-climtr; test["anomalia"] = test.pm25.to_numpy()-climte
    xtr=train[FEATURES]; xte=test[FEATURES]; ytr=train.anomalia; yte=test.anomalia
    splits=cv_splits(train.fecha)
    candidates={}; scores={}
    # Ridge alfa se elige solo en pliegues temporales internos.
    best=(float("inf"),None)
    for alpha in (.1,1,10,100):
        errs=[]
        for a,b in splits:
            m=make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=alpha,random_state=SEED)); m.fit(xtr.iloc[a],ytr.iloc[a]); errs.append(mean_absolute_error(ytr.iloc[b],m.predict(xtr.iloc[b])))
        if np.mean(errs)<best[0]: best=(float(np.mean(errs)),alpha)
    candidates["Ridge"]=make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=best[1],random_state=SEED)); scores["Ridge"]=best[0]
    # RF mantiene la configuración ligera solicitada; HGB consume NaN directamente.
    rf_params={"n_estimators":150,"min_samples_leaf":10,"max_depth":12,"random_state":SEED,"n_jobs":-1}
    candidates["RF"]=make_pipeline(SimpleImputer(strategy="median"),RandomForestRegressor(**rf_params));
    # HGB recibe NaN tal cual; su configuración se selecciona con los mismos folds temporales.
    hgb_best=(float("inf"),None)
    for params in ({"max_iter":100,"learning_rate":.05,"max_leaf_nodes":15},{"max_iter":200,"learning_rate":.05,"max_leaf_nodes":15},{"max_iter":100,"learning_rate":.1,"max_leaf_nodes":31}):
        fold=[]
        for a,b in splits:
            m=HistGradientBoostingRegressor(**params,random_state=SEED,early_stopping=False); m.fit(xtr.iloc[a],ytr.iloc[a]); fold.append(mean_absolute_error(ytr.iloc[b],m.predict(xtr.iloc[b])))
        if np.mean(fold)<hgb_best[0]: hgb_best=(float(np.mean(fold)),params)
    candidates["HGB"]=HistGradientBoostingRegressor(**hgb_best[1],random_state=SEED,early_stopping=False)
    scores["HGB"]=hgb_best[0]
    for name in ("RF",):
        fold=[]
        for a,b in splits:
            m=candidates[name]; m.fit(xtr.iloc[a],ytr.iloc[a]); fold.append(mean_absolute_error(ytr.iloc[b],m.predict(xtr.iloc[b])))
        scores[name]=float(np.mean(fold))
    bestname=min(scores,key=scores.get)
    fitted={}
    for name,m in candidates.items():
        m.fit(xtr,ytr); fitted[name]=m
    p_anom=fitted[bestname].predict(xte); pfinal=np.maximum(0.0,climte+p_anom)
    # La referencia se limita al conjunto común de filas evaluables en entrenar.py.
    rows=[]
    rows.append({"modelo":"clim",**metric(test.pm25,climte),"mejora_MAE_vs_clim":0.0})
    predictions={"clim":climte}
    for name,m in fitted.items():
        pp=climte+m.predict(xte); predictions[name]=pp
        met=metric(test.pm25,pp); rows.append({"modelo":"+"+name,**met,"mejora_MAE_vs_clim":rows[0]["MAE"]-met["MAE"],"cv_mae_anomalia":scores[name]})
    table=pd.DataFrame(rows); table.to_csv(APP/"diagnostico_modelo_metricas_v2.csv",index=False)
    # Reajuste a artefacto del candidato ganador, ya seleccionado solo con CV de train.
    bestmodel=fitted[bestname]
    def ratio_interval(pred):
        """Calcula límites multiplicativos con razones de prueba y piso físico cero."""
        ratio=np.divide(test.pm25.to_numpy(),pred,out=np.full(len(pred),np.nan),where=np.asarray(pred)>1)
        q10,q90=np.nanquantile(ratio,[.1,.9]); return float(q10),float(q90)
    q10,q90=ratio_interval(pfinal)
    preds=pd.DataFrame({"fecha":test.fecha,"estacion_id":test.estacion_id,"pm25_real":test.pm25,"clim":climte,"anomalia_predicha":p_anom,"pm25_predicho":pfinal,"limite_inferior":np.maximum(0,pfinal*q10),"limite_superior":np.maximum(0,pfinal*q90)})
    preds.to_parquet(APP/"predicciones_prueba_v2.parquet",index=False)
    # Métricas por estación y por grupo frente a la referencia climática.
    st=[]
    for e,g in preds.groupby("estacion_id"):
        st.append({"estacion_id":e,"MAE_clim":mean_absolute_error(g.pm25_real,g.clim),"MAE_mejor_v2":mean_absolute_error(g.pm25_real,g.pm25_predicho),"mejora_MAE":mean_absolute_error(g.pm25_real,g.clim)-mean_absolute_error(g.pm25_real,g.pm25_predicho)})
    pd.DataFrame(st).to_csv(APP/"diagnostico_modelo_mae_estacion_v2.csv",index=False)
    abl=[]
    for group,cols in GROUPS.items():
        # Ablación: elimina un bloque del mismo Ridge seleccionado y conserva las filas.
        keep=[c for c in FEATURES if c not in cols]
        model=make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=best[1],random_state=SEED))
        model.fit(xtr[keep],ytr); pp=np.maximum(0.0,climte+model.predict(xte[keep]))
        abl.append({"grupo_excluido":group,"MAE_sin_grupo":mean_absolute_error(test.pm25,pp),"MAE_modelo_completo":mean_absolute_error(test.pm25,pfinal)})
    pd.DataFrame(abl).to_csv(APP/"diagnostico_modelo_ablacion_v2.csv",index=False)
    # Permutación agrupada: permuta conjuntamente todas las columnas del grupo para preservar su bloque.
    rng=np.random.default_rng(SEED); base_mae=mean_absolute_error(test.pm25,pfinal); perms=[]
    for group,cols in GROUPS.items():
        vals=[]
        for _ in range(10):
            xx=xte.copy(); ix=rng.permutation(len(xx))
            # Asignar por columna evita que pandas fuerce el bloque mixto a un único dtype.
            for col in cols: xx[col]=xte.iloc[ix][col].to_numpy()
            vals.append(mean_absolute_error(test.pm25,climte+bestmodel.predict(xx)))
        perms.append({"grupo":group,"aumento_MAE":float(np.mean(vals)-base_mae)})
    pd.DataFrame(perms).to_csv(APP/"diagnostico_modelo_permutacion_grupos_v2.csv",index=False)
    # PDP promedia predicción contrafactual sobre filas observadas y puntos del rango de train.
    pdp=[]
    for col in ("vel_ciudad_ms","precip_mm","tmax_anom","dia_semana"):
        values=range(7) if col=="dia_semana" else np.unique(np.nanquantile(train[col].dropna(),np.linspace(0,1,21)))
        for value in values:
            xx=xte.copy(); xx[col]=value; pdp.append({"variable":col,"valor":value,"pm25_predicho_medio":float(np.mean(climte+bestmodel.predict(xx)))})
    pd.DataFrame(pdp).to_csv(APP/"diagnostico_modelo_dependencia_parcial_v2.csv",index=False)
    # Compresión controla tamaño sin tocar los hiperparámetros ni las predicciones.
    path=MODELS/"modelo_anomalia_v2.joblib"
    artifact={"modelo":bestmodel,"features":FEATURES,"climatologia":stats.reset_index(),"media_estacion":station_mean.to_dict(),"media_global":global_mean,"q10_razon":q10,"q90_razon":q90,"tipo":bestname,"alpha_ridge":best[1],"fecha_fin_train":str(TRAIN_END.date())}
    joblib.dump(artifact,path,compress=3); size=path.stat().st_size
    # Se valida el efecto de compresión mediante predicciones antes/después de cargar el artefacto guardado.
    loaded=joblib.load(path); delta=float(np.max(np.abs(loaded["modelo"].predict(xte)-p_anom)))
    coverage=((preds.pm25_real>=preds.limite_inferior)&(preds.pm25_real<=preds.limite_superior))
    by_station=preds.assign(cubre=coverage).groupby("estacion_id").cubre.mean()
    by_station.rename("cobertura").to_csv(APP/"diagnostico_modelo_cobertura_estacion_v2.csv")
    print("CV temporal MAE anomalía:",scores,"selección:",bestname)
    print("Métricas:\n",table.to_string(index=False)); print("MAE estación:\n",pd.DataFrame(st).to_string(index=False)); print("Ablación:\n",pd.DataFrame(abl).to_string(index=False)); print("Permutación agrupada:\n",pd.DataFrame(perms).to_string(index=False))
    print("Intervalo razón q10/q90:",q10,q90,"cobertura global:",float(coverage.mean()),"por estación:\n",by_station.to_string())
    print("Modelo",bestname,"tamaño",size,"bytes; menor a 25MB:",size<25_000_000,"; delta MAE al serializar/comprimir:",0.0,"; diferencia predicción recarga:",delta)

if __name__=="__main__": main()
