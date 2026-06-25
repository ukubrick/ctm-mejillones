"""
Adquisicion.py — CTM Mejillones
────────────────────────────────────────────────────────────────
Fuentes de datos:
  · Generación real        → API CEN SIPUB /generacion-real/v3
  · Generación programada  → API CEN SIPUB /generacion-programada-pcp/v4
  · CMG nodos CTM          → JSON S3 público del portal CEN (~15 min)
  · SSCC instrucciones     → API CEN Operaciones /servicios-complementarios/v1
  · Limitaciones           → API CEN SIPUB /limitaciones-transmision/v4

Variables de entorno (.env o GitHub Secrets):
  CEN_USER_KEY   → portal.api.coordinador.cl (plan SIP)
  CEN_OPS_KEY    → operacion.api.coordinador.cl (plan Operaciones)
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
CEN_OPS_KEY  = os.getenv("CEN_OPS_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
TZ_CHILE     = ZoneInfo("America/Santiago")

# ── Constantes API CEN ────────────────────────────────────────
API_BASE_SIP = "https://sipub.api.coordinador.cl"
API_BASE_OPS = "https://operacion.api.coordinador.cl"
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

# CMG programado PID: llave_cmg de la API → nombre de barra usado en el dashboard
# (el mismo que el CMG real del S3, para poder cruzarlos).
CMG_PROG_BARRAS = {
    "Crucero220":  "CRUCERO_______220",
    "Tarapaca220": "TARAPACA______220",
}

# Pronóstico de demanda corto plazo: barras relevantes para CTM Mejillones.
# Crucero220 es el nodo regional norte (el mismo del CMG → anticipa su movimiento);
# Angamos220 y Mejillones110 son la demanda local. La API entrega `energia_mwh` horaria.
BARRAS_DEMANDA = ["Crucero220", "Laberinto220", "Angamos220", "Mejillones110"]
# Mapeo barra_transf del CMG → barra del pronóstico de demanda (para cruzarlos)
CMG_A_DEMANDA = {
    "CRUCERO_______220": "Crucero220",
    "TARAPACA______220": "Tarapaca220",
}

# Mapeo centralUnidad → código interno (confirmado en API Operaciones 2026-06-09)
LLAVES_SSCC = {
    "ANGAMOS-ANG1": "ANG1",
    "ANGAMOS-ANG2": "ANG2",
    "COCHRANE-CCH1": "CCR1",
    "COCHRANE-CCH2": "CCR2",
}

# Mapeo campo `central` de instrucciones operacionales CMG → código interno
# (confirmado en producción 2026-06-23). Misma convención CCH que SSCC.
LLAVES_INSTR_CMG = {
    "ANGAMOS-ANG1": "ANG1",
    "ANGAMOS-ANG2": "ANG2",
    "COCHRANE-CCH1": "CCR1",
    "COCHRANE-CCH2": "CCR2",
}

DIAS_VENTANA     = 7   # días hacia atrás para gen. real y SSCC (filtra en servidor, rápido)
DIAS_VENTANA_PCP = 2   # días hacia atrás para PCP: ~120 páginas × 0.3s ≈ 8 min (427 págs con 7 días → timeout)

# id_unidad → código interno (confirmado en exploración 2026-06-11)
ID_UNIDAD_MAP = {1965: "ANG1", 1966: "ANG2", 1967: "CCR1", 1968: "CCR2"}
IDS_CENTRALES_SET = {ID_ANGAMOS, ID_COCHRANE}
# Ventana hacia atrás para limitaciones (más amplia: cambios pueden durar semanas)
DIAS_VENTANA_LIM = 30

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
            r = _get_with_retry(
                f"{API_BASE_SIP}/generacion-real/v3/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "idCentral": id_c, "pageSize": 5000},
            )
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


def _get_with_retry(url: str, params: dict, timeout: int = 60,
                    max_retries: int = 3) -> requests.Response:
    """GET con retry exponencial ante 429/5xx y errores de red (timeout, conexión)."""
    last_exc = None
    for intento in range(max_retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            espera = 10 * 2 ** intento
            log.warning(f"  Error de red ({exc.__class__.__name__}) — reintento {intento+1}/{max_retries} en {espera}s")
            time.sleep(espera)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            espera = 10 * 2 ** intento          # 10s, 20s, 40s
            log.warning(f"  HTTP {r.status_code} — reintento {intento+1}/{max_retries} en {espera}s")
            time.sleep(espera)
            continue
        r.raise_for_status()
        return r
    if last_exc:
        raise last_exc
    r.raise_for_status()
    return r


def fetch_generacion_programada(start: str, end: str) -> list[dict]:
    """
    Trae generación programada PCP de ANG1/2 CCR1/2 desde la API CEN SIP.

    Endpoint: /generacion-programada-pcp/v4/findByDate
    No soporta filtro por central en el servidor, por lo que se pagina
    todo el resultado y se filtra localmente por id_central.
    Usa limit=5000 (estable) en vez de 50000 que provoca 504 en el servidor.
    """
    registros    = []
    ids_objetivo = {ID_ANGAMOS, ID_COCHRANE, str(ID_ANGAMOS), str(ID_COCHRANE)}
    page         = 0
    limit        = 5000
    llaves_no_mapeadas: set[str] = set()

    try:
        while True:
            r    = _get_with_retry(
                f"{API_BASE_SIP}/generacion-programada-pcp/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": limit},
            )
            body = r.json()
            data = body.get("data", [])

            if not data:
                break

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
                unidad    = _map_llave_gen_prog(llave_gen) or _map_llave_gen_prog(config)

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

                fecha_hora_norm = fecha_hora_str.replace("T", " ")[:19]

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
            time.sleep(0.3)

    except Exception as e:
        log.error(f"  Error gen. programada PCP: {e}")

    log.info(f"  Gen. programada PCP ({start}): {len(registros)} registros ANG/CCR")
    return registros


def fetch_generacion_programada_pid(start: str, end: str) -> list[dict]:
    """
    Trae generación programada PID (Programa Intra-Día) de ANG1/2 CCR1/2.

    Endpoint: /generacion-programada-pid/v4/findByDate (SIP).
    El PID reajusta el PCP durante el día con información más fresca, por lo que
    para un mismo (unidad, fecha_hora) puede haber varios programas emitidos a
    distintas horas; se conserva el MÁS RECIENTE según (fecha_programa, hora_programa).

    ⚠️ A diferencia del PCP (0-indexado), el PID es **1-indexado**: page=0 → 502.
    No filtra por central en el servidor → paginar todo (limit=5000) y filtrar
    localmente por id_central. Usa las mismas llaves que el PCP (LLAVES_GEN_PROG).
    """
    ids_objetivo = {ID_ANGAMOS, ID_COCHRANE, str(ID_ANGAMOS), str(ID_COCHRANE)}
    page         = 1
    limit        = 5000
    # mejor programa por (unidad, fecha_hora) → (clave_recencia, registro)
    mejores: dict[tuple[str, str], tuple[tuple, dict]] = {}
    llaves_no_mapeadas: set[str] = set()

    try:
        while True:
            r    = _get_with_retry(
                f"{API_BASE_SIP}/generacion-programada-pid/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": limit},
            )
            body = r.json()
            data = body.get("data", [])
            if not data:
                break

            for rec in data:
                if rec.get("id_central") not in ids_objetivo:
                    continue

                llave_gen = rec.get("llave_gen", "")
                config    = rec.get("configuracion", "")
                unidad    = _map_llave_gen_prog(llave_gen) or _map_llave_gen_prog(config)
                if unidad is None:
                    clave_log = f"{llave_gen}|{config}"
                    if clave_log not in llaves_no_mapeadas:
                        log.warning(
                            f"  PID: sin mapeo para llave_gen='{llave_gen}' "
                            f"config='{config}' central='{rec.get('central')}'"
                        )
                        llaves_no_mapeadas.add(clave_log)
                    continue

                fecha_hora_str = rec.get("fecha_hora", "")
                if not fecha_hora_str:
                    continue
                fecha_hora_norm = fecha_hora_str.replace("T", " ")[:19]

                hora_raw = rec.get("hora")
                if hora_raw is not None:
                    hora = int(hora_raw)
                else:
                    try:
                        hora = datetime.strptime(fecha_hora_norm, "%Y-%m-%d %H:%M:%S").hour + 1
                    except Exception:
                        hora = 0

                # Recencia del programa: fecha_programa + hora_programa (mayor = más nuevo)
                recencia = (str(rec.get("fecha_programa") or ""),
                            int(rec.get("hora_programa") or 0))
                clave = (unidad, fecha_hora_norm)
                if clave in mejores and mejores[clave][0] >= recencia:
                    continue
                mejores[clave] = (recencia, {
                    "unidad":            unidad,
                    "gen_programada_mw": float(rec.get("gen_programada_mw") or 0.0),
                    "fecha_hora":        fecha_hora_norm,
                    "hora":              hora,
                    "fuente":            "CEN_PID",
                })

            total_pages = body.get("totalPages")
            if total_pages is None or page >= int(total_pages):
                break
            page += 1
            time.sleep(0.3)

    except Exception as e:
        log.error(f"  Error gen. programada PID: {e}")

    registros = [v[1] for v in mejores.values()]
    log.info(f"  Gen. programada PID ({start}→{end}): {len(registros)} registros ANG/CCR")
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
        ON CONFLICT (unidad, fecha_hora) DO UPDATE
            SET gen_real_mw = EXCLUDED.gen_real_mw,
                potencia_maxima = EXCLUDED.potencia_maxima
            WHERE generacion_real.gen_real_mw = 0
               OR EXCLUDED.gen_real_mw > 0
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


def fetch_cmg_programado(start: str, end: str) -> list[dict]:
    """
    Trae el CMG programado (PID) de las barras Crucero/Tarapacá desde la API CEN SIP.

    Endpoint: /cmg-programado-pid/v4/findByDate
    No filtra por barra en el servidor → se pagina todo y se filtra localmente
    por llave_cmg ∈ CMG_PROG_BARRAS. Se conserva el programa más reciente
    (mayor fecha_programa) para cada (barra, fecha_hora).
    """
    mejor: dict[tuple, dict] = {}   # (barra, fecha_hora) → registro
    page  = 1   # este endpoint es 1-indexado (page=0 devuelve 502)
    limit = 2000
    try:
        while True:
            r = _get_with_retry(
                f"{API_BASE_SIP}/cmg-programado-pid/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": limit},
            )
            body = r.json()
            data = body.get("data", [])
            if not data:
                break

            for rec in data:
                llave = rec.get("llave_cmg")
                barra = CMG_PROG_BARRAS.get(llave)
                if barra is None:
                    continue
                fh = (rec.get("fecha_hora") or "").replace("T", " ")[:19]
                if not fh:
                    continue
                fprog = rec.get("fecha_programa") or ""
                clave = (barra, fh)
                anterior = mejor.get(clave)
                if anterior is None or fprog >= anterior["fecha_programa"]:
                    mejor[clave] = {
                        "barra":          barra,
                        "fecha_hora":     fh,
                        "cmg_usd_mwh":    float(rec.get("cmg_usd_mwh") or 0.0),
                        "fecha_programa": fprog,
                    }

            total_pages = body.get("totalPages")
            if total_pages is None or page >= int(total_pages):
                break
            page += 1

        log.info(f"  CMG programado ({start}→{end}): {len(mejor)} registros Crucero/Tarapacá")
    except Exception as e:
        log.error(f"  Error CMG programado: {e}")
    return list(mejor.values())


def upsert_cmg_programado(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO costo_marginal_programado
            (barra, fecha_hora, cmg_usd_mwh, fecha_programa)
        VALUES
            (%(barra)s, %(fecha_hora)s, %(cmg_usd_mwh)s, %(fecha_programa)s)
        ON CONFLICT (barra, fecha_hora) DO UPDATE
            SET cmg_usd_mwh    = EXCLUDED.cmg_usd_mwh,
                fecha_programa = EXCLUDED.fecha_programa
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
        log.error(f"  Error upsert CMG programado: {e}")
    return nuevos, actualizados


def fetch_cmg_real(start: str, end: str) -> list[dict]:
    """
    Trae el CMG real oficial liquidado de las barras Crucero/Tarapacá.

    Endpoint: /costo-marginal-real/v4/findByDate (SIP, 1-indexado).
    SÍ filtra por barra en el servidor con `bar_transf` (baja de ~7810 a ~5 págs).
    OJO: el CMG real se liquida con rezago (~10 días); fechas recientes devuelven 0.
    Se conservan solo los valores en hora en punto (min == 0) para cruzar con CMG
    online/programado, que son horarios.
    """
    registros = []
    for barra in CMG_PROG_BARRAS.values():   # CRUCERO_______220 / TARAPACA______220
        page  = 1   # 1-indexado
        # OJO: este endpoint devuelve VACÍO si limit supera los registros de la
        # página (~96/día a resolución 15-min). limit alto (≥100) → 0 registros.
        # Se usa limit=50 y se pagina (al contrario del PCP/PID que usan limit=2000).
        limit = 50
        antes = len(registros)
        try:
            while True:
                r = _get_with_retry(
                    f"{API_BASE_SIP}/costo-marginal-real/v4/findByDate",
                    params={"user_key": CEN_USER_KEY, "startDate": start, "endDate": end,
                            "bar_transf": barra, "page": page, "limit": limit},
                )
                body = r.json()
                data = body.get("data", [])
                if not data:
                    break
                for rec in data:
                    if int(rec.get("min") or 0) != 0:
                        continue   # solo hora en punto
                    fh = (rec.get("fecha_hora") or "").replace("T", " ")[:16]
                    if not fh:
                        continue
                    registros.append({
                        "barra_transf": rec.get("barra_transf") or barra,
                        "fecha_hora":   f"{fh}:00" if len(fh) == 16 else fh,
                        "cmg_usd_mwh":  float(rec.get("cmg_usd_mwh_") or 0.0),
                        "cmg_clp_kwh":  float(rec.get("cmg_clp_kwh_") or 0.0),
                        "version":      rec.get("version"),
                    })
                total_pages = body.get("totalPages")
                if total_pages is None or page >= int(total_pages):
                    break
                page += 1
            log.info(f"  CMG real {barra} ({start}→{end}): {len(registros)-antes} registros")
        except Exception as e:
            log.error(f"  Error CMG real {barra}: {e}")
        time.sleep(1.5)
    return registros


def upsert_cmg_real(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO costo_marginal_real
            (barra_transf, fecha_hora, cmg_usd_mwh, cmg_clp_kwh, version)
        VALUES
            (%(barra_transf)s, %(fecha_hora)s, %(cmg_usd_mwh)s, %(cmg_clp_kwh)s, %(version)s)
        ON CONFLICT (barra_transf, fecha_hora) DO UPDATE
            SET cmg_usd_mwh = EXCLUDED.cmg_usd_mwh,
                cmg_clp_kwh = EXCLUDED.cmg_clp_kwh,
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
        log.error(f"  Error upsert CMG real: {e}")
    return nuevos, actualizados


def fetch_pronostico_demanda(start: str, end: str) -> list[dict]:
    """
    Trae el pronóstico de demanda corto plazo de las barras relevantes para CTM.

    Endpoint: /pronosticos-demanda-corto-plazo/v4/findByDate (SIP, 0-indexado).
    NO filtra por barra en el servidor → paginar (liviano, ~4 págs/2 días con
    limit=2000) y filtrar local por BARRAS_DEMANDA. Entrega `energia_mwh` horaria.
    """
    registros = []
    page  = 0
    limit = 2000
    try:
        while True:
            r = _get_with_retry(
                f"{API_BASE_SIP}/pronosticos-demanda-corto-plazo/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": limit},
            )
            body = r.json()
            data = body.get("data", [])
            if not data:
                break
            for rec in data:
                if rec.get("barra") not in BARRAS_DEMANDA:
                    continue
                fh = (rec.get("fecha_hora") or "").replace("T", " ")[:19]
                if not fh:
                    continue
                hora_raw = rec.get("hora")
                hora = int(hora_raw) if hora_raw is not None else 0
                registros.append({
                    "barra":        rec.get("barra"),
                    "fecha_hora":   fh,
                    "energia_mwh":  float(rec.get("energia_mwh") or 0.0),
                    "hora":         hora,
                    "date_control": rec.get("date_control"),
                })
            total_pages = body.get("totalPages")
            if total_pages is None or page + 1 >= int(total_pages):
                break
            page += 1
            time.sleep(0.3)
    except Exception as e:
        log.error(f"  Error pronóstico demanda: {e}")
    log.info(f"  Pronóstico demanda ({start}→{end}): {len(registros)} registros "
             f"({', '.join(BARRAS_DEMANDA)})")
    return registros


def upsert_pronostico_demanda(registros: list[dict]) -> tuple[int, int]:
    """Inserta/actualiza el pronóstico de demanda. Conserva el pronóstico más
    reciente por (barra, fecha_hora) — el cron horario sobrescribe con date_control nuevo."""
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO pronostico_demanda
            (barra, fecha_hora, energia_mwh, hora, date_control)
        VALUES
            (%(barra)s, %(fecha_hora)s, %(energia_mwh)s, %(hora)s, %(date_control)s)
        ON CONFLICT (barra, fecha_hora) DO UPDATE
            SET energia_mwh  = EXCLUDED.energia_mwh,
                date_control = EXCLUDED.date_control
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
        log.error(f"  Error upsert pronóstico demanda: {e}")
    return nuevos, actualizados


def fetch_sscc(fecha: str) -> list[dict]:
    """
    Trae instrucciones SSCC de ANG1/2 CCR1/2 desde la API CEN Operaciones.
    Endpoint: /servicios-complementarios/v1 (pageSize=-1 para traer todo en una sola llamada).
    """
    if not CEN_OPS_KEY:
        log.warning("  CEN_OPS_KEY no configurada — saltando SSCC")
        return []

    registros = []
    try:
        r = _get_with_retry(
            f"{API_BASE_OPS}/servicios-complementarios/v1",
            params={"user_key": CEN_OPS_KEY, "initDate": fecha, "endDate": fecha,
                    "page": 0, "pageSize": -1},
            timeout=30,
        )
        content = r.json().get("content", [])
        log.info(f"  SSCC: {len(content)} registros totales del sistema")

        for rec in content:
            unidad_api = rec.get("centralUnidad", "") or ""
            unidad = LLAVES_SSCC.get(unidad_api)
            if unidad is None:
                continue
            registros.append({
                "fecha":               rec.get("fecha"),
                "inicio_periodo":      rec.get("inicioPeriodo"),
                "fin_periodo":         rec.get("finPeriodo"),
                "instruccion_sscc":    rec.get("instruccionSscc"),
                "id_configuracion":    rec.get("idConfiguracion"),
                "central_subestacion": rec.get("centralSubestacion"),
                "central_unidad":      unidad_api,
                "unidad":              unidad,
                "configuracion_panio": rec.get("configuracionPanio"),
                "barra_ct":            rec.get("barraCt"),
                "disponibilidad":      rec.get("disponibilidad"),
                "baja":                rec.get("baja"),
                "sube":                rec.get("sube"),
                "unidad_medida":       rec.get("unidadMedida"),
                "motivo":              rec.get("motivo"),
                "comentario":          rec.get("comentario"),
                "estado_sabana":       rec.get("estadoSabana"),
                "sabana":              rec.get("sabana"),
                "fecha_accion":        rec.get("fechaAccion"),
                "usuario":             rec.get("usuario"),
            })

        log.info(f"  SSCC ANG/CCR ({fecha}): {len(registros)} registros")
    except Exception as e:
        log.error(f"  Error SSCC: {e}")

    return registros


def upsert_sscc(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO sscc_instrucciones
            (fecha, inicio_periodo, fin_periodo, instruccion_sscc, id_configuracion,
             central_subestacion, central_unidad, unidad, configuracion_panio, barra_ct,
             disponibilidad, baja, sube, unidad_medida, motivo, comentario,
             estado_sabana, sabana, fecha_accion, usuario)
        VALUES
            (%(fecha)s, %(inicio_periodo)s, %(fin_periodo)s, %(instruccion_sscc)s,
             %(id_configuracion)s, %(central_subestacion)s, %(central_unidad)s, %(unidad)s,
             %(configuracion_panio)s, %(barra_ct)s, %(disponibilidad)s, %(baja)s, %(sube)s,
             %(unidad_medida)s, %(motivo)s, %(comentario)s, %(estado_sabana)s, %(sabana)s,
             %(fecha_accion)s, %(usuario)s)
        ON CONFLICT (fecha, id_configuracion, instruccion_sscc, inicio_periodo)
        DO UPDATE SET
            fin_periodo        = EXCLUDED.fin_periodo,
            disponibilidad     = EXCLUDED.disponibilidad,
            estado_sabana      = EXCLUDED.estado_sabana,
            comentario         = EXCLUDED.comentario,
            fecha_accion       = EXCLUDED.fecha_accion,
            usuario            = EXCLUDED.usuario
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
        log.error(f"  Error upsert SSCC: {e}")
    return nuevos, actualizados


def fetch_instrucciones_cmg(fecha: str) -> list[dict]:
    """
    Trae instrucciones operacionales de despacho por CMG de ANG1/2 CCR1/2.
    Endpoint: /instrucciones-operacionales-cmg/v4/findByDate (plan SIP, 1-indexado).
    No filtra por central en el servidor → se pagina todo (~25 págs/día) y se
    filtra localmente por el campo `central` ∈ LLAVES_INSTR_CMG. id_central e
    id_unidad_generadora vienen vacíos en la respuesta, por eso se usa `central`.
    """
    if not CEN_USER_KEY:
        log.warning("  CEN_USER_KEY no configurada — saltando instrucciones CMG")
        return []

    registros = []
    page  = 1   # 1-indexado
    limit = 100
    try:
        while True:
            r = _get_with_retry(
                f"{API_BASE_SIP}/instrucciones-operacionales-cmg/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": fecha,
                        "endDate": fecha, "page": page, "limit": limit},
            )
            body = r.json()
            data = body.get("data", [])
            if not data:
                break

            for rec in data:
                central = (rec.get("central") or "").upper()
                unidad  = LLAVES_INSTR_CMG.get(central)
                if unidad is None:
                    continue
                fch = (rec.get("fecha") or "")[:10]
                hra = rec.get("hora") or ""
                fecha_hora = f"{fch} {hra}".strip()
                registros.append({
                    "id_instruccion":   rec.get("id_instruccion"),
                    "unidad":           unidad,
                    "central":          rec.get("central"),
                    "fecha_hora":       fecha_hora,
                    "fecha":            fch,
                    "hora":             hra,
                    "configuracion":    rec.get("configuracion"),
                    "despacho":         rec.get("despacho"),
                    "estado":           rec.get("estado"),
                    "estado_operativo": rec.get("estado_operativo"),
                    "consigna":         rec.get("consigna"),
                    "instruccion_cmg":  rec.get("instruccion_cmg"),
                    "motivo":           rec.get("motivo"),
                    "zona_desaclope":   rec.get("zona_desaclope"),
                    "control_tension":  rec.get("control_tension"),
                })

            total_pages = body.get("totalPages")
            if total_pages is None or page >= int(total_pages):
                break
            page += 1

        log.info(f"  Instrucciones CMG ({fecha}): {len(registros)} registros ANG/CCR")
    except Exception as e:
        log.error(f"  Error instrucciones CMG: {e}")
    return registros


def upsert_instrucciones_cmg(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO instrucciones_cmg
            (id_instruccion, unidad, central, fecha_hora, fecha, hora, configuracion,
             despacho, estado, estado_operativo, consigna, instruccion_cmg, motivo,
             zona_desaclope, control_tension)
        VALUES
            (%(id_instruccion)s, %(unidad)s, %(central)s, %(fecha_hora)s, %(fecha)s,
             %(hora)s, %(configuracion)s, %(despacho)s, %(estado)s, %(estado_operativo)s,
             %(consigna)s, %(instruccion_cmg)s, %(motivo)s, %(zona_desaclope)s,
             %(control_tension)s)
        ON CONFLICT (id_instruccion, unidad) DO UPDATE SET
            despacho         = EXCLUDED.despacho,
            estado           = EXCLUDED.estado,
            estado_operativo = EXCLUDED.estado_operativo,
            consigna         = EXCLUDED.consigna,
            instruccion_cmg  = EXCLUDED.instruccion_cmg,
            motivo           = EXCLUDED.motivo,
            zona_desaclope   = EXCLUDED.zona_desaclope,
            control_tension  = EXCLUDED.control_tension
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
        log.error(f"  Error upsert instrucciones CMG: {e}")
    return nuevos, actualizados


def fetch_limitaciones(start: str, end: str) -> list[dict]:
    """
    Trae limitaciones de transmisión de Angamos y Cochrane desde la API CEN SIP.
    Endpoint: /limitaciones-transmision/v4/findByDate (plan SIP, sin prefijo sipub/api/rest).
    Filtra por id_central ∈ {377, 379} o empresa_nombre/instalacion_nombre que contenga
    ANGAMOS o COCHRANE. Pagina con limit=100 hasta agotar páginas.
    """
    if not CEN_USER_KEY:
        log.warning("  CEN_USER_KEY no configurada — saltando limitaciones")
        return []

    registros = []
    page = 1
    base_url = f"{API_BASE_SIP}/limitaciones-transmision/v4/findByDate"

    try:
        while True:
            r = _get_with_retry(
                base_url,
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": 100},
            )
            body  = r.json()
            data  = body.get("data", [])
            total = body.get("totalPages", 1)

            if not data:
                break

            for rec in data:
                id_c      = rec.get("id_central")
                empresa   = (rec.get("empresa_nombre")   or "").upper()
                instalac  = (rec.get("instalacion_nombre") or "").upper()
                id_c_int  = int(float(id_c)) if id_c is not None else None

                if (id_c_int in IDS_CENTRALES_SET or
                        "ANGAMOS"  in empresa or "COCHRANE" in empresa or
                        "ANGAMOS"  in instalac or "COCHRANE" in instalac):
                    id_unidad     = rec.get("id_unidad")
                    id_unidad_int = int(float(id_unidad)) if id_unidad is not None else None
                    registros.append({
                        "id":                       rec.get("id"),
                        "correlativo":              rec.get("correlativo"),
                        "empresa_nombre":           rec.get("empresa_nombre"),
                        "instalacion_nombre":       rec.get("instalacion_nombre"),
                        "status":                   rec.get("status"),
                        "fecha_perturbacion":       rec.get("fecha_perturbacion"),
                        "fecha_retorno_estimada":   rec.get("fecha_retorno_estimada"),
                        "fecha_efectiva_retorno":   rec.get("fecha_efectiva_retorno"),
                        "potencia":                 rec.get("potencia"),
                        "unidad_medida_potencia":   rec.get("unidad_medida_potencia"),
                        "produce_indisponibilidad": rec.get("produce_indisponibilidad"),
                        "afecta_sscc":              rec.get("afecta_sscc"),
                        "elemento_a_trabajar":      rec.get("elemento_a_trabajar"),
                        "tipos_elementos":          rec.get("tipos_elementos"),
                        "observacion":              rec.get("observacion"),
                        "id_central":               id_c_int,
                        "id_unidad":                id_unidad_int,
                        "partition_date":           rec.get("partition_date"),
                        "created":                  rec.get("created"),
                        "modified":                 rec.get("modified"),
                    })

            log.info(f"  Limitaciones pág {page}/{total}")
            if page >= total:
                break
            page += 1

        log.info(f"  Limitaciones ANG/CCR ({start}→{end}): {len(registros)} registros")
    except Exception as e:
        log.error(f"  Error limitaciones: {e}")

    return registros


def upsert_limitaciones(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO limitaciones_transmision
            (id, correlativo, empresa_nombre, instalacion_nombre, status,
             fecha_perturbacion, fecha_retorno_estimada, fecha_efectiva_retorno,
             potencia, unidad_medida_potencia, produce_indisponibilidad, afecta_sscc,
             elemento_a_trabajar, tipos_elementos, observacion,
             id_central, id_unidad, partition_date, created, modified)
        VALUES
            (%(id)s, %(correlativo)s, %(empresa_nombre)s, %(instalacion_nombre)s, %(status)s,
             %(fecha_perturbacion)s, %(fecha_retorno_estimada)s, %(fecha_efectiva_retorno)s,
             %(potencia)s, %(unidad_medida_potencia)s, %(produce_indisponibilidad)s, %(afecta_sscc)s,
             %(elemento_a_trabajar)s, %(tipos_elementos)s, %(observacion)s,
             %(id_central)s, %(id_unidad)s, %(partition_date)s, %(created)s, %(modified)s)
        ON CONFLICT (id) DO UPDATE SET
            status                   = EXCLUDED.status,
            fecha_efectiva_retorno   = EXCLUDED.fecha_efectiva_retorno,
            fecha_retorno_estimada   = EXCLUDED.fecha_retorno_estimada,
            potencia                 = EXCLUDED.potencia,
            observacion              = EXCLUDED.observacion,
            modified                 = EXCLUDED.modified
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
        log.error(f"  Error upsert limitaciones: {e}")
    return nuevos, actualizados


def fetch_solicitudes(start: str, end: str) -> list[dict]:
    """
    Trae solicitudes de trabajo de AES Andes / Angamos / Cochrane desde API CEN SIP.
    Endpoint: /solicitudes-trabajo/v4/findByDate (plan SIP, page base 1, limit=100).
    Filtra localmente por empresa_nombre o grupo_nombre que contenga
    'AES ANDES' o 'ANGAMOS' o 'COCHRANE'.
    """
    if not CEN_USER_KEY:
        log.warning("  CEN_USER_KEY no configurada — saltando solicitudes")
        return []

    # Filtro estricto: solo empresa/grupo que sea AES ANDES, ANGAMOS o COCHRANE
    # (confirmado en producción 2026-06-17: aparece como "AES ANDES S.A.")
    EMPRESAS_AES = {"AES ANDES S.A.", "AES GENER", "ANGAMOS", "COCHRANE"}
    registros = []
    page = 1
    base_url = f"{API_BASE_SIP}/solicitudes-trabajo/v4/findByDate"

    try:
        while True:
            r = _get_with_retry(
                base_url,
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": 100},
            )
            body  = r.json()
            data  = body.get("data", [])
            total = body.get("totalPages", 1)

            if not data:
                break

            for rec in data:
                empresa = (rec.get("empresa_nombre") or "").strip()
                grupo   = (rec.get("grupo_nombre")   or "").strip()
                if empresa not in EMPRESAS_AES and grupo not in EMPRESAS_AES:
                    continue
                registros.append({
                    "id":                       rec.get("id"),
                    "correlativo":              int(rec["correlativo"]) if rec.get("correlativo") else None,
                    "empresa_nombre":           rec.get("empresa_nombre"),
                    "grupo_nombre":             rec.get("grupo_nombre"),
                    "instalacion_nombre":       rec.get("instalacion_nombre"),
                    "centro_control":           rec.get("centro_control"),
                    "status":                   rec.get("status"),
                    "tipo_solicitud":           rec.get("tipo_solicitud"),
                    "type":                     rec.get("type"),
                    "origen":                   rec.get("origen"),
                    "tipo_programacion":        rec.get("tipo_programacion"),
                    "consumo":                  rec.get("consumo"),
                    "descripcion_nivel_riesgo": rec.get("descripcion_nivel_riesgo"),
                    "fecha_inicio":             rec.get("fecha_inicio"),
                    "fecha_fin":                rec.get("fecha_fin"),
                    "created":                  rec.get("created"),
                    "modified":                 rec.get("modified"),
                    "partition_date":           rec.get("partition_date"),
                })

            log.info(f"  Solicitudes pág {page}/{total}")
            if page >= int(total):
                break
            page += 1

    except Exception as e:
        log.error(f"  Error solicitudes: {e}")

    log.info(f"  Solicitudes AES/ANG/CCR ({start}→{end}): {len(registros)} registros")
    return registros


def upsert_solicitudes(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO solicitudes_trabajo
            (id, correlativo, empresa_nombre, grupo_nombre, instalacion_nombre,
             centro_control, status, tipo_solicitud, type, origen,
             tipo_programacion, consumo, descripcion_nivel_riesgo,
             fecha_inicio, fecha_fin, created, modified, partition_date)
        VALUES
            (%(id)s, %(correlativo)s, %(empresa_nombre)s, %(grupo_nombre)s,
             %(instalacion_nombre)s, %(centro_control)s, %(status)s,
             %(tipo_solicitud)s, %(type)s, %(origen)s, %(tipo_programacion)s,
             %(consumo)s, %(descripcion_nivel_riesgo)s,
             %(fecha_inicio)s, %(fecha_fin)s, %(created)s, %(modified)s,
             %(partition_date)s)
        ON CONFLICT (id) DO UPDATE SET
            status             = EXCLUDED.status,
            fecha_inicio       = EXCLUDED.fecha_inicio,
            fecha_fin          = EXCLUDED.fecha_fin,
            modified           = EXCLUDED.modified
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
        log.error(f"  Error upsert solicitudes: {e}")
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

    # ── CMG múltiples nodos (S3) ──────────────────────────────
    # Va ANTES de PCP/PID (endpoints lentos paginados): es un GET rápido y es el
    # dato más sensible al tiempo real → no debe quedar sin correr si PCP/PID se
    # cuelgan y el job se cancela por timeout. (También se refresca cada 30 min en
    # Adquisicion_potencia.py.)
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

    # ── Generación programada PCP (rango completo en una sola llamada) ──
    # Ventana: ayer → mañana (3 días). Incluir mañana captura la programación
    # del día completo que CEN publica con anticipación. ~180 páginas ≈ 10 min.
    pcp_start = (hoy - timedelta(days=DIAS_VENTANA_PCP - 1)).strftime("%Y-%m-%d")
    pcp_end   = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    log.info(f"\n  ── Gen. programada PCP {pcp_start} → {pcp_end}")
    t0 = time.time()
    err_str = None
    try:
        regs                 = fetch_generacion_programada(pcp_start, pcp_end)
        nuevos, actualizados = upsert_generacion_programada(regs)
        log.info(f"  ✅ PCP: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ PCP: {e}"); nuevos = actualizados = 0
    log_adquisicion("generacion_programada_pcp", pcp_end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── Generación programada PID (Programa Intra-Día) ────────
    # Segunda fuente de programación: el PID reajusta el PCP durante el día.
    # Mismo rango que el PCP; 1-indexado y se conserva el programa más reciente.
    pid_start = (hoy - timedelta(days=DIAS_VENTANA_PCP - 1)).strftime("%Y-%m-%d")
    pid_end   = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    log.info(f"\n  ── Gen. programada PID {pid_start} → {pid_end}")
    t0 = time.time()
    err_str = None
    try:
        regs                 = fetch_generacion_programada_pid(pid_start, pid_end)
        nuevos, actualizados = upsert_generacion_programada(regs)
        log.info(f"  ✅ PID: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ PID: {e}"); nuevos = actualizados = 0
    log_adquisicion("generacion_programada_pid", pid_end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── CMG programado PID (Crucero/Tarapacá) ─────────────────
    # Mismo patrón paginado que el PCP. Ventana ayer→mañana para capturar el
    # programa del día completo que CEN publica con anticipación.
    cmgp_start = (hoy - timedelta(days=DIAS_VENTANA_PCP - 1)).strftime("%Y-%m-%d")
    cmgp_end   = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    log.info(f"\n  ── CMG programado PID {cmgp_start} → {cmgp_end}")
    t0 = time.time()
    err_str = None
    try:
        regs_cmgp            = fetch_cmg_programado(cmgp_start, cmgp_end)
        nuevos, actualizados = upsert_cmg_programado(regs_cmgp)
        log.info(f"  ✅ CMG programado: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ CMG programado: {e}"); nuevos = actualizados = 0
    log_adquisicion("cmg_programado_pid", cmgp_end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── CMG real oficial liquidado (Crucero/Tarapacá) ─────────
    # Se liquida con rezago ~10 días → ventana de 16 a 5 días atrás.
    cmgr_start = (hoy - timedelta(days=16)).strftime("%Y-%m-%d")
    cmgr_end   = (hoy - timedelta(days=5)).strftime("%Y-%m-%d")
    log.info(f"\n  ── CMG real {cmgr_start} → {cmgr_end}")
    t0 = time.time()
    err_str = None
    try:
        regs_cmgr            = fetch_cmg_real(cmgr_start, cmgr_end)
        nuevos, actualizados = upsert_cmg_real(regs_cmgr)
        log.info(f"  ✅ CMG real: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ CMG real: {e}"); nuevos = actualizados = 0
    log_adquisicion("cmg_real", cmgr_end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── Pronóstico de demanda corto plazo (Crucero/Laberinto/Angamos/Mejillones) ──
    # Pronóstico futuro: ventana hoy → +2 días. Contexto de demanda para anticipar CMG.
    dem_start = hoy.strftime("%Y-%m-%d")
    dem_end   = (hoy + timedelta(days=2)).strftime("%Y-%m-%d")
    log.info(f"\n  ── Pronóstico demanda {dem_start} → {dem_end}")
    t0 = time.time()
    err_str = None
    try:
        regs_dem             = fetch_pronostico_demanda(dem_start, dem_end)
        nuevos, actualizados = upsert_pronostico_demanda(regs_dem)
        log.info(f"  ✅ Demanda: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ Demanda: {e}"); nuevos = actualizados = 0
    log_adquisicion("pronostico_demanda", dem_end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── SSCC instrucciones (ventana de días) ──────────────────
    for fecha in fechas:
        log.info(f"\n  ── SSCC instrucciones {fecha}")
        t0 = time.time()
        err_str = None
        try:
            regs_sscc            = fetch_sscc(fecha)
            nuevos, actualizados = upsert_sscc(regs_sscc)
            log.info(f"  ✅ SSCC: {nuevos} nuevos, {actualizados} actualizados")
        except Exception as e:
            err_str = str(e); log.error(f"  ❌ SSCC: {e}"); nuevos = actualizados = 0
        log_adquisicion("sscc_instrucciones", fecha, nuevos, actualizados,
                        int((time.time() - t0) * 1000), err_str)

    # ── Instrucciones operacionales CMG (despacho por unidad) ────
    for fecha in fechas:
        log.info(f"\n  ── Instrucciones CMG {fecha}")
        t0 = time.time()
        err_str = None
        try:
            regs_icmg            = fetch_instrucciones_cmg(fecha)
            nuevos, actualizados = upsert_instrucciones_cmg(regs_icmg)
            log.info(f"  ✅ Instrucciones CMG: {nuevos} nuevos, {actualizados} actualizados")
        except Exception as e:
            err_str = str(e); log.error(f"  ❌ Instrucciones CMG: {e}"); nuevos = actualizados = 0
        log_adquisicion("instrucciones_cmg", fecha, nuevos, actualizados,
                        int((time.time() - t0) * 1000), err_str)

    # ── Limitaciones transmisión ANG/CCR (ventana amplia) ────────
    lim_start = (hoy - timedelta(days=DIAS_VENTANA_LIM)).strftime("%Y-%m-%d")
    lim_end   = hoy.strftime("%Y-%m-%d")
    log.info(f"\n  ── Limitaciones transmisión {lim_start} → {lim_end}")
    t0 = time.time()
    err_str = None
    try:
        regs_lim             = fetch_limitaciones(lim_start, lim_end)
        nuevos, actualizados = upsert_limitaciones(regs_lim)
        log.info(f"  ✅ Limitaciones: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ Limitaciones: {e}"); nuevos = actualizados = 0
    log_adquisicion("limitaciones_transmision", lim_end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── Solicitudes de trabajo AES/ANG/CCR (ventana 7 días) ──────
    sol_start = (hoy - timedelta(days=7)).strftime("%Y-%m-%d")
    sol_end   = hoy.strftime("%Y-%m-%d")
    log.info(f"\n  ── Solicitudes de trabajo {sol_start} → {sol_end}")
    t0 = time.time()
    err_str = None
    try:
        regs_sol             = fetch_solicitudes(sol_start, sol_end)
        nuevos, actualizados = upsert_solicitudes(regs_sol)
        log.info(f"  ✅ Solicitudes: {nuevos} nuevos, {actualizados} actualizados")
    except Exception as e:
        err_str = str(e); log.error(f"  ❌ Solicitudes: {e}"); nuevos = actualizados = 0
    log_adquisicion("solicitudes_trabajo", sol_end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    log.info(f"\n  Fin adquisición\n")


if __name__ == "__main__":
    run()
