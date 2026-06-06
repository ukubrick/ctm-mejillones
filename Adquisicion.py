"""
Adquisicion.py — CTM Mejillones
────────────────────────────────────────────────────────────────
Fuentes de datos:
  · Generación real        → API CEN SIPUB /generacion-real/v3
  · Generación programada  → API CEN SIPUB /generacion-programada-pcp/v4
  · CMG nodos CTM          → JSON S3 público del portal CEN (~15 min)

Variables de entorno (.env o GitHub Secrets):
  CEN_USER_KEY   → portal.api.coordinador.cl (plan SIP)
  DATABASE_URL   → postgresql://... (Supabase)
────────────────────────────────────────────────────────────────
"""

import os, sys, time, logging, requests, psycopg2
from datetime import datetime, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

CEN_USER_KEY = os.getenv("CEN_USER_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
TZ_CHILE     = ZoneInfo("America/Santiago")

# ── Constantes API CEN SIP ────────────────────────────────────
API_BASE_SIP = "https://sipub.api.coordinador.cl"
ID_ANGAMOS   = 377
ID_COCHRANE  = 379

# Mapeo llave_opreal → código de unidad (generación real)
LLAVES_OPREAL = {
    "ANG1": "TER ANGAMOS-ANG1",
    "ANG2": "TER ANGAMOS-ANG2",
    "CCR1": "TER COCHRANE-CCR1 (Carbon)",
    "CCR2": "TER COCHRANE-CCR2 (Carbon)",
}

# Mapeo llave_gen → código de unidad (generación programada PCP).
# Formato confirmado en producción (2026-06-06): "ANGAMOS_1", "ANGAMOS_2",
# "COCHRANE_1", "COCHRANE_2". Se mantienen variantes por si la API cambia.
LLAVES_GEN_PROG = {
    "ANG1": ["ANGAMOS_1", "TER ANGAMOS-ANG1", "ANGAMOS-ANG1", "ANG1"],
    "ANG2": ["ANGAMOS_2", "TER ANGAMOS-ANG2", "ANGAMOS-ANG2", "ANG2"],
    "CCR1": ["COCHRANE_1", "TER COCHRANE-CCR1 (Carbon)", "TER COCHRANE-CCR1", "COCHRANE-CCR1", "CCR1"],
    "CCR2": ["COCHRANE_2", "TER COCHRANE-CCR2 (Carbon)", "TER COCHRANE-CCR2", "COCHRANE-CCR2", "CCR2"],
}

# ── CMG S3 ────────────────────────────────────────────────────
CMG_S3_URL     = ("https://cen-template-graph-pweb-prod.s3.us-east-1"
                  ".amazonaws.com/CMG-online/costo-marginal-online.json")
CMG_S3_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible)",
    "Referer":    "https://cen-template-graph-pweb-prod.s3.us-east-1"
                  ".amazonaws.com/CMG-online/cmg_chart.html",
}

# Nodos CMG disponibles en el JSON S3 del portal CEN.
# El S3 expone 8 barras fijas del sistema. Para CTM Mejillones los más
# relevantes geográficamente son Crucero (zona norte, más cercano) y Tarapacá.
# Confirmado 2026-06-06: NO existen nodos Mejillones/Angamos/Cochrane en el S3.
CMG_NODOS = {
    "CRUCERO_______220": "crucero",
    "TARAPACA______220": "tarapaca",
}

DIAS_VENTANA = 2   # días hacia atrás para gen. real y programada

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
                timeout=25,
            )
            r.raise_for_status()
            raw = r.json().get("data", [])
            antes = len(registros)
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
            log.info(f"  Gen. real {nombre}: {len(registros)-antes} registros")
        except Exception as e:
            log.error(f"  Error gen. real {nombre}: {e}")
        time.sleep(1.5)
    return registros


def _map_llave_gen_prog(texto: str) -> str | None:
    """Mapea un texto (llave_gen o configuracion) al código de unidad."""
    if not texto:
        return None
    texto_up = texto.upper()
    for unidad, variantes in LLAVES_GEN_PROG.items():
        for v in variantes:
            if v.upper() == texto_up or v.upper() in texto_up:
                return unidad
    return None


