"""Explora cobertura, asociaciones y patrones temporales del aire bogotano.
Lee la tabla diaria y series IDEAM intermedias sin alterar sus valores.
Imprime verificaciones de fechas, temporadas y contaminantes.
Escribe resúmenes livianos para la aplicación bajo data/processed/app.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"
APP = DATA / "app"
IDEAM = ROOT / "data" / "interim" / "ideam_largo.parquet"
UMBRAL_OMS_24H = None  # TODO: completar con la cifra y la fuente oficial citada
UMBRAL_COL_24H = None  # TODO: completar con la cifra y la fuente oficial citada


def desfases(a: pd.Series, b: pd.Series) -> tuple[int, float]:
    """Busca el mayor |r| entre -2 y 2 días tras alinear ambas series al calendario diario."""
    calendario = pd.date_range(min(a.index.min(), b.index.min()), max(a.index.max(), b.index.max()), freq="D")
    a = a.groupby(level=0).first().reindex(calendario)
    b = b.groupby(level=0).first().reindex(calendario)
    resultados = [(d, a.corr(b.shift(-d))) for d in range(-2, 3)]
    return max(resultados, key=lambda x: abs(x[1]) if pd.notna(x[1]) else -1)


def main() -> None:
    """Ejecuta diagnósticos y produce tablas exploratorias para la app."""
    APP.mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet(DATA / "aire_bogota_diario.parquet")
    d["fecha"] = pd.to_datetime(d.fecha)
    d["año"] = d.fecha.dt.year
    d["dia_semana"] = d.fecha.dt.day_of_week
    print("PARTE 0a: correlación por desfase IDEAM")
    i = pd.read_parquet(IDEAM)
    i = i.loc[i.flag_calidad.fillna("").eq("")].copy()
    i["fecha"] = pd.to_datetime(i.fecha)
    def serie(codigo: str, variable: str) -> pd.Series:
        z = i.loc[(i.estacion_ideam_id.astype(str) == codigo) & i.variable.eq(variable)].set_index("fecha").valor
        return pd.to_numeric(z, errors="coerce").sort_index()
    for var in ("tmax_c", "tmin_c"):
        print(var, desfases(serie("21206600", var), serie("21206650", var)))
    for a, b in (("21205710", "21206600"), ("21205710", "21206650")):
        print(f"precip_mm {a} vs {b}", desfases(serie(a, "precip_mm"), serie(b, "precip_mm")))
    print("PARTE 0b: precipitación media por mes y comparación temporada")
    lluvia = i.loc[i.variable.eq("precip_mm") & i.estacion_ideam_id.astype(str).isin(["21206600", "21205710", "21206650"])].copy()
    lluvia["valor"] = pd.to_numeric(lluvia.valor, errors="coerce")
    lluvia["mes"] = lluvia.fecha.dt.month
    mensual = lluvia.groupby(["estacion_ideam_id", "fecha"], as_index=False).agg(valor=("valor", "mean"))
    mensual["mes"] = mensual.fecha.dt.month
    pm = mensual.groupby("mes").valor.mean().rename("precip_mm_dia").reset_index()
    print(pm.to_string(index=False))
    patron = set(pm.nlargest(6, "precip_mm_dia").mes)
    secos = {12, 1, 2, 7, 8}; humedos = set(range(1, 13)) - secos
    print(f"Meses con más precipitación: {sorted(patron)}; coinciden con temporada lluviosa fija: {patron <= humedos}")
    print("PARTE 0c")
    pares = d[["pm25", "pm10"]].dropna()
    print(f"correlación={pares.pm25.corr(pares.pm10):.4f}; mediana razón pm25/pm10={ (pares.pm25 / pares.pm10.replace(0, np.nan)).median():.4f}; n={len(pares)}")
    cobertura = d.assign(año_mes=d.fecha.dt.to_period("M").astype(str)).groupby(["estacion_id", "año_mes"]).pm25.apply(lambda x: 100*x.notna().mean()).rename("pct_dias_pm25").reset_index()
    # La exploración conserva el detalle largo separado; la app usa la matriz compacta que genera preparar_cobertura_app.py.
    cobertura.to_csv(APP / "cobertura_estacion_mes_detalle.csv", index=False)

    # El umbral queda omitido hasta disponer de una cifra oficial citada.
    categorias = ["estacion", "localidad", "dia_semana", "mes", "temporada", "es_festivo", "llueve", "precip_1d_antes_ge_1", "cuartil_vel_ciudad", "año"]
    d["precip_1d_antes_ge_1"] = np.where(d.precip_1d_antes.notna(), d.precip_1d_antes.ge(1).astype(str), np.nan)
    d["cuartil_vel_ciudad"] = pd.qcut(d.vel_ciudad_ms, 4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
    tablas = []
    for variable in categorias:
        z = d.groupby(variable, dropna=False).pm25.agg(media="mean", mediana="median", n="count").reset_index().rename(columns={variable:"grupo"})
        z.insert(0, "variable", variable); tablas.append(z)
    pd.concat(tablas, ignore_index=True).to_csv(APP / "resumen_exploratorio.csv", index=False)
    dif = d.groupby(["estacion_id", "es_fin_semana"]).pm25.mean().unstack()
    dif["laboral_menos_fin_semana"] = dif[False] - dif[True]
    dif.reset_index().to_csv(APP / "diferencia_laboral_fin_semana.csv", index=False)
    num = [c for c in d.select_dtypes(include=np.number).columns if c != "pm25"]
    corr = [{"grupo":"global", "variable":c, "spearman":d[["pm25",c]].corr(method="spearman").iloc[0,1]} for c in num]
    for est, g in d.groupby("estacion_id"):
        corr += [{"grupo":est, "variable":c, "spearman":g[["pm25",c]].corr(method="spearman").iloc[0,1]} for c in num]
    pd.DataFrame(corr).to_csv(APP / "correlaciones_spearman.csv", index=False)
    if UMBRAL_OMS_24H is not None or UMBRAL_COL_24H is not None:
        raise NotImplementedError("Completar el cálculo solo tras documentar fuentes oficiales.")
    print("Porcentaje sobre umbrales 24 h: omitido; umbrales None pendientes de fuente oficial.")
    print("Tablas exploratorias escritas en", APP)


if __name__ == "__main__":
    main()
