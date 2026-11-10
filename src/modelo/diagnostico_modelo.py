"""Diagnostica la climatología y el modelo explicativo sin cambiar sus artefactos.
Lee la tabla maestra y el modelo explicativo existente.
Recalcula resultados y escenarios en memoria usando la partición temporal vigente.
Escribe únicamente archivos nuevos con prefijo diagnostico_modelo.
"""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"
APP = DATA / "app"
TRAIN_END = pd.Timestamp("2025-10-23")
TEST_START, TEST_END = pd.Timestamp("2025-10-24"), pd.Timestamp("2026-10-23")


def metricas(y, p):
    """Resume errores en las filas observadas de prueba."""
    return {"n": len(y), "MAE": mean_absolute_error(y, p), "RMSE": mean_squared_error(y, p) ** .5, "R2": r2_score(y, p)}


def main():
    """Imprime las comprobaciones del diagnóstico y guarda tablas ampliadas."""
    d = pd.read_parquet(DATA / "aire_bogota_diario.parquet")
    d["fecha"] = pd.to_datetime(d.fecha)
    # Reproduce la ingeniería de temperatura usada por entrenar.py con medias train.
    for c in ("tmax_c", "tmin_c"):
        means=d.loc[d.fecha.le(TRAIN_END)].groupby("temp_estacion_id")[c].mean()
        d[c.replace("_c", "_anom")]=d[c]-d.temp_estacion_id.map(means)
    for c in ("llueve",): d[c]=d[c].astype(float)
    for c in ("es_fin_semana", "es_festivo", "es_movil"): d[c]=d[c].astype(int)
    # Réplica independiente de entrenar.py: promedio PM por estación y mes,
    # calculado estrictamente con fechas hasta el último día de entrenamiento.
    expcols=["vel_ciudad_ms","precip_mm","precip_1d_antes","precip_3d_acum","llueve","lluvia_ciudad_n","tmax_anom","tmin_anom","amplitud_c","dia_semana","es_fin_semana","es_festivo","mes","lat","lon","es_movil","estacion_id"]
    complete=d.pm25.notna() & d[expcols].notna().all(axis=1)
    train = d.loc[d.fecha.le(TRAIN_END) & complete].copy()
    test = d.loc[d.fecha.between(TEST_START, TEST_END) & complete].copy()
    clim = train.groupby(["estacion_id", "mes"]).pm25.mean()
    test["clim"] = [clim.get((e, m), train.pm25.mean()) for e, m in zip(test.estacion_id, test.mes)]
    print("Código registrado en entrenar.py: z = d.loc[mask] (incluye train y test); base = z.groupby(['estacion_id','mes']).pm25.mean(); predice test con base. Por tanto NO usa solo entrenamiento.")
    print("Climatología correcta train-only (hasta 2025-10-23):", metricas(test.pm25, test.clim))
    ztodo=d.loc[d.pm25.notna() & d[expcols].notna().all(axis=1)].copy()
    legacy=ztodo.groupby(["estacion_id","mes"]).pm25.mean()
    leaked=np.array([legacy.get((e,m),train.pm25.mean()) for e,m in zip(test.estacion_id,test.mes)])
    print("Réplica independiente del cálculo actual con fuga test:",metricas(test.pm25,leaked))
    # Describe deriva por estación y trimestre usando datos observados sin imputación.
    por_est = d.loc[d.pm25.notna()].assign(periodo=lambda x: np.where(x.fecha.le(TRAIN_END), "train", "test")).pivot_table(index=["estacion_id", "estacion"], columns="periodo", values="pm25", aggfunc="mean")
    por_est["diferencia_test_menos_train"] = por_est.get("test") - por_est.get("train")
    por_est.to_csv(APP/"diagnostico_modelo_medias_estacion_v2.csv")
    print("Medias estación train/test/diferencia:\n", por_est.to_string())
    q = d.loc[d.pm25.notna()].groupby(d.fecha.dt.quarter).pm25.mean()
    print("PM2.5 medio por trimestre calendario (Q1-Q4):\n", q.to_string())
    q.rename("pm25_medio").to_csv(APP/"diagnostico_modelo_trimestre_v2.csv")
    model = joblib.load(ROOT / "models" / "modelo_explicativo.joblib")
    meta = model._air_metadata
    z = d.loc[complete & d.fecha.between(TEST_START, TEST_END)].copy()
    pred = model.predict(z[meta["columns"]]); z["rf"] = pred
    z["clim"] = [clim.get((e, m), train.pm25.mean()) for e, m in zip(z.estacion_id, z.mes)]
    for name in ("clim", "rf"):
        z[name + "_sesgo"] = z[name] - z.pm25
        print(name, "sesgo prueba global", z[name + "_sesgo"].mean(), "MAE corregido por sesgo estación", mean_absolute_error(z.pm25, z[name] - z.groupby("estacion_id")[name + "_sesgo"].transform("mean")))
    print("Sesgo RF por estación:\n", z.groupby("estacion").rf_sesgo.mean().to_string())
    print("Sesgo climatología por estación:\n", z.groupby("estacion").clim_sesgo.mean().to_string())
    z.groupby(["estacion_id","estacion"])[["clim_sesgo","rf_sesgo"]].mean().to_csv(APP/"diagnostico_modelo_sesgo_estacion_v2.csv")
    # La imputación indicada es cualquier predictor que llega nulo al pipeline.
    exp = d.loc[d.pm25.notna() & d[meta["columns"]].notna().all(axis=1) & d.fecha.between(TEST_START, TEST_END)].copy()
    # Identifica faltantes entre las columnas esperadas antes de filtrar completos: documenta cero por definición de entrenar.py.
    complete = d.loc[d.pm25.notna() & d.fecha.between(TEST_START, TEST_END)].copy()
    missing = complete[meta["columns"]].isna().any(axis=1)
    complete["pred"] = np.nan
    if (~missing).any(): complete.loc[~missing, "pred"] = model.predict(complete.loc[~missing, meta["columns"]])
    print("RF prueba con algún predictor imputado: %.2f%% (%d/%d); filas imputadas no forman parte de entrenar.py explicativo por máscara de casos completos." % (100*missing.mean(), missing.sum(), len(missing)))
    print("RF MAE sin imputación:", mean_absolute_error(complete.loc[~missing, "pm25"], complete.loc[~missing, "pred"]))
    if missing.any():
        # En el pipeline existente la imputación es mediana, pero sus filas se excluyeron en el ajuste/evaluación original.
        fill = complete.loc[missing, meta["columns"]].copy()
        complete.loc[missing, "pred"] = model.predict(fill)
        print("RF MAE con imputación:", mean_absolute_error(complete.loc[missing, "pm25"], complete.loc[missing, "pred"]))
    # Serie mensual comparativa de estaciones con mejor correlación histórica con Carvajal.
    wide = d.pivot_table(index="fecha", columns="estacion", values="pm25")
    target = next((c for c in wide.columns if "Carvajal" in c and "Sevillana" in c), None)
    if target:
        corr = wide.corr(min_periods=100)[target].drop(target).sort_values(ascending=False)
        comp = [target] + corr.head(3).index.tolist()
        monthly = wide[comp].resample("MS").mean()
        monthly.to_csv(APP / "diagnostico_modelo_carvajal_mensual_v2.csv")
        print("Comparables Carvajal:", comp, "\nMedias mensuales guardadas en diagnostico_modelo_carvajal_mensual_v2.csv")
        for col in comp: print(col, "media antes/después 2025-10:", monthly.loc[monthly.index < "2025-10-01", col].mean(), monthly.loc[monthly.index >= "2025-10-01", col].mean())
    # Años parciales; noviembre/diciembre no deben compararse como una tendencia homogénea.
    print("Días 2023-10-24 a 2023-12-31:", d.loc[d.fecha.between("2023-10-24", "2023-12-31"), "fecha"].nunique())
    print("Días 2026-01-01 a 2026-10-23:", d.loc[d.fecha.between("2026-01-01", "2026-10-23"), "fecha"].nunique())
    print("Nov/dic medios:\n", d.loc[d.pm25.notna() & d.fecha.dt.year.isin([2023,2024,2025]) & d.fecha.dt.month.isin([11,12])].groupby([d.fecha.dt.year,d.fecha.dt.month]).pm25.mean().to_string())
    print("La comparación 17.25 vs 10.91 usa periodos distintos y no se presenta como tendencia.")
    # Valores completos de entrada para escenarios citados por el simulador.
    med = d.loc[d.fecha.le(TRAIN_END), meta["columns"]].median(numeric_only=True)
    print("Medianas de referencia entrenamiento:", med.to_dict())
    print("No encontré en el repositorio entradas de los tres escenarios mencionados; la tabla inferior es una sensibilidad reproducible con centro_de_alto_rendimiento.")
    station = next((str(x) for x in model._air_metadata["categories"]["estacion_id"] if "centro_de_alto_rendimiento" == str(x).lower()), None)
    # Se modifican individualmente factores sobre una fila completa válida, con medianas de train.
    base = {c: med.get(c, 0) for c in meta["columns"]}; station = station or model._air_metadata["categories"]["estacion_id"][0]
    base.update({"estacion_id":station,"mes":int(d.loc[d.fecha.le(TRAIN_END),"mes"].median()),"lat":float(d.loc[d.estacion_id.eq(station),"lat"].dropna().median()),"lon":float(d.loc[d.estacion_id.eq(station),"lon"].dropna().median()),"es_movil":0})
    scenarios=[]
    tmean=d.loc[d.fecha.le(TRAIN_END)].groupby("temp_estacion_id").tmax_c.mean()
    assignment=pd.read_csv(DATA/"asignacion_estaciones.csv",dtype={"estacion_id":str})
    temp_station=int(assignment.loc[assignment.estacion_id.eq(station),"temp_estacion_id"].iloc[0])
    for c, vals in (("precip_mm",[0,1,5,20]),("vel_ciudad_ms",[.5,1,1.5,2,2.5,3]),("tmax_c",[10,15,20,25,30]),("dia_semana",range(7))):
        for v in vals:
            row=base.copy(); row[c]=v
            if c=="precip_mm": row["llueve"]=float(v>=1)
            if c=="tmax_c":
                # La columna del modelo es anomalía; la entrada absoluta se centra en la media térmica train.
                row["tmax_anom"]=float(v)-float(tmean.loc[temp_station])
            if c=="dia_semana": row["es_fin_semana"]=int(v>=5)
            scenarios.append({"variable":c,"valor":v,"entradas":str(row),"prediccion":float(model.predict(pd.DataFrame([row],columns=meta["columns"]))[0])})
    pd.DataFrame(scenarios).to_csv(APP/"diagnostico_modelo_simulador_v2.csv",index=False)
    print("Tabla de sensibilidad (filas completas de entrada en CSV):\n",pd.DataFrame(scenarios)[["variable","valor","prediccion"]].to_string(index=False))
    print("Tres escenarios comparables (entradas completas; solo lluvia y calendario cambian entre filas):")
    for label,changes in (("laborable seco",{"precip_mm":0.0,"llueve":0.0,"dia_semana":2,"es_fin_semana":0}),("fin de semana seco",{"precip_mm":0.0,"llueve":0.0,"dia_semana":5,"es_fin_semana":1}),("laborable lluvioso",{"precip_mm":20.0,"llueve":1.0,"dia_semana":2,"es_fin_semana":0})):
        row=base|changes; value=float(model.predict(pd.DataFrame([row],columns=meta["columns"]))[0]); print(label,"predicción",value,"entradas",row)
    print("Escenarios guardados en diagnostico_modelo_simulador_v2.csv")

if __name__ == "__main__": main()
