"""components/manual.py — Ingreso manual de respaldo: programada y generación real."""
from datetime import datetime

import streamlit as st
import pandas as pd

from config import LABELS, UNIDADES
from utils.db import write_upsert, write_update, write_delete, fetch
from utils.data import load_prog, load_real

_SQL_UP_PROG = """INSERT INTO generacion_programada (unidad,gen_programada_mw,fecha_hora,hora,fuente)
    VALUES (%s,%s,%s,%s,%s)
    ON CONFLICT (unidad,fecha_hora,fuente) DO UPDATE SET gen_programada_mw=EXCLUDED.gen_programada_mw"""
# Marca origen='MANUAL' → la adquisición automática NO sobreescribe estas horas
# (ver guard en Adquisicion.upsert_generacion_real). El ingreso manual prevalece.
_SQL_UP_REAL = """INSERT INTO generacion_real (unidad, gen_real_mw, fecha_hora, hora, origen)
    VALUES (%s, %s, %s, %s, 'MANUAL')
    ON CONFLICT (unidad, fecha_hora) DO UPDATE SET gen_real_mw=EXCLUDED.gen_real_mw, origen='MANUAL'"""


def render_programada_manual(s, e, hoy):
    st.markdown('<div class="sec">POTENCIA PROGRAMADA · CEN PCP + INGRESO MANUAL</div>', unsafe_allow_html=True)
    st.info("Los datos de programación se importan automáticamente desde la API CEN (PCP) cada hora. "
            "El ingreso manual **tiene prioridad**: si cargas un valor manual para una unidad/hora, "
            "ese valor prevalece sobre el PCP y no lo pisa la adquisición automática.")

    tab1, tab2 = st.tabs(["Por hora", "24 horas de una vez"])
    with tab1:
        u = st.radio("Unidad", UNIDADES, key="up", horizontal=True)
        c2, c3, c4 = st.columns(3)
        f = c2.date_input("Fecha", value=hoy, max_value=hoy, key="fp")
        h = c3.number_input("Hora (1-24)", 1, 24, datetime.now().hour + 1, key="hp")
        mw = c4.number_input("MW programados", 0.0, 400.0, step=0.5, key="mwp")
        if st.button("Guardar hora", key="btn_h"):
            fh = f"{f} {int(h)-1:02d}:00:00"
            ok = write_upsert("generacion_programada",
                [{"unidad": u, "gen_programada_mw": mw, "fecha_hora": fh, "hora": int(h), "fuente": "MANUAL"}],
                "unidad,fecha_hora,fuente", sql=_SQL_UP_PROG, params_list=[(u, mw, fh, int(h), "MANUAL")])
            if ok:
                st.success(f"Guardado: {LABELS[u]} H{h} → {mw} MW"); st.cache_data.clear(); st.rerun()

    with tab2:
        st.caption("Selecciona unidad y fecha, luego pega los 24 valores MW separados por salto de línea (hora 1 → hora 24).")
        u = st.radio("Unidad", UNIDADES, key="um", horizontal=True)
        c1, c2 = st.columns([1, 2])
        f = c1.date_input("Fecha", value=hoy, max_value=hoy, key="fm")
        c1.caption("Ejemplo formato:\n280.5\n275.3\n271.0\n...")
        mw_masa = c2.text_area("24 valores MW (uno por línea):", height=220, key="mwm", placeholder="280.5\n275.3\n271.0\n...")
        if st.button("Guardar las 24 horas", key="btn_m"):
            try:
                valores = [float(v.strip().replace(",", ".")) for v in mw_masa.strip().split("\n") if v.strip()]
                if len(valores) != 24:
                    st.error(f"Se esperan 24 valores, se ingresaron {len(valores)}.")
                else:
                    rows = [{"unidad": u, "gen_programada_mw": mw, "fecha_hora": f"{f} {hh-1:02d}:00:00", "hora": hh, "fuente": "MANUAL"}
                            for hh, mw in enumerate(valores, 1)]
                    params = [(u, mw, f"{f} {hh-1:02d}:00:00", hh, "MANUAL") for hh, mw in enumerate(valores, 1)]
                    if write_upsert("generacion_programada", rows, "unidad,fecha_hora,fuente", sql=_SQL_UP_PROG, params_list=params):
                        st.success(f"24 horas guardadas: {LABELS[u]} · {f}"); st.cache_data.clear(); st.rerun()
            except ValueError:
                st.error("Formato inválido. Solo números, uno por línea.")

    df = load_prog(s, e)
    if df.empty:
        return
    if st.checkbox("Ver tabla de datos programados", value=False, key="show_prog_tbl"):
        d = df.copy()
        d["fecha_hora"] = pd.to_datetime(d["fecha_hora"]).dt.strftime("%Y-%m-%d %H:%M")
        cols = ["unidad", "fecha_hora", "hora", "gen_programada_mw", "fuente"] if "fuente" in d.columns else ["unidad", "fecha_hora", "hora", "gen_programada_mw"]
        st.dataframe(d[cols].rename(columns={"gen_programada_mw": "MW Programado", "fuente": "Fuente"}), use_container_width=True, hide_index=True)

    _crud_manual(s, e, tabla="generacion_programada", campo="gen_programada_mw", solo_manual=True, key="prog")


