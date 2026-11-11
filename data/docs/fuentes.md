# IDEAM DHIME: precipitación, temperaturas y humedad

- **Fuente:** libros Excel por estación y variable descargados del reporte IDEAM DHIME.
- **Archivos:** `data/raw/precipitacion/`, `data/raw/temperatura_max/`, `data/raw/temperatura_min/` y `data/raw/humedad/`.
- **Estructura:** metadatos etiquetados antes de la tabla `Fecha | Valor: | Nivel de Aprobación`; los encabezados y pares etiqueta-valor se buscan por contenido.
- **Unidades observadas:** precipitación en mm, temperaturas en degC y humedad en %.
- **Transformación:** `src/datos/limpiar_ideam.py`; precipitación y temperaturas quedan en `data/interim/ideam_largo.parquet`; humedad agregada por día queda en `data/interim/ideam_humedad_diaria.parquet` para exploración.

## Fuentes oficiales de contexto incluidas en la app

- **ICA de 24 horas:** IDEAM, hoja metodológica de indicadores; puntos de corte asociados a la Resolución 2254 de 2017, artículo 20, Tabla 6. Consultada el 2026-11-11. [PDF IDEAM](https://bart.ideam.gov.co/indiecosistemas/ind/aire/hm/1.%20HM%20Indice%20calidad%20aire.pdf) y [Resolución MADS](https://www.minambiente.gov.co/wp-content/uploads/2021/10/Resolucion-2254-de-2017.pdf). La tabla del IDEAM contiene la errata del rango PM2.5 16–150 para la categoría “Dañina a la salud”; la interfaz usa el inicio 56 µg/m³ indicado por la Tabla 4 de la resolución.
- **Mortalidad atribuida a exposición de largo plazo a PM2.5:** Secretaría Distrital de Salud, metodología AirQ+ de la OMS; serie 2018–2024 y ficha técnica del 2025-07-25. Consultada el 2026-11-11. [PDF indicado para la app](https://saludata.saludcapital.gov.co/osb/wp-content/uploads/2026/04/OSB_MortalidadAtribuible_PM2.5.pdf), [ficha técnica PDF accesible](https://saludata.saludcapital.gov.co/osb/wp-content/uploads/2026/03/OSB_MortalidadAtribuible_PM2.5.pdf) y [página del indicador](https://saludata.saludcapital.gov.co/osb/indicadores/mortalidad-calidad-aire/).
