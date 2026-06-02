"""
app.py — Dashboard CTM Mejillones v3
Fixes: expanders, tooltip keyboard, serie de tiempo limpia, costo como gráficos
"""

import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, datetime, timedelta

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="CTM Mejillones",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded",
)

COLORES = {
    "ANG1": {"line": "#0284C7", "badge": "#E0F2FE", "text": "#0284C7"},
    "ANG2": {"line": "#059669", "badge": "#D1FAE5", "text": "#059669"},
    "CCR1": {"line": "#D97706", "badge": "#FEF3C7", "text": "#D97706"},
    "CCR2": {"line": "#DC2626", "badge": "#FEE2E2", "text": "#DC2626"},
    "CMG":  {"line": "#7C3AED", "badge": "#EDE9FE", "text": "#7C3AED"},
}
LABELS = {
    "ANG1": "Angamos U1", "ANG2": "Angamos U2",
    "CCR1": "Cochrane U1", "CCR2": "Cochrane U2",
}

# ══════════════════════════════════════════════════════════════
# ESTILOS
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --bg:     #F1F5F9;
    --surf:   #FFFFFF;
    --surf2:  #F8FAFC;
    --bord:   #E2E8F0;
    --txt:    #0F172A;
    --muted:  #64748B;
    --accent: #0284C7;
}
.stApp { background: var(--bg) !important; }
.block-container { padding: 1.5rem 2rem 3rem; max-width: 1400px; }

/* Sidebar */
[data-testid="stSidebar"] { background: var(--surf) !important; border-right:1px solid var(--bord) !important; }
[data-testid="stSidebar"] * { color: var(--txt) !important; }

/* Tipografía */
h1,h2,h3 { font-family:'Inter',sans-serif !important; color:var(--txt) !important; }
p,span,div,label { font-family:'Inter',sans-serif !important; }

/* Ocultar elementos innecesarios */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* Ocultar tooltip keyboard_double del toggle */
[data-testid="InputInstructions"] { display: none !important; }
div[class*="instruction"] { display: none !important; }

