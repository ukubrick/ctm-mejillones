"""Escritura por LOTES (`_upsert_lote`).

Los 17 upserts hacían un `cur.execute` por fila: con ~145 ms de round-trip al
pooler de São Paulo, guardar 754 filas costaba 102 s de puro viaje. El lote lo
baja a una sentencia, pero se lleva por delante dos cosas que el bucle daba
gratis — la deduplicación dentro del lote y el conteo — y son justo las que un
error dejaría en silencio: un duplicado ABORTA el INSERT entero (se perderían
todas las filas del lote, no una) y un conteo mal hecho deja el log mintiendo.

En seco: sin red ni DB.
"""
import re

import pytest

import Adquisicion as A


def _sqls_reales():
    """Los INSERT ... ON CONFLICT tal como están escritos en Adquisicion.py."""
    src = open(A.__file__.replace(".pyc", ".py")).read()
    return [q for q in re.findall(r'sql = """(.*?)"""', src, re.DOTALL)
            if "INSERT INTO" in q and "ON CONFLICT" in q]


class _CursorFalso:
    def __init__(self):
        self.ejecutados = []      # (sql, filas) por llamada a execute_values
        self.otros = []

    def execute(self, sql, params=None):
        self.otros.append(sql)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _ConnFalsa:
    def __init__(self, cur):
        self._cur, self.commits = cur, 0

    def cursor(self):
        return self._cur

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def db(monkeypatch):
    cur = _CursorFalso()
    conn = _ConnFalsa(cur)
    monkeypatch.setattr(A, "get_conn", lambda: conn)

    def _ev(c, sql, filas, template=None, page_size=None, fetch=False):
        c.ejecutados.append((sql, list(filas)))
        # Simula el RETURNING (xmax = 0): inserta las filas con `nueva` verdadero.
        return [(bool(f.get("nueva", True)),) for f in filas]

    monkeypatch.setattr(A, "execute_values", _ev)
    return cur, conn


SQL = """
    INSERT INTO t (a, b, c)
    VALUES (%(a)s, %(b)s, %(c)s)
    ON CONFLICT (a, b) DO UPDATE SET c = EXCLUDED.c
"""


def test_los_17_sql_reales_se_parten_bien():
    """Si `_partir_sql` fallara en uno, ese upsert dejaría de escribir en silencio."""
    sqls = _sqls_reales()
    assert len(sqls) == 17, f"cambió la cantidad de upserts: {len(sqls)}"
    for q in sqls:
        prefijo, plantilla, resto = A._partir_sql(q)
        tabla = re.search(r"INSERT INTO (\w+)", q).group(1)
        assert prefijo.rstrip().endswith("VALUES %s"), tabla
        assert resto.strip().upper().startswith("ON CONFLICT"), tabla
        # Un placeholder por columna declarada: si no cuadran, psycopg2 revienta
        # recién en producción.
        cols = prefijo[prefijo.index("(") + 1:prefijo.index(")")].count(",") + 1
        assert plantilla.count("%(") == cols, tabla
        assert A._RE_ON_CONFLICT.search(q), tabla


def test_una_sentencia_por_lote_no_una_por_fila(db):
    cur, conn = db
    filas = [{"a": i, "b": 1, "c": i} for i in range(120)]
    assert A._upsert_lote(SQL, filas, "prueba") == (120, 0)
    assert len(cur.ejecutados) == 1          # ← el punto de todo el cambio
    assert conn.commits == 1


def test_lote_grande_se_parte_en_paginas(db):
    cur, _ = db
    filas = [{"a": i, "b": 1, "c": 0} for i in range(1200)]
    A._upsert_lote(SQL, filas, "prueba")
    assert [len(f) for _, f in cur.ejecutados] == [500, 500, 200]


def test_dedup_dentro_del_lote(db):
    """Postgres aborta el INSERT completo si la clave se repite en el mismo lote."""
    cur, _ = db
    filas = [{"a": 1, "b": 1, "c": "vieja"},
             {"a": 1, "b": 1, "c": "nueva"},
             {"a": 2, "b": 1, "c": "otra"}]
    insertadas, existentes = A._upsert_lote(SQL, filas, "prueba")
    enviadas = cur.ejecutados[0][1]
    assert len(enviadas) == 2
    # Gana la ÚLTIMA, igual que cuando el bucle fila-a-fila la pisaba.
    assert [f["c"] for f in enviadas if f["a"] == 1] == ["nueva"]
    assert (insertadas, existentes) == (2, 0)


def test_cuenta_insertadas_contra_ya_existentes(db):
    """`rowcount == 1` no distinguía INSERT de UPDATE: todo salía como «nuevo»."""
    filas = [{"a": 1, "b": 1, "c": 0, "nueva": True},
             {"a": 2, "b": 1, "c": 0, "nueva": False},
             {"a": 3, "b": 1, "c": 0, "nueva": False}]
    assert A._upsert_lote(SQL, filas, "prueba") == (1, 2)


def test_filas_no_devueltas_cuentan_como_existentes(db, monkeypatch):
    """El WHERE del DO UPDATE (p.ej. una fila `origen='MANUAL'`) hace que esa fila
    no vuelva en el RETURNING: no se insertó, y no puede contarse como tal."""
    # Se mandan 3 filas y el servidor solo devuelve 1 (las otras 2 las frenó el
    # WHERE): la cuenta tiene que salir 1 insertada / 2 ya existentes.
    monkeypatch.setattr(A, "execute_values",
                        lambda c, s, f, **kw: [(True,)])
    filas = [{"a": i, "b": 1, "c": 0} for i in range(3)]
    assert A._upsert_lote(SQL, filas, "prueba") == (1, 2)


def test_pre_se_ejecuta_antes_del_lote(db):
    """`_ensure_origen_col` debe correr dentro de la misma transacción."""
    cur, _ = db
    llamadas = []
    A._upsert_lote(SQL, [{"a": 1, "b": 1, "c": 0}], "prueba",
                   pre=lambda c: llamadas.append(c))
    assert llamadas == [cur]


def test_lista_vacia_no_abre_conexion(monkeypatch):
    def _boom():
        raise AssertionError("no debe conectarse con 0 registros")
    monkeypatch.setattr(A, "get_conn", _boom)
    assert A._upsert_lote(SQL, [], "prueba") == (0, 0)


def test_error_de_db_no_propaga_y_devuelve_cero(monkeypatch):
    """Un fallo de escritura se loguea y lo contabiliza ResumenCorrida (regla 56),
    pero no debe tumbar los pasos siguientes de la corrida."""
    def _boom():
        raise RuntimeError("pooler caído")
    monkeypatch.setattr(A, "get_conn", _boom)
    assert A._upsert_lote(SQL, [{"a": 1, "b": 1, "c": 0}], "prueba") == (0, 0)
