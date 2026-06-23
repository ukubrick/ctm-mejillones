# Resumen consolidado de endpoints y guía de peticiones de adquisición - Coordinador Eléctrico Nacional

> Consolidado de 4 planes/APIs: **SIP**, **OPERACIONES**, **PLANIFICACION** y **MERCADOS**. Fecha de generación: 2026-06-23.

## 1. Alcance y aclaración sobre “plan”

En las especificaciones no siempre aparece un campo formal llamado **plan** por endpoint. Para consolidar la documentación, se usa **Plan/API** como clasificación principal según el título de cada especificación OpenAPI:

- **SIP**: Sistema de Información Pública.

- **OPERACIONES**: APIs de Servicio de la Gerencia de Operaciones.

- **PLANIFICACION**: APIs de Planificación; `/activos` corresponde a Infotécnica e `/activos-web` a Infotécnica Web.

- **MERCADOS**: APIs de Servicio de Mercados.


La expresión **peticiones de adquisición** se interpreta como peticiones HTTP para **adquirir, consultar, descargar, validar o enviar datos** hacia/desde estas APIs.

## 2. Resumen ejecutivo de los 4 planes

| Plan/API | Título OpenAPI | Versión API | OpenAPI | URL base | Endpoints | Métodos | Tags | Schemas | Descripción |
|---|---|---|---|---|---:|---|---:|---:|---|
| SIP | SIP Sistema de Información Pública | 3.0.0 | 3.0.0 | `https://sipub.api.coordinador.cl` | 95 | GET:95 | 28 | 139 | Aquellas API'S tachadas se encuentran deprecadas por tanto no tiene soporte, sin embargo seguirán en uso, en caso necesario se recomienda utilizar aquellas indicadas como v3 |
| OPERACIONES | OPERACIONES | V1.0.0 | 3.0.3 | `https://operacion.api.coordinador.cl` | 44 | GET:44 | 13 | 308 | Apis de Servicio de la Gerencia de Operaciones |
| PLANIFICACION | PLANIFICACION | 1.0.0 | 3.0.2 | `https://planificacion.api.coordinador.cl` | 295 | GET:295 | 48 | 383 | Apis de Servicio de Planificación, /activos corresponde a Infotecnica y /activos-web a Infotecnica Web |
| MERCADOS | MERCADOS | 1.0.0 | 3.0.2 | `https://mercados.api.coordinador.cl` | 3 | POST:3 | 3 | 21 | Apis de Servicio de Mercados |

**Total consolidado:** 437 endpoints documentados.

## 3. Autenticación consolidada

Los cuatro planes declaran autenticación tipo **API key** mediante parámetro de consulta `user_key`.

| Plan/API | Tipo | Ubicación | Nombre | Descripción declarada |
|---|---|---|---|---|
| SIP | `apiKey` | `query` | `user_key` | Debe ingresar la api key asignada, si no la tiene, solicitela mediante mesa de ayuda, https://sipub.api.coordinador.cl/{backend}/{funcion}?user_key={APIKey} |
| OPERACIONES | `apiKey` | `query` | `user_key` | Debe ingresar la api key asignada, si no la tiene, regístrese en la plataforma |
| PLANIFICACION | `apiKey` | `query` | `user_key` | Debe ingresar la api key asignada, si no la tiene, regístrese!, https://planificacion.api.coordinador.cl/{backend}/{funcion}?user_key={APIKey} |
| MERCADOS | `apiKey` | `query` | `user_key` | Debe ingresar la api key asignada, si no la tiene, solicitela mediante mesa de ayuda, https://planificacion.api.coordinador.cl/{backend}/{funcion}?user_key={APIKey} |

Patrón general:

```text
?user_key=TU_API_KEY
```

## 4. Cómo realizar peticiones de adquisición

### 4.1. Peticiones GET

Se usan para consultar o descargar datos. Los filtros se envían como parámetros de URL.

```bash
curl -X GET "https://sipub.api.coordinador.cl/generacion-programada-pcp/v4/findByDate?startDate=2026-06-22&endDate=2026-06-22&page=0&limit=100&user_key=TU_API_KEY"
```

### 4.2. Peticiones POST

Aparecen en **MERCADOS** para validar/recepcionar pronósticos. Además de `user_key`, requieren body JSON con `Content-Type: application/json`.

```bash
curl -X POST "https://mercados.api.coordinador.cl/pronosticos/recepcion-pronosticos-cpasada/api/Forecast/v1/validate?user_key=TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "sender_name": "Proveedor Centrales de Pasada",
  "forecast_name": "Centrales de Pasada",
  "forecast_type": "Day-ahead-168 | h, resolución 1 | h",
  "since": "2023-09-24T00:00:00",
  "central_pass_forecast": [
    {
      "pass_center_id": 5,
      "forecast_datetime": "2023-09-24T00:00:00",
      "mtw_value": 1,
      "min_generation": 0
    },
    {
      "pass_center_id": 5,
      "forecast_datetime": "2023-09-24T01:00:00",
      "mtw_value": 1,
      "min_generation": 0
    },
    {
      "pass_center_id": 5,
      "forecast_datetime": "2023-09-24T02:00:00",
      "mtw_value": 1,
      "min_generation": 0
    }
  ]
}'
```

### 4.3. Parámetros comunes

| Parámetro | Uso típico |
|---|---|
| `user_key` | API key asignada. Obligatoria cuando el endpoint requiere autenticación. |
| `startDate`, `endDate` | Rango de fechas en formato habitual `YYYY-MM-DD`. Muy usado en SIP. |
| `date` | Fecha única de consulta. Usado en reportes de Operaciones. |
| `page` | Número de página. Ojo: varios endpoints `v1` parten en `0`; varios `v2` parten en `1`. |
| `limit`, `pageSize` | Tamaño de página o cantidad de registros. |
| `id` | Identificador de recurso, como path o query parameter. |
| `search` | Búsqueda textual general cuando el endpoint lo permite. |
| `ordering` | Ordenamiento por campo permitido. |
| `nombre`, `nemotecnico` | Filtros de activos y maestros técnicos. |
| `bar_transf`, `type` | Filtros específicos de costo marginal real/online en SIP. |

### 4.4. Códigos de respuesta comunes

| Código | Significado práctico |
|---:|---|
| `200` | Consulta, validación o recepción exitosa. |
| `400` | Parámetros o body inválidos. |
| `401` | No se envió API key o el servicio no la aceptó. |
| `403` | API key incorrecta o sin permisos. |
| `404` | Recurso, entidad o tipo de pronóstico no encontrado. |
| `422` | Error de negocio. Aparece en endpoints POST de pronósticos de MERCADOS. |
| `500` | Error interno del servidor. |

## 5. Ejemplos rápidos por plan

### SIP - Generación programada PCP

```bash
curl -X GET "https://sipub.api.coordinador.cl/generacion-programada-pcp/v4/findByDate?startDate=2026-06-22&endDate=2026-06-22&page=0&limit=100&user_key=TU_API_KEY"
```

### OPERACIONES - Reporte generación OpReal

```bash
curl -X GET "https://operacion.api.coordinador.cl/reportes/v3/generation?date=2026-06-22&page=0&user_key=TU_API_KEY"
```

### PLANIFICACION - Centrales Infotécnica

```bash
curl -X GET "https://planificacion.api.coordinador.cl/activos/centrales/v2?search=ANGAMOS&page=1&pageSize=100&user_key=TU_API_KEY"
```

### MERCADOS - Validar pronóstico ERV

```bash
curl -X POST "https://mercados.api.coordinador.cl/pronosticos/recepcion-erv/api/Forecast/v1/validate?user_key=TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "sender_name": "UL",
  "central_name": "PE VALLE DE LOS VIENTOS",
  "forecast_type_name": "Intra-day-12 | h, resolución 1 | h",
  "forecast_name": "ERV Eólica",
  "erv_forecast": [
    {
      "since": "2024-01-01T06:00:00",
      "until": "2024-01-01T07:00:00",
      "exceedance_prob_25": 9.2209,
      "exceedance_prob_50": 9.1296,
      "exceedance_prob_75": 8.7644,
      "speed": 8,
      "direction": 139,
      "celsius_temperature": 32,
      "pressure_bar": 11
    },
    {
      "since": "2024-01-01T07:00:00",
      "until": "2024-01-01T08:00:00",
      "exceedance_prob_25": 18.8876,
      "exceedance_prob_50": 17.8185,
      "exceedance_prob_75": 17.2839,
      "speed": 9,
      "direction": 292,
      "celsius_temperature": 6,
      "pressure_bar": 15
    },
    {
      "since": "2024-01-01T08:00:00",
      "until": "2024-01-01T09:00:00",
      "exceedance_prob_25": 11.6892,
      "exceedance_prob_50": 11.46,
      "exceedance_prob_75": 9.8556,
      "speed": 18,
      "direction": 87,
      "celsius_temperature": 6,
      "pressure_bar": 17
    },
    {
      "since": "2024-01-01T09:00:00",
      "until": "2024-01-01T10:00:00",
      "exceedance_prob_25": 7.9175,
      "exceedance_prob_50": 7.0066,
      "exceedance_prob_75": 6.4461,
      "speed": 28,
      "direction": 290,
      "celsius_temperature": 14,
      "pressure_bar": 11
    },
    {
      "since": "2024-01-01T10:00:00",
      "until": "2024-01-01T11:00:00",
      "exceedance_prob_25": 0.1204,
      "exceedance_prob_50": 0.1056,
      "exceedance_prob_75": 0.1024,
      "speed": 26,
      "direction": 170,
      "celsius_temperature": 17,
      "pressure_bar": 9
    },
    {
      "since": "2024-01-01T11:00:00",
      "until": "2024-01-01T12:00:00",
      "exceedance_prob_25": 3.2893,
      "exceedance_prob_50": 3.1031,
      "exceedance_prob_75": 2.6376,
      "speed": 6,
      "direction": 151,
      "celsius_temperature": 30,
      "pressure_bar": 3
    },
    {
      "since": "2024-01-01T12:00:00",
      "until": "2024-01-01T13:00:00",
      "exceedance_prob_25": 5.0548,
      "exceedance_prob_50": 5.0048,
      "exceedance_prob_75": 4.4543,
      "speed": 14,
      "direction": 219,
      "celsius_temperature": 21,
      "pressure_bar": 3
    },
    {
      "since": "2024-01-01T13:00:00",
      "until": "2024-01-01T14:00:00",
      "exceedance_prob_25": 4.5536,
      "exceedance_prob_50": 4.0657,
      "exceedance_prob_75": 3.9844,
      "speed": 20,
      "direction": 102,
      "celsius_temperature": 10,
      "pressure_bar": 4
    },
    {
      "since": "2024-01-01T14:00:00",
      "until": "2024-01-01T15:00:00",
      "exceedance_prob_25": 3.6502,
      "exceedance_prob_50": 3.2591,
      "exceedance_prob_75": 3.0961,
      "speed": 15,
      "direction": 155,
      "celsius_temperature": 26,
      "pressure_bar": 20
    },
    {
      "since": "2024-01-01T15:00:00",
      "until": "2024-01-01T16:00:00",
      "exceedance_prob_25": 3.0202,
      "exceedance_prob_50": 2.7209,
      "exceedance_prob_75": 2.4216,
      "speed": 28,
      "direction": 180,
      "celsius_temperature": 18,
      "pressure_bar": 7
    },
    {
      "since": "2024-01-01T16:00:00",
      "until": "2024-01-01T17:00:00",
      "exceedance_prob_25": 26.148,
      "exceedance_prob_50": 25.3864,
      "exceedance_prob_75": 24.6248,
      "speed": 6,
      "direction": 138,
      "celsius_temperature": 7,
      "pressure_bar": 11
    },
    {
      "since": "2024-01-01T17:00:00",
      "until": "2024-01-01T18:00:00",
      "exceedance_prob_25": 69.9601,
      "exceedance_prob_50": 67.2693,
      "exceedance_prob_75": 63.2331,
      "speed": 26,
      "direction": 281,
      "celsius_temperature": 20,
      "pressure_bar": 17
    }
  ]
}'
```

## 6. Python base para adquisición GET

```python
import requests
import pandas as pd

API_KEY = "TU_API_KEY"

def consultar_get(base_url, endpoint, params=None, timeout=60):
    params = dict(params or {})
    params["user_key"] = API_KEY

    response = requests.get(
        base_url.rstrip("/") + endpoint,
        params=params,
        timeout=timeout
    )

    if response.status_code in (400, 401, 403, 404, 422):
        raise RuntimeError(f"Error {response.status_code}: {response.text}")

    response.raise_for_status()
    return response.json()

def normalizar_registros(payload):
    # Convenciones observadas:
    # - SIP y varios endpoints: data o content
    # - Planificación v1: content
    # - Planificación v2: result
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data", payload.get("content", payload.get("result", payload)))
        if isinstance(data, dict):
            return [data]
        return data
    return []

payload = consultar_get(
    "https://planificacion.api.coordinador.cl",
    "/activos/centrales/v2",
    params={"search": "ANGAMOS", "page": 1, "pageSize": 100}
)

df = pd.json_normalize(normalizar_registros(payload))
print(df.head())
```

## 7. Python base para adquisición paginada

```python
import requests
import pandas as pd

API_KEY = "TU_API_KEY"

def adquirir_paginas(base_url, endpoint, params=None, first_page=0, page_size=None, max_pages=10000):
    registros = []
    page = first_page
    params_base = dict(params or {})
    params_base["user_key"] = API_KEY

    if page_size is not None:
        # Usar el nombre correcto según endpoint: limit o pageSize.
        params_base.setdefault("limit", page_size)

    while page < first_page + max_pages:
        params_page = dict(params_base)
        params_page["page"] = page

        response = requests.get(base_url.rstrip("/") + endpoint, params=params_page, timeout=60)
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list):
            registros.extend(payload)
            break

        if not isinstance(payload, dict):
            break

        # Convención content
        if "content" in payload:
            lote = payload.get("content") or []
            registros.extend(lote)

            total_pages = payload.get("totalPages")
            if total_pages is not None and page >= int(total_pages) - 1:
                break
            if not lote:
                break

            page += 1
            continue

        # Convención result
        if "result" in payload:
            lote = payload.get("result") or []
            if isinstance(lote, dict):
                lote = [lote]
            registros.extend(lote)

            if not payload.get("next"):
                break
            if not lote:
                break

            page += 1
            continue

        # Convención data
        if "data" in payload:
            lote = payload.get("data") or []
            if isinstance(lote, dict):
                lote = [lote]
            registros.extend(lote)
            if not lote:
                break
            page += 1
            continue

        registros.append(payload)
        break

    return pd.json_normalize(registros)

# Ejemplo SIP con limit
df_sip = adquirir_paginas(
    "https://sipub.api.coordinador.cl",
    "/costo-marginal-online/v4/findByDate",
    params={"startDate": "2026-06-22", "endDate": "2026-06-22", "limit": 100},
    first_page=0
)

# Ejemplo Planificación v2 con pageSize
df_plan = adquirir_paginas(
    "https://planificacion.api.coordinador.cl",
    "/activos/centrales/v2",
    params={"search": "ANGAMOS", "pageSize": 100},
    first_page=1
)
```

## 8. Python base para POST de MERCADOS

```python
import requests

API_KEY = "TU_API_KEY"
BASE_URL = "https://mercados.api.coordinador.cl"

body = {
    "sender_name": "UL",
    "central_name": "PE VALLE DE LOS VIENTOS",
    "forecast_type_name": "Intra-day-12 | h, resolución 1 | h",
    "forecast_name": "ERV Eólica",
    "erv_forecast": [
        {
            "since": "2024-01-01T06:00:00",
            "until": "2024-01-01T07:00:00",
            "exceedance_prob_25": 9.2209,
            "exceedance_prob_50": 9.1296,
            "exceedance_prob_75": 8.7644,
            "speed": 8,
            "direction": 139,
            "celsius_temperature": 32,
            "pressure_bar": 11
        }
    ]
}

response = requests.post(
    BASE_URL + "/pronosticos/recepcion-erv/api/Forecast/v1/validate",
    params={"user_key": API_KEY},
    json=body,
    timeout=60
)

print(response.status_code)
print(response.json())
```

## 9. Endpoints prioritarios para adquisición/consulta de datos

