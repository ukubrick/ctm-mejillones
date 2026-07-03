"""
utils/data.py — Loaders cacheados de datos del dashboard.

Cada función usa la capa unificada `fetch` (REST de Supabase si hay credenciales,
si no psycopg2). Las consultas que el SQL hacía en el servidor (DISTINCT ON,
condiciones OR) se replican en pandas cuando se usa la vía REST.
"""
import streamlit as st
import pandas as pd

from utils.db import fetch, rest_enabled


def _ini(s):  # inicio de día
    return f"{s} 00:00:00"


def _fin(e):  # fin de día
    return f"{e} 23:59:59"


@st.cache_data(ttl=300)
def load_real(s, e):
    df = fetch(
        "generacion_real", "unidad,gen_real_mw,fecha_hora,hora,potencia_maxima",
        gte={"fecha_hora": _ini(s)}, lte={"fecha_hora": _fin(e)}, order="fecha_hora",
        sql="SELECT unidad,gen_real_mw,fecha_hora,hora,potencia_maxima FROM generacion_real "
            "WHERE fecha_hora::date BETWEEN %s AND %s ORDER BY unidad,fecha_hora",
        params=(s, e),
    )
    if not df.empty:
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
        df = df.sort_values(["unidad", "fecha_hora"])
    return df


@st.cache_data(ttl=300)
def load_prog(s, e):
    """Programada 'oficial' por unidad/hora: PCP > MANUAL. Excluye el PID
    (intra-día), que se consulta aparte con load_prog_pid para comparar."""
    df = fetch(
        "generacion_programada", "unidad,gen_programada_mw,fecha_hora,hora,fuente",
        gte={"fecha_hora": _ini(s)}, lte={"fecha_hora": _fin(e)},
        sql="""
        SELECT DISTINCT ON (unidad, fecha_hora)
            unidad, gen_programada_mw, fecha_hora, hora, fuente
        FROM generacion_programada
        WHERE fecha_hora::date BETWEEN %s AND %s
          AND fuente <> 'CEN_PID'
        ORDER BY unidad, fecha_hora, CASE fuente WHEN 'CEN_PCP' THEN 0 ELSE 1 END
        """,
        params=(s, e),
    )
    if df.empty:
        return df
    # En la vía REST hay que filtrar el PID y deduplicar priorizando CEN_PCP
    # (lo que el SQL hace con WHERE + DISTINCT ON).
    if rest_enabled():
        df = df[df["fuente"] != "CEN_PID"]
        if df.empty:
            return df
        df["_pri"] = (df["fuente"] != "CEN_PCP").astype(int)
        df = (df.sort_values(["unidad", "fecha_hora", "_pri"])
                .drop_duplicates(["unidad", "fecha_hora"], keep="first")
                .drop(columns="_pri"))
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df


@st.cache_data(ttl=300)
def load_prog_pid(s, e):
    """Generación programada PID (Programa Intra-Día) por unidad/hora.
    Segunda fuente de programación: reajusta el PCP durante el día. Silencioso
    si aún no hay registros PID en la tabla."""
    df = fetch(
        "generacion_programada", "unidad,gen_programada_mw,fecha_hora,hora,fuente",
        eq={"fuente": "CEN_PID"},
        gte={"fecha_hora": _ini(s)}, lte={"fecha_hora": _fin(e)}, order="fecha_hora",
        sql="""
        SELECT unidad, gen_programada_mw, fecha_hora, hora, fuente
        FROM generacion_programada
        WHERE fecha_hora::date BETWEEN %s AND %s AND fuente = 'CEN_PID'
        ORDER BY unidad, fecha_hora
        """,
        params=(s, e),
    )
    if df.empty:
        return df
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df.sort_values(["unidad", "fecha_hora"])


@st.cache_data(ttl=300)
def load_cmg(s, e, nodo="CRUCERO_______220"):
    df = fetch(
        "costo_marginal", "fecha_hora,hora,cmg_usd_mwh",
        eq={"barra_transf": nodo}, gte={"fecha_hora": _ini(s)}, lte={"fecha_hora": _fin(e)}, order="fecha_hora",
        sql="SELECT fecha_hora,hora,cmg_usd_mwh FROM costo_marginal "
            "WHERE barra_transf=%s AND fecha_hora::date BETWEEN %s AND %s ORDER BY fecha_hora",
        params=(nodo, s, e),
    )
    if not df.empty:
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
        df = df.sort_values("fecha_hora")
    return df


