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

import os, re, sys, time, random, logging, requests, psycopg2
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

# Mínimo técnico de las unidades a carbón (MW). Un programa PCP/PID con un valor
# ESTRICTAMENTE entre 0 y este umbral se trata como fantasma de un programa
# preliminar: no debe ganarle a un valor válido en el dedup solo por ser de un
# `fecha_programa` más reciente.
#
# ⚠️ OJO (2026-07-29): el umbral NO es un criterio físico confiable. El CEN sí
# programa valores bajo 60 MW cuando la unidad explora NUEVOS mínimos técnicos
# (julio 2026: 28,3–55,2 MW, casi todos en ANG1, en campañas de varios días).
# Esas horas son legítimas. El umbral solo desempata (no borra filas), pero puede
# preferir una versión vieja ≥60 MW por sobre la prueba reemitida. Ver PENDIENTES
# VIVOS en CLAUDE.md antes de tocar esta lógica.
POT_MIN_PROG = 60.0

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

# Barras del CMG online por API (/costo-marginal-online/v4, resolución 15 min).
# A diferencia del S3, este endpoint SÍ trae las barras de las propias centrales
# (verificado en vivo 2026-07-29) → es la fuente principal desde esta fecha.
CMG_ONLINE_BARRAS = {
    "CRUCERO_______220",
    "TARAPACA______220",
    "ANGAMOS_______220",
    "COCHRANE______220",
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

# Mapeo `configuracion`/`llave_sscc` del SSCC PROGRAMADO PCP → código interno.
# Ojo: este endpoint NO usa la convención CCH del SSCC instruido ni de las
# instrucciones CMG — identifica la unidad como CENTRAL_N (verificado 2026-08-01).
LLAVES_SSCC_PROG = {
    "ANGAMOS_1":  "ANG1",
    "ANGAMOS_2":  "ANG2",
    "COCHRANE_1": "CCR1",
    "COCHRANE_2": "CCR2",
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
                # Descartar el 0.0 exacto: es una lectura SCADA faltante/mala del CEN,
                # no una detención real (que lee <5 MW pero rara vez 0.0 — ver regla 23).
                # Se deja la hora AUSENTE hasta que el CEN entregue el valor real; así no
                # se congelan ceros fantasma (p.ej. las 4 unidades a 0 en una misma hora).
                gen_mw = rec.get("gen_real_mw")
                if gen_mw is None or float(gen_mw) == 0.0:
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
            log.error(f"  Error gen. real {nombre}: {_redactar(e)}")
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


# ── Cliente HTTP del CEN ───────────────────────────────────────────────────────
# Sesión reutilizable: reusa la conexión TCP/TLS entre llamadas. En un barrido de
# 120 páginas evita 120 handshakes.
_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})

# Espaciado mínimo entre requests al CEN. Un throttle chico previene el 429 EN
# ORIGEN, y eso sale mucho más barato que pagarlo después: un solo 429 cuesta
# 10-40 s de backoff, o sea 30-130 veces este espaciado. Subirlo en los jobs que
# paginan el sistema completo; bajarlo a 0 solo si se mide que no hay 429.
_MIN_INTERVALO_S = float(os.getenv("CEN_THROTTLE_S") or 0.3)

# Base del backoff ante 429/5xx (10s, 20s, 40s). En los crons cortos y frecuentes
# conviene bajarla: con 4 requests, un 429 con base 10 cuesta más que TODO el
# trabajo útil del job.
_BACKOFF_BASE_S = float(os.getenv("CEN_BACKOFF_BASE_S") or 10)
_ULTIMO_REQUEST_TS = 0.0


def _throttle():
    global _ULTIMO_REQUEST_TS
    espera = _MIN_INTERVALO_S - (time.monotonic() - _ULTIMO_REQUEST_TS)
    if espera > 0:
        time.sleep(espera)
    _ULTIMO_REQUEST_TS = time.monotonic()


def _redactar(msg) -> str:
    """Quita la user_key de un mensaje de error.

    Las excepciones de `requests` incluyen la URL COMPLETA con el query string, o
    sea la key del CEN en claro. GitHub Actions enmascara los secrets, pero este
    repo es PÚBLICO y un log local o un traceback pegado en un issue la filtraría.
    """
    return re.sub(r"(user_key=)[^&\s'\")]+", r"\1***", str(msg))


def _get_with_retry(url: str, params: dict, timeout: int = 60,
                    max_retries: int = 3) -> requests.Response:
    """GET resiliente contra la API del CEN.

    - Reintenta 429 y 5xx; en 429 respeta el header `Retry-After` si viene.
    - Backoff exponencial CON JITTER: sin el jitter, varios reintentos se
      sincronizan y vuelven a chocar contra el rate limiter a la vez.
    - Un 4xx que no sea 429 falla rápido: no tiene sentido reintentar un 400/404.
    - SSLError NO se reintenta. Hereda de ConnectionError, así que el `except`
      genérico se lo tragaba y le aplicaba backoff a un problema que jamás se
      arregla esperando (un certificado vencido del lado del servidor). En Pulsar
      eso agotó el timeout del job sin traer un solo dato, y Actions lo marcó
      `cancelled` en vez de fallido, lo que despista el diagnóstico.
    """
    last_exc = None
    for intento in range(max_retries):
        try:
            _throttle()
            r = _SESSION.get(url, params=params, timeout=timeout)
        except requests.exceptions.SSLError as exc:
            log.error(f"  [SSL] Certificado inválido/vencido en el CEN: {_redactar(exc)}")
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            espera = _BACKOFF_BASE_S * 2 ** intento + random.uniform(0, 3)
            log.warning(f"  Error de red ({exc.__class__.__name__}) — "
                        f"reintento {intento+1}/{max_retries} en {espera:.0f}s")
            time.sleep(espera)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            retry_after = r.headers.get("Retry-After")
            espera = (float(retry_after) if retry_after and retry_after.isdigit()
                      else _BACKOFF_BASE_S * 2 ** intento + random.uniform(0, 3))
            log.warning(f"  HTTP {r.status_code} — reintento {intento+1}/{max_retries} "
                        f"en {espera:.0f}s")
            last_exc = requests.HTTPError(f"HTTP {r.status_code}")
            time.sleep(espera)
            continue
        r.raise_for_status()
        return r
    if last_exc:
        raise last_exc
    r.raise_for_status()
    return r


