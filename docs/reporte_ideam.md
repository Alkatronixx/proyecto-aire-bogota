# Inspección y limpieza de datos IDEAM

Creé `src/datos/limpiar_ideam.py` y `tests/test_ideam.py`. El script completó la inspección, limpieza y asignación; **los cuatro tests pasaron**. No se modificó `data/raw` ni scripts existentes.

## Etapa 1: inspección

Los Excel traen las fechas como texto con hora. La búsqueda del encabezado y de las etiquetas encontró las tablas en los 22 libros. Las coordenadas y elevaciones de metadatos son texto con punto decimal, no coma decimal; las unidades observadas fueron `mm`, `degC` y `%`. No se encontraron fechas irreconocibles, unidades inesperadas, parámetros de máxima/mínima cruzados ni archivos idénticos por hash.

| Carpeta | Archivos | Patrón | Ejemplos |
|---|---:|---|---|
| `precipitacion` | 10 | `<código>.xlsx` | 21201240, 21201300, 2120500204, 21205710, 21205791 |
| `temperatura_max` | 3 | `<código>.xlsx` | 21206260, 21206600, 21206650 |
| `temperatura_min` | 4 | `<código>.xlsx` | 21206260, 21206560, 21206600, 21206650 |
| `humedad` | 5 | `<código>.xlsx` | 21205012, 21205710, 21205791, 21206560, 21206600 |

En todos los archivos, `Fecha consulta` declara el rango **24/10/2023 00:00–24/10/2026 00:00**. Esta es la tabla por archivo; las coordenadas son los textos crudos del Excel.

| Carpeta | Código — estación | Categoría | Lat, lon; elev. (m) | Variable; parámetro; frecuencia; unidad | Municipio |
|---|---|---|---|---|---|
| precipitación | 21201240 — Santa María de Usme | Pluviométrica | 4.4813055560, -74.12627778; 2800 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| precipitación | 21201300 — Australia | Pluviométrica | 4.394250, -74.1320; 3050 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| precipitación | 2120500204 — IDEAM Puente Aranda | Climatológica Principal | 4.621608, -74.103408; 2559 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| precipitación | 21205710 — Jardín Botánico | Climatológica Principal | 4.667867, -74.101034; 2552 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| precipitación | 21205791 — El Dorado CATAM | Climatológica Principal | 4.705583, -74.150667; 2547 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| precipitación | 21206260 — C. Univ. Agrop-UDCA | Climatológica Ordinaria | 4.7986388890, -74.04972222; 2570 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| precipitación | 21206560 — INEM Kennedy | Climatológica Principal | 4.625470, -74.156066; 2557 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| precipitación | 21206600 — Nueva Generación | Climatológica Principal | 4.786594, -74.102247; 2590 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| precipitación | 21206650 — Colegio San Cayetano | Climatológica Ordinaria | 4.5167527780, -74.0882222220; 3100 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| precipitación | 35020310 — Nazareth | Pluviográfica | 4.172250, -74.1460; 2800 | PRECIPITACION; Día pluviométrico (convencional); diaria; mm | Bogotá, D.C |
| temperatura máxima | 21206260 — C. Univ. Agrop-UDCA | Climatológica Ordinaria | 4.7986388890, -74.04972222; 2570 | TEMPERATURA; Temperatura máxima diaria; diaria; degC | Bogotá, D.C |
| temperatura máxima | 21206600 — Nueva Generación | Climatológica Principal | 4.786594, -74.102247; 2590 | TEMPERATURA; Temperatura máxima diaria; diaria; degC | Bogotá, D.C |
| temperatura máxima | 21206650 — Colegio San Cayetano | Climatológica Ordinaria | 4.5167527780, -74.0882222220; 3100 | TEMPERATURA; Temperatura máxima diaria; diaria; degC | Bogotá, D.C |
| temperatura mínima | 21206260 — C. Univ. Agrop-UDCA | Climatológica Ordinaria | 4.7986388890, -74.04972222; 2570 | TEMPERATURA; Temperatura mínima diaria; diaria; degC | Bogotá, D.C |
| temperatura mínima | 21206560 — INEM Kennedy | Climatológica Principal | 4.625470, -74.156066; 2557 | TEMPERATURA; Temperatura mínima diaria; diaria; degC | Bogotá, D.C |
| temperatura mínima | 21206600 — Nueva Generación | Climatológica Principal | 4.786594, -74.102247; 2590 | TEMPERATURA; Temperatura mínima diaria; diaria; degC | Bogotá, D.C |
| temperatura mínima | 21206650 — Colegio San Cayetano | Climatológica Ordinaria | 4.5167527780, -74.0882222220; 3100 | TEMPERATURA; Temperatura mínima diaria; diaria; degC | Bogotá, D.C |
| humedad | 21205012 — Universidad Nacional | Climatológica Principal | 4.637230, -74.088920; 2556 | HUM RELATIVA; Humedad relativa del aire a 2 metros horaria; horaria; % | Bogotá, D.C |
| humedad | 21205710 — Jardín Botánico | Climatológica Principal | 4.667867, -74.101034; 2552 | HUM RELATIVA; Humedad relativa del aire a 2 metros horaria; horaria; % | Bogotá, D.C |
| humedad | 21205791 — El Dorado CATAM | Climatológica Principal | 4.705583, -74.150667; 2547 | HUM RELATIVA; Humedad relativa del aire a 2 metros horaria; horaria; % | Bogotá, D.C |
| humedad | 21206560 — INEM Kennedy | Climatológica Principal | 4.625470, -74.156066; 2557 | HUM RELATIVA; Humedad relativa del aire a 2 metros horaria; horaria; % | Bogotá, D.C |
| humedad | 21206600 — Nueva Generación | Climatológica Principal | 4.786594, -74.102247; 2590 | HUM RELATIVA; Humedad relativa del aire a 2 metros horaria; horaria; % | Bogotá, D.C |

