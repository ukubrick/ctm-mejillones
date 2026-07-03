"""
migracion_rls.py — Habilita Row-Level Security (RLS) en todas las tablas públicas.

Por qué es seguro para este proyecto:
  · El dashboard accede por REST con la **service_role** key, que pertenece al rol
    `bypassrls` → ignora RLS por completo (sigue leyendo/escribiendo normal).
  · La adquisición (Adquisicion.py) conecta por psycopg2 como `postgres` (dueño de
    las tablas) → también ignora RLS mientras no se use FORCE ROW LEVEL SECURITY.
  · Con RLS activado y SIN políticas, los roles `anon`/`authenticated` (la key
    pública) quedan bloqueados → si la key anon se filtrara, nadie podría leer los
    datos. Ese es exactamente el objetivo de seguridad.

⚠️ ANTES DE CORRER: verifica que producción (Streamlit Cloud → Secrets) use la
`service_role` key en SUPABASE_KEY, NO la `anon`. Si usa anon, RLS romperá las
lecturas del dashboard.

Uso (desde Actions → workflow "Migracion puntual", el 5432 no está bloqueado allí):
    python migracion_rls.py
"""
from Adquisicion import get_conn, log

# Activa RLS en cada tabla base del esquema public (idempotente).
_SQL = """
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', r.tablename);
    RAISE NOTICE 'RLS habilitado en %', r.tablename;
  END LOOP;
END $$;
"""


def run():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_SQL)
            # Reporta el estado final para dejar constancia en el log del job.
            cur.execute(
                "SELECT tablename, rowsecurity FROM pg_tables "
                "WHERE schemaname='public' ORDER BY tablename;")
            filas = cur.fetchall()
        conn.commit()
    log.info("Estado RLS por tabla (public):")
    for t, rls in filas:
        log.info(f"  {'✅' if rls else '❌'}  {t}: rowsecurity={rls}")
    print(f"OK · RLS habilitado en {sum(1 for _, r in filas if r)}/{len(filas)} tablas.")


if __name__ == "__main__":
    run()
