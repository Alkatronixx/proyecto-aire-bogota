# Auditoría de la app antes de desplegar

**Fecha:** 2026-11-10
**Alcance:** auditoría de solo lectura; el único archivo nuevo de esta tarea es este informe.
**Raíz:** `proyecto-aire-bogota`.

## Resumen ejecutivo

**No recomiendo desplegar todavía.** El venv limpio no pudo ejecutar tests porque falta `pytest` en `requirements.txt`. Hay módulos y datos necesarios para Contexto, Simulador y mapas que existen localmente pero Git no versiona. Portada y Simulador superaron ampliamente 5 s en la primera medición AppTest. No se pudo obtener un pico de memoria válido tras visitar todas las páginas; por eso no certifico el límite de 800 MB.

## 1. Entorno limpio, tests y versiones

Creé el venv fuera del repo en `D:\ciencia de datos\.venvs\auditoria_app_20261110` e instalé **solo** `requirements.txt`. Versiones observadas:

| Paquete | Versión |
|---|---:|
| Python | 3.15.2 |
| streamlit | 1.67.0 |
| pandas | 3.1.1 |
| numpy | 2.5.4 |
| plotly | 7.1.0 |
| pydeck | 0.9.3 |
| scikit-learn | 1.9.1 |
| joblib | 1.6.0 |
| pyarrow | 26.0.1 |
| shapely | 2.2.0 |
| pyproj | 3.8.0 |

Las diez dependencias están fijadas con `==`. Streamlit 1.67.0 supera el mínimo 1.60 pedido. `AGENTS.md` declara Python 3.11; la máquina no tenía Python 3.11 y la prueba quedó en Python 3.15.2.

`python -m pytest -q` en el venv limpio falló al iniciar:

```
D:\ciencia de datos\.venvs\auditoria_app_20261110\Scripts\python.exe: No module named pytest
```

**Paquete faltante confirmado:** `pytest`. No instalé paquetes adicionales. La suite no se ejecutó.

Con scikit-learn 1.9.1 cargué `modelo_anomalia_v2.joblib` (dict), `modelo_predictivo.joblib` (Pipeline) y el archivo local ignorado `modelo_explicativo.joblib` (Pipeline). Los tres cargaron sin advertencias de incompatibilidad en esa versión. Esto acredita compatibilidad con la versión probada, no una metadata independiente de la versión usada al guardar. `app/utils/datos.py:127-129` carga solo el modelo v2.

AppTest directo sobre los siete archivos de página, en este orden, acabó sin excepciones:

| Página | Tiempo | Excepciones |
|---|---:|---:|
| Portada | 40,64 s | 0 |
| Contexto | 0,72 s | 0 |
| Mapa | 0,34 s | 0 |
| Factores | 0,75 s | 0 |
| Simulador | 53,57 s | 0 |
| Modelo | 0,59 s | 0 |
| Datos y metodología | 0,76 s | 0 |

Se observaron avisos deprecados de `use_container_width` y un aviso de estado/valor inicial duplicado de widget en Simulador.

**Arranque headless:** lancé Streamlit y el endpoint local `/_stcore/health` respondió `ok`; tiempo medido hasta health: **5,35 s**. El proceso que atendía la app usaba **89,8 MB RSS** y 76,7 MB de memoria privada en esa lectura. Intenté medir el pico al abrir todas las páginas desde AppTest, pero el instrumento no devolvió muestras y se detuvo; el pico de memoria queda **sin verificar**, no concluyo que esté bajo 800 MB.

## 2. Rutas e importaciones

