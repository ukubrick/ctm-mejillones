"""
ml_pruebas.py — Pruebas de ML sobre datos CTM Mejillones
  1. Forecasting CMG a corto plazo (XGBoost + lags)
  2. Detección de anomalías en generación real (Isolation Forest)

Modos de carga de datos:
  - CSV (por defecto): coloca los archivos exportados en data/
      data/cmg.csv          → columnas: fecha_hora, barra_transf, cmg_usd_mwh
      data/gen_real.csv     → columnas: unidad, fecha_hora, gen_real_mw, potencia_maxima
      data/gen_prog.csv     → columnas: unidad, fecha_hora, gen_programada_mw
  - DB: descomenta USE_DB = True (requiere conexión directa a Supabase)
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from sklearn.ensemble import IsolationForest
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

warnings.filterwarnings("ignore")

USE_DB   = False   # Cambia a True si tienes conexión directa a Supabase
DATA_DIR = "data"  # Carpeta donde se ubican los CSVs exportados

# ── Conexión DB (opcional) ─────────────────────────────────────────────────────

def get_conn():
    from dotenv import load_dotenv
    import psycopg2
    load_dotenv()
    return psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=30)


def load_cmg() -> pd.DataFrame:
    if USE_DB:
        import psycopg2
        with get_conn() as conn:
            df = pd.read_sql("""
                SELECT fecha_hora, barra_transf, cmg_usd_mwh
                FROM costo_marginal
                WHERE barra_transf IN ('CRUCERO_______220', 'TARAPACA______220')
                ORDER BY fecha_hora
            """, conn)
    else:
        path = os.path.join(DATA_DIR, "cmg.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No se encontró {path}. Exporta los datos primero (ver instrucciones arriba).")
        df = pd.read_csv(path)
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df


def load_gen_real() -> pd.DataFrame:
    if USE_DB:
        with get_conn() as conn:
            df = pd.read_sql("""
                SELECT unidad, fecha_hora, gen_real_mw, potencia_maxima
                FROM generacion_real
                ORDER BY fecha_hora
            """, conn)
    else:
        path = os.path.join(DATA_DIR, "gen_real.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No se encontró {path}.")
        df = pd.read_csv(path)
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df


def load_gen_prog() -> pd.DataFrame:
    if USE_DB:
        with get_conn() as conn:
            df = pd.read_sql("""
                SELECT DISTINCT ON (unidad, fecha_hora)
                    unidad, fecha_hora, gen_programada_mw
                FROM generacion_programada
                ORDER BY unidad, fecha_hora, CASE fuente WHEN 'CEN_PCP' THEN 0 ELSE 1 END
            """, conn)
    else:
        path = os.path.join(DATA_DIR, "gen_prog.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No se encontró {path}.")
        df = pd.read_csv(path)
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    return df


# ── Utilidades ─────────────────────────────────────────────────────────────────

def add_time_features(df: pd.DataFrame, col: str = "fecha_hora") -> pd.DataFrame:
    df = df.copy()
    df["hora"]       = df[col].dt.hour
    df["dia_semana"] = df[col].dt.dayofweek
    df["mes"]        = df[col].dt.month
    df["hora_sin"]   = np.sin(2 * np.pi * df["hora"] / 24)
    df["hora_cos"]   = np.cos(2 * np.pi * df["hora"] / 24)
    return df


def add_lags(df: pd.DataFrame, col: str, lags: list[int]) -> pd.DataFrame:
    df = df.copy()
    for lag in lags:
        df[f"{col}_lag{lag}"] = df[col].shift(lag)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# MODELO 1 — Forecasting de CMG (XGBoost)
# ══════════════════════════════════════════════════════════════════════════════

def modelo_cmg_forecast():
    print("\n" + "═" * 60)
    print("MODELO 1 — Forecasting CMG (XGBoost)")
    print("═" * 60)

    df_raw = load_cmg()
    print(f"  Registros totales CMG: {len(df_raw):,}")
    print(f"  Barras: {df_raw['barra_transf'].unique().tolist()}")
    print(f"  Rango: {df_raw['fecha_hora'].min()} → {df_raw['fecha_hora'].max()}")

    # Trabajar con Crucero 220 (más representativo de la zona norte)
    nodo = "CRUCERO_______220"
    df = (df_raw[df_raw["barra_transf"] == nodo]
          .set_index("fecha_hora")
          .sort_index()
          [["cmg_usd_mwh"]]
          .copy())

    # Rellenar huecos horarios y hacer forward fill (máx 3 horas)
    idx_full = pd.date_range(df.index.min(), df.index.max(), freq="h")
    df = df.reindex(idx_full)
    df["cmg_usd_mwh"] = df["cmg_usd_mwh"].ffill(limit=3)
    df = df.dropna()
    df = df.reset_index().rename(columns={"index": "fecha_hora"})

    print(f"  Registros tras limpieza: {len(df):,}")

    # Features
    LAGS = [1, 2, 3, 6, 12, 24, 48]
    df = add_time_features(df)
    df = add_lags(df, "cmg_usd_mwh", LAGS)
    df = df.dropna()

    feature_cols = (["hora_sin", "hora_cos", "dia_semana", "mes"]
                    + [f"cmg_usd_mwh_lag{l}" for l in LAGS])

    # Split temporal: últimas 2 semanas como test
    cutoff = df["fecha_hora"].max() - pd.Timedelta(days=14)
    train = df[df["fecha_hora"] <= cutoff]
    test  = df[df["fecha_hora"] >  cutoff]

    X_train, y_train = train[feature_cols], train["cmg_usd_mwh"]
    X_test,  y_test  = test[feature_cols],  test["cmg_usd_mwh"]

    print(f"  Train: {len(train):,} registros | Test: {len(test):,} registros")

    model = xgb.XGBRegressor(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae  = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mape = np.mean(np.abs((y_test - y_pred) / (y_test + 1e-6))) * 100

    print(f"\n  Métricas en test (últimas 2 semanas):")
    print(f"    MAE  = {mae:.2f}  USD/MWh")
    print(f"    RMSE = {rmse:.2f} USD/MWh")
    print(f"    MAPE = {mape:.1f}%")

    # Importancia de features
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print(f"\n  Top 5 features más importantes:")
    for feat, imp in importances.head(5).items():
        print(f"    {feat:<30} {imp:.4f}")

    # ── Gráfico ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), facecolor="#F5F7FA")
    fig.suptitle("Modelo 1 — Forecasting CMG Crucero 220kV (XGBoost)", fontsize=13, fontweight="bold", color="#1e293b")

    # Panel superior: real vs predicho
    ax1 = axes[0]
    ax1.set_facecolor("#ffffff")
    ax1.plot(test["fecha_hora"], y_test.values,  color="#4DC8DC", lw=1.8, label="Real", alpha=0.9)
    ax1.plot(test["fecha_hora"], y_pred,          color="#f97316", lw=1.5, label="Predicho", alpha=0.85, linestyle="--")
    ax1.set_ylabel("CMG (USD/MWh)", fontsize=9)
    ax1.legend(fontsize=9)
    ax1.set_title(f"Real vs Predicho — últimas 2 semanas  |  MAE={mae:.1f}  RMSE={rmse:.1f}  MAPE={mape:.0f}%", fontsize=9, color="#475569")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
    ax1.grid(axis="y", alpha=0.3)

    # Panel inferior: importancia de features
    ax2 = axes[1]
    ax2.set_facecolor("#ffffff")
    top10 = importances.head(10)
    bars = ax2.barh(top10.index[::-1], top10.values[::-1], color="#4DC8DC", alpha=0.85)
    ax2.set_xlabel("Importancia (gain)", fontsize=9)
    ax2.set_title("Importancia de features", fontsize=9, color="#475569")
    ax2.grid(axis="x", alpha=0.3)

    plt.tight_layout()
    plt.savefig("ml_cmg_forecast.png", dpi=150, bbox_inches="tight")
    print("\n  Gráfico guardado: ml_cmg_forecast.png")

    return model, df, feature_cols


# ══════════════════════════════════════════════════════════════════════════════
# MODELO 2 — Detección de anomalías en generación real (Isolation Forest)
# ══════════════════════════════════════════════════════════════════════════════

def modelo_anomalias_gen():
    print("\n" + "═" * 60)
    print("MODELO 2 — Detección de anomalías en generación real")
    print("       (Isolation Forest)")
    print("═" * 60)

    df_real = load_gen_real()
    df_prog = load_gen_prog()

    print(f"  Registros gen. real:       {len(df_real):,}")
    print(f"  Registros gen. programada: {len(df_prog):,}")
    print(f"  Unidades: {sorted(df_real['unidad'].unique())}")

    # Unir real + programada
    df = df_real.merge(df_prog, on=["unidad", "fecha_hora"], how="left")
    df = add_time_features(df)
    df["desvio_mw"]  = df["gen_real_mw"] - df["gen_programada_mw"]
    df["factor_planta"] = df["gen_real_mw"] / df["potencia_maxima"].replace(0, np.nan)

    # Lag de gen real (t-1) por unidad
    df = df.sort_values(["unidad", "fecha_hora"])
    df["gen_real_lag1"] = df.groupby("unidad")["gen_real_mw"].shift(1)
    df["cambio_brusco"] = (df["gen_real_mw"] - df["gen_real_lag1"]).abs()

    df = df.dropna(subset=["gen_programada_mw", "gen_real_lag1"])

    print(f"\n  Registros con programada disponible: {len(df):,}")
    print(f"  Período: {df['fecha_hora'].min()} → {df['fecha_hora'].max()}")

    results = []

    for unidad in sorted(df["unidad"].unique()):
        dfu = df[df["unidad"] == unidad].copy()
        if len(dfu) < 50:
            print(f"  [{unidad}] Muy pocos datos, omitiendo.")
            continue

        features = ["gen_real_mw", "gen_programada_mw", "desvio_mw",
                    "factor_planta", "cambio_brusco", "hora_sin", "hora_cos"]
        X = dfu[features].copy()

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        iso = IsolationForest(
            n_estimators=200,
            contamination=0.05,   # esperamos ~5% de puntos anómalos
            random_state=42,
        )
        dfu["anomalia"]      = iso.fit_predict(X_scaled)   # -1 = anomalía
        dfu["anomalia_score"] = iso.score_samples(X_scaled)  # más negativo = más anómalo

        n_anom = (dfu["anomalia"] == -1).sum()
        pct    = n_anom / len(dfu) * 100

        print(f"\n  [{unidad}]  {len(dfu):,} registros → {n_anom} anomalías ({pct:.1f}%)")

        top5 = (dfu[dfu["anomalia"] == -1]
                .nsmallest(5, "anomalia_score")
                [["fecha_hora", "gen_real_mw", "gen_programada_mw", "desvio_mw", "cambio_brusco", "anomalia_score"]]
                .reset_index(drop=True))
        print(f"    Top 5 más anómalas:")
        print(top5.to_string(index=False))

        results.append(dfu)

    # ── Gráfico ────────────────────────────────────────────────────────────────
    if not results:
        print("  Sin datos suficientes para graficar.")
        return

    df_all = pd.concat(results)
    unidades = sorted(df_all["unidad"].unique())
    n = len(unidades)
    cols = 2
    rows = (n + 1) // cols

    COLORES = {
        "ANG1": "#6366f1",
        "ANG2": "#3b82f6",
        "CCR1": "#eab308",
        "CCR2": "#22c55e",
    }

    fig, axes = plt.subplots(rows, cols, figsize=(16, 4 * rows), facecolor="#F5F7FA")
    fig.suptitle("Modelo 2 — Detección de anomalías en generación real (Isolation Forest)", fontsize=13, fontweight="bold", color="#1e293b")
    axes_flat = axes.flatten() if n > 1 else [axes]

    for i, unidad in enumerate(unidades):
        ax = axes_flat[i]
        ax.set_facecolor("#ffffff")
        dfu = df_all[df_all["unidad"] == unidad].sort_values("fecha_hora")

        normal = dfu[dfu["anomalia"] == 1]
        anomal = dfu[dfu["anomalia"] == -1]

        color = COLORES.get(unidad, "#64748b")
        ax.plot(dfu["fecha_hora"], dfu["gen_real_mw"],
                color=color, lw=1.2, alpha=0.7, label="Gen. real")
        ax.scatter(anomal["fecha_hora"], anomal["gen_real_mw"],
                   color="#ef4444", s=25, zorder=5, label=f"Anomalía ({len(anomal)})")

        ax.set_title(f"{unidad}", fontsize=10, fontweight="bold", color="#1e293b")
        ax.set_ylabel("MW", fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.3)

    # Ocultar axes sobrantes
    for j in range(i + 1, len(axes_flat)):
        axes_flat[j].set_visible(False)

    plt.tight_layout()
    plt.savefig("ml_anomalias_gen.png", dpi=150, bbox_inches="tight")
    print("\n  Gráfico guardado: ml_anomalias_gen.png")

    return df_all


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("CTM Mejillones — Pruebas de ML")
    print("Cargando datos desde Supabase...\n")

    modelo_cmg_forecast()
    df_anomalias = modelo_anomalias_gen()

    print("\n" + "═" * 60)
    print("Listo. Revisa los archivos:")
    print("  ml_cmg_forecast.png")
    print("  ml_anomalias_gen.png")
    print("═" * 60)
