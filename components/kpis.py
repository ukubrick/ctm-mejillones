"""components/kpis.py — Estado actual por unidad: último dato de potencia, régimen
operacional (plena carga / mínimo técnico / rampa / detenida), factor de planta
del período y alarma de trip cruzada con las limitaciones VIGENTES (regla 47)."""
import pandas as pd
import streamlit as st

from config import (COLORES, LABELS, PMAX, POT_MIN_TECNICA, UNIDADES,
                    ID_UNIDAD_LABEL)
from utils.eventos import limitaciones_vigentes
from utils.plotly_theme import TZ_CHILE

# Umbral (MW) bajo el cual se considera unidad detenida / desenganchada (trip).
# < 5 MW en la práctica ya indica potencia 0 (unidad desenganchada) — regla 23.
UMBRAL_TRIP = 5.0
# Margen sobre el mínimo técnico dentro del cual se considera "en mínimo técnico".
MARGEN_MIN_TEC_MW = 8.0
# Fracción de Pmax a partir de la cual se considera "plena carga".
FRAC_PLENA_CARGA = 0.95
# Variación total (MW) en las últimas ~2 horas para declarar una rampa.
RAMPA_MIN_MW = 12.0
# Variación de la ÚLTIMA hora que confirma que la maniobra sigue en curso.
PASO_VIVO_MW = 3.0
# Horas de antigüedad del último dato a partir de las cuales se avisa (rezago
# normal del CEN en gen-real: ~4,6 h — regla 55).
REZAGO_AVISO_H = 7.0

# unidad → id_unidad de la API CEN (inverso de ID_UNIDAD_LABEL)
_UNIDAD_A_ID = {v: k for k, v in ID_UNIDAD_LABEL.items()}

# régimen → (etiqueta, color de texto, color de fondo)
_ESTILO_REGIMEN = {
    "detenida":     ("Detenida",       "#991B1B", "#FEE2E2"),
    "plena":        ("Plena carga",    "#065F46", "#D1FAE5"),
    "minimo":       ("Mínimo técnico", "#92400E", "#FEF3C7"),
    "subiendo":     ("Subiendo carga", "#1E3A8A", "#DBEAFE"),
    "bajando":      ("Bajando carga",  "#5B21B6", "#EDE9FE"),
    "parcial":      ("Carga parcial",  "#0E7490", "#CFFAFE"),
}


def _limitacion_activa(df_lim, unidad):
    """Limitación REALMENTE vigente de la unidad (por ventana, no por `status`).

    El CEN nunca cierra el registro, así que filtrar por `status == 'pendiente'`
    declaraba activas limitaciones muertas hace meses (regla 47).
    """
    if df_lim is None or df_lim.empty or "id_unidad" not in df_lim.columns:
        return None
    try:
        d = limitaciones_vigentes(df_lim)
    except Exception:
        return None
    if d is None or d.empty:
        return None
    d = d[d["_unidad"] == unidad]
    if d.empty:
        return None
    return d.sort_values("_ini", ascending=False).iloc[0]


def _regimen(serie_mw, unidad):
    """Clasifica el punto de operación actual de la unidad.

    Devuelve (clave de régimen, rampa MW en la ventana observada).
    `serie_mw` viene ordenada cronológicamente; el último valor es el actual.
    """
    ult = float(serie_mw.iloc[-1])
    pmax = PMAX.get(unidad, 0) or 0
    pmin = POT_MIN_TECNICA.get(unidad, 0) or 0

    # Rampa sobre las últimas ~2 horas (3 registros): un solo par de puntos
    # confunde el ruido SCADA con una maniobra de carga.
    ventana = serie_mw.tail(3).astype(float)
    rampa = float(ventana.iloc[-1] - ventana.iloc[0]) if len(ventana) > 1 else 0.0
    ultimo_paso = float(ventana.iloc[-1] - ventana.iloc[-2]) if len(ventana) > 1 else 0.0

    if ult < UMBRAL_TRIP:
        return "detenida", rampa
    # Una rampa manda sobre el nivel: la unidad está EN MANIOBRA, no estabilizada.
    # Pero solo si la maniobra SIGUE EN CURSO: una unidad que bajó hace dos horas
    # y ya se estabilizó en su mínimo técnico está en mínimo técnico, no bajando.
    en_curso = abs(ultimo_paso) >= PASO_VIVO_MW and (ultimo_paso * rampa) > 0
    if abs(rampa) >= RAMPA_MIN_MW and en_curso:
        return ("subiendo" if rampa > 0 else "bajando"), rampa
    if pmax and ult >= FRAC_PLENA_CARGA * pmax:
        return "plena", rampa
    if pmin and ult <= pmin + MARGEN_MIN_TEC_MW:
        return "minimo", rampa
    return "parcial", rampa


