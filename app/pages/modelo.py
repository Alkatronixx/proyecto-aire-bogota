"""Explica los modelos, su evaluación temporal y las verificaciones realizadas.
Lee el artefacto de anomalías v2 y resultados versionados en data/processed/app.
No carga los modelos explicativo v1 ni predictivo; sus métricas salen de CSV.
Agrega series temporales antes de graficar y describe límites de interpretación.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from app.components.paleta import ACENTO
from app.components.tema_graficos import aplicar_tema
from app.components.ui import cargar_estilos, caja_hallazgo, encabezado_pagina, nota_metodologica
from app.utils.datos import (
    cargar_aire, cargar_csv_app, cargar_modelo_anomalia, cargar_parquet_app,
    ROOT,
)
from app.utils.cifras_modelo import (
    MAX_ABS_RHO_LLUVIA, MAX_ABS_RHO_TEMPERATURA, FILAS_PRUEBA_ALINEACION,
    MAE_K0, MAE_K_MAS_1, MEJORA_MAE_K_MAS_1,
)

INICIO_TRAIN = pd.Timestamp("2023-10-24")
FIN_TRAIN = pd.Timestamp("2025-10-23")
INICIO_TEST = pd.Timestamp("2025-10-24")
FIN_TEST = pd.Timestamp("2026-10-23")
INICIO_HUECO = pd.Timestamp("2025-08-04")
FIN_HUECO = pd.Timestamp("2025-10-16")


@st.cache_data(show_spinner=False)
def agregar_series_prueba(predicciones: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Agrega PM real y predicho a nivel ciudad y semana para el gráfico temporal."""
    diaria = (predicciones.groupby("fecha", as_index=False)
              .agg(observado=("pm25_real", "mean"), predicho=("pm25_predicho", "mean")))
    diaria["semana"] = pd.to_datetime(diaria.fecha).dt.to_period("W").dt.start_time
    semanal = diaria.groupby("semana", as_index=False)[["observado", "predicho"]].mean()
    return diaria, semanal


@st.cache_data(show_spinner=False)
def ejemplo_anomalia(datos: pd.DataFrame, climatologia: pd.DataFrame) -> dict:
    """Busca una observación real de entrenamiento con climatología estación-mes suficiente."""
    entrenamiento = datos.loc[pd.to_datetime(datos.fecha).le(FIN_TRAIN) & datos.pm25.notna()].copy()
    parejas = climatologia.loc[climatologia["count"].ge(10)]
    muestra = entrenamiento.merge(parejas, on=["estacion_id", "mes"], how="inner")
    fila = muestra.sort_values(["estacion_id", "fecha"]).iloc[0]
    return {
        "fecha": pd.Timestamp(fila.fecha), "estacion": fila.estacion,
        "pm25": float(fila.pm25), "climatologia": float(fila["mean"]),
        "anomalia": float(fila.pm25-fila["mean"]),
    }


def tabla_metricas(explicativo: pd.DataFrame, predictivo: pd.DataFrame,
                   predicciones: pd.DataFrame) -> pd.DataFrame:
    """Arma la comparación leyendo las cifras publicadas de sus CSV de origen."""
    exp = explicativo.set_index("modelo")
    registros = []
    for clave, nombre in [("clim", "Climatología"), ("+Ridge", "Ridge (publicado)"),
                          ("+RF", "Random Forest"), ("+HGB", "HGB")]:
        fila = exp.loc[clave]
        registros.append({"familia": "Explicativo", "modelo": nombre,
                          "n": len(predicciones), "MAE": fila.MAE,
                          "RMSE": fila.RMSE, "R2": fila.R2})
    pred = predictivo.loc[predictivo.version.eq("predictivo")].set_index("modelo")
    nombres_pred = [("línea base", "Persistencia"), ("Ridge", "Ridge (guardado)"),
                    ("Random Forest", "Random Forest (comparación)")]
    for clave, nombre in nombres_pred:
        fila = pred.loc[clave]
        registros.append({"familia": "Predictivo", "modelo": nombre, "n": int(fila.n),
                          "MAE": fila.MAE, "RMSE": fila.RMSE, "R2": fila.R2})
    return pd.DataFrame(registros)


cargar_estilos()
encabezado_pagina("Modelo", "Qué aprende cada versión, cómo se evaluó y qué límites tienen sus predicciones.")
datos = cargar_aire()
artefacto = cargar_modelo_anomalia()
predicciones = cargar_parquet_app("predicciones_prueba_v2.parquet")
metricas_exp = cargar_csv_app("diagnostico_modelo_metricas_v2.csv")
metricas_pred = cargar_csv_app("metricas_modelos.csv")

