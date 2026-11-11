"""Construye figuras compactas compartidas por las páginas de la app.
Recibe agregados procesados, no lee archivos ni transforma la tabla diaria.
Devuelve un mapa de calor ligero para cobertura mensual de PM2.5.
"""
import plotly.graph_objects as go

from app.components.paleta import escala_plotly
from app.components.tema_graficos import aplicar_tema


def figura_cobertura_estacion_mes(matriz, meses: list[str], estaciones: list[str]) -> go.Figure:
    """Dibuja la matriz mensual sin texto por celda para reducir el payload del navegador."""
    figura = go.Figure(go.Heatmap(
        z=matriz.to_numpy(dtype=float),
        x=meses,
        y=estaciones,
        zmin=0,
        zmax=100,
        colorscale=escala_plotly(matriz.stack().dropna()),
        colorbar={"title": "% con dato", "ticksuffix": "%"},
        hovertemplate="%{y}<br>%{x}: %{z:.1f}%<extra></extra>",
        xgap=1,
        ygap=1,
    ))
    figura.update_layout(
        title="Porcentaje de días del mes con PM2.5 observado",
        height=620,
        margin={"l": 10, "r": 10, "t": 55, "b": 70},
    )
    figura.update_xaxes(title="Año-mes", tickangle=-60, dtick=2)
    figura.update_yaxes(title="Estación")
    # El sombreado conserva el contexto del hueco sin añadir anotaciones dentro de las celdas.
    if "2025-08" in meses and "2025-10" in meses:
        figura.add_vrect(x0="2025-08", x1="2025-10", fillcolor="#7B8492", opacity=.18,
                         line_width=0, layer="below")
    return aplicar_tema(figura)
