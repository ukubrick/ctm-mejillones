"""components/bitacora_auto.py — Bitácora automática de movimientos por unidad.

Se sitúa bajo la serie de CMG (vista Resumen) y consolida en una sola tabla
cronológica los movimientos relevantes de las 4 unidades:
  · Instrucciones SSCC (Operaciones)
  · Instrucciones de despacho por CMG (a las centrales)
  · Limitaciones de transmisión que generan trip / derrateo de unidad

A diferencia de «Novedades» (estado actual de un vistazo), la bitácora es un
registro histórico con fecha (dd-mm-aaaa) y hora exacta + descripción. Si no
hay limitaciones activas, lo declara explícitamente.
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from config import COLORES, LABELS, ID_UNIDAD_LABEL
from utils.data import load_sscc, load_instrucciones_cmg, load_limitaciones


# Paleta por tipo de evento (badge de la columna «Tipo»)
_TIPO_COLOR = {
    "SSCC":       ("#0EA5E9", "#E0F2FE"),
    "Despacho":   ("#3D53E8", "#E2E7FD"),
    "Limitación": ("#DC2626", "#FEE2E2"),
}


def _dt(fecha, hora=None):
    """Combina fecha (+ hora opcional 'HH:MM[:SS]') en un Timestamp; NaT si falla."""
    try:
        if hora:
            return pd.to_datetime(f"{str(fecha)[:10]} {str(hora)[:8]}", errors="coerce")
        return pd.to_datetime(fecha, errors="coerce")
    except Exception:
        return pd.NaT


def _eventos_sscc(df, eventos):
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        u = r.get("unidad")
        if u not in LABELS:
            continue
        dt = _dt(r.get("fecha"), r.get("inicio_periodo"))
        tipo = str(r.get("instruccion_sscc") or "SSCC").strip()
        ini = str(r.get("inicio_periodo"))[:5] if r.get("inicio_periodo") else "—"
        fin = str(r.get("fin_periodo"))[:5] if r.get("fin_periodo") else "—"
        motivo = str(r.get("motivo") or "").strip()
        desc = f"Instrucción SSCC · <b>{tipo}</b> ({ini}→{fin})"
        if motivo:
            desc += f" — {motivo[:80]}"
        eventos.append({"dt": dt, "unidad": u, "tipo": "SSCC", "desc": desc})


def _eventos_despacho(df, eventos):
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        u = r.get("unidad")
        if u not in LABELS:
            continue
        dt = _dt(r.get("fecha_hora"))
        desp = f"{float(r['despacho']):.0f} MW" if pd.notna(r.get("despacho")) else "—"
        consigna = str(r.get("consigna") or "").strip() or "—"
        motivo = str(r.get("motivo") or "").strip()
        desc = f"Instrucción de despacho CMG · <b>{desp}</b> · consigna {consigna}"
        if motivo:
            desc += f" — {motivo[:80]}"
        eventos.append({"dt": dt, "unidad": u, "tipo": "Despacho", "desc": desc})


def _eventos_limitaciones(df, eventos):
    """Solo limitaciones que afectan a una unidad y provocan trip o derrateo."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        idu = r.get("id_unidad")
        u = ID_UNIDAD_LABEL.get(int(float(idu))) if pd.notna(idu) else None
        if u not in LABELS:
            continue
        dt = _dt(r.get("fecha_perturbacion"))
        pot = r.get("potencia")
        um = str(r.get("unidad_medida_potencia") or "MW")
        status = str(r.get("status") or "").strip()
        instal = str(r.get("instalacion_nombre") or "").split(" - ")[0]
        # potencia limitada > 0 → derrateo parcial; 0/ausente → desconexión (trip)
        if pd.notna(pot) and float(pot) > 0:
            efecto = f"Derrateo a <b>{float(pot):.0f} {um}</b>"
        else:
            efecto = "<b>Trip / desconexión</b>"
        estado_txt = f" · {status}" if status else ""
        desc = f"Limitación de transmisión · {efecto} — {instal}{estado_txt}"
        eventos.append({"dt": dt, "unidad": u, "tipo": "Limitación", "desc": desc})


def _fila_html(ev):
    tc, tb = _TIPO_COLOR.get(ev["tipo"], ("#475569", "#F1F5F9"))
    fh = ev["dt"].strftime("%d-%m-%Y %H:%M") if pd.notna(ev["dt"]) else "—"
    return (
        "<tr>"
        f'<td style="padding:7px 12px;font-size:0.74rem;color:#334155;'
        f'font-variant-numeric:tabular-nums;white-space:nowrap;border-bottom:1px solid #F1F5F9">{fh}</td>'
        f'<td style="padding:7px 12px;border-bottom:1px solid #F1F5F9;white-space:nowrap">'
        f'<span style="background:{tb};color:{tc};font-weight:600;font-size:0.68rem;'
        f'padding:2px 8px;border-radius:5px">{ev["tipo"]}</span></td>'
        f'<td style="padding:7px 12px;font-size:0.76rem;color:#475569;'
        f'border-bottom:1px solid #F1F5F9">{ev["desc"]}</td>'
        "</tr>"
    )


