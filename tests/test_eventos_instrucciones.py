"""Cierre de la limitación declarada en la instrucción de despacho (regla 50).

En seco: sin red ni DB. Reproduce la secuencia real de ANG1 (02/08 → 04/08):
SICF → días en LF a 87/60 MW → prueba de subida a PC citando la misma SICF →
«Cancela SICF». Con la lógica anterior la ventana quedaba ABIERTA porque la
instrucción de cancelación cita el código y caía dentro del propio bloque.
"""
import unittest
import pandas as pd

from utils.eventos import eventos_desde_instrucciones


def _fila(fh, desp, estado, motivo):
    return {"id_instruccion": fh + motivo, "unidad": "ANG1", "central": "ANGAMOS",
            "fecha_hora": fh, "despacho": desp, "estado": estado, "motivo": motivo,
            "consigna": "", "instruccion_cmg": "", "zona_desaclope": "",
            "control_tension": ""}


SECUENCIA = pd.DataFrame([
    _fila("2026-08-02 22:30:00", 87.0, "RO", ""),
    _fila("2026-08-02 23:13:00", 87.0, "LF", "Según SICFXXXXXX"),
    _fila("2026-08-02 23:13:00", 87.0, "LF", "Según SICF2026087731"),
    _fila("2026-08-03 19:00:00", 87.0, "LF", ""),
    _fila("2026-08-04 00:00:00", 60.0, "LF",
          "Limitada en 60 MW, Revisión y reparación de atomizador por falla, "
          "según SICF 2026087731"),
    _fila("2026-08-04 17:23:00", 87.0, "PO", "Sube a PC, según SICF 2026087731"),
    _fila("2026-08-04 18:23:00", 87.0, "PO",
          "A PC e inicia hora de prueba, según SICF 2026087731"),
    _fila("2026-08-04 20:27:00", 87.0, "RO", "Cancela SICF 2026087731"),
])
REF = pd.Timestamp("2026-08-05 09:00:00")


class TestCierreSICF(unittest.TestCase):

    def _ev(self, df=SECUENCIA, ref=REF):
        ev = eventos_desde_instrucciones(df, ref=ref)
        self.assertEqual(len(ev), 1, ev.to_string())
        return ev.iloc[0]

    def test_cierra_con_la_cancelacion(self):
        e = self._ev()
        self.assertEqual(e["ini"], pd.Timestamp("2026-08-02 23:13:00"))
        self.assertEqual(e["fin"], pd.Timestamp("2026-08-04 20:27:00"))
        self.assertEqual(e["estado"], "cerrada")

    def test_la_prueba_no_cierra_ni_se_pierde(self):
        """La subida a PC citando la misma SICF es parte de la intervención."""
        e = self._ev()
        self.assertIn("hora de prueba", e["detalle"])
        self.assertGreater(e["fin"], pd.Timestamp("2026-08-04 18:23:00"))

    def test_sin_cancelacion_la_ventana_sigue_abierta(self):
        e = self._ev(SECUENCIA.iloc[:-1], ref=REF)
        self.assertEqual(e["estado"], "activa")
        self.assertIn("sigue vigente", e["detalle"])

    def test_relimitacion_posterior_abre_evento_nuevo(self):
        df = pd.concat([SECUENCIA, pd.DataFrame([
            _fila("2026-08-05 02:00:00", 60.0, "LF", "Según SICF 2026090001")])])
        ev = eventos_desde_instrucciones(df, ref=REF)
        self.assertEqual(len(ev), 2, ev.to_string())
        nueva = ev[ev["titulo"].str.contains("2026090001")].iloc[0]
        self.assertEqual(nueva["estado"], "activa")
        self.assertEqual(nueva["ini"], pd.Timestamp("2026-08-05 02:00:00"))


if __name__ == "__main__":
    unittest.main()
