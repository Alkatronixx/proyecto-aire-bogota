# Asignación IDEAM y tabla maestra diaria

Se construyeron las asignaciones IDEAM para las 19 estaciones de aire y la tabla maestra diaria. Las asignaciones coinciden con las estaciones esperadas.

## Archivos generados

- `src/datos/asignar_estaciones.py`
- `src/datos/construir_maestra.py`
- `data/processed/asignacion_estaciones.csv`
- `data/processed/aire_bogota_diario.parquet`
- `data/processed/cobertura_maestra.csv`
- `tests/test_maestra.py`

Se actualizó el diccionario con las 37 columnas de la tabla maestra y se reemplazó únicamente la lista de columnas de “Tabla maestra” en `AGENTS.md` (74 líneas). No se modificaron `data/raw`, los scripts de limpieza, los parquets de `data/interim` ni `docs/decisiones.md`.

## Asignación IDEAM

NG = Nueva Generación; JB = Jardín Botánico; SC = Colegio San Cayetano. Coberturas en porcentaje.

| Estación de aire | Precipitación | Dist. km | Cob. % | Temperatura | Dist. km | Cob. % |
|---|---|---:|---:|---|---:|---:|
| Centro de Alto Rendimiento | JB | 2.16 | 90.40 | NG | 14.39 | 96.22 |
| Guaymaral | NG | 6.49 | 98.55 | NG | 6.49 | 96.44 |
| Kennedy | JB | 8.20 | 90.12 | SC | 14.52 | 99.78 |
| Las Ferias | JB | 3.27 | 89.44 | NG | 10.88 | 96.66 |
| Puente Aranda | JB | 4.41 | 89.88 | SC | 13.20 | 99.51 |
| MinAmbiente | JB | 6.04 | 90.96 | SC | 12.33 | 99.58 |
| San Cristobal | SC | 6.24 | 99.77 | SC | 6.24 | 99.53 |
| Móvil Fontibón | JB | 5.26 | 90.73 | NG | 14.15 | 96.72 |
| Móvil 7ma | JB | 5.05 | 90.89 | SC | 14.58 | 99.54 |
| Suba | NG | 2.97 | 98.78 | NG | 2.97 | 96.68 |
| Tunal | SC | 8.14 | 99.76 | SC | 8.14 | 99.53 |
| Colina | NG | 6.59 | 98.38 | NG | 6.59 | 95.64 |
| Usaquen | JB | 9.14 | 92.20 | NG | 11.63 | 96.45 |
| Ciudad Bolívar | SC | 11.00 | 99.77 | SC | 11.00 | 99.55 |
| Usme | SC | 3.63 | 99.77 | SC | 3.63 | 99.53 |
| Jazmín | JB | 6.78 | 91.11 | SC | 10.62 | 99.57 |
| Fontibón | JB | 4.88 | 91.59 | NG | 12.90 | 96.34 |
| Bolivia | NG | 6.22 | 98.42 | NG | 6.22 | 96.00 |
| Carvajal - Sevillana | JB | 9.61 | 92.00 | SC | 11.03 | 99.53 |

**Diferencias frente a lo esperado:** ninguna. Todas las asignaciones cumplen la cobertura mínima del 85%.

## Localidad y `en_bogota` de las estaciones IDEAM

| Código | Estación IDEAM | `en_bogota` | Localidad |
|---|---|:---:|---|
| 21201240 | SANTA MARIA DE USME | Sí | CIUDAD BOLIVAR |
| 21201300 | AUSTRALIA | Sí | USME |
| 2120500204 | IDEAM PUENTE ARANDA | Sí | PUENTE ARANDA |
| 21205710 | JARDIN BOTANICO | Sí | ENGATIVA |
| 21205791 | EL DORADO CATAM | Sí | FONTIBON |
| 21206260 | C.UNIV.AGROP-UDCA | Sí | SUBA |
| 21206560 | INEM KENNEDY | Sí | KENNEDY |
| 21206600 | NUEVA GENERACION | Sí | SUBA |
| 21206650 | COLEGIO SAN CAYETANO | Sí | USME |
| 35020310 | NAZARETH | No | SUMAPAZ |
| 21205012 | UNIVERSIDAD NACIONAL | Sí | TEUSAQUILLO |

Ninguna estación IDEAM ni estación de aire quedó fuera de todas las localidades. El GeoJSON no incluye altitud para Móvil Fontibón, Móvil 7ma, Colina, Ciudad Bolívar, Usme, Jazmín y Fontibón; sus altitudes quedan como NaN.

## Representatividad IDEAM

