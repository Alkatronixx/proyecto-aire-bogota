# Resumen de correcciones — 2026-11-11

Completé las correcciones y dejé el informe actualizado en [docs/auditoria_app.md](</D:/ciencia de datos/proyecto-aire-bogota/docs/auditoria_app.md>).

- **Contexto:** verifiqué que los 19 IDs coinciden con la tabla maestra y retiré ambos avisos internos de verificación. La única diferencia de localidad es `centro_de_alto_rendimiento`: la ficha SDA indica Engativá y el cruce espacial, Barrios Unidos. Dejé la tabla intacta.
- **ICA y salud:** añadí la tabla de categorías de 24 horas y los riesgos relativos junto con sus advertencias. Quité los marcadores de cifras pendientes y no incluí las 13.345 muertes. La referencia del IDEAM es la [Resolución 2254 de 2017, Tabla 6](https://bart.ideam.gov.co/indiecosistemas/ind/aire/hm/1.%20HM%20Indice%20calidad%20aire.pdf). El PDF de salud indicado en la solicitud no estuvo accesible en esta sesión; también añadí la versión oficial de [marzo de 2026](https://saludata.saludcapital.gov.co/osb/wp-content/uploads/2026/03/OSB_MortalidadAtribuible_PM2.5.pdf) y la [página del indicador](https://saludata.saludcapital.gov.co/osb/indicadores/mortalidad-calidad-aire/) para consulta.
- **Simulador:** la prueba previa fallaba porque el bloque B estaba dentro de un expander cerrado. Lo dejé abierto y moví la comparación para que ambos escenarios se vean. La nueva prueba confirma que A y B aparecen y dan resultados distintos con entradas distintas.
- **Ablación:** confirmé que la gráfica presenta MAE en prueba, reentrenando el Ridge sin cada grupo y comparándolo con el modelo completo. Aclaré que una barra más alta indica mayor error; los valores coinciden con la tabla fuente.
- **README:** redacté la guía en español y creé [docs/documentacion_datos_y_modelo.md](</D:/ciencia de datos/proyecto-aire-bogota/docs/documentacion_datos_y_modelo.md>) porque el archivo enlazado solicitado no existía. Validé los enlaces relativos. Los scripts de regeneración existen y pasan revisión de sintaxis, pero no ofrecen modo seco; no los ejecuté porque modificarían datos o modelos excluidos de esta tarea.

**Verificación:** `pytest -q` pasó con **61 pruebas**; AppTest cargó las **7 páginas** sin excepciones; Streamlit arrancó en modo headless y el endpoint de salud respondió `ok`. La comparación de cifras visibles antes y después encontró los mismos valores. `git diff --check` no reportó errores; no hice commit ni push.

**Decisiones humanas pendientes**

1. Confirmar cómo presentar la diferencia de localidad de Centro de Alto Rendimiento.
2. Decidir si alguna página debe clasificar días con las categorías ICA; actualmente usa escala continua.
3. Confirmar si se debe preferir el PDF de salud `/2026/04/` o la versión oficial accesible `/2026/03/`.
4. Revisar si el contexto de riesgos poblacionales es adecuado para la audiencia de la app.
5. Elegir un entorno de trabajo separado para probar la regeneración completa de datos y modelo.
