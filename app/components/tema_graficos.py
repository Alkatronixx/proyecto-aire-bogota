"""Plantilla Plotly oscura compartida para mantener lectura consistente."""
import plotly.graph_objects as go
import plotly.io as pio
from app.components.paleta import FONDO, FONDO_TARJETA, ACENTO

TEMA_AIRE = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor=FONDO,
        plot_bgcolor=FONDO_TARJETA,
        font={"family": "Inter, Segoe UI, sans-serif", "color": "#E9EDF3", "size": 13},
        title_font={"size": 19, "color": "#F7F8FA"},
        colorway=[ACENTO, "#2ECC71", "#F1C40F", "#E67E22", "#E74C3C", "#8E44AD"],
        xaxis={"showgrid": False, "zeroline": False, "linecolor": "#394252"},
        yaxis={"showgrid": True, "gridcolor": "#2B3341", "zeroline": False, "linecolor": "#394252"},
        hoverlabel={"bgcolor": "#252C3A", "font": {"color": "#FFFFFF"}},
    )
)
pio.templates["aire_bogota_dark"] = TEMA_AIRE


def aplicar_tema(fig: go.Figure, titulo_eje: str | None = None) -> go.Figure:
    """Aplica fondo, tipografía, rejilla y colores coherentes a una figura."""
    fig.update_layout(
        template="aire_bogota_dark",
        margin={"l": 18, "r": 18, "t": 58, "b": 20},
    )
    if titulo_eje:
        fig.update_yaxes(title=titulo_eje)
    return fig
