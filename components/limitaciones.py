"""components/limitaciones.py — Limitaciones de transmisión ANG/CCR (cards + estadísticas)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import (ID_UNIDAD_LABEL, ID_CENTRAL_LABEL, LABELS, STATUS_COLOR_LIM,
                    UNIDADES)
from utils.data import load_instrucciones_cmg, load_limitaciones
from utils.eventos import eventos_desde_instrucciones, preparar_limitaciones
from components._common import render_kpi_grid

MAX_CARDS = 5


# Presentación del estado REAL (ventana), no del `status` de papel del CEN.
_ESTADO_VIS = {
    "activa":  ("VIGENTE",         "#991B1B", "#FEE2E2"),
    "vencida": ("CERRADA DE FACTO", "#475569", "#F1F5F9"),
    "cerrada": ("CERRADA",          "#166534", "#DCFCE7"),
    "futura":  ("PROGRAMADA",       "#5B21B6", "#EDE9FE"),
}

_ORIGEN_TXT = {
    "efectivo": "cierre real informado por el CEN",
    "estimado": "el CEN nunca emitió el cierre → se usa el retorno estimado",
    "supuesto": "sin retorno declarado → ventana supuesta de 7 días",
    "tope":     "registro abierto sin fecha creíble → ventana topeada a 30 días",
}


def _card_html(row):
    estado = row.get("_estado", "")
    if estado in _ESTADO_VIS:
        badge_txt, c_txt, c_bg = _ESTADO_VIS[estado]
        st_key = "pendiente" if estado == "activa" else estado
    else:
        st_key = str(row.get("status", "")).lower()
        c_txt, c_bg = STATUS_COLOR_LIM.get(st_key, ("#475569", "#F8FAFC"))
        badge_txt = str(row.get("status", ""))
    id_u = int(float(row["id_unidad"])) if pd.notna(row.get("id_unidad")) else -1
    id_c = int(float(row["id_central"])) if pd.notna(row.get("id_central")) else -1
    unidad_lbl  = ID_UNIDAD_LABEL.get(id_u, "")
    central_lbl = ID_CENTRAL_LABEL.get(id_c, str(row.get("instalacion_nombre", "")).split(" - ")[0])
    fecha_pert  = str(row.get("fecha_perturbacion") or "")[:16]
    ret_ef, ret_est = row.get("fecha_efectiva_retorno"), row.get("fecha_retorno_estimada")
    es_efectivo = ret_ef and str(ret_ef) not in ("NaT", "None", "nan", "")
    retorno_val = ret_ef if es_efectivo else ret_est
    fecha_ret = str(retorno_val)[:16] if (retorno_val and str(retorno_val) not in ("NaT", "None", "nan", "")) else "—"
    ret_label = "Cierre real" if es_efectivo else "Retorno est."
    potencia  = row.get("potencia")
    pot_str   = str(int(float(potencia))) + " " + str(row.get("unidad_medida_potencia") or "MW") if pd.notna(potencia) and float(potencia) > 0 else ""
    correlativo = row.get("correlativo")
    corr_num = str(int(float(correlativo))) if pd.notna(correlativo) else ""
    obs = str(row.get("observacion") or "").strip()[:220]
    afecta = bool(row.get("afecta_sscc"))

    partes = []
    # Solo palpita si está REALMENTE vigente (antes palpitaban todas las
    # «pendientes», incluidas las de febrero que el CEN nunca cerró).
    _bcls = ' class="badge-pend"' if estado == "activa" else ''
    partes.append(f'<span{_bcls} style="background:{c_bg};color:{c_txt};padding:2px 8px;border-radius:4px;font-size:0.71rem;font-weight:700;text-transform:uppercase">{badge_txt}</span>')
    if estado == "vencida":
        partes.append('<span style="font-size:0.66rem;color:#94A3B8">status CEN: pendiente</span>')
    partes.append(f'<span style="font-weight:600;font-size:0.84rem">{central_lbl}</span>')
    if unidad_lbl:
        partes.append(f'<span style="background:#EDE9FE;color:#6D28D9;padding:1px 7px;border-radius:4px;font-size:0.71rem;font-weight:600">{unidad_lbl}</span>')
    if afecta:
        partes.append('<span style="background:#FEF3C7;color:#D97706;padding:1px 6px;border-radius:4px;font-size:0.67rem">Afecta SSCC</span>')
    if corr_num:
        partes.append(f'<span style="font-size:0.67rem;color:#94A3B8">N. {corr_num}</span>')

    origen = _ORIGEN_TXT.get(row.get("_origen_fin", ""), "")
    origen_txt = f' <span style="font-size:0.66rem;color:#94A3B8">({origen})</span>' if origen else ""
    f2_left = (f'<span style="font-size:0.71rem;color:#475569">Apertura: <b>{fecha_pert}</b> '
               f'&rarr; {ret_label}: <b>{fecha_ret}</b></span>{origen_txt}')
    f2_right = f'<span style="font-size:0.77rem;font-weight:700;color:#DC2626">{pot_str}</span>' if pot_str else ""
    fila2 = f'{f2_left}{("&nbsp;&nbsp;&nbsp;" + f2_right) if f2_right else ""}'
    obs_div = f'<div style="font-size:0.71rem;color:#64748B;margin-top:3px">{obs}</div>' if obs else ""
    return (f'<div style="border:1px solid #E2E8F0;border-radius:8px;padding:10px 14px;margin-bottom:8px;background:#FAFAFA">'
            f'<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:3px">{"".join(partes)}</div>'
            f'<div>{fila2}</div>{obs_div}</div>')


def _card_despacho_html(ev):
    """Card de una limitación declarada en la instrucción de despacho.

    Se distingue a propósito de las de transmisión (borde punteado, badge de
    origen): no es un registro formal del CEN sino un documento citado en el
    texto de la instrucción, y no trae correlativo, retorno ni observación.
    """
    unidad = ev.get("unidad", "")
    ini, fin = str(ev["ini"])[:16], str(ev["fin"])[:16]
    mw = ev.get("mw")
    mw_str = f"{float(mw):.0f} MW despachados" if pd.notna(mw) else ""
    badge_txt, c_txt, c_bg = _ESTADO_VIS.get(
        "activa" if ev.get("estado") == "activa" else "cerrada",
        ("CERRADA", "#166534", "#DCFCE7"))
    if ev.get("estado") == "futura":
        badge_txt, c_txt, c_bg = _ESTADO_VIS["futura"]
    _bcls = ' class="badge-pend"' if ev.get("estado") == "activa" else ''
    partes = [
        f'<span{_bcls} style="background:{c_bg};color:{c_txt};padding:2px 8px;border-radius:4px;'
        f'font-size:0.71rem;font-weight:700;text-transform:uppercase">{badge_txt}</span>',
        f'<span style="font-weight:600;font-size:0.84rem">{ev.get("titulo", "")}</span>',
    ]
    if unidad:
        partes.append(f'<span style="background:#EDE9FE;color:#6D28D9;padding:1px 7px;'
                      f'border-radius:4px;font-size:0.71rem;font-weight:600">{unidad}</span>')
    partes.append('<span style="background:#DBEAFE;color:#1D4ED8;padding:1px 6px;'
                  'border-radius:4px;font-size:0.67rem">Declarada en despacho</span>')
    fila2 = (f'<span style="font-size:0.71rem;color:#475569">Ventana instruida: '
             f'<b>{ini}</b> &rarr; <b>{fin}</b></span>')
    if mw_str:
        fila2 += f'&nbsp;&nbsp;&nbsp;<span style="font-size:0.77rem;font-weight:700;color:#DC2626">{mw_str}</span>'
    det = str(ev.get("detalle") or "")
    det_div = f'<div style="font-size:0.71rem;color:#64748B;margin-top:3px">{det}</div>' if det else ""
    return (f'<div style="border:1px dashed #CBD5E1;border-radius:8px;padding:10px 14px;'
            f'margin-bottom:8px;background:#FAFAFA">'
            f'<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:3px">'
            f'{"".join(partes)}</div><div>{fila2}</div>{det_div}</div>')


def _seccion_despacho(df_ins_ev, unidad=None):
    d = df_ins_ev if unidad is None else df_ins_ev[df_ins_ev["unidad"] == unidad]
    if d.empty:
        return
    titulo = ("Declaradas en la instrucción de despacho"
              if unidad is None else
              f"Declaradas en la instrucción de despacho · {LABELS.get(unidad, unidad)}")
    st.markdown(f'<p style="color:#334155;font-weight:600;font-size:0.84rem;'
                f'margin:0.9rem 0 0.35rem">{titulo}</p>', unsafe_allow_html=True)
    st.markdown("".join(_card_despacho_html(r) for _, r in d.iterrows()), unsafe_allow_html=True)


def render_limitaciones(s, e):
    st.markdown('<div class="sec">Limitaciones de transmisión</div>', unsafe_allow_html=True)
    df_lim = load_limitaciones(s, e)

    # Segundo origen: los SICF/SDCF/IL/IF citados en el texto de la instrucción
    # de despacho, que el CEN no publica como limitación de transmisión
    # (regla 50). Se muestran aparte, no mezclados en la tabla del CEN: no
    # comparten campos (no hay correlativo, retorno ni observación).
    df_ins_ev = eventos_desde_instrucciones(load_instrucciones_cmg(s, e))

    if df_lim.empty:
        if df_ins_ev.empty:
            st.info("Sin limitaciones registradas para el período seleccionado.")
        else:
            st.info("Sin limitaciones de transmisión registradas por el CEN en el período. "
                    "Sí hay limitaciones declaradas en la instrucción de despacho:")
            _seccion_despacho(df_ins_ev)
        return

    # El `status` del CEN no cierra nunca: la vigencia se juzga por la VENTANA
    # (ver utils/eventos.py). Sin esto el panel declaraba «activas» limitaciones
    # de hace meses cuyo retorno estimado ya había pasado.
    df_lim = preparar_limitaciones(df_lim)
    df_sorted = df_lim.sort_values("fecha_perturbacion", ascending=False)

    n_vigentes = int((df_lim["_estado"] == "activa").sum())
    n_fantasma = int((df_lim["_estado"] == "vencida").sum())
    n_total = len(df_lim)
    n_sscc = int(df_lim["afecta_sscc"].fillna(False).sum())
    act = df_lim[df_lim["_estado"] == "activa"]
    pot_max = act["potencia"].max() if not act.empty else None
    pot_str = f"{pot_max:.0f} MW" if pd.notna(pot_max) and pot_max > 0 else "—"

    render_kpi_grid([
        ("Vigentes ahora", n_vigentes, "ventana abierta hoy",
         "Limitaciones cuya ventana (apertura → retorno) contiene el instante actual."),
        ("Cerradas de facto", n_fantasma, "status pendiente vencido",
         "El CEN las dejó en «pendiente» pero su fecha de retorno ya pasó: "
         "en la práctica están cerradas y NO se cuentan como activas."),
        ("Total en período", n_total, "registros cargados"),
        ("Afectan SSCC", n_sscc, "con impacto declarado"),
        ("Mayor limitación vigente", pot_str, "potencia limitada"),
        ("Declaradas en despacho", len(df_ins_ev), "SICF / SDCF / IL / IF",
         "Limitaciones citadas en el texto de la instrucción de despacho por CMG. "
         "El CEN no las publica como limitación de transmisión, así que no están "
         "en la tabla de este panel."),
    ], por_fila=3)

    if n_vigentes == 0 and n_fantasma:
        st.success(f"Ninguna limitación vigente en este momento. Hay {n_fantasma} registro(s) "
                   f"que el CEN mantiene en «pendiente» pero cuyo retorno estimado ya pasó: "
                   f"se muestran como CERRADA DE FACTO y no generan alarma.")

    sub = st.radio("Sección", ["ANG1", "ANG2", "CCR1", "CCR2", "Todas", "Estadísticas"],
                   horizontal=True, label_visibility="collapsed", key="lim_sub")
    if sub in UNIDADES:
        df_u = df_sorted[df_sorted["_unidad"] == sub]
        sin_despacho = df_ins_ev.empty or df_ins_ev[df_ins_ev["unidad"] == sub].empty
        if df_u.empty and sin_despacho:
            st.info(f"Sin limitaciones para {sub} en el período.")
        elif df_u.empty:
            st.caption(f"Sin limitaciones de transmisión del CEN para {sub} en el período.")
        else:
            st.markdown("".join(_card_html(r) for _, r in df_u.head(MAX_CARDS).iterrows()), unsafe_allow_html=True)
            if len(df_u) > MAX_CARDS:
                st.caption(f"+{len(df_u) - MAX_CARDS} más en «Todas»")
        _seccion_despacho(df_ins_ev, sub)
    elif sub == "Todas":
        st.markdown("".join(_card_html(r) for _, r in df_sorted.iterrows()), unsafe_allow_html=True)
        _seccion_despacho(df_ins_ev)
    else:
        _estadisticas(df_lim)

    _tabla_completa(df_sorted)


def _estadisticas(df_lim):
    df = df_lim.copy()
    df["fecha_perturbacion"] = pd.to_datetime(df["fecha_perturbacion"])
    COLOR_STATUS = {"pendiente": "#D97706", "finalizado": "#16A34A", "anulado": "#94A3B8"}
    COLORES_UNIDAD = {"ANG1": "#7C3AED", "ANG2": "#2563EB", "CCR1": "#CA8A04", "CCR2": "#16A34A"}

    gc1, gc2 = st.columns([3, 2])
    with gc1:
        df_mes = df.copy()
        df_mes["mes"] = df_mes["fecha_perturbacion"].dt.to_period("M").astype(str)
        pivot = df_mes.groupby(["mes", "status"]).size().reset_index(name="n")
        fig = go.Figure()
        for sv in ["pendiente", "finalizado", "anulado"]:
            d = pivot[pivot["status"] == sv]
            if not d.empty:
                fig.add_trace(go.Bar(x=d["mes"], y=d["n"], name=sv.capitalize(), marker_color=COLOR_STATUS[sv]))
        fig.update_layout(title=dict(text="Limitaciones por mes", font=dict(size=13, color="#0F172A"), x=0),
            barmode="stack", height=300, margin=dict(t=50, b=30, l=30, r=10), legend=dict(orientation="h", y=-0.25),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", yaxis=dict(gridcolor="#E2E8F0", tickfont=dict(color="#94A3B8",size=10)), xaxis=dict(tickfont=dict(color="#475569",size=10)))
        fig.update_xaxes(tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
    with gc2:
        conteo = df["_unidad"].replace("", "Sin unidad").value_counts().reset_index()
        conteo.columns = ["unidad", "n"]
        fig = go.Figure(go.Pie(labels=conteo["unidad"], values=conteo["n"], hole=0.55,
            marker_colors=[COLORES_UNIDAD.get(u, "#94A3B8") for u in conteo["unidad"]],
            textinfo="label+value", textfont_size=12))
        fig.update_layout(title=dict(text="Por unidad", font=dict(size=13, color="#0F172A"), x=0), height=300, margin=dict(t=50, b=10, l=10, r=10), showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    gc3, gc4 = st.columns(2)
    with gc3:
        df_pot = df[df["potencia"].notna() & (df["potencia"] > 0)].copy()
        labels_pot = ["1–50", "51–100", "101–150", "151–200", ">200"]
        df_pot["rango"] = pd.cut(df_pot["potencia"], bins=[0, 50, 100, 150, 200, 300], labels=labels_pot, right=True)
        conteo = df_pot["rango"].value_counts().reindex(labels_pot, fill_value=0).reset_index()
        conteo.columns = ["rango", "n"]
        fig = go.Figure(go.Bar(x=conteo["rango"], y=conteo["n"], marker_color="#3B82F6",
            text=conteo["n"], textposition="outside"))
        fig.update_layout(title=dict(text="Distribución por potencia limitada (MW)", font=dict(size=13, color="#0F172A"), x=0), height=300,
            margin=dict(t=50, b=30, l=30, r=10), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="#E2E8F0", title="Cantidad", tickfont=dict(color="#94A3B8",size=10)), xaxis=dict(title="Rango MW", tickfont=dict(color="#475569",size=10)))
        st.plotly_chart(fig, use_container_width=True)
    with gc4:
        df_fin = df[df["status"] == "finalizado"].copy()
        df_fin["retorno"] = pd.to_datetime(df_fin["fecha_efectiva_retorno"].fillna(df_fin["fecha_retorno_estimada"]))
        df_fin["duracion_dias"] = (df_fin["retorno"] - df_fin["fecha_perturbacion"]).dt.total_seconds() / 86400
        df_fin = df_fin[df_fin["duracion_dias"].notna() & (df_fin["duracion_dias"] >= 0)].sort_values("fecha_perturbacion")
        df_fin["label"] = df_fin["correlativo"].apply(lambda x: f"N.{int(float(x))}" if pd.notna(x) else "")
        if df_fin.empty:
            st.info("Sin limitaciones finalizadas en el período para calcular duración.")
        else:
            fig = go.Figure(go.Bar(x=df_fin["label"], y=df_fin["duracion_dias"].round(1),
                marker_color="#16A34A", text=df_fin["duracion_dias"].round(1), textposition="outside"))
            fig.update_layout(title=dict(text="Duración (días) — limitaciones finalizadas", font=dict(size=13, color="#0F172A"), x=0), height=300,
                margin=dict(t=50, b=30, l=30, r=10), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(gridcolor="#E2E8F0", title="Días", tickfont=dict(color="#94A3B8",size=10)), xaxis=dict(title="Correlativo", tickfont=dict(color="#475569",size=10)))
            st.plotly_chart(fig, use_container_width=True)


def _tabla_completa(df_sorted):
    df = df_sorted.copy()
    df["correlativo"] = df["correlativo"].apply(lambda x: str(int(float(x))) if pd.notna(x) else "")
    cols = ["correlativo", "status", "instalacion_nombre", "fecha_perturbacion",
            "fecha_retorno_estimada", "fecha_efectiva_retorno", "potencia", "afecta_sscc", "observacion"]
    df_t = df[[c for c in cols if c in df.columns]]
    hdrs = "".join(f'<th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#475569;border-bottom:1px solid #E2E8F0;white-space:nowrap">{c}</th>' for c in df_t.columns)
    rows = ""
    for _, r in df_t.iterrows():
        cells = "".join(f'<td style="padding:5px 10px;font-size:0.72rem;border-bottom:1px solid #F1F5F9;white-space:nowrap">{str(r[c]) if pd.notna(r[c]) else ""}</td>' for c in df_t.columns)
        rows += f"<tr>{cells}</tr>"
    st.markdown(
        f'<details style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:0.6rem 1rem;margin-top:0.5rem">'
        f'<summary style="cursor:pointer;font-weight:600;color:#334155;font-size:0.88rem">Ver tabla completa de limitaciones ({len(df_t)} registros)</summary>'
        f'<div style="overflow-x:auto;margin-top:0.6rem"><table style="border-collapse:collapse;width:100%"><thead><tr>{hdrs}</tr></thead><tbody>{rows}</tbody></table></div>'
        f'</details>', unsafe_allow_html=True)
