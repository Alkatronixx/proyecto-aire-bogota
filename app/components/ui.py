"""Bloques de interfaz reutilizables con estilos definidos en assets/style.css."""
import streamlit as st


def cargar_estilos() -> None:
    """Inyecta el CSS local permitido para conservar un diseño compartido."""
    from pathlib import Path
    css = Path(__file__).resolve().parents[1] / "assets" / "style.css"
    st.markdown(f"<style>{css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def encabezado_pagina(titulo: str, descripcion: str = "") -> None:
    """Muestra el encabezado principal y su contexto en cada página."""
    st.markdown(f'<div class="page-kicker">AIRE BOGOTÁ · PM2.5</div><h1 class="page-title">{titulo}</h1>', unsafe_allow_html=True)
    if descripcion:
        st.markdown(f'<p class="page-description">{descripcion}</p>', unsafe_allow_html=True)


def tarjeta_kpi(titulo: str, valor: str, detalle: str = "") -> None:
    """Renderiza una métrica compacta en una tarjeta destacada."""
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">{titulo}</div>'
        f'<div class="kpi-value">{valor}</div><div class="kpi-detail">{detalle}</div></div>',
        unsafe_allow_html=True,
    )


def caja_hallazgo(texto: str) -> None:
    """Resalta una asociación descriptiva calculada desde los datos."""
    st.markdown(f'<div class="finding-card"><span class="finding-mark">●</span><span>{texto}</span></div>', unsafe_allow_html=True)


def caja_pendiente(texto: str = "") -> None:
    """Muestra un pendiente con estilo neutral cuando falta una fuente oficial."""
    detalle = f"<br>{texto}" if texto else ""
    st.markdown(f'<div class="pending-card"><strong>Cifra pendiente de fuente oficial</strong>{detalle}</div>', unsafe_allow_html=True)


def nota_metodologica(texto: str) -> None:
    """Presenta una precisión metodológica secundaria sin ocultarla."""
    st.markdown(f'<div class="method-note">{texto}</div>', unsafe_allow_html=True)
