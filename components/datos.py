"""components/datos.py — Tabla de datos horarios + bitácora de novedades."""
from datetime import date, datetime

import streamlit as st
import pandas as pd

from config import UNIDADES
from utils.db import write_update, write_delete, write_insert
from utils.data import load_bit


def render_datos_horarios(df_r, df_c, s):
    st.markdown('<div class="sec">Datos horarios</div>', unsafe_allow_html=True)
    if not st.checkbox("Ver tabla completa", value=False):
        return
    df_pv = df_r.pivot_table(index="fecha_hora", columns="unidad", values="gen_real_mw", aggfunc="mean").reset_index()
    if not df_c.empty:
        df_pv = df_pv.merge(df_c[["fecha_hora", "cmg_usd_mwh"]].rename(columns={"cmg_usd_mwh": "CMG (USD/MWh)"}), on="fecha_hora", how="left")
    df_pv["fecha_hora"] = pd.to_datetime(df_pv["fecha_hora"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(df_pv, use_container_width=True, hide_index=True)
    st.download_button("Descargar CSV", df_pv.to_csv(index=False).encode(),
                       f"complejo-termico-mejillones_{s}.csv", "text/csv")


def render_bitacora(s, e):
    st.markdown('<div class="sec">Bitácora de novedades operacionales</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Ver registros", "Nueva novedad"])
    with tab1:
        fu = st.radio("Filtrar", ["Todas"] + UNIDADES, horizontal=True, label_visibility="collapsed")
        df_b = load_bit(s, e, fu)
        if df_b.empty:
            st.info("Sin novedades para el período seleccionado.")
        else:
            d = df_b.copy()
            d["fecha"] = d["fecha"].astype(str)
            d["hora"] = d["hora"].astype(str).str[:5]
            st.dataframe(d.drop(columns=["id"], errors="ignore"), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("**Modificar o eliminar registro:**")
            opc = df_b.apply(lambda r: f"[{r['unidad']}] {str(r['fecha'])} {str(r['hora'])[:5]} — {str(r['comentario'])[:50]}", axis=1).tolist()
            idx = st.selectbox("Seleccionar registro", range(len(opc)), format_func=lambda i: opc[i], key="sel_bit")
            reg = df_b.iloc[idx]
            ce, cd = st.columns([3, 1])
            with ce:
                new_com = st.text_area("Editar comentario:", value=str(reg.get("comentario", "")), height=80, key="edit_com_b")
                if st.button("Actualizar novedad", key="upd_bit"):
                    if write_update("bitacora", {"comentario": new_com.strip()}, int(reg["id"]),
                                    sql="UPDATE bitacora SET comentario=%s WHERE id=%s", params=(new_com.strip(), int(reg["id"]))):
                        st.success("Actualizado."); st.cache_data.clear(); st.rerun()
            with cd:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Eliminar", key="del_bit", type="primary"):
                    if write_delete("bitacora", int(reg["id"]),
                                    sql="DELETE FROM bitacora WHERE id=%s", params=(int(reg["id"]),)):
                        st.success("Eliminado."); st.cache_data.clear(); st.rerun()
    with tab2:
        ub = st.radio("Unidad", UNIDADES, key="ub", horizontal=True)
        b2, b3, b4 = st.columns(3)
        ab = b2.text_input("Autor / Turno", key="ab")
        fb = b3.date_input("Fecha del evento", value=date.today(), key="fb")
        hb = b4.time_input("Hora evento", value=datetime.now().time(), step=60, key="hb")
        cb = st.text_area("Comentario", height=90, placeholder="Descripción de la novedad operacional...", key="cb")
        if st.button("Guardar novedad", type="primary"):
            if ab.strip() and cb.strip():
                if write_insert("bitacora",
                        {"unidad": ub, "autor": ab.strip(), "comentario": cb.strip(), "fecha": str(fb), "hora": str(hb)},
                        sql="INSERT INTO bitacora (unidad,autor,comentario,fecha,hora) VALUES (%s,%s,%s,%s,%s)",
                        params=(ub, ab.strip(), cb.strip(), str(fb), str(hb))):
                    st.success("Novedad guardada."); st.cache_data.clear(); st.rerun()
            else:
                st.warning("Completa autor y comentario.")
