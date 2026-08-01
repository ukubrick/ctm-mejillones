"""
utils/eventos.py — Modelo unificado de EVENTOS que afectan a las unidades CTM.

Nace de un problema real de datos: el CEN **no cierra** los registros de
`limitaciones_transmision`. `status` se queda en «pendiente» para siempre y
`fecha_efectiva_retorno` viene casi siempre NULL, así que contar los
«pendientes» sobreestima groseramente lo que está vigente (verificado
2026-08-01: limitaciones de febrero seguían «pendientes» con retorno estimado
en febrero). La señal honesta es la VENTANA, no el status:

    ventana = [fecha_perturbacion, fin]
    fin = fecha_efectiva_retorno          (cierre real, si existe)
        | fecha_retorno_estimada          (compromiso declarado al CEN)
        | fecha_perturbacion + 7 días     (sin ninguna referencia)
    y siempre topeada a fecha_perturbacion + 30 días (regla 41: una causa que
    abarca meses no explica nada; hay registros abiertos hasta el 31/12).

Estados resultantes:
  · «activa»  — la ventana contiene el instante de referencia.
  · «vencida» — status pendiente pero la ventana ya pasó → cerrada de facto,
                el CEN simplemente no emitió el cierre.
  · «cerrada» — tiene cierre real o status finalizado/anulado.
  · «futura»  — la ventana empieza después de la referencia (evento latente).

Sobre esa base se construye un evento genérico (limitación, mantenimiento
mayor, compromiso SSCC) con la misma forma, para poder pintarlos todos en la
serie de tiempo de la unidad y cruzarlos contra los desvíos reales.
"""
import pandas as pd

from config import ID_UNIDAD_LABEL, UNIDADES
from utils.plotly_theme import TZ_CHILE

# Ventana asumida cuando el registro no declara ningún retorno.
VENTANA_DEFECTO_DIAS = 7
# Tope duro de una ventana de atribución (regla 41).
MAX_VENTANA_DIAS = 30

# Tipos de evento y su presentación (color de línea, relleno translúcido).
TIPO_EVENTO = {
    "limitacion":   ("Limitación",       "#DC2626", "rgba(220,38,38,0.10)"),
    "mantenimiento": ("Mantenimiento",   "#7C3AED", "rgba(124,77,224,0.10)"),
    "corredor":     ("Corredor",         "#0E7E93", "rgba(14,126,147,0.08)"),
    "sscc":         ("SSCC",             "#D97706", "rgba(217,119,6,0.10)"),
}

# Instalaciones del corredor de evacuación: no intervienen las unidades, pero
# restringen su salida al sistema → aplican a las 4.
CLAVES_CORREDOR = ("O'HIGGINS", "O´HIGGINS", "OHIGGINS", "MEJILLONES",
                   "LABERINTO", "KAPATUR", "CRUCERO", "CHACAYA")


def _ahora():
    return pd.Timestamp.now(tz=TZ_CHILE).tz_localize(None)


def _ts(v):
    """Timestamp naive o NaT. Tolera los formatos mixtos del CEN."""
    t = pd.to_datetime(v, errors="coerce")
    if pd.isna(t):
        return pd.NaT
    if getattr(t, "tzinfo", None) is not None:
        t = t.tz_localize(None)
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Limitaciones
# ─────────────────────────────────────────────────────────────────────────────
def ventana_limitacion(row):
    """(inicio, fin, origen_fin) de una limitación.

    origen_fin ∈ {'efectivo', 'estimado', 'supuesto', 'tope'} — se muestra en la
    UI para que quede explícito de dónde sale el cierre.
    """
    ini = _ts(row.get("fecha_perturbacion"))
    if pd.isna(ini):
        return pd.NaT, pd.NaT, "sin_inicio"

    ef = _ts(row.get("fecha_efectiva_retorno"))
    if pd.notna(ef):
        fin, origen = ef, "efectivo"
    else:
        est = _ts(row.get("fecha_retorno_estimada"))
        if pd.notna(est) and est >= ini:
            fin, origen = est, "estimado"
        else:
            fin, origen = ini + pd.Timedelta(days=VENTANA_DEFECTO_DIAS), "supuesto"

    tope = ini + pd.Timedelta(days=MAX_VENTANA_DIAS)
    if fin > tope:
        fin, origen = tope, "tope"
    return ini, fin, origen


def estado_limitacion(row, ref=None):
    """'activa' | 'vencida' | 'cerrada' | 'futura' para el instante `ref`."""
    ref = _ts(ref) if ref is not None else _ahora()
    status = str(row.get("status", "")).strip().lower()
    ini, fin, origen = ventana_limitacion(row)
    if pd.isna(ini):
        return "cerrada"
    if status in ("finalizado", "anulado") or origen == "efectivo":
        return "cerrada"
    if ini > ref:
        return "futura"
    return "activa" if fin >= ref else "vencida"