El campo **Parametro** dice “Día pluviométrico (convencional)” para precipitación, sin especificar la hora de inicio. Temperaturas: “Temperatura máxima diaria” y “Temperatura mínima diaria”.

Muestras de fecha cruda (las celdas son `str` en las cuatro carpetas): precipitación, primeras `2023-10-24 00:00` a `2023-10-26 00:00`, últimas `2026-10-22 00:00` a `2026-10-24 00:00`; temperatura máxima, primeras `2023-10-24` a `2023-10-26`, últimas `2026-10-20` a `2026-10-22`; temperatura mínima, primeras `2023-10-24` a `2023-10-26`, últimas `2026-10-21` a `2026-10-23`; humedad, primeras `2024-01-01 00:00`, `01:00`, `05:00`, últimas `2026-10-05 21:00`, `22:00`, `23:00`. Los libros diarios llevan `00:00`; humedad trae marcas horarias. El limpiador interpreta ISO explícitamente y usa `dayfirst=True` para las demás fechas.

Niveles de aprobación: **Preliminar 34,130**, **En revisión 948**, **Definitivo 68**. No hubo valores no numéricos en `Valor`; no hubo hashes duplicados.

El rango de consulta **no coincide con los datos reales en 14 archivos**: precipitación 21201300 (termina 2026-08-31), 2120500204 (empieza 2025-09-01), 21205791 (2023-11-15 a 2026-07-22), 21206260 (termina 2026-10-22), 21206560 (termina 2026-02-01) y 35020310 (termina 2026-03-01); temperatura máxima 21206260 (termina 2026-10-22); temperatura mínima 21206260 (termina 2026-10-23) y 21206560 (termina 2026-01-01); humedad: tres estaciones comienzan en 2024-01-01 y terminan el 2026-10-05, Kennedy solo tiene datos el 2026-10-05, y Nueva Generación va de 2024-04-22 a 2026-10-05. Son brechas de cobertura observadas, no errores de parseo, así que el proceso continuó.

