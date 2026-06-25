# CLAUDE.md — Dashboard CTM Mejillones

## Qué es este proyecto
Dashboard operacional del Complejo Térmico Mejillones (AES Andes).
Monitorea generación real vs programada + CMG + SSCC para 4 unidades:
ANG1, ANG2 (Angamos) y CCR1, CCR2 (Cochrane).

Desplegado en Streamlit Cloud. Código en GitHub (`ukubrick/ctm-mejillones`).
Adquisición automática vía GitHub Actions cada hora (minuto 5 UTC) + corrida
ligera de gen. real cada 30 min (minutos :25 y :55).

## Workflow de potencia real cada 30 min (2026-06-24)

Réplica del patrón Pulsar (`ernc-aes-dashboard`, Sesión 25). Baja el lag de la
generación real corriéndola 3×/h en vez de 1×/h.

- **`Adquisicion_potencia.py`** — script ligero que solo corre gen-real (reutiliza
  `fetch_generacion_real` + `upsert_generacion_real` + `log` + `log_adquisicion` de
  `Adquisicion.py`, importándolas; el guard `if __name__` evita correr `run()` al importar).
  Ventana `DIAS_VENTANA_POT = 2` días. Solo necesita `CEN_USER_KEY` + `DATABASE_URL`
  (**NO** usa `CEN_OPS_KEY`; esa solo la requiere SSCC, plan Operaciones).
- **`.github/workflows/potencia.yml`** — cron `25,55 * * * *`, timeout 15 min,
  `concurrency: potencia-ctm cancel-in-progress` para no solaparse. Espaciado del `:05`
  de la corrida horaria completa (`adquisicion.yml`).

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | Streamlit (app.py) |
| Backend DB | Supabase PostgreSQL (psycopg2) |
| Adquisición | Python (Adquisicion.py) + GitHub Actions |
| Gen. real | API CEN SIPUB /generacion-real/v3 |
| Gen. programada | API CEN SIPUB /generacion-programada-pcp/v4 |
| CMG | JSON S3 público portal CEN (~15 min) |
| SSCC | API CEN Operaciones /servicios-complementarios/v1 |

---

## Arquitectura del dashboard (refactor modular — 2026-06-22)

El monolito `app.py` (~2500 líneas) se dividió en módulos siguiendo el patrón del
proyecto ERNC. `app.py` ahora es solo el orquestador.

```
app.py                  # orquestador: page_config, CSS, sidebar, KPIs, navegación, dispatch de vistas
config.py               # paleta AES, constantes (COLORES, LABELS, PMAX, NOMBRES_NODO, mapeos id), get_css()
utils/
  db.py                 # get_conn, test_conn, qry, exe, exe_many (psycopg2)
  data.py               # loaders cacheados (@st.cache_data): load_real/prog/cmg/sscc/limitaciones/solicitudes/bit
  reports.py            # generar_pdf / generar_ppt + helpers matplotlib (movidos verbatim)
components/
  sidebar.py            # render_sidebar() → dict de filtros; estado de fuentes; export PDF/PPT
  kpis.py               # render_kpis(df_r) — tarjetas por unidad
  gen_unidad.py         # render_gen_unidad — selector por botones (primary/secondary) + gráfico real/prog/CMG
  costo.py              # render_costo — análisis CMG×generación (overlay CMG real oficial; tabs Gráficos / Estadísticas)
  novedades.py          # render_novedades(s,e) — panel estado actual por unidad (despacho/SSCC/limitación) bajo la serie CMG en Resumen
  limitaciones.py       # render_limitaciones(s,e)
  sscc.py               # render_sscc(s,e)
  despacho_cmg.py       # render_despacho_cmg(s,e) — instrucciones de despacho por CMG (despacho MW, consigna, motivo)
  solicitudes.py        # render_solicitudes(s,e)
  manual.py             # render_programada_manual / render_real_manual (CRUD)
  datos.py              # render_datos_horarios / render_bitacora
pages/ml_analysis.py    # página ML (usa config.get_css() y constantes de config)
```

**Navegación de vista única** (categoría → vista) en `app.py`: `Operación`
(Resumen, Análisis de Costo), `Restricciones` (Limitaciones, SSCC, Despacho CMG,
Solicitudes), `Gestión de Datos` (Ingreso Manual, Datos & Bitácora). Solo se
renderiza la vista activa → evita el bug de Plotly width=0 dentro de `st.tabs` y
despeja la UI.

**Navegación — botones nativos, NO `st.popover` (2026-06-23):** se abandonó
`st.popover` porque en Streamlit 1.58 quedaba **fijo abierto** y exigía **doble click**
(ni quitar `st.rerun()` ni inyectar JS para re-clickear el trigger lo resolvieron de
forma fiable). Ahora `_navegacion()` usa solo `st.button` + `session_state`: cada
categoría es un botón con flecha ▾/▴ que alterna `_cat_abierta`; al abrirse, sus vistas
se renderizan como botones bajo su columna (`st.columns` alineado por índice). Elegir una
vista hace `vista=v` + `_cat_abierta=None` + `st.rerun()`. Todo nativo → un solo click,
sin quedar fijo. (El CSS `[data-testid="stPopover"]` quedó sin uso.)

