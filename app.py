"""
app.py — Dashboard Operacional Complejo Térmico Mejillones (AES Andes).

Orquestador modular: la lógica vive en config.py, utils/ y components/.
Navegación de vista única (categoría → vista) para evitar el bug de Plotly
dentro de st.tabs y mantener la interfaz despejada.
"""
import streamlit as st
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
from components.infotecnica import render_infotecnica
from components.estadisticas import render_estadisticas
from components.ml import render_ml

st.set_page_config(
    page_title="Complejo Térmico Mejillones",
    layout="wide",
    page_icon=None,
    initial_sidebar_state="expanded",
)

# Auto-refresh horario: mantiene la app despierta en Streamlit Cloud.
st_autorefresh(interval=3_600_000, limit=None, key="autorefresh_horario")

st.markdown(get_css(), unsafe_allow_html=True)

# ── Navegación plana (4 vistas · principio de simplicidad) ────────────────────
# Se fusionaron las categorías: las sub-secciones viven dentro de cada vista con
# radio-pills internos. Los estadísticos dispersos se consolidaron en «Análisis».
VISTAS = ["Resumen", "Análisis", "Restricciones", "Datos"]


def _navegacion():
    """Barra de navegación plana (segmented control). Devuelve la vista activa."""
    vista = st.session_state.get("vista", VISTAS[0])
    if vista not in VISTAS:
        vista = VISTAS[0]
    st.markdown("<div class='menubar'>", unsafe_allow_html=True)
    vista = st.radio("Navegación", VISTAS, index=VISTAS.index(vista),
                     horizontal=True, label_visibility="collapsed", key="vista")
    st.markdown("</div><div style='height:10px'></div>", unsafe_allow_html=True)
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
        '<h1 style="font-size:30px;font-weight:800;letter-spacing:-0.5px;margin-bottom:2px;'
        'background:linear-gradient(100deg,#22A95B 0%,#1FB6E5 45%,#3D53E8 72%,#7C4DE0 100%);'
        '-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;'
        'display:inline-block">Dashboard Operacional — Complejo Térmico Mejillones</h1>',
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

    elif vista == "Análisis":
        seccion = st.radio("Sección", ["Costos", "Estadísticas", "Predicción (ML)"],
                           horizontal=True, label_visibility="collapsed", key="analisis_sub")
        if seccion == "Costos":
            render_costo(df_r, df_c, s, e, f["nodo_cmg"], df_p)
        elif seccion == "Estadísticas":
            render_estadisticas(df_r, df_p, df_c, s, e)
        else:
            render_ml()

    elif vista == "Restricciones":
        seccion = st.radio("Sección", ["Limitaciones", "SSCC", "Despacho CMG", "Solicitudes"],
                           horizontal=True, label_visibility="collapsed", key="restric_sub")
        if seccion == "Limitaciones":
            render_limitaciones(s, e)
        elif seccion == "SSCC":
            render_sscc(s, e)
        elif seccion == "Despacho CMG":
            render_despacho_cmg(s, e)
        else:
            render_solicitudes(s, e)

    elif vista == "Datos":
        seccion = st.radio("Sección", ["Ingreso Manual", "Datos & Bitácora", "Infotécnica"],
                           horizontal=True, label_visibility="collapsed", key="datos_sub")
        if seccion == "Ingreso Manual":
            render_programada_manual(s, e, hoy)
            render_real_manual(s, e, hoy)
        elif seccion == "Datos & Bitácora":
            render_datos_horarios(df_r, df_c, s)
            render_bitacora(s, e)
        else:
            render_infotecnica()

    st.markdown("""
    <div style="margin-top:3rem;padding-top:1rem;border-top:1px solid #E2E8F0;
                text-align:center;font-size:0.78rem;color:#94A3B8;">
        Dashboard creado por <strong style="color:#64748B;">Erick Herrera</strong> · AES Andes
    </div>
    """, unsafe_allow_html=True)


main()
