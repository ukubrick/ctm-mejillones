"""
components/_common.py — Helpers compartidos entre componentes.

Unifica lo que estaba duplicado: métrica de precisión PCP vs real
(gen_unidad + costo), guía desplegable <details> (sscc + despacho_cmg)
y cards por unidad (sscc + despacho_cmg).
"""
import pandas as pd
import streamlit as st

from config import LABELS, UNIDADES


def metricas_precision(df_real, df_prog,
                       col_real="gen_real_mw", col_prog="gen_programada_mw"):
    """MAE, RMSE y sesgo de la programada vs real (merge_asof ±1h).

    Devuelve (mae, rmse, sesgo) o None si no hay cruce.
    """
    if df_real is None or df_prog is None or df_real.empty or df_prog.empty:
        return None
    m = pd.merge_asof(
        df_real[["fecha_hora", col_real]].sort_values("fecha_hora"),
        df_prog[["fecha_hora", col_prog]].sort_values("fecha_hora"),
        on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"),
    ).dropna()
    if m.empty:
        return None
    err = m[col_real] - m[col_prog]
    return err.abs().mean(), (err ** 2).mean() ** 0.5, err.mean()


def render_guia(titulo: str, cuerpo_html: str):
    """Guía desplegable estándar (<details>/<summary> con estilo unificado)."""
    st.markdown(
        f'<details style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;'
        f'padding:0.7rem 1rem;margin-bottom:1rem;">'
        f'<summary style="cursor:pointer;font-weight:600;color:#334155;font-size:0.9rem;">{titulo}</summary>'
        f'<div style="margin-top:0.8rem;font-size:0.88rem;color:#475569;line-height:1.6;">{cuerpo_html}</div>'
        f'</details>',
        unsafe_allow_html=True)


def tabla_guia(filas, encabezados=("Campo", "Significado")) -> str:
    """Tabla HTML de 2 columnas para el cuerpo de una guía."""
    th = "".join(f'<th style="padding:6px 12px;text-align:left;font-size:0.82rem;">{h}</th>'
                 for h in encabezados)
    tr = "".join(
        f'<tr><td style="padding:5px 12px;border-top:1px solid #E2E8F0;"><strong>{k}</strong></td>'
        f'<td style="padding:5px 12px;border-top:1px solid #E2E8F0;">{v}</td></tr>'
        for k, v in filas)
    return (f'<table style="width:100%;border-collapse:collapse;margin:0.5rem 0;">'
            f'<thead><tr style="background:#E2E8F0;">{th}</tr></thead><tbody>{tr}</tbody></table>')


def render_cards_unidad(df, card_html_fn, orden_cols, max_n=5,
                        ascendente=False, vacio="Sin instrucciones"):
    """4 columnas (una por unidad) con máx `max_n` cards recientes.

    `card_html_fn(row, unidad, es_primera)` devuelve el HTML de cada card
    (la primera lleva la clase palpitante `.sscc-latest` a cargo del caller).
    """
    cols = st.columns(4)
    for col, unidad in zip(cols, UNIDADES):
        df_u = df[df["unidad"] == unidad].sort_values(orden_cols, ascending=ascendente)
        with col:
            st.markdown(f"**{LABELS[unidad]}**")
            if df_u.empty:
                st.caption(vacio)
                continue
            for i, (_, row) in enumerate(df_u.head(max_n).iterrows()):
                st.markdown(card_html_fn(row, unidad, i == 0), unsafe_allow_html=True)
            if len(df_u) > max_n:
                st.caption(f"+{len(df_u) - max_n} más en «Tabla completa»")
