"""
migracion_cmg_programado.py — Crea la tabla costo_marginal_programado y hace un
backfill inicial del CMG programado (PID) para Crucero/Tarapacá.

Ejecutar UNA vez (con conexión a la DB disponible, p. ej. hotspot):
    python migracion_cmg_programado.py [DIAS_ATRAS]

DIAS_ATRAS por defecto = 7. Después, Adquisicion.py mantiene la tabla cada hora.
"""
import sys
from datetime import date, timedelta

from Adquisicion import get_conn, fetch_cmg_programado, upsert_cmg_programado

DDL = """
CREATE TABLE IF NOT EXISTS costo_marginal_programado (
    id             SERIAL PRIMARY KEY,
    barra          TEXT NOT NULL,
    fecha_hora     TEXT NOT NULL,
    cmg_usd_mwh    NUMERIC,
    fecha_programa TEXT,
    UNIQUE (barra, fecha_hora)
);
CREATE INDEX IF NOT EXISTS idx_cmg_prog_fh ON costo_marginal_programado (fecha_hora);
"""


def main():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print("Creando tabla costo_marginal_programado...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    print("Tabla lista.")

    hoy = date.today()
    start = (hoy - timedelta(days=dias)).strftime("%Y-%m-%d")
    end   = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Backfill CMG programado {start} → {end} (esto pagina ~60 págs, ~5 min)...")
    regs = fetch_cmg_programado(start, end)
    nuevos, act = upsert_cmg_programado(regs)
    print(f"Listo: {nuevos} nuevos, {act} actualizados ({len(regs)} registros).")


if __name__ == "__main__":
    main()
