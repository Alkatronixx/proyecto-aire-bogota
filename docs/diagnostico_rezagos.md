## Rezagos de `entrenar.py`

En [entrenar.py](../src/modelo/entrenar.py#L39), primero se ordena por estación y fecha; luego `pm25_ayer` usa `shift(1)` y `pm25_media_3d` calcula un rolling de tres filas previas, con `min_periods=2`.

La tabla maestra tiene una fila diaria por estación, incluso durante el hueco, con PM2.5 faltante. Comparé los rezagos con fechas calendario explícitas:

| Periodo | Filas estación-día | `pm25_ayer` distinto de PM2.5 en D-1 | `pm25_media_3d` distinto de ventana estricta D-3 a D-1 |
|---|---:|---:|---:|
| Entrenamiento | 13,889 | **0** | 714 |
| Prueba | 6,935 | **0** | 364 |

**`pm25_ayer` no salta el hueco de 2025.** Al faltar PM2.5 en D-1, el rezago queda NaN; no toma la última medición disponible de semanas atrás. Por ejemplo, en Bolivia, el 2025-10-23 usa NaN porque el dato del 22 es NaN; el 2025-10-24 también queda NaN porque el día 23 no tiene PM2.5.

`pm25_media_3d` sí usa las tres filas calendario previas en esta tabla diaria. La diferencia está en el tratamiento de faltantes: el código original promedia dos días si el tercero está ausente; la ventana estricta que pediste queda NaN si falta cualquiera de D-3, D-2 o D-1. Por eso difieren 714 filas de entrenamiento y 364 de prueba.

## Ridge predictivo en memoria

No encontré filas con `pm25_ayer` incorrecto, así que esa condición no exige reentrenar. Como comprobación adicional, sí ajusté en memoria el Ridge con la regla estricta de tres días. La selección temporal eligió `alpha=100` en ambos casos.

| Variante | Filas train | Filas test | MAE | RMSE | R² |
|---|---:|---:|---:|---:|---:|
| Rezagos actuales (`min_periods=2`) | 8,483 | 5,170 | **3.3318** | **4.3874** | **0.7068** |
| Ventana estricta D-3:D-1; NaN si falta un día | 8,166 | 4,969 | **3.3383** | **4.4013** | **0.7094** |

La variante estricta descarta 317 filas train y 201 filas test adicionales porque no tienen los tres PM2.5 previos. En una comparación pareada —mismas 8,166 filas train y 4,969 test— ambas variantes dan MAE **3.3383**, RMSE **4.4013** y R² **0.7094**: cuando los tres días están completos, los valores de `pm25_media_3d` coinciden.

La verificación y los ajustes se ejecutaron solo en memoria; no modifiqué archivos.