**Fix sidebar (de raíz):** el CSS ya **NO** fuerza `transform:none`/`width` ni
oculta `stSidebarCollapseButton`/`stExpandSidebarButton`/`stToolbar`. Solo se
oculta `#MainMenu`. Así Streamlit gestiona el colapso/expansión nativamente y
desaparece el ícono "keyboard_double" suelto y el botón muerto. (Igual que ERNC.)

## Archivos principales

- `app.py` — orquestador modular (~150 líneas)
- `Adquisicion.py` — Script de adquisición (~890 líneas)
- `requirements.txt` — requests, psycopg2-binary, python-dotenv, streamlit, pandas, plotly, matplotlib, reportlab, **streamlit-autorefresh**, python-pptx, scikit-learn, xgboost
- `.github/workflows/adquisicion.yml` — cron "5 * * * *", timeout 55 min
- Scripts de exploración/test eliminados (check_cmg, probe_*, test_*, resumen_endpoints_sscc_sen.md). `backfill_programada.py` se conserva (tiene workflow). `ml_pruebas.py` / `exportar_datos_ml.py` quedan como material de experimentos ML.

## ⭐ Patrón de menú desplegable (REPLICAR EN PULSAR / ERNC)

> El usuario quiere este mismo diseño de navegación en la app **Pulsar (ernc-aes-dashboard)**.

Navegación tipo barra de menú de escritorio: cada **categoría** es un `st.popover`
a todo el ancho que se **despliega hacia abajo** mostrando sus vistas como botones
(primary = vista activa). Reemplaza al `st.selectbox` + botones. Cómo se hizo en `app.py`:

```python
CATEGORIAS = {
    "Operación":        ["Resumen", "Análisis de Costo"],
    "Restricciones":    ["Limitaciones", "SSCC", "Solicitudes"],
    "Gestión de Datos": ["Ingreso Manual", "Datos & Bitácora"],
}
VISTAS = [v for g in CATEGORIAS.values() for v in g]

def _navegacion():
    vista = st.session_state.get("vista", VISTAS[0])
    st.markdown('<div class="menubar">', unsafe_allow_html=True)
    cols = st.columns(len(CATEGORIAS))
    for col, (cat, vistas_cat) in zip(cols, CATEGORIAS.items()):
        with col:
            activa = vista in vistas_cat
            etiqueta = f"{cat}  ·  {vista}" if activa else cat   # la categoría activa muestra la vista
            with st.popover(etiqueta, use_container_width=True):
                for v in vistas_cat:
                    if st.button(v, key=f"nav_{v}", use_container_width=True,
                                 type="primary" if v == vista else "secondary"):
                        st.session_state["vista"] = v; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    return vista
```

CSS clave (en `config.get_css()`): estiliza el botón del popover a todo el ancho,
con gradiente azul cuando está abierto (`aria-expanded="true"`):

```css
[data-testid="stPopover"] > div > button {
  width:100%; background:linear-gradient(180deg,#FFFFFF 0%,#F3F5FF 100%);
  border:1.6px solid #C7CDF5; border-radius:10px; min-height:48px;
  font-weight:700; font-size:14px; color:#2530B0; justify-content:center;
}
[data-testid="stPopover"] > div > button[aria-expanded="true"] {
  background:linear-gradient(135deg,#3B4CE8 0%,#2530B0 100%); color:#fff; border-color:#2530B0;
}
```

Ventajas: se ve como app de escritorio, ocupa todo el ancho, y al renderizar **solo
la vista activa** evita el bug de Plotly width=0 dentro de `st.tabs`.

## Nuevos endpoints y vistas (2026-06-23)

Tras explorar los 4 planes de la API CEN (ver sección de exploración más arriba) se
integraron 2 endpoints nuevos y se añadió un panel de estado:

- **Vista "Despacho CMG"** (`components/despacho_cmg.py`, categoría Restricciones):
  instrucciones operacionales de despacho por unidad (despacho MW, consigna, instrucción
  CMG, motivo). Fuente `/instrucciones-operacionales-cmg/v4` → tabla `instrucciones_cmg`.
  Primera fila con efecto palpitante (`.sscc-latest`).
- **CMG real oficial** en Análisis de Costo: overlay "CMG real oficial" (3 series:
  online · programado · real oficial) + KPI "Desvío online vs real oficial". Fuente
  `/costo-marginal-real/v4` → tabla `costo_marginal_real`. ⚠️ usar `limit=50` (ver tabla).
- **Panel "Novedades por unidad"** (`components/novedades.py`): bajo la serie de CMG en
  Resumen, muestra de un vistazo el estado actual de cada unidad — última consigna de
  despacho, última instrucción SSCC y limitación activa. Referencia operativa rápida.
- **Loaders REST nuevos** en `utils/data.py`: `load_instrucciones_cmg`, `load_cmg_real`
  (ambos silenciosos si la tabla no existe).
- **Migraciones** (correr una vez con DB accesible o backfill REST): `migracion_instrucciones_cmg.py`,
  `migracion_cmg_real.py`. El backfill de CMG real puede hacerse por REST (puerto 443) si
  la red bloquea psycopg2.

