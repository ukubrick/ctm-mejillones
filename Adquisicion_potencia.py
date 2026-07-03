"""
Adquisición rápida de GENERACIÓN BRUTA EN TIEMPO REAL — solo generación real.

Ejecutado por GitHub Actions cada 30 min (cron 25,55 * * * *) para tener la
generación de las 4 unidades (ANG1/ANG2/CCR1/CCR2) lo antes posible, sin esperar
a la corrida horaria completa (PCP/PID/CMG/SSCC/limitaciones son más lentos).

Reutiliza las funciones de Adquisicion.py para no duplicar lógica.
Patrón replicado del proyecto Pulsar (ernc-aes-dashboard → Adquisicion_potencia_ernc.py).

Solo necesita CEN_USER_KEY (plan SIP) + DATABASE_URL. NO usa CEN_OPS_KEY (solo SSCC la requiere).
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
    fetch_generacion_real,
    upsert_generacion_real,
    fetch_cmg_nodos,
    upsert_cmg,
    log_adquisicion,
)

# Ventana corta: hoy + ayer. La gen-real filtra por central en el servidor (rápido),
# 2 días basta para refrescar lo más reciente y cubrir el cambio de día UTC/Chile.
DIAS_VENTANA_POT = 2


def run():
    log.info("═" * 58)
    log.info("  Adquisición POTENCIA REAL (gen-real, cada 30 min) — CTM")
    log.info("═" * 58)

    hoy    = datetime.now(TZ_CHILE).date()
    fechas = [(hoy - timedelta(days=d)).strftime("%Y-%m-%d")
              for d in range(DIAS_VENTANA_POT - 1, -1, -1)]

    # ⚠️ SIEMPRE una llamada POR DÍA: el endpoint v3 trunca los rangos multi-día
    # (verificado 2026-07-03). Ver nota en Adquisicion.run().
    total = 0
    for fecha in fechas:
        log.info(f"\n  ── Gen. real {fecha}")
        t0 = time.time()
        err_str = None
        try:
            regs          = fetch_generacion_real(fecha, fecha)
            nuevos, dupes = upsert_generacion_real(regs)
            total += nuevos
            log.info(f"  ✅ {nuevos} nuevos, {dupes} duplicados")
        except Exception as e:
            err_str = str(e); log.error(f"  ❌ {e}"); nuevos = dupes = 0
        log_adquisicion("generacion_real", fecha, nuevos, dupes,
                        int((time.time() - t0) * 1000), err_str)

    # ── CMG nodos (S3) ── GET rápido, se actualiza ~15 min en el S3 del CEN.
    # Corre aquí cada 30 min para tener el CMG lo más cercano a tiempo real,
    # sin depender del job horario completo (que puede colgarse en PCP/PID).
    log.info(f"\n  ── CMG Nodos CTM (S3 portal CEN)")
    t0 = time.time()
    err_str = None
    try:
        regs_cmg             = fetch_cmg_nodos()
        nuevos, actualizados = upsert_cmg(regs_cmg)
        log.info(f"  ✅ CMG: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ CMG: {e}"); nuevos = actualizados = 0
    log_adquisicion("cmg_nodos_s3", hoy.strftime("%Y-%m-%d"), nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    log.info(f"\n  Fin — {total} registros de potencia + CMG procesados\n")


if __name__ == "__main__":
    run()
