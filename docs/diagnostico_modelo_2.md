# Segundo diagnóstico del modelado

Ejecuté `diagnostico_modelo_2.py`. El ajuste temporal del RF se hizo en memoria; los únicos archivos creados por el diagnóstico son el script y CSV nuevos con el prefijo solicitado. No modifiqué los datos, modelos ni scripts protegidos.

## Parte 1. RF explicativo y discrepancia de métricas

El diagnóstico anterior usó **`models/modelo_explicativo.joblib`**, el artefacto final ajustado con todas las filas completas disponibles, incluidas las fechas de prueba. No usó el RF temporal ajustado solo con entrenamiento. Al aplicarlo a las 5,410 filas de prueba que ya había visto en el ajuste, la evaluación es **dentro de muestra**.

Reentrené en memoria el RF con las mismas columnas e hiperparámetros del artefacto: 250 árboles, `min_samples_leaf=5`, `max_features=0.8`, `max_depth=None`, `random_state=42`. El ajuste temporal usó **8,905 filas**; las 5,410 filas de prueba son idénticas para ambos cálculos.

| Modelo evaluado en las mismas filas de prueba | MAE | RMSE | R² | Sesgo medio |
|---|---:|---:|---:|---:|
| RF reajustado solo con entrenamiento | 5.235 | 6.915 | 0.272 | +3.462 |
| RF guardado, ajustado con todo el periodo | 1.932 | 2.767 | 0.883 | +0.582 |

Por tanto, el MAE **1.932** y el sesgo **+0.582** del informe anterior no son métricas de prueba independientes. El MAE corregido por sesgo de estación de 1.735 también deriva de las predicciones dentro de muestra del artefacto guardado.

El desglose por estación confirma que el RF temporal tiene errores mucho mayores:

| Estación | n | Sesgo RF train | MAE RF train | Sesgo RF guardado | MAE RF guardado |
|---|---:|---:|---:|---:|---:|
| Bolivia | 290 | 4.29 | 5.37 | 0.67 | 1.44 |
| Carvajal - Sevillana | 295 | 9.63 | 11.80 | 2.56 | 4.57 |
| Centro de Alto Rendimiento | 299 | 2.72 | 4.51 | 0.29 | 1.30 |
| Ciudad Bolívar | 288 | 4.43 | 6.02 | 1.67 | 2.87 |
| Colina | 218 | 3.67 | 4.56 | 0.56 | 1.08 |
| Fontibón | 290 | 3.18 | 5.20 | 0.07 | 2.44 |
| Guaymaral | 292 | 4.10 | 5.20 | 0.65 | 1.54 |
| Jazmín | 302 | 1.71 | 4.61 | −0.33 | 1.64 |
| Kennedy | 289 | 2.16 | 4.58 | 0.11 | 1.98 |
| Las Ferias | 290 | 1.09 | 4.00 | −1.09 | 1.46 |
| MinAmbiente | 318 | 2.95 | 4.55 | 0.70 | 1.34 |
| Móvil 7ma | 266 | 0.91 | 3.23 | −0.25 | 1.26 |
| Móvil Fontibón | 266 | 5.82 | 6.66 | 1.74 | 2.69 |
| Puente Aranda | 236 | 3.35 | 4.86 | 0.88 | 1.72 |
| San Cristobal | 303 | 1.44 | 3.69 | 0.05 | 1.41 |
| Suba | 284 | 3.12 | 4.62 | −0.23 | 1.46 |
| Tunal | 289 | 2.24 | 4.91 | 0.02 | 2.22 |
| Usaquen | 280 | 6.03 | 6.31 | 2.10 | 2.17 |
| Usme | 315 | 3.18 | 4.64 | 0.99 | 1.94 |

El detalle también está en [RF temporal por estación](../data/processed/app/diagnostico_modelo_2_rf_temporal_sesgo_mae_estacion.csv) y [RF guardado por estación](../data/processed/app/diagnostico_modelo_2_rf_guardado_sesgo_mae_estacion.csv).

## Parte 2. Qué contienen los artefactos

| Archivo | Estimador final e hiperparámetros principales | Tamaño | Filas vistas al ajustar | Ajuste |
|---|---|---:|---:|---|
| `modelo_explicativo.joblib` | `RandomForestRegressor`; 250 árboles, hoja mínima 5, `max_features=0.8`, profundidad sin límite, semilla 42 | 51,842,433 bytes | 14,315 | Todos los casos completos; última fecha 2026-10-23 |
| `modelo_predictivo.joblib` | `Ridge(alpha=100)`, estandarizado | 5,373 bytes | 13,653 | Todos los casos completos con rezagos; última fecha 2026-10-23 |
| `modelo_anomalia_v2.joblib` | `Ridge(alpha=100)`, imputación mediana y estandarizado | 5,183 bytes | 8,905 | Solo entrenamiento; última fila elegible 2025-10-22 |