def preflight_cen(timeout: int = 15) -> tuple[bool, str]:
    """Sonda barata: ¿está viva la API del CEN antes de gastar el runner?

    Un fallo de TLS o de conexión acá significa que la API está caída del lado
    del CEN y NINGÚN paso va a funcionar: mejor abortar en un segundo que quemar
    el timeout completo del job en reintentos condenados. Un 4xx cuenta como
    "viva": responde, y ya es problema del endpoint puntual, no del host.
    """
    if not CEN_USER_KEY:
        return False, "CEN_USER_KEY no configurada"
    hoy = datetime.now(TZ_CHILE).strftime("%Y-%m-%d")
    try:
        r = _SESSION.get(
            f"{API_BASE_SIP}/generacion-real/v3/findByDate",
            params={"user_key": CEN_USER_KEY, "startDate": hoy, "endDate": hoy,
                    "idCentral": ID_ANGAMOS, "pageSize": 1, "page": 1},
            timeout=timeout,
        )
        if r.status_code >= 500:
            return False, f"API CEN responde {r.status_code} (caída del lado del CEN)"
        return True, "ok"
    except requests.exceptions.SSLError as e:
        return False, f"certificado TLS inválido/vencido en el CEN: {_redactar(e)}"
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        return False, f"API CEN inalcanzable: {_redactar(e)}"


# ── Paginado SIP: integridad del barrido ───────────────────────────────────────
# El SIP intercala páginas VACÍAS de forma no determinista: una respuesta con
# `data: []` en medio del feed NO significa que se acabó. Cortar ahí trunca el día
# en un punto aleatorio y, como el feed tampoco viene ordenado por hora, lo que se
# pierde son horas sueltas — no la cola. El síntoma no es un error ni una fila
# repetida: son menos datos, en silencio, distintos en cada corrida.
#
# Y el cuerpo de esa página vacía NO trae `totalPages`, así que preguntárselo a
# ella es preguntarle justo a la única página que no sabe cuántas hay: hay que
# RECORDAR el último conteo conocido del barrido.
#
# (Verificado en el proyecto Pulsar sobre este mismo SIP, reglas #55/#59/#62: el
#  cron de potencia cerraba en 1, 1, 2, 4 y 4 páginas de 11 en cinco corridas
#  seguidas, entre 0 y 126 de los 488 registros del día.)

def _total_pages(body, previo: int | None = None) -> int | None:
    """`totalPages` del body, o el ÚLTIMO conocido del mismo barrido."""
    tp = body.get("totalPages") if isinstance(body, dict) else None
    try:
        return int(tp) if tp is not None else previo
    except (TypeError, ValueError):
        return previo


def _pedir_pagina(url: str, params: dict, tag: str,
                  tp_previo: int | None = None, pagina_1based: int | None = None,
                  reintentos: int = 2) -> tuple[list, int | None]:
    """Pide una página del SIP y, si vuelve VACÍA existiendo más, la RE-pide.

    Saltear la página vacía evita truncar el barrido, pero sus filas se pierden
    igual. Como el hueco es no determinista, volver a pedir la MISMA página suele
    traerla con datos. Retorna (data, total_pages).
    """
    if pagina_1based is None:
        pagina_1based = int(params.get("page") or 1)
    data, tp = [], tp_previo
    for intento in range(reintentos + 1):
        body = _get_with_retry(url, params).json()
        data = body.get("data", []) if isinstance(body, dict) else []
        tp   = _total_pages(body, tp)
        if data or tp is None or pagina_1based >= tp:
            return data, tp
        if intento < reintentos:
            log.warning(f"  [{tag}] Página {pagina_1based}/{tp} vacía — la re-pido.")
            time.sleep(1.5)
    return data, tp


def _seguir_pese_a_vacia(tag: str, pagina_1based: int, tp: int | None) -> bool:
    """True si una página vacía es un hueco del feed y hay que seguir paginando."""
    if tp is None or pagina_1based >= tp:
        return False
    log.warning(f"  [{tag}] Página {pagina_1based}/{tp} vacía — sigo (hueco del feed).")
    return True


def _avisar_parcial(tag: str, paginas_ok: int, tp: int | None) -> None:
    """Métrica de VERIFICACIÓN del barrido, no de progreso.

    Una línea de log que nadie compara contra su valor esperado no sirve de nada:
    en Pulsar se imprimió `4 páginas → 126 registros` durante días mientras se
    perdía el 74% del día. Si el barrido cerró corto, tiene que decirlo.
    """
    if tp is not None and paginas_ok < tp:
        log.warning(f"  [{tag}] AVISO: barrido PARCIAL — {paginas_ok} páginas con "
                    f"datos de {tp}. Puede faltar información del período.")


