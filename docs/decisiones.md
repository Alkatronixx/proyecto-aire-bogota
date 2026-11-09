# Decisiones vigentes (consolidado al 2026-11-08)

| ID | Tema | Decisión vigente | Motivo corto | Fecha original |
|---|---|---|---|---|
| DV-01 | Periodo | Periodo: 2023-10-24 a 2026-10-23 (1,096 días). Motivo: el día 24 de cada mes está en el archivo siguiente y el 24-oct-2026 no estaba cerrado al descargar. | Periodo completo y cerrado. | 2026-11-05 |
| DV-02 | Lectura RMCAB | Lectura de archivos RMCAB: "24:00" se interpreta como cierre del mismo día; '----' es NaN; la última fila de cada archivo es el día 24 sin cerrar, vacía, y se descarta; el nombre del archivo solo se usa para validar, nunca para deducir fechas. | Evitar fechas y datos inferidos desde nombres. | 2026-11-08 |
| DV-03 | Duplicados | Duplicados: se conserva la fila con valor frente a la fila NaN de la misma fecha; los duplicados idénticos se eliminan; no hay conflictos numéricos reales. | Resolver duplicados sin corregir valores. | 2026-11-08 |
| DV-04 | Archivo feb-mar 2024 | Archivo feb-mar 2024 de aire: traía datos de enero; se detectó con el diagnóstico de cobertura, se volvió a descargar y se añadió validación de integridad (continuidad de fechas y archivos repetidos). | Controlar continuidad y repetición de archivos. | 2026-11-05 |
| DV-05 | Hueco PM y cobertura | Hueco de PM (2025-08-04 a 2025-10-16): es real en la fuente (se volvió a descargar y sigue vacío; los archivos de viento sí tienen datos esas fechas); causa desconocida; se mantiene NaN, nunca se imputa. La cobertura de cada estación se calcula también excluyendo ese hueco. | Mantener faltantes reales sin imputación. | 2026-11-05 |
| DV-06 | PM2.5 mayor que PM10 | PM2.5 mayor que PM10: 3 casos de 15,232 pares; se conservan, posible ruido instrumental. | Sin evidencia para corregirlos. | 2026-11-05 |
| DV-07 | Centinelas y negativos | Valores centinela y negativos: los negativos de aire (4: Jazmin 2024-04-09 y Movil Fontibon 2025-11-04, PM2.5 y PM10, cercanos a -3800) y de viento (14: diez -9999 en Las Ferias, uno -9999 en MinAmbiente, -3911.1, -452.8 y -525.4) son datos inválidos. Se conservan intactos en aire_largo y viento_largo; en viento pasan a NaN con bandera en viento_limpio.parquet; en aire pasan a NaN con bandera al construir la tabla maestra. Nunca se corrigen ni se reemplazan por otro valor. | Preservar fuente y marcar inválidos en productos limpios. | 2026-11-08 |
| DV-08 | Dirección ligada a velocidad | Dirección ligada a la velocidad: si la velocidad de una estación y día es inválida, la dirección de ese día y estación también pasa a NaN. | Evitar dirección asociada a una medición inválida. | 2026-11-08 |
| DV-09 | Direcciones 0 y 360 | Direcciones 0 y 360: no hay calma codificada (ningún día tiene velocidad exactamente 0); no se corrigen; con seno y coseno son equivalentes. | Mantener equivalencia angular. | 2026-11-08 |
| DV-10 | Rachas | Rachas: una dirección idéntica durante 4 o más días consecutivos (un NaN corta la racha) pasa a NaN con bandera. Las rachas de velocidad repetida (49 rachas, 211 filas) no se tocan: son consecuencia de la resolución de 0.1 m/s. | Limpiar repeticiones direccionales; conservar velocidad. | 2026-11-08 |
| DV-11 | Dirección 81 grados | Dirección 81 grados: solo se anula cuando cae dentro de una falla (20 casos). Los 35 casos aislados se conservan: su frecuencia es comparable a la de 80 (29) y 82 (32). | No tratar el valor aislado como centinela. | 2026-11-08 |
| DV-12 | Índice de viento de ciudad | Índice de viento de ciudad: mediana diaria de las velocidades normalizadas (velocidad dividida por la media de cada estación) de 15 estaciones, con mínimo de 3 estaciones por día (el mínimo real es 5). Excluye Kennedy (correlación -0.08 con el índice) y San Cristobal (0.25); el umbral de exclusión es criterio del equipo. Se adopta la versión normalizada; correlaciona 0.905 con la mediana simple. | Normalizar por nivel medio y excluir dos estaciones según criterio del equipo. | 2026-11-08 |
| DV-13 | Viento para estaciones móviles | Móvil Fontibón y Usme: sin viento propio. Se descarta prestarles el viento de la estación vecina por representatividad débil (por ejemplo, Tunal con sus vecinas a 3-4 km tiene r de 0.47 a 0.68 y Kennedy con Fontibón 0.17). Usan el índice de ciudad. | Evitar asignaciones locales débiles. | 2026-11-08 |
| DV-14 | Dirección en modelo base | La dirección del viento queda fuera del modelo base: la fuente la entrega como promedio de 24 horas (no se sabe si aritmético), no es coherente entre estaciones cercanas, y solo entra como extra si hay tiempo. | Calidad y coherencia espacial limitadas. | 2026-11-08 |
| DV-15 | Sensor de Guaymaral | Guaymaral: su sensor se rotula "10M" en los 36 archivos; la comparabilidad con las demás estaciones no está verificada. | Limitación de comparabilidad sin resolver. | 2026-11-08 |
| DV-16 | Humedad relativa | Humedad relativa: fuera del modelo (no hay datos en 2025); solo exploración. | Evitar imputar el periodo sin medición. | 2026-11-05 |
| DV-17 | Recorte de alcance | Recorte de alcance del 2026-11-08 por tiempo (entrega 2026-11-13): tráfico (aforos), clustering y LightGBM quedan fuera. Los semáforos ya estaban descartados desde antes. | Priorizar entregables dentro del tiempo disponible. | 2026-11-08 |
| DV-18 | Modelo | Modelo: validación temporal; Ridge y Random Forest contra una línea base ingenua; modelo explicativo (sin PM2.5 de días anteriores) como prioridad porque alimenta el simulador. | Priorizar utilidad explicativa y evaluación temporal. | 2026-11-08 |

