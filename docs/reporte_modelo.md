## Archivos y ejecución

Creé [explorar.py](/D:/ciencia%20de%20datos/proyecto-aire-bogota/src/modelo/explorar.py), [entrenar.py](/D:/ciencia%20de%20datos/proyecto-aire-bogota/src/modelo/entrenar.py), [simular.py](/D:/ciencia%20de%20datos/proyecto-aire-bogota/src/modelo/simular.py) y [test_modelo.py](/D:/ciencia%20de%20datos/proyecto-aire-bogota/tests/test_modelo.py). Cambié en `AGENTS.md` la línea de estaciones móviles; no modifiqué `docs/decisiones.md`, `data/raw`, `data/interim` ni `aire_bogota_diario.parquet`.

Corrí ambos scripts y las pruebas: `pytest tests/test_modelo.py -q` terminó con **3 passed**. Los artefactos quedaron en [data/processed/app](/D:/ciencia%20de%20datos/proyecto-aire-bogota/data/processed/app) y `models/`.

## Parte 0: verificaciones

- **Desfases IDEAM:** tmax Nueva Generación–San Cayetano, máximo en **0 días (r=0,216)**; tmin, en **+1 día (r=−0,089)**. El desfase apenas cambia la correlación baja observada. Precipitación: Jardín Botánico–Nueva Generación, **0 días (r=0,374)**; Jardín Botánico–San Cayetano, **0 días (r=0,219)**.
- **Temporada:** precipitación promedio diaria por mes, mm/día: ene **1,63**; feb **3,31**; mar **2,86**; abr **4,27**; may **3,51**; jun **3,15**; jul **2,05**; ago **1,38**; sep **1,57**; oct **4,33**; nov **3,88**; dic **1,27**. Las etiquetas actuales distinguen meses lluviosos más húmedos en promedio (**3,37 mm/día**) que los secos (**1,93**), pero febrero está entre los meses más lluviosos pese a estar etiquetado seca.
- **PM2.5–PM10:** correlación **0,853**; mediana de la razón PM2.5/PM10 **0,455**; **15.745** pares.
- Se generó `cobertura_estacion_mes.csv` con `estacion_id`, `año_mes` y porcentaje de días con PM2.5. Los umbrales 24 h se omitieron; ambos siguen como `None` con TODO para cifra y fuente oficial.

## Métricas de prueba

La partición temporal fue entrenamiento **2023-10-24 a 2025-10-23** y prueba **2025-10-24 a 2026-10-23**. Las filas son casos completos comunes a los modelos de cada versión. La columna de mejora compara MAE con la línea base: positivo indica mejora.

| Versión | Modelo | Filas | MAE | RMSE | R² | Mejora MAE vs. base |
|---|---|---:|---:|---:|---:|---:|
| Explicativo | Línea base climatología | 5.410 | 4,297 | 5,522 | 0,536 | 0,0% |
| Explicativo | Ridge | 5.410 | 6,213 | 7,576 | 0,126 | −44,6% |
| Explicativo | Ridge log | 5.410 | 6,195 | 7,857 | 0,060 | −44,2% |
| Explicativo | Random Forest | 5.410 | 5,235 | 6,915 | 0,272 | −21,8% |
| Predictivo | Línea base persistencia | 5.170 | 3,442 | 4,852 | 0,641 | 0,0% |
| Predictivo | Ridge | 5.170 | 3,332 | 4,387 | 0,707 | 3,2% |
| Predictivo | Ridge log | 5.170 | 3,511 | 5,297 | 0,573 | −2,0% |
| Predictivo | Random Forest | 5.170 | 3,223 | 4,329 | 0,715 | 6,3% |

El predictivo Random Forest obtuvo el mejor MAE de su versión. En la versión explicativa, la climatología superó a los modelos aprendidos; por eso el desempeño del simulador debe leerse junto con esa comparación. Los Ridge y Random Forest usan imputación mediana dentro del pipeline, ajustada con entrenamiento. La CV temporal expansiva seleccionó Ridge α=0,1 para explicativo y α=100 para predictivo; para ambos bosques eligió 250 árboles, hoja mínima 5 y `max_features=0.8`.

## MAE por estación

| Estación | Explicativo RF | Predictivo RF |
|---|---:|---:|
| Bolivia | 5,37 | 3,29 |
| Carvajal Sevillana | 11,80 | 4,56 |
| Centro de Alto Rendimiento | 4,51 | 3,06 |
| Ciudad Bolívar | 6,02 | 4,02 |
| Colina | 4,56 | 2,40 |
| Fontibón | 5,20 | 3,69 |
| Guaymaral | 5,20 | 2,91 |
| Jazmín | 4,61 | 3,51 |
| Kennedy | 4,58 | 3,52 |
| Las Ferias | 4,00 | 2,94 |
| MinAmbiente | 4,55 | 2,79 |
| Móvil 7ma | 3,23 | 2,66 |
| Móvil Fontibón | 6,66 | 3,59 |
| Puente Aranda | 4,86 | 3,17 |
| San Cristóbal | 3,69 | 2,91 |
| Suba | 4,62 | 3,03 |
| Tunal | 4,91 | 3,28 |
| Usaquén | 6,31 | 2,80 |
| Usme | 4,64 | 2,91 |

