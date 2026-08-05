"""
Adquisición de la GENERACIÓN PROGRAMADA PCP (programa day-ahead).

Por qué salió del job horario:

El PCP es el programa que el CEN publica con un día de anticipación, y que
reemite ocasionalmente. Su cadencia natural NO es horaria. Pero el endpoint
`/generacion-programada-pcp/v4` no filtra por central (regla 9), así que hay que
paginar el SEN completo para quedarse con las ~750 filas de ANG/CCR:

    62 páginas por DÍA de ventana con limit=5000  (medido 2026-08-05)
    ventana ayer→mañana = 124 páginas ≈ 11 min a ritmo sostenido (regla 34)

Correrlo cada hora eran ~3.000 páginas diarias contra el rate limiter del CEN
para traer casi siempre el mismo dato — y era casi la mitad del tiempo del job
horario, que existe para lo que sí cambia en la hora.

Cada 3 h son 8 corridas diarias: sigue siendo 8× más seguido de lo que la fuente
publica, y cualquier reemisión entra al dashboard dentro de las 3 h. El programa
INTRA-DÍA (PID), que es el que se mueve durante la jornada, sigue en el horario.

Solo necesita CEN_USER_KEY (plan SIP) + DATABASE_URL.
"""
import os
import sys
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

_missing = [v for v in ("CEN_USER_KEY", "DATABASE_URL") if not os.environ.get(v)]
if _missing:
    print(f"[ERROR] Variables de entorno faltantes: {', '.join(_missing)}")
    sys.exit(1)

from Adquisicion import (
    log, TZ_CHILE, DIAS_VENTANA_PCP,
    fetch_generacion_programada, upsert_generacion_programada,
    log_adquisicion, ResumenCorrida, abortar_si_cen_caido, _redactar,
)


def run() -> int:
    log.info("═" * 58)
    log.info("  Adquisición GENERACIÓN PROGRAMADA PCP (day-ahead)")
    log.info("═" * 58)

    abortar_si_cen_caido("PCP")
    resumen = ResumenCorrida("PCP")

    hoy = datetime.now(TZ_CHILE).date()
    # Ventana ayer → mañana: incluir mañana captura el programa del día completo
    # que el CEN publica con anticipación, que es justo el que se dibuja contra
    # la generación real en el panel.
    start = (hoy - timedelta(days=DIAS_VENTANA_PCP - 1)).strftime("%Y-%m-%d")
    end   = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")

    log.info(f"\n  ── Gen. programada PCP {start} → {end}")
    t0 = time.time()
    err_str = None
    nuevos = actualizados = 0
    try:
        regs = fetch_generacion_programada(start, end)
        nuevos, actualizados = upsert_generacion_programada(regs)
        log.info(f"  ✅ PCP: {nuevos} nuevas, {actualizados} ya existentes")
        resumen.paso_ok("pcp")
    except Exception as e:
        err_str = _redactar(e)
        log.error(f"  ❌ PCP: {err_str}")
        resumen.paso_fallo("pcp", e)
    log_adquisicion("generacion_programada_pcp", end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    log.info("\n  Fin adquisición PCP\n")
    return resumen.cerrar()


if __name__ == "__main__":
    sys.exit(run())
