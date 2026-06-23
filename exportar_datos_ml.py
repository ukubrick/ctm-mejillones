"""
exportar_datos_ml.py — Exporta tablas de Supabase a CSV para ml_pruebas.py

Uso: python3 exportar_datos_ml.py

Genera en data/:
  cmg.csv, gen_real.csv, gen_prog.csv
"""

import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

OUT_DIR = "data"
os.makedirs(OUT_DIR, exist_ok=True)

print("Conectando a Supabase...")
conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=30)
print("Conectado.\n")

queries = {
    "cmg.csv": """
        SELECT fecha_hora, barra_transf, cmg_usd_mwh
        FROM costo_marginal
        WHERE barra_transf IN ('CRUCERO_______220', 'TARAPACA______220')
        ORDER BY fecha_hora
    """,
    "gen_real.csv": """
        SELECT unidad, fecha_hora, gen_real_mw, potencia_maxima
        FROM generacion_real
        ORDER BY fecha_hora
    """,
    "gen_prog.csv": """
        SELECT DISTINCT ON (unidad, fecha_hora)
            unidad, fecha_hora, gen_programada_mw
        FROM generacion_programada
        ORDER BY unidad, fecha_hora,
            CASE fuente WHEN 'CEN_PCP' THEN 0 ELSE 1 END
    """,
}

for filename, sql in queries.items():
    print(f"Exportando {filename}...", end=" ", flush=True)
    df = pd.read_sql(sql, conn)
    path = os.path.join(OUT_DIR, filename)
    df.to_csv(path, index=False)
    print(f"{len(df):,} registros → {path}")

conn.close()
print("\nListo. Ahora ejecuta: python3 ml_pruebas.py")
