# CLAUDE.md — Dashboard CTM Mejillones

## Qué es este proyecto
Dashboard operacional del Complejo Térmico Mejillones (AES Andes).
Monitorea generación real vs programada + CMG + SSCC para 4 unidades:
ANG1, ANG2 (Angamos) y CCR1, CCR2 (Cochrane).

Desplegado en Streamlit Cloud. Código en GitHub (`ukubrick/ctm-mejillones`).
Adquisición automática vía GitHub Actions cada hora (minuto 5 UTC).

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

## Archivos principales

- `app.py` — Dashboard Streamlit v5 (~1300 líneas)
- `Adquisicion.py` — Script de adquisición (~620 líneas)
- `requirements.txt` — requests, psycopg2-binary, python-dotenv, streamlit, pandas, plotly, matplotlib, reportlab, **streamlit-autorefresh**
- `.github/workflows/adquisicion.yml` — cron "5 * * * *", timeout 55 min
- `backfill_programada.py` — script de recuperación manual de gen. programada (uso: `python3 backfill_programada.py YYYY-MM-DD YYYY-MM-DD`)

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

## Estado actual del código (2026-06-18 — actualizado)

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

---

## Pendiente / Por explorar

- **[PRIORIDAD 1] Solicitudes de trabajo — integrar al dashboard** (`/solicitudes-trabajo/v4/findByDate`, SIP) — endpoint confirmado funcional el 2026-06-17 (ventana ≤7 días). El servidor CEN es intermitente, reintentar con `python probe_solicitudes.py` hasta obtener respuesta estable. Parámetros confirmados: `startDate`, `endDate` (YYYY-MM-DD), `page` (base 1), `limit=100`. Respuesta: `{"data":[...], "totalPages":N, "page":N, "limit":N}`. Con 7 días devuelve ~267 páginas (~26.700 registros del sistema). Campos conocidos: `id`, `correlativo` (JOIN con `limitaciones_transmision`), `empresa_nombre`, `grupo_nombre`, `centro_control` (campo extra no documentado), `status`, `tipo_solicitud`, `type`, `origen`, `tipo_programacion`, `consumo`, `perdida_registro_energia`, `descripcion_nivel_riesgo`, `fecha_inicio`, `fecha_fin`, `created`, `modified`, `partition_date`. Filtro local por `empresa_nombre` + `grupo_nombre` + `centro_control` buscando ANGAMOS/COCHRANE/AES. **Próximo paso:** cuando el servidor responda estable, correr probe para ver empresas únicas y confirmar cómo aparece AES Andes en los datos, luego integrar sección en dashboard igual que limitaciones.

- **SSCC programados PCP** (`/servicios-complementarios-programados-pcp/v4/findByDate`, SIP) — respondía 502 el 2026-06-09 por caída del servidor CEN. Probar cuando la API se recupere.
- **Instrucciones operacionales SSCC** (`/instrucciones-operacionales-sscc/v4/findByDate`, SIP) — mismo estado, 502 ese día.
- **Stock combustible** (`/stock-combustible/v4/findByDate`, SIP) — retorna 404 consistente, posible endpoint inactivo o requiere parámetros distintos.
- **Optimización PCP:** actualmente se hacen 2 consultas separadas (una por día en DIAS_VENTANA). Podría hacerse una sola con rango de 2 días para reducir tiempo de ~24 min a ~12 min.
- **Limitaciones/estado operativo unidades:** `/operativos/v1/estados` (Operaciones) sólo retorna catálogo de 21 tipos de estado (LP, LF, LC, DLP, etc.), no el estado actual por unidad. Los módulos referenciados (`desconexion_intervencion`, `informe_fallas`, `limitaciones`) tienen rutas propias aún no identificadas. Angamos ID=377, Cochrane ID=379.
- **Solicitudes de trabajo** (`/solicitudes-trabajo/v4/findByDate`, SIP) — explorado 2026-06-11, 502 persistente (caída CEN). **Pendiente probar 2026-06-12.** Schema conocido: `id`, `correlativo` (JOIN con limitaciones_transmision), `empresa_nombre`, `grupo_nombre`, `status`, `tipo_solicitud`, `type`, `origen`, `tipo_programacion`, `consumo`, `perdida_registro_energia`, `descripcion_nivel_riesgo`, `fecha_inicio`, `fecha_fin`, `created`, `modified`, `partition_date`. Filtro: `empresa_nombre` o `grupo_nombre` contiene ANGAMOS/COCHRANE. Integración planeada: complementar sección limitaciones con detalle de la solicitud asociada via correlativo.
- **Limpieza de archivos obsoletos:** eliminar scripts de prueba/exploración que ya cumplieron su propósito: `check_cmg.py`, `probe_sscc.py`, `test_api_cen.py`, `test_cmg_crucero.py`, `test_scraping_cmg.py`, `resumen_endpoints_sscc_sen.md`. También evaluar si conservar `backfill_programada.py` (backfill jun 5–9 ya completado).
- **RLS Supabase (seguridad):** habilitar Row-Level Security en todas las tablas públicas del proyecto `ctm-mejillones`. El SQL Editor web da timeout; usar psql con conexión directa `db.luddatnopktghtxeixyd.supabase.co:5432` (obtener desde Project Settings → Database → Direct connection). Ver SQL completo en historial de conversación 2026-06-16.