## Etapa 2: limpieza y cobertura

Se excluyeron del periodo **5 filas de precipitación y 2 filas de cada temperatura**. Se retiraron cero duplicados no conflictivos y no hubo conflictos numéricos. Los valores numéricos se conservaron; **no se activó ninguna bandera** por centinela, rangos físicos, precipitación mayor de 150 mm o `tmax < tmin`.

El parquet diario quedó con **13,725 filas**: 7,700 de precipitación, 2,908 de temperatura máxima y 3,117 de mínima, desde 2023-10-24 hasta 2026-10-23. Humedad produjo **932 resúmenes diarios**. No hay humedad en 2025: Universidad Nacional, Jardín Botánico, El Dorado CATAM y Nueva Generación tienen datos en 2024 y 2026; INEM Kennedy solo en 2026.

El porcentaje NaN se calcula sobre los 1,096 días del periodo. Los rangos enumerados son huecos continuos de al menos 7 días.

| Código | Variable | % NaN | Primera–última fecha con dato | Rangos sin dato ≥7 días |
|---|---|---:|---|---|
| 21201240 | precip_mm | 8.39 | 2023-10-24–2026-10-23 | 2026-02-25..2026-05-21 (86 d) |
| 21201300 | precip_mm | 4.84 | 2023-10-24–2026-08-31 | 2026-09-01..2026-10-23 (53 d) |
| 2120500204 | precip_mm | 62.23 | 2025-09-01–2026-10-23 | 2023-10-24..2025-08-31 (678 d) |
| 21205710 | precip_mm | 9.58 | 2023-10-24–2026-10-23 | 2024-12-27..2025-01-05 (10 d); 2025-04-10..2025-04-20 (11 d); 2025-08-01..2025-08-12 (12 d); 2025-12-26..2026-01-03 (9 d) |
| 21205791 | precip_mm | 97.99 | 2023-11-15–2026-07-22 | 2023-10-24..2023-11-14 (22 d); 2023-11-16..2023-11-22 (7 d); 2023-11-24..2023-12-25 (32 d); 2024-01-01..2024-01-09 (9 d); 2024-01-13..2025-09-28 (625 d); 2025-10-01..2025-11-20 (51 d); 2025-11-22..2025-12-28 (37 d); 2025-12-30..2026-02-01 (34 d); 2026-02-03..2026-03-26 (52 d); 2026-03-31..2026-05-10 (41 d); 2026-05-12..2026-05-24 (13 d); 2026-05-26..2026-06-16 (22 d); 2026-06-18..2026-06-28 (11 d); 2026-06-30..2026-07-19 (20 d); 2026-07-23..2026-10-23 (93 d) |
| 21206260 | precip_mm | 30.38 | 2023-10-24–2026-10-22 | 2023-12-16..2024-01-09 (25 d); 2024-03-23..2024-03-30 (8 d); 2024-04-20..2024-04-30 (11 d); 2024-12-12..2025-01-11 (31 d); 2025-12-17..2026-01-22 (37 d); 2026-03-27..2026-04-04 (9 d) |
| 21206260 | tmax_c | 31.75 | 2023-10-24–2026-10-22 | 2023-12-16..2024-01-09 (25 d); 2024-03-24..2024-03-31 (8 d); 2024-04-21..2024-04-29 (9 d); 2024-12-13..2025-01-11 (30 d); 2025-04-12..2025-04-19 (8 d); 2025-12-17..2026-01-22 (37 d); 2026-03-27..2026-04-05 (10 d) |
| 21206260 | tmin_c | 31.57 | 2023-10-24–2026-10-23 | 2023-12-16..2024-01-09 (25 d); 2024-03-24..2024-03-31 (8 d); 2024-04-21..2024-04-29 (9 d); 2024-12-13..2025-01-12 (31 d); 2025-04-13..2025-04-20 (8 d); 2025-12-18..2026-01-23 (37 d); 2026-03-28..2026-04-06 (10 d) |
| 21206560 | precip_mm | 60.77 | 2023-10-24–2026-02-01 | 2023-12-02..2024-01-16 (46 d); 2024-02-26..2024-03-09 (13 d); 2024-03-22..2024-03-30 (9 d); 2024-06-21..2024-07-07 (17 d); 2024-10-04..2024-10-14 (11 d); 2024-12-15..2025-01-25 (42 d); 2025-04-11..2025-04-20 (10 d); 2025-06-20..2025-07-08 (19 d); 2025-10-03..2025-10-12 (10 d); 2025-11-28..2026-01-24 (58 d); 2026-02-02..2026-10-23 (264 d) |
| 21206560 | tmin_c | 82.03 | 2023-10-24–2026-01-01 | 2023-12-02..2024-01-31 (61 d); 2024-02-02..2024-03-10 (38 d); 2024-03-23..2024-03-31 (9 d); 2024-06-22..2024-07-29 (38 d); 2024-08-02..2024-09-02 (32 d); 2024-10-01..2024-10-29 (29 d); 2024-12-16..2025-01-22 (38 d); 2025-01-31..2025-03-31 (60 d); 2025-04-02..2025-07-29 (119 d); 2025-09-02..2025-09-30 (29 d); 2025-10-04..2025-10-13 (10 d); 2025-11-29..2025-12-31 (33 d); 2026-01-02..2026-10-23 (295 d) |
| 21206600 | precip_mm | 1.46 | 2023-10-24–2026-10-23 | Ninguno |
| 21206600 | tmax_c | 2.65 | 2023-10-24–2026-10-23 | 2026-01-25..2026-01-31 (7 d) |
| 21206600 | tmin_c | 1.73 | 2023-10-24–2026-10-23 | Ninguno |
| 21206650 | precip_mm | 0.27 | 2023-10-24–2026-10-23 | Ninguno |
| 21206650 | tmax_c | 0.27 | 2023-10-24–2026-10-23 | Ninguno |
| 21206650 | tmin_c | 0.27 | 2023-10-24–2026-10-23 | Ninguno |
| 35020310 | precip_mm | 21.53 | 2023-10-24–2026-03-01 | 2026-03-02..2026-10-23 (236 d) |

