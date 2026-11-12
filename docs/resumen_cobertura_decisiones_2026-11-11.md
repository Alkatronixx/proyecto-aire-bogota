# Resumen: cobertura y decisiones — 2026-11-11

La cobertura dejó de enviar al navegador anotaciones y datos redundantes. En el gráfico anterior, `px.imshow` partía de 703 filas × 3 columnas, pivotaba a 19 × 37 y generaba 15,42 KB de JSON, con una traza y una anotación general. El nuevo `go.Heatmap` pesa **9,32 KB**, tiene una traza, 703 celdas y cero anotaciones. El hover es breve y la altura, fija en 620 px.

El nuevo script [preparar_cobertura_app.py](</D:/ciencia de datos/proyecto-aire-bogota/src/datos/preparar_cobertura_app.py>) reconstruyó la matriz desde la tabla maestra y comprobó **703 de 703 celdas iguales** a la cobertura anterior. El CSV ahora tiene 19 filas × 38 columnas y pesa 7.795 bytes. No encontré Playwright instalado, así que no pude medir la respuesta del hilo principal ni observar el aviso del navegador.

La página interpreta **56 decisiones** y no encontró entradas mal formadas. Acepta etiquetas sin énfasis, en negrita o cursiva, y muestra un aviso si una entrada fechada no se puede interpretar. La caché depende de la modificación y tamaño de los dos documentos que lee; el detalle reciente está en un expander.

Las cinco entradas más recientes son:

1. 2026-11-11 — Simulador y despliegue
2. 2026-11-10 — Índice de viento de ciudad en lugar de viento por estación
3. 2026-11-10 — Valores centinela y rachas inválidas
4. 2026-11-10 — Tabla ICA y cifras de salud
5. 2026-11-10 — Selección del modelo por validación cruzada temporal, no por la prueba

**Verificación:** en el clon del último commit con el árbol de trabajo aplicado, `pytest -q` terminó con **47 passed, 19 skipped**; las pruebas AppTest de las siete páginas y navegación dieron **15 passed**. Streamlit headless respondió `ok`. La comparación con la captura anterior confirmó métricas iguales en las siete páginas, los KPI anteriores presentes y los valores de Datos y metodología intactos: periodo, grano y 20.824 filas. El detalle está en [docs/auditoria_app.md](</D:/ciencia de datos/proyecto-aire-bogota/docs/auditoria_app.md>).

Corregí un test heredado que requería `modelo_explicativo.joblib`, excluido del repositorio, para que valide los modelos versionados y el Simulador v2. No modifiqué `docs/decisiones.md`, datos crudos o intermedios ni modelos; tampoco hice commit o push. Los cambios previos en `README.md` y `data/docs/decisiones.md` ya estaban en el árbol antes de esta tarea y quedaron intactos.

**Decisiones humanas pendientes**

1. Confirmar si la documentación futura debe mantener el registro detallado en `data/docs/decisiones.md` además del consolidado en `docs/decisiones.md`.
2. Si el aviso del navegador persiste, decidir si se mide con Playwright instalado o con telemetría de Community Cloud.
3. Revisar si conviene conservar permanentemente el CSV largo de cobertura como archivo de detalle independiente.
