"""Mide el COSTO y la COBERTURA real de los endpoints del CEN.

Por qué existe: dimensionar un cron con números supuestos es como se pierden
datos en silencio. Dos lecciones caras del proyecto Pulsar:

  · `totalPages` escala con `limit`, así que comparar ese número entre endpoints
    medidos con distinto `limit` no significa NADA. Un endpoint quedó descartado
    un mes por "totalPages≈120.178" — con el limit de producción eran 121.
  · La cobertura temporal de "las últimas N páginas" NO es N/totalPages: la
    última página viene parcial y `totalPages` crece hora a hora. Se MIDE
    imprimiendo el min→max de los timestamps devueltos, no se deduce.

Uso:
    python3 medir_endpoints.py cobertura    # ventana real de ultimas_paginas
    python3 medir_endpoints.py limites      # techo de `limit` por endpoint
    python3 medir_endpoints.py ritmo        # segundos/página sostenidos

No escribe en la DB. Solo lee de la API y reporta.
"""
import sys
import time
from datetime import datetime, timedelta

from Adquisicion import (
    API_BASE_SIP, CEN_USER_KEY, TZ_CHILE, _SESSION, log, preflight_cen,
)

# Endpoints que paginan, con el `limit` que usan HOY en producción.
ENDPOINTS = {
    "cmg-online":      ("/costo-marginal-online/v4/findByDate",        4000),
    "gen-prog-pcp":    ("/generacion-programada-pcp/v4/findByDate",    5000),
    "gen-prog-pid":    ("/generacion-programada-pid/v4/findByDate",    5000),
    "cmg-prog-pid":    ("/cmg-programado-pid/v4/findByDate",           2000),
    "instrucciones":   ("/instrucciones-operacionales-cmg/v4/findByDate", 100),
    "limitaciones":    ("/limitaciones-transmision/v4/findByDate",      100),
    "solicitudes":     ("/solicitudes-trabajo/v4/findByDate",           100),
    "mant-mayor":      ("/programas-mantenimiento-mayor/v4/findByDate", 500),
    "demanda-neta":    ("/demanda-neta/v4/findByDate",                 1000),
}

# Escalera de `limit` a probar. El techo es POR ENDPOINT y hay que medirlo:
# en Pulsar, costo-marginal-online acepta 10000 y da 502 en 20000; el PID da
# 502 ya en 20000 mientras el PCP no. Nunca extrapolar de un endpoint a otro.
ESCALERA = [100, 500, 1000, 2000, 5000, 10000, 20000]


def _pedir(path, params, timeout=90):
    """GET crudo, devolviendo (status, body, segundos). No reintenta: acá el
    503/502 es el DATO que se está midiendo, no un problema a superar."""
    t0 = time.monotonic()
    try:
        r = _SESSION.get(f"{API_BASE_SIP}{path}",
                         params={**params, "user_key": CEN_USER_KEY},
                         timeout=timeout)
        dt = time.monotonic() - t0
        try:
            return r.status_code, r.json(), dt
        except ValueError:
            return r.status_code, None, dt
    except Exception as e:
        return None, {"_error": e.__class__.__name__}, time.monotonic() - t0


def _hoy():
    return datetime.now(TZ_CHILE).strftime("%Y-%m-%d")


# ── cobertura ──────────────────────────────────────────────────────────────────

def cobertura(ultimas=6, limit=4000):
    """¿Cuántas HORAS del día cubren realmente las últimas N páginas?

    Es la pregunta que decide si el cron de potencia deja huecos: si la ventana
    del script no cubre el salto entre corridas, lo que cae fuera no se vuelve a
    pedir NUNCA.
    """
    path = ENDPOINTS["cmg-online"][0]
    fecha = _hoy()
    print(f"\n=== COBERTURA de ultimas_paginas ({fecha}, limit={limit}) ===\n")

    st, body, dt = _pedir(path, {"startDate": fecha, "endDate": fecha,
                                 "limit": limit, "page": 1})
    if st != 200 or not isinstance(body, dict):
        print(f"  La primera página falló (HTTP {st}) — sin medición.")
        return
    total = int(body.get("totalPages") or 1)
    print(f"  totalPages del día EN CURSO: {total}  ({dt:.1f}s la página 1)")
    print("  (crece hora a hora: a las 23:00 será bastante mayor que ahora)\n")

    marcas = []
    paginas = range(max(1, total - ultimas + 1), total + 1)
    for pg in paginas:
        st, body, dt = _pedir(path, {"startDate": fecha, "endDate": fecha,
                                     "limit": limit, "page": pg})
        filas = (body or {}).get("data", []) if isinstance(body, dict) else []
        ts = [(f.get("fecha_minuto") or f.get("fecha_hora") or "")[:16]
              for f in filas]
        ts = [t for t in ts if t]
        if ts:
            marcas += ts
            print(f"  pág {pg:>3}/{total}: {len(filas):>5} filas  "
                  f"{min(ts)} → {max(ts)}  ({dt:.1f}s)")
        else:
            print(f"  pág {pg:>3}/{total}: VACÍA  ({dt:.1f}s)")
        time.sleep(0.3)

    if not marcas:
        print("\n  Sin datos — no se puede medir la cobertura.")
        return

    ini, fin = min(marcas), max(marcas)
    try:
        horas = (datetime.strptime(fin, "%Y-%m-%d %H:%M")
                 - datetime.strptime(ini, "%Y-%m-%d %H:%M")).total_seconds() / 3600
    except ValueError:
        horas = float("nan")

    print(f"\n  VENTANA REAL de las últimas {ultimas} páginas: {ini} → {fin}")
    print(f"  = {horas:.2f} h de cobertura")
    print(f"\n  Regla: la ventana debe cubrir 1-2 SALTOS del cron, no el intervalo")
    print(f"  nominal. Actions salta corridas programadas de forma sistemática.")
    for cada in (15, 30, 60):
        veredicto = "OK" if horas >= 2 * cada / 60 else "INSUFICIENTE"
        print(f"    cron cada {cada:>3} min → cubre "
              f"{horas / (cada / 60):.1f} corridas   [{veredicto}]")


