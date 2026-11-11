"""Prepara escenarios y aplica el modelo de anomalías v2 sin leer fuentes crudas.
Lee el artefacto v2 y estadísticas de entrenamiento de la tabla procesada.
Completa solo variables no solicitadas usando reglas expresas y auditables.
Devuelve predicción, climatología, intervalo multiplicativo y datos del tornado.
"""
import numpy as np
import pandas as pd
import streamlit as st

FIN_ENTRENAMIENTO = pd.Timestamp("2025-10-23")
VARIABLES_MODELO = [
    "vel_ciudad_ms", "precip_mm", "precip_1d_antes", "precip_3d_acum",
    "llueve", "lluvia_ciudad_n", "tmax_anom", "tmin_anom", "amplitud_c",
    "es_fin_semana", "es_festivo", "dia_semana",
]
VARIABLES_ENTRADA_NUMERICA = [
    "vel_ciudad_ms", "precip_mm", "precip_1d_antes", "tmax_c", "tmin_c",
]
COLUMNAS_MODELO_COMPLETO = [
    "vel_ciudad_ms", "precip_mm", "precip_1d_antes", "precip_3d_acum",
    "llueve", "lluvia_ciudad_n", "tmax_anom", "tmin_anom", "amplitud_c",
    "dia_semana", "es_fin_semana", "es_festivo", "mes", "lat", "lon",
    "es_movil", "estacion_id",
]


@st.cache_data(show_spinner=False)
def estadisticas_entrenamiento(datos: pd.DataFrame) -> dict:
    """Resume rangos y medianas sin incluir observaciones posteriores al corte."""
    entrenamiento = datos.loc[pd.to_datetime(datos.fecha).le(FIN_ENTRENAMIENTO)].copy()
    if entrenamiento.empty:
        raise ValueError("No hay filas de entrenamiento hasta 2025-10-23.")

    # Las referencias de anomalía se calculan por estación IDEAM como en el ajuste v2.
    media_tmax = entrenamiento.groupby("temp_estacion_id").tmax_c.mean()
    media_tmin = entrenamiento.groupby("temp_estacion_id").tmin_c.mean()
    mediana_tmax = entrenamiento.groupby("temp_estacion_id").tmax_c.median()
    mediana_tmin = entrenamiento.groupby("temp_estacion_id").tmin_c.median()

    cotas = {}
    medianas_entrada = {}
    cuantiles_entrada = {}
    for columna in VARIABLES_ENTRADA_NUMERICA:
        valores = pd.to_numeric(entrenamiento[columna], errors="coerce").dropna()
        if valores.empty:
            raise ValueError(f"No hay valores de entrenamiento para {columna}.")
        cotas[columna] = tuple(float(x) for x in valores.quantile([.01, .99]))
        cuantiles_entrada[columna] = tuple(float(x) for x in valores.quantile([.1, .9]))
        medianas_entrada[columna] = float(valores.median())

    # La suma usa fechas calendario por estación: un faltante no se salta como haría shift por filas.
    lluvia_diaria = entrenamiento.pivot(index="fecha", columns="estacion_id", values="precip_mm")
    calendario = pd.date_range(entrenamiento.fecha.min(), entrenamiento.fecha.max(), freq="D")
    lluvia_diaria = lluvia_diaria.reindex(calendario)
    lluvia_dias_previos = lluvia_diaria.shift(3) + lluvia_diaria.shift(2)
    mediana_lluvia_dias_previos = float(lluvia_dias_previos.stack().median())

    lluvia_por_estado = {}
    for estado in (False, True):
        valores = entrenamiento.loc[entrenamiento.llueve.eq(estado).fillna(False), "lluvia_ciudad_n"].dropna()
        if valores.empty:
            raise ValueError(f"No hay lluvia_ciudad_n de entrenamiento para llueve={estado}.")
        lluvia_por_estado[estado] = float(valores.median())

    # Las distribuciones del tornado corresponden a las mismas filas completas con que se ajustó v2.
    conjunto = datos.copy()
    medias_max = entrenamiento.groupby("temp_estacion_id").tmax_c.mean()
    medias_min = entrenamiento.groupby("temp_estacion_id").tmin_c.mean()
    conjunto["tmax_anom"] = conjunto.tmax_c - conjunto.temp_estacion_id.map(medias_max)
    conjunto["tmin_anom"] = conjunto.tmin_c - conjunto.temp_estacion_id.map(medias_min)
    conjunto["llueve"] = conjunto.llueve.astype(float)
    for columna in ("es_fin_semana", "es_festivo", "es_movil"):
        conjunto[columna] = conjunto[columna].astype(int)
    completas = conjunto.loc[
        conjunto.pm25.notna() & conjunto[COLUMNAS_MODELO_COMPLETO].notna().all(axis=1)
        & conjunto.fecha.le(FIN_ENTRENAMIENTO)
    ]
    features_train = completas[VARIABLES_MODELO]
    mediana_variables = features_train.median().to_dict()
    cuantiles_variables = {
        columna: tuple(float(x) for x in features_train[columna].quantile([.1, .9]))
        for columna in VARIABLES_MODELO
    }
    return {
        "cotas_entrada": cotas,
        "cuantiles_entrada": cuantiles_entrada,
        "medianas_entrada": medianas_entrada,
        "media_tmax_ideam": {int(k): float(v) for k, v in media_tmax.items()},
        "media_tmin_ideam": {int(k): float(v) for k, v in media_tmin.items()},
        "mediana_tmax_ideam": {int(k): float(v) for k, v in mediana_tmax.items()},
        "mediana_tmin_ideam": {int(k): float(v) for k, v in mediana_tmin.items()},
        "mediana_d3_d2": mediana_lluvia_dias_previos,
        "mediana_lluvia_ciudad_n": lluvia_por_estado,
        "mediana_variables": mediana_variables,
        "cuantiles_variables": cuantiles_variables,
        "mediana_dia_semana": int(round(float(entrenamiento.dia_semana.median()))),
        "meses": sorted(int(x) for x in entrenamiento.mes.dropna().unique()),
        "dias_semana": sorted(int(x) for x in entrenamiento.dia_semana.dropna().unique()),
        "estaciones": sorted(str(x) for x in entrenamiento.estacion_id.dropna().unique()),
        "pm25_entrenamiento": entrenamiento.pm25.dropna().to_numpy(),
        "n_train": int(len(completas)),
    }


