"""Evalúa desplazamientos temporales entre IDEAM y anomalías de PM2.5.
Lee la tabla maestra, IDEAM limpio y libros crudos solo para inspeccionar hora y categoría.
Calcula correlaciones por desfase y compara Ridge de anomalías en fechas comunes.
Escribe tablas nuevas con prefijo diagnostico_alineacion_ en data/processed/app.
"""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import openpyxl
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
APP = PROCESSED / "app"
INTERIM = ROOT / "data" / "interim"
RAW = ROOT / "data" / "raw"
TRAIN_END = pd.Timestamp("2025-10-23")
TEST_START = pd.Timestamp("2025-10-24")
TEST_END = pd.Timestamp("2026-10-23")
SEED = 42
ALPHA = 100.0
DESPLAZAMIENTOS = (-2, -1, 0, 1, 2)
FEATURES = [
    "vel_ciudad_ms", "precip_mm", "precip_1d_antes", "precip_3d_acum",
    "llueve", "lluvia_ciudad_n", "tmax_anom", "tmin_anom", "amplitud_c",
    "es_fin_semana", "es_festivo", "dia_semana",
]
GRUPOS = {
    "lluvia": ["precip_mm", "precip_1d_antes", "precip_3d_acum", "llueve", "lluvia_ciudad_n"],
    "temperatura": ["tmax_anom", "tmin_anom", "amplitud_c"],
    "viento": ["vel_ciudad_ms"],
    "calendario": ["es_fin_semana", "es_festivo", "dia_semana"],
}
NOMBRES_IDEAM = {
    "21206600": "Nueva Generación",
    "21205710": "Jardín Botánico",
    "21206650": "San Cayetano",
}
FOLDERS = {
    "precip_mm": "precipitacion",
    "tmax_c": "temperatura_max",
    "tmin_c": "temperatura_min",
    "humedad": "humedad",
}


def _id_texto(serie: pd.Series) -> pd.Series:
    """Normaliza códigos numéricos/string a códigos comparables sin sufijo decimal."""
    return serie.astype("string").str.replace(r"\.0$", "", regex=True).str.strip()


def _spearman(x: pd.Series, y: pd.Series) -> tuple[float, int]:
    """Devuelve Spearman y n tras retirar faltantes de la pareja analizada."""
    pares = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    return (float(pares.x.corr(pares.y, method="spearman")) if len(pares) >= 2 else np.nan, len(pares))


def _climatologia(pm: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, float]:
    """Calcula referencia train estación-mes con los respaldos de entrenar_v2."""
    train = pm.loc[pm.fecha.le(TRAIN_END) & pm.pm25.notna()].copy()
    train["mes"] = train.fecha.dt.month
    pares = train.groupby(["estacion_id", "mes"]).pm25.agg(media="mean", n="size")
    estaciones = train.groupby("estacion_id").pm25.mean()
    return pares, estaciones, float(train.pm25.mean())


def _predecir_clima(frame: pd.DataFrame, pares: pd.DataFrame, estaciones: pd.Series, global_: float) -> np.ndarray:
    """Aplica la regla estación-mes >=10, estación y finalmente global."""
    salida = []
    for est, mes in zip(frame.estacion_id, frame.fecha.dt.month):
        if (est, mes) in pares.index and pares.loc[(est, mes), "n"] >= 10:
            salida.append(float(pares.loc[(est, mes), "media"]))
        else:
            salida.append(float(estaciones.get(est, global_)))
    return np.asarray(salida)


def _series_ideam() -> dict[str, pd.DataFrame]:
    """Carga IDEAM limpio y devuelve fecha por estación y variable, sin rellenar."""
    ideam = pd.read_parquet(INTERIM / "ideam_largo.parquet")
    ideam["fecha"] = pd.to_datetime(ideam.fecha).dt.normalize()
    ideam["estacion_ideam_id"] = _id_texto(ideam.estacion_ideam_id)
    return {
        variable: grupo.pivot_table(index="fecha", columns="estacion_ideam_id", values="valor", aggfunc="first")
        for variable, grupo in ideam.groupby("variable")
    }


