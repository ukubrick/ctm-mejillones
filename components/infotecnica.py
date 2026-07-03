"""
components/infotecnica.py — Fichas técnicas de las 4 unidades del CTM.

Patrón del tab_infotecnica de Pulsar: fichas por unidad con los datos maestros
declarados ante el CEN. Fuente primaria: tabla `unidades_maestro` (adquirida de
/unidades-generadoras/v4); fallback: dict estático config.INFOTECNICA + PMAX.
"""
import pandas as pd
import streamlit as st

from config import COLORES, INFOTECNICA, LABELS, PMAX, POT_MIN_TECNICA, UNIDADES
from utils.data import load_unidades_maestro


def _fmt(v, unidad="", dec=1):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"{float(v):,.{dec}f} {unidad}".strip()
    except (ValueError, TypeError):
        return str(v)


def _ficha(unidad, datos, fuente):
    c = COLORES[unidad]
    filas = [
        ("Pot. máx. bruta",        _fmt(datos.get("pot_max_bruta"), "MW")),
        ("Pot. neta efectiva",     _fmt(datos.get("pot_neta_efectiva"), "MW")),
        ("Mínimo técnico",         _fmt(datos.get("pot_min_tecnica"), "MW", 0)),
        ("Mín. técnico ctrl. frec.", _fmt(datos.get("min_tec_ctrl_frec"), "MW", 0)),
        ("Consumos propios",       _fmt(datos.get("consumos_propios_pct"), "%")),
        ("Tensión nominal",        _fmt(datos.get("tension_nominal"), "kV", 0)),
        ("Factor de potencia",     _fmt(datos.get("factor_pot_nominal"), "", 2)),
        ("Tecnología",             datos.get("tecnologia") or "—"),
        ("Propietario",            datos.get("propietario") or "—"),
        ("Punto de conexión",      datos.get("punto_conexion") or "—"),
        ("Nemotécnico CEN",        datos.get("nemotecnico") or "—"),
    ]
    filas_html = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
        f'border-bottom:1px solid #F1F5F9;font-size:0.78rem">'
        f'<span style="color:#64748B">{k}</span>'
        f'<span style="color:#1A1F36;font-weight:600;text-align:right;max-width:60%">{v}</span></div>'
        for k, v in filas)
    st.markdown(
        f'<div class="aes-card" style="border-top:4px solid {c["line"]}">'
        f'<div class="kpi-badge" style="background:{c["badge"]};color:{c["text"]}">{LABELS[unidad]}</div>'
        f'{filas_html}'
        f'<div style="font-size:0.66rem;color:#94A3B8;margin-top:6px">Fuente: {fuente}</div></div>',
        unsafe_allow_html=True)


def render_infotecnica():
    st.markdown('<div class="sec">INFOTÉCNICA · MAESTRO DE UNIDADES CEN</div>', unsafe_allow_html=True)
    st.caption("Datos técnicos declarados ante el Coordinador (/unidades-generadoras/v4). "
               "Si aún no hay datos adquiridos, se muestran los valores de referencia del proyecto.")

    df = load_unidades_maestro()
    cols = st.columns(4)
    for col, u in zip(cols, UNIDADES):
        with col:
            fila = df[df["unidad"] == u] if not df.empty and "unidad" in df.columns else pd.DataFrame()
            if not fila.empty:
                _ficha(u, fila.iloc[0].to_dict(), "API CEN (unidades_maestro)")
            else:
                datos = dict(INFOTECNICA.get(u, {}))
                datos.setdefault("pot_max_bruta", PMAX.get(u))
                datos.setdefault("pot_min_tecnica", POT_MIN_TECNICA.get(u))
                _ficha(u, datos, "referencia estática (config)")
