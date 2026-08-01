"""
Adquisición SSCC PROGRAMADO (PCP) — workflow propio, 1×/día.

`/servicios-complementarios-programados-pcp/v4` es el único endpoint pendiente
que valía la pena conectar (sondeo 2026-08-01): entrega la provisión programada
en MW por unidad y tipo de servicio (CPF/CSF/CTF, en subida y bajada), que es la
contraparte que faltaba del SSCC instruido y del desempeño CPF/CSF.

Va SEPARADO de `Adquisicion_diaria.py` porque es caro y solo, no porque cambie
seguido: el endpoint IGNORA `idCentral` (verificado: idCentral / id_central /
centralId devuelven el sistema completo), así que hay que paginar el día entero
del SEN — ~121 páginas de 5000 y la API estrangula a ~10 s/página bajo carga
sostenida → **~21 min por día**. Metido en la diaria la haría pasarse del
timeout de 60 min.

Ventana: por defecto AYER (el día operativo ya cerrado, con su programa final).
Se puede pedir otro rango con DIAS_ATRAS, pero cada día extra son ~21 min.

    python Adquisicion_sscc_prog.py [DIAS_ATRAS]   (default 1 = solo ayer)

Requiere CEN_USER_KEY + DATABASE_URL.
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
    fetch_sscc_programado_pcp, upsert_sscc_programado,
    log_adquisicion,
)

# Tope de días por corrida: 2 × 21 min ya roza el timeout de 60 min del workflow.
MAX_DIAS = 2


def run():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if dias > MAX_DIAS:
        log.warning(f"  DIAS_ATRAS={dias} excede el tope de {MAX_DIAS} "
                    f"(~21 min/día vs timeout de 60) — se acota.")
        dias = MAX_DIAS

    log.info("═" * 58)
    log.info("  Adquisición SSCC PROGRAMADO (PCP)")
    log.info("═" * 58)

    hoy = datetime.now(TZ_CHILE).date()
    for d in range(dias, 0, -1):
        fecha = (hoy - timedelta(days=d)).strftime("%Y-%m-%d")
        log.info(f"\n  ── SSCC programado {fecha}")
        t0 = time.time()
        err_str = None
        nuevos = actualizados = 0
        try:
            regs = fetch_sscc_programado_pcp(fecha)
            nuevos, actualizados = upsert_sscc_programado(regs)
            con_mw = sum(1 for r in regs if (r.get("provision_mw") or 0) > 0)
            log.info(f"  ✅ {len(regs)} filas ({con_mw} con provisión > 0): "
                     f"{nuevos} nuevas, {actualizados} actualizadas")
        except Exception as e:
            err_str = e.__class__.__name__
            log.error(f"  ❌ SSCC programado {fecha}: {err_str}")
        log_adquisicion("sscc_programado", fecha, nuevos, actualizados,
                        int((time.time() - t0) * 1000), err_str)

    log.info("\n  Fin adquisición SSCC programado\n")


if __name__ == "__main__":
    run()
