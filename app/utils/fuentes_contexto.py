"""Centraliza cifras, textos de contexto y sus fuentes oficiales.
Las páginas Contexto, Mapa y Datos y metodología importan estos datos para evitar cifras dispersas.
Incluye tablas normativas, notas de interpretación y enlaces con fechas de consulta.
Las fuentes anteriores se consultaron el 2026-11-10; ICA y salud se consultaron el 2026-11-11.
"""

# fuente verificada el 2026-11-10: https://www.saludcapital.gov.co/Documents/Brief_Determinantes_Sociales_Bogota.pdf
POBLACION_BOGOTA_2025 = 7_937_898
# fuente verificada el 2026-11-10: https://bogota.gov.co/mi-ciudad/ambiente/en-bogota-se-monitorea-calidad-del-aire-en-dia-sin-carro-y-sin-moto
ESTACIONES_SDA = 19
MICROSENSORES_SDA = 70
# fuente verificada el 2026-11-10: https://ambientebogota.gov.co/es/web/sda/estaciones-rmcab
URL_ESTACIONES_SDA = "https://ambientebogota.gov.co/es/web/sda/estaciones-rmcab"
# fuente verificada el 2026-11-10: ficha de estaciones RMCAB de la SDA.
ESTACIONES_LISTADAS_SDA = 20
# fuente verificada el 2026-11-10: página de contaminantes de la OMS.
DIAMETRO_PM25_MICROMETROS = 2.5
DIAMETRO_PM10_MICROMETROS = 10
# fuente verificada el 2026-11-10: https://www.who.int/teams/environment-climate-change-and-health/air-quality-and-health/health-impacts/types-of-pollutants
URL_GUIAS_OMS = "https://www.who.int/teams/environment-climate-change-and-health/air-quality-and-health/health-impacts/types-of-pollutants"
# fuente verificada el 2026-11-10: https://www.who.int/news-room/questions-and-answers/item/who-global-air-quality-guidelines
OMS_DIAS_EXCEDENCIA_24H = (3, 4)
# fuente verificada el 2026-11-10: los días de excedencia OMS se expresan por año.
DIAS_ANO_REFERENCIA = 365
# fuente verificada el 2026-11-10: https://www.who.int/publications/i/item/9789240034228
OMS_ANIO_GUIA = 2021
OMS_PM25_ANUAL = 5
OMS_PM25_24H = 15
OMS_PM10_ANUAL = 15
OMS_PM10_24H = 45
# fuente verificada el 2026-11-10: https://www.minambiente.gov.co/wp-content/uploads/2021/10/Resolucion-2254-de-2017.pdf
URL_RESOLUCION_2254 = "https://www.minambiente.gov.co/wp-content/uploads/2021/10/Resolucion-2254-de-2017.pdf"
# fuente verificada el 2026-11-10: Resolución 2254 de 2017, Tabla 1 y parágrafo 1 del artículo 2.
COLOMBIA_ANIO_RESOLUCION = 2017
COLOMBIA_ANIO_INICIO_NORMA = 2018
COLOMBIA_ANIO_FIN_NORMA = 2029
COLOMBIA_FECHA_INICIO_24H = "2018-07-01"
COLOMBIA_PM25_ANUAL_2018_2029 = 25
COLOMBIA_PM25_24H_2018_2029 = 37
COLOMBIA_PM10_ANUAL_2018_2029 = 50
COLOMBIA_PM10_24H_2018_2029 = 75
# fuente verificada el 2026-11-10: Resolución 2254 de 2017, Tabla 2 (vigente desde 2030).
COLOMBIA_PM25_ANUAL_2030 = 15
COLOMBIA_PM10_ANUAL_2030 = 30
# fuente verificada el 2026-11-10: Resolución 2254 de 2017, Tabla 4.
COLOMBIA_PM25_PREVENCION = "38–55"
COLOMBIA_PM25_ALERTA = "56–150"
COLOMBIA_PM25_EMERGENCIA = "≥151"
# fuente verificada el 2026-11-10: Resolución 2254 de 2017, parágrafo 2 del artículo 2.
EVALUACION_NORMATIVA_POR_ESTACION = True
# fuente verificada el 2026-11-10: indicador SDA promedio anual PM2.5 por estación.
DIAS_MINIMOS_PROMEDIO_ANUAL = 274
URL_FICHA_274_DIAS = "https://oab.ambientebogota.gov.co/indicadores/?id=f62a2070-a6f0-11eb-bab2-0d17a53c0ac6"
# fuente verificada el 2026-11-10: https://www.ambientebogota.gov.co/es/historial-de-noticias/-/asset_publisher/VqEYxdh9mhVF/content/inversion-termica-que-es-y-cual-es-su-relacion-con-la-calidad-del-aire
URL_INVERSION_TERMICA_SDA = "https://www.ambientebogota.gov.co/es/historial-de-noticias/-/asset_publisher/VqEYxdh9mhVF/content/inversion-termica-que-es-y-cual-es-su-relacion-con-la-calidad-del-aire"
# fuente verificada el 2026-11-10: https://oab.ambientebogota.gov.co/operativos-viales-en-bogota/
URL_FACTORES_INTERNOS_EXTERNOS_SDA = "https://oab.ambientebogota.gov.co/operativos-viales-en-bogota/"
# fuente verificada el 2026-11-10: Circular 006 de 2026 IDIGER, basada en la caracterización climatológica distrital e IDEAM.
URL_REGIMEN_LLUVIA_BOGOTA = "https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?dt=S&i=193754"
# fuente verificada el 2026-11-10: https://www.ideam.gov.co/documents/21021/418894/Caracter%C3%ADsticas+de+Ciudades+Principales+y+Municipios+Tur%C3%ADsticos.pdf
URL_CLIMA_IDEAM = "https://www.ideam.gov.co/documents/21021/418894/Caracter%C3%ADsticas+de+Ciudades+Principales+y+Municipios+Tur%C3%ADsticos.pdf/c3ca90c8-1072-434a-a235-91baee8c73fc"
# fuente verificada el 2026-11-10: https://www.who.int/news-room/questions-and-answers/item/who-global-air-quality-guidelines
TEXTO_SALUD_OMS = "Superar los valores guía de la OMS se asocia con riesgos graves para la salud pública."
# fuente verificada el 2026-11-10: página institucional del Distrito, comunicado del 5 de febrero de 2026.
URL_COMUNICADO_RED_2026 = "https://bogota.gov.co/mi-ciudad/ambiente/en-bogota-se-monitorea-calidad-del-aire-en-dia-sin-carro-y-sin-moto"