El sesgo por estación, mes y temporada quedó en `metricas_desglosadas.csv`. Se calcula como predicción menos valor observado.

## Interpretación y hallazgos

La importancia por permutación del Random Forest explicativo, agrupada, fue: calendario **1,816**; ubicación **1,236**; viento **0,700**; lluvia **0,089**; temperatura **0,079**. Los coeficientes estandarizados Ridge y sus intervalos bootstrap 10–90% están en `coeficientes_ridge.csv`; entre los mayores: estación Carvajal Sevillana **14,11 [13,48; 14,71]**, Bolivia **−5,20 [−5,67; −4,57]**, velocidad de viento **−3,67 [−4,25; −3,02]**, tmax_anom **1,95 [1,39; 2,39]**.

Cinco hallazgos descriptivos calculados:

1. PM2.5 medio fue **23,24 µg/m³ en Kennedy** y **17,86 µg/m³ en Fontibón**, las dos localidades con mayor promedio.
2. El promedio fue **14,93 µg/m³ en días laborales** y **12,97 µg/m³ en fin de semana**; Carvajal Sevillana tuvo la diferencia laboral–fin de semana más alta: **5,75 µg/m³**.
3. En los días con precipitación del día anterior ≥1 mm, PM2.5 medio fue **13,84 µg/m³**, frente a **14,79** cuando no se cumplió esa condición.
4. El promedio descendió de **17,57 µg/m³** en el cuartil más bajo de velocidad de ciudad a **9,90** en el más alto. La correlación Spearman global entre velocidad y PM2.5 fue **−0,383**.
5. La correlación Spearman PM2.5–PM10 fue **0,873**. El promedio anual de PM2.5 bajó de **17,25 µg/m³ en 2023** a **10,91 en 2026**; es una descripción del periodo, no una atribución causal.

La ablación explicativa dio MAE **5,116** sin temperatura, **5,472** sin viento, **5,336** sin lluvia y **6,053** sin calendario, frente a **5,235** con todas las variables. Sin estaciones móviles, MAE fue **5,246** en **4.878** filas; el modelo completo usó 5.410. Las tablas de dependencia parcial están en `dependencia_parcial.csv`.

El simulador devolvió predicción e intervalo 10–90% para tres escenarios, usando `centro_de_alto_rendimiento`:

- Fin de semana seco: **7,29 µg/m³**, intervalo **[−3,57; 10,19]**.
- Laborable lluvioso: **20,53**, intervalo **[9,68; 23,43]**.
- Laborable sin viento: **14,37**, intervalo **[3,51; 17,27]**.

El intervalo residual es aditivo y puede tener límite inferior negativo; las entradas no permiten especificar precipitación acumulada a tres días ni el conteo de estaciones lluviosas, que el pipeline completa con medianas de entrenamiento.

Los modelos están en [modelo_explicativo.joblib](/D:/ciencia%20de%20datos/proyecto-aire-bogota/models/modelo_explicativo.joblib) (**51.842.433 bytes**) y [modelo_predictivo.joblib](/D:/ciencia%20de%20datos/proyecto-aire-bogota/models/modelo_predictivo.joblib) (**5.373 bytes**). Las predicciones de prueba quedaron en `predicciones_prueba.parquet`.

## Decisiones que requieren revisión humana

1. Completar y citar fuentes oficiales para los umbrales de 24 horas antes de calcular porcentajes.
2. Revisar la clasificación seca/lluviosa: febrero figura seca, pero promedió **3,31 mm/día**.
3. Decidir si el simulador debe pedir precipitación acumulada y lluvia de ciudad para reemplazar sus medianas asumidas.
4. Elegir el balance entre respuesta a escenarios y precisión: la climatología superó al RF en el explicativo.
5. Evaluar tratamiento de sesgos altos por estación, en especial el MAE explicativo de Carvajal Sevillana (**11,80**) y el de Móvil Fontibón (**6,66**).

## Decisiones nuevas para añadir a `docs/decisiones.md`

No añadí estas entradas al archivo, según tu instrucción. Propongo registrar:

- La partición temporal y el criterio de filas completas comunes por versión para comparar modelos.
- El cálculo de rezagos sobre la malla completa antes de filtrar casos completos.
- El uso de medianas de entrenamiento para variables del simulador que no solicita la interfaz.
- La discrepancia observada entre la etiqueta de temporada y la precipitación mensual; los umbrales 24 h siguen pendientes de fuente oficial.
