# Dashboard ERNC AES Andes — Documentación de Arquitectura y Datos

> Documento de base para nuevo proyecto independiente.  
> Generado el 2026-06-17 a partir de pruebas reales contra APIs CEN.

---

## 1. Descripción del Proyecto

Dashboard operacional para parques de energías renovables no convencionales (ERNC) de **AES Andes**:
fotovoltaicos y eólicos ubicados en Chile. Monitorea generación real vs programada, condiciones
meteorológicas e irradiancia en tiempo real, con mapa interactivo de ubicación de parques.

Proyecto **independiente** al dashboard CTM Mejillones (térmicas ANG/CCR).

---

## 2. Parques a Monitorear

### Confirmados en API CEN — Gen. Real (probado 2026-06-17)

| Nombre solicitado | Nombre oficial CEN | `id_central` | `llave_opreal` | Potencia máx (MW) | Tecnología |
|---|---|---|---|---|---|
| Andes Solar I | PFV ANDES SOLAR | `374` | `PFV ANDES SOLAR` | 23.97 | Solar FV |
| Andes Solar 2 A | PFV ANDES SOLAR II | `643` | `PFV ANDES SOLAR IIA` | 91.09 | Solar FV |
| Andes Solar 2 B | PFV ANDES SOLAR II-B | `1850` | `PFV ANDES SOLAR IIB` | 220.0 | Solar FV |
| Andes Solar III | PFV ANDES SOLAR III | `2322` | `PFV Andes Solar III` | 175.0 | Solar FV |
| Andes Solar IV | PFV ANDES SOLAR IV | `2076` | `PFV ANDES SOLAR IV` | 220.0 | Solar FV |
| PFV Bolero | PFV BOLERO | `456` | `PFV BOLERO` | 161.3 | Solar FV |
| PE Campo Lindo | PE CAMPO LINDO | `1845` | `PE CAMPO LINDO` | 76.8 | Eólica |
| PE Los Olmos | PE LOS OLMOS | `1757` | `PE LOS OLMOS` | 115.92 | Eólica |
| PE Los Cururos | PE LOS CURUROS | `318` | `PE LOS CURUROS` | 115.08 | Eólica |
| PE San Matías | PE SAN MATIAS | `2091` | `PE SAN MATIAS` | 87.5 | Eólica |
| PE Mesamavida | PE MESAMAVIDA | `1758` | `PE MESAMÁVIDA` | 70.56 | Eólica |

**Total capacidad instalada confirmada: ~1.358 MW FV + ~466 MW Eólica = ~1.824 MW**

### BESS asociados (aparecen en gen-real, `id_central=None`)

Varios parques tienen sistemas de almacenamiento activos en la API.
No tienen `id_central`, se identifican por `llave_opreal`:

| `llave_opreal` | `central` | Potencia máx (MW) |
|---|---|---|
| `PFV ANDES SOLAR IIA` *(referencia)* | SAE PFV Sol de los Andes (Inyección) | 105.0 |
| `BESS ANDES SOLAR IIA (inyección)` | BESS Andes Solar IIA | 84.0 |
| `BESS ANDES SOLAR IIA (retiro)` | BESS Andes Solar IIA | 84.0 |
| `BESS ANDES SOLAR IIB (inyección)` | BESS Andes Solar IIB | 136.5 |
| `BESS ANDES SOLAR IIB (retiro)` | BESS Andes Solar IIB | 220.0 |
| `BESS ANDES SOLAR IV (inyección)` | BESS Andes IV | 140.0 |
| `BESS ANDES SOLAR IV (retiro)` | BESS Andes IV | 220.0 |
| `SAE PFV Andes Solar III (Inyección)` | SAE Andes Solar III | 177.0 |
| `SAE PFV Andes Solar III (Retiro de central)` | SAE Andes Solar III | 172.0 |
| `SAE PFV Bolero (Inyección)` | SAE PFV Bolero | 160.0 |
| `SAE PFV Bolero (Retiro de central)` | SAE PFV Bolero | 160.0 |

---

## 3. Propietarios / Coordinados (de API gen-real)

| id_central | propietario | coordinado |
|---|---|---|
| 374 | ANDES SOLAR SPA | ANDES SOLAR SPA |
| Resto | Por confirmar paginando gen-real con cada id_central | — |

---

## 4. APIs CEN Disponibles (confirmadas en producción)

### 4.1 Autenticación

