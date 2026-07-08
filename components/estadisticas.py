"""
components/estadisticas.py — Vista consolidada de estadísticos (rediseño 2026-07).

Panel analítico profesional del complejo. Reúne lo que antes vivía disperso y lo
amplía con gráficos de valor operacional y económico:

  · KPIs enriquecidos (energía, factor de planta, ingreso, CMG, ingreso realizado).
  · Mapa de calor de precios CMG por hora del día × fecha (patrón intradiario).
  · Curva de duración de precios CMG (¿cuántas horas el precio superó X?).
  · Ingreso acumulado por unidad en el tiempo (área apilada).
  · Perfil horario de generación por unidad (forma del despacho intradía).
  · Aporte energético y factor de planta por unidad.
  · Correlación generación total vs CMG (respuesta de mérito) y precisión PCP.

Paleta corporativa AES: unidades = tema categórico de orden fijo (violeta/azul/
cyan/verde); las magnitudes (CMG) usan una rampa secuencial violeta de un solo
matiz (claro→oscuro). Sin ejes duales. Grillas y ejes recesivos.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (COLORES, LABELS, PMAX, UNIDADES, BG_TRANSP, C_GRID,
                    AES_AZUL, AES_VIOLETA)
from components._common import metricas_precision

# Rampa secuencial AES de un solo matiz (violeta), claro→oscuro. Codifica MAGNITUD
# (precio CMG). Un solo hue, nunca arcoíris (regla dataviz para escalas secuenciales).
CMG_SCALE = [
    [0.00, "#F4EFFC"], [0.25, "#D3BEF5"], [0.50, "#A981EC"],
    [0.75, "#7C4DE0"], [1.00, "#4E2699"],
]
INK       = "#0F172A"   # texto de títulos
INK_MUTED = "#64748B"   # texto secundario
INK_AXIS  = "#94A3B8"   # ticks de eje


def render_estadisticas(df_r, df_p, df_c, s=None, e=None):
    st.markdown('<div class="sec">Estadísticos · operación, economía y precios</div>',
                unsafe_allow_html=True)

    if df_r.empty:
        st.info("Sin datos de generación para el período seleccionado.")
        return

    # ── Cruce gen × CMG (base económica) ─────────────────────────────────────
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

    _kpis(df_r, df_c, energia_unit, ingreso_unit, tiene_cmg)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Fila 1 · Precios: patrón intradiario + curva de duración ─────────────
    if tiene_cmg:
        c1, c2 = st.columns(2)
        with c1:
            _heatmap_cmg(df_c)
        with c2:
            _curva_duracion(df_c)

    # ── Fila 2 · Economía: ingreso acumulado + perfil horario de generación ──
    c3, c4 = st.columns(2)
    with c3:
        if tiene_cmg and ingreso_unit.sum() > 0:
            _ingreso_acumulado(df_merge)
        else:
            _grafico_participacion(ingreso_unit) if ingreso_unit.sum() > 0 else \
                st.caption("Ingreso acumulado: requiere datos de CMG en el período.")
    with c4:
        _perfil_horario_gen(df_r)

    # ── Fila 3 · Operación por unidad: aporte energético + factor de planta ──
    c5, c6 = st.columns(2)
    with c5:
        _grafico_aporte_energia(energia_unit)
    with c6:
        _grafico_factor_planta(df_r)

    # ── Fila 4 · Mérito y precisión ──────────────────────────────────────────
    c7, c8 = st.columns(2)
    with c7:
        if tiene_cmg:
            _grafico_correlacion(df_merge)
        else:
            st.caption("Respuesta de mérito (gen vs CMG): requiere datos de CMG.")
    with c8:
        _grafico_precision(df_r, df_p)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de layout
# ─────────────────────────────────────────────────────────────────────────────
def _layout(fig, titulo, y_title=None, height=320, **kw):
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=13, color=INK), x=0),
        height=height, margin=dict(l=10, r=14, t=50, b=10),
        plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
        font=dict(family="Inter, sans-serif"),
        xaxis=dict(showgrid=False, tickfont=dict(color="#475569", size=11)),
        yaxis=dict(gridcolor=C_GRID, tickfont=dict(color=INK_AXIS, size=10),
                   title=y_title, title_font=dict(color=INK_AXIS, size=10)),
        **kw)
    return fig


def _show(fig):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────────────────────
def _kpis(df_r, df_c, energia_unit, ingreso_unit, tiene_cmg):
    energia_total = energia_unit.sum()
    horas = df_r["fecha_hora"].dt.floor("h").nunique() or 1
    fp_global = (df_r["gen_real_mw"].sum() / horas) / sum(PMAX.values()) * 100
    # Factor de utilización: fracción de horas-unidad con la máquina generando.
    horas_unidad = len(df_r)
    horas_op = int((df_r["gen_real_mw"] > 1).sum())
    util = horas_op / horas_unidad * 100 if horas_unidad else 0

    kpis = [
        ("Energía total", f"{energia_total:,.0f}", "MWh en el período"),
        ("Factor de planta", f"{fp_global:.1f}%", "promedio 4 unidades"),
        ("Disponibilidad", f"{util:.0f}%", "horas-unidad en operación"),
    ]
    if tiene_cmg:
        ing = ingreso_unit.sum()
        # Ingreso medio realizado = USD/MWh que efectivamente capturó el complejo
        # (ponderado por generación), distinto del CMG simple (media aritmética).
        realizado = ing / energia_total if energia_total else 0
        kpis += [
            ("Ingreso estimado", f"${ing:,.0f}", "USD (gen × CMG)"),
            ("Ingreso realizado", f"{realizado:.1f}", "USD/MWh capturado"),
            ("CMG promedio", f"{df_c['cmg_usd_mwh'].mean():.1f}", "USD/MWh simple"),
        ]
    cols = st.columns(len(kpis))
    for col, (lbl, val, sub) in zip(cols, kpis):
        col.metric(lbl, val, sub)


# ─────────────────────────────────────────────────────────────────────────────
# Fila 1 — precios
# ─────────────────────────────────────────────────────────────────────────────
def _heatmap_cmg(df_c):
    """Mapa de calor CMG por hora del día (0-23) × fecha. Revela el patrón
    intradiario del precio (horas caras/baratas) a lo largo del período."""
    d = df_c.copy()
    d["hora"] = d["fecha_hora"].dt.hour
    d["dia"] = d["fecha_hora"].dt.strftime("%d/%m")
    piv = d.pivot_table(index="hora", columns="dia", values="cmg_usd_mwh", aggfunc="mean")
    piv = piv.reindex(range(24))          # todas las horas, huecos = NaN
    # Ordenar columnas cronológicamente (por primera aparición en el período).
    orden = d.drop_duplicates("dia")["dia"].tolist()
    piv = piv.reindex(columns=[c for c in orden if c in piv.columns])
    fig = go.Figure(go.Heatmap(
        z=piv.values, x=piv.columns, y=piv.index, colorscale=CMG_SCALE,
        colorbar=dict(title=dict(text="USD/MWh", font=dict(size=9, color=INK_AXIS)),
                      thickness=10, tickfont=dict(size=9, color=INK_AXIS), len=0.85),
        hovertemplate="Día %{x} · %{y}:00 h<br><b>%{z:.1f} USD/MWh</b><extra></extra>",
        hoverongaps=False))
    _layout(fig, "Precio CMG por hora del día y fecha (USD/MWh)", "Hora del día")
    fig.update_yaxes(dtick=3, autorange="reversed", gridcolor=BG_TRANSP)
    fig.update_xaxes(tickfont=dict(color=INK_AXIS, size=9))
    _show(fig)
    st.caption("Cada celda es el CMG medio de esa hora. Bandas oscuras = horas de "
               "precio alto; ayuda a ubicar las ventanas caras del día.")


def _curva_duracion(df_c):
    """Curva de duración de precios: CMG ordenado de mayor a menor contra el % del
    tiempo. Clásico de sistemas de potencia — responde '¿cuántas horas el precio
    superó X?'. El área bajo la curva ≈ nivel general de precios del período."""
    v = df_c["cmg_usd_mwh"].dropna().sort_values(ascending=False).to_numpy()
    if v.size == 0:
        st.caption("Curva de duración: sin datos de CMG.")
        return
    pct = np.linspace(0, 100, v.size)
    med = float(np.median(v))
    prom = float(np.mean(v))
    fig = go.Figure(go.Scatter(
        x=pct, y=v, mode="lines", line=dict(color=AES_VIOLETA, width=2.4),
        fill="tozeroy", fillcolor="rgba(124,77,224,0.12)",
        hovertemplate="Superado el %{x:.0f}% del tiempo<br><b>%{y:.1f} USD/MWh</b><extra></extra>"))
    fig.add_hline(y=med, line_color=INK_AXIS, line_dash="dot",
                  annotation_text=f"Mediana {med:.0f}", annotation_position="top right",
                  annotation_font=dict(color=INK_MUTED, size=10))
    _layout(fig, "Curva de duración de precios CMG (USD/MWh)", "USD/MWh")
    fig.update_xaxes(title="% del tiempo con CMG ≥ valor", ticksuffix="%",
                     title_font=dict(color=INK_AXIS, size=10), range=[0, 100])
    _show(fig)
    st.caption(f"El precio fue ≥ mediana ({med:.0f}) la mitad del tiempo; promedio "
               f"{prom:.0f} USD/MWh. Cuanto más plana y alta, más sostenidos los precios.")


