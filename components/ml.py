"""
components/ml.py — Análisis predictivo (Machine Learning) del CTM · rediseño 2026-08.

Tres modelos, cada uno respondiendo una pregunta accionable:

  · «Pronóstico CMG» — ¿cuánto valdrá la energía?
    Forecast recursivo 24h con banda P10–P90 de regresión cuantílica (XGBoost
    `reg:quantileerror`) CALIBRADA por conformal (CQR): la banda deja de ser un
    ensanchamiento ciego ~√h y pasa a estar condicionada a la hora y al estado del
    sistema, con cobertura verificada sobre un set que el modelo nunca vio.
    Exógenas nuevas: CMG programado PCP de la propia hora (el prior del
    Coordinador, disponible día-antes en todo el horizonte) y peso ERV del SEN.
    Y el número que importa: BENCHMARK contra el PCP y el PID del Coordinador
    en ventanas de 78h / 7d / 30d, con un modelo day-ahead reentrenado solo con
    datos previos a cada ventana (mismo tablero de juego que el CEN).

  · «Desviación explicada» — ¿qué hay que ir a revisar?
    Dos detectores en paralelo (umbral operacional + Isolation Forest) marcan las
    horas donde el real se apartó del programa; cada una se CRUZA en cascada con
    las fuentes que el dashboard ya adquiere (instrucción CEN → limitación de
    transmisión → SSCC instruido → mantenimiento mayor). Lo que no cruza con nada
    queda como «sin explicar — posible falla»: esa lista es el entregable.

  · «Riesgo de desacople» — ¿cuándo se cae el ingreso?
    Clasificador day-ahead de CMG ≈ 0 en la barra. Un modelo de MAE aplana los
    ceros; este los modela como el evento que son. Salida: probabilidad hora a
    hora para las próximas 24h e INGRESO EN RIESGO (probabilidad × despacho
    programado × precio previsto).

Se renderiza como sub-sección de «Análisis» (no fija page_config) y también desde
pages/ml_analysis.py. Paleta corporativa AES; sin ejes duales (regla 22).
"""
from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (COLORES, LABELS, AES_AZUL, AES_AMBAR, AES_CYAN, AES_VERDE,
                    AES_VIOLETA, AES_ROJO, NOMBRES_NODO, BG_TRANSP, C_GRID)
from utils.db import fetch, rest_enabled
from utils.plotly_theme import hex_to_rgba
from utils.data import (load_instrucciones_cmg, load_limitaciones, load_sscc,
                        load_mantenimiento_mayor)

INK       = "#1A1F36"
INK_AXIS  = "#94A3B8"

# Regla 23: potencia real < 5 MW = unidad detenida, no 0 exacto.
UMBRAL_TRIP = 5.0
# Mapeo de las limitaciones de transmisión (regla: id_unidad 1965-1968).
ID_UNIDAD_LIM = {1965: "ANG1", 1966: "ANG2", 1967: "CCR1", 1968: "CCR2"}
# Tope de duración de una ventana de atribución. Una causa que abarca meses
# "explica" todos los desvíos del período y vuelve inútil la cascada.
VENTANA_MAX_DIAS = 30
# Causas que solo pueden explicar un desvío A LA BAJA: una limitación o un
# mantenimiento reducen la salida, nunca justifican generar de más.
CAUSAS_SOLO_BAJA = {"Limitación transmisión", "Mantenimiento mayor", "SSCC instruido"}

# Colores de la cascada de atribución (orden = prioridad).
COLOR_CAUSA = {
    "Instrucción CEN":      AES_AZUL,
    "Limitación transmisión": AES_CYAN,
    "SSCC instruido":       AES_VERDE,
    "Mantenimiento mayor":  AES_AMBAR,
    "Sin explicar":         AES_ROJO,
}


# ══════════════════════════════════════════════════════════════════════════════
# Loaders
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def _load_cmg():
    """CMG online horario en las 4 barras (Crucero/Tarapacá + Angamos/Cochrane).

    Ojo (regla 28): un CMG de 0 es un DATO — es exactamente el evento que modela
    la sección de desacople. Nunca filtrarlo."""
    barras = tuple(NOMBRES_NODO.keys())
    df = fetch(
        "costo_marginal", "fecha_hora,barra_transf,cmg_usd_mwh", order="fecha_hora",
        sql="SELECT fecha_hora, barra_transf, cmg_usd_mwh FROM costo_marginal "
            "WHERE barra_transf IN %s ORDER BY fecha_hora",
        params=(barras,),
    )
    if not df.empty:
        df = df[df["barra_transf"].isin(list(NOMBRES_NODO.keys()))]
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors="coerce")
        df = df.dropna(subset=["fecha_hora"]).sort_values("fecha_hora")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def _load_dem_neta():
    """Demanda neta horaria del SEN (tabla demanda_neta, integrada 2026-07-08).
    Es el driver físico del CMG → feature del forecast. Silencioso si no existe."""
    try:
        df = fetch(
            "demanda_neta", "fecha_hora,demanda_neta_mwh", order="fecha_hora",
            sql="SELECT fecha_hora, demanda_neta_mwh FROM demanda_neta ORDER BY fecha_hora",
        )
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors="coerce")
        df = df.dropna(subset=["fecha_hora", "demanda_neta_mwh"]).sort_values("fecha_hora")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def _load_cmg_prog_ml(barra):
    """CMG programado (PCP y PID) de una barra, como dos series por fecha_hora.

    El PCP es el prior del Coordinador publicado el DÍA ANTES → está disponible en
    todo el horizonte de forecast, a diferencia de cualquier rezago del propio CMG.
    Es, de lejos, la exógena más informativa que tiene el proyecto."""
    try:
        df = fetch(
            "costo_marginal_programado", "fecha_hora,cmg_usd_mwh,fuente",
            eq={"barra": barra}, order="fecha_hora",
            sql="SELECT fecha_hora, cmg_usd_mwh, fuente FROM costo_marginal_programado "
                "WHERE barra = %s ORDER BY fecha_hora",
            params=(barra,),
        )
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors="coerce")
        df["cmg_usd_mwh"] = pd.to_numeric(df["cmg_usd_mwh"], errors="coerce")
        df = df.dropna(subset=["fecha_hora", "cmg_usd_mwh"])
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def _load_cmg_real_ml(barra):
    """CMG REAL liquidado de una barra — el target del clasificador de desacople.

    Por qué no se usa el CMG online: hasta el 2026-07-27 esa serie venía del feed
    S3, que DESCARTABA los registros en 0 (regla 27). O sea, en el histórico online
    los desacoples anteriores a esa fecha sencillamente no existen, y entrenar
    sobre él daría un modelo que nunca vio el evento que debe predecir. El CMG real
    liquidado nunca filtró ceros: es el único histórico honesto del evento, a costa
    de un rezago de ~10 días (irrelevante para ENTRENAR)."""
    try:
        df = fetch(
            "costo_marginal_real", "fecha_hora,cmg_usd_mwh",
            eq={"barra_transf": barra}, order="fecha_hora",
            sql="SELECT fecha_hora, cmg_usd_mwh FROM costo_marginal_real "
                "WHERE barra_transf = %s ORDER BY fecha_hora",
            params=(barra,),
        )
    except Exception:
        return pd.Series(dtype=float)
    if df.empty:
        return pd.Series(dtype=float)
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors="coerce")
    df["cmg_usd_mwh"] = pd.to_numeric(df["cmg_usd_mwh"], errors="coerce")
    df = df.dropna(subset=["fecha_hora", "cmg_usd_mwh"])
    s = df.set_index("fecha_hora")["cmg_usd_mwh"]
    return s[~s.index.duplicated(keep="last")]


@st.cache_data(ttl=3600, show_spinner=False)
def _load_erv_share():
    """Peso de la generación ERV (solar + eólica) en el mix diario del SEN.

    Es el driver #1 del desacople: cuando la inyección renovable del norte supera
    lo que la transmisión puede evacuar, el CMG de la zona se va a cero."""
    try:
        df = fetch(
            "mix_generacion_diaria", "fecha,tecnologia,energia_mwh", order="fecha",
            sql="SELECT fecha, tecnologia, energia_mwh FROM mix_generacion_diaria "
                "ORDER BY fecha",
        )
    except Exception:
        return pd.Series(dtype=float)
    if df.empty:
        return pd.Series(dtype=float)
    df["energia_mwh"] = pd.to_numeric(df["energia_mwh"], errors="coerce").fillna(0.0)
    tec = df["tecnologia"].astype(str).str.lower()
    es_erv = tec.str.contains("solar|fotovolt|eólic|eolic|viento", regex=True, na=False)
    tot = df.groupby("fecha")["energia_mwh"].sum()
    erv = df[es_erv].groupby("fecha")["energia_mwh"].sum().reindex(tot.index).fillna(0.0)
    share = (erv / tot.replace(0, np.nan)).dropna()
    share.index = pd.to_datetime(share.index, errors="coerce").date
    return share