Misma plataforma 3scale del dashboard CTM. Parámetro `user_key` en query string.

| Plan | Host | Variable secret |
|---|---|---|
| Información Pública (SIP) | `sipub.api.coordinador.cl` | `CEN_USER_KEY` |
| Operaciones | `operacion.api.coordinador.cl` | `CEN_OPS_KEY` |

### 4.2 Generación Real

```
GET https://sipub.api.coordinador.cl/generacion-real/v3/findByDate
    ?startDate=YYYY-MM-DD
    &endDate=YYYY-MM-DD
    &pageSize=5000
    &page=1
    &user_key={CEN_USER_KEY}
```

- **Filtra por central en servidor** cuando se pasa `idCentral={id}`, pero también se puede traer todo y filtrar local.
- Paginación: 5 páginas × 5000 registros (~24.000 registros del sistema por 2 días).
- Campos clave en respuesta:

```json
{
  "id_opreal": 15293,
  "llave_opreal": "PFV ANDES SOLAR",
  "id_central": 374,
  "central": "PFV ANDES SOLAR",
  "gen_real_mw": 0.0,
  "fecha_hora": "2026-06-16 20:00:00",
  "hora": 21,
  "potencia_maxima": "23.9745",
  "id_propietario": 2668,
  "propietario": "ANDES SOLAR SPA",
  "id_coordinado": 2519,
  "coordinado": "ANDES SOLAR SPA",
  "tipo_tecnologia": "Solar",
  "subtipo_tecnologia": null,
  "factor_ernc": 1.0,
  "alcance": "global",
  "valor_ernc": 0.0
}
```

### 4.3 Generación Programada PCP

```
GET https://sipub.api.coordinador.cl/generacion-programada-pcp/v4/findByDate
    ?startDate=YYYY-MM-DD
    &endDate=YYYY-MM-DD
    &limit=5000
    &page=1
    &user_key={CEN_USER_KEY}
```

- **NO filtra por central en servidor** (ignorar parámetro `idCentral` — retorna igual sin filtrar).
- Paginar todo y filtrar local por `id_central`.
- ~3141 páginas × 5000 para 2 días del sistema completo → filtrar por `id_central` de cada parque.
- Tarda ~12 min por día consultado si se recorre todo el sistema.
- Llaves confirmadas de nuestros parques:

```python
LLAVES_GEN_PROG = {
    "AS1":  ["ANDES_FV"],
    "AS2A": ["ANDES_2A_FV"],
    "AS2B": ["ANDES_2B_FV"],
    "AS3":  ["ANDES_3_FV"],
    "AS4":  ["ANDES_4_FV"],
    "BOL":  ["BOLERO_1_FV"],
    "CL":   ["CAMPO_LINDO_EO"],
    "OLM":  ["LOS_OLMOS_EO"],
    "CUR":  ["LOS_CURUROS_EO"],
    "STM":  ["SAN_MATIAS_EO"],
    "MSM":  ["MESAMAVIDA_EO"],
}
```

- Campos adicionales en PCP: `costo_generacion_usd`, `costo_partida_detencion_usd`, `capacidad_disponible_mw`, `fecha_programa`, `region`, `barra`, `clasificacion`, `configuracion`, `id_barra_info`, `nmb_barra_info`.

### 4.4 SSCC Instrucciones (Operaciones)

```
GET https://operacion.api.coordinador.cl/servicios-complementarios/v1
    ?initDate=YYYY-MM-DD
    &endDate=YYYY-MM-DD
    &page=0
    &pageSize=-1
    &user_key={CEN_OPS_KEY}
```

- `-1` trae todos en una llamada (~500 registros sistema).
- Paginación: `content` (no `data`), campos en camelCase (`centralUnidad`, `instruccionSscc`, `inicioPeriodo`, etc.).
- Solo **PE San Matías** confirmado con instrucciones activas (`PE-SANMATIAS`, instrucción `CPF(+)`).
- Los parques solares generalmente no aparecen en SSCC (sin compromisos de servicios complementarios).

### 4.5 Limitaciones de Transmisión

```
GET https://sipub.api.coordinador.cl/limitaciones-transmision/v4/findByDate
    ?startDate=YYYY-MM-DD
    &endDate=YYYY-MM-DD
    &limit=100
    &page=1
    &user_key={CEN_USER_KEY}
```

