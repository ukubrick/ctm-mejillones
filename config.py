"""
config.py — Constantes, paleta y CSS del Dashboard CTM Mejillones.

Centraliza todo lo compartido entre app.py y los módulos de components/.
El monolito original tenía estas constantes y el CSS incrustados; aquí viven
en un solo lugar para mantener consistencia visual.
"""

# ── Paleta AES ────────────────────────────────────────────────────────────────
AES_AZUL     = "#3B4CE8"
AES_AZUL_OSC = "#2530B0"
AES_CYAN     = "#4DC8DC"
AES_VIOLETA  = "#9B6FD4"
AES_VERDE    = "#5AB848"
AES_AMBAR    = "#F59E0B"
AES_ROJO     = "#EF4444"
AES_GRIS     = "#F5F7FA"
AES_TEXTO    = "#1A1F36"
AES_MUTED    = "#6B7280"
AES_BORDE    = "#E5E7EB"
AES_BLANCO   = "#FFFFFF"

# ── Unidades ────────────────────────────────────────────────────────────────
UNIDADES = ["ANG1", "ANG2", "CCR1", "CCR2"]

# Color por unidad (línea principal, programada clara, badge, texto)
COLORES = {
    "ANG1": {"line": "#6D28D9", "prog": "#C4B5FD", "badge": "#EDE9FE", "text": "#6D28D9"},
    "ANG2": {"line": "#2563EB", "prog": "#93C5FD", "badge": "#DBEAFE", "text": "#2563EB"},
    "CCR1": {"line": "#0891B2", "prog": "#67E8F9", "badge": "#CFFAFE", "text": "#0891B2"},
    "CCR2": {"line": "#16A34A", "prog": "#86EFAC", "badge": "#DCFCE7", "text": "#16A34A"},
    "CMG":  {"line": "#6D28D9"},
}
LABELS = {"ANG1": "Angamos U1", "ANG2": "Angamos U2", "CCR1": "Cochrane U1", "CCR2": "Cochrane U2"}

# Colores ESTÁNDAR de las series de tiempo — fijos, no cambian con la unidad.
# Evita el choque visual con las áreas verde/roja de desviación.
SERIE = {
    "real":     "#1E293B",            # gris azulado oscuro (generación real)
    "prog":     "#475569",            # gris pizarra oscuro, punteado (programada PCP)
    "prog_pid": "#0EA5E9",            # cyan, punteado (programada PID intra-día)
    "cmg":      "#7C3AED",            # violeta (CMG real)
    "cmg_fill": "rgba(124,58,237,0.10)",
    "cmg_prog": "#F59E0B",            # ámbar, punteado (CMG programado)
    "over":     "rgba(22,163,74,0.25)",   # sobregeneración (real > prog)
    "under":    "rgba(239,68,68,0.25)",   # subgeneración  (real < prog)
    "minimo":   "#94A3B8",            # línea de mínimo técnico
}

# Potencias máximas declaradas ante el CEN (MW)
PMAX = {"ANG1": 277.0, "ANG2": 280.0, "CCR1": 276.0, "CCR2": 276.0}

# Mínimo técnico declarado ante el CEN (MW) — fuente: /unidades-generadoras/v4
# Por debajo de este valor la unidad no puede operar de forma estable.
POT_MIN_TECNICA = {"ANG1": 60.0, "ANG2": 60.0, "CCR1": 60.0, "CCR2": 60.0}

# Nodos CMG disponibles en el S3 del CEN
NOMBRES_NODO = {
    "CRUCERO_______220": "Crucero 220kV",
    "TARAPACA______220": "Tarapacá 220kV",
}

# Mapeo id_unidad / id_central de la API CEN
ID_UNIDAD_LABEL  = {1965: "ANG1", 1966: "ANG2", 1967: "CCR1", 1968: "CCR2"}
ID_CENTRAL_LABEL = {377: "Angamos", 379: "Cochrane"}

# ── Limitaciones de transmisión ────────────────────────────────────────────
STATUS_COLOR_LIM = {
    "pendiente":  ("#D97706", "#FEF3C7"),
    "finalizado": ("#16A34A", "#DCFCE7"),
    "anulado":    ("#94A3B8", "#F1F5F9"),
}

# ── Servicios complementarios (SSCC) ────────────────────────────────────────
COLORES_SSCC = {
    "CSF(+)": "#16A34A", "CSF(-)": "#0891B2",
    "CPF(+)": "#6D28D9", "CPF(-)": "#D97706",
    "CT":     "#CA8A04", "CTF":    "#DC2626",
}
BADGE_SSCC = {
    "CSF(+)": "#DCFCE7", "CSF(-)": "#CFFAFE",
    "CPF(+)": "#EDE9FE", "CPF(-)": "#FEF3C7",
    "CT":     "#FEF9C3", "CTF":    "#FEE2E2",
}