def fetch_generacion_programada(start: str, end: str) -> list[dict]:
    """
    Trae generación programada PCP de ANG1/2 CCR1/2 desde la API CEN SIP.

    Endpoint: /generacion-programada-pcp/v4/findByDate
    No soporta filtro por central en el servidor, por lo que se pagina
    todo el resultado y se filtra localmente por id_central.
    Usa limit=5000 (estable) en vez de 50000 que provoca 504 en el servidor.

    ⚠️ El PCP entrega VARIAS versiones del programa por (unidad, fecha_hora),
    una por cada `fecha_programa` (día en que el CEN corrió el PCP). Hay que
    quedarse con la MÁS RECIENTE; si no, el upsert deja una versión arbitraria y
    aparecen valores fantasma (p.ej. 28 MW aislado entre horas a plena carga,
    de un programa preliminar con costo≈0). Mismo patrón que el PID.
    """
    ids_objetivo = {ID_ANGAMOS, ID_COCHRANE, str(ID_ANGAMOS), str(ID_COCHRANE)}
    page         = 0
    limit        = 5000
    # mejor programa por (unidad, fecha_hora) → (fecha_programa, registro)
    mejores: dict[tuple[str, str], tuple[str, dict]] = {}
    llaves_no_mapeadas: set[str] = set()

    tp_visto: int | None = None   # el body VACÍO no trae totalPages — recordarlo
    paginas_ok = 0

    try:
        while True:
            data, tp_visto = _pedir_pagina(
                f"{API_BASE_SIP}/generacion-programada-pcp/v4/findByDate",
                {"user_key": CEN_USER_KEY, "startDate": start,
                 "endDate": end, "page": page, "limit": limit},
                "PCP", tp_visto, pagina_1based=page + 1,
            )

            if not data:
                if not _seguir_pese_a_vacia("PCP", page + 1, tp_visto):
                    break
                page += 1
                continue

            paginas_ok += 1

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

                # Preferencia = (validez_física, fecha_programa). Un valor 0<mw<60
                # es fantasma (programa preliminar): NO debe ganarle a un valor válido
                # aunque sea de un programa más reciente. Entre valores de igual validez
                # gana el fecha_programa mayor (más nuevo). Si TODOS son inválidos, se
                # conserva el mejor disponible.
                mw       = float(rec.get("gen_programada_mw") or 0.0)
                valido   = not (0 < mw < POT_MIN_PROG)
                pref     = (valido, str(rec.get("fecha_programa") or ""))
                clave    = (unidad, fecha_hora_norm)
                if clave in mejores and mejores[clave][0] >= pref:
                    continue
                mejores[clave] = (pref, {
                    "unidad":            unidad,
                    "gen_programada_mw": mw,
                    "fecha_hora":        fecha_hora_norm,
                    "hora":              hora,
                    "fuente":            "CEN_PCP",
                })

            if tp_visto is None or page + 1 >= tp_visto:
                break

            page += 1
            time.sleep(0.15)

    except Exception as e:
        log.error(f"  Error gen. programada PCP: {_redactar(e)}")

    _avisar_parcial("PCP", paginas_ok, tp_visto)
    registros = [v[1] for v in mejores.values()]
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

    tp_visto: int | None = None
    paginas_ok = 0

    try:
        while True:
            data, tp_visto = _pedir_pagina(
                f"{API_BASE_SIP}/generacion-programada-pid/v4/findByDate",
                {"user_key": CEN_USER_KEY, "startDate": start,
                 "endDate": end, "page": page, "limit": limit},
                "PID", tp_visto,
            )
            if not data:
                if not _seguir_pese_a_vacia("PID", page, tp_visto):
                    break
                page += 1
                continue

            paginas_ok += 1

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

                # Preferencia = (validez_física, fecha_programa, hora_programa). Igual
                # que en el PCP: un valor 0<mw<60 es fantasma y no debe ganarle a un
                # valor válido aunque sea de un programa más reciente. Entre iguales gana
                # el programa más nuevo (fecha_programa + hora_programa).
                mw       = float(rec.get("gen_programada_mw") or 0.0)
                valido   = not (0 < mw < POT_MIN_PROG)
                pref     = (valido, str(rec.get("fecha_programa") or ""),
                            int(rec.get("hora_programa") or 0))
                clave = (unidad, fecha_hora_norm)
                if clave in mejores and mejores[clave][0] >= pref:
                    continue
                mejores[clave] = (pref, {
                    "unidad":            unidad,
                    "gen_programada_mw": mw,
                    "fecha_hora":        fecha_hora_norm,
                    "hora":              hora,
                    "fuente":            "CEN_PID",
                })

            if tp_visto is None or page >= tp_visto:
                break
            page += 1
            time.sleep(0.15)

    except Exception as e:
        log.error(f"  Error gen. programada PID: {_redactar(e)}")

    _avisar_parcial("PID", paginas_ok, tp_visto)
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
                total    = h.get("total")
                # Un CMG de 0 es un dato REAL (desacople) → no se descarta.
                # Solo se saltan los intervalos sin valor.
                if not hora_str or total is None:
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
        log.error(f"  Error CMG S3: {_redactar(e)}")
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
        log.error(f"  Error upsert gen. real: {_redactar(e)}")
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
        log.error(f"  Error upsert gen. programada: {_redactar(e)}")
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
        log.error(f"  Error upsert CMG: {_redactar(e)}")
    return nuevos, actualizados


