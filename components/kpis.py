"""components/kpis.py — Tarjetas KPI de generación real por unidad + alarmas de trip."""
import pandas as pd
import streamlit as st

from config import COLORES, LABELS, PMAX, UNIDADES, ID_UNIDAD_LABEL

# Umbral (MW) bajo el cual se considera unidad detenida / desenganchada (trip)
UMBRAL_TRIP = 1.0
# unidad → id_unidad de la API CEN (inverso de ID_UNIDAD_LABEL)
_UNIDAD_A_ID = {v: k for k, v in ID_UNIDAD_LABEL.items()}


def _limitacion_activa(df_lim, unidad):
    """Devuelve la limitación pendiente más reciente de la unidad, o None."""
    if df_lim is None or df_lim.empty or "id_unidad" not in df_lim.columns:
        return None
    idu = _UNIDAD_A_ID.get(unidad)
    if idu is None:
        return None
    d = df_lim[df_lim["status"] == "pendiente"].copy()
    if d.empty:
        return None
    d["_idu"] = d["id_unidad"].apply(lambda x: int(float(x)) if pd.notna(x) else -1)
    d = d[d["_idu"] == idu].sort_values("fecha_perturbacion", ascending=False)
    return d.iloc[0] if not d.empty else None


def render_kpis(df_r, df_lim=None):
    st.markdown('<div class="sec">Generación real · promedio del período</div>', unsafe_allow_html=True)

    # ── Detección de trips (último dato en 0) + cruce con limitaciones ───────
    trips = []
    for u in UNIDADES:
        df_u = df_r[df_r["unidad"] == u]
        if not df_u.empty:
            ult = df_u.sort_values("fecha_hora").iloc[-1]
            if float(ult["gen_real_mw"]) <= UMBRAL_TRIP:
                trips.append((u, str(ult["fecha_hora"])[:16]))
    if trips:
        partes = []
        for u, fh in trips:
            lim = _limitacion_activa(df_lim, u)
            if lim is not None:
                corr = lim.get("correlativo")
                corr = f"N°{int(float(corr))}" if pd.notna(corr) else "s/correlativo"
                ret = lim.get("fecha_retorno_estimada") or lim.get("fecha_efectiva_retorno")
                ret = str(ret)[:16] if ret and str(ret) not in ("NaT", "None", "nan") else "—"
                partes.append(
                    f'<b>{LABELS[u]}</b> en 0 MW ({fh}) → <span style="color:#92400E">'
                    f'limitación activa {corr}, retorno est. {ret}</span> (baja programada)')
            else:
                partes.append(
                    f'<b>{LABELS[u]}</b> en 0 MW ({fh}) → '
                    f'<span style="color:#991B1B">sin limitación registrada — posible TRIP/desenganche</span>')
        st.markdown(
            f'<div class="alarm-trip"><span class="dot-status dot-r" style="animation:blink 1s infinite"></span>'
            f'<b>ALARMA · GENERACIÓN EN 0</b><br>' + "<br>".join(partes) + '</div>',
            unsafe_allow_html=True,
        )

    trip_units = {u for u, _ in trips}
    cols = st.columns(4)
    for i, u in enumerate(UNIDADES):
        with cols[i]:
            df_u = df_r[df_r["unidad"] == u]
            if df_u.empty:
                st.markdown(
                    f'<div class="kpi" style="border-top:4px solid {COLORES[u]["line"]}">'
                    f'<div class="kpi-badge" style="background:{COLORES[u]["badge"]};color:{COLORES[u]["text"]}">{LABELS[u]}</div>'
                    f'<div class="kpi-val">—</div></div>',
                    unsafe_allow_html=True,
                )
                continue
            prom = df_u["gen_real_mw"].mean()
            pmax = PMAX.get(u, 0)
            fp   = prom / pmax * 100 if pmax else 0
            ult  = df_u.sort_values("fecha_hora").iloc[-1]
            ult_mw, ult_fh = ult["gen_real_mw"], str(ult["fecha_hora"])[:16]
            delta = ult_mw - prom
            sym   = "▲" if delta >= 0 else "▼"
            col_d = "#10B981" if delta >= 0 else "#EF4444"
            es_trip = u in trip_units
            borde = "#EF4444" if es_trip else COLORES[u]["line"]
            estado = (
                '<div class="kpi-delta badge-pend" style="color:#fff;background:#EF4444;'
                'display:inline-block;padding:2px 8px;border-radius:5px">⚠ TRIP · 0 MW</div>'
                if es_trip else
                f'<div class="kpi-delta" style="color:{col_d}">{sym} {abs(delta):.1f} MW vs última hora</div>'
            )
            st.markdown(f"""<div class="kpi" style="border-top:4px solid {borde}">
                <div class="kpi-badge" style="background:{COLORES[u]['badge']};color:{COLORES[u]['text']}">{LABELS[u]}</div>
                <div class="kpi-val">{prom:.1f}<span class="kpi-mw"> MW</span></div>
                <div class="kpi-sub">Factor de planta {fp:.0f}% <span style="color:#9CA3AF;font-size:0.68rem">(promedio período)</span></div>
                {estado}
                <div style="font-size:0.68rem;color:#9CA3AF;margin-top:3px">Último dato: {ult_fh}</div>
            </div>""", unsafe_allow_html=True)
