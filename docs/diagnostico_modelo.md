# Diagnóstico y alternativa v2

Ejecuté ambos scripts y los tests. No modifiqué `docs/decisiones.md` ni los datos protegidos. El diagnóstico encontró una fuga de información en la climatología de `entrenar.py`; por eso los resultados publicados de esa línea base no son una evaluación válida fuera de muestra.

## Parte A: diagnóstico

**A1. Climatología.** El código existente forma `base = z.groupby(["estacion_id", "mes"]).pm25.mean()` después de construir `z` con filas de entrenamiento **y prueba**; luego usa esa media para predecir prueba. Por tanto, **no usa solo entrenamiento**. La réplica independiente de ese cálculo reproduce MAE 4.2971, RMSE 5.5221 y R² 0.5358. Al calcular la climatología estrictamente con entrenamiento hasta el **2025-10-23**, sobre las mismas 5,410 filas de prueba completas, resulta MAE **5.5092**, RMSE **6.9950** y R² **0.2552**. La mejora aparente publicada se explica por incluir observaciones de prueba en el promedio estación-mes.

**A2. Deriva y sesgos.** La media de PM2.5 cae entre entrenamiento y prueba en **las 19 estaciones**; Carvajal - Sevillana muestra el mayor descenso (32.51 → 23.10 µg/m³, diferencia −9.41). El promedio trimestral calendario es Q1 20.85, Q2 12.00, Q3 8.91 y Q4 15.70. En las filas comunes de prueba, el sesgo medio (predicción menos observado) fue **+3.652** para climatología y **+0.582** para RF explicativo; al restar el sesgo por estación, sus MAE bajan a **4.196** y **1.735**, respectivamente. La tabla por estación de medias y diferencias está en [medias por estación](../data/processed/app/diagnostico_modelo_medias_estacion_v2.csv); los sesgos por estación están en [sesgos por estación](../data/processed/app/diagnostico_modelo_sesgo_estacion_v2.csv). Los promedios trimestrales están en [trimestres](../data/processed/app/diagnostico_modelo_trimestre_v2.csv).

**A3. Imputación del RF explicativo.** En la prueba completa, **7.0% (407 de 5,817) de filas** tiene al menos un predictor faltante. El MAE es **1.932** en filas sin predictor faltante y **3.988** al predecir las filas con faltantes usando la imputación del pipeline. La evaluación original de `entrenar.py` excluye esas filas incompletas; estos dos MAE son un diagnóstico sobre subconjuntos distintos.

**A4. Carvajal - Sevillana.** Hay una caída de nivel en la media mensual: 32.81 µg/m³ antes de octubre de 2025 frente a 24.24 desde entonces. También bajan las comparables elegidas por correlación histórica: Puente Aranda 13.81 → 9.35, Las Ferias 15.31 → 12.34 y Guaymaral 14.33 → 10.08. La caída simultánea sugiere un componente compartido; Carvajal presenta además el nivel más alto. La serie mensual está en [Carvajal y comparables](../data/processed/app/diagnostico_modelo_carvajal_mensual_v2.csv).

**A5. Años parciales.** Hay **69 días** entre el 24 de octubre y el 31 de diciembre de 2023, y **296 días** entre el 1 de enero y el 23 de octubre de 2026. Medias de PM2.5: noviembre 2023/2024/2025 = **15.14 / 16.00 / 14.13**; diciembre = **18.94 / 18.35 / 16.94**. La comparación 17.25 frente a 10.91 cubre periodos distintos y no debe presentarse como tendencia.

**A6. Simulador.** Variando una entrada a la vez, las predicciones muestran: precipitación 0 → 20 mm, **7.37 → 7.30**; tmax_c 10 → 30 °C, **7.12 → 6.92**; día de semana, mínimo **7.03** y máximo **8.01**; vel_ciudad_ms 0.5 → 2.0, **16.13 → 3.56**. Así, el viento por sí solo puede producir una diferencia de **12.57 µg/m³** en ese contraste, mientras lluvia, temperatura máxima y calendario producen cambios menores en esta prueba controlada. El modelo utiliza `tmax_anom`, no `tmax_c` directamente. No encontré las entradas originales de los tres escenarios mencionados; dejé tres escenarios reproducibles con centro_de_alto_rendimiento, mes y referencias fijas, y sus entradas completas y predicciones en [tabla del simulador](../data/processed/app/diagnostico_modelo_simulador_v2.csv). En esos escenarios controlados, fin de semana seco predice 7.44 y laborable lluvioso 7.23: la diferencia no se explica por lluvia o calendario; las entradas originales serían necesarias para atribuir exactamente la diferencia previa.

