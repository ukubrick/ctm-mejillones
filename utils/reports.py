"""
utils/reports.py — Reportes ejecutivos PDF y PPT del dashboard CTM Mejillones.

Rediseñados con la paleta corporativa AES (verde→teal→cyan→azul→violeta),
barras de acento con degradado y layout ejecutivo. Gráficos matplotlib
reutilizados por PDF y PPT.
"""
import io
from datetime import datetime

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ── Paleta corporativa AES ────────────────────────────────────────────────────
AES_SPECTRUM = ["#22A95B", "#12B2A0", "#1FB6E5", "#3D53E8", "#7C4DE0"]  # gradiente
C_DARK   = "#0F172A"
C_AZUL   = "#2A38C9"
C_CMG    = "#7C4DE0"
C_GRAY   = "#475569"
C_LGRAY  = "#94A3B8"
C_LINE   = "#E2E8F0"
C_BG     = "#F8FAFC"

_UNIT_COLORS = {
    "ANG1": {"real": "#7C4DE0", "prog": "#C9B5F2"},
    "ANG2": {"real": "#3D53E8", "prog": "#AEB8F5"},
    "CCR1": {"real": "#1FB6E5", "prog": "#A6E4F6"},
    "CCR2": {"real": "#22A95B", "prog": "#A4E0BC"},
}
_UNIT_NAMES = {"ANG1": "Angamos 1", "ANG2": "Angamos 2", "CCR1": "Cochrane 1", "CCR2": "Cochrane 2"}
_UNIDADES = ["ANG1", "ANG2", "CCR1", "CCR2"]
_PMAX = {"ANG1": 277, "ANG2": 280, "CCR1": 276, "CCR2": 276}


# ══════════════════════════════════════════════════════════════
# HELPERS — gráficos matplotlib
# ══════════════════════════════════════════════════════════════
def _fig_generacion(df_real, df_prog, unidad, figsize=(14, 4)):
    col = _UNIT_COLORS[unidad]
    fig, ax = plt.subplots(figsize=figsize)
    df_u  = df_real[df_real["unidad"] == unidad].sort_values("fecha_hora") if not df_real.empty else pd.DataFrame()
    df_up = df_prog[df_prog["unidad"] == unidad].sort_values("fecha_hora") if not df_prog.empty else pd.DataFrame()
    if df_u.empty:
        ax.text(0.5, 0.5, "Sin datos", ha="center", va="center", transform=ax.transAxes, color=C_LGRAY)
    else:
        ax.fill_between(df_u["fecha_hora"], df_u["gen_real_mw"], alpha=0.07, color=col["real"], zorder=1)
        ax.plot(df_u["fecha_hora"], df_u["gen_real_mw"], color=col["real"], linewidth=2.4, label="Real", zorder=3)
        if not df_up.empty:
            ax.plot(df_up["fecha_hora"], df_up["gen_programada_mw"], color=col["prog"],
                    linewidth=2.0, linestyle="--", label="Programada", zorder=2)
    ax.set_ylabel("MW", fontsize=9, color=C_GRAY)
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d/%m"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), fontsize=8, rotation=15, color=C_GRAY)
    ax.tick_params(axis="y", labelsize=8, colors=C_GRAY)
    ax.set_facecolor("#FCFDFF")
    ax.grid(axis="y", color=C_LINE, linewidth=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(C_LINE)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.4)
    return fig


def _fig_cmg(df_cmg, figsize=(14, 3)):
    fig, ax = plt.subplots(figsize=figsize)
    if df_cmg.empty:
        ax.text(0.5, 0.5, "Sin datos CMG", ha="center", va="center", transform=ax.transAxes, color=C_LGRAY)
    else:
        ax.plot(df_cmg["fecha_hora"], df_cmg["cmg_usd_mwh"], color=C_CMG, linewidth=2.0)
        ax.fill_between(df_cmg["fecha_hora"], df_cmg["cmg_usd_mwh"], alpha=0.10, color=C_CMG)
        prom = df_cmg["cmg_usd_mwh"].mean()
        ax.axhline(prom, color=C_LGRAY, linewidth=1, linestyle=":", zorder=1)
    ax.set_ylabel("USD/MWh", fontsize=9, color=C_GRAY)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d/%m"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), fontsize=8, rotation=15, color=C_GRAY)
    ax.tick_params(axis="y", labelsize=8, colors=C_GRAY)
    ax.set_facecolor("#FCFDFF")
    ax.grid(axis="y", color=C_LINE, linewidth=0.7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(C_LINE)
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.4)
    return fig


