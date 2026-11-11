## 2026-11-05: La humedad queda fuera del modelo
- **Decisión:** la humedad relativa se usa solo en el análisis exploratorio.
- **Motivo:** no hay datos de 2025 y rellenarlos sería inventar valores.
- **Alternativas descartadas:** entrenar solo con 2024 y 2026 (pierde datos); imputar 2025 (inventa datos).
## 2026-11-05: Corrección del archivo duplicado de feb-mar 2024
- *Decisión:* se reemplazó el archivo original por una nueva descarga (2026-11-05).
- *Motivo:* el archivo contenía datos correspondientes a enero de 2024. El problema se detectó mediante el diagnóstico de cobertura.
- *Aclaración:* este incidente se documenta como evidencia del control de calidad de los datos.

## 2026-11-05: Validación de integridad añadida al pipeline
- *Decisión:* se incorporaron controles automáticos de continuidad de fechas y detección de archivos repetidos.
- *Motivo:* prevenir inconsistencias temporales y duplicaciones durante la integración de los archivos.

## 2026-11-05: Casos de PM2.5 mayor que PM10
- *Decisión:* los 3 casos identificados entre 15.232 pares se mantienen sin modificar.
- *Motivo:* podrían corresponder a ruido instrumental, pero no hay evidencia suficiente para justificar su corrección o eliminación.

## 2026-11-05: Definición del periodo final
- *Decisión:* se establece como periodo definitivo del análisis el comprendido entre 2023-10-24 y 2026-10-23.
- *Motivo:* el día 24 de cada mes aparece en el archivo siguiente y el último registro (24-oct-2026) todavía estaba sin cerrar al momento de la descarga.

## 2026-11-05: Exclusión de la última fila de cada archivo
- *Decisión:* se descarta la última fila de cada archivo.
- *Motivo:* corresponde al día 24 del mes y contiene un registro vacío, todavía sin cerrar.

## 2026-11-05: Hueco de datos entre agosto y octubre de 2025
- **Decisión:** se mantiene como NaN el periodo comprendido entre el 2025-08-04 y el 2025-10-16.
- **Motivo:** el hueco es real en la fuente original, confirmado mediante una nueva descarga y por la presencia de datos de viento para esas mismas fechas.
- **Aclaración:** la causa de la ausencia de datos es desconocida y no se realizan imputaciones.

## 2026-11-05: Criterio de cobertura para la selección de estaciones
- **Decisión:** el cálculo de cobertura se realiza excluyendo el hueco de datos comprendido entre el 2025-08-04 y el 2025-10-16.
- **Motivo:** evitar que una ausencia confirmada en la fuente distorsione el porcentaje de cobertura y condicione incorrectamente la selección de estaciones.

## 2026-11-05: Limitación de la dirección del viento
- **Decisión:** se conserva la dirección del viento tal como aparece en la fuente, considerando su posible limitación metodológica.
- **Motivo:** es posible que la fuente calcule los promedios de dirección mediante una media aritmética convencional, en lugar de utilizar un promedio circular.
- **Aclaración:** esto puede generar valores representativos incorrectos cuando las direcciones se encuentran próximas a 0° y 360°.

## 2026-11-08: Exclusión de estaciones del índice de viento de ciudad [REEMPLAZADA el 2026-11-08, ver DV-12]
- **Decisión:** se excluyen Kennedy y San Cristóbal del índice de viento de ciudad.
- **Motivo:** su correlación reportada con la mediana de las otras estaciones es -0.11 y 0.11, frente a 0.32–0.76 para las demás; el supuesto se deja como constante `EXCLUIDAS_INDICE` y se puede revisar con el reporte del nuevo proceso.
- **Alternativas descartadas:** incluir las 17 estaciones sin ponderación por estación.

## 2026-11-08: Controles de calidad de viento para el índice
- **Decisión:** velocidades negativas invalidan la velocidad y su dirección del mismo día; direcciones constantes durante cuatro o más días se invalidan; las rachas de velocidad repetida solo se contabilizan conceptualmente y no se alteran.
- **Motivo:** aplicar los criterios de control definidos para esta tarea sin imputar mediciones.
- **Alternativas descartadas:** corregir valores por estimación o invalidar rachas de velocidad con baja varianza.
## 2026-11-05: Evidencia de operación durante el hueco de PM de 2025
- *Decisión:* se incorpora la nueva evidencia de la columna `Num` de viento, que muestra que las estaciones operaban durante agosto y septiembre de 2025.
- *Motivo:* esta información permite reconsiderar el hueco de datos de PM identificado para ese periodo y aporta evidencia adicional sobre la disponibilidad de las estaciones.

## 2026-11-05: Normalización de rótulos 10M de Guaymaral
- *Decisión:* se normalizan los rótulos 10M de Guaymaral utilizando el prefijo correspondiente.
- *Motivo:* unificar la identificación de los registros. Se deja documentada la duda sobre la altura real del sensor para evitar asumir que la etiqueta confirma su ubicación física.

