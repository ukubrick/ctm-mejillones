# CLAUDE.md — Dashboard CTM Mejillones
> Contexto completo para Claude Code. Leer al inicio de cada sesión.
> Autor: Erick Herrera — AES Andes, Antofagasta, Chile.
> Última actualización: 2026-07-08 (rediseño Estadísticas/Costos/ML, ingreso por unidad + alerta
>   potencia 0, contraseña en Datos, solicitudes en bitácora automática).
>
> REGLA DE MANTENIMIENTO: la cabecera (todo lo anterior al HISTORIAL DE SESIONES) es la
> ÚNICA fuente de verdad del estado actual; `config.py` manda sobre este markdown.
> Las sesiones son historia inmutable. Al cerrar cada sesión, actualizar la cabecera
> ADEMÁS de agregar el log de sesión.

---

## DESCRIPCIÓN DEL PROYECTO

Dashboard operacional del **Complejo Térmico Mejillones (CTM)** de AES Andes. Monitorea
generación real vs programada + costo marginal (CMG) + servicios complementarios (SSCC) +
restricciones para las **4 unidades térmicas a carbón**:

- **ANG1, ANG2** — Central Angamos (`id_central=377`)
- **CCR1, CCR2** — Central Cochrane (`id_central=379`)

**Proyecto independiente** del dashboard Pulsar (ERNC, parques renovables). Comparte stack,
paleta AES y patrones de navegación, pero su dominio son las térmicas.

**Estado actual:** en producción en Streamlit Cloud. Adquisición automática vía GitHub
Actions en 4 workflows escalonados (ver ADQUISICIÓN).

---

## URLS DE PRODUCCIÓN

- **GitHub:** https://github.com/ukubrick/ctm-mejillones (**PÚBLICO** — Actions ilimitado.
  Estuvo brevemente privado el 2026-07-03 pero se revirtió: el consumo de Actions (~20.000
  min/mes) excede la cuota gratuita de 2.000 min/mes de repos privados).
- **Supabase:** https://luddatnopktghtxeixyd.supabase.co (proyecto CTM, región São Paulo)
- **Streamlit Cloud:** ctm-mejillones.streamlit.app (cuenta ukubrick, main file: `app.py`)

---

## REGLAS APRENDIDAS — NO VIOLAR

Destiladas de bugs y quirks reales del CEN/Streamlit:

1. **Plotly + st.tabs:** `st.tabs` renderiza paneles ocultos con `display:none` → Plotly mide
   width=0 y el gráfico queda comprimido para siempre. Renderizar SOLO la vista activa
   (botones/`st.radio` + `session_state`); nunca `st.plotly_chart` en un tab inactivo.
2. **st.plotly_chart:** usar `key=` único (incluir la unidad si depende de un selector) →
   evita `StreamlitDuplicateElementId`.
3. **Hora CEN:** convención 1-24 → en código `dt.hour + 1`. En DB `fecha_hora` es string
   `"YYYY-MM-DD HH:MM:SS"` con hora **0-based** en America/Santiago (hora 1 = "...00:00:00").
4. **gen-real v3 TRUNCA rangos multi-día** (verificado 2026-07-03: rango de 4 días devolvió
   146/192 con `totalPages=1`). Consultar gen-real SIEMPRE **por día**, una llamada por fecha.
5. **CMG real (`/costo-marginal-real/v4`)**: devuelve VACÍO si `limit` supera los registros de
   la página (~96/día). Usar **`limit=50`** y paginar (al revés del PCP/PID que usan 2000).
6. **CMG programado PID (`/cmg-programado-pid/v4`)**: es **1-indexado** (`page=0` → 502,
   empezar en `page=1`), `limit=2000` (5000 da 502 intermitente). No filtra por barra → paginar
   y filtrar local por `llave_cmg ∈ {Crucero220, Tarapaca220}`.
7. **Limitaciones (`/limitaciones-transmision/v4/findByDate`)**: ruta **SIN** el prefijo
   `/sipub/api/rest/v4/`. Filtrar local por `id_central ∈ {377,379}` o nombre. `correlativo`
   llega como float → `int(float(v))`.
8. **SSCC (Operaciones):** Cochrane aparece como **CCH1/CCH2** (no CCR) en `centralUnidad`.
   Respuesta paginada con `pageSize=-1` trae todo. `CEN_OPS_KEY` solo la usa SSCC.
