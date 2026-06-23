"""
migracion_generacion_programada_pid.py — Backfill de la generación programada PID
(Programa Intra-Día) en la tabla existente `generacion_programada` (fuente='CEN_PID').

No crea tablas: el PID reutiliza `generacion_programada` (conflict key
(unidad, fecha_hora, fuente)). Solo hace backfill histórico; luego Adquisicion.py
lo mantiene cada hora.

Ejecutar UNA vez (con conexión a la DB disponible):
    python migracion_generacion_programada_pid.py [DIAS_ATRAS]

DIAS_ATRAS por defecto = 7. Se hace día por día (el PID es 1-indexado y pesado,
~72 págs/día con limit=5000).
"""
import sys
from datetime import date, timedelta

from Adquisicion import fetch_generacion_programada_pid, upsert_generacion_programada


def main():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    hoy = date.today()
    total_n = total_a = 0
    # Incluye mañana (programa publicado con anticipación)
    for delta in range(-dias, 2):
        dia = (hoy + timedelta(days=delta)).strftime("%Y-%m-%d")
        print(f"Backfill PID {dia} (paginando ~72 págs)...")
        regs = fetch_generacion_programada_pid(dia, dia)
        n, a = upsert_generacion_programada(regs)
        total_n += n; total_a += a
        print(f"  {dia}: {n} nuevos, {a} actualizados ({len(regs)} registros)")
    print(f"Listo: {total_n} nuevos, {total_a} actualizados en total.")


if __name__ == "__main__":
    main()
