# CLAUDE.md — Dashboard CTM Mejillones
> Contexto completo para Claude Code. Leer al inicio de cada sesión.
> Autor: Erick Herrera — AES Andes, Antofagasta, Chile.
> Última actualización: 2026-08-02 (4ª sesión: **modelo unificado de EVENTOS** en `utils/eventos.py`
>   — la vigencia de una limitación se juzga por su VENTANA y no por el `status` del CEN, que
>   nunca cierra (hallazgo: 0 limitaciones realmente vigentes contra 16 «pendientes» de papel).
>   La serie de cada unidad ahora pinta las ventanas de limitación/mantenimiento, atribuye cada
>   bloque de detención a su causa (o la declara SIN causa registrada) y anticipa los eventos
>   latentes del PMPM. La vista «Restricciones» pasó a **«Operación»** y abre con la subsección
>   nueva **«Panorama»** (qué está activo, energía no generada valorizada, cobertura documental
>   del desvío). KPI cards sin truncado: `render_kpi_grid` + CSS anti-elipsis, verificado en el
>   DOM real. El informe ejecutivo ya no lista pendientes fantasma.)
> Anterior: 2026-08-01 (3ª sesión: **suite ML rediseñada** — Anomalías y Regímenes
>   reemplazadas por «Desviación explicada» (cascada de atribución contra las fuentes del CEN) y
>   «Riesgo de desacople» (clasificador day-ahead); el pronóstico de CMG gana banda cuantílica
>   calibrada por conformal (CQR) y benchmark contra el PCP/PID. **Hallazgo de datos mayor:** el
>   feed S3 no emitía fila cuando el CMG era 0 → esas horas están AUSENTES, no en cero, y eso
>   sesgaba +10,7% el CMG medio a 30 días en Costos y Estadísticas. `migracion_cmg_ceros.py`
>   escrita para reponerlas desde el liquidado — **PENDIENTE DE EJECUTAR**).
> Anterior: 2026-08-01 (2ª sesión: re-sondeo de los endpoints CEN pendientes y
>   **SSCC programado PCP integrado, desplegado y verificado en producción** — tabla
>   `sscc_programado` (576 filas del 01/08), workflow propio `adquisicion_sscc_prog.yml`
>   (~21 min/día porque el endpoint ignora `idCentral`) y sub «Programado (PCP)» en la vista SSCC.
>   Falta la primera corrida por schedule del cron. `costo-combustible` y `/reduccion` confirmados
>   como recursos no suscritos en 3scale).
> Anterior: 2026-08-01 (reportes PDF/PPT reducidos a informe ejecutivo de
>   gerencia — 2 páginas / 4 slides, con la fuente del programa PID/PCP declarada; sidebar
>   depurado a las fuentes reales post-migración CMG; fixes de layout verificados contra el
>   DOM real: botones del sidebar, franja derecha del gráfico, pills del nodo CMG y menú
>   principal compacto).
> Anterior: 2026-07-29 (CMG online migrado del feed S3 a la API SIP
>   `/costo-marginal-online/v4`: 15 min, 4 barras incl. Angamos/Cochrane, y los CMG = 0 dejan
>   de perderse; tabla `costo_marginal_online_min` + `migracion_cmg_online_min.py`).
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
   y filtrar local por `llave_cmg ∈ CMG_PROG_BARRAS` (Crucero/Tarapacá + Angamos/Cochrane).
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
24. **CMG en barra de central:** el CMG programado PCP/PID trae las llaves `Angamos220` y
    `Cochrane220`, y el CMG real (`bar_transf`) acepta `ANGAMOS_______220` (7 letras+7 `_`) y
    `COCHRANE______220` (8+6) SERVER-SIDE. El S3 online NO las trae (solo 8 barras) y la API
    online con bar_transf da 429/500 → el online sigue en Crucero/Tarapacá. El PCP de CMG es
    **1-indexado** como el PID (page=0 → 502).
25. **CPF/CSF (`/indicador-desempeno-{cpf,csf}/v4`): filtrar por id_unidad 1965-1968, NUNCA por
    texto** — 'ANG' calza con ANGOSTURA. `hora` viene 0-23 como string. Publican con rezago de
    2-3 MESES y por bloques con huecos → la diaria sondea solo días faltantes
    (`dias_faltantes_desempeno`), un día vacío cuesta 2 requests.
26. **`/programas-mantenimiento-mayor/v4` filtra por fecha de PUBLICACIÓN (campo `date`), no por
    las fechas del programa** → una ventana de 45 días hacia atrás captura mantenimientos futuros
    ya publicados. Sin id_central → filtro local por texto (CLAVES_MANT_CTM, incluye O'HIGGINS y
    MEJILLONES: el corredor de evacuación afecta a CTM sin intervenir sus unidades).
27. **CMG online: usar `/costo-marginal-online/v4/findByDate` (API SIP), NO el feed S3.** El S3
    solo expone 8 barras (sin Angamos/Cochrane) y su parser descartaba `total == 0.0` → los
    desacoples con CMG = 0 NUNCA aparecían en el dashboard (bug detectado 2026-07-29). La API
    trae resolución de 15 min, `barra_transf` en formato de 17 caracteres y las barras de las
    propias centrales. Es el feed COMPLETO del sistema (~1.600 barras, ~40 páginas de 4000 por
    día, ordenado por `fecha_minuto`, última página vacía) y NO filtra por barra en el servidor
    → filtrar local por `CMG_ONLINE_BARRAS`. Para el cron de 30 min bajar solo las últimas N
    páginas (`ultimas_paginas=6`); el día completo lo cubren el horario y la migración.
28. **Un CMG de 0 es un DATO, no un faltante** (a diferencia de la gen-real 0.0, que sí es una
    lectura SCADA mala — regla 23). Nunca filtrar ceros en el CMG.
29. **Día del cambio de hora chileno = 25 horas: el CEN emite `hora='24'`** en los endpoints
    horarios (visto en CPF/CSF, 2026-04-04). `"... 24:00:00"` no es timestamp válido → rompe
    `pd.to_datetime` de TODA la vista. Al adquirir, saltar `h > 23`; en loaders de tablas nuevas
    usar `pd.to_datetime(..., errors="coerce")` + dropna como cinturón de seguridad.
30. **Franja en blanco a la derecha de un `make_subplots`: la causa es un `secondary_y` declarado
    y vacío.** Con `specs=[[...],[{"secondary_y": True}]]` Plotly recorta el dominio x al
    **(0, 0.94)** de TODAS las filas (con `shared_xaxes`), aunque no haya ninguna traza en el eje
    secundario → 6% del ancho perdido. Declarar `secondary_y` solo cuando la serie está visible
    (en `gen_unidad.py` va condicionado a `tiene_dem`). Secundario: las anotaciones de
    `add_hline` con `annotation_position` sin prefijo (`"right"`, `"left"`, `"top"`) se dibujan
    FUERA del área y obligan a reservar margen; usar las combinadas (`"top right"`, …).
31. **Botones angostos/desalineados en el sidebar: el problema es el ANCHO del wrapper, no el
    centrado del texto.** `width:100%` sobre el `<button>` se resuelve contra
    `div[data-testid="stButton"]`, que es shrink-to-fit (~145 px) → cada botón queda del ancho de
    su texto y pegado a la izquierda. La solución es de Python: `width="stretch"` en cada
    `st.button`/`st.download_button` (Streamlit ≥1.55). El label ya viene centrado de fábrica
    (Streamlit lo envuelve en un div flex con `justify-content:center`), así que NO hace falta CSS
    de centrado — agregarlo solo enmascara el síntoma.
32. **Verificar el DOM real antes de escribir CSS a medida para Streamlit.** Levantar la app en un
    puerto local + Playwright (`page.evaluate`) y consultar `getBoundingClientRect` y qué reglas
    ganan; deducir el DOM desde una captura de pantalla llevó a dos diagnósticos equivocados
    seguidos. Comprobado así el 2026-08-01: (a) `data-testid="stButton"` SÍ existe (vive en el
    chunk `Button.*.js`, por eso no aparece si se hace grep sobre `index.*.js`); (b) en **1.58.0 el
    grupo de radios NO tiene `data-testid="stRadioGroup"`** — es `div[role="radiogroup"]` a secas
    (la regla 19 quedó desactualizada; el CSS cubre ambos y por eso no se notó); (c) un widget con
    `key=` recibe la clase `.st-key-<key>` en su contenedor, que es el mejor ancla para CSS
    puntual (más estable que `st.container(key=...)` extra).
