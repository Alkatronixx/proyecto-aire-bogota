"""Entrena, compara e interpreta modelos temporales de PM2.5.
Lee aire_bogota_diario.parquet y construye variables sin imputar objetivos.
Evalúa validación y prueba en fechas fijas y comunes por versión.
Escribe métricas, predicciones, interpretaciones y artefactos de la app.
"""
from pathlib import Path
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"
APP = DATA / "app"
MODEL_DIR = ROOT / "models"
SEMILLA = 42
INICIO_TRAIN, FIN_TRAIN = pd.Timestamp("2023-10-24"), pd.Timestamp("2025-10-23")
INICIO_TEST, FIN_TEST = pd.Timestamp("2025-10-24"), pd.Timestamp("2026-10-23")
BASE_NUM = ["vel_ciudad_ms", "precip_mm", "precip_1d_antes", "precip_3d_acum", "llueve", "lluvia_ciudad_n", "tmax_anom", "tmin_anom", "amplitud_c", "dia_semana", "es_fin_semana", "es_festivo", "mes", "lat", "lon", "es_movil"]
CAT = ["estacion_id"]
LAGS = ["pm25_ayer", "pm25_media_3d"]


def preparar(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Calcula anomalías solo con entrenamiento y rezagos sobre malla ordenada."""
    d = d.sort_values(["estacion_id", "fecha"]).copy()
    medias = {}
    for c in ("tmax_c", "tmin_c"):
        medias[c] = d.loc[d.fecha.between(INICIO_TRAIN, FIN_TRAIN)].groupby("temp_estacion_id")[c].mean().to_dict()
        m = d.temp_estacion_id.map(medias[c])
        d[c.replace("_c", "_anom")] = d[c] - m
    d["pm25_ayer"] = d.groupby("estacion_id").pm25.shift(1)
    d["pm25_media_3d"] = d.groupby("estacion_id").pm25.transform(lambda s: s.shift(1).rolling(3, min_periods=2).mean())
    d["llueve"] = d.llueve.astype("float")
    d["es_fin_semana"] = d.es_fin_semana.astype(int); d["es_festivo"] = d.es_festivo.astype(int); d["es_movil"] = d.es_movil.astype(int)
    return d, medias


def preprocesador(numericas: list[str]) -> ColumnTransformer:
    """Escala numéricas y codifica estación/mes, imputando medianas dentro del pipeline."""
    from sklearn.impute import SimpleImputer
    return ColumnTransformer([("num", Pipeline([("imputar", SimpleImputer(strategy="median")), ("escalar", StandardScaler())]), numericas), ("cat", OneHotEncoder(handle_unknown="ignore"), CAT)])


def modelo_ridge(numericas: list[str], alpha: float = 10, log: bool = False) -> Pipeline:
    """Crea Ridge con transformaciones ajustadas únicamente al subconjunto de entrenamiento."""
    # La retransformación lognormal usa el factor de corrección estimado en train.
    return Pipeline([("pre", preprocesador(numericas)), ("ridge", Ridge(alpha=alpha, random_state=SEMILLA))])


def resumen(y: pd.Series, p: np.ndarray) -> dict:
    """Calcula métricas en la unidad original de PM2.5."""
    return {"n":len(y), "MAE":mean_absolute_error(y,p), "RMSE":mean_squared_error(y,p)**0.5, "R2":r2_score(y,p)}


def cortes_cv(fechas: pd.Series) -> list[tuple[np.ndarray,np.ndarray]]:
    """Genera tres pliegues expansivos por fecha dentro del entrenamiento."""
    dias = np.array(sorted(fechas.dt.normalize().unique()))
    bloques = np.array_split(dias, 4)
    return [(np.flatnonzero(fechas.isin(np.concatenate(bloques[:i]))), np.flatnonzero(fechas.isin(bloques[i]))) for i in range(1,4)]


def seleccionar_alpha(x: pd.DataFrame, y: pd.Series, fechas: pd.Series, numericas: list[str], log: bool=False) -> float:
    """Selecciona alpha por MAE promedio en los tres pliegues temporales expansivos."""
    mejor = (float("inf"), 10.0)
    for alpha in (0.1, 1, 10, 100):
        errores=[]
        for tr, va in cortes_cv(fechas):
            m=modelo_ridge(numericas, alpha)
            objetivo=np.log1p(y.iloc[tr]) if log else y.iloc[tr]
            m.fit(x.iloc[tr],objetivo); pred=m.predict(x.iloc[va])
            if log: pred=np.expm1(pred)
            errores.append(mean_absolute_error(y.iloc[va],pred))
        if np.mean(errores)<mejor[0]: mejor=(float(np.mean(errores)),alpha)
    return mejor[1]


def seleccionar_rf(x: pd.DataFrame, y: pd.Series, fechas: pd.Series, numericas: list[str]) -> dict:
    """Selecciona tamaño y hoja del bosque con los mismos pliegues temporales expansivos."""
    mejor=(float("inf"),{"n_estimators":150,"min_samples_leaf":3,"max_features":0.8})
    for parametros in ({"n_estimators":150,"min_samples_leaf":3,"max_features":0.8},{"n_estimators":250,"min_samples_leaf":5,"max_features":0.8}):
        errores=[]
        for tr,va in cortes_cv(fechas):
            m=Pipeline([("pre",preprocesador(numericas)),("rf",RandomForestRegressor(**parametros,n_jobs=2,random_state=SEMILLA))])
            m.fit(x.iloc[tr],y.iloc[tr]); errores.append(mean_absolute_error(y.iloc[va],m.predict(x.iloc[va])))
        if np.mean(errores)<mejor[0]: mejor=(float(np.mean(errores)),parametros)
    return mejor[1]


def main() -> None:
    """Ejecuta comparaciones temporales, interpretabilidad y reentrenamiento final."""
    APP.mkdir(parents=True,exist_ok=True); MODEL_DIR.mkdir(parents=True,exist_ok=True)
    d, medias = preparar(pd.read_parquet(DATA/"aire_bogota_diario.parquet"))
    d.fecha=pd.to_datetime(d.fecha)
    exp_cols=BASE_NUM+CAT; pred_cols=BASE_NUM+LAGS+CAT
    outcomes=[]; preds=[]; fitted={}; metrics_by={}; rf_params_by_version={}; alpha_by_version={}
    for version, cols in (("explicativo",exp_cols),("predictivo",pred_cols)):
        mask=d.pm25.notna() & d[cols].notna().all(axis=1)
        z=d.loc[mask].copy(); tr=z.fecha.between(INICIO_TRAIN,FIN_TRAIN); te=z.fecha.between(INICIO_TEST,FIN_TEST)
        train=z.loc[tr]; test=z.loc[te]; ytr=train.pm25; yte=test.pm25; xtr=train[cols]; xte=test[cols]
        ncols=[c for c in cols if c not in CAT]
        # Casos completos comunes a todos los modelos de cada versión.
        base=(z.groupby(["estacion_id","mes"]).pm25.mean())
        if version=="explicativo": pbase=np.array([base.get((e,m),ytr.mean()) for e,m in zip(test.estacion_id,test.mes)])
        else: pbase=test.pm25_ayer.to_numpy()
        m0=resumen(yte,pbase); m0.update(modelo="línea base",version=version); outcomes.append(m0)
        alpha=seleccionar_alpha(xtr,ytr,train.fecha,ncols)
        alpha_by_version[version]=alpha
        for etiqueta,log in (("Ridge",False),("Ridge log",True)):
            m=modelo_ridge(ncols,alpha,log); m.fit(xtr,np.log1p(ytr) if log else ytr)
            p=m.predict(xte); factor=1.0
            if log:
                resid=np.log1p(ytr)-m.predict(xtr); factor=float(np.mean(np.exp(resid))); p=np.expm1(p)*factor
            met=resumen(yte,p); met.update(modelo=etiqueta,version=version,alpha=alpha,imputacion="mediana en pipeline ajustada en entrenamiento"); outcomes.append(met)
            if etiqueta=="Ridge": fitted[(version,"Ridge")]=m
            if version=="explicativo" and etiqueta=="Ridge":
                m._air_log=False; m._air_smear=factor
        rf_params=seleccionar_rf(xtr,ytr,train.fecha,ncols)
        rf_params_by_version[version]=rf_params
        rf=RandomForestRegressor(**rf_params,n_jobs=2,random_state=SEMILLA)
        rfpipe=Pipeline([("pre",preprocesador(ncols)),("rf",rf)]); rfpipe.fit(xtr,ytr); pr=rfpipe.predict(xte)
        met=resumen(yte,pr); met.update(modelo="Random Forest",version=version,imputacion="mediana en pipeline ajustada en entrenamiento",**{f"rf_{k}":v for k,v in rf_params.items()}); outcomes.append(met)
        fitted[(version,"Random Forest")]=rfpipe
        # Métricas desglosadas con predicción RF como candidato elegido.
        metrics_by[version]=(test,yte,pr,pbase,rfpipe,xte)
        for fecha,e,est,mes,temp,y,pred in zip(test.fecha,test.estacion_id,test.estacion,test.mes,test.temporada,yte,pr):
            preds.append({"fecha":fecha,"estacion_id":e,"pm25_real":y,"pm25_predicho":pred,"version":version})
        # Ablaciones: reentrenamiento con las mismas filas de prueba, excluidas estaciones móviles solo en su ablación.
        if version=="explicativo":
            grupos={"sin_temperatura":["tmax_anom","tmin_anom","amplitud_c"],"sin_viento":["vel_ciudad_ms"],"sin_lluvia":["precip_mm","precip_1d_antes","precip_3d_acum","llueve","lluvia_ciudad_n"],"sin_calendario":["dia_semana","es_fin_semana","es_festivo","mes"],"sin_estaciones_moviles":[]}
            for nombre, quitar in grupos.items():
                keep=[c for c in ncols if c not in quitar]
                if nombre=="sin_estaciones_moviles":
                    sel_train=train.loc[~train.es_movil.astype(bool)]; sel_test=test.loc[~test.es_movil.astype(bool)]
                else: sel_train=train; sel_test=test
                abl=Pipeline([("pre",preprocesador(keep)),("rf",RandomForestRegressor(**rf_params_by_version["explicativo"],n_jobs=2,random_state=SEMILLA))])
                abl.fit(sel_train[keep+CAT],sel_train.pm25); pp=abl.predict(sel_test[keep+CAT])
                outcomes.append({"modelo":nombre,"version":"ablacion","MAE":mean_absolute_error(sel_test.pm25,pp),"n":len(sel_test)})

    # La mejora usa el MAE ingenuo de la misma versión y las mismas filas.
    metricas=pd.DataFrame(outcomes)
    for version in ("explicativo","predictivo"):
        base_mae=metricas.loc[(metricas.version==version)&(metricas.modelo=="línea base"),"MAE"].iloc[0]
        sel=metricas.version.eq(version)
        metricas.loc[sel,"mejora_mae_vs_base_pct"]=(base_mae-metricas.loc[sel,"MAE"])/base_mae*100
    metricas.to_csv(APP/"metricas_modelos.csv",index=False)
    metricas.loc[metricas.version.eq("ablacion")].to_csv(APP/"ablacion.csv",index=False)
    pd.DataFrame(preds).to_parquet(APP/"predicciones_prueba.parquet",index=False)
    # Detalle de errores por estación, mes y temporada para RF explicativo y predictivo.
    detalles=[]
    for version,(test,y,p,_,_,_) in metrics_by.items():
        t=test.copy(); t["real"]=y.to_numpy();t["pred"]=p;t["sesgo"]=t.pred-t.real
        for group in ("estacion_id","mes","temporada"):
            for k,g in t.groupby(group): detalles.append({"version":version,"grupo":group,"categoria":k,"MAE":mean_absolute_error(g.real,g.pred),"sesgo":g.sesgo.mean(),"n":len(g)})
    pd.DataFrame(detalles).to_csv(APP/"metricas_desglosadas.csv",index=False)
    # Interpretación del RF explicativo por grupos de variables.
    test,y,p,_,rfpipe,xte=metrics_by["explicativo"]
    perm=permutation_importance(rfpipe,xte,y,n_repeats=10,random_state=SEMILLA,scoring="neg_mean_absolute_error",n_jobs=2)
    # La permutación se aplica a columnas originales para que cada variable categórica
    # represente su conjunto completo de columnas one-hot y admita agrupación directa.
    names=list(xte.columns); imp=pd.DataFrame({"feature":names,"importancia":perm.importances_mean})
    def grupo(s: str) -> str:
        s=s.split("__")[-1]
        if any(k in s for k in ("precip","llueve","lluvia_ciudad")): return "lluvia"
        if any(k in s for k in ("tmax","tmin","amplitud")): return "temperatura"
        if any(k in s for k in ("dia_semana","fin_semana","festivo","mes")): return "calendario"
        if "vel_ciudad" in s:return "viento"
        return "ubicación"
    imp["grupo"]=imp.feature.map(grupo); imp.groupby("grupo").importancia.sum().sort_values(ascending=False).rename("importancia").to_csv(APP/"importancias_rf.csv")
    # Bootstrap por bloques de semanas para reflejar dependencia temporal en los intervalos del Ridge.
    ridge=fitted[("explicativo","Ridge")]; coef=ridge.named_steps["ridge"].coef_; nombres=ridge.named_steps["pre"].get_feature_names_out()
    rng=np.random.default_rng(SEMILLA); semanas=(pd.to_datetime(test.fecha).dt.to_period("W").astype(str)); bloques=semanas.unique(); boot=[]
    # Reajusta coeficientes sobre muestras por bloques de entrenamiento para obtener incertidumbre temporal.
    trmask=d.pm25.notna() & d[exp_cols].notna().all(axis=1) & d.fecha.between(INICIO_TRAIN,FIN_TRAIN)
    z=d.loc[trmask]; weeks=z.fecha.dt.to_period("W").astype(str); week_ids=weeks.unique()
    for b in range(200):
        sampled=rng.choice(week_ids,len(week_ids),replace=True); ix=np.concatenate([np.flatnonzero(weeks.to_numpy()==w) for w in sampled])
        mb=modelo_ridge([c for c in exp_cols if c not in CAT],ridge.named_steps["ridge"].alpha); mb.fit(z.iloc[ix][exp_cols],z.iloc[ix].pm25)
        boot.append(mb.named_steps["ridge"].coef_)
    boot=np.asarray(boot); pd.DataFrame({"feature":nombres,"coef_estandarizado":coef,"ic10":np.quantile(boot,.05,axis=0),"ic90":np.quantile(boot,.95,axis=0)}).to_csv(APP/"coeficientes_ridge.csv",index=False)
    # Dependencia parcial manual sobre filas observadas del test.
    pdp=[]
    for col in ("vel_ciudad_ms","precip_mm","tmax_anom","dia_semana","mes"):
        vals=np.unique(np.quantile(xte[col].dropna(),np.linspace(0,1,15)))
        for val in vals:
            xx=xte.copy();xx[col]=val;pdp.append({"variable":col,"valor":val,"prediccion_media":rfpipe.predict(xx).mean()})
    pd.DataFrame(pdp).to_csv(APP/"dependencia_parcial.csv",index=False)
    # Modelo de app: RF explicativo elegido y Ridge predictivo elegido, entrenados con todos los datos.
    all_exp=d.loc[d.pm25.notna() & d[exp_cols].notna().all(axis=1)]; all_pred=d.loc[d.pm25.notna() & d[pred_cols].notna().all(axis=1)]
    app_exp=Pipeline([("pre",preprocesador([c for c in exp_cols if c not in CAT])),("rf",RandomForestRegressor(**rf_params_by_version["explicativo"],n_jobs=2,random_state=SEMILLA))]); app_exp.fit(all_exp[exp_cols],all_exp.pm25)
    app_exp._air_metadata={"columns":exp_cols,"numericas":[c for c in exp_cols if c not in CAT],"medias_anomalia":medias,"categories":{c:sorted(d[c].dropna().astype(str).unique()) for c in CAT},"residuos_q10":float(np.quantile(test.pm25.to_numpy()-p,.1)),"residuos_q90":float(np.quantile(test.pm25.to_numpy()-p,.9)),"model_type":"RandomForestRegressor"}
    app_pred=modelo_ridge([c for c in pred_cols if c not in CAT],alpha_by_version["predictivo"]);app_pred.fit(all_pred[pred_cols],all_pred.pm25);app_pred._air_metadata={"columns":pred_cols,"medias_anomalia":medias,"categories":{c:sorted(d[c].dropna().astype(str).unique()) for c in CAT}}
    joblib.dump(app_exp,MODEL_DIR/"modelo_explicativo.joblib");joblib.dump(app_pred,MODEL_DIR/"modelo_predictivo.joblib")
    print(pd.DataFrame(outcomes).to_string(index=False)); print("Filas completas",{k:len(v[0]) for k,v in metrics_by.items()})
    for f in (MODEL_DIR/"modelo_explicativo.joblib",MODEL_DIR/"modelo_predictivo.joblib"):print(f.name,f.stat().st_size,"bytes")

if __name__=="__main__": main()
