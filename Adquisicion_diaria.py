"""
Adquisición DIARIA — endpoints lentos que cambian poco.

Ejecutado por GitHub Actions 1×/día. Estos endpoints son paginados/pesados y su
dato cambia con baja frecuencia, así que no necesitan correr cada hora; sacarlos
del job horario evita que éste se pase del timeout (dejándolo con su núcleo:
PCP/PID/CMG-programado).

  · CMG real oficial liquidado (rezago ~10 días)
  · Pronóstico de demanda corto plazo
  · Solicitudes de trabajo (ventana 7 días, muy paginado)
  · Maestro técnico de unidades (casi estático)

Reutiliza las funciones de Adquisicion.py. Requiere CEN_USER_KEY + DATABASE_URL.
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
    fetch_cmg_real, upsert_cmg_real,
    fetch_pronostico_demanda, upsert_pronostico_demanda,
    fetch_solicitudes, upsert_solicitudes,
    fetch_unidades_generadoras, upsert_unidades_maestro,
    log_adquisicion,
)


def _bloque(nombre, tabla, fecha_log, fetch_fn, upsert_fn, *args):
    log.info(f"\n  ── {nombre}")
    t0 = time.time()
    err_str = None
    try:
        regs = fetch_fn(*args)
        nuevos, actualizados = upsert_fn(regs)
        log.info(f"  ✅ {nombre}: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ {nombre}: {e}"); nuevos = actualizados = 0
    log_adquisicion(tabla, fecha_log, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)


def run():
    log.info("═" * 58)
    log.info("  Adquisición DIARIA (CMG real · demanda · solicitudes · maestro)")
    log.info("═" * 58)

    hoy = datetime.now(TZ_CHILE).date()

    # CMG real oficial liquidado — rezago ~10 días → ventana 16 a 5 días atrás.
    cmgr_start = (hoy - timedelta(days=16)).strftime("%Y-%m-%d")
    cmgr_end   = (hoy - timedelta(days=5)).strftime("%Y-%m-%d")
    _bloque(f"CMG real {cmgr_start}→{cmgr_end}", "cmg_real", cmgr_end,
            fetch_cmg_real, upsert_cmg_real, cmgr_start, cmgr_end)

    # Pronóstico de demanda corto plazo — hoy → +2 días.
    dem_start = hoy.strftime("%Y-%m-%d")
    dem_end   = (hoy + timedelta(days=2)).strftime("%Y-%m-%d")
    _bloque(f"Pronóstico demanda {dem_start}→{dem_end}", "pronostico_demanda", dem_end,
            fetch_pronostico_demanda, upsert_pronostico_demanda, dem_start, dem_end)

    # Solicitudes de trabajo — ventana 7 días.
    sol_start = (hoy - timedelta(days=7)).strftime("%Y-%m-%d")
    sol_end   = hoy.strftime("%Y-%m-%d")
    _bloque(f"Solicitudes {sol_start}→{sol_end}", "solicitudes_trabajo", sol_end,
            fetch_solicitudes, upsert_solicitudes, sol_start, sol_end)

    # Maestro técnico de unidades — dato casi estático (~12 págs).
    ug_fecha = (hoy - timedelta(days=1)).strftime("%Y-%m-%d")
    _bloque(f"Unidades maestro {ug_fecha}", "unidades_maestro", ug_fecha,
            fetch_unidades_generadoras, upsert_unidades_maestro, ug_fecha)

    log.info("\n  Fin adquisición diaria\n")


if __name__ == "__main__":
    run()