# ─────────────────────────────────────────────────────────────────────────────
# Fila 2 — economía y forma del despacho
# ─────────────────────────────────────────────────────────────────────────────
def _ingreso_acumulado(df_merge):
    """Ingreso estimado ACUMULADO por unidad a lo largo del período (área apilada).
    Muestra el ritmo de acumulación de ingresos y la participación relativa."""
    piv = (df_merge.dropna(subset=["ingreso_usd"])
           .pivot_table(index="fecha_hora", columns="unidad",
                        values="ingreso_usd", aggfunc="sum")
           .sort_index().fillna(0).cumsum())
    fig = go.Figure()
    for u in UNIDADES:
        if u not in piv.columns:
            continue
        fig.add_trace(go.Scatter(
            x=piv.index, y=piv[u], name=LABELS[u], mode="lines",
            line=dict(color=COLORES[u]["line"], width=1.5), stackgroup="ing",
            hovertemplate=f"<b>{LABELS[u]}</b><br>%{{x|%d/%m %H:%M}}<br>"
                          "Acumulado $%{y:,.0f}<extra></extra>"))
    _layout(fig, "Ingreso estimado acumulado por unidad (USD)", "USD",
            height=320, legend=dict(orientation="h", y=-0.16, font=dict(size=10)))
    _show(fig)
    st.caption("Área apilada del ingreso (gen × CMG) acumulado. La pendiente indica "
               "cuándo el complejo capturó más valor.")


