"""
probe_operativos.py — Explora el endpoint /operativos/v1/estados y sub-rutas
para encontrar el estado operativo actual de unidades Angamos/Cochrane.
Uso: python probe_operativos.py
"""
import os, requests, json
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()
KEY_OPS = os.getenv("CEN_OPS_KEY", "")
KEY_SIP = os.getenv("CEN_USER_KEY", "")
if not KEY_OPS:
    print("CEN_OPS_KEY no encontrada en .env"); exit(1)

BASE_OPS = "https://operacion.api.coordinador.cl"
BASE_SIP = "https://sipub.api.coordinador.cl"

# IDs conocidos
ID_ANGAMOS  = 377
ID_COCHRANE = 379
ID_UNIDADES = [1965, 1966, 1967, 1968]  # ANG1, ANG2, CCR1, CCR2

end_date   = date.today().strftime("%Y-%m-%d")
start_date = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")

def get(base, path, key, params=None):
    p = {"user_key": key, **(params or {})}
    try:
        r = requests.get(f"{base}/{path}", params=p, timeout=20)
        return r
    except Exception as e:
        print(f"  ERROR red: {e}")
        return None

def probe(label, base, path, key, params=None):
    print(f"\n{'─'*60}")
    print(f"  {label}")
    print(f"  GET {base}/{path}")
    if params:
        print(f"  params: {params}")
    r = get(base, path, key, params)
    if r is None: return
    print(f"  HTTP {r.status_code}")
    try:
        body = r.json()
        print(f"  Body: {json.dumps(body, ensure_ascii=False)[:800]}")
    except Exception:
        print(f"  Body (texto): {r.text[:400]}")

# ── 1. Catálogo de estados operativos ────────────────────────
probe("Catálogo estados operativos",
      BASE_OPS, "operativos/v1/estados", KEY_OPS)

# ── 2. Sub-rutas de módulos ───────────────────────────────────
for modulo in ["desconexion_intervencion", "informe_fallas", "limitaciones"]:
    probe(f"Módulo: {modulo}",
          BASE_OPS, f"operativos/v1/{modulo}", KEY_OPS)

# ── 3. Intentar filtrar por central/unidad ────────────────────
probe("Estados por idCentral=377 (Angamos)",
      BASE_OPS, "operativos/v1/estados", KEY_OPS,
      {"idCentral": ID_ANGAMOS})

probe("Estados por idCentral=379 (Cochrane)",
      BASE_OPS, "operativos/v1/estados", KEY_OPS,
      {"idCentral": ID_COCHRANE})

probe("Estados activos únicamente",
      BASE_OPS, "operativos/v1/estados", KEY_OPS,
      {"active": "true"})

# ── 4. Rutas alternativas con fecha ──────────────────────────
for path in [
    "operativos/v1/findByDate",
    "operativos/v1/estados/findByDate",
    "estados-operativos/v1/findByDate",
    "estados-operativos/v4/findByDate",
    "desconexion-intervencion/v4/findByDate",
    "informe-fallas/v4/findByDate",
]:
    probe(f"Ruta alternativa: {path}",
          BASE_OPS, path, KEY_OPS,
          {"startDate": start_date, "endDate": end_date, "page": 0, "limit": 10})

# ── 5. Mismas rutas en SIP ────────────────────────────────────
for path in [
    "desconexion-intervencion/v4/findByDate",
    "informe-fallas/v4/findByDate",
    "estados-operativos/v4/findByDate",
]:
    probe(f"SIP — {path}",
          BASE_SIP, path, KEY_SIP,
          {"startDate": start_date, "endDate": end_date, "page": 0, "limit": 10})

print(f"\n{'='*60}\n  Fin probe operativos\n{'='*60}")
