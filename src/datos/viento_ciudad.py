"""Limpia controles de calidad de viento y calcula un índice diario de ciudad.
Lee data/interim/viento_largo.parquet sin modificarlo.
Produce viento_limpio.parquet y viento_ciudad.parquet en data/interim.
Imprime auditoría de reglas, valores sospechosos, cobertura y correlaciones.
"""

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
ENTRADA = INTERIM_DIR / "viento_largo.parquet"
SALIDA_LIMPIA = INTERIM_DIR / "viento_limpio.parquet"
SALIDA_INDICE = INTERIM_DIR / "viento_ciudad.parquet"
# SUPUESTO: Kennedy y San Cristóbal se excluyen por correlación negativa o débil
# con la mediana de las otras estaciones (-0.11 y 0.11, respectivamente).
EXCLUIDAS_INDICE = {"kennedy", "san_cristobal"}
REGLAS = ("vel_negativa", "dir_por_vel_invalida", "dir_racha")


def _ordenar_grupo(grupo: pd.DataFrame) -> pd.DataFrame:
    """Ordena una serie de estación por fecha para detectar rachas.

    Parámetros: filas de una estación y variable. Devuelve filas cronológicas.
    """
    return grupo.sort_values("fecha")


def _marcar_rachas(direccion: pd.DataFrame) -> pd.Series:
    """Marca direcciones en rachas constantes de al menos cuatro días.

    Parámetros: direcciones de una estación. Devuelve máscara booleana indexada.
    """
    grupo = _ordenar_grupo(direccion)
    fechas = pd.to_datetime(grupo["fecha"]).tolist()
    valores = grupo["valor"].tolist()
    marcadas = pd.Series(False, index=grupo.index)
    inicio = 0
    for posicion in range(1, len(grupo) + 1):
        continua = (
            posicion < len(grupo)
            and pd.notna(valores[posicion])
            and pd.notna(valores[posicion - 1])
            and valores[posicion] == valores[posicion - 1]
            and fechas[posicion] - fechas[posicion - 1] == pd.Timedelta(days=1)
        )
        if continua:
            continue
        if posicion - inicio >= 4 and pd.notna(valores[inicio]):
            marcadas.loc[grupo.index[inicio:posicion]] = True
        inicio = posicion
    return marcadas


