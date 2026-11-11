"""Centraliza cifras de contexto y sus fuentes oficiales verificadas.
La página Contexto importa estas constantes para evitar números sueltos en la UI.
Incluye el contenido de las normas y las URLs de las entidades citadas.
Fuentes consultadas el 2026-11-10; los estadísticos de la red del proyecto se calculan aparte.
"""

# fuente verificada el 2026-11-10: https://www.saludcapital.gov.co/Documents/Brief_Determinantes_Sociales_Bogota.pdf
POBLACION_BOGOTA_2025 = 7_937_898
# fuente verificada el 2026-11-10: https://bogota.gov.co/mi-ciudad/ambiente/en-bogota-se-monitorea-calidad-del-aire-en-dia-sin-carro-y-sin-moto
ESTACIONES_SDA = 19
MICROSENSORES_SDA = 70
# fuente verificada el 2026-11-10: https://ambientebogota.gov.co/es/web/sda/estaciones-rmcab
URL_ESTACIONES_SDA = "https://ambientebogota.gov.co/es/web/sda/estaciones-rmcab"
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
]
