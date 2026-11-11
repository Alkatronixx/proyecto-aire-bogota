"""Permite explorar escenarios de PM2.5 con el Ridge de anomalías v2.
Lee el artefacto v2, sus predicciones de prueba y datos procesados de entrenamiento.
Mantiene una referencia fija y completa automáticamente los campos no editables.
Las diferencias se presentan como asociaciones del modelo, no como efectos causales.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from app.components.paleta import color_rgb_cuantil
from app.components.tema_graficos import aplicar_tema
from app.components.ui import cargar_estilos, encabezado_pagina, nota_metodologica
from app.utils.datos import (
    cargar_aire, cargar_csv_app, cargar_modelo_anomalia, cargar_tabla_maestra,
    cargar_parquet_app,
)
from app.utils.simulador import (
    calcular_tornado, crear_preset, estadisticas_entrenamiento,
    escenario_referencia, predecir_escenario,
)

CLAVES_ESCENARIO = [
    "estacion_id", "mes", "dia_semana", "es_festivo", "vel_ciudad_ms",
    "precip_mm", "precip_1d_antes", "tmax_c", "tmin_c",
]
NOMBRES_DIA = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
               4: "Viernes", 5: "Sábado", 6: "Domingo"}
PRESETS = ["Personalizado", "Día laborable sin viento",
           "Fin de semana seco y ventoso", "Día laborable lluvioso"]


def controles_escenario(prefijo: str, titulo: str, inicial: dict, estaciones: list[str],
                        nombres: dict, estadisticas: dict) -> dict:
    """Renderiza controles con opciones discretas y límites percentiles del entrenamiento."""
    st.markdown(f"**{titulo}**")
    for clave in CLAVES_ESCENARIO:
        st.session_state.setdefault(f"{prefijo}_{clave}", inicial[clave])
    e1, e2 = st.columns(2)
    with e1:
        estacion = st.selectbox("Estación", estaciones,
                                format_func=lambda x: nombres.get(x, x), key=f"{prefijo}_estacion_id")
        mes = st.selectbox("Mes", estadisticas["meses"], key=f"{prefijo}_mes",
                           format_func=lambda x: pd.Timestamp(2025, int(x), 1).strftime("%B"))
        dia = st.selectbox("Día de la semana", estadisticas["dias_semana"],
                           key=f"{prefijo}_dia_semana", format_func=lambda x: NOMBRES_DIA[int(x)])
    with e2:
        festivo = st.checkbox("Es festivo", key=f"{prefijo}_es_festivo")
        viento = _slider_rango(prefijo, "vel_ciudad_ms", "Viento de ciudad (m/s)", estadisticas)
        lluvia_hoy = _slider_rango(prefijo, "precip_mm", "Lluvia hoy (mm)", estadisticas)
        lluvia_ayer = _slider_rango(prefijo, "precip_1d_antes", "Lluvia ayer (mm)", estadisticas)
    tmin = _slider_rango(prefijo, "tmin_c", "Temperatura mínima (°C)", estadisticas)
    tmax_min = max(estadisticas["cotas_entrada"]["tmax_c"][0], float(tmin))
    maximo_tmax = float(estadisticas["cotas_entrada"]["tmax_c"][1])
    clave_tmax = f"{prefijo}_tmax_c"
    valor_tmax = float(np.clip(st.session_state.get(clave_tmax, inicial["tmax_c"]),
                               tmax_min, maximo_tmax))
    if clave_tmax in st.session_state:
        # La sesión ya contiene el valor inicial, por eso no se pasa además value= al widget.
        st.session_state[clave_tmax] = valor_tmax
    argumentos_tmax = {"min_value": float(tmax_min), "max_value": maximo_tmax,
                       "step": 0.1, "format": "%.1f", "key": clave_tmax}
    if clave_tmax not in st.session_state:
        argumentos_tmax["value"] = valor_tmax
    tmax = st.slider("Temperatura máxima (°C)", **argumentos_tmax)
    st.caption(f"Rango p1–p99 de entrenamiento: {tmax_min:.1f}–{estadisticas['cotas_entrada']['tmax_c'][1]:.1f} °C; tmax ≥ tmin.")
    return {
        "estacion_id": estacion, "mes": int(mes), "dia_semana": int(dia),
        "es_festivo": bool(festivo), "vel_ciudad_ms": float(viento),
        "precip_mm": float(lluvia_hoy), "precip_1d_antes": float(lluvia_ayer),
        "tmax_c": float(tmax), "tmin_c": float(tmin),
    }


def _slider_rango(prefijo: str, variable: str, titulo: str, estadisticas: dict) -> float:
    """Muestra un deslizador cuya cota impide salir del rango p1-p99 observado."""
    minimo, maximo = estadisticas["cotas_entrada"][variable]
    inicial = float(estadisticas["medianas_entrada"][variable])
    step = 0.1 if variable.startswith("precip") else 0.05
    clave = f"{prefijo}_{variable}"
    valor_inicial = float(np.clip(st.session_state.get(clave, inicial), minimo, maximo))
    if clave in st.session_state:
        # Se evita duplicar el valor en Session State y el argumento value del slider.
        st.session_state[clave] = valor_inicial
    argumentos = {"min_value": float(minimo), "max_value": float(maximo),
                  "step": step, "format": "%.2f", "key": clave}
    if clave not in st.session_state:
        argumentos["value"] = valor_inicial
    valor = st.slider(titulo, **argumentos)
    st.caption(f"Entrenamiento p1–p99: {minimo:.2f}–{maximo:.2f}")
    return float(valor)


def mostrar_resultado(nombre: str, resultado: dict, referencia: dict,
                      artefacto: dict, estadisticas: dict) -> None:
    """Muestra cifra principal, intervalo multiplicativo y cambio ante la referencia."""
    tono = color_rgb_cuantil(resultado["prediccion"], estadisticas["pm25_entrenamiento"])
    color = f"rgb({tono[0]}, {tono[1]}, {tono[2]})"
    cambio = resultado["prediccion"] - referencia["prediccion"]
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">PM2.5 · escenario {nombre}</div>'
        f'<div class="kpi-value" style="color:{color}">{resultado["prediccion"]:.1f} µg/m³</div>'
        f'<div class="kpi-detail">Intervalo 10–90 %: [{resultado["limite_inferior"]:.1f}; '
        f'{resultado["limite_superior"]:.1f}] µg/m³</div></div>', unsafe_allow_html=True,
    )
    st.markdown(f"**Nivel típico de esta estación en este mes: {resultado['nivel_tipico']:.1f} µg/m³**")
    st.metric("Cambio frente a la referencia", f"{cambio:+.1f} µg/m³",
              help="La referencia usa las medianas del entrenamiento, día laborable y sin lluvia.")


cargar_estilos()
encabezado_pagina("Simulador de escenarios", "Explora cómo cambia la predicción del modelo al modificar una situación meteorológica y de calendario.")
datos = cargar_aire()
artefacto = cargar_modelo_anomalia()
estadisticas = estadisticas_entrenamiento(datos)
asignacion = cargar_tabla_maestra("asignacion_estaciones.csv")
asignacion["estacion_id"] = asignacion.estacion_id.astype(str)
estaciones = [e for e in estadisticas["estaciones"] if e in set(asignacion.estacion_id)]
nombres = datos.drop_duplicates("estacion_id").set_index("estacion_id").estacion.to_dict()
estacion_inicial = "centro_de_alto_rendimiento" if "centro_de_alto_rendimiento" in estaciones else estaciones[0]
mes_inicial = min(estadisticas["meses"], key=lambda m: abs(m - 6))
referencia_inicial = escenario_referencia(estadisticas, estacion_inicial, mes_inicial, asignacion)

col_controles, col_resultados = st.columns([0.95, 1.2], gap="large")
with col_controles:
    st.subheader("Escenario A")
    preset = st.selectbox("Presets", PRESETS, key="sim_preset_a")
    aplicado = st.session_state.get("_sim_preset_aplicado", preset)
    if preset != aplicado and preset != "Personalizado":
        valores_preset = crear_preset(preset, referencia_inicial, estadisticas)
        for clave in CLAVES_ESCENARIO:
            st.session_state[f"a_{clave}"] = valores_preset[clave]
    st.session_state["_sim_preset_aplicado"] = preset
    escenario_a = controles_escenario("a", "Entradas del escenario A", referencia_inicial,
                                      estaciones, nombres, estadisticas)
    st.caption("El preset de bajo viento usa el percentil 10 observado; no representa calma ni un valor cero inventado.")
    st.session_state["_ultimo_escenario_a"] = escenario_a.copy()
    if st.button("Copiar A en B", width="stretch"):
        for clave in CLAVES_ESCENARIO:
            st.session_state[f"b_{clave}"] = escenario_a[clave]
    escenario_b_inicial = crear_preset("Fin de semana seco y ventoso", referencia_inicial, estadisticas)
    with st.expander("Configurar escenario B", expanded=True):
        escenario_b = controles_escenario("b", "Entradas del escenario B", escenario_b_inicial,
                                          estaciones, nombres, estadisticas)

with col_resultados:
    st.subheader("Resultado del escenario A")
    resultado_a = predecir_escenario(escenario_a, artefacto, estadisticas, asignacion)
    referencia_a = escenario_referencia(estadisticas, escenario_a["estacion_id"], escenario_a["mes"], asignacion)
    prediccion_referencia_a = predecir_escenario(referencia_a, artefacto, estadisticas, asignacion)
    mostrar_resultado("A", resultado_a, prediccion_referencia_a, artefacto, estadisticas)
    resultado_b = predecir_escenario(escenario_b, artefacto, estadisticas, asignacion)

    st.subheader("Cambio al mover una variable")
    tornado = calcular_tornado(referencia_a, artefacto, estadisticas, asignacion)
    tornado = tornado.sort_values("cambio")
    figura = go.Figure(go.Bar(
        x=tornado.cambio, y=tornado.variable, orientation="h",
        marker_color=["#2ECC71" if valor < 0 else "#E67E22" if valor > 0 else "#AAB3C2"
                      for valor in tornado.cambio],
        customdata=np.column_stack([tornado.p10, tornado.p90]),
        hovertemplate="%{y}<br>Δ predicción: %{x:+.2f} µg/m³<br>p10=%{customdata[0]:.3f}; p90=%{customdata[1]:.3f}<extra></extra>",
    ))
    figura.add_vline(x=0, line_color="#D5DAE2", line_width=1)
    figura.update_layout(title="Cambio al comparar p10 con p90; resto fijo en la referencia",
                         xaxis_title="Cambio en PM2.5 predicho (µg/m³)", yaxis_title="")
    st.plotly_chart(aplicar_tema(figura), width="stretch", config={"displayModeBar": False})
    mayor = tornado.iloc[tornado.cambio.abs().argmax()]
    mae_ridge = float(cargar_csv_app("diagnostico_modelo_metricas_v2.csv").set_index("modelo").loc["+Ridge", "MAE"])
    if abs(float(mayor.cambio)) < mae_ridge:
        st.info(f"En el rango p10–p90, el mayor cambio individual es {abs(float(mayor.cambio)):.2f} µg/m³ ({mayor.variable}), menor que el MAE de prueba del Ridge ({mae_ridge:.2f}). El modelo calcula efectos individuales pequeños frente a su error típico.")
    else:
        st.info(f"En el rango p10–p90, el mayor cambio individual es {abs(float(mayor.cambio)):.2f} µg/m³ ({mayor.variable}); se muestra el valor calculado por el modelo.")

st.subheader("Comparación lado a lado")
cmp_a, cmp_b = st.columns(2, gap="large")
with cmp_a:
    st.metric(
        "Escenario A", f"{resultado_a['prediccion']:.1f} µg/m³",
        f"[{resultado_a['limite_inferior']:.1f}; {resultado_a['limite_superior']:.1f}]",
    )
with cmp_b:
    st.metric(
        "Escenario B", f"{resultado_b['prediccion']:.1f} µg/m³",
        f"[{resultado_b['limite_inferior']:.1f}; {resultado_b['limite_superior']:.1f}]",
    )
st.caption(
    f"B − A: {resultado_b['prediccion']-resultado_a['prediccion']:+.1f} µg/m³. "
    "El intervalo se obtiene multiplicando la predicción por los cuantiles de razón del artefacto."
)

st.subheader("Supuestos del escenario")
with st.expander("Variables completadas automáticamente", expanded=False):
    st.markdown(
        "- `es_fin_semana`: se deriva del día elegido (sábado o domingo).\n"
        "- `llueve`: lluvia de hoy ≥ 1 mm.\n"
        f"- `precip_3d_acum`: lluvia de ayer + mediana de entrenamiento de D−3 y D−2 ({estadisticas['mediana_d3_d2']:.2f} mm).\n"
        f"- `lluvia_ciudad_n`: mediana de entrenamiento condicionada por `llueve` (sin lluvia: {estadisticas['mediana_lluvia_ciudad_n'][False]:.1f}; con lluvia: {estadisticas['mediana_lluvia_ciudad_n'][True]:.1f}).\n"
        "- `tmax_anom` y `tmin_anom`: temperatura elegida menos la media de entrenamiento de la estación IDEAM asignada.\n"
        "- `amplitud_c`: tmax menos tmin. Mes y estación seleccionados determinan el nivel típico de climatología.\n\n"
        "El artefacto v2 no contiene los promedios IDEAM usados para las anomalías térmicas; la app los recalcula solo con filas hasta 2025-10-23."
    )

predicciones = cargar_parquet_app("predicciones_prueba_v2.parquet")
sesgo = (predicciones.pm25_predicho - predicciones.pm25_real).mean()
sesgo_estacion = (predicciones.assign(sesgo=predicciones.pm25_predicho-predicciones.pm25_real)
                  .groupby("estacion_id").sesgo.mean())
cubierto = predicciones.pm25_real.between(predicciones.limite_inferior, predicciones.limite_superior)
cobertura_global = float(cubierto.mean())
cobertura_estacion = cargar_csv_app("diagnostico_modelo_cobertura_estacion_v2.csv").cobertura
metricas_v2 = cargar_csv_app("diagnostico_modelo_metricas_v2.csv").set_index("modelo")
mejora = 100*(metricas_v2.loc["clim", "MAE"]-metricas_v2.loc["+Ridge", "MAE"])/metricas_v2.loc["clim", "MAE"]
train_pm = datos.loc[datos.fecha.le("2025-10-23"), "pm25"].mean()
test_pm = datos.loc[datos.fecha.ge("2025-10-24"), "pm25"].mean()
st.warning(
    f"El estimador resume asociaciones y no identifica relaciones causales. El PM2.5 medio observado fue {train_pm:.2f} µg/m³ en entrenamiento y {test_pm:.2f} en el año de prueba; el sesgo medio predicción−observado del Ridge v2 fue {sesgo:+.2f} µg/m³ (por estación, de {sesgo_estacion.min():+.2f} a {sesgo_estacion.max():+.2f}). La predicción absoluta puede sobreestimar; conviene leer los cambios frente a la referencia. "
    f"El intervalo se calibró con el año de prueba: cobertura global {cobertura_global:.1%} y rango por estación {cobertura_estacion.min():.1%}–{cobertura_estacion.max():.1%}. La mejora de MAE del Ridge v2 frente a climatología fue {mejora:.1f}%."
)
nota_metodologica("La referencia se recalcula para la misma estación y mes: medianas de entrenamiento, un día laborable y precipitación de hoy y ayer en cero. Los intervalos son calibración empírica de prueba, no una garantía individual.")
