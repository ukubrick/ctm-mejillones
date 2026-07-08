"""components/costo.py — Análisis económico del complejo (rediseño 2026-07).

Deep-dive económico y de precios, complementario a la vista «Estadísticas»
(que cubre operación y patrones). Aquí el foco es el DINERO y el PRECIO:

  · KPIs económicos: ingreso estimado y realizado (USD/MWh capturado),
    CMG promedio, volatilidad, rango, y desvíos de pronóstico/liquidación.
  · CMG en el tiempo: online vs programado (PID) vs real oficial liquidado
    — benchmarking de precio en un solo eje (USD/MWh).
  · Elasticidad precio-demanda: CMG vs demanda pronosticada (dispersión + ajuste).
  · Ingreso diario por unidad (barra apilada) — estacionalidad del valor.
  · Mapa de valor: energía vs precio capturado por unidad (burbuja = ingreso).
  · Cascada de ingreso por unidad → total del complejo.
  · Calidad del pronóstico CMG: distribución del error online − programado.

Sin ejes duales (cada gráfico, un solo eje de magnitud). Paleta corporativa AES:
unidades = tema categórico de orden fijo; CMG = violeta AES; programado = ámbar-oro;
real oficial = teal. Grillas y ejes recesivos.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (COLORES, LABELS, UNIDADES, BG_TRANSP, C_GRID, SERIE,
                    AES_VIOLETA, AES_AZUL, AES_VERDE, AES_ROJO, CMG_A_DEMANDA,
                    NOMBRES_BARRA_CMG)
from utils.data import (load_cmg_prog, load_cmg_real, load_pronostico_demanda,
                        load_mix_diario)

INK       = "#0F172A"
INK_MUTED = "#64748B"
INK_AXIS  = "#94A3B8"
C_REAL_OF = "#0F766E"   # teal — CMG real oficial liquidado


def render_costo(df_r, df_c, s=None, e=None, nodo_cmg="CRUCERO_______220", df_p=None):
    st.markdown('<div class="sec">Análisis económico · precio, ingreso y pronóstico</div>',
                unsafe_allow_html=True)

    if df_c.empty:
        st.info("Sin datos de CMG para calcular estadísticos de costo.")
        return

    df_cp  = load_cmg_prog(s, e, nodo_cmg) if s and e else None
    df_cr  = load_cmg_real(s, e, nodo_cmg) if s and e else None
    barra_dem = CMG_A_DEMANDA.get(nodo_cmg, "Crucero220")
    df_dem = load_pronostico_demanda(s, e, barra_dem) if s and e else None

    # ── Base económica: ingreso = generación × CMG (merge_asof ±1h) ──────────
    df_merge = pd.merge_asof(
        df_r[["unidad", "fecha_hora", "gen_real_mw"]].sort_values("fecha_hora"),
        df_c[["fecha_hora", "cmg_usd_mwh"]].sort_values("fecha_hora"),
        on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
    )
    df_merge["ingreso_usd"] = df_merge["gen_real_mw"] * df_merge["cmg_usd_mwh"]
    ingreso_unit  = df_merge.groupby("unidad")["ingreso_usd"].sum()
    energia_unit  = df_r.groupby("unidad")["gen_real_mw"].sum()

    _kpis(df_c, df_cp, df_cr, ingreso_unit, energia_unit)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Fila 1 · Precio: benchmarking temporal + elasticidad demanda ─────────
    c1, c2 = st.columns(2)
    with c1:
        _cmg_tiempo(df_c, df_cp, df_cr)
    with c2:
        _cmg_vs_demanda(df_c, df_dem, barra_dem)

    # ── Fila 2 · Ingreso: estacionalidad diaria + mapa de valor ──────────────
    c3, c4 = st.columns(2)
    with c3:
        _ingreso_diario(df_merge)
    with c4:
        _mapa_valor(ingreso_unit, energia_unit)

    # ── Fila 3 · Contribución + calidad del pronóstico ───────────────────────
    c5, c6 = st.columns(2)
    with c5:
        _cascada_ingreso(ingreso_unit)
    with c6:
        _error_pronostico(df_c, df_cp)

    # ── Fila 4 · Precio en barra de central + contexto térmico del SEN ──────
    c7, c8 = st.columns(2)
    with c7:
        _cmg_barras_central(s, e)
    with c8:
        _mix_termico(s, e)


# ─────────────────────────────────────────────────────────────────────────────
def _layout(fig, titulo, y_title=None, height=330, **kw):
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=13, color=INK), x=0),
        height=height, margin=dict(l=10, r=14, t=52, b=10),
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
def _kpis(df_c, df_cp, df_cr, ingreso_unit, energia_unit):
    cmg = df_c["cmg_usd_mwh"]
    ing = ingreso_unit.sum()
    ene = energia_unit.sum()
    realizado = ing / ene if ene else 0
    kpis = [
        ("Ingreso estimado", f"${ing:,.0f}", "USD (gen × CMG)"),
        ("Ingreso realizado", f"{realizado:.1f}", "USD/MWh capturado"),
        ("CMG promedio", f"{cmg.mean():.1f}", "USD/MWh simple"),
        ("Volatilidad CMG", f"{cmg.std():.1f}", "desv. estándar"),
        ("Rango CMG", f"{cmg.min():.0f}–{cmg.max():.0f}", "mín–máx USD/MWh"),
    ]
    # Sesgo de pronóstico (online − programado): + = precio salió más caro de lo previsto.
    if df_cp is not None and not df_cp.empty:
        m = _cruce(df_c, df_cp)
        if not m.empty:
            kpis.append(("Sesgo pronóstico", f"{(m['a'] - m['b']).mean():+.1f}",
                         "USD/MWh online−prog"))
    # Desvío online vs real oficial liquidado (rezago ~10 días).
    if df_cr is not None and not df_cr.empty:
        m = _cruce(df_c, df_cr)
        if not m.empty:
            kpis.append(("Online vs real oficial", f"{(m['a'] - m['b']).mean():+.1f}",
                         "USD/MWh medio"))
    cols = st.columns(len(kpis))
    for col, (lbl, val, sub) in zip(cols, kpis):
        col.metric(lbl, val, sub)


def _cruce(df_a, df_b):
    """merge_asof ±1h de dos series CMG. Devuelve columnas a (df_a) y b (df_b)."""
    return pd.merge_asof(
        df_a[["fecha_hora", "cmg_usd_mwh"]].rename(columns={"cmg_usd_mwh": "a"}).sort_values("fecha_hora"),
        df_b[["fecha_hora", "cmg_usd_mwh"]].rename(columns={"cmg_usd_mwh": "b"}).sort_values("fecha_hora"),
        on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
    ).dropna(subset=["a", "b"])


# ─────────────────────────────────────────────────────────────────────────────
# Fila 1
# ─────────────────────────────────────────────────────────────────────────────
def _cmg_tiempo(df_c, df_cp, df_cr):
    """CMG online vs programado (PID) vs real oficial. Un solo eje (USD/MWh).
    Marca máximo/mínimo y la media del período."""
    prom = df_c["cmg_usd_mwh"].mean()
    idx_max = df_c["cmg_usd_mwh"].idxmax()
    idx_min = df_c["cmg_usd_mwh"].idxmin()
    cmg_max = df_c.loc[idx_max, "cmg_usd_mwh"]
    cmg_min = df_c.loc[idx_min, "cmg_usd_mwh"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"], mode="none",
        fill="tozeroy", fillcolor="rgba(124,77,224,0.08)", showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"], mode="lines",
        name="Online", line=dict(color=SERIE["cmg"], width=2, shape="spline", smoothing=0.5),
        hovertemplate="<b>Online</b> %{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>"))
    if df_cp is not None and not df_cp.empty:
        fig.add_trace(go.Scatter(x=df_cp["fecha_hora"], y=df_cp["cmg_usd_mwh"], mode="lines",
            name="Programado", line=dict(color=SERIE["cmg_prog"], width=1.4, dash="dash"),
            hovertemplate="<b>Programado</b> %{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>"))
    if df_cr is not None and not df_cr.empty:
        fig.add_trace(go.Scatter(x=df_cr["fecha_hora"], y=df_cr["cmg_usd_mwh"], mode="lines",
            name="Real oficial", line=dict(color=C_REAL_OF, width=1.6),
            hovertemplate="<b>Real oficial</b> %{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>"))
    fig.add_hline(y=prom, line_color="#CBD5E1", line_width=1.2, line_dash="dot",
        annotation_text=f"Prom {prom:.0f}", annotation_position="right",
        annotation_font=dict(color=INK_MUTED, size=10))
    fig.add_trace(go.Scatter(x=[df_c.loc[idx_max, "fecha_hora"]], y=[cmg_max], mode="markers+text",
        marker=dict(size=9, color=AES_ROJO, symbol="triangle-up", line=dict(color="#fff", width=1.2)),
        text=[f" máx {cmg_max:.0f}"], textposition="top center",
        textfont=dict(size=9, color=AES_ROJO), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[df_c.loc[idx_min, "fecha_hora"]], y=[cmg_min], mode="markers+text",
        marker=dict(size=9, color=AES_VERDE, symbol="triangle-down", line=dict(color="#fff", width=1.2)),
        text=[f" mín {cmg_min:.0f}"], textposition="bottom center",
        textfont=dict(size=9, color=AES_VERDE), showlegend=False, hoverinfo="skip"))
    _layout(fig, "CMG en el tiempo · online vs programado vs real (USD/MWh)", "USD/MWh",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)),
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#1E293B", font_color="#F8FAFC", bordercolor="#334155"))
    fig.update_xaxes(tickformat="%d/%m\n%H:%M", tickfont=dict(color=INK_AXIS, size=10))
    _show(fig)
    st.caption("Benchmarking del precio: la separación online↔programado mide el error "
               "del pronóstico; online↔real oficial, el sesgo del dato preliminar.")


def _cmg_vs_demanda(df_c, df_dem, barra_dem):
    """Elasticidad precio-demanda: CMG online vs demanda pronosticada (una hora =
    un punto). Un eje por variable (dispersión, no eje dual)."""
    if df_dem is None or df_dem.empty:
        st.caption(f"Elasticidad precio-demanda: sin pronóstico de demanda para {barra_dem}.")
        return
    m = pd.merge_asof(
        df_c[["fecha_hora", "cmg_usd_mwh"]].sort_values("fecha_hora"),
        df_dem[["fecha_hora", "energia_mwh"]].sort_values("fecha_hora"),
        on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
    ).dropna()
    if len(m) < 3:
        st.caption("Elasticidad precio-demanda: cruce insuficiente en el período.")
        return
    fig = go.Figure(go.Scatter(
        x=m["energia_mwh"], y=m["cmg_usd_mwh"], mode="markers",
        marker=dict(color=AES_AZUL, size=6, opacity=0.5, line=dict(color="#fff", width=0.4)),
        hovertemplate="Demanda %{x:,.0f} MWh<br>CMG %{y:.1f} USD/MWh<extra></extra>"))
    coef = np.polyfit(m["energia_mwh"], m["cmg_usd_mwh"], 1)
    xl = [m["energia_mwh"].min(), m["energia_mwh"].max()]
    fig.add_trace(go.Scatter(x=xl, y=[coef[0]*x + coef[1] for x in xl], mode="lines",
        line=dict(color=INK_AXIS, dash="dot", width=1.5), showlegend=False, hoverinfo="skip"))
    r = m["energia_mwh"].corr(m["cmg_usd_mwh"])
    fig.add_annotation(xref="paper", yref="paper", x=0.98, y=0.05, showarrow=False,
        text=f"r = {r:.2f}", font=dict(size=11, color=INK_MUTED), align="right")
    _layout(fig, "Elasticidad precio-demanda · CMG vs demanda", "CMG USD/MWh")
    fig.update_xaxes(title=f"Demanda pronosticada {barra_dem} (MWh)",
                     title_font=dict(color=INK_AXIS, size=10), tickfont=dict(color=INK_AXIS, size=10))
    _show(fig)
    st.caption("Cada punto es una hora. Pendiente positiva = a más demanda, mayor precio "
               "(señal de escasez); r cercano a 0 indica que el precio lo fija otro factor.")


# ─────────────────────────────────────────────────────────────────────────────
# Fila 2
# ─────────────────────────────────────────────────────────────────────────────
def _ingreso_diario(df_merge):
    """Ingreso estimado diario por unidad (barra apilada). Estacionalidad del valor."""
    d = df_merge.dropna(subset=["ingreso_usd"]).copy()
    d["dia"] = d["fecha_hora"].dt.strftime("%d/%m")
    orden = d.drop_duplicates("dia")["dia"].tolist()
    piv = (d.pivot_table(index="dia", columns="unidad", values="ingreso_usd", aggfunc="sum")
           .reindex(orden).fillna(0))
    fig = go.Figure()
    for u in UNIDADES:
        if u not in piv.columns:
            continue
        fig.add_trace(go.Bar(x=piv.index, y=piv[u], name=LABELS[u],
            marker=dict(color=COLORES[u]["line"], line=dict(color="#FFFFFF", width=0.4)),
            hovertemplate=f"<b>{LABELS[u]}</b><br>%{{x}}<br>$%{{y:,.0f}}<extra></extra>"))
    _layout(fig, "Ingreso estimado diario por unidad (USD)", "USD",
            barmode="stack", bargap=0.25,
            legend=dict(orientation="h", y=-0.18, font=dict(size=10)))
    _show(fig)
    st.caption("Ingreso (gen × CMG) agregado por día y apilado por unidad. Revela los "
               "días de mayor captura de valor del complejo.")


def _mapa_valor(ingreso_unit, energia_unit):
    """Mapa de valor: energía (x) vs precio capturado (y), burbuja = ingreso.
    Ubica cada unidad en el plano volumen-precio."""
    us = [u for u in UNIDADES if energia_unit.get(u, 0) > 0]
    if not us:
        st.caption("Mapa de valor: sin generación en el período.")
        return
    xs = [energia_unit.get(u, 0) for u in us]
    ings = [ingreso_unit.get(u, 0) for u in us]
    ys = [ings[i] / xs[i] if xs[i] else 0 for i in range(len(us))]
    ref = max(ings) or 1
    fig = go.Figure()
    for i, u in enumerate(us):
        fig.add_trace(go.Scatter(
            x=[xs[i]], y=[ys[i]], mode="markers+text", name=LABELS[u],
            marker=dict(size=28 + 46 * (ings[i] / ref), color=COLORES[u]["line"],
                        opacity=0.82, line=dict(color="#fff", width=1.5)),
            text=[LABELS[u].replace("Angamos", "ANG").replace("Cochrane", "CCR")],
            textposition="middle center", textfont=dict(size=9, color="#fff"),
            hovertemplate=(f"<b>{LABELS[u]}</b><br>Energía %{{x:,.0f}} MWh<br>"
                           f"Precio capturado %{{y:.1f}} USD/MWh<br>"
                           f"Ingreso ${ings[i]:,.0f}<extra></extra>"),
            showlegend=False))
    _layout(fig, "Mapa de valor · volumen vs precio capturado", "USD/MWh capturado")
    fig.update_xaxes(title="Energía generada (MWh)", title_font=dict(color=INK_AXIS, size=10),
                     tickfont=dict(color=INK_AXIS, size=10))
    _show(fig)
    st.caption("Cada burbuja es una unidad; su tamaño = ingreso estimado. Arriba-derecha "
               "= mucho volumen a buen precio (posición más rentable).")


# ─────────────────────────────────────────────────────────────────────────────
# Fila 3
# ─────────────────────────────────────────────────────────────────────────────
def _cascada_ingreso(ingreso_unit):
    """Cascada: contribución de cada unidad al ingreso total del complejo."""
    us = [u for u in UNIDADES if ingreso_unit.get(u, 0) > 0]
    if not us:
        st.caption("Cascada de ingreso: sin datos económicos.")
        return
    vals = [ingreso_unit.get(u, 0) for u in us]
    total = sum(vals)
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=["relative"] * len(us) + ["total"],
        x=[LABELS[u] for u in us] + ["Total complejo"],
        y=vals + [total],
        text=[f"${v:,.0f}" for v in vals] + [f"${total:,.0f}"],
        textposition="outside", textfont=dict(size=10, color="#475569"),
        connector=dict(line=dict(color="#CBD5E1", width=1)),
        increasing=dict(marker=dict(color=AES_VIOLETA)),
        totals=dict(marker=dict(color=INK)),
        hovertemplate="<b>%{x}</b><br>$%{y:,.0f}<extra></extra>"))
    _layout(fig, "Cascada de ingreso · aporte de cada unidad al total (USD)", "USD")
    fig.update_yaxes(range=[0, total * 1.15])
    _show(fig)
    st.caption("Cómo se construye el ingreso total del complejo sumando la contribución "
               "de cada unidad.")


# ─────────────────────────────────────────────────────────────────────────────
# Fila 4 — barras de central + contexto térmico (integrado 2026-07-08)
# ─────────────────────────────────────────────────────────────────────────────
# Barras del CMG programado a comparar: las de las propias centrales vs el nodo
# regional Crucero. Colores: entidades distintas → categórico fijo (no rampa).
_BARRAS_CENTRAL = {
    "ANGAMOS_______220": AES_AZUL,
    "COCHRANE______220": "#1FB6E5",
    "CRUCERO_______220": AES_VIOLETA,
}


def _cmg_barras_central(s, e):
    """CMG programado (PID) en la barra de cada central vs el nodo regional
    Crucero. La diferencia es el spread de localización: cuánto más (o menos)
    vale la energía en el punto de conexión de Angamos/Cochrane."""
    if not (s and e):
        return
    series = {b: load_cmg_prog(s, e, b) for b in _BARRAS_CENTRAL}
    con_datos = {b: d for b, d in series.items() if d is not None and not d.empty}
    if "ANGAMOS_______220" not in con_datos and "COCHRANE______220" not in con_datos:
        st.caption("CMG en barra de central: aún sin datos de Angamos/Cochrane "
                   "(la adquisición los incorpora automáticamente).")
        return
    fig = go.Figure()
    for barra, color in _BARRAS_CENTRAL.items():
        d = con_datos.get(barra)
        if d is None:
            continue
        nombre = NOMBRES_BARRA_CMG.get(barra, barra)
        fig.add_trace(go.Scatter(
            x=d["fecha_hora"], y=d["cmg_usd_mwh"], mode="lines", name=nombre,
            line=dict(color=color, width=2 if barra != "CRUCERO_______220" else 1.4,
                      dash="solid" if barra != "CRUCERO_______220" else "dot"),
            hovertemplate=f"<b>{nombre}</b> %{{x|%d/%m %H:%M}}<br>"
                          "%{y:.1f} USD/MWh<extra></extra>"))
    _layout(fig, "CMG programado en barra de central vs nodo Crucero (USD/MWh)",
            "USD/MWh",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)),
            hovermode="x unified")
    fig.update_xaxes(tickformat="%d/%m\n%H:%M", tickfont=dict(color=INK_AXIS, size=10))
    _show(fig)
    # Spread medio de localización respecto de Crucero.
    spreads = []
    cru = con_datos.get("CRUCERO_______220")
    if cru is not None:
        for barra in ("ANGAMOS_______220", "COCHRANE______220"):
            d = con_datos.get(barra)
            if d is None:
                continue
            m = _cruce(d, cru)
            if not m.empty:
                spreads.append(f"{NOMBRES_BARRA_CMG[barra]} {(m['a'] - m['b']).mean():+.1f}")
    extra = f" Spread medio vs Crucero: {' · '.join(spreads)} USD/MWh." if spreads else ""
    st.caption("El precio en el punto de conexión de cada central es el que valoriza "
               f"su energía; Crucero es la referencia regional del CMG online.{extra}")


def _mix_termico(s, e):
    """Participación térmica del SEN por día (mix de generación). Contexto del
    precio: cuando el sistema depende más de las térmicas, el CMG sube."""
    if not (s and e):
        return
    df = load_mix_diario(s, e)
    if df is None or df.empty:
        st.caption("Peso térmico del SEN: aún sin datos de mix diario "
                   "(la adquisición los incorpora automáticamente).")
        return
    piv = df.pivot_table(index="fecha", columns="tecnologia", values="energia_mwh",
                         aggfunc="sum")
    col_ter = next((c for c in piv.columns if "TÉRMICA" in str(c).upper()
                    or "TERMICA" in str(c).upper()), None)
    col_tot = next((c for c in piv.columns if "TOTAL GENERACI" in str(c).upper()), None)
    if col_ter is None or col_tot is None:
        st.caption("Peso térmico del SEN: mix diario sin columnas esperadas.")
        return
    share = (piv[col_ter] / piv[col_tot].replace(0, np.nan) * 100).dropna()
    if share.empty:
        st.caption("Peso térmico del SEN: sin días con mix completo en el período.")
        return
    etiquetas = [pd.to_datetime(f).strftime("%d/%m") for f in share.index]
    fig = go.Figure(go.Bar(
        x=etiquetas, y=share.values, marker_color=AES_VIOLETA, opacity=0.85,
        text=[f"{v:.0f}%" for v in share.values], textposition="outside",
        textfont=dict(size=9, color=INK_MUTED),
        hovertemplate="%{x}<br>Térmicas: %{y:.1f}% del SEN<extra></extra>"))
    fig.add_hline(y=float(share.mean()), line_color="#CBD5E1", line_width=1.2,
                  line_dash="dot", annotation_text=f"Prom {share.mean():.0f}%",
                  annotation_position="right",
                  annotation_font=dict(color=INK_MUTED, size=10))
    _layout(fig, "Peso térmico del SEN por día (% de la generación total)", "%",
            bargap=0.3, showlegend=False)
    fig.update_yaxes(range=[0, min(100, share.max() * 1.25)])
    _show(fig)
    st.caption("A mayor participación térmica (menos sol/viento/agua), unidades más "
               "caras fijan el precio → CMG alto. Es el telón de fondo del precio "
               "que capturan Angamos y Cochrane.")


def _error_pronostico(df_c, df_cp):
    """Calidad del pronóstico CMG: distribución del error (online − programado).
    Centrado en 0 = pronóstico insesgado; cola ancha = baja precisión."""
    if df_cp is None or df_cp.empty:
        st.caption("Calidad del pronóstico CMG: sin CMG programado en el período.")
        return
    m = _cruce(df_c, df_cp)
    if m.empty:
        st.caption("Calidad del pronóstico CMG: sin cruce disponible.")
        return
    err = (m["a"] - m["b"])
    mae = err.abs().mean()
    sesgo = err.mean()
    fig = go.Figure(go.Histogram(x=err, nbinsx=25, marker_color=AES_VIOLETA, opacity=0.78,
        hovertemplate="Error %{x:.0f} USD/MWh<br>Horas: %{y}<extra></extra>"))
    fig.add_vline(x=0, line_color="#94A3B8", line_width=1.2)
    fig.add_vline(x=sesgo, line_color=AES_ROJO, line_dash="dot",
        annotation_text=f"Sesgo {sesgo:+.0f}", annotation_position="top right",
        annotation_font=dict(color=AES_ROJO, size=10))
    _layout(fig, "Calidad del pronóstico CMG · error online − programado", "Horas", bargap=0.05)
    fig.update_xaxes(title="Error (USD/MWh)", title_font=dict(color=INK_AXIS, size=10),
                     tickfont=dict(color=INK_AXIS, size=10))
    _show(fig)
    st.caption(f"MAE {mae:.1f} · sesgo {sesgo:+.1f} USD/MWh. Barras a la derecha del 0 = el "
               "precio real superó al programado (subestimación del pronóstico).")
