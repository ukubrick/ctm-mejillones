"""
test_scraping_cmg.py  v3
────────────────────────────────────────────────────────────────
Objetivo:
  1. Fetch costo-marginal-online.json desde S3 (nombre confirmado)
  2. Explorar iframes Qlik de costos-marginales
  3. Verificar si Crucero está en los datos
────────────────────────────────────────────────────────────────
"""
import requests
from bs4 import BeautifulSoup
import re, json

SEP = "═" * 65

# Headers simulando el browser desde el sitio del CEN
HEADERS_S3 = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Referer":         "https://cen-template-graph-pweb-prod.s3.us-east-1.amazonaws.com/CMG-online/cmg_chart.html",
    "Origin":          "https://www.coordinador.cl",
    "Accept":          "application/json, */*",
}

HEADERS_WEB = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Referer":         "https://www.coordinador.cl/costos-marginales/",
    "Accept":          "text/html,application/xhtml+xml,*/*",
}

S3_BASE   = "https://cen-template-graph-pweb-prod.s3.us-east-1.amazonaws.com/CMG-online"
QAP_BASE  = "https://qap-prd.coordinador.cl/ext/extensions"


# ══════════════════════════════════════════════════════════════
# PASO 1 — JSON S3 confirmado (costo-marginal-online.json)
# ══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  PASO 1 — costo-marginal-online.json (nombre confirmado en JS)")
print(SEP)

import time
url_json = f"{S3_BASE}/costo-marginal-online.json?t={int(time.time()*1000)}"
print(f"  URL: {url_json}")

r = requests.get(url_json, headers=HEADERS_S3, timeout=20)
print(f"  HTTP: {r.status_code}  |  {len(r.text):,} chars")

if r.status_code == 200:
    try:
        data = r.json()
        print(f"\n  ✅ JSON OBTENIDO")
        print(f"  Tipo: {type(data)}")
        if isinstance(data, dict):
            print(f"  Claves raíz: {list(data.keys())}")
        elif isinstance(data, list):
            print(f"  Lista: {len(data)} elementos")
            print(f"  Columnas 1er elem: {list(data[0].keys()) if data else '—'}")

        # Buscar Crucero
        txt = json.dumps(data, ensure_ascii=False)
        crucero = "crucero" in txt.lower()
        print(f"  Contiene 'crucero': {'✅ SÍ' if crucero else '❌ NO'}")
        print(f"\n  Preview (primeros 1500 chars):")
        print(txt[:1500])

        # Guardar para análisis
        with open("/tmp/cmg_data.json", "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n  Guardado en /tmp/cmg_data.json")

    except Exception as e:
        print(f"  No es JSON válido: {e}")
        print(f"  Respuesta: {r.text[:500]}")
else:
    print(f"  Respuesta: {r.text[:300]}")

    # Intentar sin timestamp y sin headers especiales
    print(f"\n  Reintentando sin timestamp y sin headers...")
    r2 = requests.get(f"{S3_BASE}/costo-marginal-online.json", timeout=20)
    print(f"  HTTP: {r2.status_code}")
    if r2.status_code == 200:
        print(f"  ✅ Funciona sin headers especiales!")
        print(f"  Preview: {r2.text[:500]}")
    else:
        print(f"  {r2.text[:200]}")


# ══════════════════════════════════════════════════════════════
# PASO 2 — Explorar iframes Qlik (mashup_cmg_real)
# ══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  PASO 2 — Iframes Qlik CMG")
print(SEP)

qlik_iframes = [
    ("CMG Real",            f"{QAP_BASE}/mashup_cmg_real/mashup_cmg_real.html"),
    ("CMG Descargable",     f"{QAP_BASE}/cmg_real_descargable/cmg_real_descargable.html"),
    ("CMG Online",          f"{QAP_BASE}/DEMO_mashup_cmg_en_linea/DEMO_mashup_cmg_en_linea.html"),
]

for nombre, url in qlik_iframes:
    print(f"\n  📡 {nombre}")
    print(f"     {url}")
    r = requests.get(url, headers=HEADERS_WEB, timeout=15)
    print(f"     HTTP {r.status_code}  |  {len(r.text):,} chars")
    if r.status_code == 200:
        html = r.text
        # Buscar Crucero y URLs de datos
        if "crucero" in html.lower():
            print(f"     ✅ CONTIENE 'crucero'")
            idx = html.lower().find("crucero")
            print(f"     Contexto: ...{html[max(0,idx-100):idx+200]}...")

        # Buscar fetch/XHR/data URLs
        fetches = re.findall(r'fetch\(["\`]([^"\`\)]+)["\`]', html)
        xhrs    = re.findall(r'\.open\(["\']GET["\'],\s*["\']([^"\']+)["\']', html)
        api_u   = re.findall(r'["\`](https?://[^"\`\s<>]{15,})["\`]', html)
        api_u   = [u for u in api_u if any(x in u.lower()
                   for x in ["api","json","data","cmg","qlik","sense"])]

        for f in fetches[:5]:
            print(f"     fetch: {f}")
        for x in xhrs[:5]:
            print(f"     XHR: {x}")
        for u in api_u[:10]:
            print(f"     API URL: {u}")

        # Buscar el host de Qlik Sense para la API
        qlik_hosts = re.findall(r'https?://([a-zA-Z0-9\-\.]+qlik[a-zA-Z0-9\-\.]*|[a-zA-Z0-9\-\.]+sense[a-zA-Z0-9\-\.]*)', html, re.I)
        if qlik_hosts:
            print(f"     Hosts Qlik: {set(qlik_hosts)}")


# ══════════════════════════════════════════════════════════════
# PASO 3 — Intentar API Qlik Sense directamente
#          (qap-prd.coordinador.cl puede tener API REST)
# ══════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  PASO 3 — API Qlik Sense en qap-prd.coordinador.cl")
print(SEP)

qlik_endpoints = [
    "https://qap-prd.coordinador.cl/api/v1/items",
    "https://qap-prd.coordinador.cl/qrs/app",
    "https://qap-prd.coordinador.cl/api/v1/apps",
]
for url in qlik_endpoints:
    r = requests.get(url, headers=HEADERS_WEB, timeout=10)
    print(f"  {url.split('/')[-1]:<20} HTTP {r.status_code}  {r.text[:100]}")

print(f"\n{SEP}\n")