def _fig_to_bytes(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _kpis_unidad(df_real, df_prog, unidad):
    df_u  = df_real[df_real["unidad"] == unidad] if not df_real.empty else pd.DataFrame()
    df_up = df_prog[df_prog["unidad"] == unidad] if not df_prog.empty else pd.DataFrame()
    pmax  = _PMAX[unidad]
    if df_u.empty:
        return {"prom": "—", "max": "—", "min": "—", "fc": "—", "desv": "—"}
    prom = df_u["gen_real_mw"].mean()
    desv = "—"
    if not df_up.empty:
        df_m = pd.merge_asof(
            df_u[["fecha_hora", "gen_real_mw"]].sort_values("fecha_hora"),
            df_up[["fecha_hora", "gen_programada_mw"]].sort_values("fecha_hora"),
            on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h")).dropna()
        if not df_m.empty:
            desv = f"{(df_m['gen_real_mw'] - df_m['gen_programada_mw']).mean():+.1f}"
    return {"prom": f"{prom:.1f}", "max": f"{df_u['gen_real_mw'].max():.1f}",
            "min": f"{df_u['gen_real_mw'].min():.1f}", "fc": f"{prom / pmax * 100:.1f}%", "desv": desv}


def _bitacora(unidad, s, e):
    """Bitácora de una unidad en el período (silencioso si falla)."""
    try:
        from utils.data import load_bit
        df = load_bit(s, e, unidad)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _periodo(start_str, end_str):
    try:
        dt_s = datetime.strptime(start_str, "%Y-%m-%d")
        return (dt_s.isocalendar()[1], dt_s.strftime("%d/%m/%Y"),
                datetime.strptime(end_str, "%Y-%m-%d").strftime("%d/%m/%Y"))
    except Exception:
        return "—", start_str, end_str


# ══════════════════════════════════════════════════════════════
# GENERADOR PDF
# ══════════════════════════════════════════════════════════════
def generar_pdf(df_real, df_prog, df_cmg, start_str, end_str, df_sscc=None, df_lim=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image as RLImage, HRFlowable, PageBreak, Table, TableStyle)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    if df_sscc is None: df_sscc = pd.DataFrame()
    if df_lim  is None: df_lim  = pd.DataFrame()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    H_DARK, H_AZUL = HexColor(C_DARK), HexColor(C_AZUL)
    H_GRAY, H_LGRAY, H_LINE = HexColor(C_GRAY), HexColor(C_LGRAY), HexColor(C_LINE)

    def _sty(name, size=10, color=None, after=4, align=TA_LEFT, bold=False):
        return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica",
                              fontSize=size, leading=size * 1.2, textColor=color or H_DARK,
                              spaceAfter=after, alignment=align)

    sTitle  = _sty("tt", size=26, bold=True, after=8, color=H_DARK)
    sSub    = _sty("ss", size=12, color=H_GRAY, after=2)
    sH2     = _sty("h2", size=14, bold=True, after=6, color=H_AZUL)
    sH3     = _sty("h3", size=11, bold=True, after=4)
    sBody   = _sty("bd", size=9,  color=H_GRAY, after=3)
    sSmall  = _sty("sm", size=8,  color=H_LGRAY, after=2)
    sCenter = _sty("ct", size=8,  color=H_LGRAY, after=2, align=TA_CENTER)
    sBit    = _sty("bt", size=9,  color=H_DARK, after=2)

    def _accent_bar():
        """Barra fina con el degradado AES (5 celdas de color)."""
        w = 17.4 / len(AES_SPECTRUM) * cm
        t = Table([[""] * len(AES_SPECTRUM)], colWidths=[w] * len(AES_SPECTRUM), rowHeights=[0.16*cm])
        sty = [("LINEBELOW", (0,0), (-1,-1), 0, white), ("TOPPADDING",(0,0),(-1,-1),0),
               ("BOTTOMPADDING",(0,0),(-1,-1),0)]
        for i, c in enumerate(AES_SPECTRUM):
            sty.append(("BACKGROUND", (i,0), (i,0), HexColor(c)))
        t.setStyle(TableStyle(sty))
        return t

    semana, fmt_s, fmt_e = _periodo(start_str, end_str)
    story = []

    # ── PORTADA ────────────────────────────────────────────────
    story += [
        Spacer(1, 2.2*cm),
        _accent_bar(),
        Spacer(1, 0.5*cm),
        Paragraph("Complejo Térmico Mejillones", sTitle),
        Paragraph("Monitoreo Operacional", sSub),
        Spacer(1, 0.7*cm),
        Paragraph(f"Reporte Operacional — Semana {semana}", _sty("rw", size=15, bold=True, after=4)),
        Paragraph(f"Período: {fmt_s} al {fmt_e}", _sty("rp", size=12, color=H_GRAY, after=8)),
        Spacer(1, 0.6*cm),
    ]

    resumen_rows = [["Unidad", "Prom Real (MW)", "Máx (MW)", "Mín (MW)", "Factor Planta", "Desv. vs Prog."]]
    for u in _UNIDADES:
        k = _kpis_unidad(df_real, df_prog, u)
        resumen_rows.append([_UNIT_NAMES[u], k["prom"], k["max"], k["min"], k["fc"], k["desv"]])
    tbl = Table(resumen_rows, colWidths=[3.6*cm, 3*cm, 2.4*cm, 2.4*cm, 3*cm, 3*cm])
    tbl_style = [
        ("BACKGROUND",  (0,0), (-1,0), H_AZUL),
        ("TEXTCOLOR",   (0,0), (-1,0), white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",    (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor(C_BG), white]),
        ("GRID",        (0,0), (-1,-1), 0.5, H_LINE),
        ("ALIGN",       (1,0), (-1,-1), "CENTER"),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",  (0,0), (-1,-1), 6), ("BOTTOMPADDING",(0,0),(-1,-1), 6),
    ]
    for i, u in enumerate(_UNIDADES, 1):
        tbl_style.append(("TEXTCOLOR", (0,i), (0,i), HexColor(_UNIT_COLORS[u]["real"])))
    tbl.setStyle(TableStyle(tbl_style))
    story += [tbl, Spacer(1, 0.6*cm)]

    if not df_cmg.empty:
        story.append(Paragraph(
            f"Costo marginal promedio — Crucero 220 kV: <b>{df_cmg['cmg_usd_mwh'].mean():.1f} USD/MWh</b>"
            f"  ·  Mín {df_cmg['cmg_usd_mwh'].min():.1f}  ·  Máx {df_cmg['cmg_usd_mwh'].max():.1f}", sBody))
    if not df_lim.empty:
        n_act = int((df_lim["status"] == "pendiente").sum())
        n_sscc = int(df_lim["afecta_sscc"].fillna(False).sum())
        story.append(Paragraph(
            f"Limitaciones de transmisión — <b>{n_act} activas</b> en el período · {n_sscc} afectan SSCC", sBody))

    story += [
        Spacer(1, 1.4*cm),
        HRFlowable(width="100%", thickness=0.5, color=H_LINE),
        Paragraph(f"Generado {datetime.now().strftime('%d/%m/%Y %H:%M')}  ·  Fuente: API CEN (SIP / OPS / CMG S3)", sCenter),
        PageBreak(),
    ]

    # ── PÁGINA CMG ─────────────────────────────────────────────
    story += [Paragraph("Costo Marginal (CMG)", sH2), _accent_bar(), Spacer(1, 0.3*cm)]
    story.append(RLImage(_fig_to_bytes(_fig_cmg(df_cmg, figsize=(14, 3.5))), width=17*cm, height=6*cm))
    if not df_cmg.empty:
        story.append(Paragraph(
            f"Nodo Crucero 220 kV (preliminar)  ·  Prom {df_cmg['cmg_usd_mwh'].mean():.1f}  "
            f"Mín {df_cmg['cmg_usd_mwh'].min():.1f}  Máx {df_cmg['cmg_usd_mwh'].max():.1f} USD/MWh", sSmall))
    story += [Spacer(1, 0.4*cm), PageBreak()]

    # ── PÁGINAS POR UNIDAD ─────────────────────────────────────
    for u in _UNIDADES:
        k = _kpis_unidad(df_real, df_prog, u)
        uc = HexColor(_UNIT_COLORS[u]["real"])
        story += [Paragraph(_UNIT_NAMES[u], _sty("uh", size=14, bold=True, after=6, color=uc)),
                  _accent_bar(), Spacer(1, 0.25*cm)]

        kpi_data = [["Prom Real", "Máx", "Mín", "Factor Planta", "Desv. vs Prog."],
                    [f"{k['prom']} MW", f"{k['max']} MW", f"{k['min']} MW", k["fc"], f"{k['desv']} MW"]]
        tk = Table(kpi_data, colWidths=[3.4*cm]*5)
        tk.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), HexColor(C_BG)),
            ("FONTNAME",    (0,0), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,0), 8), ("FONTSIZE", (0,1), (-1,1), 11),
            ("ALIGN",       (0,0), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("GRID",        (0,0), (-1,-1), 0.5, H_LINE),
            ("TEXTCOLOR",   (0,0), (-1,0), H_GRAY), ("TEXTCOLOR", (0,1), (-1,1), uc),
            ("TOPPADDING",  (0,0), (-1,-1), 6), ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ]))
        story += [tk, Spacer(1, 0.3*cm)]
        story.append(RLImage(_fig_to_bytes(_fig_generacion(df_real, df_prog, u, figsize=(14, 4))),
                             width=17*cm, height=7*cm))
        story.append(Spacer(1, 0.3*cm))

        if not df_sscc.empty:
            df_su = df_sscc[df_sscc["unidad"] == u]
            if not df_su.empty:
                story.append(Paragraph(f"SSCC — {len(df_su)} instrucciones", sH3))
                rows = [["Fecha", "Inicio", "Fin", "Instrucción", "Motivo"]]
                for _, r in df_su.head(10).iterrows():
                    rows.append([str(r.get("fecha",""))[:10], str(r.get("inicio_periodo",""))[:5],
                                 str(r.get("fin_periodo",""))[:5], str(r.get("instruccion_sscc","")),
                                 str(r.get("motivo","") or "")[:60]])
                t = Table(rows, colWidths=[2.2*cm, 1.8*cm, 1.8*cm, 2.5*cm, 8.7*cm])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), HexColor("#EAF7F0")),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 8),
                    ("GRID", (0,0), (-1,-1), 0.4, H_LINE),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, HexColor(C_BG)]),
                    ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING",(0,0),(-1,-1), 3)]))
                story += [t, Spacer(1, 0.2*cm)]

        if not df_lim.empty and "_unidad" in df_lim.columns:
            df_lu = df_lim[df_lim["_unidad"] == u]
            if not df_lu.empty:
                story.append(Paragraph(f"Limitaciones — {len(df_lu)}", sH3))
                rows = [["Correlativo", "Status", "Apertura", "Retorno est.", "Potencia", "Afecta SSCC"]]
                for _, r in df_lu.head(8).iterrows():
                    corr = str(int(float(r["correlativo"]))) if pd.notna(r.get("correlativo")) else "—"
                    pot  = f"{int(float(r['potencia']))} MW" if pd.notna(r.get("potencia")) and float(r["potencia"]) > 0 else "—"
                    rows.append([corr, str(r.get("status","")), str(r.get("fecha_perturbacion",""))[:16],
                                 str(r.get("fecha_retorno_estimada","") or "—")[:10], pot,
                                 "Sí" if r.get("afecta_sscc") else "No"])
                t = Table(rows, colWidths=[2.5*cm, 2.2*cm, 3.5*cm, 2.5*cm, 2.5*cm, 2.8*cm])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), HexColor("#FFF7E6")),
                    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 8),
                    ("GRID", (0,0), (-1,-1), 0.4, H_LINE),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, HexColor(C_BG)]),
                    ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING",(0,0),(-1,-1), 3)]))
                story += [t, Spacer(1, 0.2*cm)]

        nov = _bitacora(u, start_str, end_str)
        if not nov.empty:
            story.append(Paragraph("Bitácora", sH3))
            for _, r in nov.iterrows():
                try: fd = datetime.strptime(str(r["fecha"]), "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception: fd = str(r["fecha"])
                story.append(Paragraph(f"<b>{fd} {str(r['hora'])[:5]}</b> — {str(r['comentario'])}", sBit))

        story += [Spacer(1, 0.4*cm), HRFlowable(width="100%", thickness=0.4, color=H_LINE),
                  Paragraph(f"Generado {datetime.now().strftime('%d/%m/%Y %H:%M')}", sCenter), PageBreak()]

    if story and isinstance(story[-1], PageBreak):
        story.pop()
    doc.build(story)
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════
# GENERADOR PPT
# ══════════════════════════════════════════════════════════════
def generar_ppt(df_real, df_prog, df_cmg, start_str, end_str, df_sscc=None, df_lim=None):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    if df_sscc is None: df_sscc = pd.DataFrame()
    if df_lim  is None: df_lim  = pd.DataFrame()

    def _rgb(hexs):
        h = hexs.lstrip("#")
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    RGB_DARK, RGB_AZUL = _rgb(C_DARK), _rgb(C_AZUL)
    RGB_GRAY, RGB_LGRAY = _rgb(C_GRAY), _rgb(C_LGRAY)
    RGB_WHITE, RGB_BG   = RGBColor(0xFF, 0xFF, 0xFF), _rgb(C_BG)
    RGB_AMBER, RGB_CMG  = _rgb("#D97706"), _rgb(C_CMG)
    unit_rgb = {u: _rgb(_UNIT_COLORS[u]["real"]) for u in _UNIDADES}

    semana, fmt_s, fmt_e = _periodo(start_str, end_str)

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.33), Inches(7.5)
    blank = prs.slide_layouts[6]

    def _slide(bg=RGB_WHITE):
        sl = prs.slides.add_slide(blank)
        sl.background.fill.solid(); sl.background.fill.fore_color.rgb = bg
        return sl

    def _txb(sl, text, l, t, w, h, size=18, bold=False, color=RGB_DARK, align=PP_ALIGN.LEFT):
        tb = sl.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
        tf = tb.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = align
        run = p.add_run(); run.text = text
        run.font.size = Pt(size); run.font.bold = bold; run.font.color.rgb = color
        return tb

    def _rect(sl, l, t, w, h, color):
        shp = sl.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
        shp.fill.solid(); shp.fill.fore_color.rgb = color; shp.line.fill.background()
        return shp

    def _accent(sl, l, t, w, h=0.09):
        """Barra de degradado AES (5 rects contiguos)."""
        seg = w / len(AES_SPECTRUM)
        for i, c in enumerate(AES_SPECTRUM):
            _rect(sl, l + i*seg, t, seg, h, _rgb(c))

    def _img(sl, fig, l, t, w, h):
        sl.shapes.add_picture(_fig_to_bytes(fig, dpi=150), Inches(l), Inches(t), Inches(w), Inches(h))

    # ── SLIDE 1: PORTADA ───────────────────────────────────────
    sl = _slide(RGB_DARK)
    _accent(sl, 0.6, 2.3, 5.0, 0.12)
    _txb(sl, "Complejo Térmico Mejillones", 0.6, 2.6, 12, 1.0, size=40, bold=True, color=RGB_WHITE)
    _txb(sl, "Monitoreo Operacional", 0.6, 3.7, 12, 0.6, size=18, color=RGB_LGRAY)
    _txb(sl, f"Reporte Semana {semana}  ·  {fmt_s} — {fmt_e}", 0.6, 4.4, 12, 0.5, size=16, color=_rgb("#8FA0FF"))
    _txb(sl, f"Generado {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0.6, 6.9, 12, 0.4, size=10, color=RGB_LGRAY)

    # ── SLIDE 2: RESUMEN EJECUTIVO ─────────────────────────────
    sl = _slide(RGB_BG)
    _rect(sl, 0, 0, 13.33, 0.62, RGB_AZUL)
    _accent(sl, 0, 0.62, 13.33, 0.06)
    _txb(sl, "Resumen Ejecutivo", 0.35, 0.1, 10, 0.44, size=20, bold=True, color=RGB_WHITE)
    col_x = [0.35, 3.6, 6.85, 10.1]
    for u, cx in zip(_UNIDADES, col_x):
        k = _kpis_unidad(df_real, df_prog, u); cc = unit_rgb[u]
        _rect(sl, cx, 0.95, 2.95, 0.4, cc)
        _txb(sl, _UNIT_NAMES[u], cx+0.12, 0.98, 2.7, 0.34, size=14, bold=True, color=RGB_WHITE)
        for j, txt in enumerate([f"Prom real:  {k['prom']} MW", f"Máximo:  {k['max']} MW",
                                 f"Mínimo:  {k['min']} MW", f"Factor planta:  {k['fc']}",
                                 f"Desv. prog.:  {k['desv']} MW"]):
            _txb(sl, txt, cx+0.12, 1.5 + j*0.52, 2.85, 0.5, size=11, color=RGB_DARK)
    if not df_cmg.empty:
        _txb(sl, f"CMG Crucero 220 kV  ·  Prom {df_cmg['cmg_usd_mwh'].mean():.1f}  "
             f"Mín {df_cmg['cmg_usd_mwh'].min():.1f}  Máx {df_cmg['cmg_usd_mwh'].max():.1f} USD/MWh",
             0.35, 6.7, 9, 0.4, size=11, color=RGB_GRAY)
    if not df_lim.empty:
        n_act = int((df_lim["status"] == "pendiente").sum())
        _txb(sl, f"Limitaciones activas: {n_act}", 10.1, 6.7, 3, 0.4, size=11,
             bold=(n_act > 0), color=RGB_AMBER if n_act > 0 else RGB_GRAY, align=PP_ALIGN.RIGHT)

    # ── SLIDE 3: CMG ───────────────────────────────────────────
    sl = _slide(RGB_BG)
    _rect(sl, 0, 0, 13.33, 0.62, RGB_CMG)
    _accent(sl, 0, 0.62, 13.33, 0.06)
    _txb(sl, "Costo Marginal — CMG", 0.35, 0.1, 10, 0.44, size=20, bold=True, color=RGB_WHITE)
    _img(sl, _fig_cmg(df_cmg, figsize=(13, 4.5)), 0.35, 0.95, 12.6, 5.4)
    if not df_cmg.empty:
        _txb(sl, f"Nodo Crucero 220 kV (preliminar)  ·  Prom {df_cmg['cmg_usd_mwh'].mean():.1f}  "
             f"Mín {df_cmg['cmg_usd_mwh'].min():.1f}  Máx {df_cmg['cmg_usd_mwh'].max():.1f} USD/MWh",
             0.35, 6.5, 12, 0.5, size=11, color=RGB_GRAY)

    # ── SLIDES POR UNIDAD ──────────────────────────────────────
    for u in _UNIDADES:
        k = _kpis_unidad(df_real, df_prog, u); cc = unit_rgb[u]
        sl = _slide(RGB_BG)
        _rect(sl, 0, 0, 13.33, 0.62, cc)
        _accent(sl, 0, 0.62, 13.33, 0.06)
        _txb(sl, f"{_UNIT_NAMES[u]} — Generación", 0.35, 0.1, 10, 0.44, size=20, bold=True, color=RGB_WHITE)
        for i, (lbl, val) in enumerate(zip(["Prom Real", "Máximo", "Mínimo", "Factor Planta", "Desv. Prog."],
                                           [f"{k['prom']} MW", f"{k['max']} MW", f"{k['min']} MW", k["fc"], f"{k['desv']} MW"])):
            bx = 0.35 + i * 2.6
            _rect(sl, bx, 0.85, 2.45, 0.62, RGB_WHITE)
            _txb(sl, lbl, bx+0.05, 0.88, 2.35, 0.24, size=8, color=RGB_GRAY, align=PP_ALIGN.CENTER)
            _txb(sl, val, bx+0.05, 1.1, 2.35, 0.3, size=12, bold=True, color=cc, align=PP_ALIGN.CENTER)
        _img(sl, _fig_generacion(df_real, df_prog, u, figsize=(13, 4.2)), 0.35, 1.65, 12.6, 4.9)

        # Slide de restricciones/bitácora por unidad
        sl = _slide(RGB_BG)
        _rect(sl, 0, 0, 13.33, 0.62, cc)
        _accent(sl, 0, 0.62, 13.33, 0.06)
        _txb(sl, f"{_UNIT_NAMES[u]} — SSCC · Limitaciones · Bitácora", 0.35, 0.1, 12, 0.44, size=20, bold=True, color=RGB_WHITE)
        cur_y = 0.95
        if not df_sscc.empty:
            df_su = df_sscc[df_sscc["unidad"] == u].head(6)
            if not df_su.empty:
                _txb(sl, f"SSCC ({len(df_sscc[df_sscc['unidad']==u])} instrucciones)", 0.35, cur_y, 8, 0.3,
                     size=12, bold=True, color=_rgb("#22A95B")); cur_y += 0.34
                for _, r in df_su.iterrows():
                    _txb(sl, f"{str(r.get('fecha',''))[:10]}  {str(r.get('inicio_periodo',''))[:5]}–"
                         f"{str(r.get('fin_periodo',''))[:5]}  [{r.get('instruccion_sscc','')}]  "
                         f"{str(r.get('motivo','') or '')[:55]}", 0.45, cur_y, 12.5, 0.3, size=9, color=RGB_DARK)
                    cur_y += 0.3
        cur_y += 0.1
        if not df_lim.empty and "_unidad" in df_lim.columns:
            df_lu = df_lim[df_lim["_unidad"] == u].head(5)
            if not df_lu.empty:
                _txb(sl, f"Limitaciones ({len(df_lim[df_lim['_unidad']==u])})", 0.35, cur_y, 8, 0.3,
                     size=12, bold=True, color=RGB_AMBER); cur_y += 0.34
                for _, r in df_lu.iterrows():
                    corr = str(int(float(r["correlativo"]))) if pd.notna(r.get("correlativo")) else "—"
                    pot  = f"{int(float(r['potencia']))} MW" if pd.notna(r.get("potencia")) and float(r["potencia"]) > 0 else ""
                    _txb(sl, f"N.{corr}  [{r.get('status','')}]  {str(r.get('fecha_perturbacion',''))[:16]}  {pot}  "
                         f"{'[Afecta SSCC]' if r.get('afecta_sscc') else ''}", 0.45, cur_y, 12.5, 0.3, size=9, color=RGB_DARK)
                    cur_y += 0.3
        cur_y += 0.1
        nov = _bitacora(u, start_str, end_str)
        if not nov.empty and cur_y < 6.8:
            _txb(sl, "Bitácora", 0.35, cur_y, 8, 0.3, size=12, bold=True, color=RGB_DARK); cur_y += 0.34
            for _, r in nov.head(4).iterrows():
                try: fd = datetime.strptime(str(r["fecha"]), "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception: fd = str(r["fecha"])
                _txb(sl, f"{fd} {str(r['hora'])[:5]} — {str(r['comentario'])[:90]}", 0.45, cur_y, 12.5, 0.32, size=9, color=RGB_DARK)
                cur_y += 0.32

    # ── SLIDE FINAL: LIMITACIONES ──────────────────────────────
    if not df_lim.empty:
        sl = _slide(RGB_BG)
        _rect(sl, 0, 0, 13.33, 0.62, RGB_AMBER)
        _accent(sl, 0, 0.62, 13.33, 0.06)
        _txb(sl, "Limitaciones de Transmisión — Resumen", 0.35, 0.1, 12, 0.44, size=20, bold=True, color=RGB_WHITE)
        cur_y = 0.95
        for _, r in df_lim.head(12).iterrows():
            corr   = str(int(float(r["correlativo"]))) if pd.notna(r.get("correlativo")) else "—"
            unidad = r.get("_unidad", "") if "_unidad" in df_lim.columns else ""
            pot    = f"{int(float(r['potencia']))} MW" if pd.notna(r.get("potencia")) and float(r["potencia"]) > 0 else "—"
            _txb(sl, f"N.{corr}  {unidad}  [{r.get('status','')}]  Apertura {str(r.get('fecha_perturbacion',''))[:16]}  "
                 f"Potencia {pot}  {'[Afecta SSCC]' if r.get('afecta_sscc') else ''}", 0.35, cur_y, 12.6, 0.35, size=9, color=RGB_DARK)
            cur_y += 0.38
            if cur_y > 7.0: break

    buf = io.BytesIO()
    prs.save(buf); buf.seek(0)
    return buf.read()