def _alinear_variable(frame: pd.DataFrame, series: pd.DataFrame, id_col: str, k: int) -> pd.Series:
    """Busca dato IDEAM en fecha PM+k para cada estación de aire asignada."""
    ids = _id_texto(frame[id_col]).to_numpy()
    fechas = (frame.fecha + pd.to_timedelta(k, unit="D")).to_numpy(dtype="datetime64[ns]")
    valores = np.full(len(frame), np.nan)
    for codigo in pd.unique(ids):
        if pd.isna(codigo) or codigo not in series.columns:
            continue
        mask = ids == codigo
        consulta = pd.DatetimeIndex(fechas[mask])
        valores[mask] = series[codigo].reindex(consulta).to_numpy(dtype=float)
    return pd.Series(valores, index=frame.index, dtype=float)


def _lluvia_ciudad(series: pd.DataFrame, fechas: pd.Series, k: int) -> pd.Series:
    """Cuenta estaciones con >=1 mm en fecha desplazada; conserva NaN si no hay datos."""
    consulta = pd.DatetimeIndex((fechas + pd.to_timedelta(k, unit="D")).to_numpy())
    filas = series.reindex(consulta)
    cuenta = filas.ge(1).sum(axis=1).astype(float)
    cuenta[filas.notna().sum(axis=1).eq(0).to_numpy()] = np.nan
    return pd.Series(cuenta.to_numpy(), index=fechas.index)


def _variables_desfasadas(pm: pd.DataFrame, series: dict[str, pd.DataFrame], k: int) -> pd.DataFrame:
    """Construye los predictores IDEAM de una variante k mediante fechas exactas."""
    out = pd.DataFrame(index=pm.index)
    out["precip_mm"] = _alinear_variable(pm, series["precip_mm"], "precip_estacion_id", k)
    out["precip_1d_antes"] = _alinear_variable(pm, series["precip_mm"], "precip_estacion_id", k - 1)
    # entrenar_v2 usa una ventana de tres días previos al día IDEAM de referencia.
    partes = [_alinear_variable(pm, series["precip_mm"], "precip_estacion_id", k - j) for j in (1, 2, 3)]
    out["precip_3d_acum"] = pd.concat(partes, axis=1).sum(axis=1, min_count=3)
    out["llueve"] = out.precip_mm.ge(1).astype(float).where(out.precip_mm.notna())
    out["lluvia_ciudad_n"] = _lluvia_ciudad(series["precip_mm"], pm.fecha, k)
    out["tmax_c"] = _alinear_variable(pm, series["tmax_c"], "temp_estacion_id", k)
    out["tmin_c"] = _alinear_variable(pm, series["tmin_c"], "temp_estacion_id", k)
    # Las medias de anomalía quedan fijas con fechas IDEAM del periodo de entrenamiento.
    for variable, columna in (("tmax_c", "tmax_anom"), ("tmin_c", "tmin_anom")):
        base = series[variable].loc[series[variable].index <= TRAIN_END]
        medias = base.mean(axis=0)
        codigos = _id_texto(pm.temp_estacion_id)
        out[columna] = out[variable].to_numpy() - codigos.map(medias).to_numpy(dtype=float)
    out["amplitud_c"] = out.tmax_c - out.tmin_c
    return out


