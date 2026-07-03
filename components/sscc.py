"""components/sscc.py — Servicios Complementarios (instrucciones SSCC)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import COLORES_SSCC, BADGE_SSCC, LABELS, UNIDADES
from utils.data import load_sscc
from components._common import render_guia, tabla_guia, render_cards_unidad

_FILAS_GUIA = [
    ("CSF(+)", "Control Secundario de Frecuencia en <strong>subida</strong> — la unidad debe estar disponible para aumentar potencia y corregir la frecuencia del sistema"),
    ("CSF(−)", "Control Secundario de Frecuencia en <strong>bajada</strong> — la unidad debe estar disponible para reducir potencia"),
    ("CPF(+)", "Control Primario de Frecuencia en <strong>subida</strong> — respuesta automática e inmediata ante caída de frecuencia"),
    ("CPF(−)", "Control Primario de Frecuencia en <strong>bajada</strong> — respuesta automática ante alza de frecuencia"),
    ("CT",     "Control de <strong>Tensión</strong> — regulación de tensión reactiva en la barra de conexión"),
    ("CTF",    "Control <strong>Terciario de Frecuencia</strong> — reserva de potencia de respuesta más lenta (minutos) que activa el Coordinador para restablecer la frecuencia nominal tras un evento"),
]
_CUERPO_GUIA = (
    "<p>Los <strong>Servicios Complementarios (SSCC)</strong> son prestaciones que el Coordinador Eléctrico Nacional instruye "
    "a las unidades generadoras para mantener la seguridad y calidad del Sistema Eléctrico Nacional, "
    "más allá de su generación de energía.</p>"
    + tabla_guia(_FILAS_GUIA, ("Instrucción", "Significado")) +
    "<p>Cada instrucción indica un <strong>período de prestación</strong> (inicio → fin) durante el cual la unidad debe "
    "mantener una reserva de potencia disponible. El campo <strong>Disp. MW</strong> indica la capacidad comprometida cuando está declarada.</p>"
)


def render_sscc(s, e):
    st.markdown('<div class="sec">SERVICIOS COMPLEMENTARIOS (SSCC)</div>', unsafe_allow_html=True)
    render_guia("Guía de instrucciones SSCC — CSF, CPF, CT, CTF", _CUERPO_GUIA)

    df = load_sscc(s, e)
    if df.empty:
        st.info("Sin datos SSCC para el período seleccionado. Los datos se adquieren automáticamente cada hora.")
        return

    dias = df["fecha"].nunique()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Instrucciones totales", len(df))
    k2.metric("Unidades con SSCC", f"{df['unidad'].nunique()} / 4")
    k3.metric("Tipos de servicio", df["instruccion_sscc"].nunique())
    k4.metric("Días con datos", dias)
    st.markdown("")

    sub = st.radio("Sección", ["Por unidad", "Estadísticas", "Tabla completa"], horizontal=True,
                   label_visibility="collapsed", key="sscc_sub")
    if sub == "Por unidad":
        _por_unidad(df)
    elif sub == "Estadísticas":
        _estadisticas(df, dias)
    else:
        _tabla(df)


def _card_sscc(row, unidad, es_primera):
    tipo = str(row["instruccion_sscc"])
    color = COLORES_SSCC.get(tipo, "#64748B")
    bg = BADGE_SSCC.get(tipo, "#F1F5F9")
    ini = str(row["inicio_periodo"])[:5] if row["inicio_periodo"] else "—"
    fin = str(row["fin_periodo"])[:5] if row["fin_periodo"] else "—"
    extra = ' sscc-latest' if es_primera else ''
    return (f'<div class="sscc-card{extra}" style="border:1px solid {color}33;border-left:3px solid {color};'
            f'background:{bg};border-radius:6px;padding:6px 10px;margin-bottom:6px;">'
            f'<span style="font-weight:700;color:{color};font-size:0.8rem">{tipo}</span>'
            f'<span style="color:#64748B;font-size:0.72rem;float:right">{row["fecha"]}</span><br>'
            f'<span style="color:#475569;font-size:0.72rem">{ini} → {fin}</span></div>')


def _por_unidad(df):
    render_cards_unidad(df, _card_sscc, orden_cols=["fecha", "inicio_periodo"])


def _estadisticas(df, dias):
    from config import BG_TRANSP as BG, C_GRID as GR
    conteo = df.groupby("instruccion_sscc").size().reset_index(name="count").sort_values("count", ascending=False)
    fig_tipos = go.Figure(go.Bar(x=conteo["instruccion_sscc"], y=conteo["count"],
        marker_color=[COLORES_SSCC.get(t, "#64748B") for t in conteo["instruccion_sscc"]],
        text=conteo["count"], textposition="outside"))
    fig_tipos.update_layout(title=dict(text="Instrucciones por tipo de SSCC", font=dict(size=13, color="#0F172A"), x=0),
        height=280, margin=dict(l=10, r=10, t=50, b=10), plot_bgcolor=BG, paper_bgcolor=BG,
        xaxis=dict(tickfont=dict(color="#94A3B8", size=11), showgrid=False),
        yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="N° instrucciones"))

    pivot = df.groupby(["unidad", "instruccion_sscc"]).size().reset_index(name="count")
    fig_unidad = go.Figure()
    for tipo in df["instruccion_sscc"].unique():
        d = pivot[pivot["instruccion_sscc"] == tipo]
        fig_unidad.add_trace(go.Bar(name=tipo, x=d["unidad"], y=d["count"], marker_color=COLORES_SSCC.get(tipo, "#64748B")))
    fig_unidad.update_layout(barmode="stack", title=dict(text="Instrucciones por unidad", font=dict(size=13, color="#0F172A"), x=0),
        height=280, margin=dict(l=10, r=10, t=50, b=10), plot_bgcolor=BG, paper_bgcolor=BG,
        xaxis=dict(tickfont=dict(color="#94A3B8", size=11), showgrid=False),
        yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="N° instrucciones"),
        legend=dict(orientation="h", y=-0.2, font=dict(size=10)))

    c1, c2 = st.columns(2)
    c1.plotly_chart(fig_tipos, use_container_width=True, config={"displayModeBar": False})
    c2.plotly_chart(fig_unidad, use_container_width=True, config={"displayModeBar": False})

    def parse_hhmm(t):
        try:
            h, m, *_ = str(t).split(":")
            return int(h) + int(m) / 60
        except Exception:
            return None
    dd = df.copy()
    dd["h_ini"] = dd["inicio_periodo"].apply(parse_hhmm)
    dd["h_fin"] = dd["fin_periodo"].apply(parse_hhmm)
    dd["duracion_h"] = (dd["h_fin"] - dd["h_ini"]).clip(lower=0)
    dur = dd.groupby("instruccion_sscc")["duracion_h"].mean().reset_index().sort_values("duracion_h", ascending=False)
    fig_dur = go.Figure(go.Bar(x=dur["instruccion_sscc"], y=dur["duracion_h"].round(1),
        marker_color=[COLORES_SSCC.get(t, "#64748B") for t in dur["instruccion_sscc"]],
        text=dur["duracion_h"].round(1).astype(str) + " h", textposition="outside"))
    fig_dur.update_layout(title=dict(text="Duración promedio por tipo (horas)", font=dict(size=13, color="#0F172A"), x=0),
        height=280, margin=dict(l=10, r=10, t=50, b=10), plot_bgcolor=BG, paper_bgcolor=BG,
        xaxis=dict(tickfont=dict(color="#94A3B8", size=11), showgrid=False),
        yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="Horas promedio"))

    if dias > 1:
        evol = df.groupby(["fecha", "instruccion_sscc"]).size().reset_index(name="count")
        evol["fecha"] = pd.to_datetime(evol["fecha"])
        fig_evol = go.Figure()
        for tipo in sorted(df["instruccion_sscc"].unique()):
            d = evol[evol["instruccion_sscc"] == tipo]
            fig_evol.add_trace(go.Scatter(x=d["fecha"], y=d["count"], name=tipo, mode="lines+markers",
                line=dict(color=COLORES_SSCC.get(tipo, "#64748B"), width=2), marker=dict(size=6)))
        fig_evol.update_layout(title=dict(text="Evolución diaria de instrucciones SSCC", font=dict(size=13, color="#0F172A"), x=0),
            height=280, margin=dict(l=10, r=10, t=50, b=10), plot_bgcolor=BG, paper_bgcolor=BG,
            xaxis=dict(tickfont=dict(color="#94A3B8", size=10), showgrid=False, tickformat="%d/%m"),
            yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="N° instrucciones"),
            legend=dict(orientation="h", y=-0.2, font=dict(size=10)), hovermode="x unified")
        c3, c4 = st.columns(2)
        c3.plotly_chart(fig_dur, use_container_width=True, config={"displayModeBar": False})
        c4.plotly_chart(fig_evol, use_container_width=True, config={"displayModeBar": False})
    else:
        st.plotly_chart(fig_dur, use_container_width=True, config={"displayModeBar": False})


def _tabla(df):
    d = df.copy()
    d["inicio"] = d["inicio_periodo"].astype(str).str[:5]
    d["fin"] = d["fin_periodo"].astype(str).str[:5]
    d["motivo"] = d["motivo"].fillna("").str[:80]
    st.dataframe(
        d[["fecha", "unidad", "instruccion_sscc", "inicio", "fin", "disponibilidad", "motivo", "estado_sabana"]].rename(
            columns={"instruccion_sscc": "Instrucción", "inicio": "Inicio", "fin": "Fin",
                     "disponibilidad": "Disp. MW", "motivo": "Motivo", "estado_sabana": "Estado"}),
        use_container_width=True, hide_index=True)
