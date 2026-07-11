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
Uso: python3 migracion_fix_pcp_fantasma.py 2026-06-15 2026-07-11

Rango largo (>5 días) tarda 15-30 min por la paginación de todo el sistema.
"""

import sys
from Adquisicion import fetch_generacion_programada, upsert_generacion_programada, log

if len(sys.argv) != 3:
    print("Uso: python3 migracion_fix_pcp_fantasma.py YYYY-MM-DD YYYY-MM-DD")
    sys.exit(1)

start_date, end_date = sys.argv[1], sys.argv[2]
log.info(f"Fix PCP fantasma: re-consulta {start_date} → {end_date} (fecha_programa más reciente)")

regs = fetch_generacion_programada(start_date, end_date)

bajos = [r for r in regs if 0 < r["gen_programada_mw"] < 60]
if bajos:
    log.warning(f"  {len(bajos)} valores <60 MW persisten (posible parada/rampa real):")
    for r in sorted(bajos, key=lambda x: x["fecha_hora"]):
        log.warning(f"    {r['fecha_hora']} {r['unidad']} {r['gen_programada_mw']}")
else:
    log.info("  Sin valores <60 MW tras la deduplicación por fecha_programa.")

nuevos, actualizados = upsert_generacion_programada(regs)
log.info(f"\nTotal: {nuevos} nuevos, {actualizados} actualizados")