| Plan/API | Subservicio | Tag | Método | Endpoint | ¿Para qué sirve? | Parámetros/body principales | Respuesta 200 |
|---|---|---|---:|---|---|---|---|
| MERCADOS | Recepción/validación de pronósticos | Recepción de Pronósticos Centrales de Pasada | `POST` | `/pronosticos/recepcion-pronosticos-cpasada/api/Forecast/v1/validate` | Recepción de pronósticos para centrales de pasada | Body `ReceptionForecastDto` | `FormatOutputDto` |
| MERCADOS | Recepción/validación de pronósticos | Recepción de Pronósticos Demanda | `POST` | `/pronosticos/recepcion-demanda/api/Forecast/v1/validate` | Recepción de pronósticos para Demanda | Body `DemandForecastDto` | `FormatOutputDto` |
| MERCADOS | Recepción/validación de pronósticos | Recepción de Pronósticos ERV | `POST` | `/pronosticos/recepcion-erv/api/Forecast/v1/validate` | Recepción de pronósticos para ERV | Body `ERVForecastDto` | `FormatOutputDto` |
| OPERACIONES | Gerencia de Operaciones | Conexiones | `GET` | `/conexion/v1/derivacion` | Devuelve una lista de conexiones dado los parámetros de búsqueda. | id, idPropietario, propietarioNombreIn, circuitoNombreIn, nombre, search, ordering, page | `PagedResponseInstalationTapDto` |
| OPERACIONES | Gerencia de Operaciones | Conexiones | `GET` | `/conexion/v1/derivacion/extended` | Retorna una lista de conexiones | id, idPropietario, nemotecnico, nemotecnicoIContains, nombre, nombreIContains, ordering, search, page | `PagedResponseWebConnectionDto` |
| OPERACIONES | Gerencia de Operaciones | Conexiones | `GET` | `/conexion/v1/derivacion/extended/{id}` | Retorna una conexion dado el id | id | `WebConnectionDto` |
| OPERACIONES | Gerencia de Operaciones | Conexiones | `GET` | `/conexion/v1/derivacion/{id}` | Devuelve una conexion dado un Id válido | id | `InstalationTapDto` |
| OPERACIONES | Gerencia de Operaciones | Mantenimiento Mayor | `GET` | `/mantenimiento-mayor/v1` | Devuelve una lista de secciones de tramos dado los parámetros de búsqueda. | id, page | `PagedResponseMajorMaintenanceDocDtoResponse` |
| OPERACIONES | Gerencia de Operaciones | Potencia | `GET` | `/net-power/v1/` | Retorna la potencia neta buscado por id_central | id | `NetPowerDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `GET` | `/proyectos/v1` | Retorna una lista de proyectos | id, nombre, nombreIContains, ordering, search, page | `PagedResponseProjectDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `GET` | `/proyectos/v1/completitud-calidad` | Retorna una lista completitud calidad | page | `PagedResponseCompletenessQualityDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `GET` | `/proyectos/v1/completitud-calidad/empresas` | Retorna una lista proyectos completitud calidad empresas | page | `PagedResponseCompletenessQualityEnterpriseDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `GET` | `/proyectos/v1/completitud-calidad/estudio-pes-anexos` | Retorna una lista proyecyos estudios anexos | page | `PagedResponseCompletenessQualityAnnexDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `GET` | `/proyectos/v1/completitud-calidad/instalaciones` | Retorna una lista proyectos proyectos completitud instalación | page | `PagedResponseCompletenessQualityInstallationDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `GET` | `/proyectos/v1/completitud-calidad/{id}` | Retorna completitud calidad dado el id | id | `CompletenessQualityDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `GET` | `/proyectos/v1/{id}` | Retorna un proyecto dado el id | id | `ProjectDto` |
| OPERACIONES | Gerencia de Operaciones | Reducción | `GET` | `/reduccion/v1/generacion` | Obtener el listado de reducción generacion por el filtrado de parámetros. | id, page | `PagedResponseReductionGenerationDto` |
| OPERACIONES | Gerencia de Operaciones | Reporte | `GET` | `/reportes/v3/generation` | Devuelve una lista de Generación GWh dada la fecha | date, page | `PagedResponseReportGenerationDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `GET` | `/servicios-complementarios/v1` | Obtener lista de Servicios Complementarios dado un rango de fechas y filtrando los elementos que no están especificados como registros eliminados. Si el campo configuracionPanio es null o vacío se pone en ese atributo el valor del campo centralUnidad. Si existen múltiples estados para un mismo registro, sólo se devuelve el último de los estados referente a ese registro ordenados por el campo fechaAccion. | initDate, endDate, page, pageSize | `PagedResponseOpRealComplementaryServiceDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `GET` | `/servicios-complementarios/v1/interruptores-sscc` | Obtener el listado de interruptores-sscc por el filtrado de parámetros. | id, page | `PagedResponseSwitchesSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `GET` | `/servicios-complementarios/v1/panos-sscc` | Obtener el listado de panos_sscc por el filtrado de parámetros. | id, page | `PagedResponsePanosSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `GET` | `/servicios-complementarios/v1/reactores-sscc` | Obtener el listado de reactores_sscc por el filtrado de parámetros. | id, page | `PagedResponseReactorSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `GET` | `/servicios-complementarios/v1/subestacion-sscc` | Obtener el listado de subestacion_sscc por el filtrado de parámetros. | id, page | `PagedResponseSubstationSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `GET` | `/servicios-complementarios/v1/tramos-sscc` | Obtener el listado de tramos-sscc por el filtrado de parámetros. | id, page | `PagedResponseStretchSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `GET` | `/servicios-complementarios/v1/unidades-generadoras-sscc` | Obtener el listado de unidades-generadoras-sscc por el filtrado de parámetros. | id, page | `PagedResponseGeneratingUnitsSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Topología | `GET` | `/topologia/v3/energygen/{infotecnica_id}` | Devuelve una lista de la lista de generación de energía dado el id de infotecnica | infotecnica_id, page | `PagedResponseTopologyKeyDto` |
| OPERACIONES | Gerencia de Operaciones | Topología | `GET` | `/topologia/v3/fuelcons/{infotecnica_id}` | Devuelve una lista de clave de combustible dado el id de Infotecnica | infotecnica_id, page | `PagedResponseTopologyKeyDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `GET` | `/tramos/v1` | Buscar todos los Tramos por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, idPropietario, search, ordering, page | `PagedResponseStretchDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `GET` | `/tramos/v1/tipos` | Buscar todos los Tramos Tipos | page | `PagedResponseStretchTypeDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `GET` | `/tramos/v1/tipos/{id}` | Retorna un solo Tramo Tipo | id | `StretchTypeDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `GET` | `/tramos/v1/trampas-ondas` | Buscar todas las Trampas Ondas por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | `PagedResponseWaveTrapDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `GET` | `/tramos/v1/trampas-ondas/{id}` | Retorna una sola Trampas Ondas | id | `WaveTrapDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `GET` | `/tramos/v1/{id}` | Retorna un solo Tramo | id | `StretchDto` |
| OPERACIONES | Gerencia de Operaciones | Unidades Generadoras | `GET` | `/unidades-generadoras/v1` | Buscar todas las Unidades Generadoras por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, idPropietario, search, ordering, page | `PagedResponseGeneratingUnitDto` |
| OPERACIONES | Gerencia de Operaciones | Unidades Generadoras | `GET` | `/unidades-generadoras/v1/{id}` | Retorna una sola Unidad Generadora | id | `GeneratingUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Api-Project | `GET` | `/activos/proyectos/v2/{id}` | Devuelve una proyecto dado un Id válido | id | `InstalationProjectDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Banco-Condensadores | `GET` | `/activos/banco-condensadores/v1/` | Devuelve una lista de bancos condensadores del sistema Infotécnica Instalaciones, dado los parámetros de búsqueda | id, idPropietario, nombre, search, ordering, page | `PagedResponseCapacitorBankDto` |
| PLANIFICACION | Infotécnica Instalaciones | Banco-Condensadores | `GET` | `/activos/banco-condensadores/v1/{id}` | Devuelve un banco condensador del sistema Infotécnica Instalaciones, dado un id válido | id | `CapacitorBankDto` |
| PLANIFICACION | Infotécnica Instalaciones | Banco-Condensadores | `GET` | `/activos/banco-condensadores/v2/` | Devuelve una lista de bancos condensadores del sistema Infotécnica Instalaciones, dado los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | `PagedResponse2CapacitorBankDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Banco-Condensadores | `GET` | `/activos/banco-condensadores/v2/{id}` | Devuelve un banco condensador del sistema Infotécnica Instalaciones, dado un id válido | id | `CapacitorBankDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Barras | `GET` | `/activos/barras/v1` | Buscar todas las Barras por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | `PagedResponseBarDto` |
| PLANIFICACION | Infotécnica Instalaciones | Barras | `GET` | `/activos/barras/v1/{id}` | Retorna una sola Barra | id | `BarDto` |
| PLANIFICACION | Infotécnica Instalaciones | Barras | `GET` | `/activos/barras/v2` | Buscar todas las Barras por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | `PagedResponse2BarDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Barras | `GET` | `/activos/barras/v2/{id}` | Retorna una sola Barra | id | `BarDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Celdas | `GET` | `/activos/celdas/v1` | Buscar todas las celdas por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, idPropietario, search, ordering, page | `PagedResponseSynchronizerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Celdas | `GET` | `/activos/celdas/v1/{id}` | Retorna una celda | id | `SynchronizerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Celdas | `GET` | `/activos/celdas/v2` | Buscar todas las celdas por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, nombre, id_propietario, search, ordering, page | `PagedResponse2SynchronizerDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Celdas | `GET` | `/activos/celdas/v2/{id}` | Retorna una celda | id | `SynchronizerDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `GET` | `/activos/centrales/v1` | Buscar todas las centrales por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, idPropietario, idCentralTipo, idRegion, nemotecnico, nemotecnicoIContains, search, ordering, page, pageSize | `PagedResponseCentralDto` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `GET` | `/activos/centrales/v1/tipos` | Buscar todos los tipo de centrales por ordenamiento | ordering | `array[TypeCentralDto]` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `GET` | `/activos/centrales/v1/tipos/{id}` | Devuelve una sola entidad tipo de central | id | `TypeCentralDto` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `GET` | `/activos/centrales/v1/{id}` | Retorna una sola central | id | `CentralDto` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `GET` | `/activos/centrales/v2` | Buscar todas las centrales por filtros de búsqueda y ordenamiento | id, nombre, nombre_i_contains, id_propietario, id_central_tipo, id_region, nemotecnico, nemotecnico_i_contains, search, ordering, page, pageSize | `PagedResponse2CentralDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `GET` | `/activos/centrales/v2/tipos` | Buscar todos los tipo de centrales por ordenamiento | ordering | `array[TypeCentralDto]` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `GET` | `/activos/centrales/v2/tipos/{id}` | Devuelve una sola entidad tipo de central | id | `TypeCentralDto` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `GET` | `/activos/centrales/v2/{id}` | Retorna una sola central | id | `CentralDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Circuitos | `GET` | `/activos/circuitos/v1` | Devuelve una lista de circuitos dado los parámetros de búsqueda. | id, nombre, nemotecnico, idPropietario, search, ordering, page | `PagedResponseInstallationCircuitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Circuitos | `GET` | `/activos/circuitos/v1/{id}` | Devuelve un circuito dado un Id válido | id | `InstallationCircuitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Circuitos | `GET` | `/activos/circuitos/v2` | Devuelve una lista de circuitos dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, nombre, nemotecnico, id_propietario, search, ordering, page | `PagedResponse2InstallationCircuitDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Circuitos | `GET` | `/activos/circuitos/v2/{id}` | Devuelve un circuito dado un Id válido | id | `InstallationCircuitDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Combustible | `GET` | `/activos/combustible/v1` | Retorna una lista de combustible del Sistema Infotecnica Instalaciones | ordering, page | `PagedResponseFuelDto` |
| PLANIFICACION | Infotécnica Instalaciones | Combustible | `GET` | `/activos/combustible/v1/{id}` | Retorna un combustible dado el id del Sistema Infotecnica Instalaciones | id | `FuelDto` |
| PLANIFICACION | Infotécnica Instalaciones | Combustible | `GET` | `/activos/combustible/v2` | Retorna una lista de combustible del Sistema Infotecnica Instalaciones. (Se muestra por defecto 10 registros por página). | ordering, page | `PagedResponse2FuelDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Combustible | `GET` | `/activos/combustible/v2/{id}` | Retorna un combustible dado el id del Sistema Infotecnica Instalaciones | id | `FuelDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `GET` | `/activos/condensadores/v1/series` | Devuelve una lista de series de condensadores del sistema Infotecnica Instalaciones de los filtros de búsqueda. | id, idPropietario, nombre, search, ordering, page | `PagedResponseCapacitorsDto` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `GET` | `/activos/condensadores/v1/series/{id}` | Devuelve una serie de condensador del sistema Infotecnica Instalaciones dada la Id.B | id | `CapacitorsDto` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `GET` | `/activos/condensadores/v1/sincronos` | Devuelve una lista de series de condensadores sincronos del sistema Infotecnica Instalaciones de los filtros de búsqueda. | id, idPropietario, nombre, search, ordering, page | `PagedResponseCapacitorsDto` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `GET` | `/activos/condensadores/v1/sincronos/{id}` | Devuelve un condensador síncrono del sistema Infotecnica Instalaciones dado el Id. | id | `CapacitorsDto` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `GET` | `/activos/condensadores/v2/series` | Devuelve una lista de series de condensadores del sistema Infotecnica Instalaciones de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | `PagedResponse2CapacitorsDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `GET` | `/activos/condensadores/v2/series/{id}` | Devuelve una serie de condensador del sistema Infotecnica Instalaciones dada la Id.B | id | `CapacitorsDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `GET` | `/activos/condensadores/v2/sincronos` | Devuelve una lista de series de condensadores sincronos del sistema Infotecnica Instalaciones de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | `PagedResponse2CapacitorsDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `GET` | `/activos/condensadores/v2/sincronos/{id}` | Devuelve un condensador síncrono del sistema Infotecnica Instalaciones dado el Id. | id | `CapacitorsDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Conexiones | `GET` | `/activos/conexiones/v1/derivacion` | Devuelve una lista de conexiones dado los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | `PagedResponseInstalationTapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Conexiones | `GET` | `/activos/conexiones/v1/derivacion/{id}` | Devuelve una conexión dado un Id válido del Sistema Infotécnica Instalaciones | id | `InstalationTapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Conexiones | `GET` | `/activos/conexiones/v2/derivacion` | Devuelve una lista de conexiones dado los parámetros de búsqueda del Sistema Infotecnica Instalaciones. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | `PagedResponse2InstalationTapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Conexiones | `GET` | `/activos/conexiones/v2/derivacion/{id}` | Devuelve una conexión dado un Id válido del Sistema Infotécnica Instalaciones | id | `InstalationTapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Dispositivos | `GET` | `/activos/dispositivos/v1/reconexiones` | Devuelve una lista de dispositivos del sistema Infotécnica Instalaciones dado los parámetros. | id, idPropietario, nombre, search, ordering, page | `PagedResponseDeviceDto` |
| PLANIFICACION | Infotécnica Instalaciones | Dispositivos | `GET` | `/activos/dispositivos/v1/reconexiones/{id}` | Devuelve un dispositivo del sistema Infotécnica Instalaciones dado un Id válido | id | `DeviceDto` |
| PLANIFICACION | Infotécnica Instalaciones | Dispositivos | `GET` | `/activos/dispositivos/v2/reconexiones` | Devuelve una lista de dispositivos del sistema Infotécnica Instalaciones dado los parámetros. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | `PagedResponse2DeviceDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Dispositivos | `GET` | `/activos/dispositivos/v2/reconexiones/{id}` | Devuelve un dispositivo del sistema Infotécnica Instalaciones dado un Id válido | id | `DeviceDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Interruptores | `GET` | `/activos/interruptores/v1` | Buscar todos los Interruptores por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | `PagedResponseSwitchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Interruptores | `GET` | `/activos/interruptores/v1/{id}` | Retorna un solo Interruptor | id | `SwitchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Interruptores | `GET` | `/activos/interruptores/v2` | Buscar todos los Interruptores por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | `PagedResponse2SwitchDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Interruptores | `GET` | `/activos/interruptores/v2/{id}` | Retorna un solo Interruptor | id | `SwitchDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `GET` | `/activos/lineas/v1` | Retorna datos de lineas segun filtros del sistema Infotecnica Instalaciones | id, idPropietario, nombre, nemotecnico, search, ordering, page | `PagedResponseLineDto` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `GET` | `/activos/lineas/v1/estadisticas` | Buscar todas las estadísticas de líneas | Sin parámetros principales o ver detalle | `StatisticsLineDto` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `GET` | `/activos/lineas/v1/{id}` | Devuelve datos de Linea del sistema Infotecnica Instalaciones | id | `LineDto` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `GET` | `/activos/lineas/v2` | Retorna datos de lineas segun filtros del sistema Infotecnica Instalaciones. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nemotecnico, nemotecnico_i_contains, search, ordering, page | `PagedResponse2LineDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `GET` | `/activos/lineas/v2/{id}` | Devuelve datos de Linea del sistema Infotecnica Instalaciones | id | `LineDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Panios | `GET` | `/activos/panos/v1` | Buscar todos los paños por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, idPropietario, search, ordering, page | `PagedResponseWiperDto` |
| PLANIFICACION | Infotécnica Instalaciones | Panios | `GET` | `/activos/panos/v1/{id}` | Retorna un solo paño | id | `WiperDto` |
| PLANIFICACION | Infotécnica Instalaciones | Panios | `GET` | `/activos/panos/v2` | Buscar todos los paños por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, nombre, nombre_i_contains, id_propietario, search, ordering, page | `PagedResponse2WiperDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Panios | `GET` | `/activos/panos/v2/{id}` | Retorna un solo paño | id | `WiperDto` |
| PLANIFICACION | Infotécnica Instalaciones | Potencia Neta | `GET` | `/activos/potencia-neta/v1/` | Retorna la potencia neta buscado por id_central | id | `NetPowerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Potencia Neta | `GET` | `/activos/potencia-neta/v2/` | Retorna la potencia neta buscado por id_central | id | `NetPowerDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Proyectos | `GET` | `/activos/proyectos/v1/` | Devuelve una lista de proyectos dado los parámetros de búsqueda. | id, nombre, search, ordering, page | `PagedResponseInstalationProjectDto` |
| PLANIFICACION | Infotécnica Instalaciones | Proyectos | `GET` | `/activos/proyectos/v1/{id}` | Devuelve una proyecto dado un Id válido | id | `InstalationProjectDto` |
| PLANIFICACION | Infotécnica Instalaciones | Proyectos | `GET` | `/activos/proyectos/v2` | Devuelve una lista de proyectos dado los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, nombre, search, ordering, page | `PagedResponse2InstalationProjectDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Reactores | `GET` | `/activos/reactores/v1` | Buscar todos los Reactores por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | `PagedResponseReactorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Reactores | `GET` | `/activos/reactores/v1/{id}` | Retorna un solo Reactor | id | `ReactorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Reactores | `GET` | `/activos/reactores/v2` | Buscar todos los Reactores por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | `PagedResponse2ReactorDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Reactores | `GET` | `/activos/reactores/v2/{id}` | Retorna un solo Reactor | id | `ReactorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v1/barras` | Devuelve una lista de secciones de barras dado los parámetros de búsqueda. | id, idPropietario, nombre, search, ordering, page | `PagedResponseInstalationSectionBarDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v1/barras/{id}` | Devuelve una sección de barras dado un Id válido | id | `InstalationSectionBarDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v1/conexion` | Buscar todas las conexiones por ordenamiento | ordering, page | `PagedResponseInstalationSectionConnectionDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v1/conexion/{id}` | Devuelve una sección de conexiones dado un Id válido | id | `InstalationSectionConnectionDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v1/tramos` | Devuelve una lista de secciones de tramos dado los parámetros de búsqueda. | id, idPropietario, nombre, nemotecnico, search, ordering, page | `PagedResponseInstalationsSectionStretchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v1/tramos/{id}` | Devuelve una sección de tramos dado un id válido | id | `InstalationsSectionStretchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v2/barras` | Devuelve una lista de secciones de barras dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | `PagedResponse2InstalationSectionBarDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v2/barras/{id}` | Devuelve una sección de barras dado un Id válido | id | `InstalationSectionBarDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v2/conexion` | Buscar todas las conexiones por ordenamiento. (Se muestra por defecto 10 registros por página). | ordering, page | `PagedResponse2InstalationSectionConnectionDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v2/conexion/{id}` | Devuelve una sección de conexiones dado un Id válido | id | `InstalationSectionConnectionDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v2/tramos` | Devuelve una lista de secciones de tramos dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nemotecnico, search, ordering, page | `PagedResponse2InstalationsSectionStretchDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `GET` | `/activos/secciones/v2/tramos/{id}` | Devuelve una sección de tramos dado un id válido | id | `InstalationsSectionStretchDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `GET` | `/activos/subestaciones/v1` | Devuelve una lista de subestaciónes dado los parámetros de búsqueda. | id, idPropietario, nombre, nemotecnico, search, ordering, page | `PagedResponseInstalationSubstationDto` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `GET` | `/activos/subestaciones/v1/elementos-totales` | Devuelve el total de elementos de subestación | Sin parámetros principales o ver detalle | `TotalElementDto` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `GET` | `/activos/subestaciones/v1/{id}` | Devuelve un subestación dado un Id válido | id | `InstalationSubstationDto` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `GET` | `/activos/subestaciones/v1/{id}/elementos` | Devuelve el total de elementos dado Id de subestación | id, page | `TotalDataElementDto` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `GET` | `/activos/subestaciones/v2` | Devuelve una lista de subestaciónes dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nemotecnico, search, ordering, page | `PagedResponse2InstalationSubstationDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `GET` | `/activos/subestaciones/v2/{id}` | Devuelve un subestación dado un Id válido | id | `InstalationSubstationDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v1` | Buscar todos los Tramos por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, idPropietario, search, ordering, page | `PagedResponseStretchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v1/tipos` | Buscar todos los Tramos Tipos | page | `PagedResponseStretchTypeDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v1/tipos/{id}` | Retorna un solo Tramo Tipo | id | `StretchTypeDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v1/trampas-ondas` | Buscar todas las Trampas Ondas por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | `PagedResponseWaveTrapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v1/trampas-ondas/{id}` | Retorna una sola Trampa Onda | id | `WaveTrapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v1/{id}` | Retorna un solo Tramo | id | `StretchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v2` | Buscar todos los Tramos por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, id_propietario, search, ordering, page | `PagedResponse2StretchDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v2/tipos` | Buscar todos los Tramos Tipos.Se muestra por defecto 10 registros por página | page | `PagedResponse2StretchTypeDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v2/tipos/{id}` | Retorna un solo Tramo Tipo | id | `StretchTypeDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v2/trampas-ondas` | Buscar todas las Trampas Ondas por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | `PagedResponse2WaveTrapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v2/trampas-ondas/{id}` | Retorna una sola Trampa Onda | id | `WaveTrapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `GET` | `/activos/tramos/v2/{id}` | Retorna un solo Tramo | id | `StretchDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/2d` | Devuelve una lista de transformadores 2d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones | id, idPropietario, nombre, search, ordering, page | `PagedResponseTransformer2DDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/2d/{id}` | Devuelve un transformador 2d dado un Id válido del Sistema Infotecnica Instalaciones | id | `Transformer2DDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/3d` | Devuelve una lista de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | `PagedResponseTransformer3DDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/3d/{id}` | Devuelve un transformador 3d dado un Id válido del Sistema Infotecnica Instalaciones | id | `Transformer3DDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/auxiliares` | Devuelve una lista de transformadores auxiliares dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | `PagedResponseAssistantsTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/auxiliares/{id}` | Devuelve un transformador auxiliar dado un Id válido del Sistema Infotecnica Instalaciones | id | `AssistantsTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/corrientes` | Devuelve una lista de transformadores corrientes dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | `PagedResponseCurrentTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/corrientes/{id}` | Devuelve un transformador corriente dado un Id válido del Sistema Infotecnica Instalaciones | id | `PotentialTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/potenciales` | Devuelve una lista de transformadores potenciales dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | `PagedResponsePotentialTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v1/potenciales/{id}` | Devuelve un transformador potencial dado un Id válido del Sistema Infotecnica Instalaciones | id | `PotentialTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v2/2d` | Devuelve una lista de datos de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, page | `PagedResponseTransformer3DV2Dto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v2/3d` | Devuelve una lista de datos de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, page | `PagedResponseTransformer3DV2Dto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/2d` | Devuelve una lista de transformadores 2d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | `PagedResponse2Transformer2DDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/2d/{id}` | Devuelve un transformador 2d dado un Id válido del Sistema Infotecnica Instalaciones | id | `Transformer2DDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/3d` | Devuelve una lista de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | `PagedResponse2Transformer3DDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/3d/{id}` | Devuelve un transformador 3d dado un Id válido del Sistema Infotecnica Instalaciones | id | `Transformer3DDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/auxiliares` | Devuelve una lista de transformadores auxiliares dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | `PagedResponse2AssistantsTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/auxiliares/{id}` | Devuelve un transformador auxiliar dado un Id válido del Sistema Infotecnica Instalaciones | id | `AssistantsTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/corrientes` | Devuelve una lista de transformadores corrientes dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | `PagedResponse2CurrentTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/corrientes/{id}` | Devuelve un transformador corriente dado un Id válido del Sistema Infotecnica Instalaciones | id | `PotentialTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/potenciales` | Devuelve una lista de transformadores potenciales dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | `PagedResponse2PotentialTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v3/potenciales/{id}` | Devuelve un transformador potencial dado un Id válido del Sistema Infotecnica Instalaciones | id | `PotentialTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v4/2d` | Devuelve una lista de datos de transformadores 2d dados los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, page | `PagedResponse2Transformer2DV2Dto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `GET` | `/activos/transformadores/v4/3d` | Devuelve una lista de datos de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, page | `PagedResponse2Transformer3DV2Dto2` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades Medidas | `GET` | `/activos/unidades-medidas/v1` | Devuelve una lista de Unidades Medidas dado los parámetros de búsqueda del sistema Infotécnica Instalaciones. | page | `PagedResponseMeasurementUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades Medidas | `GET` | `/activos/unidades-medidas/v1/{id}` | Devuelve un registro de Unidades Medidas dado un Id válido del sistema Infotécnica Instalaciones. | id | `MeasurementUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades Medidas | `GET` | `/activos/unidades-medidas/v2` | Devuelve una lista de Unidades Medidas dado los parámetros de búsqueda del sistema Infotécnica Instalaciones. (Se muestra por defecto 10 registros por página). | page | `PagedResponse2MeasurementUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `GET` | `/activos/unidades-generadoras/v1` | Buscar todas las Unidades Generadoras por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, idPropietario, search, ordering, page | `PagedResponseGeneratingUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `GET` | `/activos/unidades-generadoras/v1/pmgd` | Buscar todas las Unidades Generadoras PMGD por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, idPropietario, search, ordering, page | `PagedResponseGeneratingUnitPMGDDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `GET` | `/activos/unidades-generadoras/v1/pmgd/{id}` | Retorna una sola Unidad Generadora PMGD | id | `GeneratingUnitPMGDDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `GET` | `/activos/unidades-generadoras/v1/{id}` | Retorna una sola Unidad Generadora | id | `GeneratingUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `GET` | `/activos/unidades-generadoras/v2` | Buscar todas las Unidades Generadoras por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, id_propietario, search, ordering, page | `PagedResponse2GeneratingUnitDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `GET` | `/activos/unidades-generadoras/v2/pmgd` | Buscar todas las Unidades Generadoras PMGD por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, id_propietario, search, ordering, page | `PagedResponse2GeneratingUnitPMGDDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `GET` | `/activos/unidades-generadoras/v2/pmgd/{id}` | Retorna una sola Unidad Generadora PMGD | id | `GeneratingUnitPMGDDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `GET` | `/activos/unidades-generadoras/v2/{id}` | Retorna una sola Unidad Generadora | id | `GeneratingUnitDto` |
| PLANIFICACION | Infotécnica Web | Centrales | `GET` | `/activos-web/centrales/v1/estadisticas` | Buscar todas las estadísticas de centrales por filtros de búsqueda | Sin parámetros principales o ver detalle | `StatisticsCentralsDto` |
| PLANIFICACION | Infotécnica Web | Centrales | `GET` | `/activos-web/centrales/v1/extendida` | Buscar todas las centrales extendidas por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, search, ordering, page | `PagedResponseCentralExtendedDto` |
| PLANIFICACION | Infotécnica Web | Centrales | `GET` | `/activos-web/centrales/v1/extendida/{id}` | Retorna una sola central extendida | id | `CentralExtendedDto` |
| PLANIFICACION | Infotécnica Web | Centrales | `GET` | `/activos-web/centrales/v1/puntos` | Buscar todos los puntos de centrales | Sin parámetros principales o ver detalle | `array[PointsCentralsDto]` |
| PLANIFICACION | Infotécnica Web | Centrales | `GET` | `/activos-web/centrales/v2/estadisticas` | Buscar todas las estadísticas de centrales por filtros de búsqueda | Sin parámetros principales o ver detalle | `StatisticsCentralsDto2` |
| PLANIFICACION | Infotécnica Web | Centrales | `GET` | `/activos-web/centrales/v2/extendida` | Buscar todas las centrales extendidas por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, search, ordering, page | `PagedResponse2CentralExtendedDto2` |
| PLANIFICACION | Infotécnica Web | Centrales | `GET` | `/activos-web/centrales/v2/extendida/{id}` | Retorna una sola central extendida | id | `CentralExtendedDto2` |
| PLANIFICACION | Infotécnica Web | Centrales | `GET` | `/activos-web/centrales/v2/puntos` | Buscar todos los puntos de centrales | Sin parámetros principales o ver detalle | `array[PointsCentralsDto]` |
| PLANIFICACION | Infotécnica Web | Conexiones | `GET` | `/activos-web/conexiones/v1/derivacion/extended` | Retorna una lista de conexiones | id, idPropietario, nemotecnico, nemotecnicoIContains, nombre, nombreIContains, ordering, search, page | `PagedResponseWebConnectionDto` |
| PLANIFICACION | Infotécnica Web | Conexiones | `GET` | `/activos-web/conexiones/v1/derivacion/extended/{id}` | Retorna una conexion dado el id | id | `WebConnectionDto` |
| PLANIFICACION | Infotécnica Web | Conexiones | `GET` | `/activos-web/conexiones/v2/derivacion/extended` | Devuelve una lista de conexiones del sistema Infotécnica Web, dado los parámetros de búsqueda. | id, id_propietario, nemotecnico, nemotecnico_i_contains, nombre, nombre_i_contains, ordering, search, page | `PagedResponse2WebConnectionDto2` |
| PLANIFICACION | Infotécnica Web | Conexiones | `GET` | `/activos-web/conexiones/v2/derivacion/extended/{id}` | Devuelve una conexion del sistema Infotécnica Web, dado un Id válido | id | `WebConnectionDto2` |
| PLANIFICACION | Infotécnica Web | Lineas | `GET` | `/activos-web/lineas/v1/estadisticas` | Buscar todas las estadísticas de líneas | Sin parámetros principales o ver detalle | `StatisticsLineDto` |
| PLANIFICACION | Infotécnica Web | Lineas | `GET` | `/activos-web/lineas/v2/estadisticas` | Buscar todas las estadísticas de líneas | Sin parámetros principales o ver detalle | `StatisticsLineDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v1` | Devuelve una lista de proyectos a partir de los filtros de búsqueda | id, nombre, nombreIContains, ordering, search, page | `PagedResponseProjectDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v1/completitud-calidad` | Retorna una lista completitud calidad a partir de los filtros de búsqueda | page | `PagedResponseCompletenessQualityDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v1/completitud-calidad/empresas` | Retorna una lista proyectos completitud calidad empresas a partir de los filtros de búsqueda | page | `PagedResponseCompletenessQualityEnterpriseDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v1/completitud-calidad/estudio-pes-anexos` | Devuelve una lista proyectos estudios anexos para los filtros de búsqueda. | page | `PagedResponseCompletenessQualityAnnexDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v1/completitud-calidad/instalaciones` | Devuelve una lista de proyectos completitud instalación para los filtros de búsqueda. | page | `PagedResponseCompletenessQualityInstallationDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v1/completitud-calidad/{id}` | Retorna completitud calidad dado el id | id | `CompletenessQualityDetailDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v1/{id}` | Retorna un proyecto dado el id | id | `ProjectDetailDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v2` | Devuelve una lista de proyectos a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, ordering, search, page | `PagedResponse2ProjectDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v2/completitud-calidad` | Retorna una lista completitud calidad a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | page | `PagedResponse2CompletenessQualityDto3` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v2/completitud-calidad/empresas` | Retorna una lista proyectos completitud calidad empresas a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | page | `PagedResponse2CompletenessQualityEnterpriseDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v2/completitud-calidad/estudio-pes-anexos` | Devuelve una lista proyectos estudios anexos para los filtros de búsqueda.Se muestra por defecto 10 registros por página | page | `PagedResponse2CompletenessQualityAnnexDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v2/completitud-calidad/instalaciones` | Devuelve una lista de proyectos completitud instalación para los filtros de búsqueda.Se muestra por defecto 10 registros por página | page | `PagedResponse2CompletenessQualityInstallationDto4` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v2/completitud-calidad/{id}` | Retorna completitud calidad dado el id | id | `CompletenessQualityDetailDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos | `GET` | `/activos-web/proyectos/v2/{id}` | Retorna un proyecto dado el id | id | `ProjectDetailDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos Instalaciones | `GET` | `/activos-web/proyectos-instalaciones/v1` | Devuelve una lista de proyectos instalaciones del sistema Infotécnica Web, dado los parámetros de búsqueda. | id, page | `PagedResponseInstallationProjectDto` |
| PLANIFICACION | Infotécnica Web | Proyectos Instalaciones | `GET` | `/activos-web/proyectos-instalaciones/v1/{id}` | Devuelve un proyecto instalacion del sistema Infotécnica Web, dado un Id válido | id | `InstallationProjectDto` |
| PLANIFICACION | Infotécnica Web | Proyectos Instalaciones | `GET` | `/activos-web/proyectos-instalaciones/v2` | Devuelve una lista de proyectos instalaciones del sistema Infotécnica Web, dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, page | `PagedResponse2InstallationProjectDtoV2` |
| PLANIFICACION | Infotécnica Web | Proyectos Instalaciones | `GET` | `/activos-web/proyectos-instalaciones/v2/{id}` | Devuelve un proyecto instalacion del sistema Infotécnica Web, dado un Id válido | id | `InstallationProjectDtoV2` |
| PLANIFICACION | Infotécnica Web | Substation | `GET` | `/activos-web/sub-estaciones/v1/estadisticas` | Devuelve reporte de subestaciones por region, empresa y elementos ssee | Sin parámetros principales o ver detalle | `SubstationStaticDto` |
| PLANIFICACION | Infotécnica Web | Substation | `GET` | `/activos-web/sub-estaciones/v1/extendida` | Devuelve una lista de subestaciones dado los parameters de búsqueda. | id, nemotecnico, nemotecnicoIContains, idPropietario, nombre, nombreIContains, search, ordering, page | `PagedResponseWebSubstationDto` |
| PLANIFICACION | Infotécnica Web | Substation | `GET` | `/activos-web/sub-estaciones/v2/estadisticas` | Devuelve reporte de subestaciones por region, empresa y elementos ssee | Sin parámetros principales o ver detalle | `SubstationStaticDtoV2` |
| PLANIFICACION | Infotécnica Web | Substation | `GET` | `/activos-web/sub-estaciones/v2/extendida` | Devuelve una lista de subestaciones dado los parámetros  de búsqueda. (Se muestra por defecto 10 registros por página). | id, nemotecnico, nemotecnico_i_contains, id_propietario, nombre, nombre_i_contains, search, ordering, page | `PagedResponse2WebSubstationDtoV2` |
| PLANIFICACION | Infotécnica Web | Tramos | `GET` | `/activos-web/tramos/v1/extended` | Devuelve una lista de secciones dado los parámetros de búsqueda. | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, ordering, search, page | `PagedResponseWebSectionDto` |
| PLANIFICACION | Infotécnica Web | Tramos | `GET` | `/activos-web/tramos/v1/extended/{id}` | Retorna una seccion tramo dado el id | id | `WebSectionDto` |
| PLANIFICACION | Infotécnica Web | Tramos | `GET` | `/activos-web/tramos/v2/extended` | Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, ordering, search, page | `PagedResponse2WebSectionDto2` |
| PLANIFICACION | Infotécnica Web | Tramos | `GET` | `/activos-web/tramos/v2/extended/{id}` | Devuelve una sección del sistema Infotécnica Web dado el id | id | `WebSectionDto2` |
| SIP | Sistema de Información Pública | Capacidad | `GET` | `/capacidad-instalada/v4/findByDate` | Corresponde al concepto capacidad instalada que es la capacidad disponible para el SEN de cada central eléctrica expresada por su potencia máxima. Al sumar estas potencias se obtiene la capacidad instalada total del SEN que se actualiza cada mes, del area de negocio Ejecución Estratégica | page, limit | `CapacidadInstaladaResponse` |
| SIP | Sistema de Información Pública | Cargos Distribución | `GET` | `/cargos-distribucion-ar/v4/findByDate` | Corresponde al concepto cargos distribucion ar que son cargos aplicables a todas las tarifas, incluido en el precio de energía a nivel generación – transmisión, y calculados semestralmente en los procesos de cálculo de los precios de nudos promedio. En este caso AR significa “Ajuste o Recargo”, TD significa “Transferencias entre distribuidoras” y CDRGL significa “ Cargo o descuento por reconocimiento de generación local que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `CargosDistribucionARResponse` |
| SIP | Sistema de Información Pública | Cargos Distribución | `GET` | `/cargos-distribucion-etr/v4/findByDate` | Corresponde al concepto cargos de distribucion etr que es un cargo incluido en la estructura tarifaria mediante el Valor Agregado de Distribución (V.A.D.), y calculado semestralmente en los procesos de cálculo de los precios de nudos promedio, aplicable a todos los clientes regulados e incluido en el cargo de potencia de las tarifas eléctricas. En este cado ETR significa “Equidad Tarifaria Residencial que se actualiza mensualmente, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `CargosDistribucionETRResponse` |
| SIP | Sistema de Información Pública | Centrales | `GET` | `/centrales/v4/findByDate` | Devuelve una lista de todas las entradas de centrales, una central generadora es una instalación diseñada para producir energía eléctrica a gran escala que se actualiza cada dia o mes, del area de negocio Gestión de Acceso Abierto y Conexiones | page, limit | `CentralesResponse` |
| SIP | Sistema de Información Pública | Combustibles | `GET` | `/costo-combustible/v3/findAll` | Son los costos declarados por los Coordinados por día en un mes de los combustibles utilizados para la generación eléctrica del SEN (carbón, gas natural, diésel, otros). Información actualizada de forma diaria. | startDate, endDate, page | `ResponseCostoCombustibles` |
| SIP | Sistema de Información Pública | Combustibles | `GET` | `/stock-combustible/v4/findByDate` | Corresponde al concepto stock combustible, disponibilidad de los diferentes tipos de combustible para las empresas generadoras del Sistema Eléctrico Nacional. La disponibilidad se expresa en función a los tipos de combustibles existentes utilizados para la generación eléctrica del SEN que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `StockCombustibleResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `GET` | `/cmg-programado-pcp/v4/findByDate` | Corresponde al concepto costo marginal programado pcp, Refleja el costo proyectado para un conjunto de barras del SEN para el día siguiente, de suministrar un kilowatt hora (kWh) adicional al sistema eléctrico para una hora determinada, expresado en USD/MWH que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `CMGProgramadoPCPResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `GET` | `/cmg-programado-pid/v4/findByDate` | Corresponde al concepto costo marginal programado pid que Refleja el costo proyectado para un conjunto de barras del SEN para el día siguiente, de suministrar un kilowatt hora (kWh) adicional al sistema eléctrico para una hora determinada, expresado en USD/MWH, ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `CMGProgramadoPIDResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `GET` | `/costo-marginal-online/v4/findByDate` | Corresponde al concepto costo marginal en linea que es el costo de producir una unidad adicional de energía en el sistema para abastecer la demanda, para eso se necesita elegir la central que tiene el precio más alto, esta revisión del abastecimiento se da cada 15 minutos. que se actualiza cada 15 minutos, del area de negocio Gestión de Mercado | startDate, endDate, page, limit, bar_transf | `CMGOnlineResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `GET` | `/costo-marginal-programado/v3/findAll` | Refleja el costo proyectado para un conjunto de barras del SEN para el día siguiente, de suministrar un kilo watt hora (kWh) adicional al sistema eléctrico para una hora determinada, expresado en USD/MWH. | endDate, startDate, page | `PagedResponseScheduleMarginalCostDTO` |
| SIP | Sistema de Información Pública | Costo Marginal | `GET` | `/costo-marginal-programado/v4/findAllHourly` | Refleja el costo proyectado por hora para cada barra del SEN en el día indicado. | date | `HourlyDataResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `GET` | `/costo-marginal-proyectado/v3/findAll` | Refleja el costo proyectado para un conjunto de barras del SEN para el día siguiente, de suministrar un kilo watt hora (kWh) adicional al sistema eléctrico para una hora determinada, expresado en USD/MWH. Información actualizada de forma diaria (4 am.) | starDate, endDate, page | `PagedResponseProjectedMarginalCostDto` |
| SIP | Sistema de Información Pública | Costo Marginal | `GET` | `/costo-marginal-proyectado/v4/findByDate` | Costo Marginal proyectado para los distintos escenarios evaluados en el Informe de Expansión de la Transmisión para un periodo de 20 años | anio_carga, anio, page, limit | `PagedResponseProjectedMarginalCostDtoV4` |
| SIP | Sistema de Información Pública | Costo Marginal | `GET` | `/costo-marginal-real/v4/findByDate` | Corresponde al concepto costo marginal real, el Costo Marginal Real corresponde al valor expresado en USD/MWh, obtenido a partir del Costo Marginal en Línea. Se determina una vez que se han resuelto las observaciones recibidas por el Coordinador. Este costo es el que se utiliza, luego de su conversión a pesos chilenos, para la valorización de la energía en el Balance de Transferencias. que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit, type, bar_transf | `CMGRealResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `GET` | `/costos-marginales-online-8b/v4/findAll` | Devuelve los registros de las últimas 24 horas, tomando los valores de las horas en punto (con los minutos en cero), de costo marginal online para las 8 barras 'Tarapaca 220 KV', 'Crucero 220 KV', 'Atacama 220 KV', 'Cardones 220 KV', 'P.Azucar 220 KV', 'Quillota 220 KV', 'Charrua 220 KV', 'P.Montt 220 KV'. Los resultados son ordenados de forma ascendente por fecha y hora. | Sin parámetros principales o ver detalle | `ResponseCostoMarginalEnLinea` |
| SIP | Sistema de Información Pública | Cotas de Embalses | `GET` | `/cotas-embalses-reales/v3/findAll` | Declaración horaria, realizada por los coordinados, de las cotas de los embalses que abastecen centrales generadoras conectadas al Sistema Eléctrico Nacional en m.s.n.m por hora. Información actualizada de forma horaria. | startDate, endDate, page | `ResponseCotasEmbalses` |
| SIP | Sistema de Información Pública | Cotas de Embalses | `GET` | `/cotas-niveles-embalses-programado/v3/findAll` | Proyección diaria de las cotas de los embalses que abastecen centrales generadoras conectadas al Sistema Eléctrico Nacional en m.s.n.m por hora. Información actualizada de forma diaria (4 am.). | startDate, endDate, page | `ResponseCotasEmbalsesProgramadas` |
| SIP | Sistema de Información Pública | Demanda | `GET` | `/demanda-neta/v4/findByDate` | Corresponde al concepto demanda neta, Corresponderá al valor de demanda descontando la generación de energías renovables con recursos primarios variables, como la eólica y la solar fotovoltaica y centrales hidráulicas de pasada que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `DemandaNetaResponse` |
| SIP | Sistema de Información Pública | Demanda | `GET` | `/demanda-programada-pcp/v4/findByDate` | Corresponde al concepto demanda programada pcp, Esto corresponde a un proyección del consumo total del SEN en MW y por hora y barra, para el día siguiente que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `DemandaProgramadaResponse` |
| SIP | Sistema de Información Pública | Demanda | `GET` | `/demanda-programada-pid/v4/findByDate` | Corresponde al concepto demanda programada pid, Esto corresponde a un proyección del consumo total del SEN en MW por hora y barra ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `DemandaProgramadaPIDResponse` |
| SIP | Sistema de Información Pública | Demanda | `GET` | `/demanda-proyectada/v3/findAll` | Corresponde a la proyección de energía y demanda máxima del SEN para un periodo u horizonte de 20 años, considerando las instalaciones existentes y nuevos proyectos. Información actualizada de forma anual. | startYear, endYear, page | `PagedResponseProjectedDemandDto` |
| SIP | Sistema de Información Pública | Demanda | `GET` | `/demanda-proyectada/v4/findByDate` | Corresponde a la proyección de energía y demanda máxima del SEN para un periodo u horizonte de 20 años, considerando las instalaciones existentes y nuevos proyectos. Información actualizada de forma anual. | anio_carga, anio, page, limit | `PagedResponseProjectedDemandDtoV4` |
| SIP | Sistema de Información Pública | Demanda | `GET` | `/demanda-real-estimada/v4/findByDate` | Corresponde al concepto demanda real estimada, Demanda Real = Consumo Real = Retiros del sistema (estimación) = Generación Bruta - Consumos propios (estimación) - Perdidas de Trasmisión (estimación) que se actualiza cada mes, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `DemandaRealEstimadaResponse` |
| SIP | Sistema de Información Pública | Embalse | `GET` | `/embalse-programado-pcp/v4/findByDate` | Corresponde al concepto embalse programado pcp que es objeto de acumulación de agua para generación de energía eléctrica (programado) que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `EmbalseProgramadoPCPResponse` |
| SIP | Sistema de Información Pública | Embalse | `GET` | `/embalse-programado-pid/v4/findByDate` | Corresponde al concepto embalse programado pid que es objeto de acumulación de agua para generación de energía eléctrica (programado), ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `EmbalseProgramadoPIDResponse` |
| SIP | Sistema de Información Pública | Embalse | `GET` | `/embalse-real/v3/findByDate` | Corresponde al concepto embalse real que es objeto de acumulacion de agua para generacion de energia electrica (real) que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page | `EmbalseRealResponse` |
| SIP | Sistema de Información Pública | Embalse | `GET` | `/embalse-real/v3/findLast` | Objeto de acumulación de agua para generación de energía eléctrica (real) | Sin parámetros principales o ver detalle | `EmbalseRealLastResponse` |
| SIP | Sistema de Información Pública | Embalse | `GET` | `/embalse-real/v3/findWeekly` | Objeto de acumulación de agua para generación de energía eléctrica (real) | embalse | `EmbalseRealWeeklyResponse` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-actual/v3/getSumGeneration` | Devuelve una lista de valores sumarizados de las horas de generaciones reales entre fechas de inicio y fin | startDate, endDate, technology, page, pageSize | `ResponseGeneracionActual2` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-maxima-mensual/v3/findAll` | Devuelve las horas y dias donde se alcanzó el máximo de las generaciones reales entre fechas de inicio y fin, buscando por Tipo de Tecnología. El resultado devuelto por la búsqueda se encuentra ordenado de manera descendente por fecha y hora. | startDate, endDate, technology, page, pageSize | `PagedResponseMonthlyMaximumActualGeneration` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-programada-pcp/v4/findByDate` | Corresponde al concepto generacion programada pcp, Esto corresponde a una proyección de la generación del SEN en MWH, para el día siguiente que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `GeneracionProgramadaPCPResponse` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-programada-pid/v4/findByDate` | Corresponde al concepto generacion programada pid que corresponde a una proyección de la generación del SEN en MWH, ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `GeneracionProgramadaPIDResponse` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-programada-sum/v3/getSumGeneration` | Devuelve el valor total de la generación programada por fecha y hora, buscando por Fecha de inicio,Fecha Término y por Tipo de Tecnología.El resultado de la búsqueda se encuentra ordenado de manera descendente por fecha y hora. | startDate, endDate, technology, page, pageSize | `PageResponseScheduledGenerationv2` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-programada/v3/findAll` | Devuelve todas las Generaciones Programadas, buscando por Fecha de inicio y Fecha Término, ordenados de manera ascendente por fecha, hora e idCentral. | startDate, endDate, page, pageSize | `PageResponseScheduledGeneration` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-real/v3/findByDate` | Devuelve todas las Generaciones Reales que se encuentren en el rango de fechas indicados (startDate - endDate), ordenados de manera descendente por: idCentral, fecha y hora. | startDate, endDate, page, pageSize | `ResponseGeneracionActual` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-real/v3/getAnnualySum` | OP Real. La Generación Real del Sistema Eléctrico Nacional, corresponde al resultado de la operación en tiempo real del sistema, se presenta desglosada por tipo de tecnología. Al descargar los datos se presenta el detalle horario de producción de las distintas centrales generadoras. | Sin parámetros principales o ver detalle | `GeneracionRealSumResponse` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-real/v3/getDailySum` | OP Real. La Generación Real del Sistema Eléctrico Nacional, corresponde al resultado de la operación en tiempo real del sistema, se presenta desglosada por tipo de tecnología. Al descargar los datos se presenta el detalle horario de producción de las distintas centrales generadoras. | date | `GeneracionRealSumResponse` |
| SIP | Sistema de Información Pública | Generación | `GET` | `/generacion-real/v3/getMonthlySum` | OP Real. La Generación Real del Sistema Eléctrico Nacional, corresponde al resultado de la operación en tiempo real del sistema, se presenta desglosada por tipo de tecnología. Al descargar los datos se presenta el detalle horario de producción de las distintas centrales generadoras. | Sin parámetros principales o ver detalle | `GeneracionRealSumResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `GET` | `/indicador-desempeno-cpf/v4/findByDate` | Corresponde al concepto indicador desenpeño cpf que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `IndicadorDesempenoCPFResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `GET` | `/indicador-desempeno-csf/v4/findByDate` | Corresponde al concepto indicador desenpeño csf que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `IndicadorDesempenoCSFResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `GET` | `/indicador-desempeno-ct/v3/findByDate` | Corresponde al concepto indicador desenpeño ct que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page | `IndicadorDesempenoCTResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `GET` | `/indicador-desempeno-ctf/v3/findByDate` | Corresponde al concepto indicador desenpeño ctf que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page | `IndicadorDesempenoCTFResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `GET` | `/indicador-desempeno-edac/v3/findByDate` | Corresponde al concepto indicador desenpeño edac que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page | `IndicadorDesempenoEDACResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `GET` | `/indicador-desempeno-prs/v3/findByDate` | Corresponde al concepto indicador desenpeño prs que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page | `IndicadorDesempenoPRSResponse` |
| SIP | Sistema de Información Pública | Instrucciones | `GET` | `/instrucciones-operacionales-cmg/v4/findByDate` | Corresponde al concepto instrucciones operacionales cmg, Listado de Instrucciones dadas a los Centros de Control para las Unidades Generadoras según los requerimientos del Sistema Eléctrico Nacional durante la Operación en Tiempo Real, que permiten la evaluación de la correcta operación y la determinación de los factores utilizados para la remuneración de los mismos que se actualiza cada dia, del area de negocio Gestión y Operación del SEN | startDate, endDate, page, limit | `InstruccionesOperacionalesCMGResponse` |
| SIP | Sistema de Información Pública | Instrucciones | `GET` | `/instrucciones-operacionales-sscc/v4/findByDate` | Corresponde al concepto instrucciones operacionales sscc, Listado de Instrucciones dadas a los Centros de Control para instruir a Unidades Generadoras la prestación de SSCC según los requerimientos del Sistema Eléctrico Nacional conforme a la programación de los mismos o la resignación en Tiempo Real que permiten la evaluación determinación de los factores utilizados para la remuneración de los mismos que se actualiza cada dia, del area de negocio Gestión y Operación del SEN | startDate, endDate, page, limit | `InstruccionesOperacionalesSSCCResponse` |
| SIP | Sistema de Información Pública | Líneas | `GET` | `/lineas-transmision/v4/findByDate` | Devuelve una lista de todas las entradas de lineas de transmision que se considera que una línea de transimisión corresponde a un enlace que permite transportar energía eléctrica entre dos extremos, los cuales pueden ser una subestación eléctrica o una central. que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | page, limit | `LineasTransmisionResponse` |
| SIP | Sistema de Información Pública | Oferta Proyectada | `GET` | `/oferta-proyectada/v3/findAll` | Plan de obras de generación detallado por región, para los distintos escenarios evaluados en el Informe de Expansión de la Transmisión. Con un horizonte a 20 años. Información actualizada de forma anual. | startYear, endYear, page | `ResponseOfertaProyectada` |
| SIP | Sistema de Información Pública | Potencia | `GET` | `/potencia-activa-reactiva-unidad/v4/findByDate` | Corresponde al concepto potencia activa reactiva unidad, Potencia Activa es aquella que se disipa o realiza el trabajo útil en el circuito, mientras que la potencia reactiva es la potencia requerida por las corrientes que son necesarias para establecer los campos magnéticos para su correcto funcionamiento en cada unidad del coordinador que se actualiza cada dia, del area de negocio Gestión y Operación del SEN | startDate, endDate, page, limit | `PotenciaActivaReactivaUnidadResponse` |
| SIP | Sistema de Información Pública | Potencia | `GET` | `/potencia-transitada/v4/findByDate` | Corresponde al concepto potencia transitada que son flujos netos de potencia históricos horarios transitados por el sistema de transmisión que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `PotenciaTransitadaResponse` |
| SIP | Sistema de Información Pública | Programas | `GET` | `/programas-mantenimiento-mayor/v4/findByDate` | Corresponde al concepto programa mantenimiento, Programa de mantenimiento, Funcionamiento de la Plataforma Programa Mantenimiento Programado Mayor (PMPM), Se hace alusión a Mantenimiento Mayor a 24 Horas, asociado a desconexiones de líneas, centrales y subestaciones, con tiempos de planificación a 18 meses, y cada programa va cambiando cada 6 meses. Finalmente se realizan informes que van a PLP y Plexo de manera diaria. que se actualiza cada dia, mes o semestre, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `ProgramMantenimientoResponse` |
| SIP | Sistema de Información Pública | Pronósticos | `GET` | `/pronostico-centrales-pasada/v4/findByDate` | Corresponde al concepto pronostico centrales pasada, Pronósticos de generación de energía para centrales hidráulicas de pasada, enviada por los coordinados, que se encuentran conectados al sistema eléctrico nacional. que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `PronosticoCentralesPasadaResponse` |
| SIP | Sistema de Información Pública | Pronósticos | `GET` | `/pronostico-erv/v4/findByDate` | Corresponde al concepto pronostico erv que es el perfil acotado en el tiempo que corresponde a 240 horas en el futuro y ese perfil responde al pronostico de produccion de una planta generadora que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `PronosticoERVResponse` |
| SIP | Sistema de Información Pública | Pronósticos | `GET` | `/pronosticos-demanda-corto-plazo/v4/findByDate` | Corresponde al concepto pronosticos demanda corto plazo que es el consumo de electricidad en promedio horario (MWh/h) estimado para el sistema eléctrico nacional de corto plazo (7 dias) que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `PronosticosDemandaCortoPlazoResponse` |
| SIP | Sistema de Información Pública | Pronósticos | `GET` | `/pronosticos-demanda-mediano-plazo/v4/findByDate` | Corresponde al concepto pronosticos demanda mediano plazo que es el consumo de electricidad en promedio horario (MWh/h) estimado para el sistema eléctrico nacional de mediano plazo (14 dias). que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `PronosticosDemandaMedianoPlazoResponse` |
| SIP | Sistema de Información Pública | SSCC | `GET` | `/servicios-complementarios-programados-pcp/v4/findByDate` | Corresponde al concepto servicios complementarios programados pcp que es la cantidad ofertada diaria en MW de los servicios complementarios programados y su precio por disponibilidad o activación de reserva, expresado en US$/MW para cada Configuración Operativa de propiedad del oferente que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `ServiciosComplementariosProgramadosPCPResponse` |
| SIP | Sistema de Información Pública | SSCC | `GET` | `/servicios-complementarios-programados-pid/v4/findByDate` | Corresponde al concepto servicios complementarios programados pid que es la cantidad ofertada diaria en MW de los servicios complementarios programados y su precio por disponibilidad o activación de reserva, expresado en US$/MW para cada Configuración Operativa de propiedad del oferente, ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | `ServiciosComplementariosProgramadosPIDResponse` |
| SIP | Sistema de Información Pública | Transferencias | `GET` | `/transferencia-economica-nacional/v4/findByDate` | Corresponde al concepto transferencia economica nacional que son pagos que se realizan por el uso de las redes de transmisión eléctrica. Estos pagos son esenciales para gestionar el costo y el mantenimiento de las infraestructuras que permiten la transmisión de electricidad desde los puntos de generación hasta los puntos de consumo que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `TransferenciaEconomicaNacionalResponse` |
| SIP | Sistema de Información Pública | Transferencias | `GET` | `/transferencia-economica-zonal/v4/findByDate` | Corresponde al concepto transferencia economica zonal, Son pagos que se realizan por el uso de las redes de transmisión eléctrica. Estos pagos son esenciales para gestionar el costo y el mantenimiento de las infraestructuras que permiten la transmisión de electricidad desde los puntos de generación hasta los puntos de consumo que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | `TransferenciaEconomicaZonalResponse` |
| SIP | Sistema de Información Pública | Transformadores | `GET` | `/transformadores-2d/v3/findAll` | Corresponde al concepto transformadores 2d, Banco de Transformadores 2D que pueden tomar determinadas configuraciones las cuales son transformador 2D trifásico sin reserva, transformador 2D trifásico con reserva, dos transformadores 2D trifásicos comparten un transformador trifásico de reserva, banco de transformadores 2D monofásicos sin reserva, banco de transformadores 2D monofásicos con reserva y dos bancos de transformadores 2D monofásicos comparten un transformador monofásico de reserva que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | `Transformadores2dResponse` |
| SIP | Sistema de Información Pública | Transformadores | `GET` | `/transformadores-3d/v3/findAll` | Corresponde al concepto transformadores 3d, Para un banco de transformadores 3D se deben considerar los mismos conjuntos de equipos para efectos de creación de registros que se indican para transformadores 3D. Las configuraciones que pueden determinarse son transformador 3D trifásico sin reserva, transformador 3D trifásico con reserva, dos transformadores 3D trifásicos comparten un transformador trifásico de reserva, banco de transformadores 3D monofásicos sin reserva, banco de transformadores 3D monofásicos con reserva y dos bancos de transformadores 3D monofásicos comparten un transformador monofásico de reserva que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | `Transformadores3dResponse` |
| SIP | Sistema de Información Pública | Transformadores | `GET` | `/transformadores-auxiliares/v3/findAll` | Corresponde al concepto transformadores auxiliares, la creación de un transformador de servicios auxiliares es requisito mínimo que este aparezca representado con las siguientes características en los DUF (Diagrama Unilineal Funcional) • Nombre identificatorio e irrepetible para la subestación, respetando la nomenclatura definida en Guía de Nomenclatura y Requisitos Mínimos DUF en su versión más reciente. • Se indica el nivel de tensión de sus devanados, razón de transformación. • Se indica la capacidad de transformación que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | `TransformadoresAuxiliaresResponse` |
| SIP | Sistema de Información Pública | Transformadores | `GET` | `/transformadores-corrientes/v3/findAll` | Corresponde al concepto transformadores corriente, un registro de transformador de corriente representa los transformadores de corriente de las tres fases, por lo que se debe crear un solo registro para estos. Cuando existen transformadores de corriente en serie entonces corresponde la creación de un registro para cada uno de ellos. Por otra parte, los registros de transformadores de corriente ubicados en los neutros de las máquinas eléctricas se interpretan como un sólo equipo en lugar de tres y también corresponde la creación de un registro para estos. Finalmente los transformadores de corriente de fase y de neutro deben respetar lo siguiente • No se debe crear un registro para el TC trifásico1 de las celdas, ya que, este está considerado en el registro de Celdas. Por el contrario, los TC toroidales2 si deben ser registrados en esta Instalación ya sea que estos se ubiquen al interior de la celda o en la entrada/salida de estas. • No se debe crear un registro para transformadores de corriente asociados a reconectadores. • No se debe crear un registro para sensores de corriente que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | `TransformadoresCorrientesResponse` |
| SIP | Sistema de Información Pública | Transformadores | `GET` | `/transformadores-potenciales/v3/findAll` | Corresponde al concepto transformadores potenciales, Se debe crear un registro de transformador de potencial el cual representa los transformadores de potencial de las tres fases o de una sola según sea el caso, se deben registrar los transformadores de potencial, ya sean de tipo capacitivo o inducitvo. Se debe respatar que:• Los sensores de tensión presentes en celdas y/o reconectadores no son creados en la BDIT (Base de Dato de InfoTecnica).• Los transformadores de potencial de paños al interior de celdas NO deben ser creados.• Los transformadores de potencial de barras al interior de celdas SI deben ser creados. que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | `TransformadoresPotencialesResponse` |
| SIP | Sistema de Información Pública | Transformadores | `GET` | `/transformadores-zigzag/v3/findAll` | Corresponde al concepto transformadores zigzag, Para realizar la creación de un transformador Zig Zag es requisito mínimo que éste aparezca representadocon las siguientes características en los DUF (Diagrama Unilineal Funcional):• Nombre identificatorio e irrepetible para la subestación, respetando la nomenclatura definida en guía de Nomenclatura y Requisitos Mínimos DUF en su versión más reciente.• Se indica el nivel de tensión del transformador.• Se indica la capacidad de transformación que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | `TransformadoresZigzagResponse` |
| SIP | Sistema de Información Pública | Unidades | `GET` | `/unidades-generadoras/v4/findByDate` | Corresponde al concepto unidades generadoras, Información técnica de las instalaciones en operación del SEN. En este caso unidades generadoras de las centrales que se actualiza cada dia o mes, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page, limit | `UnidadesGeneradorasResponse` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/contratos_de_suministro_vigentes/` | Contratos de suministro vigentes. Para obtener información de las empresas a partir de los IDs de infotécnica, referirse al endpoint `infotecnica/empresas`. **Fuente:** Datos cargados manualmente en el sistema por el Departamento de Transferencias Económicas **Por defecto:** Entrega 20 datos por página **Campos** * `suministrador_mnemotecnico`: Mnemotécnico de la empresa suministradora * `cliente_mnemotecnico`: Mnemotécnico de la empresa cliente * `fecha_suscripcion`: Fecha de suscripción contrato * `fecha_inicio`: Fecha de inicio vigencia contrato * `fecha_termino`: Fecha de término vigencia contrato * `puntos_de_suministro`: Nombres de las barras * `puntos_de_retiro`: Nombres de las barras * `potencia_conectada`: Valor potencia conectada en MW * `año`: - * `energia_contratada`: Valor energía contratada en MWh/año * `potencia_contratada`: Valor potencia contratada en MW * `potencia_contratada_horapunta`: Valor potencia contratada en MW * `potencia_contratada_no_horapunta`: Valor potencia contratada en MW * `nombre_distribuidora`: En caso de que el contrato sea de tipo LD, el nombre distribuidora indica la red a la que se conecta el cliente. * `tipo`: \| L: Cliente Libre R: Cliente Regulado C: Entre Generadores LD: Distribución con Clientes Libres * `afecto_obligacion_ernc`: * `enlace`: Link a declaración jurada * `fecha_suscripcion_renovacion`: Fecha suscripción de la última renovación * `fecha_inicio_renovacion`: Fecha de inicio vigencia de la última renovación * `fecha_termino_renovacion`: Fecha de término vigencia de la última renovación | limit | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/contratos_de_suministro_vigentes/slices/` | Stock de Combustibles Disponibles para Generación - Real. **Por defecto:** Entrega todos los valores de suministradores disponibles para ser consultadas. **Campos** * `suministrador_mnemotecnico`: Mnemotécnico del suministrador. | limit | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/costo_marginal_programado/` | Costo marginal programado por llave. Para hacer cruces de datos entre las llaves de OpReal y el mnemotécnico de la barra, referirse al endpoint `costo_marginal_llaves`. **Fuente:** Datos extraídos de OpReal. **Por defecto:** Entrega 20 datos por página **Campos** * `llave_id`: ID de la llave en OpReal * `fecha`: Fecha de los costos * `hora`: Hora indexada de los costos * `costo`: Costo en USD | limit, fecha | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/costo_marginal_programado/slices/` | Costo marginal programado por llave. **Por defecto:** Entrega todos los valores de fechas disponibles para ser consultadas. **Campos** * `fecha`: Fecha. | limit | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/costos_marginales_reales/` | Costos marginales reales. Para obtener información de las barras a partir de los IDs de infotécnica, referirse al endpoint `infotecnica/barras`. **Fuente:** Datos cargados manualmente en el sistema por el Departamento de Transferencias Económicas. **Por defecto:** Entrega 20 datos por página **Campos** * `fecha`: Fecha. * `hora`: Hora indexada. * `costo_en_dolares`: Valor en USD/MWh * `costo_en_pesos`: Valor en CLP/KWh * `barra`: ID de la barra en infotécnica. * `barra_referencia`: ID de la barra de referencia en infotécnica. | limit, fecha | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/demanda_sistema_real/` | Demanda real del sistema. Corresponde a la: * Generación Real del sistema horaria, obtenida de OpReal, para fechas anteriores a los últimos 2 días. * Generación Online horaria, obtenida de SCADA, para los últimos 2 días. **Fuente:** Datos extraídos de OpReal y SCADA. **Por defecto:** Entrega 20 datos por página **Campos** * `fecha`: Fecha. * `hora`: Hora indexada. * `demanda`: Demanda en MWh. | limit | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/demanda_sistema_real/slices/` | Demanda real sistémica. **Por defecto:** Entrega todos los valores de fechas disponibles para ser consultadas. **Campos** * `fecha`: Fecha. | limit | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/generacion_programada/` | Generación programada por llave. Para hacer cruces de datos referirse a los siguientes endpoints: - `generacion_programada_llaves`: relaciona los mnemotécnicos de las llaves de OpReal con los nombres de las políticas de programación. - `generacion_programada_politicas`: relaciona los nombres de las políticas con sus empresas propietarias. **Fuente:** Datos extraídos de OpReal. **Por defecto:** Entrega 20 datos por página **Campos** * `fecha`: Fecha * `hora`: Hora indexada * `key_id`: ID de la llave en OpReal, * `natural_key`: Mnemotécnico de la llave en OpReal, * `generación`: Generacion programada de la llave en MWh. | limit, fecha | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/generacion_programada/slices/` | Generación programada por llave. **Por defecto:** Entrega todos los valores de fechas disponibles para ser consultadas. **Campos** * `fecha`: Fecha. | limit | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/generacion_programada_llaves/` | Relación entre las llaves OPreal y la política de programación. **Fuente:** Datos extraídos de OpReal. **Por defecto:** Entrega 20 datos por página. **Campos** * `key_id`: ID numérico de la llave en OpReal * `nombre_llave`: Mnemotécnico de la llave en OPReal * `nombre_politica`: Nombre de la política de programación. | limit, key_id | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/generacion_programada_llaves/slices/` | Relación entre las llaves OPreal y la política de programación. **Por defecto:** Entrega todos los valores de llaves disponibles para ser consultadas. **Campos** * `key_id`: ID de la llave. | limit | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/generacion_programada_sistema/` | Generación programada sistémica **Fuente:** Corresponde a la suma de la generación programada de todas las barras. **Por defecto:** Entrega 20 datos por página. **Campos** * `fecha`: Fecha * `hora`: Hora indexada. * `generacion`: Generación en MWh. | limit, fecha | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/generacion_programada_sistema/slices/` | Generación programada sistémica | limit | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/infotecnica/barras/` | Barras. **Fuente:** Datos extraídos de la BD Infotécnica. **Por defecto:** Entrega 20 datos por página. **Campos** * `id_infotecnica`: ID numérico en infotécnica * `propietario`: Mnemotécnico del propietario * `subestacion`: Mnemotécnico de la subestación a la que pertenece * `codigo`: Código de la barra * `descripcion`: Descripción de la barra * `mnemotecnico`: Mnemotécnico en infotécnica * `nombre`: Nombre de la barra * `numero`: Número de la barra | limit, nombre | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/infotecnica/centrales/` | Centrales. **Fuente:** Datos extraídos de la BD Infotécnica. **Por defecto:** Entrega 20 datos por página. **Campos** * `id_infotecnica`: ID numérico en infotécnica * `nombre`: Nombre de la central * `mnemotecnico`: Mnemotécnico en infotécnica * `descripcion`: Descripción * `propietario`: Mnemotécnico del propietario de la central * `codigo`: Código de la central * `numero`: Número de la central | limit, nombre | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/infotecnica/centrales_tipos/` | Tipos de centrales. **Fuente:** Datos extraídos de la BD Infotécnica. **Por defecto:** Entrega 20 datos por página. **Campos** * `id_infotecnica`: ID numérico en infotécnica * `nombre`: Nombre del tipo de central * `mnemotecnico`: Mnemotécnico en infotécnica * `descripcion`: Descripción * `central_set`: Lista con los mnemotécnicos de las centrales que pertenecen al tipo | limit, nombre | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/infotecnica/empresas/` | Empresas. **Fuente:** Datos extraídos de la BD Infotécnica. **Por defecto:** Entrega 20 datos por página. **Campos** * `barra_set`: Lista con los mnemotécnicos de las barras en las que es propietario * `central_set`: Lista con los mnemotécnicos de las centrales en las que es propietario * `linea_set`: Lista con los mnemotécnicos de las líneas en las que es propietario * `subestacion_set`: Lista con los mnemotécnicos de las subestaciones en las que es propietario * `paño_set`: Lista con los mnemotécnicos de los paños en las que es propietario * `rut`: RUT de la empresa * `id_infotecnica`: ID numérico en infotécnica * `giro`: ID numérico del giro a cual pertenece * `grupo`: ID numérico del grupo a cual pertenece * `nombre`: Nombre de la empresa * `descripcion`: Descripción * `mnemotecnico`: Mnemotécnico en infotécnica * `numero`: Número de la empresa | limit, nombre | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/potencia_transitada/` | Potencia transitada por líneas **Fuente:** Datos cargados manualmente en el sistema por el Departamento de Peajes. **Por defecto:** Entrega 20 datos por página, ordenados del más antiguo al más reciente. **Campos** * `tramo_nombre`: Nombre del tramo * `linea_nombre`: Línea del tramo * `ssee`: * `potencia`: Potencia transitada en MW * `intervalos`: Hora indexada * `fecha`: Fecha informada * `correlativo`: Número correlativo (TODO: esclarecer el signficado de este campo) | limit, fecha | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `GET` | `/api/v2/recursos/potencia_transitada/slices/` | Potencia transitada por líneas. | limit | `` |

