"""
adquisicion.py — CTM Mejillones
────────────────────────────────────────────────────────────────
Fuentes de datos:
  · Generación real     → API CEN SIPUB (SIP plan)
  · CMG Nodo Crucero    → JSON S3 público del portal CEN
                          (actualizado cada ~15 min, sin auth)
  · Generación programada → pendiente plan correcto / manual

Variables de entorno (.env o GitHub Secrets):
  CEN_USER_KEY   → portal.api.coordinador.cl (plan SIP)
  DATABASE_URL   → postgresql://... (Supabase o Neon)
────────────────────────────────────────────────────────────────
"""

import os, sys, time, logging, requests, psycopg2
from datetime import date, datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

CEN_USER_KEY = os.getenv("CEN_USER_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── Constantes API CEN ────────────────────────────────────────
API_BASE_SIP = "https://sipub.api.coordinador.cl"
ID_ANGAMOS   = 377
ID_COCHRANE  = 379
LLAVES_OPREAL = {
    "ANG1": "TER ANGAMOS-ANG1",
    "ANG2": "TER ANGAMOS-ANG2",
    "CCR1": "TER COCHRANE-CCR1 (Carbon)",
    "CCR2": "TER COCHRANE-CCR2 (Carbon)",
}

# ── CMG S3 ────────────────────────────────────────────────────
CMG_S3_URL     = ("https://cen-template-graph-pweb-prod.s3.us-east-1"
                  ".amazonaws.com/CMG-online/costo-marginal-online.json")
CMG_S3_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible)",
    "Referer":    "https://cen-template-graph-pweb-prod.s3.us-east-1"
                  ".amazonaws.com/CMG-online/cmg_chart.html",
}
# Nombre exacto del nodo Crucero en el JSON S3
# Confirmar en el output del test (probablemente "CRUCERO_____220")
NODO_CRUCERO = "CRUCERO_______220"   # confirmado: 7 guiones bajos

