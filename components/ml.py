"""
components/ml.py — Análisis predictivo (Machine Learning) del CTM · rediseño 2026-07.

Suite de modelos con valor operacional y económico directo:

  · Pronóstico CMG PROBABILÍSTICO (XGBoost): forecast 24h con banda de
    incertidumbre P10–P90 (bootstrap de residuales), backtest e importancia de
    variables, y — novedad — el INGRESO ESPERADO 24h (CMG previsto × despacho
    programado por hora), que traduce el precio a dinero.
  · Detección de anomalías (Isolation Forest) por unidad, con línea de severidad
    (score) en el tiempo y ranking de las horas más atípicas.
  · Regímenes operacionales (KMeans): agrupa los días del histórico por su perfil
    horario de precio y descubre "tipos de día" (valle nocturno, caro sostenido,
    volátil…) — inteligencia de patrones no supervisada.

Se renderiza como sub-sección de «Análisis» (no fija page_config) y también desde
pages/ml_analysis.py. Paleta corporativa AES; sin ejes duales.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (COLORES, LABELS, AES_AZUL, AES_AMBAR, AES_CYAN, AES_VERDE,
                    AES_VIOLETA, AES_ROJO, NOMBRES_NODO, BG_TRANSP, C_GRID)
from utils.db import fetch, rest_enabled
from utils.plotly_theme import hex_to_rgba

INK       = "#1A1F36"
INK_AXIS  = "#94A3B8"
# Tema categórico de clusters (orden fijo, nunca cíclico) — anclas del espectro AES.
CLUSTER_COLORS = [AES_VIOLETA, AES_AZUL, AES_CYAN, AES_VERDE, AES_AMBAR]


@st.cache_data(ttl=3600, show_spinner=False)
def _load_cmg():
    df = fetch(
        "costo_marginal", "fecha_hora,barra_transf,cmg_usd_mwh", order="fecha_hora",
        sql="SELECT fecha_hora, barra_transf, cmg_usd_mwh FROM costo_marginal "
            "WHERE barra_transf IN ('CRUCERO_______220','TARAPACA______220') ORDER BY fecha_hora",
    )
    if not df.empty:
        df = df[df["barra_transf"].isin(list(NOMBRES_NODO.keys()))]
        df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
        df = df.sort_values("fecha_hora")
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


# ══════════════════════════════════════════════════════════════════════════════
def render_ml():
    st.markdown('<div class="sec">Análisis predictivo · suite de modelos ML</div>',
                unsafe_allow_html=True)
    st.caption("Modelos entrenados sobre el histórico de Supabase (se recargan cada hora). "
               "Pronóstico probabilístico de precio + ingreso esperado, vigilancia de "
               "anomalías y descubrimiento de regímenes operacionales.")
    sub = st.radio("Modelo",
                   ["Pronóstico CMG", "Anomalías de generación", "Regímenes operacionales"],
                   horizontal=True, label_visibility="collapsed", key="ml_sub")
    if sub == "Pronóstico CMG":
        _seccion_cmg()
    elif sub == "Anomalías de generación":
        _seccion_anomalias()
    else:
        _seccion_regimenes()


# ══════════════════════════════════════════════════════════════════════════════
# 1 · Pronóstico CMG probabilístico + ingreso esperado
# ══════════════════════════════════════════════════════════════════════════════
def _seccion_cmg():
    try:
        from xgboost import XGBRegressor
        from sklearn.metrics import mean_absolute_error, mean_squared_error
    except ImportError:
        st.error("Instala xgboost y scikit-learn: `pip install xgboost scikit-learn`")
        return

    nodo = st.selectbox("Nodo CMG", list(NOMBRES_NODO.keys()),
                        format_func=lambda x: NOMBRES_NODO[x], key="ml_cmg_nodo")
    with st.spinner("Entrenando modelo..."):
        df_raw = _load_cmg()
        df = (df_raw[df_raw["barra_transf"] == nodo]
              .set_index("fecha_hora").sort_index()[["cmg_usd_mwh"]].copy())
        if df.empty:
            st.warning("Sin datos de CMG para el nodo seleccionado.")
            return
        idx = pd.date_range(df.index.min(), df.index.max(), freq="h")
        df = df.reindex(idx).ffill(limit=3).dropna().reset_index().rename(columns={"index": "fecha_hora"})

        LAGS = [1, 2, 3, 6, 12, 24, 48]
        df = _add_time(df)
        for l in LAGS:
            df[f"lag_{l}h"] = df["cmg_usd_mwh"].shift(l)
        # Medias móviles: nivel reciente y de un día — suavizan el arranque recursivo.
        df["ma_6h"] = df["cmg_usd_mwh"].shift(1).rolling(6).mean()
        df["ma_24h"] = df["cmg_usd_mwh"].shift(1).rolling(24).mean()
        feats_base = ["hora_sin", "hora_cos", "dia_semana", "mes", "ma_6h", "ma_24h"] + \
                     [f"lag_{l}h" for l in LAGS]
        df = df.dropna(subset=feats_base + ["cmg_usd_mwh"])
        feats = list(feats_base)

        # Demanda neta del SEN con rezago de 24h: el driver físico del precio.
        # Con lag 24 el valor está disponible en TODO el horizonte de forecast
        # (para t+h se usa la demanda de t+h−24, ya observada). XGBoost tolera
        # los NaN de las horas sin publicación (rezago ~1 día del CEN).
        dem = _load_dem_neta()
        dem_map = (dem.set_index("fecha_hora")["demanda_neta_mwh"]
                   if not dem.empty else None)
        if dem_map is not None:
            df["dem_lag_24h"] = (df["fecha_hora"] - pd.Timedelta(hours=24)).map(dem_map)
            if df["dem_lag_24h"].notna().mean() >= 0.3:
                feats.append("dem_lag_24h")
            else:
                dem_map = None

        cutoff = df["fecha_hora"].max() - pd.Timedelta(days=14)
        train, test = df[df["fecha_hora"] <= cutoff], df[df["fecha_hora"] > cutoff]
        if len(train) < 100 or len(test) < 10:
            st.warning("Datos insuficientes para entrenar (se necesitan ≥2 semanas de histórico).")
            return

        model = XGBRegressor(n_estimators=400, max_depth=5, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0)
        model.fit(train[feats], train["cmg_usd_mwh"])
        y_pred, y_true = model.predict(test[feats]), test["cmg_usd_mwh"].values

    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_true.mean()) ** 2))
    # Residuales del backtest → cuantiles empíricos para la banda de incertidumbre.
    resid = y_true - y_pred
    q10, q90 = np.quantile(resid, 0.10), np.quantile(resid, 0.90)

    # ── Forecast 24h recursivo + banda P10–P90 ───────────────────────────────
    history = list(df["cmg_usd_mwh"].values)
    preds = []
    for h in range(1, 25):
        ndt = df["fecha_hora"].iloc[-1] + pd.Timedelta(hours=h)
        recent = np.array(history)
        row = {"hora_sin": np.sin(2*np.pi*ndt.hour/24), "hora_cos": np.cos(2*np.pi*ndt.hour/24),
               "dia_semana": ndt.dayofweek, "mes": ndt.month,
               "ma_6h": recent[-6:].mean(), "ma_24h": recent[-24:].mean()}
        for l in LAGS:
            row[f"lag_{l}h"] = history[-l] if l <= len(history) else np.nan
        if "dem_lag_24h" in feats:
            row["dem_lag_24h"] = dem_map.get(ndt - pd.Timedelta(hours=24), np.nan)
        p = float(model.predict(pd.DataFrame([row])[feats])[0])
        # La banda se ensancha con el horizonte (incertidumbre acumulada).
        w = np.sqrt(h)
        preds.append({"fecha_hora": ndt, "cmg_pred": p,
                      "lo": max(0, p + q10 * w), "hi": p + q90 * w})
        history.append(p)
    dff = pd.DataFrame(preds)
    pico, valle = dff.loc[dff["cmg_pred"].idxmax()], dff.loc[dff["cmg_pred"].idxmin()]

    # ── Ingreso esperado 24h = CMG previsto × despacho esperado por hora ──────
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
        name="Banda P10–P90", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=ctx["fecha_hora"], y=ctx["cmg_usd_mwh"], name="Histórico (48h)",
        line=dict(color=AES_AZUL, width=2.4, shape="spline", smoothing=0.4),
        fill="tozeroy", fillcolor=hex_to_rgba(AES_AZUL, 0.06)))
    fig.add_trace(go.Scatter(x=dff["fecha_hora"], y=dff["cmg_pred"], name="Forecast 24h",
        mode="lines+markers", line=dict(color=AES_AMBAR, width=2.4, dash="dot"), marker=dict(size=5),
        hovertemplate="%{x|%d/%m %Hh}<br>%{y:.1f} USD/MWh<extra></extra>"))
    fig.add_vline(x=df["fecha_hora"].iloc[-1].timestamp()*1000, line_dash="dash",
        line_color="#94A3B8", line_width=1, annotation_text="ahora", annotation_position="top")
    _base_layout(fig, "Costo marginal — histórico y pronóstico 24h con banda de incertidumbre",
                 "CMG USD/MWh", hovermode="x unified")
    _show(fig)
    dem_txt = (" y demanda neta del SEN (lag 24h)" if "dem_lag_24h" in feats else "")
    st.caption("La línea punteada es el pronóstico puntual; la banda ámbar cubre el rango "
               f"P10–P90 (se ensancha con el horizonte). Modelo XGBoost con lags, "
               f"estacionalidad horaria{dem_txt}.")

    # ── Ingreso esperado por hora (si hay despacho) ──────────────────────────
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
        f2.add_trace(go.Scatter(x=test["fecha_hora"], y=y_true, name="Real",
            line=dict(color=AES_AZUL, width=2)))
        f2.add_trace(go.Scatter(x=test["fecha_hora"], y=y_pred, name="Predicho",
            line=dict(color=AES_AMBAR, width=1.8, dash="dash")))
        _base_layout(f2, f"Validación: real vs predicho · MAE {mae:.1f} · R² {r2:.2f}",
                     "CMG USD/MWh", height=320, hovermode="x unified")
        _show(f2)
    with cB:
        imp = pd.Series(model.feature_importances_, index=feats).sort_values().tail(10)
        f3 = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h", marker_color=AES_CYAN,
            hovertemplate="%{y}<br>%{x:.3f}<extra></extra>"))
        _base_layout(f3, "Variables más influyentes", None, height=320)
        f3.update_layout(showlegend=False, yaxis=dict(tickfont=dict(color="#475569", size=10)))
        _show(f3)


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
                        "ingreso": dff["cmg_pred"].values * disp})
    return float(out["ingreso"].sum()), out


# ══════════════════════════════════════════════════════════════════════════════
# 2 · Anomalías de generación
# ══════════════════════════════════════════════════════════════════════════════
def _seccion_anomalias():
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        st.error("Instala scikit-learn: `pip install scikit-learn`")
        return

    cont = st.slider("Sensibilidad — % esperado de anomalías", 1, 15, 5, 1, key="ml_cont",
                     help="Fracción del historial clasificada como anómala. 5% es un buen punto de partida.")
    with st.spinner("Cargando datos..."):
        df_real, df_prog = _load_gen()
    df = df_real.merge(df_prog, on=["unidad", "fecha_hora"], how="left")
    df = _add_time(df)
    df["desvio_mw"] = df["gen_real_mw"] - df["gen_programada_mw"]
    df["fp"] = df["gen_real_mw"] / df["potencia_maxima"].replace(0, np.nan)
    df = df.sort_values(["unidad", "fecha_hora"])
    df["gen_lag1"] = df.groupby("unidad")["gen_real_mw"].shift(1)
    df["cambio_brusco"] = (df["gen_real_mw"] - df["gen_lag1"]).abs()
    df = df.dropna(subset=["gen_programada_mw", "gen_lag1"])

    unidades = sorted(df["unidad"].unique())
    sel = st.radio("Unidad", unidades, horizontal=True,
                   format_func=lambda u: LABELS.get(u, u), key="ml_anom_u")
    dfu = df[df["unidad"] == sel].copy()
    if len(dfu) < 50:
        st.info(f"Datos insuficientes para {LABELS.get(sel, sel)}.")
        return

    feats = ["gen_real_mw", "gen_programada_mw", "desvio_mw", "fp", "cambio_brusco", "hora_sin", "hora_cos"]
    Xs = StandardScaler().fit_transform(dfu[feats])
    iso = IsolationForest(n_estimators=200, contamination=cont/100, random_state=42)
    dfu["anomalia"] = iso.fit_predict(Xs)
    dfu["score"] = iso.score_samples(Xs)
    # Severidad 0–100: reescala el score (más negativo = más anómalo) a un índice legible.
    smin, smax = dfu["score"].min(), dfu["score"].max()
    dfu["severidad"] = (smax - dfu["score"]) / (smax - smin + 1e-9) * 100
    anomal = dfu[dfu["anomalia"] == -1]
    color = COLORES[sel]["line"]

    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, f"{len(anomal)}", "Horas anómalas detectadas", AES_ROJO)
    _kpi(k2, f"{len(anomal)/len(dfu)*100:.1f}%", "del historial de la unidad", color)
    _kpi(k3, f"{(anomal['desvio_mw'].abs().mean() if len(anomal) else 0):.1f} MW", "desvío medio en anomalías", color)
    _kpi(k4, f"{(anomal['cambio_brusco'].max() if len(anomal) else 0):.1f} MW", "mayor cambio brusco", color)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dfu["fecha_hora"], y=dfu["gen_real_mw"], name="Gen. real",
        line=dict(color=color, width=1.6), opacity=0.85))
    fig.add_trace(go.Scatter(x=dfu["fecha_hora"], y=dfu["gen_programada_mw"], name="Programada",
        line=dict(color=COLORES[sel]["prog"], width=1, dash="dot"), opacity=0.7))
    if len(anomal):
        fig.add_trace(go.Scatter(x=anomal["fecha_hora"], y=anomal["gen_real_mw"],
            name=f"Anomalía ({len(anomal)})", mode="markers",
            marker=dict(color=AES_ROJO, size=8, line=dict(color="#fff", width=1)),
            customdata=anomal["severidad"],
            hovertemplate="%{x|%d/%m %H:%M}<br>%{y:.0f} MW<br>Severidad %{customdata:.0f}/100<extra></extra>"))
    _base_layout(fig, f"{LABELS.get(sel, sel)} — generación real con anomalías marcadas",
                 "MW", hovermode="x unified")
    _show(fig)

    # ── Línea de severidad en el tiempo ──────────────────────────────────────
    fsev = go.Figure(go.Scatter(x=dfu["fecha_hora"], y=dfu["severidad"], mode="lines",
        line=dict(color=color, width=1), fill="tozeroy", fillcolor=hex_to_rgba(color, 0.12),
        hovertemplate="%{x|%d/%m %H:%M}<br>Severidad %{y:.0f}/100<extra></extra>"))
    if len(anomal):
        fsev.add_trace(go.Scatter(x=anomal["fecha_hora"], y=anomal["severidad"], mode="markers",
            marker=dict(color=AES_ROJO, size=6), showlegend=False, hoverinfo="skip"))
    _base_layout(fsev, "Índice de severidad de anomalía en el tiempo (0–100)", "Severidad",
                 height=240)
    fsev.update_layout(showlegend=False)
    _show(fsev)
    st.caption("El índice resume cuán atípica es cada hora según el modelo (generación, "
               "desvío, factor de planta y cambios bruscos). Picos rojos = eventos a revisar.")

    if len(anomal):
        st.markdown("**Las 10 horas más anómalas**")
        top = (anomal.nsmallest(10, "score")
               [["fecha_hora", "gen_real_mw", "gen_programada_mw", "desvio_mw", "cambio_brusco", "severidad"]]
               .rename(columns={"fecha_hora": "Fecha/Hora", "gen_real_mw": "Real (MW)",
                                "gen_programada_mw": "Programada (MW)", "desvio_mw": "Desvío (MW)",
                                "cambio_brusco": "Cambio brusco (MW)", "severidad": "Severidad"})
               .reset_index(drop=True))
        top["Fecha/Hora"] = pd.to_datetime(top["Fecha/Hora"]).dt.strftime("%d/%m %H:%M")
        num_cols = ["Real (MW)", "Programada (MW)", "Desvío (MW)", "Cambio brusco (MW)", "Severidad"]
        top[num_cols] = top[num_cols].round(1)
        st.dataframe(top, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# 3 · Regímenes operacionales (clustering no supervisado)
# ══════════════════════════════════════════════════════════════════════════════
def _seccion_regimenes():
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        st.error("Instala scikit-learn: `pip install scikit-learn`")
        return

    st.caption("Agrupa cada día del histórico por la FORMA de su perfil horario de precio. "
               "Descubre 'tipos de día' recurrentes sin etiquetas previas (KMeans).")
    cc1, cc2 = st.columns([2, 1])
    with cc1:
        nodo = st.selectbox("Nodo CMG", list(NOMBRES_NODO.keys()),
                            format_func=lambda x: NOMBRES_NODO[x], key="ml_reg_nodo")
    with cc2:
        k = st.slider("Número de regímenes", 2, 5, 3, 1, key="ml_reg_k")

    with st.spinner("Agrupando días..."):
        df_raw = _load_cmg()
        d = df_raw[df_raw["barra_transf"] == nodo].copy()
        if d.empty:
            st.warning("Sin datos de CMG para el nodo seleccionado.")
            return
        d["dia"] = d["fecha_hora"].dt.date
        d["h"] = d["fecha_hora"].dt.hour
        piv = d.pivot_table(index="dia", columns="h", values="cmg_usd_mwh", aggfunc="mean")
        piv = piv.reindex(columns=range(24))
        piv = piv[piv.isna().sum(axis=1) <= 4]          # descartar días muy incompletos
        piv = piv.interpolate(axis=1, limit_direction="both")
        if len(piv) < k + 2:
            st.warning("Datos insuficientes: se necesitan más días completos para agrupar.")
            return
        nivel = piv.mean(axis=1)
        # Estandarizar por fila = agrupar por FORMA, no por nivel absoluto de precio.
        forma = piv.sub(piv.mean(axis=1), axis=0).div(piv.std(axis=1).replace(0, 1), axis=0)
        Xs = StandardScaler().fit_transform(forma.values)
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        lab = km.fit_predict(Xs)

    piv = piv.assign(cluster=lab, nivel=nivel.values)
    # Ordenar clusters por nivel medio (0 = más barato) para lectura estable.
    orden = piv.groupby("cluster")["nivel"].mean().sort_values().index.tolist()
    remap = {c: i for i, c in enumerate(orden)}
    piv["cluster"] = piv["cluster"].map(remap)

    # ── KPIs por régimen ─────────────────────────────────────────────────────
    resumen = piv.groupby("cluster").agg(dias=("nivel", "size"),
                                         nivel=("nivel", "mean")).reset_index()
    cols = st.columns(len(resumen))
    etiquetas = _nombrar_regimenes(piv, k)
    for i, (col, row) in enumerate(zip(cols, resumen.itertuples())):
        _kpi(col, f"{int(row.dias)} días",
             f"{etiquetas[i]} · CMG medio {row.nivel:.0f}", CLUSTER_COLORS[i])
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Perfil horario medio de cada régimen ─────────────────────────────────
    horas = list(range(24))
    fig = go.Figure()
    for i in range(k):
        perfil = piv[piv["cluster"] == i][horas].mean()
        fig.add_trace(go.Scatter(x=horas, y=perfil.values, mode="lines",
            name=f"{etiquetas[i]}", line=dict(color=CLUSTER_COLORS[i], width=2.6, shape="spline"),
            hovertemplate=f"<b>{etiquetas[i]}</b><br>%{{x}}:00 h<br>%{{y:.1f}} USD/MWh<extra></extra>"))
    _base_layout(fig, "Perfil horario medio de cada régimen de precio (USD/MWh)", "CMG USD/MWh")
    fig.update_xaxes(dtick=3, title="Hora del día", title_font=dict(color=INK_AXIS, size=10))
    _show(fig)
    st.caption("Cada curva es el 'día típico' de un régimen. La forma (no el nivel) define el "
               "grupo: valles nocturnos, picos vespertinos o mesetas planas se separan solos.")

    # ── Calendario: qué régimen cayó cada día ────────────────────────────────
    cal = piv.reset_index()[["dia", "cluster", "nivel"]].sort_values("dia")
    fig2 = go.Figure()
    for i in range(k):
        sub = cal[cal["cluster"] == i]
        fig2.add_trace(go.Bar(x=sub["dia"].astype(str), y=[1]*len(sub), name=etiquetas[i],
            marker_color=CLUSTER_COLORS[i], customdata=sub["nivel"],
            hovertemplate=f"<b>{etiquetas[i]}</b><br>%{{x}}<br>CMG medio %{{customdata:.0f}}<extra></extra>"))
    _base_layout(fig2, "Régimen asignado a cada día del histórico", None, height=200,
                 barmode="stack")
    fig2.update_yaxes(showticklabels=False, showgrid=False, range=[0, 1])
    fig2.update_xaxes(tickfont=dict(color=INK_AXIS, size=8))
    _show(fig2)
    st.caption("Secuencia temporal de regímenes: revela rachas (p. ej. varios días caros "
               "seguidos) y transiciones del sistema.")


def _nombrar_regimenes(piv, k):
    """Etiqueta descriptiva por régimen según nivel y forma del perfil horario."""
    horas = list(range(24))
    niveles = piv.groupby("cluster")["nivel"].mean()
    nombres = {}
    for i in range(k):
        perfil = piv[piv["cluster"] == i][horas].mean()
        rango = perfil.max() - perfil.min()
        hora_pico = int(perfil.idxmax())
        nivel = niveles[i]
        nivel_txt = "barato" if nivel <= niveles.quantile(0.34) else \
                    ("caro" if nivel >= niveles.quantile(0.66) else "medio")
        if rango < perfil.mean() * 0.25:
            forma_txt = "plano"
        elif 17 <= hora_pico <= 23:
            forma_txt = "pico vespertino"
        elif 0 <= hora_pico <= 7:
            forma_txt = "pico nocturno"
        else:
            forma_txt = "pico diurno"
        nombres[i] = f"Régimen {i+1} · {nivel_txt}/{forma_txt}"
    return nombres