- Filtrar local por `instalacion_nombre` o `id_central`.
- Confirmadas para este grupo de parques (2026-06-01 a 2026-06-17):
  - PE MESAMAVIDA — status: pendiente, potencia: 0.0 MW
  - PE LOS OLMOS — status: pendiente, potencia: 105.6 MW
  - PFV BOLERO — status: pendiente, potencia: 124.8 MW
- Ventana recomendada: 30 días hacia atrás (limitaciones de larga duración).

### 4.6 CMG (Costo Marginal)

```
GET https://cen-template-graph-pweb-prod.s3.us-east-1.amazonaws.com/CMG-online/costo-marginal-online.json
Headers: Referer: https://www.coordinador.cl/
```

- JSON estático, actualizado cada ~15 min. Solo 8 nodos fijos del sistema.
- Nodos más cercanos a los parques: `CRUCERO_______220`, `TARAPACA______220` (norte), y del sur depende de ubicación.
- Requiere mapear cada parque al nodo CMG más cercano geográficamente.

---

## 5. APIs de Meteorología e Irradiancia (a integrar)

### 5.1 Open-Meteo (Recomendada — gratuita, sin key)

```
GET https://api.open-meteo.com/v1/forecast
    ?latitude={lat}
    &longitude={lon}
    &hourly=temperature_2m,windspeed_10m,windspeed_100m,winddirection_10m,
            shortwave_radiation,direct_radiation,diffuse_radiation,
            direct_normal_irradiance,global_tilted_irradiance
    &timezone=America/Santiago
    &forecast_days=7
```

- **Sin API key.** Gratis hasta 10.000 llamadas/día. Resolución horaria.
- Cobertura global, excelente para Chile.
- Para parques solares: `shortwave_radiation` (GHI), `direct_normal_irradiance` (DNI), `global_tilted_irradiance` (GTI).
- Para parques eólicos: `windspeed_10m`, `windspeed_100m` (hub height aprox.), `winddirection_10m`.

### 5.2 Solcast (Irradiancia solar — plan gratuito para investigación)

```
GET https://api.solcast.com.au/radiation/forecasts
    ?latitude={lat}
    &longitude={lon}
    &hours=168
    &period=PT60M
    &output_parameters=ghi,dni,dhi,cloud_opacity,air_temp,wind_speed_10m,wind_direction_10m
    &format=json
    &api_key={SOLCAST_API_KEY}
```

- Especializado en irradiancia solar (más preciso que Open-Meteo para FV).
- Plan gratuito: 10 sitios, hasta 10 llamadas/día por sitio.
- Requiere registro en solcast.com.au.

### 5.3 OpenWeatherMap (alternativa con key gratuita)

```
GET https://api.openweathermap.org/data/2.5/forecast
    ?lat={lat}&lon={lon}
    &appid={OWM_KEY}
    &units=metric
    &cnt=40
```

- API key gratuita (60 calls/min, 1.000.000 calls/mes).
- Incluye: temperatura, humedad, nubosidad, viento, precipitación.
- No tan preciso en irradiancia como Solcast.

### 5.4 ERA5 / Copernicus (histórico — gratuito)

```python
# Via cdsapi (librería Python)
import cdsapi
c = cdsapi.Client()
c.retrieve('reanalysis-era5-single-levels', {
    'variable': ['surface_solar_radiation_downwards', '100m_u_component_of_wind', '100m_v_component_of_wind'],
    'year': '2026', 'month': '06', 'day': ['01', '17'],
    'time': [f'{h:02d}:00' for h in range(24)],
    'area': [-20, -72, -40, -65],  # Norte-Oeste-Sur-Este Chile
    'format': 'netcdf',
}, 'output.nc')
```

- Ideal para análisis histórico y correlación con gen. real histórica.
- Requiere cuenta gratuita en cds.climate.copernicus.eu.

---

## 6. Coordenadas Geográficas de los Parques

Coordenadas aproximadas para mapa y consultas meteorológicas.
**Verificar y refinar con datos oficiales de la empresa.**

