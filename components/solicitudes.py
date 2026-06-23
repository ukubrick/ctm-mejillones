"""components/solicitudes.py — Solicitudes de trabajo AES Andes (cards + tabla)."""
import streamlit as st
import pandas as pd

from config import STATUS_COLOR_SOL, TIPO_LABEL, TYPE_LABEL
from utils.data import load_solicitudes


def _cards(df_view):
    if df_view.empty:
        st.info("Sin registros.")
        return
    for _, row in df_view.head(5).iterrows():
        st_key = str(row.get("status", "")).lower()
        c_txt, c_bg = STATUS_COLOR_SOL.get(st_key, ("#475569", "#F8FAFC"))
        tipo_lbl = TIPO_LABEL.get(str(row.get("tipo_solicitud", "")), str(row.get("tipo_solicitud", "")))
        type_lbl = TYPE_LABEL.get(str(row.get("type", "")), str(row.get("type", "")))
        inst = str(row.get("instalacion_nombre") or "—")
        f_ini = str(row.get("fecha_inicio") or "—")[:16]
        f_fin = str(row.get("fecha_fin") or "—")[:16]
        corr = int(row["correlativo"]) if pd.notna(row.get("correlativo")) else "—"
        riesgo = str(row.get("descripcion_nivel_riesgo") or "—")
        st.markdown(f"""
        <div style="background:{c_bg};border-left:4px solid {c_txt};border-radius:6px;
                    padding:0.6rem 0.9rem;margin-bottom:0.5rem;font-size:0.82rem">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem">
                <span style="font-weight:700;color:#1E293B">N° {corr} — {inst}</span>
                <span style="background:{c_txt};color:#fff;border-radius:4px;padding:2px 8px;font-size:0.72rem;font-weight:600">{st_key.replace("_"," ").upper()}</span>
            </div>
            <div style="color:#475569;line-height:1.7">
                <b>Tipo:</b> {tipo_lbl} · {type_lbl} &nbsp;|&nbsp;
                <b>Inicio:</b> {f_ini} &nbsp;|&nbsp; <b>Fin:</b> {f_fin}<br>
                <b>Riesgo:</b> {riesgo[:120]}{'…' if len(riesgo) > 120 else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)
    if len(df_view) > 5:
        st.caption(f"+{len(df_view) - 5} más en «Tabla completa»")


def render_solicitudes(s, e):
    st.markdown('<div class="sec">SOLICITUDES DE TRABAJO — AES ANDES</div>', unsafe_allow_html=True)
    df = load_solicitudes(s, e)
    if df.empty:
        st.info("Sin solicitudes de trabajo registradas para el período seleccionado.")
        return

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total solicitudes", len(df))
    k2.metric("Pendientes", int((df["status"] == "pendiente").sum()))
    k3.metric("Ejecutadas", int((df["status"] == "ejecucion_exitosa").sum()))
    k4.metric("Desconexiones", int((df["tipo_solicitud"] == "desconexion").sum()))

    tab_todas, tab_pend, tab_tabla = st.tabs(["Todas", "Pendientes", "Tabla completa"])
    with tab_todas:
        _cards(df)
    with tab_pend:
        _cards(df[df["status"] == "pendiente"])
    with tab_tabla:
        cols = ["correlativo", "empresa_nombre", "instalacion_nombre", "status",
                "tipo_solicitud", "type", "fecha_inicio", "fecha_fin"]
        df_t = df[cols].copy()
        df_t.columns = ["Correlativo", "Empresa", "Instalación", "Status", "Tipo", "Elemento", "Inicio", "Fin"]
        hdrs = "".join(f'<th style="padding:5px 10px;background:#F1F5F9;font-size:0.72rem;text-align:left">{c}</th>' for c in df_t.columns)
        rows = ""
        for _, r in df_t.iterrows():
            cells = "".join(f'<td style="padding:5px 10px;font-size:0.72rem;border-bottom:1px solid #F1F5F9;white-space:nowrap">{str(r[c]) if pd.notna(r[c]) else ""}</td>' for c in df_t.columns)
            rows += f"<tr>{cells}</tr>"
        st.markdown(f'<div style="overflow-x:auto;margin-top:0.5rem"><table style="border-collapse:collapse;width:100%">'
                    f'<thead><tr>{hdrs}</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