def fetch_cmg_online_api(start: str, end: str,
                         ultimas_paginas: int | None = None) -> list[dict]:
    """
    CMG real EN LÍNEA con resolución de 15 min desde la API SIP
    (/costo-marginal-online/v4/findByDate), filtrado local a CMG_ONLINE_BARRAS.

    Reemplaza al feed S3 como fuente principal (patrón replicado de Pulsar):
      · trae las barras de las PROPIAS centrales (ANGAMOS_______220 /
        COCHRANE______220), que el S3 no expone;
      · NO descarta los valores 0 — el desacople con CMG=0 es un dato real.

    El feed es de TODO el sistema (~1.600 barras, ~40 páginas de 4000 por día) y
    NO filtra por barra en el servidor. Viene ordenado por fecha_minuto → con
    `ultimas_paginas=N` se bajan solo las N últimas páginas (lo más fresco), para
    el cron de 30 min. La última página suele venir vacía.
    """
    url   = f"{API_BASE_SIP}/costo-marginal-online/v4/findByDate"
    limit = 4000

    def _pedir(page: int) -> dict:
        r = _get_with_retry(url, {"startDate": start, "endDate": end,
                                  "limit": limit, "page": page,
                                  "user_key": CEN_USER_KEY}, timeout=90)
        return r.json()

    primera     = _pedir(1)
    total_pages = int(primera.get("totalPages") or 1)

    if ultimas_paginas and total_pages > ultimas_paginas:
        paginas    = range(total_pages - ultimas_paginas + 1, total_pages + 1)
        items_ini  = []
    else:
        paginas    = range(2, total_pages + 1)
        items_ini  = primera.get("data", [])

    # (barra, fecha_minuto) → registro. El dict deduplica reemitidos.
    mejor: dict[tuple[str, str], dict] = {}

    def _consumir(items):
        for rec in items:
            barra = rec.get("barra_transf")
            if barra not in CMG_ONLINE_BARRAS:
                continue
            fm = (rec.get("fecha_minuto") or rec.get("fecha_hora") or "").replace("T", " ")[:16]
            if len(fm) != 16:
                continue
            val = rec.get("cmg_usd_mwh_", rec.get("cmg_usd_mwh"))
            if val is None:
                continue
            mejor[(barra, fm)] = {
                "barra_transf": barra,
                "barra_info":   rec.get("barra_info"),
                "fecha_minuto": f"{fm}:00",
                "cmg_usd_mwh":  round(float(val), 4),
                "cmg_clp_kwh":  (round(float(rec["cmg_clp_kwh_"]), 4)
                                 if rec.get("cmg_clp_kwh_") is not None else None),
                "version":      rec.get("version") or "EN LINEA",
            }

    _consumir(items_ini)
    for pg in paginas:
        try:
            _consumir(_pedir(pg).get("data", []))
        except Exception as e:
            # Nunca loguear la excepción cruda: requests incluye la URL completa
            # (con user_key) y los logs de Actions son públicos.
            log.warning(f"  CMG online API: página {pg} falló ({e.__class__.__name__})")

    log.info(f"  CMG online API: {len(mejor)} puntos de 15 min "
             f"({len(paginas) + (1 if items_ini else 0)} de {total_pages} páginas)")
    return list(mejor.values())


def agregar_cmg_horario(registros_min: list[dict]) -> list[dict]:
    """Promedia los puntos de 15 min por (barra, hora) → filas para `costo_marginal`.

    A diferencia del feed S3, los valores 0 SÍ entran en el promedio: una hora
    completa en desacople debe quedar registrada como 0, no ausente.
    """
    por_hora: dict[tuple[str, str], list] = defaultdict(list)
    info: dict[str, str] = {}
    for r in registros_min:
        por_hora[(r["barra_transf"], r["fecha_minuto"][:13])].append(r["cmg_usd_mwh"])
        info.setdefault(r["barra_transf"], r.get("barra_info") or "")

    salida = []
    for (barra, hora_key), valores in por_hora.items():
        try:
            dt = datetime.strptime(hora_key, "%Y-%m-%d %H")
        except ValueError:
            continue
        salida.append({
            "barra_transf": barra,
            "barra_info":   info.get(barra) or f"Nodo {barra[:8].rstrip('_')} 220kV",
            "fecha_hora":   dt.strftime("%Y-%m-%d %H:%M:%S"),
            "hora":         dt.hour + 1,          # convención CEN 1-24
            "minuto":       0,
            "cmg_usd_mwh":  round(sum(valores) / len(valores), 4),
            "cmg_clp_kwh":  None,
            "version":      "EN LINEA",
        })
    return salida


def upsert_cmg_online_min(registros: list[dict]) -> tuple[int, int]:
    """Upsert de los puntos de 15 min en `costo_marginal_online_min`."""
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO costo_marginal_online_min
            (barra_transf, barra_info, fecha_minuto, cmg_usd_mwh, cmg_clp_kwh, version)
        VALUES
            (%(barra_transf)s, %(barra_info)s, %(fecha_minuto)s,
             %(cmg_usd_mwh)s, %(cmg_clp_kwh)s, %(version)s)
        ON CONFLICT (barra_transf, fecha_minuto) DO UPDATE
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
        log.error(f"  Error upsert CMG online min: {_redactar(e)}")
    return nuevos, actualizados