- Temperatura máxima, Nueva Generación vs. San Cayetano: **r = 0.216**, diferencia media San Cayetano − Nueva Generación **−6.361 °C**, **n = 1,064**.
- Temperatura mínima, Nueva Generación vs. San Cayetano: **r = −0.087**, diferencia media **−3.712 °C**, **n = 1,074**.
- Precipitación, Nueva Generación vs. Jardín Botánico: **r = 0.374**, acuerdo en lluvia ≥1 mm **70.59%**, **n = 976**.
- Precipitación, Jardín Botánico vs. San Cayetano: **r = 0.219**, acuerdo **61.84%**, **n = 988**.

## Cobertura maestra

Porcentajes de días con dato. “Sin hueco” excluye los 74 días del hueco y deja 1,022 días por estación. Ordenada por cobertura de PM2.5 sin hueco, de menor a mayor.

| Estación | PM2.5 total % | PM10 total % | PM2.5 sin hueco % | PM10 sin hueco % | Meses con 0% PM2.5 | Casos completos sin hueco % |
|---|---:|---:|---:|---:|---|---:|
| Las Ferias | 68.25 | 74.36 | 73.19 | 79.75 | 2023-10; 2025-09 | 63.11 |
| Colina | 73.18 | 72.17 | 78.47 | 77.40 | 2025-05; 2025-09; 2025-10; 2025-11; 2025-12 | 74.36 |
| Puente Aranda | 74.82 | 73.91 | 80.23 | 79.26 | 2025-09 | 71.72 |
| Bolivia | 75.27 | 85.77 | 80.72 | 91.98 | 2024-02; 2024-03; 2025-09 | 76.81 |
| Usaquen | 77.19 | 80.93 | 82.78 | 86.79 | 2025-03; 2025-09; 2026-01 | 73.48 |
| Tunal | 77.19 | 81.84 | 82.78 | 87.77 | 2025-08; 2025-09 | 82.39 |
| Carvajal - Sevillana | 77.55 | 69.25 | 83.17 | 74.27 | 2025-08; 2025-09; 2026-01 | 76.13 |
| Usme | 77.92 | 82.21 | 83.56 | 88.16 | 2024-11; 2025-08; 2025-09 | 83.17 |
| San Cristobal | 78.47 | 79.38 | 84.15 | 85.13 | 2025-08; 2025-09 | 83.76 |
| Móvil 7ma | 80.11 | 85.40 | 85.91 | 91.59 | 2025-08; 2025-09; 2026-01 | 77.69 |
| Ciudad Bolívar | 80.38 | 82.57 | 86.20 | 88.55 | 2025-09 | 85.81 |
| Móvil Fontibón | 80.75 | 84.12 | 86.59 | 90.22 | 2025-09; 2026-01 | 75.83 |
| Kennedy | 81.30 | 82.21 | 87.18 | 88.16 | 2025-09 | 78.38 |
| Guaymaral | 82.03 | 83.12 | 87.96 | 89.14 | 2025-09 | 84.15 |
| Suba | 82.48 | 84.58 | 88.45 | 90.70 | 2025-09 | 84.83 |
| Jazmín | 84.12 | 84.12 | 90.22 | 90.22 | 2025-08; 2025-09; 2026-01 | 81.80 |
| Centro de Alto Rendimiento | 84.58 | 84.12 | 90.70 | 90.22 | 2025-09 | 78.67 |
| Fontibón | 84.67 | 81.48 | 90.80 | 87.38 | 2025-09; 2026-01 | 79.94 |
| MinAmbiente | 86.77 | 88.59 | 93.05 | 95.01 | 2025-08; 2025-09 | 84.25 |

## Conteo de filas

| Ventana | PM2.5 válido | Casos completos del modelo base |
|---|---:|---:|
| Total | 16,517 | 15,292 |
| 2023-10-24 a 2024-10-23 | 6,308 | 5,995 |
| 2024-10-24 a 2025-10-23 | 4,392 | 3,792 |
| 2025-10-24 a 2026-10-23 | 5,817 | 5,505 |

La tabla tiene **20,824 filas**, 19 estaciones y 1,096 días. `pytest -q tests/test_maestra.py` terminó con **3 passed**.

## Decisiones nuevas y asuntos para decisión humana

1. Se aplicó el umbral de cobertura **0.85** y se eligió la estación más cercana que lo cumple.
2. Para temperatura se exigió que una misma estación tuviera tmax y tmin disponibles el mismo día.
3. `pm_invalido` es True cuando cualquiera de los valores PM originales era negativo; esos valores pasan a NaN.
4. La temporada se etiquetó con los meses indicados, como supuesto pendiente de validación con una fuente IDEAM antes de citarla en la app.
5. Requiere decisión humana confirmar el criterio estacional y cómo representar las siete estaciones sin altitud disponible; no se inventaron altitudes.
