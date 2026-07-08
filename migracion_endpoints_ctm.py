"""
migracion_endpoints_ctm.py — Integración de endpoints CEN nuevos (2026-07-08).

1. `costo_marginal_programado`: agrega la columna `fuente` (CEN_PID/CEN_PCP) y
   cambia la llave única a (barra, fecha_hora, fuente). Las filas existentes
   quedan como CEN_PID (era la única fuente hasta ahora).
2. Crea las tablas nuevas: `mantenimiento_mayor`, `demanda_neta`,
   `mix_generacion_diaria`, `desempeno_sscc` (con RLS habilitado).
3. Backfill inicial:
   · CMG real en las 4 barras (incluye ANGAMOS_______220 / COCHRANE______220)
   · CMG programado PCP (7 días) y PID (3 días) en las 4 barras
   · Demanda neta (120 días — histórico de entrenamiento para el forecast ML)
   · Mix diario por tecnología (60 días)
   · Mantenimiento mayor CTM (60 días de publicaciones)
   El desempeño SSCC (CPF/CSF) NO se backfillea aquí: lo puebla la corrida
   diaria vía dias_faltantes_desempeno() (sondea hasta 120 días faltantes/día).

Ejecutar UNA vez vía el workflow `migracion.yml` (Actions no bloquea el 5432):
    python migracion_endpoints_ctm.py
"""
from datetime import date, timedelta

from Adquisicion import (
    get_conn,
    fetch_cmg_real, upsert_cmg_real,
    fetch_cmg_programado, upsert_cmg_programado,
    fetch_demanda_neta, upsert_demanda_neta,
    fetch_mix_diario, upsert_mix_diario,
    fetch_mantenimiento_mayor, upsert_mantenimiento_mayor,
)

DDL = """
ALTER TABLE costo_marginal_programado
    ADD COLUMN IF NOT EXISTS fuente TEXT NOT NULL DEFAULT 'CEN_PID';
ALTER TABLE costo_marginal_programado
    DROP CONSTRAINT IF EXISTS costo_marginal_programado_barra_fecha_hora_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cmg_prog_barra_fh_fuente
    ON costo_marginal_programado (barra, fecha_hora, fuente);

CREATE TABLE IF NOT EXISTS mantenimiento_mayor (
    id                     SERIAL PRIMARY KEY,
    correlativo            TEXT NOT NULL DEFAULT '',
    mantenimiento_nup      TEXT,
    nombre_instalacion     TEXT,
    nombre_sub_instalacion TEXT NOT NULL DEFAULT '',
    tipo_instalacion       TEXT,
    elemento_instalacion   TEXT,
    descripcion_trabajo    TEXT,
    estado                 TEXT,
    riesgo                 TEXT,
    postergable            TEXT,
    consumos_afectados     TEXT,
    fecha_inicio_programa  TEXT NOT NULL DEFAULT '',
    fecha_fin_programa     TEXT,
    fecha_inicio_real      TEXT,
    fecha_termino_real     TEXT,
    fecha_dato             TEXT,
    UNIQUE (correlativo, nombre_sub_instalacion, fecha_inicio_programa)
);
CREATE INDEX IF NOT EXISTS idx_mant_mayor_ini ON mantenimiento_mayor (fecha_inicio_programa);

CREATE TABLE IF NOT EXISTS demanda_neta (
    id               SERIAL PRIMARY KEY,
    fecha_hora       TEXT NOT NULL UNIQUE,
    hora             INTEGER,
    gen_bruta_mwh    NUMERIC,
    gen_erv_mwh      NUMERIC,
    cons_propio_mwh  NUMERIC,
    demanda_neta_mwh NUMERIC
);

CREATE TABLE IF NOT EXISTS mix_generacion_diaria (
    id          SERIAL PRIMARY KEY,
    fecha       TEXT NOT NULL,
    tecnologia  TEXT NOT NULL,
    energia_mwh NUMERIC,
    UNIQUE (fecha, tecnologia)
);

CREATE TABLE IF NOT EXISTS desempeno_sscc (
    id         SERIAL PRIMARY KEY,
    unidad     TEXT NOT NULL,
    tipo       TEXT NOT NULL,
    fecha_hora TEXT NOT NULL,
    hora       INTEGER,
    fdis       NUMERIC,
    desempeno  NUMERIC,
    factor     NUMERIC,
    detalle    TEXT,
    UNIQUE (unidad, tipo, fecha_hora)
);
CREATE INDEX IF NOT EXISTS idx_desemp_sscc_fh ON desempeno_sscc (fecha_hora);

ALTER TABLE mantenimiento_mayor    ENABLE ROW LEVEL SECURITY;
ALTER TABLE demanda_neta           ENABLE ROW LEVEL SECURITY;
ALTER TABLE mix_generacion_diaria  ENABLE ROW LEVEL SECURITY;
ALTER TABLE desempeno_sscc         ENABLE ROW LEVEL SECURITY;
"""


def main():
    print("1/6 · DDL (columna fuente + tablas nuevas + RLS)...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    print("   DDL listo.")

    hoy = date.today()

    print("2/6 · Backfill CMG real 4 barras (rezago liquidación)...")
    start = (hoy - timedelta(days=21)).strftime("%Y-%m-%d")
    end   = (hoy - timedelta(days=5)).strftime("%Y-%m-%d")
    regs = fetch_cmg_real(start, end)
    n, a = upsert_cmg_real(regs)
    print(f"   CMG real: {n} nuevos, {a} actualizados.")

    print("3/6 · Backfill CMG programado PCP (7 días)...")
    regs = fetch_cmg_programado((hoy - timedelta(days=7)).strftime("%Y-%m-%d"),
                                (hoy + timedelta(days=1)).strftime("%Y-%m-%d"),
                                fuente="CEN_PCP")
    n, a = upsert_cmg_programado(regs)
    print(f"   CMG PCP: {n} nuevos, {a} actualizados.")

    print("4/6 · Backfill CMG programado PID (3 días, incluye barras nuevas)...")
    regs = fetch_cmg_programado((hoy - timedelta(days=3)).strftime("%Y-%m-%d"),
                                (hoy + timedelta(days=1)).strftime("%Y-%m-%d"),
                                fuente="CEN_PID")
    n, a = upsert_cmg_programado(regs)
    print(f"   CMG PID: {n} nuevos, {a} actualizados.")

    print("5/6 · Backfill demanda neta (120 días) + mantenimiento mayor (60 días)...")
    regs = fetch_demanda_neta((hoy - timedelta(days=120)).strftime("%Y-%m-%d"),
                              hoy.strftime("%Y-%m-%d"))
    n, a = upsert_demanda_neta(regs)
    print(f"   Demanda neta: {n} nuevos, {a} actualizados.")
    regs = fetch_mantenimiento_mayor((hoy - timedelta(days=60)).strftime("%Y-%m-%d"),
                                     hoy.strftime("%Y-%m-%d"))
    n, a = upsert_mantenimiento_mayor(regs)
    print(f"   Mantenimiento mayor: {n} nuevos, {a} actualizados.")

    print("6/6 · Backfill mix diario (60 días)...")
    tot = 0
    for d in range(60, 0, -1):
        f = (hoy - timedelta(days=d)).strftime("%Y-%m-%d")
        n, a = upsert_mix_diario(fetch_mix_diario(f))
        tot += n + a
    print(f"   Mix diario: {tot} registros.")

    print("Migración completa. El desempeño SSCC lo poblará la corrida diaria "
          "(dias_faltantes_desempeno).")


if __name__ == "__main__":
    main()