## Mejoras de rediseño y valor (2026-06-22)

- **Navegación tipo menú de escritorio:** `app.py` usa `st.popover` por categoría (a todo el ancho) que se despliega hacia abajo.
- **Área de desviación bicolor** en gráficos por unidad: verde = sobregeneración (real>prog), rojo = subgeneración (real<prog). Solo si hay real **y** programada.
- **Línea de mínimo técnico** (60 MW para las 4 unidades, fuente `/unidades-generadoras/v4`) en cada gráfico — ver `POT_MIN_TECNICA` en config.py.
- **Contraste de fechas** en el sidebar (caja blanca, texto oscuro).
- **`connect_timeout=8`** en `utils/db.py` + corte temprano con error claro si la DB no responde (el sidebar hace `st.stop()`).
- **CMG real vs programado** (nuevo): overlay programado + KPI "Desvío CMG real vs prog." en Análisis de Costo.

### Nuevo endpoint y tabla — CMG programado

- Endpoint: `GET /cmg-programado-pid/v4/findByDate` (SIP). **IMPORTANTE: es 1-indexado** (`page=0` devuelve 502; empezar en `page=1`), a diferencia del PCP que es 0-indexado. No filtra por barra → paginar y filtrar local por `llave_cmg ∈ {Crucero220, Tarapaca220}` (ver `CMG_PROG_BARRAS`). Usar `limit=2000` (5000 da 502 intermitente). Se conserva el programa más reciente por `(barra, fecha_hora)`.
- Tabla **`costo_marginal_programado`**: `id, barra, fecha_hora, cmg_usd_mwh, fecha_programa`, UNIQUE `(barra, fecha_hora)`. `barra` usa el mismo nombre que `costo_marginal` (`CRUCERO_______220`/`TARAPACA______220`) para cruzar real vs programado.
- Adquisición: `fetch_cmg_programado` / `upsert_cmg_programado` en `Adquisicion.py`, llamada en `main()` tras el CMG S3.
- **Migración única** (correr con DB accesible): `python migracion_cmg_programado.py [DIAS]` — crea la tabla y hace backfill. Luego el cron horario la mantiene.

### Endpoints explorados con valor potencial (pendientes de integrar)

- `/generacion-actual/v3/getSumGeneration` — requiere `startDate`+`technology`; snapshot prog vs real por central.
- `/instrucciones-operacionales/v4/findByDate` — despacho, consigna, motivo por unidad.
- `/transferencia-economica-nacional/v4`, `/stock-combustible/v4` — KPIs económicos y de combustible.

### Capa de datos: REST de Supabase (2026-06-22) — RESUELVE el bloqueo de red

El dashboard ahora accede a la DB por **REST (supabase-py, HTTPS/443)** cuando hay
`SUPABASE_URL` + `SUPABASE_KEY`, con **fallback automático a psycopg2** si no están.
Esto resuelve el bloqueo de redes que filtran el puerto Postgres (5432/6543): la REST
va por 443. `Adquisicion.py` sigue en psycopg2 (corre en GitHub Actions, sin restricción).

- `utils/db.py`: `rest_enabled()`, `get_client()` (cacheado), y API unificada
  `fetch(...)`, `write_upsert/update/delete/insert`, `last_ts(...)`, `test_conn()` —
  todas eligen REST o psycopg2 automáticamente. Cada llamada lleva un `sql=`/`params` de respaldo.
- `utils/data.py`: loaders por REST. Lo que el SQL hacía en el servidor se replica en
  pandas para la vía REST: `load_prog` deduplica priorizando `CEN_PCP`; `load_limitaciones`
  y `load_solicitudes` aplican su condición OR en pandas. Filtros de fecha por `gte/lte`
  sobre el texto ISO (ordena lexicográficamente).
- Credenciales: `SUPABASE_URL`, `SUPABASE_KEY` (service_role) en `.env` y `.streamlit/secrets.toml`
  (ambos gitignoreados). Para que **producción** (Streamlit Cloud) también use REST, agregar
  esas dos claves en los secrets de Streamlit Cloud; si no, seguirá usando psycopg2 (DATABASE_URL).
- Dependencia nueva: `supabase` en requirements.txt.
- Las tablas tienen RLS deshabilitado → la service_role key (server-side en Streamlit) tiene acceso completo.

### Puntos de datos descartados (probados en vivo 2026-06-22)

- `/instrucciones-operacionales/v4` (despacho/consigna): **404** en el plan SIP. La variante
  `-sscc` trae datos pero a nivel de central (sin ANG1/ANG2) y duplica la sección SSCC. → no se integró.
- `/stock-combustible/v4`: **404**. → descartado.
- `/transferencia-economica-nacional/v4`: responde, pero es liquidación mensual de peajes/VATT
  a nivel de propietario, contable y con muchos `None` recientes. Poco accionable. → descartado.
- `backfill_programada.py` — script de recuperación manual de gen. programada (uso: `python3 backfill_programada.py YYYY-MM-DD YYYY-MM-DD`)

### Exploración de los 4 planes de la API CEN (2026-06-23)

