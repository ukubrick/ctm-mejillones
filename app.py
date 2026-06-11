"""
app.py — Dashboard Complejo Térmico Mejillones v5
Fixes: dots de color en tabs, estado conexión sidebar,
eje X visible, títulos separados, programada visible
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import psycopg2
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, datetime, timedelta
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage

st.set_page_config(
    page_title="Complejo Térmico Mejillones",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded",
)

# Auto-refresh cada 60 minutos (3600000 ms) — mantiene la app despierta y datos frescos
st_autorefresh(interval=3_600_000, limit=None, key="autorefresh_horario")

# Paleta AES: púrpura → azul → cyan → verde (logo AES)
COLORES = {
    "ANG1": {"line":"#6D28D9","prog":"#C4B5FD","badge":"#EDE9FE","text":"#6D28D9","dot":"🟣"},
    "ANG2": {"line":"#2563EB","prog":"#93C5FD","badge":"#DBEAFE","text":"#2563EB","dot":"🔵"},
    "CCR1": {"line":"#0891B2","prog":"#67E8F9","badge":"#CFFAFE","text":"#0891B2","dot":"🩵"},
    "CCR2": {"line":"#16A34A","prog":"#86EFAC","badge":"#DCFCE7","text":"#16A34A","dot":"🟢"},
    "CMG":  {"line":"#6D28D9"},
}
LABELS = {"ANG1":"Angamos U1","ANG2":"Angamos U2","CCR1":"Cochrane U1","CCR2":"Cochrane U2"}

# Potencias máximas reales declaradas por AES Andes ante el CEN
PMAX = {"ANG1": 277.0, "ANG2": 280.0, "CCR1": 276.0, "CCR2": 276.0}

NOMBRES_NODO = {
    "CRUCERO_______220": "Crucero 220kV",
    "TARAPACA______220": "Tarapacá 220kV",
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@300;400;500;600;700&display=swap');
:root{--bg:#F1F5F9;--surf:#FFFFFF;--surf2:#F8FAFC;--bord:#E2E8F0;--txt:#0F172A;--muted:#64748B;--accent:#2563EB;}
.stApp{background:var(--bg)!important;}
.block-container{padding:1.5rem 2rem 3rem;max-width:1400px;}
[data-testid="stSidebar"]{background:#1E293B!important;border-right:1px solid #334155!important;}
[data-testid="stSidebar"] *{color:#E2E8F0!important;}
[data-testid="stSidebar"] .status-box{background:#0F172A!important;border-color:#334155!important;}
[data-testid="stSidebar"] .stCheckbox label{color:#CBD5E1!important;}
[data-testid="stSidebar"] .stDateInput label{color:#94A3B8!important;font-size:0.75rem!important;}
[data-testid="stSidebar"] input{background:#0F172A!important;color:#E2E8F0!important;border-color:#334155!important;}
h1,h2,h3{font-family:'Inter',sans-serif!important;color:var(--txt)!important;}
p,span,div,label{font-family:'Inter',sans-serif!important;}
#MainMenu,footer,header{visibility:hidden;}
[data-testid="stToolbar"]{display:none;}
[data-testid="InputInstructions"]{display:none!important;}
kbd{display:none!important;}
/* keyboard_double / sidebar collapse button fix */
[role="tooltip"]{display:none!important;}
[data-baseweb="tooltip"]{display:none!important;}
.material-symbols-rounded{font-size:0!important;width:0!important;height:0!important;overflow:hidden!important;display:inline-block!important;}
[aria-label*="keyboard"]{display:none!important;}
div[class*="Tooltip"]{display:none!important;}
span[class*="instruction"]{display:none!important;}
[data-testid="InputInstructions"]{display:none!important;visibility:hidden!important;}
span[class*="material"]{font-size:0!important;color:transparent!important;width:0!important;}
[data-testid="stWidgetLabel"] span{font-size:0!important;}
[data-testid="stWidgetLabel"] span[data-testid="stWidgetLabelHelpInline"]{display:none!important;}
/* Forzar sidebar siempre visible y ocultar botón collapse */
[data-testid="stSidebar"]{display:block!important;visibility:visible!important;transform:none!important;left:0!important;min-width:244px!important;}
[data-testid="collapsedControl"]{display:none!important;}
[data-testid="stSidebarCollapseButton"]{display:none!important;}
button[aria-label="Close sidebar"]{display:none!important;}
button[aria-label="Open sidebar"]{display:none!important;}
section[data-testid="stSidebar"] > div:first-child > div:first-child > button{display:none!important;}
.kpi{background:var(--surf);border:1px solid var(--bord);border-radius:12px;padding:1.2rem 1.4rem;box-shadow:0 1px 3px rgba(0,0,0,0.06);}
.kpi-badge{display:inline-block;font-size:0.65rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;padding:3px 10px;border-radius:20px;margin-bottom:0.7rem;}
.kpi-val{font-family:'IBM Plex Mono',monospace;font-size:2rem;font-weight:600;color:var(--txt);line-height:1;}
.kpi-mw{font-size:1rem;font-weight:400;color:var(--muted);}
.kpi-sub{font-size:0.75rem;color:var(--muted);margin-top:0.4rem;}
.kpi-delta{font-size:0.78rem;margin-top:0.5rem;font-weight:500;}
.sec{font-size:0.68rem;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--bord);padding-bottom:0.4rem;margin:1.8rem 0 1rem;}
.dot-status{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle;}
.dot-g{background:#10B981;box-shadow:0 0 5px rgba(16,185,129,0.6);animation:blink 2s infinite;}
.dot-r{background:#EF4444;}
.dot-y{background:#F59E0B;animation:blink 2s infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.status-box{background:var(--surf2);border:1px solid var(--bord);border-radius:8px;padding:0.6rem 0.8rem;margin-top:0.5rem;font-size:0.72rem;}
.stTextInput>div>div>input,.stTextArea>div>div>textarea,.stNumberInput>div>div>input{
    background:var(--surf2)!important;border:1px solid var(--bord)!important;border-radius:8px!important;color:var(--txt)!important;}
.stButton>button{background:var(--accent)!important;color:#fff!important;border:none!important;border-radius:8px!important;font-family:'Inter',sans-serif!important;font-weight:600!important;}
.stButton>button:hover{opacity:.88!important;}
.stTabs [data-baseweb="tab-list"]{gap:4px;}
.stTabs [data-baseweb="tab"]{border-radius:8px 8px 0 0;font-weight:600;font-family:'Inter',sans-serif;}
/* ── Selectbox: valor mostrado ── */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div{color:#0F172A!important;background:#FFFFFF!important;}
[data-testid="stSelectbox"] div[data-baseweb="select"] span{color:#0F172A!important;}
[data-testid="stSelectbox"] div[data-baseweb="select"] input{color:#0F172A!important;}
/* Sidebar selectbox — texto claro sobre fondo oscuro */
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div{color:#E2E8F0!important;background:#1E293B!important;}
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] span{color:#E2E8F0!important;}
/* ── Lista desplegable (portal baseweb, fuera del sidebar DOM) ── */
[data-baseweb="popover"] ul li div,
[data-baseweb="popover"] ul li span,
[data-baseweb="popover"] [role="option"] div,
[data-baseweb="popover"] [role="option"] span{color:#0F172A!important;}
[data-baseweb="popover"] ul{background:#FFFFFF!important;}
[data-baseweb="popover"] [role="option"]{background:#FFFFFF!important;}
[data-baseweb="popover"] [role="option"]:hover{background:#EFF6FF!important;}
[data-baseweb="popover"] [aria-selected="true"]{background:#DBEAFE!important;}
/* ── Select nativo (bitácora "Ver registros" filtro) ── */
select,select option{color:#0F172A!important;background:#FFFFFF!important;}
</style>
<script>
function hideKeyboardHints() {
    document.querySelectorAll('[data-testid="InputInstructions"]').forEach(function(el){el.style.display='none';});
    document.querySelectorAll('.material-symbols-rounded').forEach(function(el){el.style.fontSize='0';el.style.width='0';});
}
hideKeyboardHints();
setInterval(hideKeyboardHints, 500);

// Limpiar estado colapsado de sidebar en localStorage y sessionStorage
(function() {
    try {
        [localStorage, sessionStorage].forEach(function(store) {
            Object.keys(store).forEach(function(k) {
                if (/sidebar|Sidebar|collapsed/i.test(k)) store.removeItem(k);
            });
        });
    } catch(e) {}
})();

// MutationObserver: revertir cualquier intento de Streamlit de colapsar el sidebar
(function() {
    function forceSidebar() {
        var sb = document.querySelector('[data-testid="stSidebar"]');
        if (!sb) return;
        sb.style.setProperty('display','block','important');
        sb.style.setProperty('visibility','visible','important');
        sb.style.setProperty('transform','none','important');
        sb.style.setProperty('left','0','important');
        if (sb.getAttribute('data-collapsed') === 'true') {
            sb.setAttribute('data-collapsed','false');
        }
    }
    forceSidebar();
    var obs = new MutationObserver(forceSidebar);
    obs.observe(document.body, {subtree:true, attributes:true, childList:true});
})();

// Inyectar CSS en <head> para dropdown options (mayor especificidad que variables Streamlit)
(function injectDropdownCSS() {
    var style = document.createElement('style');
    style.innerHTML = [
        '[data-baseweb="popover"] [role="option"] { color: #0F172A !important; background-color: #ffffff !important; }',
        '[data-baseweb="popover"] [role="option"]:hover { background-color: #EFF6FF !important; color: #1E40AF !important; }',
        '[data-baseweb="popover"] [role="option"] * { color: #0F172A !important; }',
        '[data-baseweb="popover"] [aria-selected="true"] { background-color: #DBEAFE !important; }',
        '[data-baseweb="popover"] [aria-selected="true"] * { color: #1E40AF !important; }',
        '[data-baseweb="list"] { background-color: #ffffff !important; }',
        '[data-baseweb="list"] * { color: #0F172A !important; }',
        'ul[data-baseweb="menu"] li { color: #0F172A !important; background-color: #ffffff !important; }',
        'ul[data-baseweb="menu"] li * { color: #0F172A !important; }',
    ].join('\n');
    document.head.appendChild(style);
    // Re-aplicar cuando Streamlit monta nuevos portales
    var obs2 = new MutationObserver(function(muts) {
        muts.forEach(function(m) {
            m.addedNodes.forEach(function(node) {
                if (node.nodeType !== 1) return;
                var opts = node.querySelectorAll ? node.querySelectorAll('[role="option"]') : [];
                opts.forEach(function(el) {
                    el.style.setProperty('color','#0F172A','important');
                    el.style.setProperty('background-color','#ffffff','important');
                });
            });
        });
    });
    obs2.observe(document.body, {childList:true, subtree:true});
})();
</script>
""", unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════
# GENERADOR PDF — Formato Highlight Semanal
# ══════════════════════════════════════════════════════════════
def generar_pdf(df_real, df_prog, df_cmg, start_str, end_str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, HRFlowable
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import io as _io

    buf = _io.BytesIO()
    W, H = A4  # portrait
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    # Colores AES
    C_DARK   = HexColor("#0F172A")
    C_BLUE   = HexColor("#2563EB")
    C_GRAY   = HexColor("#64748B")
    C_LGRAY  = HexColor("#94A3B8")

    UNIT_REAL = {"ANG1":"#1E3A8A","ANG2":"#1E3A8A","CCR1":"#1E3A8A","CCR2":"#1E3A8A"}
    UNIT_PROG = {"ANG1":"#67E8F9","ANG2":"#67E8F9","CCR1":"#67E8F9","CCR2":"#67E8F9"}
    UNIT_NAMES= {"ANG1":"Angamos 1","ANG2":"Angamos 2","CCR1":"Cochrane 1","CCR2":"Cochrane 2"}

    # Estilos
    sTitle   = ParagraphStyle("t",  fontName="Helvetica-Bold", fontSize=22, textColor=C_DARK, spaceAfter=6)
    sSub     = ParagraphStyle("s",  fontName="Helvetica",      fontSize=13, textColor=C_GRAY, spaceAfter=4)
    sWeek    = ParagraphStyle("w",  fontName="Helvetica-Bold", fontSize=15, textColor=C_DARK, spaceAfter=4)
    sPeriod  = ParagraphStyle("p",  fontName="Helvetica",      fontSize=12, textColor=C_GRAY, spaceAfter=20)
    sUnit    = ParagraphStyle("u",  fontName="Helvetica-Bold", fontSize=16, textColor=C_DARK, spaceAfter=10)
    sDate    = ParagraphStyle("d",  fontName="Helvetica-Bold", fontSize=10, textColor=C_BLUE, spaceAfter=2)
    sNov     = ParagraphStyle("n",  fontName="Helvetica",      fontSize=10, textColor=C_DARK, spaceAfter=8, leftIndent=0)
    sNone    = ParagraphStyle("nn", fontName="Helvetica-Oblique",fontSize=10, textColor=C_LGRAY,spaceAfter=8)
    sFooter  = ParagraphStyle("f",  fontName="Helvetica",      fontSize=8,  textColor=C_LGRAY, alignment=TA_CENTER)

    # Número de semana
    try:
        from datetime import datetime as _dt
        dt_start = _dt.strptime(start_str, "%Y-%m-%d")
        semana_num = dt_start.isocalendar()[1]
    except: semana_num = "—"

    # Fecha formateada
    def fmt(d):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
        except: return d

    story = []

    # ── PORTADA ──────────────────────────────────────────────
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph("Complejo Térmico Mejillones", sTitle))
    story.append(Paragraph("Thermal Operations", sSub))
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#E2E8F0")))
    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph(f"Highlight Semana {semana_num}", sWeek))
    story.append(Paragraph(f"Periodo: {fmt(start_str)} — {fmt(end_str)}", sPeriod))
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph(
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}  ·  Fuente: API CEN SIPUB + CMG S3",
        sFooter
    ))
    from reportlab.platypus import PageBreak
    story.append(PageBreak())

    # ── PÁGINA POR UNIDAD ─────────────────────────────────────
    for u in ["ANG1","ANG2","CCR1","CCR2"]:
        df_u  = df_real[df_real["unidad"]==u].sort_values("fecha_hora") if not df_real.empty else pd.DataFrame()
        df_up = df_prog[df_prog["unidad"]==u].sort_values("fecha_hora") if not df_prog.empty else pd.DataFrame()

        # Novedades de bitácora — query directa
        try:
            novedades = qry(
                "SELECT fecha, hora, comentario FROM bitacora WHERE unidad=%s AND fecha BETWEEN %s AND %s ORDER BY fecha,hora",
                (u, start_str, end_str)
            )
        except: novedades = pd.DataFrame()

        # Header unidad
        story.append(Paragraph(UNIT_NAMES[u], sUnit))

        # Novedades arriba (si existen)
        if not novedades.empty:
            for _, row in novedades.iterrows():
                fecha_str = str(row["fecha"])
                hora_str  = str(row["hora"])[:5]
                try:
                    from datetime import datetime as _dt
                    fd = _dt.strptime(fecha_str, "%Y-%m-%d").strftime("%d/%m/%Y")
                except: fd = fecha_str
                story.append(Paragraph(f"{fd} — {hora_str} hrs", sDate))
                story.append(Paragraph(str(row["comentario"]), sNov))
        else:
            story.append(Paragraph("Sin novedades", sNone))

        # Gráfico
        if not df_u.empty:
            fig, ax = plt.subplots(figsize=(15, 4.5))
            ax.plot(df_u["fecha_hora"], df_u["gen_real_mw"],
                   color=UNIT_REAL[u], linewidth=2.2, label="Potencia Real MW", zorder=3)
            if not df_up.empty:
                ax.plot(df_up["fecha_hora"], df_up["gen_programada_mw"],
                       color=UNIT_PROG[u], linewidth=2.2, label="Potencia Programada MW", zorder=2)
                # Área entre curvas
                df_m = pd.merge_asof(
                    df_u[["fecha_hora","gen_real_mw"]].sort_values("fecha_hora"),
                    df_up[["fecha_hora","gen_programada_mw"]].sort_values("fecha_hora"),
                    on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h")
                ).dropna()
                if not df_m.empty:
                    ax.fill_between(df_m["fecha_hora"], df_m["gen_real_mw"],
                                   df_m["gen_programada_mw"],
                                   alpha=0.12, color="#2563EB")
            ax.set_ylabel("MW", fontsize=10)
            ax.set_ylim(bottom=0)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d/%m"))
            ax.xaxis.set_major_locator(mdates.DayLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), fontsize=9)
            ax.tick_params(axis="y", labelsize=9)
            ax.set_facecolor("#FAFBFF")
            ax.grid(axis="y", color="#E2E8F0", linewidth=0.8)
            ax.grid(axis="x", color="#E2E8F0", linewidth=0.5)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.legend(loc="lower right", fontsize=9, framealpha=0.9)
            fig.patch.set_facecolor("white")
            fig.tight_layout(pad=0.5)

            img_buf = _io.BytesIO()
            fig.savefig(img_buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            img_buf.seek(0)
            story.append(Spacer(1, 0.3*cm))
            story.append(RLImage(img_buf, width=17*cm, height=7.5*cm))

        # CMG stats si hay datos
        if not df_cmg.empty:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph(
                f"CMG Nodo Crucero (preliminar) · Prom: {df_cmg['cmg_usd_mwh'].mean():.1f} USD/MWh  ·  "
                f"Mín: {df_cmg['cmg_usd_mwh'].min():.1f}  ·  Máx: {df_cmg['cmg_usd_mwh'].max():.1f}",
                ParagraphStyle("cmg", fontName="Helvetica", fontSize=8, textColor=C_LGRAY)
            ))

        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#E2E8F0")))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            f"Reporte generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            sFooter
        ))
        story.append(PageBreak())

    # Quitar último PageBreak
    if story and isinstance(story[-1], PageBreak):
        story.pop()

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── DB ────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    url = st.secrets.get("DATABASE_URL","")
    if not url: st.error("DATABASE_URL no configurada."); st.stop()
    return psycopg2.connect(url)

