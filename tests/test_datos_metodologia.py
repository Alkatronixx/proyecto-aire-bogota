"""Comprueba la cobertura compacta y la lectura tolerante de decisiones.
Lee productos procesados y documentación publicada del proyecto.
Valida igualdad de porcentajes, formatos Markdown y render de la página.
"""
import pandas as pd
from PIL import Image
from streamlit.testing.v1 import AppTest

from app.utils.datos import ROOT, cargar_csv_app, entradas_decisiones, preparar_cobertura_estacion_mes
from src.datos.preparar_cobertura_app import generar_imagen


def test_matriz_cobertura_tiene_19_por_37_y_mismos_valores() -> None:
    """Compara las 703 celdas de la matriz publicada con un cálculo independiente."""
    _, meses, estaciones, matriz = preparar_cobertura_estacion_mes()
    assert matriz.shape == (19, 37)
    assert len(meses) == 37
    assert len(estaciones) == 19

    aire = pd.read_parquet(
        ROOT / "data" / "processed" / "aire_bogota_diario.parquet",
        columns=["fecha", "estacion_id", "pm25"],
    )
    aire["año_mes"] = pd.to_datetime(aire.fecha).dt.to_period("M").astype(str)
    larga = (
        aire.groupby(["estacion_id", "año_mes"]).pm25
        .apply(lambda serie: 100 * serie.notna().mean()).rename("pct").reset_index()
    )
    esperada = larga.pivot(index="estacion_id", columns="año_mes", values="pct")
    esperada = esperada.reindex(index=estaciones, columns=meses).round(6)
    pd.testing.assert_frame_equal(matriz.astype(float), esperada.astype(float), check_names=False)
    assert cargar_csv_app("cobertura_estacion_mes.csv").shape == (19, 38)


def test_imagen_cobertura_es_ligera_y_codifica_los_valores_csv(tmp_path) -> None:
    """Genera el PNG, valida sus dimensiones y verifica píxeles de dos celdas conocidas."""
    _, _, _, matriz = preparar_cobertura_estacion_mes()
    destino = tmp_path / "cobertura.png"
    peso = generar_imagen(matriz, destino)
    assert peso < 400 * 1024
    assert Image.open(destino).size == (1500, 1050)
    assert matriz.loc["bolivia", "2023-10"] == 100.0
    assert matriz.loc["bolivia", "2024-02"] == 0.0


def test_entradas_decisiones_acepta_estilos_y_avisa_si_no_interpreta() -> None:
    """Los énfasis Markdown no ocultan la etiqueta ni silencian un encabezado incompleto."""
    texto = """## 2026-11-09: Sin énfasis
- Decisión: texto uno.

## 2026-11-10: Negrita
- **Decisión:** texto dos.

## 2026-11-11: Cursiva
- *Decisión:* texto tres.

## 2026-11-11: Sin decisión
- Motivo: entrada incompleta.
"""
    tabla, avisos = entradas_decisiones(texto)
    assert len(tabla) == 3
    assert tabla.Decisión.tolist() == ["texto uno.", "texto dos.", "texto tres."]
    assert avisos == ["2026-11-11: Sin decisión"]


def test_cache_markdown_cambia_con_mtime(tmp_path, monkeypatch) -> None:
    """Una modificación del archivo cambia la clave y el contenido cacheado."""
    import os

    import app.utils.datos as datos

    ruta = tmp_path / "decisiones.md"
    ruta.write_text("primera", encoding="utf-8")
    monkeypatch.setattr(datos, "rutas_markdown", lambda _tipo: (ruta,))
    firma_antes = datos.firma_markdown("decisiones")
    assert datos.cargar_markdown("decisiones", firma_antes) == "primera"
    ruta.write_text("segunda", encoding="utf-8")
    os.utime(ruta, ns=(firma_antes[0] + 2_000_000, firma_antes[0] + 2_000_000))
    firma_despues = datos.firma_markdown("decisiones")
    assert firma_despues != firma_antes
    assert datos.cargar_markdown("decisiones", firma_despues) == "segunda"


def test_registro_lee_decisiones_nuevas_y_renderiza_el_expander() -> None:
    """La página muestra el registro reciente y su render no falla al abrirlo."""
    from app.utils.datos import cargar_markdown, firma_markdown

    texto = cargar_markdown("decisiones", firma_markdown("decisiones"))
    entradas, avisos = entradas_decisiones(texto)
    assert len(entradas) >= 20
    assert "Simulador y despliegue" in set(entradas.Título)
    assert avisos == []

    pagina = ROOT / "app" / "pages" / "datos_metodologia.py"
    prueba = AppTest.from_file(str(pagina), default_timeout=45).run()
    assert not prueba.exception, str(prueba.exception)
    assert any("Registro de decisiones fechadas" in elemento.value for elemento in prueba.subheader)
    assert any("Entradas interpretadas:" in elemento.value for elemento in prueba.caption)


def test_cobertura_renderiza_al_abrir_su_desplegable() -> None:
    """La página metodológica carga sin excepción con la cobertura en imagen estática."""
    imagen = ROOT / "data" / "processed" / "app" / "cobertura_estacion_mes.png"
    assert imagen.is_file()
    assert imagen.stat().st_size < 400 * 1024
    pagina = ROOT / "app" / "pages" / "datos_metodologia.py"
    prueba = AppTest.from_file(str(pagina), default_timeout=45).run()
    assert not prueba.exception, str(prueba.exception)