El artefacto explicativo contiene una `Pipeline` con preprocesador y RF. Sus columnas son 16 predictores numéricos —viento, lluvia, anomalías de temperatura, calendario y ubicación— y `estacion_id` categórica. El preprocesador ajustado guarda medianas, escalador y las 19 categorías one-hot. Los metadatos incluyen medias de tmax/tmin por estación IDEAM, columnas, categorías y cuantiles de residuales (`q10 = −10.855`, `q90 = 2.900`).

El predictivo es **Ridge, no RF**. Contiene los mismos predictores, más `pm25_ayer` y `pm25_media_3d`; guarda los estados del imputador/escalador y las medias térmicas y categorías. El código selecciona `alpha` mediante CV temporal y guarda explícitamente Ridge en la línea 199 de `entrenar.py`; no elige el algoritmo por MAE de prueba. Por eso no coincide con el RF que obtuvo MAE 3.223 frente a 3.332 de Ridge en prueba.

El artefacto v2 guarda una `Pipeline` Ridge, la lista de 12 features, una tabla de climatología con **228 pares estación-mes** y 8,905 observaciones, las medias por estación, media global, tipo, alpha, fecha final de entrenamiento y cuantiles de razón `q10=0.3812`, `q90=1.2776`.

## Parte 3. Diferencia entre las climatologías

Ambos cálculos usan **5,410 filas de prueba**. El groupby simple usa la media estación-mes y, si falta el par, la media global. La regla v2 reemplaza por la media de la estación los pares con menos de 10 observaciones. No hubo pares estación-mes ausentes ni estaciones ausentes en esta prueba; **74 filas** corresponden a pares con menos de 10 observaciones.

| Climatología en las mismas filas | n | MAE | RMSE | R² | Sesgo |
|---|---:|---:|---:|---:|---:|
| Groupby simple; par ausente → global | 5,410 | 5.5092 | 6.9950 | 0.2552 | +3.6518 |
| Regla v2; par con n<10 → media estación | 5,410 | 5.4903 | 6.9682 | 0.2609 | +3.5954 |

La diferencia de MAE, **0.0189 µg/m³**, se debe al respaldo estación-mes de menos de 10 datos; el tamaño de prueba no cambia. [Comparación de climatologías](../data/processed/app/diagnostico_modelo_2_comparacion_climatologia_misma_prueba.csv).

## Parte 4. PM2.5/PM10 y el hueco

Los valores son medias globales de las 19 estaciones. La tabla incluye las medianas mensuales de la razón observada PM2.5/PM10. Los meses sin filas disponibles aparecen como “—”.

| Mes | PM2.5 2024 | 2025 | 2026 | PM10 2024 | 2025 | 2026 | Razón mediana 2024 | 2025 | 2026 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 21.11 | 17.64 | 11.53 | 42.78 | 37.14 | 24.46 | 0.499 | 0.482 | 0.477 |
| 2 | 20.63 | 18.67 | 16.67 | 42.79 | 37.17 | 33.30 | 0.486 | 0.517 | 0.507 |
| 3 | 29.97 | 19.54 | 21.79 | 49.74 | 37.13 | 40.61 | 0.634 | 0.538 | 0.526 |
| 4 | 23.71 | 14.31 | 13.44 | 44.05 | 29.89 | 28.09 | 0.541 | 0.488 | 0.459 |
| 5 | 10.75 | 12.06 | 7.64 | 26.36 | 29.23 | 20.56 | 0.389 | 0.406 | 0.352 |
| 6 | 9.70 | 9.06 | 7.09 | 25.57 | 23.33 | 20.19 | 0.378 | 0.392 | 0.346 |
| 7 | 7.28 | 6.88 | 5.94 | 21.47 | 19.74 | 17.77 | 0.352 | 0.370 | 0.362 |
| 8 | 12.94 | 7.36 | 6.58 | 28.81 | 19.40 | 18.62 | 0.457 | 0.350 | 0.383 |
| 9 | 14.50 | — | 8.98 | 30.11 | — | 24.19 | 0.480 | — | 0.391 |
| 10 | 14.31 | 12.44 | 10.79 | 31.35 | 31.81 | 26.02 | 0.453 | 0.385 | 0.425 |
| 11 | 16.00 | 14.13 | — | 32.75 | 33.74 | — | 0.491 | 0.403 | — |
| 12 | 18.35 | 16.94 | — | 38.28 | 38.48 | — | 0.486 | 0.445 | — |

