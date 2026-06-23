"""
migracion_cmg_real.py — Crea la tabla costo_marginal_real y hace un backfill
inicial del CMG real oficial liquidado para Crucero/Tarapacá.

Ejecutar UNA vez (con conexión a la DB disponible, p. ej. hotspot):
    python migracion_cmg_real.py [DIAS_ATRAS]

DIAS_ATRAS por defecto = 30. El CMG real se liquida con rezago ~10 días.
Después, Adquisicion.py mantiene la tabla cada hora.
"""
import sys
from datetime import date, timedelta

from Adquisicion import get_conn, fetch_cmg_real, upsert_cmg_real

DDL = """
CREATE TABLE IF NOT EXISTS costo_marginal_real (
    id           SERIAL PRIMARY KEY,
    barra_transf TEXT NOT NULL,
    fecha_hora   TEXT NOT NULL,
    cmg_usd_mwh  NUMERIC,
    cmg_clp_kwh  NUMERIC,
    version      TEXT,
    UNIQUE (barra_transf, fecha_hora)
);
CREATE INDEX IF NOT EXISTS idx_cmg_real_fh ON costo_marginal_real (fecha_hora);
"""


def main():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    print("Creando tabla costo_marginal_real...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    print("Tabla lista.")

    hoy = date.today()
    start = (hoy - timedelta(days=dias)).strftime("%Y-%m-%d")
    end   = (hoy - timedelta(days=5)).strftime("%Y-%m-%d")  # rezago de liquidación
    print(f"Backfill CMG real {start} → {end}...")
    regs = fetch_cmg_real(start, end)
    nuevos, act = upsert_cmg_real(regs)
    print(f"Listo: {nuevos} nuevos, {act} actualizados ({len(regs)} registros).")


if __name__ == "__main__":
    main()