@st.cache_data(ttl=3600, show_spinner=False)
def _load_gen():
    df_real = fetch("generacion_real", "unidad,fecha_hora,gen_real_mw,potencia_maxima",
        order="fecha_hora",
        sql="SELECT unidad, fecha_hora, gen_real_mw, potencia_maxima FROM generacion_real ORDER BY fecha_hora")
    df_prog = fetch("generacion_programada", "unidad,fecha_hora,gen_programada_mw,fuente",
        sql="SELECT DISTINCT ON (unidad, fecha_hora) unidad, fecha_hora, gen_programada_mw, fuente "
            "FROM generacion_programada "
            "ORDER BY unidad, fecha_hora, CASE fuente WHEN 'CEN_PCP' THEN 0 ELSE 1 END")
    if not df_prog.empty and rest_enabled():
        df_prog["_pri"] = (df_prog["fuente"] != "CEN_PCP").astype(int)
        df_prog = (df_prog.sort_values(["unidad", "fecha_hora", "_pri"])
                   .drop_duplicates(["unidad", "fecha_hora"], keep="first").drop(columns="_pri"))
    if not df_real.empty:
        df_real["fecha_hora"] = pd.to_datetime(df_real["fecha_hora"])
    if not df_prog.empty:
        df_prog["fecha_hora"] = pd.to_datetime(df_prog["fecha_hora"])
        df_prog = df_prog.drop(columns=[c for c in ["fuente"] if c in df_prog.columns])
    return df_real, df_prog


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════
def _add_time(df):
    df = df.copy()
    df["hora"] = df["fecha_hora"].dt.hour
    df["dia_semana"] = df["fecha_hora"].dt.dayofweek
    df["mes"] = df["fecha_hora"].dt.month
    df["hora_sin"] = np.sin(2 * np.pi * df["hora"] / 24)
    df["hora_cos"] = np.cos(2 * np.pi * df["hora"] / 24)
    return df


def _kpi(col, val, lbl, color=AES_AZUL):
    col.markdown(
        f'<div style="background:#fff;border-radius:12px;padding:16px 20px;'
        f'border-top:3px solid {color};box-shadow:0 2px 10px rgba(0,0,0,0.06)">'
        f'<div style="font-size:1.5rem;font-weight:800;color:{INK}">{val}</div>'
        f'<div style="font-size:0.74rem;color:#6B7280;margin-top:2px">{lbl}</div></div>',
        unsafe_allow_html=True)


def _base_layout(fig, titulo, y_title=None, height=380, **kw):
    fig.update_layout(
        template="plotly_white", plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
        title=dict(text=titulo, font=dict(size=13, color=INK), x=0),
        height=height, margin=dict(l=10, r=12, t=55, b=10),
        font=dict(family="Inter, sans-serif"),
        yaxis=dict(title=y_title, gridcolor=C_GRID, tickfont=dict(color=INK_AXIS, size=10),
                   title_font=dict(color=INK_AXIS, size=10)),
        xaxis=dict(showgrid=False, tickfont=dict(color=INK_AXIS, size=10)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)),
        **kw)
    return fig


def _show(fig):
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _pinball(y, q, alpha):
    """Pérdida pinball: asimétrica, es la función objetivo de la regresión cuantílica.
    Para el P90 quedarse corto cuesta 9× más que pasarse."""
    d = np.asarray(y) - np.asarray(q)
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))


# ══════════════════════════════════════════════════════════════════════════════
# Dataset compartido: CMG del nodo + calendario + exógenas
# ══════════════════════════════════════════════════════════════════════════════
LAGS_CORTOS = [1, 2, 3, 6, 12]
LAGS_LARGOS = [24, 48, 72]
F_TIEMPO = ["hora_sin", "hora_cos", "dia_semana", "mes"]


def _dataset(nodo):
    """Construye la matriz de features del nodo y devuelve (df, feats_rec, feats_da, mapas).

    · feats_rec — todo, incluidos los rezagos cortos. Sirve al forecast RECURSIVO:
      para t+1 el lag_1h es el último dato real; de ahí en adelante se realimenta
      con la propia predicción.
    · feats_da  — solo información de ≥24 h antes + exógenas publicadas el día
      anterior. Es el conjunto «day-ahead»: el mismo tablero de juego que tiene el
      PCP del Coordinador, y por eso es el que se usa para el benchmark y para el
      clasificador de desacople. Sin esta distinción, comparar contra el PCP con
      un modelo que conoce el precio de hace una hora sería hacer trampa.
    """
    df_raw = _load_cmg()
    d = df_raw[df_raw["barra_transf"] == nodo]
    if d.empty:
        return None, None, None, None
    d = d.set_index("fecha_hora").sort_index()[["cmg_usd_mwh"]]
    idx = pd.date_range(d.index.min(), d.index.max(), freq="h")
    df = (d.reindex(idx).ffill(limit=3).dropna().reset_index()
          .rename(columns={"index": "fecha_hora"}))
    df = _add_time(df)

    for l in LAGS_CORTOS + LAGS_LARGOS:
        df[f"lag_{l}h"] = df["cmg_usd_mwh"].shift(l)
    df["ma_6h"] = df["cmg_usd_mwh"].shift(1).rolling(6).mean()
    df["ma_24h"] = df["cmg_usd_mwh"].shift(1).rolling(24).mean()
    # Volatilidad reciente: alimenta la banda cuantílica con el "cuán agitado
    # viene el sistema", que es lo que un √h ciego no puede saber.
    df["std_24h"] = df["cmg_usd_mwh"].shift(1).rolling(24).std()
    df["ma_24h_lag24"] = df["cmg_usd_mwh"].shift(24).rolling(24).mean()

    mapas = {}
    exo_rec, exo_da = [], []

    # Demanda neta con rezago 24h — disponible en todo el horizonte.
    dem = _load_dem_neta()
    if not dem.empty:
        dmap = dem.set_index("fecha_hora")["demanda_neta_mwh"]
        df["dem_lag_24h"] = (df["fecha_hora"] - timedelta(hours=24)).map(dmap)
        if df["dem_lag_24h"].notna().mean() >= 0.3:
            exo_rec.append("dem_lag_24h"); exo_da.append("dem_lag_24h")
            mapas["dem"] = dmap

    # CMG programado del Coordinador para la PROPIA hora (PCP día-antes, PID intra-día).
    prog = _load_cmg_prog_ml(nodo)
    if not prog.empty:
        for f, col in (("CEN_PCP", "cmg_pcp"), ("CEN_PID", "cmg_pid")):
            s = prog[prog["fuente"] == f].set_index("fecha_hora")["cmg_usd_mwh"]
            s = s[~s.index.duplicated(keep="last")]
            if s.empty:
                continue
            df[col] = df["fecha_hora"].map(s)
            if df[col].notna().mean() >= 0.3:
                exo_rec.append(col)
                mapas[col] = s
                if col == "cmg_pcp":       # el PID no está disponible day-ahead
                    exo_da.append(col)

    # Peso ERV del SEN del día anterior (mix diario).
    erv = _load_erv_share()
    if not erv.empty:
        emap = erv.to_dict()
        df["erv_share"] = [emap.get((ts - timedelta(days=1)).date(), np.nan)
                           for ts in df["fecha_hora"]]
        if df["erv_share"].notna().mean() >= 0.3:
            exo_rec.append("erv_share"); exo_da.append("erv_share")
            mapas["erv"] = emap

    base_rec = F_TIEMPO + [f"lag_{l}h" for l in LAGS_CORTOS + LAGS_LARGOS] + \
               ["ma_6h", "ma_24h", "std_24h"]
    base_da = F_TIEMPO + [f"lag_{l}h" for l in LAGS_LARGOS] + ["ma_24h_lag24"]
    feats_rec = base_rec + exo_rec
    feats_da = base_da + exo_da

    df = df.dropna(subset=base_rec + ["cmg_usd_mwh"])
    return df, feats_rec, feats_da, mapas


