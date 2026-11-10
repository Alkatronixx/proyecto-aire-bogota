## 2026-11-05: La humedad queda fuera del modelo
- **Decisión:** la humedad relativa se usa solo en el análisis exploratorio.
- **Motivo:** no hay datos de 2025 y rellenarlos sería inventar valores.
- **Alternativas descartadas:** entrenar solo con 2024 y 2026 (pierde datos); imputar 2025 (inventa datos).
## 2026-11-05: Corrección del archivo duplicado de feb-mar 2024
- *Decisión:* se reemplazó el archivo original por una nueva descarga (fecha).
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