9. **PCP/PID no filtran por central en el servidor** → paginar todo (limit=5000/2000) y filtrar
   local por `id_central ∈ {377,379}`. Deduplicar antes del upsert.
10. **supabase-py (REST/443) para el dashboard, psycopg2 (5432/6543) para la adquisición.**
    La conexión TCP directa falla desde redes locales (firewall); la REST siempre funciona.
    `utils/db.py` elige REST si hay `SUPABASE_URL`+`SUPABASE_KEY`, con fallback a psycopg2.
11. **Migraciones DDL (ALTER/CREATE): correr vía el workflow `migracion.yml`** (Actions no
    bloquea el 5432; las redes locales sí). Nunca depender de que corran localmente.
12. **Navegación Streamlit:** no escribir en `session_state[key]` de un widget vivo en el mismo
    run. El selector de nodo CMG y las sub-secciones usan `key=` y se leen en el run siguiente.
13. **f-strings** sin backslash dentro (Python < 3.12) — extraer a variable.
14. **Sin emojis** en la UI. Fondo nunca blanco puro (`#F5F7FA`); cards `#FFFFFF`.
15. **RLS Supabase (activo desde 2026-07-03):** la `service_role` key (dashboard) y `postgres`
    (adquisición, dueño de tablas) **ignoran RLS**; el `anon` queda bloqueado. Toda tabla nueva
    ya nace protegida. Si el frontend usara la `anon` key, RLS rompería las lecturas → producción
    DEBE usar `service_role` en `SUPABASE_KEY`.
16. **Ingreso manual con prioridad:** en `generacion_programada`, `MANUAL > CEN_PCP` (ver
    `load_prog`). En `generacion_real`, la fila manual se marca `origen='MANUAL'` y la adquisición
    automática NO la sobreescribe (guard en `upsert_generacion_real`). La columna `origen` se
    auto-crea (idempotente) en la corrida horaria.
17. **Job horario aligerado:** NO recargar en el horario lo que ya cubren los otros crons
    (gen-real/CMG → potencia; SSCC/despacho/limitaciones → operaciones; lentos → diaria).
18. **Tras mover código entre módulos, correr `py_compile`/pyflakes** — detecta nombres que
    quedaron como globals del módulo original (NameError solo en runtime/Cloud). Ej.: `reports.py`
    referenciaba `datetime`/`qry` sin importar → PDF roto hasta el fix.
19. **Fijar la versión de Streamlit en `requirements.txt` (`streamlit==1.58.0`).** Sin pin, un
    redeploy trae la última versión y puede cambiar el DOM interno → rompe el CSS a medida SIN
    error visible. 1.58 renombró el grupo de radios a `data-testid="stRadioGroup"` (antes solo
    `[role="radiogroup"]` + `label[data-baseweb="radio"]`) → el segmented control quedó como radios
    nativos. El CSS de radios ahora cubre ambos nombres.
20. **No forzar `width/display:flex` en los HIJOS de un botón de Streamlit para centrar** — el
    `<button>` ya es `inline-flex; justify-content:center` (se centra solo, como los botones del
    área principal). Sobreescribir los hijos ROMPE ese centrado. Para el sidebar basta el estilo a
    nivel de `button` + `text-align:center` en el `p`.
21. **Keep-alive con `st_autorefresh`: usar intervalo corto (~5 min), no 1 h.** Los navegadores
    estrangulan timers largos en pestañas en segundo plano y la WebSocket puede caer → la app se
    duerme. Aun así SOLO mantiene viva la app mientras haya ≥1 pestaña abierta; sin cliente,
    Streamlit Cloud la suspende igual (para evitarlo haría falta un pinger externo).
22. **Diseño de gráficos (skill dataviz): NUNCA eje dual (dos escalas y).** Dos magnitudes de
    escala distinta → dos gráficos, small multiples, o una dispersión (x vs y). El color sigue a
    la ENTIDAD (unidad = tema categórico de orden fijo violeta/azul/cyan/verde, nunca cíclico);
    las MAGNITUDES (CMG) usan rampa secuencial de un solo matiz (violeta claro→oscuro), nunca
    arcoíris. La paleta de unidades AES tiene un par CVD-débil (violeta↔azul en protan) → SIEMPRE
    va con leyenda + etiquetas directas (codificación secundaria) que la hacen admisible.
