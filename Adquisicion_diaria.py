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

Y el SELF-HEAL de las fuentes de alta frecuencia, cuyos crons trabajan sobre
ventanas cortas para no gastar requests repitiendo lo mismo:

  · Gen. real de los últimos 7 días (el horario solo hace hoy + ayer)
  · CMG online: día completo de ayer (el horario solo barre hoy)

Actions descarta corridas programadas de forma sistemática (regla 54), así que
lo que queda fuera de una ventana corta no se vuelve a pedir nunca: este barrido
diario, con upsert idempotente, es lo que garantiza que el hueco se tape.

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
    log, TZ_CHILE, DIAS_VENTANA,
    fetch_generacion_real, upsert_generacion_real,
    adquirir_cmg_online,
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
    ResumenCorrida,
    abortar_si_cen_caido,
    _redactar,
)

# Resumen de la corrida en curso. Lo llena `_bloque` y lo lee `run()` para decidir
# el código de salida: una corrida que no adquirió nada debe salir ROJA.
_RESUMEN: ResumenCorrida | None = None


def _bloque(nombre, tabla, fecha_log, fetch_fn, upsert_fn, *args):
    log.info(f"\n  ── {nombre}")
    t0 = time.time()
    err_str = None
    try:
        regs = fetch_fn(*args)
        nuevos, actualizados = upsert_fn(regs)
        log.info(f"  ✅ {nombre}: {nuevos} nuevos, {actualizados} actualizados")
        if _RESUMEN:
            _RESUMEN.paso_ok(tabla)
    except Exception as e:
        err_str = _redactar(e); log.error(f"  ❌ {nombre}: {err_str}"); nuevos = actualizados = 0
        if _RESUMEN:
            _RESUMEN.paso_fallo(tabla, e)
    log_adquisicion(tabla, fecha_log, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)


def run() -> int:
    global _RESUMEN
    log.info("═" * 58)
    log.info("  Adquisición DIARIA (CMG real · demanda · solicitudes · maestro)")
    log.info("═" * 58)

    abortar_si_cen_caido("Diaria")
    _RESUMEN = ResumenCorrida("Diaria")

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
    fallos_desempeno = 0
    for f_d in faltantes:
        try:
            regs = fetch_desempeno_sscc(f_d)
            n, a = upsert_desempeno_sscc(regs)
            total_regs += n + a
        except Exception as e:
            fallos_desempeno += 1
            log.error(f"  ❌ Desempeño SSCC {f_d}: {_redactar(e)}")
    log_adquisicion("desempeno_sscc", hoy.strftime("%Y-%m-%d"), total_regs, 0,
                    int((time.time() - t0) * 1000), None)
    # Los días faltantes suelen ser cero (el CEN publica con 2-3 meses de rezago),
    # así que "sin días que sondear" NO es un fallo: solo cuenta si algo reventó.
    if faltantes:
        if fallos_desempeno == len(faltantes):
            _RESUMEN.paso_fallo("desempeno_sscc", f"{fallos_desempeno} días fallaron")
        else:
            _RESUMEN.paso_ok("desempeno_sscc")

    # ── SELF-HEAL de las fuentes de alta frecuencia ───────────────────────────
    # Los crons rápidos trabajan sobre ventanas cortas (gen-real: hoy+ayer; CMG
    # online: 3 h) porque repetir la ventana larga 24 veces al día es puro gasto
    # contra el rate limiter. Pero Actions descarta corridas programadas de forma
    # sistemática (regla 54), así que la cadencia pedida no es la garantizada y lo
    # que cae fuera de una ventana corta no se vuelve a pedir NUNCA. Acá se
    # re-barre el rango completo una vez al día, con upsert idempotente.
    log.info(f"\n  ── Self-heal gen. real (últimos {DIAS_VENTANA} días)")
    for d in range(DIAS_VENTANA - 1, -1, -1):
        f_gr = (hoy - timedelta(days=d)).strftime("%Y-%m-%d")
        _bloque(f"Gen. real {f_gr}", "generacion_real", f_gr,
                fetch_generacion_real, upsert_generacion_real, f_gr, f_gr)

    # CMG online: día completo de AYER, que a esta hora ya cerró y no cambia más.
    # El job horario solo barre HOY.
    ayer = (hoy - timedelta(days=1)).strftime("%Y-%m-%d")
    log.info(f"\n  ── Self-heal CMG online día completo {ayer}")
    t0 = time.time()
    err_str = None
    n_min = n_hora = 0
    try:
        n_min, n_hora = adquirir_cmg_online(ayer, ayer)
        log.info(f"  ✅ CMG: {n_min} puntos de 15 min, {n_hora} filas horarias")
        _RESUMEN.paso_ok("cmg-online")
    except Exception as e:
        err_str = _redactar(e)
        log.error(f"  ❌ CMG online: {err_str}")
        _RESUMEN.paso_fallo("cmg-online", e)
    log_adquisicion("cmg_online_min", ayer, n_min, n_hora,
                    int((time.time() - t0) * 1000), err_str)

    log.info("\n  Fin adquisición diaria\n")
    return _RESUMEN.cerrar()


if __name__ == "__main__":
    sys.exit(run())