def adquirir_cmg_online(start: str, end: str,
                        ultimas_paginas: int | None = None) -> tuple[int, int]:
    """Trae el CMG online por API y escribe 15 min + agregado horario.

    Fallback al feed S3 si la API no devuelve nada (mantenimiento / 429 sostenido).
    Devuelve (puntos_15min, filas_horarias).
    """
    regs_min = []
    try:
        regs_min = fetch_cmg_online_api(start, end, ultimas_paginas)
    except Exception as e:
        log.error(f"  CMG online API falló: {_redactar(e)}")

    if not regs_min:
        log.warning("  CMG online API sin datos → fallback al feed S3")
        n, a = upsert_cmg(fetch_cmg_nodos())
        return 0, n + a

    upsert_cmg_online_min(regs_min)
    n, a = upsert_cmg(agregar_cmg_horario(regs_min))
    return len(regs_min), n + a


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
    tag = f"CMG-PROG {fuente}"
    tp_visto: int | None = None
    paginas_ok = 0
    try:
        while True:
            data, tp_visto = _pedir_pagina(
                f"{API_BASE_SIP}/{endpoint}/v4/findByDate",
                {"user_key": CEN_USER_KEY, "startDate": start,
                 "endDate": end, "page": page, "limit": limit},
                tag, tp_visto,
            )
            if not data:
                if not _seguir_pese_a_vacia(tag, page, tp_visto):
                    break
                page += 1
                continue

            paginas_ok += 1

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

            if tp_visto is None or page >= tp_visto:
                break
            page += 1

        log.info(f"  CMG programado {fuente} ({start}→{end}): {len(mejor)} registros "
                 f"({len(CMG_PROG_BARRAS)} barras)")
    except Exception as e:
        log.error(f"  Error CMG programado {fuente}: {_redactar(e)}")
    _avisar_parcial(tag, paginas_ok, tp_visto)
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
        log.error(f"  Error upsert CMG programado: {_redactar(e)}")
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
        tag = f"CMG-REAL {barra}"
        tp_visto: int | None = None
        paginas_ok = 0
        try:
            while True:
                data, tp_visto = _pedir_pagina(
                    f"{API_BASE_SIP}/costo-marginal-real/v4/findByDate",
                    {"user_key": CEN_USER_KEY, "startDate": start, "endDate": end,
                     "bar_transf": barra, "page": page, "limit": limit},
                    tag, tp_visto,
                )
                if not data:
                    if not _seguir_pese_a_vacia(tag, page, tp_visto):
                        break
                    page += 1
                    continue
                paginas_ok += 1
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
                if tp_visto is None or page >= tp_visto:
                    break
                page += 1
            log.info(f"  CMG real {barra} ({start}→{end}): {len(registros)-antes} registros")
        except Exception as e:
            log.error(f"  Error CMG real {barra}: {_redactar(e)}")
        _avisar_parcial(tag, paginas_ok, tp_visto)
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
        log.error(f"  Error upsert CMG real: {_redactar(e)}")
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
    tp_visto: int | None = None
    paginas_ok = 0
    try:
        while True:
            data, tp_visto = _pedir_pagina(
                f"{API_BASE_SIP}/pronosticos-demanda-corto-plazo/v4/findByDate",
                {"user_key": CEN_USER_KEY, "startDate": start,
                 "endDate": end, "page": page, "limit": limit},
                "PRON-DEM", tp_visto, pagina_1based=page + 1,
            )
            if not data:
                if not _seguir_pese_a_vacia("PRON-DEM", page + 1, tp_visto):
                    break
                page += 1
                continue
            paginas_ok += 1
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
            if tp_visto is None or page + 1 >= tp_visto:
                break
            page += 1
            time.sleep(0.15)
    except Exception as e:
        log.error(f"  Error pronóstico demanda: {_redactar(e)}")
    _avisar_parcial("PRON-DEM", paginas_ok, tp_visto)
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
        log.error(f"  Error upsert pronóstico demanda: {_redactar(e)}")
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
        log.error(f"  Error SSCC: {_redactar(e)}")

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
        log.error(f"  Error upsert SSCC: {_redactar(e)}")
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
    tp_visto: int | None = None
    paginas_ok = 0
    try:
        while True:
            data, tp_visto = _pedir_pagina(
                f"{API_BASE_SIP}/instrucciones-operacionales-cmg/v4/findByDate",
                {"user_key": CEN_USER_KEY, "startDate": start,
                 "endDate": end, "page": page, "limit": limit},
                "INSTR-CMG", tp_visto,
            )
            if not data:
                if not _seguir_pese_a_vacia("INSTR-CMG", page, tp_visto):
                    break
                page += 1
                continue

            paginas_ok += 1

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

            if tp_visto is None or page >= tp_visto:
                break
            page += 1

        log.info(f"  Instrucciones CMG ({start}→{end}): {len(registros)} registros ANG/CCR")
    except Exception as e:
        log.error(f"  Error instrucciones CMG: {_redactar(e)}")
    _avisar_parcial("INSTR-CMG", paginas_ok, tp_visto)
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
        log.error(f"  Error upsert instrucciones CMG: {_redactar(e)}")
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

    tp_visto: int | None = None
    paginas_ok = 0

    try:
        while True:
            data, tp_visto = _pedir_pagina(
                base_url,
                {"user_key": CEN_USER_KEY, "startDate": start,
                 "endDate": end, "page": page, "limit": 100},
                "LIMITACIONES", tp_visto,
            )
            total = tp_visto if tp_visto is not None else 1

            if not data:
                if not _seguir_pese_a_vacia("LIMITACIONES", page, tp_visto):
                    break
                page += 1
                continue

            paginas_ok += 1

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
        log.error(f"  Error limitaciones: {_redactar(e)}")

    _avisar_parcial("LIMITACIONES", paginas_ok, tp_visto)
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
        log.error(f"  Error upsert limitaciones: {_redactar(e)}")
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

    tp_visto: int | None = None
    paginas_ok = 0

    try:
        while True:
            data, tp_visto = _pedir_pagina(
                base_url,
                {"user_key": CEN_USER_KEY, "startDate": start,
                 "endDate": end, "page": page, "limit": 100},
                "SOLICITUDES", tp_visto,
            )
            total = tp_visto if tp_visto is not None else 1

            if not data:
                if not _seguir_pese_a_vacia("SOLICITUDES", page, tp_visto):
                    break
                page += 1
                continue

            paginas_ok += 1

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
        log.error(f"  Error solicitudes: {_redactar(e)}")

    _avisar_parcial("SOLICITUDES", paginas_ok, tp_visto)
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
        log.error(f"  Error upsert solicitudes: {_redactar(e)}")
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
    tp_visto: int | None = None
    paginas_ok = 0
    try:
        while True:
            data, tp_visto = _pedir_pagina(
                f"{API_BASE_SIP}/programas-mantenimiento-mayor/v4/findByDate",
                {"user_key": CEN_USER_KEY, "startDate": start,
                 "endDate": end, "page": page, "limit": 500},
                "MANT-MAYOR", tp_visto,
            )
            if not data:
                if not _seguir_pese_a_vacia("MANT-MAYOR", page, tp_visto):
                    break
                page += 1
                continue
            paginas_ok += 1
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
            if tp_visto is None or page >= tp_visto:
                break
            page += 1
            time.sleep(0.15)
        log.info(f"  Mantenimiento mayor ({start}→{end}): {len(registros)} programas CTM")
    except Exception as e:
        log.error(f"  Error mantenimiento mayor: {_redactar(e)}")
    _avisar_parcial("MANT-MAYOR", paginas_ok, tp_visto)
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
        log.error(f"  Error upsert mantenimiento mayor: {_redactar(e)}")
    return nuevos, actualizados