st.subheader("Qué quisimos saber")
st.markdown(
    "El **modelo explicativo** usa meteorología y calendario para resumir asociaciones con PM2.5. "
    "El **predictivo** también usa mediciones recientes de PM2.5 para anticipar valores; no es el modelo del simulador. "
    "La **climatología** es el promedio de entrenamiento para una estación y mes. La **anomalía** es la diferencia entre una observación y ese nivel típico."
)
ejemplo = ejemplo_anomalia(datos, artefacto["climatologia"])
st.info(
    f"Ejemplo real de entrenamiento: {ejemplo['estacion']}, {ejemplo['fecha']:%d-%b-%Y}; "
    f"PM2.5 observado {ejemplo['pm25']:.2f} µg/m³ − climatología estación-mes "
    f"{ejemplo['climatologia']:.2f} = anomalía {ejemplo['anomalia']:+.2f} µg/m³."
)

st.subheader("Línea de tiempo de evaluación")
linea = go.Figure()
linea.add_trace(go.Scatter(x=[INICIO_TRAIN, FIN_TRAIN], y=[1, 1], mode="lines+markers",
                           name="Entrenamiento", line={"color": ACENTO, "width": 18},
                           marker={"size": 9}))
linea.add_trace(go.Scatter(x=[INICIO_TEST, FIN_TEST], y=[0, 0], mode="lines+markers",
                           name="Prueba", line={"color": "#E67E22", "width": 18},
                           marker={"size": 9}))
linea.add_vrect(x0=INICIO_HUECO, x1=FIN_HUECO, y0=.68, y1=1.32,
                fillcolor="#778395", opacity=.45, line_width=0,
                annotation_text="sin mediciones PM", annotation_position="top left")
linea.update_yaxes(tickvals=[0, 1], ticktext=["Prueba", "Entrenamiento"], range=[-.5, 1.5])
linea.update_layout(title="Separación temporal", xaxis_title="Fecha", yaxis_title="")
st.plotly_chart(aplicar_tema(linea), use_container_width=True, config={"displayModeBar": False})
st.caption("Entrenamiento: 24-oct-2023 a 23-oct-2025. Prueba: 24-oct-2025 a 23-oct-2026. El hueco 04-ago a 16-oct-2025 cae dentro del entrenamiento; nunca se mezclan fechas al azar.")

st.subheader("Control de alineación temporal")
st.markdown(
    "El IDEAM define su día meteorológico desde las 7:00 a. m. del día anterior hasta las 7:00 a. m. "
    "del día de la medición; por eso comprobamos si lluvia y temperaturas estaban desfasadas respecto al PM2.5. "
    "Desplazamos esas variables entre −2 y +2 días."
)
st.info(
    f"No aparece un desfase uniforme: las correlaciones de lluvia no pasan de "
    f"{MAX_ABS_RHO_LLUVIA:.2f} y las de temperatura de {MAX_ABS_RHO_TEMPERATURA:.2f} en valor absoluto, "
    f"con signos cambiantes. Con +1 día, el MAE pasa de {MAE_K0:.3f} a {MAE_K_MAS_1:.3f} µg/m³ "
    f"(mejora {MEJORA_MAE_K_MAS_1:.3f}; {FILAS_PRUEBA_ALINEACION:,} filas de prueba). "
    "Es un cambio pequeño: se mantiene la alineación sin desplazar. La hipótesis sobre el día meteorológico "
    "no pudo confirmarse con estos datos."
)

st.subheader("Resultados de prueba")
metricas = tabla_metricas(metricas_exp, metricas_pred, predicciones)
st.dataframe(metricas.style.format({"MAE": "{:.3f}", "RMSE": "{:.3f}", "R2": "{:.3f}"}),
             hide_index=True, use_container_width=True)
st.caption("Las cifras explicativas se leen de diagnostico_modelo_metricas_v2.csv y las predictivas de metricas_modelos.csv; coinciden con la tabla indicada a tres decimales.")
st.info("HGB obtuvo el menor MAE explicativo en prueba. El Ridge publicado se eligió por validación cruzada temporal dentro del entrenamiento, no por el resultado de prueba.")