F_DESACOPLE = ["hora_sin", "hora_cos", "dia_semana", "mes",
               "cmg_pcp", "dem_lag_24h", "erv_share"]


def _dataset_desacople(nodo):
    """Matriz del clasificador de desacople, anclada al CMG REAL liquidado.

    Se construye sobre la línea de tiempo del CMG real y NO sobre la del online,
    por dos razones: (a) el online descartaba los ceros antes del 27/07 (regla 27),
    así que su histórico de desacoples es ficticio; (b) en Angamos y Cochrane el
    online arranca el 27/07 y el real termina ~10 días atrás — no se solapan, y
    cruzarlos dejaba el set en CERO filas justamente en las barras de las propias
    centrales, que son las que importan.

    Todas las features están disponibles el día anterior: calendario, CMG
    programado PCP de la hora, demanda neta con rezago 24h y peso ERV del día
    previo. Deliberadamente NO hay rezagos del propio CMG real: llegan con ~10
    días de atraso y no existirían al momento de predecir."""
    real = _load_cmg_real_ml(nodo)
    if real.empty:
        return None
    b = pd.DataFrame({"fecha_hora": real.index, "cmg_real": real.values}).sort_values("fecha_hora")
    b = _add_time(b)

    prog = _load_cmg_prog_ml(nodo)
    s = pd.Series(dtype=float)
    if not prog.empty:
        s = prog[prog["fuente"] == "CEN_PCP"].set_index("fecha_hora")["cmg_usd_mwh"]
        s = s[~s.index.duplicated(keep="last")]
    b["cmg_pcp"] = b["fecha_hora"].map(s) if not s.empty else np.nan

    dem = _load_dem_neta()
    dmap = dem.set_index("fecha_hora")["demanda_neta_mwh"] if not dem.empty else None
    b["dem_lag_24h"] = ((b["fecha_hora"] - timedelta(hours=24)).map(dmap)
                        if dmap is not None else np.nan)

    emap = _load_erv_share().to_dict()
    b["erv_share"] = [emap.get((t - timedelta(days=1)).date(), np.nan) for t in b["fecha_hora"]]

    mapas = {"cmg_pcp": s, "dem": dmap, "erv": emap}
    return b.reset_index(drop=True), mapas


def _filas_futuras_desacople(desde, mapas, horas=24):
    """Vector de features day-ahead para las próximas `horas`, sin rezagos propios."""
    out = []
    for h in range(1, horas + 1):
        t = desde + timedelta(hours=h)
        pcp = mapas["cmg_pcp"]
        out.append({
            "fecha_hora": t,
            "hora_sin": np.sin(2*np.pi*t.hour/24), "hora_cos": np.cos(2*np.pi*t.hour/24),
            "dia_semana": t.dayofweek, "mes": t.month,
            "cmg_pcp": (pcp.get(t, np.nan) if pcp is not None and len(pcp) else np.nan),
            "dem_lag_24h": (mapas["dem"].get(t - timedelta(hours=24), np.nan)
                            if mapas["dem"] is not None else np.nan),
            "erv_share": mapas["erv"].get((t - timedelta(days=1)).date(), np.nan),
        })
    return pd.DataFrame(out)


def _fila_futura(ndt, history, mapas, feats):
    """Vector de features para una hora futura, dado el historial (real + predicho)."""
    recent = np.array(history, dtype=float)
    row = {"hora_sin": np.sin(2*np.pi*ndt.hour/24), "hora_cos": np.cos(2*np.pi*ndt.hour/24),
           "dia_semana": ndt.dayofweek, "mes": ndt.month,
           "ma_6h": recent[-6:].mean(), "ma_24h": recent[-24:].mean(),
           "std_24h": recent[-24:].std(),
           "ma_24h_lag24": recent[-48:-24].mean() if len(recent) >= 48 else recent[:-24].mean()}
    for l in LAGS_CORTOS + LAGS_LARGOS:
        row[f"lag_{l}h"] = history[-l] if l <= len(history) else np.nan
    if "dem_lag_24h" in feats:
        row["dem_lag_24h"] = mapas["dem"].get(ndt - timedelta(hours=24), np.nan)
    for col in ("cmg_pcp", "cmg_pid"):
        if col in feats:
            row[col] = mapas[col].get(ndt, np.nan)
    if "erv_share" in feats:
        row["erv_share"] = mapas["erv"].get((ndt - timedelta(days=1)).date(), np.nan)
    return row


# ══════════════════════════════════════════════════════════════════════════════
def render_ml():
    st.markdown('<div class="sec">Análisis predictivo · suite de modelos ML</div>',
                unsafe_allow_html=True)
    st.caption("Modelos entrenados en vivo sobre el histórico de Supabase (se recargan cada "
               "hora; no hay pesos congelados). Precio con banda calibrada y medido contra el "
               "Coordinador, desviaciones cruzadas con su causa, y riesgo de desacople.")
    sub = st.radio("Modelo",
                   ["Pronóstico CMG", "Desviación explicada", "Riesgo de desacople"],
                   horizontal=True, label_visibility="collapsed", key="ml_sub")
    if sub == "Pronóstico CMG":
        _seccion_cmg()
    elif sub == "Desviación explicada":
        _seccion_desviacion()
    else:
        _seccion_desacople()


