"""
migracion_origen_real.py — Añade la columna `origen` a generacion_real.

Marca el origen de cada registro de generación real. Las filas con
origen='MANUAL' (ingreso manual desde el dashboard) NO son sobreescritas por la
adquisición automática (ver guard en Adquisicion.upsert_generacion_real), de modo
que un reemplazo manual prevalece.

Uso (con DB accesible / desde GitHub Actions vía migracion.yml):
    python migracion_origen_real.py
"""
from Adquisicion import get_conn


def run():
    sql = "ALTER TABLE generacion_real ADD COLUMN IF NOT EXISTS origen text;"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("OK · columna 'origen' asegurada en generacion_real.")


if __name__ == "__main__":
    run()