def _datos_crudos_horas_y_categorias() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inspecciona fechas crudas Excel y extrae categoría de metadatos de estaciones."""
    registros = []
    for variable, carpeta in FOLDERS.items():
        for ruta in sorted((RAW / carpeta).glob("*.xlsx")):
            libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
            hoja = libro[libro.sheetnames[0]]
            hoja.reset_dimensions()
            filas = list(hoja.iter_rows(values_only=True))
            encabezado = next((i for i, fila in enumerate(filas) if any(str(v).strip().lower() == "fecha" for v in fila if v is not None)), None)
            if encabezado is None:
                libro.close()
                continue
            columna = next(i for i, valor in enumerate(filas[encabezado]) if valor is not None and str(valor).strip().lower() == "fecha")
            horas = 0
            horas_no_cero = 0
            observadas = 0
            for datos in filas[encabezado + 1:]:
                if columna >= len(datos) or datos[columna] is None:
                    continue
                fecha = datos[columna]
                observadas += 1
                if hasattr(fecha, "hour"):
                    tiene_hora = isinstance(fecha, pd.Timestamp) or hasattr(fecha, "minute")
                    no_cero = fecha.hour != 0 or fecha.minute != 0 or fecha.second != 0
                else:
                    texto = str(fecha).strip()
                    tiene_hora = bool(re.search(r"\d{1,2}:\d{2}(?::\d{2})?", texto))
                    hora_txt = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", texto)
                    no_cero = bool(hora_txt and (int(hora_txt.group(1)) != 0 or int(hora_txt.group(2)) != 0 or int(hora_txt.group(3) or 0) != 0))
                horas += int(tiene_hora)
                horas_no_cero += int(no_cero)
            registros.append({"variable": variable, "archivo": ruta.name, "n_fechas": observadas, "n_con_hora": horas, "n_hora_no_cero": horas_no_cero})
            libro.close()
    categorias = pd.read_csv(PROCESSED / "estaciones_ideam.csv", dtype={"id": str})
    categorias["id"] = categorias.id.astype(str).str.strip()
    seleccion = categorias[categorias.id.isin(NOMBRES_IDEAM)].copy()
    seleccion["grupo_reporte"] = seleccion.id.map(NOMBRES_IDEAM)
    return pd.DataFrame(registros), seleccion[["id", "grupo_reporte", "nombre", "categoria"]]


def _tabla_correlaciones(pm: pd.DataFrame, variables_por_k: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """Calcula correlaciones y contrastes de lluvia globales y por estación IDEAM."""
    filas = []
    agrupaciones = [("global", None)] + [(nombre, codigo) for codigo, nombre in NOMBRES_IDEAM.items()]
    for k, wx in variables_por_k.items():
        base = pm[["fecha", "estacion_id", "precip_estacion_id", "temp_estacion_id", "pm_anomalia"]].join(wx)
        for grupo, codigo in agrupaciones:
            for variable, id_asignacion in (
                ("precip_mm", "precip_estacion_id"), ("llueve", "precip_estacion_id"),
                ("tmax_anom", "temp_estacion_id"), ("tmin_anom", "temp_estacion_id"),
                ("amplitud_c", "temp_estacion_id"),
            ):
                sub = base if codigo is None else base[_id_texto(base[id_asignacion]).eq(codigo)]
                rho, n = _spearman(sub.pm_anomalia, sub[variable])
                filas.append({"k": k, "grupo": grupo, "variable": variable, "spearman": rho, "n_dias": n})
            sub = base if codigo is None else base[_id_texto(base.precip_estacion_id).eq(codigo)]
            pares = sub.loc[sub.pm_anomalia.notna() & sub.llueve.notna()]
            con = pares.loc[pares.llueve.eq(1), "pm_anomalia"]
            sin = pares.loc[pares.llueve.eq(0), "pm_anomalia"]
            filas.append({"k": k, "grupo": grupo, "variable": "anomalia_media_con_lluvia", "spearman": float(con.mean()), "n_dias": len(con)})
            filas.append({"k": k, "grupo": grupo, "variable": "anomalia_media_sin_lluvia", "spearman": float(sin.mean()), "n_dias": len(sin)})
            filas.append({"k": k, "grupo": grupo, "variable": "diferencia_con_menos_sin_lluvia", "spearman": float(con.mean() - sin.mean()) if len(con) and len(sin) else np.nan, "n_dias": len(pares)})
    return pd.DataFrame(filas)


def _ajustar_y_evaluar(pm: pd.DataFrame, variables_por_k: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compara Ridge k=0 y k=+1 en casos comunes y ejecuta ablación de grupos."""
    pares, estaciones, global_ = _climatologia(pm)
    pm = pm.copy()
    pm["clim"] = _predecir_clima(pm, pares, estaciones, global_)
    pm["anomalia_objetivo"] = pm.pm25 - pm.clim
    xframes = {}
    for k, wx in variables_por_k.items():
        x = pd.DataFrame(index=pm.index)
        for col in ("vel_ciudad_ms", "es_fin_semana", "es_festivo", "dia_semana"):
            x[col] = pm[col]
        if k == 0:
            # La comparación de referencia coincide exactamente con las columnas
            # evaluadas por entrenar_v2; k=+1 reconstruye cada predictor por fecha.
            for col in ("precip_mm", "precip_1d_antes", "precip_3d_acum", "llueve", "lluvia_ciudad_n", "amplitud_c"):
                x[col] = pm[col]
            for variable, columna in (("tmax_c", "tmax_anom"), ("tmin_c", "tmin_anom")):
                medias = pm.loc[pm.fecha.le(TRAIN_END)].groupby("temp_estacion_id")[variable].mean()
                x[columna] = pm[variable] - pm.temp_estacion_id.map(medias)
        else:
            for col in ("precip_mm", "precip_1d_antes", "precip_3d_acum", "llueve", "lluvia_ciudad_n", "tmax_anom", "tmin_anom", "amplitud_c"):
                x[col] = wx[col]
        xframes[k] = x[FEATURES]
    # Se replica el filtro de filas completas de entrenar_v2; el imputador solo
    # resuelve faltantes que aparezcan al desplazar la serie respecto de esa base.
    expcols = [
        "vel_ciudad_ms", "precip_mm", "precip_1d_antes", "precip_3d_acum",
        "llueve", "lluvia_ciudad_n", "amplitud_c", "dia_semana", "es_fin_semana",
        "es_festivo", "mes", "lat", "lon", "es_movil", "estacion_id",
    ]
    filas_entrenables = (
        pm.pm25.notna()
        & xframes[0][["tmax_anom", "tmin_anom"]].notna().all(axis=1)
        & pm[expcols].notna().all(axis=1)
    )
    train = pm.fecha.le(TRAIN_END) & filas_entrenables
    test = pm.fecha.between(TEST_START, TEST_END) & pm.pm25.notna()
    comun = test.copy()
    for k in (0, 1):
        comun &= xframes[k].notna().all(axis=1)
    ids = pm.index[comun]
    metricas, fitted = [], {}
    for k in (0, 1):
        modelo = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=ALPHA, random_state=SEED))
        modelo.fit(xframes[k].loc[train], pm.loc[train, "anomalia_objetivo"])
        fitted[k] = modelo
        pred_anom = modelo.predict(xframes[k].loc[ids])
        y = pm.loc[ids, "pm25"].to_numpy()
        clim = pm.loc[ids, "clim"].to_numpy()
        pred = np.maximum(0, clim + pred_anom)
        metricas.append({"k": k, "n_prueba_comun": len(ids), "MAE": mean_absolute_error(y, pred), "RMSE": mean_squared_error(y, pred) ** .5, "R2": r2_score(y, pred), "MAE_climatologia_mismas_filas": mean_absolute_error(y, clim), "alpha": ALPHA, "n_train_pm": int(train.sum())})
    ablacion = []
    ytr = pm.loc[train, "anomalia_objetivo"]
    yte = pm.loc[ids, "pm25"].to_numpy()
    clima_te = pm.loc[ids, "clim"].to_numpy()
    pred_completa = np.maximum(0, clima_te + fitted[1].predict(xframes[1].loc[ids]))
    for grupo, columnas in GRUPOS.items():
        conservar = [col for col in FEATURES if col not in columnas]
        modelo = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=ALPHA, random_state=SEED))
        modelo.fit(xframes[1].loc[train, conservar], ytr)
        pred = np.maximum(0, clima_te + modelo.predict(xframes[1].loc[ids, conservar]))
        ablacion.append({"grupo_excluido": grupo, "n_prueba_comun": len(ids), "MAE_sin_grupo": mean_absolute_error(yte, pred), "MAE_modelo_completo": mean_absolute_error(yte, pred_completa), "MAE_climatologia": mean_absolute_error(yte, clima_te)})
    return pd.DataFrame(metricas), pd.DataFrame(ablacion)