# ══════════════════════════════════════════════════════════════════════════════
# 1 · Pronóstico CMG cuantílico calibrado + benchmark vs Coordinador
# ══════════════════════════════════════════════════════════════════════════════
def _seccion_cmg():
    # Los ajustes viven en las funciones cacheadas; aquí solo se comprueba el stack.
    try:
        from importlib.util import find_spec
        if find_spec("xgboost") is None:
            raise ImportError("xgboost")
        from sklearn.metrics import mean_absolute_error, mean_squared_error
    except ImportError:
        st.error("Instala xgboost y scikit-learn: `pip install xgboost scikit-learn`")
        return

    nodo = st.selectbox("Nodo CMG", list(NOMBRES_NODO.keys()),
                        format_func=lambda x: NOMBRES_NODO[x], key="ml_cmg_nodo")

    df, feats, feats_da, mapas = _dataset(nodo)
    if df is None or df.empty:
        st.warning("Sin datos de CMG para el nodo seleccionado.")
        return
    if len(df) < 400:
        st.warning("Datos insuficientes para entrenar (se necesitan ≥3 semanas de histórico).")
        return

    with st.spinner("Entrenando modelo cuantílico..."):
        # El sello es la última hora del histórico: mientras no llegue dato nuevo,
        # cambiar de sub-sección o mover un widget NO reentrena los 3 modelos.
        sello = str(df["fecha_hora"].iloc[-1])
        R = _entrenar_cmg(nodo, sello)

    test, dff, Q = R["test"], R["forecast"], R["Q"]
    y_true, y_pred, lo_t, hi_t = R["y_true"], R["y_pred"], R["lo_t"], R["hi_t"]
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_true.mean()) ** 2))
    cobertura = R["cobertura"]
    pin = R["pinball"]
    pico, valle = dff.loc[dff["cmg_pred"].idxmax()], dff.loc[dff["cmg_pred"].idxmin()]

    ingreso_esp, dff_ing = _ingreso_esperado(dff)

    c1, c2, c3, c4 = st.columns(4)
    _kpi(c1, f"{dff['cmg_pred'].mean():.1f}", "CMG medio previsto 24h (USD/MWh)", AES_VIOLETA)
    _kpi(c2, f"{pico['cmg_pred']:.0f}", f"Pico previsto · {pico['fecha_hora'].strftime('%d/%m %Hh')}", AES_AMBAR)
    _kpi(c3, f"{valle['cmg_pred']:.0f}", f"Valle previsto · {valle['fecha_hora'].strftime('%d/%m %Hh')}", AES_CYAN)
    if ingreso_esp is not None:
        _kpi(c4, f"${ingreso_esp:,.0f}", "Ingreso esperado 24h (USD)", AES_VERDE)
    else:
        _kpi(c4, f"±{mae:.1f}", f"Error del modelo (RMSE {rmse:.1f} · R² {r2:.2f})", AES_AZUL)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Gráfico: histórico 48h + forecast 24h con banda ──────────────────────
    ctx = df.tail(48)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dff["fecha_hora"], y=dff["hi"], mode="lines",
        line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=dff["fecha_hora"], y=dff["lo"], mode="lines", fill="tonexty",
        fillcolor=hex_to_rgba(AES_AMBAR, 0.16), line=dict(width=0),
        name="Banda P10–P90 (calibrada)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=ctx["fecha_hora"], y=ctx["cmg_usd_mwh"], name="Histórico (48h)",
        line=dict(color=AES_AZUL, width=2.4, shape="spline", smoothing=0.4),
        fill="tozeroy", fillcolor=hex_to_rgba(AES_AZUL, 0.06)))
    if "cmg_pcp" in feats:
        pcp_fut = [mapas["cmg_pcp"].get(ts, np.nan) for ts in dff["fecha_hora"]]
        if np.isfinite(pd.Series(pcp_fut, dtype=float)).sum() >= 3:
            fig.add_trace(go.Scatter(x=dff["fecha_hora"], y=pcp_fut, name="PCP del Coordinador",
                line=dict(color=AES_CYAN, width=1.6, dash="dash"),
                hovertemplate="%{x|%d/%m %Hh}<br>PCP %{y:.1f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=dff["fecha_hora"], y=dff["cmg_pred"], name="Forecast 24h",
        mode="lines+markers", line=dict(color=AES_AMBAR, width=2.4, dash="dot"), marker=dict(size=5),
        hovertemplate="%{x|%d/%m %Hh}<br>%{y:.1f} USD/MWh<extra></extra>"))
    fig.add_vline(x=df["fecha_hora"].iloc[-1].timestamp()*1000, line_dash="dash",
        line_color="#94A3B8", line_width=1, annotation_text="ahora", annotation_position="top")
    _base_layout(fig, "Costo marginal — histórico y pronóstico 24h con banda calibrada",
                 "CMG USD/MWh", hovermode="x unified")
    _show(fig)
    st.caption(f"La banda no es un ensanchamiento genérico: sale de dos modelos cuantílicos "
               f"(P10 y P90, pérdida pinball) y se corrige por conformal con Q = {Q:.1f} USD/MWh. "
               f"Cobertura verificada sobre el set de prueba: **{cobertura:.0f}%** "
               f"(objetivo 80%; si diera 60% la banda mentiría, si diera 95% sería inútilmente ancha).")

    # ── Benchmark contra el Coordinador ──────────────────────────────────────
    _benchmark_coordinador(nodo, sello)

    # ── Ingreso esperado por hora ────────────────────────────────────────────
    if dff_ing is not None:
        f_ing = go.Figure(go.Bar(x=dff_ing["fecha_hora"], y=dff_ing["ingreso"],
            marker_color=AES_VERDE,
            hovertemplate="%{x|%d/%m %Hh}<br>$%{y:,.0f}<extra></extra>"))
        _base_layout(f_ing, "Ingreso esperado por hora · CMG previsto × despacho (USD)",
                     "USD", height=300)
        f_ing.update_xaxes(tickformat="%d/%m\n%Hh")
        _show(f_ing)
        st.caption("Traduce el pronóstico de precio a dinero: multiplica el CMG previsto por la "
                   "generación programada de cada hora. Ubica las ventanas de mayor ingreso.")

    # ── Validación + importancia ─────────────────────────────────────────────
    cA, cB = st.columns([3, 2])
    with cA:
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=test["fecha_hora"], y=hi_t, mode="lines",
            line=dict(width=0), showlegend=False, hoverinfo="skip"))
        f2.add_trace(go.Scatter(x=test["fecha_hora"], y=lo_t, mode="lines", fill="tonexty",
            fillcolor=hex_to_rgba(AES_AMBAR, 0.14), line=dict(width=0),
            name="Banda P10–P90", hoverinfo="skip"))
        f2.add_trace(go.Scatter(x=test["fecha_hora"], y=y_true, name="Real",
            line=dict(color=AES_AZUL, width=2)))
        f2.add_trace(go.Scatter(x=test["fecha_hora"], y=y_pred, name="Predicho (P50)",
            line=dict(color=AES_AMBAR, width=1.8, dash="dash")))
        _base_layout(f2, f"Validación · MAE {mae:.1f} · R² {r2:.2f} · cobertura {cobertura:.0f}% "
                         f"· pinball {pin:.2f}", "CMG USD/MWh", height=320, hovermode="x unified")
        _show(f2)
    with cB:
        imp = R["importancia"].sort_values().tail(10)
        f3 = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h", marker_color=AES_CYAN,
            hovertemplate="%{y}<br>%{x:.3f}<extra></extra>"))
        _base_layout(f3, "Variables más influyentes", None, height=320)
        f3.update_layout(showlegend=False, yaxis=dict(tickfont=dict(color="#475569", size=10)))
        _show(f3)