33. **Medir el costo de un endpoint paginado SIEMPRE con el `limit` de producción, nunca con el
    de exploración.** `servicios-complementarios-programados-pcp/v4` quedó descartado un mes por
    "totalPages≈120.178" — ese número era con `limit` bajo. Con `limit=5000` y ventana de UN día
    son **121 páginas**, o sea 500× menos. `totalPages` escala con `limit`, así que compararlo
    entre endpoints medidos con distinto `limit` no significa nada; la métrica real es
    páginas × segundos con el `limit` que se va a usar.
34. **Bajo paginación sostenida la API SIP se estrangula: ~10 s/página, no los ~0,3-4 s de las
    primeras llamadas.** Medido 2026-08-01: 121 páginas tardaron 1.252 s aunque las páginas
    sueltas del sondeo respondían en 2,5-4,3 s. Estimar el timeout de un workflow con el ritmo
    SOSTENIDO, no con el de la primera página.
35. **`servicios-complementarios-programados-pcp/v4` IGNORA el filtro por central.** `idCentral`,
    `id_central` y `centralId` devuelven los tres el sistema completo (verificado). Filtrar local
    por `id_central ∈ {377,379}`. Además identifica la unidad en `configuracion`/`llave_sscc` como
    **`ANGAMOS_1` / `COCHRANE_2`** — NO la convención `CCH` del SSCC instruido y de las
    instrucciones CMG (mapeo propio `LLAVES_SSCC_PROG`).
36. **Un `provision_mw` de 0 en el SSCC programado es un DATO** (la unidad no fue comprometida en
    ese servicio esa hora), igual que el CMG=0 de la regla 28. No filtrarlo al adquirir; filtrarlo
    solo al graficar. En un día típico solo ~5% de las filas tienen provisión > 0.
37. **Tras crear una tabla nueva, el primer sospechoso de un panel vacío es `st.cache_data`, no la
    adquisición.** Los loaders nuevos llevan `except Exception: return pd.DataFrame()` para no
    reventar antes de que exista la tabla — pero eso hace que un fallo REAL se vea idéntico a
    "sin datos". Si además se abrió el panel antes de correr la migración, el vacío queda cacheado
    el TTL completo (1 h). Orden de diagnóstico: (a) «↻ Actualizar datos» del sidebar
    (`st.cache_data.clear()` + `rerun`); (b) Reboot desde Manage app; (c) recién ahí quitar el catch
    silencioso para ver el error. Pasó el 2026-08-01 con `sscc_programado`.
38. **`st.metric`: usar `delta_color="off"` cuando el texto secundario es una PROPORCIÓN y no una
    variación.** Por defecto Streamlit le pone flecha verde hacia arriba, así que un «7% de las
    filas» se lee como si algo hubiera mejorado. Y el valor principal debe ser CORTO: un
    `"CSF (-) · 266 MW-h"` no cabe en la card y se trunca con puntos suspensivos — la magnitud va
    en la línea de detalle, no en el valor.
39. **Gráfico de barras por día con UN solo día: pasar el eje x a `type="category"`.** Con eje
    temporal Plotly estira la única barra a todo el ancho del área de trazado y parece un bloque de
    color, no una barra. Como categoría, `bargap` la mantiene de ancho razonable (`categoryarray`
    con los días ordenados conserva el orden cronológico).

40. **Un hueco en `costo_marginal` anterior al 2026-07-27 ES UN CERO, no un dato faltante.** El
    feed S3 no emitía fila cuando la barra se desacoplaba (corolario duro de la regla 27).
    Verificado 2026-08-01: de los 142 huecos de la malla horaria de Crucero, TODOS anteriores al
    27/07, los 138 que tienen liquidación son cero el 100% de las veces (máximo 0,00). Consecuencias:
    · **NUNCA `ffill` sobre la malla horaria del CMG online.** Rellenar con el último precio
      conocido inventa precio ALTO justo en las horas de desacople. Le costó al modelo de CMG un
      sesgo de +24,6 USD/MWh (sobreestimaba el 92% de las horas) y una predicción mínima de 14,2
      cuando el real llegaba a 0.
    · **Todo lo que promedie el CMG online sobre un período que cruce esa frontera está sesgado
      hacia arriba** (+10,7% a 30 días, +9,5% a 60): KPI «CMG promedio», curva de duración,
      heatmap hora×día, correlación gen-CMG, y sobre todo la elasticidad precio-demanda, cuyo
      scatter descarta justo los puntos de precio cero (los de mayor inyección ERV). El ingreso
      (Σ gen × CMG) NO se ve afectado: esas horas aportan 0 igual.
    · **El único histórico honesto de ceros es `costo_marginal_real`** (liquidado, nunca los
      filtró). Es el target correcto para cualquier modelo del evento «desacople»: entrenar el
      clasificador sobre el online daba 0 positivos en train y AUC 0,500 exacto.
    · Angamos/Cochrane no tienen huecos (su online arranca el 27/07) pero **sí tienen el problema
      inverso**: su serie online y el CMG real (rezago ~10 días) NO SE SOLAPAN, así que cruzarlas
      deja el set en CERO filas justo en las barras de las propias centrales.

41. **Una causa que abarca meses no explica nada: topear las ventanas de atribución.**
    `limitaciones_transmision` trae registros abiertos (visto: 29/04 → 31/12 con `potencia` 0) y
    `fecha_efectiva_retorno` viene casi siempre NULL. Sin tope, esas cuatro filas atribuían 234 de
    las 323 horas desviadas de ANG1. Reglas: (a) si no hay retorno efectivo, acotar la ventana
    (estimada, o +7 días), nunca `Timestamp.max`; (b) descartar ventanas > 30 días; (c) una causa
    de SUBRENDIMIENTO (limitación, mantenimiento, SSCC) no puede explicar un desvío AL ALZA.

42. **Umbral de detección: percentil de la propia serie, nunca un valor absoluto.** Un corte fijo
    de 27,5 MW (10% de Pmax) marcaba el 50% de las horas como «desviadas», porque el desvío real
    vs programa del complejo tiene mediana ~28 MW y p90 ~200 MW (las unidades entran y salen de
    servicio). Con percentil el detector se autocalibra por unidad y el tamaño de la lista pasa a
    ser una decisión explícita del usuario. Mostrar el MW resultante junto al percentil.

43. **El CMG deriva de régimen en semanas: ponderar el entrenamiento por recencia.** Medido: la
    media de Crucero cayó de 116 (train) → 86 (calib) → 40 USD/MWh (test) en dos meses. Sin peso,
    el modelo aprende el régimen caro. Decaimiento exponencial con vida media ~10 días
    (`sample_weight=0.5**(edad_dias/10)`) + resta de la mediana del residuo medida en el set de
    CALIBRACIÓN (nunca en el de prueba) llevó el sesgo de +24,6 a +3,4 y el MAE de 25,7 a 17,4.
    · **Un R² negativo bajo deriva NO significa modelo malo:** se calcula contra la media del
      período de prueba, que el modelo no conoce. Contrastar siempre con una referencia honesta
      (predecir la media del train daba MAE 76 contra los 17 del modelo). Publicar el SESGO junto
      al MAE: es la métrica que delata la deriva y la que el usuario ve a ojo en el gráfico.

44. **Banda de incertidumbre: regresión cuantílica + conformal, nunca un ensanchamiento ~√h.**
    Tres XGBoost (`objective="reg:quantileerror"`, `quantile_alpha` 0,10/0,50/0,90) y partición
    cronológica 60/20/20. Los cuantiles crudos cubrían el 21% de la realidad (sobreconfianza);
    ensanchando por el percentil 80 del error medido en calibración quedan en 80% verificado.
    Publicar SIEMPRE la cobertura: es lo único que distingue una banda honesta de una decorativa.

