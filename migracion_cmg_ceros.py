"""
migracion_cmg_ceros.py — Repone en `costo_marginal` las horas de CMG = 0 que el
feed S3 nunca emitió, tomándolas del CMG real liquidado.

EL PROBLEMA
El feed S3 que alimentó `costo_marginal` hasta el 2026-07-27 no publicaba una
fila con valor 0 cuando la barra se desacoplaba: sencillamente NO emitía la hora
(regla 27). O sea, en el histórico anterior a esa fecha los desacoples no figuran
como cero, figuran como AUSENCIA. Eso sesga hacia arriba todo lo que promedie el
CMG (KPI «CMG promedio» de Estadísticas y de Costos, curva de duración de
precios, heatmap hora×día, elasticidad precio-demanda, correlación gen–CMG).

Medido el 2026-08-01 sobre una ventana de 30 días: el CMG medio de Crucero cae de
95,8 a 85,6 USD/MWh al reponer las horas faltantes — un sesgo de +10,7%.

LA CORRECCIÓN
`costo_marginal_real` (CMG liquidado del CEN) nunca filtró ceros. Para cada hora
que falta en la malla horaria del online y que sí está liquidada, se repone la
fila. Verificado antes de escribir esto: de las 272 horas recuperables en Crucero
y Tarapacá, el valor liquidado máximo es 0,00 — son TODAS ceros, así que no se
está mezclando el precio de dos fuentes distintas, se está reponiendo un cero que
ya sabíamos que era cero. Aun así el script solo repone si el liquidado es
<= UMBRAL_CERO, para que siga siendo cierto si se corre más adelante.

Las filas repuestas quedan marcadas con `origen = 'LIQUIDADO'` (la columna se
crea idempotente; las existentes quedan como 'CEN_ONLINE'), de modo que siempre
se pueda distinguir el dato online del reconstruido.

USO — correr vía el workflow `migracion.yml` (el 5432 no responde desde redes
locales, regla 10):
    python migracion_cmg_ceros.py           -> SIMULACIÓN (no escribe nada)
    python migracion_cmg_ceros.py apply     -> aplica los cambios

Idempotente: solo inserta horas ausentes, así que correrlo dos veces no duplica.
"""
import sys

from Adquisicion import get_conn

UMBRAL_CERO = 1.0          # USD/MWh: por debajo de esto la barra está desacoplada

DDL = """
ALTER TABLE costo_marginal
    ADD COLUMN IF NOT EXISTS origen TEXT NOT NULL DEFAULT 'CEN_ONLINE';
"""

# Horas que faltan en la malla del online y sí están liquidadas como cero.
# Se acota a [primera hora del online de esa barra, última], para no inventar
# histórico anterior a que la barra existiera en el feed.
SQL_CANDIDATAS = """
WITH rango AS (
    SELECT barra_transf,
           MIN(fecha_hora::timestamp) AS desde,
           MAX(fecha_hora::timestamp) AS hasta
    FROM costo_marginal
    GROUP BY barra_transf
)
SELECT r.barra_transf,
       r.fecha_hora::timestamp AS fh,
       r.cmg_usd_mwh
FROM costo_marginal_real r
JOIN rango g ON g.barra_transf = r.barra_transf
WHERE r.cmg_usd_mwh <= %s
  AND r.fecha_hora::timestamp BETWEEN g.desde AND g.hasta
  AND NOT EXISTS (
        SELECT 1 FROM costo_marginal o
        WHERE o.barra_transf = r.barra_transf
          AND o.fecha_hora::timestamp = r.fecha_hora::timestamp
  )
ORDER BY r.barra_transf, fh
"""