## 10. Resumen por plan y tag

### SIP — SIP Sistema de Información Pública

| Tag | Endpoints | Métodos |
|---|---:|---|
| api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | 20 | GET:20 |
| Generación | 10 | GET:10 |
| Costo Marginal | 9 | GET:9 |
| Demanda | 6 | GET:6 |
| Indicadores Desenpeño | 6 | GET:6 |
| Transformadores | 6 | GET:6 |
| Embalse | 5 | GET:5 |
| Pronósticos | 4 | GET:4 |
| Cargos Distribución | 2 | GET:2 |
| Combustibles | 2 | GET:2 |
| Cotas de Embalses | 2 | GET:2 |
| Flujo Programado | 2 | GET:2 |
| Instrucciones | 2 | GET:2 |
| Potencia | 2 | GET:2 |
| SSCC | 2 | GET:2 |
| Sistemas Medianos | 2 | GET:2 |
| Transferencias | 2 | GET:2 |
| Capacidad | 1 | GET:1 |
| Centrales | 1 | GET:1 |
| Energía | 1 | GET:1 |
| Indices | 1 | GET:1 |
| Limitaciones | 1 | GET:1 |
| Líneas | 1 | GET:1 |
| Oferta Proyectada | 1 | GET:1 |
| Programas | 1 | GET:1 |
| Punto de Control | 1 | GET:1 |
| Solicitudes | 1 | GET:1 |
| Unidades | 1 | GET:1 |

### OPERACIONES — OPERACIONES

| Tag | Endpoints | Métodos |
|---|---:|---|
| Proyectos | 7 | GET:7 |
| Servicios Complementarios | 7 | GET:7 |
| Topología | 6 | GET:6 |
| Tramos | 6 | GET:6 |
| Conexiones | 4 | GET:4 |
| Reporte | 3 | GET:3 |
| Giros | 2 | GET:2 |
| Nodos | 2 | GET:2 |
| Reducción | 2 | GET:2 |
| Unidades Generadoras | 2 | GET:2 |
| Mantenimiento Mayor | 1 | GET:1 |
| Operativos | 1 | GET:1 |
| Potencia | 1 | GET:1 |

### PLANIFICACION — PLANIFICACION

| Tag | Endpoints | Métodos |
|---|---:|---|
| Transformadores | 24 | GET:24 |
| Proyectos | 17 | GET:17 |
| Centrales | 16 | GET:16 |
| Tramos | 16 | GET:16 |
| Completitud | 12 | GET:12 |
| Secciones | 12 | GET:12 |
| Calidad | 8 | GET:8 |
| Compensadores | 8 | GET:8 |
| Condensadores | 8 | GET:8 |
| Conexiones | 8 | GET:8 |
| Enterprise | 8 | GET:8 |
| Tap | 8 | GET:8 |
| Teleprotecciones | 8 | GET:8 |
| Unidades-Generadoras | 8 | GET:8 |
| Lineas | 7 | GET:7 |
| Subestaciones | 6 | GET:6 |
| Substation | 6 | GET:6 |
| Turbinas | 6 | GET:6 |
| Banco-Condensadores | 4 | GET:4 |
| Barras | 4 | GET:4 |
| Celdas | 4 | GET:4 |
| Circuitos | 4 | GET:4 |
| Combustible | 4 | GET:4 |
| Conceptos | 4 | GET:4 |
| Conductor | 4 | GET:4 |
| Configuraciones | 4 | GET:4 |
| Desconectadores | 4 | GET:4 |
| Dispositivos | 4 | GET:4 |
| Fuentes Energías | 4 | GET:4 |
| Giros | 4 | GET:4 |
| Grupos | 4 | GET:4 |
| Historicos | 4 | GET:4 |
| Intercomunicadores | 4 | GET:4 |
| Interruptores | 4 | GET:4 |
| Medidores | 4 | GET:4 |
| Panios | 4 | GET:4 |
| Pararrayos | 4 | GET:4 |
| Proyectos Instalaciones | 4 | GET:4 |
| Reactores | 4 | GET:4 |
| Retiro-Instalaciones | 4 | GET:4 |
| Sincronizadores | 4 | GET:4 |
| Sistemas-Protecciones | 4 | GET:4 |
| Torre | 4 | GET:4 |
| Unidades Medidas | 3 | GET:3 |
| Empresas | 2 | GET:2 |
| Potencia Neta | 2 | GET:2 |
| Api-Project | 1 | GET:1 |
| Instalaciones | 1 | GET:1 |

### MERCADOS — MERCADOS

| Tag | Endpoints | Métodos |
|---|---:|---|
| Recepción de Pronósticos Centrales de Pasada | 1 | POST:1 |
| Recepción de Pronósticos Demanda | 1 | POST:1 |
| Recepción de Pronósticos ERV | 1 | POST:1 |

## 11. Tabla consolidada de todos los endpoints