def fetch_generacion_programada(start: str, end: str) -> list[dict]:
    """
    Trae generación programada PCP de ANG1/2 CCR1/2 desde la API CEN SIP.

    Endpoint: /generacion-programada-pcp/v4/findByDate
    No soporta filtro por central en el servidor, por lo que se pagina
    todo el resultado y se filtra localmente por id_central.
    """
    registros    = []
    ids_objetivo = {ID_ANGAMOS, ID_COCHRANE, str(ID_ANGAMOS), str(ID_COCHRANE)}
    page         = 0
    limit        = 5000
    llaves_no_mapeadas: set[str] = set()

    try:
        while True:
            r = requests.get(
                f"{API_BASE_SIP}/generacion-programada-pcp/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": limit},
                timeout=30,
            )
            r.raise_for_status()
            body = r.json()
            data = body.get("data", [])

            if not data:
                break

            # En la primera página logueamos un registro de ejemplo para
            # diagnosticar el formato real de llave_gen en producción.
            if page == 0:
                muestra = [d for d in data if d.get("id_central") in ids_objetivo]
                if muestra:
                    m = muestra[0]
                    log.info(
                        f"  PCP ejemplo — central='{m.get('central')}' "
                        f"llave_gen='{m.get('llave_gen')}' "
                        f"config='{m.get('configuracion')}' "
                        f"id_central={m.get('id_central')}"
                    )
                else:
                    log.info(
                        f"  PCP pág.0: {len(data)} registros totales, "
                        f"ninguno con id_central {ID_ANGAMOS}/{ID_COCHRANE}"
                    )

            for rec in data:
                id_c = rec.get("id_central")
                if id_c not in ids_objetivo:
                    continue

                llave_gen = rec.get("llave_gen", "")
                config    = rec.get("configuracion", "")

                # Intentar mapear por llave_gen primero; luego por configuracion
                unidad = _map_llave_gen_prog(llave_gen) or _map_llave_gen_prog(config)

                if unidad is None:
                    clave_log = f"{llave_gen}|{config}"
                    if clave_log not in llaves_no_mapeadas:
                        log.warning(
                            f"  PCP: sin mapeo para "
                            f"llave_gen='{llave_gen}' config='{config}' "
                            f"central='{rec.get('central')}' — "
                            f"agrega la variante a LLAVES_GEN_PROG"
                        )
                        llaves_no_mapeadas.add(clave_log)
                    continue

                fecha_hora_str = rec.get("fecha_hora", "")
                if not fecha_hora_str:
                    continue

                # Normalizar fecha_hora (puede venir como ISO "T" o con espacio)
                fecha_hora_norm = fecha_hora_str.replace("T", " ")[:19]

                # hora: el campo puede no existir; derivar de fecha_hora si falta
                hora_raw = rec.get("hora")
                if hora_raw is not None:
                    hora = int(hora_raw)
                else:
                    try:
                        hora = datetime.strptime(fecha_hora_norm, "%Y-%m-%d %H:%M:%S").hour + 1
                    except Exception:
                        hora = 0

                registros.append({
                    "unidad":            unidad,
                    "gen_programada_mw": float(rec.get("gen_programada_mw") or 0.0),
                    "fecha_hora":        fecha_hora_norm,
                    "hora":              hora,
                    "fuente":            "CEN_PCP",
                })

            total_pages = body.get("totalPages")
            if total_pages is None or page + 1 >= int(total_pages):
                break

            page += 1
            time.sleep(0.4)

    except Exception as e:
        log.error(f"  Error gen. programada PCP: {e}")

    log.info(f"  Gen. programada PCP ({start}): {len(registros)} registros ANG/CCR")
    return registros


def fetch_cmg_nodos() -> list[dict]:
    """
    Obtiene el CMG de múltiples nodos (Crucero, Mejillones, Angamos, Cochrane)
    desde el JSON S3 público del portal CEN. Devuelve registros horarios
    (promedio de los intervalos de 15 min por hora).
    """
    try:
        url = f"{CMG_S3_URL}?t={int(time.time() * 1000)}"
        r   = requests.get(url, headers=CMG_S3_HEADERS, timeout=20)
        r.raise_for_status()
        body = r.json()

        if body.get("maintenance"):
            log.warning("  CMG S3: en mantenimiento, sin datos")
            return []

        nodos_json = body.get("data", [])
        log.info(f"  CMG S3: {len(nodos_json)} nodos en el JSON")

        registros_total = []

        for nombre_exacto, fallback_substr in CMG_NODOS.items():
            # Buscar por nombre exacto primero; fallback por substring
            nodo = next((n for n in nodos_json if n["name"] == nombre_exacto), None)
            if nodo is None:
                nodo = next(
                    (n for n in nodos_json if fallback_substr in n["name"].lower()),
                    None,
                )
            if nodo is None:
                log.debug(f"  CMG: nodo '{nombre_exacto}' no encontrado en el JSON S3")
                continue

            horas_raw = nodo.get("horas", [])
            log.info(f"  CMG: {nodo['name']} — {len(horas_raw)} intervalos")

            # Agrupar intervalos de 15 min en horas completas (promedio)
            por_hora: dict[str, list[float]] = defaultdict(list)
            for h in horas_raw:
                hora_str = h.get("hora", "")   # "2026-06-01 11:15"
                total    = h.get("total", 0.0)
                if not hora_str or total == 0.0:
                    continue
                hora_key = hora_str[:13]         # "2026-06-01 11"
                por_hora[hora_key].append(total)

            tag = nombre_exacto[:8].rstrip("_")  # "CRUCERO" | "MEJILLON" etc.
            for hora_key, valores in por_hora.items():
                try:
                    dt   = datetime.strptime(hora_key, "%Y-%m-%d %H")
                    prom = round(sum(valores) / len(valores), 4)
                    registros_total.append({
                        "barra_transf": nodo["name"],
                        "barra_info":   f"Nodo {tag} 220kV",
                        "fecha_hora":   dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "hora":         dt.hour + 1,   # convención CEN: 1-24
                        "minuto":       0,
                        "cmg_usd_mwh":  prom,
                        "cmg_clp_kwh":  None,
                        "version":      "REAL-ONLINE",
                    })
                except Exception:
                    continue

        log.info(
            f"  CMG total: {len(registros_total)} registros "
            f"({len([k for k in CMG_NODOS if any(n['name']==k for n in nodos_json)])} nodos)"
        )
        return registros_total

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
                    if cur.rowcount == 1: nuevos += 1
                    else:                dupes  += 1
            conn.commit()
    except Exception as e:
        log.error(f"  Error upsert gen. real: {e}")
    return nuevos, dupes