def validar_escenario(escenario: dict, estadisticas: dict, estaciones_ideam: set[str]) -> None:
    """Rechaza entradas no finitas o que exceden el rango p1-p99 del entrenamiento."""
    if float(escenario["tmax_c"]) < float(escenario["tmin_c"]):
        raise ValueError("tmax_c debe ser mayor o igual que tmin_c.")
    for columna, (minimo, maximo) in estadisticas["cotas_entrada"].items():
        valor = float(escenario[columna])
        if not np.isfinite(valor) or valor < minimo or valor > maximo:
            raise ValueError(f"{columna} debe permanecer entre {minimo:.3f} y {maximo:.3f} (p1-p99 del entrenamiento).")
    if str(escenario["estacion_id"]) not in estaciones_ideam:
        raise ValueError("La estación seleccionada no tiene asignación térmica publicada.")
    if int(escenario["mes"]) not in estadisticas["meses"]:
        raise ValueError("El mes elegido no aparece en el entrenamiento.")
    if int(escenario["dia_semana"]) not in estadisticas["dias_semana"]:
        raise ValueError("El día elegido no aparece en el entrenamiento.")


def climatologia_escenario(artefacto: dict, estacion_id: str, mes: int) -> float:
    """Consulta climatología estación-mes, con los respaldos guardados en v2."""
    tabla = artefacto["climatologia"]
    par = tabla.loc[tabla.estacion_id.eq(str(estacion_id)) & tabla.mes.eq(int(mes))]
    if not par.empty and int(par.iloc[0]["count"]) >= 10:
        return float(par.iloc[0]["mean"])
    medias = artefacto["media_estacion"]
    if str(estacion_id) in medias:
        return float(medias[str(estacion_id)])
    return float(artefacto["media_global"])


def predecir_anomalia(artefacto: dict, caracteristicas: pd.DataFrame) -> np.ndarray:
    """Aplica el estimador tras verificar el orden exacto de sus 12 variables."""
    if list(caracteristicas.columns) != list(artefacto["features"]):
        raise ValueError("Las columnas deben coincidir con el orden guardado en el artefacto.")
    return np.asarray(artefacto["modelo"].predict(caracteristicas), dtype=float)