- Sin coincidencias de rutas locales absolutas `D:\`, `C:\` o `/Users` en código/CSS de `app/`.
- Sin accesos ejecutables a `data/raw`, `data/interim` o `src/`. La única coincidencia de `data/raw` es texto de comentario en `app/utils/datos.py:58`.
- Lecturas a través de rutas basadas en `Path(__file__).resolve()`: `app/app.py:10`, `app/components/ui.py:8-9` y `app/utils/datos.py:12,51,62,86,95,104,110,122,129`. No hallé lecturas que dependan del directorio de trabajo.
- `app/pages/contexto.py:69` tiene una URL externa de mapa base; no es una ruta local.

## 3. Git y archivos

`git ls-files` muestra **122 archivos**; el inventario completo con tamaño en bytes está en el Apéndice A. No hay archivos versionados mayores de 25 MB.

| Ruta | Existe | Git la versiona | Tamaño |
|---|---:|---:|---:|
| `data/processed/aire_bogota_diario.parquet` | Sí | Sí | 217.204 B |
| `data/processed/geo/` | Sí | **No** | directorio |
| `data/processed/app/` | Sí | Sí, archivos rastreados | varios |
| `models/modelo_anomalia_v2.joblib` | Sí | Sí | 5.183 B |
| `.streamlit/config.toml` | Sí | Sí | 193 B |
| `app/assets/style.css` | Sí | Sí | 2.022 B |
| `requirements.txt` | Sí | Sí | 152 B |
| `models/modelo_explicativo.joblib` | Sí, local | **No** | 51.842.433 B |

El RF explicativo local mide 51.842.433 B y está ignorado por `.gitignore:11`; `git ls-files` confirma que no está versionado.

**Falta empaquetado para despliegue desde Git:** están sin rastrear `app/utils/contexto.py`, `app/utils/fuentes_contexto.py`, `app/utils/simulador.py`, `app/utils/cifras_modelo.py` y `data/processed/geo/{estaciones.geojson,localidades.geojson,estaciones_rmcab_ficha.csv}`. Son módulos importados o entradas de datos de páginas activas. Funcionan en este workspace porque existen localmente, pero no viajarán en un checkout/versionado. Los CSV de diagnóstico de alineación que están sin rastrear no aparecen entre las lecturas de app. Los archivos de `data/processed/app/` declarados en `rutas_lectura_app()` sí están versionados.

## 4. Rendimiento

Arranque en frío hasta health: **5,35 s**. Render AppTest medido: Portada **40,64 s**, Contexto **0,72 s**, Mapa **0,34 s**, Factores **0,75 s**, Simulador **53,57 s**, Modelo **0,59 s**, Datos y metodología **0,76 s**. Portada y Simulador incumplen el umbral de 5 s. Son renders directos por AppTest, no navegación de navegador con cachés calientes.

Memoria: medida inicial del proceso servidor **89,8 MB RSS**; pico tras visitar todas las páginas sin medición válida. Debe repetirse esa medición antes de declarar cumplimiento de 800 MB.

## 5. Cifras literales en `app/`

`docs/documentacion_datos_y_modelo.md` **no existe**, así que la comprobación cruzada solo pudo hacerse contra `docs/decisiones.md`. “No aparece allí” no implica que sea falsa. La tabla enumera cifras y parámetros escritos manualmente que afectan el texto, ventanas de análisis o interpretación; excluye números de diseño CSS, RGB, índices y métricas calculadas/leídas de datos.

| Archivo:línea | Literal o parámetro | Comparación/observación |
|---|---|---|
| `app/pages/contexto.py:104-105` | 3–4 días/año; literal `365` en anotación | 3–4 procede de `fuentes_contexto.py`; `365` se repite fuera del módulo de fuentes, aunque la fórmula también usa su constante. |
| `app/pages/contexto.py:129` | Diámetros `2,5` y `10` micrómetros | Definición mostrada como texto fuera de `fuentes_contexto.py`. |
| `app/pages/datos_metodologia.py:80-85` | `19`, `11 de 19`, `97%`, años `2023`/`2026`, `20` estaciones | 19, 11/19 y 97% constan en decisiones; años derivables de datos. `20`/Bosa no aparece en decisiones ni como constante en el módulo de fuentes. |
| `app/pages/factores.py:16-20` | Fechas de partición/hueco, semilla `42`, `200` réplicas | Fechas documentadas; semilla y réplicas son parámetros no registrados en decisiones. |
| `app/pages/factores.py:68-69,124` | Cuantiles `0,025`/`0,975`, mínimo `30` pares | Parámetros analíticos que no aparecen en decisiones. |
| `app/pages/factores.py:196` | Diferencia de altitud `550 m` | Diverge de `docs/decisiones.md:168`, que dice aproximadamente `500 m`. Revisar fuente y uniformar. |
| `app/pages/modelo.py:23-28,45,111,115,144` | Fechas train/test/hueco, mínimo climatológico `10`, hora `7:00`, `12` variables | Fechas/corte constan en decisiones; regla climatológica y hora IDEAM no constan allí. `12` describe el artefacto. |
| `app/pages/portada.py:27,31,36,52-60,79-84,94` | Multiplicador `100`, ventana `12` meses, coordenadas/zoom y fechas de hueco, cuantiles `0,25`/`0,75` | El periodo/hueco se deriva o documenta; layout, coordenadas y cuantiles son configuración, no cifras normativas. |
| `app/pages/mapa.py:16-20,100,120` | Periodo, fechas del hueco y cobertura baja `0,50` | Fechas están documentadas; umbral 50% no aparece en decisiones. |
| `app/pages/portada.py:60,82-83` | Centro/zoom visual y fechas del hueco | Fechas documentadas; coordenadas/zoom son configuración cartográfica. |
| `app/pages/datos_metodologia.py:42,48,50-56` | Escala 0–100%, saltos del eje y hueco agosto–octubre 2025 | Porcentajes/datos y hueco; parámetros gráficos. |
| `app/utils/simulador.py:10,47-48,55,81,112,125,154,174-179,196-198,224,238-247` | Corte entrenamiento/prueba; p1/p99 y p10/p90; mínimo `10`; lluvia `1 mm`; día `5`; suelo `0` | Partición documentada; reglas de interfaz/modelado no aparecen en decisiones. |
| `app/utils/cifras_modelo.py:6-17` | Rho 0,11/0,16; n=5.258; MAE 5,441/5,397; diferencia 0,044 | Con comentario de fuente “diagnostico_alineacion, validado el 2026-11-10”; no está en decisiones. |
| `app/utils/fuentes_contexto.py:7-47,59-69` | Cifras de población, red, OMS, norma, años y 274 días | Centralizadas en el módulo con fuentes/enlaces verificados. Algunas no figuran en decisiones, pero sí cumplen la regla de centralizar las cifras contextuales. |

Cifras normativas/de OMS/población se importan desde `fuentes_contexto.py`, con estas excepciones de presentación: los diámetros 2,5/10 y el literal 365 están escritos en `contexto.py`; el conteo 20/Bosa está escrito en `datos_metodologia.py:85`. Conviene centralizarlos para que la regla sea comprobable. El número 550 m también necesita conciliación con la documentación (500 m).

## 6. Lenguaje y cifras de contexto

La búsqueda de `causa`, `provoca`, `reduce`, `aumenta` y `genera` no encontró afirmaciones causales con esos verbos. Apariciones revisables:

- `app/pages/datos_metodologia.py:80`: “la causa no está determinada” es uso nominal, no atribuye una causa.
- En Factores/Modelo se habla de “relaciones causales” o “causalidad” para negar que el análisis las demuestre.

No vi una cifra literal de OMS/norma/población fuera de `fuentes_contexto.py` salvo los literales de diámetros y 365 señalados arriba; 20 estaciones/Bosa es una cifra de red que también conviene centralizar. Las métricas y resúmenes de observaciones en otras páginas proceden de datos/CSV.

## 7. Calidad

- `TODO`: uno en `app/components/paleta.py:16`, los puntos de corte quedan pendientes de fuente oficial.
- `FIXME`: ninguno.
- “en construcción”: ninguna página activa presenta ese aviso. Docstring obsoleta en `app/app.py:1-4` dice que páginas no desarrolladas muestran aviso.
- Excepciones: `app/pages/contexto.py:67-73` captura solo `StreamlitPageNotFoundError` y usa un enlace alternativo explícito para AppTest aislado; no silencia el error. No encontré `except:` ni `except Exception`.
- Gráfico sin título general: composición “La caída de nivel”, `app/pages/factores.py:230-242`; `update_layout` no le asigna título.
- Ejes: los demás gráficos revisados indican unidad física o porcentaje. En caída de nivel, `factores.py:241` pone solo `µg/m³` sin nombrar PM2.5/PM10 en el eje; título de sección da contexto, pero el eje queda ambiguo. Cronología `modelo.py:98-109` es categórica y no necesita unidad.
- Avisos de Streamlit: múltiples `use_container_width` deprecados y el estado/valor inicial redundante en widget del Simulador.

## 8. Priorización

### Bloqueantes para desplegar

1. Versionar los cuatro módulos utilitarios y los tres recursos de `data/processed/geo/`; hoy faltan en el checkout Git aunque la app los importa/lee.
2. Declarar `pytest` en dependencias de CI/desarrollo y repetir la suite limpia; actualmente no pudo iniciarse.
3. Investigar Portada y Simulador, medidos en 40,64 s y 53,57 s frente al máximo indicado de 5 s.

### Importantes

1. Obtener pico de memoria reproducible tras visitar las siete páginas; 89,8 MB es solo el servidor inicial.
2. Repetir pruebas bajo Python 3.11 conforme a `AGENTS.md`; solo se encontró Python 3.15.2.
3. Resolver 550 m vs. aproximadamente 500 m y centralizar las cifras de tamaños 2,5/10, 365 y 20 estaciones.
4. Revisar arranque frío de 5,35 s si el objetivo de despliegue requiere inicio más rápido.

### Menores

1. Poner título al gráfico de caída y etiquetar PM2.5/PM10 en el eje.
2. Actualizar `use_container_width` y corregir el estado inicial duplicado del widget.
3. Actualizar la docstring obsoleta de `app/app.py`.

## Apéndice A. Inventario versionado

Tamaños de archivos en bytes según el checkout y `git ls-files`; excluye archivos ignorados y sin rastrear.

| Bytes | Ruta |
|---:|---|
| 192 | `.gitignore` |
| 193 | `.streamlit/config.toml` |
| 7,775 | `AGENTS.md` |
| 0 | `README.md` |
| 71 | `app/__init__.py` |
| 1,370 | `app/app.py` |
| 0 | `app/assets/.gitkeep` |
| 2,022 | `app/assets/style.css` |
| 0 | `app/components/.gitkeep` |
| 67 | `app/components/__init__.py` |
| 2,629 | `app/components/paleta.py` |
| 1,202 | `app/components/tema_graficos.py` |
| 1,920 | `app/components/ui.py` |
| 0 | `app/pages/.gitkeep` |
| 66 | `app/pages/__init__.py` |
| 16,179 | `app/pages/contexto.py` |
| 4,484 | `app/pages/datos_metodologia.py` |
| 18,915 | `app/pages/factores.py` |
| 12,401 | `app/pages/mapa.py` |
| 19,124 | `app/pages/modelo.py` |
| 6,298 | `app/pages/portada.py` |
| 13,387 | `app/pages/simulador.py` |
| 69 | `app/utils/__init__.py` |
| 7,312 | `app/utils/datos.py` |
| 6,904 | `data/docs/decisiones.md` |
| 7,876 | `data/docs/diccionario_datos.md` |
| 750 | `data/docs/fuentes.md` |
| 0 | `data/interim/.gitkeep` |
| 0 | `data/processed/.gitkeep` |
| 217,204 | `data/processed/aire_bogota_diario.parquet` |
| 404 | `data/processed/app/ablacion.csv` |
| 22,300 | `data/processed/app/cobertura_estacion_mes.csv` |
| 2,919 | `data/processed/app/coeficientes_ridge.csv` |
| 17,967 | `data/processed/app/correlaciones_spearman.csv` |
| 2,490 | `data/processed/app/dependencia_parcial.csv` |
| 2,805 | `data/processed/app/diagnostico_modelo_2_auditoria_filtraciones.csv` |
| 291 | `data/processed/app/diagnostico_modelo_2_comparacion_climatologia_misma_prueba.csv` |
| 1,765 | `data/processed/app/diagnostico_modelo_2_comparacion_meses_iguales.csv` |
| 6,581 | `data/processed/app/diagnostico_modelo_2_medias_estacion_pre_post_hueco.csv` |
| 658 | `data/processed/app/diagnostico_modelo_2_pm10_mes_anio.csv` |
| 662 | `data/processed/app/diagnostico_modelo_2_pm25_mes_anio.csv` |
| 1,513 | `data/processed/app/diagnostico_modelo_2_pm25_semanal_ciudad.csv` |
| 1,208 | `data/processed/app/diagnostico_modelo_2_razon_mediana_estacion_antes_despues.csv` |
| 689 | `data/processed/app/diagnostico_modelo_2_razon_mediana_mes_anio.csv` |
| 1,079 | `data/processed/app/diagnostico_modelo_2_retorno_estacion_hueco.csv` |
| 1,280 | `data/processed/app/diagnostico_modelo_2_rf_guardado_sesgo_mae_estacion.csv` |
| 1,253 | `data/processed/app/diagnostico_modelo_2_rf_temporal_sesgo_mae_estacion.csv` |
| 235 | `data/processed/app/diagnostico_modelo_ablacion_v2.csv` |
| 2,670 | `data/processed/app/diagnostico_modelo_carvajal_mensual_v2.csv` |
| 613 | `data/processed/app/diagnostico_modelo_cobertura_estacion_v2.csv` |
| 2,860 | `data/processed/app/diagnostico_modelo_dependencia_parcial_v2.csv` |
| 1,338 | `data/processed/app/diagnostico_modelo_mae_estacion_v2.csv` |
| 1,568 | `data/processed/app/diagnostico_modelo_medias_estacion_v2.csv` |
| 424 | `data/processed/app/diagnostico_modelo_metricas_v2.csv` |
| 141 | `data/processed/app/diagnostico_modelo_permutacion_grupos_v2.csv` |
| 1,207 | `data/processed/app/diagnostico_modelo_sesgo_estacion_v2.csv` |
| 12,642 | `data/processed/app/diagnostico_modelo_simulador_v2.csv` |
| 104 | `data/processed/app/diagnostico_modelo_trimestre_v2.csv` |
| 1,337 | `data/processed/app/diferencia_laboral_fin_semana.csv` |
| 168 | `data/processed/app/importancias_rf.csv` |
| 4,660 | `data/processed/app/metricas_desglosadas.csv` |
| 1,543 | `data/processed/app/metricas_modelos.csv` |
| 128,573 | `data/processed/app/predicciones_prueba.parquet` |
| 195,225 | `data/processed/app/predicciones_prueba_v2.parquet` |
| 3,159 | `data/processed/app/resumen_exploratorio.csv` |
| 4,211 | `data/processed/asignacion_estaciones.csv` |
| 67,362 | `data/processed/cobertura_aire.csv` |
| 35,441 | `data/processed/cobertura_ideam.csv` |
| 3,146 | `data/processed/cobertura_maestra.csv` |
| 49,670 | `data/processed/cobertura_viento.csv` |
| 1,324 | `data/processed/estaciones_ideam.csv` |
| 0 | `data/raw/aire/.gitkeep` |
| 0 | `data/raw/geografia/.gitkeep` |
| 0 | `data/raw/humedad/.gitkeep` |
| 0 | `data/raw/precipitacion/.gitkeep` |
| 0 | `data/raw/temperatura_max/.gitkeep` |
| 0 | `data/raw/temperatura_min/.gitkeep` |
| 0 | `data/raw/trafico_aforos/.gitkeep` |
| 0 | `data/raw/viento/.gitkeep` |
| 0 | `docs/.gitkeep` |
| 6,453 | `docs/asignacion_estaciones_tabla_maestra.md` |
| 23,658 | `docs/decisiones.md` |
| 7,566 | `docs/diagnostico_modelo.md` |
| 17,419 | `docs/diagnostico_modelo_2.md` |
| 2,254 | `docs/diagnostico_rezagos.md` |
| 0 | `docs/fuentes.md` |
| 17,565 | `docs/reporte_ideam.md` |
| 7,947 | `docs/reporte_modelo.md` |
| 0 | `models/.gitkeep` |
| 5,183 | `models/modelo_anomalia_v2.joblib` |
| 5,373 | `models/modelo_predictivo.joblib` |
| 0 | `notebooks/.gitkeep` |
| 152 | `requirements.txt` |
| 0 | `src/__init__.py` |
| 0 | `src/datos/__init__.py` |
| 14,995 | `src/datos/asignar_estaciones.py` |
| 16,191 | `src/datos/construir_maestra.py` |
| 18,208 | `src/datos/diagnostico_aire.py` |
| 23,111 | `src/datos/diagnostico_viento.py` |
| 20,135 | `src/datos/diagnostico_viento_2.py` |
| 23,402 | `src/datos/diagnostico_viento_3.py` |
| 36,754 | `src/datos/limpiar_aire.py` |
| 32,771 | `src/datos/limpiar_ideam.py` |
| 26,038 | `src/datos/limpiar_viento.py` |
| 11,438 | `src/datos/viento_ciudad.py` |
| 0 | `src/modelo/__init__.py` |
| 10,235 | `src/modelo/diagnostico_modelo.py` |
| 18,266 | `src/modelo/diagnostico_modelo_2.py` |
| 14,736 | `src/modelo/entrenar.py` |
| 11,702 | `src/modelo/entrenar_v2.py` |
| 5,344 | `src/modelo/explorar.py` |
| 2,878 | `src/modelo/simular.py` |
| 0 | `src/utils/__init__.py` |
| 0 | `tests/.gitkeep` |
| 6,197 | `tests/test_aire.py` |
| 3,876 | `tests/test_app.py` |
| 2,158 | `tests/test_ideam.py` |
| 2,119 | `tests/test_maestra.py` |
| 1,781 | `tests/test_modelo.py` |
| 1,100 | `tests/test_modelo_v2.py` |
| 2,734 | `tests/test_viento.py` |
| 2,069 | `tests/test_viento_ciudad.py` |

## Seguimiento de despliegue · 2026-11-10

Después de esta auditoría se añadió `pytest==9.2.0` a `requirements.txt` para que el procedimiento indicado pueda instalar el runner junto con las dependencias. Recreé `.venv-prueba` desde cero con ese archivo y la instalación terminó correctamente en Python 3.15.2. La suite con `python -m pytest -q` se mantuvo en cinco casos completados y sin progreso durante más de tres minutos; la interrumpí. El caso aislado de Portada también no terminó en más de 90 s en AppTest. El smoke test real `streamlit run app/app.py` desde ese venv sí devolvió `ok` en `/_stcore/health`.

La instalación de Python 3.11 solicitada para ajustarse a `AGENTS.md` fue rechazada por el control de aprobación; el entorno local continúa en Python 3.15.2. La ejecución en Cloud con Python 3.11 todavía no está validada localmente.


## Correcciones del 2026-11-10

### Antes y después

| Tema | Antes | Después |
|---|---|---|
| Git | La auditoría indicaba que cuatro utilidades y `data/processed/geo/` no estaban versionados. En el estado revisado para esta corrección ya estaban rastreados; `git ls-files --others --exclude-standard` solo mostró `app/utils/portada.py` y `requirements-dev.txt`. | Ejecuté `git add app/utils/contexto.py app/utils/fuentes_contexto.py app/utils/simulador.py app/utils/cifras_modelo.py data/processed/geo/`. Ninguna regla de `.gitignore` coincide con esas rutas. `models/modelo_explicativo.joblib` no está en el índice y no añadí `data/raw`. No hice commit ni push. |
| Dependencias | `pytest`, `shapely` y `pyproj` estaban en `requirements.txt`. | `pytest==9.2.0` y `psutil==7.1.3` quedaron en `requirements-dev.txt`, que incluye `-r requirements.txt`. No encontré importaciones de ejecución de Shapely ni PyProj en `app/`; se quitaron de `requirements.txt`. Todas las dependencias de ejecución siguen fijadas con `==`. El venv limpio usó Python 3.15.2, Streamlit 1.67.0 y scikit-learn 1.9.1. Añadí en `AGENTS.md` que el despliegue use la versión más reciente que ofrezca Streamlit Community Cloud. |
| Carga y agregaciones | Portada y Simulador habían tardado 40,64 s y 53,57 s en la auditoría original. | Añadí `@st.cache_data` al resumen de Portada; datos y agregaciones del Simulador ya usan caché, y el modelo mantiene `@st.cache_resource`. Las expresiones del resumen de Portada se trasladaron sin cambiar sus fórmulas. |
| Carga diferida | `app.py` deserializaba el Ridge aunque Portada no lo usa. | El modelo se carga al abrir Simulador o Modelo y se reutiliza con caché. En AppTest de navegación, la primera Portada bajó de 18,48 s a 10,57 s en una medición; en la medición final fue 11,41 s. La primera apertura de Simulador fue 11,23 s en una medición y 10,18 s en la final; las aperturas calientes quedaron entre 0,06 y 0,25 s. El objetivo AppTest de frío (<10 s) aún se excede levemente en Portada y Simulador; el perfil atribuye la mayor parte a importaciones/carga de `scikit-learn` y esperas internas del runner. |
| Importación en navegación | En un proceso AppTest limpio, `app.py` podía ocultar el paquete `app` y producir `ModuleNotFoundError: 'app' is not a package`; la suite habitual lo ocultaba porque importaba antes `app.utils`. | `app.py` pone la raíz del repositorio antes de `app/` en `sys.path`. La navegación limpia por las siete rutas terminó sin excepciones. |
| Avisos y presentación | Había `use_container_width`, un slider con valor duplicado en Session State, la altitud fija errónea de 550 m y el gráfico de caída no nombraba ambos contaminantes. | Reemplacé el parámetro por `width="stretch"`; los sliders no reciben simultáneamente `value` y estado; la diferencia IDEAM se calcula desde `asignacion_estaciones.csv` y da 510 m; el gráfico ahora tiene título y ejes PM2.5/PM10. Actualicé la docstring de `app.py`. |
| Cifras de contexto | Los diámetros 2,5 y 10, el divisor 365 y el conteo 20/Bosa estaban escritos directamente en páginas. | Están centralizados en `app/utils/fuentes_contexto.py` con referencias y se usan desde Contexto y Datos y metodología. Los textos conservan los valores que ya mostraba la app. |

### Rendimiento medido

El cProfile de Portada se ejecutó en un proceso aparte del de Simulador, ambos con el venv limpio. Portada: 13,26 s en el runner; la importación de pandas ocupó 5,99 s y `time.sleep` del AppTest acumuló 9,35 s. Simulador: 13,59 s en el runner; cargar el `.joblib` y sus importaciones ocupó 7,84 s, incluida la inicialización de scikit-learn (6,62 s). El tiempo de espera del AppTest no equivale a tiempo de cómputo de la página.

Medición independiente por bloques: lectura de `aire_bogota_diario.parquet` 1,539 s; carga del artefacto y scikit-learn 7,406 s; agregaciones cache miss de Portada 0,489 s; estadísticas de entrenamiento del Simulador 0,096 s; predicción 0,140 s; tornado de 12 variables 0,041 s; asignación 0,041 s. La lectura de geometrías tomó 0,013 s (estaciones) y 0,016 s (localidades); Portada y Simulador no consumen geometrías. El bootstrap semanal de 200 réplicas solo se usa en Factores; con caché fría, la página Factores completa tardó 0,855–1,169 s junto con sus gráficos.

En la navegación final AppTest, Portada tardó 11,407 s; Contexto 0,465 s; Mapa 0,185 s; Factores 0,855 s; Simulador 10,184 s; Modelo 0,379 s; Datos y metodología 0,492 s. En caliente: 0,068; 0,210; 0,112; 0,175; 0,250; 0,167; y 0,063 s, respectivamente. Las siete páginas cargaron sin excepciones. El pico RSS muestreado cada 20 ms en ese mismo proceso fue 302,1 MiB (RSS final 299,0 MiB), por debajo de 800 MiB.

Streamlit headless en el venv limpio respondió `ok` en 7,296 s; el proceso se detuvo al terminar. Esto mide arranque hasta el endpoint de salud, no el tiempo de descarga/render del navegador.

### Comparación de cifras visibles

Antes de editar guardé la captura AppTest en `D:\ciencia de datos\baseline_app_numbers_20261111.json`. La comparación posterior está en `D:\ciencia de datos\app_visible_after_20261111.json`; ambas quedaron fuera del repositorio. Los KPI de Portada permanecen en 11,7 µg/m³; 19 estaciones; 1.096 días; 79,3% de cobertura. En Contexto siguen 7.937.898 habitantes, 19 estaciones, 70 microsensores y el rango de 2.547–2.688 m; los diámetros conservan 2,5 y 10. En Simulador permanecen el escenario A de 8,5 µg/m³, intervalo [3,2; 10,8], nivel típico 6,6; escenario B de 3,3 e intervalo [1,3; 4,2]. Modelo conserva sus métricas y tablas; Datos y metodología mantiene 20.824 filas. La única cifra corregida intencionalmente es la diferencia de altitud de 550 a 510 m. Los cálculos y series de los gráficos no se cambiaron; en “La caída de nivel” solo añadí título y nombres de ejes.

### Verificación

En el venv nuevo se instaló `requirements-dev.txt`; `pytest -q` terminó con **60 passed in 33,04 s** en la última corrida. AppTest recorrió las siete páginas dentro de la suite y la navegación limpia; no hubo excepciones. El arranque headless respondió correctamente. No ejecuté commit ni push.

## Corrección de datos_metodologia (2026-11-11)

### Diagnóstico y causa reproducida

La página leía la tabla maestra completa (`20.824 × 37`) aunque solo usaba la fecha para periodo y conteo; además, calculaba el pivote y serializaba la figura de cobertura en cada render, aun cuando esa sección no estuviera abierta. En el perfil previo, `cargar_aire()` tardó **2,377 s** y materializó **5,590 MB** en memoria; el pivote tardó **0,269 s** y la creación de la figura **0,715 s**. La página acumuló **7,580 s** en el perfil anterior. La tabla maestra en disco ocupa **0,217 MB**; el coste era leer y convertir columnas que la página no necesitaba, junto con trabajo de gráficos incondicional.

No pude consultar el URL público ni sus logs desde esta sesión. Por tanto, esto identifica la causa de coste local reproducida, pero no prueba que sea la causa única del bloqueo específico de Community Cloud. En la app no encontré ninguna ruta de `data/raw`, `data/interim` o `modelo_explicativo.joblib`.

### Lecturas, tablas, gráficos y cálculos

| Archivo o bloque | Tamaño/forma | Uso en la página |
|---|---:|---|
| `app/assets/style.css` | 2.022 bytes (**0,00202 MB**) | CSS compartido, leído por ruta derivada de `__file__`; lectura cacheada. |
| `data/processed/aire_bogota_diario.parquet` | En disco **0,2172 MB**; completo `20.824 × 37`, memoria pandas **5,5901 MB**; proyección actual `20.824 × 1`, **0,1667 MB** | Solo se necesita `fecha`; min, max y conteo de filas producen periodo `2023-10-24 — 2026-10-23` y **20.824** filas. |
| `data/docs/fuentes.md` | 750 bytes (**0,00075 MB**) | Se convierte en una tabla de fuentes de `1 × 5`, memoria **0,000757 MB**, mostrada con `st.dataframe` y descarga CSV. |
| `data/processed/app/cobertura_estacion_mes.csv` | `703 × 3`, disco **0,0223 MB**, memoria **0,02899 MB** | Lectura, pivote estación-mes `19 × 37` (**0,005967 MB**) y figura Plotly. Todo el bloque queda diferido hasta abrir el expander y ofrece descarga CSV. |
| `docs/decisiones.md` | 23.658 bytes (**0,02366 MB**) | Se convierte en tabla de decisiones `18 × 5` (**0,005991 MB**); incidentes: filtro de cuatro registros y adición del registro IDEAM, tabla final `5 × 3`. Ambas tablas están en un expander y tienen descarga CSV. |
| Figura de cobertura | matriz `19 × 37`; JSON Plotly de **12,39 kB** | `px.imshow`, título, escala, eje mensual y marca del hueco de PM; solo se construye al abrir el expander. |

Todos los archivos de la tabla anterior aparecen en `git ls-files`. `git check-ignore -v` no devolvió reglas para esas rutas; no hay archivos no versionados requeridos por esta página. La página no lee `data/raw`, `data/interim`, ni archivos de `models/`. Las tablas son pequeñas (máximo 18 decisiones); se mantienen completas, con visualización diferida y botón de descarga CSV, sin truncar filas.

### Corrección y rendimiento

- Añadí `cargar_fechas_aire()` con `read_parquet(columns=["fecha"])`, caché de datos, y cacheé la lectura del CSS, las fuentes, decisiones, CSV de cobertura y el pivote mensual.
- El mapa de calor y las tablas de decisiones/incidentes se calculan dentro de expanders con `on_change="rerun"`; los bloques muestran un spinner durante su carga. La matriz tiene solo 703 observaciones de origen y se construye en **0,016 s**; el gráfico diferido se crea en **0,336 s**. No se justifica un archivo precalculado ni un script nuevo para un cálculo de ese tamaño.
- No hay un modelo ni otro objeto persistente en esta página que requiera `st.cache_resource`; sus lecturas y agregaciones corresponden a `st.cache_data`.
- En proceso nuevo, AppTest aislado demoró **10,783 s** de pared incluyendo arranque e importaciones de Python/Streamlit (RSS **156,86 MB**); con esas dependencias ya importadas, el render frío y con cachés vacías demoró **1,481 s**, pico RSS **157,40 MB**, sin excepciones. En el recorrido secuencial de las siete páginas, Datos y metodología demoró **0,338 s** y el pico RSS del proceso fue **281,49 MB**, bajo el objetivo de 600 MB. En la misma secuencia: Portada 2,602 s; Contexto 0,747 s; Mapa 0,348 s; Factores 1,002 s; Simulador 11,921 s; Modelo 1,481 s; Datos y metodología 0,338 s. El tiempo alto de Simulador incluye su primera carga del artefacto y no pertenece a esta corrección.
- Comparación con el estado previo: Datos y metodología pasó de **7,580 s** en el perfil local previo a **1,481 s** de render frío medido tras importar el runtime (y **0,338 s** en el recorrido); el perfil previo no obtuvo un pico RSS válido para las siete páginas. El pico RSS de la medición secuencial actual es **281,49 MB**.
- Las tres métricas visibles siguen exactamente en **2023-10-24 — 2026-10-23**, “Una fila por estación y día” y **20.824** filas. El JSON del gráfico regenerado coincide con la captura anterior en datos y layout (`old_data_equal=True`, `old_layout_equal=True`). Las tablas usan las mismas fuentes y funciones de transformación; el cambio es de carga diferida, proyección y caché.

AppTest sin importar la página directamente terminó sin excepciones en cada una de las siete páginas. El render aislado de Datos y metodología quedó por debajo de 5 s una vez inicializado el runtime. No se hizo commit ni push.