23. **Potencia real < 5 MW = unidad detenida (trip/desconexión/mantención), NO 0 exacto.** La
    medición SCADA rara vez marca 0.0; `UMBRAL_CERO`/`UMBRAL_TRIP = 5.0`. Se alerta en rojo en la
    serie (gen_unidad.py) y en el tope (kpis.py cruza con limitaciones: baja programada vs trip).

---

## CONVENCIONES DE CÓDIGO

```python
# Hora CEN: convención 1-24 → dt.hour + 1 al escribir "hora"; fecha_hora en DB 0-based.
# fecha_hora en DB: siempre string "YYYY-MM-DD HH:MM:SS" en hora America/Santiago.
# Timezone: usar datetime.now(TZ_CHILE) (ZoneInfo("America/Santiago")), NUNCA UTC ni offset fijo.

# Retry: SIEMPRE _get_with_retry() para las llamadas CEN (429/5xx → backoff 10→20→40s).
# Capa de datos: fetch()/write_* de utils/db.py eligen REST o psycopg2 automáticamente;
#   cada llamada lleva un sql=/params de respaldo para la vía psycopg2.

# SECRETOS: NUNCA escribir valores reales de keys/tokens/passwords en CLAUDE.md ni en
# archivos commiteados (el repo es PÚBLICO). Solo el nombre de la variable + dónde vive
# (.env local / GitHub Actions Secrets / Streamlit Cloud Secrets).
```

---

## STACK TECNOLÓGICO

```
Frontend:        Streamlit (app.py), tema claro, paleta corporativa AES con degradados
Gráficos:        Plotly (template plotly_white) — tema compartido en utils/plotly_theme.py
Base de datos:   Supabase PostgreSQL — REST via supabase-py (dashboard) + psycopg2 (adquisición)
Adquisición:     Python + GitHub Actions (4 crons escalonados)
Gen. real:       API CEN SIP /generacion-real/v3
Gen. programada: PCP /generacion-programada-pcp/v4 + PID /generacion-programada-pid/v4
CMG online:      JSON S3 público del Coordinador (~15 min) — nodos Crucero/Tarapacá 220 kV
CMG prog/real:   /cmg-programado-pid/v4 + /costo-marginal-real/v4
SSCC:            API CEN Operaciones /servicios-complementarios/v1
Reportes:        ReportLab (PDF) + python-pptx (PPT) — ejecutivos, paleta AES, in-memory
ML:              scikit-learn (Isolation Forest) + xgboost (forecast CMG)
Autorefresh:     streamlit-autorefresh (3.600.000 ms)
```

### Por qué REST (supabase-py) y no psycopg2 en el dashboard
La conexión TCP directa a Supabase (5432/6543) falla desde redes locales con egress
restringido. La REST API (HTTPS/443) siempre funciona. La adquisición corre en GitHub Actions
(sin restricción) y usa psycopg2 directo.

---

## CREDENCIALES Y VARIABLES DE ENTORNO

```env
# API CEN — valores reales SOLO en .env local, GitHub Actions Secrets y Streamlit Cloud Secrets
CEN_USER_KEY=<ver .env / Secrets>    # plan SIP (sipub.api.coordinador.cl) — query param user_key
CEN_OPS_KEY=<ver .env / Secrets>     # plan Operaciones (operacion.api.coordinador.cl) — solo SSCC

# Supabase — proyecto CTM
SUPABASE_URL=https://luddatnopktghtxeixyd.supabase.co
SUPABASE_KEY=<service_role — ver Secrets>   # service_role (escribe/lee sin RLS)
DATABASE_URL=<postgresql://... — ver Secrets>  # pooler São Paulo (psycopg2 en Actions)
```

> REGLA DE SEGURIDAD: `service_role` key y `DATABASE_URL` SOLO en `.env` local, GitHub Actions
> Secrets y Streamlit Cloud Secrets. `.env` y `.streamlit/secrets.toml` están en `.gitignore`.
> El dashboard usa `service_role` (bypassa RLS). Si alguna credencial se expone → rotarla en
> Supabase (Settings → Database / API) y actualizar los 3 lugares.

### Secrets configurados
```
GitHub Actions (ukubrick/ctm-mejillones):  CEN_USER_KEY ✅  CEN_OPS_KEY ✅  DATABASE_URL ✅
Streamlit Cloud:                            SUPABASE_URL ✅  SUPABASE_KEY ✅ (service_role)
```