## Hipótesis y limitaciones abiertas

- Las coincidencias de fecha entre negativos de aire y viento (2024-04-09 en Jazmin, ambos; 2025-11-04 en Movil Fontibon en aire y MinAmbiente en viento) sugieren fallas de registro compartidas; NO confirmado.
- HIPÓTESIS (no comprobable): los valores de viento como -3911 son promedios diarios contaminados por horas en -9999.
- La mediana de ciudad describe el viento de la ciudad, no el local; 4 estaciones tienen más de 59% de días sin viento propio.
- La ventana 2025-08-04 a 2025-10-16 deja agosto y septiembre con un solo año de entrenamiento (2024).
- Sin datos de humedad en 2025.

## Clasificación de entradas existentes

- Vigentes: humedad; corrección de archivo feb-mar 2024; validación de integridad; PM2.5 mayor que PM10; periodo; descarte de última fila; hueco de PM; criterio de cobertura; limitación de dirección; controles de calidad de viento.
- Reemplazada: exclusión del índice de viento de ciudad con correlaciones anteriores; los coeficientes -0.11 y 0.11 discrepan de los valores vigentes -0.08 y 0.25.
- Duplicadas: ninguna entrada completa duplicada. Las reglas de dirección ligada a velocidad y rachas en controles de calidad se mantienen porque la nueva consolidación las precisa y amplía.
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

## 2026-11-08: Lectura y fechas de archivos RMCAB
- **Decisión:** "24:00" se interpreta como cierre del mismo día; '----' se convierte en NaN; se descarta la última fila vacía del día 24 y el nombre del archivo se usa para validar, nunca para deducir fechas.
- **Motivo:** evitar inferencias de fecha y conservar como faltantes los marcadores no numéricos y registros aún sin cerrar.
- **Alternativas descartadas:** asignar fechas a partir del nombre del archivo o convertir '----' en un valor.

## 2026-11-08: Resolución de duplicados
- **Decisión:** ante una misma fecha se conserva la fila con valor frente a una fila NaN; los duplicados idénticos se eliminan y no se detectaron conflictos numéricos reales.
- **Motivo:** resolver duplicaciones sin alterar mediciones.
- **Alternativas descartadas:** conservar duplicados idénticos o elegir arbitrariamente entre dos valores distintos.