| Plan/API | Subservicio | Tag | Versión | Método | Endpoint | Operation ID | Resumen | Descripción disponible | Parámetros principales / Body | Auth | Respuestas | Schema 200 |
|---|---|---|---|---:|---|---|---|---|---|---|---|---|
| MERCADOS | Recepción/validación de pronósticos | Recepción de Pronósticos Centrales de Pasada | `v1` | `POST` | `/pronosticos/recepcion-pronosticos-cpasada/api/Forecast/v1/validate` | `` | Recepción de pronósticos para centrales de pasada | No aparece descripción adicional en la especificación. | Body `ReceptionForecastDto` requerido=True | Sí (global: api-key) | 200, 400, 500 | `FormatOutputDto` |
| MERCADOS | Recepción/validación de pronósticos | Recepción de Pronósticos Demanda | `v1` | `POST` | `/pronosticos/recepcion-demanda/api/Forecast/v1/validate` | `` | Recepción de pronósticos para Demanda | No aparece descripción adicional en la especificación. | Body `DemandForecastDto` requerido=True | Sí (global: api-key) | 200, 400, 404, 422, 500 | `FormatOutputDto` |
| MERCADOS | Recepción/validación de pronósticos | Recepción de Pronósticos ERV | `v1` | `POST` | `/pronosticos/recepcion-erv/api/Forecast/v1/validate` | `` | Recepción de pronósticos para ERV | No aparece descripción adicional en la especificación. | Body `ERVForecastDto` requerido=True | Sí (global: api-key) | 200, 400, 404, 422, 500 | `FormatOutputDto` |
| OPERACIONES | Gerencia de Operaciones | Conexiones | `v1` | `GET` | `/conexion/v1/derivacion` | `getConnectionByFilter` | Devuelve una lista de conexiones a partir de los filtros de búsqueda | Devuelve una lista de conexiones dado los parámetros de búsqueda. | id, idPropietario, propietarioNombreIn, circuitoNombreIn, nombre, search, ordering, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseInstalationTapDto` |
| OPERACIONES | Gerencia de Operaciones | Conexiones | `v1` | `GET` | `/conexion/v1/derivacion/extended` | `getConnectionExtended` | Obtener lista de conexiones | Retorna una lista de conexiones | id, idPropietario, nemotecnico, nemotecnicoIContains, nombre, nombreIContains, ordering, search, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseWebConnectionDto` |
| OPERACIONES | Gerencia de Operaciones | Conexiones | `v1` | `GET` | `/conexion/v1/derivacion/extended/{id}` | `getConnectionExtendedById` | Obtener una conexion dado el id | Retorna una conexion dado el id | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `WebConnectionDto` |
| OPERACIONES | Gerencia de Operaciones | Conexiones | `v1` | `GET` | `/conexion/v1/derivacion/{id}` | `getConnectionById` | Devuelve una conexion dado el Id | Devuelve una conexion dado un Id válido | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `InstalationTapDto` |
| OPERACIONES | Gerencia de Operaciones | Giros | `v1` | `GET` | `/giros/v1` | `getTurns` | Devuelve una lista de giros a partir de los filtros de búsqueda | Devuelve una lista de giros dado los parámetros de búsqueda. | id, nombre, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseCompanyTurnDto` |
| OPERACIONES | Gerencia de Operaciones | Giros | `v1` | `GET` | `/giros/v1/{id}` | `getTurnById` | Devuelve un giro dado el Id | Devuelve un giro dado un Id válido | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `CompanyTurnDto` |
| OPERACIONES | Gerencia de Operaciones | Mantenimiento Mayor | `v1` | `GET` | `/mantenimiento-mayor/v1` | `getMajorMaintenanceByFilter` | Devuelve una lista de secciones de tramos a partir de los filtros de búsqueda | Devuelve una lista de secciones de tramos dado los parámetros de búsqueda. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseMajorMaintenanceDocDtoResponse` |
| OPERACIONES | Gerencia de Operaciones | Nodos | `v4` | `GET` | `/opreal-nodos/v4/getAllByPage` | `getNodeType` | Obtiene una lista de tipos de nodos | Retorna una lista de tipos de nodos | page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseOprealNodeTypeDto` |
| OPERACIONES | Gerencia de Operaciones | Nodos | `v4` | `GET` | `/opreal-nodos/v4/getType` | `getNode` | Obtiene una lista de nodos | Retorna una lista de nodos dado identificador del tipo de nodo y identificador de infotécnica | page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseOprealNodeDto` |
| OPERACIONES | Gerencia de Operaciones | Operativos | `v1` | `GET` | `/operativos/v1/estados` | `findOperativeStates` | Buscar todos los Estados Operativos del sistema Neomante por filtros de búsqueda | Buscar todos los Estados Operativos por filtros de búsqueda | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseStatesDto` |
| OPERACIONES | Gerencia de Operaciones | Potencia | `v1` | `GET` | `/net-power/v1/` | `getNetPower` | Obtener PotenciaNeta | Retorna la potencia neta buscado por id_central | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `NetPowerDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `v1` | `GET` | `/proyectos/v1` | `getProjectFilter` | Obtener lista de proyectos | Retorna una lista de proyectos | id, nombre, nombreIContains, ordering, search, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseProjectDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `v1` | `GET` | `/proyectos/v1/completitud-calidad` | `getCompleteness` | Obtener lista completitud calidad | Retorna una lista completitud calidad | page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessQualityDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `v1` | `GET` | `/proyectos/v1/completitud-calidad/empresas` | `getProjectCompletenessEnterprise` | Obtener lista proyectos completitud calidad empresas | Retorna una lista proyectos completitud calidad empresas | page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessQualityEnterpriseDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `v1` | `GET` | `/proyectos/v1/completitud-calidad/estudio-pes-anexos` | `getProjectAnnexStudy` | Obtener lista proyecyos estudios anexos | Retorna una lista proyecyos estudios anexos | page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessQualityAnnexDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `v1` | `GET` | `/proyectos/v1/completitud-calidad/instalaciones` | `getProjectInstallation` | Obtener lista proyectos completitud instalación | Retorna una lista proyectos proyectos completitud instalación | page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessQualityInstallationDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `v1` | `GET` | `/proyectos/v1/completitud-calidad/{id}` | `getCompletenessId` | Obtener completitud calidad dado el id | Retorna completitud calidad dado el id | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `CompletenessQualityDto` |
| OPERACIONES | Gerencia de Operaciones | Proyectos | `v1` | `GET` | `/proyectos/v1/{id}` | `getProjectById` | Obtener un proyecto dado el id | Retorna un proyecto dado el id | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `ProjectDto` |
| OPERACIONES | Gerencia de Operaciones | Reducción | `v1` | `GET` | `/reduccion/v1/consumo` | `findReductionUsageDtoByFilters` | Obtener reducción consumo del sistema Neomante | Obtener el listado de reducción consumo por el filtrado de parámetros. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseReductionUsageDto` |
| OPERACIONES | Gerencia de Operaciones | Reducción | `v1` | `GET` | `/reduccion/v1/generacion` | `findReductionGenerationDtoByFilters` | Obtener reducción generacion del sistema Neomante | Obtener el listado de reducción generacion por el filtrado de parámetros. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseReductionGenerationDto` |
| OPERACIONES | Gerencia de Operaciones | Reporte | `v3` | `GET` | `/reportes/v3/cne` | `getCneReport` | Obtiene el reporte CNE desde el sistema OpReal | Devuelve el reporte CNE por fecha | date | Sí (global: api-key) | 200, 400, 404, 500 | `ReportDailyCneReportDto` |
| OPERACIONES | Gerencia de Operaciones | Reporte | `v3` | `GET` | `/reportes/v3/deviation` | `getDeviation` | Obtiene el reporte de desviación desde el sistema Opreal | Devuelve la desviación por fecha | date, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseReportDeviationDto` |
| OPERACIONES | Gerencia de Operaciones | Reporte | `v3` | `GET` | `/reportes/v3/generation` | `getGwh` | Obtiene la clasificación de generación desde el sistema OpReal | Devuelve una lista de Generación GWh dada la fecha | date, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseReportGenerationDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `v1` | `GET` | `/servicios-complementarios/v1` | `getComplementaryService` | Obtener lista de Servicios Complementarios del sistema OpReal dado un rango de fechas | Obtener lista de Servicios Complementarios dado un rango de fechas y filtrando los elementos que no están especificados como registros eliminados. Si el campo configuracionPanio es null o vacío se pone en ese atributo el valor del campo centralUnidad. Si existen múltiples estados para un mismo registro, sólo se devuelve el último de los estados referente a ese registro ordenados por el campo fechaAccion. | initDate, endDate, page, pageSize | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseOpRealComplementaryServiceDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `v1` | `GET` | `/servicios-complementarios/v1/interruptores-sscc` | `findSwitchesSsccDtoByFilters` | Obtener interruptores-sscc del sistema Neomante | Obtener el listado de interruptores-sscc por el filtrado de parámetros. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseSwitchesSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `v1` | `GET` | `/servicios-complementarios/v1/panos-sscc` | `findPanosSsccDtoByFilters` | Obtener panos_sscc del sistema Neomante | Obtener el listado de panos_sscc por el filtrado de parámetros. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponsePanosSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `v1` | `GET` | `/servicios-complementarios/v1/reactores-sscc` | `findReactorSsccDtoByFilters` | Obtener reactores_sscc del sistema Neomante | Obtener el listado de reactores_sscc por el filtrado de parámetros. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseReactorSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `v1` | `GET` | `/servicios-complementarios/v1/subestacion-sscc` | `findSubstationSsccDtoByFilters` | Obtener subestacion_sscc del sistema Neomante | Obtener el listado de subestacion_sscc por el filtrado de parámetros. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseSubstationSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `v1` | `GET` | `/servicios-complementarios/v1/tramos-sscc` | `findStretchSsccDtoByFilters` | Obtener tramos-sscc del sistema Neomante | Obtener el listado de tramos-sscc por el filtrado de parámetros. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseStretchSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Servicios Complementarios | `v1` | `GET` | `/servicios-complementarios/v1/unidades-generadoras-sscc` | `findGeneratingUnitsSsccDtoByFilters` | Obtener unidades-generadoras-sscc del sistema Neomante | Obtener el listado de unidades-generadoras-sscc por el filtrado de parámetros. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseGeneratingUnitsSsccDto` |
| OPERACIONES | Gerencia de Operaciones | Topología | `v3` | `GET` | `/topologia/v3/energygen/{infotecnica_id}` | `getEnergyGen` | Obtiene la lista de generación de energía dada la identificación desde el sistema OpReal | Devuelve una lista de la lista de generación de energía dado el id de infotecnica | infotecnica_id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTopologyKeyDto` |
| OPERACIONES | Gerencia de Operaciones | Topología | `v3` | `GET` | `/topologia/v3/fuelcons/{infotecnica_id}` | `getFuelCons` | Obtiene la lista de claves de combustible desde el sistema Opreal | Devuelve una lista de clave de combustible dado el id de Infotecnica | infotecnica_id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTopologyKeyDto` |
| OPERACIONES | Gerencia de Operaciones | Topología | `v3` | `GET` | `/topologia/v3/plantcompany/{infotecnica_id}` | `getPlantCompany` | Obtiene la lista de plantas de empresas desde el sistema OpReal | Devuelve una lista de Plantas de Empresas dado el id de Infotecnica | infotecnica_id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTopologyCompanyDto` |
| OPERACIONES | Gerencia de Operaciones | Topología | `v3` | `GET` | `/topologia/v3/plantowner/{infotecnica_id}` | `getPlantowner` | Obtiene la lista de nodos del propietario desde el sistema OpReal | Devuelve una lista de Nodo de propietario dado el id Infotecnica | infotecnica_id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTopologyNodeDto` |
| OPERACIONES | Gerencia de Operaciones | Topología | `v3` | `GET` | `/topologia/v3/progsen/{infotecnica_id}` | `getProgSen` | Obtenga la lista de claves de programación desde el Sistema Opreal | Devuelve una lista de claves de programación dado el id de Infotecnica | infotecnica_id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTopologyKeyDto` |
| OPERACIONES | Gerencia de Operaciones | Topología | `v3` | `GET` | `/topologia/v3/reportgroup/{infotecnica_id}` | `getReportGroup` | Obtiene el informe de nodos desde el sistema Opreal | Devuelve una lista de Informe de Nodos dado el Id infotécnico | infotecnica_id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTopologyNodeDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `v1` | `GET` | `/tramos/v1` | `getStretchsByFilters` | Buscar todos los Tramos por filtros de búsqueda y ordenamiento | Buscar todos los Tramos por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, idPropietario, search, ordering, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseStretchDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `v1` | `GET` | `/tramos/v1/tipos` | `getStretchTypesByFilters` | Buscar todos los Tramos Tipos | Buscar todos los Tramos Tipos | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseStretchTypeDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `v1` | `GET` | `/tramos/v1/tipos/{id}` | `getStretchTypeById` | Buscar un Tramo Tipo por ID | Retorna un solo Tramo Tipo | id | Sí (global: api-key) | 200, 400, 404, 500 | `StretchTypeDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `v1` | `GET` | `/tramos/v1/trampas-ondas` | `getWaveTrapsByFilters` | Buscar todas las Trampas Ondas por filtros de búsqueda y ordenamiento | Buscar todas las Trampas Ondas por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseWaveTrapDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `v1` | `GET` | `/tramos/v1/trampas-ondas/{id}` | `getWaveTrapById` | Buscar una Trampas Ondas por ID | Retorna una sola Trampas Ondas | id | Sí (global: api-key) | 200, 400, 404, 500 | `WaveTrapDto` |
| OPERACIONES | Gerencia de Operaciones | Tramos | `v1` | `GET` | `/tramos/v1/{id}` | `getStretchById` | Buscar un Tramo por ID | Retorna un solo Tramo | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `StretchDto` |
| OPERACIONES | Gerencia de Operaciones | Unidades Generadoras | `v1` | `GET` | `/unidades-generadoras/v1` | `getGeneratingUnitsByFilters` | Buscar todas las Unidades Generadoras por filtros de búsqueda y ordenamiento | Buscar todas las Unidades Generadoras por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, idPropietario, search, ordering, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseGeneratingUnitDto` |
| OPERACIONES | Gerencia de Operaciones | Unidades Generadoras | `v1` | `GET` | `/unidades-generadoras/v1/{id}` | `getGeneratingUnitById` | Buscar una Unidad Generadora por ID | Retorna una sola Unidad Generadora | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `GeneratingUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Api-Project | `v2` | `GET` | `/activos/proyectos/v2/{id}` | `getProjectById` | Devuelve una proyecto del sistema Infotecnica Instalaciones dado el Id | Devuelve una proyecto dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationProjectDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Banco-Condensadores | `v1` | `GET` | `/activos/banco-condensadores/v1/` | `getCapacitorBankList` | Devuelve una lista de bancos condensadores del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de bancos condensadores del sistema Infotécnica Instalaciones, dado los parámetros de búsqueda | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCapacitorBankDto` |
| PLANIFICACION | Infotécnica Instalaciones | Banco-Condensadores | `v1` | `GET` | `/activos/banco-condensadores/v1/{id}` | `getCapacitorBankById` | Devuelve un banco condensador del sistema Infotécnica Instalaciones dado el id | Devuelve un banco condensador del sistema Infotécnica Instalaciones, dado un id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `CapacitorBankDto` |
| PLANIFICACION | Infotécnica Instalaciones | Banco-Condensadores | `v2` | `GET` | `/activos/banco-condensadores/v2/` | `getCapacitorBankList` | Devuelve una lista de bancos condensadores del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de bancos condensadores del sistema Infotécnica Instalaciones, dado los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CapacitorBankDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Banco-Condensadores | `v2` | `GET` | `/activos/banco-condensadores/v2/{id}` | `getCapacitorBankById` | Devuelve un banco condensador del sistema Infotécnica Instalaciones dado el id | Devuelve un banco condensador del sistema Infotécnica Instalaciones, dado un id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `CapacitorBankDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Barras | `v1` | `GET` | `/activos/barras/v1` | `getBarsByFilters` | Buscar todas las Barras del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todas las Barras por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseBarDto` |
| PLANIFICACION | Infotécnica Instalaciones | Barras | `v1` | `GET` | `/activos/barras/v1/{id}` | `getBarById` | Buscar una Barra del sistema Infotécnica Instalaciones por ID | Retorna una sola Barra | id | Sí (global: api-key) | 200, 400, 404, 500 | `BarDto` |
| PLANIFICACION | Infotécnica Instalaciones | Barras | `v2` | `GET` | `/activos/barras/v2` | `getBarsByFilters_1` | Buscar todas las Barras del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todas las Barras por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2BarDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Barras | `v2` | `GET` | `/activos/barras/v2/{id}` | `getBarById_1` | Buscar una Barra del sistema Infotécnica Instalaciones por ID | Retorna una sola Barra | id | Sí (global: api-key) | 200, 400, 404, 500 | `BarDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Celdas | `v1` | `GET` | `/activos/celdas/v1` | `getCellsByFilters` | Buscar todas las celdas del sistema Infotécnica Instalaciones, por filtros de búsqueda y ordenamiento | Buscar todas las celdas por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, idPropietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseSynchronizerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Celdas | `v1` | `GET` | `/activos/celdas/v1/{id}` | `getCellById_1` | Buscar celda por ID del sistema Infotécnica Instalaciones | Retorna una celda | id | Sí (global: api-key) | 200, 400, 404, 500 | `SynchronizerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Celdas | `v2` | `GET` | `/activos/celdas/v2` | `getCellsByFilters2` | Buscar todas las celdas del sistema Infotécnica Instalaciones, por filtros de búsqueda y ordenamiento | Buscar todas las celdas por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, nombre, id_propietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2SynchronizerDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Celdas | `v2` | `GET` | `/activos/celdas/v2/{id}` | `getCellById` | Buscar celda por ID del sistema Infotécnica Instalaciones | Retorna una celda | id | Sí (global: api-key) | 200, 400, 404, 500 | `SynchronizerDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `v1` | `GET` | `/activos/centrales/v1` | `getAllCentrals` | Buscar todas las centrales del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todas las centrales por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, idPropietario, idCentralTipo, idRegion, nemotecnico, nemotecnicoIContains, search, ordering, page, pageSize | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCentralDto` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `v1` | `GET` | `/activos/centrales/v1/tipos` | `getAllTypesOfCentrals` | Buscar todos los tipos de centrales del sistema Infotécnica Instalaciones por ordenamiento | Buscar todos los tipo de centrales por ordenamiento | ordering | Sí (global: api-key) | 200, 400, 404, 500 | `array[TypeCentralDto]` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `v1` | `GET` | `/activos/centrales/v1/tipos/{id}` | `getTypeCentralById` | Buscar tipo de central del sistema Infotécnica Instalaciones por ID | Devuelve una sola entidad tipo de central | id | Sí (global: api-key) | 200, 400, 404, 500 | `TypeCentralDto` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `v1` | `GET` | `/activos/centrales/v1/{id}` | `getCentralById` | Buscar central del sistema Infotécnica Instalaciones por ID | Retorna una sola central | id | Sí (global: api-key) | 200, 400, 404, 500 | `CentralDto` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `v2` | `GET` | `/activos/centrales/v2` | `getAllCentrals_1` | Buscar todas las centrales del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todas las centrales por filtros de búsqueda y ordenamiento | id, nombre, nombre_i_contains, id_propietario, id_central_tipo, id_region, nemotecnico, nemotecnico_i_contains, search, ordering, page, pageSize | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CentralDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `v2` | `GET` | `/activos/centrales/v2/tipos` | `getAllTypesOfCentrals_1` | Buscar todos los tipos de centrales del sistema Infotécnica Instalaciones por ordenamiento | Buscar todos los tipo de centrales por ordenamiento | ordering | Sí (global: api-key) | 200, 400, 404, 500 | `array[TypeCentralDto]` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `v2` | `GET` | `/activos/centrales/v2/tipos/{id}` | `getTypeCentralById_1` | Buscar tipo de central del sistema Infotécnica Instalaciones por ID | Devuelve una sola entidad tipo de central | id | Sí (global: api-key) | 200, 400, 404, 500 | `TypeCentralDto` |
| PLANIFICACION | Infotécnica Instalaciones | Centrales | `v2` | `GET` | `/activos/centrales/v2/{id}` | `getCentralById_1` | Buscar central del sistema Infotécnica Instalaciones por ID | Retorna una sola central | id | Sí (global: api-key) | 200, 400, 404, 500 | `CentralDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Circuitos | `v1` | `GET` | `/activos/circuitos/v1` | `getCircuitsByFilter` | Devuelve una lista de circuitos del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de circuitos dado los parámetros de búsqueda. | id, nombre, nemotecnico, idPropietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationCircuitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Circuitos | `v1` | `GET` | `/activos/circuitos/v1/{id}` | `getCircuitById` | Devuelve un circuito del sistema Infotecnica Instalaciones, dado el Id | Devuelve un circuito dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationCircuitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Circuitos | `v2` | `GET` | `/activos/circuitos/v2` | `getCircuitsByFilter` | Devuelve una lista de circuitos del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de circuitos dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, nombre, nemotecnico, id_propietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationCircuitDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Circuitos | `v2` | `GET` | `/activos/circuitos/v2/{id}` | `getCircuitById` | Devuelve un circuito del sistema Infotecnica Instalaciones, dado el Id | Devuelve un circuito dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationCircuitDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Combustible | `v1` | `GET` | `/activos/combustible/v1` | `getFuelList` | Obtener lista de combustible del Sistema Infotecnica Instalaciones | Retorna una lista de combustible del Sistema Infotecnica Instalaciones | ordering, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseFuelDto` |
| PLANIFICACION | Infotécnica Instalaciones | Combustible | `v1` | `GET` | `/activos/combustible/v1/{id}` | `getFuelById` | Obtener un combustible dado el id del Sistema Infotecnica Instalaciones | Retorna un combustible dado el id del Sistema Infotecnica Instalaciones | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `FuelDto` |
| PLANIFICACION | Infotécnica Instalaciones | Combustible | `v2` | `GET` | `/activos/combustible/v2` | `getFuelList_1` | Obtener lista de combustible del Sistema Infotecnica Instalaciones | Retorna una lista de combustible del Sistema Infotecnica Instalaciones. (Se muestra por defecto 10 registros por página). | ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2FuelDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Combustible | `v2` | `GET` | `/activos/combustible/v2/{id}` | `getFuelById_1` | Obtener un combustible dado el id del Sistema Infotecnica Instalaciones | Retorna un combustible dado el id del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `FuelDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Compensadores | `v1` | `GET` | `/activos/compensadores/v1/activos` | `getActiveCompensatorByFilter_1` | Devuelve una lista de compensadores activos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de compensadores activos dado los parámetros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationActiveCompensatorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Compensadores | `v1` | `GET` | `/activos/compensadores/v1/activos/{id}` | `getActiveCompensatorById_1` | Devuelve un compensador activo del sistema Infotécnica Instalaciones, dado el Id | Devuelve un compensador activo dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationActiveCompensatorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Compensadores | `v1` | `GET` | `/activos/compensadores/v1/estaticos-reactivos` | `getReactiveStaticCompensatorByFilter_1` | Devuelve una lista de compensadores estáticos reactivos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de compensadores estáticos reactivos dado los parámetros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationReactiveStaticCompensatorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Compensadores | `v1` | `GET` | `/activos/compensadores/v1/estaticos-reactivos/{id}` | `getReactiveStaticCompensatorById_1` | Devuelve un compensador estático reactivo del sistema Infotécnica Instalaciones, dado el Id | Devuelve una compensador estático reactivo dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationReactiveStaticCompensatorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Compensadores | `v2` | `GET` | `/activos/compensadores/v2/activos` | `getActiveCompensatorByFilter` | Devuelve una lista de compensadores activos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | Devuelve una lista de compensadores activos dado los parámetros de búsqueda. | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationActiveCompensatorDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Compensadores | `v2` | `GET` | `/activos/compensadores/v2/activos/{id}` | `getReactiveStaticCompensatorById` | Devuelve un compensador estático reactivo del sistema Infotécnica Instalaciones, dado el Id | Devuelve una compensador estático reactivo dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationReactiveStaticCompensatorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Compensadores | `v2` | `GET` | `/activos/compensadores/v2/estaticos-reactivos` | `getReactiveStaticCompensatorByFilter` | Devuelve una lista de compensadores estáticos reactivos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | Devuelve una lista de compensadores estáticos reactivos dado los parámetros de búsqueda. | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationReactiveStaticCompensatorDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Compensadores | `v2` | `GET` | `/activos/compensadores/v2/estaticos-reactivos/{id}` | `getReactiveStaticCompensatorById` | Devuelve un compensador estático reactivo del sistema Infotécnica Instalaciones, dado el Id | Devuelve una compensador estático reactivo dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationReactiveStaticCompensatorDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Completitud | `v1` | `GET` | `/activos/completitud/v1/grado-de-cumplimiento` | `getCompletenessQualityByFilters_1` | Buscar las Completitudes Calidad Instalaciones del sistema Infotécnica Instalaciones por filtros de búsqueda | Buscar las Completitudes Calidad Instalaciones por filtros de búsqueda | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationCompletenessQualityDto` |
| PLANIFICACION | Infotécnica Instalaciones | Completitud | `v2` | `GET` | `/activos/completitud/v2/grado-de-cumplimiento` | `getCompletenessQualityByFilters` | Buscar las Completitudes Calidad Instalaciones del sistema Infotécnica Instalaciones por filtros de búsqueda | Buscar las Completitudes Calidad Instalaciones por filtros de búsqueda. (Se muestra por defecto 10 registros por página). | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationCompletenessQualityDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Conceptos | `v1` | `GET` | `/activos/conceptos/v1` | `getConceptByFilter` | Devuelve una lista de conceptos del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de conceptos dado los parámetros de búsqueda. | id, nombre, nombreIContains, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseConceptDto` |
| PLANIFICACION | Infotécnica Instalaciones | Conceptos | `v1` | `GET` | `/activos/conceptos/v1/{id}` | `getConceptById` | Obtiene los Conceptos de Infotecnica Instalaciones | Devuelve  un concepto dado un Id válido | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `ConceptDto` |
| PLANIFICACION | Infotécnica Instalaciones | Conceptos | `v2` | `GET` | `/activos/conceptos/v2` | `getConceptByFilter_1` | Devuelve una lista de conceptos del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de conceptos dado los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2ConceptDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Conceptos | `v2` | `GET` | `/activos/conceptos/v2/{id}` | `getConceptById_1` | Devuelve un concepto del sistema Infotécnica Instalaciones dado el Id | Devuelve  un concepto dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `ConceptDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `v1` | `GET` | `/activos/condensadores/v1/series` | `getCapacitorSeriesByFilter` | Obtiene una lista de series de condensadores del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de series de condensadores del sistema Infotecnica Instalaciones de los filtros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCapacitorsDto` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `v1` | `GET` | `/activos/condensadores/v1/series/{id}` | `getCapacitorSeriesById` | Obtiene la serie de condensador del sistema Infotecnica Instalaciones, dado el Id. | Devuelve una serie de condensador del sistema Infotecnica Instalaciones dada la Id.B | id | Sí (global: api-key) | 200, 400, 404, 500 | `CapacitorsDto` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `v1` | `GET` | `/activos/condensadores/v1/sincronos` | `getCapacitorSynchronousByFilter` | Obtiene una lista de condensadores síncronos del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de series de condensadores sincronos del sistema Infotecnica Instalaciones de los filtros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCapacitorsDto` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `v1` | `GET` | `/activos/condensadores/v1/sincronos/{id}` | `getCapacitorSynchronousById` | Obtiene condensador síncrono del sistema Infotecnica Instalaciones, dado el Id | Devuelve un condensador síncrono del sistema Infotecnica Instalaciones dado el Id. | id | Sí (global: api-key) | 200, 400, 404, 500 | `CapacitorsDto` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `v2` | `GET` | `/activos/condensadores/v2/series` | `getCapacitorSeriesByFilter_1` | Obtiene una lista de series de condensadores del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de series de condensadores del sistema Infotecnica Instalaciones de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CapacitorsDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `v2` | `GET` | `/activos/condensadores/v2/series/{id}` | `getCapacitorSeriesById_1` | Obtiene la serie de condensador del sistema Infotecnica Instalaciones, dado el Id. | Devuelve una serie de condensador del sistema Infotecnica Instalaciones dada la Id.B | id | Sí (global: api-key) | 200, 400, 404, 500 | `CapacitorsDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `v2` | `GET` | `/activos/condensadores/v2/sincronos` | `getCapacitorSynchronousByFilter_1` | Obtiene una lista de condensadores síncronos del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de series de condensadores sincronos del sistema Infotecnica Instalaciones de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CapacitorsDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Condensadores | `v2` | `GET` | `/activos/condensadores/v2/sincronos/{id}` | `getCapacitorSynchronousById_1` | Obtiene condensador síncrono del sistema Infotecnica Instalaciones, dado el Id | Devuelve un condensador síncrono del sistema Infotecnica Instalaciones dado el Id. | id | Sí (global: api-key) | 200, 400, 404, 500 | `CapacitorsDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Conductor | `v1` | `GET` | `/activos/conductor/v1/tipos` | `getConductorTypeByFilter_1` | Devuelve una lista de conductor tipo a partir de los filtros de búsqueda del sistema Infotécnica Instalaciones | Devuelve una lista de conductor tipo dado los parámetros de búsqueda del sistema Infotécnica Instalaciones. | id, nombre, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseConductorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Conductor | `v1` | `GET` | `/activos/conductor/v1/tipos/{id}` | `getConductorTypeById_1` | Devuelve un Tipo de Conductor dado el Id del sistema Infotécnica Instalaciones | Devuelve un Tipo de Conductor dado un Id válido del sistema Infotécnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `ConductorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Conductor | `v2` | `GET` | `/activos/conductor/v2/tipos` | `getConductorTypeByFilter` | Devuelve una lista de conductor tipo a partir de los filtros de búsqueda del sistema Infotécnica Instalaciones | Devuelve una lista de conductor tipo dado los parámetros de búsqueda del sistema Infotécnica Instalaciones. (Se muestra por defecto 10 registros por página). | id, nombre, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2ConductorDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Conductor | `v2` | `GET` | `/activos/conductor/v2/tipos/{id}` | `getConductorTypeById` | Devuelve un Tipo de Conductor dado el Id del sistema Infotécnica Instalaciones | Devuelve un Tipo de Conductor dado un Id válido del sistema Infotécnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `ConductorDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Conexiones | `v1` | `GET` | `/activos/conexiones/v1/derivacion` | `getConnectionByFilter` | Devuelve una lista de conexiones a partir de los filtros de búsqueda | Devuelve una lista de conexiones dado los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstalationTapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Conexiones | `v1` | `GET` | `/activos/conexiones/v1/derivacion/{id}` | `getConnectionById` | Devuelve una conexion dado el Id | Devuelve una conexión dado un Id válido del Sistema Infotécnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationTapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Conexiones | `v2` | `GET` | `/activos/conexiones/v2/derivacion` | `getConnectionByFilter2` | Devuelve una lista de conexiones a partir de los filtros de búsqueda | Devuelve una lista de conexiones dado los parámetros de búsqueda del Sistema Infotecnica Instalaciones. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstalationTapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Conexiones | `v2` | `GET` | `/activos/conexiones/v2/derivacion/{id}` | `getConnectionById2` | Devuelve una conexion dado el Id | Devuelve una conexión dado un Id válido del Sistema Infotécnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationTapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Configuraciones | `v1` | `GET` | `/activos/configuraciones/v1` | `getSettingByFilters_1` | Devuelve una lista de configuraciones del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de configuraciones dado los parámetros de búsqueda. | id, nombre, nemotecnico, idPropietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationSettingDto` |
| PLANIFICACION | Infotécnica Instalaciones | Configuraciones | `v1` | `GET` | `/activos/configuraciones/v1/{id}` | `getSettingById_1` | Devuelve una configuración del sistema Infotécnica Instalaciones, dado el Id | Devuelve una configuración dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationSettingDto` |
| PLANIFICACION | Infotécnica Instalaciones | Configuraciones | `v2` | `GET` | `/activos/configuraciones/v2` | `getSettingByFilters` | Devuelve una lista de configuraciones del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de configuraciones dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, nombre, nemotecnico, id_propietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationSettingDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Configuraciones | `v2` | `GET` | `/activos/configuraciones/v2/{id}` | `getSettingById` | Devuelve una configuración del sistema Infotécnica Instalaciones, dado el Id | Devuelve una configuración dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationSettingDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Desconectadores | `v1` | `GET` | `/activos/desconectadores/v1` | `getDisconnectorByFilter_1` | Devuelve una lista de desconectadores del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de desconectadores dado los parámetros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationDisconnectorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Desconectadores | `v1` | `GET` | `/activos/desconectadores/v1/{id}` | `getDisconnectorById_1` | Devuelve un desconectador del sistema Infotécnica Instalaciones, dado el Id | Devuelve un desconectador dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationDisconnectorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Desconectadores | `v2` | `GET` | `/activos/desconectadores/v2` | `getDisconnectorByFilter` | Devuelve una lista de desconectadores del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de desconectadores dado los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationDisconnectorDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Desconectadores | `v2` | `GET` | `/activos/desconectadores/v2/{id}` | `getDisconnectorById` | Devuelve un desconectador del sistema Infotécnica Instalaciones, dado el Id | Devuelve un desconectador dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationDisconnectorDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Dispositivos | `v1` | `GET` | `/activos/dispositivos/v1/reconexiones` | `getDevicesByFilters` | Devuelve una lista de dispositivos del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de dispositivos del sistema Infotécnica Instalaciones dado los parámetros. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseDeviceDto` |
| PLANIFICACION | Infotécnica Instalaciones | Dispositivos | `v1` | `GET` | `/activos/dispositivos/v1/reconexiones/{id}` | `getDeviceById` | Devuelve un dispositivo del sistema Infotécnica Instalaciones dado el Id | Devuelve un dispositivo del sistema Infotécnica Instalaciones dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `DeviceDto` |
| PLANIFICACION | Infotécnica Instalaciones | Dispositivos | `v2` | `GET` | `/activos/dispositivos/v2/reconexiones` | `getDevicesByFilters2` | Devuelve una lista de dispositivos del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de dispositivos del sistema Infotécnica Instalaciones dado los parámetros. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2DeviceDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Dispositivos | `v2` | `GET` | `/activos/dispositivos/v2/reconexiones/{id}` | `getDeviceById2` | Devuelve un dispositivo del sistema Infotécnica Instalaciones dado el Id | Devuelve un dispositivo del sistema Infotécnica Instalaciones dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `DeviceDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Enterprise | `v1` | `GET` | `/activos/empresas/v1` | `getCompanyByFilter_1` | Devuelve una lista de empresas del sistema Infotecnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de empresa dado los parámetros de búsqueda. | id, nombre, nemotecnico, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstalationEnterpriseDto` |
| PLANIFICACION | Infotécnica Instalaciones | Enterprise | `v1` | `GET` | `/activos/empresas/v1/completitud-calidad/estudio-pes-anexos` | `getEnterpriseCompletenessQualityStudyPesAnnexes_1` | Devuelve la completitud calidad del sistema Infotecnica Instalaciones dado el Id Empresa | Devuelve la completitud calidad dado un Id Empresa válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationStudyPesAnnexesDto` |
| PLANIFICACION | Infotécnica Instalaciones | Enterprise | `v1` | `GET` | `/activos/empresas/v1/completitud-calidad/instalaciones` | `getEnterpriseCompletenessQualityInstallation_1` | Devuelve la completitud calidad de instalacion del sistema Infotecnica Instalaciones dado el Id Empresa | Devuelve la completitud calidad de instalacion dado un Id Empresa válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `CompletenessQualityPerInstallationDto` |
| PLANIFICACION | Infotécnica Instalaciones | Enterprise | `v1` | `GET` | `/activos/empresas/v1/{id}` | `getEnterpriseById_1` | Devuelve una empresa del sistema Infotecnica Instalaciones dado el Id | Devuelve una empresa dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationEnterpriseDto` |
| PLANIFICACION | Infotécnica Instalaciones | Enterprise | `v2` | `GET` | `/activos/empresas/v2` | `getCompanyByFilter` | Devuelve una lista de empresas del sistema Infotecnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de empresa dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, nombre, nemotecnico, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstalationEnterpriseDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Enterprise | `v2` | `GET` | `/activos/empresas/v2/completitud-calidad/estudio-pes-anexos` | `getEnterpriseCompletenessQualityStudyPesAnnexes` | Devuelve la completitud calidad del sistema Infotecnica Instalaciones dado el Id Empresa | Devuelve la completitud calidad dado un Id Empresa válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationStudyPesAnnexesDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Enterprise | `v2` | `GET` | `/activos/empresas/v2/completitud-calidad/instalaciones` | `getEnterpriseCompletenessQualityInstallation` | Devuelve la completitud calidad de instalacion del sistema Infotecnica Instalaciones dado el Id Empresa | Devuelve la completitud calidad de instalacion dado un Id Empresa válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `CompletenessQualityPerInstallationDto` |
| PLANIFICACION | Infotécnica Instalaciones | Enterprise | `v2` | `GET` | `/activos/empresas/v2/{id}` | `getEnterpriseById` | Devuelve una empresa del sistema Infotecnica Instalaciones dado el Id | Devuelve una empresa dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationEnterpriseDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Fuentes Energías | `v1` | `GET` | `/activos/fuentes-energias/v1/` | `getPowerSourceByOrdering` | Devuelve una lista de fuentes de energías | Devuelve una lista de fuentes de energías. | ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationPowerSourceDto` |
| PLANIFICACION | Infotécnica Instalaciones | Fuentes Energías | `v1` | `GET` | `/activos/fuentes-energias/v1/{id}` | `getPowerSourceById` | Devuelve una fuente de energía dado el Id | Devuelve una fuente de energía dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationPowerSourceDto` |
| PLANIFICACION | Infotécnica Instalaciones | Fuentes Energías | `v2` | `GET` | `/activos/fuentes-energias/v2/` | `getPowerSourceByOrdering` | Devuelve una lista de fuentes de energías del sistema Infotécnica Instalaciones | Devuelve una lista de fuentes de energías del sistema Infotécnica Instalaciones. | ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationPowerSourceDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Fuentes Energías | `v2` | `GET` | `/activos/fuentes-energias/v2/{id}"` | `getPowerSourceById` | Devuelve una fuente de energía dado el Id del sistema Infotécnica Instalaciones | Devuelve una fuente de energía dado un Id válido del sistema Infotécnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationPowerSourceDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Giros | `v1` | `GET` | `/activos/giros/v1` | `getTurns_1` | Devuelve una lista de giros del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de giros dado los parámetros de búsqueda. | id, nombre, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCompanyTurnDto` |
| PLANIFICACION | Infotécnica Instalaciones | Giros | `v1` | `GET` | `/activos/giros/v1/{id}` | `getTurnById` | Devuelve un giro dado el Id del sistema Infotécnica Instalaciones | Devuelve un giro dado un Id válido del sistema Infotécnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `CompanyTurnDto` |
| PLANIFICACION | Infotécnica Instalaciones | Giros | `v2` | `GET` | `/activos/giros/v2` | `getTurns` | Devuelve una lista de giros del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de giros dado los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, nombre, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CompanyTurnDto` |
| PLANIFICACION | Infotécnica Instalaciones | Giros | `v2` | `GET` | `/activos/giros/v2/{id}` | `getTurnById` | Devuelve un giro del sistema Infotécnica Instalaciones dado el Id | Devuelve un giro dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `CompanyTurnDto` |
| PLANIFICACION | Infotécnica Instalaciones | Grupos | `v1` | `GET` | `/activos/grupos/v1` | `getGroupByFilter_1` | Devuelve grupos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve grupos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | id, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseGroupDto` |
| PLANIFICACION | Infotécnica Instalaciones | Grupos | `v1` | `GET` | `/activos/grupos/v1/{id}` | `getGroupById_1` | Devuelve un grupo del sistema Infotécnica Instalaciones, dado el id | Devuelve un grupo del sistema Infotécnica Instalaciones, dado un id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `GroupDto` |
| PLANIFICACION | Infotécnica Instalaciones | Grupos | `v2` | `GET` | `/activos/grupos/v2` | `getGroupByFilter` | Devuelve grupos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve grupos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2GroupDto` |
| PLANIFICACION | Infotécnica Instalaciones | Grupos | `v2` | `GET` | `/activos/grupos/v2/{id}` | `getGroupById` | Devuelve un grupo del sistema Infotécnica Instalaciones, dado el id | Devuelve un grupo del sistema Infotécnica Instalaciones, dado un id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `GroupDto` |
| PLANIFICACION | Infotécnica Instalaciones | Instalaciones | `v1` | `GET` | `/activos/instalaciones/v1/reporte` | `getReportData` | Devuelve los datos para el reporte de instalaciones | Devuelve los datos para el reporte de instalaciones | installationTypeId, technicalDataIds | Sí (global: api-key) | 200, 400, 404, 500 | `array[EntityDto]` |
| PLANIFICACION | Infotécnica Instalaciones | Intercomunicadores | `v1` | `GET` | `/activos/intercomunicadores/v1` | `getIntercomByFilter` | Devuelve una lista de intercomunicadores del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de intercomunicadores dado los parámetros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationIntercomDto` |
| PLANIFICACION | Infotécnica Instalaciones | Intercomunicadores | `v1` | `GET` | `/activos/intercomunicadores/v1/{id}` | `getIntercomById` | Devuelve un intercomunicador del sistema Infotecnica Instalaciones, dado el Id | Devuelve un intercomunicador dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationIntercomDto` |
| PLANIFICACION | Infotécnica Instalaciones | Intercomunicadores | `v2` | `GET` | `/activos/intercomunicadores/v2` | `getIntercomByFilter` | Devuelve una lista de intercomunicadores del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de intercomunicadores dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationIntercomDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Intercomunicadores | `v2` | `GET` | `/activos/intercomunicadores/v2/{id}` | `getIntercomById` | Devuelve un intercomunicador del sistema Infotecnica Instalaciones, dado el Id | Devuelve un intercomunicador dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationIntercomDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Interruptores | `v1` | `GET` | `/activos/interruptores/v1` | `getSwitchesByFilters` | Buscar todos los Interruptores del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todos los Interruptores por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseSwitchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Interruptores | `v1` | `GET` | `/activos/interruptores/v1/{id}` | `getSwitchById` | Buscar un Interruptor del sistema Infotécnica Instalaciones por ID | Retorna un solo Interruptor | id | Sí (global: api-key) | 200, 400, 404, 500 | `SwitchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Interruptores | `v2` | `GET` | `/activos/interruptores/v2` | `getSwitchesByFilters2` | Buscar todos los Interruptores del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todos los Interruptores por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2SwitchDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Interruptores | `v2` | `GET` | `/activos/interruptores/v2/{id}` | `getSwitchById2` | Buscar un Interruptor del sistema Infotécnica Instalaciones por ID | Retorna un solo Interruptor | id | Sí (global: api-key) | 200, 400, 404, 500 | `SwitchDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `v1` | `GET` | `/activos/lineas/v1` | `getLinesDetail` | Obtener datos de Lineas del sistema Infotecnica Instalaciones | Retorna datos de lineas segun filtros del sistema Infotecnica Instalaciones | id, idPropietario, nombre, nemotecnico, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseLineDto` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `v1` | `GET` | `/activos/lineas/v1/estadisticas` | `getAllStatisticsOfLines` | Buscar todas las estadísticas de líneas de Infotecnica Instalaciones | Buscar todas las estadísticas de líneas | Sin parámetros principales o ver detalle | Sí (endpoint: api-key) | 200, 400, 404, 500 | `StatisticsLineDto` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `v1` | `GET` | `/activos/lineas/v1/{id}` | `getLines` | Obtener Linea segun su id del sistema Infotecnica Instalaciones | Devuelve datos de Linea del sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `LineDto` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `v2` | `GET` | `/activos/lineas/v2` | `getLinesDetail` | Obtener datos de Lineas del sistema Infotecnica Instalaciones | Retorna datos de lineas segun filtros del sistema Infotecnica Instalaciones. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nemotecnico, nemotecnico_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2LineDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Lineas | `v2` | `GET` | `/activos/lineas/v2/{id}` | `getLines` | Obtener Linea segun su id del sistema Infotecnica Instalaciones | Devuelve datos de Linea del sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `LineDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Medidores | `v1` | `GET` | `/activos/medidores/v1` | `getAllGauges` | Buscar todos los Medidores por filtros de búsqueda y ordenamiento del sistema Infotecnica Instalaciones | Buscar todos los Medidores por filtros de búsqueda y ordenamiento del sistema Infotecnica Instalaciones | id, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseGaugeDto` |
| PLANIFICACION | Infotécnica Instalaciones | Medidores | `v1` | `GET` | `/activos/medidores/v1/{id}` | `getGaugeById` | Buscar un Medidor del sistema Infotécnica Instalaciones por ID | Retorna un Medidor del sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `GaugeDto` |
| PLANIFICACION | Infotécnica Instalaciones | Medidores | `v2` | `GET` | `/activos/medidores/v2` | `getAllGauges2` | Buscar todos los Medidores por filtros de búsqueda y ordenamiento del sistema Infotecnica Instalaciones | Buscar todos los Medidores por filtros de búsqueda y ordenamiento del sistema Infotecnica Instalaciones. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2GaugeDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Medidores | `v2` | `GET` | `/activos/medidores/v2/{id}` | `getGaugeById2` | Buscar un Medidor del sistema Infotécnica Instalaciones por ID | Retorna un Medidor del sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `GaugeDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Panios | `v1` | `GET` | `/activos/panos/v1` | `getWipersByFilters_1` | Buscar todos los paños del sistema Infotécnica Instalaciones por ordenamiento | Buscar todos los paños por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, idPropietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseWiperDto` |
| PLANIFICACION | Infotécnica Instalaciones | Panios | `v1` | `GET` | `/activos/panos/v1/{id}` | `getWiperById_1` | Buscar paño del sistema Infotécnica Instalaciones por ID | Retorna un solo paño | id | Sí (global: api-key) | 200, 400, 404, 500 | `WiperDto` |
| PLANIFICACION | Infotécnica Instalaciones | Panios | `v2` | `GET` | `/activos/panos/v2` | `getWipersByFilters` | Buscar todos los paños del sistema Infotécnica Instalaciones por ordenamiento | Buscar todos los paños por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, nombre, nombre_i_contains, id_propietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2WiperDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Panios | `v2` | `GET` | `/activos/panos/v2/{id}` | `getWiperById` | Buscar paño del sistema Infotécnica Instalaciones por ID | Retorna un solo paño | id | Sí (global: api-key) | 200, 400, 404, 500 | `WiperDto` |
| PLANIFICACION | Infotécnica Instalaciones | Pararrayos | `v1` | `GET` | `/activos/pararrayos/v1` | `getLightningRodByFilters_1` | Devuelve una lista de Pararrayos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de Pararrayos del sistema Infotécnica Instalaciones, dado los parámetros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseLightningRodDto` |
| PLANIFICACION | Infotécnica Instalaciones | Pararrayos | `v1` | `GET` | `/activos/pararrayos/v1/{id}` | `getLightningRodById_1` | Devuelve un Pararrayo del sistema Infotécnica Instalaciones, dado el Id | Devuelve un Pararrayo del sistema Infotécnica Instalaciones, dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `LightningRodDto` |
| PLANIFICACION | Infotécnica Instalaciones | Pararrayos | `v2` | `GET` | `/activos/pararrayos/v2` | `getLightningRodByFilters` | Devuelve una lista de Pararrayos del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de Pararrayos del sistema Infotécnica Instalaciones, dado los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2LightningRodDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Pararrayos | `v2` | `GET` | `/activos/pararrayos/v2/{id}` | `getLightningRodById` | Devuelve un Pararrayo del sistema Infotécnica Instalaciones, dado el Id | Devuelve un Pararrayo del sistema Infotécnica Instalaciones, dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `LightningRodDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Potencia Neta | `v1` | `GET` | `/activos/potencia-neta/v1/` | `getNetPower_1` | Obtener PotenciaNeta | Retorna la potencia neta buscado por id_central | id | Sí (global: api-key) | 200, 400, 404, 500 | `NetPowerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Potencia Neta | `v2` | `GET` | `/activos/potencia-neta/v2/` | `getNetPower` | Obtener PotenciaNeta | Retorna la potencia neta buscado por id_central | id | Sí (global: api-key) | 200, 400, 404, 500 | `NetPowerDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Proyectos | `v1` | `GET` | `/activos/proyectos/v1/` | `getProjectByFilter` | Devuelve una lista de proyectos del sistema Infotecnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de proyectos dado los parámetros de búsqueda. | id, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstalationProjectDto` |
| PLANIFICACION | Infotécnica Instalaciones | Proyectos | `v1` | `GET` | `/activos/proyectos/v1/{id}` | `getProjectById` | Devuelve una proyecto del sistema Infotecnica Instalaciones dado el Id | Devuelve una proyecto dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationProjectDto` |
| PLANIFICACION | Infotécnica Instalaciones | Proyectos | `v2` | `GET` | `/activos/proyectos/v2` | `getProjectByFilter` | Devuelve una lista de proyectos del sistema Infotecnica Instalaciones a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de proyectos dado los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstalationProjectDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Reactores | `v1` | `GET` | `/activos/reactores/v1` | `getReactorsByFilters_1` | Buscar todos los Reactores del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todos los Reactores por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseReactorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Reactores | `v1` | `GET` | `/activos/reactores/v1/{id}` | `getReactorById_1` | Buscar un Reactor del sistema Infotécnica Instalaciones por ID | Retorna un solo Reactor | id | Sí (global: api-key) | 200, 400, 404, 500 | `ReactorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Reactores | `v2` | `GET` | `/activos/reactores/v2` | `getReactorsByFilters` | Buscar todos los Reactores del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todos los Reactores por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2ReactorDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Reactores | `v2` | `GET` | `/activos/reactores/v2/{id}` | `getReactorById` | Buscar un Reactor del sistema Infotécnica Instalaciones por ID | Retorna un solo Reactor | id | Sí (global: api-key) | 200, 400, 404, 500 | `ReactorDto` |
| PLANIFICACION | Infotécnica Instalaciones | Retiro-Instalaciones | `v1` | `GET` | `/activos/retiro-instalaciones/v1` | `getInstallationRemovalByFilters_1` | Buscar todos los Retiro Instalaciones del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | Buscar todos los Retiro Instalaciones por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationRemovalDto` |
| PLANIFICACION | Infotécnica Instalaciones | Retiro-Instalaciones | `v1` | `GET` | `/activos/retiro-instalaciones/v1/{id}` | `getInstallationRemovalById_1` | Buscar un Retiro Instalaciones del sistema Infotécnica Instalaciones por ID | Retorna un solo Retiro Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationRemovalDto` |
| PLANIFICACION | Infotécnica Instalaciones | Retiro-Instalaciones | `v2` | `GET` | `/activos/retiro-instalaciones/v2` | `getInstallationRemovalByFilters` | Buscar todos los Retiro Instalaciones del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | Buscar todos los Retiro Instalaciones por filtros de búsqueda y ordenamiento | id, nombre, nombre_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationRemovalDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Retiro-Instalaciones | `v2` | `GET` | `/activos/retiro-instalaciones/v2/{id}` | `getInstallationRemovalById` | Buscar un Retiro Instalaciones del sistema Infotécnica Instalaciones por ID | Retorna un solo Retiro Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationRemovalDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v1` | `GET` | `/activos/secciones/v1/barras` | `getSectionBarByFilter` | Devuelve una lista de secciones de barras del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de secciones de barras dado los parámetros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstalationSectionBarDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v1` | `GET` | `/activos/secciones/v1/barras/{id}` | `getSectionBarById` | Devuelve una sección de barras del sistema Infotécnica Instalaciones dado el Id | Devuelve una sección de barras dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationSectionBarDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v1` | `GET` | `/activos/secciones/v1/conexion` | `getSection` | Buscar todas las conexiones del  sistema Infotécnica Instalaciones por ordenamiento | Buscar todas las conexiones por ordenamiento | ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstalationSectionConnectionDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v1` | `GET` | `/activos/secciones/v1/conexion/{id}` | `getSectionConnectionById` | Devuelve una sección de conexiones del sistema Infotécnica Instalaciones dado el Id | Devuelve una sección de conexiones dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationSectionConnectionDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v1` | `GET` | `/activos/secciones/v1/tramos` | `getSectionStretchByFilter` | Devuelve una lista de secciones de tramos del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de secciones de tramos dado los parámetros de búsqueda. | id, idPropietario, nombre, nemotecnico, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstalationsSectionStretchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v1` | `GET` | `/activos/secciones/v1/tramos/{id}` | `getSectionStretchById` | Devuelve una sección de tramos del sistema Infotécnica Instalaciones dado el id | Devuelve una sección de tramos dado un id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationsSectionStretchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v2` | `GET` | `/activos/secciones/v2/barras` | `getSectionBarByFilter` | Devuelve una lista de secciones de barras del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de secciones de barras dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstalationSectionBarDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v2` | `GET` | `/activos/secciones/v2/barras/{id}` | `getSectionBarById` | Devuelve una sección de barras del sistema Infotécnica Instalaciones dado el Id | Devuelve una sección de barras dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationSectionBarDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v2` | `GET` | `/activos/secciones/v2/conexion` | `getSection` | Buscar todas las conexiones del  sistema Infotécnica Instalaciones por ordenamiento | Buscar todas las conexiones por ordenamiento. (Se muestra por defecto 10 registros por página). | ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstalationSectionConnectionDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v2` | `GET` | `/activos/secciones/v2/conexion/{id}` | `getSectionConnectionById` | Devuelve una sección de conexiones del sistema Infotécnica Instalaciones dado el Id | Devuelve una sección de conexiones dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationSectionConnectionDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v2` | `GET` | `/activos/secciones/v2/tramos` | `getSectionStretchByFilter` | Devuelve una lista de secciones de tramos del sistema Infotécnica Instalaciones a partir de los filtros de búsqueda | Devuelve una lista de secciones de tramos dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nemotecnico, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstalationsSectionStretchDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Secciones | `v2` | `GET` | `/activos/secciones/v2/tramos/{id}` | `getSectionStretchById` | Devuelve una sección de tramos del sistema Infotécnica Instalaciones dado el id | Devuelve una sección de tramos dado un id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationsSectionStretchDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Sincronizadores | `v1` | `GET` | `/activos/sincronizadores/v1` | `getSynchronizersByFilters_1` | Buscar todos los Sincronizadores del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todos los Sincronizadores por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseSynchronizerDto3` |
| PLANIFICACION | Infotécnica Instalaciones | Sincronizadores | `v1` | `GET` | `/activos/sincronizadores/v1/{id}` | `getSynchronizerById_1` | Buscar un Sincronizador del sistema Infotécnica Instalaciones por ID | Retorna un solo Sincronizador | id | Sí (global: api-key) | 200, 400, 404, 500 | `SynchronizerDto3` |
| PLANIFICACION | Infotécnica Instalaciones | Sincronizadores | `v2` | `GET` | `/activos/sincronizadores/v2` | `getSynchronizersByFilters` | Buscar todos los Sincronizadores del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | Buscar todos los Sincronizadores por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2SynchronizerDto4` |
| PLANIFICACION | Infotécnica Instalaciones | Sincronizadores | `v2` | `GET` | `/activos/sincronizadores/v2/{id}` | `getSynchronizerById` | Buscar un Sincronizador del sistema Infotécnica Instalaciones por ID | Retorna un solo Sincronizador | id | Sí (global: api-key) | 200, 400, 404, 500 | `SynchronizerDto4` |
| PLANIFICACION | Infotécnica Instalaciones | Sistemas-Protecciones | `v1` | `GET` | `/activos/sistemas-proteccion/v1` | `getProtectionSystemsByFilters` | Buscar todos los Sistemas Protecciones del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todos los Sistemas Protecciones por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseProtectionSystemDto` |
| PLANIFICACION | Infotécnica Instalaciones | Sistemas-Protecciones | `v1` | `GET` | `/activos/sistemas-proteccion/v1/{id}` | `getProtectionSystemById` | Buscar un Sistema Protección del sistema Infotécnica Instalaciones por ID | Retorna un solo Sistema Protección | id | Sí (global: api-key) | 200, 400, 404, 500 | `ProtectionSystemDto` |
| PLANIFICACION | Infotécnica Instalaciones | Sistemas-Protecciones | `v2` | `GET` | `/activos/sistemas-proteccion/v2` | `getProtectionSystemsByFilters_1` | Buscar todos los Sistemas Protecciones del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todos los Sistemas Protecciones por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2ProtectionSystemDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Sistemas-Protecciones | `v2` | `GET` | `/activos/sistemas-proteccion/v2/{id}` | `getProtectionSystemById_1` | Buscar un Sistema Protección del sistema Infotécnica Instalaciones por ID | Retorna un solo Sistema Protección | id | Sí (global: api-key) | 200, 400, 404, 500 | `ProtectionSystemDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `v1` | `GET` | `/activos/subestaciones/v1` | `getSubstationByFilter_1` | Devuelve una lista de subestaciones del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de subestaciónes dado los parámetros de búsqueda. | id, idPropietario, nombre, nemotecnico, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstalationSubstationDto` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `v1` | `GET` | `/activos/subestaciones/v1/elementos-totales` | `getTotalElements` | Devuelve el total de elementos de subestación del sistema Infotécnica Instalaciones | Devuelve el total de elementos de subestación | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `TotalElementDto` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `v1` | `GET` | `/activos/subestaciones/v1/{id}` | `getSubstationById_1` | Devuelve una subestación del sistema Infotécnica Instalaciones, dado el Id | Devuelve un subestación dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationSubstationDto` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `v1` | `GET` | `/activos/subestaciones/v1/{id}/elementos` | `getTotalElementsByIdSubstation` | Devuelve el total de elementos de subestación dado Id de subestación | Devuelve el total de elementos dado Id de subestación | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `TotalDataElementDto` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `v2` | `GET` | `/activos/subestaciones/v2` | `getSubstationByFilter` | Devuelve una lista de subestaciones del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de subestaciónes dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, nemotecnico, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstalationSubstationDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Subestaciones | `v2` | `GET` | `/activos/subestaciones/v2/{id}` | `getSubstationById` | Devuelve una subestación del sistema Infotécnica Instalaciones, dado el Id | Devuelve un subestación dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstalationSubstationDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tap | `v1` | `GET` | `/activos/taps/v1` | `getTapByFilter` | Devuelve una lista de taps del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de taps dado los parámetros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationTapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tap | `v1` | `GET` | `/activos/taps/v1/{id}` | `getTapById` | Devuelve un tap del sistema Infotecnica Instalaciones, dado el Id | Devuelve un tap dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationTapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tap | `v2` | `GET` | `/activos/taps/v2` | `getTapByFilter_1` | Devuelve una lista de taps del sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de taps dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationTapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tap | `v2` | `GET` | `/activos/taps/v2/{id}` | `getTapById_1` | Devuelve un tap del sistema Infotecnica Instalaciones, dado el Id | Devuelve un tap dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationTapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Teleprotecciones | `v1` | `GET` | `/activos/teleprotecciones/v1` | `getTeleprotectionByFilter` | Devuelve una lista de teleprotecciones del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de teleprotecciones dado los parámetros de búsqueda. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationTeleprotectionDto` |
| PLANIFICACION | Infotécnica Instalaciones | Teleprotecciones | `v1` | `GET` | `/activos/teleprotecciones/v1/{id}` | `getTeleprotectionById` | Devuelve una teleprotección del sistema Infotécnica Instalaciones, dado el Id | Devuelve una teleprotección dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationTeleprotectionDto` |
| PLANIFICACION | Infotécnica Instalaciones | Teleprotecciones | `v2` | `GET` | `/activos/teleprotecciones/v2` | `getTeleprotectionByFilter2` | Devuelve una lista de teleprotecciones del sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de teleprotecciones dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationTeleprotectionDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Teleprotecciones | `v2` | `GET` | `/activos/teleprotecciones/v2/{id}` | `getTeleprotectionById2` | Devuelve una teleprotección del sistema Infotécnica Instalaciones, dado el Id | Devuelve una teleprotección dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationTeleprotectionDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Torre | `v1` | `GET` | `/activos/torre/v1/tipos` | `getTowers_1` | Devuelve una lista de Torres del Sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de Torres del Sistema Infotécnica Instalaciones, dado los parámetros de búsqueda. | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTowerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Torre | `v1` | `GET` | `/activos/torre/v1/tipos/{id}` | `getTowerById_1` | Devuelve un registro de Torre del Sistema Infotécnica Instalaciones, dado el Id | Devuelve un registro de Torre del Sistema Infotécnica Instalaciones, dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `TowerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Torre | `v2` | `GET` | `/activos/torre/v2/tipos` | `getTowers` | Devuelve una lista de Torres del Sistema Infotécnica Instalaciones, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de Torres del Sistema Infotécnica Instalaciones, dado los parámetros de búsqueda.Se muestra por defecto 10 registros por página | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2TowerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Torre | `v2` | `GET` | `/activos/torre/v2/tipos/{id}` | `getTowerById` | Devuelve un registro de Torre del Sistema Infotécnica Instalaciones, dado el Id | Devuelve un registro de Torre del Sistema Infotécnica Instalaciones, dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `TowerDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v1` | `GET` | `/activos/tramos/v1` | `getStretchsByFilters_1` | Buscar todos los Tramos del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todos los Tramos por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, idPropietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseStretchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v1` | `GET` | `/activos/tramos/v1/tipos` | `getStretchTypesByFilters_1` | Buscar todos los Tramos Tipos del sistema Infotécnica Instalaciones | Buscar todos los Tramos Tipos | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseStretchTypeDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v1` | `GET` | `/activos/tramos/v1/tipos/{id}` | `getStretchTypeById_1` | Buscar un Tramo Tipo del sistema Infotécnica Instalaciones por ID | Retorna un solo Tramo Tipo | id | Sí (global: api-key) | 200, 400, 404, 500 | `StretchTypeDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v1` | `GET` | `/activos/tramos/v1/trampas-ondas` | `getWaveTrapsByFilters_1` | Buscar todas las Trampas Ondas del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todas las Trampas Ondas por filtros de búsqueda y ordenamiento | id, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseWaveTrapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v1` | `GET` | `/activos/tramos/v1/trampas-ondas/{id}` | `getWaveTrapById_1` | Buscar una Trampa Onda del sistema Infotécnica Instalaciones por ID | Retorna una sola Trampa Onda | id | Sí (global: api-key) | 200, 400, 404, 500 | `WaveTrapDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v1` | `GET` | `/activos/tramos/v1/{id}` | `getStretchById_1` | Buscar un Tramo del sistema Infotécnica Instalaciones por ID | Retorna un solo Tramo | id | Sí (global: api-key) | 200, 400, 404, 500 | `StretchDto` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v2` | `GET` | `/activos/tramos/v2` | `getStretchsByFilters` | Buscar todos los Tramos del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | Buscar todos los Tramos por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, id_propietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2StretchDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v2` | `GET` | `/activos/tramos/v2/tipos` | `getStretchTypesByFilters` | Buscar todos los Tramos Tipos del sistema Infotécnica Instalaciones.Se muestra por defecto 10 registros por página | Buscar todos los Tramos Tipos.Se muestra por defecto 10 registros por página | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2StretchTypeDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v2` | `GET` | `/activos/tramos/v2/tipos/{id}` | `getStretchTypeById` | Buscar un Tramo Tipo del sistema Infotécnica Instalaciones por ID | Retorna un solo Tramo Tipo | id | Sí (global: api-key) | 200, 400, 404, 500 | `StretchTypeDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v2` | `GET` | `/activos/tramos/v2/trampas-ondas` | `getWaveTrapsByFilters` | Buscar todas las Trampas Ondas del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | Buscar todas las Trampas Ondas por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, nombre_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2WaveTrapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v2` | `GET` | `/activos/tramos/v2/trampas-ondas/{id}` | `getWaveTrapById` | Buscar una Trampa Onda del sistema Infotécnica Instalaciones por ID | Retorna una sola Trampa Onda | id | Sí (global: api-key) | 200, 400, 404, 500 | `WaveTrapDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Tramos | `v2` | `GET` | `/activos/tramos/v2/{id}` | `getStretchById` | Buscar un Tramo del sistema Infotécnica Instalaciones por ID | Retorna un solo Tramo | id | Sí (global: api-key) | 200, 400, 404, 500 | `StretchDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/2d` | `getTransformer2DByFilter_3` | Devuelve una lista de transformadores 2d a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones | Devuelve una lista de transformadores 2d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTransformer2DDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/2d/{id}` | `getTransformer2DById_1` | Devuelve un transformador 2d dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador 2d dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `Transformer2DDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/3d` | `getTransformer3DByFilter_3` | Devuelve una lista de transformadores 3d a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones | Devuelve una lista de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTransformer3DDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/3d/{id}` | `getTransformer3DById_1` | Devuelve un transformador 3d dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador 3d dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `Transformer3DDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/auxiliares` | `getTransformerAssistantsByFilter_1` | Devuelve una lista de transformadores auxiliares a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones | Devuelve una lista de transformadores auxiliares dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseAssistantsTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/auxiliares/{id}` | `getAssistantsTransformersById_1` | Devuelve un transformador auxiliar dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador auxiliar dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `AssistantsTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/corrientes` | `getCurrentTransformersByFilter_1` | Devuelve una lista de transformadores corrientes a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones | Devuelve una lista de transformadores corrientes dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCurrentTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/corrientes/{id}` | `getCurrentTransformersById_1` | Devuelve un transformador corriente dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador corriente dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `PotentialTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/potenciales` | `getPotentialTransformersByFilter_1` | Devuelve una lista de transformadores potenciales a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones | Devuelve una lista de transformadores potenciales dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, idPropietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponsePotentialTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v1` | `GET` | `/activos/transformadores/v1/potenciales/{id}` | `getPotentialTransformersById_1` | Devuelve un transformador potencial dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador potencial dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `PotentialTransformersDto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v2` | `GET` | `/activos/transformadores/v2/2d` | `getTransformer3DByFilter_1` | Devuelve una lista de datos de transformadores 3d del Sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de datos de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTransformer3DV2Dto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v2` | `GET` | `/activos/transformadores/v2/3d` | `getTransformer3DByFilter_2` | Devuelve una lista de datos de transformadores 3d del Sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda | Devuelve una lista de datos de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTransformer3DV2Dto` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/2d` | `getTransformer2DByFilter_1` | Devuelve una lista de transformadores 2d a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | Devuelve una lista de transformadores 2d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2Transformer2DDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/2d/{id}` | `getTransformer2DById` | Devuelve un transformador 2d dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador 2d dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `Transformer2DDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/3d` | `getTransformer3DByFilter_1` | Devuelve una lista de transformadores 3d a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | Devuelve una lista de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2Transformer3DDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/3d/{id}` | `getTransformer3DById` | Devuelve un transformador 3d dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador 3d dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `Transformer3DDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/auxiliares` | `getTransformerAssistantsByFilter` | Devuelve una lista de transformadores auxiliares a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | Devuelve una lista de transformadores auxiliares dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2AssistantsTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/auxiliares/{id}` | `getAssistantsTransformersById` | Devuelve un transformador auxiliar dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador auxiliar dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `AssistantsTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/corrientes` | `getCurrentTransformersByFilter` | Devuelve una lista de transformadores corrientes a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | Devuelve una lista de transformadores corrientes dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CurrentTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/corrientes/{id}` | `getCurrentTransformersById` | Devuelve un transformador corriente dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador corriente dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `PotentialTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/potenciales` | `getPotentialTransformersByFilter` | Devuelve una lista de transformadores potenciales a partir de los filtros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | Devuelve una lista de transformadores potenciales dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, id_propietario, nombre, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2PotentialTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v3` | `GET` | `/activos/transformadores/v3/potenciales/{id}` | `getPotentialTransformersById` | Devuelve un transformador potencial dado el Id del Sistema Infotecnica Instalaciones | Devuelve un transformador potencial dado un Id válido del Sistema Infotecnica Instalaciones | id | Sí (global: api-key) | 200, 400, 404, 500 | `PotentialTransformersDto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v4` | `GET` | `/activos/transformadores/v4/2d` | `getTransformer2DByFilter` | Devuelve una lista de datos de transformadores 2d del Sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de datos de transformadores 2d dados los parámetros de búsqueda.Se muestra por defecto 10 registros por página | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2Transformer2DV2Dto2` |
| PLANIFICACION | Infotécnica Instalaciones | Transformadores | `v4` | `GET` | `/activos/transformadores/v4/3d` | `getTransformer3DByFilter` | Devuelve una lista de datos de transformadores 3d del Sistema Infotecnica Instalaciones, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de datos de transformadores 3d dados los parámetros de búsqueda del Sistema Infotecnica Instalaciones.Se muestra por defecto 10 registros por página | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2Transformer3DV2Dto2` |
| PLANIFICACION | Infotécnica Instalaciones | Turbinas | `v1` | `GET` | `/activos/turbina/v1/marcas` | `getTurbineBrandsByFilters_1` | Buscar todas las Turbinas Marcas del sistema Infotécnica Instalaciones con paginado | Buscar todas las Turbinas Marcas con paginado | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTurbineBrandDto` |
| PLANIFICACION | Infotécnica Instalaciones | Turbinas | `v1` | `GET` | `/activos/turbina/v1/marcas/{id}` | `getTurbineBrandById` | Buscar una Turbina Marca del sistema Infotécnica Instalaciones por ID | Retorna una sola Turbina Marca | id | Sí (global: api-key) | 200, 400, 404, 500 | `TurbineBrandDto` |
| PLANIFICACION | Infotécnica Instalaciones | Turbinas | `v1` | `GET` | `/activos/turbina/v1/tipos` | `getTurbineTypesByFilters_1` | Buscar todas las Turbinas Tipos del sistema Infotécnica Instalaciones con paginado | Buscar todas las Turbinas Tipos con paginado | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseTurbineTypeDto` |
| PLANIFICACION | Infotécnica Instalaciones | Turbinas | `v1` | `GET` | `/activos/turbina/v1/tipos/{id}` | `getTurbineTypeById` | Buscar una Turbina Tipo del sistema Infotécnica Instalaciones por ID | Retorna una sola Turbina Tipo | id | Sí (global: api-key) | 200, 400, 404, 500 | `TurbineTypeDto` |
| PLANIFICACION | Infotécnica Instalaciones | Turbinas | `v2` | `GET` | `/activos/turbina/v2/marcas` | `getTurbineBrandsByFilters` | Buscar todas las Turbinas Marcas del sistema Infotécnica Instalaciones con paginado | Buscar todas las Turbinas Marcas con paginado. (Se muestra por defecto 10 registros por página). | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2TurbineBrandDto` |
| PLANIFICACION | Infotécnica Instalaciones | Turbinas | `v2` | `GET` | `/activos/turbina/v2/tipos` | `getTurbineTypesByFilters` | Buscar todas las Turbinas Tipos del sistema Infotécnica Instalaciones con paginado | Buscar todas las Turbinas Tipos con paginado. (Se muestra por defecto 10 registros por página). | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2TurbineTypeDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades Medidas | `v1` | `GET` | `/activos/unidades-medidas/v1` | `getMeasurementUnit` | Devuelve una lista de Unidades Medidas a partir de los filtros de búsqueda del sistema Infotécnica Instalaciones. | Devuelve una lista de Unidades Medidas dado los parámetros de búsqueda del sistema Infotécnica Instalaciones. | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseMeasurementUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades Medidas | `v1` | `GET` | `/activos/unidades-medidas/v1/{id}` | `getMeasurementUnitById` | Devuelve un registro de Unidades Medidas dado el Id del sistema Infotécnica Instalaciones. | Devuelve un registro de Unidades Medidas dado un Id válido del sistema Infotécnica Instalaciones. | id | Sí (global: api-key) | 200, 400, 404, 500 | `MeasurementUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades Medidas | `v2` | `GET` | `/activos/unidades-medidas/v2` | `getMeasurementUnit2` | Devuelve una lista de Unidades Medidas a partir de los filtros de búsqueda del sistema Infotécnica Instalaciones. | Devuelve una lista de Unidades Medidas dado los parámetros de búsqueda del sistema Infotécnica Instalaciones. (Se muestra por defecto 10 registros por página). | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2MeasurementUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `v1` | `GET` | `/activos/unidades-generadoras/v1` | `getGeneratingUnitsByFilters_1` | Buscar todas las Unidades Generadoras del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todas las Unidades Generadoras por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, idPropietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseGeneratingUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `v1` | `GET` | `/activos/unidades-generadoras/v1/pmgd` | `getGeneratingUnitsPMGDByFilters_1` | Buscar todas las Unidades Generadoras PMGD del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todas las Unidades Generadoras PMGD por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, idPropietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseGeneratingUnitPMGDDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `v1` | `GET` | `/activos/unidades-generadoras/v1/pmgd/{id}` | `getGeneratingUnitPMGDById_1` | Buscar una Unidad Generadora PMGD del sistema Infotécnica Instalaciones por ID | Retorna una sola Unidad Generadora PMGD | id | Sí (global: api-key) | 200, 400, 404, 500 | `GeneratingUnitPMGDDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `v1` | `GET` | `/activos/unidades-generadoras/v1/{id}` | `getGeneratingUnitById_1` | Buscar una Unidad Generadora del sistema Infotécnica Instalaciones por ID | Retorna una sola Unidad Generadora | id | Sí (global: api-key) | 200, 400, 404, 500 | `GeneratingUnitDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `v2` | `GET` | `/activos/unidades-generadoras/v2` | `getGeneratingUnitsByFilters` | Buscar todas las Unidades Generadoras del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todas las Unidades Generadoras por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, id_propietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2GeneratingUnitDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `v2` | `GET` | `/activos/unidades-generadoras/v2/pmgd` | `getGeneratingUnitsPMGDByFilters` | Buscar todas las Unidades Generadoras PMGD del sistema Infotécnica Instalaciones por filtros de búsqueda y ordenamiento | Buscar todas las Unidades Generadoras PMGD por filtros de búsqueda y ordenamiento. (Se muestra por defecto 10 registros por página). | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, id_propietario, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2GeneratingUnitPMGDDtoV2` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `v2` | `GET` | `/activos/unidades-generadoras/v2/pmgd/{id}` | `getGeneratingUnitPMGDById` | Buscar una Unidad Generadora PMGD del sistema Infotécnica Instalaciones por ID | Retorna una sola Unidad Generadora PMGD | id | Sí (global: api-key) | 200, 400, 404, 500 | `GeneratingUnitPMGDDto` |
| PLANIFICACION | Infotécnica Instalaciones | Unidades-Generadoras | `v2` | `GET` | `/activos/unidades-generadoras/v2/{id}` | `getGeneratingUnitById` | Buscar una Unidad Generadora del sistema Infotécnica Instalaciones por ID | Retorna una sola Unidad Generadora | id | Sí (global: api-key) | 200, 400, 404, 500 | `GeneratingUnitDto` |
| PLANIFICACION | Infotécnica Web | Calidad | `v1` | `GET` | `/activos-web/calidad/v1/empresas` | `getCompanyQuality_1` | Devuelve una lista de calidad de empresas del sistema Infotécnica Web, a partir de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | Devuelve una lista de calidad de empresas | ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCompanyQualityDto` |
| PLANIFICACION | Infotécnica Web | Calidad | `v1` | `GET` | `/activos-web/calidad/v1/general` | `getGeneralQuality_1` | Devuelve el resumen de calidad general del sistema Infotécnica Web | Devuelve el resumen de calidad general | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `GeneralQualityDto` |
| PLANIFICACION | Infotécnica Web | Calidad | `v1` | `GET` | `/activos-web/calidad/v1/rangos-empresas` | `getRangeCompanyQuality_1` | Devuelve el resumen de calidad por rango del sistema Infotécnica Web | Devuelve el resumen de calidad por rango | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `array[RangeCompanyQualityDto]` |
| PLANIFICACION | Infotécnica Web | Calidad | `v1` | `GET` | `/activos-web/calidad/v1/tipo-instalaciones` | `getInstallationType_1` | Devuelve una lista de calidad de tipos de instalación del sistema Infotécnica Web, a partir de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | Devuelve una lista de calidad de tipos de instalación, a partir de los filtros de búsqueda | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationTypeQualityDto` |
| PLANIFICACION | Infotécnica Web | Calidad | `v2` | `GET` | `/activos-web/calidad/v2/empresas` | `getCompanyQuality` | Devuelve una lista de calidad de empresas del sistema Infotécnica Web, a partir de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | Devuelve una lista de calidad de empresas | ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CompanyQualityDto2` |
| PLANIFICACION | Infotécnica Web | Calidad | `v2` | `GET` | `/activos-web/calidad/v2/general` | `getGeneralQuality` | Devuelve el resumen de calidad general del sistema Infotécnica Web | Devuelve el resumen de calidad general | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `GeneralQualityDto2` |
| PLANIFICACION | Infotécnica Web | Calidad | `v2` | `GET` | `/activos-web/calidad/v2/rangos-empresas` | `getRangeCompanyQuality` | Devuelve el resumen de calidad por rango del sistema Infotécnica Web | Devuelve el resumen de calidad por rango | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `array[RangeCompanyQualityDto2]` |
| PLANIFICACION | Infotécnica Web | Calidad | `v2` | `GET` | `/activos-web/calidad/v2/tipo-instalaciones` | `getInstallationType` | Devuelve una lista de calidad de tipos de instalación del sistema Infotécnica Web, a partir de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | Devuelve una lista de calidad de tipos de instalación, a partir de los filtros de búsqueda | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationTypeQualityDto2` |
| PLANIFICACION | Infotécnica Web | Centrales | `v1` | `GET` | `/activos-web/centrales/v1/estadisticas` | `getAllStatisticsOfCentrals_1` | Buscar todas las estadísticas de centrales del sistema Infotécnica Web por filtros de búsqueda | Buscar todas las estadísticas de centrales por filtros de búsqueda | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `StatisticsCentralsDto` |
| PLANIFICACION | Infotécnica Web | Centrales | `v1` | `GET` | `/activos-web/centrales/v1/extendida` | `getAllCentralsExtended_1` | Buscar todas las centrales extendidas del sistema Infotécnica Web por filtros de búsqueda y ordenamiento | Buscar todas las centrales extendidas por filtros de búsqueda y ordenamiento | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCentralExtendedDto` |
| PLANIFICACION | Infotécnica Web | Centrales | `v1` | `GET` | `/activos-web/centrales/v1/extendida/{id}` | `getExtendedCentralById_1` | Buscar central extendida del sistema Infotécnica Web por ID | Retorna una sola central extendida | id | Sí (global: api-key) | 200, 400, 404, 500 | `CentralExtendedDto` |
| PLANIFICACION | Infotécnica Web | Centrales | `v1` | `GET` | `/activos-web/centrales/v1/puntos` | `getAllPointsOfCentrals_1` | Buscar todos los puntos de centrales del sistema Infotécnica Web | Buscar todos los puntos de centrales | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `array[PointsCentralsDto]` |
| PLANIFICACION | Infotécnica Web | Centrales | `v2` | `GET` | `/activos-web/centrales/v2/estadisticas` | `getAllStatisticsOfCentrals` | Buscar todas las estadísticas de centrales del sistema Infotécnica Web por filtros de búsqueda | Buscar todas las estadísticas de centrales por filtros de búsqueda | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `StatisticsCentralsDto2` |
| PLANIFICACION | Infotécnica Web | Centrales | `v2` | `GET` | `/activos-web/centrales/v2/extendida` | `getAllCentralsExtended` | Buscar todas las centrales extendidas del sistema Infotécnica Web por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | Buscar todas las centrales extendidas por filtros de búsqueda y ordenamiento.Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CentralExtendedDto2` |
| PLANIFICACION | Infotécnica Web | Centrales | `v2` | `GET` | `/activos-web/centrales/v2/extendida/{id}` | `getExtendedCentralById` | Buscar central extendida del sistema Infotécnica Web por ID | Retorna una sola central extendida | id | Sí (global: api-key) | 200, 400, 404, 500 | `CentralExtendedDto2` |
| PLANIFICACION | Infotécnica Web | Centrales | `v2` | `GET` | `/activos-web/centrales/v2/puntos` | `getAllPointsOfCentrals` | Buscar todos los puntos de centrales del sistema Infotécnica Web | Buscar todos los puntos de centrales | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `array[PointsCentralsDto]` |
| PLANIFICACION | Infotécnica Web | Completitud | `v1` | `GET` | `/activos-web/completitud/v1/calidad-instalaciones` | `getCompletenessQualityInstallationByFilters` | Buscar las Completitudes Calidad Instalaciones | Buscar las Completitudes Calidad Instalaciones | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessQualityInstallationDto2` |
| PLANIFICACION | Infotécnica Web | Completitud | `v1` | `GET` | `/activos-web/completitud/v1/empresas` | `getCompletenessCompanyByFilters` | Buscar las Completitudes Empresas | Buscar las Completitudes Empresas | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessCompanyDto` |
| PLANIFICACION | Infotécnica Web | Completitud | `v1` | `GET` | `/activos-web/completitud/v1/tipo-instalaciones` | `getCompletenessInstallationType` | Buscar las Completitudes Instalaciones | Buscar las Completitudes Instalaciones | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessInstallationTypeDto` |
| PLANIFICACION | Infotécnica Web | Completitud | `v2` | `GET` | `/activos-web/completitud/v2/calidad-instalaciones` | `getCompletenessQualityInstallationByFilters_1` | Buscar las Completitudes Calidad Instalaciones del sistema Infotécnica Web. | Buscar las Completitudes Calidad Instalaciones. (Se muestra por defecto 10 registros por página). | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CompletenessQualityInstallationDto3` |
| PLANIFICACION | Infotécnica Web | Completitud | `v2` | `GET` | `/activos-web/completitud/v2/empresas` | `getCompletenessCompanyByFilters_1` | Buscar las Completitudes Empresas del sistema Infotécnica Web | Buscar las Completitudes Empresas. (Se muestra por defecto 10 registros por página). | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CompletenessCompanyDto2` |
| PLANIFICACION | Infotécnica Web | Completitud | `v2` | `GET` | `/activos-web/completitud/v2/general` | `getCompletenessGeneral_1` | Obtener resumen completitud general del sistema Infotécnica Web | Obtener resumen completitud general | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `CompletenessGeneralDto2` |
| PLANIFICACION | Infotécnica Web | Completitud | `v2` | `GET` | `/activos-web/completitud/v2/rangos-empresas` | `getRangeCompletenessCompany_1` | Obtener resumen completitud empresas por rango del sistema Infotécnica Web | Obtener resumen completitud empresas por rango | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `array[RangeCompletenessCompanyDto2]` |
| PLANIFICACION | Infotécnica Web | Completitud | `v2` | `GET` | `/activos-web/completitud/v2/tipo-instalaciones` | `getCompletenessInstallationType_1` | Buscar las Completitudes Instalaciones del sistema Infotécnica Web | Buscar las Completitudes Instalaciones. (Se muestra por defecto 10 registros por página). | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CompletenessInstallationTypeDto2` |
| PLANIFICACION | Infotécnica Web | Completitud | `` | `GET` | `/activos-web/completitudv1/general` | `getCompletenessGeneral` | Obtener resumen completitud general | Obtener resumen completitud general | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `CompletenessGeneralDto` |
| PLANIFICACION | Infotécnica Web | Completitud | `` | `GET` | `/activos-web/completitudv1/rangos-empresas` | `getRangeCompletenessCompany` | Obtener resumen completitud empresas por rango | Obtener resumen completitud empresas por rango | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `array[RangeCompletenessCompanyDto]` |
| PLANIFICACION | Infotécnica Web | Conexiones | `v1` | `GET` | `/activos-web/conexiones/v1/derivacion/extended` | `getConnectionExtended` | Obtener lista de conexiones de Infotecnica Web | Retorna una lista de conexiones | id, idPropietario, nemotecnico, nemotecnicoIContains, nombre, nombreIContains, ordering, search, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseWebConnectionDto` |
| PLANIFICACION | Infotécnica Web | Conexiones | `v1` | `GET` | `/activos-web/conexiones/v1/derivacion/extended/{id}` | `getConnectionExtendedById` | Obtener una conexion dado el id de Infotecnica Web | Retorna una conexion dado el id | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `WebConnectionDto` |
| PLANIFICACION | Infotécnica Web | Conexiones | `v2` | `GET` | `/activos-web/conexiones/v2/derivacion/extended` | `getConnectionExtended` | Devuelve una lista paginada de conexiones del sistema Infotécnica Web, a partir de los filtros de búsqueda. Se muestran 10 elementos por página. | Devuelve una lista de conexiones del sistema Infotécnica Web, dado los parámetros de búsqueda. | id, id_propietario, nemotecnico, nemotecnico_i_contains, nombre, nombre_i_contains, ordering, search, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2WebConnectionDto2` |
| PLANIFICACION | Infotécnica Web | Conexiones | `v2` | `GET` | `/activos-web/conexiones/v2/derivacion/extended/{id}` | `getConnectionExtendedById` | Devuelve una conexion del sistema Infotécnica Web dado el Id | Devuelve una conexion del sistema Infotécnica Web, dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `WebConnectionDto2` |
| PLANIFICACION | Infotécnica Web | Empresas | `v1` | `GET` | `/activos-web/empresas/v1/statistics` | `getEnterpriseCompletenessByFilter` | Devuelve empresas del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve empresas a partir de los filtros de búsqueda | page | Sí (global: api-key) | 200, 400, 404, 500 | `EnterpriseWebDto` |
| PLANIFICACION | Infotécnica Web | Empresas | `v2` | `GET` | `/activos-web/empresas/v2/statistics` | `getEnterpriseCompletenessByFilter_1` | Devuelve empresas del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve empresas a partir de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | page | Sí (global: api-key) | 200, 400, 404, 500 | `EnterpriseWebDtoV2` |
| PLANIFICACION | Infotécnica Web | Historicos | `v1` | `GET` | `/activos-web/historicos/v1/aplicada-data` | `getHistoricalByFilter` | Devuelve historicos del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve historicos del sistema Infotécnica Web, a partir de los filtros de búsqueda | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseHistoricalDto` |
| PLANIFICACION | Infotécnica Web | Historicos | `v1` | `GET` | `/activos-web/historicos/v1/aplicada-data/generar-reporte` | `getReportHistorical` | Devuelve reporte de historicos del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve reporte de historicos del sistema Infotécnica Web, a partir de los filtros de búsqueda | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseReportHistoricalDto` |
| PLANIFICACION | Infotécnica Web | Historicos | `v2` | `GET` | `/activos-web/historicos/v2/aplicada-data` | `getHistoricalByFilter_1` | Devuelve históricos del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve históricos del sistema Infotécnica Web, a partir de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2HistoricalDto2` |
| PLANIFICACION | Infotécnica Web | Historicos | `v2` | `GET` | `/activos-web/historicos/v2/aplicada-data/generar-reporte` | `getReportHistorical_1` | Devuelve reporte de históricos del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve reporte de históricos del sistema Infotécnica Web, a partir de los filtros de búsqueda. (Se muestra por defecto 10 registros por página). | fecha_modificacion_gte, fecha_modificacion_lte, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2ReportHistoricalDto2` |
| PLANIFICACION | Infotécnica Web | Lineas | `v1` | `GET` | `/activos-web/lineas/v1/estadisticas` | `getAllStatisticsOfLinesWeb` | Buscar todas las estadísticas de líneas  de Infotecnica Web | Buscar todas las estadísticas de líneas | Sin parámetros principales o ver detalle | Sí (endpoint: api-key) | 200, 400, 404, 500 | `StatisticsLineDto` |
| PLANIFICACION | Infotécnica Web | Lineas | `v2` | `GET` | `/activos-web/lineas/v2/estadisticas` | `getAllStatisticsOfLines` | Buscar todas las estadísticas de líneas del sistema Infotécnica Web | Buscar todas las estadísticas de líneas | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `StatisticsLineDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v1` | `GET` | `/activos-web/proyectos/v1` | `getProjectFilter_1` | Devuelve una lista de proyectos del sistema Infotecnica Web, a partir de los filtros de búsqueda | Devuelve una lista de proyectos a partir de los filtros de búsqueda | id, nombre, nombreIContains, ordering, search, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseProjectDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v1` | `GET` | `/activos-web/proyectos/v1/completitud-calidad` | `getCompleteness_1` | Obtener lista completitud calidad del sistema Infotecnica Web, a partir de los filtros de búsqueda | Retorna una lista completitud calidad a partir de los filtros de búsqueda | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessQualityDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v1` | `GET` | `/activos-web/proyectos/v1/completitud-calidad/empresas` | `getProjectCompletenessEnterprise_1` | Obtener lista proyectos completitud calidad empresas del sistema Infotecnica Web, a partir de los filtros de búsqueda | Retorna una lista proyectos completitud calidad empresas a partir de los filtros de búsqueda | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessQualityEnterpriseDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v1` | `GET` | `/activos-web/proyectos/v1/completitud-calidad/estudio-pes-anexos` | `getProjectAnnexStudy_1` | Devuelve una lista proyectos estudios anexos del sistema Infotecnica Web, para los filtros de búsqueda. | Devuelve una lista proyectos estudios anexos para los filtros de búsqueda. | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessQualityAnnexDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v1` | `GET` | `/activos-web/proyectos/v1/completitud-calidad/instalaciones` | `getProjectInstallation_1` | Devuelve una lista de proyectos completitud instalación del sistema Infotecnica Web, para los filtros de búsqueda. | Devuelve una lista de proyectos completitud instalación para los filtros de búsqueda. | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseCompletenessQualityInstallationDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v1` | `GET` | `/activos-web/proyectos/v1/completitud-calidad/{id}` | `getCompletenessId_1` | Obtener completitud calidad del sistema Infotecnica Web, dado el id | Retorna completitud calidad dado el id | id | Sí (global: api-key) | 200, 400, 404, 500 | `CompletenessQualityDetailDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v1` | `GET` | `/activos-web/proyectos/v1/{id}` | `getProjectById_1` | Devuelve un proyecto del sistema Infotécnica Web, dado el id | Retorna un proyecto dado el id | id | Sí (global: api-key) | 200, 400, 404, 500 | `ProjectDetailDto` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v2` | `GET` | `/activos-web/proyectos/v2` | `getProjectFilter` | Devuelve una lista de proyectos del sistema Infotecnica Web, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de proyectos a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, ordering, search, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2ProjectDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v2` | `GET` | `/activos-web/proyectos/v2/completitud-calidad` | `getCompleteness` | Obtener lista completitud calidad del sistema Infotecnica Web, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Retorna una lista completitud calidad a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CompletenessQualityDto3` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v2` | `GET` | `/activos-web/proyectos/v2/completitud-calidad/empresas` | `getProjectCompletenessEnterprise` | Obtener lista proyectos completitud calidad empresas del sistema Infotecnica Web, a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Retorna una lista proyectos completitud calidad empresas a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CompletenessQualityEnterpriseDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v2` | `GET` | `/activos-web/proyectos/v2/completitud-calidad/estudio-pes-anexos` | `getProjectAnnexStudy` | Devuelve una lista proyectos estudios anexos del sistema Infotecnica Web, para los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista proyectos estudios anexos para los filtros de búsqueda.Se muestra por defecto 10 registros por página | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CompletenessQualityAnnexDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v2` | `GET` | `/activos-web/proyectos/v2/completitud-calidad/instalaciones` | `getProjectInstallation` | Devuelve una lista de proyectos completitud instalación del sistema Infotecnica Web, para los filtros de búsqueda.Se muestra por defecto 10 registros por página | Devuelve una lista de proyectos completitud instalación para los filtros de búsqueda.Se muestra por defecto 10 registros por página | page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2CompletenessQualityInstallationDto4` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v2` | `GET` | `/activos-web/proyectos/v2/completitud-calidad/{id}` | `getCompletenessId` | Obtener completitud calidad del sistema Infotecnica Web, dado el id | Retorna completitud calidad dado el id | id | Sí (global: api-key) | 200, 400, 404, 500 | `CompletenessQualityDetailDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos | `v2` | `GET` | `/activos-web/proyectos/v2/{id}` | `getProjectById` | Devuelve un proyecto del sistema Infotécnica Web, dado el id | Retorna un proyecto dado el id | id | Sí (global: api-key) | 200, 400, 404, 500 | `ProjectDetailDto2` |
| PLANIFICACION | Infotécnica Web | Proyectos Instalaciones | `v1` | `GET` | `/activos-web/proyectos-instalaciones/v1` | `getInstallationProjectByFilter` | Devuelve una lista de proyectos instalaciones del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve una lista de proyectos instalaciones del sistema Infotécnica Web, dado los parámetros de búsqueda. | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseInstallationProjectDto` |
| PLANIFICACION | Infotécnica Web | Proyectos Instalaciones | `v1` | `GET` | `/activos-web/proyectos-instalaciones/v1/{id}` | `getInstallationProjectById` | Devuelve un proyecto instalacion del sistema Infotécnica Web dado el Id | Devuelve un proyecto instalacion del sistema Infotécnica Web, dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationProjectDto` |
| PLANIFICACION | Infotécnica Web | Proyectos Instalaciones | `v2` | `GET` | `/activos-web/proyectos-instalaciones/v2` | `getInstallationProjectByFilter_1` | Devuelve una lista de proyectos instalaciones del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve una lista de proyectos instalaciones del sistema Infotécnica Web, dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2InstallationProjectDtoV2` |
| PLANIFICACION | Infotécnica Web | Proyectos Instalaciones | `v2` | `GET` | `/activos-web/proyectos-instalaciones/v2/{id}` | `getInstallationProjectById_1` | Devuelve un proyecto instalacion del sistema Infotécnica Web dado el Id | Devuelve un proyecto instalacion del sistema Infotécnica Web, dado un Id válido | id | Sí (global: api-key) | 200, 400, 404, 500 | `InstallationProjectDtoV2` |
| PLANIFICACION | Infotécnica Web | Substation | `v1` | `GET` | `/activos-web/sub-estaciones/v1/estadisticas` | `getSubstationExtendedStatic` | Devuelve reporte de subestaciones por region, empresa y elementos ssee | Devuelve reporte de subestaciones por region, empresa y elementos ssee | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `SubstationStaticDto` |
| PLANIFICACION | Infotécnica Web | Substation | `v1` | `GET` | `/activos-web/sub-estaciones/v1/extendida` | `getSubstationExtended` | Devuelve una lista de subestaciones externas a partir de los filtros de búsqueda | Devuelve una lista de subestaciones dado los parameters de búsqueda. | id, nemotecnico, nemotecnicoIContains, idPropietario, nombre, nombreIContains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseWebSubstationDto` |
| PLANIFICACION | Infotécnica Web | Substation | `v1` | `GET` | `/activos-web/sub-estaciones/v1/extendida/{id}` | `getSubstationById` | Devuelve un subestacion externa dado el Id | Devuelve un subestacion externa dado un Id valido | id | Sí (global: api-key) | 200, 400, 404, 500 | `WebSubstationDto` |
| PLANIFICACION | Infotécnica Web | Substation | `v2` | `GET` | `/activos-web/sub-estaciones/v2/estadisticas` | `getSubstationExtendedStatic` | Devuelve reporte de subestaciones del sistema Infotécnica Web por region, empresa y elementos ssee | Devuelve reporte de subestaciones por region, empresa y elementos ssee | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 400, 404, 500 | `SubstationStaticDtoV2` |
| PLANIFICACION | Infotécnica Web | Substation | `v2` | `GET` | `/activos-web/sub-estaciones/v2/extendida` | `getSubstationExtended` | Devuelve una lista de subestaciones externas del sistema Infotécnica Web a partir de los filtros de búsqueda | Devuelve una lista de subestaciones dado los parámetros  de búsqueda. (Se muestra por defecto 10 registros por página). | id, nemotecnico, nemotecnico_i_contains, id_propietario, nombre, nombre_i_contains, search, ordering, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2WebSubstationDtoV2` |
| PLANIFICACION | Infotécnica Web | Substation | `v2` | `GET` | `/activos-web/sub-estaciones/v2/extendida/{id}` | `getSubstationById` | Devuelve un subestacion externa del sistema Infotécnica Web dado el Id | Devuelve un subestacion externa dado un Id valido | id | Sí (global: api-key) | 200, 400, 404, 500 | `WebSubstationDtoV2` |
| PLANIFICACION | Infotécnica Web | Tap | `v1` | `GET` | `/activos-web/taps/v1/extended` | `getTapByFilter_1` | Devuelve una lista de taps del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve una lista de taps dado los parámetros de búsqueda. | id, nombre, nemotecnico, search, ordering, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseWebTapDto` |
| PLANIFICACION | Infotécnica Web | Tap | `v1` | `GET` | `/activos-web/taps/v1/extended/{id}` | `getTapById_1` | Devuelve un tap del sistema Infotécnica Web, dado el Id | Devuelve un tap dado un Id válido | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `WebTapDto` |
| PLANIFICACION | Infotécnica Web | Tap | `v2` | `GET` | `/activos-web/taps/v2/extended` | `getTapByFilter_1` | Devuelve una lista de taps del sistema Infotécnica Web, a partir de los filtros de búsqueda | Devuelve una lista de taps dado los parámetros de búsqueda. (Se muestra por defecto 10 registros por página). | id, nombre, nemotecnico, search, ordering, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponse2WebTapDto2` |
| PLANIFICACION | Infotécnica Web | Tap | `v2` | `GET` | `/activos-web/taps/v2/extended/{id}` | `getTapById` | Devuelve un tap del sistema Infotécnica Web, dado el Id | Devuelve un tap dado un Id válido | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `WebTapDto2` |
| PLANIFICACION | Infotécnica Web | Teleprotecciones | `v1` | `GET` | `/activos-web/teleprotecciones/v1/tipos-fichas-tecnicas` | `getTechnicalSheets_1` | Obtener lista de tipos fichas tecnicas | Retorna una lista de tipos fichas tecnicas | id, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseTypesTechnicalSheetsDto` |
| PLANIFICACION | Infotécnica Web | Teleprotecciones | `v1` | `GET` | `/activos-web/teleprotecciones/v1/tipos-fichas-tecnicas/{id}` | `getTechnicalSheetsById_1` | Devuelve un un tipo de ficha tecnica del sistema Infotécnica Web dado el Id | Devuelve un tipo de ficha tecnica del sistema Infotécnica Web, dado un Id válido | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `TypesTechnicalSheetsDto` |
| PLANIFICACION | Infotécnica Web | Teleprotecciones | `v2` | `GET` | `/activos-web/teleprotecciones/v2/tipos-fichas-tecnicas` | `getTechnicalSheets` | Obtener lista de tipos fichas tecnicas | Retorna una lista de tipos fichas tecnicas. (Se muestra por defecto 10 registros por página). | id, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponse2TypesTechnicalSheetsDtoV2` |
| PLANIFICACION | Infotécnica Web | Teleprotecciones | `v2` | `GET` | `/activos-web/teleprotecciones/v2/tipos-fichas-tecnicas/{id}` | `getTechnicalSheetsById` | Devuelve un un tipo de ficha tecnica del sistema Infotécnica Web dado el Id | Devuelve un tipo de ficha tecnica del sistema Infotécnica Web, dado un Id válido | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `TypesTechnicalSheetsDtoV2` |
| PLANIFICACION | Infotécnica Web | Tramos | `v1` | `GET` | `/activos-web/tramos/v1/extended` | `getSectionStretchFilter_1` | Devuelve una lista de secciones  del sistema Infotécnica Web a partir de los filtros de búsqueda | Devuelve una lista de secciones dado los parámetros de búsqueda. | id, nombre, nombreIContains, nemotecnico, nemotecnicoIContains, ordering, search, page | Sí (endpoint: api-key) | 200, 400, 404, 500 | `PagedResponseWebSectionDto` |
| PLANIFICACION | Infotécnica Web | Tramos | `v1` | `GET` | `/activos-web/tramos/v1/extended/{id}` | `getSectionStretchById` | Obtener una seccion tramo dado el id de Infotecnica Web | Retorna una seccion tramo dado el id | id | Sí (endpoint: api-key) | 200, 400, 404, 500 | `WebSectionDto` |
| PLANIFICACION | Infotécnica Web | Tramos | `v2` | `GET` | `/activos-web/tramos/v2/extended` | `getSectionStretchFilter` | Devuelve una lista de secciones  del sistema Infotécnica Web a partir de los filtros de búsqueda.Se muestra por defecto 10 registros por página | Se muestra por defecto 10 registros por página | id, nombre, nombre_i_contains, nemotecnico, nemotecnico_i_contains, ordering, search, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponse2WebSectionDto2` |
| PLANIFICACION | Infotécnica Web | Tramos | `v2` | `GET` | `/activos-web/tramos/v2/extended/{id}` | `getSectionStretchById` | Devuelve una sección del sistema Infotécnica Web dado el id | Devuelve una sección del sistema Infotécnica Web dado el id | id | Sí (global: api-key) | 200, 400, 404, 500 | `WebSectionDto2` |
| SIP | Sistema de Información Pública | Capacidad | `v4` | `GET` | `/capacidad-instalada/v4/findByDate` | `` | Encuentra entradas de capacidad instalada para un rango de fechas | Corresponde al concepto capacidad instalada que es la capacidad disponible para el SEN de cada central eléctrica expresada por su potencia máxima. Al sumar estas potencias se obtiene la capacidad instalada total del SEN que se actualiza cada mes, del area de negocio Ejecución Estratégica | page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `CapacidadInstaladaResponse` |
| SIP | Sistema de Información Pública | Cargos Distribución | `v4` | `GET` | `/cargos-distribucion-ar/v4/findByDate` | `` | Encuentra las entradas de cargos distribucion ar para un rango de fechas | Corresponde al concepto cargos distribucion ar que son cargos aplicables a todas las tarifas, incluido en el precio de energía a nivel generación – transmisión, y calculados semestralmente en los procesos de cálculo de los precios de nudos promedio. En este caso AR significa “Ajuste o Recargo”, TD significa “Transferencias entre distribuidoras” y CDRGL significa “ Cargo o descuento por reconocimiento de generación local que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `CargosDistribucionARResponse` |
| SIP | Sistema de Información Pública | Cargos Distribución | `v4` | `GET` | `/cargos-distribucion-etr/v4/findByDate` | `` | Encuentra entradas de cargos de distribucion etr para un rango de fechas | Corresponde al concepto cargos de distribucion etr que es un cargo incluido en la estructura tarifaria mediante el Valor Agregado de Distribución (V.A.D.), y calculado semestralmente en los procesos de cálculo de los precios de nudos promedio, aplicable a todos los clientes regulados e incluido en el cargo de potencia de las tarifas eléctricas. En este cado ETR significa “Equidad Tarifaria Residencial que se actualiza mensualmente, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `CargosDistribucionETRResponse` |
| SIP | Sistema de Información Pública | Centrales | `v4` | `GET` | `/centrales/v4/findByDate` | `` | Encuentra todas las entradas de centrales | Devuelve una lista de todas las entradas de centrales, una central generadora es una instalación diseñada para producir energía eléctrica a gran escala que se actualiza cada dia o mes, del area de negocio Gestión de Acceso Abierto y Conexiones | page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `CentralesResponse` |
| SIP | Sistema de Información Pública | Combustibles | `v3` | `GET` | `/costo-combustible/v3/findAll` | `` |  | Son los costos declarados por los Coordinados por día en un mes de los combustibles utilizados para la generación eléctrica del SEN (carbón, gas natural, diésel, otros). Información actualizada de forma diaria. | startDate, endDate, page | Sí (global: api-key) | 200, 400, 404, 500 | `ResponseCostoCombustibles` |
| SIP | Sistema de Información Pública | Combustibles | `v4` | `GET` | `/stock-combustible/v4/findByDate` | `` | Encuentra entradas de stock combustible para un rango de fechas | Corresponde al concepto stock combustible, disponibilidad de los diferentes tipos de combustible para las empresas generadoras del Sistema Eléctrico Nacional. La disponibilidad se expresa en función a los tipos de combustibles existentes utilizados para la generación eléctrica del SEN que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `StockCombustibleResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `v4` | `GET` | `/cmg-programado-pcp/v4/findByDate` | `` | Encuentra entradas de costo marginal programado pcp para un rango de fechas | Corresponde al concepto costo marginal programado pcp, Refleja el costo proyectado para un conjunto de barras del SEN para el día siguiente, de suministrar un kilowatt hora (kWh) adicional al sistema eléctrico para una hora determinada, expresado en USD/MWH que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `CMGProgramadoPCPResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `v4` | `GET` | `/cmg-programado-pid/v4/findByDate` | `` | Encuentra entradas de costo marginal programado pid para un rango de fechas | Corresponde al concepto costo marginal programado pid que Refleja el costo proyectado para un conjunto de barras del SEN para el día siguiente, de suministrar un kilowatt hora (kWh) adicional al sistema eléctrico para una hora determinada, expresado en USD/MWH, ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `CMGProgramadoPIDResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `v4` | `GET` | `/costo-marginal-online/v4/findByDate` | `` | Encuentra entradas de costo marginal en linea para un rango de fechas | Corresponde al concepto costo marginal en linea que es el costo de producir una unidad adicional de energía en el sistema para abastecer la demanda, para eso se necesita elegir la central que tiene el precio más alto, esta revisión del abastecimiento se da cada 15 minutos. que se actualiza cada 15 minutos, del area de negocio Gestión de Mercado | startDate, endDate, page, limit, bar_transf | Sí (global: api-key) | 200, 401, 403, 500 | `CMGOnlineResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `v3` | `GET` | `/costo-marginal-programado/v3/findAll` | `` |  | Refleja el costo proyectado para un conjunto de barras del SEN para el día siguiente, de suministrar un kilo watt hora (kWh) adicional al sistema eléctrico para una hora determinada, expresado en USD/MWH. | endDate, startDate, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseScheduleMarginalCostDTO` |
| SIP | Sistema de Información Pública | Costo Marginal | `v4` | `GET` | `/costo-marginal-programado/v4/findAllHourly` | `` |  | Refleja el costo proyectado por hora para cada barra del SEN en el día indicado. | date | Sí (global: api-key) | 200, 400, 404, 500 | `HourlyDataResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `v3` | `GET` | `/costo-marginal-proyectado/v3/findAll` | `` |  | Refleja el costo proyectado para un conjunto de barras del SEN para el día siguiente, de suministrar un kilo watt hora (kWh) adicional al sistema eléctrico para una hora determinada, expresado en USD/MWH. Información actualizada de forma diaria (4 am.) | starDate, endDate, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseProjectedMarginalCostDto` |
| SIP | Sistema de Información Pública | Costo Marginal | `v4` | `GET` | `/costo-marginal-proyectado/v4/findByDate` | `` |  | Costo Marginal proyectado para los distintos escenarios evaluados en el Informe de Expansión de la Transmisión para un periodo de 20 años | anio_carga, anio, page, limit | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseProjectedMarginalCostDtoV4` |
| SIP | Sistema de Información Pública | Costo Marginal | `v4` | `GET` | `/costo-marginal-real/v4/findByDate` | `` | Encuentra entradas de costo marginal real para un rango de fechas | Corresponde al concepto costo marginal real, el Costo Marginal Real corresponde al valor expresado en USD/MWh, obtenido a partir del Costo Marginal en Línea. Se determina una vez que se han resuelto las observaciones recibidas por el Coordinador. Este costo es el que se utiliza, luego de su conversión a pesos chilenos, para la valorización de la energía en el Balance de Transferencias. que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit, type, bar_transf | Sí (global: api-key) | 200, 401, 403, 500 | `CMGRealResponse` |
| SIP | Sistema de Información Pública | Costo Marginal | `v4` | `GET` | `/costos-marginales-online-8b/v4/findAll` | `` |  | Devuelve los registros de las últimas 24 horas, tomando los valores de las horas en punto (con los minutos en cero), de costo marginal online para las 8 barras 'Tarapaca 220 KV', 'Crucero 220 KV', 'Atacama 220 KV', 'Cardones 220 KV', 'P.Azucar 220 KV', 'Quillota 220 KV', 'Charrua 220 KV', 'P.Montt 220 KV'. Los resultados son ordenados de forma ascendente por fecha y hora. | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 404, 500 | `ResponseCostoMarginalEnLinea` |
| SIP | Sistema de Información Pública | Cotas de Embalses | `v3` | `GET` | `/cotas-embalses-reales/v3/findAll` | `` |  | Declaración horaria, realizada por los coordinados, de las cotas de los embalses que abastecen centrales generadoras conectadas al Sistema Eléctrico Nacional en m.s.n.m por hora. Información actualizada de forma horaria. | startDate, endDate, page | Sí (global: api-key) | 200, 400, 404, 500 | `ResponseCotasEmbalses` |
| SIP | Sistema de Información Pública | Cotas de Embalses | `v3` | `GET` | `/cotas-niveles-embalses-programado/v3/findAll` | `` |  | Proyección diaria de las cotas de los embalses que abastecen centrales generadoras conectadas al Sistema Eléctrico Nacional en m.s.n.m por hora. Información actualizada de forma diaria (4 am.). | startDate, endDate, page | Sí (global: api-key) | 200, 400, 404, 500 | `ResponseCotasEmbalsesProgramadas` |
| SIP | Sistema de Información Pública | Demanda | `v4` | `GET` | `/demanda-neta/v4/findByDate` | `` | Encuentra entradas de demanda neta para un rango de fechas | Corresponde al concepto demanda neta, Corresponderá al valor de demanda descontando la generación de energías renovables con recursos primarios variables, como la eólica y la solar fotovoltaica y centrales hidráulicas de pasada que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `DemandaNetaResponse` |
| SIP | Sistema de Información Pública | Demanda | `v4` | `GET` | `/demanda-programada-pcp/v4/findByDate` | `` | Encuentra entradas de demanda programada pcp para un rango de fechas | Corresponde al concepto demanda programada pcp, Esto corresponde a un proyección del consumo total del SEN en MW y por hora y barra, para el día siguiente que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `DemandaProgramadaResponse` |
| SIP | Sistema de Información Pública | Demanda | `v4` | `GET` | `/demanda-programada-pid/v4/findByDate` | `` | Encuentra entradas de demanda programada pid para un rango de fechas | Corresponde al concepto demanda programada pid, Esto corresponde a un proyección del consumo total del SEN en MW por hora y barra ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `DemandaProgramadaPIDResponse` |
| SIP | Sistema de Información Pública | Demanda | `v3` | `GET` | `/demanda-proyectada/v3/findAll` | `` |  | Corresponde a la proyección de energía y demanda máxima del SEN para un periodo u horizonte de 20 años, considerando las instalaciones existentes y nuevos proyectos. Información actualizada de forma anual. | startYear, endYear, page | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseProjectedDemandDto` |
| SIP | Sistema de Información Pública | Demanda | `v4` | `GET` | `/demanda-proyectada/v4/findByDate` | `` |  | Corresponde a la proyección de energía y demanda máxima del SEN para un periodo u horizonte de 20 años, considerando las instalaciones existentes y nuevos proyectos. Información actualizada de forma anual. | anio_carga, anio, page, limit | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseProjectedDemandDtoV4` |
| SIP | Sistema de Información Pública | Demanda | `v4` | `GET` | `/demanda-real-estimada/v4/findByDate` | `` | Encuentra entradas de demanda real estimada para un rango de fechas | Corresponde al concepto demanda real estimada, Demanda Real = Consumo Real = Retiros del sistema (estimación) = Generación Bruta - Consumos propios (estimación) - Perdidas de Trasmisión (estimación) que se actualiza cada mes, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `DemandaRealEstimadaResponse` |
| SIP | Sistema de Información Pública | Embalse | `v4` | `GET` | `/embalse-programado-pcp/v4/findByDate` | `` | Encuentra entradas de embalse programado pcp para un rango de fechas | Corresponde al concepto embalse programado pcp que es objeto de acumulación de agua para generación de energía eléctrica (programado) que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `EmbalseProgramadoPCPResponse` |
| SIP | Sistema de Información Pública | Embalse | `v4` | `GET` | `/embalse-programado-pid/v4/findByDate` | `` | Encuentra entradas de embalse programado pid para un rango de fechas | Corresponde al concepto embalse programado pid que es objeto de acumulación de agua para generación de energía eléctrica (programado), ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `EmbalseProgramadoPIDResponse` |
| SIP | Sistema de Información Pública | Embalse | `v3` | `GET` | `/embalse-real/v3/findByDate` | `` | Encuentra entradas de embalse real para un rango de fechas | Corresponde al concepto embalse real que es objeto de acumulacion de agua para generacion de energia electrica (real) que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `EmbalseRealResponse` |
| SIP | Sistema de Información Pública | Embalse | `v3` | `GET` | `/embalse-real/v3/findLast` | `` | Encuentra la cota actual para los embalses Maule, Polcura, Colbun, Pangue, Rapel, Chapo, Ralco, Laja, Angostura, Machicura. | Objeto de acumulación de agua para generación de energía eléctrica (real) | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 401, 403, 500 | `EmbalseRealLastResponse` |
| SIP | Sistema de Información Pública | Embalse | `v3` | `GET` | `/embalse-real/v3/findWeekly` | `` | Encuentra el valor de la cota por semana cada lunes a las 04:00 para los ultimos tres años incluido el actual para el embalse solicitado. | Objeto de acumulación de agua para generación de energía eléctrica (real) | embalse | Sí (global: api-key) | 200, 401, 403, 500 | `EmbalseRealWeeklyResponse` |
| SIP | Sistema de Información Pública | Energía | `v4` | `GET` | `/energia-no-suministrada/v4/findByDate` | `` | Encuentra entradas de energia no suministrada para un rango de fechas | Corresponde al concepto energia no suministrada, corresponde al exceso de la Energía Interrumpida por sobre los estándares de indisponibilidad de suministro, registrada en MWh con dos cifras decimales. que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `EnergiaNoSuministradaResponse` |
| SIP | Sistema de Información Pública | Flujo Programado | `v4` | `GET` | `/flujo-programado-pcp/v4/findByDate` | `` | Encuentra entradas de flujo programado pcp para un rango de fechas | Corresponde al concepto flujo programado pcp que son flujos de energía por el sistema que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `FlujoProgramadoPCPResponse` |
| SIP | Sistema de Información Pública | Flujo Programado | `v4` | `GET` | `/flujo-programado-pid/v4/findByDate` | `` | Encuentra entradas de flujo programado pid para un rango de fechas | Corresponde al concepto flujo programado pid que son flujos de energía por el sistema, ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `FlujoProgramadoPIDResponse` |
| SIP | Sistema de Información Pública | Generación | `v3` | `GET` | `/generacion-actual/v3/getSumGeneration` | `` |  | Devuelve una lista de valores sumarizados de las horas de generaciones reales entre fechas de inicio y fin | startDate, endDate, technology, page, pageSize | Sí (global: api-key) | 200, 400, 404, 500 | `ResponseGeneracionActual2` |
| SIP | Sistema de Información Pública | Generación | `v3` | `GET` | `/generacion-maxima-mensual/v3/findAll` | `` |  | Devuelve las horas y dias donde se alcanzó el máximo de las generaciones reales entre fechas de inicio y fin, buscando por Tipo de Tecnología. El resultado devuelto por la búsqueda se encuentra ordenado de manera descendente por fecha y hora. | startDate, endDate, technology, page, pageSize | Sí (global: api-key) | 200, 400, 404, 500 | `PagedResponseMonthlyMaximumActualGeneration` |
| SIP | Sistema de Información Pública | Generación | `v4` | `GET` | `/generacion-programada-pcp/v4/findByDate` | `` | Encuentra entradas de generacion programada pcp para un rango de fechas | Corresponde al concepto generacion programada pcp, Esto corresponde a una proyección de la generación del SEN en MWH, para el día siguiente que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `GeneracionProgramadaPCPResponse` |
| SIP | Sistema de Información Pública | Generación | `v4` | `GET` | `/generacion-programada-pid/v4/findByDate` | `` | Encuentra entradas de generacion programada pid para un rango de fechas | Corresponde al concepto generacion programada pid que corresponde a una proyección de la generación del SEN en MWH, ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `GeneracionProgramadaPIDResponse` |
| SIP | Sistema de Información Pública | Generación | `v3` | `GET` | `/generacion-programada-sum/v3/getSumGeneration` | `` |  | Devuelve el valor total de la generación programada por fecha y hora, buscando por Fecha de inicio,Fecha Término y por Tipo de Tecnología.El resultado de la búsqueda se encuentra ordenado de manera descendente por fecha y hora. | startDate, endDate, technology, page, pageSize | Sí (global: api-key) | 200, 400, 404, 500 | `PageResponseScheduledGenerationv2` |
| SIP | Sistema de Información Pública | Generación | `v3` | `GET` | `/generacion-programada/v3/findAll` | `` |  | Devuelve todas las Generaciones Programadas, buscando por Fecha de inicio y Fecha Término, ordenados de manera ascendente por fecha, hora e idCentral. | startDate, endDate, page, pageSize | Sí (global: api-key) | 200, 400, 404, 500 | `PageResponseScheduledGeneration` |
| SIP | Sistema de Información Pública | Generación | `v3` | `GET` | `/generacion-real/v3/findByDate` | `` |  | Devuelve todas las Generaciones Reales que se encuentren en el rango de fechas indicados (startDate - endDate), ordenados de manera descendente por: idCentral, fecha y hora. | startDate, endDate, page, pageSize | Sí (global: api-key) | 200, 400, 404, 500 | `ResponseGeneracionActual` |
| SIP | Sistema de Información Pública | Generación | `v3` | `GET` | `/generacion-real/v3/getAnnualySum` | `` | Encuentra la sumatoria de valores por tecnologia para el dia año o fecha enviada. | OP Real. La Generación Real del Sistema Eléctrico Nacional, corresponde al resultado de la operación en tiempo real del sistema, se presenta desglosada por tipo de tecnología. Al descargar los datos se presenta el detalle horario de producción de las distintas centrales generadoras. | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 401, 403, 500 | `GeneracionRealSumResponse` |
| SIP | Sistema de Información Pública | Generación | `v3` | `GET` | `/generacion-real/v3/getDailySum` | `` | Encuentra la sumatoria de valores por tecnologia para el dia actual o fecha enviada. | OP Real. La Generación Real del Sistema Eléctrico Nacional, corresponde al resultado de la operación en tiempo real del sistema, se presenta desglosada por tipo de tecnología. Al descargar los datos se presenta el detalle horario de producción de las distintas centrales generadoras. | date | Sí (global: api-key) | 200, 401, 403, 500 | `GeneracionRealSumResponse` |
| SIP | Sistema de Información Pública | Generación | `v3` | `GET` | `/generacion-real/v3/getMonthlySum` | `` | Encuentra la sumatoria de valores por tecnologia para el mes actual o fecha enviada. | OP Real. La Generación Real del Sistema Eléctrico Nacional, corresponde al resultado de la operación en tiempo real del sistema, se presenta desglosada por tipo de tecnología. Al descargar los datos se presenta el detalle horario de producción de las distintas centrales generadoras. | Sin parámetros principales o ver detalle | Sí (global: api-key) | 200, 401, 403, 500 | `GeneracionRealSumResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `v4` | `GET` | `/indicador-desempeno-cpf/v4/findByDate` | `` | Encuentra entradas de indicador desenpeño cpf para un rango de fechas | Corresponde al concepto indicador desenpeño cpf que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `IndicadorDesempenoCPFResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `v4` | `GET` | `/indicador-desempeno-csf/v4/findByDate` | `` | Encuentra entradas de indicador desenpeño csf para un rango de fechas | Corresponde al concepto indicador desenpeño csf que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `IndicadorDesempenoCSFResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `v3` | `GET` | `/indicador-desempeno-ct/v3/findByDate` | `` | Encuentra entradas de indicador desenpeño ct para un rango de fechas | Corresponde al concepto indicador desenpeño ct que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `IndicadorDesempenoCTResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `v3` | `GET` | `/indicador-desempeno-ctf/v3/findByDate` | `` | Encuentra entradas de indicador desenpeño ctf para un rango de fechas | Corresponde al concepto indicador desenpeño ctf que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `IndicadorDesempenoCTFResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `v3` | `GET` | `/indicador-desempeno-edac/v3/findByDate` | `` | Encuentra entradas de indicador desenpeño edac para un rango de fechas | Corresponde al concepto indicador desenpeño edac que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `IndicadorDesempenoEDACResponse` |
| SIP | Sistema de Información Pública | Indicadores Desenpeño | `v3` | `GET` | `/indicador-desempeno-prs/v3/findByDate` | `` | Encuentra entradas de indicador desenpeño prs para un rango de fechas | Corresponde al concepto indicador desenpeño prs que es un cálculo de Indicadores que permiten la evaluación de la correcta prestación de los SSCC y la determinación de los factores utilizados para la remuneración de éstos que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `IndicadorDesempenoPRSResponse` |
| SIP | Sistema de Información Pública | Indices | `v4` | `GET` | `/indices-continuidad-fmik-ttik/v4/findByDate` | `` | Encuentra entradas de indices de continuidad fmik ttik para un rango de fechas | Corresponde al concepto indices de continuidad fmik ttik que son indices que permiten medir la interrupción en relación a frecuencia media y tiempo medio, estos calculos de realizan de manera mensual mantiendo siempre una historia de 12 meses móviles que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `IndicesContinuidadFMIKTTIKResponse` |
| SIP | Sistema de Información Pública | Instrucciones | `v4` | `GET` | `/instrucciones-operacionales-cmg/v4/findByDate` | `` | Encuentra entradas de instrucciones operacionales cmg para un rango de fechas | Corresponde al concepto instrucciones operacionales cmg, Listado de Instrucciones dadas a los Centros de Control para las Unidades Generadoras según los requerimientos del Sistema Eléctrico Nacional durante la Operación en Tiempo Real, que permiten la evaluación de la correcta operación y la determinación de los factores utilizados para la remuneración de los mismos que se actualiza cada dia, del area de negocio Gestión y Operación del SEN | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `InstruccionesOperacionalesCMGResponse` |
| SIP | Sistema de Información Pública | Instrucciones | `v4` | `GET` | `/instrucciones-operacionales-sscc/v4/findByDate` | `` | Encuentra entradas de instrucciones operacionales sscc para un rango de fechas | Corresponde al concepto instrucciones operacionales sscc, Listado de Instrucciones dadas a los Centros de Control para instruir a Unidades Generadoras la prestación de SSCC según los requerimientos del Sistema Eléctrico Nacional conforme a la programación de los mismos o la resignación en Tiempo Real que permiten la evaluación determinación de los factores utilizados para la remuneración de los mismos que se actualiza cada dia, del area de negocio Gestión y Operación del SEN | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `InstruccionesOperacionalesSSCCResponse` |
| SIP | Sistema de Información Pública | Limitaciones | `v4` | `GET` | `/limitaciones-transmision/v4/findByDate` | `` | Encuentra entradas de limitaciones de transmicion para un rango de fechas | Corresponde al concepto limitaciones de transmicion, Informe donde el propietario de la instalación electrica declara al coordinador alguna limitación o imposibilidad de operar el equipo en las condiciones normales que se actualiza cada dia, del area de negocio Gestión y Operación del SEN | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `LimitacionesTransmisionResponse` |
| SIP | Sistema de Información Pública | Líneas | `v4` | `GET` | `/lineas-transmision/v4/findByDate` | `` | Encuentra todas las entradas de lineas de transmision | Devuelve una lista de todas las entradas de lineas de transmision que se considera que una línea de transimisión corresponde a un enlace que permite transportar energía eléctrica entre dos extremos, los cuales pueden ser una subestación eléctrica o una central. que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `LineasTransmisionResponse` |
| SIP | Sistema de Información Pública | Oferta Proyectada | `v3` | `GET` | `/oferta-proyectada/v3/findAll` | `` |  | Plan de obras de generación detallado por región, para los distintos escenarios evaluados en el Informe de Expansión de la Transmisión. Con un horizonte a 20 años. Información actualizada de forma anual. | startYear, endYear, page | Sí (global: api-key) | 200, 400, 404, 500 | `ResponseOfertaProyectada` |
| SIP | Sistema de Información Pública | Potencia | `v4` | `GET` | `/potencia-activa-reactiva-unidad/v4/findByDate` | `` | Encuentra entradas de potencia activa reactiva unidad para un rango de fechas | Corresponde al concepto potencia activa reactiva unidad, Potencia Activa es aquella que se disipa o realiza el trabajo útil en el circuito, mientras que la potencia reactiva es la potencia requerida por las corrientes que son necesarias para establecer los campos magnéticos para su correcto funcionamiento en cada unidad del coordinador que se actualiza cada dia, del area de negocio Gestión y Operación del SEN | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `PotenciaActivaReactivaUnidadResponse` |
| SIP | Sistema de Información Pública | Potencia | `v4` | `GET` | `/potencia-transitada/v4/findByDate` | `` | Encuentra entradas de potencia transitada para un rango de fechas | Corresponde al concepto potencia transitada que son flujos netos de potencia históricos horarios transitados por el sistema de transmisión que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `PotenciaTransitadaResponse` |
| SIP | Sistema de Información Pública | Programas | `v4` | `GET` | `/programas-mantenimiento-mayor/v4/findByDate` | `` | Encuentra entradas de programa mantenimiento para un rango de fechas | Corresponde al concepto programa mantenimiento, Programa de mantenimiento, Funcionamiento de la Plataforma Programa Mantenimiento Programado Mayor (PMPM), Se hace alusión a Mantenimiento Mayor a 24 Horas, asociado a desconexiones de líneas, centrales y subestaciones, con tiempos de planificación a 18 meses, y cada programa va cambiando cada 6 meses. Finalmente se realizan informes que van a PLP y Plexo de manera diaria. que se actualiza cada dia, mes o semestre, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `ProgramMantenimientoResponse` |
| SIP | Sistema de Información Pública | Pronósticos | `v4` | `GET` | `/pronostico-centrales-pasada/v4/findByDate` | `` | Encuentra entradas de pronostico centrales pasada para un rango de fechas | Corresponde al concepto pronostico centrales pasada, Pronósticos de generación de energía para centrales hidráulicas de pasada, enviada por los coordinados, que se encuentran conectados al sistema eléctrico nacional. que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `PronosticoCentralesPasadaResponse` |
| SIP | Sistema de Información Pública | Pronósticos | `v4` | `GET` | `/pronostico-erv/v4/findByDate` | `` | Encuentra entradas de pronostico erv para un rango de fechas | Corresponde al concepto pronostico erv que es el perfil acotado en el tiempo que corresponde a 240 horas en el futuro y ese perfil responde al pronostico de produccion de una planta generadora que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `PronosticoERVResponse` |
| SIP | Sistema de Información Pública | Pronósticos | `v4` | `GET` | `/pronosticos-demanda-corto-plazo/v4/findByDate` | `` | Encuentra entradas de pronosticos demanda corto plazo para un rango de fechas | Corresponde al concepto pronosticos demanda corto plazo que es el consumo de electricidad en promedio horario (MWh/h) estimado para el sistema eléctrico nacional de corto plazo (7 dias) que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `PronosticosDemandaCortoPlazoResponse` |
| SIP | Sistema de Información Pública | Pronósticos | `v4` | `GET` | `/pronosticos-demanda-mediano-plazo/v4/findByDate` | `` | Encuentra entradas de pronosticos demanda mediano plazo para un rango de fechas | Corresponde al concepto pronosticos demanda mediano plazo que es el consumo de electricidad en promedio horario (MWh/h) estimado para el sistema eléctrico nacional de mediano plazo (14 dias). que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `PronosticosDemandaMedianoPlazoResponse` |
| SIP | Sistema de Información Pública | Punto de Control | `v3` | `GET` | `/punto-control/v3/findByDate` | `` | Encuentra entradas de punto control para un rango de fechas | Corresponde al concepto punto control que corresponde al punto de control ingresado por los coordinados a la plataforma de OPREAL y medido en metros cúbicos /seg que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `PuntoControlResponse` |
| SIP | Sistema de Información Pública | SSCC | `v4` | `GET` | `/servicios-complementarios-programados-pcp/v4/findByDate` | `` | Encuentra entradas de servicios complementarios programados pcp para un rango de fechas | Corresponde al concepto servicios complementarios programados pcp que es la cantidad ofertada diaria en MW de los servicios complementarios programados y su precio por disponibilidad o activación de reserva, expresado en US$/MW para cada Configuración Operativa de propiedad del oferente que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `ServiciosComplementariosProgramadosPCPResponse` |
| SIP | Sistema de Información Pública | SSCC | `v4` | `GET` | `/servicios-complementarios-programados-pid/v4/findByDate` | `` | Encuentra entradas de servicios complementarios programados pid para un rango de fechas | Corresponde al concepto servicios complementarios programados pid que es la cantidad ofertada diaria en MW de los servicios complementarios programados y su precio por disponibilidad o activación de reserva, expresado en US$/MW para cada Configuración Operativa de propiedad del oferente, ajuste a la programación de la operación que se realiza dentro del día (00 -23hrs) para incorporar cambios que hayan pasado en la operación en tiempo real y que no fueran considerados en la programación diaria que se generó el día anterior, para efectos de operar el sistema eléctrico nacional que se actualiza cada dia, del area de negocio Programación de la Operación | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `ServiciosComplementariosProgramadosPIDResponse` |
| SIP | Sistema de Información Pública | Sistemas Medianos | `v4` | `GET` | `/sistema-mediano-hornopiren/v4/findByDate` | `` | Encuentra entradas de sistema mediano hornopiren para un rango de fechas | Corresponde al concepto sistema mediano hornopiren, programación de la operación del Sistema Mediano de Hornopirén para el día N. Principal resultado despacho de cada central y/o unidad generadora que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `SistemaMedianoHornopirenResponse` |
| SIP | Sistema de Información Pública | Sistemas Medianos | `v4` | `GET` | `/sistema-mediano-punta-arenas/v4/findByDate` | `` | Encuentra entradas de sistema mediano punta arenas para un rango de fechas | Corresponde al concepto sistema mediano punta arenas, programación de la operación del Sistema Mediano de Punta Arenas para el día N, con resultados para los días N a N + 6. Principal resultado despacho de cada central y/o unidad generadora que se actualiza cada dia, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `SistemaMedianoPuntaArenasResponse` |
| SIP | Sistema de Información Pública | Solicitudes | `v4` | `GET` | `/solicitudes-trabajo/v4/findByDate` | `` | Encuentra entradas de solicitudes de trabajo para un rango de fechas | Corresponde al concepto solicitudes de trabajo, corresponde a toda conexión, intervención o desconexión que una empresa electrica propietaria de instalaciones requiera realizar requiriendo de la autorización del coordinador que se actualiza cada dia, del area de negocio Gestión y Operación del SEN | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `SolicitudesTrabajoResponse` |
| SIP | Sistema de Información Pública | Transferencias | `v4` | `GET` | `/transferencia-economica-nacional/v4/findByDate` | `` | Encuentra entradas de transferencia economica nacional para un rango de fechas | Corresponde al concepto transferencia economica nacional que son pagos que se realizan por el uso de las redes de transmisión eléctrica. Estos pagos son esenciales para gestionar el costo y el mantenimiento de las infraestructuras que permiten la transmisión de electricidad desde los puntos de generación hasta los puntos de consumo que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `TransferenciaEconomicaNacionalResponse` |
| SIP | Sistema de Información Pública | Transferencias | `v4` | `GET` | `/transferencia-economica-zonal/v4/findByDate` | `` | Encuentra entradas de transferencia economica zonal para un rango de fechas | Corresponde al concepto transferencia economica zonal, Son pagos que se realizan por el uso de las redes de transmisión eléctrica. Estos pagos son esenciales para gestionar el costo y el mantenimiento de las infraestructuras que permiten la transmisión de electricidad desde los puntos de generación hasta los puntos de consumo que se actualiza cada mes, del area de negocio Gestión de Mercado | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `TransferenciaEconomicaZonalResponse` |
| SIP | Sistema de Información Pública | Transformadores | `v3` | `GET` | `/transformadores-2d/v3/findAll` | `` | Encuentra entradas de transformadores 2d para un rango de fechas | Corresponde al concepto transformadores 2d, Banco de Transformadores 2D que pueden tomar determinadas configuraciones las cuales son transformador 2D trifásico sin reserva, transformador 2D trifásico con reserva, dos transformadores 2D trifásicos comparten un transformador trifásico de reserva, banco de transformadores 2D monofásicos sin reserva, banco de transformadores 2D monofásicos con reserva y dos bancos de transformadores 2D monofásicos comparten un transformador monofásico de reserva que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `Transformadores2dResponse` |
| SIP | Sistema de Información Pública | Transformadores | `v3` | `GET` | `/transformadores-3d/v3/findAll` | `` | Encuentra entradas de transformadores 3d para un rango de fechas | Corresponde al concepto transformadores 3d, Para un banco de transformadores 3D se deben considerar los mismos conjuntos de equipos para efectos de creación de registros que se indican para transformadores 3D. Las configuraciones que pueden determinarse son transformador 3D trifásico sin reserva, transformador 3D trifásico con reserva, dos transformadores 3D trifásicos comparten un transformador trifásico de reserva, banco de transformadores 3D monofásicos sin reserva, banco de transformadores 3D monofásicos con reserva y dos bancos de transformadores 3D monofásicos comparten un transformador monofásico de reserva que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `Transformadores3dResponse` |
| SIP | Sistema de Información Pública | Transformadores | `v3` | `GET` | `/transformadores-auxiliares/v3/findAll` | `` | Encuentra entradas de transformadores auxiliares para un rango de fechas | Corresponde al concepto transformadores auxiliares, la creación de un transformador de servicios auxiliares es requisito mínimo que este aparezca representado con las siguientes características en los DUF (Diagrama Unilineal Funcional) • Nombre identificatorio e irrepetible para la subestación, respetando la nomenclatura definida en Guía de Nomenclatura y Requisitos Mínimos DUF en su versión más reciente. • Se indica el nivel de tensión de sus devanados, razón de transformación. • Se indica la capacidad de transformación que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `TransformadoresAuxiliaresResponse` |
| SIP | Sistema de Información Pública | Transformadores | `v3` | `GET` | `/transformadores-corrientes/v3/findAll` | `` | Encuentra entradas de transformadores corriente para un rango de fechas | Corresponde al concepto transformadores corriente, un registro de transformador de corriente representa los transformadores de corriente de las tres fases, por lo que se debe crear un solo registro para estos. Cuando existen transformadores de corriente en serie entonces corresponde la creación de un registro para cada uno de ellos. Por otra parte, los registros de transformadores de corriente ubicados en los neutros de las máquinas eléctricas se interpretan como un sólo equipo en lugar de tres y también corresponde la creación de un registro para estos. Finalmente los transformadores de corriente de fase y de neutro deben respetar lo siguiente • No se debe crear un registro para el TC trifásico1 de las celdas, ya que, este está considerado en el registro de Celdas. Por el contrario, los TC toroidales2 si deben ser registrados en esta Instalación ya sea que estos se ubiquen al interior de la celda o en la entrada/salida de estas. • No se debe crear un registro para transformadores de corriente asociados a reconectadores. • No se debe crear un registro para sensores de corriente que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `TransformadoresCorrientesResponse` |
| SIP | Sistema de Información Pública | Transformadores | `v3` | `GET` | `/transformadores-potenciales/v3/findAll` | `` | Encuentra entradas de transformadores potenciales para un rango de fechas | Corresponde al concepto transformadores potenciales, Se debe crear un registro de transformador de potencial el cual representa los transformadores de potencial de las tres fases o de una sola según sea el caso, se deben registrar los transformadores de potencial, ya sean de tipo capacitivo o inducitvo. Se debe respatar que:• Los sensores de tensión presentes en celdas y/o reconectadores no son creados en la BDIT (Base de Dato de InfoTecnica).• Los transformadores de potencial de paños al interior de celdas NO deben ser creados.• Los transformadores de potencial de barras al interior de celdas SI deben ser creados. que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `TransformadoresPotencialesResponse` |
| SIP | Sistema de Información Pública | Transformadores | `v3` | `GET` | `/transformadores-zigzag/v3/findAll` | `` | Encuentra entradas de transformadores zigzag para un rango de fechas | Corresponde al concepto transformadores zigzag, Para realizar la creación de un transformador Zig Zag es requisito mínimo que éste aparezca representadocon las siguientes características en los DUF (Diagrama Unilineal Funcional):• Nombre identificatorio e irrepetible para la subestación, respetando la nomenclatura definida en guía de Nomenclatura y Requisitos Mínimos DUF en su versión más reciente.• Se indica el nivel de tensión del transformador.• Se indica la capacidad de transformación que se actualiza cada dia, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page | Sí (global: api-key) | 200, 401, 403, 500 | `TransformadoresZigzagResponse` |
| SIP | Sistema de Información Pública | Unidades | `v4` | `GET` | `/unidades-generadoras/v4/findByDate` | `` | Encuentra entradas de unidades generadoras para un rango de fechas | Corresponde al concepto unidades generadoras, Información técnica de las instalaciones en operación del SEN. En este caso unidades generadoras de las centrales que se actualiza cada dia o mes, del area de negocio Gestión de Acceso Abierto y Conexiones | startDate, endDate, page, limit | Sí (global: api-key) | 200, 401, 403, 500 | `UnidadesGeneradorasResponse` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/contratos_de_suministro_vigentes/` | `v2_recursos_contratos_de_suministro_vigentes_list` | Contratos de suministro vigentes. | Contratos de suministro vigentes. Para obtener información de las empresas a partir de los IDs de infotécnica, referirse al endpoint `infotecnica/empresas`. **Fuente:** Datos cargados manualmente en el sistema por el Departamento de Transferencias Económicas **Por defecto:** Entrega 20 datos por página **Campos** * `suministrador_mnemotecnico`: Mnemotécnico de la empresa suministradora * `cliente_mnemotecnico`: Mnemotécnico de la empresa cliente * `fecha_suscripcion`: Fecha de suscripción contrato * `fecha_inicio`: Fecha de inicio vigencia contrato * `fecha_termino`: Fecha de término vigencia contrato * `puntos_de_suministro`: Nombres de las barras * `puntos_de_retiro`: Nombres de las barras * `potencia_conectada`: Valor potencia conectada en MW * `año`: - * `energia_contratada`: Valor energía contratada en MWh/año * `potencia_contratada`: Valor potencia contratada en MW * `potencia_contratada_horapunta`: Valor potencia contratada en MW * `potencia_contratada_no_horapunta`: Valor potencia contratada en MW * `nombre_distribuidora`: En caso de que el contrato sea de tipo LD, el nombre distribuidora indica la red a la que se conecta el cliente. * `tipo`: \| L: Cliente Libre R: Cliente Regulado C: Entre Generadores LD: Distribución con Clientes Libres * `afecto_obligacion_ernc`: * `enlace`: Link a declaración jurada * `fecha_suscripcion_renovacion`: Fecha suscripción de la última renovación * `fecha_inicio_renovacion`: Fecha de inicio vigencia de la última renovación * `fecha_termino_renovacion`: Fecha de término vigencia de la última renovación | limit | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/contratos_de_suministro_vigentes/slices/` | `v2_recursos_contratos_de_suministro_vigentes_slices_list` | Stock de Combustibles Disponibles para Generación - Real. | Stock de Combustibles Disponibles para Generación - Real. **Por defecto:** Entrega todos los valores de suministradores disponibles para ser consultadas. **Campos** * `suministrador_mnemotecnico`: Mnemotécnico del suministrador. | limit | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/costo_marginal_programado/` | `v2_recursos_costo_marginal_programado_list` | Costo marginal programado por llave. | Costo marginal programado por llave. Para hacer cruces de datos entre las llaves de OpReal y el mnemotécnico de la barra, referirse al endpoint `costo_marginal_llaves`. **Fuente:** Datos extraídos de OpReal. **Por defecto:** Entrega 20 datos por página **Campos** * `llave_id`: ID de la llave en OpReal * `fecha`: Fecha de los costos * `hora`: Hora indexada de los costos * `costo`: Costo en USD | limit, fecha | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/costo_marginal_programado/slices/` | `v2_recursos_costo_marginal_programado_slices_list` | Costo marginal programado por llave. | Costo marginal programado por llave. **Por defecto:** Entrega todos los valores de fechas disponibles para ser consultadas. **Campos** * `fecha`: Fecha. | limit | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/costos_marginales_reales/` | `v2_recursos_costos_marginales_reales_list` | Costos marginales reales. | Costos marginales reales. Para obtener información de las barras a partir de los IDs de infotécnica, referirse al endpoint `infotecnica/barras`. **Fuente:** Datos cargados manualmente en el sistema por el Departamento de Transferencias Económicas. **Por defecto:** Entrega 20 datos por página **Campos** * `fecha`: Fecha. * `hora`: Hora indexada. * `costo_en_dolares`: Valor en USD/MWh * `costo_en_pesos`: Valor en CLP/KWh * `barra`: ID de la barra en infotécnica. * `barra_referencia`: ID de la barra de referencia en infotécnica. | limit, fecha | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/costos_marginales_reales/slices/` | `v2_recursos_costos_marginales_reales_slices_list` | Costos marginales reales. | Costos marginales reales. **Por defecto:** Entrega todos los valores de fechas disponibles para ser consultadas. **Campos** * `fecha`: Fecha. | limit | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/demanda_sistema_real/` | `v2_recursos_demanda_sistema_real_list` | Demanda real del sistema. | Demanda real del sistema. Corresponde a la: * Generación Real del sistema horaria, obtenida de OpReal, para fechas anteriores a los últimos 2 días. * Generación Online horaria, obtenida de SCADA, para los últimos 2 días. **Fuente:** Datos extraídos de OpReal y SCADA. **Por defecto:** Entrega 20 datos por página **Campos** * `fecha`: Fecha. * `hora`: Hora indexada. * `demanda`: Demanda en MWh. | limit | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/demanda_sistema_real/slices/` | `v2_recursos_demanda_sistema_real_slices_list` | Demanda real sistémica. | Demanda real sistémica. **Por defecto:** Entrega todos los valores de fechas disponibles para ser consultadas. **Campos** * `fecha`: Fecha. | limit | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/generacion_programada/` | `v2_recursos_generacion_programada_list` | Generación programada por llave. | Generación programada por llave. Para hacer cruces de datos referirse a los siguientes endpoints: - `generacion_programada_llaves`: relaciona los mnemotécnicos de las llaves de OpReal con los nombres de las políticas de programación. - `generacion_programada_politicas`: relaciona los nombres de las políticas con sus empresas propietarias. **Fuente:** Datos extraídos de OpReal. **Por defecto:** Entrega 20 datos por página **Campos** * `fecha`: Fecha * `hora`: Hora indexada * `key_id`: ID de la llave en OpReal, * `natural_key`: Mnemotécnico de la llave en OpReal, * `generación`: Generacion programada de la llave en MWh. | limit, fecha | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/generacion_programada/slices/` | `v2_recursos_generacion_programada_slices_list` | Generación programada por llave. | Generación programada por llave. **Por defecto:** Entrega todos los valores de fechas disponibles para ser consultadas. **Campos** * `fecha`: Fecha. | limit | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/generacion_programada_llaves/` | `v2_recursos_generacion_programada_llaves_list` | Relación entre las llaves OPreal y la política de programación. | Relación entre las llaves OPreal y la política de programación. **Fuente:** Datos extraídos de OpReal. **Por defecto:** Entrega 20 datos por página. **Campos** * `key_id`: ID numérico de la llave en OpReal * `nombre_llave`: Mnemotécnico de la llave en OPReal * `nombre_politica`: Nombre de la política de programación. | limit, key_id | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/generacion_programada_llaves/slices/` | `v2_recursos_generacion_programada_llaves_slices_list` | Relación entre las llaves OPreal y la política de programación. | Relación entre las llaves OPreal y la política de programación. **Por defecto:** Entrega todos los valores de llaves disponibles para ser consultadas. **Campos** * `key_id`: ID de la llave. | limit | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/generacion_programada_sistema/` | `v2_recursos_generacion_programada_sistema_list` | Generación programada sistémica | Generación programada sistémica **Fuente:** Corresponde a la suma de la generación programada de todas las barras. **Por defecto:** Entrega 20 datos por página. **Campos** * `fecha`: Fecha * `hora`: Hora indexada. * `generacion`: Generación en MWh. | limit, fecha | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/generacion_programada_sistema/slices/` | `v2_recursos_generacion_programada_sistema_slices_list` | Generación programada sistémica | No aparece descripción adicional en la especificación. | limit | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/infotecnica/barras/` | `v2_recursos_infotecnica_barras_list` | Barras. | Barras. **Fuente:** Datos extraídos de la BD Infotécnica. **Por defecto:** Entrega 20 datos por página. **Campos** * `id_infotecnica`: ID numérico en infotécnica * `propietario`: Mnemotécnico del propietario * `subestacion`: Mnemotécnico de la subestación a la que pertenece * `codigo`: Código de la barra * `descripcion`: Descripción de la barra * `mnemotecnico`: Mnemotécnico en infotécnica * `nombre`: Nombre de la barra * `numero`: Número de la barra | limit, nombre | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/infotecnica/centrales/` | `v2_recursos_infotecnica_centrales_list` | Centrales. | Centrales. **Fuente:** Datos extraídos de la BD Infotécnica. **Por defecto:** Entrega 20 datos por página. **Campos** * `id_infotecnica`: ID numérico en infotécnica * `nombre`: Nombre de la central * `mnemotecnico`: Mnemotécnico en infotécnica * `descripcion`: Descripción * `propietario`: Mnemotécnico del propietario de la central * `codigo`: Código de la central * `numero`: Número de la central | limit, nombre | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/infotecnica/centrales_tipos/` | `v2_recursos_infotecnica_centrales_tipos_list` | Tipos de centrales. | Tipos de centrales. **Fuente:** Datos extraídos de la BD Infotécnica. **Por defecto:** Entrega 20 datos por página. **Campos** * `id_infotecnica`: ID numérico en infotécnica * `nombre`: Nombre del tipo de central * `mnemotecnico`: Mnemotécnico en infotécnica * `descripcion`: Descripción * `central_set`: Lista con los mnemotécnicos de las centrales que pertenecen al tipo | limit, nombre | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/infotecnica/empresas/` | `v2_recursos_infotecnica_empresas_list` | Empresas. | Empresas. **Fuente:** Datos extraídos de la BD Infotécnica. **Por defecto:** Entrega 20 datos por página. **Campos** * `barra_set`: Lista con los mnemotécnicos de las barras en las que es propietario * `central_set`: Lista con los mnemotécnicos de las centrales en las que es propietario * `linea_set`: Lista con los mnemotécnicos de las líneas en las que es propietario * `subestacion_set`: Lista con los mnemotécnicos de las subestaciones en las que es propietario * `paño_set`: Lista con los mnemotécnicos de los paños en las que es propietario * `rut`: RUT de la empresa * `id_infotecnica`: ID numérico en infotécnica * `giro`: ID numérico del giro a cual pertenece * `grupo`: ID numérico del grupo a cual pertenece * `nombre`: Nombre de la empresa * `descripcion`: Descripción * `mnemotecnico`: Mnemotécnico en infotécnica * `numero`: Número de la empresa | limit, nombre | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/potencia_transitada/` | `v2_recursos_potencia_transitada_list` | Potencia transitada por líneas | Potencia transitada por líneas **Fuente:** Datos cargados manualmente en el sistema por el Departamento de Peajes. **Por defecto:** Entrega 20 datos por página, ordenados del más antiguo al más reciente. **Campos** * `tramo_nombre`: Nombre del tramo * `linea_nombre`: Línea del tramo * `ssee`: * `potencia`: Potencia transitada en MW * `intervalos`: Hora indexada * `fecha`: Fecha informada * `correlativo`: Número correlativo (TODO: esclarecer el signficado de este campo) | limit, fecha | Sí (global: api-key) | 200 | `` |
| SIP | Sistema de Información Pública | api - Disponibles Solo Hasta el 31 de Diciembre del  2024 | `v2` | `GET` | `/api/v2/recursos/potencia_transitada/slices/` | `v2_recursos_potencia_transitada_slices_list` | Potencia transitada por líneas. | No aparece descripción adicional en la especificación. | limit | Sí (global: api-key) | 200 | `` |

