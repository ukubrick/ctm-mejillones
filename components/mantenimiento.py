"""components/mantenimiento.py — Programas de mantenimiento mayor CTM.

Fuente: /programas-mantenimiento-mayor/v4 (SIP), integrado 2026-07-08. La tabla
solo contiene los programas relevantes para el complejo o su corredor de
evacuación (Angamos, Cochrane, Mejillones, S/E O'Higgins, Laberinto, Kapatur,
Crucero — el filtro vive en la adquisición). Incluye programas FUTUROS ya
publicados (la ventana de adquisición filtra por fecha de publicación).

Vista: KPIs + línea de tiempo (Gantt simple, un programa por fila) + tabla.
"""
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import BG_TRANSP, C_GRID
from utils.data import load_mantenimiento_mayor
from components._common import render_guia

_ESTADO_COLOR = {
    "aprobado":   ("#16A34A", "#DCFCE7"),
    "pendiente":  ("#D97706", "#FEF3C7"),
    "rechazado":  ("#DC2626", "#FEE2E2"),
    "finalizado": ("#64748B", "#F1F5F9"),
}

_CUERPO_GUIA = (
    "<p>El <strong>Programa de Mantenimiento Mayor (PMPM)</strong> del Coordinador registra los "
    "trabajos mayores a 24 horas asociados a desconexiones de líneas, centrales y subestaciones, "
    "con planificación hasta 18 meses.</p>"
    "<p>Aquí se muestran solo los programas que afectan al complejo o a su corredor de "
    "evacuación: <strong>Angamos, Cochrane, Mejillones, S/E O'Higgins, Laberinto, Kapatur y "
    "Crucero</strong>. Un mantenimiento en la línea Mejillones–O'Higgins o en la S/E O'Higgins "
    "puede restringir la evacuación de las unidades aunque no las intervenga directamente.</p>"
)


def _color_estado(estado):
    return _ESTADO_COLOR.get(str(estado or "").strip().lower(), ("#475569", "#F8FAFC"))


def render_mantenimiento(s, e):
    st.markdown('<div class="sec">Mantenimiento mayor · complejo y corredor de evacuación</div>',
                unsafe_allow_html=True)
    render_guia("Qué es el mantenimiento mayor (PMPM) y qué se muestra aquí", _CUERPO_GUIA)

    df = load_mantenimiento_mayor()
    if df.empty:
        st.info("Aún no hay programas de mantenimiento mayor registrados. "
                "La adquisición diaria los incorpora automáticamente.")
        return

    hoy = pd.Timestamp(date.today())
    ini = df["fecha_inicio_programa_dt"]
    fin = df["fecha_fin_programa_dt"]
    en_curso = df[(ini <= hoy) & (fin >= hoy)]
    futuros = df[ini > hoy]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Programas registrados", len(df))
    k2.metric("En curso hoy", len(en_curso))
    k3.metric("Próximos", len(futuros))
    prox_txt = "—"
    if not futuros.empty:
        prox = futuros.sort_values("fecha_inicio_programa_dt").iloc[0]
        prox_txt = prox["fecha_inicio_programa_dt"].strftime("%d-%m-%Y")
    k4.metric("Próximo inicio", prox_txt)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    _timeline(df, hoy)
    _tabla(df)