def render_bitacora_auto(s, e, unidad):
    """Bitácora de la unidad activa (botón de la serie). Muestra por defecto solo
    el día anterior; un selector permite elegir otro día dentro del período."""
    if unidad not in LABELS:
        return

    c = COLORES.get(unidad, {}).get("line", "#64748B")
    st.markdown(
        f'<div class="sec">Bitácora automática · '
        f'<span style="color:{c}">{LABELS[unidad]}</span></div>',
        unsafe_allow_html=True)

    df_s = load_sscc(s, e)
    df_d = load_instrucciones_cmg(s, e)
    df_l = load_limitaciones(s, e)

    # ── Consolidación cronológica de eventos (solo la unidad activa) ────────────
    todos = []
    _eventos_sscc(df_s, todos)
    _eventos_despacho(df_d, todos)
    _eventos_limitaciones(df_l, todos)
    eventos_u = [ev for ev in todos if ev["unidad"] == unidad and pd.notna(ev["dt"])]

    # ── Selector de día: por defecto el día anterior (ayer) ─────────────────────
    dias = sorted({ev["dt"].date() for ev in eventos_u}, reverse=True)
    ayer = date.today() - timedelta(days=1)
    if ayer in dias:
        idx_def = dias.index(ayer)
    elif dias:
        # si ayer no tiene movimientos, cae al día con datos más cercano y anterior
        previos = [d for d in dias if d <= ayer]
        idx_def = dias.index(previos[0]) if previos else 0
    else:
        idx_def = 0

    if dias:
        col_sel, _ = st.columns([1, 2])
        with col_sel:
            dia = st.selectbox(
                "Día", dias, index=idx_def,
                format_func=lambda d: d.strftime("%d-%m-%Y")
                + (" · ayer" if d == ayer else ""),
                key=f"bit_dia_{unidad}")
    else:
        dia = ayer

    eventos = sorted([ev for ev in eventos_u if ev["dt"].date() == dia],
                     key=lambda ev: ev["dt"], reverse=True)

    # ── Estado de limitaciones activas de la unidad ese día ─────────────────────
    lim_activas = pd.DataFrame()
    if df_l is not None and not df_l.empty:
        dia_ts = pd.Timestamp(dia)
        es_unidad = df_l["id_unidad"].apply(
            lambda x: pd.notna(x) and ID_UNIDAD_LABEL.get(int(float(x))) == unidad)
        pert = pd.to_datetime(df_l["fecha_perturbacion"], errors="coerce")
        ret_col = (df_l["fecha_efectiva_retorno"] if "fecha_efectiva_retorno" in df_l.columns
                   else pd.Series(pd.NaT, index=df_l.index))
        retorno = pd.to_datetime(ret_col, errors="coerce")
        activa_dia = pert.dt.normalize() <= dia_ts
        sigue = retorno.isna() | (retorno.dt.normalize() >= dia_ts)
        lim_activas = df_l[es_unidad & activa_dia & sigue]

    if lim_activas.empty:
        st.markdown(
            '<div style="background:#ECFDF5;border:1px solid #A7F3D0;border-left:4px solid #22A95B;'
            'border-radius:8px;padding:8px 14px;margin:2px 0 10px;color:#166534;font-size:0.82rem;'
            'font-weight:600">Sin limitaciones activas</div>',
            unsafe_allow_html=True)
    else:
        chips = "".join(
            f'<span style="background:#FEE2E2;color:#B91C1C;font-weight:700;font-size:0.72rem;'
            f'padding:2px 9px;border-radius:5px;margin-right:6px">'
            f'{str(r.get("instalacion_nombre") or "").split(" - ")[0]}: '
            f'{(str(int(float(r["potencia"]))) + " MW") if pd.notna(r["potencia"]) and float(r["potencia"]) > 0 else "trip"}'
            f'</span>'
            for _, r in lim_activas.iterrows())
        st.markdown(
            '<div style="background:#FEF2F2;border:1px solid #FECACA;border-left:4px solid #DC2626;'
            'border-radius:8px;padding:8px 14px;margin:2px 0 10px;color:#991B1B;font-size:0.82rem">'
            f'<b>{len(lim_activas)} limitación(es) activa(s):</b> {chips}</div>',
            unsafe_allow_html=True)

    # ── Tabla del día ───────────────────────────────────────────────────────────
    if not eventos:
        st.caption(f"Sin movimientos registrados para {LABELS[unidad]} el {dia.strftime('%d-%m-%Y')}.")
        return

    filas = "".join(_fila_html(ev) for ev in eventos)
    hdr = "".join(
        f'<th style="padding:8px 12px;text-align:left;font-size:0.66rem;color:#64748B;'
        f'text-transform:uppercase;letter-spacing:0.4px;border-bottom:2px solid #E2E8F0;'
        f'white-space:nowrap">{h}</th>'
        for h in ("Fecha y hora", "Tipo", "Descripción"))
    st.markdown(
        '<div style="border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;background:#FFFFFF">'
        '<div style="overflow-x:auto"><table style="border-collapse:collapse;width:100%">'
        f'<thead style="background:#F8FAFC"><tr>{hdr}</tr></thead>'
        f'<tbody>{filas}</tbody></table></div></div>',
        unsafe_allow_html=True)
