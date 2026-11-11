"""Colores compartidos y escala continua de PM2.5 basada en cuantiles.
Los colores mantienen la identidad visual del proyecto sin clasificar por umbrales.
La escala cambia sus puntos de corte con la distribución observada suministrada.
Los límites normativos quedan pendientes de una fuente oficial verificable.
"""
import numpy as np
import pandas as pd

FONDO = "#0E1117"
FONDO_TARJETA = "#1A1F2B"
ACENTO = "#00C2A8"
COLORES_PM = ["#2ECC71", "#F1C40F", "#E67E22", "#E74C3C", "#8E44AD"]


def niveles_calidad_oficial():
    """TODO: devolver umbrales solo cuando haya una fuente oficial citada."""
    return None


def _cuantiles(valores) -> np.ndarray:
    """Calcula cortes robustos de la distribución no nula de PM2.5."""
    datos = pd.to_numeric(pd.Series(valores), errors="coerce").dropna().to_numpy()
    if not len(datos):
        return np.array([0., 1., 2., 3., 4.])
    return np.quantile(datos, [0., .25, .5, .75, 1.])


def escala_plotly(valores) -> list[list[float | str]]:
    """Crea la escala Plotly continua ubicando los colores en cuantiles."""
    cortes = _cuantiles(valores)
    amplitud = cortes[-1] - cortes[0]
    posiciones = np.linspace(0., 1., len(COLORES_PM)) if amplitud == 0 else (cortes - cortes[0]) / amplitud
    escala = []
    for posicion, color in zip(posiciones, COLORES_PM):
        punto = [float(posicion), color]
        if not escala or punto[0] > escala[-1][0]:
            escala.append(punto)
        else:
            escala[-1] = punto
    if len(escala) == 1:
        return [[0., COLORES_PM[0]], [1., COLORES_PM[-1]]]
    return escala


def color_rgb_cuantil(valor: float, referencia) -> list[int]:
    """Interpela el color de un valor según los cuantiles de referencia."""
    cortes = _cuantiles(referencia)
    rgb = np.array([[int(color[i:i+2], 16) for i in (1, 3, 5)] for color in COLORES_PM], dtype=float)
    if cortes[-1] == cortes[0]:
        return [int(round(v)) for v in rgb[len(COLORES_PM) // 2]]
    posiciones = (cortes - cortes[0]) / (cortes[-1] - cortes[0])
    # Si varios cuartiles coinciden, conserva el color del último corte en esa posición.
    puntos = []
    for posicion, color in zip(posiciones, rgb):
        if puntos and posicion <= puntos[-1][0]:
            puntos[-1] = (float(posicion), color)
        else:
            puntos.append((float(posicion), color))
    posicion_valor = float(np.clip((float(valor) - cortes[0]) / (cortes[-1] - cortes[0]), 0., 1.))
    x = np.array([p[0] for p in puntos])
    colores = np.array([p[1] for p in puntos])
    return [int(round(np.interp(posicion_valor, x, colores[:, i]))) for i in range(3)]