@st.cache_data(ttl=300)
def load_cmg_prog(s, e, nodo="CRUCERO_______220"):
    """CMG programado (PID) por barra. Silencioso si la tabla aún no existe."""
    try:
        df = fetch(
            "costo_marginal_programado", "fecha_hora,cmg_usd_mwh",
            eq={"barra": nodo}, gte={"fecha_hora": _ini(s)}, lte={"fecha_hora": _fin(e)}, order="fecha_hora",
            sql="SELECT fecha_hora, cmg_usd_mwh FROM costo_marginal_programado "
                "WHERE barra=%s AND fecha_hora::date BETWEEN %s AND %s ORDER BY fecha_hora",
            params=(nodo, s, e),
        )
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
        df = df.sort_values("fecha_hora")
    return df


@st.cache_data(ttl=300)
def load_sscc(s, e):
    df = fetch(
        "sscc_instrucciones",
        "unidad,instruccion_sscc,fecha,inicio_periodo,fin_periodo,disponibilidad,motivo,comentario,estado_sabana",
        gte={"fecha": s}, lte={"fecha": e},
        sql="SELECT unidad, instruccion_sscc, fecha, inicio_periodo, fin_periodo, "
            "disponibilidad, motivo, comentario, estado_sabana FROM sscc_instrucciones "
            "WHERE fecha BETWEEN %s AND %s ORDER BY fecha DESC, unidad, inicio_periodo",
        params=(s, e),
    )
    if not df.empty:
        df = df.sort_values(["fecha", "unidad", "inicio_periodo"], ascending=[False, True, True])
    return df


@st.cache_data(ttl=300)
def load_limitaciones(s, e):
    cols = ("id,correlativo,instalacion_nombre,status,fecha_perturbacion,fecha_retorno_estimada,"
            "fecha_efectiva_retorno,potencia,unidad_medida_potencia,afecta_sscc,observacion,id_central,id_unidad")
    df = fetch(
        "limitaciones_transmision", cols,
        sql="SELECT " + cols.replace(",", ", ") + " FROM limitaciones_transmision "
            "WHERE fecha_perturbacion::date BETWEEN %s AND %s "
            "   OR (fecha_perturbacion::date < %s AND "
            "       (fecha_efectiva_retorno IS NULL OR fecha_efectiva_retorno::date >= %s)) "
            "ORDER BY fecha_perturbacion DESC",
        params=(s, e, s, s),
    )
    if df.empty:
        return df
    if rest_enabled():
        # Replica del filtro OR del SQL: perturbación en [s,e] o limitación activa durante el período.
        pert = pd.to_datetime(df["fecha_perturbacion"], errors="coerce")
        eff  = pd.to_datetime(df["fecha_efectiva_retorno"], errors="coerce")
        sd, ed = pd.to_datetime(s), pd.to_datetime(e) + pd.Timedelta(days=1)
        en_periodo = (pert >= sd) & (pert < ed)
        activa = (pert < sd) & (eff.isna() | (eff >= sd))
        df = df[en_periodo | activa]
        df = df.sort_values("fecha_perturbacion", ascending=False)
    return df


@st.cache_data(ttl=300)
def load_solicitudes(s, e):
    cols = ("id,correlativo,empresa_nombre,instalacion_nombre,status,tipo_solicitud,type,"
            "tipo_programacion,descripcion_nivel_riesgo,fecha_inicio,fecha_fin,modified")
    df = fetch(
        "solicitudes_trabajo", cols + ",partition_date",
        sql="SELECT " + cols.replace(",", ", ") + " FROM solicitudes_trabajo "
            "WHERE fecha_inicio::date <= %s AND fecha_fin::date >= %s "
            "   OR partition_date::date BETWEEN %s AND %s ORDER BY fecha_inicio DESC",
        params=(e, s, s, e),
    )
    if df.empty:
        return df
    if rest_enabled():
        fi = pd.to_datetime(df["fecha_inicio"], errors="coerce")
        ff = pd.to_datetime(df["fecha_fin"], errors="coerce")
        pd_ = pd.to_datetime(df.get("partition_date"), errors="coerce")
        sd, ed = pd.to_datetime(s), pd.to_datetime(e) + pd.Timedelta(days=1)
        solapa = (fi < ed) & (ff >= sd)
        en_part = (pd_ >= sd) & (pd_ < ed)
        df = df[solapa | en_part].sort_values("fecha_inicio", ascending=False)
        df = df.drop(columns=[c for c in ["partition_date"] if c in df.columns])
    return df