@st.cache_data(ttl=3600, show_spinner=False)
def _entrenar_cmg(nodo, sello):
    """Entrena los 3 modelos cuantílicos, calibra por conformal y proyecta 24h.

    Cacheado por (nodo, última hora del histórico): son ~6 s de ajuste y sin esto
    se repetirían en cada interacción con un widget de la vista. Devuelve datos
    planos (no los modelos) para que `st.cache_data` los serialice sin problema.
    """
    from xgboost import XGBRegressor

    df, feats, _, mapas = _dataset(nodo)
    # Partición CRONOLÓGICA 60/20/20: entrena · calibra · prueba. El bloque de
    # calibración es el que hace honesta la banda (CQR) y el modelo nunca lo ve
    # durante el ajuste.
    n = len(df)
    i1, i2 = int(n * 0.60), int(n * 0.80)
    train, calib, test = df.iloc[:i1], df.iloc[i1:i2], df.iloc[i2:]

    def _fit(alpha=None):
        kw = dict(n_estimators=400, max_depth=5, learning_rate=0.05, subsample=0.8,
                  colsample_bytree=0.8, random_state=42, verbosity=0)
        if alpha is not None:
            kw.update(objective="reg:quantileerror", quantile_alpha=alpha)
        m = XGBRegressor(**kw)
        m.fit(train[feats], train["cmg_usd_mwh"])
        return m

    m50, m10, m90 = _fit(), _fit(0.10), _fit(0.90)

    # Los cuantiles crudos siempre dan bandas angostas (sobreconfianza). Sobre el
    # set de calibración se mide cuánto se salió la realidad de la banda y se
    # ensancha en el percentil 80 de ese error: banda bonita → banda honesta.
    yc = calib["cmg_usd_mwh"].values
    E = np.maximum(m10.predict(calib[feats]) - yc, yc - m90.predict(calib[feats]))
    Q = float(np.quantile(E, 0.80)) if len(E) else 0.0

    y_true = test["cmg_usd_mwh"].values
    y_pred = m50.predict(test[feats])
    q10_t, q90_t = m10.predict(test[feats]), m90.predict(test[feats])
    lo_t, hi_t = q10_t - Q, q90_t + Q

    # Forecast 24h recursivo: para t+1 el lag_1h es dato real; de ahí en adelante
    # se realimenta con la propia predicción.
    history = list(df["cmg_usd_mwh"].values)
    preds = []
    for h in range(1, 25):
        ndt = df["fecha_hora"].iloc[-1] + timedelta(hours=h)
        row = pd.DataFrame([_fila_futura(ndt, history, mapas, feats)])[feats]
        p = float(m50.predict(row)[0])
        preds.append({"fecha_hora": ndt, "cmg_pred": p,
                      "lo": max(0.0, float(m10.predict(row)[0]) - Q),
                      "hi": max(float(m90.predict(row)[0]) + Q, p)})
        history.append(p)

    return {
        "test": test, "forecast": pd.DataFrame(preds), "Q": Q,
        "y_true": y_true, "y_pred": y_pred, "lo_t": lo_t, "hi_t": hi_t,
        "cobertura": float(np.mean((y_true >= lo_t) & (y_true <= hi_t)) * 100),
        "pinball": (_pinball(y_true, q10_t, 0.10) + _pinball(y_true, q90_t, 0.90)) / 2,
        "importancia": pd.Series(m50.feature_importances_, index=feats),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def _benchmark_datos(nodo, sello):
    """Compara el MAE del modelo contra el del PCP y el PID del Coordinador.

    Regla del juego: para cada ventana se reentrena un modelo DAY-AHEAD usando
    SOLO datos anteriores a esa ventana, y con features disponibles el día previo
    (rezagos ≥24h + programa PCP + exógenas). Es la única comparación honesta
    contra el PCP, que también se emite el día anterior.

    Cacheado por (nodo, última hora): son 3 ajustes más, encima de los 3 del
    modelo cuantílico. Devuelve (filas, motivo_si_vacio)."""
    from xgboost import XGBRegressor

    df, _, feats_da, _ = _dataset(nodo)
    prog = _load_cmg_prog_ml(nodo)
    if prog.empty:
        return [], "Sin CMG programado almacenado para esta barra — no hay contra qué compararse."
    series = {}
    for f, nom in (("CEN_PCP", "PCP"), ("CEN_PID", "PID")):
        s = prog[prog["fuente"] == f].set_index("fecha_hora")["cmg_usd_mwh"]
        s = s[~s.index.duplicated(keep="last")]
        if not s.empty:
            series[nom] = s

    # NO se hace dropna sobre las exógenas: XGBoost trata el NaN como una rama más,
    # y el PCP solo cubre ~la mitad de las horas → un dropna dejaría el set de
    # entrenamiento en unas decenas de filas y el benchmark mediría el tamaño de
    # la muestra, no la calidad del modelo.
    d = df.dropna(subset=["cmg_usd_mwh"])
    if len(d) < 500:
        return [], "Histórico insuficiente para el benchmark contra el Coordinador."
    fin = d["fecha_hora"].max()
    ventanas = [("78 horas", 78), ("7 días", 24*7), ("30 días", 24*30)]
    filas = []
    if True:
        for nombre, horas in ventanas:
            ini = fin - timedelta(hours=horas)
            tr, te = d[d["fecha_hora"] < ini], d[d["fecha_hora"] >= ini]
            if len(tr) < 300 or len(te) < 24:
                continue
            m = XGBRegressor(n_estimators=350, max_depth=5, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0)
            m.fit(tr[feats_da], tr["cmg_usd_mwh"])
            y = te["cmg_usd_mwh"].values
            fila = {"Ventana": nombre, "Horas": len(te),
                    "MAE modelo": float(np.mean(np.abs(y - m.predict(te[feats_da]))))}
            for nom, s in series.items():
                ref = te["fecha_hora"].map(s).values.astype(float)
                ok = np.isfinite(ref)
                fila[f"MAE {nom}"] = (float(np.mean(np.abs(y[ok] - ref[ok])))
                                      if ok.sum() >= max(12, len(te) * 0.5) else np.nan)
            cands = {k.replace("MAE ", ""): v for k, v in fila.items()
                     if k.startswith("MAE") and np.isfinite(v)}
            fila["Más preciso"] = min(cands, key=cands.get) if cands else "—"
            filas.append(fila)
    return filas, None


def _benchmark_coordinador(nodo, sello):
    """Render del benchmark; el cómputo pesado vive en `_benchmark_datos`."""
    with st.spinner("Reentrenando el modelo para cada ventana del benchmark..."):
        filas, motivo = _benchmark_datos(nodo, sello)
    if not filas:
        st.info(motivo or "Histórico insuficiente para el benchmark contra el Coordinador.")
        return

    st.markdown("**Benchmark contra el Coordinador** — MAE en USD/MWh, mismo tablero day-ahead")
    t = pd.DataFrame(filas)
    num = [c for c in t.columns if c.startswith("MAE")]
    t[num] = t[num].round(2)
    st.dataframe(t, use_container_width=True, hide_index=True)

    fig = go.Figure()
    colores = {"modelo": AES_VIOLETA, "PCP": AES_CYAN, "PID": AES_AZUL}
    for c in num:
        nom = c.replace("MAE ", "")
        fig.add_trace(go.Bar(x=t["Ventana"], y=t[c], name=nom,
            marker_color=colores.get(nom, AES_AMBAR),
            hovertemplate=f"<b>{nom}</b><br>%{{x}}<br>MAE %{{y:.2f}} USD/MWh<extra></extra>"))
    _base_layout(fig, "Error del modelo vs el programa del Coordinador (menor es mejor)",
                 "MAE USD/MWh", height=300, barmode="group")
    _show(fig)
    ganadores = [f["Más preciso"] for f in filas]
    gana_modelo = sum(g == "modelo" for g in ganadores)
    st.caption(
        "El modelo se reentrena para cada ventana usando solo datos previos y con información "
        "disponible el día anterior (rezagos ≥24 h, programa PCP y exógenas) — las mismas "
        "cartas que tiene el Coordinador. Es medirse contra el estándar de la industria, no "
        "contra uno mismo."
        + ("" if gana_modelo == len(ganadores) else
           "  \n**Lectura honesta:** hoy el programa del Coordinador gana el NIVEL de precio "
           "en la mayoría de las ventanas, y era esperable: el PCP/PID sale de una optimización "
           "del sistema completo con hidrología, costos de combustible y unit commitment, "
           "mientras que este modelo solo ve precio, demanda y peso ERV sobre ~2 meses de "
           "historia. Donde el modelo sí aporta valor que el programa no da es en la BANDA de "
           "incertidumbre calibrada y en el riesgo de desacople — no en reemplazar al PID como "
           "referencia de precio."))


def _ingreso_esperado(dff):
    """Ingreso esperado 24h = Σ (CMG previsto × MW despachados) por hora.
    Usa la generación programada futura si existe; si no, el perfil horario típico
    de generación del complejo. Devuelve (total_usd, df_por_hora) o (None, None)."""
    df_real, df_prog = _load_gen()
    disp = None
    if df_prog is not None and not df_prog.empty:
        gp = (df_prog.groupby("fecha_hora")["gen_programada_mw"].sum()
              .reindex(dff["fecha_hora"]))
        if gp.notna().sum() >= 6:            # despacho futuro suficiente
            disp = gp.values
    if disp is None and df_real is not None and not df_real.empty:
        # Fallback: perfil horario típico (MW totales medios por hora del día).
        g = df_real.copy()
        g["h"] = g["fecha_hora"].dt.hour
        g["d"] = g["fecha_hora"].dt.date
        perfil = g.groupby(["d", "h"])["gen_real_mw"].sum().groupby("h").mean()
        disp = np.array([perfil.get(ts.hour, np.nan) for ts in dff["fecha_hora"]])
    if disp is None or np.all(np.isnan(disp)):
        return None, None
    disp = np.nan_to_num(disp, nan=np.nanmean(disp))
    out = pd.DataFrame({"fecha_hora": dff["fecha_hora"].values,
                        "ingreso": dff["cmg_pred"].values * disp,
                        "despacho_mw": disp})
    return float(out["ingreso"].sum()), out


# ══════════════════════════════════════════════════════════════════════════════
# 2 · Desviación explicada — de "hora anómala" a "anomalía con causa"
# ══════════════════════════════════════════════════════════════════════════════
def _seccion_desviacion():
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        st.error("Instala scikit-learn: `pip install scikit-learn`")
        return

    st.caption("Marca las horas en que la unidad se apartó de su programa y cruza cada una "
               "con las fuentes del CEN que el dashboard ya adquiere. Lo que no cruza con "
               "ninguna queda como «sin explicar»: esa es la lista a revisar en terreno.")

    cA, cB, cC = st.columns([1, 1, 1])
    with cA:
        dias = st.slider("Ventana de análisis (días)", 7, 90, 30, 1, key="ml_dev_dias")
    with cB:
        # Un umbral fijo en MW no sirve: el desvío del complejo tiene mediana ~28 MW
        # y p90 ~200 MW (las unidades entran y salen de servicio), así que cualquier
        # corte absoluto marca la mitad de las horas. El percentil se autocalibra
        # por unidad y hace que el tamaño de la lista sea una decisión explícita.
        pct = st.slider("Corte de desvío (percentil de la unidad)", 75, 99, 90, 1,
                        key="ml_dev_pct",
                        help="Se marcan las horas cuyo |desvío| supera este percentil "
                             "del histórico de la propia unidad.")
    with cC:
        cont = st.slider("Sensibilidad del detector estadístico (%)", 1, 15, 5, 1,
                         key="ml_dev_cont",
                         help="Fracción del historial que el Isolation Forest marca como atípica.")

    with st.spinner("Cargando generación y fuentes de atribución..."):
        df_real, df_prog = _load_gen()
        if df_real is None or df_real.empty:
            st.warning("Sin datos de generación.")
            return
        df = df_real.merge(df_prog, on=["unidad", "fecha_hora"], how="left")
        fin = df["fecha_hora"].max()
        ini = fin - timedelta(days=dias)
        df = df[df["fecha_hora"] >= ini].copy()
        df = _add_time(df)
        df["desvio_mw"] = df["gen_real_mw"] - df["gen_programada_mw"]
        df["fp"] = df["gen_real_mw"] / df["potencia_maxima"].replace(0, np.nan)
        df = df.sort_values(["unidad", "fecha_hora"])
        df["gen_lag1"] = df.groupby("unidad")["gen_real_mw"].shift(1)
        df["cambio_brusco"] = (df["gen_real_mw"] - df["gen_lag1"]).abs()
        df = df.dropna(subset=["gen_programada_mw", "gen_lag1"])
        if df.empty:
            st.warning("Sin horas con programa y real comparables en la ventana.")
            return
        eventos = _cargar_eventos(ini.date().isoformat(), fin.date().isoformat())

    unidades = sorted(df["unidad"].unique())
    sel = st.radio("Unidad", unidades, horizontal=True,
                   format_func=lambda u: LABELS.get(u, u), key="ml_dev_u")
    dfu = df[df["unidad"] == sel].copy()
    if len(dfu) < 50:
        st.info(f"Datos insuficientes para {LABELS.get(sel, sel)}.")
        return

    # ── Dos detectores en paralelo ───────────────────────────────────────────
    # (1) Umbral operacional: desvío material respecto del programa (percentil de
    #     la propia unidad), o unidad detenida cuando el programa la pedía en
    #     servicio (regla 23) — este segundo caso entra siempre, sin importar el
    #     percentil, porque un trip es un evento por sí mismo.
    umbral = float(np.percentile(dfu["desvio_mw"].abs(), pct))
    det_umbral = (dfu["desvio_mw"].abs() > umbral) | \
                 ((dfu["gen_real_mw"] < UMBRAL_TRIP) & (dfu["gen_programada_mw"] >= UMBRAL_TRIP))
    # (2) Isolation Forest: combinaciones raras aunque el desvío sea moderado.
    feats = ["gen_real_mw", "gen_programada_mw", "desvio_mw", "fp", "cambio_brusco",
             "hora_sin", "hora_cos"]
    Xs = StandardScaler().fit_transform(dfu[feats])
    iso = IsolationForest(n_estimators=200, contamination=cont/100, random_state=42)
    det_iso = iso.fit_predict(Xs) == -1
    dfu["score"] = iso.score_samples(Xs)
    smin, smax = dfu["score"].min(), dfu["score"].max()
    dfu["severidad"] = (smax - dfu["score"]) / (smax - smin + 1e-9) * 100
    dfu["detectada"] = det_umbral | det_iso
    dfu["detector"] = np.where(det_umbral & det_iso, "ambos",
                        np.where(det_umbral, "umbral", "estadístico"))

    anomal = dfu[dfu["detectada"]].copy()
    if anomal.empty:
        st.success(f"Sin desviaciones materiales de {LABELS.get(sel, sel)} en la ventana.")
        return

    # ── Cascada de atribución ────────────────────────────────────────────────
    anomal["causa"] = [_atribuir(sel, ts, eventos, dv)
                       for ts, dv in zip(anomal["fecha_hora"], anomal["desvio_mw"])]
    color = COLORES[sel]["line"]
    sin_exp = anomal[anomal["causa"] == "Sin explicar"]
    # Solo el subrendimiento no explicado es "energía perdida"; un desvío al alza
    # no es una pérdida y mezclarlos inflaría la cifra.
    energia_perdida = float((-sin_exp["desvio_mw"].clip(upper=0)).sum())
    pct_expl = (1 - len(sin_exp) / len(anomal)) * 100

    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, f"{len(anomal)}", f"Horas desviadas · corte {umbral:.0f} MW (p{pct})", color)
    _kpi(k2, f"{pct_expl:.0f}%", "explicadas por una fuente del CEN", AES_VERDE)
    _kpi(k3, f"{len(sin_exp)}", "sin explicar — posible falla", AES_ROJO)
    _kpi(k4, f"{energia_perdida:,.0f} MW-h", "de subrendimiento sin explicar", AES_AMBAR)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Serie con las desviaciones coloreadas por causa ──────────────────────
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dfu["fecha_hora"], y=dfu["gen_real_mw"], name="Gen. real",
        line=dict(color=color, width=1.6), opacity=0.85))
    fig.add_trace(go.Scatter(x=dfu["fecha_hora"], y=dfu["gen_programada_mw"], name="Programada",
        line=dict(color=COLORES[sel]["prog"], width=1, dash="dot"), opacity=0.7))
    for causa in COLOR_CAUSA:
        sub = anomal[anomal["causa"] == causa]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(x=sub["fecha_hora"], y=sub["gen_real_mw"], mode="markers",
            name=f"{causa} ({len(sub)})",
            marker=dict(color=COLOR_CAUSA[causa], size=8,
                        symbol="x" if causa == "Sin explicar" else "circle",
                        line=dict(color="#fff", width=1)),
            customdata=np.stack([sub["desvio_mw"], sub["severidad"]], axis=-1),
            hovertemplate="%{x|%d/%m %H:%M}<br>%{y:.0f} MW<br>Desvío %{customdata[0]:.0f} MW"
                          "<br>Severidad %{customdata[1]:.0f}/100<extra>" + causa + "</extra>"))
    _base_layout(fig, f"{LABELS.get(sel, sel)} — desviaciones marcadas y atribuidas a su causa",
                 "MW", hovermode="closest")
    _show(fig)
    st.caption("Cada marca es una hora detectada; el color dice por qué. Las cruces rojas son "
               "las que ninguna fuente del CEN justifica.")

    # ── Reparto por causa ────────────────────────────────────────────────────
    cG1, cG2 = st.columns([1, 1])
    with cG1:
        rep = (anomal.groupby("causa").size().reindex(list(COLOR_CAUSA)).dropna()
               .sort_values(ascending=True))
        f2 = go.Figure(go.Bar(x=rep.values, y=rep.index, orientation="h",
            marker_color=[COLOR_CAUSA[c] for c in rep.index],
            hovertemplate="%{y}<br>%{x} horas<extra></extra>"))
        _base_layout(f2, "Horas desviadas por causa atribuida", None, height=280)
        f2.update_layout(showlegend=False,
                         yaxis=dict(tickfont=dict(color="#475569", size=10)))
        _show(f2)
    with cG2:
        en = anomal.copy()
        en["perdida"] = -en["desvio_mw"].clip(upper=0)
        en["dia"] = en["fecha_hora"].dt.date
        serie = en[en["causa"] == "Sin explicar"].groupby("dia")["perdida"].sum()
        f3 = go.Figure(go.Bar(x=[str(d) for d in serie.index], y=serie.values,
            marker_color=AES_ROJO,
            hovertemplate="%{x}<br>%{y:.0f} MW-h sin explicar<extra></extra>"))
        _base_layout(f3, "Subrendimiento sin explicar por día (MW-h)", "MW-h", height=280)
        f3.update_layout(showlegend=False, bargap=0.45,
                         xaxis=dict(type="category", tickfont=dict(color=INK_AXIS, size=9)))
        _show(f3)

    # ── La lista que importa ─────────────────────────────────────────────────
    st.markdown("**Horas sin explicar — candidatas a revisión en terreno**")
    if sin_exp.empty:
        st.success("Todas las desviaciones de la ventana quedaron atribuidas a una fuente del CEN.")
    else:
        top = (sin_exp.nlargest(15, "severidad")
               [["fecha_hora", "gen_real_mw", "gen_programada_mw", "desvio_mw",
                 "cambio_brusco", "severidad", "detector"]]
               .rename(columns={"fecha_hora": "Fecha/Hora", "gen_real_mw": "Real (MW)",
                                "gen_programada_mw": "Programada (MW)", "desvio_mw": "Desvío (MW)",
                                "cambio_brusco": "Cambio brusco (MW)", "severidad": "Severidad",
                                "detector": "Detector"})
               .reset_index(drop=True))
        top["Fecha/Hora"] = pd.to_datetime(top["Fecha/Hora"]).dt.strftime("%d/%m %H:%M")
        num_cols = ["Real (MW)", "Programada (MW)", "Desvío (MW)", "Cambio brusco (MW)", "Severidad"]
        top[num_cols] = top[num_cols].round(1)
        st.dataframe(top, use_container_width=True, hide_index=True)
        st.caption("Orden de prioridad de la cascada: instrucción del CEN → limitación de "
                   "transmisión → SSCC instruido → mantenimiento mayor. Si una hora no cruza "
                   "con ninguna, el desvío no tiene origen documentado.")