def test_conn():
    try:
        conn = get_conn()
        with conn.cursor() as c: c.execute("SELECT 1")
        return True, None
    except Exception:
        get_conn.clear()
        try:
            conn = get_conn()
            with conn.cursor() as c: c.execute("SELECT 1")
            return True, None
        except Exception as e:
            return False, str(e)

def qry(sql, params=None):
    try:
        conn = get_conn()
        return pd.read_sql(sql, conn, params=params)
    except Exception:
        get_conn.clear()
        try: return pd.read_sql(sql, get_conn(), params=params)
        except Exception as ex: st.error(f"Error DB: {ex}"); return pd.DataFrame()

def exe(sql, params=None):
    try:
        conn = get_conn()
        with conn.cursor() as c: c.execute(sql, params)
        conn.commit(); return True
    except Exception as e: st.error(f"Error DB: {e}"); return False

def exe_many(sql, params_list):
    try:
        conn = get_conn()
        with conn.cursor() as c: c.executemany(sql, params_list)
        conn.commit(); return True
    except Exception as e: st.error(f"Error DB: {e}"); return False


# ── Datos ─────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_real(s,e):
    df = qry("SELECT unidad,gen_real_mw,fecha_hora,hora,potencia_maxima FROM generacion_real WHERE fecha_hora::date BETWEEN %s AND %s ORDER BY unidad,fecha_hora",(s,e))
    if not df.empty: df["fecha_hora"]=pd.to_datetime(df["fecha_hora"])
    return df

