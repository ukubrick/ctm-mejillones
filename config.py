"""
config.py — Constantes, paleta y CSS del Dashboard CTM Mejillones.

Centraliza todo lo compartido entre app.py y los módulos de components/.
El monolito original tenía estas constantes y el CSS incrustados; aquí viven
en un solo lugar para mantener consistencia visual.
"""

# ── Paleta corporativa AES Andes ──────────────────────────────────────────────
# Espectro de marca (logo infinito/espiral): verde → teal → cyan → azul → violeta.
# Todo el dashboard usa degradados con estas 5 anclas.
AES_VERDE    = "#22A95B"   # verde AES (inicio del espectro)
AES_TEAL     = "#12B2A0"   # teal / esmeralda
AES_CYAN     = "#1FB6E5"   # cyan
AES_AZUL     = "#3D53E8"   # azul AES (color de acción principal)
AES_AZUL_OSC = "#2A38C9"
AES_VIOLETA  = "#7C4DE0"   # violeta (fin del espectro)
AES_VIOLETA_OSC = "#5B2FB0"
AES_AMBAR    = "#F59E0B"
AES_ROJO     = "#EF4444"
AES_GRIS     = "#F5F7FA"
AES_TEXTO    = "#1A1F36"
AES_MUTED    = "#6B7280"
AES_BORDE    = "#E5E7EB"
AES_BLANCO   = "#FFFFFF"

# Degradado corporativo completo (verde→teal→cyan→azul→violeta) — usado en
# barras de acento, KPI border-top, títulos y botones destacados.
AES_GRAD      = ("linear-gradient(120deg,#22A95B 0%,#12B2A0 26%,"
                 "#1FB6E5 52%,#3D53E8 76%,#7C4DE0 100%)")
# Degradado de acción (azul→violeta) para botones/tabs activos.
AES_GRAD_BTN  = "linear-gradient(135deg,#3D53E8 0%,#6A3FCC 100%)"

# ── Unidades ────────────────────────────────────────────────────────────────
UNIDADES = ["ANG1", "ANG2", "CCR1", "CCR2"]

# Color por unidad — mapeadas sobre el espectro AES (violeta→azul→cyan→verde)
# para que las 4 unidades "hablen" la paleta corporativa.
COLORES = {
    "ANG1": {"line": "#7C4DE0", "prog": "#C9B5F2", "badge": "#EDE7FC", "text": "#6A3FCC"},  # violeta
    "ANG2": {"line": "#3D53E8", "prog": "#AEB8F5", "badge": "#E2E7FD", "text": "#2A38C9"},  # azul
    "CCR1": {"line": "#1FB6E5", "prog": "#A6E4F6", "badge": "#DBF3FC", "text": "#1391BC"},  # cyan
    "CCR2": {"line": "#22A95B", "prog": "#A4E0BC", "badge": "#DCF5E7", "text": "#1B8B4A"},  # verde
    "CMG":  {"line": "#7C4DE0"},
}
LABELS = {"ANG1": "Angamos U1", "ANG2": "Angamos U2", "CCR1": "Cochrane U1", "CCR2": "Cochrane U2"}

