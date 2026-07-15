"""
components/gen_unidad.py — Generación real vs programada + CMG por unidad.

Selector de unidad por botones (evita el bug de Plotly width=0 dentro de
st.tabs) y gráfico de 1 o 2 filas según haya CMG.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import LABELS, NOMBRES_NODO, UNIDADES, BG, GR, POT_MIN_TECNICA, SERIE, CMG_A_DEMANDA
from utils.data import (load_cmg_prog, load_prog_pid, load_pronostico_demanda,
                        load_real, load_cmg)
from utils.plotly_theme import add_linea_ahora, estilo_serie, hover
from components._common import metricas_precision

# MW bajo el cual se considera que la unidad está detenida (trip / desconexión).
# < 5 MW en la práctica ya indica potencia 0 (unidad desenganchada).
UMBRAL_CERO = 5.0


def _banda_desviacion(fig, df_real, df_ref, ref_nombre):
    """Área bicolor entre la generación real y el programa de referencia.

    Verde = real por encima del programa (sobregeneración); rojo = real por
    debajo (subgeneración). Se dibuja ANTES que las líneas para quedar detrás.
    """
    idx_real = df_real.set_index("fecha_hora")["gen_real_mw"]
    idx_ref  = df_ref.set_index("fecha_hora")["gen_programada_mw"]
    idx_com  = idx_real.index.union(idx_ref.index)
    # limit_area="inside": interpola solo huecos internos, nunca extrapola. Así la
    # banda no invade el futuro (donde hay PID pero aún no hay real medida).
    real_ri  = idx_real.reindex(idx_com).interpolate("time", limit_area="inside")
    ref_ri   = idx_ref.reindex(idx_com).interpolate("time", limit_area="inside")
    dfm = pd.DataFrame({"real": real_ri, "ref": ref_ri}).dropna()
    if dfm.empty:
        return
    x = dfm.index.to_numpy()
    over  = dfm[["real", "ref"]].max(axis=1)   # techo → sobregeneración
    under = dfm[["real", "ref"]].min(axis=1)   # piso  → subgeneración
    fig.add_trace(go.Scatter(x=x, y=dfm["ref"], mode="lines",
        line=dict(width=0), hoverinfo="skip", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=over, mode="lines", fill="tonexty",
        fillcolor=SERIE["over"], line=dict(width=0), legendrank=4,
        name=f"Real > {ref_nombre}", hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=dfm["ref"], mode="lines",
        line=dict(width=0), hoverinfo="skip", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=under, mode="lines", fill="tonexty",
        fillcolor=SERIE["under"], line=dict(width=0), legendrank=5,
        name=f"Real < {ref_nombre}", hoverinfo="skip"), row=1, col=1)


def _ingreso(df_real_u, df_cmg):
    """Ingreso estimado (USD) = Σ gen_real × CMG (merge_asof ±1h). None si falta CMG."""
    if df_real_u is None or df_real_u.empty or df_cmg is None or df_cmg.empty:
        return None
    m = pd.merge_asof(
        df_real_u[["fecha_hora", "gen_real_mw"]].sort_values("fecha_hora"),
        df_cmg[["fecha_hora", "cmg_usd_mwh"]].sort_values("fecha_hora"),
        on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
    ).dropna(subset=["cmg_usd_mwh"])
    if m.empty:
        return None
    return float((m["gen_real_mw"] * m["cmg_usd_mwh"]).sum())


def _ingreso_semana_pasada(unidad, nodo_cmg, e):
    """Ingreso de la unidad en la semana previa a `e` ([e-14d, e-7d]) para comparar."""
    if not e:
        return None
    e_ts = pd.Timestamp(e)
    ini = (e_ts - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
    fin = (e_ts - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    dr = load_real(ini, fin)
    dc = load_cmg(ini, fin, nodo_cmg or "CRUCERO_______220")
    if dr is None or dr.empty:
        return None
    return _ingreso(dr[dr["unidad"] == unidad], dc)


def _chart_unidad(unidad, df_r, df_p, df_pid, df_c, df_cp, df_dem, barra_dem,
                  vis, nodo_label, nodo_cmg=None, s=None, e=None):
    df_u   = df_r[df_r["unidad"] == unidad].sort_values("fecha_hora")
    df_up  = df_p[df_p["unidad"] == unidad].sort_values("fecha_hora") if not df_p.empty else pd.DataFrame()
    df_upid = (df_pid[df_pid["unidad"] == unidad].sort_values("fecha_hora")
               if (df_pid is not None and not df_pid.empty) else pd.DataFrame())

    if df_u.empty:
        st.info(f"Sin datos para {LABELS[unidad]} en el período.")
        return

    # ── Detección de potencia real en 0 (trip / desconexión / mantención) ────
    # Cualquier hora con gen_real ≤ umbral significa unidad detenida. Se resalta
    # en rojo en la serie y con un mensaje de alerta sobre el gráfico.
    df_cero = df_u[df_u["gen_real_mw"] < UMBRAL_CERO]
    if not df_cero.empty:
        n = len(df_cero)
        ini = df_cero["fecha_hora"].min().strftime("%d-%m %H:%M")
        fin = df_cero["fecha_hora"].max().strftime("%d-%m %H:%M")
        rango = f"{ini}" if n == 1 else f"{ini} → {fin}"
        st.markdown(
            f'<div style="background:#FEF2F2;border:1px solid #FCA5A5;border-left:5px solid #DC2626;'
            f'border-radius:8px;padding:10px 16px;margin:2px 0 10px;color:#991B1B;font-size:0.86rem;'
            f'font-weight:600;display:flex;align-items:center;gap:9px">'
            f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
            f'background:#DC2626;animation:blink 1s infinite"></span>'
            f'ALERTA · {LABELS[unidad]} con potencia en 0 MW en {n} hora(s) '
            f'({rango}) — trip, desconexión programada o mantención.</div>',
            unsafe_allow_html=True,
        )

    tiene_cmg = vis["cmg"] and not df_c.empty
    tiene_pcp = vis["pcp"] and not df_up.empty
    tiene_pid = vis["pid"] and not df_upid.empty
    # Fallback: si se pidió PID pero aún no hay datos PID en la ventana, se muestra
    # el PCP como referencia visible (así el gráfico nunca queda sin programa).
    pid_en_fallback = vis["pid"] and not tiene_pid and not df_up.empty
    if pid_en_fallback:
        tiene_pcp = True
        st.markdown(
            '<div style="background:#FFF4E5;border-left:3px solid #E8A33D;'
            'border-radius:6px;padding:8px 12px;margin:4px 0 10px;'
            'color:#7A5316;font-size:0.86rem;">'
            'PID no disponible en este rango — el CEN dejó de emitir el programa '
            'intra-día. Se muestra el PCP (programa del día anterior) como referencia.'
            '</div>',
            unsafe_allow_html=True,
        )
    tiene_dem = tiene_cmg and vis["demanda"] and df_dem is not None and not df_dem.empty

    # Programa de referencia del área de desviación: PID (intra-día, más fresco)
    # si está visible; si no, PCP (día-ante). El área mide real vs ese programa.
    if tiene_pid:
        ref_df, ref_nombre = df_upid, "PID"
    elif tiene_pcp:
        ref_df, ref_nombre = df_up, "PCP"
    else:
        ref_df, ref_nombre = None, None
    mostrar_banda = vis["desv"] and ref_df is not None

    n_rows  = 2 if tiene_cmg else 1
    heights = [0.62, 0.38] if n_rows == 2 else [1.0]

    # La fila del CMG lleva eje secundario para la demanda (MWh)
    specs = [[{"secondary_y": False}], [{"secondary_y": True}]] if n_rows == 2 else [[{"secondary_y": False}]]
    fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True, row_heights=heights,
                        vertical_spacing=0.12, specs=specs)

    # 1) Área de desviación primero → queda detrás de las líneas
    if mostrar_banda:
        _banda_desviacion(fig, df_u, ref_df, ref_nombre)

    # 2) Real (protagonista). Sin relleno a cero cuando hay banda (evita doble área)
    real_style = estilo_serie("real")
    if mostrar_banda:
        real_style = {k: v for k, v in real_style.items() if k not in ("fill", "fillcolor")}
    fig.add_trace(go.Scatter(
        x=df_u["fecha_hora"], y=df_u["gen_real_mw"], name="Real", mode="lines",
        hovertemplate=hover("Real", "MW", "medición SCADA horaria"), legendrank=1,
        **real_style,
    ), row=1, col=1)

    # 2b) Resaltar en rojo las horas con potencia real en 0 (unidad detenida).
    if not df_cero.empty:
        for x0 in df_cero["fecha_hora"]:
            fig.add_vrect(x0=x0 - pd.Timedelta(minutes=30), x1=x0 + pd.Timedelta(minutes=30),
                          fillcolor="rgba(220,38,38,0.10)", line_width=0, row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_cero["fecha_hora"], y=df_cero["gen_real_mw"], name="Potencia 0 (detenida)",
            mode="markers", legendrank=1,
            marker=dict(color="#DC2626", size=11, symbol="x-thin",
                        line=dict(color="#DC2626", width=2.5)),
            hovertemplate="<b>UNIDAD DETENIDA</b> %{x|%d/%m %H:%M}<br>"
                          "0 MW · trip / desconexión / mantención<extra></extra>",
        ), row=1, col=1)

    # Línea de mínimo técnico — referencia de operación estable de la unidad
    pmin = POT_MIN_TECNICA.get(unidad)
    if pmin:
        fig.add_hline(
            y=pmin, line_color=SERIE["minimo"], line_width=1.2, line_dash="dot",
            annotation_text=f"Mín técnico {pmin:.0f} MW", annotation_position="bottom right",
            annotation_font_color="#64748B", annotation_font_size=10, row=1, col=1,
        )

    # 3) Programada PCP (día-ante) — referencia recesiva, punteada gris
    if tiene_pcp:
        fig.add_trace(go.Scatter(
            x=df_up["fecha_hora"], y=df_up["gen_programada_mw"], name="Programada PCP", mode="lines",
            hovertemplate=hover("Programada PCP", "MW", "programa diario declarado D-1 ante CEN"),
            legendrank=3, **estilo_serie("prog"),
        ), row=1, col=1)

    # 4) Programada PID (intra-día) — programa operativo, ámbar discontinua prominente
    if tiene_pid:
        fig.add_trace(go.Scatter(
            x=df_upid["fecha_hora"], y=df_upid["gen_programada_mw"], name="Programada PID", mode="lines",
            hovertemplate=hover("Programada PID", "MW", "reajuste intra-día del PCP"),
            legendrank=2, **estilo_serie("prog_pid"),
        ), row=1, col=1)

    # Marcar horas con el programa de referencia bajo el mínimo técnico (rampas /
    # pruebas especiales; operación sostenida bajo mínimo es excepcional).
    if ref_df is not None and pmin:
        bajo = ref_df[(ref_df["gen_programada_mw"] > 0) & (ref_df["gen_programada_mw"] < pmin)]
        if not bajo.empty:
            fig.add_trace(go.Scatter(
                x=bajo["fecha_hora"], y=bajo["gen_programada_mw"], mode="markers",
                name="Programa < mín técnico", legendrank=8,
                marker=dict(color="#F97316", size=9, symbol="diamond",
                            line=dict(color="#FFFFFF", width=1.2)),
                hovertemplate="<b>Bajo mín técnico</b> %{x|%d/%m %H:%M}<br>"
                              "%{y:.1f} MW (mín " + f"{pmin:.0f}" + ")<br>"
                              "<i>rampa o prueba especial</i><extra></extra>",
            ), row=1, col=1)

    if tiene_cmg:
        fig.add_trace(go.Scatter(
            x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"], name=f"CMG real {nodo_label}", mode="lines",
            hovertemplate=hover("CMG real", "USD/MWh", "online S3, actualiza ~15 min"),
            legendrank=6, **estilo_serie("cmg"),
        ), row=2, col=1)
        # Overlay CMG programado (PID), para comparar y tomar decisiones de programación
        if vis["cmg_prog"] and df_cp is not None and not df_cp.empty:
            fig.add_trace(go.Scatter(
                x=df_cp["fecha_hora"], y=df_cp["cmg_usd_mwh"], name="CMG programado", mode="lines",
                hovertemplate=hover("CMG programado", "USD/MWh", "programa PID del CEN"),
                legendrank=7, **estilo_serie("cmg_prog"),
            ), row=2, col=1)
        # Overlay demanda pronosticada (eje secundario): alta demanda anticipa CMG alto
        if tiene_dem:
            fig.add_trace(go.Scatter(
                x=df_dem["fecha_hora"], y=df_dem["energia_mwh"], name=f"Demanda {barra_dem}", mode="lines",
                hovertemplate=hover("Demanda", "MWh", "pronóstico corto plazo CEN"),
                **estilo_serie("demanda"),
            ), row=2, col=1, secondary_y=True)
        prom_cmg = df_c["cmg_usd_mwh"].mean()
        fig.add_hline(y=prom_cmg, line_color="#94A3B8", line_width=1, line_dash="dot",
                      annotation_text=f"Prom: {prom_cmg:.1f}", annotation_position="right",
                      annotation_font_color="#64748B", annotation_font_size=10, row=2, col=1,
                      secondary_y=False)

    fig.update_layout(
        height=520, autosize=True, margin=dict(l=10, r=70, t=20, b=10),
        template="plotly_white", plot_bgcolor=BG, paper_bgcolor="#FFFFFF",
        transition=dict(duration=300, easing="cubic-in-out"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    traceorder="normal",
                    font=dict(color="#6B7280", size=11), bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1A1F36", font_color="#F5F7FA", bordercolor="#3B4CE8"),
    )
    fig.update_yaxes(title_text="MW", gridcolor=GR, zeroline=False, rangemode="tozero",
                     tickfont=dict(color="#94A3B8", size=10), title_font=dict(color="#94A3B8", size=11), row=1, col=1)

    # Línea "ahora": separa lo medido (real) de lo programado a futuro (PCP/PID)
    xs = [df_u["fecha_hora"]]
    if not df_up.empty:
        xs.append(df_up["fecha_hora"])
    if not df_upid.empty:
        xs.append(df_upid["fecha_hora"])
    x_all = pd.concat(xs)
    x_min, x_max = x_all.min(), x_all.max()
    add_linea_ahora(fig, x_min, x_max)
    if tiene_cmg:
        fig.update_yaxes(title_text="USD/MWh", gridcolor=GR, zeroline=False,
                         tickfont=dict(color="#94A3B8", size=10), title_font=dict(color="#94A3B8", size=11),
                         row=2, col=1, secondary_y=False)
        if tiene_dem:
            fig.update_yaxes(title_text="Demanda MWh", showgrid=False, zeroline=False,
                             tickfont=dict(color="#94A3B8", size=10), title_font=dict(color="#94A3B8", size=11),
                             row=2, col=1, secondary_y=True)
    for r in range(1, n_rows + 1):
        # range explícito = las series llegan de borde a borde (sin el padding
        # automático ~5% que dejaba franjas vacías a izquierda/derecha).
        fig.update_xaxes(showticklabels=True, tickformat="%d/%m\n%H:%M",
                         tickfont=dict(color="#64748B", size=10), showgrid=False,
                         range=[x_min, x_max], autorange=False, row=r, col=1)

    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False, "responsive": True}, key=f"chart_unidad_{unidad}")

    if vis["pcp"] and df_up.empty:
        st.caption("Sin datos de programada — se importan automáticamente desde CEN PCP cada hora. "
                   "El ingreso manual está disponible más abajo.")

    # Precisión de la programación vs generación real (MAE / RMSE / sesgo).
    # Se mide contra el programa más fresco disponible: PID si existe, si no PCP.
    metr_df, metr_nombre = ((df_upid, "PID") if not df_upid.empty
                            else ((df_up, "PCP") if not df_up.empty else (None, None)))
    if metr_df is not None:
        res = metricas_precision(df_u, metr_df)
        if res is not None:
            mae, rmse, sesgo = res
            st.caption(f"Precisión de la programación {metr_nombre} vs real (menor = mejor)")
            # Ingreso estimado de la unidad (gen_real × CMG) + comparación semana pasada.
            ingreso = _ingreso(df_u, df_c)
            k0, k1, k2, k3 = st.columns(4)
            if ingreso is not None:
                prev = _ingreso_semana_pasada(unidad, nodo_cmg, e)
                delta = None
                if prev and prev > 0:
                    # + verde = ingresó más que la semana pasada; − rojo = peor.
                    delta = f"{(ingreso - prev) / prev * 100:+.1f}% vs semana pasada"
                k0.metric("Ingreso estimado", f"${ingreso:,.0f}", delta,
                          help="Σ generación real × CMG en el período (USD). "
                               "Delta = variación vs la semana anterior.")
            else:
                k0.metric("Ingreso estimado", "—",
                          help="Requiere datos de CMG en el período.")
            k1.metric("MAE", f"{mae:.1f} MW", help="Error absoluto medio |real − programada|")
            k2.metric("RMSE", f"{rmse:.1f} MW", help="Raíz del error cuadrático medio (penaliza desvíos grandes)")
            k3.metric("Sesgo", f"{sesgo:+.1f} MW", help="Promedio (real − programada): + sobregeneró, − subgeneró")


def render_gen_unidad(df_r, df_p, df_c, mostrar_prog, mostrar_cmg, nodo_cmg, s=None, e=None):
    st.markdown('<div class="sec">Generación por unidad · real vs programada y costo marginal</div>',
                unsafe_allow_html=True)

    # Selector de nodo CMG (antes en el sidebar). Persiste en session_state["nodo_cmg"]
    # → app.py lo lee para cargar df_c en la próxima corrida.
    _nodos = list(NOMBRES_NODO.keys())
    sc1, _ = st.columns([1, 2])
    with sc1:
        nodo_cmg = st.radio("Nodo CMG", _nodos,
                            index=_nodos.index(nodo_cmg) if nodo_cmg in _nodos else 0,
                            format_func=lambda x: NOMBRES_NODO[x], horizontal=True, key="nodo_cmg")
    nl = NOMBRES_NODO.get(nodo_cmg, "Crucero 220kV")

    # ── Control de series visibles ──────────────────────────────────────────
    # La línea Real siempre se muestra; el resto se activa/desactiva aquí para
    # evitar saturar el gráfico. Los valores del sidebar actúan como default.
    with st.expander("Series visibles", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("Generación")
            v_pid  = st.checkbox("Programada PID", value=mostrar_prog, key="vis_pid",
                                 help="Programa intra-día (operativo). Referencia del área de desviación.")
            v_pcp  = st.checkbox("Programada PCP", value=False, key="vis_pcp",
                                 help="Programa día-ante (referencia secundaria).")
            v_desv = st.checkbox("Área de desviación", value=True, key="vis_desv",
                                 disabled=not (v_pid or v_pcp))
        with c2:
            st.caption("Costo marginal")
            v_cmg  = st.checkbox("CMG real", value=mostrar_cmg, key="vis_cmg")
            v_cmgp = st.checkbox("CMG programado", value=True, key="vis_cmgp",
                                 disabled=not v_cmg)
        with c3:
            st.caption("Contexto")
            v_dem  = st.checkbox("Demanda pronosticada", value=False, key="vis_dem",
                                 disabled=not v_cmg)

    vis = {"pcp": v_pcp, "pid": v_pid, "desv": v_desv and (v_pid or v_pcp),
           "cmg": v_cmg, "cmg_prog": v_cmgp, "demanda": v_dem}

    st.session_state.setdefault("unidad_sel", "ANG1")
    cols_btn = st.columns(4)
    for col, u in zip(cols_btn, UNIDADES):
        with col:
            activo = st.session_state["unidad_sel"] == u
            if st.button(LABELS[u], key=f"btn_u_{u}", use_container_width=True,
                         type="primary" if activo else "secondary"):
                st.session_state["unidad_sel"] = u
                st.rerun()

    u_act = st.session_state["unidad_sel"]
    df_cp  = load_cmg_prog(s, e, nodo_cmg) if (vis["cmg_prog"] and s and e) else None
    df_pid = load_prog_pid(s, e) if (vis["pid"] and s and e) else None
    barra_dem = CMG_A_DEMANDA.get(nodo_cmg, "Crucero220")
    df_dem = load_pronostico_demanda(s, e, barra_dem) if (vis["demanda"] and s and e) else None
    st.markdown(
        f'<p style="color:#334155;font-weight:600;font-size:0.9rem;margin:0.4rem 0 0.3rem">'
        f'{LABELS[u_act]} · Real vs Programada (MW) + CMG {nl} (USD/MWh)</p>',
        unsafe_allow_html=True,
    )
    _chart_unidad(u_act, df_r, df_p, df_pid, df_c, df_cp, df_dem, barra_dem, vis, nl,
                  nodo_cmg=nodo_cmg, s=s, e=e)
