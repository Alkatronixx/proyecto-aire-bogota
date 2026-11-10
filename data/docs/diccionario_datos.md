# Productos de calidad e índice de viento de ciudad (`viento_ciudad.py`)

| Columna | Producto | Descripción |
|---|---|---|
| `valor_original` | `viento_limpio.parquet` | Medición del parquet original antes de las reglas de calidad. |
| `flag_calidad` | `viento_limpio.parquet` | Regla que invalidó el valor (`vel_negativa`, `dir_por_vel_invalida` o `dir_racha`); vacío si no hubo cambio. |
| `sensor_dudoso` | `viento_limpio.parquet` | Booleano verdadero para Kennedy y San Cristóbal. |
| `vel_ciudad_ms` | `viento_ciudad.parquet` | Índice diario: mediana de velocidades normalizadas por estación, reescalada a m/s. NaN si contribuyen menos de tres estaciones. |
| `n_estaciones` | `viento_ciudad.parquet` | Cantidad de estaciones incluidas con velocidad válida ese día. |

## Productos IDEAM (`limpiar_ideam.py`)

| Columna | Producto | Descripción |
|---|---|---|
| `estacion_ideam_id` | `ideam_largo.parquet`, `ideam_humedad_diaria.parquet` | Código de estación IDEAM tomado del nombre del archivo; se conserva como texto. |
| `valor_original` | `ideam_largo.parquet` | Valor crudo del Excel antes de conversión numérica; permite auditar los textos no numéricos. |
| `nivel_aprobacion` | `ideam_largo.parquet` | Nivel de aprobación tal como aparece en el Excel. |
| `flag_calidad` | `ideam_largo.parquet` | Banderas separadas por punto y coma para centinelas, rangos físicos y tmax menor que tmin; no altera `valor`. |
| `media`, `minimo`, `maximo` | `ideam_humedad_diaria.parquet` | Resumen diario exploratorio de las observaciones horarias de humedad relativa. |
| `n_horas_con_dato` | `ideam_humedad_diaria.parquet` | Cantidad de observaciones horarias de humedad no nulas en el día. |
| `variables_disponibles` | `estaciones_ideam.csv` | Variables para las que existe un libro de entrada de esa estación. |
| `en_bogota` | `estaciones_ideam.csv` | Verdadero cuando las coordenadas caen dentro de la caja 4.3–5.0° N y -74.4–-73.8° O. |
| `dias_con_dato`, `porcentaje_mes` | `cobertura_ideam.csv` | Días observados y porcentaje sobre los días del mes incluidos en el periodo del proyecto. |

## Tabla maestra diaria (`aire_bogota_diario.parquet`)