# ── Solicitudes de trabajo ──────────────────────────────────────────────────
STATUS_COLOR_SOL = {
    "pendiente":         ("#D97706", "#FEF3C7"),
    "ejecucion_exitosa": ("#16A34A", "#DCFCE7"),
    "anulado":           ("#94A3B8", "#F1F5F9"),
    "borrador":          ("#6366F1", "#EEF2FF"),
}
TIPO_LABEL = {"desconexion": "Desconexión", "intervencion": "Intervención"}
TYPE_LABEL = {"central_generadora": "Central", "subestacion": "Subestación", "linea": "Línea"}

# Fondo y grilla de los gráficos Plotly
BG = "#F5F7FA"
GR = "#E5E7EB"


def get_css() -> str:
    """Devuelve el bloque <style> global del dashboard.

    Diseño AES alineado al dashboard ERNC. A diferencia del monolito anterior,
    NO se fuerza el sidebar (transform/width) ni se ocultan los botones de
    colapso: Streamlit gestiona el colapso/expansión de forma nativa.
    """
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {{
  --bg:{AES_GRIS}; --surf:{AES_BLANCO}; --surf2:#F8FAFC; --bord:{AES_BORDE};
  --txt:{AES_TEXTO}; --muted:{AES_MUTED};
  --aes-azul:{AES_AZUL}; --aes-azul-osc:{AES_AZUL_OSC}; --aes-cyan:{AES_CYAN};
  --aes-violeta:{AES_VIOLETA}; --aes-verde:{AES_VERDE}; --aes-ambar:{AES_AMBAR}; --aes-rojo:{AES_ROJO};
}}

/* ── Animaciones ──────────────────────────────────────────────────────── */
@keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:.3}} }}
@keyframes fadeInUp {{ from{{opacity:0;transform:translateY(16px)}} to{{opacity:1;transform:translateY(0)}} }}
@keyframes fadeInLeft {{ from{{opacity:0;transform:translateX(-12px)}} to{{opacity:1;transform:translateX(0)}} }}
@keyframes pulse-pend {{ 0%,100%{{box-shadow:0 0 0 0 rgba(217,119,6,0.7)}} 70%{{box-shadow:0 0 0 6px rgba(217,119,6,0)}} }}
@keyframes pulse-sscc {{ 0%,100%{{box-shadow:0 0 0 0 rgba(100,116,139,0.5)}} 70%{{box-shadow:0 0 0 5px rgba(100,116,139,0)}} }}
@keyframes pulse-green {{ 0%{{box-shadow:0 0 0 0 rgba(90,184,72,0.7)}} 70%{{box-shadow:0 0 0 7px rgba(90,184,72,0)}} 100%{{box-shadow:0 0 0 0 rgba(90,184,72,0)}} }}

/* ── Base ─────────────────────────────────────────────────────────────── */
html, body, .stApp {{ font-family:'Inter',sans-serif; background:var(--bg); color:var(--txt); }}
.block-container {{ padding:1.4rem 2rem 3rem; max-width:1400px; animation:fadeInUp 0.5s ease both; }}
h1,h2,h3 {{ font-family:'Inter',sans-serif!important; color:var(--txt)!important; }}
p,span,div,label {{ font-family:'Inter',sans-serif; }}

/* Limpieza mínima — solo menú hamburguesa. El toolbar se conserva para que
   el botón de expandir el sidebar siga funcionando tras colapsarlo. */
#MainMenu {{ visibility:hidden; }}
[data-testid="InputInstructions"] {{ display:none!important; }}

