"""
migracion_sscc_programado.py — Crea la tabla `sscc_programado` (SSCC programado
en el PCP: provisión MW por unidad y tipo de servicio) y hace un backfill día
por día desde /servicios-complementarios-programados-pcp/v4.

Motivo: el dashboard tenía el SSCC INSTRUIDO (Operaciones v1) y el DESEMPEÑO
CPF/CSF, pero no el PROGRAMADO — no se podía contrastar lo que el CEN programó
contra lo que instruyó ni contra la nota de desempeño.

Correr vía el workflow `migracion.yml`:
    python migracion_sscc_programado.py [DIAS_ATRAS]   (default 1)

⚠️ CADA DÍA CUESTA ~21 min (121 páginas de 5000 y la API estrangula a ~10 s/pág;
el endpoint ignora idCentral, hay que paginar el sistema completo). El workflow
`migracion.yml` tiene timeout de **30 min** → por esta vía cabe UN solo día
(MAX_DIAS=1). Para acumular historia, disparar varias veces
`adquisicion_sscc_prog.yml` (timeout 60), que sí admite 2 días por corrida.
"""
import sys
from datetime import date, timedelta

from Adquisicion import (get_conn, fetch_sscc_programado_pcp,
                         upsert_sscc_programado)

DDL = """
CREATE TABLE IF NOT EXISTS sscc_programado (
    id             SERIAL PRIMARY KEY,
    unidad         TEXT NOT NULL,
    tipo_servicio  TEXT NOT NULL,
    fecha_hora     TEXT NOT NULL,
    hora           INTEGER,
    provision_mw   NUMERIC,
    barra          TEXT,
    llave_sscc     TEXT,
    fecha_programa TEXT,
    UNIQUE (unidad, tipo_servicio, fecha_hora)
);
CREATE INDEX IF NOT EXISTS idx_sscc_prog_fh ON sscc_programado (fecha_hora);
ALTER TABLE sscc_programado ENABLE ROW LEVEL SECURITY;
"""


# El workflow migracion.yml corta a los 30 min y cada día son ~21 → cabe uno solo.
MAX_DIAS = 1


def main():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if dias > MAX_DIAS:
        print(f"[AVISO] DIAS_ATRAS={dias} no cabe en el timeout de 30 min de "
              f"migracion.yml (~21 min/día) — se acota a {MAX_DIAS}. "
              f"Para más historia usar adquisicion_sscc_prog.yml.")
        dias = MAX_DIAS
    print("Creando tabla sscc_programado...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    print("Tabla lista (RLS activado: service_role/postgres la ignoran).")

    hoy = date.today()
    for d in range(dias - 1, -1, -1):
        fecha = (hoy - timedelta(days=d)).strftime("%Y-%m-%d")
        print(f"\n-- Backfill SSCC programado {fecha} (~21 min)")
        try:
            regs = fetch_sscc_programado_pcp(fecha)
        except Exception as e:
            print(f"   fallo: {e.__class__.__name__}")
            continue
        n, a = upsert_sscc_programado(regs)
        con_mw = sum(1 for r in regs if (r.get("provision_mw") or 0) > 0)
        print(f"   {len(regs)} filas ({con_mw} con provision > 0) · "
              f"{n} nuevas / {a} actualizadas")


if __name__ == "__main__":
    main()