@st.cache_data(show_spinner=False)
def reconstruir_prueba_v2(datos: pd.DataFrame) -> pd.DataFrame:
    """Reconstruye las filas evaluables de prueba para comprobar paridad del artefacto."""
    datos = datos.copy()
    datos["fecha"] = pd.to_datetime(datos.fecha)
    entrenamiento = datos.loc[datos.fecha.le(FIN_ENTRENAMIENTO)]
    for columna in ("tmax_c", "tmin_c"):
        medias = entrenamiento.groupby("temp_estacion_id")[columna].mean()
        datos[columna.replace("_c", "_anom")] = datos[columna] - datos.temp_estacion_id.map(medias)
    datos["llueve"] = datos.llueve.astype(float)
    for columna in ("es_fin_semana", "es_festivo", "es_movil"):
        datos[columna] = datos[columna].astype(int)
    completas = datos.loc[
        datos.pm25.notna() & datos[COLUMNAS_MODELO_COMPLETO].notna().all(axis=1)
        & datos.fecha.between("2025-10-24", "2026-10-23")
    ].sort_values(["estacion_id", "fecha"])
    return completas[["fecha", "estacion_id", "pm25", *VARIABLES_MODELO]].reset_index(drop=True)


def fila_caracteristicas(escenario: dict, artefacto: dict, estadisticas: dict,
                         asignacion: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Completa los predictores no solicitados y devuelve fila ordenada y climatología."""
    mapa_estacion = asignacion.set_index("estacion_id")
    estacion_id = str(escenario["estacion_id"])
    if estacion_id not in mapa_estacion.index:
        raise ValueError(f"No hay asignación publicada para {estacion_id}.")
    ideam = int(mapa_estacion.loc[estacion_id, "temp_estacion_id"])
    lluvia_hoy = float(escenario["precip_mm"])
    dia = int(escenario["dia_semana"])
    fila = {
        "vel_ciudad_ms": float(escenario["vel_ciudad_ms"]),
        "precip_mm": lluvia_hoy,
        "precip_1d_antes": float(escenario["precip_1d_antes"]),
        "precip_3d_acum": float(escenario["precip_1d_antes"]) + estadisticas["mediana_d3_d2"],
        "llueve": float(lluvia_hoy >= 1.0),
        "lluvia_ciudad_n": estadisticas["mediana_lluvia_ciudad_n"][lluvia_hoy >= 1.0],
        "tmax_anom": float(escenario["tmax_c"]) - estadisticas["media_tmax_ideam"][ideam],
        "tmin_anom": float(escenario["tmin_c"]) - estadisticas["media_tmin_ideam"][ideam],
        "amplitud_c": float(escenario["tmax_c"]) - float(escenario["tmin_c"]),
        "es_fin_semana": int(dia >= 5),
        "es_festivo": int(bool(escenario["es_festivo"])),
        "dia_semana": dia,
    }
    caracteristicas = pd.DataFrame([[fila[c] for c in artefacto["features"]]],
                                   columns=artefacto["features"])
    nivel_tipico = climatologia_escenario(artefacto, estacion_id, int(escenario["mes"]))
    return caracteristicas, nivel_tipico


def predecir_escenario(escenario: dict, artefacto: dict, estadisticas: dict,
                       asignacion: pd.DataFrame) -> dict:
    """Devuelve PM2.5 estimado, climatología, intervalo y variables completadas."""
    ideam_por_estacion = set(asignacion.estacion_id.astype(str))
    validar_escenario(escenario, estadisticas, ideam_por_estacion)
    caracteristicas, nivel_tipico = fila_caracteristicas(escenario, artefacto, estadisticas, asignacion)
    anomalía = float(predecir_anomalia(artefacto, caracteristicas)[0])
    prediccion = max(0.0, nivel_tipico + anomalía)
    inferior = max(0.0, prediccion * float(artefacto["q10_razon"]))
    superior = max(0.0, prediccion * float(artefacto["q90_razon"]))
    return {
        "prediccion": prediccion,
        "limite_inferior": inferior,
        "limite_superior": superior,
        "nivel_tipico": nivel_tipico,
        "anomalia_predicha": anomalía,
        "caracteristicas": caracteristicas,
        "llueve": bool(caracteristicas.iloc[0]["llueve"]),
        "precip_3d_acum": float(caracteristicas.iloc[0]["precip_3d_acum"]),
        "lluvia_ciudad_n": float(caracteristicas.iloc[0]["lluvia_ciudad_n"]),
        "temp_estacion_id": int(asignacion.set_index("estacion_id").loc[str(escenario["estacion_id"]), "temp_estacion_id"]),
    }


def escenario_referencia(estadisticas: dict, estacion_id: str, mes: int,
                         asignacion: pd.DataFrame) -> dict:
    """Fija una referencia laboral y seca con medianas de entrenamiento."""
    mapa = asignacion.set_index("estacion_id")
    ideam = int(mapa.loc[str(estacion_id), "temp_estacion_id"])
    maximo = estadisticas["mediana_tmax_ideam"][ideam]
    minimo = estadisticas["mediana_tmin_ideam"][ideam]
    return {
        "estacion_id": str(estacion_id), "mes": int(mes),
        "dia_semana": min(4, estadisticas["mediana_dia_semana"]), "es_festivo": False,
        "vel_ciudad_ms": estadisticas["medianas_entrada"]["vel_ciudad_ms"],
        "precip_mm": 0.0, "precip_1d_antes": 0.0,
        "tmax_c": maximo, "tmin_c": minimo,
    }


def crear_preset(nombre: str, referencia: dict, estadisticas: dict) -> dict:
    """Cambia una referencia usando cuantiles de entrenamiento en vez de valores inventados."""
    escenario = referencia.copy()
    p10_viento = float(estadisticas["cuantiles_entrada"]["vel_ciudad_ms"][0])
    p90_viento = float(estadisticas["cuantiles_entrada"]["vel_ciudad_ms"][1])
    p90_lluvia = float(estadisticas["cuantiles_entrada"]["precip_mm"][1])
    dia_laboral = min(4, estadisticas["mediana_dia_semana"])
    if nombre == "Día laborable sin viento":
        escenario.update({"dia_semana": dia_laboral, "es_festivo": False,
                          "vel_ciudad_ms": p10_viento, "precip_mm": 0.0,
                          "precip_1d_antes": 0.0})
    elif nombre == "Fin de semana seco y ventoso":
        escenario.update({"dia_semana": 5, "es_festivo": False,
                          "vel_ciudad_ms": p90_viento, "precip_mm": 0.0,
                          "precip_1d_antes": 0.0})
    elif nombre == "Día laborable lluvioso":
        escenario.update({"dia_semana": dia_laboral, "es_festivo": False,
                          "vel_ciudad_ms": estadisticas["medianas_entrada"]["vel_ciudad_ms"],
                          "precip_mm": p90_lluvia, "precip_1d_antes": 0.0})
    else:
        raise ValueError(f"Preset desconocido: {nombre}")
    return escenario


def calcular_tornado(referencia: dict, artefacto: dict, estadisticas: dict,
                     asignacion: pd.DataFrame) -> pd.DataFrame:
    """Mide cambios p10-p90 de un predictor a la vez con los demás en referencia."""
    base, climatología = fila_caracteristicas(referencia, artefacto, estadisticas, asignacion)
    modelo = artefacto["modelo"]
    filas = []
    for variable in artefacto["features"]:
        p10, p90 = estadisticas["cuantiles_variables"][variable]
        extremo_bajo = base.copy()
        extremo_alto = base.copy()
        extremo_bajo.loc[:, variable] = p10
        extremo_alto.loc[:, variable] = p90
        pred_baja = max(0.0, climatología + float(modelo.predict(extremo_bajo)[0]))
        pred_alta = max(0.0, climatología + float(modelo.predict(extremo_alto)[0]))
        filas.append({"variable": variable, "p10": p10, "p90": p90,
                      "prediccion_p10": pred_baja, "prediccion_p90": pred_alta,
                      "cambio": pred_alta - pred_baja})
    return pd.DataFrame(filas).sort_values("cambio", key=lambda s: s.abs())