---

## ESTRUCTURA DE ARCHIVOS

```
dashboard_api/
├── CLAUDE.md                       ← este archivo
├── .env / .streamlit/secrets.toml  ← credenciales (gitignored)
├── config.py                       ← paleta AES (degradados), constantes, LABELS/PMAX/mapeos, get_css()
├── requirements.txt
├── app.py                          ← orquestador: page_config, CSS, sidebar, KPIs, navegación plana, dispatch
├── Adquisicion.py                  ← funciones fetch_/upsert_ + run() horario (núcleo PCP/PID/CMG-prog)
├── Adquisicion_potencia.py         ← cron :25/:55 — gen-real + CMG S3 (baja latencia)
├── Adquisicion_operaciones.py      ← cron :10/:40 — SSCC + Despacho CMG + Limitaciones
├── Adquisicion_diaria.py           ← cron 08:20 UTC — CMG real, pronóstico demanda, solicitudes, maestro
├── backfill_programada.py          ← utilidad puntual (recupera PCP por rango)
├── migracion_*.py                  ← migraciones puntuales (correr vía workflow migracion.yml)
├── utils/
│   ├── db.py                       ← capa unificada REST/psycopg2 (fetch, write_*, last_ts, test_conn)
│   ├── data.py                     ← loaders cacheados @st.cache_data (load_real/prog/cmg/sscc/...)
│   ├── reports.py                  ← generar_pdf / generar_ppt ejecutivos (ReportLab + python-pptx)
│   └── plotly_theme.py             ← apply_aes_layout, estilo_serie, hover, add_linea_ahora, hex_to_rgba
├── components/
│   ├── _common.py                  ← metricas_precision, render_guia/tabla_guia, render_cards_unidad
│   ├── sidebar.py                  ← render_sidebar → filtros; estado de adquisición; export PDF/PPT
│   ├── kpis.py                     ← render_kpis — cards por unidad + alarma de TRIP (UMBRAL_TRIP=5 MW)
│   ├── gen_unidad.py               ← render_gen_unidad — series real/prog/CMG + selector nodo CMG +
│   │                                  ingreso estimado por unidad (junto al MAE, delta vs semana pasada) +
│   │                                  alerta potencia 0 (<5 MW = trip) en la serie (UMBRAL_CERO=5.0)
│   ├── costo.py                    ← render_costo — deep-dive económico: benchmarking CMG (online/prog/
│   │                                  real), elasticidad precio-demanda, ingreso diario, mapa de valor,
│   │                                  cascada de ingreso, calidad del pronóstico CMG
│   ├── estadisticas.py             ← render_estadisticas — heatmap CMG hora×día, curva de duración,
│   │                                  ingreso acumulado, perfil horario gen, aporte/FP, correlación, precisión
│   ├── ml.py                       ← render_ml — suite: forecast CMG probabilístico (XGBoost, banda
│   │                                  P10-P90 + ingreso esperado 24h), anomalías (IsolationForest +
│   │                                  severidad), regímenes operacionales (KMeans de perfiles diarios)
│   ├── novedades.py                ← render_novedades — estado actual por unidad (bajo la serie CMG)
│   ├── bitacora_auto.py            ← render_bitacora_auto — bitácora cronológica de la unidad activa
│   │                                  (SSCC + despacho + limitaciones + novedades manuales + solicitudes
│   │                                  que mencionan Angamos/Cochrane), ayer x defecto
│   ├── limitaciones.py / sscc.py / despacho_cmg.py / solicitudes.py   ← vistas de Restricciones
│   ├── manual.py                   ← render_programada_manual / render_real_manual (CRUD + override)
│   ├── datos.py                    ← render_datos_horarios / render_bitacora
│   └── infotecnica.py              ← fichas técnicas por unidad (unidades_maestro + fallback config)
├── pages/ml_analysis.py            ← wrapper delgado que llama components.ml.render_ml()
└── .github/workflows/
    ├── adquisicion.yml             ← cron :05 (núcleo horario, timeout 60)
    ├── adquisicion_potencia.yml    ← cron :25/:55 (gen-real + CMG S3)
    ├── adquisicion_operaciones.yml ← cron :10/:40 (SSCC + despacho + limitaciones)
    ├── adquisicion_diaria.yml      ← cron 08:20 UTC (endpoints lentos que cambian poco)
    └── migracion.yml               ← workflow_dispatch (corre cualquier migracion_*.py)
```

