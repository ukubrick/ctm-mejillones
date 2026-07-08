"""
Adquisición DIARIA — endpoints lentos que cambian poco.

Ejecutado por GitHub Actions 1×/día. Estos endpoints son paginados/pesados y su
dato cambia con baja frecuencia, así que no necesitan correr cada hora; sacarlos
del job horario evita que éste se pase del timeout (dejándolo con su núcleo:
PCP/PID/CMG-programado).

  · CMG real oficial liquidado (rezago ~10 días) — 4 barras (+ Angamos/Cochrane)
  · CMG programado PCP (día-anterior; el PID lo lleva el job horario)
  · Pronóstico de demanda corto plazo
  · Solicitudes de trabajo (ventana 7 días, muy paginado)
  · Maestro técnico de unidades (casi estático)
  · Mantenimiento mayor CTM (liviano, ventana 45 días de publicación)
  · Demanda neta del SEN (feature del forecast CMG)
  · Mix de generación diaria por tecnología
  · Desempeño SSCC CPF/CSF (solo días faltantes; el CEN publica con rezago 2-3 meses)

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
    fetch_cmg_programado, upsert_cmg_programado,
    fetch_pronostico_demanda, upsert_pronostico_demanda,
    fetch_solicitudes, upsert_solicitudes,
    fetch_unidades_generadoras, upsert_unidades_maestro,
    fetch_mantenimiento_mayor, upsert_mantenimiento_mayor,
    fetch_demanda_neta, upsert_demanda_neta,
    fetch_mix_diario, upsert_mix_diario,
    fetch_desempeno_sscc, upsert_desempeno_sscc, dias_faltantes_desempeno,
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

    # CMG programado PCP (día-anterior) — ayer → mañana. El PID (intra-día) lo
    # actualiza el job horario; el PCP cambia 1×/día, basta la corrida diaria.
    pcp_start = (hoy - timedelta(days=1)).strftime("%Y-%m-%d")
    pcp_end   = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    _bloque(f"CMG programado PCP {pcp_start}→{pcp_end}", "cmg_programado_pcp", pcp_end,
            fetch_cmg_programado, upsert_cmg_programado, pcp_start, pcp_end, "CEN_PCP")

    # Mantenimiento mayor CTM — la ventana filtra por fecha de PUBLICACIÓN, así
    # que 45 días hacia atrás captura también los programas futuros ya publicados.
    mm_start = (hoy - timedelta(days=45)).strftime("%Y-%m-%d")
    mm_end   = hoy.strftime("%Y-%m-%d")
    _bloque(f"Mantenimiento mayor {mm_start}→{mm_end}", "mantenimiento_mayor", mm_end,
            fetch_mantenimiento_mayor, upsert_mantenimiento_mayor, mm_start, mm_end)

    # Demanda neta del SEN — publica con rezago ~1 día; ventana 4 días.
    dn_start = (hoy - timedelta(days=4)).strftime("%Y-%m-%d")
    dn_end   = hoy.strftime("%Y-%m-%d")
    _bloque(f"Demanda neta {dn_start}→{dn_end}", "demanda_neta", dn_end,
            fetch_demanda_neta, upsert_demanda_neta, dn_start, dn_end)

    # Mix de generación diaria — una llamada liviana por día (últimos 3).
    for d in range(3, 0, -1):
        f_mix = (hoy - timedelta(days=d)).strftime("%Y-%m-%d")
        _bloque(f"Mix diario {f_mix}", "mix_generacion_diaria", f_mix,
                fetch_mix_diario, upsert_mix_diario, f_mix)

    # Desempeño SSCC CPF/CSF — solo los días que faltan en la tabla (el CEN
    # publica por bloques con rezago 2-3 meses; un día vacío cuesta 2 requests).
    faltantes = dias_faltantes_desempeno()
    log.info(f"\n  ── Desempeño SSCC: {len(faltantes)} días faltantes por sondear")
    total_regs = 0
    t0 = time.time()
    for f_d in faltantes:
        try:
            regs = fetch_desempeno_sscc(f_d)
            n, a = upsert_desempeno_sscc(regs)
            total_regs += n + a
        except Exception as e:
            log.error(f"  ❌ Desempeño SSCC {f_d}: {e}")
    log_adquisicion("desempeno_sscc", hoy.strftime("%Y-%m-%d"), total_regs, 0,
                    int((time.time() - t0) * 1000), None)

    log.info("\n  Fin adquisición diaria\n")


if __name__ == "__main__":
    run()