def _cargar_eventos(s, e):
    """Ventanas (unidad, inicio, fin, causa) de todas las fuentes de atribución.

    Cada fuente aporta intervalos; la atribución es un test de pertenencia de la
    hora desviada a esos intervalos. Todo va defensivo: una fuente que falta
    simplemente no aporta ventanas (y sus horas caerán en «Sin explicar»)."""
    ev = {c: [] for c in COLOR_CAUSA if c != "Sin explicar"}

    # 1 · Instrucción de despacho por CMG (hora puntual, unidad explícita).
    try:
        ins = load_instrucciones_cmg(s, e)
        if ins is not None and not ins.empty:
            for _, r in ins.iterrows():
                u = r.get("unidad")
                dt = pd.to_datetime(r.get("fecha_hora"), errors="coerce")
                if u in LABELS and pd.notna(dt):
                    ev["Instrucción CEN"].append((u, dt.floor("h"), dt.floor("h")))
    except Exception:
        pass

    # 2 · Limitaciones de transmisión (perturbación → retorno; id_unidad 1965-1968).
    try:
        lim = load_limitaciones(s, e)
        if lim is not None and not lim.empty:
            for _, r in lim.iterrows():
                try:
                    u = ID_UNIDAD_LIM.get(int(float(r.get("id_unidad"))))
                except (TypeError, ValueError):
                    u = None
                if u is None:
                    continue
                ini = pd.to_datetime(r.get("fecha_perturbacion"), errors="coerce")
                fin = pd.to_datetime(r.get("fecha_efectiva_retorno"), errors="coerce")
                if pd.isna(fin):
                    fin = pd.to_datetime(r.get("fecha_retorno_estimada"), errors="coerce")
                if pd.isna(ini):
                    continue
                if pd.isna(fin):          # limitación aún abierta: acotar, no eternizar
                    fin = ini + timedelta(days=7)
                # Una limitación que "cubre" meses no explica nada: la tabla trae
                # registros abiertos (p. ej. 29/04 → 31/12 con potencia 0) que, sin
                # este tope, atribuirían el 100% de los desvíos de ANG1/ANG2.
                if (fin - ini) > timedelta(days=VENTANA_MAX_DIAS):
                    continue
                ev["Limitación transmisión"].append((u, ini.floor("h"), fin.ceil("h")))
    except Exception:
        pass

    # 3 · SSCC instruido (fecha + inicio/fin del período "HH:MM:SS").
    try:
        ss = load_sscc(s, e)
        if ss is not None and not ss.empty:
            for _, r in ss.iterrows():
                u = r.get("unidad")
                if u not in LABELS:
                    continue
                f = str(r.get("fecha") or "")[:10]
                ini = pd.to_datetime(f"{f} {str(r.get('inicio_periodo') or '')[:8]}",
                                     errors="coerce")
                fin = pd.to_datetime(f"{f} {str(r.get('fin_periodo') or '')[:8]}",
                                     errors="coerce")
                if pd.isna(ini):
                    continue
                if pd.isna(fin) or fin < ini:
                    fin = ini + timedelta(hours=1)
                ev["SSCC instruido"].append((u, ini.floor("h"), fin.ceil("h")))
    except Exception:
        pass

    # 4 · Mantenimiento mayor (aplica a las 4 unidades: incluye el corredor de
    #     evacuación Mejillones–O'Higgins, que afecta a CTM sin intervenirla).
    try:
        mm = load_mantenimiento_mayor()
        if mm is not None and not mm.empty:
            for _, r in mm.iterrows():
                ini = r.get("fecha_inicio_programa_dt")
                fin = r.get("fecha_fin_programa_dt")
                if pd.isna(ini):
                    continue
                if pd.isna(fin):
                    fin = ini + timedelta(days=1)
                if (pd.Timestamp(fin) - pd.Timestamp(ini)) > timedelta(days=VENTANA_MAX_DIAS):
                    continue
                for u in LABELS:
                    ev["Mantenimiento mayor"].append((u, pd.Timestamp(ini).floor("h"),
                                                      pd.Timestamp(fin).ceil("h")))
    except Exception:
        pass

    # Indexar por unidad para que la atribución no sea O(n²) sobre todo el set.
    idx = {}
    for causa, lst in ev.items():
        for u, a, b in lst:
            idx.setdefault(u, []).append((a, b, causa))
    return idx