---

## NAVEGACIÓN (menú plano de 4 vistas — desde 2026-07-03)

Se abandonaron las categorías desplegables (popovers). El menú es un **segmented control**
(`st.radio` horizontal) de 4 vistas planas; las sub-secciones viven dentro con radio-pills:

| Vista | Sub-secciones |
|-------|---------------|
| **Resumen** | Gráfico por unidad (real/prog/CMG) + selector de nodo CMG + bitácora automática de la unidad + novedades |
| **Análisis** | Costos · Estadísticas (consolidada) · Predicción (ML) |
| **Restricciones** | Limitaciones · SSCC · Despacho CMG · Solicitudes |
| **Datos** | Ingreso Manual · Datos & Bitácora · Infotécnica (**las 2 primeras tras contraseña `jt`**) |

- **El selector de nodo CMG vive en Resumen** (antes en el sidebar); persiste en
  `session_state["nodo_cmg"]` y `app.py` lo lee para cargar `df_c`.
- **Contraseña en Datos:** Ingreso Manual y Datos & Bitácora piden clave `jt` (constante
  `_CLAVE_DATOS` en `app.py`, gate `_acceso_restringido`, se recuerda en `session_state["datos_auth"]`).
  Infotécnica queda libre. Es una verja de UI (no seguridad server-side).
- **Estadísticos y Costos rediseñados (2026-07-08):** Estadísticas y Costos son ahora paneles
  profundos y COMPLEMENTARIOS (no duplican gráficos). Estadísticas = operación/patrones; Costos =
  dinero/precio. Regla dataviz aplicada: 1 solo eje por gráfico (sin ejes duales), categórico por
  unidad + rampa secuencial violeta para magnitudes CMG.
- **Solicitudes** se filtran por relevancia CTM: Angamos, Cochrane, S/E Laberinto, Kapatur,
  Crucero (`load_solicitudes` en utils/data.py).

---

## ADQUISICIÓN — 4 WORKFLOWS ESCALONADOS

Réplica del patrón de separación por concern. El job horario único se pasaba del timeout en
PCP/PID (lentos paginados) → se separaron los endpoints rápidos y los lentos-que-cambian-poco.

| Workflow | Script | Endpoints | Cron | Timeout |
|----------|--------|-----------|------|---------|
| Horaria | `Adquisicion.py` | **Núcleo:** PCP · PID · CMG-programado (+ gen-real/CMG S3 de respaldo) | `:05` | 60 min |
| Potencia | `Adquisicion_potencia.py` | gen-real + CMG S3 | `:25,:55` | — |
| Operaciones | `Adquisicion_operaciones.py` | SSCC + Despacho CMG + Limitaciones | `:10,:40` | — |
| Diaria | `Adquisicion_diaria.py` | CMG real + pronóstico demanda + solicitudes + maestro unidades | `08:20 UTC` | 60 min |

- Crons espaciados para no solaparse. Cada script reutiliza las funciones de `Adquisicion.py`
  (el guard `if __name__` evita correr `run()` al importar).
- `gen-real` SIEMPRE por día (el v3 trunca rangos). PCP/PID/CMG-prog por rango ayer→mañana.

---

## BASE DE DATOS SUPABASE — TABLAS

Proyecto CTM (`luddatnopktghtxeixyd`, región São Paulo). RLS activado (2026-07-03). Acceso por
REST (service_role) desde el dashboard; psycopg2 (postgres) desde la adquisición.

