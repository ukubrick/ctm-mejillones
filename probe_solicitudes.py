"""
probe_solicitudes.py — Explora el endpoint /solicitudes-trabajo/v4/findByDate
filtrando por empresa Angamos / Cochrane (AES Andes).

Notas confirmadas 2026-06-17:
- Parámetros: startDate, endDate (YYYY-MM-DD), page (base 1), limit
- Ventana corta (<=7 días) funciona. 30 días causa 502.
- El servidor CEN es intermitente — reintentar si da 502.
- Respuesta: {"data": [...], "totalPages": N, "page": N, "limit": N}

Uso: python probe_solicitudes.py
"""
import os, requests, json, time
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("CEN_USER_KEY", "")
if not KEY:
    print("CEN_USER_KEY no encontrada en .env"); exit(1)

BASE     = "https://sipub.api.coordinador.cl"
ENDPOINT = "solicitudes-trabajo/v4/findByDate"

end_date   = date.today().strftime("%Y-%m-%d")
start_date = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")

KEYWORDS = ["ANGAMOS", "COCHRANE", "AES"]

print(f"\nConsultando {ENDPOINT}")
print(f"Ventana: {start_date} → {end_date}\n")

# Primer request para conocer totalPages
params = {"user_key": KEY, "startDate": start_date, "endDate": end_date, "page": 1, "limit": 100}
for intento in range(3):
    try:
        r = requests.get(f"{BASE}/{ENDPOINT}", params=params, timeout=30)
        if r.status_code == 200:
            break
        print(f"  Intento {intento+1}: HTTP {r.status_code} — {r.text[:100]}")
        time.sleep(5)
    except Exception as e:
        print(f"  Intento {intento+1}: ERROR {e}")
        time.sleep(5)
else:
    print("Endpoint no disponible. Reintentar más tarde."); exit(0)

body        = r.json()
data        = body.get("data", [])
total_pages = int(body.get("totalPages", 1))
total_items = body.get("totalItems", "?")
print(f"Página 1/{total_pages}: {len(data)} registros | totalItems={total_items}")

todos, ang_ccr = list(data), []

# Paginar el resto
for page in range(2, total_pages + 1):
    params["page"] = page
    for intento in range(3):
        try:
            r = requests.get(f"{BASE}/{ENDPOINT}", params=params, timeout=30)
            if r.status_code == 200:
                break
            time.sleep(5)
        except Exception:
            time.sleep(5)
    else:
        print(f"  Página {page}: no disponible, saltando")
        continue
    data = r.json().get("data", [])
    todos.extend(data)
    print(f"  Página {page}/{total_pages}: {len(data)} registros")

# Filtrar ANG/CCR buscando en todos los campos de texto
for d in todos:
    texto = json.dumps(d).upper()
    if any(kw in texto for kw in KEYWORDS):
        ang_ccr.append(d)

print(f"\n{'='*60}")
print(f"Total registros descargados : {len(todos)}")
print(f"Registros Angamos/Cochrane  : {len(ang_ccr)}")
print(f"{'='*60}")

if ang_ccr:
    print("\n--- Primer registro ANG/CCR ---")
    print(json.dumps(ang_ccr[0], ensure_ascii=False, indent=2))
    print("\n--- Campos disponibles ---")
    campos = set()
    for d in ang_ccr: campos.update(d.keys())
    print(sorted(campos))
    print("\n--- Valores únicos por campo clave ---")
    for campo in ["empresa_nombre", "grupo_nombre", "status", "tipo_solicitud", "type"]:
        vals = sorted({str(h.get(campo, "")) for h in ang_ccr if h.get(campo)})
        if vals: print(f"  · {campo}: {vals[:10]}")
    print("\n--- Correlativos ---")
    correlativos = sorted({h.get("correlativo") for h in ang_ccr if h.get("correlativo")})
    print(f"  {correlativos[:20]}")
elif todos:
    print("\nNo se encontraron registros de Angamos/Cochrane.")
    print("Empresas únicas en muestra (pág 1):")
    empresas = sorted({d.get("empresa_nombre", "") for d in todos})
    print(f"  {empresas[:30]}")
    print("\n--- Primer registro del sistema ---")
    print(json.dumps(todos[0], ensure_ascii=False, indent=2))
else:
    print("\nSin datos.")

print(f"\n{'='*60}\n  Fin probe\n{'='*60}")