st.subheader("Qué contiene el artefacto activo")
modelo = artefacto["modelo"]
archivo_modelo = ROOT / "models" / "modelo_anomalia_v2.joblib"
izq, der = st.columns(2)
with izq:
    st.markdown(f"**Estimador:** {type(modelo).__name__} con Ridge · alpha {artefacto['alpha_ridge']} · {archivo_modelo.stat().st_size:,} bytes.")
    st.markdown(f"**Entrenamiento final:** hasta {artefacto['fecha_fin_train']} · {modelo.named_steps['standardscaler'].n_samples_seen_:,} filas ajustadas.")
    st.markdown(f"**Climatología:** {len(artefacto['climatologia'])} pares estación-mes; {len(artefacto['media_estacion'])} medias de estación; media global {artefacto['media_global']:.3f} µg/m³.")
with der:
    st.markdown("**12 variables, en orden de predicción:**")
    st.code(" → ".join(artefacto["features"]), language=None)
    st.markdown(f"**Razón del intervalo:** q10 {artefacto['q10_razon']:.4f} · q90 {artefacto['q90_razon']:.4f}.")
    st.markdown("Las medias térmicas por estación IDEAM no están guardadas en este artefacto; el simulador las calcula con entrenamiento únicamente.")

st.subheader("Predicho frente a observado")
scatter_col, weekly_col = st.columns(2, gap="large")
with scatter_col:
    disperso = go.Figure(go.Scatter(
        x=predicciones.pm25_real, y=predicciones.pm25_predicho, mode="markers",
        marker={"color": ACENTO, "size": 5, "opacity": .45},
        hovertemplate="Observado %{x:.2f}<br>Predicho %{y:.2f} µg/m³<extra></extra>",
        name="Día-estación",
    ))
    limite = max(float(predicciones.pm25_real.max()), float(predicciones.pm25_predicho.max()))
    disperso.add_trace(go.Scatter(x=[0, limite], y=[0, limite], mode="lines",
                                  line={"color": "#E67E22", "dash": "dash"}, name="45°"))
    disperso.update_layout(title="Predicho frente a observado · prueba", xaxis_title="PM2.5 observado (µg/m³)", yaxis_title="PM2.5 predicho (µg/m³)")
    st.plotly_chart(aplicar_tema(disperso), use_container_width=True, config={"displayModeBar": False})
with weekly_col:
    _, semanal = agregar_series_prueba(predicciones)
    serie = go.Figure()
    serie.add_trace(go.Scatter(x=semanal.semana, y=semanal.observado, mode="lines+markers",
                               name="Observado", line={"color": ACENTO}))
    serie.add_trace(go.Scatter(x=semanal.semana, y=semanal.predicho, mode="lines+markers",
                               name="Predicho", line={"color": "#E67E22"}))
    serie.update_layout(title="Media semanal de ciudad · prueba", xaxis_title="Semana", yaxis_title="PM2.5 (µg/m³)", hovermode="x unified")
    st.plotly_chart(aplicar_tema(serie), use_container_width=True, config={"displayModeBar": False})

sesgo_filas = predicciones.assign(sesgo=predicciones.pm25_predicho-predicciones.pm25_real)
sesgo_global = float(sesgo_filas.sesgo.mean())
sesgo_por_estacion = (sesgo_filas.groupby("estacion_id", as_index=False)
                      .agg(sesgo_medio=("sesgo", "mean"), n=("sesgo", "size"))
                      .sort_values("sesgo_medio", ascending=False))
st.subheader("Sesgo medio del Ridge v2 en prueba")
st.markdown(f"Sesgo = predicción − observado. Global: **{sesgo_global:+.3f} µg/m³** en {len(predicciones):,} filas.")
st.dataframe(sesgo_por_estacion.style.format({"sesgo_medio": "{:+.3f}", "n": "{:,.0f}"}),
             hide_index=True, use_container_width=True)

st.subheader("MAE por estación frente a climatología")
mae_estacion = cargar_csv_app("diagnostico_modelo_mae_estacion_v2.csv").sort_values("MAE_clim")
fig_mae = go.Figure()
fig_mae.add_trace(go.Bar(x=mae_estacion.MAE_clim, y=mae_estacion.estacion_id,
                         name="Climatología", orientation="h", marker_color="#778395"))
fig_mae.add_trace(go.Bar(x=mae_estacion.MAE_mejor_v2, y=mae_estacion.estacion_id,
                         name="Ridge v2", orientation="h", marker_color=ACENTO))
