# Correcciones para el despliegue

Corregí los bloqueantes de dependencias, las cifras de contexto, los avisos de Streamlit y la colisión de importaciones que aparecía al navegar en un proceso limpio. Añadí el resumen cacheado de Portada y diferí la carga del modelo hasta Simulador o Modelo.

La sección **“Correcciones del 2026-11-10”** quedó añadida al final de [docs/auditoria_app.md](auditoria_app.md). Python está fijado en [AGENTS.md](../AGENTS.md) como 3.15.2; `requirements.txt` conserva dependencias exactas y ya no incluye pytest, Shapely ni PyProj. Creé `requirements-dev.txt` con `pytest==9.2.0` y `psutil==7.1.3`.

**Verificación real:** `pytest -q` terminó con **60 passed en 33,04 s**. AppTest recorrió las siete páginas sin excepciones; el servidor headless respondió `ok` en **7,296 s**. El pico RSS observado en el recorrido final fue **302,1 MiB**, bajo el límite de 800 MiB.

| Página | Fría | Caliente |
|---|---:|---:|
| Portada | 11,407 s | 0,068 s |
| Contexto | 0,465 s | 0,210 s |
| Mapa | 0,185 s | 0,112 s |
| Factores | 0,855 s | 0,175 s |
| Simulador | 10,184 s | 0,250 s |
| Modelo | 0,379 s | 0,167 s |
| Datos y metodología | 0,492 s | 0,063 s |

El objetivo de frío de menos de 10 s **aún se excede levemente** en Portada y Simulador. El perfil atribuye la mayor parte a la inicialización de pandas/scikit-learn y esperas del runner AppTest; el arranque headless sí quedó bajo 10 s. La única cifra visible corregida fue la diferencia de altitud, de 550 a **510 m**; el resto de cifras capturadas antes de los cambios se mantuvo. Las capturas quedaron fuera del repo en `D:\ciencia de datos\baseline_app_numbers_20261111.json` y `D:\ciencia de datos\app_visible_after_20261111.json`.

`git check-ignore -v` no encontró reglas que excluyan las utilidades ni `data/processed/geo/`; el modelo explicativo no está versionado. Ejecuté `git add` sobre las rutas solicitadas. No hice commit ni push; `app/utils/portada.py` y `requirements-dev.txt` siguen sin rastrear y deberán incluirse antes del commit de despliegue.

```text
 M AGENTS.md
 M app/app.py
 M app/pages/contexto.py
 M app/pages/datos_metodologia.py
 M app/pages/factores.py
 M app/pages/mapa.py
 M app/pages/modelo.py
 M app/pages/portada.py
 M app/pages/simulador.py
M  app/utils/fuentes_contexto.py
 M docs/auditoria_app.md
 M requirements.txt
?? app/utils/portada.py
?? requirements-dev.txt
```

No modifiqué `data/raw`, `data/interim`, `data/processed`, `models/` ni `docs/decisiones.md`.