def _factor_planta(df_u, unidad, horas_periodo):
    """FP correcto = energía generada / (Pmax × horas del PERÍODO).

    El promedio simple de `gen_real_mw` sobrestima el FP cuando faltan horas en
    la serie: una unidad con 6 h de dato a 270 MW no tiene 97% de FP en una
    semana. Devuelve (fp %, energía MWh, cobertura de datos %).
    """
    pmax = PMAX.get(unidad, 0) or 0
    energia = float(df_u["gen_real_mw"].sum())          # malla horaria → MWh
    horas_dato = len(df_u)
    cobertura = horas_dato / horas_periodo * 100 if horas_periodo else 0.0
    fp = energia / (pmax * horas_periodo) * 100 if (pmax and horas_periodo) else 0.0
    return fp, energia, cobertura


def _horas_periodo(df_r):
    """Horas del período analizado, medidas sobre la malla horaria del complejo."""
    if df_r.empty:
        return 0
    fh = pd.to_datetime(df_r["fecha_hora"], errors="coerce").dropna()
    if fh.empty:
        return 0
    return int((fh.max() - fh.min()).total_seconds() // 3600) + 1


def _antiguedad(ts):
    """Texto de antigüedad del último dato, en hora de Chile (nunca UTC)."""
    ts = pd.to_datetime(ts, errors="coerce")
    if pd.isna(ts):
        return "—", 0.0
    ahora = pd.Timestamp.now(tz=TZ_CHILE).tz_localize(None)
    h = (ahora - ts).total_seconds() / 3600
    if h < 0:
        return "en línea", 0.0
    if h < 1:
        return f"hace {int(h * 60)} min", h
    if h < 48:
        return f"hace {h:.1f} h", h
    return f"hace {h / 24:.1f} d", h


def _fmt_energia(mwh):
    return f"{mwh / 1000:.1f} GWh" if mwh >= 1000 else f"{mwh:.0f} MWh"


def render_kpis(df_r, df_lim=None):
    horas_periodo = _horas_periodo(df_r)
    st.markdown(
        '<div class="sec">Estado actual por unidad'
        '<span class="sec-sub">Último dato de potencia y régimen de operación · '
        f'factor de planta sobre las {horas_periodo} h del período</span></div>',
        unsafe_allow_html=True,
    )

    # ── Detección de trips (último dato bajo el umbral) + cruce con limitaciones ─
    trips = []
    for u in UNIDADES:
        df_u = df_r[df_r["unidad"] == u]
        if not df_u.empty:
            ult = df_u.sort_values("fecha_hora").iloc[-1]
            if float(ult["gen_real_mw"]) < UMBRAL_TRIP:
                trips.append((u, str(ult["fecha_hora"])[:16]))
    if trips:
        partes = []
        for u, fh in trips:
            lim = _limitacion_activa(df_lim, u)
            if lim is not None:
                corr = lim.get("correlativo")
                corr = f"N°{int(float(corr))}" if pd.notna(corr) else "s/correlativo"
                fin = lim.get("_fin")
                fin = str(fin)[:16] if pd.notna(fin) else "—"
                partes.append(
                    f'<b>{LABELS[u]}</b> detenida ({fh}) → <span style="color:#92400E">'
                    f'limitación vigente {corr}, ventana hasta {fin}</span> (baja programada)')
            else:
                partes.append(
                    f'<b>{LABELS[u]}</b> detenida ({fh}) → '
                    f'<span style="color:#991B1B">sin limitación vigente registrada — '
                    f'posible TRIP/desenganche</span>')
        st.markdown(
            f'<div class="alarm-trip"><span class="dot-status dot-r" style="animation:blink 1s infinite"></span>'
            f'<b>ALARMA · UNIDAD DETENIDA (&lt; {UMBRAL_TRIP:.0f} MW)</b><br>' + "<br>".join(partes) + '</div>',
            unsafe_allow_html=True,
        )

    trip_units = {u for u, _ in trips}
    cols = st.columns(4)
    for i, u in enumerate(UNIDADES):
        with cols[i]:
            df_u = df_r[df_r["unidad"] == u].sort_values("fecha_hora")
            badge = (f'<div class="kpi-badge" style="background:{COLORES[u]["badge"]};'
                     f'color:{COLORES[u]["text"]}">{LABELS[u]}</div>')
            if df_u.empty:
                st.markdown(
                    f'<div class="kpi" style="border-top:4px solid #CBD5E1">{badge}'
                    f'<div class="kpi-val">—<span class="kpi-mw"> MW</span></div>'
                    f'<div class="kpi-sub">Sin datos en el período</div></div>',
                    unsafe_allow_html=True,
                )
                continue

            pmax = PMAX.get(u, 0) or 0
            ult = df_u.iloc[-1]
            ult_mw = float(ult["gen_real_mw"])
            ult_fh = str(ult["fecha_hora"])[:16]
            edad_txt, edad_h = _antiguedad(ult["fecha_hora"])
            carga = ult_mw / pmax * 100 if pmax else 0.0

            reg, rampa = _regimen(df_u["gen_real_mw"], u)
            etiq, c_txt, c_bg = _ESTILO_REGIMEN[reg]
            fp, energia, cobertura = _factor_planta(df_u, u, horas_periodo)

            # Variación real contra el registro ANTERIOR (antes decía "vs última
            # hora" pero comparaba contra el promedio del período).
            if len(df_u) > 1:
                prev = float(df_u["gen_real_mw"].iloc[-2])
                delta = ult_mw - prev
                sym = "▲" if delta > 0 else ("▼" if delta < 0 else "=")
                col_d = "#059669" if delta > 0 else ("#DC2626" if delta < 0 else "#64748B")
                var_txt = (f'<span style="color:{col_d};font-weight:700">{sym} {abs(delta):.1f} MW</span>'
                           f'<span style="color:#94A3B8"> vs hora anterior</span>')
            else:
                var_txt = '<span style="color:#94A3B8">Sin hora previa para comparar</span>'

            borde = "#EF4444" if u in trip_units else COLORES[u]["line"]
            pct_barra = max(0.0, min(100.0, carga))
            barra = (
                f'<div class="kpi-bar"><div class="kpi-bar-fill" '
                f'style="width:{pct_barra:.1f}%;background:{COLORES[u]["line"]}"></div></div>'
                f'<div class="kpi-bar-lbl"><span>{carga:.0f}% de Pmax</span>'
                f'<span>{pmax:.0f} MW</span></div>'
            )
            pill_cls = "kpi-pill badge-pend" if reg == "detenida" else "kpi-pill"
            aviso = ("" if edad_h < REZAGO_AVISO_H else
                     ' <span style="color:#B45309;font-weight:600">· dato atrasado</span>')
            nota_cob = ("" if cobertura >= 95 else
                        f' <span style="color:#B45309">· cobertura {cobertura:.0f}%</span>')

            st.markdown(f"""<div class="kpi" style="border-top:4px solid {borde}">
                {badge}
                <div class="kpi-val">{ult_mw:.1f}<span class="kpi-mw"> MW</span></div>
                <div class="{pill_cls}" style="color:{c_txt};background:{c_bg}">{etiq}</div>
                {barra}
                <div class="kpi-delta">{var_txt}</div>
                <div class="kpi-row"><span>Factor de planta</span>
                    <b>{fp:.1f}%</b></div>
                <div class="kpi-row"><span>Energía del período</span>
                    <b>{_fmt_energia(energia)}</b></div>
                <div class="kpi-foot">Último dato {ult_fh} · {edad_txt}{aviso}{nota_cob}</div>
            </div>""", unsafe_allow_html=True)