Salidas: `data/interim/ideam_largo.parquet`, `data/interim/ideam_humedad_diaria.parquet`, `data/processed/estaciones_ideam.csv` (11 estaciones, 10 dentro de la caja de coordenadas usada para `en_bogota`) y `data/processed/cobertura_ideam.csv`.

## Etapa 3: asignación y correlación

Abreviaturas en la tabla: NG Nueva Generación; UDCA C. Univ. Agrop-UDCA; CSC Colegio San Cayetano; JB Jardín Botánico; IK INEM Kennedy; IPA IDEAM Puente Aranda; EDC El Dorado CATAM; SMU Santa María de Usme. Cada celda muestra los tres más cercanos como `estación (km / % de días PM2.5 con dato)`.

| Estación de aire | precip_mm | tmax_c | tmin_c |
|---|---|---|---|
| Bolivia | EDC (4.35/2.3%); NG (6.22/98.4%); JB (8.05/91.8%) | NG (6.22/97.5%); UDCA (10.95/67.0%); CSC (24.72/99.8%) | NG (6.22/98.1%); UDCA (10.95/67.5%); IK (12.72/14.3%) |
| Carvajal–Sevillana | IK (3.42/36.7%); IPA (5.78/36.2%); JB (9.61/92.0%) | CSC (11.03/99.8%); NG (21.85/97.8%); UDCA (25.09/67.4%) | IK (3.42/16.4%); CSC (11.03/99.8%); NG (21.85/98.1%) |
| Centro Alto Rendimiento | JB (2.16/90.4%); IPA (4.63/36.9%); IK (8.79/35.9%) | NG (14.39/97.4%); CSC (15.77/99.8%); UDCA (16.04/66.1%) | IK (8.79/16.6%); NG (14.39/98.4%); CSC (15.77/99.8%) |
| Ciudad Bolívar | IK (5.42/38.7%); IPA (8.50/33.6%); CSC (11.00/99.8%) | CSC (11.00/99.8%); NG (24.28/98.0%); UDCA (27.75/66.9%) | IK (5.42/16.9%); CSC (11.00/99.8%); NG (24.28/98.5%) |
| Colina | NG (6.59/98.4%); UDCA (7.17/71.1%); JB (8.47/90.5%) | NG (6.59/97.3%); UDCA (7.17/68.8%); CSC (24.60/99.9%) | NG (6.59/97.9%); UDCA (7.17/68.8%); IK (15.70/15.6%) |
| Fontibón | EDC (3.13/2.0%); JB (4.88/91.6%); IK (6.02/38.7%) | NG (12.90/97.7%); UDCA (16.97/68.4%); CSC (18.98/99.8%) | IK (6.02/17.1%); NG (12.90/98.2%); UDCA (16.97/68.9%) |
| Guaymaral | UDCA (1.78/70.2%); NG (6.49/98.6%); JB (14.36/91.1%) | UDCA (1.78/67.9%); NG (6.49/97.8%); CSC (30.09/99.8%) | UDCA (1.78/68.3%); NG (6.49/98.3%); IK (21.55/16.6%) |
| Jazmín | IPA (1.94/35.1%); IK (4.93/39.4%); JB (6.78/91.1%) | CSC (10.62/99.8%); NG (19.85/98.0%); UDCA (22.34/68.5%) | IK (4.93/16.5%); CSC (10.62/99.8%); NG (19.85/98.4%) |
| Kennedy | IK (0.59/37.8%); IPA (6.43/34.2%); JB (8.20/90.1%) | CSC (14.52/99.9%); NG (19.12/97.6%); UDCA (22.92/69.0%) | IK (0.59/15.9%); CSC (14.52/99.9%); NG (19.12/98.1%) |
| Las Ferias | JB (3.27/89.4%); EDC (7.74/1.6%); IPA (8.03/44.9%) | NG (10.88/97.7%); UDCA (12.54/66.4%); CSC (19.35/99.9%) | NG (10.88/98.5%); IK (10.91/15.4%); UDCA (12.54/67.2%) |
| MinAmbiente | IPA (4.07/35.9%); JB (6.04/91.0%); IK (9.89/37.0%) | CSC (12.33/99.8%); NG (18.33/97.5%); UDCA (19.34/67.3%) | IK (9.89/15.6%); CSC (12.33/99.8%); NG (18.33/98.2%) |
| Móvil 7ma | JB (5.05/90.9%); IPA (5.33/32.1%); IK (10.70/39.6%) | CSC (14.58/99.8%); NG (16.36/97.8%); UDCA (17.11/68.5%) | IK (10.70/17.7%); CSC (14.58/99.8%); NG (16.36/98.6%) |
| Móvil Fontibón | EDC (4.19/2.1%); IK (4.80/39.3%); JB (5.26/90.7%) | NG (14.15/98.1%); CSC (18.10/99.9%); UDCA (18.19/67.7%) | IK (4.80/17.0%); NG (14.15/98.2%); CSC (18.10/99.8%) |
| Puente Aranda | IPA (1.93/31.0%); IK (4.33/39.9%); JB (4.41/89.9%) | CSC (13.20/99.8%); NG (17.30/98.2%); UDCA (20.02/67.1%) | IK (4.33/18.9%); CSC (13.20/99.8%); NG (17.30/98.2%) |
| San Cristóbal | IPA (5.86/36.9%); CSC (6.24/99.8%); IK (9.93/38.4%) | CSC (6.24/99.8%); NG (23.88/98.0%); UDCA (25.41/69.5%) | CSC (6.24/99.8%); IK (9.93/15.9%); NG (23.88/98.6%) |
| Suba | NG (2.97/98.8%); UDCA (6.38/70.1%); EDC (8.87/2.2%) | NG (2.97/97.8%); UDCA (6.38/68.5%); CSC (27.21/99.8%) | NG (2.97/98.6%); UDCA (6.38/69.1%); IK (16.63/16.3%) |
| Tunal | IPA (5.89/35.8%); IK (6.13/37.0%); CSC (8.14/99.8%) | CSC (8.14/99.8%); NG (23.60/97.5%); UDCA (26.31/66.9%) | IK (6.13/16.3%); CSC (8.14/99.8%); NG (23.60/98.0%) |
| Usaquén | JB (9.14/92.2%); UDCA (10.05/71.2%); NG (11.63/98.7%) | UDCA (10.05/68.7%); NG (11.63/97.8%); CSC (22.46/99.8%) | UDCA (10.05/69.1%); NG (11.63/98.2%); IK (16.82/18.7%) |
| Usme | CSC (3.63/99.8%); SMU (5.73/90.4%); IPA (10.07/37.8%) | CSC (3.63/99.8%); NG (28.35/97.8%); UDCA (30.57/67.6%) | CSC (3.63/99.8%); IK (11.25/16.2%); NG (28.35/98.6%) |

