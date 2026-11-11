"""Pruebas de visibilidad y comparación de escenarios del simulador.
Ejecuta la página con Streamlit AppTest y revisa los controles y resultados.
Comprueba que el escenario B no dependa de una acción previa para aparecer.
Evita regresiones en la comparación cuando los valores de entrada difieren.
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_ambos_escenarios_visibles_y_con_resultados_distintos() -> None:
    """Comprueba que se ven A y B, con controles distintos y métricas comparables."""
    app = AppTest.from_file(str(ROOT / "app" / "pages" / "simulador.py"), default_timeout=180).run()

    assert not app.exception, str(app.exception)
    metricas = {elemento.label: elemento.value for elemento in app.metric}
    assert "Escenario A" in metricas
    assert "Escenario B" in metricas
    assert metricas["Escenario A"] != metricas["Escenario B"]

    dia_a = next(elemento.value for elemento in app.selectbox if elemento.key == "a_dia_semana")
    dia_b = next(elemento.value for elemento in app.selectbox if elemento.key == "b_dia_semana")
    assert dia_a != dia_b
    assert app.expander[0].proto.expanded
