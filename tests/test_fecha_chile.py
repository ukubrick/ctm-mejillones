"""La fecha de las vistas es la de CHILE, no la del servidor.

Streamlit Cloud corre en UTC. Desde las 20:00 hora de Chile (21:00 en invierno)
`date.today()` ya devuelve el día siguiente, así que todo lo que se derive de
ahí queda corrido un día justo en el horario de mayor uso de la tarde.

El sintoma real (04-08-2026, 21:25 Chile): el selector de la bitácora marcaba
«04-08-2026 · ayer» cuando el 04-08 era HOY, y la tabla salía vacía — todos los
movimientos del día anterior desaparecían de golpe, sin ningún error. El
sidebar, en paralelo, proponía un «Hasta» en el futuro.

Correr:  python3 -m unittest discover tests -v
"""

import os
import sys
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.plotly_theme import TZ_CHILE, hoy_chile  # noqa: E402


class TestHoyChile(unittest.TestCase):

    def test_devuelve_un_date(self):
        self.assertIsInstance(hoy_chile(), date)

    def test_coincide_con_la_fecha_de_santiago(self):
        self.assertEqual(hoy_chile(), datetime.now(TZ_CHILE).date())

    def test_de_noche_difiere_de_la_fecha_utc(self):
        """El caso que rompía: entre las 20:00 de Chile y la medianoche UTC,
        la fecha del servidor va UN DÍA ADELANTE de la de Chile."""
        utc = datetime.now(ZoneInfo("UTC"))
        chile = utc.astimezone(TZ_CHILE)
        if utc.date() == chile.date():
            self.skipTest("ahora mismo UTC y Chile caen en el mismo día")
        # Estamos en la franja del bug: el helper debe seguir a Chile.
        self.assertEqual(hoy_chile(), chile.date())
        self.assertNotEqual(hoy_chile(), utc.date())

    def test_la_franja_del_bug_existe(self):
        """Verifica la premisa con un instante FIJO, sin depender de la hora
        a la que corran los tests: 04-08-2026 21:25 en Chile es el 05-08 en UTC."""
        instante = datetime(2026, 8, 5, 1, 25, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(instante.date(), date(2026, 8, 5))
        self.assertEqual(instante.astimezone(TZ_CHILE).date(), date(2026, 8, 4))


class TestSinDateToday(unittest.TestCase):
    """Ningún componente debe volver a usar `date.today()` para la fecha actual.

    Es un test de PATRÓN, no de comportamiento: la clase de bug reaparece cada
    vez que alguien escribe el atajo, y revisarlo a mano depende de acordarse.
    """

    # `datos.py` está exento: ahí `date.today()` es el valor POR DEFECTO de un
    # campo de formulario que el usuario edita a mano, no una fecha de cálculo.
    # `plotly_theme.py` es donde vive `hoy_chile()`, y su docstring NOMBRA el
    # atajo prohibido para explicar por qué no se usa.
    EXENTOS = {"datos.py", "plotly_theme.py"}

    def test_ningun_componente_usa_date_today(self):
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        infractores = []
        for carpeta in ("components", "utils"):
            d = os.path.join(raiz, carpeta)
            for nombre in sorted(os.listdir(d)):
                if not nombre.endswith(".py") or nombre in self.EXENTOS:
                    continue
                with open(os.path.join(d, nombre), encoding="utf-8") as fh:
                    for i, linea in enumerate(fh, 1):
                        codigo = linea.split("#")[0]
                        if "date.today()" in codigo:
                            infractores.append(f"{carpeta}/{nombre}:{i}")
        self.assertEqual(
            infractores, [],
            "usar hoy_chile() de utils.plotly_theme en vez de date.today(): "
            + ", ".join(infractores))


if __name__ == "__main__":
    unittest.main(verbosity=2)