def _timeline(df, hoy):
    """Gantt simple: una barra horizontal por programa (inicio → fin), color por
    estado, línea vertical en «hoy». Un solo eje temporal."""
    d = df.dropna(subset=["fecha_inicio_programa_dt", "fecha_fin_programa_dt"]).copy()
    # Últimos 60 días + todo lo futuro, para que la vista no crezca sin límite.
    d = d[d["fecha_fin_programa_dt"] >= hoy - pd.Timedelta(days=60)]
    if d.empty:
        st.caption("Sin programas vigentes o próximos para graficar.")
        return
    d = d.sort_values("fecha_inicio_programa_dt").tail(25)
    d["etiqueta"] = (d["nombre_instalacion"].fillna("").str.slice(0, 38) + "  ·  " +
                     d["fecha_inicio_programa_dt"].dt.strftime("%d-%m"))

    fig = go.Figure()
    for _, r in d.iterrows():
        c_txt, _ = _color_estado(r.get("estado"))
        fig.add_trace(go.Scatter(
            x=[r["fecha_inicio_programa_dt"], r["fecha_fin_programa_dt"]],
            y=[r["etiqueta"], r["etiqueta"]],
            mode="lines", line=dict(color=c_txt, width=9),
            hovertemplate=(f"<b>{str(r.get('nombre_instalacion') or '')[:60]}</b><br>"
                           f"{str(r.get('nombre_sub_instalacion') or '')[:60]}<br>"
                           f"%{{x|%d-%m-%Y}}<br>Estado: {r.get('estado') or '—'}"
                           "<extra></extra>"),
            showlegend=False))
    fig.add_vline(x=hoy.timestamp() * 1000, line_dash="dash", line_color="#94A3B8",
                  line_width=1, annotation_text="hoy", annotation_position="top")
    fig.update_layout(
        title=dict(text="Línea de tiempo de programas (inicio → fin)",
                   font=dict(size=13, color="#0F172A"), x=0),
        height=max(240, 34 * len(d) + 90), margin=dict(l=10, r=14, t=52, b=10),
        plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
        font=dict(family="Inter, sans-serif"),
        xaxis=dict(showgrid=True, gridcolor=C_GRID, tickformat="%d-%m",
                   tickfont=dict(color="#94A3B8", size=10)),
        yaxis=dict(showgrid=False, tickfont=dict(color="#475569", size=10),
                   autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key="mant_timeline")
    st.caption("Verde = aprobado · ámbar = pendiente · gris = finalizado. La línea "
               "discontinua marca hoy.")


def _tabla(df):
    filas = ""
    for _, r in df.head(40).iterrows():
        c_txt, c_bg = _color_estado(r.get("estado"))
        desc = str(r.get("descripcion_trabajo") or "").strip()
        f_ini = (r["fecha_inicio_programa_dt"].strftime("%d-%m-%Y")
                 if pd.notna(r.get("fecha_inicio_programa_dt")) else "—")
        f_fin = (r["fecha_fin_programa_dt"].strftime("%d-%m-%Y")
                 if pd.notna(r.get("fecha_fin_programa_dt")) else "—")
        filas += (
            "<tr>"
            f'<td style="padding:6px 10px;font-size:0.74rem;border-bottom:1px solid #F1F5F9;'
            f'white-space:nowrap">{f_ini} → {f_fin}</td>'
            f'<td style="padding:6px 10px;font-size:0.74rem;border-bottom:1px solid #F1F5F9">'
            f'<b>{str(r.get("nombre_instalacion") or "—")[:50]}</b><br>'
            f'<span style="color:#94A3B8">{str(r.get("nombre_sub_instalacion") or "")[:50]}</span></td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #F1F5F9;white-space:nowrap">'
            f'<span style="background:{c_bg};color:{c_txt};font-weight:600;font-size:0.68rem;'
            f'padding:2px 8px;border-radius:5px">{str(r.get("estado") or "—")}</span></td>'
            f'<td style="padding:6px 10px;font-size:0.72rem;color:#475569;'
            f'border-bottom:1px solid #F1F5F9">{desc[:130]}{"…" if len(desc) > 130 else ""}</td>'
            "</tr>")
    hdr = "".join(
        f'<th style="padding:7px 10px;text-align:left;font-size:0.66rem;color:#64748B;'
        f'text-transform:uppercase;letter-spacing:0.4px;border-bottom:2px solid #E2E8F0;'
        f'white-space:nowrap">{h}</th>'
        for h in ("Programa", "Instalación", "Estado", "Trabajo"))
    st.markdown(
        '<div style="border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;background:#FFFFFF;'
        'margin-top:0.6rem"><div style="overflow-x:auto">'
        '<table style="border-collapse:collapse;width:100%">'
        f'<thead style="background:#F8FAFC"><tr>{hdr}</tr></thead>'
        f'<tbody>{filas}</tbody></table></div></div>',
        unsafe_allow_html=True)