Se consolidaron las 4 specs OpenAPI en `resumen_consolidado_4_planes_coordinador.md`
(437 endpoints: SIP 95, OPERACIONES 44, PLANIFICACION 295 catálogos, MERCADOS 3 POST).
Se probaron en vivo los candidatos de mayor valor para CTM. Resultado:

**✅ Confirmados integrables (vía `CEN_USER_KEY`, plan SIP):**
- **`/instrucciones-operacionales-cmg/v4/findByDate`** — **INTEGRADO**. Despacho por
  unidad (MW) + consigna + instrucción CMG + motivo (texto libre). 1-indexado, NO filtra
  por central → paginar (~25 págs/día) y filtrar local por campo `central` ∈
  `LLAVES_INSTR_CMG` (`ANGAMOS-ANG1/ANG2`, `COCHRANE-CCH1/CCH2`, convención CCH como SSCC).
  `id_central`/`id_unidad_generadora` vienen vacíos. ~19 registros ANG/CCR por día.
  Tabla `instrucciones_cmg` + `migracion_instrucciones_cmg.py` (correr con DB accesible).
- **`/costo-marginal-real/v4/findByDate`** — **INTEGRADO**. CMG **real oficial** liquidado.
  Filtro servidor `bar_transf=CRUCERO_______220` (5 págs vs 7810). Tabla `costo_marginal_real`,
  `migracion_cmg_real.py`. Overlay "CMG real oficial" en Análisis de Costo (`components/costo.py`).
  **Rezago de liquidación ~10 días** (ayer/hoy devuelven 0 registros).
- **`/pronosticos-demanda-corto-plazo/v4/findByDate`** — pronóstico demanda con barra
  `Angamos220` (`energia_mwh` horaria). Insumo para el modelo XGBoost de la página ML.
  ~67 págs/día, filtrar local por barra. Pendiente integrar.

**❌ Intermitencia CEN el 2026-06-23 (reintentar otro día, NO es error de parámetros):**
- `/cmg-programado-pcp/v4` — 504 timeout persistente (endpoint pesado).
- `/potencia-activa-reactiva-unidad/v4` — 504 timeout incluso con `idCentral=377`.
- `/costo-combustible/v3/findAll` — 502 persistente.
- `/demanda-real-estimada/v4` — 404 consistente (ruta no desplegada bajo v4, descartar).

PLANIFICACION (295 endpoints) son catálogos estáticos de activos (líneas, barras,
interruptores, centrales) → solo consulta puntual de referencia, no series temporales.
MERCADOS son 3 POST de **envío** de pronósticos → no sirven para adquisición.

---

## Variables de entorno / Secrets

| Variable | Descripción |
|----------|-------------|
| `CEN_USER_KEY` | API key plan Información Pública (SIP) — `sipub.api.coordinador.cl` |
| `CEN_OPS_KEY` | API key plan Operaciones — `operacion.api.coordinador.cl` |
| `DATABASE_URL` | PostgreSQL Supabase (región São Paulo) |

---

## Base de datos (Supabase PostgreSQL, región São Paulo)

### Tablas

**generacion_real**
- PK conflict: `(unidad, fecha_hora)` → DO NOTHING
- Campos: id, unidad, llave_opreal, id_central, central, gen_real_mw, potencia_maxima, fecha_hora, hora

**generacion_programada**
- PK conflict: `(unidad, fecha_hora, fuente)` → DO UPDATE gen_programada_mw
- Campos: id, unidad, gen_programada_mw, fecha_hora, hora, fuente
- fuente = `'CEN_PCP'` (automático) o `'MANUAL'` (ingreso desde dashboard)
- Query en app.py usa `DISTINCT ON (unidad, fecha_hora)` priorizando CEN_PCP

**costo_marginal**
- PK conflict: `(barra_transf, fecha_hora)` → DO UPDATE cmg_usd_mwh, version
- Campos: id, barra_transf, barra_info, fecha_hora, hora, minuto, cmg_usd_mwh, cmg_clp_kwh, version

**sscc_instrucciones**
- PK conflict: `(fecha, id_configuracion, instruccion_sscc, inicio_periodo)` → DO UPDATE fin_periodo, disponibilidad, estado_sabana, comentario, fecha_accion, usuario
- Campos: id, fecha, inicio_periodo, fin_periodo, instruccion_sscc, id_configuracion, central_subestacion, central_unidad, unidad, configuracion_panio, barra_ct, disponibilidad, baja, sube, unidad_medida, motivo, comentario, estado_sabana, sabana, fecha_accion, usuario

**limitaciones_transmision**
- PK: `id` (string hex de la API CEN) → DO UPDATE status, fecha_efectiva_retorno, fecha_retorno_estimada, potencia, observacion, modified
- Campos: id, correlativo, empresa_nombre, instalacion_nombre, status (pendiente/finalizado/anulado), fecha_perturbacion, fecha_retorno_estimada, fecha_efectiva_retorno, potencia, unidad_medida_potencia, produce_indisponibilidad, afecta_sscc, elemento_a_trabajar, tipos_elementos, observacion, id_central, id_unidad, partition_date, created, modified
- Mapeo id_unidad → unidad: 1965=ANG1, 1966=ANG2, 1967=CCR1, 1968=CCR2
- Ventana adquisición: 30 días hacia atrás (`DIAS_VENTANA_LIM=30`) para capturar limitaciones de larga duración
- Endpoint: `https://sipub.api.coordinador.cl/limitaciones-transmision/v4/findByDate` (SIN prefijo `/sipub/api/rest/v4/`)
- Filtro: id_central ∈ {377,379} OR empresa_nombre/instalacion_nombre contiene ANGAMOS o COCHRANE

