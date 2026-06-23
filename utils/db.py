"""
utils/db.py — Capa de acceso a Supabase.

Doble vía:
  • REST (supabase-py, HTTPS/443) — preferida: funciona en redes que bloquean
    el puerto Postgres (5432/6543). Se activa si hay SUPABASE_URL + SUPABASE_KEY.
  • psycopg2 (Postgres directo) — fallback si no hay credenciales REST.

Las funciones fetch/upsert_rows/update_by_id/delete_by_id eligen la vía
automáticamente, de modo que los loaders y componentes no se enteran de cuál se usa.
"""
import os
import streamlit as st
import psycopg2
import pandas as pd


def _secret(name):
    try:
        v = st.secrets.get(name)
        if v:
            return v
    except Exception:
        pass
    return os.environ.get(name, "")


def rest_enabled() -> bool:
    return bool(_secret("SUPABASE_URL") and _secret("SUPABASE_KEY"))


@st.cache_resource
def get_client():
    """Cliente REST de Supabase (supabase-py)."""
    from supabase import create_client
    return create_client(_secret("SUPABASE_URL"), _secret("SUPABASE_KEY"))


# ── API unificada (REST si está disponible, si no psycopg2) ──────────────────

def fetch(table, columns="*", eq=None, gte=None, lte=None, order=None,
          sql=None, params=None):
    """Devuelve un DataFrame. Vía REST si está habilitada; si no, usa `sql` (psycopg2).

    eq:  dict {col: valor} de igualdades.
    gte/lte: dict {col: valor} de >= / <=.
    order: nombre de columna para ordenar ascendente.
    sql/params: consulta de respaldo para la vía psycopg2.
    """
    if rest_enabled():
        try:
            return _rest_fetch(table, columns, eq, gte, lte, order)
        except Exception as ex:
            st.error(f"Error REST ({table}): {ex}")
            return pd.DataFrame()
    return qry(sql, params) if sql else pd.DataFrame()


def _rest_fetch(table, columns, eq, gte, lte, order):
    sb = get_client()
    rows, start, page = [], 0, 1000
    while True:
        q = sb.table(table).select(columns)
        for c, v in (eq or {}).items():
            q = q.eq(c, v)
        for c, v in (gte or {}).items():
            q = q.gte(c, v)
        for c, v in (lte or {}).items():
            q = q.lte(c, v)
        if order:
            q = q.order(order)
        q = q.range(start, start + page - 1)
        data = q.execute().data or []
        rows.extend(data)
        if len(data) < page:
            break
        start += page
    return pd.DataFrame(rows)


def write_upsert(table, rows, on_conflict, sql=None, params_list=None):
    """Upsert por REST; si no, exe_many con `sql`/`params_list` (psycopg2)."""
    try:
        if rest_enabled():
            get_client().table(table).upsert(rows, on_conflict=on_conflict).execute()
            return True
        return exe_many(sql, params_list)
    except Exception as ex:
        st.error(f"Error guardando: {ex}")
        return False


def write_update(table, values, row_id, sql=None, params=None):
    try:
        if rest_enabled():
            get_client().table(table).update(values).eq("id", row_id).execute()
            return True
        return exe(sql, params)
    except Exception as ex:
        st.error(f"Error actualizando: {ex}")
        return False


def write_delete(table, row_id, sql=None, params=None):
    try:
        if rest_enabled():
            get_client().table(table).delete().eq("id", row_id).execute()
            return True
        return exe(sql, params)
    except Exception as ex:
        st.error(f"Error eliminando: {ex}")
        return False


def write_insert(table, values, sql=None, params=None):
    try:
        if rest_enabled():
            get_client().table(table).insert(values).execute()
            return True
        return exe(sql, params)
    except Exception as ex:
        st.error(f"Error insertando: {ex}")
        return False


@st.cache_resource
def get_conn():
    url = st.secrets.get("DATABASE_URL", "")
    if not url:
        st.error("DATABASE_URL no configurada.")
        st.stop()
    # connect_timeout evita que la app se quede colgada indefinidamente si la DB
    # no responde (red, firewall, host caído): falla rápido con error visible.
    return psycopg2.connect(url, connect_timeout=8)


def last_ts(table, col, eq=None):
    """Última marca temporal (máx) de una columna. REST si está disponible."""
    if rest_enabled():
        try:
            q = get_client().table(table).select(col)
            for k, v in (eq or {}).items():
                q = q.eq(k, v)
            r = q.order(col, desc=True).limit(1).execute()
            return r.data[0][col] if r.data else None
        except Exception:
            return None
    where = ""
    params = None
    if eq:
        k, v = next(iter(eq.items()))
        where = f" WHERE {k}=%s"
        params = (v,)
    df = qry(f"SELECT MAX({col}) AS t FROM {table}{where}", params)
    return df.iloc[0]["t"] if not df.empty else None


def test_conn():
    """Devuelve (ok, error). Vía REST si está disponible; si no, psycopg2."""
    if rest_enabled():
        try:
            get_client().table("generacion_real").select("id").limit(1).execute()
            return True, None
        except Exception as e:
            return False, str(e)
    try:
        conn = get_conn()
        with conn.cursor() as c:
            c.execute("SELECT 1")
        return True, None
    except Exception:
        get_conn.clear()
        try:
            conn = get_conn()
            with conn.cursor() as c:
                c.execute("SELECT 1")
            return True, None
        except Exception as e:
            return False, str(e)


def qry(sql, params=None):
    """SELECT → DataFrame, con reintento ante conexión caída."""
    try:
        return pd.read_sql(sql, get_conn(), params=params)
    except Exception:
        get_conn.clear()
        try:
            return pd.read_sql(sql, get_conn(), params=params)
        except Exception as ex:
            st.error(f"Error DB: {ex}")
            return pd.DataFrame()


def exe(sql, params=None):
    try:
        conn = get_conn()
        with conn.cursor() as c:
            c.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error DB: {e}")
        return False


def exe_many(sql, params_list):
    try:
        conn = get_conn()
        with conn.cursor() as c:
            c.executemany(sql, params_list)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error DB: {e}")
        return False
