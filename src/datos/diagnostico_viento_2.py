"""Busca centinelas, rachas constantes y sensibilidad de correlaciones al viento inválido.
Lee viento_largo.parquet, aire_largo.parquet y coordenadas del GeoJSON de estaciones.
Todas las conversiones para este diagnóstico son temporales y solo en memoria.
Escribe el reporte en un archivo nuevo data/interim/diagnostico_viento_2_resultados.txt.
"""

import json
import math
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
WIND_PATH = ROOT / "data" / "interim" / "viento_largo.parquet"
AIR_PATH = ROOT / "data" / "interim" / "aire_largo.parquet"
GEO_PATH = ROOT / "data" / "raw" / "geografia" / "estacion_calida_aire.geojson"
REPORT_PATH = ROOT / "data" / "interim" / "diagnostico_viento_2_resultados.txt"
PERIOD_START = pd.Timestamp("2023-10-24")
PERIOD_END = pd.Timestamp("2026-10-23")
GAP_START = pd.Timestamp("2025-08-04")
GAP_END = pd.Timestamp("2025-10-16")
EARTH_KM = 6371.0088


def normalizar_id(nombre):
    """Normaliza una etiqueta para empatar estaciones entre fuentes.

    Parámetros: nombre original. Devuelve identificador sin tildes ni signos.
    """
    texto = unicodedata.normalize("NFKD", str(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()
    texto = pd.Series([texto]).str.replace(r"[\s\-]+", "_", regex=True).iloc[0]
    return pd.Series([texto]).str.replace(r"[^a-z0-9_]", "", regex=True).iloc[0]


def leer_coordenadas():
    """Lee los puntos GeoJSON y prueba codificaciones sin escribir al archivo.

    Parámetros: ninguno. Devuelve estación_id→(nombre, longitud, latitud) y encoding.
    """
    contenido = GEO_PATH.read_bytes()
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            texto = contenido.decode(encoding)
            geo = json.loads(texto)
            nombres = [str(f.get("properties", {}).get("estacion", "")) for f in geo["features"]]
            if "\ufffd" in texto or any("�" in n for n in nombres):
                continue
            salida = {}
            for feature in geo["features"]:
                props, geom = feature.get("properties", {}), feature.get("geometry", {})
                coords = geom.get("coordinates", [])
                if geom.get("type") == "Point" and len(coords) >= 2:
                    nombre = str(props.get("estacion", "")).strip()
                    salida[normalizar_id(nombre)] = (nombre, float(coords[0]), float(coords[1]))
            return salida, encoding
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError("No se pudo leer el GeoJSON de estaciones con codificaciones conocidas.")


def haversine(lon_a, lat_a, lon_b, lat_b):
    """Calcula distancia entre coordenadas geográficas en kilómetros.

    Parámetros: longitud/latitud de dos puntos, en grados. Devuelve km.
    """
    lon_a, lat_a, lon_b, lat_b = map(math.radians, [lon_a, lat_a, lon_b, lat_b])
    dlon, dlat = lon_b - lon_a, lat_b - lat_a
    a = math.sin(dlat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def tabla_diaria(df, variable_col, value_col, variables):
    """Crea una tabla fecha-estación para análisis de rachas y comparaciones.

    Parámetros: tabla larga y nombres de campos. Devuelve una tabla pivote única.
    """
    subset = df[df[variable_col].isin(variables)]
    return subset.pivot(index=["fecha", "estacion_id", "estacion"], columns=variable_col, values=value_col).reset_index()


def extraer_rachas(df, variable_col, value_col, etiquetas, minimo=4):
    """Encuentra rachas de valores numéricos idénticos en días calendarios seguidos.

    Parámetros: tabla larga, campos y etiquetas; NaN no cuenta y corta una racha diaria.
    Devuelve registros con estación, variable, valor, inicio y duración.
    """
    resultados = []
    for (sid, estacion, variable), grupo in df.groupby(["estacion_id", "estacion", variable_col], sort=True):
        diario = grupo.set_index("fecha")[value_col].sort_index()
        diario = diario.reindex(pd.date_range(PERIOD_START, PERIOD_END, freq="D"))
        inicio = None
        anterior_fecha = None
        anterior_valor = None
        longitud = 0
        for fecha, valor in diario.items():
            numerico = pd.notna(valor) and isinstance(valor, (int, float, np.number))
            if numerico and inicio is not None and fecha == anterior_fecha + pd.Timedelta(days=1) and float(valor) == float(anterior_valor):
                longitud += 1
            else:
                if inicio is not None and longitud >= minimo:
                    resultados.append({
                        "estacion": estacion, "variable": etiquetas.get(variable, variable),
                        "valor": float(anterior_valor), "inicio": inicio, "duracion_dias": longitud,
                    })
                inicio = fecha if numerico else None
                longitud = 1 if numerico else 0
            anterior_fecha, anterior_valor = fecha, valor
        if inicio is not None and longitud >= minimo:
            resultados.append({
                "estacion": estacion, "variable": etiquetas.get(variable, variable),
                "valor": float(anterior_valor), "inicio": inicio, "duracion_dias": longitud,
            })
    return pd.DataFrame(resultados, columns=["estacion", "variable", "valor", "inicio", "duracion_dias"])


def rachas_texto(rachas):
    """Formatea rachas en tabla completa y encabezado con el total.

    Parámetros: DataFrame de rachas. Devuelve texto listo para incluir en el informe.
    """
    if rachas.empty:
        return "Total de rachas: 0\n(ninguna)"
    rachas = rachas.sort_values(["estacion", "variable", "inicio", "valor"])
    tabla = rachas.copy()
    tabla["inicio"] = pd.to_datetime(tabla["inicio"]).dt.strftime("%Y-%m-%d")
    tabla["valor"] = tabla["valor"].map(lambda x: f"{x:.10g}")
    return f"Total de rachas: {len(tabla)}\n" + tabla.to_string(index=False)


def reporte_negativos_viento(viento):
    """Lista las mediciones de velocidad negativas con archivo de origen.

    Parámetros: tabla limpia de viento. Devuelve texto con las filas completas.
    """
    malos = viento[(viento["variable"] == "vel_viento") & (viento["valor"] < 0)].sort_values(["fecha", "estacion"])
    lineas = [f"1. VELOCIDADES NEGATIVAS ({len(malos)})"]
    for row in malos.itertuples(index=False):
        lineas.append(f"  {row.fecha:%Y-%m-%d} | {row.estacion} | {row.valor:g} | {row.archivo_origen}")
    return "\n".join(lineas)


def reporte_aire_negativo(aire):
    """Lista todo PM2.5/PM10 negativo, sin convertirlo ni reemplazarlo.

    Parámetros: parquet largo de aire. Devuelve lista y conteos por contaminante.
    """
    malos = aire[aire["valor"] < 0].sort_values(["fecha", "estacion", "contaminante"])
    lineas = [f"\n2. VALORES NEGATIVOS DE PM2.5/PM10 ({len(malos)})"]
    lineas.append(f"Conteo por contaminante: {malos['contaminante'].value_counts().to_dict()}")
    if malos.empty:
        lineas.append("  (ninguno)")
    else:
        for row in malos.itertuples(index=False):
            lineas.append(f"  {row.fecha:%Y-%m-%d} | {row.estacion} | {row.contaminante} | {row.valor:g} | {row.archivo_origen}")
    return "\n".join(lineas)


def reporte_cent_nales(aire, viento):
    """Agrupa valores centinela/imposibles y lista máximo 30 casos por tabla.

    Parámetros: parquets de aire y viento. Devuelve conteos y filas de muestra.
    """
    lineas = ["\n3. CENTINELAS / IMPOSIBLES (valor <= -99 o >= 9999)"]
    entradas = []
    for etiqueta, df, variable_col in (("aire", aire, "contaminante"), ("viento", viento, "variable")):
        mask = (df["valor"] <= -99) | (df["valor"] >= 9999)
        malos = df.loc[mask].copy()
        conteo = malos.groupby(["estacion", variable_col]).size().sort_values(ascending=False)
        lineas.append(f"\n{etiqueta}: total={len(malos)}; conteos estación-variable={conteo.to_dict()}")
        for row in malos.itertuples(index=False):
            entradas.append((etiqueta, row.fecha, row.estacion, getattr(row, variable_col), row.valor, row.archivo_origen))
    entradas.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
    lineas.append(f"\nPrimeros {min(30, len(entradas))} de {len(entradas)} valores centinela/imposibles combinados:")
    for tabla, fecha, estacion, variable, valor, origen in entradas[:30]:
        lineas.append(f"  {tabla} | {fecha:%Y-%m-%d} | {estacion} | {variable} | {valor:g} | {origen}")

    altos = aire[(aire["contaminante"].isin(["PM2.5", "PM10"])) & (aire["valor"] > 500)].sort_values(["fecha", "estacion", "contaminante"])
    lineas.append(f"\nAire PM2.5/PM10 > 500: total={len(altos)}; conteos estación-variable={altos.groupby(['estacion', 'contaminante']).size().to_dict()}")
    for row in altos.head(30).itertuples(index=False):
        lineas.append(f"  {row.fecha:%Y-%m-%d} | {row.estacion} | {row.contaminante} | {row.valor:g} | {row.archivo_origen}")
    if altos.empty:
        lineas.append("  (ninguno)")
    return "\n".join(lineas)


def correlaciones_parejas(pivot, estaciones, coords, canales):
    """Calcula coeficientes Pearson por pareja y canal circular/no circular.

    Parámetros: fechas×estación, estaciones, coordenadas y nombres de canales.
    Devuelve registros de distancia, correlaciones y días solapados.
    """
    registros = []
    for i, sid_a in enumerate(estaciones):
        if sid_a not in coords:
            continue
        _, lon_a, lat_a = coords[sid_a]
        for sid_b in estaciones[i + 1:]:
            if sid_b not in coords:
                continue
            _, lon_b, lat_b = coords[sid_b]
            distancia = haversine(lon_a, lat_a, lon_b, lat_b)
            par = {"sid_a": sid_a, "sid_b": sid_b, "distancia_km": distancia}
            for canal in canales:
                juntos = pivot[[f"{canal}__{sid_a}", f"{canal}__{sid_b}"]].dropna()
                par[f"corr_{canal}"] = juntos.iloc[:, 0].corr(juntos.iloc[:, 1]) if len(juntos) >= 2 else np.nan
                par[f"n_{canal}"] = len(juntos)
            registros.append(par)
    return pd.DataFrame(registros)


def formato_corr(valor):
    """Formatea correlación numérica y preserva NaN como texto.

    Parámetros: coeficiente. Devuelve texto corto.
    """
    return "NaN" if pd.isna(valor) else f"{valor:.4f}"


def resumen_corr(pares, columnas, encabezado):
    """Resume media y mediana de correlación por rango de distancia.

    Parámetros: tabla de pares, nombres de coeficiente y título. Devuelve texto.
    """
    bins = [(0, 3, "0–3 km"), (3, 6, "3–6 km"), (6, 10, "6–10 km"),
            (10, 15, "10–15 km"), (15, np.inf, ">15 km")]
    lineas = [encabezado]
    for lo, hi, nombre in bins:
        grupo = pares[(pares.distancia_km >= lo) & (pares.distancia_km < hi)]
        for col, etiqueta in columnas:
            valores = grupo[col].dropna()
            media = valores.mean() if len(valores) else np.nan
            mediana = valores.median() if len(valores) else np.nan
            lineas.append(
                f"  {nombre} | {etiqueta}: media={formato_corr(media)}; mediana={formato_corr(mediana)}; "
                f"parejas={len(grupo)}; correlaciones válidas={len(valores)}"
            )
    return "\n".join(lineas)


def reporte_medias_y_correlaciones(viento, coords):
    """Recalcula medias y correlaciones excluyendo velocidades negativas en memoria.

    Parámetros: viento y coordenadas. Devuelve medias, correlaciones y pares cercanos.
    """
    fechas = pd.date_range(PERIOD_START, PERIOD_END, freq="D")
    viento_ok = viento.copy()
    velocidad_mask = viento_ok["variable"] == "vel_viento"
    n_negativos = int((velocidad_mask & (viento_ok["valor"] < 0)).sum())
    viento_ok.loc[velocidad_mask & (viento_ok["valor"] < 0), "valor"] = np.nan
    speeds = viento_ok[viento_ok.variable == "vel_viento"].pivot(index="fecha", columns="estacion_id", values="valor").reindex(fechas)
    lineas = [f"\n5. ANÁLISIS EN MEMORIA: vel_viento < 0 tratados como NaN ({n_negativos} valores; fuentes intactas)"]
    stats = viento_ok[viento_ok.variable == "vel_viento"].groupby("estacion").valor.agg(media="mean", mediana="median").sort_index()
    lineas.append("a) Velocidad media y mediana por estación (m/s):")
    lineas.append(stats.to_string(float_format=lambda x: f"{x:.4f}"))

    estaciones = sorted(speeds.columns)
    speed_long = speeds
    pares_speed = []
    for i, sid_a in enumerate(estaciones):
        if sid_a not in coords:
            continue
        _, lon_a, lat_a = coords[sid_a]
        for sid_b in estaciones[i + 1:]:
            if sid_b not in coords:
                continue
            _, lon_b, lat_b = coords[sid_b]
            juntos = speed_long[[sid_a, sid_b]].dropna()
            pares_speed.append({
                "sid_a": sid_a, "sid_b": sid_b,
                "distancia_km": haversine(lon_a, lat_a, lon_b, lat_b),
                "corr_vel": juntos[sid_a].corr(juntos[sid_b]) if len(juntos) >= 2 else np.nan,
                "n_vel": len(juntos),
            })
    pares_speed = pd.DataFrame(pares_speed)
    lineas.append(resumen_corr(pares_speed, [("corr_vel", "vel_viento")], "b) Correlación diaria de velocidad, por distancia:"))
    cercanos = pares_speed[pares_speed.distancia_km < 6].sort_values("distancia_km")
    lineas.append("Parejas de viento a menos de 6 km (distancia y correlación de velocidad):")
    nombres = viento.drop_duplicates("estacion_id").set_index("estacion_id")["estacion"].to_dict()
    for row in cercanos.itertuples(index=False):
        lineas.append(f"  {nombres.get(row.sid_a, row.sid_a)} — {nombres.get(row.sid_b, row.sid_b)}: {row.distancia_km:.3f} km; r={formato_corr(row.corr_vel)}; días={row.n_vel}")

    # Convertir dirección a seno/coseno solo en memoria evita promediar grados circulares.
    dirs = viento[viento.variable == "dir_viento"].pivot(index="fecha", columns="estacion_id", values="valor").reindex(fechas)
    dir_sin = np.sin(np.deg2rad(dirs))
    dir_cos = np.cos(np.deg2rad(dirs))
    dir_channels = {}
    for etiqueta, matriz in (("dir_sin", dir_sin), ("dir_cos", dir_cos)):
        for sid in estaciones:
            dir_channels[f"{etiqueta}__{sid}"] = matriz[sid]
    dir_wide = pd.DataFrame(dir_channels, index=fechas)
    pares_dir = []
    for i, sid_a in enumerate(estaciones):
        if sid_a not in coords:
            continue
        _, lon_a, lat_a = coords[sid_a]
        for sid_b in estaciones[i + 1:]:
            if sid_b not in coords:
                continue
            _, lon_b, lat_b = coords[sid_b]
            par = {
                "sid_a": sid_a, "sid_b": sid_b,
                "distancia_km": haversine(lon_a, lat_a, lon_b, lat_b),
            }
            for canal in ("dir_sin", "dir_cos"):
                together = dir_wide[[f"{canal}__{sid_a}", f"{canal}__{sid_b}"]].dropna()
                par[f"corr_{canal}"] = together.iloc[:, 0].corr(together.iloc[:, 1]) if len(together) >= 2 else np.nan
                par[f"n_{canal}"] = len(together)
            pares_dir.append(par)
    pares_dir = pd.DataFrame(pares_dir)
    lineas.append(resumen_corr(
        pares_dir,
        [("corr_dir_sin", "dirección seno"), ("corr_dir_cos", "dirección coseno")],
        "c) Correlación diaria de dirección circular (Pearson por seno y coseno), por distancia:",
    ))

    for objetivo in ("Fontibon", "Tunal"):
        sid_obj = normalizar_id(objetivo)
        if sid_obj not in coords or sid_obj not in speeds.columns:
            lineas.append(f"\nCorrelaciones de {objetivo}: coordenada o serie no encontrada.")
            continue
        _, lon_o, lat_o = coords[sid_obj]
        candidatas = []
        for sid in estaciones:
            if sid == sid_obj or sid not in coords:
                continue
            _, lon, lat = coords[sid]
            candidatas.append((haversine(lon_o, lat_o, lon, lat), sid))
        lineas.append(f"\nCorrelaciones de {objetivo} con sus 3 estaciones de viento más cercanas:")
        for distancia, sid in sorted(candidatas)[:3]:
            sp = pares_speed[(pares_speed.sid_a == min(sid_obj, sid)) & (pares_speed.sid_b == max(sid_obj, sid))]
            if sp.empty:
                sp = pares_speed[(pares_speed.sid_a == min(sid, sid_obj)) & (pares_speed.sid_b == max(sid, sid_obj))]
            dp = pares_dir[(pares_dir.sid_a == min(sid_obj, sid)) & (pares_dir.sid_b == max(sid_obj, sid))]
            if dp.empty:
                dp = pares_dir[(pares_dir.sid_a == min(sid, sid_obj)) & (pares_dir.sid_b == max(sid, sid_obj))]
            sr = sp.iloc[0]["corr_vel"] if len(sp) else np.nan
            sin_r = dp.iloc[0]["corr_dir_sin"] if len(dp) else np.nan
            cos_r = dp.iloc[0]["corr_dir_cos"] if len(dp) else np.nan
            lineas.append(
                f"  {coords[sid][0]}: {distancia:.3f} km; r_vel={formato_corr(sr)}; "
                f"r_dir_sin={formato_corr(sin_r)}; r_dir_cos={formato_corr(cos_r)}"
            )
    return "\n".join(lineas)


def main():
    """Ejecuta lecturas y cálculos temporales, guarda y muestra el reporte completo.

    Parámetros: ninguno. No modifica datos originales ni productos existentes.
    """
    viento = pd.read_parquet(WIND_PATH)
    aire = pd.read_parquet(AIR_PATH)
    for df in (viento, aire):
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.normalize()
    coords, encoding = leer_coordenadas()
    bounds_ok = all(-180 <= lon <= 180 and -90 <= lat <= 90 for _, lon, lat in coords.values())
    lineas = [
        f"DIAGNÓSTICO DE VIENTO 2 — GeoJSON decodificado con {encoding}; coordenadas [lon, lat] en grados plausibles={bounds_ok}.",
        reporte_negativos_viento(viento),
        reporte_aire_negativo(aire),
        reporte_cent_nales(aire, viento),
    ]

    viento_r = viento.rename(columns={"variable": "variable_diag"})
    viento_r["variable_diag"] = viento_r["variable_diag"].replace({"vel_viento": "vel_viento", "dir_viento": "dir_viento"})
    rachas_viento = extraer_rachas(viento_r, "variable_diag", "valor", {"vel_viento": "vel_viento", "dir_viento": "dir_viento"})
    aire_r = aire.rename(columns={"contaminante": "variable_diag"})
    rachas_aire = extraer_rachas(aire_r, "variable_diag", "valor", {"PM2.5": "PM2.5", "PM10": "PM10"})
    rachas = pd.concat([rachas_aire, rachas_viento], ignore_index=True)
    lineas.append(
        "\n4. SENSOR ATASCADO: rachas de 4+ días con valor numérico idéntico. "
        "NaN no cuenta y corta la continuidad del calendario.\n" + rachas_texto(rachas)
    )
    lineas.append(reporte_medias_y_correlaciones(viento, coords))
    lineas.extend([
        "\n5 LÍNEAS: DIFERENCIAS O DECISIONES HUMANAS",
        "1. Los negativos de viento incluyen -9999 y valores extremos distintos; decidir cuáles son códigos centinela documentados.",
        "2. Revisar centinelas/imposibles de aire y viento y los episodios de valores constantes antes de interpretar medias o correlaciones.",
        "3. La recálculo de velocidad excluye en memoria todo vel_viento < 0; validar si la regla es suficiente para la tabla maestra.",
        "4. La dirección se compara mediante seno y coseno; decidir cómo mantener esa codificación al integrar fuentes.",
        "5. Correlaciones espaciales por distancia describen asociación, no garantizan representatividad local para otra estación.",
    ])
    informe = "\n\n".join(lineas) + "\n"
    REPORT_PATH.write_text(informe, encoding="utf-8")
    print(informe, end="")
    print(f"\nInforme completo: {REPORT_PATH}")


if __name__ == "__main__":
    main()