## 2026-11-08: Valores centinela y negativos
- **Decisión:** conservar los valores originales en aire_largo y viento_largo, reportarlos y convertir los inválidos a NaN con bandera en los productos limpios correspondientes; no corregirlos ni reemplazarlos.
- **Motivo:** distinguir los datos publicados de la fuente de los valores utilizables para análisis.
- **Alternativas descartadas:** corregir, reemplazar o eliminar los valores de los parquets originales.

## 2026-11-08: Convención de direcciones 0 y 360 grados
- **Decisión:** no corregir 0 ni 360; se consideran equivalentes al convertir la dirección a seno y coseno. No hay días con velocidad exactamente cero.
- **Motivo:** conservar la representación angular circular y la evidencia disponible.
- **Alternativas descartadas:** reinterpretar 0 como calma o reemplazar un extremo del rango.

## 2026-11-08: Tratamiento de dirección de 81 grados
- **Decisión:** invalidar únicamente los 20 valores 81 que coinciden con una falla; conservar los 35 aislados.
- **Motivo:** las frecuencias de 80 (29) y 82 (32) son comparables a los aislados de 81.
- **Alternativas descartadas:** invalidar todas las observaciones con dirección 81.

## 2026-11-08: Índice normalizado de viento de ciudad
- **Decisión:** calcular la mediana diaria de velocidades divididas por la media de cada una de las 15 estaciones incluidas; exigir al menos tres estaciones y reescalar por la media de estaciones. Excluir Kennedy y San Cristóbal conforme al criterio del equipo; conservar la versión normalizada, con correlación 0.905 frente a la mediana simple.
- **Motivo:** reducir el efecto de diferencias de nivel entre estaciones y resumir el viento de ciudad.
- **Alternativas descartadas:** índice con las 17 estaciones o mediana sin normalizar como indicador principal.

## 2026-11-08: Viento de estaciones móviles sin sensor propio
- **Decisión:** Móvil Fontibón y Usme usan el índice de ciudad; no se les asigna el viento de una estación vecina.
- **Motivo:** las correlaciones disponibles indican representatividad local débil, incluso entre estaciones a 3-4 km.
- **Alternativas descartadas:** asignar viento de Fontibón a Móvil Fontibón o de Tunal a Usme.

## 2026-11-08: Dirección fuera del modelo base
- **Decisión:** excluir la dirección de viento del modelo base; considerarla solo como variable extra si queda tiempo.
- **Motivo:** promedio diario de método desconocido y baja coherencia entre estaciones cercanas.
- **Alternativas descartadas:** incluirla como predictor base sin validar su cálculo y consistencia.

## 2026-11-08: Comparabilidad del sensor de Guaymaral
- **Decisión:** dejar documentado que el sensor de Guaymaral se rotula "10M" en los 36 archivos y que su comparabilidad no está verificada.
- **Motivo:** la diferencia potencial de altura puede afectar la comparación con otras estaciones.
- **Alternativas descartadas:** asumir comparabilidad sin verificación.

## 2026-11-08: Recorte de alcance por tiempo
- **Decisión:** dejar tráfico (aforos), clustering y LightGBM fuera del alcance por la fecha de entrega 2026-11-13; los semáforos ya estaban descartados.
- **Motivo:** concentrar el trabajo en los entregables prioritarios dentro del tiempo disponible.
- **Alternativas descartadas:** mantener esos componentes como compromisos de esta entrega.

## 2026-11-08: Prioridad del modelo explicativo
- **Decisión:** usar validación temporal y comparar una línea base ingenua, Ridge y Random Forest; priorizar el modelo explicativo sin PM2.5 rezagado.
- **Motivo:** el modelo explicativo alimenta el simulador y la interpretación de factores.
- **Alternativas descartadas:** partición aleatoria, LightGBM y priorizar el modelo predictivo con PM2.5 de días anteriores.

## 2026-11-08: Fecha diaria de precipitación IDEAM
- **Decisión:** usar la fecha de precipitación tal como aparece en el archivo, sin desplazarla por la hora de corte del día pluviométrico.
- **Motivo:** el metadato indica “Día pluviométrico (convencional)” pero no especifica una hora de inicio; desplazar fechas supondría una convención no documentada.
- **Alternativas descartadas:** desplazar todos los registros por una hora supuesta.