DIAS_VENTANA = 2   # cuántos días hacia atrás consultar generación real

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("adquisicion.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# FUNCIONES DE ADQUISICIÓN
# ══════════════════════════════════════════════════════════════

def fetch_generacion_real(start: str, end: str) -> list[dict]:
    """Trae generación real de ANG1/2 CCR1/2 desde API CEN SIP."""
    registros = []
    for id_c in [ID_ANGAMOS, ID_COCHRANE]:
        nombre = "Angamos" if id_c == ID_ANGAMOS else "Cochrane"
        try:
            r = requests.get(
                f"{API_BASE_SIP}/generacion-real/v3/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "idCentral": id_c, "pageSize": 5000},
                timeout=25
            )
            r.raise_for_status()
            raw = r.json().get("data", [])
            for rec in raw:
                llave  = rec.get("llave_opreal", "")
                unidad = next((u for u, l in LLAVES_OPREAL.items() if l == llave), None)
                if unidad is None:
                    continue
                registros.append({
                    "unidad":          unidad,
                    "llave_opreal":    llave,
                    "id_central":      rec.get("id_central"),
                    "central":         rec.get("central"),
                    "gen_real_mw":     rec.get("gen_real_mw"),
                    "potencia_maxima": rec.get("potencia_maxima"),
                    "fecha_hora":      rec.get("fecha_hora"),
                    "hora":            rec.get("hora"),
                })
            log.info(f"  Gen. real {nombre}: {len([x for x in registros if x['id_central']==id_c])} registros")
        except Exception as e:
            log.error(f"  Error gen. real {nombre}: {e}")
        time.sleep(1.5)
    return registros


def fetch_cmg_crucero() -> list[dict]:
    """
    Obtiene el CMG del nodo Crucero desde el JSON S3 público del portal CEN.
    Retorna lista de registros horarios (promedio de los intervalos de 15 min).
    Unidad: USD/MWh (campo 'total' del JSON).
    """
    try:
        url = f"{CMG_S3_URL}?t={int(time.time()*1000)}"
        r   = requests.get(url, headers=CMG_S3_HEADERS, timeout=20)
        r.raise_for_status()
        body = r.json()

        if body.get("maintenance"):
            log.warning("  CMG S3: en mantenimiento, sin datos")
            return []

        nodos = body.get("data", [])
        log.info(f"  CMG S3: {len(nodos)} nodos en el JSON")

        # Encontrar el nodo Crucero (flexible: busca por nombre exacto o parcial)
        nodo = next(
            (n for n in nodos if n["name"] == NODO_CRUCERO),
            None
        )
        if nodo is None:
            # Fallback: buscar por substring
            nodo = next(
                (n for n in nodos if "crucero" in n["name"].lower()),
                None
            )
        if nodo is None:
            nombres = [n["name"] for n in nodos]
            log.warning(f"  CMG: nodo Crucero no encontrado. Nodos disponibles: {nombres[:10]}")
            return []

        log.info(f"  CMG Crucero: nodo={nodo['name']}, {len(nodo['horas'])} intervalos")

        # Agrupar intervalos de 15 min en horas completas (promedio)
        por_hora: dict[str, list[float]] = defaultdict(list)
        for h in nodo["horas"]:
            hora_str = h.get("hora", "")       # "2026-06-01 11:15"
            total    = h.get("total", 0.0)
            if not hora_str or total == 0.0:
                continue
            hora_key = hora_str[:13]             # "2026-06-01 11"
            por_hora[hora_key].append(total)

        registros = []
        for hora_key, valores in por_hora.items():
            try:
                # hora_key = "2026-06-01 11"
                dt  = datetime.strptime(hora_key, "%Y-%m-%d %H")
                prom = round(sum(valores) / len(valores), 4)
                registros.append({
                    "barra_transf": nodo["name"],
                    "barra_info":   f"Nodo Crucero 220kV",
                    "fecha_hora":   dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "hora":         dt.hour + 1,   # 1-24 (hora CEN)
                    "minuto":       0,
                    "cmg_usd_mwh":  prom,
                    "cmg_clp_kwh":  None,          # no disponible en este JSON
                    "version":      "REAL-ONLINE",
                })
            except Exception:
                continue

        log.info(f"  CMG Crucero: {len(registros)} horas procesadas")
        return registros

    except Exception as e:
        log.error(f"  Error CMG S3: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# FUNCIONES DB
# ══════════════════════════════════════════════════════════════

def get_conn():
    return psycopg2.connect(DATABASE_URL)


def upsert_generacion_real(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO generacion_real
            (unidad, llave_opreal, id_central, central,
             gen_real_mw, potencia_maxima, fecha_hora, hora)
        VALUES
            (%(unidad)s, %(llave_opreal)s, %(id_central)s, %(central)s,
             %(gen_real_mw)s, %(potencia_maxima)s, %(fecha_hora)s, %(hora)s)
        ON CONFLICT (unidad, fecha_hora) DO NOTHING
    """
    nuevos = dupes = 0
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                for rec in registros:
                    cur.execute(sql, rec)
                    nuevos += 1 if cur.rowcount == 1 else 0
                    dupes  += 1 if cur.rowcount == 0 else 0
            conn.commit()
    except Exception as e:
        log.error(f"  Error upsert gen. real: {e}")
    return nuevos, dupes


def upsert_cmg(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO costo_marginal
            (barra_transf, barra_info, fecha_hora, hora, minuto,
             cmg_usd_mwh, cmg_clp_kwh, version)
        VALUES
            (%(barra_transf)s, %(barra_info)s, %(fecha_hora)s, %(hora)s,
             %(minuto)s, %(cmg_usd_mwh)s, %(cmg_clp_kwh)s, %(version)s)
        ON CONFLICT (barra_transf, fecha_hora) DO UPDATE
            SET cmg_usd_mwh = EXCLUDED.cmg_usd_mwh,
                version     = EXCLUDED.version
    """
    nuevos = dupes = 0
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                for rec in registros:
                    cur.execute(sql, rec)
                    nuevos += 1 if cur.rowcount == 1 else 0
                    dupes  += 1 if cur.rowcount == 0 else 0
            conn.commit()
    except Exception as e:
        log.error(f"  Error upsert CMG: {e}")
    return nuevos, dupes


def log_adquisicion(endpoint, fecha, nuevos, dupes, duracion_ms, error=None):
    sql = """
        INSERT INTO log_adquisicion
            (endpoint, fecha_consultada, registros_nuevos,
             registros_duplicados, duracion_ms, error)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (endpoint, fecha, nuevos, dupes, duracion_ms, error))
            conn.commit()
    except Exception as e:
        log.warning(f"  No se pudo registrar log: {e}")


# ══════════════════════════════════════════════════════════════
# EJECUCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════

def run():
    log.info("═" * 55)
    log.info("  Adquisición CTM Mejillones — API CEN + CMG S3")
    log.info("═" * 55)

    if not CEN_USER_KEY:
        log.error("❌  CEN_USER_KEY no configurada"); sys.exit(1)
    if not DATABASE_URL:
        log.error("❌  DATABASE_URL no configurada"); sys.exit(1)

    hoy    = date.today()
    fechas = [(hoy - timedelta(days=d)).strftime("%Y-%m-%d")
              for d in range(DIAS_VENTANA - 1, -1, -1)]

    # ── Generación real ───────────────────────────────────────
    for fecha in fechas:
        log.info(f"\n  ── Gen. real {fecha}")
        t0 = time.time()
        err_str = None
        try:
            regs            = fetch_generacion_real(fecha, fecha)
            nuevos, dupes   = upsert_generacion_real(regs)
            log.info(f"  ✅ {nuevos} nuevos, {dupes} duplicados")
        except Exception as e:
            err_str = str(e)
            log.error(f"  ❌ {e}")
            nuevos = dupes = 0
        log_adquisicion("generacion_real", fecha, nuevos, dupes,
                        int((time.time()-t0)*1000), err_str)

    # ── CMG Crucero (S3) ──────────────────────────────────────
    log.info(f"\n  ── CMG Nodo Crucero (S3 portal CEN)")
    t0 = time.time()
    err_str = None
    try:
        regs_cmg        = fetch_cmg_crucero()
        nuevos, dupes   = upsert_cmg(regs_cmg)
        log.info(f"  ✅ CMG: {nuevos} nuevos, {dupes} actualizados")
    except Exception as e:
        err_str = str(e)
        log.error(f"  ❌ CMG: {e}")
        nuevos = dupes = 0
    log_adquisicion("cmg_crucero_s3", hoy.strftime("%Y-%m-%d"), nuevos, dupes,
                    int((time.time()-t0)*1000), err_str)

    log.info(f"\n  Fin adquisición\n")


if __name__ == "__main__":
    run()