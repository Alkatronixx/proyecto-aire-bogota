"""Resume asociaciones descriptivas entre PM, meteorología y calendario.
Lee la tabla maestra procesada y prepara agregados con caché antes de graficar.
Calcula anomalías térmicas con la referencia media del periodo de entrenamiento.
Las figuras y notas evitan atribuir causalidad a las diferencias observadas.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from app.components.paleta import ACENTO, color_rgb_cuantil
from app.components.tema_graficos import aplicar_tema
from app.components.ui import cargar_estilos, encabezado_pagina, nota_metodologica
from app.utils.datos import cargar_aire, cargar_tabla_maestra

FECHA_FIN_ENTRENAMIENTO = pd.Timestamp("2025-10-23")
ANTES_HUECO = pd.Timestamp("2025-08-03")
DESPUES_HUECO = pd.Timestamp("2025-10-17")
SEMILLA_BOOTSTRAP = 42
REPLICAS_BOOTSTRAP = 200


@st.cache_data(show_spinner=False)
def resumir_factores(datos: pd.DataFrame) -> dict[str, pd.DataFrame | float | int | str]:
    """Calcula tablas agregadas y bootstrap semanal una vez por versión de datos."""
    d = datos.copy()
    # Se conserva la referencia de entrenamiento para hacer comparables las anomalías térmicas.
    entrenamiento = d.loc[d.fecha.le(FECHA_FIN_ENTRENAMIENTO)]
    medias_tmax = entrenamiento.groupby("temp_estacion_id").tmax_c.mean()
    d["tmax_anom"] = d.tmax_c - d.temp_estacion_id.map(medias_tmax)
    pm = d.dropna(subset=["pm25"]).copy()

    viento = pm.dropna(subset=["vel_ciudad_ms"]).copy()
    viento["cuartil"] = pd.qcut(viento.vel_ciudad_ms.rank(method="first"), 4,
                                labels=["Q1 · menor", "Q2", "Q3", "Q4 · mayor"])
    cajas_viento = viento[["cuartil", "pm25"]].copy()
    # Spearman equivale a Pearson sobre rangos; así no se importa scipy en el arranque.
    spearman_viento = float(viento["vel_ciudad_ms"].rank().corr(viento.pm25.rank()))

    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    calendario = pm.copy()
    calendario["dia"] = calendario.fecha.dt.day_of_week.map(dict(enumerate(dias)))
    calendario["tipo_dia"] = np.select(
        [calendario.es_festivo.fillna(False), calendario.es_fin_semana],
        ["Festivo", "Fin de semana"], default="Laborable")
    calendario["semana"] = calendario.fecha.dt.to_period("W").astype(str)
    semanal_dia = calendario.groupby(["semana", "dia"], observed=True).pm25.mean().reset_index()
    semanal_tipo = calendario.groupby(["semana", "tipo_dia"], observed=True).pm25.mean().reset_index()

    def intervalo_semanal(tabla: pd.DataFrame, categoria: str) -> pd.DataFrame:
        """Obtiene intervalos percentiles por remuestreo de semanas completas."""
        rng = np.random.default_rng(SEMILLA_BOOTSTRAP)
        tabla = tabla.copy()
        tabla["categoria"] = tabla[categoria].astype(str)
        semanas = tabla.semana.drop_duplicates().to_numpy()
        categorias = tabla.categoria.drop_duplicates().tolist()
        resumen = tabla.groupby(["semana", "categoria"], observed=True).pm25.agg(["sum", "count"])
        sumas = resumen["sum"].unstack("categoria").reindex(index=semanas, columns=categorias).fillna(0).to_numpy()
        conteos = resumen["count"].unstack("categoria").reindex(index=semanas, columns=categorias).fillna(0).to_numpy()
        # El remuestreo vectorizado mantiene juntas todas las observaciones de una semana.
        indices = rng.integers(0, len(semanas), size=(REPLICAS_BOOTSTRAP, len(semanas)))
        sumas_replicadas = sumas[indices].sum(axis=1)
        conteos_replicados = conteos[indices].sum(axis=1)
        medias_replicadas = np.divide(sumas_replicadas, conteos_replicados,
                                      out=np.full_like(sumas_replicadas, np.nan), where=conteos_replicados > 0)
        medias = tabla.groupby("categoria", observed=True).pm25.mean()
        return pd.DataFrame([{"categoria": c, "media": float(medias[c]),
                              "inferior": float(np.nanquantile(medias_replicadas[:, j], .025)),
                              "superior": float(np.nanquantile(medias_replicadas[:, j], .975))}
                             for j, c in enumerate(categorias) if c in medias.index])

    ci_dia = intervalo_semanal(semanal_dia, "dia")
    ci_tipo = intervalo_semanal(semanal_tipo, "tipo_dia")
    lluvia_hoy = pm.loc[pm.llueve.notna()].copy()
    lluvia_hoy["grupo"] = np.where(lluvia_hoy.llueve.astype(bool), "Con lluvia", "Sin lluvia")
    lluvia_ayer = pm.loc[pm.precip_1d_antes.notna()].copy()
    lluvia_ayer["grupo"] = np.where(lluvia_ayer.precip_1d_antes.gt(0), "Lluvia día anterior", "Sin lluvia día anterior")
    lluvia = pd.concat([
        lluvia_hoy.assign(periodo="Mismo día")[ ["periodo", "grupo", "pm25"] ],
        lluvia_ayer.assign(periodo="Día anterior")[ ["periodo", "grupo", "pm25"] ],
    ]).groupby(["periodo", "grupo"], as_index=False).pm25.agg(["mean", "count"]).reset_index()
    lluvia_dif = {}
    for periodo, grupo in lluvia.groupby("periodo"):
        medias = grupo.set_index("grupo")["mean"]
        lluvia_dif[periodo] = float(medias.get("Con lluvia", medias.get("Lluvia día anterior", np.nan)) -
                                     medias.get("Sin lluvia", medias.get("Sin lluvia día anterior", np.nan)))

    temperatura = pm.dropna(subset=["tmax_anom"]).copy()
    temperatura["ventana"] = pd.qcut(temperatura.tmax_anom.rank(method="first"), 5,
                                     labels=["Q1 · menor", "Q2", "Q3", "Q4", "Q5 · mayor"])
    temp_resumen = temperatura.groupby("ventana", observed=True).pm25.agg(media="mean", n="count").reset_index()

    mensual = d.assign(anio=d.fecha.dt.year, mes=d.fecha.dt.month)
    pm_mes = mensual.dropna(subset=["pm25"]).groupby(["anio", "mes"], as_index=False).pm25.mean()
    lluvia_mes = mensual.dropna(subset=["precip_mm"]).groupby(["anio", "mes"], as_index=False).precip_mm.mean()
    mensual = pm_mes.merge(lluvia_mes, on=["anio", "mes"], how="outer")
    lluvia_climatologica = (d.dropna(subset=["precip_mm"]).groupby(d.fecha.dt.month).precip_mm.mean()
                            .rename_axis("mes").reset_index(name="precip_media"))
    mensual["anio_label"] = mensual.anio.astype(str)
    mensual.loc[mensual.anio.eq(2023), "anio_label"] = "2023 (parcial)"
    estaciones = pm.groupby(["estacion_id", "estacion"], as_index=False).pm25.mean().sort_values("pm25")
    localidades = pm.groupby("localidad", as_index=False).pm25.mean().sort_values("pm25")

    pre = d.loc[d.fecha.le(ANTES_HUECO)]
    post = d.loc[d.fecha.ge(DESPUES_HUECO)]
    columnas = ["pm25", "pm10", "vel_ciudad_ms", "precip_mm", "tmax_anom"]
    pre_est = pre.groupby(["estacion_id", "estacion"], as_index=False)[columnas].mean()
    post_est = post.groupby(["estacion_id", "estacion"], as_index=False)[columnas].mean()
    cambio = pre_est.merge(post_est, on=["estacion_id", "estacion"], suffixes=("_antes", "_despues"))
    for col in columnas:
        cambio[f"{col}_diferencia"] = cambio[f"{col}_despues"] - cambio[f"{col}_antes"]
    pares_pre = pre.dropna(subset=["pm25", "pm10"]).assign(razon=lambda x: x.pm25 / x.pm10)
    pares_post = post.dropna(subset=["pm25", "pm10"]).assign(razon=lambda x: x.pm25 / x.pm10)
    razon = pd.DataFrame([{"periodo": "Antes del hueco", "mediana": pares_pre.razon.median()},
                          {"periodo": "Después del hueco", "mediana": pares_post.razon.median()}])

    medias_tmin = entrenamiento.groupby("temp_estacion_id").tmin_c.mean()
    d["tmin_anom"] = d.tmin_c - d.temp_estacion_id.map(medias_tmin)
    variables = ["pm25", "pm10", "vel_ciudad_ms", "vel_viento_propia", "precip_mm",
                 "precip_1d_antes", "precip_3d_acum", "lluvia_ciudad_n", "tmax_c",
                 "tmin_c", "tmedia_c", "amplitud_c", "tmax_anom", "tmin_anom",
                 "es_fin_semana", "es_festivo", "dia_semana", "mes"]
    rangos = d[variables].rank(method="average", na_option="keep")
    correlaciones = rangos.corr(method="pearson", min_periods=30)
    caida = int((cambio.pm25_diferencia < 0).sum())
    return {"viento": cajas_viento, "spearman_viento": spearman_viento,
            "ci_dia": ci_dia, "ci_tipo": ci_tipo, "lluvia": lluvia, "lluvia_dif": lluvia_dif,
            "temperatura": temp_resumen, "mensual": mensual, "lluvia_climatologica": lluvia_climatologica,
            "estaciones": estaciones,
            "localidades": localidades, "cambio": cambio, "razon": razon,
            "correlaciones": correlaciones, "caida_estaciones": caida,
            "n_estaciones": int(cambio.estacion_id.nunique()),
            "dias_2023": int(d.fecha.loc[d.fecha.dt.year.eq(2023)].dt.normalize().nunique()),
            "dias_2026": int(d.fecha.loc[d.fecha.dt.year.eq(2026)].dt.normalize().nunique()),
            "pm_mediana_antes": float(pre.pm25.median()), "pm_mediana_despues": float(post.pm25.median())}


def figura_barras_error(tabla: pd.DataFrame, eje: str, titulo: str) -> go.Figure:
    """Construye barras con intervalos bootstrap ya calculados por la función cacheada."""
    fig = go.Figure(go.Bar(x=tabla[eje], y=tabla.media,
                           error_y={"type": "data", "symmetric": False,
                                    "array": tabla.superior-tabla.media,
                                    "arrayminus": tabla.media-tabla.inferior},
                           marker_color=ACENTO, hovertemplate="%{x}<br>Media %{y:.2f} µg/m³<extra></extra>"))
    fig.update_layout(title=titulo, xaxis_title="", yaxis_title="PM2.5 (µg/m³)")
    return fig


cargar_estilos()
encabezado_pagina("Factores asociados", "Comparaciones descriptivas del PM2.5, el tiempo meteorológico y el calendario.")
res = resumir_factores(cargar_aire())
asignaciones = cargar_tabla_maestra("asignacion_estaciones.csv")
# Las elevaciones corresponden a las estaciones IDEAM asignadas, no a las de aire.
altitudes_asignadas = asignaciones[["temp_estacion", "elev_ideam_temp_m"]].drop_duplicates()
altitud_nueva_generacion = float(altitudes_asignadas.loc[
    altitudes_asignadas.temp_estacion.str.contains("NUEVA GENERACION", case=False), "elev_ideam_temp_m"
].iloc[0])
altitud_san_cayetano = float(altitudes_asignadas.loc[
    altitudes_asignadas.temp_estacion.str.contains("SAN CAYETANO", case=False), "elev_ideam_temp_m"
].iloc[0])
diferencia_altitud_ideam = abs(altitud_san_cayetano - altitud_nueva_generacion)

st.subheader("a) Viento")
fig = go.Figure()
for grupo in res["viento"].cuartil.cat.categories:
    valores = res["viento"].loc[res["viento"].cuartil.eq(grupo), "pm25"]
    fig.add_trace(go.Box(y=valores, name=str(grupo), boxpoints=False,
                         marker_color=ACENTO, line_color=ACENTO))
fig.update_layout(title="PM2.5 observado por cuartil de velocidad del viento de ciudad",
                  xaxis_title="Cuartil de vel_ciudad_ms", yaxis_title="PM2.5 (µg/m³)")
st.plotly_chart(aplicar_tema(fig), width="stretch", config={"displayModeBar": False})
nota_metodologica(f"<strong>Qué se ve:</strong> Spearman global = {res['spearman_viento']:.2f} en {len(res['viento']):,} observaciones.<br><strong>Qué no se puede concluir:</strong> es una asociación descriptiva; no identifica un efecto del viento por sí solo.")

st.subheader("b) Calendario")
cal = make_subplots(rows=1, cols=2, subplot_titles=("Día de la semana", "Tipo de día"))
for i, tabla in enumerate([res["ci_dia"], res["ci_tipo"]], start=1):
    categoria = "categoria"
    cal.add_trace(go.Bar(x=tabla[categoria], y=tabla.media,
                         error_y={"type":"data","symmetric":False,"array":tabla.superior-tabla.media,"arrayminus":tabla.media-tabla.inferior},
                         marker_color=ACENTO, showlegend=False), row=1, col=i)
cal.update_yaxes(title_text="PM2.5 (µg/m³)", row=1, col=1)
cal.update_yaxes(title_text="PM2.5 (µg/m³)", row=1, col=2)
st.plotly_chart(aplicar_tema(cal), width="stretch", config={"displayModeBar": False})
dif_cal = float(res["ci_tipo"].set_index("categoria").media.get("Laborable", np.nan) - res["ci_tipo"].set_index("categoria").media.get("Fin de semana", np.nan))
nota_metodologica(f"<strong>Qué se ve:</strong> las barras muestran promedios por día y tipo, con intervalos bootstrap por semana ({REPLICAS_BOOTSTRAP} réplicas; laborable menos fin de semana: {dif_cal:+.2f} µg/m³).<br><strong>Qué no se puede concluir:</strong> las diferencias no aíslan el calendario de las demás condiciones concurrentes.")

st.subheader("c) Lluvia")
lluvia = res["lluvia"]
ll = go.Figure()
for periodo, tabla in lluvia.groupby("periodo"):
    ll.add_trace(go.Bar(x=tabla.grupo, y=tabla["mean"], name=periodo,
                        text=tabla["count"].map(lambda n: f"n={n:,}"), marker_color=ACENTO))
ll.update_layout(title="PM2.5 observado según lluvia del mismo día y del día anterior",
                 barmode="group", xaxis_title="Condición observada", yaxis_title="PM2.5 (µg/m³)")
st.plotly_chart(aplicar_tema(ll), width="stretch", config={"displayModeBar": False})
d_hoy = res["lluvia_dif"].get("Mismo día", float("nan")); d_ayer = res["lluvia_dif"].get("Día anterior", float("nan"))
nota_metodologica(f"<strong>Qué se ve:</strong> diferencia con/sin lluvia de {d_hoy:+.2f} µg/m³ el mismo día y {d_ayer:+.2f} µg/m³ al comparar el día anterior.<br><strong>Qué no se puede concluir:</strong> estos contrastes no estiman un efecto aislado de la lluvia.")

st.subheader("d) Temperatura")
temp = res["temperatura"]
tf = go.Figure(go.Scatter(x=temp.ventana, y=temp.media, mode="lines+markers",
                          marker={"size": 10, "color": ACENTO}, line={"color": ACENTO},
                          text=temp.n.map(lambda n: f"n={n:,}"), hovertemplate="%{x}<br>%{y:.2f} µg/m³<br>%{text}<extra></extra>"))
tf.update_layout(title="PM2.5 medio por ventanas de cuantiles de tmax_anom", xaxis_title="Cuantil de anomalía de temperatura máxima", yaxis_title="PM2.5 (µg/m³)")
st.plotly_chart(aplicar_tema(tf), width="stretch", config={"displayModeBar": False})
nota_metodologica(f"<strong>Qué se ve:</strong> las ventanas comparan anomalías respecto a la media de entrenamiento de cada estación IDEAM.<br><strong>Qué no se puede concluir:</strong> San Cayetano y Nueva Generación difieren en {diferencia_altitud_ideam:.0f} m de altitud, calculados desde el catálogo IDEAM asignado; los niveles absolutos no son directamente comparables.")

st.subheader("e) Estacionalidad")
mensual = res["mensual"]
est = make_subplots(specs=[[{"secondary_y": True}]])
for anio, tabla in mensual.groupby("anio_label", sort=True):
    linea = "dash" if "parcial" in anio else "solid"
    est.add_trace(go.Scatter(x=tabla.mes, y=tabla.pm25, mode="lines+markers", name=anio,
                             line={"dash":linea}), secondary_y=False)
lluvia_mes = res["lluvia_climatologica"]
est.add_trace(go.Bar(x=lluvia_mes.mes, y=lluvia_mes.precip_media,
                     name="Lluvia mensual media", marker_color="rgba(0,194,168,.22)"), secondary_y=True)
est.update_layout(title="PM2.5 mensual por año y lluvia media mensual", xaxis_title="Mes calendario", hovermode="x unified")
est.update_yaxes(title_text="PM2.5 (µg/m³)", secondary_y=False)
est.update_yaxes(title_text="Precipitación media (mm/día)", secondary_y=True)
st.plotly_chart(aplicar_tema(est), width="stretch", config={"displayModeBar": False})
nota_metodologica(f"<strong>Qué se ve:</strong> 2023 se rotula parcial y la lluvia media por mes calendario aparece en eje secundario.<br><strong>Qué no se puede concluir:</strong> 2023 ({res['dias_2023']} días) y 2026 ({res['dias_2026']} días) son parciales y no se comparan como tendencia.")

st.subheader("f) Estaciones y localidades")
col1, col2 = st.columns(2, gap="large")
with col1:
    estaciones = res["estaciones"]
    esf = go.Figure(go.Bar(x=estaciones.pm25, y=estaciones.estacion, orientation="h",
                           marker_color=[f"rgb{tuple(color_rgb_cuantil(v, estaciones.pm25))}" for v in estaciones.pm25]))
    esf.update_layout(title="PM2.5 medio por estación", xaxis_title="µg/m³", yaxis_title="")
    st.plotly_chart(aplicar_tema(esf), width="stretch", config={"displayModeBar": False})
with col2:
    localidades = res["localidades"]
    lof = go.Figure(go.Bar(x=localidades.pm25, y=localidades.localidad, orientation="h",
                           marker_color=[f"rgb{tuple(color_rgb_cuantil(v, localidades.pm25))}" for v in localidades.pm25]))
    lof.update_layout(title="PM2.5 medio por localidad", xaxis_title="µg/m³", yaxis_title="")
    st.plotly_chart(aplicar_tema(lof), width="stretch", config={"displayModeBar": False})
nota_metodologica(f"<strong>Qué se ve:</strong> las medias resumen {len(estaciones)} estaciones y {len(localidades)} localidades con registros.<br><strong>Qué no se puede concluir:</strong> las diferencias espaciales no separan ubicación, cobertura y características de cada estación.")

st.subheader("La caída de nivel")
cambio = res["cambio"].sort_values("pm25_diferencia")
ca = make_subplots(rows=1, cols=3, subplot_titles=("PM2.5 medio", "PM10 medio", "Mediana PM2.5/PM10"))
for nombre, sufijo, color in [("Antes del hueco", "_antes", "#00C2A8"), ("Después del hueco", "_despues", "#E67E22")]:
    ca.add_trace(go.Bar(x=cambio.estacion, y=cambio[f"pm25{sufijo}"], name=nombre,
                        marker_color=color, showlegend=True), row=1, col=1)
    ca.add_trace(go.Bar(x=cambio.estacion, y=cambio[f"pm10{sufijo}"], name=nombre,
                        marker_color=color, showlegend=False), row=1, col=2)
ca.add_trace(go.Bar(x=res["razon"].periodo, y=res["razon"].mediana,
                    marker_color=["#00C2A8", "#E67E22"], showlegend=False), row=1, col=3)
ca.update_xaxes(tickangle=-65, row=1, col=1); ca.update_xaxes(tickangle=-65, row=1, col=2)
ca.update_yaxes(title_text="PM2.5 (µg/m³)", row=1, col=1); ca.update_yaxes(title_text="PM10 (µg/m³)", row=1, col=2)
ca.update_layout(title="La caída de nivel · PM2.5, PM10 y razón", barmode="group", height=580)
st.plotly_chart(aplicar_tema(ca), width="stretch", config={"displayModeBar": False})
razon_a = float(res["razon"].iloc[0].mediana); razon_d = float(res["razon"].iloc[1].mediana)
nota_metodologica(f"<strong>Qué se ve:</strong> el PM2.5 medio fue menor después del hueco en {res['caida_estaciones']} de {res['n_estaciones']} estaciones; la razón mediana PM2.5/PM10 pasó de {razon_a:.3f} a {razon_d:.3f}. Las medias de viento, lluvia y tmax_anom cambiaron {cambio.vel_ciudad_ms_diferencia.mean():+.3f} m/s, {cambio.precip_mm_diferencia.mean():+.3f} mm y {cambio.tmax_anom_diferencia.mean():+.3f} °C.<br><strong>Qué no se puede concluir:</strong> este resumen no determina el origen; podría tratarse de una variación real o de una diferencia de equipo o calibración.")

st.subheader("Correlaciones de Spearman")
corr = res["correlaciones"]
heat = go.Figure(go.Heatmap(z=corr.to_numpy(), x=corr.columns, y=corr.index,
                            zmin=-1, zmax=1, zmid=0,
                            colorscale=[[0, "#8E44AD"], [.25, "#E67E22"], [.5, "#1A1F2B"], [.75, "#F1C40F"], [1, "#2ECC71"]],
                            colorbar={"title":"ρ"}, hovertemplate="%{y} · %{x}<br>Spearman: %{z:.2f}<extra></extra>"))
heat.update_layout(title="Variables numéricas y PM2.5 (sin dirección del viento)", height=680,
                   xaxis={"tickangle":-45})
st.plotly_chart(aplicar_tema(heat), width="stretch", config={"displayModeBar": False})
nota_metodologica("Correlación no es causalidad. Se excluyen dir_sin y dir_cos porque la dirección del viento está fuera de este análisis según las decisiones vigentes.")