def preparar_limitaciones(df, ref=None, s=None, e=None):
    """Añade `_ini`, `_fin`, `_origen_fin`, `_estado` y `_unidad` al DataFrame.

    `ref` es el instante contra el que se juzga la vigencia. Por defecto «ahora»;
    si se pasa el fin del período (`e`) el juicio es «vigente al cierre del
    período analizado», que es lo que corresponde en un reporte histórico.
    """
    if df is None or df.empty:
        return df
    d = df.copy()
    if ref is None and e is not None:
        # Fin del día `e` — un reporte de un período pasado no debe declarar
        # activo algo que hoy sigue abierto pero entonces no lo estaba.
        ref = _ts(e) + pd.Timedelta(hours=23, minutes=59)
    ref = _ts(ref) if ref is not None else _ahora()

    v = d.apply(ventana_limitacion, axis=1, result_type="expand")
    d["_ini"], d["_fin"], d["_origen_fin"] = v[0], v[1], v[2]
    d["_estado"] = d.apply(lambda r: estado_limitacion(r, ref), axis=1)
    d["_unidad"] = d["id_unidad"].apply(
        lambda x: ID_UNIDAD_LABEL.get(int(float(x)), "") if pd.notna(x) else "")
    return d


def limitaciones_vigentes(df, ref=None, s=None, e=None):
    """Solo las limitaciones realmente activas (no las «pendientes» de papel).

    Si se entrega el período [s, e], «activa» significa que la ventana de la
    limitación SE SOLAPA con el período, no que esté abierta hoy.
    """
    d = preparar_limitaciones(df, ref=ref, s=s, e=e)
    if d is None or d.empty:
        return d
    if s is not None and e is not None:
        sd, ed = _ts(s), _ts(e) + pd.Timedelta(days=1)
        solapa = (d["_ini"] < ed) & (d["_fin"] >= sd)
        return d[solapa & d["_estado"].isin(["activa", "vencida", "cerrada"])
                 & (d["_fin"] >= sd)]
    return d[d["_estado"] == "activa"]


# ─────────────────────────────────────────────────────────────────────────────
# Mantenimiento mayor → unidades
# ─────────────────────────────────────────────────────────────────────────────
def unidades_mantenimiento(row):
    """Unidades afectadas por un programa del PMPM y si es intervención directa.

    Devuelve (lista_unidades, tipo) con tipo ∈ {'mantenimiento', 'corredor'}.
    La tabla del CEN no trae `id_unidad` → el mapeo es por texto (regla 26).
    """
    txt = " ".join(str(row.get(c) or "") for c in
                   ("nombre_instalacion", "nombre_sub_instalacion",
                    "elemento_instalacion", "descripcion_trabajo")).upper()

    def _con_numero(prefijos, unidades):
        """Detecta 'U1'/'UNIDAD 1'/'ANGAMOS 1' para acotar a una unidad."""
        if not any(p in txt for p in prefijos):
            return []
        marcas_1 = ("U1", "U 1", "UNIDAD 1", "N°1", "N 1", "Nº1")
        marcas_2 = ("U2", "U 2", "UNIDAD 2", "N°2", "N 2", "Nº2")
        hit = []
        if any(m in txt for m in marcas_1):
            hit.append(unidades[0])
        if any(m in txt for m in marcas_2):
            hit.append(unidades[1])
        return hit or list(unidades)

    directas = _con_numero(("ANGAMOS",), ("ANG1", "ANG2"))
    directas += _con_numero(("COCHRANE",), ("CCR1", "CCR2"))
    if directas:
        return directas, "mantenimiento"
    if any(k in txt for k in CLAVES_CORREDOR):
        return list(UNIDADES), "corredor"
    return [], "corredor"


# ─────────────────────────────────────────────────────────────────────────────
# Evento unificado
# ─────────────────────────────────────────────────────────────────────────────
def _evento(tipo, unidad, ini, fin, titulo, detalle="", mw=None, ref=None,
            fuente="", ident=""):
    ref = ref if ref is not None else _ahora()
    if pd.isna(ini):
        return None
    if pd.isna(fin):
        fin = ini + pd.Timedelta(days=VENTANA_DEFECTO_DIAS)
    if ini > ref:
        estado = "futura"
    elif fin >= ref:
        estado = "activa"
    else:
        estado = "cerrada"
    return {"tipo": tipo, "unidad": unidad, "ini": ini, "fin": fin,
            "titulo": titulo, "detalle": detalle, "mw": mw, "estado": estado,
            "fuente": fuente, "id": ident,
            "dias": max((fin - ini).total_seconds() / 86400, 0)}