## 2026-11-08: Indicador geográfico en_bogota
- **Decisión:** marcar `en_bogota=True` si latitud y longitud caen en la caja 4.3–5.0° N y -74.4–-73.8° O.
- **Motivo:** ese criterio coincide con el rango de coordenadas exigido para validar estaciones dentro de Bogotá y evita inferir límites administrativos no entregados en esta tarea.
- **Alternativas descartadas:** inferir pertenencia municipal solo del nombre o municipio textual del libro.
## 2026-11-08: Tratamiento del nivel de aprobación de los datos
- Decisión: conservar el nivel de aprobación únicamente como dato descriptivo, sin utilizarlo como criterio de exclusión de registros. El 97% de las filas (34.130 de 35.146) tiene estado “Preliminar”, por lo que excluirlas implicaría una pérdida significativa de información.
- Motivo: evitar la reducción considerable de datos disponibles y conservar la mayor cantidad de información para el análisis. Esta condición se documentará como una limitación metodológica.
## 2026-11-08: Selección y asignación de estaciones IDEAM para variables meteorológicas
- Decisión: se seleccionan únicamente tres estaciones IDEAM para el análisis: Nueva Generación, Jardín Botánico y San Cayetano. Las demás estaciones se descartan por problemas de cobertura, con porcentajes de días vacíos entre el 31 % y el 98 %. No se realizarán nuevas descargas de información de las estaciones descartadas.
- Motivo: garantizar una calidad mínima de información y evitar incorporar estaciones con vacíos excesivos que puedan afectar los resultados del análisis.
## 2026-11-08: Criterio de asignación de datos meteorológicos

- Decisión: se establece como criterio asignar a cada estación la información de la estación IDEAM más cercana que tenga una cobertura igual o superior al 85 %, de acuerdo con el criterio definido por el equipo. Los valores de temperatura máxima (tmax) y temperatura mínima (tmin) deben provenir de una misma estación.
- Motivo: mantener un criterio espacial consistente y evitar combinar temperaturas máximas y mínimas provenientes de estaciones diferentes.

## 2026-11-08: Convención de fecha para los datos de precipitación

- Decisión: se utiliza la fecha registrada en los datos de precipitación tal como aparece en la fuente, aplicando un rezago de un día.
- Motivo: permitir la asignación temporal de los datos de lluvia. Esta convención se considera un supuesto, dado que no se ha verificado la convención oficial del día pluviométrico utilizada por IDEAM.

## 2026-11-08: Limitaciones en la asignación de datos meteorológicos

- Decisión: se documentan las limitaciones de cobertura y representatividad de los datos IDEAM utilizados. En particular, 11 de las 19 estaciones comparten los datos de precipitación de Jardín Botánico. Además, la temperatura se encuentra distribuida entre dos estaciones con baja correlación entre sus registros y una diferencia de altitud de aproximadamente 500 m.
- Motivo: dejar explícitas las limitaciones espaciales y de representatividad de los datos, evitando asumir que la información asignada refleja necesariamente las condiciones meteorológicas locales de cada estación.

## 2026-11-08: Uso de datos preliminares de IDEAM

- Decisión: se conserva la información IDEAM disponible, dejando documentado que aproximadamente el 97 % de los datos tiene carácter preliminar.
- Motivo: disponer de la mayor cantidad de información posible para el análisis, reconociendo que los registros podrían estar sujetos a modificaciones o validaciones posteriores.

## 2026-11-08: Definición espacial de estaciones dentro de Bogotá

- Decisión: se utiliza la caja de coordenadas como criterio para definir si una estación se encuentra dentro de Bogotá (en_bogota). La estación Nazareth queda por fuera de esta delimitación.
- Motivo: establecer un criterio geográfico uniforme para clasificar las estaciones y documentar los casos que quedan excluidos por ubicación.

## 2026-11-08: Uso de información de humedad relativa

- Decisión: se genera un resumen de humedad relativa con 932 días de información, correspondientes a 2024 y 2026, para cinco estaciones. No se cuenta con información para 2025. Estos datos se utilizarán únicamente con fines exploratorios y no como insumo definitivo del análisis.
- Motivo: la cobertura temporal y espacial de los registros es insuficiente para garantizar un análisis representativo y comparable entre estaciones y años.