## 2026-11-05: Dirección del viento promediada desde la fuente
- *Decisión:* se conserva la dirección del viento tal como viene promediada desde la fuente.
- *Motivo:* la información disponible ya contiene valores promediados, por lo que no es posible reconstruir la dirección original. Esta limitación queda documentada para tenerla en cuenta durante el análisis.

## 2026-11-05: Datos de viento faltantes en estaciones móviles de Fontibón y Usme
- *Decisión:* queda pendiente definir el criterio para asignar datos de viento a las estaciones móviles de Fontibón y Usme, que no cuentan con mediciones propias. Se propone utilizar los datos de la estación más cercana que tenga información disponible.
- *Motivo:* evitar dejar sin información de viento a las estaciones móviles y establecer un criterio espacial consistente. La propuesta requiere validación antes de su implementación.

2026-11-09: Validación de métricas predictivas, comportamiento del PM2.5 y escenarios del simulador
- Decisión: retirar las métricas del Random Forest guardado (MAE 1,93 y R² 0,88), ya que corresponden a resultados dentro de muestra. Se establecen como métricas válidas del Random Forest MAE 5,24 y R² 0,27. Se confirma que el modelo predictivo guardado es un Ridge, con MAE 3,332 y R² 0,707, frente a un modelo de persistencia con MAE 3,442. También se acuerda describir la caída del nivel de PM2.5 sin atribuirle una causa específica y expresar los escenarios del simulador como cambios frente a una referencia.

- Motivo: garantizar la transparencia y consistencia en la presentación de los resultados, utilizando métricas válidas para evaluar el desempeño predictivo. Evitar atribuir la caída del PM2.5 a una causa no comprobada, dado que podría deberse a un cambio real en las concentraciones, a modificaciones en los equipos o a ajustes de calibración. Expresar los escenarios del simulador respecto a una referencia permite facilitar su interpretación y comparación

## 2026-11-10: Modelo explicativo por anomalía con Ridge (α=100)
- *Decisión:* el modelo que usa el Simulador predice la anomalía (pm25 menos la climatología de estación y mes) y la predicción final es climatología más anomalía predicha. Algoritmo: Ridge con α=100, imputación por mediana y estandarización dentro del pipeline, 12 variables de viento, lluvia, temperatura y calendario.
- *Motivo:* es interpretable, estable y no sobreajusta; el simulador necesita un modelo cuyas respuestas a los escenarios sean coherentes.
- *Detalle técnico:* la climatología se calcula solo con el periodo de entrenamiento (2023-10-24 a 2025-10-23); si un par estación-mes tiene menos de 10 observaciones se usa la media de la estación, y si falta la estación, la media global. Hay 228 pares.
- *Alternativas descartadas:* modelar el PM2.5 directo; Random Forest e HistGradientBoosting (ver siguiente entrada).
- *Registro:* decisión tomada antes; documentada retroactivamente el 2026-11-11.

## 2026-11-10: Selección del modelo por validación cruzada temporal, no por la prueba
- *Decisión:* el modelo se elige con validación cruzada temporal expansiva dentro del entrenamiento (Ridge 4,547 frente a HistGradientBoosting 4,554). HistGradientBoosting obtuvo mejor error en la prueba (MAE 5,221) pero no se publica.
- *Motivo:* elegir mirando el conjunto de prueba lo contaminaría como evaluación honesta.
- *Aclaración:* en la prueba, Random Forest tiene MAE 5,24 y R² 0,27; esas son sus métricas válidas (ver entrada del 2026-11-09).
- *Registro:* decisión tomada antes; documentada retroactivamente el 2026-11-11.

## 2026-11-10: Corrección de la fuga en la climatología
- *Decisión:* la climatología de referencia se recalculó solo con el entrenamiento, porque una versión anterior usaba filas de prueba.
- *Motivo:* esa versión inflaba el desempeño. Las métricas dentro de muestra del Random Forest (MAE 1,93; R² 0,88) ya se retiraron el 2026-11-09.
- *Aclaración:* la mejora del modelo sobre la climatología es pequeña (cercana al 2 % en MAE). Se comunica así, sin presentarla como una gran ganancia.
- *Registro:* documentado retroactivamente el 2026-11-11.

## 2026-11-10: Modelo predictivo con el PM2.5 de los días previos
- *Decisión:* existe un segundo Ridge que además usa pm25_ayer y el promedio de los 3 días previos. Sus métricas son MAE 3,332, RMSE 4,387 y R² 0,707, frente a persistencia con MAE 3,442. Solo se muestra en la página Modelo; no alimenta el Simulador.
- *Motivo:* mostrar cuánto ayuda conocer el nivel reciente frente a usar solo clima y calendario.

## 2026-11-10: Intervalo de incertidumbre multiplicativo calibrado con el año de prueba
- *Decisión:* el simulador muestra un intervalo con factores q10=0,3812 y q90=1,2776 sobre la predicción. La cobertura es 79,56 % en total, entre 63,98 % (Puente Aranda) y 88,28 % (Fontibón).
- *Motivo:* dar al usuario una idea de la incertidumbre.
- *Limitación:* los factores se calibraron con el mismo año que se usa para evaluar, así que la cobertura es optimista y debe presentarse como aproximada.