En meses iguales, octubre-diciembre de 2025 frente a 2024, PM2.5 baja **1.41–1.87** cada mes, mientras PM10 sube **0.21–0.99**. De enero a agosto de 2026 frente a los mismos meses de 2025, PM2.5 baja en siete de ocho meses (marzo sube 2.26); PM10 también baja en siete de ocho (marzo sube 3.48). No hay PM de septiembre de 2025 con que comparar. Las comparaciones mensuales completas están en [diferencias de meses iguales](../data/processed/app/diagnostico_modelo_2_comparacion_meses_iguales.csv).

La mediana global de PM2.5/PM10 es **0.473 antes** del 2025-10-17 y **0.418 desde esa fecha**. Por estación:

| Estación | Antes | Desde 2025-10-17 |
|---|---:|---:|
| Bolivia | 0.384 | 0.320 |
| Carvajal - Sevillana | 0.467 | 0.261 |
| Centro de Alto Rendimiento | 0.536 | 0.538 |
| Ciudad Bolívar | 0.413 | 0.351 |
| Colina | 0.562 | 0.567 |
| Fontibón | 0.647 | 0.581 |
| Guaymaral | 0.488 | 0.359 |
| Jazmín | 0.522 | 0.444 |
| Kennedy | 0.421 | 0.485 |
| Las Ferias | 0.613 | 0.703 |
| MinAmbiente | 0.553 | 0.462 |
| Móvil 7ma | 0.378 | 0.387 |
| Móvil Fontibón | 0.334 | 0.279 |
| Puente Aranda | 0.459 | 0.375 |
| San Cristobal | 0.483 | 0.496 |
| Suba | 0.468 | 0.378 |
| Tunal | 0.492 | 0.466 |
| Usaquen | 0.456 | 0.326 |
| Usme | 0.353 | 0.317 |

Ambos contaminantes disminuyen en las ventanas amplias pre/post, pero no en la misma proporción: la razón mediana general baja. En octubre-diciembre de 2024/2025, en cambio, PM2.5 disminuye mientras PM10 queda estable o aumenta. La razón varía según estación; estos son patrones descriptivos, no una atribución causal.

Las medias semanales siguientes son medias de los promedios diarios de ciudad; la primera semana es parcial (solo el 1 de junio) y la última termina el 31 de diciembre. El conteo de estaciones indica cuántas tuvieron PM2.5 al menos un día esa semana.

| Inicio de semana | PM2.5 | Estaciones |
|---|---:|---:|
| 2025-05-26 | 5.93 | 15 |
| 2025-06-02 | 7.68 | 18 |
| 2025-06-09 | 12.87 | 18 |
| 2025-06-16 | 7.93 | 19 |
| 2025-06-23 | 8.83 | 19 |
| 2025-06-30 | 6.45 | 18 |
| 2025-07-07 | 6.39 | 18 |
| 2025-07-14 | 7.03 | 18 |
| 2025-07-21 | 7.13 | 19 |
| 2025-07-28 | 6.58 | 17 |
| 2025-08-04 a 2025-10-12 | sin datos | 0 cada semana |
| 2025-10-13 | 11.52 | 3 |
| 2025-10-20 | 13.19 | 17 |
| 2025-10-27 | 11.62 | 18 |
| 2025-11-03 | 16.40 | 17 |
| 2025-11-10 | 13.81 | 17 |
| 2025-11-17 | 15.48 | 17 |
| 2025-11-24 | 12.44 | 17 |
| 2025-12-01 | 18.40 | 17 |
| 2025-12-08 | 15.73 | 17 |
| 2025-12-15 | 21.98 | 18 |
| 2025-12-22 | 15.52 | 18 |
| 2025-12-29 | 8.36 | 17 |

Hay una diferencia entre las últimas semanas pre-hueco y las primeras semanas con cobertura recuperada, pero el hueco impide observar la transición; además, la cobertura pasa de 17 estaciones antes del hueco a solo 3 en la primera semana con datos y luego a 17–18. Las semanas posteriores fluctúan, no forman una bajada gradual uniforme. [Tabla semanal completa](../data/processed/app/diagnostico_modelo_2_pm25_semanal_ciudad.csv).

En el periodo del 2023-10-24 al 2025-08-03 frente al 2025-10-17 al 2026-10-23, las medias globales son: PM2.5 **15.79 → 11.77**; PM10 **33.44 → 27.27**; mediana de `vel_ciudad_ms` **en promedio 1.6007 → 1.6041** (el índice es común a las estaciones); precipitación media por fila **3.11 → 2.91**; anomalía tmax **+0.07 → +0.06**. Por estación, los valores de PM y los cambios de lluvia y tmax son:

| Estación | PM2.5 pre → post (Δ) | PM10 pre → post (Δ) | Precipitación pre → post (Δ) | tmax_anom pre → post (Δ) |
|---|---:|---:|---:|---:|
| Bolivia | 11.77 → 9.61 (−2.16) | 33.39 → 27.24 (−6.14) | 2.61 → 1.95 (−0.66) | 0.12 → 0.00 (−0.12) |
| Carvajal - Sevillana | 32.51 → 23.10 (−9.41) | 70.21 → 62.48 (−7.74) | 3.20 → 3.28 (+0.09) | 0.02 → 0.16 (+0.13) |
| Centro de Alto Rendimiento | 12.60 → 10.18 (−2.42) | 23.78 → 18.98 (−4.80) | 3.20 → 3.28 (+0.09) | 0.12 → 0.00 (−0.12) |
| Ciudad Bolívar | 16.32 → 12.19 (−4.13) | 38.13 → 31.99 (−6.14) | 3.02 → 2.56 (−0.46) | 0.02 → 0.16 (+0.13) |
| Colina | 11.68 → 8.30 (−3.38) | 20.46 → 15.55 (−4.90) | 2.61 → 1.95 (−0.66) | 0.12 → 0.00 (−0.12) |
| Fontibón | 19.63 → 16.18 (−3.44) | 29.94 → 26.08 (−3.86) | 3.20 → 3.28 (+0.09) | 0.12 → 0.00 (−0.12) |
| Guaymaral | 14.41 → 10.04 (−4.37) | 29.37 → 25.59 (−3.78) | 2.61 → 1.95 (−0.66) | 0.12 → 0.00 (−0.12) |
| Jazmín | 15.88 → 11.64 (−4.25) | 30.11 → 24.83 (−5.28) | 3.20 → 3.28 (+0.09) | 0.02 → 0.16 (+0.13) |
| Kennedy | 18.87 → 15.35 (−3.52) | 43.74 → 30.75 (−12.99) | 3.20 → 3.28 (+0.09) | 0.02 → 0.16 (+0.13) |
| Las Ferias | 15.29 → 12.35 (−2.95) | 24.72 → 16.79 (−7.93) | 3.20 → 3.28 (+0.09) | 0.12 → 0.00 (−0.12) |
| MinAmbiente | 14.81 → 10.00 (−4.82) | 25.91 → 21.26 (−4.65) | 3.20 → 3.28 (+0.09) | 0.02 → 0.16 (+0.13) |
| Móvil 7ma | 13.55 → 10.10 (−3.45) | 33.45 → 26.09 (−7.36) | 3.20 → 3.28 (+0.09) | 0.02 → 0.16 (+0.13) |
| Móvil Fontibón | 19.10 → 13.42 (−5.67) | 54.21 → 47.90 (−6.31) | 3.20 → 3.28 (+0.09) | 0.12 → 0.00 (−0.12) |
| Puente Aranda | 14.27 → 9.12 (−5.15) | 31.08 → 23.55 (−7.54) | 3.20 → 3.28 (+0.09) | 0.02 → 0.16 (+0.13) |
| San Cristobal | 11.80 → 10.57 (−1.23) | 25.08 → 20.78 (−4.30) | 3.02 → 2.56 (−0.46) | 0.02 → 0.16 (+0.13) |
| Suba | 15.66 → 11.74 (−3.93) | 33.14 → 28.89 (−4.25) | 2.61 → 1.95 (−0.66) | 0.12 → 0.00 (−0.12) |
| Tunal | 17.61 → 13.55 (−4.06) | 35.31 → 29.82 (−5.49) | 3.02 → 2.56 (−0.46) | 0.02 → 0.16 (+0.13) |
| Usaquen | 10.96 → 6.22 (−4.74) | 22.58 → 15.92 (−6.66) | 3.20 → 3.28 (+0.09) | 0.12 → 0.00 (−0.12) |
| Usme | 12.56 → 9.28 (−3.28) | 32.04 → 28.76 (−3.28) | 3.02 → 2.56 (−0.46) | 0.02 → 0.16 (+0.13) |

Las 19 estaciones tenían observaciones PM2.5 antes del hueco, cero durante el hueco y volvieron a tener datos después. **18 volvieron en octubre de 2025**; Colina volvió el **2026-01-30**. No infiero una causa para los cambios descritos. La tabla completa por estación está en [medias pre/post del hueco](../data/processed/app/diagnostico_modelo_2_medias_estacion_pre_post_hueco.csv), y el retorno por estación en [retorno del hueco](../data/processed/app/diagnostico_modelo_2_retorno_estacion_hueco.csv).