45. **No dibujar el «ahora» a mano: usar `utils.plotly_theme.add_linea_ahora`.** Escribir un
    `fig.add_vline(x=ts.timestamp()*1000)` propio (a) depende del huso del contenedor y (b) suele
    terminar marcando el ÚLTIMO DATO en vez del instante actual — dos errores que se suman y dejan
    la línea corrida varias horas. El helper usa `datetime.now(TZ_CHILE)` y dibuja con `add_shape`
    (`add_vline` con `annotation_text` revienta en ejes de fecha en plotly 5.x).

46. **Verificar paneles Streamlit sin navegador con `streamlit.testing.v1.AppTest`.** Complementa
    la regla 32 (Playwright sirve para el DOM/CSS; AppTest para la LÓGICA). `AppTest.from_string`
    corre el script headless contra la DB real y expone `.exception`, `.warning`, `.info`,
    `.dataframe`: detecta NameError y guards mal puestos en segundos y permite barrer todas las
    combinaciones de widgets (`at.session_state["key"]=...`) antes de commitear. Para inspeccionar
    una figura Plotly, `AppTest` no la expone → monkeypatchear el helper de render (`_show`) y
    capturar el objeto.

47. **El `status` de `limitaciones_transmision` NO indica vigencia: el CEN nunca cierra el
    registro.** Verificado 2026-08-02 contra la DB: de 21 limitaciones del período, 16 seguían en
    «pendiente» con su `fecha_retorno_estimada` ya pasada (algunas de febrero) y
    `fecha_efectiva_retorno` venía NULL en TODAS. Contar «pendientes» hacía que el panel, la
    bitácora y el informe ejecutivo declararan activas limitaciones muertas hace meses.
    · La señal honesta es la VENTANA: `fin = efectiva | estimada | inicio+7d`, topeada a
      `inicio+30d` (regla 41). Estados: **activa** (la ventana contiene el instante),
      **vencida** = cerrada de facto (pendiente con ventana pasada), **cerrada**, **futura**.
    · Vive en `utils/eventos.py` (`ventana_limitacion`, `estado_limitacion`,
      `preparar_limitaciones`, `limitaciones_vigentes`). Cualquier consumidor nuevo de
      `limitaciones_transmision` DEBE pasar por ahí — nunca filtrar por `status` a mano.

48. **El corredor de evacuación es CONTEXTO, no causa.** Los mantenimientos de S/E O'Higgins,
    Mejillones–O'Higgins o Laberinto duran semanas y aplican a las 4 unidades, así que al
    atribuir desvíos se llevaban TODO: el primer «Panorama» reportó 82.074 MWh y US$ 2,4 M de
    energía no generada, cuando lo atribuible de verdad era 0. Reglas: `explicar_horas` excluye
    `corredor` por defecto; el impacto en MWh/USD solo cuenta intervenciones DIRECTAS
    (limitación o mantenimiento de la unidad); el gráfico de cobertura muestra el corredor como
    una tercera categoría gris, separada de «causa directa» y de «sin causa registrada».
    · Corolario de conteo: un evento de corredor aparece 4 veces (una por unidad) → deduplicar
      por (título, ini, fin, instalación) antes de mostrar un KPI de cantidad, o «3
      intervenciones» se publica como «12».
    · **Corolario de UI (feedback del usuario, 2026-08-02): el corredor NO va en la serie de
      tiempo de la unidad.** En esa franja solo deben aparecer eventos que intervienen la
      MÁQUINA: limitaciones de la unidad y mantenimiento mayor / outage de la propia térmica.
      Las subestaciones y líneas dejaban una banda permanente que cubría casi todo el gráfico y
      copaban el banner de eventos latentes. `render_gen_unidad` llama a `eventos_unidad(...,
      incluir_corredor=False)`; el contexto del corredor vive en Operación > Panorama (gris,
      etiquetado como contexto) y en la subsección Mant. mayor.
    · `mantenimiento_mayor` NO trae `id_unidad`: el mapeo a unidad es por texto
      (`unidades_mantenimiento`). Hoy la tabla solo tiene líneas y subestaciones del corredor;
      cuando el CEN publique el PMPM de las unidades de Angamos (outage coordinado para octubre
      2026), el mapeo lo toma solo y aparece como evento latente sin tocar código.

49. **`st.metric` trunca con puntos suspensivos y no avisa.** Con 6-7 KPIs en una fila las cards
    quedan en ~180 px y se recortan los TRES campos: label («INGRESO ESTIM…»), valor
    («$3,74…») y delta. La solución es de tres partes y ninguna basta sola:
    (a) `render_kpi_grid` (components/_common.py) reparte en filas de máximo 4-5;
    (b) el CSS pone `white-space:normal` + `text-overflow:clip` en label y delta y escala el
        valor con `clamp(1.1rem, 1.55vw, 1.7rem)`;
    (c) los montos grandes se abrevian con `fmt_usd` («$3.7 M») y el valor exacto va en `help`.
    · Verificado midiendo `scrollWidth > clientWidth` en las 12 cards con Playwright (regla 32):
      `cut:false` en todas. Comprobar así, no a ojo — la elipsis se ve idéntica a un valor corto.
    · La flecha del delta se oculta con `[class*="st-key-kpigrid_"] [data-testid="stMetricDelta"]
      svg`: `delta_color="off"` (regla 38) apaga el color pero NO la flecha.

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
CMG online:      API CEN /costo-marginal-online/v4 (15 min) — Crucero/Tarapacá/Angamos/Cochrane
                 (feed S3 del Coordinador solo como fallback)
CMG prog/real:   /cmg-programado-pid/v4 + /costo-marginal-real/v4
SSCC:            API CEN Operaciones /servicios-complementarios/v1
Reportes:        ReportLab (PDF, 2 págs) + python-pptx (PPT, 4 slides) + matplotlib (figuras)
                 — informe EJECUTIVO de gerencia, paleta AES, in-memory
