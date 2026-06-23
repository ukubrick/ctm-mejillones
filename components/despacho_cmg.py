"""components/despacho_cmg.py — Instrucciones operacionales de despacho por CMG."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import COLORES, LABELS, UNIDADES
from utils.data import load_instrucciones_cmg

_GUIA = """
<details style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:0.7rem 1rem;margin-bottom:1rem;">
<summary style="cursor:pointer;font-weight:600;color:#334155;font-size:0.9rem;">Guía de instrucciones de despacho CMG</summary>
<div style="margin-top:0.8rem;font-size:0.88rem;color:#475569;line-height:1.6;">
<p>Las <strong>instrucciones operacionales por CMG</strong> son las órdenes de despacho que el
Coordinador Eléctrico Nacional entrega a cada unidad para operar según el orden de mérito económico
(costo marginal). Cada registro indica el <strong>despacho en MW</strong> instruido a una hora dada,
junto con el tipo de consigna y el motivo cuando existe.</p>
<table style="width:100%;border-collapse:collapse;margin:0.5rem 0;">
<thead><tr style="background:#E2E8F0;">
<th style="padding:6px 12px;text-align:left;font-size:0.82rem;">Campo</th>
<th style="padding:6px 12px;text-align:left;font-size:0.82rem;">Significado</th>
</tr></thead>
<tbody>
<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>Despacho</strong></td><td style="padding:5px 12px;border-top:1px solid #E2E8F0;">Potencia instruida a la unidad para esa hora (MW)</td></tr>
<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>Consigna</strong></td><td style="padding:5px 12px;border-top:1px solid #E2E8F0;">Tipo de orden: MT (mínimo técnico), PC (potencia coordinada), EP (en pruebas), etc.</td></tr>
<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>Instrucción CMG</strong></td><td style="padding:5px 12px;border-top:1px solid #E2E8F0;">Razón económica: OM (orden de mérito), OT (otro), etc.</td></tr>
<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>Motivo</strong></td><td style="padding:5px 12px;border-top:1px solid #E2E8F0;">Justificación en texto libre cuando el despacho se aparta del orden de mérito</td></tr>
</tbody>
</table>
</div>
</details>
"""


def render_despacho_cmg(s, e):
    st.markdown('<div class="sec">INSTRUCCIONES DE DESPACHO (CMG)</div>', unsafe_allow_html=True)
    st.markdown(_GUIA, unsafe_allow_html=True)

    df = load_instrucciones_cmg(s, e)
    if df.empty:
        st.info("Sin instrucciones de despacho para el período seleccionado. "
                "Los datos se adquieren automáticamente cada hora.")
        return

    dias = df["fecha"].nunique()
    con_motivo = df["motivo"].fillna("").str.strip().ne("").sum()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Instrucciones totales", len(df))
    k2.metric("Unidades con despacho", f"{df['unidad'].nunique()} / 4")
    k3.metric("Con motivo registrado", int(con_motivo))
    k4.metric("Días con datos", dias)
    st.markdown("")

    tab1, tab2, tab3 = st.tabs(["Por unidad", "Despacho instruido", "Tabla completa"])
    with tab1:
        _por_unidad(df)
    with tab2:
        _grafico_despacho(df)
    with tab3:
        _tabla(df)


def _por_unidad(df):
    cols = st.columns(4)
    for col, unidad in zip(cols, UNIDADES):
        df_u = df[df["unidad"] == unidad].sort_values("fecha_hora_dt", ascending=False)
        color = COLORES[unidad]["line"]
        with col:
            st.markdown(f"**{LABELS[unidad]}**")
            if df_u.empty:
                st.caption("Sin instrucciones")
                continue
            for idx_row, (_, row) in enumerate(df_u.head(5).iterrows()):
                desp = f"{float(row['despacho']):.0f} MW" if pd.notna(row["despacho"]) else "—"
                consigna = str(row.get("consigna") or "").strip() or "—"
                fh = str(row["fecha_hora"])[:16]
                motivo = str(row.get("motivo") or "").strip()
                motivo_html = (f'<br><span style="color:#64748B;font-size:0.7rem;font-style:italic">{motivo[:90]}</span>'
                               if motivo else "")
                extra = ' sscc-latest' if idx_row == 0 else ''
                st.markdown(
                    f'<div class="sscc-card{extra}" style="border:1px solid {color}33;border-left:3px solid {color};'
                    f'background:#F8FAFC;border-radius:6px;padding:6px 10px;margin-bottom:6px;">'
                    f'<span style="font-weight:700;color:{color};font-size:0.85rem">{desp}</span>'
                    f'<span style="color:#64748B;font-size:0.7rem;float:right">{fh}</span><br>'
                    f'<span style="color:#475569;font-size:0.72rem">Consigna: {consigna}</span>'
                    f'{motivo_html}</div>',
                    unsafe_allow_html=True)
            if len(df_u) > 5:
                st.caption(f"+{len(df_u) - 5} más en «Tabla completa»")


def _grafico_despacho(df):
    BG, GR = "rgba(0,0,0,0)", "#E2E8F0"
    d = df.dropna(subset=["fecha_hora_dt", "despacho"]).copy()
    if d.empty:
        st.caption("Sin valores de despacho para graficar.")
        return
    fig = go.Figure()
    for unidad in UNIDADES:
        du = d[d["unidad"] == unidad].sort_values("fecha_hora_dt")
        if du.empty:
            continue
        fig.add_trace(go.Scatter(
            x=du["fecha_hora_dt"], y=du["despacho"], name=LABELS[unidad], mode="lines+markers",
            line=dict(color=COLORES[unidad]["line"], width=2), marker=dict(size=5)))
    fig.update_layout(
        title=dict(text="Despacho instruido por unidad (MW)", font=dict(size=13, color="#0F172A"), x=0),
        height=380, margin=dict(l=10, r=10, t=50, b=10), plot_bgcolor=BG, paper_bgcolor=BG,
        xaxis=dict(tickfont=dict(color="#94A3B8", size=10), showgrid=False),
        yaxis=dict(gridcolor=GR, tickfont=dict(color="#94A3B8", size=10), title="MW"),
        legend=dict(orientation="h", y=-0.2, font=dict(size=10)), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _tabla(df):
    d = df.copy()
    d["motivo"] = d["motivo"].fillna("").str[:100]
    d["despacho"] = pd.to_numeric(d["despacho"], errors="coerce").round(0)
    st.dataframe(
        d[["fecha_hora", "unidad", "despacho", "consigna", "instruccion_cmg",
           "estado_operativo", "motivo"]].rename(
            columns={"fecha_hora": "Fecha/Hora", "despacho": "Despacho MW", "consigna": "Consigna",
                     "instruccion_cmg": "Instr. CMG", "estado_operativo": "Estado op.", "motivo": "Motivo"}),
        use_container_width=True, hide_index=True)