# fuente consultada el 2026-11-11: IDEAM, hoja metodológica ICA; reproduce los rangos del art. 20, Tabla 6 de la Resolución 2254 de 2017.
URL_IDEAM_ICA_24H = "https://bart.ideam.gov.co/indiecosistemas/ind/aire/hm/1.%20HM%20Indice%20calidad%20aire.pdf"
ICA_24H_PM = [
    {"ICA": "0–50", "Categoría": "Buena", "Color": "Verde", "PM2.5 24 h (µg/m³)": "0–12", "PM10 24 h (µg/m³)": "0–54"},
    {"ICA": "51–100", "Categoría": "Aceptable", "Color": "Amarillo", "PM2.5 24 h (µg/m³)": "13–37", "PM10 24 h (µg/m³)": "55–154"},
    {"ICA": "101–150", "Categoría": "Dañina a grupos sensibles", "Color": "Naranja", "PM2.5 24 h (µg/m³)": "38–55", "PM10 24 h (µg/m³)": "155–254"},
    {"ICA": "151–200", "Categoría": "Dañina a la salud", "Color": "Rojo", "PM2.5 24 h (µg/m³)": "56–150", "PM10 24 h (µg/m³)": "255–354"},
    {"ICA": "201–300", "Categoría": "Muy dañina", "Color": "Púrpura", "PM2.5 24 h (µg/m³)": "151–250", "PM10 24 h (µg/m³)": "355–424"},
    {"ICA": "301–500", "Categoría": "Peligrosa", "Color": "Marrón", "PM2.5 24 h (µg/m³)": "251–500", "PM10 24 h (µg/m³)": "425–604"},
]
# Colores por categoría que aparecen en la tabla de referencia ICA de IDEAM.
COLORES_ICA = {
    "Verde": "#00E400", "Amarillo": "#FFFF00", "Naranja": "#FF7E00",
    "Rojo": "#FF0000", "Púrpura": "#8F3F97", "Marrón": "#7E0023",
}
NOTA_ERRATA_IDEAM_ICA = (
    "El límite inferior de 56 µg/m³ para PM2.5 en 'Dañina a la salud' coincide con el nivel de alerta "
    "de la Tabla 4 de la misma resolución; el PDF del IDEAM trae una errata (16-150)."
)
TEXTO_PRESENTACION_ICA_24H = (
    "Puntos de corte de 24 h para PM2.5 y PM10 por rango del ICA, según artículo 20, Tabla 6 "
    "de la Resolución 2254 de 2017."
)
TEXTO_MAPA_ICA_CONTINUA = (
    "La escala del mapa muestra concentraciones de forma continua y no asigna categorías ICA. "
    "La tabla oficial de puntos de corte está en Contexto."
)
TEXTO_DATOS_ICA = "Los puntos de corte oficiales del ICA de 24 horas se presentan en la página Contexto."