def fetch_demanda_neta(start: str, end: str) -> list[dict]:
    """
    Demanda neta horaria del SEN (gen. bruta, ERV, consumos propios, demanda neta).

    Endpoint: /demanda-neta/v4/findByDate (SIP, 1-indexado, liviano: ~24 filas/día
    en 1 página). Publica con rezago de ~1 día. Es el driver principal del CMG →
    se usa como feature del forecast de precios en ml.py.
    """
    registros, page = [], 1
    tp_visto: int | None = None
    paginas_ok = 0
    try:
        while True:
            data, tp_visto = _pedir_pagina(
                f"{API_BASE_SIP}/demanda-neta/v4/findByDate",
                {"user_key": CEN_USER_KEY, "startDate": start,
                 "endDate": end, "page": page, "limit": 1000},
                "DEMANDA-NETA", tp_visto,
            )
            if not data:
                if not _seguir_pese_a_vacia("DEMANDA-NETA", page, tp_visto):
                    break
                page += 1
                continue
            paginas_ok += 1
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
            if tp_visto is None or page >= tp_visto:
                break
            page += 1
            time.sleep(0.15)
        log.info(f"  Demanda neta ({start}→{end}): {len(registros)} registros")
    except Exception as e:
        log.error(f"  Error demanda neta: {_redactar(e)}")
    _avisar_parcial("DEMANDA-NETA", paginas_ok, tp_visto)
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
        log.error(f"  Error upsert demanda neta: {_redactar(e)}")
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
        log.error(f"  Error mix diario {fecha}: {_redactar(e)}")
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
        log.error(f"  Error upsert mix diario: {_redactar(e)}")
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
        tag = f"DESEMP-{tipo}"
        tp_visto: int | None = None
        paginas_ok = 0
        try:
            while True:
                data, tp_visto = _pedir_pagina(
                    f"{API_BASE_SIP}/{ep}/v4/findByDate",
                    {"user_key": CEN_USER_KEY, "startDate": fecha,
                     "endDate": fecha, "page": page, "limit": 1000},
                    tag, tp_visto,
                )
                if not data:
                    if not _seguir_pese_a_vacia(tag, page, tp_visto):
                        break
                    page += 1
                    continue
                paginas_ok += 1
                for rec in data:
                    unidad = ID_UNIDAD_MAP.get(rec.get("id_unidad"))
                    if unidad is None:
                        continue
                    try:
                        h = int(rec.get("hora") or 0)
                    except (TypeError, ValueError):
                        h = 0
                    # Día del cambio de hora en Chile (25 horas): el CEN emite
                    # hora '24', que no existe como timestamp naive → se omite.
                    if h > 23:
                        continue
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
                if tp_visto is None or page >= tp_visto:
                    break
                page += 1
                time.sleep(0.15)
        except Exception as e:
            log.error(f"  Error desempeño {tipo} {fecha}: {_redactar(e)}")
        _avisar_parcial(tag, paginas_ok, tp_visto)
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
        log.error(f"  Error upsert desempeño SSCC: {_redactar(e)}")
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
        log.warning(f"  No se pudo leer días presentes de desempeno_sscc: {_redactar(e)}")
    faltantes = []
    d = fin
    while d >= ini and len(faltantes) < cap:
        s = d.strftime("%Y-%m-%d")
        if s not in presentes:
            faltantes.append(s)
        d -= timedelta(days=1)
    return faltantes