fig_mae.update_layout(title="MAE de PM2.5 por estación", barmode="group", xaxis_title="MAE (µg/m³)", yaxis_title="")
st.plotly_chart(aplicar_tema(fig_mae), use_container_width=True, config={"displayModeBar": False})
nota_metodologica("Qué se ve: el MAE del Ridge v2 y de la climatología cambia entre estaciones. Qué no se puede concluir: la diferencia no identifica por sí sola qué característica de una estación está asociada con el error.")

st.subheader("Ablación por grupos")
ablacion = cargar_csv_app("diagnostico_modelo_ablacion_v2.csv")
fig_abl = go.Figure()
fig_abl.add_trace(go.Bar(x=ablacion.grupo_excluido, y=ablacion.MAE_modelo_completo,
                         name="Modelo completo", marker_color=ACENTO))
fig_abl.add_trace(go.Bar(x=ablacion.grupo_excluido, y=ablacion.MAE_sin_grupo,
                         name="Sin el grupo", marker_color="#E67E22"))
fig_abl.update_layout(title="Error al quitar un bloque de variables", barmode="group", xaxis_title="Grupo excluido", yaxis_title="MAE (µg/m³)")
st.plotly_chart(aplicar_tema(fig_abl), use_container_width=True, config={"displayModeBar": False})
nota_metodologica("Qué se ve: el MAE varía al excluir cada grupo del Ridge de ablación. Qué no se puede concluir: la diferencia no es una contribución causal aislada ni una selección universal de variables.")
completo = float(ablacion.MAE_modelo_completo.iloc[0])
sin_lluvia = float(ablacion.loc[ablacion.grupo_excluido.eq("lluvia"), "MAE_sin_grupo"].iloc[0])
if sin_lluvia <= completo:
    texto_lluvia = (
        f"La lluvia diaria no aportó mejora medible en el año de prueba: MAE sin lluvia "
        f"{sin_lluvia:.3f} µg/m³ y modelo completo {completo:.3f} µg/m³."
    )
else:
    texto_lluvia = (
        f"La tabla muestra MAE de {sin_lluvia:.3f} µg/m³ al excluir lluvia y "
        f"{completo:.3f} µg/m³ para el modelo completo (diferencia {sin_lluvia-completo:+.3f})."
    )
resumen_ablacion = " ".join(
    f"Sin {fila.grupo_excluido}: {fila.MAE_sin_grupo:.3f} µg/m³."
    for fila in ablacion.itertuples()
)
st.caption(f"{texto_lluvia} {resumen_ablacion}")

st.subheader("Importancia por permutación agrupada")
permutacion = cargar_csv_app("diagnostico_modelo_permutacion_grupos_v2.csv").sort_values("aumento_MAE")
fig_perm = go.Figure(go.Bar(x=permutacion.aumento_MAE, y=permutacion.grupo,
                            orientation="h", marker_color=ACENTO))
fig_perm.update_layout(title="Cambio de MAE al permutar conjuntamente cada grupo", xaxis_title="Aumento del MAE (µg/m³)", yaxis_title="")
st.plotly_chart(aplicar_tema(fig_perm), use_container_width=True, config={"displayModeBar": False})
nota_metodologica("Qué se ve: la pérdida predictiva cambia al permutar grupos de columnas en conjunto. Qué no se puede concluir: columnas relacionadas pueden compartir información y el orden no demuestra causalidad.")