## Parte B: modelo por anomalías

La anomalía es PM2.5 menos la media estación-mes calculada solo con entrenamiento. Si ese par tiene menos de 10 observaciones, se usa la media de entrenamiento de la estación; si tampoco existe la estación en entrenamiento, se usa la media global. Ridge y RF imputan dentro del pipeline; HGB admite NaN sin imputación. La selección de Ridge y HGB usa CV temporal interna de entrenamiento; el RF conserva los hiperparámetros ligeros solicitados. En v2, la climatología y los modelos se evalúan sobre las mismas filas completas que el RF explicativo.

| Modelo | MAE | RMSE | R² | Mejora MAE frente a clim |
|---|---:|---:|---:|---:|
| Climatología | 5.490 | 6.968 | 0.261 | — |
| + Ridge | 5.393 | 6.923 | 0.270 | 0.097 |
| + RF | 5.386 | 6.955 | 0.264 | 0.105 |
| + HGB | 5.221 | 6.777 | 0.301 | 0.269 |

Ridge ganó por poco en CV temporal (MAE de anomalía 4.547 frente a 4.554 de HGB), así que se guardó Ridge sin seleccionar por el resultado de prueba. Aunque HGB obtuvo mejor MAE de prueba, eso no se usó para elegir el artefacto. Los resultados por estación, ablación y permutación agrupada están en [MAE por estación](../data/processed/app/diagnostico_modelo_mae_estacion_v2.csv), [ablación](../data/processed/app/diagnostico_modelo_ablacion_v2.csv) e [importancia por permutación](../data/processed/app/diagnostico_modelo_permutacion_grupos_v2.csv). La dependencia parcial solicitada está en [CSV de dependencia parcial](../data/processed/app/diagnostico_modelo_dependencia_parcial_v2.csv).

## Parte C: intervalo

Para el Ridge seleccionado, los cuantiles de la razón observado/predicción en filas con predicción mayor que 1 son **q10 = 0.3812** y **q90 = 1.2776**. El intervalo multiplica la predicción por esos cuantiles y aplica un piso de cero. Cobertura empírica global: **79.56%**. Por estación va de **63.98%** (Puente Aranda) a **88.28%** (Fontibón); el desglose está en [cobertura por estación](../data/processed/app/diagnostico_modelo_cobertura_estacion_v2.csv).

El artefacto comprimido mide **5,183 bytes**, muy por debajo de 25 MB. La recarga después de comprimir no cambió las predicciones ni el MAE; la diferencia máxima de predicción fue cero. Las predicciones e intervalos están en [predicciones v2](../data/processed/app/predicciones_prueba_v2.parquet); el modelo, en [modelo_anomalia_v2.joblib](../models/modelo_anomalia_v2.joblib).

## Decisiones que requieren criterio humano

1. Decidir si se corrigen los resultados previos de climatología, dada la fuga detectada.
2. Decidir si una mejora de MAE de 0.097 µg/m³ de Ridge frente a la climatología justifica más complejidad.
3. Ponderar el mejor resultado de prueba de HGB frente a la selección de Ridge por CV temporal.
4. Investigar si la caída de Carvajal y la caída compartida reflejan un cambio real o condiciones de medición y cobertura.
5. Decidir si el simulador debe limitar velocidades y destacar su sensibilidad, mientras se recuperan las entradas completas de los escenarios previos.

Los archivos creados son [diagnostico_modelo.py](../src/modelo/diagnostico_modelo.py), [entrenar_v2.py](../src/modelo/entrenar_v2.py) y [test_modelo_v2.py](../tests/test_modelo_v2.py). Ejecuté ambos scripts y `python -m pytest tests/test_modelo_v2.py -q`: **3 tests pasaron**.