def main() -> None:
    """Ejecuta el diagnóstico, guarda tablas nuevas e imprime sus resultados completos."""
    APP.mkdir(parents=True, exist_ok=True)
    pm = pd.read_parquet(PROCESSED / "aire_bogota_diario.parquet")
    pm["fecha"] = pd.to_datetime(pm.fecha).dt.normalize()
    pm["precip_estacion_id"] = _id_texto(pm.precip_estacion_id)
    pm["temp_estacion_id"] = _id_texto(pm.temp_estacion_id)
    pares, estaciones, global_ = _climatologia(pm)
    pm["clim"] = _predecir_clima(pm, pares, estaciones, global_)
    pm["pm_anomalia"] = pm.pm25 - pm.clim
    series = _series_ideam()
    wx = {k: _variables_desfasadas(pm, series, k) for k in DESPLAZAMIENTOS}
    correlaciones = _tabla_correlaciones(pm, wx)
    metricas, ablacion = _ajustar_y_evaluar(pm, wx)
    horas, categorias = _datos_crudos_horas_y_categorias()
    correlaciones.to_csv(APP / "diagnostico_alineacion_correlaciones.csv", index=False)
    metricas.to_csv(APP / "diagnostico_alineacion_metricas_ridge.csv", index=False)
    ablacion.to_csv(APP / "diagnostico_alineacion_ablacion_k1.csv", index=False)
    horas.to_csv(APP / "diagnostico_alineacion_fechas_crudas.csv", index=False)
    categorias.to_csv(APP / "diagnostico_alineacion_categorias_ideam.csv", index=False)
    print("REGLA: anomalía PM2.5 = PM2.5 - media train estación-mes; pares con n<10 usan media estación, estación desconocida usa media global.")
    print(f"Corte train <= {TRAIN_END.date()}, prueba {TEST_START.date()}..{TEST_END.date()}; filas test comunes completas para k=0/k=+1.")
    print("\nCORRELACIONES Y ANOMALÍA MEDIA POR LLUVIA (Spearman en filas; medias en µg/m³):")
    print(correlaciones.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nRIDGE DE ANOMALÍAS, SOLO TRAIN (predicción final = climatología + anomalía; piso 0):")
    print(metricas.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nAB LACIÓN POR GRUPOS k=+1:")
    print(ablacion.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nFECHAS DE EXCEL CRUDOS (hora no cero):")
    print(horas.to_string(index=False))
    print("\nCATEGORÍAS EN METADATOS IDEAM:")
    print(categorias.to_string(index=False))
    print("\nFUERZA MÁXIMA POR VARIABLE (mayor |Spearman| entre k):")
    relevantes = correlaciones[correlaciones.variable.isin(["precip_mm", "llueve", "tmax_anom", "tmin_anom", "amplitud_c"])]
    for (grupo, variable), datos in relevantes.groupby(["grupo", "variable"], sort=False):
        if datos.spearman.notna().any():
            fila = datos.loc[datos.spearman.abs().idxmax()]
            print(f"{grupo} / {variable}: k={int(fila.k):+d}, rho/valor={fila.spearman:.4f}, n={int(fila.n_dias)}")
    print("\nArchivos de salida:")
    for ruta in sorted(APP.glob("diagnostico_alineacion_*.csv")):
        print(f"- data/processed/app/{ruta.name}")


if __name__ == "__main__":
    main()