Correlación de precipitación diaria por parejas, con el total de días comparables sumado entre las parejas del rango:

| Distancia | Valor: media / mediana r; parejas; suma días | Indicador ≥1 mm: media / mediana r; parejas; suma días |
|---|---|---|
| 0–3 km | —; 0; 0 | —; 0; 0 |
| 3–6 km | 0.644 / 0.590; 4; 2,209 | 0.563 / 0.531; 4; 2,209 |
| 6–10 km | 0.676 / 0.694; 4; 1,384 | 0.239 / 0.413; 3; 1,380 |
| 10–15 km | 0.479 / 0.381; 6; 2,889 | 0.326 / 0.344; 6; 2,889 |
| >15 km | 0.344 / 0.356; 31; 17,333 | 0.247 / 0.265; 31; 17,333 |

Temperaturas, misma métrica (media / mediana r; parejas; suma de días comparables):

| Variable | 0–3 km | 3–6 km | 6–10 km | 10–15 km | >15 km |
|---|---|---|---|---|---|
| tmax_c | —; 0; 0 | 0.757 / 0.757; 1; 728 | —; 0; 0 | —; 0; 0 | 0.215 / 0.215; 2; 1,810 |
| tmin_c | —; 0; 0 | 0.620 / 0.620; 1; 739 | —; 0; 0 | 0.093 / 0.093; 1; 196 | 0.317 / 0.318; 4; 2,201 |

## Archivos y tests

Se generaron `data/interim/ideam_largo.parquet`, `data/interim/ideam_humedad_diaria.parquet`, `data/processed/estaciones_ideam.csv` y `data/processed/cobertura_ideam.csv`. El parquet diario tiene llave única y solo las tres variables esperadas. La humedad agregada tiene las siete columnas solicitadas. **`pytest tests/test_ideam.py -v`: 4 passed.**

Registré la fuente, las columnas y los supuestos en la documentación del proyecto. Quedan cinco decisiones humanas:

1. Confirmar con IDEAM la hora de inicio del “Día pluviométrico (convencional)”.
2. Decidir si se vuelve a descargar la cobertura incompleta de Puente Aranda, El Dorado CATAM y Kennedy.
3. Confirmar si el criterio de `en_bogota` debe ser la caja de coordenadas solicitada o un límite administrativo oficial.
4. Decidir si estaciones IDEAM fuera de esa caja, como Nazareth, deben participar en correlaciones y asignaciones.
5. Confirmar si basta con conservar `Nivel de Aprobación` como dato descriptivo, sin excluir niveles “Preliminar” o “En revisión”.
