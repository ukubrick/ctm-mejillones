"""
migracion_instrucciones_cmg.py — Crea la tabla instrucciones_cmg y hace un
backfill inicial de las instrucciones operacionales de despacho por CMG
(ANG1/ANG2/CCR1/CCR2).

Ejecutar UNA vez (con conexión a la DB disponible, p. ej. hotspot):
    python migracion_instrucciones_cmg.py [DIAS_ATRAS]

DIAS_ATRAS por defecto = 7. Después, Adquisicion.py mantiene la tabla cada hora.
"""
import sys
from datetime import date, timedelta

from Adquisicion import get_conn, fetch_instrucciones_cmg, upsert_instrucciones_cmg

DDL = """
CREATE TABLE IF NOT EXISTS instrucciones_cmg (
    id               SERIAL PRIMARY KEY,
    id_instruccion   BIGINT,
    unidad           TEXT NOT NULL,
    central          TEXT,
    fecha_hora       TEXT,
    fecha            TEXT,
    hora             TEXT,
    configuracion    TEXT,
    despacho         NUMERIC,
    estado           TEXT,
    estado_operativo TEXT,
    consigna         TEXT,
    instruccion_cmg  TEXT,
    motivo           TEXT,
    zona_desaclope   TEXT,
    control_tension  TEXT,
    UNIQUE (id_instruccion, unidad)
);
CREATE INDEX IF NOT EXISTS idx_instr_cmg_fh     ON instrucciones_cmg (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_instr_cmg_unidad ON instrucciones_cmg (unidad);
"""


def main():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print("Creando tabla instrucciones_cmg...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    print("Tabla lista.")

    hoy = date.today()
    total_n = total_a = 0
    for d in range(dias, -1, -1):
        fecha = (hoy - timedelta(days=d)).strftime("%Y-%m-%d")
        print(f"Backfill instrucciones CMG {fecha} (~25 págs)...")
        regs = fetch_instrucciones_cmg(fecha)
        n, a = upsert_instrucciones_cmg(regs)
        total_n += n; total_a += a
        print(f"  {fecha}: {n} nuevos, {a} actualizados ({len(regs)} registros).")
    print(f"Listo: {total_n} nuevos, {total_a} actualizados en total.")


if __name__ == "__main__":
    main()