def render_real_manual(s, e, hoy):
    st.markdown('<div class="sec">GENERACIÓN REAL · INGRESO MANUAL DE RESPALDO</div>', unsafe_allow_html=True)
    st.info("Los datos de generación real se importan automáticamente desde la API CEN (SIPUB) cada hora. "
            "El ingreso manual **tiene prioridad**: la hora que cargues queda marcada como MANUAL y "
            "la adquisición automática ya no la sobreescribe (útil para reemplazos/correcciones forzadas). "
            "Para volver al valor automático, elimina el registro manual abajo.")

    tab1, tab2 = st.tabs(["Por hora", "24 horas de una vez"])
    with tab1:
        u = st.radio("Unidad", UNIDADES, key="ur", horizontal=True)
        c2, c3, c4 = st.columns(3)
        f = c2.date_input("Fecha", value=hoy, max_value=hoy, key="fr")
        h = c3.number_input("Hora (1-24)", 1, 24, datetime.now().hour + 1, key="hr")
        mw = c4.number_input("MW reales", 0.0, 400.0, step=0.5, key="mwr")
        if st.button("Guardar hora real", key="btn_hr"):
            fh = f"{f} {int(h)-1:02d}:00:00"
            ok = write_upsert("generacion_real",
                [{"unidad": u, "gen_real_mw": mw, "fecha_hora": fh, "hora": int(h), "origen": "MANUAL"}],
                "unidad,fecha_hora", sql=_SQL_UP_REAL, params_list=[(u, mw, fh, int(h))])
            if ok:
                st.success(f"Guardado: {LABELS[u]} H{h} → {mw} MW"); st.cache_data.clear(); st.rerun()

    with tab2:
        st.caption("Selecciona unidad y fecha, luego pega los 24 valores MW separados por salto de línea (hora 1 → hora 24).")
        u = st.radio("Unidad", UNIDADES, key="urm", horizontal=True)
        c1, c2 = st.columns([1, 2])
        f = c1.date_input("Fecha", value=hoy, max_value=hoy, key="frm")
        c1.caption("Ejemplo formato:\n280.5\n275.3\n271.0\n...")
        mw_masa = c2.text_area("24 valores MW (uno por línea):", height=220, key="mwrm", placeholder="280.5\n275.3\n271.0\n...")
        if st.button("Guardar las 24 horas reales", key="btn_rm"):
            try:
                valores = [float(v.strip().replace(",", ".")) for v in mw_masa.strip().split("\n") if v.strip()]
                if len(valores) != 24:
                    st.error(f"Se esperan 24 valores, se ingresaron {len(valores)}.")
                else:
                    rows = [{"unidad": u, "gen_real_mw": mw, "fecha_hora": f"{f} {hh-1:02d}:00:00", "hora": hh, "origen": "MANUAL"}
                            for hh, mw in enumerate(valores, 1)]
                    params = [(u, mw, f"{f} {hh-1:02d}:00:00", hh) for hh, mw in enumerate(valores, 1)]
                    if write_upsert("generacion_real", rows, "unidad,fecha_hora", sql=_SQL_UP_REAL, params_list=params):
                        st.success(f"24 horas guardadas: {LABELS[u]} · {f}"); st.cache_data.clear(); st.rerun()
            except ValueError:
                st.error("Formato inválido. Solo números, uno por línea.")

    df = load_real(s, e)
    if df.empty:
        return
    if st.checkbox("Ver tabla de datos reales", value=False, key="show_real_tbl"):
        d = df.copy()
        d["fecha_hora"] = pd.to_datetime(d["fecha_hora"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(d[["unidad", "fecha_hora", "hora", "gen_real_mw"]].rename(columns={"gen_real_mw": "MW Real"}), use_container_width=True, hide_index=True)

    _crud_manual(s, e, tabla="generacion_real", campo="gen_real_mw", solo_manual=False, key="real")


def _crud_manual(s, e, tabla, campo, solo_manual, key):
    """CRUD compartido: editar/eliminar un registro por id."""
    st.markdown("---")
    st.markdown(f"**Modificar o eliminar registro {'programada' if solo_manual else 'real'}:**")
    eq = {"fuente": "MANUAL"} if solo_manual else None
    sql = (f"SELECT id,unidad,{campo},fecha_hora,hora FROM {tabla} "
           f"WHERE fecha_hora::date BETWEEN %s AND %s" + (" AND fuente='MANUAL'" if solo_manual else "") +
           " ORDER BY unidad,fecha_hora")
    crud = fetch(tabla, f"id,unidad,{campo},fecha_hora,hora", eq=eq,
                 gte={"fecha_hora": f"{s} 00:00:00"}, lte={"fecha_hora": f"{e} 23:59:59"},
                 sql=sql, params=(s, e))
    if crud.empty:
        return
    crud = crud.copy()
    crud["fecha_hora"] = pd.to_datetime(crud["fecha_hora"])
    crud = crud.sort_values(["unidad", "fecha_hora"])
    opc = crud.apply(lambda r: f"[{r['unidad']}] {r['fecha_hora'].strftime('%d/%m %H:%M')} — {r[campo]:.1f} MW", axis=1).tolist()
    idx = st.selectbox(f"Seleccionar registro {key}", range(len(opc)), format_func=lambda i: opc[i], key=f"sel_{key}")
    reg = crud.iloc[idx]
    ce, cd = st.columns([2, 1])
    with ce:
        new_mw = st.number_input("Nuevo valor MW:", value=float(reg[campo]), min_value=0.0, max_value=400.0, step=0.5, key=f"edit_mw_{key}")
        if st.button("Actualizar MW", key=f"upd_{key}"):
            if write_update(tabla, {campo: new_mw}, int(reg["id"]),
                            sql=f"UPDATE {tabla} SET {campo}=%s WHERE id=%s", params=(new_mw, int(reg["id"]))):
                st.success("Actualizado."); st.cache_data.clear(); st.rerun()
    with cd:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Eliminar", key=f"del_{key}", type="primary"):
            if write_delete(tabla, int(reg["id"]),
                            sql=f"DELETE FROM {tabla} WHERE id=%s", params=(int(reg["id"]),)):
                st.success("Eliminado."); st.cache_data.clear(); st.rerun()