st.subheader("Dependencia parcial")
dependencia = cargar_csv_app("diagnostico_modelo_dependencia_parcial_v2.csv")
variables_pdp = ["vel_ciudad_ms", "precip_mm", "tmax_anom", "dia_semana"]
panel = make_subplots(rows=2, cols=2, subplot_titles=variables_pdp)
for indice, variable in enumerate(variables_pdp):
    tabla = dependencia.loc[dependencia.variable.eq(variable)].sort_values("valor")
    panel.add_trace(go.Scatter(x=tabla.valor, y=tabla.pm25_predicho_medio,
                               mode="lines+markers", line={"color": ACENTO},
                               showlegend=False), row=indice//2+1, col=indice%2+1)
panel.update_yaxes(title_text="PM2.5 medio predicho (µg/m³)")
panel.update_layout(title="Promedio de predicciones al variar una entrada", height=650)
st.plotly_chart(aplicar_tema(panel), use_container_width=True, config={"displayModeBar": False})
nota_metodologica("Qué se ve: cambia la predicción media cuando se fija una variable y se promedian las demás entradas observadas. Qué no se puede concluir: estas curvas no describen escenarios conjuntos ni una respuesta causal.")

st.subheader("Cobertura del intervalo por estación")
cobertura = cargar_csv_app("diagnostico_modelo_cobertura_estacion_v2.csv").sort_values("cobertura")
fig_cob = go.Figure(go.Bar(x=cobertura.cobertura*100, y=cobertura.estacion_id,
                           orientation="h", marker_color=ACENTO))
fig_cob.update_layout(title="Porcentaje de observaciones contenidas en el intervalo 10–90 %",
                      xaxis_title="Cobertura empírica (%)", yaxis_title="")
st.plotly_chart(aplicar_tema(fig_cob), use_container_width=True, config={"displayModeBar": False})
nota_metodologica(f"El intervalo se calibró con el año de prueba; cobertura global {sesgo_filas.pm25_real.between(predicciones.limite_inferior, predicciones.limite_superior).mean():.1%}, rango por estación {cobertura.cobertura.min():.1%}–{cobertura.cobertura.max():.1%}. Esta cobertura observada no garantiza cobertura futura.")

st.subheader("Lo que detectamos y corregimos")
qc1, qc2, qc3 = st.columns(3, gap="medium")
base_inicial = metricas_pred.loc[metricas_pred.modelo.str.contains("línea base", case=False, na=False)].iloc[0]
comparacion_clima = cargar_csv_app("diagnostico_modelo_2_comparacion_climatologia_misma_prueba.csv")
base_train = comparacion_clima.loc[comparacion_clima.metodo.str.startswith("groupby")].iloc[0]
with qc1:
    caja_hallazgo(f"La primera climatología tuvo MAE {base_inicial.MAE:.3f}; el cálculo solo con entrenamiento, sobre las mismas {int(base_train.n):,} filas, dio {base_train.MAE:.3f}. Se corrigió la referencia para evitar usar prueba al calcularla.")
rf_guardado = cargar_csv_app("diagnostico_modelo_2_rf_guardado_sesgo_mae_estacion.csv")
mae_en_muestra = float(np.average(rf_guardado.MAE, weights=rf_guardado.n))
rf_temporal = metricas_pred.loc[metricas_pred.modelo.eq("Random Forest") & metricas_pred.version.eq("explicativo")].iloc[0]
with qc2:
    caja_hallazgo(f"El RF guardado arrojó MAE {mae_en_muestra:.3f} al evaluarse sobre filas que había visto; no es un resultado de prueba válido. Reajustado solo con entrenamiento, el MAE temporal fue {rf_temporal.MAE:.3f}.")
auditoria = cargar_csv_app("diagnostico_modelo_2_auditoria_filtraciones.csv")
rezagos = auditoria.loc[auditoria.paso.str.contains("rezagos PM2.5", case=False, na=False)]
evidencia_rezagos = rezagos.iloc[0].evidencia if not rezagos.empty else "se verificaron con fechas calendario y sin usar observaciones futuras"
with qc3:
    caja_hallazgo(f"`pm25_ayer` se contrastó con D−1 y queda ausente cuando ese día no tiene medición; no salta el hueco. `pm25_media_3d` se revisó por estación y fecha. Registro: {evidencia_rezagos}.")

st.subheader("Limitaciones")
train_pm = datos.loc[datos.fecha.le(FIN_TRAIN), "pm25"].mean()
test_pm = datos.loc[datos.fecha.ge(INICIO_TEST) & datos.fecha.le(FIN_TEST), "pm25"].mean()
lluvias_compartidas = datos.loc[datos.fecha.le(FIN_TRAIN), "precip_estacion_id"].nunique()
permutacion_idx = cargar_csv_app("diagnostico_modelo_permutacion_grupos_v2.csv").set_index("grupo").aumento_MAE
st.markdown(
    f"- El PM2.5 medio observado fue {train_pm:.2f} µg/m³ en entrenamiento y {test_pm:.2f} en prueba; el origen del menor nivel de prueba no se determina aquí.\n"
    f"- La lluvia se comparte mediante {lluvias_compartidas} estaciones IDEAM asignadas; el viento usado es un índice de ciudad y no describe viento local.\n"
    "- La dirección del viento quedó fuera del modelo.\n"
    f"- En permutación agrupada, los cambios de MAE para temperatura ({permutacion_idx.get('temperatura', np.nan):+.3f}) y calendario ({permutacion_idx.get('calendario', np.nan):+.3f} µg/m³) fueron pequeños frente al del viento ({permutacion_idx.get('viento', np.nan):+.3f}); son asociaciones del modelo, no relaciones causales."
)
