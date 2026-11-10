"""Integra aire, viento de ciudad y estaciones IDEAM en una malla diaria.
Lee únicamente productos de data/interim y la asignación/catálogos procesados.
Produce aire_bogota_diario.parquet y cobertura_maestra.csv en data/processed.
Reindexa las series antes de rezagos y conserva como NaN todas las ausencias.
"""

from __future__ import annotations

from pathlib import Path

import holidays
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
AIR_PATH = INTERIM_DIR / "aire_largo.parquet"
WIND_OWN_PATH = INTERIM_DIR / "viento_limpio.parquet"
WIND_CITY_PATH = INTERIM_DIR / "viento_ciudad.parquet"
IDEAM_PATH = INTERIM_DIR / "ideam_largo.parquet"
ASSIGNMENT_PATH = PROCESSED_DIR / "asignacion_estaciones.csv"
OUTPUT_PATH = PROCESSED_DIR / "aire_bogota_diario.parquet"
COVERAGE_PATH = PROCESSED_DIR / "cobertura_maestra.csv"
INICIO = pd.Timestamp("2023-10-24")
FIN = pd.Timestamp("2026-10-23")
CALENDARIO = pd.date_range(INICIO, FIN, freq="D")
HUECO_INICIO = pd.Timestamp("2025-08-04")
HUECO_FIN = pd.Timestamp("2025-10-16")
ESTACIONES_LLUVIA_CIUDAD = {"21206600", "21205710", "21206650"}
VARIABLES_BASE = ["pm25", "vel_ciudad_ms", "precip_mm", "tmax_c", "tmin_c"]


def _id_code(valor: object) -> str:
    """Normaliza un código IDEAM que puede venir como número o texto.

    Parámetros: código crudo. Devuelve identificador de texto comparable.
    """
    try:
        return str(int(float(valor)))
    except (TypeError, ValueError):
        return str(valor).strip()


def _serie_ideam(ideam: pd.DataFrame, codigo: object, variable: str) -> pd.Series:
    """Devuelve la serie de una estación en calendario completo y válida.

    Parámetros: IDEAM largo, código y variable. Devuelve serie diaria reindexada.
    """
    codigo = _id_code(codigo)
    datos = ideam.loc[(ideam.estacion_ideam_id.map(_id_code) == codigo) & ideam.variable.eq(variable)].copy()
    if datos.empty:
        return pd.Series(np.nan, index=CALENDARIO, dtype=float)
    datos["fecha"] = pd.to_datetime(datos["fecha"]).dt.normalize()
    datos["valor"] = pd.to_numeric(datos["valor"], errors="coerce")
    # Las banderas de calidad invalidan el uso en la tabla maestra; interim conserva el valor crudo.
    validos = datos.flag_calidad.fillna("").eq("")
    serie = datos.assign(_valor=datos.valor.where(validos)).drop_duplicates("fecha").set_index("fecha")["_valor"]
    return serie.reindex(CALENDARIO)


