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
