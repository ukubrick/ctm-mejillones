"""components/novedades.py — Panel rápido de estado actual por unidad.

Muestra, debajo de la serie de CMG en la vista Resumen, las últimas novedades
de cada unidad como referencia operativa de un vistazo:
  · última consigna de despacho (instrucciones CMG)
  · última instrucción SSCC (la misma que palpita como primera fila en SSCC)
"""
import pandas as pd
import streamlit as st

from config import LABELS, UNIDADES, COLORES
from utils.data import load_instrucciones_cmg, load_sscc


def _fila(icono_color, etiqueta, valor, detalle=""):
    det = (f'<div style="color:#64748B;font-size:0.68rem;font-style:italic;'
           f'margin-top:1px">{detalle}</div>' if detalle else "")
    return (
        f'<div style="margin:4px 0">'
        f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
        f'background:{icono_color};margin-right:6px;vertical-align:middle"></span>'
        f'<span style="color:#94A3B8;font-size:0.66rem;text-transform:uppercase;'
        f'letter-spacing:0.3px">{etiqueta}</span><br>'
        f'<span style="color:#334155;font-size:0.78rem;font-weight:600;margin-left:13px">{valor}</span>'
        f'{det}</div>'
    )


def render_novedades(s, e):
    df_d = load_instrucciones_cmg(s, e)
    df_s = load_sscc(s, e)

    st.markdown('<div class="sec">Novedades por unidad · estado actual</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for col, u in zip(cols, UNIDADES):
        c = COLORES[u]["line"]
        filas = []

        # última consigna de despacho
        du = df_d[df_d["unidad"] == u] if not df_d.empty else pd.DataFrame()
        if not du.empty:
            row = du.iloc[0]
            desp = f"{float(row['despacho']):.0f} MW" if pd.notna(row["despacho"]) else "—"
            consigna = str(row.get("consigna") or "").strip() or "—"
            fh = str(row["fecha_hora"])[:16]
            motivo = str(row.get("motivo") or "").strip()
            filas.append(_fila(c, "Despacho", f"{desp} · consigna {consigna}",
                               f"{fh}" + (f" — {motivo[:60]}" if motivo else "")))
        else:
            filas.append(_fila("#CBD5E1", "Despacho", "Sin datos"))

        # última instrucción SSCC — mismo orden que la primera fila (palpitante)
        # de la sección SSCC: fecha desc, inicio_periodo desc.
        su = df_s[df_s["unidad"] == u] if not df_s.empty else pd.DataFrame()
        if not su.empty:
            su = su.sort_values(["fecha", "inicio_periodo"], ascending=[False, False])
            row = su.iloc[0]
            tipo = str(row["instruccion_sscc"])
            ini = str(row["inicio_periodo"])[:5] if row.get("inicio_periodo") else "—"
            fin = str(row["fin_periodo"])[:5] if row.get("fin_periodo") else "—"
            filas.append(_fila("#0EA5E9", "SSCC", tipo, f"{row['fecha']} · {ini}→{fin}"))
        else:
            filas.append(_fila("#CBD5E1", "SSCC", "Sin instrucciones"))

        with col:
            st.markdown(
                f'<div style="border:1px solid {c}33;border-top:3px solid {c};border-radius:8px;'
                f'padding:10px 12px;background:#FFFFFF;height:100%">'
                f'<div style="font-weight:700;color:{c};font-size:0.84rem;margin-bottom:4px">{LABELS[u]}</div>'
                + "".join(filas) + '</div>',
                unsafe_allow_html=True)