def _perfil_horario_gen(df_r):
    """Perfil horario medio de generación por unidad (barra apilada, 0-23 h).
    Revela la forma del despacho intradiario y el mix de unidades por hora."""
    d = df_r.copy()
    d["hora"] = d["fecha_hora"].dt.hour
    piv = d.pivot_table(index="hora", columns="unidad", values="gen_real_mw",
                        aggfunc="mean").reindex(range(24)).fillna(0)
    fig = go.Figure()
    for u in UNIDADES:
        if u not in piv.columns:
            continue
        fig.add_trace(go.Bar(
            x=piv.index, y=piv[u], name=LABELS[u],
            marker=dict(color=COLORES[u]["line"], line=dict(color="#FFFFFF", width=0.4)),
            hovertemplate=f"<b>{LABELS[u]}</b><br>%{{x}}:00 h<br>"
                          "%{y:.0f} MW medios<extra></extra>"))
    _layout(fig, "Perfil horario medio de generación (MW)", "MW",
            barmode="stack", bargap=0.12,
            legend=dict(orientation="h", y=-0.16, font=dict(size=10)))
    fig.update_xaxes(dtick=3, title="Hora del día", title_font=dict(color=INK_AXIS, size=10))
    _show(fig)
    st.caption("Generación media de cada hora del día, apilada por unidad. Muestra "
               "el patrón de carga y qué unidades hacen el seguimiento.")