def _series_pm(aire: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Construye PM original y limpio por estación sobre el calendario completo.

    Parámetros: aire largo. Devuelve PM2.5/PM10 originales alineados por estación.
    """
    datos = aire.copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"]).dt.normalize()
    datos["valor"] = pd.to_numeric(datos["valor"], errors="coerce")
    tabla = datos.pivot_table(index="fecha", columns=["estacion_id", "contaminante"], values="valor", aggfunc="first")
    salida = {}
    for estacion in sorted(datos.estacion_id.dropna().unique()):
        panel = pd.DataFrame(index=CALENDARIO)
        for variable, contaminante in (("pm25", "PM2.5"), ("pm10", "PM10")):
            col = (estacion, contaminante)
            original = tabla[col].reindex(CALENDARIO) if col in tabla.columns else pd.Series(np.nan, index=CALENDARIO)
            panel[f"{variable}_original"] = original
            panel[variable] = original.where(original.ge(0))
        panel["pm25_faltante"] = panel.pm25.isna()
        panel["pm10_faltante"] = panel.pm10.isna()
        panel["pm_invalido"] = panel.pm25_original.lt(0).fillna(False) | panel.pm10_original.lt(0).fillna(False)
        salida[estacion] = panel
    return salida


def _series_viento() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Lee el índice y las series propias ya limpiadas de viento.

    Parámetros: ninguno. Devuelve el índice alineado y panel propio por estación.
    """
    ciudad = pd.read_parquet(WIND_CITY_PATH)
    ciudad["fecha"] = pd.to_datetime(ciudad.fecha).dt.normalize()
    ciudad = ciudad.set_index("fecha").reindex(CALENDARIO)
    ciudad.index.name = "fecha"
    viento = pd.read_parquet(WIND_OWN_PATH)
    viento["fecha"] = pd.to_datetime(viento.fecha).dt.normalize()
    panel = viento.pivot_table(index="fecha", columns=["estacion_id", "variable"], values="valor", aggfunc="first")
    estaciones = sorted(viento.estacion_id.dropna().unique())
    resultado = {}
    for estacion in estaciones:
        filas = pd.DataFrame(index=CALENDARIO)
        for variable in ("vel_viento", "dir_viento"):
            clave = (estacion, variable)
            filas[variable] = panel[clave].reindex(CALENDARIO) if clave in panel.columns else np.nan
        resultado[estacion] = filas
    return ciudad, resultado


def _precip_ciudad(ideam: pd.DataFrame) -> pd.Series:
    """Cuenta estaciones IDEAM lluviosas, exigiendo dos datos válidos como mínimo.

    Parámetros: IDEAM largo. Devuelve conteo diario o NaN si hay menos de dos datos.
    """
    series = [_serie_ideam(ideam, codigo, "precip_mm") for codigo in sorted(ESTACIONES_LLUVIA_CIUDAD)]
    panel = pd.concat(series, axis=1)
    conocidos = panel.notna().sum(axis=1)
    lluviosos = panel.ge(1).where(panel.notna()).sum(axis=1, min_count=1)
    return lluviosos.where(conocidos >= 2).rename("lluvia_ciudad_n")


def _tabla_maestra() -> pd.DataFrame:
    """Integra malla diaria, contaminantes, viento, IDEAM y calendario.

    Parámetros: ninguno. Devuelve una fila por día y estación de aire.
    """
    if not ASSIGNMENT_PATH.exists():
        raise FileNotFoundError(f"Ejecuta primero src/datos/asignar_estaciones.py: falta {ASSIGNMENT_PATH}")
    asignacion = pd.read_csv(ASSIGNMENT_PATH)
    aire = pd.read_parquet(AIR_PATH)
    ideam = pd.read_parquet(IDEAM_PATH)
    viento_ciudad, viento_propio = _series_viento()
    pm_por_estacion = _series_pm(aire)
    lluvia_n = _precip_ciudad(ideam)
    dias_semana = CALENDARIO.day_of_week
    anos = range(INICIO.year, FIN.year + 1)
    festivos = holidays.country_holidays("CO", years=anos)
    filas = []
    for asignacion in asignacion.to_dict("records"):
        estacion = asignacion["estacion_id"]
        if estacion not in pm_por_estacion:
            raise ValueError(f"La asignación no coincide con aire_largo.parquet: {estacion}")
        pm = pm_por_estacion[estacion]
        salida = pd.DataFrame(index=CALENDARIO)
        salida.index.name = "fecha"
        salida["estacion_id"] = estacion
        salida["estacion"] = asignacion["estacion"]
        salida["es_movil"] = bool(asignacion["es_movil"])
        for col in ("pm25", "pm10", "pm25_faltante", "pm10_faltante", "pm_invalido"):
            salida[col] = pm[col]

        salida["vel_ciudad_ms"] = viento_ciudad["vel_ciudad_ms"]
        salida["n_est_viento"] = viento_ciudad["n_estaciones"]
        propio = viento_propio.get(estacion, pd.DataFrame(index=CALENDARIO, columns=["vel_viento", "dir_viento"], dtype=float))
        salida["vel_viento_propia"] = propio["vel_viento"]
        radianes = np.deg2rad(propio["dir_viento"])
        salida["dir_sin"] = np.sin(radianes)
        salida["dir_cos"] = np.cos(radianes)

        precip = _serie_ideam(ideam, asignacion.get("precip_estacion_id"), "precip_mm")
        salida["precip_mm"] = precip
        salida["precip_1d_antes"] = precip.shift(1)
        salida["precip_3d_acum"] = precip.shift(1).rolling(3, min_periods=3).sum()
        llueve = pd.Series(pd.NA, index=CALENDARIO, dtype="boolean")
        tiene_precip = precip.notna()
        llueve.loc[tiene_precip] = precip.loc[tiene_precip].ge(1)
        salida["llueve"] = llueve
        salida["lluvia_ciudad_n"] = lluvia_n
        salida["dist_precip_km"] = asignacion.get("precip_dist_km", np.nan)
        salida["precip_estacion_id"] = asignacion.get("precip_estacion_id", np.nan)

        tmax = _serie_ideam(ideam, asignacion.get("temp_estacion_id"), "tmax_c")
        tmin = _serie_ideam(ideam, asignacion.get("temp_estacion_id"), "tmin_c")
        ambos = tmax.notna() & tmin.notna()
        salida["tmax_c"] = tmax
        salida["tmin_c"] = tmin
        salida["tmedia_c"] = ((tmax + tmin) / 2).where(ambos)
        salida["amplitud_c"] = (tmax - tmin).where(ambos)
        salida["dist_temp_km"] = asignacion.get("temp_dist_km", np.nan)
        salida["temp_estacion_id"] = asignacion.get("temp_estacion_id", np.nan)

        salida["dia_semana"] = dias_semana
        salida["mes"] = CALENDARIO.month
        salida["es_fin_semana"] = np.asarray(dias_semana >= 5, dtype=bool)
        salida["es_festivo"] = [dia.date() in festivos for dia in CALENDARIO]
        # SUPUESTO: se usan los meses secos (dic-ene-feb-jul-ago) y lluviosos
        # (mar-abr-may-sep-oct-nov) indicados por el equipo; verificar con IDEAM
        # antes de presentar esta clasificación como fuente oficial en la app.
        salida["temporada"] = ["seca" if mes in {12, 1, 2, 7, 8} else "lluviosa" for mes in CALENDARIO.month]
        salida["localidad"] = asignacion.get("localidad", np.nan)
        salida["altitud_m"] = asignacion.get("altitud_m", np.nan)
        salida["lat"] = asignacion["lat"]
        salida["lon"] = asignacion["lon"]
        salida["hueco_pm_2025"] = (CALENDARIO >= HUECO_INICIO) & (CALENDARIO <= HUECO_FIN)
        filas.append(salida.reset_index())
    maestra = pd.concat(filas, ignore_index=True)
    orden = [
        "fecha", "estacion_id", "estacion", "es_movil", "pm25", "pm10", "pm25_faltante", "pm10_faltante", "pm_invalido", "hueco_pm_2025",
        "vel_ciudad_ms", "n_est_viento", "vel_viento_propia", "dir_sin", "dir_cos",
        "precip_mm", "precip_1d_antes", "precip_3d_acum", "llueve", "lluvia_ciudad_n", "dist_precip_km", "precip_estacion_id",
        "tmax_c", "tmin_c", "tmedia_c", "amplitud_c", "dist_temp_km", "temp_estacion_id",
        "dia_semana", "mes", "es_fin_semana", "es_festivo", "temporada", "localidad", "altitud_m", "lat", "lon",
    ]
    return maestra[orden].sort_values(["estacion_id", "fecha"]).reset_index(drop=True)


def _diagnosticos_representatividad(ideam: pd.DataFrame) -> None:
    """Imprime correlación y diferencia para las asignaciones IDEAM esperadas.

    Parámetros: tabla IDEAM larga. Devuelve None e imprime pares comparables.
    """
    print("\nREPRESENTATIVIDAD ENTRE ESTACIONES IDEAM")
    for variable in ("tmax_c", "tmin_c"):
        ng = _serie_ideam(ideam, "21206600", variable)
        sc = _serie_ideam(ideam, "21206650", variable)
        pares = pd.concat([ng.rename("nueva_generacion"), sc.rename("san_cayetano")], axis=1).dropna()
        r = pares.nueva_generacion.corr(pares.san_cayetano) if len(pares) >= 2 else np.nan
        diferencia = (pares.san_cayetano - pares.nueva_generacion).mean() if len(pares) else np.nan
        print(f"{variable}: r={r:.3f}; diferencia media San Cayetano - Nueva Generación={diferencia:.3f} °C; n={len(pares)}")
    for a, b, etiqueta in (("21206600", "21205710", "Nueva Generación vs Jardín Botánico"), ("21205710", "21206650", "Jardín Botánico vs San Cayetano")):
        serie_a = _serie_ideam(ideam, a, "precip_mm")
        serie_b = _serie_ideam(ideam, b, "precip_mm")
        pares = pd.concat([serie_a.rename("a"), serie_b.rename("b")], axis=1).dropna()
        r = pares.a.corr(pares.b) if len(pares) >= 2 else np.nan
        acuerdo = ((pares.a.ge(1)) == (pares.b.ge(1))).mean() * 100 if len(pares) else np.nan
        print(f"precipitación {etiqueta}: r={r:.3f}; acuerdo lluvia >=1 mm={acuerdo:.2f}%; n={len(pares)}")


def _cobertura(maestra: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula cobertura de PM y casos completos del modelo base.

    Parámetros: tabla maestra. Devuelve resumen por estación y meses sin PM2.5.
    """
    meses = pd.period_range(INICIO, FIN, freq="M")
    filas, meses_cero = [], []
    for estacion_id, grupo in maestra.groupby("estacion_id", sort=False):
        grupo = grupo.sort_values("fecha")
        pm25_full = int(grupo.pm25.notna().sum())
        pm10_full = int(grupo.pm10.notna().sum())
        sin_hueco = grupo.loc[~grupo.hueco_pm_2025]
        pm25_sh = int(sin_hueco.pm25.notna().sum())
        pm10_sh = int(sin_hueco.pm10.notna().sum())
        completos_sh = sin_hueco[VARIABLES_BASE].notna().all(axis=1)
        ceros = []
        for mes in meses:
            periodo = grupo.loc[grupo.fecha.dt.to_period("M").eq(mes)]
            if periodo.pm25.notna().sum() == 0:
                ceros.append(str(mes))
                meses_cero.append({"estacion_id": estacion_id, "mes": str(mes)})
        filas.append({
            "estacion_id": estacion_id,
            "estacion": grupo.estacion.iloc[0],
            "pm25_dias": pm25_full,
            "pm25_cobertura_pct": 100 * pm25_full / len(CALENDARIO),
            "pm10_dias": pm10_full,
            "pm10_cobertura_pct": 100 * pm10_full / len(CALENDARIO),
            "pm25_dias_sin_hueco": pm25_sh,
            "pm25_cobertura_sin_hueco_pct": 100 * pm25_sh / len(sin_hueco),
            "pm10_dias_sin_hueco": pm10_sh,
            "pm10_cobertura_sin_hueco_pct": 100 * pm10_sh / len(sin_hueco),
            "meses_pm25_0": "; ".join(ceros) if ceros else "ninguno",
            "casos_completos_modelo_base_sin_hueco": int(completos_sh.sum()),
            "casos_completos_modelo_base_pct_sin_hueco": 100 * float(completos_sh.mean()),
        })
    resumen = pd.DataFrame(filas).sort_values("pm25_cobertura_sin_hueco_pct").reset_index(drop=True)
    return resumen, pd.DataFrame(meses_cero)


def _conteos_ventana(maestra: pd.DataFrame) -> pd.DataFrame:
    """Cuenta PM2.5 válido y casos completos por ventanas anuales.

    Parámetros: tabla maestra. Devuelve total y ventanas temporales definidas.
    """
    ventanas = [
        ("2023-10-24 a 2024-10-23", pd.Timestamp("2023-10-24"), pd.Timestamp("2024-10-23")),
        ("2024-10-24 a 2025-10-23", pd.Timestamp("2024-10-24"), pd.Timestamp("2025-10-23")),
        ("2025-10-24 a 2026-10-23", pd.Timestamp("2025-10-24"), pd.Timestamp("2026-10-23")),
    ]
    completos = maestra[VARIABLES_BASE].notna().all(axis=1)
    filas = [{"ventana": "total", "pm25_valido": int(maestra.pm25.notna().sum()), "casos_completos_modelo_base": int(completos.sum())}]
    for nombre, inicio, fin in ventanas:
        parte = maestra.loc[maestra.fecha.between(inicio, fin)]
        completos_parte = parte[VARIABLES_BASE].notna().all(axis=1)
        filas.append({"ventana": nombre, "pm25_valido": int(parte.pm25.notna().sum()), "casos_completos_modelo_base": int(completos_parte.sum())})
    return pd.DataFrame(filas)


def main() -> None:
    """Construye y valida la tabla maestra y sus reportes de cobertura.

    Parámetros: ninguno. Escribe parquet y CSV bajo data/processed.
    """
    maestra = _tabla_maestra()
    if len(maestra) != 20_824:
        raise ValueError(f"Malla inesperada: {len(maestra)} filas; se esperaban 20,824")
    if maestra.duplicated(["fecha", "estacion_id"]).any():
        raise ValueError("La llave fecha-estacion_id no es única")
    ideam = pd.read_parquet(IDEAM_PATH)
    _diagnosticos_representatividad(ideam)
    cobertura, meses_cero = _cobertura(maestra)
    print("\nCOBERTURA POR ESTACION, ORDENADA DE MENOR A MAYOR")
    columnas = ["estacion_id", "estacion", "pm25_cobertura_pct", "pm10_cobertura_pct", "pm25_cobertura_sin_hueco_pct", "pm10_cobertura_sin_hueco_pct", "meses_pm25_0", "casos_completos_modelo_base_pct_sin_hueco"]
    print(cobertura[columnas].to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    conteos = _conteos_ventana(maestra)
    print("\nFILAS VALIDAS PM2.5 Y CASOS COMPLETOS DEL MODELO BASE")
    print(conteos.to_string(index=False))
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    maestra.to_parquet(OUTPUT_PATH, index=False, engine="pyarrow")
    cobertura.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    print(f"\nEscritos: {OUTPUT_PATH} y {COVERAGE_PATH}; filas={len(maestra)}; estaciones={maestra.estacion_id.nunique()}; días={maestra.fecha.nunique()}")


if __name__ == "__main__":
    main()
