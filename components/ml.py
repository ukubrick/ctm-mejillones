"""
components/ml.py — Análisis predictivo (Machine Learning) del CTM.

Reformulado para aportar valor operacional directo:
  · Forecast CMG 24h (XGBoost) con banda de contexto y lectura de próximo pico/valle.
  · Detección de anomalías en generación real (Isolation Forest) por unidad.

Se renderiza como sub-sección de la vista «Análisis» (no fija su propio
page_config), y también desde la página pages/ml_analysis.py.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (COLORES, LABELS, AES_AZUL, AES_AMBAR, AES_CYAN, AES_VIOLETA,
                    NOMBRES_NODO, BG_TRANSP, C_GRID)
from utils.db import fetch, rest_enabled
from utils.plotly_theme import hex_to_rgba


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
        f'<div style="font-size:1.5rem;font-weight:800;color:#1A1F36">{val}</div>'
        f'<div style="font-size:0.74rem;color:#6B7280;margin-top:2px">{lbl}</div></div>',
        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
def render_ml():
    st.markdown('<div class="sec">Análisis predictivo · modelos ML</div>', unsafe_allow_html=True)
    st.caption("Modelos entrenados sobre el histórico de Supabase (se recargan cada hora). "
               "El forecast de CMG anticipa el precio; la detección de anomalías vigila la operación.")
    sub = st.radio("Modelo", ["Forecast CMG", "Anomalías de generación"],
                   horizontal=True, label_visibility="collapsed", key="ml_sub")
    if sub == "Forecast CMG":
        _seccion_cmg()
    else:
        _seccion_anomalias()


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
        idx = pd.date_range(df.index.min(), df.index.max(), freq="h")
        df = df.reindex(idx).ffill(limit=3).dropna().reset_index().rename(columns={"index": "fecha_hora"})

        LAGS = [1, 2, 3, 6, 12, 24, 48]
        df = _add_time(df)
        for l in LAGS:
            df[f"lag_{l}h"] = df["cmg_usd_mwh"].shift(l)
        df = df.dropna()
        feats = ["hora_sin", "hora_cos", "dia_semana", "mes"] + [f"lag_{l}h" for l in LAGS]

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

    # ── Forecast 24h recursivo ───────────────────────────────────────────────
    history = list(df["cmg_usd_mwh"].values)
    preds = []
    for h in range(1, 25):
        ndt = df["fecha_hora"].iloc[-1] + pd.Timedelta(hours=h)
        row = {"hora_sin": np.sin(2*np.pi*ndt.hour/24), "hora_cos": np.cos(2*np.pi*ndt.hour/24),
               "dia_semana": ndt.dayofweek, "mes": ndt.month}
        for l in LAGS:
            row[f"lag_{l}h"] = history[-l] if l <= len(history) else np.nan
        p = float(model.predict(pd.DataFrame([row])[feats])[0])
        preds.append({"fecha_hora": ndt, "cmg_pred": p})
        history.append(p)
    dff = pd.DataFrame(preds)
    pico, valle = dff.loc[dff["cmg_pred"].idxmax()], dff.loc[dff["cmg_pred"].idxmin()]

    c1, c2, c3, c4 = st.columns(4)
    _kpi(c1, f"{dff['cmg_pred'].mean():.1f}", "CMG medio previsto 24h (USD/MWh)", AES_VIOLETA)
    _kpi(c2, f"{pico['cmg_pred']:.0f}", f"Pico previsto · {pico['fecha_hora'].strftime('%d/%m %Hh')}", AES_AMBAR)
    _kpi(c3, f"{valle['cmg_pred']:.0f}", f"Valle previsto · {valle['fecha_hora'].strftime('%d/%m %Hh')}", AES_CYAN)
    _kpi(c4, f"±{mae:.1f}", f"Error medio del modelo (RMSE {rmse:.1f} · R² {r2:.2f})", AES_AZUL)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Gráfico: histórico 48h + forecast 24h ────────────────────────────────
    ctx = df.tail(48)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ctx["fecha_hora"], y=ctx["cmg_usd_mwh"], name="Histórico (48h)",
        line=dict(color=AES_AZUL, width=2.4, shape="spline", smoothing=0.4),
        fill="tozeroy", fillcolor=hex_to_rgba(AES_AZUL, 0.06)))
    fig.add_trace(go.Scatter(x=dff["fecha_hora"], y=dff["cmg_pred"], name="Forecast 24h",
        mode="lines+markers", line=dict(color=AES_AMBAR, width=2.4, dash="dot"), marker=dict(size=5)))
    fig.add_vline(x=df["fecha_hora"].iloc[-1].timestamp()*1000, line_dash="dash",
        line_color="#94A3B8", line_width=1, annotation_text="ahora", annotation_position="top")
    fig.update_layout(template="plotly_white", plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
        title=dict(text="Costo marginal — histórico y pronóstico 24h", font=dict(size=13, color="#1A1F36"), x=0),
        height=380, margin=dict(l=10, r=10, t=55, b=10),
        yaxis=dict(title="CMG USD/MWh", gridcolor=C_GRID, tickfont=dict(color="#94A3B8", size=10)),
        xaxis=dict(showgrid=False, tickfont=dict(color="#94A3B8", size=10)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Real vs predicho (test) + importancia ────────────────────────────────
    cA, cB = st.columns([3, 2])
    with cA:
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=test["fecha_hora"], y=y_true, name="Real",
            line=dict(color=AES_AZUL, width=2)))
        f2.add_trace(go.Scatter(x=test["fecha_hora"], y=y_pred, name="Predicho",
            line=dict(color=AES_AMBAR, width=1.8, dash="dash")))
        f2.update_layout(template="plotly_white", plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
            title=dict(text="Validación: real vs predicho (últimas 2 semanas)", font=dict(size=12, color="#1A1F36"), x=0),
            height=320, margin=dict(l=10, r=10, t=50, b=10),
            yaxis=dict(gridcolor=C_GRID, tickfont=dict(color="#94A3B8", size=10)),
            xaxis=dict(showgrid=False, tickfont=dict(color="#94A3B8", size=10)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), hovermode="x unified")
        st.plotly_chart(f2, use_container_width=True, config={"displayModeBar": False})
    with cB:
        imp = pd.Series(model.feature_importances_, index=feats).sort_values()
        f3 = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h", marker_color=AES_CYAN))
        f3.update_layout(template="plotly_white", plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
            title=dict(text="Variables más influyentes", font=dict(size=12, color="#1A1F36"), x=0),
            height=320, margin=dict(l=10, r=10, t=50, b=10),
            xaxis=dict(showgrid=False, tickfont=dict(color="#94A3B8", size=9)),
            yaxis=dict(tickfont=dict(color="#475569", size=10)))
        st.plotly_chart(f3, use_container_width=True, config={"displayModeBar": False})


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
    anomal = dfu[dfu["anomalia"] == -1]
    color = COLORES[sel]["line"]

    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, f"{len(anomal)}", "Horas anómalas detectadas", "#EF4444")
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
            marker=dict(color="#EF4444", size=8, line=dict(color="#fff", width=1))))
    fig.update_layout(template="plotly_white", plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
        title=dict(text=f"{LABELS.get(sel, sel)} — generación real con anomalías marcadas",
                   font=dict(size=13, color="#1A1F36"), x=0),
        height=380, margin=dict(l=10, r=10, t=55, b=10),
        yaxis=dict(title="MW", gridcolor=C_GRID, tickfont=dict(color="#94A3B8", size=10)),
        xaxis=dict(showgrid=False, tickfont=dict(color="#94A3B8", size=10)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if len(anomal):
        st.markdown("**Las 10 horas más anómalas**")
        top = (anomal.nsmallest(10, "score")
               [["fecha_hora", "gen_real_mw", "gen_programada_mw", "desvio_mw", "cambio_brusco", "score"]]
               .rename(columns={"fecha_hora": "Fecha/Hora", "gen_real_mw": "Real (MW)",
                                "gen_programada_mw": "Programada (MW)", "desvio_mw": "Desvío (MW)",
                                "cambio_brusco": "Cambio brusco (MW)", "score": "Score"})
               .reset_index(drop=True))
        top["Fecha/Hora"] = pd.to_datetime(top["Fecha/Hora"]).dt.strftime("%d/%m %H:%M")
        num_cols = ["Real (MW)", "Programada (MW)", "Desvío (MW)", "Cambio brusco (MW)", "Score"]
        top[num_cols] = top[num_cols].round(2)
        st.dataframe(top, use_container_width=True, hide_index=True)