**instrucciones_cmg** (despacho operacional por unidad — 2026-06-23)
- PK conflict: `(id_instruccion, unidad)` → DO UPDATE despacho, estado, estado_operativo, consigna, instruccion_cmg, motivo, zona_desaclope, control_tension
- Campos: id, id_instruccion, unidad, central, fecha_hora, fecha, hora, configuracion, despacho (MW), estado, estado_operativo, consigna, instruccion_cmg, motivo, zona_desaclope, control_tension
- Fuente: `/instrucciones-operacionales-cmg/v4/findByDate` (SIP). Mapeo `central`→unidad en `LLAVES_INSTR_CMG`. Adquisición: `fetch_instrucciones_cmg`/`upsert_instrucciones_cmg`, ventana `DIAS_VENTANA` (7 días) en `main()`. Migración: `python migracion_instrucciones_cmg.py [DIAS]`.

**costo_marginal_real** (CMG real oficial liquidado — 2026-06-23)
- PK conflict: `(barra_transf, fecha_hora)` → DO UPDATE cmg_usd_mwh, cmg_clp_kwh, version
- Campos: id, barra_transf, fecha_hora, cmg_usd_mwh, cmg_clp_kwh, version
- Fuente: `/costo-marginal-real/v4/findByDate` (SIP). Filtro servidor `bar_transf`. Solo hora en punto (min==0). Rezago liquidación ~10 días → adquisición con ventana 16→5 días atrás. `fetch_cmg_real`/`upsert_cmg_real`. Migración: `python migracion_cmg_real.py [DIAS]`. Overlay "CMG real oficial" en Análisis de Costo.
- **⚠️ Quirk de `limit`:** este endpoint devuelve **VACÍO** si `limit` supera los registros de la página (~96/día a resolución 15-min). `limit≥100` → 0 registros. Usar **`limit=50`** y paginar (al revés del PCP/PID que usan `limit=2000`). Confirmado 2026-06-23.

**bitacora**
- Campos: id, unidad, autor, comentario, fecha, hora

**log_adquisicion**
- Campos: endpoint, fecha_consultada, registros_nuevos, registros_duplicados, duracion_ms, error

---

## Constantes clave (Adquisicion.py)

```python
API_BASE_SIP = "https://sipub.api.coordinador.cl"
API_BASE_OPS = "https://operacion.api.coordinador.cl"
ID_ANGAMOS   = 377
ID_COCHRANE  = 379
TZ_CHILE     = ZoneInfo("America/Santiago")
DIAS_VENTANA     = 2   # días hacia atrás — gen. real, programada y SSCC
DIAS_VENTANA_LIM = 30  # días hacia atrás — limitaciones (duración larga)

# Mapeo gen. real
LLAVES_OPREAL = {
    "ANG1": "TER ANGAMOS-ANG1",
    "ANG2": "TER ANGAMOS-ANG2",
    "CCR1": "TER COCHRANE-CCR1 (Carbon)",
    "CCR2": "TER COCHRANE-CCR2 (Carbon)",
}

# Mapeo gen. programada PCP (formato confirmado en producción 2026-06-06)
LLAVES_GEN_PROG = {
    "ANG1": ["ANGAMOS_1", "TER ANGAMOS-ANG1", "ANGAMOS-ANG1", "ANG1"],
    "ANG2": ["ANGAMOS_2", "TER ANGAMOS-ANG2", "ANGAMOS-ANG2", "ANG2"],
    "CCR1": ["COCHRANE_1", "TER COCHRANE-CCR1 (Carbon)", "TER COCHRANE-CCR1", "COCHRANE-CCR1", "CCR1"],
    "CCR2": ["COCHRANE_2", "TER COCHRANE-CCR2 (Carbon)", "TER COCHRANE-CCR2", "COCHRANE-CCR2", "CCR2"],
}

# Nodos CMG disponibles en S3 (confirmado: NO existen Mejillones/Angamos/Cochrane en el S3)
CMG_NODOS = {
    "CRUCERO_______220": "crucero",
    "TARAPACA______220": "tarapaca",
}

# Mapeo SSCC — centralUnidad en API Operaciones → código interno
# Confirmado en producción 2026-06-09: Cochrane aparece como CCH1/CCH2 (no CCR)
LLAVES_SSCC = {
    "ANGAMOS-ANG1":  "ANG1",
    "ANGAMOS-ANG2":  "ANG2",
    "COCHRANE-CCH1": "CCR1",
    "COCHRANE-CCH2": "CCR2",
}

# Potencias máximas declaradas ante CEN
PMAX = {"ANG1": 277.0, "ANG2": 280.0, "CCR1": 276.0, "CCR2": 276.0}
```

---

## Convenciones importantes