@st.cache_data(ttl=300)
def load_prog(s,e):
    df = qry("""
        SELECT DISTINCT ON (unidad, fecha_hora)
            unidad, gen_programada_mw, fecha_hora, hora, fuente
        FROM generacion_programada
        WHERE fecha_hora::date BETWEEN %s AND %s
        ORDER BY unidad, fecha_hora,
            CASE fuente WHEN 'CEN_PCP' THEN 0 ELSE 1 END
    """, (s,e))
    if not df.empty: df["fecha_hora"]=pd.to_datetime(df["fecha_hora"])
    return df

@st.cache_data(ttl=300)
def load_cmg(s, e, nodo="CRUCERO_______220"):
    df = qry(
        "SELECT fecha_hora,hora,cmg_usd_mwh FROM costo_marginal "
        "WHERE barra_transf=%s AND fecha_hora::date BETWEEN %s AND %s "
        "ORDER BY fecha_hora",
        (nodo, s, e),
    )
    if not df.empty: df["fecha_hora"]=pd.to_datetime(df["fecha_hora"])
    return df

@st.cache_data(ttl=300)
def load_sscc(s, e):
    return qry(
        "SELECT unidad, instruccion_sscc, fecha, inicio_periodo, fin_periodo, "
        "disponibilidad, motivo, comentario, estado_sabana "
        "FROM sscc_instrucciones "
        "WHERE fecha BETWEEN %s AND %s "
        "ORDER BY fecha DESC, unidad, inicio_periodo",
        (s, e),
    )