## 12. Detalle de endpoints MERCADOS

Los endpoints de MERCADOS son de tipo `POST` y están orientados a **recepción/validación de pronósticos**. A diferencia de la mayoría de endpoints de los otros planes, aquí la adquisición no es solo consulta: se envía un body JSON para validar datos.

### `POST /pronosticos/recepcion-pronosticos-cpasada/api/Forecast/v1/validate`

- **Tag:** Recepción de Pronósticos Centrales de Pasada
- **Resumen:** Recepción de pronósticos para centrales de pasada
- **Descripción:** Recepción de pronósticos para centrales de pasada
- **Body schema:** `ReceptionForecastDto`
- **Body requerido:** `True`
- **Respuesta 200:** `FormatOutputDto`

#### Ejemplo `curl`

```bash
curl -X POST "https://mercados.api.coordinador.cl/pronosticos/recepcion-pronosticos-cpasada/api/Forecast/v1/validate?user_key=TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "sender_name": "Proveedor Centrales de Pasada",
  "forecast_name": "Centrales de Pasada",
  "forecast_type": "Day-ahead-168 | h, resolución 1 | h",
  "since": "2023-09-24T00:00:00",
  "central_pass_forecast": [
    {
      "pass_center_id": 5,
      "forecast_datetime": "2023-09-24T00:00:00",
      "mtw_value": 1,
      "min_generation": 0
    },
    {
      "pass_center_id": 5,
      "forecast_datetime": "2023-09-24T01:00:00",
      "mtw_value": 1,
      "min_generation": 0
    },
    {
      "pass_center_id": 5,
      "forecast_datetime": "2023-09-24T02:00:00",
      "mtw_value": 1,
      "min_generation": 0
    }
  ]
}'
```