| Tabla | PK conflict | Notas |
|-------|-------------|-------|
| `generacion_real` | `(unidad, fecha_hora)` DO UPDATE | + col `origen` ('MANUAL' protege del upsert automático) |
| `generacion_programada` | `(unidad, fecha_hora, fuente)` DO UPDATE | `fuente` ∈ CEN_PCP / CEN_PID / MANUAL. `load_prog`: MANUAL > PCP, excluye PID |
| `costo_marginal` | `(barra_transf, fecha_hora)` DO UPDATE | CMG online S3. Nodos Crucero/Tarapacá 220 |
| `costo_marginal_programado` | `(barra, fecha_hora)` | CMG PID. Migración `migracion_cmg_programado.py` |
| `costo_marginal_real` | `(barra_transf, fecha_hora)` | CMG real liquidado, rezago ~10 días. `limit=50` |
| `sscc_instrucciones` | `(fecha, id_configuracion, instruccion_sscc, inicio_periodo)` | Cochrane = CCH1/CCH2 |
| `instrucciones_cmg` | `(id_instruccion, unidad)` | Despacho por CMG. `central`→unidad en `LLAVES_INSTR_CMG` |
| `limitaciones_transmision` | `id` (hex API) | id_unidad 1965=ANG1 1966=ANG2 1967=CCR1 1968=CCR2 |
| `solicitudes_trabajo` | `id` | filtro relevancia CTM en el loader |
| `pronostico_demanda` | `(barra, fecha_hora)` | insumo del forecast ML |
| `unidades_maestro` | `unidad` | maestro técnico (`/unidades-generadoras/v4`) |
| `bitacora` | `id` | novedades manuales |
| `log_adquisicion` | — | telemetría de cada corrida |

---

## CONSTANTES CLAVE (config.py / Adquisicion.py)

```python
ID_ANGAMOS = 377;  ID_COCHRANE = 379;  TZ_CHILE = ZoneInfo("America/Santiago")
PMAX = {"ANG1": 277.0, "ANG2": 280.0, "CCR1": 276.0, "CCR2": 276.0}
POT_MIN_TECNICA = {"ANG1": 60.0, "ANG2": 60.0, "CCR1": 60.0, "CCR2": 60.0}
LABELS = {"ANG1": "Angamos U1", "ANG2": "Angamos U2", "CCR1": "Cochrane U1", "CCR2": "Cochrane U2"}
CMG_NODOS = {"CRUCERO_______220": "crucero", "TARAPACA______220": "tarapaca"}
LLAVES_SSCC = {"ANGAMOS-ANG1":"ANG1","ANGAMOS-ANG2":"ANG2","COCHRANE-CCH1":"CCR1","COCHRANE-CCH2":"CCR2"}
```

---

## SISTEMA DE DISEÑO — PALETA CORPORATIVA AES (degradados)

Espectro de marca (logo infinito/espiral): **verde → teal → cyan → azul → violeta**. Todo el
dashboard usa degradados con estas 5 anclas.

```python
AES_VERDE       = "#22A95B"   # inicio del espectro (CCR2)
AES_TEAL        = "#12B2A0"
AES_CYAN        = "#1FB6E5"   # (CCR1)
AES_AZUL        = "#3D53E8"   # color de acción principal (ANG2)
AES_AZUL_OSC    = "#2A38C9"
AES_VIOLETA     = "#7C4DE0"   # fin del espectro — CMG (ANG1)
AES_VIOLETA_OSC = "#5B2FB0"
AES_GRAD     = "linear-gradient(120deg,#22A95B,#12B2A0,#1FB6E5,#3D53E8,#7C4DE0)"  # completo
AES_GRAD_BTN = "linear-gradient(135deg,#3D53E8,#6A3FCC)"                          # acción
SIDEBAR_GRAD = "linear-gradient(168deg,#0E7E93,#2A38C9,#4A25A0)"                  # sidebar
```

- **Unidades sobre el espectro:** ANG1 violeta · ANG2 azul · CCR1 cyan · CCR2 verde.
- KPIs con borde superior degradado (padding-box/border-box), títulos de sección en sentence
  case con acento degradado corto, título principal con texto degradado, botones/tabs/pills con
  `AES_GRAD_BTN`. Fondo `#F5F7FA` (nunca blanco puro), cards `#FFFFFF`, fuente Inter, sin emojis.
- Reportes PDF/PPT: layout ejecutivo con barra de degradado AES (5 celdas) y unidades coloreadas.

---

## PENDIENTES VIVOS (lista única — actualizar aquí)

- [ ] **Limpieza:** decidir si archivar/borrar `exportar_datos_ml.py` y `ml_pruebas.py` (material
      viejo de experimentos ML, no usados por la app).
- [ ] **Verificación operacional:** confirmar que el cron horario aligerado termina sin timeout,
      que la diaria corre bien (dispararla 1× manual) y que la columna `origen` se auto-creó.
