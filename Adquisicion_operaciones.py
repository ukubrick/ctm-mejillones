"""
Adquisición de OPERACIONES EN TIEMPO REAL — SSCC + Despacho CMG + Limitaciones.

Ejecutado por GitHub Actions cada 30 min (cron 10,40 * * * *). Estos endpoints son
rápidos (segundos), pero en el job horario completo quedaban al final, después de
PCP/PID (lentos paginados), y el timeout los dejaba sin correr → SSCC y Despacho CMG
se congelaban. Separándolos en su propio job (igual que potencia) quedan siempre
frescos, sin depender de los endpoints lentos.

Reutiliza las funciones de Adquisicion.py para no duplicar lógica.

Requiere CEN_USER_KEY (SIP: instrucciones CMG, limitaciones) + CEN_OPS_KEY (Operaciones:
SSCC) + DATABASE_URL.
"""
import os
import sys
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

_required = ["CEN_USER_KEY", "DATABASE_URL"]
_missing = [v for v in _required if not os.environ.get(v)]
if _missing:
    print(f"[ERROR] Variables de entorno faltantes: {', '.join(_missing)}")
    sys.exit(1)

from Adquisicion import (
    log,
    TZ_CHILE,
    DIAS_VENTANA,
    DIAS_VENTANA_LIM,
    fetch_sscc,
    upsert_sscc,
    fetch_instrucciones_cmg,
    upsert_instrucciones_cmg,
    fetch_limitaciones,
    upsert_limitaciones,
    log_adquisicion,
)


def run():
    log.info("═" * 58)
    log.info("  Adquisición OPERACIONES (SSCC + Despacho CMG + Limitaciones)")
    log.info("═" * 58)

    hoy    = datetime.now(TZ_CHILE).date()
    fechas = [(hoy - timedelta(days=d)).strftime("%Y-%m-%d")
              for d in range(DIAS_VENTANA - 1, -1, -1)]

    # ── SSCC instrucciones (una llamada por rango, pageSize=-1) ──
    log.info(f"\n  ── SSCC instrucciones {fechas[0]}→{fechas[-1]}")
    t0 = time.time()
    err_str = None
    try:
        regs_sscc            = fetch_sscc(fechas[0], fechas[-1])
        nuevos, actualizados = upsert_sscc(regs_sscc)
        log.info(f"  ✅ SSCC: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ SSCC: {e}"); nuevos = actualizados = 0
    log_adquisicion("sscc_instrucciones", fechas[-1], nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── Instrucciones operacionales CMG (una paginación por rango) ──
    log.info(f"\n  ── Instrucciones CMG {fechas[0]}→{fechas[-1]}")
    t0 = time.time()
    err_str = None
    try:
        regs_icmg            = fetch_instrucciones_cmg(fechas[0], fechas[-1])
        nuevos, actualizados = upsert_instrucciones_cmg(regs_icmg)
        log.info(f"  ✅ Instrucciones CMG: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ Instrucciones CMG: {e}"); nuevos = actualizados = 0
    log_adquisicion("instrucciones_cmg", fechas[-1], nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── Limitaciones transmisión ANG/CCR (ventana amplia) ─────
    lim_start = (hoy - timedelta(days=DIAS_VENTANA_LIM)).strftime("%Y-%m-%d")
    lim_end   = hoy.strftime("%Y-%m-%d")
    log.info(f"\n  ── Limitaciones transmisión {lim_start} → {lim_end}")
    t0 = time.time()
    err_str = None
    try:
        regs_lim             = fetch_limitaciones(lim_start, lim_end)
        nuevos, actualizados = upsert_limitaciones(regs_lim)
        log.info(f"  ✅ Limitaciones: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ Limitaciones: {e}"); nuevos = actualizados = 0
    log_adquisicion("limitaciones_transmision", lim_end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    log.info(f"\n  Fin adquisición operaciones\n")


if __name__ == "__main__":
    run()