def fetch_sscc_programado_pcp(fecha: str) -> list[dict]:
    """
    SSCC PROGRAMADO en el PCP para UN día — la provisión (MW) por unidad y tipo
    de servicio que el CEN programó, contraparte del SSCC instruido que ya se
    trae por Operaciones v1 y del desempeño CPF/CSF.

    Endpoint: /servicios-complementarios-programados-pcp/v4/findByDate (SIP).

    ⚠️ NO filtra por central en el servidor: `idCentral`, `id_central` y
    `centralId` se ignoran (verificado en vivo 2026-08-01 — los tres devuelven
    el sistema completo). Hay que paginar TODO el día y filtrar local por
    id_central ∈ {377, 379}. Con limit=5000 son ~121 páginas por día y la API
    estrangula a ~10 s/página bajo carga sostenida → ~21 min por día. Por eso
    corre en su propio workflow, con ventana de UN día.

    ⚠️ Igual que el PCP de generación, el día operativo llega con VARIAS
    versiones (una por `fecha_programa`, ~7 en la práctica) → se conserva la
    más reciente por (unidad, tipo_servicio, fecha_hora).

    Un `provision_mw` de 0 es un DATO (la unidad no fue comprometida en ese
    servicio esa hora), no un faltante — no se filtra.
    """
    url   = f"{API_BASE_SIP}/servicios-complementarios-programados-pcp/v4/findByDate"
    limit = 5000
    ids_objetivo = {ID_ANGAMOS, ID_COCHRANE, str(ID_ANGAMOS), str(ID_COCHRANE)}
    # (unidad, tipo_servicio, fecha_hora) → (fecha_programa, registro)
    mejores: dict[tuple[str, str, str], tuple[str, dict]] = {}

    def _consumir(items):
        for rec in items:
            if rec.get("id_central") not in ids_objetivo:
                continue
            unidad = LLAVES_SSCC_PROG.get(str(rec.get("configuracion") or "").strip())
            if unidad is None:
                continue
            fh = str(rec.get("fecha_hora") or "").replace("T", " ")[:19]
            if len(fh) != 19:
                continue
            tipo = str(rec.get("tipo_servicio") or "").strip()
            if not tipo:
                continue
            fprog = str(rec.get("fecha_programa") or "")[:10]
            clave = (unidad, tipo, fh)
            previo = mejores.get(clave)
            if previo is not None and previo[0] >= fprog:
                continue
            try:
                mw = float(rec.get("provision_mw") or 0.0)
            except (TypeError, ValueError):
                continue
            mejores[clave] = (fprog, {
                "unidad":         unidad,
                "tipo_servicio":  tipo,
                "fecha_hora":     fh,
                "hora":           int(fh[11:13]) + 1,   # convención CEN 1-24
                "provision_mw":   round(mw, 3),
                "barra":          rec.get("barra"),
                "llave_sscc":     rec.get("llave_sscc"),
                "fecha_programa": fprog or None,
            })

    try:
        primera     = _get_with_retry(url, {"user_key": CEN_USER_KEY, "startDate": fecha,
                                            "endDate": fecha, "page": 1, "limit": limit},
                                      timeout=90).json()
        total_pages = int(primera.get("totalPages") or 1)
        _consumir(primera.get("data", []))
        paginas_ok = 1
        paginas_vacias = 0
        for pg in range(2, total_pages + 1):
            try:
                body = _get_with_retry(url, {"user_key": CEN_USER_KEY, "startDate": fecha,
                                             "endDate": fecha, "page": pg, "limit": limit},
                                       timeout=90).json()
            except Exception as e:
                # Nunca loguear la excepción cruda: requests incluye la URL con la
                # user_key y los logs de Actions son públicos.
                log.warning(f"  SSCC programado: página {pg} falló ({e.__class__.__name__})")
                continue
            data = body.get("data", [])
            if not data:
                # Una página vacía es un hueco del feed, NO el fin: cortar acá
                # abandonaba el resto de las ~121 páginas del día en silencio.
                log.warning(f"  [SSCC-PROG] Página {pg}/{total_pages} vacía — sigo.")
                paginas_vacias += 1
                continue
            _consumir(data)
            paginas_ok += 1
            time.sleep(0.15)
        log.info(f"  SSCC programado PCP ({fecha}): {len(mejores)} filas ANG/CCR "
                 f"de {total_pages} páginas")
        if paginas_vacias:
            log.warning(f"  [SSCC-PROG] AVISO: {paginas_vacias} páginas vacías de "
                        f"{total_pages} — puede faltar información del día.")
    except Exception as e:
        log.error(f"  Error SSCC programado {fecha}: {e.__class__.__name__}")

    return [r for _, r in mejores.values()]