| Parque | Lat | Lon | Región | Nodo CMG más cercano |
|---|---|---|---|---|
| PFV Andes Solar I | -24.10 | -69.85 | Antofagasta | CRUCERO_______220 |
| PFV Andes Solar 2A | -24.10 | -69.85 | Antofagasta | CRUCERO_______220 |
| PFV Andes Solar 2B | -24.10 | -69.85 | Antofagasta | CRUCERO_______220 |
| PFV Andes Solar III | -24.12 | -69.87 | Antofagasta | CRUCERO_______220 |
| PFV Andes Solar IV | -24.08 | -69.83 | Antofagasta | CRUCERO_______220 |
| PFV Bolero | -26.20 | -69.90 | Atacama | CRUCERO_______220 |
| PE Campo Lindo | -37.80 | -72.40 | Biobío | Por definir |
| PE Los Olmos | -36.20 | -72.60 | Biobío | Por definir |
| PE Los Cururos | -30.30 | -71.00 | Coquimbo | Por definir |
| PE San Matías | -38.10 | -72.50 | Biobío | Por definir |
| PE Mesamavida | -37.50 | -72.20 | Biobío | Por definir |

> ⚠️ Las coordenadas son aproximadas. Solicitar ubicaciones exactas a AES Andes o buscar en el
> registro CEN / registro SMA de declaraciones de impacto ambiental (DGA/SEA).

---

## 7. Stack Tecnológico Propuesto

| Capa | Tecnología | Razón |
|---|---|---|
| Frontend | Streamlit | Mismo stack que CTM, rápido de implementar |
| Mapa interactivo | `pydeck` o `folium` + `streamlit-folium` | Mapas con marcadores, hover con datos en vivo |
| Backend DB | Supabase PostgreSQL | Mismo proveedor, nuevo proyecto |
| Adquisición CEN | Python + GitHub Actions | Igual que CTM, cron horario |
| Meteorología | Open-Meteo (gratuita) + Solcast (solar) | Sin costo, alta calidad |
| Gráficos | Plotly | Igual que CTM |
| Exportación | ReportLab (PDF) | Igual que CTM |

### Dependencias Python sugeridas

```
requests
psycopg2-binary
python-dotenv
streamlit
pandas
plotly
pydeck          # mapa 3D interactivo
streamlit-folium # alternativa mapa
folium
streamlit-autorefresh
reportlab
openmeteo-requests  # cliente Open-Meteo oficial
retry-requests
```

---

## 8. Esquema de Base de Datos (nuevo proyecto)

### `generacion_real_ernc`
```sql
CREATE TABLE generacion_real_ernc (
    id            SERIAL PRIMARY KEY,
    parque        TEXT NOT NULL,           -- código interno: AS1, AS2A, AS2B, AS3, AS4, BOL, CL, OLM, CUR, STM, MSM
    id_central    INTEGER,
    llave_opreal  TEXT,
    central       TEXT,
    gen_real_mw   NUMERIC,
    potencia_max  NUMERIC,
    factor_ernc   NUMERIC,
    valor_ernc    NUMERIC,
    tipo_tecnologia TEXT,
    fecha_hora    TEXT NOT NULL,           -- YYYY-MM-DD HH:MM:SS (hora 0-based)
    hora          INTEGER,
    UNIQUE (parque, fecha_hora)
);
```

### `generacion_programada_ernc`
```sql
CREATE TABLE generacion_programada_ernc (
    id                  SERIAL PRIMARY KEY,
    parque              TEXT NOT NULL,
    llave_gen           TEXT,
    gen_programada_mw   NUMERIC,
    capacidad_disponible_mw NUMERIC,
    costo_generacion_usd NUMERIC,
    fecha_hora          TEXT NOT NULL,
    hora                INTEGER,
    fecha_programa      TEXT,
    fuente              TEXT DEFAULT 'CEN_PCP',
    UNIQUE (parque, fecha_hora, fuente)
);
```

### `meteo_ernc`
```sql
CREATE TABLE meteo_ernc (
    id              SERIAL PRIMARY KEY,
    parque          TEXT NOT NULL,
    fecha_hora      TEXT NOT NULL,         -- UTC o local Chile, documentar
    -- Solar
    ghi_wm2         NUMERIC,               -- Global Horizontal Irradiance
    dni_wm2         NUMERIC,               -- Direct Normal Irradiance
    dhi_wm2         NUMERIC,               -- Diffuse Horizontal Irradiance
    -- Eólico
    wind_speed_10m  NUMERIC,               -- m/s
    wind_speed_100m NUMERIC,               -- m/s (hub height aprox.)
    wind_dir_10m    NUMERIC,               -- grados
    -- Generales
    temp_2m         NUMERIC,               -- °C
    humidity        NUMERIC,               -- %
    cloud_cover     NUMERIC,               -- %
    fuente          TEXT,                  -- 'open-meteo', 'solcast'
    UNIQUE (parque, fecha_hora, fuente)
);
```

