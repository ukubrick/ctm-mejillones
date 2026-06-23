"""
migracion_pronostico_demanda.py — Crea la tabla pronostico_demanda y hace un
backfill inicial del pronóstico de demanda corto plazo (Crucero/Laberinto/Angamos/Mejillones).

Ejecutar UNA vez (con conexión a la DB disponible):
    python migracion_pronostico_demanda.py [DIAS_ADELANTE]

DIAS_ADELANTE por defecto = 2 (es un pronóstico, mira hacia adelante).
Después, Adquisicion.py mantiene la tabla cada hora.
"""
import sys
from datetime import date, timedelta

from Adquisicion import get_conn, fetch_pronostico_demanda, upsert_pronostico_demanda

DDL = """
CREATE TABLE IF NOT EXISTS pronostico_demanda (
    id           SERIAL PRIMARY KEY,
    barra        TEXT NOT NULL,
    fecha_hora   TEXT NOT NULL,
    energia_mwh  NUMERIC,
    hora         INTEGER,
    date_control TEXT,
    UNIQUE (barra, fecha_hora)
);
CREATE INDEX IF NOT EXISTS idx_pron_dem_fh ON pronostico_demanda (fecha_hora);
"""


def main():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    print("Creando tabla pronostico_demanda...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    print("Tabla lista.")

    hoy = date.today()
    start = hoy.strftime("%Y-%m-%d")
    end   = (hoy + timedelta(days=dias)).strftime("%Y-%m-%d")
    print(f"Backfill pronóstico demanda {start} → {end} (endpoint liviano, ~4 págs)...")
    regs = fetch_pronostico_demanda(start, end)
    nuevos, act = upsert_pronostico_demanda(regs)
    print(f"Listo: {nuevos} nuevos, {act} actualizados ({len(regs)} registros).")


if __name__ == "__main__":
    main()
