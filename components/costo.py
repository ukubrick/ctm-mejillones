"""components/costo.py — Análisis de costo: aporte económico CMG × generación.

Vista de overview (KPIs + ingreso por unidad + evolución del CMG). Los
estadísticos profundos se consolidaron en components/estadisticas.py.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import COLORES, LABELS, UNIDADES, BG, GR, SERIE, CMG_A_DEMANDA
from utils.data import load_cmg_prog, load_cmg_real, load_pronostico_demanda
from utils.plotly_theme import hex_to_rgba


def render_costo(df_r, df_c, s=None, e=None, nodo_cmg="CRUCERO_______220", df_p=None):
    st.markdown('<div class="sec">Análisis de costo · CMG × generación</div>', unsafe_allow_html=True)

    if df_c.empty:
        st.info("Sin datos de CMG para calcular estadísticos de costo.")
        return

    df_cp = load_cmg_prog(s, e, nodo_cmg) if s and e else None
    df_cr = load_cmg_real(s, e, nodo_cmg) if s and e else None
    barra_dem = CMG_A_DEMANDA.get(nodo_cmg, "Crucero220")
    df_dem = load_pronostico_demanda(s, e, barra_dem) if s and e else None

    df_merge = pd.merge_asof(
        df_r[["unidad", "fecha_hora", "gen_real_mw"]].sort_values("fecha_hora"),
        df_c[["fecha_hora", "cmg_usd_mwh"]].sort_values("fecha_hora"),
        on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
    )
    df_merge["ingreso_usd"] = df_merge["gen_real_mw"] * df_merge["cmg_usd_mwh"]
    ingreso_unit  = df_merge.groupby("unidad")["ingreso_usd"].sum()
    energia_unit  = df_r.groupby("unidad")["gen_real_mw"].sum()
    ingreso_total = ingreso_unit.sum()
    energia_total = energia_unit.sum()
    cmg_prom = df_c["cmg_usd_mwh"].mean()
    cmg_min  = df_c["cmg_usd_mwh"].min()
    cmg_max  = df_c["cmg_usd_mwh"].max()
    unidades_ord = UNIDADES

    # Desvío CMG real vs programado (si hay programado disponible)
    desvio_cmg = None
    if df_cp is not None and not df_cp.empty:
        m = pd.merge_asof(
            df_c[["fecha_hora", "cmg_usd_mwh"]].sort_values("fecha_hora"),
            df_cp[["fecha_hora", "cmg_usd_mwh"]].rename(columns={"cmg_usd_mwh": "prog"}).sort_values("fecha_hora"),
            on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
        ).dropna()
        if not m.empty:
            desvio_cmg = (m["cmg_usd_mwh"] - m["prog"]).mean()

    kpis = [
        ("Ingreso Total Est.", f"${ingreso_total:,.0f}", "USD en el período"),
        ("Energía Total",      f"{energia_total:,.0f}",  "MWh generados"),
        ("CMG Promedio",       f"{cmg_prom:.1f}",        "USD/MWh"),
        ("Rango CMG",          f"{cmg_min:.1f} – {cmg_max:.1f}", "USD/MWh mín/máx"),
    ]
    if desvio_cmg is not None:
        kpis.append(("Desvío CMG real vs prog.", f"{desvio_cmg:+.1f}", "USD/MWh medio"))

    # Desvío CMG online (S3) vs real oficial liquidado (si hay datos en común)
    if df_cr is not None and not df_cr.empty:
        mr = pd.merge_asof(
            df_c[["fecha_hora", "cmg_usd_mwh"]].sort_values("fecha_hora"),
            df_cr[["fecha_hora", "cmg_usd_mwh"]].rename(columns={"cmg_usd_mwh": "real"}).sort_values("fecha_hora"),
            on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
        ).dropna()
        if not mr.empty:
            kpis.append(("Desvío online vs real oficial",
                         f"{(mr['cmg_usd_mwh'] - mr['real']).mean():+.1f}", "USD/MWh medio"))
    cols = st.columns(len(kpis))
    for col, (lbl, val, sub) in zip(cols, kpis):
        col.metric(lbl, val, sub)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Vista de aporte económico: ingreso por unidad + evolución del CMG.
    # Los estadísticos profundos viven ahora en la vista «Estadísticas».
    gc1, gc2 = st.columns(2)
    with gc1:
        _grafico_barras_ingreso(ingreso_unit, energia_unit, unidades_ord)
    with gc2:
        _grafico_cmg_tiempo(df_c, cmg_prom, cmg_min, cmg_max, df_cp, df_cr, df_dem, barra_dem)


def _grafico_barras_ingreso(ingreso_unit, energia_unit, unidades_ord):
    n_bars = len(unidades_ord)
    bar_w, dx, dy_pct = 0.42, 0.13, 0.06
    y_vals = [ingreso_unit.get(u, 0) for u in unidades_ord]
    y_max  = max(y_vals) if y_vals else 1
    dy     = y_max * dy_pct
    e_vals = [energia_unit.get(u, 0) for u in unidades_ord]
    e_max  = max(e_vals) if e_vals else 1
    e_scale = y_max / e_max if e_max else 1

    fig = go.Figure()
    for i, u in enumerate(unidades_ord):
        val = y_vals[i]
        hex_c = COLORES[u]["line"]
        r_c, g_c, b_c = int(hex_c[1:3], 16), int(hex_c[3:5], 16), int(hex_c[5:7], 16)
        col_front = hex_to_rgba(hex_c, 0.88)
        col_side  = f"rgba({max(0,r_c-55)},{max(0,g_c-55)},{max(0,b_c-55)},0.92)"
        col_top   = f"rgba({min(255,r_c+45)},{min(255,g_c+45)},{min(255,b_c+45)},1.0)"
        x0, x1 = i - bar_w/2, i + bar_w/2
        fig.add_trace(go.Scatter(x=[x0, x1, x1, x0, x0], y=[0, 0, val, val, 0],
            fill="toself", fillcolor=col_front, line=dict(color="rgba(255,255,255,0.6)", width=1),
            mode="lines", showlegend=False,
            hovertemplate=f"<b>{LABELS[u]}</b><br>${val:,.0f} USD<extra></extra>"))
        fig.add_trace(go.Scatter(x=[x1, x1+dx, x1+dx, x1, x1], y=[0, dy, val+dy, val, 0],
            fill="toself", fillcolor=col_side, line=dict(color="rgba(0,0,0,0.15)", width=0.8),
            mode="lines", showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[x0, x1, x1+dx, x0+dx, x0], y=[val, val, val+dy, val+dy, val],
            fill="toself", fillcolor=col_top, line=dict(color="rgba(255,255,255,0.7)", width=0.8),
            mode="lines", showlegend=False, hoverinfo="skip"))
        fig.add_annotation(x=i + dx/2, y=val + dy + y_max*0.025, text=f"${val:,.0f}",
                           showarrow=False, font=dict(size=10, color="#334155"), xanchor="center")

    e_scaled = [v * e_scale for v in e_vals]
    fig.add_trace(go.Scatter(x=[i + dx/2 for i in range(n_bars)], y=e_scaled,
        name="Energía (MWh)", mode="markers+lines",
        marker=dict(size=10, color="#0F172A", symbol="diamond"),
        line=dict(color="#0F172A", width=1.8, dash="dot"),
        hovertemplate="<b>Energía</b><br>%{customdata:,.0f} MWh<extra></extra>", customdata=e_vals))
    for i, ev in enumerate(e_vals):
        fig.add_annotation(x=i + dx/2, y=e_scaled[i] + y_max*0.025, text=f"{ev:,.0f} MWh",
                           showarrow=False, font=dict(size=8, color="#64748B"), xanchor="center")

    fig.update_layout(
        title=dict(text="Ingreso Estimado + Energía por Unidad", font=dict(size=13, color="#0F172A"), x=0),
        height=360, margin=dict(l=10, r=20, t=60, b=40), plot_bgcolor=BG, paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickvals=list(range(n_bars)), ticktext=[LABELS[u] for u in unidades_ord],
                   tickfont=dict(color="#475569", size=11), showgrid=False, zeroline=False, range=[-0.55, n_bars-0.25]),
        yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="USD",
                   title_font=dict(color="#94A3B8", size=10), zeroline=True, zerolinecolor="#E2E8F0", range=[0, y_max*1.18]),
        legend=dict(orientation="h", y=-0.12, x=0, font=dict(size=10, color="#475569")), showlegend=True)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _grafico_cmg_tiempo(df_c, cmg_prom, cmg_min, cmg_max, df_cp=None, df_cr=None, df_dem=None, barra_dem="Crucero220"):
    idx_max = df_c["cmg_usd_mwh"].idxmax()
    idx_min = df_c["cmg_usd_mwh"].idxmin()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"], mode="none",
        fill="tozeroy", fillcolor="rgba(109,40,217,0.08)", showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"], mode="lines", name="CMG online",
        line=dict(color=SERIE["cmg"], width=1.8, shape="spline", smoothing=0.5), showlegend=True,
        hovertemplate="<b>Online</b> %{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>"))
    # Overlay CMG programado (PID), si existe
    if df_cp is not None and not df_cp.empty:
        fig.add_trace(go.Scatter(x=df_cp["fecha_hora"], y=df_cp["cmg_usd_mwh"], mode="lines", name="CMG programado",
            line=dict(color=SERIE["cmg_prog"], width=1.4, dash="dash"),
            hovertemplate="<b>Programado</b> %{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>"))
    # Overlay CMG real oficial liquidado (rezago ~10 días), si existe
    if df_cr is not None and not df_cr.empty:
        fig.add_trace(go.Scatter(x=df_cr["fecha_hora"], y=df_cr["cmg_usd_mwh"], mode="lines", name="CMG real oficial",
            line=dict(color="#0F766E", width=1.6),
            hovertemplate="<b>Real oficial</b> %{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>"))
    # Overlay demanda pronosticada (eje secundario): alta demanda anticipa CMG alto
    if df_dem is not None and not df_dem.empty:
        fig.add_trace(go.Scatter(x=df_dem["fecha_hora"], y=df_dem["energia_mwh"], mode="lines",
            name=f"Demanda {barra_dem}", yaxis="y2",
            line=dict(color="#64748B", width=1.2, dash="dot"),
            hovertemplate="<b>Demanda</b> %{x|%d/%m %H:%M}<br>%{y:,.0f} MWh<extra></extra>"))
    fig.add_hline(y=cmg_prom, line_color="#CBD5E1", line_width=1.2, line_dash="dot",
        annotation_text=f"Prom: {cmg_prom:.1f}", annotation_position="right",
        annotation_font_color="#64748B", annotation_font_size=10)
    fig.add_trace(go.Scatter(x=[df_c.loc[idx_max, "fecha_hora"]], y=[cmg_max], mode="markers",
        showlegend=False, hoverinfo="skip",
        marker=dict(size=22, color="rgba(239,68,68,0.15)", symbol="circle", line=dict(color="rgba(239,68,68,0.4)", width=1.5))))
    fig.add_trace(go.Scatter(x=[df_c.loc[idx_min, "fecha_hora"]], y=[cmg_min], mode="markers",
        showlegend=False, hoverinfo="skip",
        marker=dict(size=22, color="rgba(16,185,129,0.15)", symbol="circle", line=dict(color="rgba(16,185,129,0.4)", width=1.5))))
    fig.add_trace(go.Scatter(x=[df_c.loc[idx_max, "fecha_hora"]], y=[cmg_max], mode="markers+text",
        marker=dict(size=10, color="#EF4444", symbol="triangle-up", line=dict(color="#fff", width=1.5)),
        text=[f"  Máx: {cmg_max:.1f}"], textposition="top right", textfont=dict(size=10, color="#EF4444"), showlegend=False))
    fig.add_trace(go.Scatter(x=[df_c.loc[idx_min, "fecha_hora"]], y=[cmg_min], mode="markers+text",
        marker=dict(size=10, color="#10B981", symbol="triangle-down", line=dict(color="#fff", width=1.5)),
        text=[f"  Mín: {cmg_min:.1f}"], textposition="bottom right", textfont=dict(size=10, color="#10B981"), showlegend=False))
    fig.update_layout(
        title=dict(text="CMG online · programado · real oficial", font=dict(size=13, color="#0F172A"), x=0),
        height=360, margin=dict(l=10, r=80, t=60, b=10), plot_bgcolor=BG, paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10, color="#475569")),
        yaxis=dict(title="USD/MWh", gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title_font=dict(color="#94A3B8", size=10)),
        yaxis2=dict(title="Demanda MWh", overlaying="y", side="right", showgrid=False,
                    tickfont=dict(color="#94A3B8", size=10), title_font=dict(color="#94A3B8", size=10)),
        xaxis=dict(tickfont=dict(color="#94A3B8", size=10), tickformat="%d/%m\n%H:%M", showgrid=False),
        hovermode="x unified", hoverlabel=dict(bgcolor="#1E293B", font_color="#F8FAFC", bordercolor="#334155"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
