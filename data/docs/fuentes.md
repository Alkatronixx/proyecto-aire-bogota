# IDEAM DHIME: precipitación, temperaturas y humedad

- **Fuente:** libros Excel por estación y variable descargados del reporte IDEAM DHIME.
- **Archivos:** `data/raw/precipitacion/`, `data/raw/temperatura_max/`, `data/raw/temperatura_min/` y `data/raw/humedad/`.
- **Estructura:** metadatos etiquetados antes de la tabla `Fecha | Valor: | Nivel de Aprobación`; los encabezados y pares etiqueta-valor se buscan por contenido.
- **Unidades observadas:** precipitación en mm, temperaturas en degC y humedad en %.
- **Transformación:** `src/datos/limpiar_ideam.py`; precipitación y temperaturas quedan en `data/interim/ideam_largo.parquet`; humedad agregada por día queda en `data/interim/ideam_humedad_diaria.parquet` para exploración.
