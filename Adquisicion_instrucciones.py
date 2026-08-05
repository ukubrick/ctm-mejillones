"""
Adquisición de ALTA FRECUENCIA de las instrucciones de despacho por CMG.

Por qué tiene cron propio y no viaja con el resto de Operaciones:

Las instrucciones son la única fuente del proyecto que NO es una serie con
malla: son EVENTOS con minuto exacto (medido: 06:20, 07:35, 17:57, 19:00). Para
un evento, la latencia con que el dashboard lo muestra ES la frecuencia con que
lo sondeamos — no hay nada que esperar del lado del CEN, como sí pasa con la
gen-real (horaria y con 4-5 h de rezago, donde subir la frecuencia no adelanta
un solo dato).

Y son las que encienden el aviso de limitación de unidad: cuando el motivo cita
un SICF / SDCF / IL / IF, esa ventana es una limitación de la MÁQUINA que el CEN
no publica en `limitaciones_transmision`. Enterarse 30 min más tarde de que una
unidad quedó limitada es media hora de operación a ciegas.

Cuesta casi nada: con `limit=5000` el día entero cabe en UNA página (~3 s).

El barrido de respaldo lo sigue haciendo `Adquisicion_operaciones.py` cada 30
min sobre la ventana completa: si este cron se salta corridas —Actions descarta
corridas programadas de forma sistemática, sobre todo de madrugada— el hueco se
rellena igual, porque el upsert es idempotente.

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
    log, TZ_CHILE,
    fetch_instrucciones_cmg, upsert_instrucciones_cmg,
    log_adquisicion, ResumenCorrida, abortar_si_cen_caido, _redactar,
)

# Ventana corta: el CEN reemite la misma instrucción (primero con el folio en
# blanco y después con el número real), así que hay que volver a mirar el
# pasado inmediato, no solo lo nuevo. 2 días cubre además el cambio de día.
DIAS_VENTANA_INSTR = 2


def run() -> int:
    log.info("═" * 58)
    log.info("  Adquisición INSTRUCCIONES DE DESPACHO (alta frecuencia)")
    log.info("═" * 58)

    abortar_si_cen_caido("Instrucciones")
    resumen = ResumenCorrida("Instrucciones")

    hoy   = datetime.now(TZ_CHILE).date()
    start = (hoy - timedelta(days=DIAS_VENTANA_INSTR - 1)).strftime("%Y-%m-%d")
    end   = hoy.strftime("%Y-%m-%d")

    log.info(f"\n  ── Instrucciones CMG {start} → {end}")
    t0 = time.time()
    err_str = None
    nuevos = actualizados = 0
    try:
        regs = fetch_instrucciones_cmg(start, end)
        nuevos, actualizados = upsert_instrucciones_cmg(regs)
        log.info(f"  ✅ {len(regs)} filas ANG/CCR: {nuevos} nuevas, "
                 f"{actualizados} actualizadas")
        resumen.paso_ok("instrucciones-cmg")
    except Exception as e:
        err_str = _redactar(e)
        log.error(f"  ❌ Instrucciones CMG: {err_str}")
        resumen.paso_fallo("instrucciones-cmg", e)
    log_adquisicion("instrucciones_cmg", end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    log.info("\n  Fin adquisición instrucciones\n")
    return resumen.cerrar()


if __name__ == "__main__":
    sys.exit(run())