def upsert_sscc_programado(registros: list[dict]) -> tuple[int, int]:
    if not registros:
        return 0, 0
    sql = """
        INSERT INTO sscc_programado
            (unidad, tipo_servicio, fecha_hora, hora, provision_mw, barra,
             llave_sscc, fecha_programa)
        VALUES
            (%(unidad)s, %(tipo_servicio)s, %(fecha_hora)s, %(hora)s,
             %(provision_mw)s, %(barra)s, %(llave_sscc)s, %(fecha_programa)s)
        ON CONFLICT (unidad, tipo_servicio, fecha_hora) DO UPDATE SET
            provision_mw   = EXCLUDED.provision_mw,
            barra          = EXCLUDED.barra,
            llave_sscc     = EXCLUDED.llave_sscc,
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
        log.error(f"  Error upsert SSCC programado: {_redactar(e)}")
    return nuevos, actualizados


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
    tp_visto: int | None = None
    paginas_ok = 0
    try:
        while True:
            data, tp_visto = _pedir_pagina(
                f"{API_BASE_SIP}/unidades-generadoras/v4/findByDate",
                {"user_key": CEN_USER_KEY, "startDate": fecha,
                 "endDate": fecha, "page": page, "limit": 300},
                "UNIDADES", tp_visto,
            )
            if not data:
                if not _seguir_pese_a_vacia("UNIDADES", page, tp_visto):
                    break
                page += 1
                continue
            paginas_ok += 1
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
            if tp_visto is None or page >= tp_visto:
                break
            page += 1
            time.sleep(0.15)
        # Dedup por unidad (el mismo registro se repite en varias páginas)
        registros = list({r["unidad"]: r for r in registros}.values())
        log.info(f"  Unidades generadoras ({fecha}): {len(registros)} fichas ANG/CCR")
    except Exception as e:
        log.error(f"  Error unidades generadoras: {_redactar(e)}")
    _avisar_parcial("UNIDADES", paginas_ok, tp_visto)
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
        log.error(f"  Error upsert unidades maestro: {_redactar(e)}")
    return nuevos, actualizados


class ResumenCorrida:
    """Contabiliza los pasos de una corrida para decidir el código de salida.

    Por qué existe: los entrypoints atrapan la excepción de cada paso y siguen,
    así que una corrida que no adquirió NADA terminaba en `exit 0` y GitHub la
    marcaba VERDE. Un job verde sin datos es peor que uno rojo: oculta la caída.
    En Pulsar ese patrón le costó a este mismo proyecto ~19 h de datos sin que
    nadie lo notara (su regla #36).

    Criterio deliberado: se falla cuando NINGÚN paso funcionó (la fuente está
    caída o la credencial es inválida). Un fallo parcial deja la corrida verde
    pero grita en el log — porque un monitor que se pone rojo seguido entrena a
    ignorarlo, que es exactamente cómo se pierde el próximo fallo real.
    """

    def __init__(self, nombre: str):
        self.nombre = nombre
        self.ok: list[str] = []
        self.fallos: list[tuple[str, str]] = []

    def paso_ok(self, paso: str) -> None:
        self.ok.append(paso)

    def paso_fallo(self, paso: str, err) -> None:
        self.fallos.append((paso, _redactar(err)))

    def cerrar(self) -> int:
        """Loguea el resumen y devuelve el código de salida (0 ok / 1 fallo)."""
        log.info(f"\n  Resumen {self.nombre}: {len(self.ok)} pasos OK, "
                 f"{len(self.fallos)} con error")
        for paso, err in self.fallos:
            log.error(f"    ✗ {paso}: {err}")

        if self.fallos and not self.ok:
            log.error(f"  ❌ {self.nombre}: NINGÚN paso se completó — la corrida "
                      f"no adquirió datos. Saliendo con error.")
            return 1
        if self.fallos:
            log.warning(f"  ⚠ {self.nombre}: corrida PARCIAL — "
                        f"{len(self.fallos)} de {len(self.ok) + len(self.fallos)} "
                        f"pasos fallaron. Revisar el log.")
        return 0


def abortar_si_cen_caido(nombre: str) -> None:
    """Sonda la API del CEN y termina en rojo si está caída.

    Una corrida contra un host caído gasta el timeout completo del job en
    reintentos condenados sin traer un dato. Mejor abortar en un segundo.
    """
    vivo, motivo = preflight_cen()
    if not vivo:
        log.error(f"  ❌ {nombre}: preflight falló — {motivo}")
        sys.exit(1)
    log.info("  Preflight CEN: OK")


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
        log.warning(f"  No se pudo registrar log: {_redactar(e)}")


# ══════════════════════════════════════════════════════════════
# EJECUCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════

def run() -> int:
    log.info("═" * 58)
    log.info("  Adquisición CTM Mejillones — API CEN + CMG S3")
    log.info("═" * 58)

    if not CEN_USER_KEY:
        log.error("❌  CEN_USER_KEY no configurada"); sys.exit(1)
    if not DATABASE_URL:
        log.error("❌  DATABASE_URL no configurada"); sys.exit(1)

    abortar_si_cen_caido("Horaria")
    resumen = ResumenCorrida("Horaria")

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
            resumen.paso_ok("gen-real")
        except Exception as e:
            err_str = _redactar(e); log.error(f"  ❌ {_redactar(e)}"); nuevos = dupes = 0
            resumen.paso_fallo("gen-real", e)
        log_adquisicion("generacion_real", fecha, nuevos, dupes,
                        int((time.time() - t0) * 1000), err_str)

    # ── CMG múltiples nodos (S3) ──────────────────────────────
    # Va ANTES de PCP/PID (endpoints lentos paginados): es un GET rápido y es el
    # dato más sensible al tiempo real → no debe quedar sin correr si PCP/PID se
    # cuelgan y el job se cancela por timeout. (También se refresca cada 30 min en
    # Adquisicion_potencia.py.)
    # Día COMPLETO (todas las páginas) de hoy y ayer: rellena los huecos que el
    # cron rápido de 30 min (solo últimas páginas) no alcanzó a cubrir.
    for fecha in [(hoy - timedelta(days=1)).strftime("%Y-%m-%d"),
                  hoy.strftime("%Y-%m-%d")]:
        log.info(f"\n  ── CMG online 15 min (API SIP) {fecha}")
        t0 = time.time()
        err_str = None
        try:
            n_min, n_hora = adquirir_cmg_online(fecha, fecha)
            log.info(f"  ✅ CMG: {n_min} puntos de 15 min, {n_hora} filas horarias")
            resumen.paso_ok("cmg-online")
        except Exception as e:
            err_str = _redactar(e); log.error(f"  ❌ CMG: {_redactar(e)}"); n_min = n_hora = 0
            resumen.paso_fallo("cmg-online", e)
        log_adquisicion("cmg_online_min", fecha, n_min, n_hora,
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
        resumen.paso_ok("pcp")
    except Exception as e:
        err_str = _redactar(e); log.error(f"  ❌ PCP: {_redactar(e)}"); nuevos = actualizados = 0
        resumen.paso_fallo("pcp", e)
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
        resumen.paso_ok("pid")
    except Exception as e:
        err_str = _redactar(e); log.error(f"  ❌ PID: {_redactar(e)}"); nuevos = actualizados = 0
        resumen.paso_fallo("pid", e)
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
        resumen.paso_ok("cmg-programado")
    except Exception as e:
        err_str = _redactar(e); log.error(f"  ❌ CMG programado: {_redactar(e)}"); nuevos = actualizados = 0
        resumen.paso_fallo("cmg-programado", e)
    log_adquisicion("cmg_programado_pid", cmgp_end, nuevos, actualizados,
                    int((time.time() - t0) * 1000), err_str)

    # ── Endpoints movidos a otros jobs (evita el timeout del horario) ──────
    #   · SSCC · Instrucciones CMG · Limitaciones  → Adquisicion_operaciones.py (cada 30 min)
    #   · Gen. real · CMG S3                        → también en Adquisicion_potencia.py (cada 30 min)
    #   · CMG real · Pronóstico demanda · Solicitudes · Unidades maestro (lentos, cambian poco)
    #     → Adquisicion_diaria.py (1×/día). El horario conserva su núcleo: PCP/PID/CMG-programado.

    log.info("\n  Fin adquisición\n")
    return resumen.cerrar()


if __name__ == "__main__":
    sys.exit(run())
