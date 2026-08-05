"""Tests del paginado del SIP — integridad del barrido.

Estos tests corren EN SECO (sin red): simulan las respuestas del CEN.

Por qué existen: el SIP intercala páginas VACÍAS de forma no determinista, y el
cuerpo de esa página vacía NO trae `totalPages`. Un barrido que corta en la
primera vacía se queda con un subconjunto ARBITRARIO del día — sin error, sin
fila repetida, sin nada que mirar en el log. Es la clase de fallo que el
proyecto Pulsar sufrió durante días en producción (sus reglas #55/#59/#62) y
que un solo test reproduce en un segundo.

Correr:  python3 -m unittest discover tests -v
         (o `pytest tests/ -q` si está instalado)
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import Adquisicion as A  # noqa: E402


class _RespFake:
    """Imita el objeto Response de requests, solo con .json()."""

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def _pagina(filas, total_pages=None):
    """Body del SIP. Una página VACÍA va SIN `totalPages` — como el real."""
    body = {"data": filas}
    if total_pages is not None:
        body["totalPages"] = total_pages
    return body


def _fake_get(paginas_por_numero):
    """Devuelve un sustituto de _get_with_retry que sirve un dict page -> body.

    Registra en `.pedidas` la secuencia de páginas solicitadas, para poder
    afirmar sobre los reintentos.
    """

    def _get(url, params, timeout=60, max_retries=3):
        page = int(params.get("page") or 1)
        _get.pedidas.append(page)
        return _RespFake(paginas_por_numero.get(page, _pagina([])))

    _get.pedidas = []
    return _get


class TestTotalPages(unittest.TestCase):
    """`totalPages` se RECUERDA a lo largo del barrido."""

    def test_lee_el_valor_del_body(self):
        self.assertEqual(A._total_pages({"totalPages": 5}), 5)

    def test_pagina_vacia_sin_total_pages_conserva_el_previo(self):
        # El caso exacto de la regla #59: preguntarle a la página vacía cuántas
        # páginas hay es preguntarle a la única que no lo sabe.
        self.assertEqual(A._total_pages({"data": []}, previo=11), 11)

    def test_sin_previo_y_sin_campo_devuelve_none(self):
        self.assertIsNone(A._total_pages({"data": []}))

    def test_valor_no_numerico_cae_al_previo(self):
        self.assertEqual(A._total_pages({"totalPages": "?"}, previo=4), 4)


class TestSeguirPeseAVacia(unittest.TestCase):
    """Una página vacía intermedia NO es el fin del feed."""

    def test_sigue_si_quedan_paginas(self):
        self.assertTrue(A._seguir_pese_a_vacia("T", 2, 5))

    def test_corta_en_la_ultima(self):
        self.assertFalse(A._seguir_pese_a_vacia("T", 5, 5))

    def test_corta_si_no_se_conoce_el_total(self):
        # Sin saber cuántas páginas hay, seguir sería un bucle infinito.
        self.assertFalse(A._seguir_pese_a_vacia("T", 2, None))


class TestPedirPagina(unittest.TestCase):
    """La página vacía se RE-pide: saltearla evita truncar, pero pierde sus filas."""

    def test_repide_la_pagina_vacia_y_recupera_las_filas(self):
        # 1er intento vacío, 2º con datos — el hueco del SIP no es determinista.
        intentos = {"n": 0}

        def _get(url, params, timeout=60, max_retries=3):
            intentos["n"] += 1
            if intentos["n"] == 1:
                return _RespFake(_pagina([]))
            return _RespFake(_pagina([{"x": 1}], total_pages=5))

        with patch.object(A, "_get_with_retry", _get), patch.object(A.time, "sleep"):
            data, tp = A._pedir_pagina("u", {"page": 2}, "T", tp_previo=5)

        self.assertEqual(data, [{"x": 1}])
        self.assertEqual(tp, 5)
        self.assertEqual(intentos["n"], 2, "debió re-pedir la página vacía")

    def test_no_repide_la_ultima_pagina(self):
        # La última página del feed puede venir vacía legítimamente.
        get = _fake_get({5: _pagina([])})
        with patch.object(A, "_get_with_retry", get), patch.object(A.time, "sleep"):
            data, tp = A._pedir_pagina("u", {"page": 5}, "T", tp_previo=5)

        self.assertEqual(data, [])
        self.assertEqual(len(get.pedidas), 1, "no debe reintentar la última página")


class TestBarridoCompleto(unittest.TestCase):
    """El test que importa: un día con vacías intercaladas se baja ENTERO."""

    def _barrer(self, paginas_por_numero, total_esperado):
        """Replica el bucle que usan los fetchers 1-indexados de Adquisicion.py."""
        get = _fake_get(paginas_por_numero)
        filas, page, tp_visto, paginas_ok = [], 1, None, 0

        with patch.object(A, "_get_with_retry", get), patch.object(A.time, "sleep"):
            while True:
                data, tp_visto = A._pedir_pagina("u", {"page": page}, "T", tp_visto)
                if not data:
                    if not A._seguir_pese_a_vacia("T", page, tp_visto):
                        break
                    page += 1
                    continue
                paginas_ok += 1
                filas.extend(data)
                if tp_visto is None or page >= tp_visto:
                    break
                page += 1

        return filas, paginas_ok, tp_visto

    def test_vacias_intercaladas_no_truncan_el_dia(self):
        # El escenario medido en Pulsar: 5 páginas, la 2 y la 3 vuelven vacías
        # SIEMPRE (ni el reintento las recupera) y sin `totalPages`.
        paginas = {
            1: _pagina([{"h": 1}], total_pages=5),
            2: _pagina([]),
            3: _pagina([]),
            4: _pagina([{"h": 4}], total_pages=5),
            5: _pagina([{"h": 5}], total_pages=5),
        }
        filas, paginas_ok, tp = self._barrer(paginas, 3)

        # Antes del fix esto devolvía UNA fila: el barrido moría en la página 2.
        self.assertEqual(len(filas), 3, "el barrido cortó antes de la última página")
        self.assertEqual([f["h"] for f in filas], [1, 4, 5])
        self.assertEqual(tp, 5)
        self.assertLess(paginas_ok, tp, "debe quedar registrado como barrido parcial")

    def test_dia_sano_baja_todas_las_paginas(self):
        paginas = {p: _pagina([{"h": p}], total_pages=4) for p in range(1, 5)}
        filas, paginas_ok, tp = self._barrer(paginas, 4)

        self.assertEqual(len(filas), 4)
        self.assertEqual(paginas_ok, 4)
        self.assertEqual(tp, 4)

    def test_una_sola_pagina(self):
        filas, paginas_ok, tp = self._barrer({1: _pagina([{"h": 1}], total_pages=1)}, 1)
        self.assertEqual(len(filas), 1)
        self.assertEqual(paginas_ok, 1)

    def test_feed_vacio_de_verdad_no_cuelga(self):
        # Sin totalPages y sin datos: no hay nada que barrer, debe cortar.
        filas, paginas_ok, tp = self._barrer({}, 0)
        self.assertEqual(filas, [])
        self.assertEqual(paginas_ok, 0)


class TestAvisoParcial(unittest.TestCase):
    """Un barrido corto tiene que DECIRLO — si no, el fallo es invisible."""

    def test_avisa_cuando_faltan_paginas(self):
        with patch.object(A.log, "warning") as w:
            A._avisar_parcial("T", 4, 11)
        self.assertTrue(w.called)
        self.assertIn("PARCIAL", w.call_args[0][0])

    def test_calla_cuando_el_barrido_fue_completo(self):
        with patch.object(A.log, "warning") as w:
            A._avisar_parcial("T", 11, 11)
        self.assertFalse(w.called)

    def test_calla_si_no_se_conoce_el_total(self):
        with patch.object(A.log, "warning") as w:
            A._avisar_parcial("T", 3, None)
        self.assertFalse(w.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
