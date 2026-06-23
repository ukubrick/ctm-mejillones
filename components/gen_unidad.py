"""
components/gen_unidad.py — Generación real vs programada + CMG por unidad.

Selector de unidad por botones (evita el bug de Plotly width=0 dentro de
st.tabs) y gráfico de 1 o 2 filas según haya CMG.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import LABELS, NOMBRES_NODO, UNIDADES, BG, GR, POT_MIN_TECNICA, SERIE
from utils.data import load_cmg_prog


def _chart_unidad(unidad, df_r, df_p, df_c, df_cp, mostrar_prog, mostrar_cmg, mostrar_desv, nodo_label):
    df_u  = df_r[df_r["unidad"] == unidad].sort_values("fecha_hora")
    df_up = df_p[df_p["unidad"] == unidad].sort_values("fecha_hora") if not df_p.empty else pd.DataFrame()

    if df_u.empty:
        st.info(f"Sin datos para {LABELS[unidad]} en el período.")
        return

    tiene_cmg  = mostrar_cmg and not df_c.empty
    tiene_prog = mostrar_prog and not df_up.empty
    n_rows  = 2 if tiene_cmg else 1
    heights = [0.62, 0.38] if n_rows == 2 else [1.0]

    fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True, row_heights=heights, vertical_spacing=0.12)

    fig.add_trace(go.Scatter(
        x=df_u["fecha_hora"], y=df_u["gen_real_mw"], name="Real", mode="lines",
        line=dict(color=SERIE["real"], width=1.8),
        hovertemplate="<b>Real</b> %{x|%d/%m %H:%M}<br>%{y:.1f} MW<extra></extra>",
    ), row=1, col=1)

    # Línea de mínimo técnico — referencia de operación estable de la unidad
    pmin = POT_MIN_TECNICA.get(unidad)
    if pmin:
        fig.add_hline(
            y=pmin, line_color=SERIE["minimo"], line_width=1.2, line_dash="dot",
            annotation_text=f"Mín técnico {pmin:.0f} MW", annotation_position="bottom right",
            annotation_font_color="#64748B", annotation_font_size=10, row=1, col=1,
        )

    if tiene_prog:
        fig.add_trace(go.Scatter(
            x=df_up["fecha_hora"], y=df_up["gen_programada_mw"], name="Programada", mode="lines",
            line=dict(color=SERIE["prog"], width=1.4, dash="dash"),
            hovertemplate="<b>Programada</b> %{x|%d/%m %H:%M}<br>%{y:.1f} MW<extra></extra>",
        ), row=1, col=1)

        if mostrar_desv:
            idx_real = df_u.set_index("fecha_hora")["gen_real_mw"]
            idx_prog = df_up.set_index("fecha_hora")["gen_programada_mw"]
            idx_com  = idx_real.index.union(idx_prog.index)
            real_ri  = idx_real.reindex(idx_com).interpolate("time")
            prog_ri  = idx_prog.reindex(idx_com).interpolate("time")
            dfm = pd.DataFrame({"real": real_ri, "prog": prog_ri}).dropna()
            if not dfm.empty:
                x = dfm.index.tolist()
                over  = dfm[["real", "prog"]].max(axis=1)  # techo → sobregeneración (real > prog)
                under = dfm[["real", "prog"]].min(axis=1)  # piso  → subgeneración  (real < prog)
                # Sobregeneración: verde, entre la línea programada y el máximo
                fig.add_trace(go.Scatter(x=x, y=dfm["prog"], mode="lines",
                    line=dict(width=0), hoverinfo="skip", showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=x, y=over, mode="lines", fill="tonexty",
                    fillcolor=SERIE["over"], line=dict(width=0),
                    name="Sobregeneración", hoverinfo="skip"), row=1, col=1)
                # Subgeneración: rojo, entre la línea programada y el mínimo
                fig.add_trace(go.Scatter(x=x, y=dfm["prog"], mode="lines",
                    line=dict(width=0), hoverinfo="skip", showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=x, y=under, mode="lines", fill="tonexty",
                    fillcolor=SERIE["under"], line=dict(width=0),
                    name="Subgeneración", hoverinfo="skip"), row=1, col=1)

    if tiene_cmg:
        fig.add_trace(go.Scatter(
            x=df_c["fecha_hora"], y=df_c["cmg_usd_mwh"], name=f"CMG real {nodo_label}", mode="lines",
            line=dict(color=SERIE["cmg"], width=1.8), fill="tozeroy",
            fillcolor=SERIE["cmg_fill"],
            hovertemplate="<b>CMG real</b> %{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>",
        ), row=2, col=1)
        # Overlay CMG programado (PID), para comparar y tomar decisiones de programación
        if df_cp is not None and not df_cp.empty:
            fig.add_trace(go.Scatter(
                x=df_cp["fecha_hora"], y=df_cp["cmg_usd_mwh"], name="CMG programado", mode="lines",
                line=dict(color=SERIE["cmg_prog"], width=1.4, dash="dash"),
                hovertemplate="<b>CMG programado</b> %{x|%d/%m %H:%M}<br>%{y:.1f} USD/MWh<extra></extra>",
            ), row=2, col=1)
        prom_cmg = df_c["cmg_usd_mwh"].mean()
        fig.add_hline(y=prom_cmg, line_color="#94A3B8", line_width=1, line_dash="dot",
                      annotation_text=f"Prom: {prom_cmg:.1f}", annotation_position="right",
                      annotation_font_color="#64748B", annotation_font_size=10, row=2, col=1)

    fig.update_layout(
        height=520, autosize=True, margin=dict(l=10, r=70, t=20, b=10),
        template="plotly_white", plot_bgcolor=BG, paper_bgcolor="#FFFFFF",
        transition=dict(duration=300, easing="cubic-in-out"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color="#6B7280", size=11), bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1A1F36", font_color="#F5F7FA", bordercolor="#3B4CE8"),
    )
    fig.update_yaxes(title_text="MW", gridcolor=GR, zeroline=False,
                     tickfont=dict(color="#94A3B8", size=10), title_font=dict(color="#94A3B8", size=11), row=1, col=1)
    if tiene_cmg:
        fig.update_yaxes(title_text="USD/MWh", gridcolor=GR, zeroline=False,
                         tickfont=dict(color="#94A3B8", size=10), title_font=dict(color="#94A3B8", size=11), row=2, col=1)
    for r in range(1, n_rows + 1):
        fig.update_xaxes(showticklabels=True, tickformat="%d/%m\n%H:%M",
                         tickfont=dict(color="#64748B", size=10), showgrid=False, row=r, col=1)

    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False, "responsive": True}, key=f"chart_unidad_{unidad}")

    if mostrar_prog and df_up.empty:
        st.caption("Sin datos de programada — se importan automáticamente desde CEN PCP cada hora. "
                   "El ingreso manual está disponible más abajo.")

    # Precisión de la programación PCP vs generación real (MAE / RMSE / sesgo)
    if not df_up.empty:
        m = pd.merge_asof(
            df_u[["fecha_hora", "gen_real_mw"]].sort_values("fecha_hora"),
            df_up[["fecha_hora", "gen_programada_mw"]].sort_values("fecha_hora"),
            on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
        ).dropna()
        if not m.empty:
            err  = m["gen_real_mw"] - m["gen_programada_mw"]
            mae  = err.abs().mean()
            rmse = (err ** 2).mean() ** 0.5
            sesgo = err.mean()
            st.caption("Precisión de la programación PCP vs real (menor = mejor)")
            k1, k2, k3 = st.columns(3)
            k1.metric("MAE", f"{mae:.1f} MW", help="Error absoluto medio |real − programada|")
            k2.metric("RMSE", f"{rmse:.1f} MW", help="Raíz del error cuadrático medio (penaliza desvíos grandes)")
            k3.metric("Sesgo", f"{sesgo:+.1f} MW", help="Promedio (real − programada): + sobregeneró, − subgeneró")


def render_gen_unidad(df_r, df_p, df_c, mostrar_prog, mostrar_cmg, nodo_cmg, s=None, e=None):
    nl = NOMBRES_NODO.get(nodo_cmg, "Crucero 220kV")
    st.markdown(f'<div class="sec">POTENCIA REAL vs PROGRAMADA + CMG {nl.upper()} · POR UNIDAD</div>', unsafe_allow_html=True)

    mostrar_desv = False
    if not df_p.empty and mostrar_prog:
        mostrar_desv = st.checkbox("Mostrar área de desviación (Real vs Programada)", value=True)

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
    df_cp = load_cmg_prog(s, e, nodo_cmg) if (mostrar_cmg and s and e) else None
    st.markdown(
        f'<p style="color:#334155;font-weight:600;font-size:0.9rem;margin:0.4rem 0 0.3rem">'
        f'{LABELS[u_act]} · Real vs Programada (MW) + CMG {nl} (USD/MWh)</p>',
        unsafe_allow_html=True,
    )
    _chart_unidad(u_act, df_r, df_p, df_c, df_cp, mostrar_prog, mostrar_cmg, mostrar_desv, nl)