# fuente indicada y consultada el 2026-11-11: ficha de la SDS; la versión /2026/03 y su página oficial están accesibles.
URL_SALUD_PM25_AIRQ = "https://saludata.saludcapital.gov.co/osb/wp-content/uploads/2026/04/OSB_MortalidadAtribuible_PM2.5.pdf"
URL_SALUD_PM25_FICHA_ACCESIBLE = "https://saludata.saludcapital.gov.co/osb/wp-content/uploads/2026/03/OSB_MortalidadAtribuible_PM2.5.pdf"
TEXTO_METODOLOGIA_SALUD_PM25 = (
    "Metodología de la Secretaría Distrital de Salud: AirQ+ de la OMS; compara el promedio anual de PM2.5 "
    "con el nivel guía de 5 µg/m³; serie 2018–2024; ficha del 25/07/2025."
)
RIESGOS_RELATIVOS_PM25 = [
    {"Evento": "Causas naturales", "Riesgo relativo (IC 95 %)": "1,08 (1,06–1,09)"},
    {"Evento": "Cardiovasculares", "Riesgo relativo (IC 95 %)": "1,11 (1,09–1,14)"},
    {"Evento": "Respiratorias", "Riesgo relativo (IC 95 %)": "1,10 (1,03–1,18)"},
]
NOTA_INTERPRETACION_SALUD_PM25 = (
    "Estos riesgos son estimaciones poblacionales de un modelo de la OMS, no resultados de este proyecto, "
    "y no implican que la concentración de un día concreto cause un efecto individual."
)

FUENTES = [
    {"nombre": "Estaciones y ficha oficial RMCAB · SDA", "url": URL_ESTACIONES_SDA},
    {"nombre": "Población Bogotá 2025 · Secretaría Distrital de Salud / DANE", "url": "https://www.saludcapital.gov.co/Documents/Brief_Determinantes_Sociales_Bogota.pdf"},
    {"nombre": "Red RMCAB y microsensores · comunicado distrital", "url": URL_COMUNICADO_RED_2026},
    {"nombre": "Guías globales de calidad del aire 2021 · OMS", "url": URL_GUIAS_OMS},
    {"nombre": "Frecuencia asociada al percentil 99 de la guía 24 h · OMS", "url": "https://www.who.int/news-room/questions-and-answers/item/who-global-air-quality-guidelines"},
    {"nombre": f"Resolución 2254 de {COLOMBIA_ANIO_RESOLUCION} · MinAmbiente", "url": URL_RESOLUCION_2254},
    {"nombre": "Indicador de PM2.5 promedio anual por estación · SDA", "url": URL_FICHA_274_DIAS},
    {"nombre": "Inversión térmica · SDA", "url": URL_INVERSION_TERMICA_SDA},
    {"nombre": "Factores internos y externos de la calidad del aire · SDA", "url": URL_FACTORES_INTERNOS_EXTERNOS_SDA},
    {"nombre": "Régimen bimodal de lluvias de Bogotá · IDIGER / referencia IDEAM", "url": URL_REGIMEN_LLUVIA_BOGOTA},
    {"nombre": "Características climatológicas de ciudades · IDEAM", "url": URL_CLIMA_IDEAM},
    {"nombre": "Puntos de corte ICA de 24 h · IDEAM / Resolución 2254 de 2017, art. 20, Tabla 6", "url": URL_IDEAM_ICA_24H, "fecha_consulta": "2026-11-11"},
    {"nombre": "Mortalidad atribuida a exposición de largo plazo a PM2.5 · SDS, ficha técnica AirQ+", "url": URL_SALUD_PM25_AIRQ, "fecha_consulta": "2026-11-11"},
    {"nombre": "Ficha técnica oficial accesible · SaluData / SDS", "url": URL_SALUD_PM25_FICHA_ACCESIBLE, "fecha_consulta": "2026-11-11"},
]