- [ ] **Endpoints CEN sondeados 2026-07-03 — revividos pero NO integrados** (costo > beneficio):
      · `/potencia-activa-reactiva-unidad/v4` → **200**, pero SCADA-level (KVAR), `totalPages≈38.687`,
        no filtra por central. Valor nicho, paginación masiva → descartado por ahora.
      · `/servicios-complementarios-programados-pcp/v4` → **200** (SSCC programado, provisión MW por
        tipo), pero `totalPages≈120.178` e **ignora `idCentral`** → paginar todo el sistema. Sería
        el de mayor valor SI el CEN agregara filtro por central; hoy el costo no compensa.
      · `/instrucciones-operacionales-sscc/v4` → **200** (172 págs), pero **duplica** el SSCC que ya
        se trae vía Operaciones `/servicios-complementarios/v1`. Aporte marginal → descartado.
- [ ] **Endpoints CEN no disponibles:** `/net-power/v1/findByDate` (404) · `/costo-combustible/v3`
      (502 persistente) · `/reduccion/v1/generacion` (404 "No Mapping Rule" — requiere suscribir el
      recurso en 3scale; la key OPS actual no lo tiene).

Resueltos (histórico): PID integrado · Solicitudes integradas y filtradas · Pronóstico demanda
integrado · Optimización PCP (1 llamada por rango) · RLS habilitado (2026-07-03) · Override
manual con prioridad · Job horario aligerado + workflow diario · Reportes PDF/PPT reescritos ·
Limpieza de scripts probe/test/check.

---

## RITUAL DE CIERRE DE SESIÓN (obligatorio)

1. Actualizar la CABECERA si cambió: estructura de archivos, tablas, workflows, paleta, navegación.
2. Agregar la sesión al HISTORIAL DE SESIONES (abajo), como historia inmutable.
3. Actualizar PENDIENTES VIVOS: agregar nuevos, marcar resueltos.
4. Si un bug enseñó una regla generalizable → agregarla a REGLAS APRENDIDAS.
5. Actualizar "Última actualización" del header.
6. Verificar: ninguna key/token/password real en archivos commiteados (repo PÚBLICO).

---

## HISTORIAL DE SESIONES

> Historia inmutable. La cabecera es la fuente de verdad del estado actual.

- **2026-06-16 — Base:** adquisición gen-real/PCP/CMG/SSCC + dashboard monolítico, retry
  exponencial, timezone Chile, exportación PDF inicial.
- **2026-06-22 — Refactor modular:** el monolito `app.py` (~2500 líneas) se dividió en
  `config.py` + `utils/` + `components/`. Capa REST de Supabase (supabase-py) con fallback
  psycopg2. Endpoint CMG programado PID + tabla. Sistema de diseño AES v1.
- **2026-06-23 — Endpoints nuevos:** instrucciones-cmg (Despacho CMG) + costo-marginal-real
  (CMG real oficial) integrados. Panel "Novedades por unidad". Exploración de los 4 planes CEN.
- **2026-06-24 — Workflows por concern:** se separó el job horario en potencia (:25/:55) +
  operaciones (:10/:40), dejando el horario como respaldo.
- **2026-07-03 (mañana) — Maestro + Infotécnica:** tabla `unidades_maestro`, vista Infotécnica,
  workflow `migracion.yml`. SSCC/instrucciones-CMG por rango. Series de tiempo por unidad
  profesionalizadas + panel de adquisición formal en el sidebar. Theme Plotly compartido.
- **2026-07-03 (tarde) — Rediseño AES + reorganización:**
  · Paleta corporativa AES con degradados (verde→teal→cyan→azul→violeta) en todo el dashboard.
  · Menú plano de 4 vistas; estadísticos consolidados en `estadisticas.py`; ML reformulado en
    `ml.py` (dentro de Análisis); costo reducido a overview; sidebar depurado; selector de nodo
    movido a Resumen; títulos en sentence case; palabra "AES" fuera de la UI.
  · Solicitudes filtradas por relevancia CTM. Reportes PDF/PPT reescritos (ejecutivos, paleta AES,
    fix de imports rotos que tenían el PDF caído).
  · Override manual con prioridad (MANUAL>PCP; `origen='MANUAL'` protege gen-real; auto-crea la
    columna). Job horario aligerado + nuevo `Adquisicion_diaria.py` (timeout 120→60).
  · Repo a privado y de vuelta a público (cuota de Actions). RLS habilitado en todas las tablas.