def _atribuir(unidad, ts, eventos, desvio=None):
    """Primera causa de la cascada cuya ventana contiene la hora. Orden = prioridad.

    `desvio` (real − programado) filtra las causas que solo pueden explicar un
    subrendimiento: si la unidad generó DE MÁS, una limitación de transmisión
    coincidente en el tiempo no es su explicación."""
    ts = pd.Timestamp(ts).floor("h")
    cands = {c for a, b, c in eventos.get(unidad, []) if a <= ts <= b}
    al_alza = desvio is not None and desvio > 0
    for causa in COLOR_CAUSA:                 # dict ordenado por prioridad
        if causa in cands and not (al_alza and causa in CAUSAS_SOLO_BAJA):
            return causa
    return "Sin explicar"


# ══════════════════════════════════════════════════════════════════════════════
# 3 · Riesgo de desacople — el evento que borra el ingreso
# ══════════════════════════════════════════════════════════════════════════════
def _seccion_desacople():
    try:
        from xgboost import XGBClassifier
        from sklearn.metrics import roc_auc_score
    except ImportError:
        st.error("Instala xgboost y scikit-learn: `pip install xgboost scikit-learn`")
        return

    st.caption("Un modelo de error medio aplana los ceros: predice mal justo el evento que "
               "más plata mueve. Aquí el desacople se modela como lo que es — un evento "
               "binario — con features disponibles el día anterior. El objetivo se toma del "
               "CMG REAL liquidado, no del online: hasta el 27/07 el feed anterior descartaba "
               "los registros en cero, así que entrenar sobre el online daría un modelo que "
               "nunca vio el evento que debe predecir.")

    c1, c2 = st.columns([2, 1])
    with c1:
        nodo = st.selectbox("Nodo CMG", list(NOMBRES_NODO.keys()),
                            format_func=lambda x: NOMBRES_NODO[x], key="ml_des_nodo")
    with c2:
        umbral = st.slider("Umbral de desacople (USD/MWh)", 0.0, 20.0, 1.0, 0.5,
                           key="ml_des_umbral",
                           help="CMG por debajo de este valor se considera desacople. "
                                "0–1 captura el cero estricto; subirlo incluye horas de precio colapsado.")

    with st.spinner("Entrenando clasificador..."):
        ds = _dataset_desacople(nodo)
        if ds is None:
            st.info(f"Sin CMG real liquidado almacenado para {NOMBRES_NODO[nodo]}: no hay "
                    "histórico de desacoples sobre el cual entrenar.")
            return
        d, mapas = ds
        feats_da = F_DESACOPLE
        d["y"] = (d["cmg_real"] <= umbral).astype(int)
        base = d["y"].mean() if len(d) else 0.0
        if len(d) < 200 or d["y"].sum() < 20:
            st.info(f"Solo {int(d['y'].sum())} horas de desacople (CMG real ≤ {umbral:.1f}) "
                    f"sobre {len(d)} horas con liquidación en {NOMBRES_NODO[nodo]}: "
                    "insuficientes para entrenar un clasificador. El CMG real llega con "
                    "~10 días de rezago, así que el histórico crece solo.")
            return
        n = len(d)
        i1 = int(n * 0.80)
        tr, te = d.iloc[:i1], d.iloc[i1:]
        if te["y"].nunique() < 2:
            st.info("El período de prueba no contiene ambos casos (desacople y no desacople): "
                    "las métricas no serían interpretables. Ajusta el umbral.")
            return
        # scale_pos_weight compensa el desbalance: sin él el modelo aprende a decir
        # "nunca hay desacople" y acierta el 95% siendo inútil.
        pos = max(int(tr["y"].sum()), 1)
        spw = (len(tr) - pos) / pos
        clf = XGBClassifier(n_estimators=350, max_depth=4, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, random_state=42,
                            eval_metric="logloss", scale_pos_weight=spw, verbosity=0)
        clf.fit(tr[feats_da], tr["y"])
        p_te = clf.predict_proba(te[feats_da])[:, 1]
        auc = float(roc_auc_score(te["y"], p_te))

    # ── Probabilidad para las próximas 24h ───────────────────────────────────
    # El ancla del horizonte es AHORA, no el último dato liquidado: las features
    # son todas day-ahead, así que el modelo puede opinar sobre mañana aunque la
    # liquidación venga con 10 días de atraso.
    ahora = pd.Timestamp.now().floor("h")
    ff = _filas_futuras_desacople(ahora, mapas)
    prob = clf.predict_proba(ff[feats_da])[:, 1]
    fut = pd.DataFrame({"fecha_hora": ff["fecha_hora"], "prob": prob})

    # ── Ingreso en riesgo = P(desacople) × despacho × precio esperado ────────
    riesgo_usd, fut = _ingreso_en_riesgo(fut, nodo, mapas)

    horas_alto = int((fut["prob"] >= 0.5).sum())
    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, f"{fut['prob'].mean()*100:.0f}%", "Probabilidad media de desacople 24h", AES_VIOLETA)
    _kpi(k2, f"{horas_alto} h", "de las próximas 24 con riesgo alto (≥50%)", AES_AMBAR)
    if riesgo_usd is not None:
        _kpi(k3, f"${riesgo_usd:,.0f}", "Ingreso en riesgo 24h (USD)", AES_ROJO)
    else:
        _kpi(k3, f"{base*100:.1f}%", "Frecuencia histórica del evento", AES_ROJO)
    _kpi(k4, f"{auc:.2f}", f"AUC del modelo · base {base*100:.1f}%", AES_AZUL)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Probabilidad hora a hora ─────────────────────────────────────────────
    cols_barra = [AES_ROJO if p >= 0.5 else (AES_AMBAR if p >= 0.25 else AES_VERDE)
                  for p in fut["prob"]]
    f1 = go.Figure(go.Bar(x=fut["fecha_hora"], y=fut["prob"] * 100, marker_color=cols_barra,
        hovertemplate="%{x|%d/%m %Hh}<br>Riesgo %{y:.0f}%<extra></extra>"))
    f1.add_hline(y=50, line_dash="dash", line_color="#94A3B8", line_width=1,
                 annotation_text="riesgo alto", annotation_position="top right",
                 annotation_font=dict(size=9, color=INK_AXIS))
    _base_layout(f1, f"Riesgo de desacople en {NOMBRES_NODO[nodo]} — próximas 24 horas", "%",
                 height=320)
    f1.update_layout(showlegend=False, yaxis=dict(range=[0, 100], gridcolor=C_GRID,
                                                  tickfont=dict(color=INK_AXIS, size=10)))
    f1.update_xaxes(tickformat="%d/%m\n%Hh")
    _show(f1)
    st.caption(f"Verde < 25% · ámbar 25–50% · rojo ≥ 50%. El modelo usa solo información "
               f"disponible el día anterior (calendario, CMG programado PCP del Coordinador, "
               f"demanda neta con rezago 24 h y peso ERV del SEN), así que el aviso llega con "
               f"un día de anticipación. AUC {auc:.2f} sobre el 20% más reciente del "
               f"histórico liquidado (0,5 sería azar; la frecuencia base del evento es "
               f"{base*100:.0f}%).")

    if riesgo_usd is not None:
        f2 = go.Figure(go.Bar(x=fut["fecha_hora"], y=fut["riesgo_usd"], marker_color=AES_ROJO,
            hovertemplate="%{x|%d/%m %Hh}<br>$%{y:,.0f} en riesgo<extra></extra>"))
        _base_layout(f2, "Ingreso en riesgo por hora · P(desacople) × despacho × precio (USD)",
                     "USD", height=280)
        f2.update_layout(showlegend=False)
        f2.update_xaxes(tickformat="%d/%m\n%Hh")
        _show(f2)
        st.caption("Traduce la probabilidad a dinero: cuánto del ingreso esperado de cada hora "
                   "está expuesto a que el precio de la barra colapse. Es el aviso que le "
                   "sirve a comercial con un día de anticipación.")

    # ── Cuándo ocurre históricamente + calibración ───────────────────────────
    cA, cB = st.columns([1, 1])
    with cA:
        por_hora = d.groupby(d["fecha_hora"].dt.hour)["y"].mean() * 100
        f3 = go.Figure(go.Bar(x=por_hora.index, y=por_hora.values, marker_color=AES_VIOLETA,
            hovertemplate="%{x}:00 h<br>%{y:.1f}% de las horas<extra></extra>"))
        _base_layout(f3, "Frecuencia histórica de desacople por hora del día", "% de horas",
                     height=300)
        f3.update_layout(showlegend=False)
        f3.update_xaxes(dtick=3, title="Hora del día", title_font=dict(color=INK_AXIS, size=10))
        _show(f3)
    with cB:
        # Curva de fiabilidad: de las horas a las que el modelo les dio ~X% de
        # riesgo, ¿qué fracción se desacopló de verdad? La diagonal es lo ideal.
        bins = np.linspace(0, 1, 6)
        b = pd.cut(p_te, bins, include_lowest=True)
        rel = pd.DataFrame({"p": p_te, "y": te["y"].values, "b": b}).groupby("b", observed=True)
        obs, esp = rel["y"].mean() * 100, rel["p"].mean() * 100
        f4 = go.Figure()
        f4.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", name="Ideal",
            line=dict(color="#CBD5E1", width=1, dash="dash"), hoverinfo="skip"))
        f4.add_trace(go.Scatter(x=esp.values, y=obs.values, mode="lines+markers",
            name="Modelo", line=dict(color=AES_CYAN, width=2.4), marker=dict(size=8),
            hovertemplate="Predicho %{x:.0f}%<br>Observado %{y:.0f}%<extra></extra>"))
        _base_layout(f4, "Fiabilidad: riesgo predicho vs frecuencia observada", "% observado",
                     height=300)
        f4.update_xaxes(title="% predicho", title_font=dict(color=INK_AXIS, size=10))
        _show(f4)
    st.caption("Izquierda: a qué hora del día se desacopla la barra (la inyección solar del "
               "mediodía es el sospechoso habitual). Derecha: si la curva sigue la diagonal, "
               "un 30% de riesgo significa de verdad que 3 de cada 10 de esas horas se desacoplan.")

    # ── Qué variables anticipan el desacople ─────────────────────────────────
    imp = pd.Series(clf.feature_importances_, index=feats_da).sort_values().tail(10)
    f5 = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h", marker_color=AES_CYAN,
        hovertemplate="%{y}<br>%{x:.3f}<extra></extra>"))
    _base_layout(f5, "Qué anticipa el desacople", None, height=300)
    f5.update_layout(showlegend=False, yaxis=dict(tickfont=dict(color="#475569", size=10)))
    _show(f5)