## Parte 5. Auditoría de ajustes y posibles filtraciones

| Archivo y líneas | Paso | ¿Usa prueba al ajustar? |
|---|---|---|
| `entrenar.py:36-38` | Medias tmax/tmin para anomalías | No; calcula con fechas hasta 2025-10-23. |
| `entrenar.py:39-40` | Rezagos PM2.5 | No usa futuro: `shift(1)` y rolling desplazado dentro de estación ordenada. Es la observación previa, que no siempre es el día calendario previo si hay huecos. |
| `entrenar.py:46-49, 91-92, 117-128` | Imputadores, escaladores y one-hot en evaluación temporal/CV | No; se ajustan en cada fold de entrenamiento o en `xtr`. |
| `entrenar.py:65-67, 70-94` | Folds CV, alpha Ridge y parámetros RF | No; bloques expansivos cronológicos dentro de entrenamiento. |
| `entrenar.py:105-107` | Máscara de casos completos y corte temporal | No ajusta parámetros; filtra filas y separa por fecha. |
| **`entrenar.py:110-112`** | **Climatología estación-mes** | **Sí: `z` contiene entrenamiento y prueba antes del groupby. Es fuga de prueba en esa línea base.** |
| `entrenar.py:117-128` | Modelos Ridge/RF temporales | No; `fit` recibe solo `xtr, ytr`. |
| `entrenar.py:138-145` | Ablaciones RF | No; se ajustan en `sel_train`, luego se evalúan en `sel_test`. |
| `entrenar.py:165-176, 190-194` | Permutación y dependencia parcial | Usan prueba para interpretación, pero no reajustan el estimador. |
| `entrenar.py:181-187` | Bootstrap de coeficientes | No; máscara de entrenamiento y remuestreo por semanas de train. |
| `entrenar.py:196-200` | Artefactos finales de app, preprocesador y categorías | **Sí: `all_exp/all_pred` abarcan fechas de entrenamiento y prueba; se ajustan con todos los datos disponibles.** Es el ajuste final de app, pero esos artefactos no deben evaluarse en esas mismas filas como prueba independiente. |
| `entrenar.py:198` | Cuantiles residuales del explicativo | Usa prueba para calibrar el intervalo, no para ajustar el estimador. |
| `entrenar_v2.py:37-39, 47-55` | Medias térmicas y climatología | No; train hasta 2025-10-23. La climatología usa fallback a media de estación para n<10 y global si no existe la estación. |
| `entrenar_v2.py:64-88` | Imputación, escalado, Ridge/HGB, selección y ajuste final | No; CV temporal y ajuste final solo dentro de entrenamiento. |
| `entrenar_v2.py:99-105` | Cuantiles q10/q90 del intervalo | Usa prueba para calibrar intervalo, no para ajustar el estimador. |
| `entrenar_v2.py:111-118` | Ablación Ridge | No; se ajusta solo con train. |
| `entrenar_v2.py:120-136` | Permutación y dependencia parcial | Usan prueba para análisis; no reajustan modelos. |
| `entrenar_v2.py:138-145` | Serialización y cobertura | El estimador guardado fue ajustado con train; los cuantiles adjuntos sí se calcularon con prueba. |

En ambos scripts los folds son expansivos por fecha: `entrenar.py:65-67` y `entrenar_v2.py:29-30`. Ningún rezago de una fila de entrenamiento incorpora fechas futuras de prueba. El hallazgo de filtración en la climatología simple no implica fuga en el ajuste temporal del RF; la discrepancia del RF del informe anterior viene del uso del artefacto final ajustado con todos los datos.

La auditoría completa está en [CSV de filtraciones](../data/processed/app/diagnostico_modelo_2_auditoria_filtraciones.csv); el script ejecutado es [diagnostico_modelo_2.py](../src/modelo/diagnostico_modelo_2.py).

### Decisiones que requieren criterio humano

1. Decidir cómo corregir o retirar las métricas del RF guardado reportadas antes como prueba independiente.
2. Decidir si se reemplaza la climatología simple por la regla v2 con fallback de menos de 10 observaciones.
3. Considerar el tamaño del artefacto explicativo, superior a 51 MB, al definir su entrega y uso.
4. Determinar si se deben investigar cambios de equipo/calibración junto con estacionalidad; estos datos descriptivos no determinan la causa.
5. Definir qué intervalo de prueba se usará para calibrar incertidumbre y cómo documentar que esa prueba ya se utilizó para calibración.
