"""
pages/ml_analysis.py — Análisis ML · Dashboard CTM Mejillones

Modelos:
  1. Forecasting CMG — XGBoost con lags temporales
  2. Detección de anomalías en generación real — Isolation Forest
"""

import streamlit as st
import pandas as pd
import numpy as np
import psycopg2
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

from config import get_css, COLORES, LABELS, PMAX

st.set_page_config(
    page_title="ML · CTM Mejillones",
    layout="wide",
    page_icon=None,
    initial_sidebar_state="expanded",
)

# Diseño AES compartido (mismo sidebar, tabs, tipografía y KPIs que la app principal)
st.markdown(get_css(), unsafe_allow_html=True)

# Clases propias de esta página (no incluidas en el CSS global)
st.markdown("""
<style>
.sec-title {
    font-size: 0.82rem; font-weight: 800; color: #334155;
    border-bottom: 2px solid #4DC8DC; padding-bottom: 4px;
    margin: 1.5rem 0 1rem; text-transform: uppercase; letter-spacing: .05em;
}
.kpi-card {
    background: #fff; border-radius: 12px; padding: 16px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 3px solid #4DC8DC;
}
.kpi-val { font-size: 1.5rem; font-weight: 800; color: #1A1F36; }
.kpi-lbl { font-size: 0.75rem; color: #6B7280; margin-top: 2px; }
.info-box {
    background: #F0F9FF; border-left: 4px solid #4DC8DC;
    border-radius: 8px; padding: 12px 16px; margin: 8px 0;
    font-size: 0.82rem; color: #1e293b;
}
</style>
""", unsafe_allow_html=True)

