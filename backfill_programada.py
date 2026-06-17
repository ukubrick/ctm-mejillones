"""
backfill_programada.py — Recupera días perdidos de gen. programada PCP.
Uso: python3 backfill_programada.py 2026-06-05 2026-06-09

Consulta el rango completo en una sola llamada (igual que el workflow).
El endpoint PCP devuelve todo el sistema sin filtro por central, por lo que
paginamos localmente. Con rangos largos (>5 días) puede tardar 15-30 min.
"""

import sys
from Adquisicion import fetch_generacion_programada, upsert_generacion_programada, log

if len(sys.argv) != 3:
    print("Uso: python3 backfill_programada.py YYYY-MM-DD YYYY-MM-DD")
    sys.exit(1)

start_date, end_date = sys.argv[1], sys.argv[2]
log.info(f"Backfill gen. programada PCP: {start_date} → {end_date}")

regs = fetch_generacion_programada(start_date, end_date)
nuevos, actualizados = upsert_generacion_programada(regs)
log.info(f"\nTotal: {nuevos} nuevos, {actualizados} actualizados")
