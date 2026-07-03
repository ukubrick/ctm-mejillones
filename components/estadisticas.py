"""
components/estadisticas.py — Vista consolidada de estadísticos.

Reúne en un solo lugar todos los gráficos analíticos que antes vivían dispersos
(pestaña "Estadísticas" de Análisis de Costo, precisión PCP vs real, factor de
planta, distribución/correlación de CMG). Paleta corporativa AES.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (COLORES, LABELS, PMAX, UNIDADES, BG_TRANSP, C_GRID,
                    AES_AZUL, AES_VIOLETA)
from components._common import metricas_precision


def render_estadisticas(df_r, df_p, df_c, s=None, e=None):
    st.markdown('<div class="sec">ESTADÍSTICOS · APORTE, PRECISIÓN Y PRECIOS</div>',
                unsafe_allow_html=True)

    if df_r.empty:
        st.info("Sin datos de generación para el período seleccionado.")
        return

    # ── Cruce gen × CMG para ingreso estimado ────────────────────────────────
    tiene_cmg = df_c is not None and not df_c.empty
    if tiene_cmg:
        df_merge = pd.merge_asof(
            df_r[["unidad", "fecha_hora", "gen_real_mw"]].sort_values("fecha_hora"),
            df_c[["fecha_hora", "cmg_usd_mwh"]].sort_values("fecha_hora"),
            on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
        )
        df_merge["ingreso_usd"] = df_merge["gen_real_mw"] * df_merge["cmg_usd_mwh"]
        ingreso_unit = df_merge.groupby("unidad")["ingreso_usd"].sum()
    else:
        df_merge = None
        ingreso_unit = pd.Series(dtype=float)
    energia_unit = df_r.groupby("unidad")["gen_real_mw"].sum()

    # ── KPIs de cabecera ─────────────────────────────────────────────────────
    energia_total = energia_unit.sum()
    horas = df_r["fecha_hora"].dt.floor("h").nunique() or 1
    fp_global = (df_r["gen_real_mw"].sum() / horas) / sum(PMAX.values()) * 100
    kpis = [
        ("Energía total", f"{energia_total:,.0f}", "MWh en el período"),
        ("Factor de planta", f"{fp_global:.1f}%", "promedio 4 unidades"),
    ]
    if tiene_cmg:
        kpis.append(("Ingreso estimado", f"${ingreso_unit.sum():,.0f}", "USD (gen × CMG)"))
        kpis.append(("CMG promedio", f"{df_c['cmg_usd_mwh'].mean():.1f}", "USD/MWh"))
    cols = st.columns(len(kpis))
    for col, (lbl, val, sub) in zip(cols, kpis):
        col.metric(lbl, val, sub)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Fila 1: aporte energético + precisión de la programación ─────────────
    c1, c2 = st.columns(2)
    with c1:
        _grafico_aporte_energia(energia_unit)
    with c2:
        _grafico_precision(df_r, df_p)

    # ── Fila 2: factor de planta + participación de ingresos ─────────────────
    c3, c4 = st.columns(2)
    with c3:
        _grafico_factor_planta(df_r)
    with c4:
        if tiene_cmg and ingreso_unit.sum() > 0:
            _grafico_participacion(ingreso_unit)
        else:
            st.caption("Participación de ingresos: requiere datos de CMG.")

    # ── Fila 3: distribución y correlación de CMG ────────────────────────────
    if tiene_cmg:
        c5, c6 = st.columns(2)
        with c5:
            _grafico_hist_cmg(df_c)
        with c6:
            _grafico_correlacion(df_merge)


def _layout(fig, titulo, y_title=None, height=310, **kw):
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=13, color="#0F172A"), x=0),
        height=height, margin=dict(l=10, r=14, t=50, b=10),
        plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
        xaxis=dict(showgrid=False, tickfont=dict(color="#475569", size=11)),
        yaxis=dict(gridcolor=C_GRID, tickfont=dict(color="#94A3B8", size=10),
                   title=y_title, title_font=dict(color="#94A3B8", size=10)),
        **kw)
    return fig


def _grafico_aporte_energia(energia_unit):
    vals = [energia_unit.get(u, 0) for u in UNIDADES]
    fig = go.Figure(go.Bar(
        x=[LABELS[u] for u in UNIDADES], y=vals,
        marker=dict(color=[COLORES[u]["line"] for u in UNIDADES],
                    line=dict(color="rgba(255,255,255,0.6)", width=1)),
        text=[f"{v:,.0f}" for v in vals], textposition="outside",
        textfont=dict(size=11, color="#475569"),
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} MWh<extra></extra>"))
    _layout(fig, "Aporte energético por unidad (MWh)", "MWh")
    fig.update_yaxes(range=[0, max(vals) * 1.18 if vals else 1])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _grafico_precision(df_r, df_p):
    if df_p is None or df_p.empty:
        st.caption("Precisión PCP vs real: sin datos de programación en el período.")
        return
    filas = []
    for u in UNIDADES:
        res = metricas_precision(df_r[df_r["unidad"] == u], df_p[df_p["unidad"] == u])
        if res is not None:
            filas.append((u, *res))
    if not filas:
        st.caption("Precisión PCP vs real: sin cruce disponible.")
        return
    labels = [LABELS[u] for u, *_ in filas]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="MAE", x=labels, y=[f[1] for f in filas],
        marker_color=AES_AZUL, text=[f"{f[1]:.1f}" for f in filas], textposition="outside"))
    fig.add_trace(go.Bar(name="RMSE", x=labels, y=[f[2] for f in filas],
        marker_color=AES_VIOLETA, text=[f"{f[2]:.1f}" for f in filas], textposition="outside"))
    _layout(fig, "Precisión de la programación PCP vs real (MW)", "MW",
            barmode="group", legend=dict(orientation="h", y=-0.18, font=dict(size=10)))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    sesgos = " · ".join(f"{LABELS[u]}: {b:+.1f}" for u, _, _, b in filas)
    st.caption(f"Sesgo medio (real − programada): {sesgos} · MAE = error absoluto medio, "
               "RMSE penaliza desvíos grandes.")


def _grafico_factor_planta(df_r):
    fp = {}
    for u in UNIDADES:
        dfu = df_r[df_r["unidad"] == u]
        if dfu.empty:
            continue
        h = dfu["fecha_hora"].dt.floor("h").nunique() or 1
        fp[u] = (dfu["gen_real_mw"].sum() / h) / PMAX.get(u, 1) * 100
    fig = go.Figure(go.Bar(
        x=[LABELS[u] for u in fp], y=[fp[u] for u in fp],
        marker=dict(color=[COLORES[u]["line"] for u in fp]),
        text=[f"{fp[u]:.0f}%" for u in fp], textposition="outside",
        textfont=dict(size=11, color="#475569"),
        hovertemplate="<b>%{x}</b><br>Factor de planta %{y:.1f}%<extra></extra>"))
    _layout(fig, "Factor de planta por unidad (%)", "%")
    fig.update_yaxes(range=[0, 105])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _grafico_participacion(ingreso_unit):
    us = [u for u in UNIDADES if ingreso_unit.get(u, 0) > 0]
    fig = go.Figure(go.Pie(
        labels=[LABELS[u] for u in us], values=[ingreso_unit.get(u, 0) for u in us],
        hole=0.55, marker=dict(colors=[COLORES[u]["line"] for u in us]),
        textfont=dict(size=11),
        hovertemplate="%{label}<br><b>$%{value:,.0f} USD</b><br>%{percent}<extra></extra>"))
    total = ingreso_unit.sum()
    fig.update_layout(
        title=dict(text="Participación en ingresos estimados", font=dict(size=13, color="#0F172A"), x=0),
        height=310, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor=BG_TRANSP,
        legend=dict(orientation="h", y=-0.1, font=dict(size=10)),
        annotations=[dict(text=f"${total:,.0f}<br><span style='font-size:10px'>USD total</span>",
                          x=0.5, y=0.5, font_size=13, showarrow=False)])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _grafico_hist_cmg(df_c):
    prom = df_c["cmg_usd_mwh"].mean()
    fig = go.Figure(go.Histogram(x=df_c["cmg_usd_mwh"], nbinsx=20,
        marker_color=COLORES["CMG"]["line"], opacity=0.78,
        hovertemplate="CMG: %{x:.1f} USD/MWh<br>Horas: %{y}<extra></extra>"))
    fig.add_vline(x=prom, line_color="#94A3B8", line_dash="dot",
        annotation_text=f"Prom {prom:.1f}", annotation_position="top right",
        annotation_font_color="#64748B", annotation_font_size=10)
    _layout(fig, "Distribución de precios CMG (USD/MWh)", "Horas", bargap=0.08)
    fig.update_xaxes(title="USD/MWh", tickfont=dict(color="#94A3B8", size=10))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _grafico_correlacion(df_merge):
    df_corr = (df_merge.dropna().groupby("fecha_hora")
               .agg(gen_total=("gen_real_mw", "sum"), cmg=("cmg_usd_mwh", "mean")).reset_index())
    fig = go.Figure(go.Scatter(x=df_corr["gen_total"], y=df_corr["cmg"], mode="markers",
        marker=dict(color=COLORES["CMG"]["line"], size=6, opacity=0.55),
        hovertemplate="Gen: %{x:.0f} MW<br>CMG: %{y:.1f} USD/MWh<extra></extra>"))
    if len(df_corr) > 2:
        coef = np.polyfit(df_corr["gen_total"], df_corr["cmg"], 1)
        xl = [df_corr["gen_total"].min(), df_corr["gen_total"].max()]
        fig.add_trace(go.Scatter(x=xl, y=[coef[0]*x + coef[1] for x in xl], mode="lines",
            line=dict(color="#94A3B8", dash="dot", width=1.5), showlegend=False))
        r = df_corr["gen_total"].corr(df_corr["cmg"])
        fig.add_annotation(xref="paper", yref="paper", x=0.98, y=0.96, showarrow=False,
            text=f"r = {r:.2f}", font=dict(size=11, color="#64748B"), align="right")
    _layout(fig, "Generación total vs CMG (correlación horaria)", "CMG USD/MWh")
    fig.update_xaxes(title="MW generados (total)", tickfont=dict(color="#94A3B8", size=10))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