### `limitaciones_ernc`
```sql
CREATE TABLE limitaciones_ernc (
    id                      TEXT PRIMARY KEY,  -- hex ID de la API CEN
    correlativo             INTEGER,
    parque                  TEXT,
    empresa_nombre          TEXT,
    instalacion_nombre      TEXT,
    status                  TEXT,
    fecha_perturbacion      TEXT,
    fecha_retorno_estimada  TEXT,
    fecha_efectiva_retorno  TEXT,
    potencia                NUMERIC,
    unidad_medida_potencia  TEXT,
    produce_indisponibilidad BOOLEAN,
    afecta_sscc             BOOLEAN,
    observacion             TEXT,
    created                 TEXT,
    modified                TEXT
);
```

### `sscc_ernc`
```sql
CREATE TABLE sscc_ernc (
    id               SERIAL PRIMARY KEY,
    parque           TEXT,
    fecha            TEXT,
    inicio_periodo   TEXT,
    fin_periodo      TEXT,
    instruccion_sscc TEXT,
    id_configuracion INTEGER,
    central_unidad   TEXT,
    disponibilidad   NUMERIC,
    baja             NUMERIC,
    sube             NUMERIC,
    unidad_medida    TEXT,
    UNIQUE (fecha, id_configuracion, instruccion_sscc, inicio_periodo)
);
```

---

## 9. Constantes de Código (Adquisicion_ernc.py)

```python
from zoneinfo import ZoneInfo

API_BASE_SIP = "https://sipub.api.coordinador.cl"
API_BASE_OPS = "https://operacion.api.coordinador.cl"
TZ_CHILE     = ZoneInfo("America/Santiago")

DIAS_VENTANA     = 2    # gen. real, programada, meteo, SSCC
DIAS_VENTANA_LIM = 30   # limitaciones

# Códigos internos → id_central CEN
ID_CENTRAL = {
    "AS1":  374,
    "AS2A": 643,
    "AS2B": 1850,
    "AS3":  2322,
    "AS4":  2076,
    "BOL":  456,
    "CL":   1845,
    "OLM":  1757,
    "CUR":  318,
    "STM":  2091,
    "MSM":  1758,
}

# Nombres display para el dashboard
NOMBRE_DISPLAY = {
    "AS1":  "Andes Solar I",
    "AS2A": "Andes Solar 2A",
    "AS2B": "Andes Solar 2B",
    "AS3":  "Andes Solar III",
    "AS4":  "Andes Solar IV",
    "BOL":  "PFV Bolero",
    "CL":   "PE Campo Lindo",
    "OLM":  "PE Los Olmos",
    "CUR":  "PE Los Cururos",
    "STM":  "PE San Matías",
    "MSM":  "PE Mesamavida",
}

# Llaves gen. real
LLAVES_OPREAL = {
    "AS1":  "PFV ANDES SOLAR",
    "AS2A": "PFV ANDES SOLAR IIA",
    "AS2B": "PFV ANDES SOLAR IIB",
    "AS3":  "PFV Andes Solar III",
    "AS4":  "PFV ANDES SOLAR IV",
    "BOL":  "PFV BOLERO",
    "CL":   "PE CAMPO LINDO",
    "OLM":  "PE LOS OLMOS",
    "CUR":  "PE LOS CURUROS",
    "STM":  "PE SAN MATIAS",
    "MSM":  "PE MESAMÁVIDA",
}

# Llaves gen. programada PCP
LLAVES_GEN_PROG = {
    "AS1":  ["ANDES_FV"],
    "AS2A": ["ANDES_2A_FV"],
    "AS2B": ["ANDES_2B_FV"],
    "AS3":  ["ANDES_3_FV"],
    "AS4":  ["ANDES_4_FV"],
    "BOL":  ["BOLERO_1_FV"],
    "CL":   ["CAMPO_LINDO_EO"],
    "OLM":  ["LOS_OLMOS_EO"],
    "CUR":  ["LOS_CURUROS_EO"],
    "STM":  ["SAN_MATIAS_EO"],
    "MSM":  ["MESAMAVIDA_EO"],
}

# Tecnología por parque
TECNOLOGIA = {
    "AS1": "Solar", "AS2A": "Solar", "AS2B": "Solar",
    "AS3": "Solar", "AS4": "Solar", "BOL": "Solar",
    "CL": "Eólica", "OLM": "Eólica", "CUR": "Eólica",
    "STM": "Eólica", "MSM": "Eólica",
}

# Potencias máximas (MW)
PMAX = {
    "AS1":  23.97,
    "AS2A": 91.09,
    "AS2B": 220.0,
    "AS3":  175.0,
    "AS4":  220.0,
    "BOL":  161.3,
    "CL":   76.8,
    "OLM":  115.92,
    "CUR":  115.08,
    "STM":  87.5,
    "MSM":  70.56,
}

# Coordenadas (aproximadas — verificar con AES Andes)
COORDENADAS = {
    "AS1":  {"lat": -24.10, "lon": -69.85},
    "AS2A": {"lat": -24.10, "lon": -69.85},
    "AS2B": {"lat": -24.10, "lon": -69.85},
    "AS3":  {"lat": -24.12, "lon": -69.87},
    "AS4":  {"lat": -24.08, "lon": -69.83},
    "BOL":  {"lat": -26.20, "lon": -69.90},
    "CL":   {"lat": -37.80, "lon": -72.40},
    "OLM":  {"lat": -36.20, "lon": -72.60},
    "CUR":  {"lat": -30.30, "lon": -71.00},
    "STM":  {"lat": -38.10, "lon": -72.50},
    "MSM":  {"lat": -37.50, "lon": -72.20},
}

# Colores por tecnología (para mapa y gráficos)
COLORES = {
    "Solar":  "#F59E0B",  # amarillo
    "Eólica": "#3B82F6",  # azul
}

# Nodo CMG más cercano por parque
CMG_NODO = {
    "AS1": "CRUCERO_______220", "AS2A": "CRUCERO_______220",
    "AS2B": "CRUCERO_______220", "AS3": "CRUCERO_______220",
    "AS4": "CRUCERO_______220", "BOL": "CRUCERO_______220",
    # eólicos del sur: por definir cuando se confirmen coordenadas
}

# SSCC — centralUnidad API → código interno
LLAVES_SSCC = {
    "PE-SANMATIAS": "STM",
    # resto por confirmar si tienen instrucciones en otros períodos
}
```

