"""
migracion_cmg_online_min.py — Crea la tabla costo_marginal_online_min (CMG real
en línea, resolución 15 min, 4 barras: Crucero/Tarapacá + Angamos/Cochrane) y
hace un backfill día por día desde /costo-marginal-online/v4.

Motivo: el feed S3 que alimentaba `costo_marginal` (a) no trae las barras de las
propias centrales y (b) DESCARTABA los valores 0 → el dashboard nunca mostraba
los desacoples con CMG = 0. La API sí los trae.

Correr vía el workflow `migracion.yml`:
    python migracion_cmg_online_min.py [DIAS_ATRAS]   (default 7)

Cada día son ~40 páginas de 4000 filas → ~1 min por día. No abusar del rango.
"""
import sys
from datetime import date, timedelta

from Adquisicion import (get_conn, fetch_cmg_online_api, agregar_cmg_horario,
                         upsert_cmg_online_min, upsert_cmg)

DDL = """
CREATE TABLE IF NOT EXISTS costo_marginal_online_min (
    id           SERIAL PRIMARY KEY,
    barra_transf TEXT NOT NULL,
    barra_info   TEXT,
    fecha_minuto TEXT NOT NULL,
    cmg_usd_mwh  NUMERIC,
    cmg_clp_kwh  NUMERIC,
    version      TEXT,
    UNIQUE (barra_transf, fecha_minuto)
);
CREATE INDEX IF NOT EXISTS idx_cmg_min_fm ON costo_marginal_online_min (fecha_minuto);
ALTER TABLE costo_marginal_online_min ENABLE ROW LEVEL SECURITY;
"""


def main():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print("Creando tabla costo_marginal_online_min...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    print("Tabla lista (RLS activado: service_role/postgres la ignoran).")

    hoy = date.today()
    for d in range(dias - 1, -1, -1):
        fecha = (hoy - timedelta(days=d)).strftime("%Y-%m-%d")
        print(f"\n── Backfill CMG online 15 min {fecha}")
        try:
            regs = fetch_cmg_online_api(fecha, fecha)
        except Exception as e:
            print(f"   fallo: {e}")
            continue
        n_min, _ = upsert_cmg_online_min(regs)
        n_h, a_h = upsert_cmg(agregar_cmg_horario(regs))
        ceros = sum(1 for r in regs if r["cmg_usd_mwh"] == 0)
        print(f"   {len(regs)} puntos ({ceros} en 0) · {n_min} nuevos 15 min · "
              f"horario: {n_h} nuevos / {a_h} actualizados")


if __name__ == "__main__":
    main()