/* ── Sidebar (gradiente cyan AES) ─────────────────────────────────────── */
[data-testid="stSidebar"] {{
  background:linear-gradient(160deg,#0e6e7e 0%,#074f5c 55%,#043840 100%)!important;
  box-shadow:4px 0 20px rgba(0,0,0,0.25)!important;
  border-right:none!important;
}}
[data-testid="stSidebar"] * {{ color:#E2E8F0!important; }}
[data-testid="stSidebar"] hr {{ border-color:rgba(255,255,255,0.12)!important; }}
[data-testid="stSidebar"] .stCheckbox label {{ color:#CBD5E1!important; }}
[data-testid="stSidebar"] .stDateInput label,
[data-testid="stSidebar"] .stRadio label {{ color:#94A3B8!important; font-size:0.75rem!important; }}
[data-testid="stSidebar"] input {{ background:rgba(255,255,255,0.07)!important; color:#E2E8F0!important; border-color:rgba(255,255,255,0.15)!important; }}
/* Filtros de fecha: caja blanca con texto oscuro y en negrita para legibilidad */
[data-testid="stSidebar"] [data-testid="stDateInput"] div[data-baseweb="input"] {{ background:#FFFFFF!important; border-radius:8px!important; }}
[data-testid="stSidebar"] [data-testid="stDateInput"] input {{ background:#FFFFFF!important; color:#0F172A!important; font-weight:700!important; -webkit-text-fill-color:#0F172A!important; }}
[data-testid="stSidebar"] [data-testid="stDateInput"] svg {{ fill:#475569!important; }}
[data-testid="stSidebar"] .stButton>button {{
  background:rgba(255,255,255,0.06)!important; border:1px solid rgba(255,255,255,0.12)!important;
  border-radius:8px!important; color:#E2E8F0!important; font-weight:500!important;
  transition:all 0.2s cubic-bezier(0.4,0,0.2,1)!important;
}}
[data-testid="stSidebar"] .stButton>button:hover {{
  background:rgba(77,200,220,0.22)!important; border-color:{AES_CYAN}!important; transform:translateX(3px)!important;
}}
[data-testid="stSidebar"] [data-baseweb="select"]>div {{ color:#E2E8F0!important; background:rgba(255,255,255,0.07)!important; }}
.status-box {{
  background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.12);
  border-radius:8px; padding:0.6rem 0.8rem; margin-top:0.5rem; font-size:0.72rem;
}}

/* ── KPI nativos (st.metric) ──────────────────────────────────────────── */
[data-testid="stMetric"] {{
  background:{AES_BLANCO}; border:1px solid var(--bord); border-top:4px solid {AES_AZUL};
  border-radius:12px; padding:1rem 1.2rem;
  box-shadow:0 2px 12px rgba(59,76,232,0.08);
  transition:transform 0.2s ease, box-shadow 0.2s ease; animation:fadeInUp 0.5s ease both;
}}
[data-testid="stMetric"]:hover {{ transform:translateY(-3px); box-shadow:0 8px 24px rgba(59,76,232,0.15); }}
[data-testid="stMetricLabel"] p {{ font-size:0.72rem!important; color:var(--muted)!important; font-weight:700!important; text-transform:uppercase; letter-spacing:0.06em; }}
[data-testid="stMetricValue"] {{ font-size:1.7rem!important; font-weight:800!important; color:var(--txt)!important; }}

/* ── KPI cards personalizadas (por unidad) ────────────────────────────── */
.kpi {{
  background:{AES_BLANCO}; border:1px solid var(--bord); border-radius:12px; padding:1.2rem 1.4rem;
  box-shadow:0 2px 12px rgba(59,76,232,0.08);
  transition:transform 0.2s ease, box-shadow 0.2s ease; animation:fadeInUp 0.5s ease both;
}}
.kpi:hover {{ transform:translateY(-3px); box-shadow:0 8px 24px rgba(59,76,232,0.15); }}
.kpi-badge {{ display:inline-block; font-size:0.65rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; padding:3px 10px; border-radius:20px; margin-bottom:0.7rem; }}
.kpi-val {{ font-size:2rem; font-weight:800; color:var(--txt); line-height:1; }}
.kpi-mw {{ font-size:1rem; font-weight:400; color:var(--muted); }}
.kpi-sub {{ font-size:0.75rem; color:var(--muted); margin-top:0.4rem; }}
.kpi-delta {{ font-size:0.78rem; margin-top:0.5rem; font-weight:600; }}

/* ── Títulos de sección ───────────────────────────────────────────────── */
.sec {{
  font-size:0.82rem; font-weight:800; letter-spacing:0.12em; text-transform:uppercase;
  color:#334155; border-bottom:2px solid var(--bord); padding-bottom:0.45rem; margin:1.8rem 0 1rem;
}}

/* ── Dots de estado ───────────────────────────────────────────────────── */
.dot-status {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; vertical-align:middle; }}
.dot-g {{ background:{AES_VERDE}; box-shadow:0 0 5px rgba(90,184,72,0.6); animation:blink 2s infinite; }}
.dot-r {{ background:{AES_ROJO}; }}
.dot-y {{ background:{AES_AMBAR}; animation:blink 2s infinite; }}
.badge-pend {{ display:inline-block; animation:pulse-pend 1.8s infinite; border-radius:4px; }}
.alarm-trip {{
  background:#FEF2F2; border:1.5px solid #FECACA; border-left:5px solid {AES_ROJO};
  color:#991B1B; border-radius:10px; padding:0.7rem 1rem; margin-bottom:1rem;
  font-size:0.86rem; animation:fadeInUp 0.4s ease both;
}}
.sscc-latest {{ animation:pulse-sscc 2.2s infinite; }}

/* ── Barra de menú (popovers a todo el ancho, estilo escritorio) ──────── */
.menubar {{ margin-bottom:2px; }}
[data-testid="stPopover"] > div > button {{
  width:100%; background:linear-gradient(180deg,#FFFFFF 0%,#F3F5FF 100%)!important;
  border:1.6px solid #C7CDF5!important; border-radius:10px!important;
  min-height:48px!important; font-weight:700!important; font-size:14px!important;
  color:{AES_AZUL_OSC}!important; justify-content:center!important;
  transition:all 0.2s cubic-bezier(0.4,0,0.2,1)!important;
}}
[data-testid="stPopover"] > div > button:hover {{
  border-color:{AES_AZUL}!important; box-shadow:0 4px 16px rgba(59,76,232,0.2)!important; transform:translateY(-1px);
}}
[data-testid="stPopover"] > div > button[aria-expanded="true"] {{
  background:linear-gradient(135deg,{AES_AZUL} 0%,{AES_AZUL_OSC} 100%)!important; color:#fff!important; border-color:{AES_AZUL_OSC}!important;
}}

/* ── Navegación de vista única (botones tipo tab) ─────────────────────── */
.block-container div[data-baseweb="select"]>div {{
  border-radius:10px; border:1.6px solid #C7CDF5;
  background:linear-gradient(180deg,#FFFFFF 0%,#F3F5FF 100%);
  min-height:46px; font-weight:700; font-size:14px; color:{AES_AZUL_OSC};
  transition:all 0.2s cubic-bezier(0.4,0,0.2,1);
}}
.block-container div[data-baseweb="select"]:hover>div {{ border-color:{AES_AZUL}; box-shadow:0 4px 16px rgba(59,76,232,0.2); transform:translateY(-1px); }}
.block-container div[data-baseweb="select"] svg {{ fill:{AES_AZUL}; }}
.block-container .stButton button {{
  font-size:13px; font-weight:600; padding:11px 14px; min-height:46px; line-height:1.2;
  white-space:normal; border-radius:10px; transition:all 0.18s cubic-bezier(0.4,0,0.2,1);
}}
.block-container .stButton button[kind="secondary"] {{ background:{AES_BLANCO}; color:{AES_MUTED}; border:1px solid var(--bord); }}
.block-container .stButton button[kind="secondary"]:hover {{ background:rgba(59,76,232,0.06); color:{AES_AZUL}; border-color:{AES_AZUL}; }}
.block-container .stButton button[kind="primary"] {{
  background:linear-gradient(135deg,{AES_AZUL} 0%,{AES_AZUL_OSC} 100%); color:white;
  border:1px solid {AES_AZUL_OSC}; box-shadow:0 4px 12px rgba(59,76,232,0.28);
}}

/* ── Tabs (cyan) ──────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{ gap:6px; background:{AES_BLANCO}; border-bottom:3px solid {AES_CYAN}; border-radius:8px 8px 0 0; box-shadow:0 2px 8px rgba(0,0,0,0.05); }}
.stTabs [data-baseweb="tab"] {{ border-radius:8px 8px 0 0; font-weight:500; font-size:13px; color:var(--muted); padding:9px 24px!important; transition:all 0.2s cubic-bezier(0.4,0,0.2,1); }}
.stTabs [aria-selected="true"][data-baseweb="tab"] {{ background:linear-gradient(135deg,{AES_CYAN} 0%,#2ba8be 100%)!important; color:{AES_TEXTO}!important; font-weight:700!important; box-shadow:0 -2px 10px rgba(77,200,220,0.35)!important; }}
.stTabs [data-baseweb="tab-panel"] [data-testid="stPlotlyChart"],
.stTabs [data-baseweb="tab-panel"] .js-plotly-plot {{ width:100%!important; min-width:0!important; }}

/* ── Gráficos Plotly ──────────────────────────────────────────────────── */
[data-testid="stPlotlyChart"] {{ border-radius:12px; overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,0.06); animation:fadeInUp 0.5s ease both; transition:box-shadow 0.2s ease; }}
[data-testid="stPlotlyChart"]:hover {{ box-shadow:0 6px 20px rgba(59,76,232,0.12); }}

/* ── Inputs / selects (área principal) ────────────────────────────────── */
.stTextInput>div>div>input,.stTextArea>div>div>textarea,.stNumberInput>div>div>input {{ background:var(--surf2)!important; border:1px solid var(--bord)!important; border-radius:8px!important; color:var(--txt)!important; }}
[data-baseweb="popover"] [role="option"] {{ color:#0F172A!important; background:#fff!important; }}
[data-baseweb="popover"] [role="option"]:hover {{ background:#EFF6FF!important; }}
[data-baseweb="popover"] [aria-selected="true"] {{ background:#DBEAFE!important; }}

/* ── Cards genéricas ──────────────────────────────────────────────────── */
.aes-card {{ background:{AES_BLANCO}; border-radius:12px; padding:18px 22px; border:1px solid var(--bord); box-shadow:0 2px 10px rgba(0,0,0,0.06); margin-bottom:14px; animation:fadeInUp 0.4s ease both; }}
</style>
"""