def _ingreso_en_riesgo(fut, nodo, mapas):
    """P(desacople) × MW despachados × precio de referencia, hora a hora.

    El precio de referencia es el PCP del Coordinador para esa hora (es lo que se
    dejaría de percibir si la barra NO se desacopla); si no hay PCP, se usa el CMG
    medio reciente del nodo. Devuelve (total_usd, fut_con_columna)."""
    fut = fut.copy()
    df_real, df_prog = _load_gen()
    disp = None
    if df_prog is not None and not df_prog.empty:
        gp = df_prog.groupby("fecha_hora")["gen_programada_mw"].sum().reindex(fut["fecha_hora"])
        if gp.notna().sum() >= 6:
            disp = gp.values
    if disp is None and df_real is not None and not df_real.empty:
        g = df_real.copy()
        g["h"] = g["fecha_hora"].dt.hour
        g["d"] = g["fecha_hora"].dt.date
        perfil = g.groupby(["d", "h"])["gen_real_mw"].sum().groupby("h").mean()
        disp = np.array([perfil.get(ts.hour, np.nan) for ts in fut["fecha_hora"]])
    if disp is None or np.all(np.isnan(disp)):
        return None, fut
    disp = np.nan_to_num(disp, nan=np.nanmean(disp))

    if "cmg_pcp" in mapas:
        precio = np.array([mapas["cmg_pcp"].get(ts, np.nan) for ts in fut["fecha_hora"]],
                          dtype=float)
    else:
        precio = np.full(len(fut), np.nan)
    if not np.isfinite(precio).any():
        cmg = _load_cmg()
        cmg = cmg[cmg["barra_transf"] == nodo].tail(24 * 7)
        if cmg.empty:
            return None, fut
        precio = np.full(len(fut), float(cmg["cmg_usd_mwh"].mean()))
    precio = np.nan_to_num(precio, nan=float(np.nanmean(precio)))

    fut["riesgo_usd"] = fut["prob"].values * disp * precio
    return float(fut["riesgo_usd"].sum()), fut