@st.cache_data(ttl=300)
def load_instrucciones_cmg(s, e):
    """Instrucciones operacionales de despacho por CMG (ANG/CCR). Silencioso si la tabla no existe."""
    cols = ("unidad,central,fecha_hora,fecha,hora,despacho,estado,estado_operativo,"
            "consigna,instruccion_cmg,motivo")
    try:
        df = fetch(
            "instrucciones_cmg", cols,
            gte={"fecha": s}, lte={"fecha": e},
            sql="SELECT " + cols.replace(",", ", ") + " FROM instrucciones_cmg "
                "WHERE fecha BETWEEN %s AND %s ORDER BY fecha_hora DESC, unidad",
            params=(s, e),
        )
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df["fecha_hora_dt"] = pd.to_datetime(df["fecha_hora"], errors="coerce")
        df = df.sort_values("fecha_hora_dt", ascending=False)
    return df


@st.cache_data(ttl=300)
def load_cmg_real(s, e, nodo="CRUCERO_______220"):
    """CMG real oficial liquidado por barra. Rezago ~10 días. Silencioso si la tabla no existe."""
    try:
        df = fetch(
            "costo_marginal_real", "fecha_hora,cmg_usd_mwh",
            eq={"barra_transf": nodo}, gte={"fecha_hora": _ini(s)}, lte={"fecha_hora": _fin(e)},
            order="fecha_hora",
            sql="SELECT fecha_hora, cmg_usd_mwh FROM costo_marginal_real "
                "WHERE barra_transf=%s AND fecha_hora::date BETWEEN %s AND %s ORDER BY fecha_hora",
            params=(nodo, s, e),
        )
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
        df = df.sort_values("fecha_hora")
    return df


@st.cache_data(ttl=300)
def load_pronostico_demanda(s, e, barra="Crucero220"):
    """Pronóstico de demanda corto plazo por barra (energia_mwh horaria).
    Silencioso si la tabla no existe."""
    try:
        df = fetch(
            "pronostico_demanda", "fecha_hora,energia_mwh",
            eq={"barra": barra}, gte={"fecha_hora": _ini(s)}, lte={"fecha_hora": _fin(e)},
            order="fecha_hora",
            sql="SELECT fecha_hora, energia_mwh FROM pronostico_demanda "
                "WHERE barra=%s AND fecha_hora::date BETWEEN %s AND %s ORDER BY fecha_hora",
            params=(barra, s, e),
        )
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
        df = df.sort_values("fecha_hora")
    return df


@st.cache_data(ttl=3600)
def load_unidades_maestro():
    """Maestro técnico de las 4 unidades (Pmax bruta/neta, mín técnico, etc.).
    Silencioso si la tabla no existe; config.PMAX/POT_MIN_TECNICA son el fallback."""
    try:
        return fetch(
            "unidades_maestro", "*",
            sql="SELECT * FROM unidades_maestro ORDER BY unidad",
        )
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60)
def load_bit(s, e, u=None):
    eq = {"unidad": u} if (u and u != "Todas") else None
    sql = ("SELECT id,unidad,autor,comentario,fecha,hora FROM bitacora "
           "WHERE fecha BETWEEN %s AND %s" + (" AND unidad=%s" if eq else "") +
           " ORDER BY fecha DESC,hora DESC")
    params = (s, e, u) if eq else (s, e)
    df = fetch("bitacora", "id,unidad,autor,comentario,fecha,hora",
               eq=eq, gte={"fecha": s}, lte={"fecha": e}, sql=sql, params=params)
    if not df.empty:
        df = df.sort_values(["fecha", "hora"], ascending=[False, False])
    return df