#### Ejemplo de body JSON

```json
{
  "sender_name": "Proveedor Centrales de Pasada",
  "forecast_name": "Centrales de Pasada",
  "forecast_type": "Day-ahead-168 | h, resolución 1 | h",
  "since": "2023-09-24T00:00:00",
  "central_pass_forecast": [
    {
      "pass_center_id": 5,
      "forecast_datetime": "2023-09-24T00:00:00",
      "mtw_value": 1,
      "min_generation": 0
    },
    {
      "pass_center_id": 5,
      "forecast_datetime": "2023-09-24T01:00:00",
      "mtw_value": 1,
      "min_generation": 0
    },
    {
      "pass_center_id": 5,
      "forecast_datetime": "2023-09-24T02:00:00",
      "mtw_value": 1,
      "min_generation": 0
    }
  ]
}
```

### `POST /pronosticos/recepcion-demanda/api/Forecast/v1/validate`

- **Tag:** Recepción de Pronósticos Demanda
- **Resumen:** Recepción de pronósticos para Demanda
- **Descripción:** Recepción de pronósticos para Demanda
- **Body schema:** `DemandForecastDto`
- **Body requerido:** `True`
- **Respuesta 200:** `FormatOutputDto`

#### Ejemplo `curl`

```bash
curl -X POST "https://mercados.api.coordinador.cl/pronosticos/recepcion-demanda/api/Forecast/v1/validate?user_key=TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "sender_name": "Proveedor Demanda",
  "forecast_type_name": "Intra-day-24 | h, resolución 1 | h",
  "forecast_since": "2023-03-12T11:00:00",
  "forecast_name": "Demanda",
  "dda_forecast": [
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T00:00:00",
      "until": "2024-01-01T01:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T01:00:00",
      "until": "2024-01-01T02:00:00",
      "exceedance_prob_50": 996.34,
      "exceedance_prob_25": 997.05,
      "exceedance_prob_75": 978.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T02:00:00",
      "until": "2024-01-01T03:00:00",
      "exceedance_prob_50": 995.34,
      "exceedance_prob_25": 996.05,
      "exceedance_prob_75": 977.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T03:00:00",
      "until": "2024-01-01T04:00:00",
      "exceedance_prob_50": 994.34,
      "exceedance_prob_25": 996.05,
      "exceedance_prob_75": 975.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T04:00:00",
      "until": "2024-01-01T05:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T05:00:00",
      "until": "2024-01-01T06:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T06:00:00",
      "until": "2024-01-01T07:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T07:00:00",
      "until": "2024-01-01T08:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T08:00:00",
      "until": "2024-01-01T09:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T09:00:00",
      "until": "2024-01-01T10:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T10:00:00",
      "until": "2024-01-01T11:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T11:00:00",
      "until": "2024-01-01T12:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T12:00:00",
      "until": "2024-01-01T13:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T13:00:00",
      "until": "2024-01-01T14:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T14:00:00",
      "until": "2024-01-01T15:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T15:00:00",
      "until": "2024-01-01T16:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T16:00:00",
      "until": "2024-01-01T17:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T17:00:00",
      "until": "2024-01-01T18:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T18:00:00",
      "until": "2024-01-01T19:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T19:00:00",
      "until": "2024-01-01T20:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T20:00:00",
      "until": "2024-01-01T21:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T21:00:00",
      "until": "2024-01-01T22:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T22:00:00",
      "until": "2024-01-01T23:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T23:00:00",
      "until": "2024-01-02T00:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    }
  ]
}'
```