# ── límites ────────────────────────────────────────────────────────────────────

def limites():
    """Techo de `limit` por endpoint. Menos páginas = menos requests = menos 429."""
    fecha = _hoy()
    ayer = (datetime.now(TZ_CHILE) - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"\n=== TECHO DE `limit` POR ENDPOINT (ventana {ayer}) ===")
    print("  Subir el limit es la palanca barata del paginado, pero el techo")
    print("  es POR ENDPOINT: hay que medirlo, nunca extrapolarlo.\n")

    for nombre, (path, limit_prod) in ENDPOINTS.items():
        print(f"  {nombre}  (producción: limit={limit_prod})")
        mejor = None
        for lim in ESCALERA:
            st, body, dt = _pedir(path, {"startDate": ayer, "endDate": ayer,
                                         "limit": lim, "page": 1})
            if st == 200 and isinstance(body, dict):
                tp = body.get("totalPages")
                n = len(body.get("data", []))
                print(f"      limit={lim:>6}: HTTP 200  totalPages={tp}  "
                      f"filas={n}  ({dt:.1f}s)")
                if n:
                    mejor = (lim, tp)
            else:
                err = (body or {}).get("_error", "")
                print(f"      limit={lim:>6}: HTTP {st} {err}  ({dt:.1f}s)  ← techo")
                break
            time.sleep(0.4)
        if mejor and mejor[0] > limit_prod:
            print(f"      → margen: se puede subir de {limit_prod} a {mejor[0]} "
                  f"(totalPages {mejor[1]})")
        print()


# ── ritmo ──────────────────────────────────────────────────────────────────────

def ritmo(nombre="cmg-online", paginas=8):
    """Segundos por página SOSTENIDOS.

    Las primeras llamadas son rápidas y luego la API se estrangula: en Pulsar,
    121 páginas tardaron 1.252 s (~10 s/pág) aunque las páginas sueltas del
    sondeo respondían en 2,5-4,3 s. El timeout de un workflow se estima con el
    ritmo sostenido, no con el de la primera página.
    """
    path, limit = ENDPOINTS[nombre]
    fecha = _hoy()
    print(f"\n=== RITMO SOSTENIDO — {nombre} (limit={limit}, {paginas} págs) ===\n")

    tiempos = []
    for pg in range(1, paginas + 1):
        st, body, dt = _pedir(path, {"startDate": fecha, "endDate": fecha,
                                     "limit": limit, "page": pg})
        tiempos.append(dt)
        n = len((body or {}).get("data", [])) if isinstance(body, dict) else 0
        print(f"  pág {pg:>3}: HTTP {st}  {n:>5} filas  {dt:5.1f}s")

    if tiempos:
        print(f"\n  primera: {tiempos[0]:.1f}s   "
              f"media: {sum(tiempos)/len(tiempos):.1f}s   "
              f"última: {tiempos[-1]:.1f}s")
        print(f"  → estimar el timeout con {max(tiempos):.1f}s/página, no con la primera.")


if __name__ == "__main__":
    if not CEN_USER_KEY:
        print("CEN_USER_KEY no configurada"); sys.exit(1)
    vivo, motivo = preflight_cen()
    if not vivo:
        print(f"API CEN no disponible: {motivo}"); sys.exit(1)

    modo = sys.argv[1] if len(sys.argv) > 1 else "cobertura"
    log.setLevel("ERROR")   # el ruido del retry estorba a la medición
    if   modo == "cobertura": cobertura(*(int(a) for a in sys.argv[2:]))
    elif modo == "limites":   limites()
    elif modo == "ritmo":     ritmo(*(sys.argv[2:3] or ["cmg-online"]))
    else:
        print(__doc__); sys.exit(1)
