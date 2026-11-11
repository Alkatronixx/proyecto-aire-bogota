# Aire de Bogotá: PM2.5, PM10 y meteorología

Proyecto de análisis de las mediciones diarias de material particulado de la RMCAB y de variables meteorológicas del IDEAM. Integra datos, diagnósticos descriptivos, modelos de referencia y una aplicación interactiva. Los resultados describen asociaciones y desempeño predictivo; no atribuyen causalidad.

## Aplicación desplegada

[Abrir la aplicación en Streamlit Community Cloud](https://proyecto-aire-bogota-kubjcjrb8nbwjmt6th9x9b.streamlit.app)

## Pregunta y público

El proyecto pregunta cómo varía el PM2.5 con el viento, la lluvia, la temperatura, el calendario y la ubicación, y cuánto cambian las predicciones en escenarios definidos por el usuario. Está pensado para apoyar la exploración de autoridades ambientales y ciudadanos; no reemplaza una evaluación oficial de calidad del aire ni es una herramienta de atribución causal.

## Datos

Los insumos de calidad del aire y viento provienen de la Red de Monitoreo de Calidad del Aire de Bogotá (RMCAB); precipitación y temperaturas provienen de archivos IDEAM DHIME. La humedad relativa queda como exploración y no entra al modelo. La procedencia y las transformaciones se documentan en [data/docs/fuentes.md](data/docs/fuentes.md), y las reglas de cada campo están en [data/docs/diccionario_datos.md](data/docs/diccionario_datos.md).

La tabla maestra `data/processed/aire_bogota_diario.parquet` tiene **20.824 filas**, **37 columnas**, grano estación-día y periodo **2023-10-24 a 2026-10-23**. Corresponde a 19 estaciones a lo largo de 1.096 días calendario. El hueco de PM2.5 y PM10 entre **2025-08-04 y 2025-10-16** comprende **74 días**, aparece en la fuente y permanece como faltante; no se interpola ni se presenta como una caída de concentración durante esos días. La decisión y su validación están descritas en [docs/decisiones.md](docs/decisiones.md).

## Hallazgos y modelos

La comparación explicativa v2 usa climatología por estación y mes como referencia y modela anomalías. En prueba, el MAE de climatología fue **5,490 µg/m³**; con Ridge fue **5,393**, una mejora aproximada de **1,8 %**. Random Forest obtuvo **5,386** y HistGradientBoosting **5,221** de MAE; este último tuvo el menor error de prueba, mientras que el Ridge publicado se seleccionó por validación cruzada temporal dentro del entrenamiento. Las métricas completas están en [documentación de datos y modelo](docs/documentacion_datos_y_modelo.md).

El diagnóstico de alineación no encontró un desfase meteorológico uniforme: los máximos absolutos de Spearman fueron **0,11** para lluvia y **0,16** para temperatura. Desplazar las variables IDEAM un día mejoró el MAE en **0,044 µg/m³** (de 5,441 a 5,397 en 5.258 filas); se conserva la alineación original. La caída de PM2.5 entre entrenamiento y prueba se observa en las estaciones, pero los datos disponibles no determinan su causa. Las cifras de alineación están centralizadas en [app/utils/cifras_modelo.py](app/utils/cifras_modelo.py).

En la comparación predictiva de 5.170 filas, Ridge obtuvo MAE **3,332 µg/m³** y el Random Forest de comparación **3,223**. El artefacto predictivo publicado es Ridge, seleccionado mediante validación temporal dentro del entrenamiento; no se afirma que ganara en el MAE de prueba. El Simulador usa el Ridge de anomalías v2 y su climatología e intervalo guardados.

## Páginas de la aplicación

- **Portada:** indicadores generales, mapa de estaciones y asociaciones descriptivas.
- **Contexto:** red de monitoreo, referencias normativas y puntos de corte del ICA.
- **Mapa:** explora concentraciones y cobertura por estación y rango de fechas.
- **Factores:** compara patrones de viento, lluvia, temperatura, calendario y ubicación.
- **Simulador:** compara escenarios con predicciones del modelo de anomalías.
- **Modelo:** describe la partición temporal, métricas y diagnósticos del modelo.
- **Datos y metodología:** fuentes, cobertura, decisiones e incidentes de calidad.

## Estructura del repositorio

```text
app/                 Aplicación Streamlit, páginas, componentes y estilos
data/docs/           Fuentes y diccionario de datos
data/processed/      Tabla maestra, catálogos y resultados publicados para la app
docs/                Decisiones, informes y documentación del proyecto
models/              Artefactos de modelos publicados
src/datos/           Limpieza, integración y preparación de datos
src/modelo/          Entrenamiento y diagnóstico de modelos
tests/               Pruebas de datos, modelos y páginas
```

## Ejecución local

Desde la raíz del repositorio, en PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app/app.py
```

Para instalar las herramientas de desarrollo y ejecutar las pruebas:

```powershell
python -m pip install -r requirements-dev.txt
pytest -q
```

### Regenerar datos y modelo

Los scripts reales del flujo están en `src/datos/` y `src/modelo/`. Desde la raíz, el orden previsto para reconstruir los productos es:

```powershell
python src/datos/limpiar_aire.py
python src/datos/limpiar_viento.py
python src/datos/limpiar_ideam.py
python src/datos/viento_ciudad.py
python src/datos/asignar_estaciones.py
python src/datos/construir_maestra.py
python src/datos/preparar_geometrias_app.py
python src/modelo/entrenar_v2.py
```

Los limpiadores leen los archivos originales y escriben productos en `data/interim/` y `data/processed/`; `entrenar_v2.py` actualiza predicciones, diagnósticos y el artefacto v2. Estos scripts no exponen una opción `--dry-run`. Se comprobaron la existencia, sintaxis y función `main` de los ocho scripts de la secuencia mediante lectura estática. Antes de reconstruir, respalda o prepara una copia de trabajo para los productos que se van a reemplazar. No se ejecutaron aquí porque esta revisión prohíbe modificar `data/interim/`, productos existentes y modelos.

## Limitaciones conocidas

- El hueco de 74 días de PM está en la fuente original; no se rellena.
- El PM2.5 del periodo de prueba es menor que el del entrenamiento y no se ha determinado por qué.
- La precipitación de varias estaciones de aire comparte una fuente IDEAM; el viento usado por el modelo es un índice de ciudad.
- El diagnóstico de desfase no confirma una alineación alternativa uniforme.
- La mejora del Ridge de anomalías frente a climatología es pequeña; los patrones descriptivos y las predicciones no identifican efectos causales.
- Los años inicial y final del periodo tienen cobertura parcial.

## Fuentes oficiales

- [Red de Monitoreo de Calidad del Aire de Bogotá (RMCAB) · SDA](https://www.ambientebogota.gov.co/es/red-de-monitoreo-de-calidad-del-aire-de-bogota-rmcab)
- [Estaciones de la RMCAB · SDA](https://www.ambientebogota.gov.co/es/web/sda/estaciones-rmcab)
- [Portal de consulta y descarga de datos hidrometeorológicos · IDEAM DHIME](https://www.dhime.ideam.gov.co/atencionciudadano/)
- [Índice de Calidad del Aire · hoja metodológica IDEAM](https://bart.ideam.gov.co/indiecosistemas/ind/aire/hm/1.%20HM%20Indice%20calidad%20aire.pdf)
- [Resolución 2254 de 2017 · MinAmbiente](https://www.minambiente.gov.co/wp-content/uploads/2021/10/Resolucion-2254-de-2017.pdf)
- [Mortalidad atribuida a exposición de largo plazo a PM2.5 · SaluData/SDS](https://saludata.saludcapital.gov.co/osb/indicadores/mortalidad-calidad-aire/)
- [Documentación y análisis del proyecto](docs/fuentes.md), [fuentes de datos](data/docs/fuentes.md) y [diccionario](data/docs/diccionario_datos.md).

## Equipo y curso

- Equipo: Sergio Fuentes, Samuel Alcala, Camilo Lamprea, Daniel Fonseca, Cristian Ortiz
- Curso / Universidad: Ciencia de Datos - Universidad UADE

## Licencia y uso de datos

No se encontró una licencia general del repositorio; este README no asigna una. Los datos se atribuyen a sus fuentes institucionales, la RMCAB/SDA e IDEAM. Al reutilizarlos, conserva la cita de la fuente original y revisa las condiciones de uso publicadas por cada entidad. Los archivos originales y los productos del proyecto pueden tener condiciones distintas.
