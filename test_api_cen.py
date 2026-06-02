"""
test_api_cen.py  v12 — Tests finales de diagnóstico
"""
import requests, json, time
from datetime import date, timedelta

KEY_SIP       = "10eb683f68b8af18378a8e11727ea6ea"        # 10eb683f...
KEY_OPERACION = "38215ca9ca6d2b1b96666df29164bc5b"  # 38215ca9...

BASE_SIP = "https://sipub.api.coordinador.cl"
BASE_OP  = "https://operacion.api.coordinador.cl:443"
hoy      = date.today()
SEP      = "═" * 65

if "PEGA_KEY" in KEY_SIP:
    print("\n⚠️  Configura las keys\n"); exit(1)

def get(base, endpoint, key, params_extra={}, label=""):
    url    = f"{base}/{endpoint}"
    params = {"user_key": key, **params_extra}
    label  = label or endpoint
    try:
        r = requests.get(url, params=params, timeout=20)
        regs, body = [], {}
        if r.status_code == 200:
            body = r.json()
            regs = body.get("data", body.get("content",
                   body if isinstance(body, list) else []))
        return r.status_code, regs, body
    except Exception as e:
        return 0, [], {}

# ══════════════════════════════════════════════════════════════
# TEST 1 — deviation con varias fechas (puede tener rezago)
# ══════════════════════════════════════════════════════════════
print(SEP)
print("  TEST 1 — deviation con distintas fechas")
print(SEP)

for dias in [1, 3, 7, 14, 30]:
    fecha = (hoy - timedelta(days=dias)).strftime("%Y-%m-%d")
    status, regs, body = get(BASE_OP, "reportes/v3/deviation",
                             KEY_OPERACION, {"date": fecha})
    if status == 200 and (regs or body):
        n = len(regs) if isinstance(regs, list) else "obj"
        print(f"  ✅ date={fecha}: HTTP 200 — {n} registros")
        data = regs if isinstance(regs, list) and regs else (
               body.get("content", []) if isinstance(body, dict) else [])
        if data:
            print(f"     Columnas: {list(data[0].keys())}")
            hits = [d for d in data if any(x in str(d).upper()
                    for x in ["ANGAMOS","COCHRANE","TERMICA","TER"])]
            print(f"     Total: {len(data)} | CTM: {len(hits)}")
            if hits:
                print(f"     ✅ Ejemplo CTM:\n{json.dumps(hits[0], ensure_ascii=False, indent=2)}")
            else:
                print(f"     Ejemplo:\n{json.dumps(data[0], ensure_ascii=False, indent=2)[:400]}")
        elif isinstance(body, dict):
            print(f"     Body: {json.dumps(body, ensure_ascii=False, indent=2)[:400]}")
        break  # encontramos datos, salir
    else:
        print(f"  ❌ date={fecha}: HTTP {status}")
    time.sleep(0.3)


# ══════════════════════════════════════════════════════════════
# TEST 2 — Programada PCP con filtros de búsqueda por nombre
# ══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  TEST 2 — Programada PCP: filtros de nombre central")
print(SEP)

ayer = (hoy - timedelta(days=1)).strftime("%Y-%m-%d")

filtros_nombre = [
    {"nombre": "ANGAMOS"},
    {"central": "TER ANGAMOS"},
    {"nombreCentral": "ANGAMOS"},
    {"llave_gen": "ANG1"},
    {"search": "ANGAMOS"},
    {"q": "ANGAMOS"},
]

for f in filtros_nombre:
    status, regs, body = get(BASE_SIP,
        "generacion-programada-pcp/v4/findByDate",
        KEY_SIP,
        {"startDate": ayer, "endDate": ayer, **f})
    total = body.get("totalPages", 0) if isinstance(body, dict) else 0
    if status == 200 and regs:
        hits = [r for r in regs if any(x in str(r).upper()
                for x in ["ANGAMOS","COCHRANE"])]
        print(f"  ✅ Filtro {f}: {len(regs)} regs | CTM: {len(hits)} | totalPages={total}")
        if hits:
            print(f"     {json.dumps(hits[0], ensure_ascii=False, indent=2)[:300]}")
    else:
        print(f"  Filtro {f}: HTTP {status} | totalPages={total} (filtro ignorado)")
    time.sleep(0.2)


# ══════════════════════════════════════════════════════════════
# TEST 3 — Reducción generación (plan Operación)
# ══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  TEST 3 — reduccion/v1/generacion (Operación)")
print(SEP)

status, regs, body = get(BASE_OP, "reduccion/v1/generacion",
    KEY_OPERACION, {"startDate": ayer, "endDate": ayer})
print(f"  HTTP {status}")
if status == 200 and (regs or body):
    data = regs if isinstance(regs,list) and regs else body
    if isinstance(data, list) and data:
        print(f"  Columnas: {list(data[0].keys())}")
        print(f"  Ejemplo : {json.dumps(data[0], ensure_ascii=False, indent=2)[:400]}")
    else:
        print(f"  Body: {json.dumps(data, ensure_ascii=False, indent=2)[:400]}")
else:
    print(f"  {str(body)[:200]}")


# ══════════════════════════════════════════════════════════════
# DIAGNÓSTICO FINAL
# ══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  DIAGNÓSTICO FINAL — Resumen de acceso API CEN")
print(SEP)

resultados = {
    "Gen. real ANG1/2 CCR1/2 (SIP)":     "✅ DISPONIBLE — 24 reg/día/unidad",
    "Prog. PCP Angamos/Cochrane (SIP)":   "❌ No filtrable por central térmica",
    "CMG Nodo Crucero (SIP)":             "❌ Solo ex-SIC, norte no incluido",
    "Reportes agregados (Operación)":     "✅ Totales por tipo (no por unidad)",
    "Deviation por unidad (Operación)":   "⏳ Por confirmar con fechas antiguas",
}

for k, v in resultados.items():
    print(f"  {v[:2]}  {k}")
    print(f"       {v}")

print(f"""
  CONCLUSIÓN:
  ─────────────────────────────────────────────────────────
  La única fuente confiable y granular por unidad (ANG1/2,
  CCR1/2) via API CEN es la GENERACIÓN REAL (SIP).

  Para la programada y el CMG Crucero, las opciones son:
  A) Ingreso manual desde operadores (bitácora/Google Sheets)
  B) Conexión directa al SCADA/MIMS de AES Andes
  C) Scraping del portal web del CEN (opcionalmente)

  Recomendación: construir dashboard con real desde API CEN
  + programada desde Google Sheets existente (manual/SCADA)
  + CMG como campo opcional cuando esté disponible.
  ─────────────────────────────────────────────────────────
""")
print(f"{SEP}\n")