ML:              scikit-learn (Isolation Forest) + xgboost (forecast CMG)
Autorefresh:     streamlit-autorefresh (300.000 ms = 5 min, keep-alive — ver regla 21)
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
├── Adquisicion_diaria.py           ← cron 08:20 UTC — CMG real (4 barras) + CMG prog PCP, pronóstico
│                                      demanda, solicitudes, maestro, mantenimiento mayor, demanda neta,
│                                      mix diario, desempeño SSCC (días faltantes)
├── Adquisicion_sscc_prog.py        ← cron 09:50 UTC — SSCC PROGRAMADO PCP (workflow propio: ~21 min
│                                      por día, tope MAX_DIAS=2)
├── backfill_programada.py          ← utilidad puntual (recupera PCP por rango)
├── migracion_*.py                  ← migraciones puntuales (correr vía workflow migracion.yml)
│                                      · migracion_cmg_ceros.py: repone en costo_marginal las horas
│                                        de CMG = 0 que el S3 nunca emitió (modo simulación por
│                                        defecto; `apply` para escribir). PENDIENTE DE EJECUTAR
├── utils/
│   ├── db.py                       ← capa unificada REST/psycopg2 (fetch, write_*, last_ts, test_conn)
│   ├── data.py                     ← loaders cacheados @st.cache_data (load_real/prog/cmg/sscc/...)
│   ├── reports.py                  ← generar_pdf (2 págs) / generar_ppt (4 slides) — INFORME
│   │                                  EJECUTIVO para gerencia: KPIs del complejo (energía, ingreso
│   │                                  estimado, FP, disponibilidad, CMG), destacados narrativos,
│   │                                  tabla por unidad, series consolidadas y eventos agregados
│   └── plotly_theme.py             ← apply_aes_layout, estilo_serie, hover, add_linea_ahora, hex_to_rgba
├── components/
│   ├── _common.py                  ← metricas_precision, render_guia/tabla_guia, render_cards_unidad,
│   │                                  fmt_usd + render_kpi_grid (KPIs sin truncado — regla 49)
│   ├── sidebar.py                  ← render_sidebar → filtros; estado de adquisición (fuentes
│   │                                  continuas con dot de frescura + último registro);
│   │                                  export PDF/PPT ejecutivo (botones con width="stretch")
│   ├── kpis.py                     ← render_kpis — cards por unidad + alarma de TRIP (UMBRAL_TRIP=5 MW)
│   ├── gen_unidad.py               ← render_gen_unidad — series real/prog/CMG + selector nodo CMG +
│   │                                  ingreso estimado por unidad (junto al MAE, delta vs semana pasada) +
│   │                                  alerta potencia 0 (<5 MW = trip) en la serie (UMBRAL_CERO=5.0)
│   ├── costo.py                    ← render_costo — deep-dive económico: benchmarking CMG (online/prog/
│   │                                  real), elasticidad precio-demanda, ingreso diario, mapa de valor,
│   │                                  cascada de ingreso, calidad del pronóstico CMG
│   ├── estadisticas.py             ← render_estadisticas — heatmap CMG hora×día, curva de duración,
│   │                                  ingreso acumulado, perfil horario gen, aporte/FP, correlación, precisión
│   ├── ml.py                       ← render_ml — suite de 3 modelos (rediseño 2026-08):
│   │                                  «Pronóstico CMG» (3 XGBoost cuantílicos + CQR, peso por
│   │                                  recencia y debias, ingreso esperado 24h, benchmark vs PCP/PID),
│   │                                  «Desviación explicada» (2 detectores + cascada de atribución),
│   │                                  «Riesgo de desacople» (clasificador day-ahead sobre CMG real)
│   ├── novedades.py                ← render_novedades — estado actual por unidad (bajo la serie CMG)
│   ├── bitacora_auto.py            ← render_bitacora_auto — bitácora cronológica de la unidad activa
│   │                                  (SSCC + despacho + limitaciones + novedades manuales + solicitudes
│   │                                  que mencionan Angamos/Cochrane), ayer x defecto
│   ├── operacion.py                ← render_panorama — primera pantalla de la vista «Operación»:
│   │                                  estado actual por unidad, timeline unificado de eventos,
│   │                                  energía no generada por evento (MWh y USD al CMG horario)
│   │                                  y cobertura documental del desvío
│   ├── limitaciones.py / sscc.py / despacho_cmg.py / solicitudes.py   ← vistas de Operación
│   │                                  (sscc.py incluye subs «Programado (PCP)» — provisión MW
│   │                                   programada — y «Desempeño (CPF/CSF)» — panel de factores)
│   ├── mantenimiento.py            ← render_mantenimiento — PMPM CTM: KPIs + timeline Gantt + tabla
│   ├── manual.py                   ← render_programada_manual / render_real_manual (CRUD + override)
│   ├── datos.py                    ← render_datos_horarios / render_bitacora
│   └── infotecnica.py              ← fichas técnicas por unidad (unidades_maestro + fallback config)
├── pages/ml_analysis.py            ← wrapper delgado que llama components.ml.render_ml()
└── .github/workflows/
    ├── adquisicion.yml             ← cron :05 (núcleo horario, timeout 60)
    ├── adquisicion_potencia.yml    ← cron :25/:55 (gen-real + CMG S3)
    ├── adquisicion_operaciones.yml ← cron :10/:40 (SSCC + despacho + limitaciones)
    ├── adquisicion_diaria.yml      ← cron 08:20 UTC (endpoints lentos que cambian poco)
    ├── adquisicion_sscc_prog.yml   ← cron 09:50 UTC (SSCC programado PCP, timeout 60)
    └── migracion.yml               ← workflow_dispatch (corre cualquier migracion_*.py)
