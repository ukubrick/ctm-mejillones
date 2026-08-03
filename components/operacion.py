"""
components/operacion.py — Panorama operacional del complejo.

Primera pantalla de la vista «Operación» (antes «Restricciones»). El resto de
las subsecciones son inventarios por fuente (limitaciones, SSCC, despacho,
solicitudes, mantenimiento); esta responde las tres preguntas que ninguna de
ellas contestaba por separado:

  1. ¿Qué está pasando AHORA en cada unidad? — estado de la máquina, evento
     vigente y próximo evento ya publicado, con la cuenta regresiva.
  2. ¿Cuánto cuesta? — energía no generada durante la ventana de cada evento
     (programa − real) valorizada al CMG de la hora, para priorizar por plata.
  3. ¿Cuánto queda sin explicar? — de las horas en que la unidad no siguió el
     programa, qué fracción cae dentro de la ventana de un evento registrado y
     qué fracción no tiene ninguna causa documentada.

La vigencia de las limitaciones se juzga por su VENTANA, nunca por el `status`
del CEN (que se queda en «pendiente» para siempre) — ver utils/eventos.py.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import BG_TRANSP, C_GRID, COLORES, LABELS, UNIDADES
from utils.data import (load_instrucciones_cmg, load_limitaciones,
                        load_mantenimiento_mayor)
from utils.eventos import (TIPO_EVENTO, dias_hasta, eventos_latentes,
                           eventos_unidad, explicar_horas)
from components._common import fmt_usd, render_guia, render_kpi_grid

# Bajo este umbral la unidad se considera detenida (regla 23).
UMBRAL_TRIP = 5.0
# Desvío mínimo respecto del programa para contar la hora como "no cumplida".
UMBRAL_DESVIO_MW = 10.0

_GUIA = (
    "<p>Este panorama cruza las cuatro fuentes de eventos del Coordinador "
    "(<strong>limitaciones de transmisión</strong>, <strong>mantenimiento mayor</strong>, "
    "<strong>SSCC</strong> y <strong>despacho por CMG</strong>) contra la generación real de "
    "cada unidad.</p>"
    "<p><strong>Vigencia:</strong> una limitación se considera activa mientras su ventana "
    "(apertura → retorno) contenga el instante actual. El campo <code>status</code> del CEN no "
    "sirve: se queda en «pendiente» indefinidamente y <code>fecha_efectiva_retorno</code> llega "
    "casi siempre vacía, así que contar «pendientes» arrastra limitaciones de meses atrás ya "
    "superadas. Esas se marcan aquí como <strong>cerradas de facto</strong>.</p>"
    "<p><strong>Energía no generada:</strong> Σ (programa − real) en las horas cubiertas por la "
    "ventana del evento, valorizada al CMG de cada hora. Es una estimación de referencia de "
    "mercado, no una liquidación.</p>"
)


# ─────────────────────────────────────────────────────────────────────────────
# Estado actual por unidad
# ─────────────────────────────────────────────────────────────────────────────
def _estado_unidad(unidad, df_r, df_ev):
    """(texto, color, detalle) del estado presente de la unidad."""
    df_u = df_r[df_r["unidad"] == unidad].sort_values("fecha_hora")
    if df_u.empty:
        return "Sin datos", "#94A3B8", "sin medición en el período"
    ultimo = df_u.iloc[-1]
    mw = float(ultimo["gen_real_mw"])
    cuando = ultimo["fecha_hora"].strftime("%d-%m %H:%M")
    if mw < UMBRAL_TRIP:
        return "Detenida", "#DC2626", f"{mw:.0f} MW · última medición {cuando}"
    return "En servicio", "#16A34A", f"{mw:.0f} MW · última medición {cuando}"


def _card_unidad(unidad, df_r, df_ev):
    estado, color, detalle = _estado_unidad(unidad, df_r, df_ev)
    activos = df_ev[df_ev["estado"] == "activa"] if not df_ev.empty else df_ev

    if activos is not None and not activos.empty:
        # Se muestra la INSTALACIÓN, no el tipo: tres líneas repitiendo
        # «Mant. corredor de evacuación» no distinguen un evento de otro.
        act = activos.drop_duplicates(subset=["titulo", "fuente", "fin"])
        filas_ev = "".join(
            f'<div style="font-size:0.72rem;margin-top:3px">'
            f'<span style="color:{TIPO_EVENTO.get(ev["tipo"], TIPO_EVENTO["limitacion"])[1]};'
            f'font-weight:600">{str(ev["fuente"])[:30] or ev["titulo"]}</span>'
            f'<span style="color:#94A3B8"> · hasta {ev["fin"].strftime("%d-%m %H:%M")}</span></div>'
            for _, ev in act.head(3).iterrows())
        if len(act) > 3:
            filas_ev += (f'<div style="font-size:0.68rem;color:#94A3B8;margin-top:2px">'
                         f'+{len(act) - 3} más</div>')
    else:
        filas_ev = ('<div style="font-size:0.72rem;color:#16A34A;margin-top:3px">'
                    'Sin eventos vigentes</div>')

    lat = eventos_latentes(df_ev)
    if lat is not None and not lat.empty:
        pr = lat.iloc[0]
        d = dias_hasta(pr["ini"])
        prox = (f'<div style="font-size:0.7rem;color:#5B21B6;margin-top:6px;'
                f'border-top:1px dashed #E2E8F0;padding-top:5px">'
                f'Próximo: <b>{pr["titulo"]}</b> en {d} d '
                f'({pr["ini"].strftime("%d-%m-%Y")})</div>')
    else:
        prox = ('<div style="font-size:0.7rem;color:#94A3B8;margin-top:6px;'
                'border-top:1px dashed #E2E8F0;padding-top:5px">'
                'Sin eventos programados por delante</div>')

    return (
        f'<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-top:3px solid '
        f'{COLORES.get(unidad, "#94A3B8")};border-radius:10px;padding:12px 14px;height:100%">'
        f'<div style="font-weight:700;font-size:0.86rem;color:#0F172A">{LABELS[unidad]}</div>'
        f'<div style="display:inline-block;background:{color}18;color:{color};font-weight:700;'
        f'font-size:0.68rem;padding:2px 8px;border-radius:5px;margin:5px 0 2px;'
        f'text-transform:uppercase">{estado}</div>'
        f'<div style="font-size:0.7rem;color:#64748B">{detalle}</div>'
        f'{filas_ev}{prox}</div>')


# ─────────────────────────────────────────────────────────────────────────────
# Impacto: energía no generada y su valorización
# ─────────────────────────────────────────────────────────────────────────────
def _impacto_eventos(unidad, df_ev, df_r, df_p, df_c):
    """Energía no generada y USD perdidos por evento (programa − real × CMG).

    Solo cuenta el DÉFICIT (real por debajo del programa): un evento que
    restringe no puede explicar una desviación al alza (regla 41).
    """
    if df_ev is None or df_ev.empty:
        return pd.DataFrame()
    du = df_r[df_r["unidad"] == unidad][["fecha_hora", "gen_real_mw"]]
    dp = df_p[df_p["unidad"] == unidad][["fecha_hora", "gen_programada_mw"]] if not df_p.empty else pd.DataFrame()
    if du.empty or dp.empty:
        return pd.DataFrame()
    m = pd.merge_asof(du.sort_values("fecha_hora"), dp.sort_values("fecha_hora"),
                      on="fecha_hora", direction="nearest",
                      tolerance=pd.Timedelta("1h")).dropna()
    if m.empty:
        return pd.DataFrame()
    if df_c is not None and not df_c.empty:
        m = pd.merge_asof(m, df_c[["fecha_hora", "cmg_usd_mwh"]].sort_values("fecha_hora"),
                          on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h"))
    else:
        m["cmg_usd_mwh"] = float("nan")
    m["deficit_mwh"] = (m["gen_programada_mw"] - m["gen_real_mw"]).clip(lower=0)

    filas = []
    # Solo intervenciones DIRECTAS sobre la unidad. El corredor de evacuación
    # queda fuera: sus ventanas duran semanas y aplican a las 4 unidades a la
    # vez, así que se llevaría casi todo el déficit del período sin haberlo
    # causado (regla 41). Se sigue viendo como contexto en la serie y el timeline.
    for _, ev in df_ev[df_ev["tipo"].isin(["limitacion", "mantenimiento"])].iterrows():
        en = m[(m["fecha_hora"] >= ev["ini"]) & (m["fecha_hora"] <= ev["fin"])]
        if en.empty:
            continue
        mwh = float(en["deficit_mwh"].sum())
        usd = float((en["deficit_mwh"] * en["cmg_usd_mwh"].fillna(0)).sum())
        filas.append({
            "unidad": unidad, "tipo": ev["tipo"], "titulo": ev["titulo"],
            "fuente": ev["fuente"], "ini": ev["ini"], "fin": ev["fin"],
            "estado": ev["estado"], "horas": len(en),
            "mwh": mwh, "usd": usd,
        })
    if not filas:
        return pd.DataFrame()
    return pd.DataFrame(filas).sort_values("mwh", ascending=False)


def _grafico_impacto(df_imp):
    """Barras horizontales de energía no generada por evento (mayor arriba)."""
    d = df_imp[df_imp["mwh"] > 0].head(12).sort_values("mwh")
    if d.empty:
        st.caption("Ningún evento del período coincide con horas de déficit respecto "
                   "del programa: las unidades siguieron el despacho durante las "
                   "ventanas registradas.")
        return
    etiquetas = [f'{r["titulo"]} · {r["unidad"]}' for _, r in d.iterrows()]
    colores = [TIPO_EVENTO.get(t, TIPO_EVENTO["limitacion"])[1] for t in d["tipo"]]
    fig = go.Figure(go.Bar(
        x=d["mwh"], y=etiquetas, orientation="h", marker_color=colores,
        text=[f"{v:,.0f} MWh" for v in d["mwh"]], textposition="outside",
        customdata=d[["usd", "horas"]].to_numpy(),
        hovertemplate="<b>%{y}</b><br>%{x:,.0f} MWh no generados<br>"
                      "US$ %{customdata[0]:,.0f} · %{customdata[1]} h de ventana<extra></extra>"))
    fig.update_layout(
        title=dict(text="Energía no generada durante la ventana de cada evento (MWh)",
                   font=dict(size=13, color="#0F172A"), x=0),
        height=max(260, 30 * len(d) + 110), margin=dict(l=10, r=60, t=52, b=30),
        plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
        font=dict(family="Inter, sans-serif"), showlegend=False,
        xaxis=dict(gridcolor=C_GRID, tickfont=dict(color="#94A3B8", size=10),
                   title="MWh", title_font=dict(color="#94A3B8", size=10)),
        yaxis=dict(showgrid=False, tickfont=dict(color="#475569", size=10)))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key="op_impacto")
    st.caption("Déficit = Σ (programa − real) dentro de la ventana, solo horas por debajo "
               "del programa. Un evento que restringe no puede explicar una desviación "
               "al alza, así que las horas de sobregeneración no se descuentan.")


# ─────────────────────────────────────────────────────────────────────────────
# Timeline unificado
# ─────────────────────────────────────────────────────────────────────────────
def _timeline(eventos_por_u, s, e):
    """Gantt de todos los eventos del período, una fila por unidad."""
    filas = []
    for u, dfe in eventos_por_u.items():
        if dfe is None or dfe.empty:
            continue
        for _, ev in dfe.iterrows():
            filas.append({**ev.to_dict(), "unidad": u})
    if not filas:
        st.caption("Sin eventos registrados que toquen el período.")
        return
    d = pd.DataFrame(filas)
    sd = pd.Timestamp(s)
    ed = pd.Timestamp(e) + pd.Timedelta(days=1)
    # Se recorta al período + lo que venga por delante (evento latente visible).
    d = d[(d["fin"] >= sd)]
    if d.empty:
        st.caption("Sin eventos registrados que toquen el período.")
        return
    x_max = max(ed, d["ini"].max() + pd.Timedelta(days=1))

    fig = go.Figure()
    # Las barras van SIN leyenda propia y las entradas se agregan después como
    # trazas vacías: con `showlegend` condicional dentro del bucle, Plotly deja
    # entradas duplicadas/en blanco cuando el mismo tipo se dibuja con distinto
    # `dash` (vigente vs futuro).
    for _, ev in d.iterrows():
        _etq, color, _relleno = TIPO_EVENTO.get(ev["tipo"], TIPO_EVENTO["limitacion"])
        futuro = ev["estado"] == "futura"
        fig.add_trace(go.Scatter(
            x=[max(ev["ini"], sd - pd.Timedelta(days=30)), ev["fin"]],
            y=[LABELS[ev["unidad"]], LABELS[ev["unidad"]]],
            mode="lines", showlegend=False,
            line=dict(color=color, width=11, dash="dot" if futuro else "solid"),
            opacity=0.45 if ev["estado"] == "cerrada" else (0.7 if futuro else 0.95),
            hovertemplate=(f'<b>{ev["titulo"]}</b> · {LABELS[ev["unidad"]]}<br>'
                           f'{ev["ini"].strftime("%d-%m %H:%M")} → '
                           f'{ev["fin"].strftime("%d-%m %H:%M")} ({ev["dias"]:.1f} d)<br>'
                           f'Estado: {ev["estado"]}<br>{str(ev["fuente"])[:50]}<extra></extra>')))
    for tipo in d["tipo"].unique():
        etiqueta, color, _r = TIPO_EVENTO.get(tipo, TIPO_EVENTO["limitacion"])
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=etiqueta,
                                 marker=dict(color=color, size=10, symbol="square"),
                                 hoverinfo="skip"))
    ahora = pd.Timestamp.now()
    fig.add_shape(type="line", x0=ahora, x1=ahora, y0=0, y1=1, yref="paper",
                  line=dict(color="#DC2626", width=1.4, dash="dash"))
    fig.update_layout(
        title=dict(text="Línea de tiempo de eventos por unidad",
                   font=dict(size=13, color="#0F172A"), x=0),
        height=300, margin=dict(l=10, r=14, t=52, b=30),
        plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
        font=dict(family="Inter, sans-serif"),
        legend=dict(orientation="h", y=1.13, x=0, font=dict(size=10, color="#6B7280")),
        xaxis=dict(gridcolor=C_GRID, tickformat="%d-%m", range=[sd, x_max],
                   tickfont=dict(color="#94A3B8", size=10)),
        yaxis=dict(showgrid=False, tickfont=dict(color="#475569", size=11),
                   categoryorder="array",
                   categoryarray=[LABELS[u] for u in reversed(UNIDADES)]))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key="op_timeline")
    st.caption("Línea punteada roja = ahora. Trazo discontinuo = evento futuro ya "
               "publicado por el CEN. Trazo tenue = evento cerrado.")


# ─────────────────────────────────────────────────────────────────────────────
# Cobertura: cuánto del desvío queda explicado
# ─────────────────────────────────────────────────────────────────────────────
def _cobertura(eventos_por_u, df_r, df_p):
    """Por unidad: horas de déficit y qué fracción cae dentro de un evento."""
    if df_p.empty:
        st.caption("Sin programa cargado en el período: no se puede medir el desvío.")
        return
    filas = []
    for u in UNIDADES:
        du = df_r[df_r["unidad"] == u][["fecha_hora", "gen_real_mw"]]
        dp = df_p[df_p["unidad"] == u][["fecha_hora", "gen_programada_mw"]]
        if du.empty or dp.empty:
            continue
        m = pd.merge_asof(du.sort_values("fecha_hora"), dp.sort_values("fecha_hora"),
                          on="fecha_hora", direction="nearest",
                          tolerance=pd.Timedelta("1h")).dropna()
        if m.empty:
            continue
        deficit = m[(m["gen_programada_mw"] - m["gen_real_mw"]) > UMBRAL_DESVIO_MW]
        if deficit.empty:
            filas.append({"unidad": u, "horas": 0, "directa": 0, "corredor": 0, "sin": 0})
            continue
        dfe = eventos_por_u.get(u)
        # Causa DIRECTA (limitación / mantenimiento de la unidad) vs mero
        # CONTEXTO de corredor: mezclarlos daría por explicado casi todo.
        directa = explicar_horas(deficit["fecha_hora"], dfe)
        corredor = explicar_horas(deficit["fecha_hora"], dfe, tipos=("corredor",))
        n_dir = int((directa != "").sum())
        n_cor = int(((directa == "") & (corredor != "")).sum())
        filas.append({"unidad": u, "horas": len(deficit), "directa": n_dir,
                      "corredor": n_cor, "sin": len(deficit) - n_dir - n_cor})
    if not filas:
        st.caption("Sin cruce real/programa suficiente para medir la cobertura.")
        return
    d = pd.DataFrame(filas)

    x = [LABELS[u] for u in d["unidad"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=d["directa"], name="Causa directa",
                         marker_color="#12B2A0",
                         hovertemplate="%{y} h con limitación o mantenimiento de la unidad<extra></extra>"))
    fig.add_trace(go.Bar(x=x, y=d["corredor"], name="Solo contexto de corredor",
                         marker_color="#94A3B8",
                         hovertemplate="%{y} h con intervención en el corredor de evacuación<extra></extra>"))
    fig.add_trace(go.Bar(x=x, y=d["sin"], name="Sin causa registrada",
                         marker_color="#DC2626",
                         hovertemplate="%{y} h sin explicar<extra></extra>"))
    fig.update_layout(
        title=dict(text=f"Horas bajo programa (> {UMBRAL_DESVIO_MW:.0f} MW de déficit) "
                        f"y su cobertura documental",
                   font=dict(size=13, color="#0F172A"), x=0),
        barmode="stack", height=300, margin=dict(l=10, r=14, t=52, b=30),
        plot_bgcolor=BG_TRANSP, paper_bgcolor=BG_TRANSP,
        font=dict(family="Inter, sans-serif"),
        legend=dict(orientation="h", y=1.13, x=0, font=dict(size=10, color="#6B7280")),
        xaxis=dict(showgrid=False, tickfont=dict(color="#475569", size=11)),
        yaxis=dict(gridcolor=C_GRID, title="Horas",
                   tickfont=dict(color="#94A3B8", size=10),
                   title_font=dict(color="#94A3B8", size=10)))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key="op_cobertura")
    st.caption("Rojo = horas bajo programa sin ninguna limitación ni mantenimiento de la "
               "unidad que cubra ese instante: o falta documentar el evento, o el desvío "
               "es propio. Gris = solo hay una intervención en el corredor de evacuación, "
               "que es contexto pero no prueba la causa (sus ventanas duran semanas y "
               "aplican a las 4 unidades).")


# ─────────────────────────────────────────────────────────────────────────────
# Render
# ─────────────────────────────────────────────────────────────────────────────
def render_panorama(s, e, df_r, df_p, df_c):
    st.markdown('<div class="sec">Panorama operacional · qué está activo y cuánto cuesta</div>',
                unsafe_allow_html=True)
    render_guia("Cómo se calcula lo que ves aquí", _GUIA)

    df_lim = load_limitaciones(s, e)
    df_mant = load_mantenimiento_mayor()
    # Las limitaciones citadas en el texto de la instrucción de despacho
    # (SICF/SDCF/IL/IF) no viven en limitaciones_transmision — entran por aquí.
    df_ins = load_instrucciones_cmg(s, e)
    eventos_por_u = {u: eventos_unidad(u, df_lim=df_lim, df_mant=df_mant,
                                       df_instr=df_ins)
                     for u in UNIDADES}

    todos = pd.concat([d for d in eventos_por_u.values() if d is not None and not d.empty],
                      ignore_index=True) if any(
        d is not None and not d.empty for d in eventos_por_u.values()) else pd.DataFrame()

    # Un mantenimiento del corredor aplica a las 4 unidades, así que aparece 4
    # veces en `todos`. Para CONTAR eventos hay que deduplicar por su identidad
    # (título + ventana + instalación); si no, «3 intervenciones» se leía como 12.
    unicos = (todos.drop_duplicates(subset=["titulo", "ini", "fin", "fuente"])
              if not todos.empty else todos)
    n_act = int((unicos["estado"] == "activa").sum()) if not unicos.empty else 0
    n_fut = int((unicos["estado"] == "futura").sum()) if not unicos.empty else 0
    prox_txt, prox_help = "—", None
    if not unicos.empty:
        lat = eventos_latentes(unicos)
        if lat is not None and not lat.empty:
            pr = lat.iloc[0]
            prox_txt = f"{dias_hasta(pr['ini'])} d"
            prox_help = (f"{pr['titulo']} · {pr['fuente']} · "
                         f"{pr['ini'].strftime('%d-%m-%Y')} → {pr['fin'].strftime('%d-%m-%Y')}")

    impactos = [_impacto_eventos(u, eventos_por_u[u], df_r, df_p, df_c) for u in UNIDADES]
    impactos = [d for d in impactos if d is not None and not d.empty]
    df_imp = pd.concat(impactos, ignore_index=True) if impactos else pd.DataFrame()
    mwh_tot = float(df_imp["mwh"].sum()) if not df_imp.empty else 0.0
    usd_tot = float(df_imp["usd"].sum()) if not df_imp.empty else 0.0

    render_kpi_grid([
        ("Eventos vigentes", n_act, "ventana abierta ahora",
         "Limitaciones y mantenimientos cuya ventana contiene el instante actual."),
        ("Eventos latentes", n_fut, "ya publicados por el CEN",
         "Programas futuros del PMPM que afectan a las unidades o a su corredor."),
        ("Próximo evento", prox_txt, "días por delante", prox_help),
        ("Energía no generada", f"{mwh_tot:,.0f}".replace(",", "."),
         "MWh en ventanas de evento"),
        ("Valor en riesgo", fmt_usd(usd_tot), "USD al CMG de la hora",
         f"Energía no generada valorizada al CMG horario. "
         f"Valor exacto: US$ {usd_tot:,.0f}. Referencia de mercado, no una liquidación."),
    ], por_fila=5)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    cols = st.columns(4)
    for col, u in zip(cols, UNIDADES):
        col.markdown(_card_unidad(u, df_r, eventos_por_u[u]), unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    _timeline(eventos_por_u, s, e)

    # Si no hay impacto que graficar, la cobertura va a ancho completo en vez de
    # dejar media pantalla vacía.
    if df_imp.empty:
        st.info("Ningún evento del período (limitación o mantenimiento de unidad) coincide "
                "con horas de déficit respecto del programa, así que no hay energía no "
                "generada que atribuir. Las intervenciones vigentes son del corredor de "
                "evacuación y no se les imputa energía.")
        _cobertura(eventos_por_u, df_r, df_p)
    else:
        c1, c2 = st.columns(2)
        with c1:
            _grafico_impacto(df_imp)
        with c2:
            _cobertura(eventos_por_u, df_r, df_p)