- **Hora CEN:** convención 1-24 → en código `dt.hour + 1`
- **fecha_hora en DB:** string `"YYYY-MM-DD HH:MM:SS"`, hora 0-based (ej. hora 1 = "...00:00:00")
- **Gen. programada PCP:** el endpoint NO filtra por central en el servidor → se paginan todos los registros (~61 páginas de 5000) y se filtra localmente por `id_central ∈ {377, 379}`. Tarda ~12 min por día consultado.
- **SSCC:** usa `pageSize=-1` para traer todo en una sola llamada (~350 registros del sistema, ~10 para ANG/CCR).

---

## Resiliencia de adquisición

Todos los endpoints usan `_get_with_retry()` con backoff exponencial:
- Reintentos ante HTTP 429, 500, 502, 503, 504
- Esperas: 10s → 20s → 40s (3 intentos máx)
- Gen. programada y SSCC consultan ventana de `DIAS_VENTANA` días para recuperar automáticamente días perdidos por fallas de API

---

## APIs CEN — hosts y autenticación

| Plan | Host | Auth |
|------|------|------|
| Información Pública (SIP) | `sipub.api.coordinador.cl` | `?user_key=CEN_USER_KEY` (query param) |
| Operaciones (OpReal) | `operacion.api.coordinador.cl` | `?user_key=CEN_OPS_KEY` (query param) |

**Importante:** ambas usan `user_key` como query param (plataforma 3scale). El host de Operaciones requiere la key del plan "Operación", no la del SIP.

### Endpoints confirmados en producción

| Endpoint | Host | Ruta exacta | Params clave | Notas |
|----------|------|-------------|--------------|-------|
| Generación real | SIP | `/generacion-real/v3/findByDate` | `startDate`, `endDate`, `idCentral`, `pageSize=5000` | Filtra por central en servidor |
| Generación programada PCP | SIP | `/generacion-programada-pcp/v4/findByDate` | `startDate`, `endDate`, `page`, `limit=5000` | NO filtra por central → paginar todo (~61 págs) y filtrar local por `id_central ∈ {377,379}`. Se consulta rango completo (startDate→endDate) en una sola llamada, no una por día |
| CMG online | S3 público | `https://cen-template-graph-pweb-prod.s3.us-east-1.amazonaws.com/CMG-online/costo-marginal-online.json` | — | JSON estático, se actualiza ~15 min. Requiere `Referer` header. Solo 8 nodos fijos, NO incluye Mejillones/Angamos/Cochrane |
| SSCC instrucciones | Operaciones | `/servicios-complementarios/v1` | `initDate`, `endDate`, `page=0`, `pageSize=-1` | `-1` trae todo en una llamada (~350 registros sistema, ~10 ANG/CCR) |
| Limitaciones transmisión | SIP | `/limitaciones-transmision/v4/findByDate` | `startDate`, `endDate`, `page`, `limit=100` | **SIN** prefijo `/sipub/api/rest/v4/` — ruta directa. Filtrar local por `id_central` o nombre |

### Endpoints explorados — no disponibles o pendientes

| Endpoint | Host | Ruta | Estado | Notas |
|----------|------|------|--------|-------|
| SSCC programados PCP | SIP | `/servicios-complementarios-programados-pcp/v4/findByDate` | 502 (2026-06-09) | Caída servidor CEN, probar después |
| Instrucciones operacionales SSCC | SIP | `/instrucciones-operacionales-sscc/v4/findByDate` | 502 (2026-06-09) | Mismo estado |
| Stock combustible | SIP | `/stock-combustible/v4/findByDate` | 404 consistente | Posible endpoint inactivo |
| Estado operativo unidades | Operaciones | `/operativos/v1/estados` | Retorna catálogo (21 tipos) | Solo devuelve tipos LP/LF/LC/DLP etc., no estado actual por unidad |
| Solicitudes | SIP | Por confirmar | Pendiente explorar | Próximo a integrar |

---

## Estado actual del código (2026-06-20 — actualizado)

