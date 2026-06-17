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

# Mapeo centralUnidad → código interno (confirmado en API Operaciones 2026-06-09)
LLAVES_SSCC = {
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

    # ── Generación programada PCP (rango completo en una sola llamada) ──
    # Ventana propia de 2 días: ~120 páginas ≈ 8 min. Con 7 días serían ~427 páginas → timeout.
    pcp_fechas = [(hoy - timedelta(days=d)).strftime("%Y-%m-%d")
                  for d in range(DIAS_VENTANA_PCP - 1, -1, -1)]
    pcp_start = pcp_fechas[0]
    pcp_end   = pcp_fechas[-1]
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

    log.info(f"\n  Fin adquisición\n")


if __name__ == "__main__":
    run()
