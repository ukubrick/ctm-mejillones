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

# CMG programado PCP/PID: llave_cmg de la API → nombre de barra usado en el dashboard
# (Crucero/Tarapacá cruzan con el CMG online del S3). Desde 2026-07-08 se agregan
# las barras de las PROPIAS centrales: Angamos220/Cochrane220 existen en el catálogo
# de llaves del PCP y del PID (verificado en vivo, 257 llaves) y en el CMG real vía
# bar_transf. El S3 online NO las trae (solo 8 barras) → el online sigue en Crucero.
CMG_PROG_BARRAS = {
    "Crucero220":  "CRUCERO_______220",
    "Tarapaca220": "TARAPACA______220",
    "Angamos220":  "ANGAMOS_______220",
    "Cochrane220": "COCHRANE______220",
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
        time.sleep(0.5)
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
            time.sleep(0.15)

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
            time.sleep(0.15)

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


_origen_col_ok = False


def _ensure_origen_col(cur):
    """Asegura la columna `origen` en generacion_real (idempotente, 1 vez/proceso).

    Permite que un ingreso manual (origen='MANUAL') no sea sobreescrito por la
    adquisición automática. Se auto-crea aquí para no depender de una migración
    manual: en Actions el puerto 5432 no está bloqueado."""
    global _origen_col_ok
    if _origen_col_ok:
        return
    cur.execute("ALTER TABLE generacion_real ADD COLUMN IF NOT EXISTS origen text;")
    _origen_col_ok = True


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
            WHERE generacion_real.origen IS DISTINCT FROM 'MANUAL'
              AND (generacion_real.gen_real_mw = 0
                   OR EXCLUDED.gen_real_mw > 0)
    """
    nuevos = dupes = 0
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                _ensure_origen_col(cur)
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


def fetch_cmg_programado(start: str, end: str, fuente: str = "CEN_PID") -> list[dict]:
    """
    Trae el CMG programado (PID o PCP) de las barras de CMG_PROG_BARRAS
    (Crucero/Tarapacá + Angamos/Cochrane, las barras de las propias centrales).

    Endpoints: /cmg-programado-pid/v4/findByDate (fuente='CEN_PID') o
    /cmg-programado-pcp/v4/findByDate (fuente='CEN_PCP'). Ambos son 1-indexados
    (page=0 devuelve 502, verificado 2026-07-08 también para el PCP).
    No filtran por barra en el servidor → se pagina todo y se filtra localmente
    por llave_cmg ∈ CMG_PROG_BARRAS. Se conserva el programa más reciente
    (mayor fecha_programa) para cada (barra, fecha_hora).
    """
    endpoint = "cmg-programado-pcp" if fuente == "CEN_PCP" else "cmg-programado-pid"
    mejor: dict[tuple, dict] = {}   # (barra, fecha_hora) → registro
    page  = 1   # 1-indexado (page=0 devuelve 502)
    limit = 2000
    try:
        while True:
            r = _get_with_retry(
                f"{API_BASE_SIP}/{endpoint}/v4/findByDate",
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
                        "fuente":         fuente,
                    }

            total_pages = body.get("totalPages")
            if total_pages is None or page >= int(total_pages):
                break
            page += 1

        log.info(f"  CMG programado {fuente} ({start}→{end}): {len(mejor)} registros "
                 f"({len(CMG_PROG_BARRAS)} barras)")
    except Exception as e:
        log.error(f"  Error CMG programado {fuente}: {e}")
    return list(mejor.values())


def upsert_cmg_programado(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO costo_marginal_programado
            (barra, fecha_hora, cmg_usd_mwh, fecha_programa, fuente)
        VALUES
            (%(barra)s, %(fecha_hora)s, %(cmg_usd_mwh)s, %(fecha_programa)s,
             %(fuente)s)
        ON CONFLICT (barra, fecha_hora, fuente) DO UPDATE
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
    Trae el CMG real oficial liquidado de las barras de CMG_PROG_BARRAS
    (Crucero/Tarapacá + Angamos/Cochrane — el filtro bar_transf acepta las barras
    de las propias centrales: ANGAMOS_______220 / COCHRANE______220, verificado
    2026-07-08).

    Endpoint: /costo-marginal-real/v4/findByDate (SIP, 1-indexado).
    SÍ filtra por barra en el servidor con `bar_transf` (baja de ~12.500 a ~5 págs).
    OJO: el CMG real se liquida con rezago (~10 días); fechas recientes devuelven 0.
    Se conservan solo los valores en hora en punto (min == 0) para cruzar con CMG
    online/programado, que son horarios.
    """
    registros = []
    for barra in CMG_PROG_BARRAS.values():
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
        time.sleep(0.5)
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
            time.sleep(0.15)
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


def fetch_sscc(start: str, end: str | None = None) -> list[dict]:
    """
    Trae instrucciones SSCC de ANG1/2 CCR1/2 desde la API CEN Operaciones.
    Endpoint: /servicios-complementarios/v1 (pageSize=-1 para traer todo en una
    sola llamada). Acepta rango initDate→endDate: una llamada cubre la ventana
    completa en vez de una por día.
    """
    if not CEN_OPS_KEY:
        log.warning("  CEN_OPS_KEY no configurada — saltando SSCC")
        return []
    end = end or start

    registros = []
    try:
        r = _get_with_retry(
            f"{API_BASE_OPS}/servicios-complementarios/v1",
            params={"user_key": CEN_OPS_KEY, "initDate": start, "endDate": end,
                    "page": 0, "pageSize": -1},
            timeout=60,
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

        log.info(f"  SSCC ANG/CCR ({start}→{end}): {len(registros)} registros")
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


def fetch_instrucciones_cmg(start: str, end: str | None = None) -> list[dict]:
    """
    Trae instrucciones operacionales de despacho por CMG de ANG1/2 CCR1/2.
    Endpoint: /instrucciones-operacionales-cmg/v4/findByDate (plan SIP, 1-indexado).
    Acepta rango startDate→endDate (una paginación para toda la ventana).
    No filtra por central en el servidor → se pagina todo (~25 págs/día) y se
    filtra localmente por el campo `central` ∈ LLAVES_INSTR_CMG. id_central e
    id_unidad_generadora vienen vacíos en la respuesta, por eso se usa `central`.
    """
    if not CEN_USER_KEY:
        log.warning("  CEN_USER_KEY no configurada — saltando instrucciones CMG")
        return []
    end = end or start

    registros = []
    page  = 1   # 1-indexado
    limit = 100
    try:
        while True:
            r = _get_with_retry(
                f"{API_BASE_SIP}/instrucciones-operacionales-cmg/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": limit},
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

        log.info(f"  Instrucciones CMG ({start}→{end}): {len(registros)} registros ANG/CCR")
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


# Relevancia CTM para mantenimientos mayores: instalaciones del complejo o de su
# corredor de evacuación (la S/E O'Higgins y la línea Mejillones–O'Higgins afectan
# la evacuación de CTM; mismo criterio de claves que las solicitudes de trabajo).
CLAVES_MANT_CTM = ("ANGAMOS", "COCHRANE", "MEJILLONES", "O'HIGGINS",
                   "LABERINTO", "KAPATUR", "CRUCERO")


def fetch_mantenimiento_mayor(start: str, end: str) -> list[dict]:
    """
    Programas de mantenimiento mayor relevantes para CTM.

    Endpoint: /programas-mantenimiento-mayor/v4/findByDate (SIP, 1-indexado,
    liviano: ~108 filas/30 días con totalPages=1). El rango de fechas filtra por
    la fecha de PUBLICACIÓN (campo `date`), no por las fechas del programa → una
    ventana de ~45 días captura también mantenimientos futuros ya publicados.
    Sin id_central en la respuesta → filtro local por texto (CLAVES_MANT_CTM).
    """
    if not CEN_USER_KEY:
        log.warning("  CEN_USER_KEY no configurada — saltando mantenimiento mayor")
        return []
    registros, page = [], 1
    try:
        while True:
            r = _get_with_retry(
                f"{API_BASE_SIP}/programas-mantenimiento-mayor/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": 500},
            )
            body = r.json()
            data = body.get("data", [])
            if not data:
                break
            for rec in data:
                texto = " ".join(str(rec.get(c) or "") for c in
                                 ("nombre_instalacion", "nombre_sub_instalacion",
                                  "elemento_instalacion")).upper()
                if not any(k in texto for k in CLAVES_MANT_CTM):
                    continue
                corr = rec.get("correlativo")
                registros.append({
                    "correlativo":            str(int(float(corr))) if corr not in (None, "") else "",
                    "mantenimiento_nup":      str(rec.get("mantenimiento_nup") or ""),
                    "nombre_instalacion":     rec.get("nombre_instalacion"),
                    "nombre_sub_instalacion": str(rec.get("nombre_sub_instalacion") or ""),
                    "tipo_instalacion":       rec.get("tipo_instalacion"),
                    "elemento_instalacion":   rec.get("elemento_instalacion"),
                    "descripcion_trabajo":    rec.get("descripcion_trabajo"),
                    "estado":                 rec.get("estado"),
                    "riesgo":                 rec.get("riesgo"),
                    "postergable":            rec.get("postergable"),
                    "consumos_afectados":     rec.get("consumos_afectados"),
                    "fecha_inicio_programa":  str(rec.get("fecha_inicio_programa") or ""),
                    "fecha_fin_programa":     rec.get("fecha_fin_programa"),
                    "fecha_inicio_real":      rec.get("fecha_inicio_real_programa"),
                    "fecha_termino_real":     rec.get("fecha_termino_real_programa"),
                    "fecha_dato":             rec.get("date"),
                })
            total_pages = body.get("totalPages")
            if total_pages is None or page >= int(total_pages):
                break
            page += 1
            time.sleep(0.15)
        log.info(f"  Mantenimiento mayor ({start}→{end}): {len(registros)} programas CTM")
    except Exception as e:
        log.error(f"  Error mantenimiento mayor: {e}")
    return registros


def upsert_mantenimiento_mayor(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO mantenimiento_mayor
            (correlativo, mantenimiento_nup, nombre_instalacion, nombre_sub_instalacion,
             tipo_instalacion, elemento_instalacion, descripcion_trabajo, estado, riesgo,
             postergable, consumos_afectados, fecha_inicio_programa, fecha_fin_programa,
             fecha_inicio_real, fecha_termino_real, fecha_dato)
        VALUES
            (%(correlativo)s, %(mantenimiento_nup)s, %(nombre_instalacion)s,
             %(nombre_sub_instalacion)s, %(tipo_instalacion)s, %(elemento_instalacion)s,
             %(descripcion_trabajo)s, %(estado)s, %(riesgo)s, %(postergable)s,
             %(consumos_afectados)s, %(fecha_inicio_programa)s, %(fecha_fin_programa)s,
             %(fecha_inicio_real)s, %(fecha_termino_real)s, %(fecha_dato)s)
        ON CONFLICT (correlativo, nombre_sub_instalacion, fecha_inicio_programa)
        DO UPDATE SET
            estado              = EXCLUDED.estado,
            riesgo              = EXCLUDED.riesgo,
            descripcion_trabajo = EXCLUDED.descripcion_trabajo,
            fecha_fin_programa  = EXCLUDED.fecha_fin_programa,
            fecha_inicio_real   = EXCLUDED.fecha_inicio_real,
            fecha_termino_real  = EXCLUDED.fecha_termino_real,
            fecha_dato          = EXCLUDED.fecha_dato
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
        log.error(f"  Error upsert mantenimiento mayor: {e}")
    return nuevos, actualizados


def fetch_demanda_neta(start: str, end: str) -> list[dict]:
    """
    Demanda neta horaria del SEN (gen. bruta, ERV, consumos propios, demanda neta).

    Endpoint: /demanda-neta/v4/findByDate (SIP, 1-indexado, liviano: ~24 filas/día
    en 1 página). Publica con rezago de ~1 día. Es el driver principal del CMG →
    se usa como feature del forecast de precios en ml.py.
    """
    registros, page = [], 1
    try:
        while True:
            r = _get_with_retry(
                f"{API_BASE_SIP}/demanda-neta/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": start,
                        "endDate": end, "page": page, "limit": 1000},
            )
            body = r.json()
            data = body.get("data", [])
            if not data:
                break
            for rec in data:
                fh = (rec.get("fecha_hora") or "").replace("T", " ")[:19]
                if not fh:
                    continue
                registros.append({
                    "fecha_hora":       fh,
                    "hora":             int(rec.get("hora") or 0),
                    "gen_bruta_mwh":    rec.get("gen_bruta_mwh"),
                    "gen_erv_mwh":      rec.get("gen_erv_mwh"),
                    "cons_propio_mwh":  rec.get("cons_propio_mwh"),
                    "demanda_neta_mwh": rec.get("demanda_neta_mwh"),
                })
            total_pages = body.get("totalPages")
            if total_pages is None or page >= int(total_pages):
                break
            page += 1
            time.sleep(0.15)
        log.info(f"  Demanda neta ({start}→{end}): {len(registros)} registros")
    except Exception as e:
        log.error(f"  Error demanda neta: {e}")
    return registros


def upsert_demanda_neta(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO demanda_neta
            (fecha_hora, hora, gen_bruta_mwh, gen_erv_mwh, cons_propio_mwh,
             demanda_neta_mwh)
        VALUES
            (%(fecha_hora)s, %(hora)s, %(gen_bruta_mwh)s, %(gen_erv_mwh)s,
             %(cons_propio_mwh)s, %(demanda_neta_mwh)s)
        ON CONFLICT (fecha_hora) DO UPDATE SET
            gen_bruta_mwh    = EXCLUDED.gen_bruta_mwh,
            gen_erv_mwh      = EXCLUDED.gen_erv_mwh,
            cons_propio_mwh  = EXCLUDED.cons_propio_mwh,
            demanda_neta_mwh = EXCLUDED.demanda_neta_mwh
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
        log.error(f"  Error upsert demanda neta: {e}")
    return nuevos, actualizados


def fetch_mix_diario(fecha: str) -> list[dict]:
    """
    Mix de generación diaria del SEN por tecnología (térmica, solar, eólica…).

    Endpoint: /generacion-real/v3/getDailySum?date= (SIP, una llamada por día,
    devuelve ~7 pares key/value con los totales en MWh). Contexto del peso
    térmico del sistema para la vista Costos.
    """
    try:
        r = _get_with_retry(
            f"{API_BASE_SIP}/generacion-real/v3/getDailySum",
            params={"user_key": CEN_USER_KEY, "date": fecha},
        )
        data = r.json().get("data", [])
        registros = [{"fecha": fecha, "tecnologia": rec.get("key"),
                      "energia_mwh": rec.get("value")}
                     for rec in data if rec.get("key")]
        log.info(f"  Mix diario ({fecha}): {len(registros)} tecnologías")
        return registros
    except Exception as e:
        log.error(f"  Error mix diario {fecha}: {e}")
        return []


def upsert_mix_diario(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO mix_generacion_diaria (fecha, tecnologia, energia_mwh)
        VALUES (%(fecha)s, %(tecnologia)s, %(energia_mwh)s)
        ON CONFLICT (fecha, tecnologia) DO UPDATE SET
            energia_mwh = EXCLUDED.energia_mwh
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
        log.error(f"  Error upsert mix diario: {e}")
    return nuevos, actualizados


def fetch_desempeno_sscc(fecha: str) -> list[dict]:
    """
    Indicadores de desempeño SSCC (CPF y CSF) por unidad para UN día.

    Endpoints: /indicador-desempeno-cpf/v4/findByDate y -csf/v4 (SIP, 1-indexados,
    ~3 págs/día con limit=1000). Horarios por unidad; los factores determinan la
    remuneración SSCC. Se filtra por id_unidad ∈ ID_UNIDAD_MAP (1965-1968) — NO por
    texto: 'ANG' también calza con Angostura. `hora` viene 0-23 (string).
    ⚠️ El CEN publica estos indicadores con rezago de 2-3 MESES y con huecos
    (verificado 2026-07-08: ene/mar/abr con datos; feb/may/jun aún vacíos).
    """
    registros = []
    for tipo, ep in (("CPF", "indicador-desempeno-cpf"),
                     ("CSF", "indicador-desempeno-csf")):
        page = 1
        try:
            while True:
                r = _get_with_retry(
                    f"{API_BASE_SIP}/{ep}/v4/findByDate",
                    params={"user_key": CEN_USER_KEY, "startDate": fecha,
                            "endDate": fecha, "page": page, "limit": 1000},
                )
                body = r.json()
                data = body.get("data", [])
                if not data:
                    break
                for rec in data:
                    unidad = ID_UNIDAD_MAP.get(rec.get("id_unidad"))
                    if unidad is None:
                        continue
                    try:
                        h = int(rec.get("hora") or 0)
                    except (TypeError, ValueError):
                        h = 0
                    sufijo = tipo.lower()
                    detalle = (rec.get("fact_csf") if tipo == "CSF"
                               else rec.get("equipo_registrador_validado"))
                    registros.append({
                        "unidad":     unidad,
                        "tipo":       tipo,
                        "fecha_hora": f"{str(rec.get('fecha'))[:10]} {h:02d}:00:00",
                        "hora":       h + 1,   # convención CEN 1-24
                        "fdis":       rec.get(f"fdis_{sufijo}"),
                        "desempeno":  rec.get(f"desempeno_{sufijo}"),
                        "factor":     rec.get(f"factor_desempeno_{sufijo}"),
                        "detalle":    str(detalle) if detalle is not None else None,
                    })
                total_pages = body.get("totalPages")
                if total_pages is None or page >= int(total_pages):
                    break
                page += 1
                time.sleep(0.15)
        except Exception as e:
            log.error(f"  Error desempeño {tipo} {fecha}: {e}")
        time.sleep(0.3)
    if registros:
        log.info(f"  Desempeño SSCC ({fecha}): {len(registros)} registros ANG/CCR")
    return registros


def upsert_desempeno_sscc(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO desempeno_sscc
            (unidad, tipo, fecha_hora, hora, fdis, desempeno, factor, detalle)
        VALUES
            (%(unidad)s, %(tipo)s, %(fecha_hora)s, %(hora)s, %(fdis)s,
             %(desempeno)s, %(factor)s, %(detalle)s)
        ON CONFLICT (unidad, tipo, fecha_hora) DO UPDATE SET
            fdis      = EXCLUDED.fdis,
            desempeno = EXCLUDED.desempeno,
            factor    = EXCLUDED.factor,
            detalle   = EXCLUDED.detalle
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
        log.error(f"  Error upsert desempeño SSCC: {e}")
    return nuevos, actualizados


def dias_faltantes_desempeno(dias_atras: int = 150, margen: int = 20,
                             cap: int = 120) -> list[str]:
    """
    Días SIN registros en desempeno_sscc dentro de [hoy-dias_atras, hoy-margen],
    de más reciente a más antiguo, acotados a `cap` por corrida.

    Los indicadores CPF/CSF publican con rezago de 2-3 meses y por bloques: la
    corrida diaria sondea solo los días faltantes (un día vacío cuesta 2 requests),
    así que cuando el CEN publica un mes nuevo se incorpora solo.
    """
    hoy = datetime.now(TZ_CHILE).date()
    ini = hoy - timedelta(days=dias_atras)
    fin = hoy - timedelta(days=margen)
    presentes: set[str] = set()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT substring(fecha_hora, 1, 10) FROM desempeno_sscc "
                    "WHERE fecha_hora >= %s", (ini.strftime("%Y-%m-%d"),))
                presentes = {r[0] for r in cur.fetchall()}
    except Exception as e:
        log.warning(f"  No se pudo leer días presentes de desempeno_sscc: {e}")
    faltantes = []
    d = fin
    while d >= ini and len(faltantes) < cap:
        s = d.strftime("%Y-%m-%d")
        if s not in presentes:
            faltantes.append(s)
        d -= timedelta(days=1)
    return faltantes


def _num_cl(v):
    """Número con coma decimal chilena ('277,99') → float, o None."""
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(".", "").replace(",", ".")) if "," in str(v) else float(v)
    except (ValueError, TypeError):
        return None


# id_unidad CEN → código interno (mismo mapeo que limitaciones)
IDS_UNIDAD_MAESTRO = {1965: "ANG1", 1966: "ANG2", 1967: "CCR1", 1968: "CCR2"}


def fetch_unidades_generadoras(fecha: str) -> list[dict]:
    """
    Maestro técnico de las 4 unidades desde /unidades-generadoras/v4/findByDate
    (SIP, 1-indexado, ~12 págs con limit=300). El endpoint publica fichas por
    fecha; no siempre aparecen las 4 unidades el mismo día → el upsert acumula.
    Valores numéricos vienen con coma decimal ('277,99').
    """
    if not CEN_USER_KEY:
        log.warning("  CEN_USER_KEY no configurada — saltando unidades generadoras")
        return []
    registros, page = [], 1
    try:
        while True:
            r = _get_with_retry(
                f"{API_BASE_SIP}/unidades-generadoras/v4/findByDate",
                params={"user_key": CEN_USER_KEY, "startDate": fecha,
                        "endDate": fecha, "page": page, "limit": 300},
            )
            body = r.json()
            data = body.get("data", [])
            if not data:
                break
            for rec in data:
                unidad = IDS_UNIDAD_MAESTRO.get(rec.get("id_unidad"))
                if unidad is None:
                    continue
                registros.append({
                    "unidad":              unidad,
                    "id_unidad":           rec.get("id_unidad"),
                    "id_central":          rec.get("id_central"),
                    "central":             rec.get("central"),
                    "unidad_nombre":       rec.get("unidad_nombre"),
                    "nemotecnico":         rec.get("unidad_nemotecnico"),
                    "propietario":         rec.get("nombre_propietario"),
                    "tecnologia":          rec.get("nombre_tecnologia"),
                    "punto_conexion":      rec.get("punto_conexion"),
                    "pot_max_bruta":       _num_cl(rec.get("pot_max_bruta")),
                    "pot_neta_efectiva":   _num_cl(rec.get("pot_neta_efectiva")),
                    "pot_min_tecnica":     _num_cl(rec.get("pot_min_tecnica")),
                    "min_tec_ctrl_frec":   _num_cl(rec.get("min_tecnico_control_frecuencia")),
                    "consumos_propios_pct": _num_cl(rec.get("%_consumos_propios")),
                    "tension_nominal":     _num_cl(rec.get("tension_nominal")),
                    "factor_pot_nominal":  _num_cl(rec.get("factor_pot_nominal")),
                    "fecha_dato":          fecha,
                })
            total_pages = body.get("totalPages")
            if total_pages is None or page >= int(total_pages):
                break
            page += 1
            time.sleep(0.15)
        # Dedup por unidad (el mismo registro se repite en varias páginas)
        registros = list({r["unidad"]: r for r in registros}.values())
        log.info(f"  Unidades generadoras ({fecha}): {len(registros)} fichas ANG/CCR")
    except Exception as e:
        log.error(f"  Error unidades generadoras: {e}")
    return registros


def upsert_unidades_maestro(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO unidades_maestro
            (unidad, id_unidad, id_central, central, unidad_nombre, nemotecnico,
             propietario, tecnologia, punto_conexion, pot_max_bruta, pot_neta_efectiva,
             pot_min_tecnica, min_tec_ctrl_frec, consumos_propios_pct, tension_nominal,
             factor_pot_nominal, fecha_dato)
        VALUES
            (%(unidad)s, %(id_unidad)s, %(id_central)s, %(central)s, %(unidad_nombre)s,
             %(nemotecnico)s, %(propietario)s, %(tecnologia)s, %(punto_conexion)s,
             %(pot_max_bruta)s, %(pot_neta_efectiva)s, %(pot_min_tecnica)s,
             %(min_tec_ctrl_frec)s, %(consumos_propios_pct)s, %(tension_nominal)s,
             %(factor_pot_nominal)s, %(fecha_dato)s)
        ON CONFLICT (unidad) DO UPDATE SET
            id_unidad            = EXCLUDED.id_unidad,
            central              = EXCLUDED.central,
            unidad_nombre        = EXCLUDED.unidad_nombre,
            nemotecnico          = EXCLUDED.nemotecnico,
            propietario          = EXCLUDED.propietario,
            tecnologia           = EXCLUDED.tecnologia,
            punto_conexion       = EXCLUDED.punto_conexion,
            pot_max_bruta        = EXCLUDED.pot_max_bruta,
            pot_neta_efectiva    = EXCLUDED.pot_neta_efectiva,
            pot_min_tecnica      = EXCLUDED.pot_min_tecnica,
            min_tec_ctrl_frec    = EXCLUDED.min_tec_ctrl_frec,
            consumos_propios_pct = EXCLUDED.consumos_propios_pct,
            tension_nominal      = EXCLUDED.tension_nominal,
            factor_pot_nominal   = EXCLUDED.factor_pot_nominal,
            fecha_dato           = EXCLUDED.fecha_dato
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
        log.error(f"  Error upsert unidades maestro: {e}")
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
    # ⚠️ SIEMPRE una llamada POR DÍA: el endpoint v3 TRUNCA los rangos multi-día
    # (verificado 2026-07-03: un rango de 4 días devolvió 146 de 192 registros
    # con totalPages=1 — el último día quedó cortado). No pasar rangos aquí.
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

    # ── Endpoints movidos a otros jobs (evita el timeout del horario) ──────
    #   · SSCC · Instrucciones CMG · Limitaciones  → Adquisicion_operaciones.py (cada 30 min)
    #   · Gen. real · CMG S3                        → también en Adquisicion_potencia.py (cada 30 min)
    #   · CMG real · Pronóstico demanda · Solicitudes · Unidades maestro (lentos, cambian poco)
    #     → Adquisicion_diaria.py (1×/día). El horario conserva su núcleo: PCP/PID/CMG-programado.

    log.info(f"\n  Fin adquisición\n")


if __name__ == "__main__":
    run()
