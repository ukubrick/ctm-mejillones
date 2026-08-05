"""
Adquisición rápida de GENERACIÓN BRUTA EN TIEMPO REAL — solo generación real.

Ejecutado por GitHub Actions cada 30 min para tener la generación de las 4
unidades (ANG1/ANG2/CCR1/CCR2) lo antes posible, sin esperar a la corrida
horaria completa.

NO tiene sentido subirlo de ahí: medido 2026-08-04, la gen-real del CEN es
HORARIA y llega con ~4,6 h de rezago, así que pedirla más seguido no adelanta
un solo dato — solo gasta requests contra el rate limiter. El CMG online, que
sí es de 15 min, se separó a `Adquisicion_cmg_min.py` justamente por eso.

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
    log_adquisicion,
    ResumenCorrida,
    abortar_si_cen_caido,
    _redactar,
)

# Ventana corta: hoy + ayer. La gen-real filtra por central en el servidor (rápido),
# 2 días basta para refrescar lo más reciente y cubrir el cambio de día UTC/Chile.
DIAS_VENTANA_POT = 2


def run() -> int:
    log.info("═" * 58)
    log.info("  Adquisición POTENCIA REAL (gen-real, cada 30 min) — CTM")
    log.info("═" * 58)

    abortar_si_cen_caido("Potencia")
    resumen = ResumenCorrida("Potencia")

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
            resumen.paso_ok(f"gen-real {fecha}")
        except Exception as e:
            err_str = _redactar(e); log.error(f"  ❌ {err_str}"); nuevos = dupes = 0
            resumen.paso_fallo(f"gen-real {fecha}", e)
        log_adquisicion("generacion_real", fecha, nuevos, dupes,
                        int((time.time() - t0) * 1000), err_str)

    log.info(f"\n  Fin — {total} registros de generación real\n")
    return resumen.cerrar()


if __name__ == "__main__":
    sys.exit(run())
