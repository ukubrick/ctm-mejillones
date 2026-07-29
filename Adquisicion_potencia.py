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
    adquirir_cmg_online,
    log_adquisicion,
)

# Páginas finales del día que se bajan del CMG online en cada corrida rápida.
# El feed viene ordenado por fecha_minuto (~40 páginas/día) → las últimas son los
# puntos más frescos. 6 páginas ≈ las últimas ~4 h, suficiente para un cron de 30 min.
CMG_ULTIMAS_PAGINAS = 6

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

    # ── CMG online (API SIP, 15 min) ── fuente principal desde 2026-07-29:
    # trae las barras de las propias centrales y NO descarta los CMG = 0
    # (el feed S3 hacía ambas cosas mal). Fallback automático al S3.
    hoy_str = hoy.strftime("%Y-%m-%d")
    log.info(f"\n  ── CMG online 15 min (API SIP, últimas {CMG_ULTIMAS_PAGINAS} págs)")
    t0 = time.time()
    err_str = None
    try:
        n_min, n_hora = adquirir_cmg_online(hoy_str, hoy_str, CMG_ULTIMAS_PAGINAS)
        log.info(f"  ✅ CMG: {n_min} puntos de 15 min, {n_hora} filas horarias")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ CMG: {e}"); n_min = n_hora = 0
    log_adquisicion("cmg_online_min", hoy_str, n_min, n_hora,
                    int((time.time() - t0) * 1000), err_str)

    log.info(f"\n  Fin — {total} registros de potencia + CMG procesados\n")


if __name__ == "__main__":
    run()
