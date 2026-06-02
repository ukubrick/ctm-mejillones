"""
test_cmg_crucero.py
Confirma el nombre exacto del nodo Crucero en el JSON S3
y muestra los últimos valores de CMG.
"""
import requests, json, time
from collections import defaultdict
from datetime import datetime

CMG_URL = ("https://cen-template-graph-pweb-prod.s3.us-east-1"
           ".amazonaws.com/CMG-online/costo-marginal-online.json")
HEADERS = {"Referer": "https://cen-template-graph-pweb-prod.s3.us-east-1"
                      ".amazonaws.com/CMG-online/cmg_chart.html"}

print("Fetching CMG JSON desde S3...")
r = requests.get(f"{CMG_URL}?t={int(time.time()*1000)}", headers=HEADERS, timeout=20)
print(f"HTTP {r.status_code}  |  {len(r.text):,} chars\n")

data  = r.json()
nodos = data["data"]
print(f"Total nodos: {len(nodos)}  |  Mantenimiento: {data['maintenance']}\n")

NORTE = ["crucero","mejo","angamo","toco","atacam","encuent","cardone","kimal"]
print("── Nodos del norte ─────────────────────────────")
for n in nodos:
    if any(x in n["name"].lower() for x in NORTE):
        ultimo = n["horas"][-1] if n["horas"] else {}
        print(f"  {n['name']:<30}  último: {ultimo.get('hora','?')}  {ultimo.get('total','?')} USD/MWh")

print("\n── Todos los nodos ─────────────────────────────")
for n in sorted(nodos, key=lambda x: x["name"]):
    print(f"  {n['name']}")

# Mostrar CMG Crucero detallado
crucero = next((n for n in nodos if "crucero" in n["name"].lower()), None)
if crucero:
    print(f"\n✅ NODO CRUCERO: '{crucero['name']}'")
    print(f"   → Actualiza NODO_CRUCERO en adquisicion.py con este valor\n")
    
    por_hora = defaultdict(list)
    for h in crucero["horas"]:
        if h.get("total", 0) > 0:
            por_hora[h["hora"][:13]].append(h["total"])
    
    print(f"   CMG horario (promedio USD/MWh):")
    for k, vals in sorted(por_hora.items()):
        print(f"     {k}h  →  {sum(vals)/len(vals):.2f}  ({len(vals)} intervalos×15min)")