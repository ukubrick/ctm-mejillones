"""
migracion_fix_pcp_fantasma.py — Limpia valores fantasma del PCP.

Contexto: el endpoint /generacion-programada-pcp/v4 devuelve VARIAS versiones del
programa por (unidad, fecha_hora), una por cada `fecha_programa`. La adquisición
antigua no deduplicaba y el upsert dejaba una versión arbitraria → aparecían
valores fantasma (p.ej. 28/30/49 MW aislados entre horas a plena carga, de un
programa preliminar con costo≈0). `fetch_generacion_programada` ya quedó corregido
(conserva la fecha_programa más reciente). Este script re-consulta un rango y
re-hace el upsert (DO UPDATE) para sobreescribir los valores viejos guardados.

Correr vía el workflow migracion.yml (Actions no bloquea el 5432; la red local sí).
Uso: python3 migracion_fix_pcp_fantasma.py 2026-06-05 2026-07-11

Itera DÍA POR DÍA (una llamada por fecha): el PCP pagina todo el sistema y un
rango largo desborda el timeout. Procesar por día acota cada barrido y deja el
progreso persistido (cada día se upserta antes de pasar al siguiente), de modo
que si el workflow se corta se relanza el mismo rango y solo rehace lo pendiente
(el upsert es idempotente, DO UPDATE).
"""

import sys
from datetime import datetime, timedelta
from Adquisicion import fetch_generacion_programada, upsert_generacion_programada, log

if len(sys.argv) != 3:
    print("Uso: python3 migracion_fix_pcp_fantasma.py YYYY-MM-DD YYYY-MM-DD")
    sys.exit(1)

start_date, end_date = sys.argv[1], sys.argv[2]
d0 = datetime.strptime(start_date, "%Y-%m-%d").date()
d1 = datetime.strptime(end_date, "%Y-%m-%d").date()
if d1 < d0:
    print("La fecha final es anterior a la inicial.")
    sys.exit(1)

log.info(f"Fix PCP fantasma día a día: {start_date} → {end_date} (fecha_programa más reciente)")

tot_nuevos = tot_actualizados = tot_bajos = 0
dia = d0
while dia <= d1:
    ds = dia.strftime("%Y-%m-%d")
    log.info(f"\n── {ds}")
    try:
        regs = fetch_generacion_programada(ds, ds)
        bajos = [r for r in regs if 0 < r["gen_programada_mw"] < 60]
        if bajos:
            tot_bajos += len(bajos)
            log.warning(f"  {len(bajos)} valores <60 MW persisten (posible parada/rampa real):")
            for r in sorted(bajos, key=lambda x: x["fecha_hora"]):
                log.warning(f"    {r['fecha_hora']} {r['unidad']} {r['gen_programada_mw']}")
        nuevos, actualizados = upsert_generacion_programada(regs)
        tot_nuevos += nuevos
        tot_actualizados += actualizados
        log.info(f"  {ds}: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        log.error(f"  {ds}: ERROR — {e} (relanzar el rango; el upsert es idempotente)")
    dia += timedelta(days=1)

log.info(f"\nTotal: {tot_nuevos} nuevos, {tot_actualizados} actualizados, "
         f"{tot_bajos} valores <60 MW residuales")