# ── Conexión DB ────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_conn():
    return psycopg2.connect(st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL", "")))


@st.cache_data(ttl=3600, show_spinner=False)
def load_cmg() -> pd.DataFrame:
    sql = """
        SELECT fecha_hora, barra_transf, cmg_usd_mwh
        FROM costo_marginal
        WHERE barra_transf IN ('CRUCERO_______220','TARAPACA______220')
        ORDER BY fecha_hora
    """
    df = pd.read_sql(sql, get_conn())
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def load_gen() -> tuple[pd.DataFrame, pd.DataFrame]:
    df_real = pd.read_sql("""
        SELECT unidad, fecha_hora, gen_real_mw, potencia_maxima
        FROM generacion_real ORDER BY fecha_hora
    """, get_conn())
    df_prog = pd.read_sql("""
        SELECT DISTINCT ON (unidad, fecha_hora)
            unidad, fecha_hora, gen_programada_mw
        FROM generacion_programada
        ORDER BY unidad, fecha_hora,
            CASE fuente WHEN 'CEN_PCP' THEN 0 ELSE 1 END
    """, get_conn())
    df_real["fecha_hora"] = pd.to_datetime(df_real["fecha_hora"])
    df_prog["fecha_hora"] = pd.to_datetime(df_prog["fecha_hora"])
    return df_real, df_prog


# ── Helpers ────────────────────────────────────────────────────────────────────

def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hora"]       = df["fecha_hora"].dt.hour
    df["dia_semana"] = df["fecha_hora"].dt.dayofweek
    df["mes"]        = df["fecha_hora"].dt.month
    df["hora_sin"]   = np.sin(2 * np.pi * df["hora"] / 24)
    df["hora_cos"]   = np.cos(2 * np.pi * df["hora"] / 24)
    return df


def add_lags(df: pd.DataFrame, col: str, lags: list) -> pd.DataFrame:
    df = df.copy()
    for lag in lags:
        df[f"lag_{lag}h"] = df[col].shift(lag)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# MODELO 1 — Forecasting CMG
# ══════════════════════════════════════════════════════════════════════════════

def seccion_cmg():
    try:
        from xgboost import XGBRegressor
        from sklearn.metrics import mean_absolute_error, mean_squared_error
    except ImportError:
        st.error("Instala xgboost y scikit-learn: `pip install xgboost scikit-learn`")
        return

    st.markdown('<div class="sec-title">Modelo 1 — Forecasting CMG (XGBoost)</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Predice el costo marginal de las próximas horas usando patrones horarios históricos y lags temporales (t-1h, t-2h, t-3h, t-6h, t-12h, t-24h, t-48h). El modelo se entrena con todos los datos disponibles y evalúa en las últimas 2 semanas.</div>', unsafe_allow_html=True)

    nodo_sel = st.selectbox(
        "Nodo CMG",
        ["CRUCERO_______220", "TARAPACA______220"],
        format_func=lambda x: {"CRUCERO_______220": "Crucero 220kV", "TARAPACA______220": "Tarapacá 220kV"}[x],
        key="cmg_nodo",
    )

    with st.spinner("Cargando datos CMG..."):
        df_raw = load_cmg()

    df = (df_raw[df_raw["barra_transf"] == nodo_sel]
          .set_index("fecha_hora").sort_index()[["cmg_usd_mwh"]].copy())

    # Rellenar huecos y limpiar
    idx_full = pd.date_range(df.index.min(), df.index.max(), freq="h")
    df = df.reindex(idx_full).ffill(limit=3).dropna().reset_index()
    df = df.rename(columns={"index": "fecha_hora"})

    LAGS = [1, 2, 3, 6, 12, 24, 48]
    df = add_time_features(df)
    df = add_lags(df, "cmg_usd_mwh", LAGS)
    df = df.dropna()

    feature_cols = (
        ["hora_sin", "hora_cos", "dia_semana", "mes"]
        + [f"lag_{l}h" for l in LAGS]
    )

    cutoff = df["fecha_hora"].max() - pd.Timedelta(days=14)
    train = df[df["fecha_hora"] <= cutoff]
    test  = df[df["fecha_hora"] >  cutoff]

    if len(train) < 100 or len(test) < 10:
        st.warning("Datos insuficientes para entrenar el modelo. Se necesitan al menos 2 semanas de histórico.")
        return

    with st.spinner("Entrenando modelo XGBoost..."):
        model = XGBRegressor(
            n_estimators=400, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbosity=0,
        )
        model.fit(train[feature_cols], train["cmg_usd_mwh"])

    y_pred = model.predict(test[feature_cols])
    y_true = test["cmg_usd_mwh"].values

    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = float(np.mean(np.abs((y_true - y_pred) / (np.abs(y_true) + 1e-6))) * 100)
    r2   = float(1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_true.mean()) ** 2))

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-val">{mae:.2f}</div><div class="kpi-lbl">MAE (USD/MWh)</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi-card"><div class="kpi-val">{rmse:.2f}</div><div class="kpi-lbl">RMSE (USD/MWh)</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="kpi-card"><div class="kpi-val">{mape:.1f}%</div><div class="kpi-lbl">MAPE</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="kpi-card"><div class="kpi-val">{r2:.3f}</div><div class="kpi-lbl">R² (período test)</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Gráfico real vs predicho ──────────────────────────────────────────────
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=test["fecha_hora"], y=y_true,
        name="Real", line=dict(color="#4DC8DC", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=test["fecha_hora"], y=y_pred,
        name="Predicho", line=dict(color="#f97316", width=1.8, dash="dash"),
    ))
    fig.update_layout(
        template="plotly_white", plot_bgcolor="#F5F7FA",
        title=dict(text="CMG real vs predicho — últimas 2 semanas (test set)", font=dict(size=13, color="#1A1F36")),
        xaxis_title="Fecha", yaxis_title="CMG (USD/MWh)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=380, margin=dict(l=0, r=0, t=60, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Importancia de features ───────────────────────────────────────────────
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=True)
    fig2 = go.Figure(go.Bar(
        x=importances.values, y=importances.index,
        orientation="h", marker_color="#4DC8DC",
    ))
    fig2.update_layout(
        template="plotly_white", plot_bgcolor="#F5F7FA",
        title=dict(text="Importancia de features (gain)", font=dict(size=12, color="#1A1F36")),
        height=320, margin=dict(l=0, r=0, t=50, b=0),
        xaxis_title="Importancia",
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── Forecast próximas 24h ────────────────────────────────────────────────
    st.markdown("**Forecast próximas 24 horas**")
    last_row = df.iloc[-1].copy()
    preds_24h = []
    history = list(df["cmg_usd_mwh"].values)

    for h in range(1, 25):
        next_dt = df["fecha_hora"].iloc[-1] + pd.Timedelta(hours=h)
        row = {
            "hora_sin":   np.sin(2 * np.pi * next_dt.hour / 24),
            "hora_cos":   np.cos(2 * np.pi * next_dt.hour / 24),
            "dia_semana": next_dt.dayofweek,
            "mes":        next_dt.month,
        }
        for lag in LAGS:
            idx = -(lag)
            row[f"lag_{lag}h"] = history[idx] if abs(idx) <= len(history) else np.nan
        X_next = pd.DataFrame([row])[feature_cols]
        pred = float(model.predict(X_next)[0])
        preds_24h.append({"fecha_hora": next_dt, "cmg_pred": pred})
        history.append(pred)

    df_forecast = pd.DataFrame(preds_24h)

    fig3 = go.Figure()
    # Últimas 48h reales como contexto
    df_ctx = df.tail(48)
    fig3.add_trace(go.Scatter(
        x=df_ctx["fecha_hora"], y=df_ctx["cmg_usd_mwh"],
        name="Histórico (48h)", line=dict(color="#4DC8DC", width=2),
    ))
    fig3.add_trace(go.Scatter(
        x=df_forecast["fecha_hora"], y=df_forecast["cmg_pred"],
        name="Forecast 24h", line=dict(color="#f97316", width=2, dash="dot"),
        mode="lines+markers", marker=dict(size=5),
    ))
    fig3.add_vline(
        x=df["fecha_hora"].iloc[-1].timestamp() * 1000,
        line_dash="dash", line_color="#94a3b8", line_width=1,
        annotation_text="Ahora", annotation_position="top left",
    )
    fig3.update_layout(
        template="plotly_white", plot_bgcolor="#F5F7FA",
        title=dict(text="Forecast CMG próximas 24h", font=dict(size=13, color="#1A1F36")),
        xaxis_title="Fecha/Hora", yaxis_title="CMG (USD/MWh)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=350, margin=dict(l=0, r=0, t=60, b=0),
    )
    st.plotly_chart(fig3, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# MODELO 2 — Detección de anomalías
# ══════════════════════════════════════════════════════════════════════════════

def seccion_anomalias():
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        st.error("Instala scikit-learn: `pip install scikit-learn`")
        return

    st.markdown('<div class="sec-title">Modelo 2 — Detección de anomalías en generación real (Isolation Forest)</div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">Identifica horas con comportamiento inusual comparando gen. real vs programada, cambios bruscos entre horas consecutivas, y patrones por hora del día. Los puntos rojos indican outliers — posibles fallas, limitaciones no registradas, o datos erróneos.</div>', unsafe_allow_html=True)

    contaminacion = st.slider(
        "Porcentaje esperado de anomalías (%)",
        min_value=1, max_value=15, value=5, step=1,
        help="Qué fracción del historial se clasifica como anómala. 5% es un buen punto de partida.",
        key="iso_contaminacion",
    )

    with st.spinner("Cargando datos de generación..."):
        df_real, df_prog = load_gen()

    df = df_real.merge(df_prog, on=["unidad", "fecha_hora"], how="left")
    df = add_time_features(df)
    df["desvio_mw"]  = df["gen_real_mw"] - df["gen_programada_mw"]
    df["fp"]         = df["gen_real_mw"] / df["potencia_maxima"].replace(0, np.nan)
    df = df.sort_values(["unidad", "fecha_hora"])
    df["gen_lag1"]      = df.groupby("unidad")["gen_real_mw"].shift(1)
    df["cambio_brusco"] = (df["gen_real_mw"] - df["gen_lag1"]).abs()
    df = df.dropna(subset=["gen_programada_mw", "gen_lag1"])

    unidades = sorted(df["unidad"].unique())
    tabs = st.tabs([LABELS.get(u, u) for u in unidades])

    for i, unidad in enumerate(unidades):
        with tabs[i]:
            dfu = df[df["unidad"] == unidad].copy()
            if len(dfu) < 50:
                st.info(f"Datos insuficientes para {unidad}.")
                continue

            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler

            features = ["gen_real_mw", "gen_programada_mw", "desvio_mw",
                        "fp", "cambio_brusco", "hora_sin", "hora_cos"]
            X = dfu[features].copy()
            X_scaled = StandardScaler().fit_transform(X)

            iso = IsolationForest(
                n_estimators=200,
                contamination=contaminacion / 100,
                random_state=42,
            )
            dfu["anomalia"]      = iso.fit_predict(X_scaled)
            dfu["score"]         = iso.score_samples(X_scaled)

            normal = dfu[dfu["anomalia"] == 1]
            anomal = dfu[dfu["anomalia"] == -1]
            color  = COLORES[unidad]["line"]

            # KPIs
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.markdown(f'<div class="kpi-card"><div class="kpi-val">{len(anomal)}</div><div class="kpi-lbl">Horas anómalas detectadas</div></div>', unsafe_allow_html=True)
            with k2:
                st.markdown(f'<div class="kpi-card"><div class="kpi-val">{len(anomal)/len(dfu)*100:.1f}%</div><div class="kpi-lbl">% del historial</div></div>', unsafe_allow_html=True)
            with k3:
                avg_dev = anomal["desvio_mw"].abs().mean() if len(anomal) else 0
                st.markdown(f'<div class="kpi-card"><div class="kpi-val">{avg_dev:.1f} MW</div><div class="kpi-lbl">Desvío medio en anomalías</div></div>', unsafe_allow_html=True)
            with k4:
                max_brsc = anomal["cambio_brusco"].max() if len(anomal) else 0
                st.markdown(f'<div class="kpi-card"><div class="kpi-val">{max_brsc:.1f} MW</div><div class="kpi-lbl">Mayor cambio brusco detectado</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Gráfico serie + anomalías ─────────────────────────────────────
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dfu["fecha_hora"], y=dfu["gen_real_mw"],
                name="Gen. real", line=dict(color=color, width=1.5), opacity=0.8,
            ))
            fig.add_trace(go.Scatter(
                x=dfu["fecha_hora"], y=dfu["gen_programada_mw"],
                name="Gen. programada", line=dict(color=COLORES[unidad]["prog"], width=1, dash="dot"),
                opacity=0.7,
            ))
            if len(anomal):
                fig.add_trace(go.Scatter(
                    x=anomal["fecha_hora"], y=anomal["gen_real_mw"],
                    name=f"Anomalía ({len(anomal)})",
                    mode="markers",
                    marker=dict(color="#ef4444", size=8, symbol="circle",
                                line=dict(color="#fff", width=1)),
                ))
            fig.update_layout(
                template="plotly_white", plot_bgcolor="#F5F7FA",
                title=dict(text=f"{LABELS.get(unidad, unidad)} — Generación real con anomalías marcadas", font=dict(size=13, color="#1A1F36")),
                xaxis_title="Fecha/Hora", yaxis_title="MW",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=380, margin=dict(l=0, r=0, t=60, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

            # ── Gráfico desvío ────────────────────────────────────────────────
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=normal["fecha_hora"], y=normal["desvio_mw"],
                name="Desvío normal", marker_color=color, opacity=0.5,
            ))
            if len(anomal):
                fig2.add_trace(go.Bar(
                    x=anomal["fecha_hora"], y=anomal["desvio_mw"],
                    name="Desvío anómalo", marker_color="#ef4444", opacity=0.9,
                ))
            fig2.add_hline(y=0, line_color="#94a3b8", line_width=1)
            fig2.update_layout(
                template="plotly_white", plot_bgcolor="#F5F7FA",
                title=dict(text="Desvío real vs programada (MW)", font=dict(size=12, color="#1A1F36")),
                barmode="overlay", height=280,
                xaxis_title="Fecha/Hora", yaxis_title="Desvío (MW)",
                margin=dict(l=0, r=0, t=50, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig2, use_container_width=True)

            # ── Tabla top anomalías ───────────────────────────────────────────
            if len(anomal):
                st.markdown("**Las 10 horas más anómalas**")
                top = (anomal.nsmallest(10, "score")
                       [["fecha_hora", "gen_real_mw", "gen_programada_mw",
                         "desvio_mw", "cambio_brusco", "score"]]
                       .rename(columns={
                           "fecha_hora": "Fecha/Hora",
                           "gen_real_mw": "Real (MW)",
                           "gen_programada_mw": "Programada (MW)",
                           "desvio_mw": "Desvío (MW)",
                           "cambio_brusco": "Cambio brusco (MW)",
                           "score": "Score anomalía",
                       })
                       .reset_index(drop=True))
                top["Score anomalía"] = top["Score anomalía"].round(4)
                top["Real (MW)"]      = top["Real (MW)"].round(1)
                top["Programada (MW)"] = top["Programada (MW)"].round(1)
                top["Desvío (MW)"]    = top["Desvío (MW)"].round(1)
                top["Cambio brusco (MW)"] = top["Cambio brusco (MW)"].round(1)
                st.dataframe(top, use_container_width=True, hide_index=True)


# ── Layout principal ───────────────────────────────────────────────────────────

with st.sidebar:
    st.page_link("app.py",               label="Aplicación")
    st.page_link("pages/ml_analysis.py", label="Machine Learning Analysis")

st.title("Análisis ML — CTM Mejillones")
st.caption("Modelos entrenados con datos históricos de Supabase · Se recargan cada hora")

tab1, tab2 = st.tabs(["Forecasting CMG", "Detección de anomalías"])

with tab1:
    seccion_cmg()

with tab2:
    seccion_anomalias()