def eventos_unidad(unidad, df_lim=None, df_mant=None, df_sscc=None, ref=None,
                   incluir_corredor=True):
    """DataFrame de eventos que afectan a `unidad`, de todas las fuentes.

    Columnas: tipo · unidad · ini · fin · titulo · detalle · mw · estado ·
    fuente · id · dias. `estado` ∈ activa / futura / cerrada.
    """
    ref = _ts(ref) if ref is not None else _ahora()
    out = []

    if df_lim is not None and not df_lim.empty:
        d = df_lim if "_estado" in df_lim.columns else preparar_limitaciones(df_lim, ref=ref)
        for _, r in d.iterrows():
            if r.get("_unidad") not in ("", unidad):
                continue
            corr = r.get("correlativo")
            corr_txt = f"N.{int(float(corr))}" if pd.notna(corr) else "s/n"
            pot = r.get("potencia")
            mw = float(pot) if pd.notna(pot) and float(pot) > 0 else None
            det = str(r.get("observacion") or "").strip()[:180]
            if r.get("_origen_fin") in ("estimado", "supuesto", "tope"):
                det = (det + " · " if det else "") + {
                    "estimado": "cierre = retorno estimado (el CEN no emitió cierre real)",
                    "supuesto": f"sin retorno declarado → ventana de {VENTANA_DEFECTO_DIAS} días",
                    "tope": f"registro abierto → ventana topeada a {MAX_VENTANA_DIAS} días",
                }[r["_origen_fin"]]
            ev = _evento("limitacion", unidad, r["_ini"], r["_fin"],
                         f"Limitación {corr_txt}", det, mw, ref,
                         fuente=str(r.get("instalacion_nombre") or ""), ident=corr_txt)
            if ev:
                # El estado ya lo decidió `estado_limitacion` (distingue vencida).
                ev["estado"] = {"vencida": "cerrada"}.get(r["_estado"], r["_estado"])
                out.append(ev)

    if df_mant is not None and not df_mant.empty:
        for _, r in df_mant.iterrows():
            unis, tipo = unidades_mantenimiento(r)
            if unidad not in unis:
                continue
            if tipo == "corredor" and not incluir_corredor:
                continue
            ini = _ts(r.get("fecha_inicio_real") or r.get("fecha_inicio_programa"))
            fin = _ts(r.get("fecha_termino_real") or r.get("fecha_fin_programa"))
            nombre = str(r.get("nombre_instalacion") or "")[:44]
            titulo = ("Mantenimiento mayor" if tipo == "mantenimiento"
                      else "Mant. corredor de evacuación")
            estado_cen = str(r.get("estado") or "").strip()
            det = f"{nombre} · {str(r.get('descripcion_trabajo') or '')[:140]}"
            ev = _evento(tipo, unidad, ini, fin, titulo, det, None, ref,
                         fuente=nombre, ident=str(r.get("correlativo") or ""))
            if ev:
                ev["detalle"] = det
                ev["estado_cen"] = estado_cen
                out.append(ev)

    if df_sscc is not None and not df_sscc.empty and "unidad" in df_sscc.columns:
        d = df_sscc[df_sscc["unidad"] == unidad]
        for _, r in d.iterrows():
            ini = _ts(r.get("inicio_periodo") or r.get("fecha"))
            fin = _ts(r.get("fin_periodo")) if r.get("fin_periodo") else pd.NaT
            if pd.isna(fin) and pd.notna(ini):
                fin = ini + pd.Timedelta(hours=1)
            ev = _evento("sscc", unidad, ini, fin,
                         str(r.get("instruccion_sscc") or "SSCC"), "", None, ref,
                         fuente="SSCC instruido")
            if ev:
                out.append(ev)

    if not out:
        return pd.DataFrame(columns=["tipo", "unidad", "ini", "fin", "titulo",
                                     "detalle", "mw", "estado", "fuente", "id", "dias"])
    df = pd.DataFrame(out).sort_values("ini", ascending=False).reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Cruce evento ↔ desvío real
# ─────────────────────────────────────────────────────────────────────────────
def explicar_horas(horas, df_ev, tipos=("limitacion", "mantenimiento")):
    # Por defecto NO se atribuye al corredor de evacuación: una intervención en
    # la S/E O'Higgins dura semanas y cubre a las 4 unidades, así que explicaría
    # casi cualquier desvío sin haberlo causado (regla 41). Es contexto —se
    # dibuja en la serie— pero no cuenta como causa salvo que se pida explícito.
    """Para cada instante de `horas`, el evento que lo cubre (o None).

    Devuelve una Serie de strings alineada al índice de `horas` con el título del
    evento explicativo, o "" si ninguna ventana registrada lo cubre.
    """
    horas = pd.Series(pd.to_datetime(horas)).reset_index(drop=True)
    res = pd.Series([""] * len(horas), index=horas.index)
    if df_ev is None or df_ev.empty:
        return res
    d = df_ev[df_ev["tipo"].isin(tipos)]
    for _, ev in d.iterrows():
        cubre = (horas >= ev["ini"]) & (horas <= ev["fin"]) & (res == "")
        res[cubre] = ev["titulo"]
    return res


def eventos_latentes(df_ev, dias=180):
    """Eventos futuros dentro de `dias` — outages/mantenimientos ya publicados."""
    if df_ev is None or df_ev.empty:
        return df_ev
    lim = _ahora() + pd.Timedelta(days=dias)
    d = df_ev[(df_ev["estado"] == "futura") & (df_ev["ini"] <= lim)]
    return d.sort_values("ini")


def dias_hasta(ts):
    """Días enteros desde ahora hasta `ts` (negativo si ya pasó)."""
    t = _ts(ts)
    if pd.isna(t):
        return None
    return int((t - _ahora()).total_seconds() // 86400)