/* KPI cards */
.kpi {
    background: var(--surf); border: 1px solid var(--bord);
    border-radius: 12px; padding: 1.2rem 1.4rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.kpi-badge {
    display: inline-block; font-size: 0.65rem; font-weight: 700;
    letter-spacing: 0.08em; text-transform: uppercase;
    padding: 3px 10px; border-radius: 20px; margin-bottom: 0.7rem;
}
.kpi-val {
    font-family: 'IBM Plex Mono', monospace; font-size: 2rem;
    font-weight: 600; color: var(--txt); line-height: 1;
}
.kpi-mw { font-size: 1rem; font-weight: 400; color: var(--muted); }
.kpi-sub { font-size: 0.75rem; color: var(--muted); margin-top: 0.4rem; }
.kpi-delta { font-size: 0.78rem; margin-top: 0.5rem; font-weight: 500; }

/* Sección headers */
.sec {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.15em;
    text-transform: uppercase; color: var(--muted);
    border-bottom: 1px solid var(--bord);
    padding-bottom: 0.4rem; margin: 1.8rem 0 1rem;
}

/* Status */
.dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; }
.dot-g { background:#10B981; box-shadow:0 0 6px rgba(16,185,129,0.5); animation:blink 2s infinite; }
.dot-y { background:#F59E0B; animation:blink 2s infinite; }
@keyframes blink { 0%,100%{opacity:1}50%{opacity:.3} }

/* Expanders limpios */
[data-testid="stExpander"] {
    background: var(--surf) !important; border: 1px solid var(--bord) !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary { font-weight: 600 !important; color: var(--txt) !important; }

/* Inputs */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea,
.stNumberInput>div>div>input {
    background: var(--surf2) !important; border: 1px solid var(--bord) !important;
    border-radius: 8px !important; color: var(--txt) !important;
}

/* Botones */
.stButton>button {
    background: var(--accent) !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important; font-weight: 600 !important;
}
.stButton>button:hover { opacity: .88 !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# DB
# ══════════════════════════════════════════════════════════════
@st.cache_resource
def get_conn():
    url = st.secrets.get("DATABASE_URL", "")
    if not url:
        st.error("DATABASE_URL no configurada."); st.stop()
    return psycopg2.connect(url)

def qry(sql, params=None):
    try:
        conn = get_conn()
        return pd.read_sql(sql, conn, params=params)
    except Exception:
        get_conn.clear()
        try:
            return pd.read_sql(sql, get_conn(), params=params)
        except Exception as e:
            st.error(f"Error DB: {e}"); return pd.DataFrame()

def exe(sql, params=None):
    try:
        conn = get_conn()
        with conn.cursor() as c: c.execute(sql, params)
        conn.commit(); return True
    except Exception as e:
        st.error(f"Error DB: {e}"); return False


# ══════════════════════════════════════════════════════════════
# DATOS
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def load_real(s, e):
    df = qry("SELECT unidad,gen_real_mw,fecha_hora,hora,potencia_maxima FROM generacion_real WHERE fecha_hora::date BETWEEN %s AND %s ORDER BY unidad,fecha_hora", (s,e))
    if not df.empty: df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df

@st.cache_data(ttl=300)
def load_prog(s, e):
    df = qry("SELECT unidad,gen_programada_mw,fecha_hora,hora FROM generacion_programada WHERE fecha_hora::date BETWEEN %s AND %s ORDER BY unidad,fecha_hora", (s,e))
    if not df.empty: df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df

@st.cache_data(ttl=300)
def load_cmg(s, e):
    df = qry("SELECT fecha_hora,hora,cmg_usd_mwh FROM costo_marginal WHERE barra_transf='CRUCERO_______220' AND fecha_hora::date BETWEEN %s AND %s ORDER BY fecha_hora", (s,e))
    if not df.empty: df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df

@st.cache_data(ttl=60)
def load_bit(s, e, u=None):
    if u and u != "Todas":
        return qry("SELECT id,unidad,autor,comentario,fecha,hora FROM bitacora WHERE fecha BETWEEN %s AND %s AND unidad=%s ORDER BY fecha DESC,hora DESC", (s,e,u))
    return qry("SELECT id,unidad,autor,comentario,fecha,hora FROM bitacora WHERE fecha BETWEEN %s AND %s ORDER BY fecha DESC,hora DESC", (s,e))


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚡ CTM Mejillones")
    st.markdown('<p style="font-size:0.72rem;color:#64748B;margin-bottom:1.2rem">Complejo Térmico · Monitoreo Operacional</p>', unsafe_allow_html=True)

    hoy   = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    fi = st.date_input("Desde", value=lunes, max_value=hoy)
    ff = st.date_input("Hasta", value=hoy,   max_value=hoy)
    if fi > ff: st.error("Fecha inicio > fin"); st.stop()

    st.markdown("---")
    usel = st.multiselect("Unidades", ["ANG1","ANG2","CCR1","CCR2"], default=["ANG1","ANG2","CCR1","CCR2"])
    mostrar_prog = st.checkbox("Mostrar programada", value=True)
    mostrar_cmg  = st.checkbox("Mostrar CMG en gráfico", value=True)

    st.markdown("---")
    if st.button("Actualizar datos"):
        st.cache_data.clear(); st.rerun()

    st.markdown(f'<p style="font-size:0.65rem;color:#94A3B8">{datetime.now().strftime("%d/%m/%Y %H:%M")}</p>', unsafe_allow_html=True)

s = fi.strftime("%Y-%m-%d")
e = ff.strftime("%Y-%m-%d")

with st.spinner("Cargando datos..."):
    df_r = load_real(s, e)
    df_p = load_prog(s, e)
    df_c = load_cmg(s, e)

if df_r.empty:
    st.warning("Sin datos para el período seleccionado."); st.stop()

df_r = df_r[df_r["unidad"].isin(usel)] if usel else df_r


# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
ch1, ch2 = st.columns([3, 1])
with ch1:
    st.markdown("# Dashboard Operacional")
    st.markdown(f'<p style="color:#64748B;font-size:0.85rem;margin-top:-0.5rem">Período {s} → {e} · Generación real + CMG Nodo Crucero</p>', unsafe_allow_html=True)
with ch2:
    ult  = df_r["fecha_hora"].max()
    diff = (datetime.now() - ult.to_pydatetime()).seconds
    cls  = "dot-g" if diff < 7200 else "dot-y"
    st.markdown(f'<div style="text-align:right;padding-top:1.5rem"><span class="dot {cls}"></span><span style="font-size:0.75rem;color:#64748B">Último: {ult.strftime("%d/%m %H:%M")}</span></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# KPI — GENERACIÓN REAL
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="sec">GENERACIÓN REAL · PROMEDIO DEL PERÍODO</div>', unsafe_allow_html=True)

cols = st.columns(4)
for i, u in enumerate(["ANG1","ANG2","CCR1","CCR2"]):
    with cols[i]:
        df_u = df_r[df_r["unidad"] == u]
        if df_u.empty:
            st.markdown(f'<div class="kpi"><div class="kpi-badge" style="background:{COLORES[u]["badge"]};color:{COLORES[u]["text"]}">{LABELS[u]}</div><div class="kpi-val">—</div></div>', unsafe_allow_html=True)
            continue
        prom   = df_u["gen_real_mw"].mean()
        pmax   = float(df_u["potencia_maxima"].iloc[0]) if not df_u["potencia_maxima"].isnull().all() else 0
        fp     = prom / pmax * 100 if pmax else 0
        ult_mw = df_u.sort_values("fecha_hora").iloc[-1]["gen_real_mw"]
        delta  = ult_mw - prom
        sym    = "▲" if delta >= 0 else "▼"
        col_d  = "#10B981" if delta >= 0 else "#EF4444"
        st.markdown(f"""
        <div class="kpi">
            <div class="kpi-badge" style="background:{COLORES[u]['badge']};color:{COLORES[u]['text']}">{LABELS[u]}</div>
            <div class="kpi-val">{prom:.1f}<span class="kpi-mw"> MW</span></div>
            <div class="kpi-sub">Factor de planta {fp:.0f}%</div>
            <div class="kpi-delta" style="color:{col_d}">{sym} {abs(delta):.1f} MW vs última hora</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# GRÁFICO SERIES DE TIEMPO — líneas limpias
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="sec">POTENCIA REAL + PROGRAMADA · MW</div>', unsafe_allow_html=True)

n_rows  = 2 if (mostrar_cmg and not df_c.empty) else 1
heights = [0.62, 0.38] if n_rows == 2 else [1.0]
fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True,
                    row_heights=heights, vertical_spacing=0.06,
                    subplot_titles=["Potencia Real + Programada (MW)",
                                    "CMG Nodo Crucero (USD/MWh)"] if n_rows==2 else ["Potencia Real + Programada (MW)"])

for u in usel:
    df_u = df_r[df_r["unidad"] == u].sort_values("fecha_hora")
    if df_u.empty: continue
    c = COLORES[u]

    # Real — línea sólida
    fig.add_trace(go.Scatter(
        x=df_u["fecha_hora"], y=df_u["gen_real_mw"],
        name=f"{LABELS[u]}",
        mode="lines",
        line=dict(color=c["line"], width=2),
        hovertemplate=f"<b>{LABELS[u]}</b><br>%{{x|%d/%m %H:%M}}<br>%{{y:.1f}} MW<extra></extra>",
    ), row=1, col=1)

    # Programada — línea punteada
    if mostrar_prog and not df_p.empty:
        df_up = df_p[df_p["unidad"] == u].sort_values("fecha_hora")
        if not df_up.empty:
            fig.add_trace(go.Scatter(
                x=df_up["fecha_hora"], y=df_up["gen_programada_mw"],
                name=f"{LABELS[u]} Prog.",
                mode="lines",
                line=dict(color=c["line"], width=1.5, dash="dash"),
                opacity=0.55,
                hovertemplate=f"<b>{LABELS[u]} Prog.</b><br>%{{x|%d/%m %H:%M}}<br>%{{y:.1f}} MW<extra></extra>",
            ), row=1, col=1)

# CMG
if mostrar_cmg and not df_c.empty:
    fig.add_trace(go.Scatter(
        x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"],
        name="CMG Crucero",
        mode="lines",
        line=dict(color=COLORES["CMG"]["line"], width=2),
        hovertemplate="<b>CMG Crucero</b><br>%{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>",
    ), row=2, col=1)

    # Banda de referencia (mín-máx CMG)
    fig.add_hrect(
        y0=df_c["cmg_usd_mwh"].quantile(0.25),
        y1=df_c["cmg_usd_mwh"].quantile(0.75),
        fillcolor="rgba(124,58,237,0.06)", line_width=0,
        row=2, col=1
    )

BG = "#FFFFFF"; GR = "#F1F5F9"
fig.update_layout(
    height=560,
    margin=dict(l=10, r=10, t=35, b=10),
    plot_bgcolor=BG, paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02,
        xanchor="left", x=0, font=dict(color="#475569", size=11),
        bgcolor="rgba(0,0,0,0)",
    ),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#1E293B", font_color="#F8FAFC", bordercolor="#334155"),
)
fig.update_yaxes(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10),
                 title_font=dict(color="#94A3B8", size=10), showline=False)
fig.update_xaxes(gridcolor="rgba(0,0,0,0)", tickfont=dict(color="#94A3B8", size=10))

st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ══════════════════════════════════════════════════════════════
# ANÁLISIS DE COSTO — GRÁFICOS DEDICADOS
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="sec">ANÁLISIS DE COSTO · CMG × GENERACIÓN</div>', unsafe_allow_html=True)

if not df_c.empty:
    # Calcular ingresos
    df_merge = pd.merge_asof(
        df_r[["unidad","fecha_hora","gen_real_mw"]].sort_values("fecha_hora"),
        df_c[["fecha_hora","cmg_usd_mwh"]].sort_values("fecha_hora"),
        on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h")
    )
    df_merge["ingreso_usd"] = df_merge["gen_real_mw"] * df_merge["cmg_usd_mwh"]

    ingreso_unit  = df_merge.groupby("unidad")["ingreso_usd"].sum()
    energia_unit  = df_r.groupby("unidad")["gen_real_mw"].sum()
    ingreso_total = ingreso_unit.sum()
    energia_total = energia_unit.sum()
    cmg_prom = df_c["cmg_usd_mwh"].mean()
    cmg_min  = df_c["cmg_usd_mwh"].min()
    cmg_max  = df_c["cmg_usd_mwh"].max()

    gc1, gc2 = st.columns([1, 1])

    # ── Gráfico 1: Ingreso estimado + Energía por unidad ──────
    with gc1:
        unidades_ord = ["ANG1","ANG2","CCR1","CCR2"]
        ingresos_val = [ingreso_unit.get(u, 0) for u in unidades_ord]
        energia_val  = [energia_unit.get(u, 0) for u in unidades_ord]
        colores_bar  = [COLORES[u]["line"] for u in unidades_ord]
        nombres_bar  = [LABELS[u] for u in unidades_ord]

        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(go.Bar(
            x=nombres_bar, y=ingresos_val,
            name="Ingreso est. (USD)",
            marker_color=colores_bar,
            marker_opacity=0.85,
            text=[f"${v:,.0f}" for v in ingresos_val],
            textposition="outside",
            textfont=dict(size=11, color="#475569"),
        ), secondary_y=False)
        fig2.add_trace(go.Scatter(
            x=nombres_bar, y=energia_val,
            name="Energía (MWh)",
            mode="markers+lines",
            marker=dict(size=10, color="#0F172A", symbol="diamond"),
            line=dict(color="#0F172A", width=1.5, dash="dot"),
        ), secondary_y=True)

        fig2.update_layout(
            title=dict(text="Ingreso Estimado + Energía por Unidad", font=dict(size=13, color="#0F172A")),
            height=320, margin=dict(l=10, r=10, t=45, b=10),
            plot_bgcolor=BG, paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=1.15, font=dict(size=10, color="#475569")),
            showlegend=True,
        )
        fig2.update_yaxes(title_text="USD", secondary_y=False,
                          gridcolor=GR, tickfont=dict(color="#94A3B8", size=10),
                          title_font=dict(color="#94A3B8", size=10))
        fig2.update_yaxes(title_text="MWh", secondary_y=True,
                          tickfont=dict(color="#94A3B8", size=10),
                          title_font=dict(color="#94A3B8", size=10),
                          showgrid=False)
        fig2.update_xaxes(tickfont=dict(color="#475569", size=11))
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # ── Gráfico 2: CMG tiempo con stats anotados ──────────────
    with gc2:
        idx_max = df_c["cmg_usd_mwh"].idxmax()
        idx_min = df_c["cmg_usd_mwh"].idxmin()

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"],
            mode="lines",
            line=dict(color=COLORES["CMG"]["line"], width=2),
            fill="tozeroy",
            fillcolor="rgba(124,58,237,0.06)",
            hovertemplate="%{x|%d/%m %H:%M}<br><b>%{y:.1f} USD/MWh</b><extra></extra>",
            name="CMG Crucero",
            showlegend=False,
        ))
        # Línea promedio
        fig3.add_hline(y=cmg_prom, line_color="#64748B", line_width=1.2, line_dash="dot",
                       annotation_text=f"Prom: {cmg_prom:.1f}", annotation_position="right",
                       annotation_font_color="#64748B", annotation_font_size=10)
        # Marcador máximo
        fig3.add_trace(go.Scatter(
            x=[df_c.loc[idx_max, "fecha_hora"]],
            y=[cmg_max],
            mode="markers+text",
            marker=dict(size=10, color="#EF4444", symbol="triangle-up"),
            text=[f" Máx: {cmg_max:.1f}"],
            textposition="top right",
            textfont=dict(size=10, color="#EF4444"),
            showlegend=False,
            hovertemplate=f"Máximo: {cmg_max:.1f} USD/MWh<extra></extra>",
        ))
        # Marcador mínimo
        fig3.add_trace(go.Scatter(
            x=[df_c.loc[idx_min, "fecha_hora"]],
            y=[cmg_min],
            mode="markers+text",
            marker=dict(size=10, color="#10B981", symbol="triangle-down"),
            text=[f" Mín: {cmg_min:.1f}"],
            textposition="bottom right",
            textfont=dict(size=10, color="#10B981"),
            showlegend=False,
            hovertemplate=f"Mínimo: {cmg_min:.1f} USD/MWh<extra></extra>",
        ))
        fig3.update_layout(
            title=dict(text="CMG Nodo Crucero en el Tiempo", font=dict(size=13, color="#0F172A")),
            height=320, margin=dict(l=10, r=60, t=45, b=10),
            plot_bgcolor=BG, paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="USD/MWh", gridcolor=GR,
                       tickfont=dict(color="#94A3B8", size=10),
                       title_font=dict(color="#94A3B8", size=10)),
            xaxis=dict(tickfont=dict(color="#94A3B8", size=10), showgrid=False),
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#1E293B", font_color="#F8FAFC"),
        )
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    # ── Resumen numérico compacto ──────────────────────────────
    rc1, rc2, rc3, rc4 = st.columns(4)
    for col, (lbl, val, sub) in zip(
        [rc1, rc2, rc3, rc4],
        [
            ("Ingreso Total Est.", f"${ingreso_total:,.0f}", "USD en el período"),
            ("Energía Total",      f"{energia_total:,.0f}",  "MWh generados"),
            ("CMG Promedio",       f"{cmg_prom:.1f}",        "USD/MWh"),
            ("Rango CMG",         f"{cmg_min:.1f} – {cmg_max:.1f}", "USD/MWh mín/máx"),
        ]
    ):
        col.metric(lbl, val, sub)

else:
    st.info("Sin datos de CMG para el período — los gráficos de costo estarán disponibles cuando haya datos.")


# ══════════════════════════════════════════════════════════════
# TABLA DE DATOS
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="sec">DATOS HORARIOS</div>', unsafe_allow_html=True)

with st.expander("Ver tabla completa"):
    df_pv = df_r.pivot_table(
        index="fecha_hora", columns="unidad",
        values="gen_real_mw", aggfunc="mean"
    ).reset_index()
    if not df_c.empty:
        df_pv = df_pv.merge(
            df_c[["fecha_hora","cmg_usd_mwh"]].rename(columns={"cmg_usd_mwh":"CMG (USD/MWh)"}),
            on="fecha_hora", how="left"
        )
    df_pv["fecha_hora"] = pd.to_datetime(df_pv["fecha_hora"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(df_pv, use_container_width=True, hide_index=True)
    st.download_button(
        "Descargar CSV",
        df_pv.to_csv(index=False).encode(),
        f"ctm_{s}.csv", "text/csv"
    )


# ══════════════════════════════════════════════════════════════
# POTENCIA PROGRAMADA — INGRESO MANUAL
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="sec">POTENCIA PROGRAMADA · INGRESO MANUAL</div>', unsafe_allow_html=True)

with st.expander("Ingresar valores de potencia programada"):
    st.caption("Ingresa la potencia programada PCP por unidad y hora. Fuente: despacho CEN o SCADA.")
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1: u_prog  = st.selectbox("Unidad", ["ANG1","ANG2","CCR1","CCR2"], key="up")
    with pc2: f_prog  = st.date_input("Fecha", value=hoy, max_value=hoy, key="fp")
    with pc3: h_prog  = st.number_input("Hora (1-24)", 1, 24, datetime.now().hour+1, key="hp")
    with pc4: mw_prog = st.number_input("MW programados", 0.0, 400.0, step=0.5, key="mwp")

    if st.button("Guardar programada"):
        fh = f"{f_prog} {int(h_prog)-1:02d}:00:00"
        ok = exe(
            """INSERT INTO generacion_programada (unidad,gen_programada_mw,fecha_hora,hora,fuente)
               VALUES (%s,%s,%s,%s,'MANUAL')
               ON CONFLICT (unidad,fecha_hora,fuente) DO UPDATE SET gen_programada_mw=EXCLUDED.gen_programada_mw""",
            (u_prog, mw_prog, fh, int(h_prog))
        )
        if ok:
            st.success(f"Guardado: {LABELS[u_prog]} · Hora {h_prog} · {mw_prog} MW")
            st.cache_data.clear(); st.rerun()

    df_pv2 = load_prog(s, e)
    if not df_pv2.empty:
        df_pv2["fecha_hora"] = pd.to_datetime(df_pv2["fecha_hora"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(
            df_pv2[["unidad","fecha_hora","hora","gen_programada_mw"]].rename(
                columns={"gen_programada_mw":"MW Programado"}
            ),
            use_container_width=True, hide_index=True
        )
    else:
        st.caption("Sin datos de programada ingresados aún.")


# ══════════════════════════════════════════════════════════════
# BITÁCORA
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="sec">BITÁCORA DE NOVEDADES OPERACIONALES</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Ver registros", "Nueva novedad"])

with tab1:
    fu   = st.selectbox("Filtrar por unidad", ["Todas","ANG1","ANG2","CCR1","CCR2"], label_visibility="collapsed")
    df_b = load_bit(s, e, fu)
    if not df_b.empty:
        df_b["fecha"] = df_b["fecha"].astype(str)
        df_b["hora"]  = df_b["hora"].astype(str).str[:5]
        st.dataframe(
            df_b.drop(columns=["id"], errors="ignore"),
            use_container_width=True, hide_index=True
        )
    else:
        st.info("Sin novedades para el período seleccionado.")

with tab2:
    b1, b2, b3 = st.columns([1, 1, 1])
    with b1: ub = st.selectbox("Unidad", ["ANG1","ANG2","CCR1","CCR2"], key="ub")
    with b2: ab = st.text_input("Autor / Turno", key="ab")
    with b3: hb = st.time_input("Hora evento", value=datetime.now().time(), key="hb")
    cb = st.text_area("Comentario", height=90,
                       placeholder="Descripción de la novedad operacional...", key="cb")
    if st.button("Guardar novedad", type="primary"):
        if ab.strip() and cb.strip():
            ok = exe(
                "INSERT INTO bitacora (unidad,autor,comentario,fecha,hora) VALUES (%s,%s,%s,%s,%s)",
                (ub, ab.strip(), cb.strip(), str(date.today()), str(hb))
            )
            if ok:
                st.success("Novedad guardada correctamente.")
                st.cache_data.clear(); st.rerun()
        else:
            st.warning("Completa autor y comentario.")