| Columna | Descripción | Unidad | Fuente | Regla de construcción | Tratamiento de faltantes |
|---|---|---|---|---|---|
| `fecha` | Día calendario | fecha | Calendario del proyecto | Malla diaria 2023-10-24 a 2026-10-23 | Sin faltantes |
| `estacion_id` | Identificador normalizado de estación de aire | — | GeoJSON / aire_largo | Llave de estación | Sin faltantes |
| `estacion` | Nombre de estación de aire | — | Asignación espacial | Nombre del catálogo geográfico | Sin faltantes |
| `es_movil` | Indica una estación móvil | booleano | Identificador de estación | True para Móvil 7ma y Móvil Fontibón | Sin faltantes |
| `pm25` | PM2.5 diario | µg/m³ | aire_largo.parquet | Negativos pasan a NaN | NaN si falta o es negativo |
| `pm10` | PM10 diario | µg/m³ | aire_largo.parquet | Negativos pasan a NaN | NaN si falta o es negativo |
| `pm25_faltante` | PM2.5 no disponible tras limpieza | booleano | aire_largo.parquet | True si `pm25` es NaN | Siempre definido |
| `pm10_faltante` | PM10 no disponible tras limpieza | booleano | aire_largo.parquet | True si `pm10` es NaN | Siempre definido |
| `pm_invalido` | Algún PM original negativo | booleano | aire_largo.parquet | True si PM2.5 o PM10 original es negativo | Siempre definido |
| `hueco_pm_2025` | Día dentro del hueco de fuente | booleano | Decisión documentada | True del 2025-08-04 al 2025-10-16, todas las estaciones | Siempre definido |
| `vel_ciudad_ms` | Índice de velocidad de viento de ciudad | m/s | viento_ciudad.parquet | Índice normalizado diario de estaciones incluidas | NaN si no hay índice válido |
| `n_est_viento` | Estaciones que contribuyen al índice | estaciones | viento_ciudad.parquet | Conteo diario de aportantes | NaN si no está informado |
| `vel_viento_propia` | Velocidad observada en la estación de aire | m/s | viento_limpio.parquet | Unión por fecha e identificador; exploración | NaN si no hay dato |
| `dir_sin` | Seno de dirección del viento | adimensional | viento_limpio.parquet | Seno de grados convertidos a radianes; exploración | NaN si no hay dirección válida |
| `dir_cos` | Coseno de dirección del viento | adimensional | viento_limpio.parquet | Coseno de grados convertidos a radianes; exploración | NaN si no hay dirección válida |
| `precip_mm` | Precipitación diaria asignada | mm/día | ideam_largo.parquet + asignación | Estación asignada de mayor proximidad con cobertura suficiente | NaN si IDEAM no tiene dato válido |
| `precip_1d_antes` | Precipitación del día anterior | mm/día | `precip_mm` | Rezago de un día tras reindexar al calendario | NaN si falta el día anterior |
| `precip_3d_acum` | Acumulado de precipitación de D-3 a D-1 | mm/3 días | `precip_mm` | Suma móvil de los tres días previos, solo si están completos | NaN si falta cualquiera de los tres días |
| `llueve` | Indicador de lluvia diaria | booleano | `precip_mm` | True si precipitación ≥ 1 mm | NaN si precipitación es NaN |
| `lluvia_ciudad_n` | Estaciones de referencia con lluvia | estaciones | ideam_largo.parquet | Conteo ≥1 mm entre 21206600, 21205710 y 21206650 | NaN si menos de dos estaciones tienen dato |
| `dist_precip_km` | Distancia a estación IDEAM de precipitación | km | Asignación espacial | Haversine entre coordenadas | NaN si no hay asignación |
| `precip_estacion_id` | Código IDEAM asignado para precipitación | código | Asignación espacial | Identificador de la candidata seleccionada | NaN si no hay asignación |
| `tmax_c` | Temperatura máxima diaria asignada | °C | ideam_largo.parquet + asignación | Estación conjunta de tmax y tmin con cobertura suficiente | NaN si falta medición válida |
| `tmin_c` | Temperatura mínima diaria asignada | °C | ideam_largo.parquet + asignación | Misma estación seleccionada para tmax | NaN si falta medición válida |
| `tmedia_c` | Promedio de máxima y mínima | °C | `tmax_c`, `tmin_c` | Media aritmética cuando ambas existen | NaN si falta cualquiera |
| `amplitud_c` | Diferencia entre máxima y mínima | °C | `tmax_c`, `tmin_c` | tmax menos tmin cuando ambas existen | NaN si falta cualquiera |
| `dist_temp_km` | Distancia a estación IDEAM de temperatura | km | Asignación espacial | Haversine entre coordenadas | NaN si no hay asignación |
| `temp_estacion_id` | Código IDEAM asignado para temperatura | código | Asignación espacial | Identificador de la candidata seleccionada | NaN si no hay asignación |
| `dia_semana` | Día de la semana | 0–6 | Calendario | Lunes=0 y domingo=6 | Sin faltantes |
| `mes` | Mes calendario | 1–12 | Calendario | Mes numérico de la fecha | Sin faltantes |
| `es_fin_semana` | Indica sábado o domingo | booleano | Calendario | Día semanal ≥5 | Sin faltantes |
| `es_festivo` | Festivo colombiano | booleano | Librería holidays | Calendario Colombia para cada fecha | Sin faltantes |
| `temporada` | Clasificación estacional exploratoria | categoría | Criterio del equipo | Seca: dic-ene-feb-jul-ago; lluviosa: mar-abr-may-sep-oct-nov | Sin faltantes |
| `localidad` | Localidad de Bogotá | nombre | GeoJSON / asignación | Cruce espacial de estación de aire | NaN si no cae en localidad |
| `altitud_m` | Altitud indicada para la estación de aire | m | GeoJSON de estaciones | Se toma solo si el atributo está presente | NaN si no está informada |
| `lat` | Latitud de estación de aire | grados decimales | GeoJSON de estaciones | Coordenada del punto | NaN si no está informada |
| `lon` | Longitud de estación de aire | grados decimales | GeoJSON de estaciones | Coordenada del punto | NaN si no está informada |