# Colores ESTÁNDAR de las series de tiempo — fijos, no cambian con la unidad.
# Paleta sobria y jerárquica: una sola "línea protagonista" (Real, azul profundo,
# sólida y gruesa); el resto en tonos secundarios/atenuados y con trazo discontinuo
# para que se lean como referencias y no compitan visualmente.
# Jerarquía visual: la Real es la ÚNICA línea protagonista (azul profundo, sólida,
# con área). "Programado / planificado" habla un solo lenguaje cromático: ámbar-oro
# discontinuo (PID intra-día, prominente) y gris pizarra punteado (PCP día-ante,
# recesivo). El CMG repite el patrón: violeta sólido = real, ámbar-oro = programado.
# Paleta validada con el skill dataviz (separación CVD ΔE>80, contraste ~2.9:1 en
# líneas con leyenda + hover + guion como codificación secundaria).
SERIE = {
    "real":     "#2A38C9",            # azul AES profundo — línea protagonista (gen. real)
    "prog":     "#94A3B8",            # gris pizarra, dotted — PCP (día-ante), recesivo
    "prog_pid": "#C98500",            # ámbar-oro, dashed — PID (intra-día), referencia operativa
    "cmg":      "#7C4DE0",            # violeta AES — CMG real
    "cmg_fill": "rgba(124,77,224,0.08)",
    "cmg_prog": "#C98500",            # ámbar-oro, dashed — CMG programado (mismo lenguaje "plan")
    "demanda":  "#64748B",            # gris pizarra, dotted — demanda pronosticada
    "over":     "rgba(12,163,12,0.14)",   # sobregeneración (real > programa)
    "under":    "rgba(208,59,59,0.14)",   # subgeneración  (real < programa)
    "minimo":   "#CBD5E1",            # línea de mínimo técnico
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

# ── Infotécnica (fallback estático; la tabla unidades_maestro tiene prioridad) ──
# Fuente: /unidades-generadoras/v4 (SIP) sondeado 2026-07-03 + PMAX declaradas.
INFOTECNICA = {
    "ANG1": {"propietario": "Empresa Eléctrica Angamos SpA", "tecnologia": "Termoeléctrica TV (carbón)",
             "punto_conexion": "S/E Angamos 220 kV", "pot_max_bruta": 277.99, "pot_neta_efectiva": 252.2,
             "pot_min_tecnica": 60.0, "min_tec_ctrl_frec": 87.0, "tension_nominal": 18.0},
    "ANG2": {"propietario": "Empresa Eléctrica Angamos SpA", "tecnologia": "Termoeléctrica TV (carbón)",
             "punto_conexion": "S/E Angamos 220 kV", "pot_max_bruta": 280.0, "pot_neta_efectiva": None,
             "pot_min_tecnica": 60.0, "min_tec_ctrl_frec": None, "tension_nominal": 18.0},
    "CCR1": {"propietario": "Empresa Eléctrica Cochrane SpA", "tecnologia": "Termoeléctrica TV (carbón)",
             "punto_conexion": "S/E Cochrane 220 kV", "pot_max_bruta": 276.0, "pot_neta_efectiva": None,
             "pot_min_tecnica": 60.0, "min_tec_ctrl_frec": None, "tension_nominal": None},
    "CCR2": {"propietario": "Empresa Eléctrica Cochrane SpA", "tecnologia": "Termoeléctrica TV (carbón)",
             "punto_conexion": "S/E Cochrane 220 kV", "pot_max_bruta": 276.0, "pot_neta_efectiva": None,
             "pot_min_tecnica": 60.0, "min_tec_ctrl_frec": None, "tension_nominal": None},
}

# Fondo y grilla de los gráficos Plotly
BG = "#F5F7FA"
GR = "#E5E7EB"
BG_TRANSP = "rgba(0,0,0,0)"   # fondo transparente (gráficos de estadísticas)
C_GRID    = "#E2E8F0"         # grilla clara
C_MUTED   = "#94A3B8"         # ticks / anotaciones atenuadas
C_TEXTO   = "#0F172A"         # títulos de gráfico

# Sidebar — degradado corporativo AES (teal→azul→violeta) con anclas oscuras
# para mantener el texto blanco legible.
SIDEBAR_GRAD = "linear-gradient(168deg,#0E7E93 0%,#2A38C9 52%,#4A25A0 100%)"

# Nodo CMG (barra_transf) → barra del pronóstico de demanda
CMG_A_DEMANDA = {
    "CRUCERO_______220": "Crucero220",
    "TARAPACA______220": "Tarapaca220",
}


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

/* ── Sidebar (gradiente púrpura AES/CTM) ──────────────────────────────── */
[data-testid="stSidebar"] {{
  background:{SIDEBAR_GRAD}!important;
  box-shadow:4px 0 20px rgba(0,0,0,0.25)!important;
  border-right:none!important;
}}
[data-testid="stSidebar"] * {{ color:#E2E8F0!important; }}
[data-testid="stSidebar"] hr {{ border-color:rgba(255,255,255,0.12)!important; }}
[data-testid="stSidebar"] .stCheckbox label {{ color:#DDD6FE!important; }}
[data-testid="stSidebar"] .stDateInput label,
[data-testid="stSidebar"] .stRadio label {{ color:#C4B5FD!important; font-size:0.75rem!important; }}
[data-testid="stSidebar"] input {{ background:rgba(255,255,255,0.07)!important; color:#E2E8F0!important; border-color:rgba(255,255,255,0.15)!important; }}
/* Filtros de fecha: caja blanca con texto oscuro y en negrita para legibilidad */
[data-testid="stSidebar"] [data-testid="stDateInput"] div[data-baseweb="input"] {{ background:#FFFFFF!important; border-radius:8px!important; }}
[data-testid="stSidebar"] [data-testid="stDateInput"] input {{ background:#FFFFFF!important; color:#0F172A!important; font-weight:700!important; -webkit-text-fill-color:#0F172A!important; }}
[data-testid="stSidebar"] [data-testid="stDateInput"] svg {{ fill:#475569!important; }}
[data-testid="stSidebar"] .stButton>button {{
  width:100%!important; background:rgba(255,255,255,0.08)!important;
  border:1px solid rgba(255,255,255,0.16)!important;
  border-radius:9px!important; color:#F1F5F9!important; font-weight:600!important;
  justify-content:center!important; text-align:center!important; min-height:40px!important;
  transition:all 0.18s cubic-bezier(0.4,0,0.2,1)!important;
}}
[data-testid="stSidebar"] .stButton>button:hover {{
  background:rgba(255,255,255,0.18)!important; border-color:rgba(255,255,255,0.5)!important;
  transform:translateY(-1px)!important; box-shadow:0 4px 14px rgba(0,0,0,0.22)!important;
}}
[data-testid="stSidebar"] [data-baseweb="select"]>div {{ color:#E2E8F0!important; background:rgba(255,255,255,0.07)!important; }}
/* Botón de descarga (export) también a ancho completo y centrado */
[data-testid="stSidebar"] [data-testid="stDownloadButton"]>button {{
  width:100%!important; justify-content:center!important;
}}
.status-box {{
  background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.14);
  border-radius:10px; padding:0.7rem 0.9rem; margin-top:0.5rem; font-size:0.72rem;
}}

/* ── Radio del sidebar como segmented control (nodo CMG) ──────────────── */
[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] {{
  display:flex; gap:5px; background:rgba(255,255,255,0.08);
  border:1px solid rgba(255,255,255,0.14); border-radius:10px; padding:4px;
}}
[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"] {{
  flex:1; margin:0; padding:6px 10px; border-radius:7px; justify-content:center;
  cursor:pointer; transition:all 0.18s ease;
}}
[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {{ display:none; }}
[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"] p {{
  font-size:12px!important; font-weight:600!important; color:rgba(255,255,255,0.7)!important; text-align:center;
}}
[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {{
  background:rgba(255,255,255,0.95);
}}
[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p {{
  color:{AES_AZUL_OSC}!important; font-weight:700!important;
}}

/* ── KPI nativos (st.metric) ──────────────────────────────────────────── */
/* Borde superior con degradado corporativo AES (padding-box/border-box trick). */
[data-testid="stMetric"] {{
  background:linear-gradient({AES_BLANCO},{AES_BLANCO}) padding-box, {AES_GRAD} border-box;
  border:1px solid transparent; border-top-width:4px;
  border-radius:12px; padding:1rem 1.2rem;
  box-shadow:0 2px 12px rgba(61,83,232,0.08);
  transition:transform 0.2s ease, box-shadow 0.2s ease; animation:fadeInUp 0.5s ease both;
}}
[data-testid="stMetric"]:hover {{ transform:translateY(-3px); box-shadow:0 8px 24px rgba(61,83,232,0.16); }}
[data-testid="stMetricLabel"] p {{ font-size:0.72rem!important; color:var(--muted)!important; font-weight:700!important; text-transform:uppercase; letter-spacing:0.06em; }}
[data-testid="stMetricValue"] {{ font-size:1.7rem!important; font-weight:800!important; color:var(--txt)!important; }}

/* ── KPI cards personalizadas (por unidad) ────────────────────────────── */
.kpi {{
  background:{AES_BLANCO}; border:1px solid var(--bord); border-radius:12px; padding:1.2rem 1.4rem;
  box-shadow:0 2px 12px rgba(59,76,232,0.08);
  transition:transform 0.2s ease, box-shadow 0.2s ease; animation:fadeInUp 0.5s ease both;
}}
.kpi:hover {{ transform:translateY(-3px); box-shadow:0 8px 24px rgba(59,76,232,0.15); }}
/* Delays escalonados (patrón Pulsar): las cards entran en cascada */
[data-testid="stColumn"]:nth-child(1) .kpi, [data-testid="stColumn"]:nth-child(1) [data-testid="stMetric"] {{ animation-delay:0s; }}
[data-testid="stColumn"]:nth-child(2) .kpi, [data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] {{ animation-delay:0.06s; }}
[data-testid="stColumn"]:nth-child(3) .kpi, [data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] {{ animation-delay:0.12s; }}
[data-testid="stColumn"]:nth-child(4) .kpi, [data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] {{ animation-delay:0.18s; }}
.kpi-badge {{ display:inline-block; font-size:0.65rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; padding:3px 10px; border-radius:20px; margin-bottom:0.7rem; }}
.kpi-val {{ font-size:2rem; font-weight:800; color:var(--txt); line-height:1; }}
.kpi-mw {{ font-size:1rem; font-weight:400; color:var(--muted); }}
.kpi-sub {{ font-size:0.75rem; color:var(--muted); margin-top:0.4rem; }}
.kpi-delta {{ font-size:0.78rem; margin-top:0.5rem; font-weight:600; }}

/* ── Títulos de sección (subrayado con degradado AES) ─────────────────── */
.sec {{
  font-size:0.82rem; font-weight:800; letter-spacing:0.12em; text-transform:uppercase;
  color:#334155; padding-bottom:0.5rem; margin:1.8rem 0 1rem; position:relative;
  border-bottom:none;
}}
.sec::after {{
  content:""; position:absolute; left:0; bottom:0; height:3px; width:100%;
  background:{AES_GRAD}; border-radius:2px; opacity:0.9;
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
  background:{AES_GRAD_BTN}; color:white;
  border:1px solid {AES_AZUL_OSC}; box-shadow:0 4px 12px rgba(61,83,232,0.28);
}}

/* ── Tabs (cyan) ──────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{ gap:6px; background:{AES_BLANCO}; border-bottom:3px solid {AES_CYAN}; border-radius:8px 8px 0 0; box-shadow:0 2px 8px rgba(0,0,0,0.05); }}
.stTabs [data-baseweb="tab"] {{ border-radius:8px 8px 0 0; font-weight:500; font-size:13px; color:var(--muted); padding:9px 24px!important; transition:all 0.2s cubic-bezier(0.4,0,0.2,1); }}
.stTabs [aria-selected="true"][data-baseweb="tab"] {{ background:linear-gradient(135deg,{AES_TEAL} 0%,{AES_CYAN} 100%)!important; color:#FFFFFF!important; font-weight:700!important; box-shadow:0 -2px 10px rgba(31,182,229,0.35)!important; }}
.stTabs [data-baseweb="tab-panel"] [data-testid="stPlotlyChart"],
.stTabs [data-baseweb="tab-panel"] .js-plotly-plot {{ width:100%!important; min-width:0!important; }}

/* ── Sub-navegación (st.radio del área principal como segmented control) ──
   Portado de Pulsar (estilos.py): sin círculo de radio, opción activa con
   gradiente AES. Solo aplica al área principal, no al sidebar. */
.block-container div[data-testid="stRadio"] [role="radiogroup"] {{
  display:inline-flex; flex-wrap:wrap; gap:6px; background:{AES_BLANCO};
  border:1px solid {AES_BORDE}; border-radius:12px; padding:5px;
  box-shadow:0 2px 8px rgba(0,0,0,0.05);
}}
.block-container div[data-testid="stRadio"] label[data-baseweb="radio"] {{
  margin:0; padding:8px 18px; border-radius:8px; border:1px solid transparent;
  cursor:pointer; transition:all 0.18s cubic-bezier(0.4,0,0.2,1);
}}
.block-container div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {{ display:none; }}
.block-container div[data-testid="stRadio"] label[data-baseweb="radio"] p {{
  font-size:13px; font-weight:600; color:{AES_MUTED}; transition:color 0.18s ease;
}}
.block-container div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {{ background:rgba(59,76,232,0.06); }}
.block-container div[data-testid="stRadio"] label[data-baseweb="radio"]:hover p {{ color:{AES_AZUL}; }}
.block-container div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {{
  background:{AES_GRAD_BTN};
  border-color:{AES_AZUL_OSC}; box-shadow:0 3px 10px rgba(61,83,232,0.30);
}}
.block-container div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p {{ color:#FFFFFF; }}

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
