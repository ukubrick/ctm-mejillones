"""
components/sidebar.py — Sidebar: marca, estado de fuentes, filtros y exportación.

Devuelve los filtros seleccionados (rango de fechas, flags de programada/CMG,
nodo CMG) que el resto de la app usa para cargar datos.
"""
from datetime import date, datetime, timedelta

import streamlit as st
import pandas as pd

from config import NOMBRES_NODO
from utils.db import test_conn, last_ts
from utils.data import load_real, load_prog, load_cmg, load_sscc, load_limitaciones
from utils.reports import generar_pdf, generar_ppt


def _fmt(v, fmt="%d/%m %H:%M"):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if hasattr(v, "strftime"):
        return v.strftime(fmt)
    # string ISO "YYYY-MM-DD HH:MM:SS" → "dd/mm HH:MM"
    txt = str(v)
    try:
        return pd.to_datetime(txt).strftime(fmt)
    except Exception:
        return txt[:16]


def render_sidebar():
    """Renderiza el sidebar y devuelve dict de filtros."""
    with st.sidebar:
        st.markdown(
            '<div style="font-size:22px;font-weight:800;color:white;letter-spacing:-0.5px;margin-bottom:2px">Complejo Térmico</div>'
            '<div style="font-size:22px;font-weight:800;color:#4DC8DC;letter-spacing:-0.5px;margin-bottom:6px">Mejillones</div>'
            '<p style="font-size:0.72rem;color:rgba(255,255,255,0.55);margin-bottom:0.3rem;font-weight:500;letter-spacing:0.04em">AES Andes · Monitoreo Operacional</p>',
            unsafe_allow_html=True,
        )

        db_ok, db_err = test_conn()
        dot_db = "dot-g" if db_ok else "dot-r"
        txt_db = "Conectado · Supabase / PostgreSQL" if db_ok else "Error de conexión DB"

        # Si la DB no responde, no encadenamos consultas (cada una reintentaría la
        # conexión colgada). Mostramos el error y detenemos con un mensaje claro.
        if not db_ok:
            st.markdown(
                f'<div class="status-box"><span class="dot-status {dot_db}"></span>'
                f'<span style="font-size:0.72rem;font-weight:600">{txt_db}</span></div>',
                unsafe_allow_html=True,
            )
            st.error(
                "No se pudo conectar a la base de datos (Supabase). "
                "Verifica que el proyecto no esté pausado y que tu red permita la "
                "conexión al pooler. Detalle: " + (db_err or "timeout")
            )
            st.stop()

        # Fuentes más relevantes (núcleo horario) con fecha + hora de adquisición
        str_r   = _fmt(last_ts("generacion_real", "fecha_hora"))
        str_p   = _fmt(last_ts("generacion_programada", "fecha_hora", {"fuente": "CEN_PCP"}))
        str_cmg = _fmt(last_ts("costo_marginal", "fecha_hora"))
        str_lim = _fmt(last_ts("limitaciones_transmision", "modified"))

        st.markdown(f"""
        <div class="status-box">
            <div style="margin-bottom:8px">
                <span class="dot-status {dot_db}"></span>
                <span style="font-size:0.72rem;font-weight:600">{txt_db}</span>
            </div>
            <div style="font-size:0.62rem;font-weight:700;letter-spacing:1.2px;color:#4DC8DC;text-transform:uppercase;margin-bottom:6px">ÚLTIMA ADQUISICIÓN · API CEN</div>
            <div style="font-size:0.7rem;line-height:1.9">
                <span class="dot-status dot-g"></span>Gen. real <b style="float:right">{str_r}</b><br>
                <span class="dot-status dot-g"></span>Gen. programada <b style="float:right">{str_p}</b><br>
                <span class="dot-status dot-g"></span>CMG <b style="float:right">{str_cmg}</b><br>
                <span class="dot-status dot-g"></span>Limitaciones <b style="float:right">{str_lim}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        st.page_link("app.py", label="Aplicación")
        st.page_link("pages/ml_analysis.py", label="Machine Learning Analysis")

        st.markdown("---")
        hoy = date.today()
        fi = st.date_input("Desde", value=hoy - timedelta(days=7), max_value=hoy)
        ff = st.date_input("Hasta", value=hoy, max_value=hoy)
        if fi > ff:
            st.error("Fecha inicio > fin")
            st.stop()

        st.markdown("---")
        mostrar_prog = st.checkbox("Mostrar programada", value=True)
        mostrar_cmg  = st.checkbox("Mostrar CMG en gráficos", value=True)
        nodo_cmg = "CRUCERO_______220"
        if mostrar_cmg:
            nodo_cmg = st.radio(
                "Nodo CMG", list(NOMBRES_NODO.keys()),
                format_func=lambda x: NOMBRES_NODO[x], key="nodo_cmg_sel",
            )

        st.markdown("---")
        if st.button("Actualizar datos"):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.markdown('<p style="font-size:0.72rem;font-weight:600;color:#E2E8F0">EXPORTAR REPORTE</p>', unsafe_allow_html=True)
        _render_export(fi, ff)

        st.markdown(f"""
        <div style="border-top:1px solid rgba(255,255,255,0.12);padding-top:10px;margin-top:4px;text-align:center;font-size:0.68rem;color:rgba(255,255,255,0.45)">
            {datetime.now().strftime("%d/%m/%Y %H:%M")}<br>
            Dashboard creado por<br>
            <b style="color:rgba(255,255,255,0.70)">Erick Herrera</b><br>AES Andes
        </div>
        """, unsafe_allow_html=True)

    return {
        "fi": fi, "ff": ff, "hoy": hoy,
        "s": fi.strftime("%Y-%m-%d"), "e": ff.strftime("%Y-%m-%d"),
        "mostrar_prog": mostrar_prog, "mostrar_cmg": mostrar_cmg, "nodo_cmg": nodo_cmg,
    }


def _datos_reporte(fi, ff):
    s_r, e_r = fi.strftime("%Y-%m-%d"), ff.strftime("%Y-%m-%d")
    df_lim_r = load_limitaciones(s_r, e_r)
    if not df_lim_r.empty:
        df_lim_r["_unidad"] = df_lim_r["id_unidad"].apply(
            lambda x: {1965: "ANG1", 1966: "ANG2", 1967: "CCR1", 1968: "CCR2"}.get(int(float(x)), "") if pd.notna(x) else ""
        )
    return (load_real(s_r, e_r), load_prog(s_r, e_r), load_cmg(s_r, e_r),
            load_sscc(s_r, e_r), df_lim_r, s_r, e_r)


def _render_export(fi, ff):
    if st.button("Generar PDF"):
        with st.spinner("Generando PDF..."):
            try:
                dr, dp, dc, ds, dl, s_r, e_r = _datos_reporte(fi, ff)
                pdf_bytes = generar_pdf(dr, dp, dc, s_r, e_r, df_sscc=ds, df_lim=dl)
                st.download_button("Descargar PDF", data=pdf_bytes,
                                   file_name=f"CTM-Reporte_{s_r}_{e_r}.pdf", mime="application/pdf")
            except Exception as ex:
                st.error(f"Error generando PDF: {ex}")

    if st.button("Generar PPT"):
        with st.spinner("Generando presentación..."):
            try:
                dr, dp, dc, ds, dl, s_r, e_r = _datos_reporte(fi, ff)
                ppt_bytes = generar_ppt(dr, dp, dc, s_r, e_r, df_sscc=ds, df_lim=dl)
                st.download_button("Descargar PPT", data=ppt_bytes,
                                   file_name=f"CTM-Reporte_{s_r}_{e_r}.pptx",
                                   mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
            except Exception as ex:
                st.error(f"Error generando PPT: {ex}")