---

## 10. Secciones del Dashboard (app_ernc.py)

### 10.1 Header / Sidebar
- Logo AES Andes
- Dot de conexión a Supabase (igual que CTM)
- Última hora adquirida por fuente (Gen. real, PCP, Meteo, CMG)
- Selector de parque o "Todos"
- Selector de rango de fechas

### 10.2 Mapa Interactivo (sección principal)
- `pydeck` ScatterplotLayer o `folium` con `streamlit-folium`
- Marcadores por parque: color según tecnología (Solar=amarillo, Eólica=azul)
- Tamaño del marcador proporcional a potencia instalada o gen. actual
- Tooltip al hover: parque, gen actual (MW), % de potencia, irradiancia/viento actual
- Vista inicial: Chile completo, zoom automático al set de parques

### 10.3 KPIs Generales (fila de métricas)
- Generación total actual (MW) vs capacidad instalada total
- Factor de planta conjunto (%)
- Generación del día (MWh acumulados)
- Desvío real vs programado total (MW)

### 10.4 Tabs por tecnología: Solar / Eólica / Todos

**Tab Solar (AS1, AS2A, AS2B, AS3, AS4, BOL):**
- Gráfico gen. real vs programada (apilado o por parque)
- Curva de irradiancia (GHI/DNI) en eje secundario
- Factor de planta solar vs hora del día

**Tab Eólica (CL, OLM, CUR, STM, MSM):**
- Gráfico gen. real vs programada
- Curva de velocidad de viento (10m / 100m) en eje secundario
- Rosa de vientos (windrose) si se integra `windrose` o `plotly` polar

**Tab Todos:**
- Comparativa entre parques (barras horizontales)

### 10.5 Detalle por Parque (expandible)
- KPIs individuales: gen actual, potmax, factor planta, desvío
- Gráfico horario últimas 24h / 7 días
- Condición meteorológica actual (irradiancia o viento según tecnología)
- Limitaciones activas (si aplica)

### 10.6 Sección CMG
- Precio actual en nodos cercanos (Crucero 220kV, otros por confirmar)
- Ingreso estimado = gen_real_mw × cmg_usd_mwh

