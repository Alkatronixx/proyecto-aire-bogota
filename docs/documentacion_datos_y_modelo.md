# Datos y modelo del proyecto

## Tabla maestra

El producto principal es `data/processed/aire_bogota_diario.parquet`: una fila por estación y día, con 37 columnas, del 2023-10-24 al 2026-10-23. Contiene **20.824 filas**, correspondientes a 19 estaciones y 1.096 días de calendario. El catálogo de variables y las reglas de construcción están en [diccionario_datos.md](../data/docs/diccionario_datos.md); la procedencia documentada de los insumos está en [fuentes.md](../data/docs/fuentes.md).

Las mediciones de PM y viento proceden de la Red de Monitoreo de Calidad del Aire de Bogotá (RMCAB). Los insumos meteorológicos IDEAM provienen de archivos descargados por estación y variable; el registro de su estructura y proceso de limpieza está en `data/docs/fuentes.md`. Las ausencias se conservan como faltantes; PM2.5 y PM10 no se interpolan.

El hueco de PM2.5 y PM10 del 2025-08-04 al 2025-10-16 comprende **74 días**. La bandera está presente en todas las estaciones y sus mediciones PM siguen vacías: el hueco se verificó en la fuente y no se rellena. La decisión está documentada en [decisiones.md](decisiones.md).

## Resultados de prueba

La comparación explicativa v2 usa la climatología por estación y mes como referencia; el modelo aprende la anomalía respecto de esa climatología. Evaluación temporal publicada:

| Modelo | MAE (µg/m³) | RMSE (µg/m³) | R² |
|---|---:|---:|---:|
| Climatología | 5,490 | 6,968 | 0,261 |
| Climatología + Ridge de anomalía | 5,393 | 6,923 | 0,270 |
| Climatología + Random Forest de anomalía | 5,386 | 6,955 | 0,264 |
| Climatología + HistGradientBoosting de anomalía | 5,221 | 6,777 | 0,301 |

HistGradientBoosting registró el menor MAE en prueba. El Ridge publicado se seleccionó mediante validación cruzada temporal dentro del entrenamiento; la tabla de prueba no se usó para esa selección. Frente a climatología, el Ridge mejora el MAE en aproximadamente **1,8 %**, una diferencia pequeña.

En el modelo predictivo comparado, el Ridge guardado obtuvo MAE **3,332** y el Random Forest de comparación **3,223** en 5.170 filas. El Random Forest tuvo menor MAE en esa prueba; el Ridge guardado fue seleccionado por validación temporal dentro del entrenamiento. No se presenta al Ridge como el mejor resultado de prueba.

## Alineación meteorológica y límites

El diagnóstico de alineación no encontró un desfase uniforme. Los máximos absolutos de Spearman reportados son **0,11** para lluvia y **0,16** para temperatura. Al usar las variables meteorológicas con fecha +1, el MAE pasó de **5,441** a **5,397 µg/m³**, una diferencia de **0,044 µg/m³** en 5.258 filas; se conserva la alineación original. Estas cifras están centralizadas en [cifras_modelo.py](../app/utils/cifras_modelo.py).

El PM2.5 observado fue menor en el año de prueba que en el entrenamiento. El análisis disponible no determina la causa: puede reflejar diferencias de medición, estacionalidad u otros factores no identificados. Las asociaciones descriptivas de viento, lluvia, temperatura y calendario no se interpretan como efectos causales. La aplicación usa el Ridge de anomalías v2 para el simulador.

## Fuentes de referencia

- [Fuentes y transformaciones de datos del proyecto](../data/docs/fuentes.md)
- [Diccionario de datos](../data/docs/diccionario_datos.md)
- [Informe de diagnóstico del modelo](reporte_modelo.md)
- [Decisiones vigentes](decisiones.md)
