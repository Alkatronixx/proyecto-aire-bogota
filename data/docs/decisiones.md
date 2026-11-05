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