### 10.7 Sección Limitaciones de Transmisión
- Misma estructura que CTM (cards con status, potencia, fechas)
- Filtrar por parque

### 10.8 Exportación
- PDF resumen del día (ReportLab)
- CSV descarga de datos

---

## 11. GitHub Actions — Adquisición Automática

```yaml
# .github/workflows/adquisicion_ernc.yml
name: Adquisición ERNC

on:
  schedule:
    - cron: "10 * * * *"   # minuto 10 de cada hora (distinto a CTM que va en el 5)
  workflow_dispatch:

jobs:
  adquirir:
    runs-on: ubuntu-latest
    timeout-minutes: 40
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python Adquisicion_ernc.py
        env:
          CEN_USER_KEY: ${{ secrets.CEN_USER_KEY }}
          CEN_OPS_KEY:  ${{ secrets.CEN_OPS_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          OPENMETEO_ENABLED: "true"   # flag para habilitar meteo
```

---

## 12. Variables de Entorno / Secrets (nuevo proyecto)

| Variable | Descripción |
|---|---|
| `CEN_USER_KEY` | API key SIP CEN (misma que CTM) |
| `CEN_OPS_KEY` | API key Operaciones CEN (misma que CTM) |
| `DATABASE_URL` | PostgreSQL Supabase — nuevo proyecto `ernc-aes` |
| `SOLCAST_API_KEY` | API key Solcast (si se usa) |

---

## 13. Pendientes y Próximos Pasos

### Antes de empezar a codificar
- [ ] Confirmar coordenadas exactas de los 11 parques con AES Andes
- [ ] Decidir si usar Open-Meteo (gratis, sin clave) o Solcast (más preciso para FV)
- [ ] Definir nodos CMG para parques del sur (eólicos Biobío/Coquimbo)
- [ ] Crear proyecto en Supabase (`ernc-aes`) y obtener nueva `DATABASE_URL`
- [ ] Crear repositorio GitHub `aes-ernc-dashboard` y configurar secrets

### Implementación sugerida (orden)
1. `Adquisicion_ernc.py` — gen. real + gen. programada (igual que CTM, adaptar IDs)
2. Tablas en Supabase + GitHub Actions cron
3. `app_ernc.py` — KPIs básicos + gráficos gen real vs programada
4. Integración meteo (Open-Meteo): añadir llamadas y tabla `meteo_ernc`
5. Mapa interactivo (`pydeck` o `folium`)
6. Limitaciones de transmisión
7. SSCC (solo San Matías confirmado, monitorear otros)
8. Exportación PDF
9. BESS: evaluar si integrar SAE/BESS como entidades separadas o sub-filas

### Explorar / Pendiente en APIs
- Solicitudes de trabajo (`/solicitudes-trabajo/v4/findByDate`, SIP) — igual que CTM, filtrar por empresa AES
- Verificar si parques eólicos (sur) tienen nodo CMG propio en el JSON S3
- SSCC programados PCP para parques eólicos (EPO, EPF)
- Factor ERNC: la API gen-real devuelve `factor_ernc` y `valor_ernc` — útil para reporte de aporte ERNC

---

## 14. Notas Técnicas Importantes

### Convenciones heredadas de CTM (mantener consistencia)
- **Hora CEN:** convención 1–24 → en código `dt.hour + 1`
- **fecha_hora en DB:** string `"YYYY-MM-DD HH:MM:SS"`, hora 0-based
- **Retry exponencial:** `_get_with_retry()` con backoff 10s→20s→40s para todos los endpoints
- **`DISTINCT ON`** en gen. programada para priorizar `CEN_PCP` sobre `MANUAL`
- **`streamlit-autorefresh`** cada 3.600.000 ms para evitar sleep de Streamlit Cloud

### Diferencias respecto a CTM
- Gen. real: parques ERNC NO tienen `llave_opreal` distinta del `central` (no hace falta mapeo extra)
- PCP: las llaves `_EO` y `_FV` son más estables que las térmicas (menos alias)
- Parques solares: gen = 0 en horas nocturnas (no confundir con error de adquisición)
- BESS: `id_central=None` en API → manejar separado o ignorar en v1
- Factor de planta solar: varía fuertemente por estación y hora → normalizar siempre sobre `potencia_maxima`

---

*Documento generado el 2026-06-17. Datos probados en vivo contra APIs CEN.*  
*Autor: Erick Herrera — AES Andes.*
