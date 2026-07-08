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

from config import COLORES, LABELS, ID_UNIDAD_LABEL, UNIDADES
from utils.data import (load_sscc, load_instrucciones_cmg, load_limitaciones,
                        load_bit, load_solicitudes, load_mantenimiento_mayor)


# Paleta por tipo de evento (badge de la columna «Tipo»)
_TIPO_COLOR = {
    "SSCC":          ("#0EA5E9", "#E0F2FE"),
    "Despacho":      ("#3D53E8", "#E2E7FD"),
    "Limitación":    ("#DC2626", "#FEE2E2"),
    "Novedad":       ("#7C3AED", "#EDE9FE"),
    "Solicitud":     ("#0F766E", "#CCFBF1"),
    "Mantenimiento": ("#D97706", "#FEF3C7"),
}

# Palabra clave de la solicitud → unidades del complejo a las que aplica.
_SOLIC_UNIDADES = {"ANGAMOS": ("ANG1", "ANG2"), "COCHRANE": ("CCR1", "CCR2")}


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


def _eventos_bitacora(df, eventos):
    """Novedades ingresadas manualmente (tabla bitacora) → aparecen automáticamente
    en la bitácora con su fecha y hora exactas."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        u = r.get("unidad")
        if u not in LABELS:
            continue
        dt = _dt(r.get("fecha"), r.get("hora"))
        com = str(r.get("comentario") or "").strip()
        autor = str(r.get("autor") or "").strip()
        desc = f"Novedad · {com}"
        if autor:
            desc += f" <span style='color:#94A3B8'>— {autor}</span>"
        eventos.append({"dt": dt, "unidad": u, "tipo": "Novedad", "desc": desc})


def _eventos_solicitudes(df, eventos):
    """Solicitudes de trabajo que mencionan Angamos o Cochrane → se asignan a las
    dos unidades de esa central (Angamos = ANG1/ANG2; Cochrane = CCR1/CCR2)."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        instal = str(r.get("instalacion_nombre") or "").strip()
        empresa = str(r.get("empresa_nombre") or "").strip()
        texto = f"{instal} {empresa}".upper()
        unidades = set()
        for clave, us in _SOLIC_UNIDADES.items():
            if clave in texto:
                unidades.update(us)
        if not unidades:
            continue
        dt = _dt(r.get("fecha_inicio"))
        tipo_sol = str(r.get("tipo_solicitud") or r.get("type") or "").strip()
        status = str(r.get("status") or "").strip()
        fin = _dt(r.get("fecha_fin"))
        rango = ""
        if pd.notna(dt) and pd.notna(fin):
            rango = f" ({dt.strftime('%d-%m')}→{fin.strftime('%d-%m')})"
        nombre = instal or empresa or "solicitud"
        desc = f"Solicitud de trabajo · <b>{nombre[:60]}</b>{rango}"
        detalle = " · ".join(x for x in (tipo_sol, status) if x)
        if detalle:
            desc += f" — {detalle[:80]}"
        for u in unidades:
            eventos.append({"dt": dt, "unidad": u, "tipo": "Solicitud", "desc": desc})


def _eventos_mantenimiento(df, eventos):
    """Programas de mantenimiento mayor: si mencionan Angamos/Cochrane se asignan
    a esa central; si afectan el corredor de evacuación (Mejillones, O'Higgins,
    Laberinto, Kapatur, Crucero) aplican a las 4 unidades. Anclados al inicio
    del programa."""
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        texto = " ".join(str(r.get(c) or "") for c in
                         ("nombre_instalacion", "nombre_sub_instalacion")).upper()
        unidades = set()
        for clave, us in _SOLIC_UNIDADES.items():
            if clave in texto:
                unidades.update(us)
        if not unidades:
            unidades = set(UNIDADES)   # corredor de evacuación → afecta a todas
        dt = r.get("fecha_inicio_programa_dt")
        fin = r.get("fecha_fin_programa_dt")
        rango = ""
        if pd.notna(dt) and pd.notna(fin):
            rango = f" ({dt.strftime('%d-%m')}→{fin.strftime('%d-%m')})"
        nombre = str(r.get("nombre_instalacion") or "programa")[:60]
        estado = str(r.get("estado") or "").strip()
        desc = f"Mantenimiento mayor · <b>{nombre}</b>{rango}"
        if estado:
            desc += f" — {estado}"
        for u in unidades:
            eventos.append({"dt": dt, "unidad": u, "tipo": "Mantenimiento", "desc": desc})