def upsert_generacion_programada(registros: list[dict]) -> tuple[int, int]:
    """
    Inserta o actualiza generación programada.
    fuente='CEN_PCP': actualiza si ya existe (dato oficial, puede revisarse).
    fuente='MANUAL': también actualiza (preserva correcciones del operador).
    """
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO generacion_programada
            (unidad, gen_programada_mw, fecha_hora, hora, fuente)
        VALUES
            (%(unidad)s, %(gen_programada_mw)s, %(fecha_hora)s, %(hora)s, %(fuente)s)
        ON CONFLICT (unidad, fecha_hora, fuente) DO UPDATE
            SET gen_programada_mw = EXCLUDED.gen_programada_mw
    """
    nuevos = actualizados = 0
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                for rec in registros:
                    cur.execute(sql, rec)
                    if cur.rowcount == 1: nuevos       += 1
                    else:                actualizados  += 1
            conn.commit()
    except Exception as e:
        log.error(f"  Error upsert gen. programada: {e}")
    return nuevos, actualizados


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
    nuevos = actualizados = 0
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                for rec in registros:
                    cur.execute(sql, rec)
                    if cur.rowcount == 1: nuevos      += 1
                    else:                actualizados += 1
            conn.commit()
    except Exception as e:
        log.error(f"  Error upsert CMG: {e}")
    return nuevos, actualizados


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
    log.info("═" * 58)
    log.info("  Adquisición CTM Mejillones — API CEN + CMG S3")
    log.info("═" * 58)

    if not CEN_USER_KEY:
        log.error("❌  CEN_USER_KEY no configurada"); sys.exit(1)
    if not DATABASE_URL:
        log.error("❌  DATABASE_URL no configurada"); sys.exit(1)

    # Usar hora chilena para evitar desfase UTC en GitHub Actions
    hoy    = datetime.now(TZ_CHILE).date()
    fechas = [(hoy - timedelta(days=d)).strftime("%Y-%m-%d")
              for d in range(DIAS_VENTANA - 1, -1, -1)]
    hoy_str = hoy.strftime("%Y-%m-%d")

    # ── Generación real ───────────────────────────────────────
    for fecha in fechas:
        log.info(f"\n  ── Gen. real {fecha}")
        t0 = time.time()
        err_str = None
        try:
            regs          = fetch_generacion_real(fecha, fecha)
            nuevos, dupes = upsert_generacion_real(regs)
            log.info(f"  ✅ {nuevos} nuevos, {dupes} duplicados")
        except Exception as e:
            err_str = str(e); log.error(f"  ❌ {e}"); nuevos = dupes = 0
        log_adquisicion("generacion_real", fecha, nuevos, dupes,
                        int((time.time() - t0) * 1000), err_str)

    # ── Generación programada PCP (solo hoy) ──────────────────
    # El PCP no filtra por central en el servidor: pagina ~61 páginas de
    # 5000 registros. Limitamos a hoy para no repetir páginas de días ya
    # guardados (la programada del día anterior no cambia).
    log.info(f"\n  ── Gen. programada PCP {hoy_str}")
    t0 = time.time()
    err_str = None
    try:
        regs             = fetch_generacion_programada(hoy_str, hoy_str)
        nuevos, actualizados = upsert_generacion_programada(regs)
        log.info(f"  ✅ PCP: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ PCP: {e}"); nuevos = actualizados = 0
    log_adquisicion("generacion_programada_pcp", hoy_str, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── CMG múltiples nodos (S3) ──────────────────────────────
    log.info(f"\n  ── CMG Nodos CTM (S3 portal CEN)")
    t0 = time.time()
    err_str = None
    try:
        regs_cmg             = fetch_cmg_nodos()
        nuevos, actualizados = upsert_cmg(regs_cmg)
        log.info(f"  ✅ CMG: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ CMG: {e}"); nuevos = actualizados = 0
    log_adquisicion("cmg_nodos_s3", hoy.strftime("%Y-%m-%d"), nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    log.info(f"\n  Fin adquisición\n")


if __name__ == "__main__":
    run()