def _tipo_fecha_hora(cur) -> str:
    """`costo_marginal.fecha_hora` es TEXT en unas tablas y timestamp en otras.

    Importa: si es TEXT hay que escribir con el MISMO formato que ya usa la tabla
    ('YYYY-MM-DDTHH:MM:SS', con la T), o la UNIQUE (barra_transf, fecha_hora) no
    detecta el duplicado y los loaders que comparan strings se confunden."""
    cur.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_name = 'costo_marginal' AND column_name = 'fecha_hora'
    """)
    fila = cur.fetchone()
    return (fila[0] if fila else "text").lower()


def main():
    aplicar = len(sys.argv) > 1 and sys.argv[1].lower() in ("apply", "aplicar", "si")
    modo = "APLICAR" if aplicar else "SIMULACIÓN (no escribe nada)"
    print(f"=== Reposición de CMG = 0 faltantes · modo {modo} ===\n")

    with get_conn() as conn:
        with conn.cursor() as cur:
            tipo = _tipo_fecha_hora(cur)
            print(f"costo_marginal.fecha_hora es de tipo: {tipo}")
            es_texto = tipo.startswith(("text", "character", "varchar"))

            cur.execute(SQL_CANDIDATAS, (UMBRAL_CERO,))
            cands = cur.fetchall()

            if not cands:
                print("\nNo hay horas que reponer: el online ya está completo.")
                return

            # Resumen por barra ANTES de tocar nada.
            print(f"\nHoras a reponer: {len(cands)}")
            por_barra: dict[str, list] = {}
            for barra, fh, cmg in cands:
                por_barra.setdefault(barra, []).append((fh, float(cmg)))
            for barra, filas in sorted(por_barra.items()):
                peor = max(v for _, v in filas)
                print(f"  {barra}: {len(filas):4} horas · "
                      f"{filas[0][0]:%d/%m} → {filas[-1][0]:%d/%m} · "
                      f"valor liquidado máximo {peor:.2f} USD/MWh")
                if peor > 0:
                    print("     ojo: hay valores > 0 — se reponen igual porque están "
                          f"bajo el umbral de desacople ({UMBRAL_CERO} USD/MWh).")

            # Efecto sobre el promedio, que es el KPI que se estaba leyendo mal.
            cur.execute("""
                SELECT barra_transf, AVG(cmg_usd_mwh)::numeric(10,2), COUNT(*)
                FROM costo_marginal GROUP BY barra_transf ORDER BY barra_transf
            """)
            print("\nEfecto sobre el CMG medio de cada barra (todo el histórico):")
            for barra, prom, n in cur.fetchall():
                nuevas = por_barra.get(barra, [])
                if not nuevas:
                    print(f"  {barra}: {prom} USD/MWh · sin cambios")
                    continue
                suma_nueva = sum(v for _, v in nuevas)
                prom2 = (float(prom) * n + suma_nueva) / (n + len(nuevas))
                print(f"  {barra}: {float(prom):.2f} → {prom2:.2f} USD/MWh "
                      f"({100*(prom2-float(prom))/float(prom):+.1f}%, "
                      f"{n} → {n+len(nuevas)} horas)")

            if not aplicar:
                print("\nSimulación terminada. Para aplicar:")
                print("    migracion.yml → script=migracion_cmg_ceros.py · arg=apply")
                return

            print("\nCreando columna `origen` si no existe...")
            cur.execute(DDL)

            if es_texto:
                ins = """
                    INSERT INTO costo_marginal
                        (barra_transf, fecha_hora, hora, minuto, cmg_usd_mwh,
                         version, origen)
                    VALUES (%s, to_char(%s::timestamp, 'YYYY-MM-DD"T"HH24:MI:SS'),
                            %s, 0, %s, 'REAL-DEF', 'LIQUIDADO')
                    ON CONFLICT (barra_transf, fecha_hora) DO NOTHING
                """
            else:
                ins = """
                    INSERT INTO costo_marginal
                        (barra_transf, fecha_hora, hora, minuto, cmg_usd_mwh,
                         version, origen)
                    VALUES (%s, %s, %s, 0, %s, 'REAL-DEF', 'LIQUIDADO')
                    ON CONFLICT (barra_transf, fecha_hora) DO NOTHING
                """

            n = 0
            for barra, fh, cmg in cands:
                # Hora en convención CEN 1-24 (regla 3).
                cur.execute(ins, (barra, fh, fh.hour + 1, float(cmg)))
                n += cur.rowcount
        conn.commit()

    print(f"\nListo: {n} filas repuestas y marcadas con origen='LIQUIDADO'.")
    print("En el dashboard, usar «↻ Actualizar datos» para vaciar el caché (regla 37).")


if __name__ == "__main__":
    main()