def _fila_html(ev):
    tc, tb = _TIPO_COLOR.get(ev["tipo"], ("#475569", "#F1F5F9"))
    fh = ev["dt"].strftime("%d-%m-%Y %H:%M") if pd.notna(ev["dt"]) else "—"
    # Las limitaciones (trip / derrateo) se resaltan en rojo en toda la fila.
    es_lim = ev["tipo"] == "Limitación"
    row_bg = "background:#FEF2F2;" if es_lim else ""
    desc_color = "#B91C1C" if es_lim else "#475569"
    desc_weight = "font-weight:600;" if es_lim else ""
    return (
        f'<tr style="{row_bg}">'
        f'<td style="padding:7px 12px;font-size:0.74rem;color:{"#B91C1C" if es_lim else "#334155"};'
        f'font-variant-numeric:tabular-nums;white-space:nowrap;border-bottom:1px solid #F1F5F9">{fh}</td>'
        f'<td style="padding:7px 12px;border-bottom:1px solid #F1F5F9;white-space:nowrap">'
        f'<span style="background:{tb};color:{tc};font-weight:600;font-size:0.68rem;'
        f'padding:2px 8px;border-radius:5px">{ev["tipo"]}</span></td>'
        f'<td style="padding:7px 12px;font-size:0.76rem;color:{desc_color};{desc_weight}'
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
    df_b = load_bit(s, e, unidad)
    df_sol = load_solicitudes(s, e)
    df_mant = load_mantenimiento_mayor()

    # ── Consolidación cronológica de eventos (solo la unidad activa) ────────────
    todos = []
    _eventos_sscc(df_s, todos)
    _eventos_despacho(df_d, todos)
    _eventos_limitaciones(df_l, todos)
    _eventos_bitacora(df_b, todos)
    _eventos_solicitudes(df_sol, todos)
    _eventos_mantenimiento(df_mant, todos)
    eventos_u = [ev for ev in todos if ev["unidad"] == unidad and pd.notna(ev["dt"])]

    # ── Selector de día: TODOS los días del período (sin saltos), ayer por defecto ──
    try:
        d_ini = pd.to_datetime(s).date()
        d_fin = pd.to_datetime(e).date()
    except Exception:
        d_fin = date.today()
        d_ini = d_fin - timedelta(days=7)
    n_dias = (d_fin - d_ini).days
    dias = [d_fin - timedelta(days=i) for i in range(n_dias + 1)]  # descendente, continuo
    ayer = date.today() - timedelta(days=1)
    idx_def = dias.index(ayer) if ayer in dias else 0

    col_sel, _ = st.columns([1, 2])
    with col_sel:
        dia = st.selectbox(
            "Día", dias, index=idx_def,
            format_func=lambda d: d.strftime("%d-%m-%Y") + (" · ayer" if d == ayer else ""),
            key=f"bit_dia_{unidad}")

    eventos = sorted([ev for ev in eventos_u if ev["dt"].date() == dia],
                     key=lambda ev: ev["dt"], reverse=True)

    # Nota verde solo si ese día no se generó ninguna limitación para la unidad.
    hay_limitacion = any(ev["tipo"] == "Limitación" for ev in eventos)
    if not hay_limitacion:
        st.markdown(
            '<div style="background:#ECFDF5;border:1px solid #A7F3D0;border-left:4px solid #22A95B;'
            'border-radius:8px;padding:8px 14px;margin:2px 0 10px;color:#166534;font-size:0.82rem;'
            'font-weight:600">Sin limitaciones activas</div>',
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
