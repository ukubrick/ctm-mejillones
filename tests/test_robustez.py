"""Tests del bloque de robustez de la adquisición (en seco, sin red).

Cubren tres fallos que ya ocurrieron en producción en este proyecto o en Pulsar:

- Un job que atrapa las excepciones y sale `exit 0` queda VERDE sin haber
  adquirido nada. Es peor que un fallo rojo: oculta la caída. (~19 h de datos
  perdidos sin que nadie lo notara.)
- `SSLError` hereda de `ConnectionError`, así que el `except` genérico le aplica
  backoff a un certificado vencido — un problema que jamás se arregla esperando.
- Las excepciones de `requests` traen la URL con la `user_key` en claro, y este
  repo es PÚBLICO.

Correr:  python3 -m unittest discover tests -v
"""

import os
import sys
import unittest
from unittest.mock import patch

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import Adquisicion as A  # noqa: E402


class TestResumenCorrida(unittest.TestCase):
    """El código de salida tiene que reflejar si se adquirió algo."""

    def test_todo_ok_sale_verde(self):
        r = A.ResumenCorrida("X")
        r.paso_ok("a")
        r.paso_ok("b")
        self.assertEqual(r.cerrar(), 0)

    def test_ningun_paso_ok_sale_rojo(self):
        # El caso que importa: la corrida no adquirió NADA.
        r = A.ResumenCorrida("X")
        r.paso_fallo("a", "boom")
        r.paso_fallo("b", "boom")
        self.assertEqual(r.cerrar(), 1, "una corrida sin datos debe salir en rojo")

    def test_fallo_parcial_sale_verde_pero_avisa(self):
        # Decisión deliberada: un rojo frecuente entrena a ignorar el monitor.
        r = A.ResumenCorrida("X")
        r.paso_ok("a")
        r.paso_fallo("b", "boom")
        with patch.object(A.log, "warning") as w:
            code = r.cerrar()
        self.assertEqual(code, 0)
        self.assertTrue(w.called, "un fallo parcial debe gritar en el log")

    def test_corrida_vacia_sale_verde(self):
        # Sin pasos y sin fallos no hay nada que reportar (p. ej. la diaria
        # cuando el CEN no publicó días nuevos de desempeño).
        self.assertEqual(A.ResumenCorrida("X").cerrar(), 0)

    def test_el_fallo_se_guarda_redactado(self):
        r = A.ResumenCorrida("X")
        r.paso_fallo("a", "GET https://api.cen.cl/x?user_key=SECRETO123 falló")
        self.assertNotIn("SECRETO123", r.fallos[0][1])


class TestRedactar(unittest.TestCase):
    """La user_key nunca puede llegar a un log — el repo es público."""

    def test_quita_la_key_de_una_url(self):
        s = A._redactar("https://api.cen.cl/v4?user_key=abc123XYZ&page=1")
        self.assertNotIn("abc123XYZ", s)
        self.assertIn("user_key=***", s)
        self.assertIn("page=1", s, "no debe destruir el resto del mensaje")

    def test_es_no_op_sin_key(self):
        self.assertEqual(A._redactar("timeout de conexión"), "timeout de conexión")

    def test_acepta_una_excepcion(self):
        e = requests.ConnectionError("falló https://x?user_key=SECRETO")
        self.assertNotIn("SECRETO", A._redactar(e))


class TestGetWithRetry(unittest.TestCase):

    def test_sslerror_no_se_reintenta(self):
        """Un certificado vencido no se arregla esperando."""
        llamadas = {"n": 0}

        def _get(url, params=None, timeout=None):
            llamadas["n"] += 1
            raise requests.exceptions.SSLError("cert expirado")

        with patch.object(A._SESSION, "get", _get), patch.object(A.time, "sleep"):
            with self.assertRaises(requests.exceptions.SSLError):
                A._get_with_retry("u", {}, max_retries=3)

        self.assertEqual(llamadas["n"], 1, "SSLError no debe consumir reintentos")

    def test_429_se_reintenta_y_luego_pasa(self):
        class _R:
            def __init__(self, code):
                self.status_code = code
                self.headers = {}

            def raise_for_status(self):
                pass

        respuestas = [_R(429), _R(200)]

        def _get(url, params=None, timeout=None):
            return respuestas.pop(0)

        with patch.object(A._SESSION, "get", _get), patch.object(A.time, "sleep"):
            r = A._get_with_retry("u", {}, max_retries=3)

        self.assertEqual(r.status_code, 200)

    def test_respeta_el_header_retry_after(self):
        class _R:
            def __init__(self, code, headers=None):
                self.status_code = code
                self.headers = headers or {}

            def raise_for_status(self):
                pass

        respuestas = [_R(429, {"Retry-After": "7"}), _R(200)]
        esperas = []

        with patch.object(A._SESSION, "get", lambda *a, **k: respuestas.pop(0)), \
             patch.object(A.time, "sleep", lambda s: esperas.append(s)):
            A._get_with_retry("u", {}, max_retries=3)

        self.assertIn(7.0, esperas, "debe usar el Retry-After del servidor")


class TestPreflight(unittest.TestCase):
    """Sondear antes de gastar el runner contra un host caído."""

    def test_ok_cuando_la_api_responde(self):
        class _R:
            status_code = 200

        with patch.object(A, "CEN_USER_KEY", "k"), \
             patch.object(A._SESSION, "get", lambda *a, **k: _R()):
            vivo, motivo = A.preflight_cen()
        self.assertTrue(vivo)

    def test_un_4xx_cuenta_como_viva(self):
        # Responde: el problema es del endpoint puntual, no del host.
        class _R:
            status_code = 404

        with patch.object(A, "CEN_USER_KEY", "k"), \
             patch.object(A._SESSION, "get", lambda *a, **k: _R()):
            vivo, _ = A.preflight_cen()
        self.assertTrue(vivo)

    def test_5xx_es_caida(self):
        class _R:
            status_code = 503

        with patch.object(A, "CEN_USER_KEY", "k"), \
             patch.object(A._SESSION, "get", lambda *a, **k: _R()):
            vivo, motivo = A.preflight_cen()
        self.assertFalse(vivo)
        self.assertIn("503", motivo)

    def test_ssl_vencido_es_caida_y_no_filtra_la_key(self):
        def _boom(*a, **k):
            raise requests.exceptions.SSLError("cert https://x?user_key=SECRETO")

        with patch.object(A, "CEN_USER_KEY", "k"), \
             patch.object(A._SESSION, "get", _boom):
            vivo, motivo = A.preflight_cen()
        self.assertFalse(vivo)
        self.assertNotIn("SECRETO", motivo)

    def test_sin_key_no_intenta_la_red(self):
        with patch.object(A, "CEN_USER_KEY", ""):
            vivo, motivo = A.preflight_cen()
        self.assertFalse(vivo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
