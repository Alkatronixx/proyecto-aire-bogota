# Corrección de Datos y metodología — 2026-11-11

## Corrección y diagnóstico

La página leía las 37 columnas del parquet aunque solo necesitaba la fecha, y dibujaba el mapa de cobertura en cada render. Añadí una lectura proyectada a `fecha`, caché para lecturas y tablas, y carga diferida con spinner para cobertura, decisiones e incidentes. Las tablas tienen descarga CSV; la matriz de cobertura es de 19×37 y se calcula en menos de 0,02 s, así que no hizo falta precalcularla.

Los archivos requeridos existen, están versionados y no están ignorados por `.gitignore`. La página no accede a `data/raw`, `data/interim` ni a `modelo_explicativo.joblib`. La revisión del código apunta a una ineficiencia local reproducible, pero no pude acceder al URL ni a los logs de Community Cloud para confirmar que esa fuera la causa única del fallo remoto.

## Mediciones y verificación

| Medición | Antes | Después |
|---|---:|---:|
| Render de Datos y metodología | 7,580 s | 1,481 s frío con runtime inicializado; 0,338 s en recorrido secuencial |
| Pico RSS de esa página | 181,14 MB | 157,40 MB |
| Pico RSS visitando las siete páginas | No hubo medición válida | 281,49 MB |

El proceso nuevo de AppTest tardó 10,783 s incluyendo el arranque e importaciones de Python/Streamlit; ese tiempo incluye inicialización del entorno. En el recorrido final, las siete páginas terminaron sin excepciones: Portada 2,602 s; Contexto 0,747 s; Mapa 0,348 s; Factores 1,002 s; Simulador 11,921 s; Modelo 1,481 s; Datos y metodología 0,338 s.

Las métricas visibles de la página siguen siendo **2023-10-24 — 2026-10-23**, **una fila por estación y día** y **20.824 filas**. El JSON del gráfico de cobertura coincide con la captura anterior en datos y layout. La suite terminó con **60 passed en 22,26 s**. No hice commit ni push.

El detalle del diagnóstico, tamaños, lecturas y cambios quedó en [auditoria_app.md](auditoria_app.md). Los cambios de código están en [datos_metodologia.py](../app/pages/datos_metodologia.py), [datos.py](../app/utils/datos.py) y [ui.py](../app/components/ui.py).

## Requiere decisión humana

- Consultar los logs de Community Cloud si el fallo persiste tras desplegar estos cambios.
- Definir si el umbral de cinco segundos debe incluir el arranque completo del proceso, además del render de la página.
- Valorar si las tablas pequeñas deben seguir completas y descargables.
