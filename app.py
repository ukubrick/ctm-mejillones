"""
app.py — Dashboard Operacional Complejo Térmico Mejillones (AES Andes).

Orquestador modular: la lógica vive en config.py, utils/ y components/.
Navegación de vista única (categoría → vista) para evitar el bug de Plotly
dentro de st.tabs y mantener la interfaz despejada.
"""
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from config import get_css, NOMBRES_NODO
from utils.data import load_real, load_prog, load_cmg, load_limitaciones
from components.sidebar import render_sidebar
from components.kpis import render_kpis
from components.gen_unidad import render_gen_unidad
from components.costo import render_costo
from components.limitaciones import render_limitaciones
from components.sscc import render_sscc
from components.despacho_cmg import render_despacho_cmg
from components.novedades import render_novedades
from components.solicitudes import render_solicitudes
from components.manual import render_programada_manual, render_real_manual
from components.datos import render_datos_horarios, render_bitacora

st.set_page_config(
    page_title="Complejo Térmico Mejillones",
    layout="wide",
    page_icon=None,
    initial_sidebar_state="expanded",
)

# Auto-refresh horario: mantiene la app despierta en Streamlit Cloud.
st_autorefresh(interval=3_600_000, limit=None, key="autorefresh_horario")

st.markdown(get_css(), unsafe_allow_html=True)

# ── Navegación de 2 niveles (categoría → vista) ───────────────────────────────
CATEGORIAS = {
    "Operación":   ["Resumen", "Análisis de Costo"],
    "Restricciones": ["Limitaciones", "SSCC", "Despacho CMG", "Solicitudes"],
    "Gestión de Datos": ["Ingreso Manual", "Datos & Bitácora"],
}
VISTAS = [v for grupo in CATEGORIAS.values() for v in grupo]


def _navegacion():
    """Barra de menú a todo el ancho: cada categoría es un menú desplegable
    (st.popover) que se abre hacia abajo, estilo aplicación de escritorio."""
    vista = st.session_state.get("vista", VISTAS[0])
    if vista not in VISTAS:
        vista = VISTAS[0]

    st.markdown('<div class="menubar">', unsafe_allow_html=True)
    cols = st.columns(len(CATEGORIAS))
    for col, (cat, vistas_cat) in zip(cols, CATEGORIAS.items()):
        with col:
            activa_aqui = vista in vistas_cat
            etiqueta = f"{cat}  ·  {vista}" if activa_aqui else cat
            with st.popover(etiqueta, use_container_width=True):
                for v in vistas_cat:
                    if st.button(v, key=f"nav_{v}", use_container_width=True,
                                 type="primary" if v == vista else "secondary"):
                        st.session_state["vista"] = v
                        st.session_state["_cerrar_popover"] = True
    st.markdown("</div><div style='height:10px'></div>", unsafe_allow_html=True)

    # st.popover (Streamlit 1.58) no se cierra al hacer click en un botón interno.
    # Tras elegir una vista, inyectamos JS que re-clickea el trigger abierto
    # (aria-expanded="true") para cerrarlo — toggle puramente client-side.
    if st.session_state.pop("_cerrar_popover", False):
        components.html(
            "<script>"
            "const d=window.parent.document;"
            "setTimeout(()=>{d.querySelectorAll("
            "'[data-testid=\\'stPopover\\'] button[aria-expanded=\\'true\\']'"
            ").forEach(b=>b.click());},60);"
            "</script>", height=0, width=0)
    return vista


def main():
    f = render_sidebar()
    s, e, hoy = f["s"], f["e"], f["hoy"]

    with st.spinner("Cargando datos..."):
        df_r = load_real(s, e)
        df_p = load_prog(s, e)
        df_c = load_cmg(s, e, f["nodo_cmg"])

    if df_r.empty:
        st.warning("Sin datos para el período seleccionado.")
        st.stop()

    nodo_nombre = NOMBRES_NODO.get(f["nodo_cmg"], "Crucero 220kV")
    st.markdown(
        '<h1 style="font-size:30px;font-weight:800;letter-spacing:-0.5px;color:#1A1F36;margin-bottom:2px">'
        'Dashboard Operacional — Complejo Térmico Mejillones</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="color:#6B7280;font-size:0.85rem;margin-top:-0.3rem">Período {s} → {e} · '
        f'Generación real + Programada PCP + CMG {nodo_nombre}</p>',
        unsafe_allow_html=True,
    )

    render_kpis(df_r, load_limitaciones(s, e))
    st.divider()

    vista = _navegacion()

    if vista == "Resumen":
        render_gen_unidad(df_r, df_p, df_c, f["mostrar_prog"], f["mostrar_cmg"], f["nodo_cmg"], s, e)
        render_novedades(s, e)
    elif vista == "Análisis de Costo":
        render_costo(df_r, df_c, s, e, f["nodo_cmg"], df_p)
    elif vista == "Limitaciones":
        render_limitaciones(s, e)
    elif vista == "SSCC":
        render_sscc(s, e)
    elif vista == "Despacho CMG":
        render_despacho_cmg(s, e)
    elif vista == "Solicitudes":
        render_solicitudes(s, e)
    elif vista == "Ingreso Manual":
        render_programada_manual(s, e, hoy)
        render_real_manual(s, e, hoy)
    elif vista == "Datos & Bitácora":
        render_datos_horarios(df_r, df_c, s)
        render_bitacora(s, e)

    st.markdown("""
    <div style="margin-top:3rem;padding-top:1rem;border-top:1px solid #E2E8F0;
                text-align:center;font-size:0.78rem;color:#94A3B8;">
        Dashboard creado por <strong style="color:#64748B;">Erick Herrera</strong> · AES Andes
    </div>
    """, unsafe_allow_html=True)


main()