Todo implementado y funcionando en producción:
- ✅ Generación real automática (API CEN SIPUB) — ventana 7 días, DO UPDATE sobrescribe ceros
- ✅ Generación programada automática (API CEN PCP) — ventana 7 días, limit=5000
- ✅ CMG dos nodos: Crucero 220kV y Tarapacá 220kV (S3 portal CEN)
- ✅ SSCC instrucciones (API CEN Operaciones) — ventana 2 días, pageSize=-1
- ✅ Retry exponencial en todos los endpoints (429/5xx)
- ✅ Dashboard: KPIs, gráficos por unidad, análisis costo, SSCC por unidad, bitácora, ingreso manual de respaldo, exportación PDF
- ✅ Timezone Chile en Adquisicion.py
- ✅ DISTINCT ON para programada priorizando CEN_PCP sobre MANUAL
- ✅ Workflow timeout 35 min (PCP tarda ~12 min/día)
- ✅ Auto-refresh horario (`streamlit-autorefresh`, 3600000 ms) — recarga automática y previene sleep de Streamlit Cloud
- ✅ Sección SSCC ubicada después de CMG, con guía desplegable (`<details>/<summary>` HTML nativo), KPIs, tabs Por unidad / Estadísticas / Tabla completa
- ✅ Tab "Por unidad" SSCC muestra máximo 5 instrucciones recientes por unidad (ordenadas fecha desc); primera instrucción con animación palpitante (`.sscc-latest`); si hay más aparece caption "+N más en «Tabla completa»"
- ✅ Footer: "Dashboard creado por Erick Herrera"
- ✅ Backfill gen. programada 05–09 junio 2026 completado (3115 registros recuperados)
- ✅ Sidebar: dot verde palpitante en todas las fuentes, texto "Conectado · Supabase / PostgreSQL", última fecha adquirida por cada fuente (Gen. real, Gen. programada, CMG S3, SSCC), etiqueta "API CEN SIPUB / OPS" encima de las fuentes
- ~~Header superior derecho con indicadores de status~~ — eliminado (duplicaba el sidebar)
- ✅ Checkbox "Mostrar área de desviación (Real vs Programada)" activado por defecto
- ~~Dots de unidades en tabs: ANG1 🟣, ANG2 🔵, CCR1 🟡, CCR2 🟢~~ — eliminados (sin emoji en UI)
- ✅ Limitaciones de transmisión (API CEN SIP `/limitaciones-transmision/v4/findByDate`) — tabla en DB, adquisición automática ventana 30 días, sección visual sobre SSCC con KPIs (activas, total, afecta SSCC, mayor potencia), tabs por unidad (ANG1/ANG2/CCR1/CCR2/Todas), cards con status/colores/correlativo N°/fechas apertura→cierre, tabla completa via `<details>/<summary>` HTML nativo, orden cronológico descendente (más reciente primero), máx 5 por tab
- ✅ Badge "pendiente" en limitaciones tiene animación palpitante naranja (`.badge-pend`, CSS `pulse-pend`)
- ✅ Header y sidebar actualizados con indicador de limitaciones activas (dot amarillo si hay pendientes)
- ✅ Tab "Estadísticas" en sección limitaciones: barras por mes (apiladas por status), donut por unidad, histograma de potencia limitada por rangos MW, barras de duración en días para limitaciones finalizadas
- ✅ Títulos de sección (.sec): font-size 0.82rem, font-weight 800, borde inferior 2px, color #334155
- ✅ KPIs factor de planta: muestra "(promedio período)" junto al % y fecha/hora del último dato adquirido
- ✅ Análisis de Costo — pestaña "Estadísticas" con 6 gráficos: ingreso horario por unidad, ingreso medio por MWh, distribución CMG (histograma), correlación gen vs CMG (scatter + coef r), donut participación ingresos, eficiencia USD/MW instalado
- ✅ Análisis de Costo — marcadores máx/mín del CMG con halo exterior (efecto destacado visual)
- ✅ Gráfico por unidad: serie CMG hereda el color de la unidad (line color = `c["line"]`) y grosor width=3 igual a la serie Real
- ✅ Solicitudes de trabajo integradas — sección después de SSCC, máx 5 cards por tab, tabla completa disponible
- ✅ Sin emoji en la UI (eliminados todos en 2026-06-18)
- ✅ Sistema de diseño AES aplicado (2026-06-19): paleta AES (cyan `#4DC8DC`, sidebar gradiente `#0e6e7e→#043840`), KPI cards con borde-top de color por unidad + hover lift + animación fadeInUp, tipografía Inter, tabs con acento cyan y padding amplio, gráficos Plotly con `template="plotly_white"` y `plot_bgcolor="#F5F7FA"`
- ✅ Selector de unidad (gráficos por unidad): reemplazado `st.tabs` por `st.button` + `session_state` — elimina bug de Plotly width=0 cuando tab está oculto con `display:none`
- ✅ Sidebar fijo siempre visible: `transform:none`, `width:300px`, `visibility:visible` forzados via CSS — evita que cookies del navegador lo dejen colapsado
- ✅ Página ML (`pages/ml_analysis.py`) — Forecasting CMG con XGBoost (lags t-1h a t-48h, forecast 24h) + Detección de anomalías gen. real con Isolation Forest (por unidad, slider % contaminación). Dependencias: `scikit-learn`, `xgboost` en requirements.txt
- ✅ Navegación multipage: `showSidebarNavigation = false` en `.streamlit/config.toml` — suprime links automáticos de Streamlit. Links manuales (`st.page_link`) debajo del recuadro de fuentes: "Aplicación" y "Machine Learning Analysis", sin emoji, con margen superior de separación

## Notas técnicas importantes (diseño/CSS)

- **Bug Plotly + st.tabs (Streamlit):** `st.tabs` renderiza todos los paneles simultáneamente con `display:none`. Plotly mide el contenedor al renderizar → obtiene width=0 → el gráfico queda pequeño para siempre. **Solución:** usar `st.button` + `st.session_state` para selector de unidad, renderizando solo un gráfico a la vez.
- **Sidebar y cookies:** Streamlit Cloud guarda el estado del sidebar (colapsado/expandido) en cookies/localStorage del navegador. Para forzar que siempre esté visible, usar CSS con `transform:none!important`, `width:300px!important`, `visibility:visible!important` en `[data-testid="stSidebar"]`.
- **DOM Streamlit 1.58:** El ícono de colapso del sidebar está en `[data-testid="stIconMaterial"]` (no `.material-symbols-rounded`). El botón de expandir cuando colapsado es `[data-testid="stExpandSidebarButton"]` y vive dentro de `[data-testid="stToolbar"]` (que por defecto ocultamos con `display:none`). El sidebar usa `aria-expanded="false"` (no `data-collapsed`) para indicar estado colapsado.

