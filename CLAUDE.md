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
- `.github/workflows/adquisicion.yml` — cron "5 * * * *", timeout 35 min
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
DIAS_VENTANA = 2   # días hacia atrás — gen. real, programada y SSCC

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

---

## Estado actual del código (2026-06-09)

Todo implementado y funcionando en producción:
- ✅ Generación real automática (API CEN SIPUB) — ventana 2 días
- ✅ Generación programada automática (API CEN PCP) — ventana 2 días, limit=5000
- ✅ CMG dos nodos: Crucero 220kV y Tarapacá 220kV (S3 portal CEN)
- ✅ SSCC instrucciones (API CEN Operaciones) — ventana 2 días, pageSize=-1
- ✅ Retry exponencial en todos los endpoints (429/5xx)
- ✅ Dashboard: KPIs, gráficos por unidad, análisis costo, SSCC por unidad, bitácora, ingreso manual de respaldo, exportación PDF
- ✅ Timezone Chile en Adquisicion.py
- ✅ DISTINCT ON para programada priorizando CEN_PCP sobre MANUAL
- ✅ Workflow timeout 35 min (PCP tarda ~12 min/día)
- ✅ Auto-refresh horario (`streamlit-autorefresh`, 3600000 ms) — recarga automática y previene sleep de Streamlit Cloud
- ✅ Sección SSCC ubicada después de CMG, con guía desplegable (`<details>/<summary>` HTML nativo), KPIs, tabs Por unidad / Estadísticas / Tabla completa
- ✅ Footer: "Dashboard creado por Erick Herrera"
- ✅ Backfill gen. programada 05–09 junio 2026 completado (3115 registros recuperados)

---

## Pendiente / Por explorar

- **SSCC programados PCP** (`/servicios-complementarios-programados-pcp/v4/findByDate`, SIP) — respondía 502 el 2026-06-09 por caída del servidor CEN. Probar cuando la API se recupere.
- **Instrucciones operacionales SSCC** (`/instrucciones-operacionales-sscc/v4/findByDate`, SIP) — mismo estado, 502 ese día.
- **Stock combustible** (`/stock-combustible/v4/findByDate`, SIP) — retorna 404 consistente, posible endpoint inactivo o requiere parámetros distintos.
- **Optimización PCP:** actualmente se hacen 2 consultas separadas (una por día en DIAS_VENTANA). Podría hacerse una sola con rango de 2 días para reducir tiempo de ~24 min a ~12 min.
- **Limitaciones/estado operativo unidades:** `/operativos/v1/estados` (Operaciones) sólo retorna catálogo de 21 tipos de estado (LP, LF, LC, DLP, etc.), no el estado actual por unidad. Los módulos referenciados (`desconexion_intervencion`, `informe_fallas`, `limitaciones`) tienen rutas propias aún no identificadas. Angamos ID=377, Cochrane ID=379.