```

---

## NAVEGACIÓN (menú plano de 4 vistas — desde 2026-07-03; «Operación» desde 2026-08-02)

Se abandonaron las categorías desplegables (popovers). El menú es un **segmented control**
(`st.radio` horizontal) de 4 vistas planas; las sub-secciones viven dentro con radio-pills:

| Vista | Sub-secciones |
|-------|---------------|
| **Resumen** | Gráfico por unidad (real/prog/CMG) + **franjas de evento de la MÁQUINA** (limitación / mantenimiento de la unidad; nunca corredor — regla 48) con atribución de las detenciones y aviso de eventos latentes + selector de nodo CMG + bitácora automática + novedades |
| **Análisis** | Costos · Estadísticas (consolidada) · Predicción (ML: Pronóstico CMG · Desviación explicada · Riesgo de desacople) |
| **Operación** | **Panorama** · Limitaciones · SSCC (incl. Programado PCP y Desempeño CPF/CSF) · Despacho CMG · Solicitudes · Mant. mayor |
| **Datos** | Ingreso Manual · Datos & Bitácora · Infotécnica (**las 2 primeras tras contraseña `jt`**) |

- **«Restricciones» → «Operación» (2026-08-02):** el nombre viejo no encapsulaba la vista —
  SSCC, despacho por CMG y solicitudes no son restricciones sino hechos operacionales del CEN
  sobre las unidades. La subsección nueva **«Panorama»** abre la vista y consolida las cinco
  fuentes en una lectura: estado actual por unidad + evento vigente + próximo evento con cuenta
  regresiva, timeline unificado, energía no generada valorizada al CMG, y cobertura documental
  del desvío (causa directa / solo corredor / sin causa registrada).
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

## ADQUISICIÓN — 5 WORKFLOWS ESCALONADOS

Réplica del patrón de separación por concern. El job horario único se pasaba del timeout en
PCP/PID (lentos paginados) → se separaron los endpoints rápidos y los lentos-que-cambian-poco.

| Workflow | Script | Endpoints | Cron | Timeout |
|----------|--------|-----------|------|---------|
| Horaria | `Adquisicion.py` | **Núcleo:** PCP · PID · CMG-programado (+ gen-real/CMG S3 de respaldo) | `:05` | 60 min |
| Potencia | `Adquisicion_potencia.py` | gen-real + CMG online 15 min (últimas 6 págs) | `:25,:55` | — |
| Operaciones | `Adquisicion_operaciones.py` | SSCC + Despacho CMG + Limitaciones | `:10,:40` | — |
| Diaria | `Adquisicion_diaria.py` | CMG real (4 barras) + CMG prog PCP + pronóstico demanda + solicitudes + maestro + mantenimiento mayor + demanda neta + mix diario + desempeño SSCC | `08:20 UTC` | 60 min |
| SSCC prog | `Adquisicion_sscc_prog.py` | SSCC programado PCP (1 día, ~21 min) | `09:50 UTC` | 60 min |

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
| `costo_marginal` | `(barra_transf, fecha_hora)` DO UPDATE | CMG online HORARIO (promedio de los 15 min de la API SIP; S3 solo de fallback). 4 barras. **Las horas < 2026-07-27 con CMG = 0 FALTAN** (el S3 no emitía fila) → `migracion_cmg_ceros.py` las repone marcadas `origen='LIQUIDADO'` |
| `costo_marginal_online_min` | `(barra_transf, fecha_minuto)` | CMG online 15 min desde `/costo-marginal-online/v4`. 4 barras, incluye CMG=0 |
| `costo_marginal_programado` | `(barra, fecha_hora, fuente)` | CMG PID (horario) + PCP (diaria). 4 barras: + Angamos/Cochrane. `fuente` desde `migracion_endpoints_ctm.py` |
| `costo_marginal_real` | `(barra_transf, fecha_hora)` | CMG real liquidado, rezago ~10 días. `limit=50`. 4 barras (+ ANGAMOS/COCHRANE 220) |
| `mantenimiento_mayor` | `(correlativo, nombre_sub_instalacion, fecha_inicio_programa)` | PMPM filtrado por relevancia CTM (CLAVES_MANT_CTM) |
| `desempeno_sscc` | `(unidad, tipo, fecha_hora)` | CPF/CSF horario por unidad; rezago 2-3 meses; diaria sondea días faltantes |
| `demanda_neta` | `fecha_hora` | horaria SEN (gen bruta/ERV/neta) — feature del forecast CMG |
| `mix_generacion_diaria` | `(fecha, tecnologia)` | getDailySum por tecnología — peso térmico en Costos |
| `sscc_instrucciones` | `(fecha, id_configuracion, instruccion_sscc, inicio_periodo)` | Cochrane = CCH1/CCH2 |
| `sscc_programado` | `(unidad, tipo_servicio, fecha_hora)` | SSCC PROGRAMADO PCP (provisión MW). Unidad por `configuracion` = ANGAMOS_1/COCHRANE_2 (NO la convención CCH). Dedup por `fecha_programa` |
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
CMG_ONLINE_BARRAS = {"CRUCERO_______220","TARAPACA______220","ANGAMOS_______220","COCHRANE______220"}
CMG_NODOS = {"CRUCERO_______220": "crucero", "TARAPACA______220": "tarapaca"}  # solo el fallback S3
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

- [ ] **EJECUTAR `migracion_cmg_ceros.py` (2026-08-01, 3ª sesión) — es lo primero de la lista.**
      Repone en `costo_marginal` las 272 horas de CMG = 0 que el feed S3 nunca emitió (regla 40),
      tomándolas del liquidado. Hasta que corra, el KPI «CMG promedio» y varios gráficos de Costos
      y Estadísticas sobreestiman ~10% en cualquier ventana que cruce el 27/07.
      · Correr primero SIN argumento (modo simulación: imprime filas y efecto por barra, no escribe).
      · Después `migracion.yml → script=migracion_cmg_ceros.py · arg=apply`.
      · Al terminar, «↻ Actualizar datos» en el dashboard (regla 37) y verificar que el CMG medio
        de Crucero a 30 días baja de ~95,8 a ~85,6 USD/MWh.
      · El script detecta en runtime si `costo_marginal.fecha_hora` es TEXT o timestamp: esa tabla
        guarda el formato con «T» y `costo_marginal_real` con espacio. NO se pudo comprobar el tipo
        desde local (regla 10) — si la simulación imprime algo raro ahí, revisar antes de aplicar.

- [ ] **Outage mayor de Angamos (octubre 2026) — esperando publicación del CEN (2026-08-02).**
      El usuario decidió NO crear registro manual: el evento aparecerá solo cuando el Coordinador
      lo publique en el PMPM. `unidades_mantenimiento` (utils/eventos.py) ya mapea por texto
      «ANGAMOS» + «U1/U2/UNIDAD n» → ANG1/ANG2, y el banner de eventos latentes de la serie lo
      mostrará con cuenta regresiva sin tocar código. Verificar en octubre que (a) la adquisición
      diaria lo trajo (el filtro de relevancia `CLAVES_MANT_CTM` incluye Angamos) y (b) el mapeo
      lo asigna a las unidades correctas y NO como «corredor» — hoy la tabla solo tiene
      instalaciones del corredor, así que esa rama del mapeo nunca se ha ejercitado con datos
      reales.

- [ ] **Cobertura del desvío: el 100% de las horas bajo programa aparece sin causa directa
      (2026-08-02).** Es un resultado correcto dado el dato (no hubo limitaciones ni
      mantenimientos de unidad en la última semana), pero conviene mirarlo con una ventana que
      SÍ contenga eventos (p. ej. junio) para calibrar el umbral `UMBRAL_DESVIO_MW = 10` de
      `components/operacion.py`. Con 10 MW casi toda hora de rampa cuenta como desvío; puede que
      convenga un percentil por unidad, como en «Desviación explicada» (regla 42).

- [ ] **Costos y Estadísticas: revisar los paneles tras la migración (2026-08-01, 3ª sesión).**
      La auditoría identificó QUÉ está sesgado pero no se tocó ningún panel: la corrección es de
      datos, no de código. Una vez repuestos los ceros, confirmar que (a) el KPI «CMG promedio»
      baja, (b) el heatmap hora×día deja de tener huecos, (c) la **elasticidad precio-demanda**
      cambia de pendiente — es la más afectada, porque su scatter descartaba justo los puntos de
      precio cero, que son los de mayor inyección ERV.

- [ ] **Pronóstico CMG: sesgo residual y barras sin histórico (2026-08-01, 3ª sesión).**
      Tras el fix quedan +3,4 USD/MWh de sesgo y R² −0,21 en Crucero (Tarapacá ya da R² +0,20).
      No se cierra más con 2 meses de datos y sin hidrología ni costo de combustible — el
      `costo-combustible` sigue siendo recurso no suscrito en 3scale. Revisar cuando haya ~3 meses
      de histórico limpio post-27/07.
      · **Angamos y Cochrane muestran «datos insuficientes» en el panel de Pronóstico** y es
        correcto: su CMG online arranca el 27/07 (~130 horas). Se destraba solo con el tiempo;
        el umbral está en 400 filas dentro de `_seccion_cmg`.

- [ ] **El modelo pierde el NIVEL de precio contra el PID del Coordinador (2026-08-01).** Medido en
      las 3 ventanas del benchmark (78h: 36,9 vs 23,8). Es esperable — el PCP/PID sale de una
      optimización del sistema completo — y el panel lo declara explícitamente. Se probó anclar el
      modelo al PCP y predecir el RESIDUO: perdió peor (54 vs 29), así que la idea está descartada,
      no pendiente. Lo que sí valdría la pena si algún día se quiere ganar esa comparación es
      replicar las exógenas de Pulsar: energía embalsada del SEN y lluvia acumulada 72h sobre las
      cuencas. Hoy no están en este proyecto.

- [ ] **SSCC programado PCP — falta la PRIMERA corrida automática del cron (2026-08-01).** La
      migración corrió OK y el panel está verificado en producción (ver historial), pero
      `adquisicion_sscc_prog.yml` **todavía no se ha ejecutado por schedule**: la primera es el
      2026-08-02 ~09:50 UTC. Esa corrida pedirá el 01/08, que ya está cargado → el log debe decir
      `0 nuevas, 576 actualizadas` (correcto, no es fallo). Confirmar además que termina dentro del
      timeout de 60 min; la migración equivalente tardó 23m40s, así que el margen es holgado.
      · Solo hay UN día en la tabla (01/08). Para que los gráficos diarios muestren una serie en
        vez de una barra, disparar a mano `adquisicion_sscc_prog.yml` con `dias_atras=2` varias
        veces (el cron solo agrega un día por jornada).
      · **Validar con criterio de negocio el reparto entre unidades**: el 01/08 dio ANG2 206,3 ·
        CCR1 134,5 · ANG1 80,0 · CCR2 67,4 MW-h. La diferencia de 3× entre ANG2 y CCR2 es el punto
        donde un error de mapeo pasaría desapercibido, porque este endpoint usa `ANGAMOS_2` en vez
        de la convención `CCH` del resto del proyecto (`LLAVES_SSCC_PROG`, regla 35).

- [ ] **Cruzar programado vs instruido vs desempeño (2026-08-01).** Ahora que existen las tres
      piezas (`sscc_programado` · `sscc_instrucciones` · `desempeno_sscc`), el panel las muestra
      por separado. El análisis que de verdad interesa es el cruce: ¿se instruyó lo que se
      programó, y con qué nota se prestó? Requiere conciliar granularidades distintas
      (programado = horario; instruido = períodos inicio→fin; desempeño = horario con rezago de
      2-3 meses) → dejarlo para cuando haya suficiente historia de programado acumulada.

- [ ] **Reportes ejecutivos (2026-08-01):** el PDF/PPT nuevo se probó con datos sintéticos y
      corriendo la app local contra la DB de producción, pero NADIE lo ha descargado todavía desde
      Streamlit Cloud ni lo ha visto un destinatario de gerencia. Al primer uso real revisar:
      (a) que el ingreso estimado y el factor de planta cuadren con lo que espera el negocio —
      el ingreso es referencia de mercado (Σ MWh × CMG), NO una liquidación; (b) si conviene
      sumar el desempeño SSCC (CPF/CSF) como quinto KPI; (c) que los «Puntos destacados»
      autogenerados no digan nada falso cuando el período tiene huecos de datos.

- [ ] **Verificar el layout en Streamlit Cloud:** los cuatro fixes de layout (botones
      `width="stretch"`, `secondary_y` condicional, pills del nodo CMG, menú compacto) se
      midieron en local con Playwright. Confirmar que se ven igual en producción tras el
      redeploy — el CSS a medida ya rompió sin aviso una vez con un cambio de versión (regla 19).

- [ ] **CMG online por API (2026-07-29):** migración corrida OK (3 días, 19 min: 854 puntos de
      15 min, 148 en 0, 232 filas horarias nuevas de Angamos/Cochrane). Falta verificar que el
      cron de potencia (:25/:55) no se alarga de más con las 6 páginas + reintentos por 429, y
      tener presente que el histórico horario ANTERIOR al 27/07 en `costo_marginal` viene del S3
      (sin ceros, solo Crucero/Tarapacá) → no comparar períodos a través de esa frontera.

- [ ] **`POT_MIN_PROG = 60` marca como fantasma pruebas REALES de mínimo técnico** (detectado
      2026-07-29, NO urgente — el usuario confirmó que la programación respondió bien a esas
      pruebas). Los programas con `0 < mw < 60` en `Adquisicion.py` (dedup PCP línea ~328 y PID
      línea ~424) se tratan como inválidos, pero en julio 2026 son **exploraciones de nuevos
      mínimos técnicos** que el CEN sí programó: 54 filas PID / 69 PCP, rango **28,3–55,2 MW**,
      concentradas en **ANG1** (42 de 54) y agrupadas en campañas (10-13/07, 22-24/07, 27/07).
      NO se borran (el umbral solo actúa como desempate), pero si el CEN reemite el PID de una
      hora de prueba y existe una versión anterior ≥60 MW, el dedup prefiere la vieja → el
      dashboard mostraría el programa equivocado justo en las horas de prueba.
      · Revisar SI aparece una discrepancia real en el gráfico de ANG1.
      · Para arreglarlo hace falta saber qué magnitud tenían los fantasmas originales: si eran
        ≪28 MW basta bajar el umbral a ~25; si eran del mismo orden que las pruebas, el umbral
        no los distingue → quitar el criterio de magnitud y quedarse con el `fecha_programa` /
        `hora_programa` más reciente (semántica natural de una reemisión del CEN).

- [ ] **Limpieza:** decidir si archivar/borrar `exportar_datos_ml.py` y `ml_pruebas.py` (material
      viejo de experimentos ML, no usados por la app).
- [ ] **Verificación operacional:** confirmar que el cron horario aligerado termina sin timeout,
      que la diaria corre bien (dispararla 1× manual) y que la columna `origen` se auto-creó.
- [ ] **Endpoints 2026-07-08:** verificar que `migracion_endpoints_ctm.py` corrió OK (Actions),
      que la diaria nueva termina dentro del timeout (desempeño SSCC sondea ~120 días faltantes
      la primera vez) y que Costos/SSCC/Restricciones muestran los paneles nuevos con datos.
- [ ] **Desempeño SSCC:** cuando el CEN publique feb/may/jun 2026, la diaria los incorpora sola
      (verificar en el panel). Evaluar sumarlo al PDF ejecutivo.
- [ ] **`/instrucciones-operacionales-sscc/v4` — descarte a re-evaluar.** Sigue vivo (200, 122 págs
      con limit=100 en 7 días). Se descartó en 2026-07-08 por "duplicar" el SSCC de Operaciones
      `/servicios-complementarios/v1`, pero NO se verificó fila a fila y expone tres campos que el
      v1 no tiene a la vista: `disponibilidad`, `estado`, `sscc_baja`. Comparar contra
      `sscc_instrucciones` antes de darlo por cerrado.

- [ ] **`/potencia-activa-reactiva-unidad/v4` — vivo, sigue sin justificarse.** Re-sondeado
      2026-08-01: devuelve **0 registros para ayer** (rezago), pero sí responde en fechas pasadas
      (2.207 págs el 25/07, 1.730 el 02/07, 1.985 el 03/05, con limit=100). Sigue siendo SCADA-level
      sin filtro por central y no alimenta nada del dashboard actual. Solo vale la pena si algún día
      se quiere análisis de reactivos.

- [ ] **Endpoints CEN no disponibles (re-verificado 2026-08-01):** `/net-power/v1/findByDate` (404
      "Recurso no encontrado") · `/costo-combustible/v3` y `/v4` (404 **"No Mapping Rule matched"** —
      EMPEORÓ: antes daba 502, o sea existía y estaba roto; ahora es recurso no suscrito) ·
      `/reduccion/v1/generacion` (404 "No Mapping Rule"). Los dos últimos NO se arreglan con código:
      hay que pedirle al CEN que agregue el recurso al plan en 3scale.

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
- **2026-07-08 (2ª sesión) — Barrido de endpoints CEN + integración de 6 nuevos:**
  · Barrido en vivo de 18+ endpoints del consolidado (4 planes) con las keys reales, cruzado con
    los hallazgos de Pulsar. Muertos y descartados quedaron documentados en PENDIENTES VIVOS.
  · **CMG en barra de central** (hallazgo mayor): llaves `Angamos220`/`Cochrane220` en CMG
    programado PCP/PID (filtro local) y `bar_transf=ANGAMOS_______220`/`COCHRANE______220`
    server-side en CMG real. `CMG_PROG_BARRAS` pasó a 4 barras; `fetch_cmg_programado` ahora
    parametrizado por fuente (PID horario / PCP en la diaria); `costo_marginal_programado` ganó
    columna `fuente` con UNIQUE (barra, fecha_hora, fuente).
  · **Mantenimiento mayor** (`/programas-mantenimiento-mayor/v4`, vivo y barato): tabla
    `mantenimiento_mayor` filtrada por relevancia CTM (CLAVES_MANT_CTM incluye el corredor
    Mejillones–O'Higgins), vista nueva «Mant. mayor» en Restricciones (`components/mantenimiento.py`:
    KPIs + timeline Gantt + tabla) y eventos en la bitácora automática (badge ámbar; corredor de
    evacuación aplica a las 4 unidades).
  · **Desempeño SSCC CPF/CSF** (`/indicador-desempeno-{cpf,csf}/v4`): tabla `desempeno_sscc`
    (horario por unidad, factores de remuneración), la diaria sondea SOLO días faltantes
    (`dias_faltantes_desempeno`, rezago CEN 2-3 meses con huecos), panel nuevo «Desempeño
    (CPF/CSF)» dentro de la vista SSCC (serie diaria del factor por unidad + participación).
  · **Demanda neta** (`/demanda-neta/v4`): tabla `demanda_neta` (horaria SEN) como feature
    `dem_lag_24h` del forecast probabilístico de CMG en ml.py (disponible en todo el horizonte
    de 24h; XGBoost tolera los NaN del rezago).
  · **Mix diario** (`getDailySum`): tabla `mix_generacion_diaria`; gráfico «Peso térmico del SEN»
    en Costos + gráfico «CMG programado en barra de central vs Crucero» con spread medio.
  · Migración `migracion_endpoints_ctm.py` (DDL + RLS + backfills: CMG real 4 barras 21d, CMG
    PCP 7d / PID 3d, demanda neta 120d, mantenimiento 60d, mix 60d); el desempeño SSCC se
    puebla solo desde la diaria. Todos los fetch probados en vivo antes del commit.

---

- **2026-07-29 — CMG online por API (fin del feed S3):** el gráfico de Resumen nunca mostraba
  los desacoples con CMG = 0. Causa: `fetch_cmg_nodos` (feed S3) descartaba `total == 0.0` y el
  S3 solo trae 8 barras (sin Angamos/Cochrane). Se replicó el patrón de Pulsar: nueva
  `fetch_cmg_online_api` sobre `/costo-marginal-online/v4/findByDate` (15 min, ~40 págs/día,
  filtro local a `CMG_ONLINE_BARRAS`), `agregar_cmg_horario` (promedio con ceros incluidos →
  `costo_marginal`) y tabla nueva `costo_marginal_online_min` con el detalle de 15 min.
  `adquirir_cmg_online` orquesta ambos y cae al S3 solo si la API no responde. El cron de
  potencia baja las últimas 6 páginas del día (lo más fresco); el horario hace ayer+hoy
  completos. Dashboard: `load_cmg_min` + serie de 15 min en `gen_unidad` (fallback al horario),
  y el selector de nodo ahora ofrece las 4 barras. Migración: `migracion_cmg_online_min.py`.
  Verificado de paso: el programa PID volvió a emitirse (datos hasta 2026-07-31).

- **2026-08-01 — Reportes ejecutivos + panel de adquisición + fixes de layout:**
  · **`utils/reports.py` reescrito como informe de gerencia.** Antes: portada + página/slide por
    unidad + tablas largas de SSCC/limitaciones/bitácora (8-9 páginas). Ahora **PDF de 2 páginas**
    (1: KPIs del complejo — energía GWh, ingreso estimado kUSD, factor de planta, disponibilidad,
    CMG promedio — + «Puntos destacados» narrativos autogenerados + tabla por unidad + aporte por
    unidad y eventos; 2: series consolidadas de generación de las 4 unidades y CMG) y **PPT de 4
    slides** (portada · resumen ejecutivo · desempeño por unidad · CMG/aporte/eventos). Métricas
    nuevas en `_metricas_unidad` / `_metricas_complejo`: energía, FP, disponibilidad (horas ≥ 5 MW,
    regla 23), sesgo y MAE vs programa, ingreso = Σ (MWh × CMG de la hora). Los 4 gráficos por
    unidad se reemplazaron por UNA figura con las 4 series (color por entidad, regla 22).
  · **Origen del programa explícito** (`_fuente_programa`): el reporte declara si la referencia es
    PCP, PID o manual y avisa cuando el CEN no emitió PID (pasó desde 2026-07-08 y la desviación se
    leía como si siempre comparara contra lo mismo). En el dashboard, `gen_unidad.py` agrega un
    caption bajo el gráfico con cuántas horas de la serie PID son en realidad PCP de relleno.
  · **Panel de adquisición del sidebar actualizado a la realidad post-migración CMG:** fuentes
    continuas Gen. real · Programada PCP · Programada PID · CMG online 15 min (cae a «CMG online
    (S3)» si `costo_marginal_online_min` está vacío) · CMG programado; último registro de Despacho
    CMG, SSCC, Limitaciones, CMG real liquidado y Mant. mayor; bloque nuevo «Frecuencia» con la
    cadencia de los 4 crons (el texto fijo «cada 30 min» era falso para 3 de ellos).
    NOTA: más tarde en la misma sesión el usuario pidió depurar el panel → se quitaron la fila
    «Conectado · Supabase», «Mant. mayor» y el bloque «Frecuencia» completo (ver último bullet).
    La cabecera manda: el estado final es fuentes continuas + último registro, sin cadencias.
  · **Fix botones del sidebar (2º intento, este sí):** el primer diagnóstico (centrado del label
    por CSS) era incorrecto. Inspeccionando el DOM real con Playwright: el `<button>` ya tenía
    `width:100%`, pero su wrapper `div[data-testid="stButton"]` es shrink-to-fit (145 px) → botones
    angostos, de distinto ancho y pegados a la izquierda. Se resolvió con `width="stretch"` en los
    `st.button`/`st.download_button` del sidebar. Verificado: 260 px los tres, texto a 0 px del
    centro. Ver reglas 31 y 32.
  · **Fix franja en blanco del gráfico de Resumen (2º intento):** la anotación «Prom» fuera del
    área era solo parte del problema. La causa real: el `specs=[[...],[{"secondary_y": True}]]`
    de la fila del CMG recortaba el dominio x a (0, 0.94) aunque la demanda no estuviera visible.
    Ahora `secondary_y` se declara solo si `tiene_dem`; margen derecho 70 → 12. Ver regla 30.
  · **Selector de nodo CMG a ancho completo:** estaba dentro de `st.columns([1,2])`, así que las 4
    barras se envolvían en una grilla 2x2. Ahora va a ancho completo y el CSS (anclado en
    `.st-key-nodo_cmg`) reparte los 4 pills en una sola fila (277 px cada uno).
  · **Ajustes finos (misma sesión):** menú principal compacto (el `<hr>` del área principal y el
    contenedor `.st-key-vista` dejaban ~110 px muertos arriba y abajo; ahora ~35 px). Sidebar
    depurado: fuera la fila «Conectado · Supabase» (el error de conexión se sigue mostrando en el
    camino de fallo), fuera «Mant. mayor (inicio)» y fuera el bloque «Frecuencia». El rótulo de
    exportación pasó a «Exportar reporte ejecutivo». Verificado en la app real con Playwright: el
    área de trazado del gráfico queda a 4 px del borde derecho del contenedor (antes ~87).

- **2026-08-01 (2ª sesión) — Re-sondeo de endpoints pendientes + SSCC programado PCP integrado:**
  · **Re-sondeo en vivo de los 7 endpoints pendientes** con las keys reales. Tres notas de
    PENDIENTES VIVOS estaban desactualizadas: `costo-combustible` v3/v4 pasó de 502 a 404 "No
    Mapping Rule" (recurso no suscrito en 3scale, no se arregla con código, igual que
    `/reduccion/v1/generacion`); `potencia-activa-reactiva-unidad` revivió (responde en fechas
    pasadas, 0 filas para ayer por rezago) pero sigue sin justificarse; `net-power` sigue 404.
  · **Hallazgo: `/servicios-complementarios-programados-pcp/v4` era mucho más barato de lo
    documentado.** El "totalPages≈120.178" que lo tuvo descartado un mes estaba medido con `limit`
    bajo — con `limit=5000` y ventana de UN día son **121 páginas**. Se paginó el día completo para
    medirlo de verdad: 4.012 filas CTM, solo TER ANGAMOS/TER COCHRANE, los 6 servicios (CPF/CSF/CTF
    en (+) y (−)), con `provision_mw`, `barra` y `fecha_programa`. Ver reglas 33 y 34.
  · **Integrado** — cerraba el hueco real de tener el SSCC instruido y la nota de desempeño pero no
    lo PROGRAMADO: `LLAVES_SSCC_PROG` (mapeo `ANGAMOS_1`/`COCHRANE_2` → unidad; este endpoint NO usa
    la convención CCH — regla 35), `fetch_sscc_programado_pcp` (dedup por `fecha_programa` más
    reciente, como el PCP de generación) + `upsert_sscc_programado`, tabla `sscc_programado`,
    `migracion_sscc_programado.py`, loader `load_sscc_programado` y sub «Programado (PCP)» en la
    vista SSCC (KPIs, provisión diaria apilada por unidad, desglose por servicio, perfil horario,
    detalle). Los ceros no se filtran al adquirir (regla 36).
  · **Workflow propio `adquisicion_sscc_prog.yml` (09:50 UTC), no dentro de la diaria:** el endpoint
    ignora `idCentral` → hay que paginar el SEN completo, y la API se estrangula a ~10 s/página bajo
    carga sostenida (121 págs = 1.252 s ≈ 21 min/día). `MAX_DIAS=2` acota la corrida al timeout de 60.
  · **Fetch validado contra la API real** antes de commitear: 576 filas para el 31/07 = 4 unidades ×
    6 servicios × 24 horas exactas, 0 duplicados de PK, horas 1-24, 47 con provisión > 0 (el resto
    ceros legítimos). El dedup redujo las 4.012 filas crudas a las 576 correctas.
  · **Desplegado y verificado en producción la misma sesión.** `migracion_sscc_programado.py` vía
    `migracion.yml`: **success en 23m40s**, tabla creada y 576 filas del 01/08 (4 unidades × 6
    servicios × 24 h, 0 duplicados de PK, 43 con provisión > 0, 488,2 MW-h; reparto ANG2 206,3 ·
    CCR1 134,5 · ANG1 80,0 · CCR2 67,4). Ojo: la migración cuenta desde HOY hacia atrás, así que
    con 1 día carga hoy, no ayer (el cron sí toma ayer).
    · Se descubrió al mirar `migracion.yml` que su timeout es de **30 min** y cada día cuesta ~21
      → el default de 3 días del script se habría pasado; corregido a `MAX_DIAS=1` con aviso.
    · Primer render del panel salió VACÍO pese a haber datos: era `st.cache_data` sirviendo el
      resultado vacío cacheado de antes de la migración (el panel se abrió mientras corría).
      Se resolvió con «↻ Actualizar datos». Ver regla 37.
  · **Pulido del panel con datos reales (commit aparte):** el KPI «Servicio dominante» se truncaba
    (`CSF (-) · 266 M…`) → la magnitud bajó a la línea de detalle; `delta_color="off"` en los dos
    KPIs cuyo texto secundario es una proporción y no una variación (Streamlit los pintaba con
    flecha verde de mejora); y el gráfico diario pasó a eje x categórico con `bargap` porque con un
    solo día el eje temporal estiraba la barra a todo el ancho. Ver reglas 38 y 39.

- **2026-08-01 (3ª sesión) — Rediseño de la suite ML + hallazgo del sesgo de ceros en el CMG:**
  · **Punto de partida:** el usuario pidió portar el «pronóstico recursivo de 12h» de Pulsar y
    reemplazar Anomalías y Regímenes por algo con aporte real. Al comparar contra
    `Metodologia_ML_Pulsar.pdf` resultó que el recursivo YA estaba implementado (y a 24h): lo que
    faltaba de Pulsar era la banda CALIBRADA (su análisis 02), el benchmark contra el Coordinador
    (04) y la anomalía EXPLICADA (03). Se descartó el optimizador de encendido/apagado porque esa
    decisión es exclusiva del CEN y la empresa siempre quiere las unidades en servicio.
  · **«Pronóstico CMG» reforzado:** 3 XGBoost cuantílicos (`reg:quantileerror`) + conformal (CQR)
    sobre partición cronológica 60/20/20 → cobertura de 21% (cruda) a 80% (calibrada); exógenas
    nuevas (CMG programado PCP de la propia hora + peso ERV del mix diario); PID y PCP dibujados
    sobre todo el rango; benchmark day-ahead contra PCP/PID reentrenado por ventana.
  · **«Desviación explicada»** (reemplaza Anomalías): 2 detectores (percentil + IsolationForest) y
    cascada de atribución contra `instrucciones_cmg` → `limitaciones_transmision` →
    `sscc_instrucciones` → `mantenimiento_mayor`; la salida es la lista de horas SIN explicar.
  · **«Riesgo de desacople»** (reemplaza Regímenes): clasificador day-ahead con dataset propio
    anclado al CMG liquidado. AUC 0,63–0,73 sobre base 20–24%, + ingreso en riesgo en USD.
  · **Hallazgo mayor (regla 40):** el feed S3 no emitía fila cuando el CMG era 0 → esas horas
    están AUSENTES, no en cero. `_dataset` las rellenaba con `ffill` (precio alto inventado justo
    en las horas de desacople) → el modelo sobreestimaba el 92% de las horas de prueba, sesgo
    +24,6 USD/MWh, R² −1,23. Lo detectó el USUARIO mirando el gráfico de validación, no las
    métricas. Corregido con parche desde el liquidado + peso por recencia + debias en calibración:
    Crucero MAE 25,7→17,4 y sesgo +24,6→+3,4; Tarapacá 24,4→16,9 y +23,3→−2,9 (R² +0,20).
  · **Auditoría de Costos y Estadísticas:** el mismo defecto los afecta (+10,7% en el CMG medio a
    30 días). Se escribió `migracion_cmg_ceros.py` (272 filas, todas con liquidado 0,00 exacto;
    modo simulación por defecto, detecta el tipo de `fecha_hora` en runtime). **No ejecutada** —
    escribe en producción y quedó como decisión del usuario.
  · **Fixes menores:** la línea «ahora» del gráfico marcaba el último dato con
    `add_vline(x=...timestamp()*1000)` en vez de usar el helper compartido `add_linea_ahora`
    (regla 45); el CMG programado PID existía en la DB y alimentaba el modelo pero no se dibujaba.
  · **Método:** todo verificado contra la DB real con `streamlit.testing.v1.AppTest` headless
    (regla 46) — 4 barras × 3 secciones × 4 unidades sin excepciones — y el entrenamiento quedó
    cacheado por (nodo, última hora): 9,2 s → 0,2 s en reruns.

- **2026-08-02 (4ª sesión) — Eventos unificados, vista «Operación» y KPIs sin truncado:**
  · **Punto de partida (reporte del usuario):** «hay limitaciones con status pendiente que en
    realidad ya se cerraron»; pedía relacionar trips/derrateos con esas novedades para que
    figuren como alarma en la serie, distinguir mantenimiento mayor / outage como evento
    latente, arreglar el truncado de las cards, y repensar el nombre y el contenido de
    «Restricciones».
  · **Hallazgo (regla 47):** el CEN nunca cierra el registro. Medido en la DB real: 21
    limitaciones en el período, **0 realmente vigentes** y 16 en «pendiente» con retorno
    estimado ya pasado; `fecha_efectiva_retorno` NULL en todas. Nace `utils/eventos.py` con la
    ventana como única fuente de vigencia y cuatro estados (activa / vencida = cerrada de facto /
    cerrada / futura). Lo consumen el panel de Limitaciones, la bitácora automática, la serie de
    la unidad, el Panorama y el informe ejecutivo.
  · **Serie de la unidad (`gen_unidad.py`):** las ventanas de evento se pintan como franjas
    translúcidas con leyenda propia; los bloques de detención (< 5 MW) se agrupan con `_bloques`
    y se atribuyen con `explicar_horas` → el banner dice «detenida 03-08 04:00 → 12:00 (9 h) —
    Limitación N.xxxx» o **«sin causa registrada»** (rojo solo en ese caso; ámbar cuando todo
    tiene causa). Banner nuevo de **eventos latentes** con cuenta regresiva a los programas
    futuros del PMPM. Checkbox «Eventos de la unidad» en Series visibles.
  · **Ajuste posterior del usuario (mismo día, commit `10cf943`): la franja es SOLO de la
    máquina.** La primera versión incluía el corredor de evacuación y el resultado fue una banda
    teal permanente sobre casi todo el gráfico (los trabajos en S/E O'Higgins y Laberinto duran
    semanas) más un banner de latentes lleno de subestaciones. Ahora `render_gen_unidad` pasa
    `incluir_corredor=False`: quedan solo limitaciones de la unidad y mantenimiento mayor /
    outage de la propia térmica. Verificado con datos reales: las 4 unidades pasan a tener solo
    eventos de tipo `limitacion` y 0 latentes. Ver regla 48.
  · **Vista «Restricciones» → «Operación» + sub «Panorama»** (`components/operacion.py`): estado
    actual por unidad con evento vigente y próximo, timeline unificado de las 4 unidades,
    energía no generada por evento (Σ programa − real dentro de la ventana, valorizada al CMG
    horario) y cobertura documental del desvío en tres categorías.
  · **Sobre-atribución detectada y corregida en la misma sesión (regla 48):** el primer Panorama
    reportó 82.074 MWh / US$ 2,4 M de energía no generada — era el mantenimiento del corredor,
    que cubre todo el período y las 4 unidades. Se excluyó el corredor de la atribución y del
    impacto (queda como contexto gris), y se dedujeron los conteos de eventos duplicados por
    unidad (12 → 3).
  · **KPI cards sin truncado (regla 49):** `render_kpi_grid` + `fmt_usd` en `_common.py`, CSS
    anti-elipsis en `config.py` y flecha del delta oculta en las grillas. Costos pasó de 7 cards
    en una fila a 4+3. Verificado con Playwright midiendo `scrollWidth > clientWidth` en las 12
    cards: ninguna recortada.
  · **Informe ejecutivo:** `_datos_reporte` ahora pasa `limitaciones_vigentes(...)`, así que el
    PDF/PPT informa lo que afectó el período en vez del conteo de pendientes fantasma; la
    columna «Pendientes» de la tabla de eventos pasó a «Vigentes». PDF y PPT regenerados OK.
  · **Decisión del usuario:** NO se crea registro manual de outages — el mantenimiento mayor de
    Angamos de octubre aparecerá cuando el CEN lo publique en el PMPM; el mapeo texto→unidad ya
    está listo para tomarlo sin cambios de código.
  · **Método:** `AppTest` headless contra la DB real, 14 combinaciones vista × subsección ×
    unidad sin excepciones, + Playwright sobre la app local para el DOM y las capturas.

*Actualizado 2026-08-02 (4ª sesión). Proyecto CTM Mejillones (4 térmicas ANG/CCR).*
*Stack: Streamlit + supabase-py/psycopg2 + GitHub Actions + API CEN (SIP/OPS) + CMG S3 + scikit-learn/xgboost.*
