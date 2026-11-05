# Proyecto
Análisis de calidad del aire en Bogotá (PM2.5 y PM10) y sus factores (viento, lluvia, temperatura, calendario, ubicación). Proyecto universitario de Ciencia de Datos, entrega viernes 13-nov-2026. Entregables: tabla integrada, modelo y app en Streamlit desplegada en Streamlit Community Cloud. Se evalúa excelencia en calidad de datos, modelo y presentación.

# Pregunta de negocio
¿Qué variables meteorológicas y de calendario influyen más en el PM2.5 en Bogotá y cuánto cambia con distintos escenarios (lluvia, día de la semana, temporada, localidad)? Sirve a autoridades ambientales y a ciudadanos.

# Decisiones de alcance (no cambiar sin avisar)
- Periodo: 2023-10-23 a 2026-10-23.
- Grano: una fila por estación y día. Llave única: (fecha, estacion_id).
- La humedad relativa NO entra al modelo (no hay datos de 2025); solo exploración.
- Tráfico (aforos): extra opcional. Los Excel traen latitud y longitud de cada nodo. Se usan solo aforos dentro del periodo 2023-10-23 a 2026-10-23. Se asigna cada nodo a la estación de aire más cercana dentro de un radio de 1.5 km y se calcula el flujo medio por tipo de vehículo como variable fija por estación (no es una serie diaria). Los tipos de vehículo (columnas L, B, M, BI, C, etc.) cambian entre archivos: pasarlos a formato largo (tipo_vehiculo, conteo) y mapearlos a categorías comunes usando la leyenda de cada archivo. No inventar el mapeo: si una categoría es ambigua, dejar un TODO.
- Estaciones móviles: confirmar ubicación antes de usarlas; si no, excluir.

# Estructura de carpetas
data/raw (no se toca, no se sube a git), data/interim (una tabla limpia por fuente, formato largo), data/processed (tabla maestra y catálogos, sí se sube), data/docs (fuentes.md, diccionario_datos.md), docs (decisiones.md), notebooks, src/datos, src/modelo, src/utils, models, app (app.py, pages, components, assets), tests.

# Fuentes
- Aire (RMCAB): Excel mensual en formato ancho, encabezado de 3 filas (estación / contaminante / unidad), una columna por estación, una fila por día, PM10 y PM2.5 en µg/m3.
- Viento (RMCAB): Excel mensual, mismo formato ancho; velocidad (m/s) y dirección (grados) por estación.
- IDEAM (precipitación mm, temperatura máxima y mínima °C, humedad %): un Excel por estación y variable, con un bloque de metadatos arriba (nombre, latitud, longitud, elevación, variable) y luego la tabla Fecha, Valor, Nivel de Aprobación.
- Aforos vehiculares: Excel por nodo maestro con nodos normales; incluyen latitud y longitud de cada nodo.
- Geografía: GeoJSON de estaciones y de localidades de Bogotá.
- Fechas en formato día/mes/año: leer con dayfirst=True.

# Tabla maestra (columnas)
fecha, estacion_id, pm25, pm10, vel_viento, dir_sin, dir_cos, precip_mm, precip_1d_antes, precip_3d_acum, tmax_c, tmin_c, tmedia_c, amplitud_c, dist_precip_km, dist_temp_km, dia_semana, mes, es_fin_semana, es_festivo, temporada, localidad, altitud_m, lat, lon, pm25_faltante, pm10_faltante.
Cada estación de aire se asigna a la estación IDEAM más cercana y se guarda la distancia.

# Reglas de datos (críticas)
- Nunca modificar data/raw. Nunca inventar, estimar ni rellenar con cero datos faltantes: un dato ausente queda vacío (NaN).
- Interpolar solo huecos de 1-2 días en variables explicativas y marcar la fila. Nunca interpolar PM2.5 ni PM10.
- Dirección del viento: convertir a seno y coseno; nunca promediar grados.
- Festivos de Colombia con la librería holidays.
- Eliminar duplicados en los límites de mes; guardar archivo_origen en interim.
- Generar una tabla de cobertura (estación x año-mes, % de días con dato) y documentar el umbral de descarte.
- Cada transformación debe ser un script en src/ reproducible, no pasos manuales.
- Verificar con tests: sin duplicados (fecha, estacion_id), rangos válidos, fechas en el periodo.

# Modelo
- Validación temporal: entrenar con los primeros años y probar con el último año completo. Nunca partir al azar.
- Comparar: línea base ingenua, Ridge y Random Forest o LightGBM. Métricas: MAE, RMSE, R2, también por estación.
- Dos modelos: predictivo (con PM2.5 de días anteriores) y explicativo (sin ellos; alimenta el simulador y la interpretación).
- Guardar con joblib en models/.

# App (Streamlit)
- Páginas: Portada, Contexto de Bogotá y negocio, Mapa, Factores, Simulador, Modelo, Datos y metodología.
- Usar @st.cache_data y @st.cache_resource. La app solo lee data/processed y models/.
- Tema oscuro, tarjetas con st.metric, gráficos con Plotly, mapa con pydeck.
- Paleta de calidad del aire (usar siempre la misma): bueno #2ECC71, moderado #F1C40F, dañino para sensibles #E67E22, dañino #E74C3C, muy dañino #8E44AD. Acento #00C2A8, fondo #0E1117.
- Toda cifra de contexto (OMS, normas colombianas, datos de Bogotá) debe venir de una fuente oficial citada con enlace. Si no hay fuente, dejar un TODO; nunca escribir cifras de memoria.

# Documentación
- Cada decisión de datos o de modelo que tomes o propongas se registra al final de docs/decisiones.md con este formato: fecha, decisión, motivo, alternativas descartadas. No borrar entradas anteriores.
- Cada fuente nueva se anota en data/docs/fuentes.md y cada columna nueva en data/docs/diccionario_datos.md.
- Si el usuario te pide un cambio que contradice una decisión de alcance, avisa antes de hacerlo.

# Comentarios y documentación del código
- Comentarios y docstrings en español. Comentar el POR QUÉ (supuestos, decisiones, rarezas de los datos), no lo obvio (nada de "# suma uno").
- Cada archivo empieza con un docstring de 3 a 5 líneas: qué hace, qué lee y qué produce.
- Cada función lleva docstring corta: qué hace, parámetros y qué devuelve.
- Los supuestos se marcan con "SUPUESTO:" y las dudas con "TODO:". Cada SUPUESTO relevante debe tener su entrada en docs/decisiones.md.
- Al modificar código, actualizar los comentarios afectados; no dejar comentarios desactualizados.
- Los comentarios deben permitir que alguien que no escribió el código pueda explicarlo en una exposición oral.

# Convenciones
- Python 3.11, pandas, scikit-learn, plotly, pydeck, streamlit, geopandas, openpyxl, pyarrow.
- Nombres de columnas en snake_case sin tildes; código y comentarios claros; funciones pequeñas con docstring corta.
- Una tarea por vez: no refactorizar ni tocar archivos fuera de lo pedido.
- Antes de terminar: ejecutar el código, mostrar errores si los hay, y no declarar éxito sin haberlo corrido.
- Si falta información o hay ambigüedad en los datos, preguntar o dejar un TODO; no suponer.
