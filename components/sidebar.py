"""
components/sidebar.py — Sidebar: marca, estado de fuentes, filtros y exportación.

Devuelve los filtros seleccionados (rango de fechas, flags de programada/CMG,
nodo CMG) que el resto de la app usa para cargar datos.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
import pandas as pd

from utils.db import test_conn, last_ts
from utils.data import load_real, load_prog, load_cmg, load_sscc, load_limitaciones
from utils.reports import generar_pdf, generar_ppt

TZ_CHILE = ZoneInfo("America/Santiago")


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


def _edad_fuente(v, hoy):
    """(clase_dot, etiqueta) según frescura del último dato de una fuente continua.

    Verde = dato de hoy (o futuro, p.ej. programada que llega a mañana);
    ámbar = de ayer; rojo = más antiguo o sin datos.
    """
    try:
        dt = pd.to_datetime(str(v))
    except Exception:
        return "dot-r", "sin datos"
    delta = (hoy - dt.date()).days
    hm = dt.strftime("%H:%M")
    if delta < 0:
        return "dot-g", f"mañana {hm}"
    if delta == 0:
        return "dot-g", f"hoy {hm}"
    if delta == 1:
        return "dot-y", f"ayer {hm}"
    return "dot-r", dt.strftime("%d/%m %H:%M")


def _row_cont(nombre, v, hoy):
    dot, lbl = _edad_fuente(v, hoy)
    return (
        '<div style="display:flex;align-items:center;justify-content:space-between;padding:3px 0">'
        f'<span style="color:rgba(255,255,255,0.82)"><span class="dot-status {dot}"></span>{nombre}</span>'
        f'<span style="font-variant-numeric:tabular-nums;color:#FFFFFF;font-weight:600;font-size:0.68rem">{lbl}</span></div>'
    )


def _row_evt(nombre, v, con_hora=True):
    txt = _fmt(v, "%d/%m %H:%M" if con_hora else "%d/%m")
    return (
        '<div style="display:flex;align-items:center;justify-content:space-between;padding:2px 0">'
        f'<span style="color:rgba(255,255,255,0.55)">{nombre}</span>'
        f'<span style="font-variant-numeric:tabular-nums;color:rgba(255,255,255,0.72);font-size:0.68rem">{txt}</span></div>'
    )


def render_sidebar():
    """Renderiza el sidebar y devuelve dict de filtros."""
    with st.sidebar:
        st.markdown(
            '<div style="font-size:23px;font-weight:800;color:white;letter-spacing:-0.6px;line-height:1.05">Complejo Térmico</div>'
            '<div style="font-size:23px;font-weight:800;color:#5FE0C8;letter-spacing:-0.6px;margin-bottom:7px">Mejillones</div>'
            '<p style="font-size:0.7rem;color:rgba(255,255,255,0.6);margin:0 0 0.2rem;font-weight:600;letter-spacing:0.14em;text-transform:uppercase">Monitoreo Operacional</p>',
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

        # ── Estado de adquisición ────────────────────────────────────────────
        # Fuentes continuas (gen/CMG): el dot refleja la frescura real del último
        # dato (verde=hoy, ámbar=ayer, rojo=más viejo). Fuentes por evento
        # (despacho/SSCC/limitaciones): la ausencia de registros recientes es
        # normal, así que se listan como "último registro" sin semántica de salud.
        hoy_cl = datetime.now(TZ_CHILE).date()
        ts_real = last_ts("generacion_real", "fecha_hora")
        ts_prog = last_ts("generacion_programada", "fecha_hora", {"fuente": "CEN_PCP"})
        ts_cmg  = last_ts("costo_marginal", "fecha_hora")
        ts_desp = last_ts("instrucciones_cmg", "fecha_hora")
        ts_sscc = last_ts("sscc_instrucciones", "fecha")
        ts_lim  = last_ts("limitaciones_transmision", "modified")

        st.markdown(f"""
        <div class="status-box">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:10px">
                <span class="dot-status {dot_db}"></span>
                <span style="font-size:0.72rem;font-weight:600">{txt_db}</span>
            </div>
            <div style="font-size:0.6rem;font-weight:700;letter-spacing:1.3px;color:#C4B5FD;text-transform:uppercase;margin-bottom:5px">Estado de adquisición · API CEN</div>
            {_row_cont("Gen. real", ts_real, hoy_cl)}
            {_row_cont("Gen. programada", ts_prog, hoy_cl)}
            {_row_cont("CMG online", ts_cmg, hoy_cl)}
            <div style="font-size:0.58rem;font-weight:700;letter-spacing:1.1px;color:rgba(255,255,255,0.4);text-transform:uppercase;margin:8px 0 3px;border-top:1px solid rgba(255,255,255,0.1);padding-top:7px">Último registro</div>
            {_row_evt("Despacho CMG", ts_desp)}
            {_row_evt("SSCC", ts_sscc, con_hora=False)}
            {_row_evt("Limitaciones", ts_lim)}
            <div style="font-size:0.6rem;color:rgba(255,255,255,0.4);margin-top:8px;text-align:center;font-style:italic">Adquisición automática cada 30 min</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<p style="font-size:0.66rem;font-weight:700;letter-spacing:0.14em;'
                    'color:#C7D2FE;margin-bottom:4px;text-transform:uppercase">Período de análisis</p>',
                    unsafe_allow_html=True)
        hoy = date.today()
        fi = st.date_input("Desde", value=hoy - timedelta(days=7), max_value=hoy)
        ff = st.date_input("Hasta", value=hoy, max_value=hoy)
        if fi > ff:
            st.error("Fecha inicio > fin")
            st.stop()

        # Bloque de acciones agrupado (botones juntos y centrados).
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        if st.button("↻  Actualizar datos"):
            st.cache_data.clear()
            st.rerun()
        st.markdown('<p style="font-size:0.62rem;font-weight:700;letter-spacing:0.14em;'
                    'color:#C7D2FE;margin:6px 0 2px;text-transform:uppercase;text-align:center">Exportar reporte</p>',
                    unsafe_allow_html=True)
        _render_export(fi, ff)

        # El nodo CMG ahora se elige en la vista Resumen; se persiste en session_state.
        nodo_cmg = st.session_state.get("nodo_cmg", "CRUCERO_______220")

        st.markdown(f"""
        <div style="border-top:1px solid rgba(255,255,255,0.14);padding-top:12px;margin-top:16px;text-align:center;font-size:0.68rem;color:rgba(255,255,255,0.5)">
            {datetime.now().strftime("%d/%m/%Y · %H:%M")}<br>
            Creado por <b style="color:rgba(255,255,255,0.8)">Erick Herrera</b>
        </div>
        """, unsafe_allow_html=True)

    return {
        "fi": fi, "ff": ff, "hoy": hoy,
        "s": fi.strftime("%Y-%m-%d"), "e": ff.strftime("%Y-%m-%d"),
        "mostrar_prog": True, "mostrar_cmg": True, "nodo_cmg": nodo_cmg,
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