@st.cache_data(ttl=60)
def load_bit(s,e,u=None):
    if u and u!="Todas":
        return qry("SELECT id,unidad,autor,comentario,fecha,hora FROM bitacora WHERE fecha BETWEEN %s AND %s AND unidad=%s ORDER BY fecha DESC,hora DESC",(s,e,u))
    return qry("SELECT id,unidad,autor,comentario,fecha,hora FROM bitacora WHERE fecha BETWEEN %s AND %s ORDER BY fecha DESC,hora DESC",(s,e))


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚡ Complejo Térmico Mejillones")
    st.markdown('<p style="font-size:0.75rem;color:#64748B;margin-bottom:0.3rem">Complejo Térmico · Monitoreo Operacional</p>', unsafe_allow_html=True)

    # Estado de conexión y fuentes
    db_ok, db_err = test_conn()
    dot_db = "dot-g" if db_ok else "dot-r"
    txt_db = "Conectado · Supabase / PostgreSQL" if db_ok else "Error de conexión DB"

    # Última adquisición por fuente
    _ult_r   = qry("SELECT MAX(fecha_hora) AS t FROM generacion_real")
    _ult_p   = qry("SELECT MAX(fecha_hora) AS t FROM generacion_programada WHERE fuente='CEN_PCP'")
    _ult_cmg = qry("SELECT MAX(fecha_hora) AS t FROM costo_marginal")
    _ult_s   = qry("SELECT MAX(fecha_accion) AS t FROM sscc_instrucciones")

    def _fmt(df, fmt="%d/%m %H:%M"):
        v = df.iloc[0]["t"] if not df.empty else None
        if v is None or pd.isna(v): return "—"
        if hasattr(v, "strftime"): return v.strftime(fmt)
        return str(v)[:16]

    str_r   = _fmt(_ult_r)
    str_p   = _fmt(_ult_p)
    str_cmg = _fmt(_ult_cmg)
    str_s   = _fmt(_ult_s, "%d/%m/%Y")

    st.markdown(f"""
    <div class="status-box">
        <div style="margin-bottom:6px">
            <span class="dot-status {dot_db}"></span>
            <span style="font-size:0.72rem;font-weight:600">{txt_db}</span>
        </div>
        <div style="font-size:0.68rem;line-height:2">
            <span class="dot-status dot-g"></span>Gen. real → <b>{str_r}</b><br>
            <span class="dot-status dot-g"></span>Gen. programada → <b>{str_p}</b><br>
            <span class="dot-status dot-g"></span>CMG S3 → <b>{str_cmg}</b><br>
            <span class="dot-status dot-g"></span>SSCC → <b>{str_s}</b><br>
            <span class="dot-status dot-g"></span>Adquisición GitHub Actions · /hora
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    hoy   = date.today()
    inicio_semana = hoy - timedelta(days=7)
    fi = st.date_input("Desde", value=inicio_semana, max_value=hoy)
    ff = st.date_input("Hasta", value=hoy,   max_value=hoy)
    if fi > ff: st.error("Fecha inicio > fin"); st.stop()
    st.markdown("---")
    mostrar_prog = st.checkbox("Mostrar programada", value=True)
    mostrar_cmg  = st.checkbox("Mostrar CMG en gráficos", value=True)
    nodo_cmg = "CRUCERO_______220"
    if mostrar_cmg:
        nodo_sel = st.radio(
            "Nodo CMG",
            list(NOMBRES_NODO.keys()),
            format_func=lambda x: NOMBRES_NODO[x],
            key="nodo_cmg_sel",
        )
        nodo_cmg = nodo_sel
    st.markdown("---")
    if st.button("Actualizar datos"):
        st.cache_data.clear(); st.rerun()

    st.markdown("---")
    st.markdown('<p style="font-size:0.72rem;font-weight:600;color:#475569">REPORTE PDF</p>', unsafe_allow_html=True)
    if st.button("Generar PDF"):
        with st.spinner("Generando reporte..."):
            try:
                s_pdf = fi.strftime("%Y-%m-%d")
                e_pdf = ff.strftime("%Y-%m-%d")
                pdf_bytes = generar_pdf(
                    load_real(s_pdf, e_pdf),
                    load_prog(s_pdf, e_pdf),
                    load_cmg(s_pdf, e_pdf),
                    s_pdf, e_pdf
                )
                st.download_button(
                    "Descargar PDF",
                    data=pdf_bytes,
                    file_name=f"CTM-Reporte_{s_pdf}_{e_pdf}.pdf",
                    mime="application/pdf",
                )
            except Exception as ex:
                st.error(f"Error generando PDF: {ex}")

    st.markdown(f'<p style="font-size:0.65rem;color:#94A3B8">{datetime.now().strftime("%d/%m/%Y %H:%M")}</p>', unsafe_allow_html=True)

s = fi.strftime("%Y-%m-%d")
e = ff.strftime("%Y-%m-%d")

with st.spinner("Cargando datos..."):
    df_r = load_real(s,e)
    df_p = load_prog(s,e)
    df_c = load_cmg(s, e, nodo_cmg)

if df_r.empty: st.warning("Sin datos para el período seleccionado."); st.stop()


# ── Header ────────────────────────────────────────────────────
ch1,ch2 = st.columns([3,1])
with ch1:
    st.markdown("# Dashboard Operacional — Complejo Térmico Mejillones")
    st.markdown(f'<p style="color:#64748B;font-size:0.85rem;margin-top:-0.5rem">Período {s} → {e} · Generación real + Programada PCP + CMG {NOMBRES_NODO.get(nodo_cmg, "Crucero 220kV")}</p>', unsafe_allow_html=True)
with ch2:
    ult_real = df_r["fecha_hora"].max()
    ult_prog = df_p["fecha_hora"].max() if not df_p.empty else None
    ult_cmg  = df_c["fecha_hora"].max() if not df_c.empty else None
    df_sscc_hdr = load_sscc(s, e)
    ult_sscc = df_sscc_hdr["fecha"].max() if not df_sscc_hdr.empty else None

    diff = (datetime.now() - ult_real.to_pydatetime()).seconds
    cls_r = "dot-g" if diff < 7200 else "dot-y"
    prog_str = ult_prog.strftime("%d/%m %H:%M") if ult_prog is not None else "—"
    cmg_str  = ult_cmg.strftime("%d/%m %H:%M")  if ult_cmg  is not None else "—"
    sscc_str = str(ult_sscc) if ult_sscc is not None else "—"

    st.markdown(f'''<div style="text-align:right;padding-top:1rem;line-height:2">
        <div><span class="dot-status {cls_r}"></span><span style="font-size:0.72rem;color:#64748B">Gen. real: <b>{ult_real.strftime("%d/%m %H:%M")}</b></span></div>
        <div><span class="dot-status dot-g"></span><span style="font-size:0.72rem;color:#64748B">Gen. programada: <b>{prog_str}</b></span></div>
        <div><span class="dot-status dot-g"></span><span style="font-size:0.72rem;color:#64748B">CMG {NOMBRES_NODO.get(nodo_cmg,"Crucero 220kV")}: <b>{cmg_str}</b></span></div>
        <div><span class="dot-status dot-g"></span><span style="font-size:0.72rem;color:#64748B">SSCC: <b>{sscc_str}</b></span></div>
    </div>''', unsafe_allow_html=True)


# ── KPI cards ─────────────────────────────────────────────────
st.markdown('<div class="sec">GENERACIÓN REAL · PROMEDIO DEL PERÍODO</div>', unsafe_allow_html=True)
cols = st.columns(4)
for i,u in enumerate(["ANG1","ANG2","CCR1","CCR2"]):
    with cols[i]:
        df_u = df_r[df_r["unidad"]==u]
        if df_u.empty:
            st.markdown(f'<div class="kpi"><div class="kpi-badge" style="background:{COLORES[u]["badge"]};color:{COLORES[u]["text"]}">{LABELS[u]}</div><div class="kpi-val">—</div></div>', unsafe_allow_html=True)
            continue
        prom  = df_u["gen_real_mw"].mean()
        pmax  = PMAX.get(u, 0)
        fp    = prom/pmax*100 if pmax else 0
        ult_mw= df_u.sort_values("fecha_hora").iloc[-1]["gen_real_mw"]
        delta = ult_mw-prom
        sym   = "▲" if delta>=0 else "▼"
        col_d = "#10B981" if delta>=0 else "#EF4444"
        st.markdown(f"""<div class="kpi">
            <div class="kpi-badge" style="background:{COLORES[u]['badge']};color:{COLORES[u]['text']}">{LABELS[u]}</div>
            <div class="kpi-val">{prom:.1f}<span class="kpi-mw"> MW</span></div>
            <div class="kpi-sub">Factor de planta {fp:.0f}%</div>
            <div class="kpi-delta" style="color:{col_d}">{sym} {abs(delta):.1f} MW vs última hora</div>
        </div>""", unsafe_allow_html=True)


# ── Función gráfico por unidad ────────────────────────────────
BG = "#FFFFFF"; GR = "#F1F5F9"

def chart_unidad(unidad: str, mostrar_desviacion: bool = False, nodo_label: str = "Crucero 220kV"):
    df_u  = df_r[df_r["unidad"]==unidad].sort_values("fecha_hora")
    df_up = df_p[df_p["unidad"]==unidad].sort_values("fecha_hora") if not df_p.empty else pd.DataFrame()
    c     = COLORES[unidad]

    tiene_cmg  = mostrar_cmg and not df_c.empty
    tiene_prog = mostrar_prog and not df_up.empty

    n_rows  = 2 if tiene_cmg else 1
    heights = [0.62, 0.38] if n_rows==2 else [1.0]

    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=True,
        row_heights=heights,
        vertical_spacing=0.12,
    )

    if df_u.empty:
        st.info(f"Sin datos para {LABELS[unidad]} en el período.")
        return

    # ── Real ──
    fig.add_trace(go.Scatter(
        x=df_u["fecha_hora"], y=df_u["gen_real_mw"],
        name="Real", mode="lines",
        line=dict(color=c["line"], width=3),
        hovertemplate="<b>Real</b> %{x|%d/%m %H:%M}<br>%{y:.1f} MW<extra></extra>",
    ), row=1, col=1)

    # ── Programada ──
    if tiene_prog:
        # Color oscurecido de la unidad para que la línea punteada sea legible
        r_d = min(255, int(c["line"][1:3],16) + 40)
        g_d = min(255, int(c["line"][3:5],16) + 30)
        b_d = min(255, int(c["line"][5:7],16) + 50)
        color_prog_dark = f"rgba({r_d},{g_d},{b_d},0.85)"
        fig.add_trace(go.Scatter(
            x=df_up["fecha_hora"], y=df_up["gen_programada_mw"],
            name="Programada", mode="lines",
            line=dict(color=color_prog_dark, width=2.2, dash="dash"),
            hovertemplate="<b>Programada</b> %{x|%d/%m %H:%M}<br>%{y:.1f} MW<extra></extra>",
        ), row=1, col=1)

        # ── Área de desviación ──
        if mostrar_desviacion:
            # Reindexar ambas series al mismo índice horario para evitar huecos
            idx_real = df_u.set_index("fecha_hora")["gen_real_mw"]
            idx_prog = df_up.set_index("fecha_hora")["gen_programada_mw"]
            idx_com  = idx_real.index.union(idx_prog.index)
            real_ri  = idx_real.reindex(idx_com).interpolate("time")
            prog_ri  = idx_prog.reindex(idx_com).interpolate("time")
            df_merge = pd.DataFrame({"real": real_ri, "prog": prog_ri}).dropna()
            if not df_merge.empty:
                r_int = int(c["line"][1:3],16)
                g_int = int(c["line"][3:5],16)
                b_int = int(c["line"][5:7],16)
                ts = df_merge.index.tolist()
                fig.add_trace(go.Scatter(
                    x=ts + ts[::-1],
                    y=df_merge["real"].tolist() + df_merge["prog"].tolist()[::-1],
                    fill="toself",
                    fillcolor=f"rgba({r_int},{g_int},{b_int},0.15)",
                    line=dict(color="rgba(0,0,0,0)"),
                    hoverinfo="skip", showlegend=True, name="Desviación",
                ), row=1, col=1)

    # ── CMG ──
    if tiene_cmg:
        fig.add_trace(go.Scatter(
            x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"],
            name=f"CMG {nodo_label}", mode="lines",
            line=dict(color=COLORES["CMG"]["line"], width=2),
            fill="tozeroy", fillcolor="rgba(109,40,217,0.10)",
            hovertemplate="<b>CMG</b> %{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>",
        ), row=2, col=1)
        prom_cmg = df_c["cmg_usd_mwh"].mean()
        fig.add_hline(
            y=prom_cmg, line_color="#94A3B8", line_width=1, line_dash="dot",
            annotation_text=f"Prom: {prom_cmg:.1f}", annotation_position="right",
            annotation_font_color="#64748B", annotation_font_size=10,
            row=2, col=1
        )

    # ── Layout ──
    fig.update_layout(
        height=520,
        margin=dict(l=10, r=70, t=20, b=10),
        plot_bgcolor=BG, paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0,
            font=dict(color="#475569", size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1E293B", font_color="#F8FAFC", bordercolor="#334155"),
    )

    # ── Eje Y ──
    fig.update_yaxes(
        title_text="MW", gridcolor=GR, zeroline=False,
        tickfont=dict(color="#94A3B8", size=10),
        title_font=dict(color="#94A3B8", size=11),
        row=1, col=1
    )
    if tiene_cmg:
        fig.update_yaxes(
            title_text="USD/MWh", gridcolor=GR, zeroline=False,
            tickfont=dict(color="#94A3B8", size=10),
            title_font=dict(color="#94A3B8", size=11),
            row=2, col=1
        )

    # ── Eje X visible en TODAS las filas ──
    for r in range(1, n_rows+1):
        fig.update_xaxes(
            showticklabels=True,
            tickformat="%d/%m\n%H:%M",
            tickfont=dict(color="#64748B", size=10),
            showgrid=False,
            row=r, col=1
        )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if mostrar_prog and df_up.empty:
        st.caption("💡 Sin datos de programada — se importan automáticamente desde CEN PCP cada hora. El ingreso manual está disponible más abajo.")


# ── Tabs por unidad ───────────────────────────────────────────
st.markdown(f'<div class="sec">POTENCIA REAL vs PROGRAMADA + CMG {NOMBRES_NODO.get(nodo_cmg,"Crucero 220kV").upper()} · POR UNIDAD</div>', unsafe_allow_html=True)

# Checkbox desviación — solo si hay programada
hay_prog_general = not df_p.empty
mostrar_desv = False
if hay_prog_general and mostrar_prog:
    mostrar_desv = st.checkbox("Mostrar área de desviación (Real vs Programada)", value=True)

tabs = st.tabs([
    f"{COLORES[u]['dot']} {LABELS[u]}" for u in ["ANG1","ANG2","CCR1","CCR2"]
])
for tab, u in zip(tabs, ["ANG1","ANG2","CCR1","CCR2"]):
    with tab:
        c = COLORES[u]
        nl = NOMBRES_NODO.get(nodo_cmg, "Crucero 220kV")
        st.markdown(f'<p style="color:{c["text"]};font-weight:600;font-size:0.9rem;margin-bottom:0.5rem">{LABELS[u]} · Real vs Programada (MW) + CMG {nl} (USD/MWh)</p>', unsafe_allow_html=True)
        chart_unidad(u, mostrar_desviacion=mostrar_desv, nodo_label=nl)


# ── Análisis de costo ─────────────────────────────────────────
st.markdown('<div class="sec">ANÁLISIS DE COSTO · CMG × GENERACIÓN</div>', unsafe_allow_html=True)

if not df_c.empty:
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

    gc1, gc2 = st.columns(2)
    unidades_ord = ["ANG1","ANG2","CCR1","CCR2"]

    with gc1:
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(go.Bar(
            x=[LABELS[u] for u in unidades_ord],
            y=[ingreso_unit.get(u,0) for u in unidades_ord],
            name="Ingreso est. (USD)",
            marker_color=[COLORES[u]["line"] for u in unidades_ord],
            marker_opacity=0.85,
            text=[f"${ingreso_unit.get(u,0):,.0f}" for u in unidades_ord],
            textposition="outside",
            textfont=dict(size=11, color="#475569"),
        ), secondary_y=False)
        fig2.add_trace(go.Scatter(
            x=[LABELS[u] for u in unidades_ord],
            y=[energia_unit.get(u,0) for u in unidades_ord],
            name="Energía (MWh)", mode="markers+lines",
            marker=dict(size=10, color="#0F172A", symbol="diamond"),
            line=dict(color="#0F172A", width=1.5, dash="dot"),
        ), secondary_y=True)
        fig2.update_layout(
            title=dict(text="Ingreso Estimado + Energía por Unidad",
                      font=dict(size=13,color="#0F172A"), x=0),
            height=340,
            margin=dict(l=10, r=10, t=60, b=10),
            plot_bgcolor=BG, paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.15, x=0,
                       font=dict(size=10,color="#475569")),
        )
        fig2.update_yaxes(title_text="USD", secondary_y=False,
                          gridcolor=GR, tickfont=dict(color="#94A3B8",size=10),
                          title_font=dict(color="#94A3B8",size=10))
        fig2.update_yaxes(title_text="MWh", secondary_y=True,
                          tickfont=dict(color="#94A3B8",size=10),
                          title_font=dict(color="#94A3B8",size=10), showgrid=False)
        fig2.update_xaxes(tickfont=dict(color="#475569",size=11))
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

    with gc2:
        idx_max = df_c["cmg_usd_mwh"].idxmax()
        idx_min = df_c["cmg_usd_mwh"].idxmin()
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"],
            mode="lines", line=dict(color=COLORES["CMG"]["line"],width=2),
            fill="tozeroy", fillcolor="rgba(109,40,217,0.12)",
            showlegend=False,
            hovertemplate="%{x|%d/%m %H:%M}<br><b>%{y:.1f} USD/MWh</b><extra></extra>",
        ))
        fig3.add_hline(y=cmg_prom, line_color="#94A3B8", line_width=1.2, line_dash="dot",
                      annotation_text=f"Prom: {cmg_prom:.1f}",
                      annotation_position="right",
                      annotation_font_color="#64748B", annotation_font_size=10)
        fig3.add_trace(go.Scatter(
            x=[df_c.loc[idx_max,"fecha_hora"]], y=[cmg_max],
            mode="markers+text",
            marker=dict(size=10,color="#EF4444",symbol="triangle-up"),
            text=[f" Máx: {cmg_max:.1f}"], textposition="top right",
            textfont=dict(size=10,color="#EF4444"), showlegend=False,
        ))
        fig3.add_trace(go.Scatter(
            x=[df_c.loc[idx_min,"fecha_hora"]], y=[cmg_min],
            mode="markers+text",
            marker=dict(size=10,color="#10B981",symbol="triangle-down"),
            text=[f" Mín: {cmg_min:.1f}"], textposition="bottom right",
            textfont=dict(size=10,color="#10B981"), showlegend=False,
        ))
        fig3.update_layout(
            title=dict(text="CMG Nodo Crucero en el Tiempo",
                      font=dict(size=13,color="#0F172A"), x=0),
            height=340,
            margin=dict(l=10, r=70, t=60, b=10),
            plot_bgcolor=BG, paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="USD/MWh", gridcolor=GR,
                      tickfont=dict(color="#94A3B8",size=10),
                      title_font=dict(color="#94A3B8",size=10)),
            xaxis=dict(tickfont=dict(color="#94A3B8",size=10),
                      tickformat="%d/%m\n%H:%M", showgrid=False),
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#1E293B",font_color="#F8FAFC"),
        )
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar":False})

    rc1,rc2,rc3,rc4 = st.columns(4)
    for col,(lbl,val,sub) in zip([rc1,rc2,rc3,rc4],[
        ("Ingreso Total Est.", f"${ingreso_total:,.0f}", "USD en el período"),
        ("Energía Total",      f"{energia_total:,.0f}",  "MWh generados"),
        ("CMG Promedio",       f"{cmg_prom:.1f}",        "USD/MWh"),
        ("Rango CMG",          f"{cmg_min:.1f} – {cmg_max:.1f}", "USD/MWh mín/máx"),
    ]):
        col.metric(lbl, val, sub)
else:
    st.info("Sin datos de CMG para calcular estadísticos de costo.")


# ── Servicios Complementarios (SSCC) ─────────────────────────
st.markdown('<div class="sec">SERVICIOS COMPLEMENTARIOS (SSCC)</div>', unsafe_allow_html=True)

COLORES_SSCC = {
    "CSF(+)": "#16A34A", "CSF(-)": "#0891B2",
    "CPF(+)": "#6D28D9", "CPF(-)": "#D97706",
    "CT":     "#64748B",
}
BADGE_SSCC = {
    "CSF(+)": "#DCFCE7", "CSF(-)": "#CFFAFE",
    "CPF(+)": "#EDE9FE", "CPF(-)": "#FEF3C7",
    "CT":     "#F1F5F9",
}
st.markdown("""
<details style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:0.7rem 1rem;margin-bottom:1rem;">
<summary style="cursor:pointer;font-weight:600;color:#334155;font-size:0.9rem;">Guía de instrucciones SSCC — CSF, CPF, CT</summary>
<div style="margin-top:0.8rem;font-size:0.88rem;color:#475569;line-height:1.6;">
<p>Los <strong>Servicios Complementarios (SSCC)</strong> son prestaciones que el Coordinador Eléctrico Nacional instruye
a las unidades generadoras para mantener la seguridad y calidad del Sistema Eléctrico Nacional,
más allá de su generación de energía.</p>
<table style="width:100%;border-collapse:collapse;margin:0.5rem 0;">
<thead><tr style="background:#E2E8F0;">
<th style="padding:6px 12px;text-align:left;font-size:0.82rem;">Instrucción</th>
<th style="padding:6px 12px;text-align:left;font-size:0.82rem;">Significado</th>
</tr></thead>
<tbody>
<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>CSF(+)</strong></td><td style="padding:5px 12px;border-top:1px solid #E2E8F0;">Control Secundario de Frecuencia en <strong>subida</strong> — la unidad debe estar disponible para aumentar potencia y corregir la frecuencia del sistema</td></tr>
<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>CSF(−)</strong></td><td style="padding:5px 12px;border-top:1px solid #E2E8F0;">Control Secundario de Frecuencia en <strong>bajada</strong> — la unidad debe estar disponible para reducir potencia</td></tr>
<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>CPF(+)</strong></td><td style="padding:5px 12px;border-top:1px solid #E2E8F0;">Control Primario de Frecuencia en <strong>subida</strong> — respuesta automática e inmediata ante caída de frecuencia</td></tr>
<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>CPF(−)</strong></td><td style="padding:5px 12px;border-top:1px solid #E2E8F0;">Control Primario de Frecuencia en <strong>bajada</strong> — respuesta automática ante alza de frecuencia</td></tr>
<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>CT</strong></td><td style="padding:5px 12px;border-top:1px solid #E2E8F0;">Control de <strong>Tensión</strong> — regulación de tensión reactiva en la barra de conexión</td></tr>
</tbody>
</table>
<p>Cada instrucción indica un <strong>período de prestación</strong> (inicio → fin) durante el cual la unidad debe
mantener una reserva de potencia disponible para activación. El campo <strong>Disp. MW</strong> indica la capacidad
comprometida cuando está declarada.</p>
</div>
</details>
""", unsafe_allow_html=True)

df_sscc = load_sscc(s, e)

if df_sscc.empty:
    st.info("Sin datos SSCC para el período seleccionado. Los datos se adquieren automáticamente cada hora.", icon="ℹ️")
else:
    total_instr  = len(df_sscc)
    unidades_act = df_sscc["unidad"].nunique()
    tipos_act    = df_sscc["instruccion_sscc"].nunique()
    dias_con_dat = df_sscc["fecha"].nunique()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Instrucciones totales", total_instr)
    k2.metric("Unidades con SSCC",     f"{unidades_act} / 4")
    k3.metric("Tipos de servicio",     tipos_act)
    k4.metric("Días con datos",        dias_con_dat)

    st.markdown("")

    tab_s1, tab_s2, tab_s3 = st.tabs(["Por unidad", "Estadísticas", "Tabla completa"])

    with tab_s1:
        cols_unit = st.columns(4)
        for col, unidad in zip(cols_unit, ["ANG1","ANG2","CCR1","CCR2"]):
            df_u = df_sscc[df_sscc["unidad"] == unidad].sort_values(
                ["fecha", "inicio_periodo"], ascending=[False, False]
            )
            total_u = len(df_u)
            df_u_show = df_u.head(5)
            with col:
                st.markdown(f"**{LABELS[unidad]}**")
                if df_u.empty:
                    st.caption("Sin instrucciones")
                else:
                    for _, row in df_u_show.iterrows():
                        tipo  = str(row["instruccion_sscc"])
                        color = COLORES_SSCC.get(tipo, "#64748B")
                        bg    = BADGE_SSCC.get(tipo, "#F1F5F9")
                        ini   = str(row["inicio_periodo"])[:5] if row["inicio_periodo"] else "—"
                        fin   = str(row["fin_periodo"])[:5]    if row["fin_periodo"]    else "—"
                        fecha = str(row["fecha"])
                        st.markdown(
                            f'<div style="border:1px solid {color}33;border-left:3px solid {color};'
                            f'background:{bg};border-radius:6px;padding:6px 10px;margin-bottom:6px;">'
                            f'<span style="font-weight:700;color:{color};font-size:0.8rem">{tipo}</span>'
                            f'<span style="color:#64748B;font-size:0.72rem;float:right">{fecha}</span><br>'
                            f'<span style="color:#475569;font-size:0.72rem">{ini} → {fin}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    if total_u > 5:
                        st.caption(f"+{total_u - 5} más en «Tabla completa»")

    with tab_s2:
        BG = "rgba(0,0,0,0)"; GR = "#E2E8F0"

        # Gráfico 1: instrucciones por tipo (barras)
        conteo_tipo = df_sscc.groupby("instruccion_sscc").size().reset_index(name="count")
        conteo_tipo = conteo_tipo.sort_values("count", ascending=False)
        fig_tipos = go.Figure(go.Bar(
            x=conteo_tipo["instruccion_sscc"],
            y=conteo_tipo["count"],
            marker_color=[COLORES_SSCC.get(t, "#64748B") for t in conteo_tipo["instruccion_sscc"]],
            text=conteo_tipo["count"], textposition="outside",
        ))
        fig_tipos.update_layout(
            title=dict(text="Instrucciones por tipo de SSCC", font=dict(size=13, color="#0F172A"), x=0),
            height=280, margin=dict(l=10, r=10, t=50, b=10),
            plot_bgcolor=BG, paper_bgcolor=BG,
            xaxis=dict(tickfont=dict(color="#94A3B8", size=11), showgrid=False),
            yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="N° instrucciones"),
        )

        # Gráfico 2: instrucciones por unidad (barras apiladas por tipo)
        pivot_unidad = df_sscc.groupby(["unidad","instruccion_sscc"]).size().reset_index(name="count")
        fig_unidad = go.Figure()
        for tipo in df_sscc["instruccion_sscc"].unique():
            df_t = pivot_unidad[pivot_unidad["instruccion_sscc"] == tipo]
            fig_unidad.add_trace(go.Bar(
                name=tipo,
                x=df_t["unidad"],
                y=df_t["count"],
                marker_color=COLORES_SSCC.get(tipo, "#64748B"),
            ))
        fig_unidad.update_layout(
            barmode="stack",
            title=dict(text="Instrucciones por unidad", font=dict(size=13, color="#0F172A"), x=0),
            height=280, margin=dict(l=10, r=10, t=50, b=10),
            plot_bgcolor=BG, paper_bgcolor=BG,
            xaxis=dict(tickfont=dict(color="#94A3B8", size=11), showgrid=False),
            yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="N° instrucciones"),
            legend=dict(orientation="h", y=-0.2, font=dict(size=10)),
        )

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.plotly_chart(fig_tipos, use_container_width=True, config={"displayModeBar": False})
        with col_g2:
            st.plotly_chart(fig_unidad, use_container_width=True, config={"displayModeBar": False})

        # Gráfico 3: duración promedio por tipo (horas)
        df_dur = df_sscc.copy()
        def parse_hhmm(t):
            try:
                h, m, *_ = str(t).split(":")
                return int(h) + int(m) / 60
            except:
                return None
        df_dur["h_ini"] = df_dur["inicio_periodo"].apply(parse_hhmm)
        df_dur["h_fin"] = df_dur["fin_periodo"].apply(parse_hhmm)
        df_dur["duracion_h"] = (df_dur["h_fin"] - df_dur["h_ini"]).clip(lower=0)
        dur_tipo = df_dur.groupby("instruccion_sscc")["duracion_h"].mean().reset_index()
        dur_tipo = dur_tipo.sort_values("duracion_h", ascending=False)

        fig_dur = go.Figure(go.Bar(
            x=dur_tipo["instruccion_sscc"],
            y=dur_tipo["duracion_h"].round(1),
            marker_color=[COLORES_SSCC.get(t, "#64748B") for t in dur_tipo["instruccion_sscc"]],
            text=dur_tipo["duracion_h"].round(1).astype(str) + " h",
            textposition="outside",
        ))
        fig_dur.update_layout(
            title=dict(text="Duración promedio por tipo (horas)", font=dict(size=13, color="#0F172A"), x=0),
            height=280, margin=dict(l=10, r=10, t=50, b=10),
            plot_bgcolor=BG, paper_bgcolor=BG,
            xaxis=dict(tickfont=dict(color="#94A3B8", size=11), showgrid=False),
            yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="Horas promedio"),
        )

        # Gráfico 4: evolución diaria de instrucciones
        if dias_con_dat > 1:
            evol = df_sscc.groupby(["fecha","instruccion_sscc"]).size().reset_index(name="count")
            evol["fecha"] = pd.to_datetime(evol["fecha"])
            fig_evol = go.Figure()
            for tipo in sorted(df_sscc["instruccion_sscc"].unique()):
                df_e = evol[evol["instruccion_sscc"] == tipo]
                fig_evol.add_trace(go.Scatter(
                    x=df_e["fecha"], y=df_e["count"], name=tipo,
                    mode="lines+markers",
                    line=dict(color=COLORES_SSCC.get(tipo, "#64748B"), width=2),
                    marker=dict(size=6),
                ))
            fig_evol.update_layout(
                title=dict(text="Evolución diaria de instrucciones SSCC", font=dict(size=13, color="#0F172A"), x=0),
                height=280, margin=dict(l=10, r=10, t=50, b=10),
                plot_bgcolor=BG, paper_bgcolor=BG,
                xaxis=dict(tickfont=dict(color="#94A3B8", size=10), showgrid=False, tickformat="%d/%m"),
                yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="N° instrucciones"),
                legend=dict(orientation="h", y=-0.2, font=dict(size=10)),
                hovermode="x unified",
            )
            col_g3, col_g4 = st.columns(2)
            with col_g3:
                st.plotly_chart(fig_dur, use_container_width=True, config={"displayModeBar": False})
            with col_g4:
                st.plotly_chart(fig_evol, use_container_width=True, config={"displayModeBar": False})
        else:
            st.plotly_chart(fig_dur, use_container_width=True, config={"displayModeBar": False})

    with tab_s3:
        df_show_sscc = df_sscc.copy()
        df_show_sscc["inicio"] = df_show_sscc["inicio_periodo"].astype(str).str[:5]
        df_show_sscc["fin"]    = df_show_sscc["fin_periodo"].astype(str).str[:5]
        df_show_sscc["motivo"] = df_show_sscc["motivo"].fillna("").str[:80]
        st.dataframe(
            df_show_sscc[["fecha","unidad","instruccion_sscc","inicio","fin","disponibilidad","motivo","estado_sabana"]].rename(columns={
                "instruccion_sscc": "Instrucción",
                "inicio":           "Inicio",
                "fin":              "Fin",
                "disponibilidad":   "Disp. MW",
                "motivo":           "Motivo",
                "estado_sabana":    "Estado",
            }),
            use_container_width=True, hide_index=True,
        )


# ── Potencia programada ───────────────────────────────────────
st.markdown('<div class="sec">POTENCIA PROGRAMADA · CEN PCP + INGRESO MANUAL</div>', unsafe_allow_html=True)
st.info(
    "Los datos de programación se importan automáticamente desde la API CEN (PCP) cada hora. "
    "El ingreso manual permite agregar o corregir valores de respaldo cuando no hay datos PCP disponibles.",
    icon="ℹ️",
)
tab_p1, tab_p2 = st.tabs(["Por hora", "24 horas de una vez"])

with tab_p1:
    u_prog = st.radio("Unidad", ["ANG1","ANG2","CCR1","CCR2"], key="up", horizontal=True)
    pc2,pc3,pc4 = st.columns(3)
    with pc2: f_prog  = st.date_input("Fecha",value=hoy,max_value=hoy,key="fp")
    with pc3: h_prog  = st.number_input("Hora (1-24)",1,24,datetime.now().hour+1,key="hp")
    with pc4: mw_prog = st.number_input("MW programados",0.0,400.0,step=0.5,key="mwp")
    if st.button("Guardar hora",key="btn_h"):
        fh = f"{f_prog} {int(h_prog)-1:02d}:00:00"
        ok = exe("""INSERT INTO generacion_programada (unidad,gen_programada_mw,fecha_hora,hora,fuente)
                    VALUES (%s,%s,%s,%s,'MANUAL')
                    ON CONFLICT (unidad,fecha_hora,fuente) DO UPDATE SET gen_programada_mw=EXCLUDED.gen_programada_mw""",
                 (u_prog,mw_prog,fh,int(h_prog)))
        if ok: st.success(f"Guardado: {LABELS[u_prog]} H{h_prog} → {mw_prog} MW"); st.cache_data.clear(); st.rerun()

with tab_p2:
    st.caption("Selecciona unidad y fecha, luego pega los 24 valores MW separados por salto de línea (hora 1 → hora 24).")
    u_masa = st.radio("Unidad", ["ANG1","ANG2","CCR1","CCR2"], key="um", horizontal=True)
    mc1,mc2 = st.columns([1,2])
    with mc1:
        f_masa = st.date_input("Fecha",value=hoy,max_value=hoy,key="fm")
        st.caption("Ejemplo formato:\n280.5\n275.3\n271.0\n...")
    with mc2:
        mw_masa = st.text_area("24 valores MW (uno por línea):", height=220, key="mwm",
                               placeholder="280.5\n275.3\n271.0\n268.5\n...")
    if st.button("Guardar las 24 horas",key="btn_m"):
        try:
            valores = [float(v.strip().replace(",",".")) for v in mw_masa.strip().split("\n") if v.strip()]
            if len(valores) != 24:
                st.error(f"Se esperan 24 valores, se ingresaron {len(valores)}.")
            else:
                params_list = [(u_masa, mw, f"{f_masa} {h-1:02d}:00:00", h, "MANUAL") for h,mw in enumerate(valores,1)]
                ok = exe_many("""INSERT INTO generacion_programada (unidad,gen_programada_mw,fecha_hora,hora,fuente)
                                 VALUES (%s,%s,%s,%s,%s)
                                 ON CONFLICT (unidad,fecha_hora,fuente) DO UPDATE SET gen_programada_mw=EXCLUDED.gen_programada_mw""",
                              params_list)
                if ok: st.success(f"24 horas guardadas: {LABELS[u_masa]} · {f_masa}"); st.cache_data.clear(); st.rerun()
        except ValueError:
            st.error("Formato inválido. Solo números, uno por línea.")

df_pv2 = load_prog(s,e)
if not df_pv2.empty:
    show_prog_table = st.checkbox("Ver tabla de datos programados", value=False, key="show_prog_tbl")
    if show_prog_table:
        df_show = df_pv2.copy()
        df_show["fecha_hora"] = pd.to_datetime(df_show["fecha_hora"]).dt.strftime("%Y-%m-%d %H:%M")
        cols_show = ["unidad","fecha_hora","hora","gen_programada_mw","fuente"] if "fuente" in df_show.columns else ["unidad","fecha_hora","hora","gen_programada_mw"]
        st.dataframe(df_show[cols_show].rename(
            columns={"gen_programada_mw":"MW Programado","fuente":"Fuente"}), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**Modificar o eliminar registro programada:**")
    # Necesitamos id — hacer query con id
    df_prog_crud = qry("SELECT id,unidad,gen_programada_mw,fecha_hora,hora FROM generacion_programada WHERE fecha_hora::date BETWEEN %s AND %s AND fuente='MANUAL' ORDER BY unidad,fecha_hora",(s,e))
    if not df_prog_crud.empty:
        df_prog_crud["fecha_hora"] = pd.to_datetime(df_prog_crud["fecha_hora"])
        opc_p = df_prog_crud.apply(lambda r: f"[{r['unidad']}] {r['fecha_hora'].strftime('%d/%m %H:%M')} — {r['gen_programada_mw']:.1f} MW", axis=1).tolist()
        idx_p = st.selectbox("Seleccionar registro programada", range(len(opc_p)),
                             format_func=lambda i: opc_p[i], key="sel_prog")
        reg_p = df_prog_crud.iloc[idx_p]
        col_ep, col_dp = st.columns([2,1])
        with col_ep:
            new_mw_p = st.number_input("Nuevo valor MW:", value=float(reg_p["gen_programada_mw"]),
                                       min_value=0.0, max_value=400.0, step=0.5, key="edit_mw_p")
            if st.button("Actualizar MW", key="upd_prog"):
                ok = exe("UPDATE generacion_programada SET gen_programada_mw=%s WHERE id=%s",
                         (new_mw_p, int(reg_p["id"])))
                if ok: st.success("✅ Actualizado."); st.cache_data.clear(); st.rerun()
        with col_dp:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Eliminar", key="del_prog", type="primary"):
                ok = exe("DELETE FROM generacion_programada WHERE id=%s", (int(reg_p["id"]),))
                if ok: st.success("✅ Eliminado."); st.cache_data.clear(); st.rerun()


# ── Generación real manual (respaldo) ────────────────────────
st.markdown('<div class="sec">GENERACIÓN REAL · INGRESO MANUAL DE RESPALDO</div>', unsafe_allow_html=True)
st.info(
    "Los datos de generación real se importan automáticamente desde la API CEN (SIPUB) cada hora. "
    "El ingreso manual permite agregar o corregir valores cuando la adquisición falla. "
    "Si ya existe un registro para esa unidad/hora, el valor se sobreescribe.",
    icon="ℹ️",
)
tab_r1, tab_r2 = st.tabs(["Por hora", "24 horas de una vez"])

with tab_r1:
    u_real = st.radio("Unidad", ["ANG1","ANG2","CCR1","CCR2"], key="ur", horizontal=True)
    rc2, rc3, rc4 = st.columns(3)
    with rc2: f_real = st.date_input("Fecha", value=hoy, max_value=hoy, key="fr")
    with rc3: h_real = st.number_input("Hora (1-24)", 1, 24, datetime.now().hour+1, key="hr")
    with rc4: mw_real = st.number_input("MW reales", 0.0, 400.0, step=0.5, key="mwr")
    if st.button("Guardar hora real", key="btn_hr"):
        fh_r = f"{f_real} {int(h_real)-1:02d}:00:00"
        ok = exe("""INSERT INTO generacion_real (unidad, gen_real_mw, fecha_hora, hora)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (unidad, fecha_hora) DO UPDATE SET gen_real_mw=EXCLUDED.gen_real_mw""",
                 (u_real, mw_real, fh_r, int(h_real)))
        if ok: st.success(f"Guardado: {LABELS[u_real]} H{h_real} → {mw_real} MW"); st.cache_data.clear(); st.rerun()

with tab_r2:
    st.caption("Selecciona unidad y fecha, luego pega los 24 valores MW separados por salto de línea (hora 1 → hora 24).")
    u_rmasa = st.radio("Unidad", ["ANG1","ANG2","CCR1","CCR2"], key="urm", horizontal=True)
    rm1, rm2 = st.columns([1, 2])
    with rm1:
        f_rmasa = st.date_input("Fecha", value=hoy, max_value=hoy, key="frm")
        st.caption("Ejemplo formato:\n280.5\n275.3\n271.0\n...")
    with rm2:
        mw_rmasa = st.text_area("24 valores MW (uno por línea):", height=220, key="mwrm",
                                placeholder="280.5\n275.3\n271.0\n268.5\n...")
    if st.button("Guardar las 24 horas reales", key="btn_rm"):
        try:
            valores_r = [float(v.strip().replace(",", ".")) for v in mw_rmasa.strip().split("\n") if v.strip()]
            if len(valores_r) != 24:
                st.error(f"Se esperan 24 valores, se ingresaron {len(valores_r)}.")
            else:
                params_r = [(u_rmasa, mw, f"{f_rmasa} {h-1:02d}:00:00", h) for h, mw in enumerate(valores_r, 1)]
                ok = exe_many("""INSERT INTO generacion_real (unidad, gen_real_mw, fecha_hora, hora)
                                 VALUES (%s, %s, %s, %s)
                                 ON CONFLICT (unidad, fecha_hora) DO UPDATE SET gen_real_mw=EXCLUDED.gen_real_mw""",
                              params_r)
                if ok: st.success(f"24 horas guardadas: {LABELS[u_rmasa]} · {f_rmasa}"); st.cache_data.clear(); st.rerun()
        except ValueError:
            st.error("Formato inválido. Solo números, uno por línea.")

df_rv2 = load_real(s, e)
if not df_rv2.empty:
    show_real_table = st.checkbox("Ver tabla de datos reales", value=False, key="show_real_tbl")
    if show_real_table:
        df_rshow = df_rv2.copy()
        df_rshow["fecha_hora"] = pd.to_datetime(df_rshow["fecha_hora"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df_rshow[["unidad","fecha_hora","hora","gen_real_mw"]].rename(
            columns={"gen_real_mw":"MW Real"}), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**Modificar o eliminar registro real:**")
    df_real_crud = qry(
        "SELECT id, unidad, gen_real_mw, fecha_hora, hora FROM generacion_real "
        "WHERE fecha_hora::date BETWEEN %s AND %s ORDER BY unidad, fecha_hora", (s, e))
    if not df_real_crud.empty:
        df_real_crud["fecha_hora"] = pd.to_datetime(df_real_crud["fecha_hora"])
        opc_r = df_real_crud.apply(
            lambda r: f"[{r['unidad']}] {r['fecha_hora'].strftime('%d/%m %H:%M')} — {r['gen_real_mw']:.1f} MW",
            axis=1).tolist()
        idx_r = st.selectbox("Seleccionar registro real", range(len(opc_r)),
                             format_func=lambda i: opc_r[i], key="sel_real")
        reg_r = df_real_crud.iloc[idx_r]
        col_er, col_dr = st.columns([2, 1])
        with col_er:
            new_mw_r = st.number_input("Nuevo valor MW:", value=float(reg_r["gen_real_mw"]),
                                       min_value=0.0, max_value=400.0, step=0.5, key="edit_mw_r")
            if st.button("Actualizar MW real", key="upd_real"):
                ok = exe("UPDATE generacion_real SET gen_real_mw=%s WHERE id=%s",
                         (new_mw_r, int(reg_r["id"])))
                if ok: st.success("✅ Actualizado."); st.cache_data.clear(); st.rerun()
        with col_dr:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Eliminar", key="del_real", type="primary"):
                ok = exe("DELETE FROM generacion_real WHERE id=%s", (int(reg_r["id"]),))
                if ok: st.success("✅ Eliminado."); st.cache_data.clear(); st.rerun()


# ── Datos horarios ────────────────────────────────────────────
st.markdown('<div class="sec">DATOS HORARIOS</div>', unsafe_allow_html=True)
show_table = st.checkbox("Ver tabla completa", value=False)
if show_table:
    df_pv = df_r.pivot_table(index="fecha_hora",columns="unidad",values="gen_real_mw",aggfunc="mean").reset_index()
    if not df_c.empty:
        df_pv = df_pv.merge(df_c[["fecha_hora","cmg_usd_mwh"]].rename(columns={"cmg_usd_mwh":"CMG (USD/MWh)"}),on="fecha_hora",how="left")
    df_pv["fecha_hora"] = pd.to_datetime(df_pv["fecha_hora"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(df_pv, use_container_width=True, hide_index=True)
    st.download_button("Descargar CSV", df_pv.to_csv(index=False).encode(), f"complejo-termico-mejillones_{s}.csv","text/csv")


# ── Bitácora ──────────────────────────────────────────────────
st.markdown('<div class="sec">BITÁCORA DE NOVEDADES OPERACIONALES</div>', unsafe_allow_html=True)
tab_b1,tab_b2 = st.tabs(["Ver registros","Nueva novedad"])
with tab_b1:
    fu   = st.radio("Filtrar", "Todas ANG1 ANG2 CCR1 CCR2".split(), horizontal=True, label_visibility="collapsed")
    df_b = load_bit(s,e,fu)
    if not df_b.empty:
        df_b2 = df_b.copy()
        df_b2["fecha"] = df_b2["fecha"].astype(str)
        df_b2["hora"]  = df_b2["hora"].astype(str).str[:5]
        st.dataframe(df_b2.drop(columns=["id"],errors="ignore"),use_container_width=True,hide_index=True)

        st.markdown("---")
        st.markdown("**Modificar o eliminar registro:**")
        opciones_b = df_b.apply(lambda r: f"[{r['unidad']}] {str(r['fecha'])} {str(r['hora'])[:5]} — {str(r['comentario'])[:50]}", axis=1).tolist()
        idx_b = st.selectbox("Seleccionar registro", range(len(opciones_b)),
                             format_func=lambda i: opciones_b[i], key="sel_bit")
        reg_b = df_b.iloc[idx_b]
        col_edit_b, col_del_b = st.columns([3,1])
        with col_edit_b:
            new_com_b = st.text_area("Editar comentario:", value=str(reg_b.get("comentario","")), height=80, key="edit_com_b")
            if st.button("Actualizar novedad", key="upd_bit"):
                ok = exe("UPDATE bitacora SET comentario=%s WHERE id=%s", (new_com_b.strip(), int(reg_b["id"])))
                if ok: st.success("✅ Actualizado."); st.cache_data.clear(); st.rerun()
        with col_del_b:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Eliminar", key="del_bit", type="primary"):
                ok = exe("DELETE FROM bitacora WHERE id=%s", (int(reg_b["id"]),))
                if ok: st.success("✅ Eliminado."); st.cache_data.clear(); st.rerun()
    else:
        st.info("Sin novedades para el período seleccionado.")
with tab_b2:
    ub = st.radio("Unidad", ["ANG1","ANG2","CCR1","CCR2"], key="ub", horizontal=True)
    b2,b3,b4 = st.columns([1,1,1])
    with b2: ab = st.text_input("Autor / Turno",key="ab")
    with b3: fb = st.date_input("Fecha del evento",value=date.today(),key="fb")
    with b4: hb = st.time_input("Hora evento",value=datetime.now().time(),step=60,key="hb")
    cb = st.text_area("Comentario",height=90,placeholder="Descripción de la novedad operacional...",key="cb")
    if st.button("Guardar novedad",type="primary"):
        if ab.strip() and cb.strip():
            ok = exe("INSERT INTO bitacora (unidad,autor,comentario,fecha,hora) VALUES (%s,%s,%s,%s,%s)",
                     (ub,ab.strip(),cb.strip(),str(fb),str(hb)))
            if ok: st.success("Novedad guardada."); st.cache_data.clear(); st.rerun()
        else: st.warning("Completa autor y comentario.")

# ── Footer ───────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:3rem;padding-top:1rem;border-top:1px solid #E2E8F0;
            text-align:center;font-size:0.78rem;color:#94A3B8;">
    Dashboard creado por <strong style="color:#64748B;">Erick Herrera</strong>
</div>
""", unsafe_allow_html=True)