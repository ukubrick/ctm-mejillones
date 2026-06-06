"""
check_cmg.py — Diagnóstico rápido:
  · Qué llave_gen / configuracion devuelve el PCP para Angamos (377) y Cochrane (379)
  · Qué nodos CMG están en el JSON S3

Uso: python check_cmg.py
"""
import os, requests, json
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("CEN_USER_KEY", "")
if not KEY:
    print("❌  CEN_USER_KEY no encontrada en .env"); exit(1)

BASE = "https://sipub.api.coordinador.cl"
ayer = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

print(f"\n{'='*60}")
print(f"  TEST 1 — Gen. programada PCP · {ayer}")
print(f"{'='*60}")

r = requests.get(
    f"{BASE}/generacion-programada-pcp/v4/findByDate",
    params={"user_key": KEY, "startDate": ayer, "endDate": ayer, "page": 0, "limit": 5000},
    timeout=30,
)
print(f"  HTTP {r.status_code}")

if r.status_code == 200:
    body = r.json()
    data = body.get("data", [])
    total_pages = body.get("totalPages", "?")
    print(f"  Registros pag.0: {len(data)} | totalPages: {total_pages}")

    # Filtrar solo Angamos (377) y Cochrane (379)
    hits = [d for d in data if d.get("id_central") in {377, 379, "377", "379"}]
    print(f"  Registros ANG/CCR: {len(hits)}")

    if hits:
        print("\n  Valores unicos de llave_gen para id_central 377/379:")
        for l in sorted({h.get("llave_gen", "") for h in hits}):
            print(f"    · '{l}'")

        print("\n  Valores unicos de configuracion:")
        for c in sorted({h.get("configuracion", "") for h in hits}):
            print(f"    · '{c}'")

        print("\n  Valores unicos de central:")
        for c in sorted({h.get("central", "") for h in hits}):
            print(f"    · '{c}'")

        print("\n  Ejemplo completo del primer registro ANG/CCR:")
        print(json.dumps(hits[0], ensure_ascii=False, indent=2))
    else:
        print("\n  AVISO: No se encontraron registros con id_central 377 o 379 en pag.0")
        if data:
            ids_muestra = list({d.get("id_central") for d in data})[:5]
            print(f"  Ejemplo id_central disponibles (primeros 5): {ids_muestra}")
            print("\n  Ejemplo primer registro (estructura del endpoint):")
            print(json.dumps(data[0], ensure_ascii=False, indent=2))
else:
    print(f"  Body: {r.text[:300]}")


print(f"\n{'='*60}")
print("  TEST 2 — Nodos CMG en JSON S3")
print(f"{'='*60}")

s3_url = ("https://cen-template-graph-pweb-prod.s3.us-east-1.amazonaws.com"
          "/CMG-online/costo-marginal-online.json")
r2 = requests.get(s3_url, headers={"User-Agent": "Mozilla/5.0 (compatible)"}, timeout=15)
print(f"  HTTP {r2.status_code}")

if r2.status_code == 200:
    body2 = r2.json()
    nodos = body2.get("data", [])
    print(f"  Total nodos: {len(nodos)}")
    print("\n  Nombres exactos de nodos disponibles:")
    for n in nodos:
        print(f"    · '{n['name']}'")
else:
    print(f"  Error: {r2.text[:200]}")

print()
