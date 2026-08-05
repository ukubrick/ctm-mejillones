"""
Adquisición de ALTA FRECUENCIA del CMG online (15 min).

Por qué se separó de `Adquisicion_potencia.py`, con el que viajaba:

Las dos fuentes de ese job tienen ritmos INCOMPATIBLES. Medido 2026-08-04:

    CMG online     granularidad 15 min · rezago 1,1 h
    gen-real       granularidad  1 h   · rezago 4,6 h

O sea que el CMG publica un dato nuevo cuatro veces por hora y llega casi
fresco, mientras la generación publica uno por hora y con casi cinco de atraso.
Atados en el mismo cron, o el CMG va demasiado lento o la gen-real se pide
cuatro veces para traer lo mismo — y cada pedido de más es una probabilidad de
429, que es lo que de verdad encarece estos jobs (el rate limit del CEN es el
cuello, no los minutos de Actions).

La ventana se expresa en HORAS de cobertura real, no en páginas: ver
`fetch_cmg_online_api`, donde está medido por qué "las últimas N páginas" es
una cuenta que miente.

El barrido del día completo (self-heal) lo hace la corrida horaria
`Adquisicion.py`, con upsert idempotente: si este cron se salta corridas
—Actions descarta corridas programadas, sobre todo de madrugada— el hueco se
rellena igual dentro de la hora.

Solo necesita CEN_USER_KEY (plan SIP) + DATABASE_URL.
"""
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

_missing = [v for v in ("CEN_USER_KEY", "DATABASE_URL") if not os.environ.get(v)]
if _missing:
    print(f"[ERROR] Variables de entorno faltantes: {', '.join(_missing)}")
    sys.exit(1)

from Adquisicion import (
    log, TZ_CHILE, adquirir_cmg_online,
    log_adquisicion, ResumenCorrida, abortar_si_cen_caido, _redactar,
)

# Horas de cobertura REAL por corrida. Con el cron cada 15 min esto tapa varias
# corridas seguidas: la cadencia que entrega Actions no es la pedida (en Pulsar
# se midió un intervalo efectivo de 147 min para un cron de 30, con saltos de
# hasta 4,3 h de madrugada), y lo que cae fuera de la ventana solo lo recupera
# el barrido horario.
CMG_HORAS_ATRAS = 3.0


def run() -> int:
    log.info("═" * 58)
    log.info("  Adquisición CMG ONLINE 15 min (alta frecuencia)")
    log.info("═" * 58)

    abortar_si_cen_caido("CMG online")
    resumen = ResumenCorrida("CMG online")

    hoy = datetime.now(TZ_CHILE).strftime("%Y-%m-%d")
    log.info(f"\n  ── CMG online {hoy} (últimas {CMG_HORAS_ATRAS} h)")
    t0 = time.time()
    err_str = None
    n_min = n_hora = 0
    try:
        n_min, n_hora = adquirir_cmg_online(hoy, hoy, horas_atras=CMG_HORAS_ATRAS)
        log.info(f"  ✅ {n_min} puntos de 15 min, {n_hora} filas horarias")
        resumen.paso_ok("cmg-online")
    except Exception as e:
        err_str = _redactar(e)
        log.error(f"  ❌ CMG online: {err_str}")
        resumen.paso_fallo("cmg-online", e)
    log_adquisicion("cmg_online_min", hoy, n_min, n_hora,
                    int((time.time() - t0) * 1000), err_str)

    log.info("\n  Fin adquisición CMG online\n")
    return resumen.cerrar()


if __name__ == "__main__":
    sys.exit(run())