# ─────────────────────────────────────────────────────────────────────────────
# Fila 3 — operación por unidad
# ─────────────────────────────────────────────────────────────────────────────
def _grafico_aporte_energia(energia_unit):
    us = [u for u in UNIDADES if energia_unit.get(u, 0) > 0]
    vals = [energia_unit.get(u, 0) for u in us]
    fig = go.Figure(go.Bar(
        x=[LABELS[u] for u in us], y=vals,
        marker=dict(color=[COLORES[u]["line"] for u in us],
                    line=dict(color="rgba(255,255,255,0.6)", width=1)),
        text=[f"{v:,.0f}" for v in vals], textposition="outside",
        textfont=dict(size=11, color="#475569"),
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} MWh<extra></extra>"))
    _layout(fig, "Aporte energético por unidad (MWh)", "MWh")
    fig.update_yaxes(range=[0, max(vals) * 1.18 if vals else 1])
    _show(fig)


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
    _show(fig)


def _grafico_participacion(ingreso_unit):
    us = [u for u in UNIDADES if ingreso_unit.get(u, 0) > 0]
    fig = go.Figure(go.Pie(
        labels=[LABELS[u] for u in us], values=[ingreso_unit.get(u, 0) for u in us],
        hole=0.55, marker=dict(colors=[COLORES[u]["line"] for u in us],
                               line=dict(color="#FFFFFF", width=2)),
        textfont=dict(size=11),
        hovertemplate="%{label}<br><b>$%{value:,.0f} USD</b><br>%{percent}<extra></extra>"))
    total = ingreso_unit.sum()
    fig.update_layout(
        title=dict(text="Participación en ingresos estimados", font=dict(size=13, color=INK), x=0),
        height=320, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor=BG_TRANSP,
        legend=dict(orientation="h", y=-0.1, font=dict(size=10)),
        annotations=[dict(text=f"${total:,.0f}<br><span style='font-size:10px'>USD total</span>",
                          x=0.5, y=0.5, font_size=13, showarrow=False)])
    _show(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Fila 4 — mérito y precisión
# ─────────────────────────────────────────────────────────────────────────────
def _grafico_correlacion(df_merge):
    df_corr = (df_merge.dropna().groupby("fecha_hora")
               .agg(gen_total=("gen_real_mw", "sum"), cmg=("cmg_usd_mwh", "mean")).reset_index())
    fig = go.Figure(go.Scatter(x=df_corr["gen_total"], y=df_corr["cmg"], mode="markers",
        marker=dict(color=AES_VIOLETA, size=6, opacity=0.55,
                    line=dict(color="#FFFFFF", width=0.4)),
        hovertemplate="Gen: %{x:.0f} MW<br>CMG: %{y:.1f} USD/MWh<extra></extra>"))
    if len(df_corr) > 2:
        coef = np.polyfit(df_corr["gen_total"], df_corr["cmg"], 1)
        xl = [df_corr["gen_total"].min(), df_corr["gen_total"].max()]
        fig.add_trace(go.Scatter(x=xl, y=[coef[0]*x + coef[1] for x in xl], mode="lines",
            line=dict(color=INK_AXIS, dash="dot", width=1.5), showlegend=False))
        r = df_corr["gen_total"].corr(df_corr["cmg"])
        fig.add_annotation(xref="paper", yref="paper", x=0.98, y=0.96, showarrow=False,
            text=f"r = {r:.2f}", font=dict(size=11, color=INK_MUTED), align="right")
    _layout(fig, "Respuesta de mérito · generación total vs CMG", "CMG USD/MWh")
    fig.update_xaxes(title="MW generados (total)", tickfont=dict(color=INK_AXIS, size=10),
                     title_font=dict(color=INK_AXIS, size=10))
    _show(fig)
    st.caption("Cada punto es una hora. Correlación positiva = las unidades generan "
               "más cuando el precio sube (respuesta esperada del despacho térmico).")


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
    _show(fig)
    sesgos = " · ".join(f"{LABELS[u]}: {b:+.1f}" for u, _, _, b in filas)
    st.caption(f"Sesgo medio (real − programada): {sesgos} · MAE = error absoluto medio, "
               "RMSE penaliza desvíos grandes.")