#### Ejemplo de body JSON

```json
{
  "sender_name": "Proveedor Demanda",
  "forecast_type_name": "Intra-day-24 | h, resolución 1 | h",
  "forecast_since": "2023-03-12T11:00:00",
  "forecast_name": "Demanda",
  "dda_forecast": [
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T00:00:00",
      "until": "2024-01-01T01:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T01:00:00",
      "until": "2024-01-01T02:00:00",
      "exceedance_prob_50": 996.34,
      "exceedance_prob_25": 997.05,
      "exceedance_prob_75": 978.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T02:00:00",
      "until": "2024-01-01T03:00:00",
      "exceedance_prob_50": 995.34,
      "exceedance_prob_25": 996.05,
      "exceedance_prob_75": 977.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T03:00:00",
      "until": "2024-01-01T04:00:00",
      "exceedance_prob_50": 994.34,
      "exceedance_prob_25": 996.05,
      "exceedance_prob_75": 975.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T04:00:00",
      "until": "2024-01-01T05:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T05:00:00",
      "until": "2024-01-01T06:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T06:00:00",
      "until": "2024-01-01T07:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T07:00:00",
      "until": "2024-01-01T08:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T08:00:00",
      "until": "2024-01-01T09:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T09:00:00",
      "until": "2024-01-01T10:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T10:00:00",
      "until": "2024-01-01T11:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T11:00:00",
      "until": "2024-01-01T12:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T12:00:00",
      "until": "2024-01-01T13:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T13:00:00",
      "until": "2024-01-01T14:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T14:00:00",
      "until": "2024-01-01T15:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T15:00:00",
      "until": "2024-01-01T16:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T16:00:00",
      "until": "2024-01-01T17:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T17:00:00",
      "until": "2024-01-01T18:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T18:00:00",
      "until": "2024-01-01T19:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T19:00:00",
      "until": "2024-01-01T20:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T20:00:00",
      "until": "2024-01-01T21:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T21:00:00",
      "until": "2024-01-01T22:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T22:00:00",
      "until": "2024-01-01T23:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    },
    {
      "demand_zone_name": "Ancoa",
      "since": "2024-01-01T23:00:00",
      "until": "2024-01-02T00:00:00",
      "exceedance_prob_50": 997.34,
      "exceedance_prob_25": 998.05,
      "exceedance_prob_75": 979.53
    }
  ]
}
```

