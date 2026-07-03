"""
migracion_unidades_maestro.py — Crea la tabla unidades_maestro y hace un
backfill inicial del maestro técnico de las 4 unidades (ANG1/2, CCR1/2).

Ejecutar UNA vez (con conexión a la DB disponible):
    python migracion_unidades_maestro.py [DIAS_ATRAS]

DIAS_ATRAS por defecto = 7: el endpoint publica fichas por fecha y no siempre
aparecen las 4 unidades el mismo día, así que se barren varios días.
Después, Adquisicion.py mantiene la tabla cada hora.
"""
import sys
import time
from datetime import date, timedelta

from Adquisicion import get_conn, fetch_unidades_generadoras, upsert_unidades_maestro

DDL = """
CREATE TABLE IF NOT EXISTS unidades_maestro (
    unidad               TEXT PRIMARY KEY,
    id_unidad            INTEGER,
    id_central           INTEGER,
    central              TEXT,
    unidad_nombre        TEXT,
    nemotecnico          TEXT,
    propietario          TEXT,
    tecnologia           TEXT,
    punto_conexion       TEXT,
    pot_max_bruta        NUMERIC,
    pot_neta_efectiva    NUMERIC,
    pot_min_tecnica      NUMERIC,
    min_tec_ctrl_frec    NUMERIC,
    consumos_propios_pct NUMERIC,
    tension_nominal      NUMERIC,
    factor_pot_nominal   NUMERIC,
    fecha_dato           TEXT
);
"""


def main():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print("Creando tabla unidades_maestro...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    print("Tabla lista.")

    hoy = date.today()
    total = 0
    for d in range(dias, 0, -1):
        fecha = (hoy - timedelta(days=d)).strftime("%Y-%m-%d")
        regs = fetch_unidades_generadoras(fecha)
        if regs:
            nuevos, act = upsert_unidades_maestro(regs)
            total += len(regs)
            print(f"  {fecha}: {len(regs)} fichas ({nuevos} nuevas, {act} actualizadas)")
        time.sleep(0.5)
    print(f"Listo: {total} fichas procesadas.")


if __name__ == "__main__":
    main()