---

## Pendiente / Por explorar

- **[INTERÉS DEL USUARIO] Generación programada PID** (`/generacion-programada-pid/v4/findByDate`, SIP)
  — la otra programación de generación además del PCP. El **PID (Programa Intra-Día)** ajusta
  el PCP (Programa de Corto Plazo / día-ante) durante el día con información más fresca. Integrar
  como segunda fuente de gen. programada para comparar PCP vs PID vs real por unidad (el dashboard
  ya distingue `fuente` en `generacion_programada`). Mismo patrón que el PCP: paginar y filtrar
  local por `id_central ∈ {377,379}`. Pendiente de explorar formato/llaves. Pedido por el usuario 2026-06-23.

- **[PRIORIDAD 1] Solicitudes de trabajo — integrar al dashboard** (`/solicitudes-trabajo/v4/findByDate`, SIP) — endpoint confirmado funcional el 2026-06-17 (ventana ≤7 días). El servidor CEN es intermitente, reintentar con `python probe_solicitudes.py` hasta obtener respuesta estable. Parámetros confirmados: `startDate`, `endDate` (YYYY-MM-DD), `page` (base 1), `limit=100`. Respuesta: `{"data":[...], "totalPages":N, "page":N, "limit":N}`. Con 7 días devuelve ~267 páginas (~26.700 registros del sistema). Campos conocidos: `id`, `correlativo` (JOIN con `limitaciones_transmision`), `empresa_nombre`, `grupo_nombre`, `centro_control` (campo extra no documentado), `status`, `tipo_solicitud`, `type`, `origen`, `tipo_programacion`, `consumo`, `perdida_registro_energia`, `descripcion_nivel_riesgo`, `fecha_inicio`, `fecha_fin`, `created`, `modified`, `partition_date`. Filtro local por `empresa_nombre` + `grupo_nombre` + `centro_control` buscando ANGAMOS/COCHRANE/AES. **Próximo paso:** cuando el servidor responda estable, correr probe para ver empresas únicas y confirmar cómo aparece AES Andes en los datos, luego integrar sección en dashboard igual que limitaciones.

- **SSCC programados PCP** (`/servicios-complementarios-programados-pcp/v4/findByDate`, SIP) — respondía 502 el 2026-06-09 por caída del servidor CEN. Probar cuando la API se recupere.
- **Instrucciones operacionales SSCC** (`/instrucciones-operacionales-sscc/v4/findByDate`, SIP) — mismo estado, 502 ese día.
- **Stock combustible** (`/stock-combustible/v4/findByDate`, SIP) — retorna 404 consistente, posible endpoint inactivo o requiere parámetros distintos.
- **Optimización PCP:** actualmente se hacen 2 consultas separadas (una por día en DIAS_VENTANA). Podría hacerse una sola con rango de 2 días para reducir tiempo de ~24 min a ~12 min.
- **Limitaciones/estado operativo unidades:** `/operativos/v1/estados` (Operaciones) sólo retorna catálogo de 21 tipos de estado (LP, LF, LC, DLP, etc.), no el estado actual por unidad. Los módulos referenciados (`desconexion_intervencion`, `informe_fallas`, `limitaciones`) tienen rutas propias aún no identificadas. Angamos ID=377, Cochrane ID=379.
- **Solicitudes de trabajo** (`/solicitudes-trabajo/v4/findByDate`, SIP) — explorado 2026-06-11, 502 persistente (caída CEN). **Pendiente probar 2026-06-12.** Schema conocido: `id`, `correlativo` (JOIN con limitaciones_transmision), `empresa_nombre`, `grupo_nombre`, `status`, `tipo_solicitud`, `type`, `origen`, `tipo_programacion`, `consumo`, `perdida_registro_energia`, `descripcion_nivel_riesgo`, `fecha_inicio`, `fecha_fin`, `created`, `modified`, `partition_date`. Filtro: `empresa_nombre` o `grupo_nombre` contiene ANGAMOS/COCHRANE. Integración planeada: complementar sección limitaciones con detalle de la solicitud asociada via correlativo.
- **Limpieza de archivos obsoletos:** eliminar scripts de prueba/exploración que ya cumplieron su propósito: `check_cmg.py`, `probe_sscc.py`, `test_api_cen.py`, `test_cmg_crucero.py`, `test_scraping_cmg.py`, `resumen_endpoints_sscc_sen.md`. También evaluar si conservar `backfill_programada.py` (backfill jun 5–9 ya completado).
- **RLS Supabase (seguridad):** habilitar Row-Level Security en todas las tablas públicas del proyecto `ctm-mejillones`. El SQL Editor web da timeout; usar psql con conexión directa `db.luddatnopktghtxeixyd.supabase.co:5432` (obtener desde Project Settings → Database → Direct connection). Ver SQL completo en historial de conversación 2026-06-16.