def limpiar(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Aplica las tres reglas en orden y conserva valor y banderas.

    Parámetros: tabla larga original. Devuelve tabla limpia y máscaras por regla.
    """
    requerido = {"fecha", "estacion", "estacion_id", "variable", "valor"}
    faltan = requerido - set(df.columns)
    if faltan:
        raise ValueError(f"Faltan columnas requeridas: {sorted(faltan)}")
    salida = df[["fecha", "estacion", "estacion_id", "variable", "valor"]].copy()
    salida["fecha"] = pd.to_datetime(salida["fecha"])
    salida["valor_original"] = pd.to_numeric(salida["valor"], errors="coerce")
    salida["valor"] = salida["valor_original"].copy()
    salida["flag_calidad"] = ""
    salida["sensor_dudoso"] = salida["estacion_id"].isin(EXCLUIDAS_INDICE)
    mascaras = {regla: pd.Series(False, index=salida.index) for regla in REGLAS}

    mascaras["vel_negativa"] = salida["variable"].eq("vel_viento") & salida["valor"].lt(0)
    salida.loc[mascaras["vel_negativa"], "valor"] = np.nan
    salida.loc[mascaras["vel_negativa"], "flag_calidad"] = "vel_negativa"

    claves = salida.loc[mascaras["vel_negativa"], ["fecha", "estacion_id"]].drop_duplicates()
    invalidas = pd.MultiIndex.from_frame(claves)
    direccion = salida["variable"].eq("dir_viento")
    idx_dir = pd.MultiIndex.from_frame(salida[["fecha", "estacion_id"]])
    mascaras["dir_por_vel_invalida"] = direccion & pd.Series(idx_dir.isin(invalidas), index=salida.index)
    salida.loc[mascaras["dir_por_vel_invalida"], "valor"] = np.nan
    salida.loc[mascaras["dir_por_vel_invalida"], "flag_calidad"] = "dir_por_vel_invalida"

    for _, grupo in salida.loc[direccion].groupby("estacion_id"):
        serie_mask = _marcar_rachas(grupo)
        mascaras["dir_racha"].loc[serie_mask.index] |= serie_mask
    # La bandera conserva ambas causas cuando una dirección ya fue invalidada
    # por velocidad y pertenece también a una racha de valores originales.
    mascaras["dir_racha"] &= direccion & salida["valor"].notna()
    salida.loc[mascaras["dir_racha"], "valor"] = np.nan
    salida.loc[mascaras["dir_racha"], "flag_calidad"] = "dir_racha"
    salida["sensor_dudoso"] = salida["sensor_dudoso"].astype(bool)
    return salida, mascaras


def _calcular_indice(limpio: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Calcula índice diario y panel de velocidades normalizadas.

    Parámetros: tabla limpia larga. Devuelve índice, panel normalizado y medias.
    """
    vel = limpio.loc[limpio["variable"].eq("vel_viento")].pivot(
        index="fecha", columns="estacion_id", values="valor"
    ).sort_index()
    incluidas = [c for c in vel.columns if c not in EXCLUIDAS_INDICE]
    medias = vel[incluidas].mean()
    normalizadas = vel[incluidas].div(medias)
    n = normalizadas.notna().sum(axis=1)
    indice = pd.DataFrame({
        "fecha": vel.index,
        "vel_ciudad_ms": normalizadas.median(axis=1) * medias.mean(),
        "n_estaciones": n.to_numpy(),
    })
    indice.loc[indice["n_estaciones"] < 3, "vel_ciudad_ms"] = np.nan
    return indice, normalizadas, medias


def _correlacion(x: pd.Series, y: pd.Series) -> tuple[float, int]:
    """Calcula Pearson con pares completos y devuelve coeficiente y cantidad.

    Parámetros: dos series alineables. Devuelve correlación y días comparables.
    """
    pares = pd.concat([x, y], axis=1).dropna()
    return (pares.iloc[:, 0].corr(pares.iloc[:, 1]) if len(pares) >= 2 else np.nan, len(pares))


def _contar_rachas_valor(grupo: pd.DataFrame, columna: str = "valor") -> list[int]:
    """Cuenta segmentos consecutivos de cuatro o más mediciones idénticas.

    Parámetros: serie larga de una estación. Devuelve longitudes de racha.
    """
    ordenado = grupo.sort_values("fecha")
    fechas, valores = pd.to_datetime(ordenado.fecha).tolist(), ordenado[columna].tolist()
    longitudes, inicio = [], 0
    for posicion in range(1, len(ordenado) + 1):
        continua = (
            posicion < len(ordenado) and pd.notna(valores[posicion])
            and pd.notna(valores[posicion - 1]) and valores[posicion] == valores[posicion - 1]
            and fechas[posicion] - fechas[posicion - 1] == pd.Timedelta(days=1)
        )
        if not continua:
            if posicion - inicio >= 4 and pd.notna(valores[inicio]):
                longitudes.append(posicion - inicio)
            inicio = posicion
    return longitudes


def _reporte(original: pd.DataFrame, limpio: pd.DataFrame, mascaras: dict, indice: pd.DataFrame, norm: pd.DataFrame, medias: pd.Series) -> None:
    """Imprime conteos de calidad, cobertura y comparaciones del índice.

    Parámetros: entrada, limpia, máscaras, índice, panel normalizado y medias.
    """
    print("\n--- Cambios por regla y estación ---")
    por_regla = {}
    for regla in REGLAS:
        cuenta = mascaras[regla].groupby(limpio["estacion_id"]).sum().astype(int)
        por_regla[regla] = cuenta
        print(f"{regla}: total={int(cuenta.sum())}; " + ", ".join(f"{k}={v}" for k, v in cuenta.items() if v))
    dias_a = limpio.loc[mascaras["vel_negativa"], ["fecha", "estacion_id"]].drop_duplicates()
    print(f"Solape a/b por fecha-estación: {len(dias_a)} (cada velocidad inválida dispara la regla b); filas compartidas literalmente: 0 porque son variables distintas.")
    candidatas_racha = pd.Series(False, index=original.index)
    for _, grupo in original.loc[original.variable.eq("dir_viento")].groupby("estacion_id"):
        candidatas_racha.loc[_marcar_rachas(grupo).index] = _marcar_rachas(grupo)
    solape_bc = mascaras["dir_por_vel_invalida"] & candidatas_racha
    print(f"Solape b/c potencial antes de aplicar b: {int(solape_bc.sum())} filas; c aplicada tras b: {int(mascaras['dir_racha'].sum())} filas nuevas.")

    print("\n--- Rachas de velocidad repetida (solo conteo; no se modifican) ---")
    vel_original = original.loc[original.variable.eq("vel_viento")]
    for estacion, grupo in vel_original.groupby("estacion_id"):
        longitudes = _contar_rachas_valor(grupo)
        if longitudes:
            print(f"{estacion}: {len(longitudes)} rachas de 4+ días; {sum(longitudes)} filas; longitudes={longitudes}")

    raw_dir = original.loc[original["variable"].eq("dir_viento")].copy()
    n81 = int(raw_dir["valor"].eq(81).sum())
    dias_invalidos = set(map(tuple, limpio.loc[mascaras["dir_por_vel_invalida"], ["fecha", "estacion_id"]].to_numpy()))
    rachas = set(map(tuple, limpio.loc[mascaras["dir_racha"], ["fecha", "estacion_id"]].to_numpy()))
    dias_81 = raw_dir.loc[raw_dir["valor"].eq(81), ["fecha", "estacion_id"]]
    cae = [tuple(x) in dias_invalidos or tuple(x) in rachas for x in dias_81.to_numpy()]
    print("\n--- Dirección exactamente 81 frente a 80 y 82 ---")
    print(f"81={n81}; dentro de racha o día con velocidad inválida={sum(cae)}; aisladas={n81-sum(cae)}; 80={int(raw_dir.valor.eq(80).sum())}; 82={int(raw_dir.valor.eq(82).sum())}")

    print("\n--- Cobertura del índice ---")
    n = indice["n_estaciones"]
    print(f"n_estaciones: mínimo={int(n.min())}; mediana={n.median():g}; días <5={int((n<5).sum())}; días <3 (índice NaN)={int((n<3).sum())}")

    print("\n--- Correlación estación / índice ---")
    idx = indice.set_index("fecha")["vel_ciudad_ms"]
    for estacion in original["estacion_id"].drop_duplicates():
        nombre = original.loc[original.estacion_id.eq(estacion), "estacion"].iloc[0]
        vel_est = limpio.loc[(limpio.estacion_id.eq(estacion)) & limpio.variable.eq("vel_viento")].set_index("fecha").valor
        if estacion in norm:
            # SUPUESTO: comparación leave-one-out evita correlación mecánica
            # entre una estación y un índice que la incluye.
            otras = norm.drop(columns=estacion)
            loo = otras.median(axis=1) * medias.drop(estacion).mean()
            loo.loc[otras.notna().sum(axis=1) < 3] = np.nan
            r, dias = _correlacion(vel_est, loo)
        else:
            r, dias = _correlacion(vel_est, idx)
        print(f"{nombre} ({estacion}): r={r:.3f}; días={dias}")

    incluida = norm.columns
    simple = limpio.loc[limpio.variable.eq("vel_viento")].pivot(index="fecha", columns="estacion_id", values="valor")[list(incluida)].median(axis=1)
    r, dias = _correlacion(simple, idx)
    print(f"\n--- Índice vs mediana simple sin normalizar ---\nr={r:.3f}; días={dias}")


def main() -> None:
    """Ejecuta la limpieza, crea los parquets nuevos e imprime la auditoría.

    Parámetros: ninguno. Lee el parquet original y escribe dos salidas interim.
    """
    original = pd.read_parquet(ENTRADA)
    limpio, mascaras = limpiar(original)
    indice, norm, medias = _calcular_indice(limpio)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    limpio.to_parquet(SALIDA_LIMPIA, index=False, engine="pyarrow")
    indice.to_parquet(SALIDA_INDICE, index=False, engine="pyarrow")
    _reporte(original, limpio, mascaras, indice, norm, medias)
    print(f"\nEscritos: {SALIDA_LIMPIA} y {SALIDA_INDICE}")


if __name__ == "__main__":
    main()