### `POST /pronosticos/recepcion-erv/api/Forecast/v1/validate`

- **Tag:** Recepción de Pronósticos ERV
- **Resumen:** Recepción de pronósticos para ERV
- **Descripción:** Recepción de pronósticos para ERV
- **Body schema:** `ERVForecastDto`
- **Body requerido:** `True`
- **Respuesta 200:** `FormatOutputDto`

#### Ejemplo `curl`

```bash
curl -X POST "https://mercados.api.coordinador.cl/pronosticos/recepcion-erv/api/Forecast/v1/validate?user_key=TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "sender_name": "UL",
  "central_name": "PE VALLE DE LOS VIENTOS",
  "forecast_type_name": "Intra-day-12 | h, resolución 1 | h",
  "forecast_name": "ERV Eólica",
  "erv_forecast": [
    {
      "since": "2024-01-01T06:00:00",
      "until": "2024-01-01T07:00:00",
      "exceedance_prob_25": 9.2209,
      "exceedance_prob_50": 9.1296,
      "exceedance_prob_75": 8.7644,
      "speed": 8,
      "direction": 139,
      "celsius_temperature": 32,
      "pressure_bar": 11
    },
    {
      "since": "2024-01-01T07:00:00",
      "until": "2024-01-01T08:00:00",
      "exceedance_prob_25": 18.8876,
      "exceedance_prob_50": 17.8185,
      "exceedance_prob_75": 17.2839,
      "speed": 9,
      "direction": 292,
      "celsius_temperature": 6,
      "pressure_bar": 15
    },
    {
      "since": "2024-01-01T08:00:00",
      "until": "2024-01-01T09:00:00",
      "exceedance_prob_25": 11.6892,
      "exceedance_prob_50": 11.46,
      "exceedance_prob_75": 9.8556,
      "speed": 18,
      "direction": 87,
      "celsius_temperature": 6,
      "pressure_bar": 17
    },
    {
      "since": "2024-01-01T09:00:00",
      "until": "2024-01-01T10:00:00",
      "exceedance_prob_25": 7.9175,
      "exceedance_prob_50": 7.0066,
      "exceedance_prob_75": 6.4461,
      "speed": 28,
      "direction": 290,
      "celsius_temperature": 14,
      "pressure_bar": 11
    },
    {
      "since": "2024-01-01T10:00:00",
      "until": "2024-01-01T11:00:00",
      "exceedance_prob_25": 0.1204,
      "exceedance_prob_50": 0.1056,
      "exceedance_prob_75": 0.1024,
      "speed": 26,
      "direction": 170,
      "celsius_temperature": 17,
      "pressure_bar": 9
    },
    {
      "since": "2024-01-01T11:00:00",
      "until": "2024-01-01T12:00:00",
      "exceedance_prob_25": 3.2893,
      "exceedance_prob_50": 3.1031,
      "exceedance_prob_75": 2.6376,
      "speed": 6,
      "direction": 151,
      "celsius_temperature": 30,
      "pressure_bar": 3
    },
    {
      "since": "2024-01-01T12:00:00",
      "until": "2024-01-01T13:00:00",
      "exceedance_prob_25": 5.0548,
      "exceedance_prob_50": 5.0048,
      "exceedance_prob_75": 4.4543,
      "speed": 14,
      "direction": 219,
      "celsius_temperature": 21,
      "pressure_bar": 3
    },
    {
      "since": "2024-01-01T13:00:00",
      "until": "2024-01-01T14:00:00",
      "exceedance_prob_25": 4.5536,
      "exceedance_prob_50": 4.0657,
      "exceedance_prob_75": 3.9844,
      "speed": 20,
      "direction": 102,
      "celsius_temperature": 10,
      "pressure_bar": 4
    },
    {
      "since": "2024-01-01T14:00:00",
      "until": "2024-01-01T15:00:00",
      "exceedance_prob_25": 3.6502,
      "exceedance_prob_50": 3.2591,
      "exceedance_prob_75": 3.0961,
      "speed": 15,
      "direction": 155,
      "celsius_temperature": 26,
      "pressure_bar": 20
    },
    {
      "since": "2024-01-01T15:00:00",
      "until": "2024-01-01T16:00:00",
      "exceedance_prob_25": 3.0202,
      "exceedance_prob_50": 2.7209,
      "exceedance_prob_75": 2.4216,
      "speed": 28,
      "direction": 180,
      "celsius_temperature": 18,
      "pressure_bar": 7
    },
    {
      "since": "2024-01-01T16:00:00",
      "until": "2024-01-01T17:00:00",
      "exceedance_prob_25": 26.148,
      "exceedance_prob_50": 25.3864,
      "exceedance_prob_75": 24.6248,
      "speed": 6,
      "direction": 138,
      "celsius_temperature": 7,
      "pressure_bar": 11
    },
    {
      "since": "2024-01-01T17:00:00",
      "until": "2024-01-01T18:00:00",
      "exceedance_prob_25": 69.9601,
      "exceedance_prob_50": 67.2693,
      "exceedance_prob_75": 63.2331,
      "speed": 26,
      "direction": 281,
      "celsius_temperature": 20,
      "pressure_bar": 17
    }
  ]
}'
```

#### Ejemplo de body JSON

```json
{
  "sender_name": "UL",
  "central_name": "PE VALLE DE LOS VIENTOS",
  "forecast_type_name": "Intra-day-12 | h, resolución 1 | h",
  "forecast_name": "ERV Eólica",
  "erv_forecast": [
    {
      "since": "2024-01-01T06:00:00",
      "until": "2024-01-01T07:00:00",
      "exceedance_prob_25": 9.2209,
      "exceedance_prob_50": 9.1296,
      "exceedance_prob_75": 8.7644,
      "speed": 8,
      "direction": 139,
      "celsius_temperature": 32,
      "pressure_bar": 11
    },
    {
      "since": "2024-01-01T07:00:00",
      "until": "2024-01-01T08:00:00",
      "exceedance_prob_25": 18.8876,
      "exceedance_prob_50": 17.8185,
      "exceedance_prob_75": 17.2839,
      "speed": 9,
      "direction": 292,
      "celsius_temperature": 6,
      "pressure_bar": 15
    },
    {
      "since": "2024-01-01T08:00:00",
      "until": "2024-01-01T09:00:00",
      "exceedance_prob_25": 11.6892,
      "exceedance_prob_50": 11.46,
      "exceedance_prob_75": 9.8556,
      "speed": 18,
      "direction": 87,
      "celsius_temperature": 6,
      "pressure_bar": 17
    },
    {
      "since": "2024-01-01T09:00:00",
      "until": "2024-01-01T10:00:00",
      "exceedance_prob_25": 7.9175,
      "exceedance_prob_50": 7.0066,
      "exceedance_prob_75": 6.4461,
      "speed": 28,
      "direction": 290,
      "celsius_temperature": 14,
      "pressure_bar": 11
    },
    {
      "since": "2024-01-01T10:00:00",
      "until": "2024-01-01T11:00:00",
      "exceedance_prob_25": 0.1204,
      "exceedance_prob_50": 0.1056,
      "exceedance_prob_75": 0.1024,
      "speed": 26,
      "direction": 170,
      "celsius_temperature": 17,
      "pressure_bar": 9
    },
    {
      "since": "2024-01-01T11:00:00",
      "until": "2024-01-01T12:00:00",
      "exceedance_prob_25": 3.2893,
      "exceedance_prob_50": 3.1031,
      "exceedance_prob_75": 2.6376,
      "speed": 6,
      "direction": 151,
      "celsius_temperature": 30,
      "pressure_bar": 3
    },
    {
      "since": "2024-01-01T12:00:00",
      "until": "2024-01-01T13:00:00",
      "exceedance_prob_25": 5.0548,
      "exceedance_prob_50": 5.0048,
      "exceedance_prob_75": 4.4543,
      "speed": 14,
      "direction": 219,
      "celsius_temperature": 21,
      "pressure_bar": 3
    },
    {
      "since": "2024-01-01T13:00:00",
      "until": "2024-01-01T14:00:00",
      "exceedance_prob_25": 4.5536,
      "exceedance_prob_50": 4.0657,
      "exceedance_prob_75": 3.9844,
      "speed": 20,
      "direction": 102,
      "celsius_temperature": 10,
      "pressure_bar": 4
    },
    {
      "since": "2024-01-01T14:00:00",
      "until": "2024-01-01T15:00:00",
      "exceedance_prob_25": 3.6502,
      "exceedance_prob_50": 3.2591,
      "exceedance_prob_75": 3.0961,
      "speed": 15,
      "direction": 155,
      "celsius_temperature": 26,
      "pressure_bar": 20
    },
    {
      "since": "2024-01-01T15:00:00",
      "until": "2024-01-01T16:00:00",
      "exceedance_prob_25": 3.0202,
      "exceedance_prob_50": 2.7209,
      "exceedance_prob_75": 2.4216,
      "speed": 28,
      "direction": 180,
      "celsius_temperature": 18,
      "pressure_bar": 7
    },
    {
      "since": "2024-01-01T16:00:00",
      "until": "2024-01-01T17:00:00",
      "exceedance_prob_25": 26.148,
      "exceedance_prob_50": 25.3864,
      "exceedance_prob_75": 24.6248,
      "speed": 6,
      "direction": 138,
      "celsius_temperature": 7,
      "pressure_bar": 11
    },
    {
      "since": "2024-01-01T17:00:00",
      "until": "2024-01-01T18:00:00",
      "exceedance_prob_25": 69.9601,
      "exceedance_prob_50": 67.2693,
      "exceedance_prob_75": 63.2331,
      "speed": 26,
      "direction": 281,
      "celsius_temperature": 20,
      "pressure_bar": 17
    }
  ]
}
```


## 13. Recomendación de arquitectura para consolidar adquisición

Para trabajar los 4 planes en un pipeline único, conviene separar la ingesta en cuatro capas:


1. **Datos operacionales/históricos:** SIP y OPERACIONES. Aquí entran generación, demanda, costo marginal, SSCC, instrucciones operacionales, reportes CNE/OpReal y desviaciones.
2. **Maestros técnicos y topología:** PLANIFICACION y parte de OPERACIONES. Aquí entran activos de Infotécnica, centrales, unidades, líneas, subestaciones, transformadores, barras, tramos, circuitos y conexiones.
3. **Recepción/validación de pronósticos:** MERCADOS. Aquí se envían pronósticos por POST y se valida estructura/reglas de negocio.
4. **Auditoría de ingesta:** para cada llamada guardar plan, endpoint, método, parámetros/body, fecha/hora de consulta, código HTTP, cantidad de registros, `hash` o archivo JSON bruto y versión del parser.

Para cargas completas usar paginación; para cargas incrementales usar rangos de fecha, `id`, `search`, `nombre`, `nemotecnico`, `idPropietario` o filtros específicos de cada endpoint.