"""
pages/ml_analysis.py — Página ML (wrapper).

La lógica vive en components/ml.py y se muestra también dentro de la vista
«Análisis» de la app principal. Esta página se conserva para acceso directo por URL.
"""
import streamlit as st

from config import get_css
from components.ml import render_ml

st.set_page_config(page_title="ML · CTM Mejillones", layout="wide",
                   page_icon=None, initial_sidebar_state="expanded")
st.markdown(get_css(), unsafe_allow_html=True)

with st.sidebar:
    st.page_link("app.py", label="← Volver al dashboard")

st.markdown(
    '<h1 style="font-size:28px;font-weight:800;color:#1A1F36;margin-bottom:2px">'
    'Análisis Predictivo — CTM Mejillones</h1>', unsafe_allow_html=True)
render_ml()
