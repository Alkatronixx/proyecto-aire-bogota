"""Cierra diagnósticos de calidad, rachas y representatividad espacial del viento.
Lee viento_largo.parquet, aire_largo.parquet y coordenadas de estaciones del GeoJSON.
Trata velocidades negativas como NaN en los análisis estadísticos, sin alterar fuentes.
Guarda el reporte íntegro en data/interim/diagnostico_viento_3_resultados.txt.
"""

import json
import math
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
WIND_PATH = ROOT / "data" / "interim" / "viento_largo.parquet"
AIR_PATH = ROOT / "data" / "interim" / "aire_largo.parquet"
GEO_PATH = ROOT / "data" / "raw" / "geografia" / "estacion_calida_aire.geojson"
REPORT_PATH = ROOT / "data" / "interim" / "diagnostico_viento_3_resultados.txt"
INICIO = pd.Timestamp("2023-10-24")
FIN = pd.Timestamp("2026-10-23")
HUECO_INICIO = pd.Timestamp("2025-08-04")
HUECO_FIN = pd.Timestamp("2025-10-16")
RADIO_TIERRA_KM = 6371.0088


def normalizar_id(nombre):
    """Normaliza nombre de estación para hacer cruces entre fuentes.

    Parámetros: nombre original. Devuelve identificador sin tildes y signos.
    """
    texto = unicodedata.normalize("NFKD", str(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()
    texto = re.sub(r"[\s\-]+", "_", texto)
    return re.sub(r"[^a-z0-9_]", "", texto)


def leer_coordenadas():
    """Lee puntos del GeoJSON probando UTF-8 y alternativas en memoria.

    Parámetros: ninguno. Devuelve mapa id→(etiqueta, longitud, latitud) y encoding.
    """
    contenido = GEO_PATH.read_bytes()
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            texto = contenido.decode(encoding)
            geo = json.loads(texto)
            nombres = [str(f.get("properties", {}).get("estacion", "")) for f in geo["features"]]
            if "\ufffd" in texto or any("�" in nombre for nombre in nombres):
                continue
            coords = {}
            for feature in geo["features"]:
                props, geom = feature.get("properties", {}), feature.get("geometry", {})
                xy = geom.get("coordinates", [])
                if geom.get("type") == "Point" and len(xy) >= 2:
                    nombre = str(props.get("estacion", "")).strip()
                    coords[normalizar_id(nombre)] = (nombre, float(xy[0]), float(xy[1]))
            return coords, encoding
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError("No se pudo decodificar el GeoJSON de estaciones.")


def haversine(lon1, lat1, lon2, lat2):
    """Calcula distancia de círculo máximo entre dos ubicaciones.

    Parámetros: longitudes y latitudes en grados. Devuelve distancia en km.
    """
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(a))


def tramos_nan(fechas_nan, minimo=7):
    """Devuelve intervalos consecutivos de fechas NaN que alcanzan mínimo días.

    Parámetros: fechas faltantes y duración mínima. Devuelve tuplas inicio, fin, días.
    """
    fechas = pd.DatetimeIndex(sorted(pd.Timestamp(f).normalize() for f in fechas_nan))
    if not len(fechas):
        return []
    resultado, inicio, previo = [], fechas[0], fechas[0]
    for fecha in fechas[1:]:
        if fecha != previo + pd.Timedelta(days=1):
            duracion = (previo - inicio).days + 1
            if duracion >= minimo:
                resultado.append((inicio, previo, duracion))
            inicio = fecha
        previo = fecha
    duracion = (previo - inicio).days + 1
    if duracion >= minimo:
        resultado.append((inicio, previo, duracion))
    return resultado


def formatear_numero(valor, decimales=3):
    """Presenta numéricos compactos y conserva los NaN como texto.

    Parámetros: valor y decimales. Devuelve cadena para tablas del informe.
    """
    if pd.isna(valor):
        return "NaN"
    return f"{float(valor):.{decimales}f}"


def rachas_iguales(df, variable_col, value_col, nombre_col="variable", minimo=4):
    """Encuentra rachas exactas en días calendarios consecutivos; NaN corta racha.

    Parámetros: tabla larga y nombres de columnas. Devuelve DataFrame con intervalos.
    """
    fechas = pd.date_range(INICIO, FIN, freq="D")
    rachas = []
    for (sid, estacion, variable), grupo in df.groupby(["estacion_id", "estacion", variable_col], sort=True):
        serie = grupo.set_index("fecha")[value_col].reindex(fechas)
        inicio, valor_anterior, longitud = None, None, 0
        for fecha, valor in serie.items():
            numerico = pd.notna(valor) and isinstance(valor, (int, float, np.number))
            if numerico and inicio is not None and float(valor) == float(valor_anterior):
                longitud += 1
            else:
                if inicio is not None and longitud >= minimo:
                    rachas.append({"estacion_id": sid, "estacion": estacion, "variable": variable,
                                   "valor": float(valor_anterior), "inicio": inicio,
                                   "fin": fecha_previa, "duracion": longitud})
                inicio = fecha if numerico else None
                valor_anterior = valor if numerico else None
                longitud = 1 if numerico else 0
            fecha_previa = fecha
        if inicio is not None and longitud >= minimo:
            rachas.append({"estacion_id": sid, "estacion": estacion, "variable": variable,
                           "valor": float(valor_anterior), "inicio": inicio,
                           "fin": fecha_previa, "duracion": longitud})
    return pd.DataFrame(rachas, columns=["estacion_id", "estacion", "variable", "valor", "inicio", "fin", "duracion"])


def tabla_faltantes(viento):
    """Calcula cobertura y tramos NaN por estación-variable con viento limpio.

    Parámetros: tabla viento con velocidades negativas recodificadas a NaN. Devuelve tabla.
    """
    calendario = pd.date_range(INICIO, FIN, freq="D")
    fuera_hueco = (calendario < HUECO_INICIO) | (calendario > HUECO_FIN)
    filas = []
    stats_vel = viento[viento.variable == "vel_viento"].groupby("estacion").valor.agg(media="mean", mediana="median")
    for estacion in sorted(viento.estacion.unique()):
        for variable in ("vel_viento", "dir_viento"):
            serie = viento[(viento.estacion == estacion) & (viento.variable == variable)].set_index("fecha").valor.reindex(calendario)
            faltantes = serie.isna()
            tramos = tramos_nan(calendario[faltantes.to_numpy()])
            mayor = max(tramos, key=lambda item: item[2]) if tramos else (pd.NaT, pd.NaT, 0)
            vel_stats = stats_vel.loc[estacion]
            filas.append({
                "estacion": estacion,
                "variable": variable,
                "nan_periodo_%": 100 * faltantes.mean(),
                "nan_sin_hueco_%": 100 * faltantes[fuera_hueco].mean(),
                "vel_media_m_s": vel_stats.media,
                "vel_mediana_m_s": vel_stats.mediana,
                "n_rangos_nan_7d+": len(tramos),
                "rango_nan_mas_largo": "ninguno" if not tramos else f"{mayor[0]:%Y-%m-%d}..{mayor[1]:%Y-%m-%d} ({mayor[2]} d)",
            })
    return pd.DataFrame(filas).sort_values(["nan_sin_hueco_%", "estacion", "variable"], ascending=[False, True, True])


def detectar_rachas(viento, aire):
    """Detecta rachas tras ocultar velocidades negativas y anota solapes cruzados.

    Parámetros: viento y aire largos. Devuelve lista filtrada, resumen y solapes.
    """
    viento_ok = viento.copy()
    mask_neg = (viento_ok.variable == "vel_viento") & (viento_ok.valor < 0)
    viento_ok.loc[mask_neg, "valor"] = np.nan
    # Se combinan fuentes con un nombre de variable común solo para analizar rachas.
    v = viento_ok.rename(columns={"variable": "variable_racha"})
    a = aire.rename(columns={"contaminante": "variable_racha"})
    rachas_v = rachas_iguales(v, "variable_racha", "valor")
    rachas_a = rachas_iguales(a, "variable_racha", "valor")
    todas = pd.concat([rachas_a, rachas_v], ignore_index=True)
    viento_rachas = todas.copy()
    anotaciones = []
    for r in viento_rachas.itertuples(index=False):
        otros = viento_rachas[
            (viento_rachas.estacion_id == r.estacion_id)
            & (viento_rachas.variable != r.variable)
        ]
        coincidencias = []
        for o in otros.itertuples(index=False):
            ini = max(r.inicio, o.inicio)
            fin = min(r.fin, o.fin)
            if ini <= fin:
                coincidencias.append(f"{o.variable}={o.valor:g} ({ini:%Y-%m-%d}..{fin:%Y-%m-%d})")
        anotaciones.append("; ".join(coincidencias) if coincidencias else "ninguna")
    todas["coincide_otra_variable"] = anotaciones
    return todas


def tabla_evento(aire, viento, fecha):
    """Cuenta NaN, negativos y mediciones numéricas por variable en un día.

    Parámetros: parquets originales y fecha del evento. Devuelve filas por fuente-variable.
    """
    filas = []
    for nombre, df, variable_col, variables, n_estaciones in [
        ("aire", aire, "contaminante", ["PM2.5", "PM10"], 19),
        ("viento", viento, "variable", ["vel_viento", "dir_viento"], 17),
    ]:
        for variable in variables:
            parte = df[(df.fecha == fecha) & (df[variable_col] == variable)]
            valores = parte.valor
            negativos = int((valores < 0).sum())
            numericos = int((valores.notna() & (valores >= 0)).sum())
            nans = n_estaciones - negativos - numericos
            filas.append({"fecha": fecha.strftime("%Y-%m-%d"), "fuente": nombre, "variable": variable,
                          "NaN": nans, "negativo": negativos, "numérico_no_negativo": numericos, "total_estaciones": n_estaciones})
    return filas


def eventos_sistema(aire, viento):
    """Cuenta categorías de medición en dos días puntuales y cada día de abril.

    Parámetros: aire y viento originales. Devuelve texto de tablas de conteos.
    """
    filas = []
    for fecha in (pd.Timestamp("2024-04-09"), pd.Timestamp("2025-11-04")):
        filas.extend(tabla_evento(aire, viento, fecha))
    tabla_puntual = pd.DataFrame(filas)
    abril = []
    for fecha in pd.date_range("2024-04-01", "2024-04-30", freq="D"):
        for fila in tabla_evento(aire, viento, fecha):
            if fila["fuente"] == "viento":
                abril.append(fila)
    tabla_abril = pd.DataFrame(abril)
    agregado_abril = tabla_abril.groupby("variable", as_index=False).agg(
        NaN_estacion_dia=("NaN", "sum"),
        negativo_estacion_dia=("negativo", "sum"),
        numerico_no_negativo_estacion_dia=("numérico_no_negativo", "sum"),
    )
    agregado_abril["posibles_estacion_dia"] = 30 * 17
    lineas = ["\n4. EVENTOS Y FALLOS: conteo bruto por estación; negativos separados de valores numéricos no negativos.",
              tabla_puntual.to_string(index=False),
              "\nViento, agregado del 2024-04-01 al 2024-04-30 (30 × 17 = 510 estación-días por variable):",
              agregado_abril.to_string(index=False)]
    return "\n".join(lineas)


def preparar_pivots(viento):
    """Construye matrices diarias de velocidad limpia y dirección seno/coseno.

    Parámetros: tabla larga original. Devuelve calendario y tres matrices fecha×estación.
    """
    calendario = pd.date_range(INICIO, FIN, freq="D")
    velocidad = viento[viento.variable == "vel_viento"].pivot(index="fecha", columns="estacion_id", values="valor").reindex(calendario)
    velocidad = velocidad.mask(velocidad < 0)
    direccion = viento[viento.variable == "dir_viento"].pivot(index="fecha", columns="estacion_id", values="valor").reindex(calendario)
    seno = np.sin(np.deg2rad(direccion))
    coseno = np.cos(np.deg2rad(direccion))
    return calendario, velocidad, direccion, seno, coseno


def ciudad_y_representatividad(viento, coords):
    """Calcula la mediana de ciudad, participación diaria y r frente a otras estaciones.

    Parámetros: viento original y coordenadas. Devuelve informe con tabla de 17 sensores.
    """
    calendario, vel, _, _, _ = preparar_pivots(viento)
    ciudad = vel.median(axis=1, skipna=True)
    contribuyen = vel.notna().sum(axis=1)
    bajo_cinco = 100 * (contribuyen < 5).mean()
    resumen_n = f"Contribuyentes/día: mínimo={int(contribuyen.min())}; mediana={contribuyen.median():.1f}; días con menos de 5={bajo_cinco:.2f}% ({int((contribuyen < 5).sum())}/{len(calendario)})."
    lineas = ["\n5. VIENTO DE CIUDAD", resumen_n, "Correlación de cada estación con mediana diaria de las otras 16:"]
    filas = []
    nombre_por_id = viento.drop_duplicates("estacion_id").set_index("estacion_id").estacion.to_dict()
    for sid in vel.columns:
        otras = vel.drop(columns=[sid]).median(axis=1, skipna=True)
        junto = pd.concat([vel[sid], otras], axis=1).dropna()
        filas.append({"estacion": nombre_por_id.get(sid, sid), "r": junto.iloc[:, 0].corr(junto.iloc[:, 1]), "n_dias": len(junto)})
    tabla = pd.DataFrame(filas).sort_values("estacion")
    lineas.append(tabla.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    for nombre in ("Fontibon", "Tunal"):
        sid = normalizar_id(nombre)
        if sid in vel.columns:
            resto = vel.drop(columns=[sid]).median(axis=1, skipna=True)
            juntos = pd.concat([vel[sid], resto], axis=1).dropna()
            lineas.append(f"Correlación específica {nombre} vs mediana de otras 16: r={juntos.iloc[:, 0].corr(juntos.iloc[:, 1]):.4f}; n={len(juntos)} días.")
    return "\n".join(lineas)


def correlacion_dos_series(a, b):
    """Calcula Pearson y n en fechas donde ambas series están disponibles.

    Parámetros: dos Series indexadas por fecha. Devuelve coeficiente y días comunes.
    """
    juntos = pd.concat([a, b], axis=1).dropna()
    return (juntos.iloc[:, 0].corr(juntos.iloc[:, 1]) if len(juntos) >= 2 else np.nan, len(juntos))


def cercanas_y_correlaciones(viento, coords):
    """Calcula cercanía y r para velocidad y seno/coseno entre estaciones cercanas.

    Parámetros: viento original y mapa de coordenadas. Devuelve tabla para Fontibón y Tunal.
    """
    calendario, vel, _, seno, coseno = preparar_pivots(viento)
    lineas = ["\n6. FONTIBÓN Y TUNAL: 3 ESTACIONES DE VIENTO MÁS CERCANAS; n según pares completos."]
    for nombre in ("Fontibon", "Tunal"):
        sid_obj = normalizar_id(nombre)
        if sid_obj not in coords:
            lineas.append(f"{nombre}: sin coordenada GeoJSON.")
            continue
        _, lon_obj, lat_obj = coords[sid_obj]
        candidatas = []
        for sid in vel.columns:
            if sid == sid_obj or sid not in coords:
                continue
            _, lon, lat = coords[sid]
            candidatas.append((haversine(lon_obj, lat_obj, lon, lat), sid))
        lineas.append(f"\n{nombre}:")
        for distancia, sid in sorted(candidatas)[:3]:
            r_vel, n_vel = correlacion_dos_series(vel[sid_obj], vel[sid])
            r_sin, n_sin = correlacion_dos_series(seno[sid_obj], seno[sid])
            r_cos, n_cos = correlacion_dos_series(coseno[sid_obj], coseno[sid])
            etiqueta = coords[sid][0]
            lineas.append(
                f"  {etiqueta}: {distancia:.3f} km | vel r={formatear_numero(r_vel, 4)} n={n_vel}; "
                f"seno r={formatear_numero(r_sin, 4)} n={n_sin}; coseno r={formatear_numero(r_cos, 4)} n={n_cos}"
            )
    return "\n".join(lineas)


def serializar_faltantes(tabla):
    """Formatea la tabla completa de faltantes con 34 filas.

    Parámetros: tabla calculada. Devuelve texto alineado para consola y reporte.
    """
    vista = tabla.copy()
    for col in ("nan_periodo_%", "nan_sin_hueco_%", "vel_media_m_s", "vel_mediana_m_s"):
        vista[col] = vista[col].map(lambda x: formatear_numero(x, 2))
    return vista.to_string(index=False)


def serializar_rachas(rachas):
    """Ordena y presenta todas las rachas sin centinela de Las Ferias.

    Parámetros: tabla de rachas limpias. Devuelve tabla y resumen por variable/duración.
    """
    sin_cent = rachas[~((rachas.estacion == "Las Ferias") & (rachas.variable == "vel_viento") & (rachas.valor == -9999))].copy()
    sin_cent = sin_cent.sort_values(["variable", "estacion", "inicio", "valor"])
    tabla = sin_cent.copy()
    tabla["inicio"] = pd.to_datetime(tabla.inicio).dt.strftime("%Y-%m-%d")
    tabla["fin"] = pd.to_datetime(tabla.fin).dt.strftime("%Y-%m-%d")
    tabla["valor"] = tabla.valor.map(lambda x: f"{x:.10g}")
    resumen = []
    for variable in sorted(sin_cent.variable.unique()):
        subset = sin_cent[sin_cent.variable == variable]
        n = len(subset)
        resumen.append({
            "variable": variable, "total": n,
            "duracion_4": int((subset.duracion == 4).sum()),
            "duracion_5_6": int(subset.duracion.between(5, 6).sum()),
            "duracion_7_mas": int((subset.duracion >= 7).sum()),
        })
    resumen.append({
        "variable": "TOTAL", "total": len(sin_cent),
        "duracion_4": int((sin_cent.duracion == 4).sum()),
        "duracion_5_6": int(sin_cent.duracion.between(5, 6).sum()),
        "duracion_7_mas": int((sin_cent.duracion >= 7).sum()),
    })
    return tabla.to_string(index=False), pd.DataFrame(resumen).to_string(index=False), sin_cent


def informe_detalle(viento):
    """Prepara fechas de rachas negativas y contexto de direcciones cercanas.

    Parámetros: viento original. Devuelve detalle de Las Ferias y otras velocidades negativas.
    """
    pivot = viento.pivot(index=["fecha", "estacion_id", "estacion"], columns="variable", values="valor").reset_index()
    lf = pivot[(pivot.estacion == "Las Ferias") & pivot.vel_viento.eq(-9999)].sort_values("fecha")
    lineas = [f"\n3. LAS FERIAS, ABRIL 2024: {len(lf)} días con -9999 y dirección diaria"]
    for row in lf.itertuples(index=False):
        lineas.append(f"  {row.fecha:%Y-%m-%d} | dir_viento={formatear_numero(row.dir_viento, 3)}")
    otras = pivot[(pivot.vel_viento < 0) & ~((pivot.estacion == "Las Ferias") & pivot.vel_viento.eq(-9999))].sort_values(["fecha", "estacion"])
    lineas.append("Otras velocidades negativas y dirección del día anterior / día / día siguiente:")
    for row in otras.itertuples(index=False):
        prev = pivot[(pivot.estacion_id == row.estacion_id) & (pivot.fecha == row.fecha - pd.Timedelta(days=1))]
        nxt = pivot[(pivot.estacion_id == row.estacion_id) & (pivot.fecha == row.fecha + pd.Timedelta(days=1))]
        dir_prev = prev.dir_viento.iloc[0] if len(prev) else np.nan
        dir_next = nxt.dir_viento.iloc[0] if len(nxt) else np.nan
        lineas.append(
            f"  {row.fecha:%Y-%m-%d} | {row.estacion} | vel={row.vel_viento:g} | "
            f"dir anterior={formatear_numero(dir_prev, 3)}; dir día={formatear_numero(row.dir_viento, 3)}; "
            f"dir siguiente={formatear_numero(dir_next, 3)}"
        )
    return "\n".join(lineas)


def main():
    """Ejecuta los cálculos en memoria y escribe/muestra informe completo.

    Parámetros: ninguno. Devuelve None y no altera parquets, CSV ni datos crudos.
    """
    viento_original = pd.read_parquet(WIND_PATH)
    aire = pd.read_parquet(AIR_PATH)
    viento_original["fecha"] = pd.to_datetime(viento_original.fecha).dt.normalize()
    aire["fecha"] = pd.to_datetime(aire.fecha).dt.normalize()
    coords, encoding = leer_coordenadas()
    estaciones = sorted(viento_original.estacion.unique())

    viento = viento_original.copy()
    neg_mask = (viento.variable == "vel_viento") & (viento.valor < 0)
    viento.loc[neg_mask, "valor"] = np.nan

    faltantes = tabla_faltantes(viento)
    rachas = detectar_rachas(viento_original, aire)
    tabla_rachas, resumen_rachas, rachas_limpias = serializar_rachas(rachas)
    eventos = eventos_sistema(aire, viento_original)

    detalle_coincidencias = []
    for r in rachas_limpias.itertuples(index=False):
        if r.coincide_otra_variable != "ninguna":
            detalle_coincidencias.append(f"  {r.estacion} | {r.variable}={r.valor:g} | {r.inicio:%Y-%m-%d}..{r.fin:%Y-%m-%d}: {r.coincide_otra_variable}")
    # El -9999 se excluye como racha estadística, pero se conserva esta nota de coincidencia cruda.
    lf_dir = rachas_limpias[(rachas_limpias.estacion == "Las Ferias") & (rachas_limpias.variable == "dir_viento") & (rachas_limpias.valor == 81)]
    if len(lf_dir):
        detalle_coincidencias.append(
            "  Las Ferias | dir_viento=81 | 2024-04-09..2024-04-18: "
            "coincide con la secuencia cruda vel_viento=-9999, excluida de las rachas tras tratar negativos como NaN."
        )
    if not detalle_coincidencias:
        detalle_coincidencias = ["  Ninguna racha coincide temporalmente con la otra variable de viento en la misma estación."]

    # Fechas de los 10 negativos centinela y vecinos se consultan desde el parquet original.
    headers = [
        f"DIAGNÓSTICO FINAL DE VIENTO — GeoJSON: {encoding}; estaciones viento={len(estaciones)}; periodo={INICIO.date()}..{FIN.date()} (1096 días).",
        "\n1. FALTANTES: velocidades negativas recodificadas como NaN solo en memoria; medias y medianas de velocidad usan valores no negativos.",
        serializar_faltantes(faltantes),
        f"\n2. RACHAS DE 4+ DÍAS TRAS TRATAR vel_viento < 0 COMO NaN (la racha de -9999 ya queda excluida).\n{tabla_rachas}",
        f"\nResumen por variable y duración:\n{resumen_rachas}",
        "\nCoincidencias temporales con racha de la otra variable en la misma estación:",
        "\n".join(detalle_coincidencias),
        informe_detalle(viento_original),
        eventos,
        ciudad_y_representatividad(viento_original, coords),
        cercanas_y_correlaciones(viento_original, coords),
        "\n5 LÍNEAS: DIFERENCIAS O DECISIONES HUMANAS",
        "1. Los 14 negativos de velocidad desaparecen de los estadísticos tras tratarlos como NaN; validar los códigos centinela antes de integrar.",
        "2. La tabla de rachas compara igualdad exacta por días calendario y excluye la racha -9999; NaN interrumpe la continuidad.",
        "3. Revisar si las categorías de aire/viento el 2024-04-09 y 2025-11-04 apuntan a problemas locales o comunes del sistema.",
        "4. Decidir si la mediana de ciudad y la mediana de otras 16 estaciones son representativas para cada estación individual.",
        "5. Las correlaciones de dirección se presentan por seno y coseno; interpretar ambas como componentes, no como grados promedio.",
    ]
    informe = "\n\n".join(headers) + "\n"
    REPORT_PATH.write_text(informe, encoding="utf-8")
    print(informe, end="")
    print(f"\nInforme completo: {REPORT_PATH}")


if __name__ == "__main__":
    main()