- **2026-07-06 — Bitácora automática + fix Streamlit 1.58:**
  · Nuevo `components/bitacora_auto.py`: bajo la serie de CMG (vista Resumen), tabla cronológica
    de la UNIDAD ACTIVA (reacciona a los botones ANG/CCR). Consolida SSCC + despacho CMG +
    limitaciones (trip/derrateo, fila roja) + novedades manuales de la tabla `bitacora`. Selector
    de día CONTINUO (todos los días del período, sin saltos), ayer por defecto. Nota verde "Sin
    limitaciones activas" solo si ese día no hubo limitación (se eliminó el banner de activas total).
  · Novedades manuales (Datos > Bitácora) aparecen automáticamente en la bitácora automática con su
    fecha/hora (tipo "Novedad", badge violeta).
  · **Fix Streamlit 1.58** (redeploy trajo versión sin pin → rompió CSS): radios adaptados a
    `data-testid="stRadioGroup"`; botones del sidebar centrados vía `justify-content` nativo (se
    quitaron las reglas sobre hijos que lo rompían). `requirements.txt` fija `streamlit==1.58.0`.
  · Keep-alive `st_autorefresh` bajado de 1 h → 5 min. Botones del sidebar por `data-testid`.
- **2026-07-08 — Rediseño analítico + alertas + contraseña:**
  · **Ingreso por unidad junto al MAE** (`gen_unidad.py`): tarjeta "Ingreso estimado" (Σ gen×CMG del
    período) a la izquierda del MAE, con delta % vs la semana previa (`[e-14d, e-7d]`, verde↑/rojo↓).
  · **Contraseña `jt` en Datos** (`app.py` `_acceso_restringido`/`_CLAVE_DATOS`): gate para Ingreso
    Manual y Datos & Bitácora; se recuerda en `session_state["datos_auth"]`. Infotécnica libre.
  · **Rediseño completo de Estadísticas** (`estadisticas.py`): heatmap CMG hora×fecha, curva de
    duración de precios, ingreso acumulado (área apilada), perfil horario medio de generación, +
    aporte/FP/correlación/precisión pulidos. KPIs enriquecidos (disponibilidad, ingreso realizado).
  · **Rediseño completo de Costos** (`costo.py`): dejó de ser overview → deep-dive económico
    complementario a Estadísticas. Benchmarking CMG online/programado/real (un solo eje), elasticidad
    precio-demanda (scatter, reemplaza el eje dual demanda), ingreso diario apilado, mapa de valor
    (burbuja energía×precio), cascada de ingreso (waterfall), calidad del pronóstico CMG (hist. error).
  · **Rediseño completo de ML** (`ml.py`): suite de 3 modelos. (1) Forecast CMG PROBABILÍSTICO
    (XGBoost + banda P10-P90 por residuales, features de medias móviles) + INGRESO ESPERADO 24h
    (CMG previsto × despacho programado/perfil típico). (2) Anomalías (IsolationForest) + índice de
    severidad 0-100 con línea temporal. (3) NUEVO: Regímenes operacionales (KMeans sobre perfiles
    horarios diarios de CMG, agrupa por FORMA, auto-nombra los "tipos de día", + calendario temporal).
  · **Solicitudes en la bitácora automática** (`bitacora_auto.py`): solicitudes que mencionan
    Angamos/Cochrane se asignan a ANG1/ANG2 o CCR1/CCR2 (badge teal "Solicitud", ancladas a
    `fecha_inicio`).
  · **Alerta de potencia 0** (`gen_unidad.py` + `kpis.py`): real < 5 MW = trip/desconexión/mantención.
    Franjas rojas + marcadores "✕" en la serie + banner rojo sobre el gráfico; `UMBRAL_TRIP` del tope
    subido 1→5 MW. (El usuario aclaró: <5 MW ya indica 0 en la práctica.)
  · Nota operacional: dots ámbar del sidebar = último dato de AYER (verde=hoy, rojo=más viejo);
    lógica en `_edad_fuente` (`sidebar.py`). No es necesariamente falla (rezago SCADA del CEN).

---

*Actualizado 2026-07-08. Proyecto CTM Mejillones (4 térmicas ANG/CCR).*
*Stack: Streamlit + supabase-py/psycopg2 + GitHub Actions + API CEN (SIP/OPS) + CMG S3 + scikit-learn/xgboost.*