## 2026-11-10: Control de alineación temporal del día de medición
- *Decisión:* se mantiene la alineación de misma fecha (k=0) entre PM2.5 y variables meteorológicas.
- *Motivo:* no hay un desfase uniforme de un día; desplazar a k=+1 mejora el MAE solo 0,044 (5,441 a 5,397 sobre 5.258 filas). Las fuentes definen el día de formas distintas y se documenta como limitación (día meteorológico del IDEAM de 7 am del día anterior a 7 am).
- *Alternativas descartadas:* desplazar todas las variables un día.

## 2026-11-10: Índice de viento de ciudad en lugar de viento por estación
- *Decisión:* se usa un índice de viento de ciudad: mediana de las velocidades normalizadas por estación, con al menos 3 estaciones por día. Se calcula con 15 estaciones; Kennedy y San Cristóbal quedan excluidas por correlación baja con el resto. (Verificar la lista contra EXCLUIDAS_INDICE en src/datos/viento_ciudad.py.) La dirección del viento queda fuera del modelo base.
- *Motivo:* hay estaciones sin viento propio y la dirección viene promediada de forma aritmética desde la fuente.
- *Reemplaza:* la propuesta de asignar a Fontibón y Usme el viento de la estación más cercana (entrada del 2026-11-05 sobre estaciones móviles), que se retira.

## 2026-11-10: Valores centinela y rachas inválidas
- *Decisión:* los valores centinela (-9999) pasan a NaN con una bandera. Una dirección de 81° solo se anula dentro de fallas de instrumento (20 casos); los 35 casos aislados se mantienen.
- *Motivo:* no inventar ni perder datos válidos por una hipótesis demasiado amplia.

## 2026-11-10: Lluvia diaria y humedad
- *Decisión:* la lluvia diaria se mantiene como variable pero no se presenta como aportante robusto; la humedad sigue solo exploratoria (ver 2026-11-05).
- *Motivo:* en las pruebas la lluvia diaria no añade valor robusto; el viento es la asociación más visible.

## 2026-11-10: Fuentes oficiales verificadas el 2026-11-10
- *Decisión:* los umbrales y datos de contexto citados en la app se verificaron contra fuentes oficiales el 2026-11-10: OMS 2021 (PM2.5: 5 anual y 15 en 24 h; PM10: 15 y 45), Resolución 2254 de 2017 (PM2.5: 25 anual y 37 en 24 h; PM10: 50 y 75; metas 2030), Secretaría Distrital de Ambiente (19 estaciones y 70 microsensores), DANE (7.937.898 habitantes, 2025) y día meteorológico del IDEAM.
- *Aclaración:* la norma colombiana se evalúa por estación; las medias diarias de este proyecto son una referencia comparativa.

## 2026-11-10: Tabla ICA y cifras de salud
- *Decisión:* la tabla de categorías ICA de 24 h es de referencia, tomada del IDEAM citando la Resolución 2254 (Tabla 6). El PDF del IDEAM trae una errata en PM2.5 "Dañina a la salud" (16-150); se usa 56-150, coherente con el nivel de alerta de la Tabla 4 de la misma resolución. Falta confirmar la fila de PM2.5 en la Tabla 6 original del Diario Oficial. El modelo usa escala continua, no categorías ICA.
- *Salud:* se citan la metodología y los riesgos relativos de la Secretaría Distrital de Salud (AirQ+ de la OMS; causas naturales 1,08; cardiovasculares 1,11; respiratorias 1,10). La cifra de 13.345 muertes (prensa, 2018-2022) no se usa como dato oficial hasta verificarla en SaluData.

## 2026-11-10: Altitud de San Cayetano y Nueva Generación
- *Decisión:* la diferencia es de 510 m (3.100 m frente a 2.590 m), calculada desde los datos; reemplaza el valor de 550 m que figuraba antes en la app.

## 2026-11-10: Estaciones: Bosa y Centro de Alto Rendimiento
- *Decisión:* se trabaja con 19 estaciones. La Secretaría Distrital de Ambiente lista 20 en su página (incluye Bosa), pero no hay datos de Bosa en los archivos recibidos. Para Centro de Alto Rendimiento la ficha de la SDA indica Engativá y el cruce espacial Barrios Unidos; se muestran ambas fuentes con rótulos claros.

## 2026-11-11: Simulador y despliegue
- *Decisión:* el escenario B del Simulador estaba dentro de un expander cerrado y no se veía; se dejó abierto y hay una prueba automática que verifica que A y B se muestran y difieren con entradas distintas. La app se despliega en Streamlit Community Cloud. No se implementa el rediseño con shadcn (rama ui-shadcn descartada) por falta de tiempo. Congelamiento del código: miércoles 2026-11-11, 18:00.