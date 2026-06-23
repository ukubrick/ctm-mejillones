"""
utils/reports.py — Generación de reportes PDF y PPT del dashboard CTM Mejillones.
Helpers de gráficos matplotlib + constructores ReportLab / python-pptx.
Extraído del monolito app.py sin cambios de lógica.
"""
import io
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
# HELPERS COMUNES — gráficos matplotlib reutilizados por PDF y PPT
# ══════════════════════════════════════════════════════════════
_UNIT_COLORS = {
    "ANG1": {"real": "#7C3AED", "prog": "#C4B5FD"},
    "ANG2": {"real": "#2563EB", "prog": "#93C5FD"},
    "CCR1": {"real": "#CA8A04", "prog": "#FDE68A"},
    "CCR2": {"real": "#16A34A", "prog": "#86EFAC"},
}
_UNIT_NAMES = {"ANG1": "Angamos 1", "ANG2": "Angamos 2", "CCR1": "Cochrane 1", "CCR2": "Cochrane 2"}


def _fig_generacion(df_real, df_prog, unidad, figsize=(14, 4)):
    """Retorna figura matplotlib con real vs programada para una unidad."""
    import matplotlib.pyplot as _plt
    import matplotlib.dates as _mdates
    col = _UNIT_COLORS[unidad]
    fig, ax = _plt.subplots(figsize=figsize)
    df_u  = df_real[df_real["unidad"] == unidad].sort_values("fecha_hora") if not df_real.empty else pd.DataFrame()
    df_up = df_prog[df_prog["unidad"] == unidad].sort_values("fecha_hora") if not df_prog.empty else pd.DataFrame()
    if df_u.empty:
        ax.text(0.5, 0.5, "Sin datos", ha="center", va="center", transform=ax.transAxes, color="#94A3B8")
    else:
        ax.plot(df_u["fecha_hora"], df_u["gen_real_mw"],
                color=col["real"], linewidth=2.2, label="Real MW", zorder=3)
        if not df_up.empty:
            ax.plot(df_up["fecha_hora"], df_up["gen_programada_mw"],
                    color=col["prog"], linewidth=2.0, linestyle="--", label="Programada MW", zorder=2)
            df_m = pd.merge_asof(
                df_u[["fecha_hora", "gen_real_mw"]].sort_values("fecha_hora"),
                df_up[["fecha_hora", "gen_programada_mw"]].sort_values("fecha_hora"),
                on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h")
            ).dropna()
            if not df_m.empty:
                ax.fill_between(df_m["fecha_hora"], df_m["gen_real_mw"], df_m["gen_programada_mw"],
                                alpha=0.15, color=col["real"])
    ax.set_ylabel("MW", fontsize=9)
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_formatter(_mdates.DateFormatter("%a %d/%m"))
    ax.xaxis.set_major_locator(_mdates.DayLocator())
    _plt.setp(ax.xaxis.get_majorticklabels(), fontsize=8, rotation=15)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_facecolor("#FAFBFF")
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
    ax.grid(axis="x", color="#F1F5F9", linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.85)
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.4)
    return fig


def _fig_cmg(df_cmg, figsize=(14, 3)):
    """Retorna figura matplotlib con CMG USD/MWh."""
    import matplotlib.pyplot as _plt
    import matplotlib.dates as _mdates
    fig, ax = _plt.subplots(figsize=figsize)
    if df_cmg.empty:
        ax.text(0.5, 0.5, "Sin datos CMG", ha="center", va="center", transform=ax.transAxes, color="#94A3B8")
    else:
        ax.plot(df_cmg["fecha_hora"], df_cmg["cmg_usd_mwh"], color="#0891B2", linewidth=1.8)
        ax.fill_between(df_cmg["fecha_hora"], df_cmg["cmg_usd_mwh"], alpha=0.12, color="#0891B2")
    ax.set_ylabel("USD/MWh", fontsize=9)
    ax.xaxis.set_major_formatter(_mdates.DateFormatter("%a %d/%m"))
    ax.xaxis.set_major_locator(_mdates.DayLocator())
    _plt.setp(ax.xaxis.get_majorticklabels(), fontsize=8, rotation=15)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_facecolor("#FAFBFF")
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.4)
    return fig


def _fig_to_bytes(fig, dpi=150):
    import io as _io, matplotlib.pyplot as _plt
    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    _plt.close(fig)
    buf.seek(0)
    return buf


def _kpis_unidad(df_real, df_prog, unidad):
    """Retorna dict con KPIs calculados para una unidad."""
    df_u  = df_real[df_real["unidad"] == unidad] if not df_real.empty else pd.DataFrame()
    df_up = df_prog[df_prog["unidad"] == unidad] if not df_prog.empty else pd.DataFrame()
    pmax  = {"ANG1": 277, "ANG2": 280, "CCR1": 276, "CCR2": 276}[unidad]
    if df_u.empty:
        return {"prom": "—", "max": "—", "min": "—", "fc": "—", "desv": "—"}
    prom = df_u["gen_real_mw"].mean()
    mx   = df_u["gen_real_mw"].max()
    mn   = df_u["gen_real_mw"].min()
    fc   = prom / pmax * 100
    desv = "—"
    if not df_up.empty:
        df_m = pd.merge_asof(
            df_u[["fecha_hora", "gen_real_mw"]].sort_values("fecha_hora"),
            df_up[["fecha_hora", "gen_programada_mw"]].sort_values("fecha_hora"),
            on="fecha_hora", direction="nearest", tolerance=pd.Timedelta("1h")
        ).dropna()
        if not df_m.empty:
            desv = f"{(df_m['gen_real_mw'] - df_m['gen_programada_mw']).mean():+.1f}"
    return {
        "prom": f"{prom:.1f}", "max": f"{mx:.1f}", "min": f"{mn:.1f}",
        "fc":   f"{fc:.1f}%",  "desv": desv,
    }


# ══════════════════════════════════════════════════════════════
# GENERADOR PDF — Reporte Operacional Completo
# ══════════════════════════════════════════════════════════════
def generar_pdf(df_real, df_prog, df_cmg, start_str, end_str,
                df_sscc=None, df_lim=None):
    from reportlab.lib.pagesizes import A4, landscape as RL_landscape
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image as RLImage, HRFlowable, PageBreak, Table, TableStyle)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    import io as _io

    if df_sscc is None: df_sscc = pd.DataFrame()
    if df_lim  is None: df_lim  = pd.DataFrame()

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    # Paleta
    C_DARK  = HexColor("#0F172A")
    C_BLUE  = HexColor("#2563EB")
    C_GRAY  = HexColor("#475569")
    C_LGRAY = HexColor("#94A3B8")
    C_BG    = HexColor("#F8FAFC")
    C_LINE  = HexColor("#E2E8F0")
    C_GREEN = HexColor("#16A34A")
    C_AMBER = HexColor("#D97706")

    # Estilos
    def _sty(name, font="Helvetica", size=10, color=None, after=4, align=TA_LEFT, bold=False):
        return ParagraphStyle(name, fontName=f"Helvetica-Bold" if bold else font,
                              fontSize=size, textColor=color or C_DARK,
                              spaceAfter=after, alignment=align)

    sTitle  = _sty("tt", size=20, bold=True, after=4)
    sSub    = _sty("ss", size=11, color=C_GRAY, after=3)
    sH2     = _sty("h2", size=13, bold=True, after=6, color=C_BLUE)
    sH3     = _sty("h3", size=11, bold=True, after=4)
    sBody   = _sty("bd", size=9,  color=C_GRAY, after=3)
    sSmall  = _sty("sm", size=8,  color=C_LGRAY, after=2)
    sCenter = _sty("ct", size=8,  color=C_LGRAY, after=2, align=TA_CENTER)
    sBit    = _sty("bt", size=9,  color=C_DARK, after=2)

    try:
        dt_s = datetime.strptime(start_str, "%Y-%m-%d")
        semana_num = dt_s.isocalendar()[1]
        fmt_s = dt_s.strftime("%d/%m/%Y")
        fmt_e = datetime.strptime(end_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        semana_num, fmt_s, fmt_e = "—", start_str, end_str

    story = []

    # ── PORTADA ───────────────────────────────────────────────
    story += [
        Spacer(1, 2.5*cm),
        Paragraph("Complejo Térmico Mejillones", sTitle),
        Paragraph("AES Andes · Monitoreo Operacional", sSub),
        Spacer(1, 0.8*cm),
        HRFlowable(width="100%", thickness=1.5, color=C_BLUE),
        Spacer(1, 0.6*cm),
        Paragraph(f"Reporte Operacional — Semana {semana_num}", _sty("rw", size=15, bold=True, after=4)),
        Paragraph(f"Período: {fmt_s} al {fmt_e}", _sty("rp", size=12, color=C_GRAY, after=8)),
        Spacer(1, 0.6*cm),
    ]

    # Resumen ejecutivo portada — KPIs del complejo
    resumen_rows = [["Unidad", "Prom Real (MW)", "Máx (MW)", "Mín (MW)", "Factor Carga", "Desv. vs Prog."]]
    for u in ["ANG1", "ANG2", "CCR1", "CCR2"]:
        k = _kpis_unidad(df_real, df_prog, u)
        resumen_rows.append([_UNIT_NAMES[u], k["prom"], k["max"], k["min"], k["fc"], k["desv"]])

    tbl_res = Table(resumen_rows, colWidths=[4*cm, 3*cm, 2.5*cm, 2.5*cm, 3*cm, 3*cm])
    tbl_res.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), C_BLUE),
        ("TEXTCOLOR",   (0,0), (-1,0), white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#F8FAFC"), white]),
        ("GRID",        (0,0), (-1,-1), 0.5, C_LINE),
        ("ALIGN",       (1,0), (-1,-1), "CENTER"),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    story += [tbl_res, Spacer(1, 0.6*cm)]

    # CMG resumen portada
    if not df_cmg.empty:
        story.append(Paragraph(
            f"CMG promedio período — Crucero 220kV: <b>{df_cmg['cmg_usd_mwh'].mean():.1f} USD/MWh</b>"
            f"  ·  Mín: {df_cmg['cmg_usd_mwh'].min():.1f}  ·  Máx: {df_cmg['cmg_usd_mwh'].max():.1f}",
            sBody
        ))

    # Limitaciones activas en portada
    if not df_lim.empty:
        n_act = int((df_lim["status"] == "pendiente").sum())
        n_sscc_lim = int(df_lim["afecta_sscc"].fillna(False).sum())
        story.append(Paragraph(
            f"Limitaciones de transmisión — <b>{n_act} activas</b> en el período"
            f"  ·  {n_sscc_lim} afectan SSCC",
            sBody
        ))

    story += [
        Spacer(1, 1.5*cm),
        HRFlowable(width="100%", thickness=0.5, color=C_LINE),
        Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}  ·  Fuente: API CEN SIPUB / OPS / CMG S3",
                  sCenter),
        PageBreak(),
    ]

    # ── PÁGINA CMG ────────────────────────────────────────────
    story += [Paragraph("Costo Marginal (CMG)", sH2), Spacer(1, 0.2*cm)]
    fig_cmg = _fig_cmg(df_cmg, figsize=(14, 3.5))
    story.append(RLImage(_fig_to_bytes(fig_cmg), width=17*cm, height=6*cm))
    if not df_cmg.empty:
        story.append(Paragraph(
            f"Nodo Crucero 220kV (preliminar)  ·  Prom: {df_cmg['cmg_usd_mwh'].mean():.1f}  "
            f"Mín: {df_cmg['cmg_usd_mwh'].min():.1f}  Máx: {df_cmg['cmg_usd_mwh'].max():.1f} USD/MWh",
            sSmall
        ))
    story += [Spacer(1, 0.5*cm), PageBreak()]

    # ── PÁGINAS POR UNIDAD ────────────────────────────────────
    for u in ["ANG1", "ANG2", "CCR1", "CCR2"]:
        k = _kpis_unidad(df_real, df_prog, u)
        story.append(Paragraph(_UNIT_NAMES[u], sH2))

        # KPIs en tabla horizontal
        kpi_data = [
            ["Prom Real", "Máx", "Mín", "Factor Carga", "Desv. vs Prog."],
            [f"{k['prom']} MW", f"{k['max']} MW", f"{k['min']} MW", k["fc"], f"{k['desv']} MW"],
        ]
        tbl_kpi = Table(kpi_data, colWidths=[3.4*cm]*5)
        tbl_kpi.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), HexColor("#EFF6FF")),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME",    (0,1), (-1,1), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("ALIGN",       (0,0), (-1,-1), "CENTER"),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("GRID",        (0,0), (-1,-1), 0.5, C_LINE),
            ("TOPPADDING",  (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("TEXTCOLOR",   (0,1), (-1,1), C_BLUE),
        ]))
        story += [tbl_kpi, Spacer(1, 0.3*cm)]

        # Gráfico gen real vs programada
        fig_g = _fig_generacion(df_real, df_prog, u, figsize=(14, 4))
        story.append(RLImage(_fig_to_bytes(fig_g), width=17*cm, height=7*cm))
        story.append(Spacer(1, 0.3*cm))

        # SSCC de la unidad
        if not df_sscc.empty:
            df_su = df_sscc[df_sscc["unidad"] == u]
            if not df_su.empty:
                story.append(Paragraph(f"SSCC — {len(df_su)} instrucciones en el período", sH3))
                sscc_rows = [["Fecha", "Inicio", "Fin", "Instrucción", "Motivo"]]
                for _, row in df_su.head(10).iterrows():
                    sscc_rows.append([
                        str(row.get("fecha", ""))[:10],
                        str(row.get("inicio_periodo", ""))[:5],
                        str(row.get("fin_periodo", ""))[:5],
                        str(row.get("instruccion_sscc", "")),
                        str(row.get("motivo", "") or "")[:60],
                    ])
                tbl_sscc = Table(sscc_rows, colWidths=[2.2*cm, 1.8*cm, 1.8*cm, 2.5*cm, 8.7*cm])
                tbl_sscc.setStyle(TableStyle([
                    ("BACKGROUND",  (0,0), (-1,0), HexColor("#F0FDF4")),
                    ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTSIZE",    (0,0), (-1,-1), 8),
                    ("GRID",        (0,0), (-1,-1), 0.4, C_LINE),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, HexColor("#F8FAFC")]),
                    ("TOPPADDING",  (0,0), (-1,-1), 3),
                    ("BOTTOMPADDING",(0,0),(-1,-1), 3),
                ]))
                story += [tbl_sscc, Spacer(1, 0.2*cm)]

        # Limitaciones de la unidad
        if not df_lim.empty and "_unidad" in df_lim.columns:
            df_lu = df_lim[df_lim["_unidad"] == u]
            if not df_lu.empty:
                story.append(Paragraph(f"Limitaciones — {len(df_lu)} en el período", sH3))
                lim_rows = [["Correlativo", "Status", "Apertura", "Retorno est.", "Potencia", "Afecta SSCC"]]
                for _, row in df_lu.head(8).iterrows():
                    corr = str(int(float(row["correlativo"]))) if pd.notna(row.get("correlativo")) else "—"
                    pot  = f"{int(float(row['potencia']))} MW" if pd.notna(row.get("potencia")) and float(row["potencia"]) > 0 else "—"
                    lim_rows.append([
                        corr,
                        str(row.get("status", "")),
                        str(row.get("fecha_perturbacion", ""))[:16],
                        str(row.get("fecha_retorno_estimada", "") or "—")[:10],
                        pot,
                        "Sí" if row.get("afecta_sscc") else "No",
                    ])
                tbl_lim = Table(lim_rows, colWidths=[2.5*cm, 2.2*cm, 3.5*cm, 2.5*cm, 2.5*cm, 2.8*cm])
                tbl_lim.setStyle(TableStyle([
                    ("BACKGROUND",  (0,0), (-1,0), HexColor("#FFFBEB")),
                    ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
                    ("FONTSIZE",    (0,0), (-1,-1), 8),
                    ("GRID",        (0,0), (-1,-1), 0.4, C_LINE),
                    ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, HexColor("#F8FAFC")]),
                    ("TOPPADDING",  (0,0), (-1,-1), 3),
                    ("BOTTOMPADDING",(0,0),(-1,-1), 3),
                ]))
                story += [tbl_lim, Spacer(1, 0.2*cm)]

        # Bitácora
        try:
            novedades = qry(
                "SELECT fecha, hora, comentario FROM bitacora "
                "WHERE unidad=%s AND fecha BETWEEN %s AND %s ORDER BY fecha, hora",
                (u, start_str, end_str)
            )
        except: novedades = pd.DataFrame()

        if not novedades.empty:
            story.append(Paragraph("Bitácora", sH3))
            for _, row in novedades.iterrows():
                try: fd = datetime.strptime(str(row["fecha"]), "%Y-%m-%d").strftime("%d/%m/%Y")
                except: fd = str(row["fecha"])
                story.append(Paragraph(
                    f"<b>{fd} {str(row['hora'])[:5]}</b> — {str(row['comentario'])}", sBit
                ))

        story += [
            Spacer(1, 0.4*cm),
            HRFlowable(width="100%", thickness=0.4, color=C_LINE),
            Paragraph(f"Reporte generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", sCenter),
            PageBreak(),
        ]

    # Quitar último PageBreak
    if story and isinstance(story[-1], PageBreak):
        story.pop()

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════
# GENERADOR PPT — Presentación Operacional
# ══════════════════════════════════════════════════════════════
def generar_ppt(df_real, df_prog, df_cmg, start_str, end_str,
                df_sscc=None, df_lim=None):
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    import io as _io

    if df_sscc is None: df_sscc = pd.DataFrame()
    if df_lim  is None: df_lim  = pd.DataFrame()

    # Colores
    RGB_DARK  = RGBColor(0x0F, 0x17, 0x2A)
    RGB_BLUE  = RGBColor(0x25, 0x63, 0xEB)
    RGB_GRAY  = RGBColor(0x47, 0x55, 0x69)
    RGB_LGRAY = RGBColor(0x94, 0xA3, 0xB8)
    RGB_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    RGB_BG    = RGBColor(0xF8, 0xFA, 0xFC)
    RGB_AMBER = RGBColor(0xD9, 0x77, 0x06)
    RGB_GREEN = RGBColor(0x16, 0xA3, 0x4A)

    try:
        dt_s = datetime.strptime(start_str, "%Y-%m-%d")
        semana_num = dt_s.isocalendar()[1]
        fmt_s = dt_s.strftime("%d/%m/%Y")
        fmt_e = datetime.strptime(end_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        semana_num, fmt_s, fmt_e = "—", start_str, end_str

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]  # completamente en blanco

    def _add_slide():
        return prs.slides.add_slide(blank)

    def _bg(slide, color=RGB_WHITE):
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def _txb(slide, text, l, t, w, h, size=18, bold=False, color=RGB_DARK, align=PP_ALIGN.LEFT, wrap=True):
        tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = wrap
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        return tb

    def _rect(slide, l, t, w, h, color=RGB_BLUE):
        from pptx.util import Inches as _I
        shp = slide.shapes.add_shape(1, _I(l), _I(t), _I(w), _I(h))
        shp.fill.solid()
        shp.fill.fore_color.rgb = color
        shp.line.fill.background()
        return shp

    def _img(slide, fig, l, t, w, h):
        buf = _fig_to_bytes(fig, dpi=150)
        slide.shapes.add_picture(buf, Inches(l), Inches(t), Inches(w), Inches(h))

    # ── SLIDE 1: PORTADA ──────────────────────────────────────
    sl = _add_slide()
    _bg(sl, RGB_DARK)
    _rect(sl, 0, 0, 13.33, 0.12, RGB_BLUE)
    _rect(sl, 0, 7.38, 13.33, 0.12, RGB_BLUE)
    _txb(sl, "Complejo Térmico Mejillones", 0.6, 1.8, 12, 1.0,
         size=36, bold=True, color=RGB_WHITE)
    _txb(sl, "AES Andes · Monitoreo Operacional", 0.6, 2.8, 12, 0.6,
         size=18, color=RGB_LGRAY)
    _txb(sl, f"Reporte Semana {semana_num}  ·  {fmt_s} — {fmt_e}", 0.6, 3.5, 12, 0.5,
         size=16, color=RGB_BLUE)
    _txb(sl, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0.6, 6.9, 12, 0.4,
         size=10, color=RGB_LGRAY)

    # ── SLIDE 2: RESUMEN EJECUTIVO ─────────────────────────────
    sl = _add_slide()
    _bg(sl, RGB_BG)
    _rect(sl, 0, 0, 13.33, 0.55, RGB_BLUE)
    _txb(sl, "Resumen Ejecutivo", 0.3, 0.08, 10, 0.4, size=18, bold=True, color=RGB_WHITE)

    col_x = [0.3, 3.5, 6.3, 9.1]
    unidades = ["ANG1", "ANG2", "CCR1", "CCR2"]
    col_colors = [RGBColor(0x7C,0x3A,0xED), RGBColor(0x25,0x63,0xEB),
                  RGBColor(0xCA,0x8A,0x04), RGBColor(0x16,0xA3,0x4A)]
    for i, (u, cx, cc) in enumerate(zip(unidades, col_x, col_colors)):
        k = _kpis_unidad(df_real, df_prog, u)
        _rect(sl, cx, 0.7, 2.9, 0.35, cc)
        _txb(sl, _UNIT_NAMES[u], cx+0.1, 0.73, 2.7, 0.3, size=13, bold=True, color=RGB_WHITE)
        items = [
            f"Prom real:  {k['prom']} MW",
            f"Máx:  {k['max']} MW",
            f"Mín:  {k['min']} MW",
            f"Factor carga:  {k['fc']}",
            f"Desv. prog.:  {k['desv']} MW",
        ]
        for j, txt in enumerate(items):
            _txb(sl, txt, cx+0.1, 1.15 + j*0.48, 2.8, 0.45, size=11, color=RGB_DARK)

    # CMG + Limitaciones resumen abajo
    if not df_cmg.empty:
        cmg_txt = (f"CMG Crucero 220kV  ·  Prom: {df_cmg['cmg_usd_mwh'].mean():.1f}  "
                   f"Mín: {df_cmg['cmg_usd_mwh'].min():.1f}  Máx: {df_cmg['cmg_usd_mwh'].max():.1f} USD/MWh")
        _txb(sl, cmg_txt, 0.3, 6.7, 8, 0.4, size=10, color=RGB_GRAY)
    if not df_lim.empty:
        n_act = int((df_lim["status"] == "pendiente").sum())
        _txb(sl, f"Limitaciones activas: {n_act}", 9.0, 6.7, 4, 0.4, size=10,
             bold=(n_act > 0), color=RGB_AMBER if n_act > 0 else RGB_GRAY)

    # ── SLIDE 3: CMG ──────────────────────────────────────────
    sl = _add_slide()
    _bg(sl, RGB_BG)
    _rect(sl, 0, 0, 13.33, 0.55, RGBColor(0x08, 0x91, 0xB2))
    _txb(sl, "Costo Marginal — CMG", 0.3, 0.08, 10, 0.4, size=18, bold=True, color=RGB_WHITE)
    fig_cmg = _fig_cmg(df_cmg, figsize=(13, 4.5))
    _img(sl, fig_cmg, 0.3, 0.7, 12.7, 5.5)
    if not df_cmg.empty:
        _txb(sl, f"Nodo Crucero 220kV (preliminar)  ·  Prom: {df_cmg['cmg_usd_mwh'].mean():.1f}  "
             f"Mín: {df_cmg['cmg_usd_mwh'].min():.1f}  Máx: {df_cmg['cmg_usd_mwh'].max():.1f} USD/MWh",
             0.3, 6.4, 12, 0.5, size=10, color=RGB_GRAY)

    # ── SLIDES POR UNIDAD ─────────────────────────────────────
    for u, cc in zip(unidades, col_colors):
        k = _kpis_unidad(df_real, df_prog, u)

        # Slide generación
        sl = _add_slide()
        _bg(sl, RGB_BG)
        _rect(sl, 0, 0, 13.33, 0.55, cc)
        _txb(sl, f"{_UNIT_NAMES[u]} — Generación", 0.3, 0.08, 10, 0.4,
             size=18, bold=True, color=RGB_WHITE)

        # KPIs en banda
        kpi_labels = ["Prom Real", "Máximo", "Mínimo", "Factor Carga", "Desv. Prog."]
        kpi_vals   = [f"{k['prom']} MW", f"{k['max']} MW", f"{k['min']} MW", k["fc"], f"{k['desv']} MW"]
        for i, (lbl, val) in enumerate(zip(kpi_labels, kpi_vals)):
            bx = 0.3 + i * 2.6
            _rect(sl, bx, 0.65, 2.4, 0.28, RGBColor(0xEF,0xF6,0xFF))
            _txb(sl, lbl, bx+0.05, 0.67, 2.3, 0.22, size=8, color=RGB_GRAY, align=PP_ALIGN.CENTER)
            _txb(sl, val,  bx+0.05, 0.88, 2.3, 0.28, size=11, bold=True, color=cc, align=PP_ALIGN.CENTER)

        fig_g = _fig_generacion(df_real, df_prog, u, figsize=(13, 4.2))
        _img(sl, fig_g, 0.3, 1.22, 12.7, 5.2)

        # Slide SSCC + Limitaciones + Bitácora
        sl = _add_slide()
        _bg(sl, RGB_BG)
        _rect(sl, 0, 0, 13.33, 0.55, cc)
        _txb(sl, f"{_UNIT_NAMES[u]} — SSCC / Limitaciones / Bitácora",
             0.3, 0.08, 12, 0.4, size=18, bold=True, color=RGB_WHITE)

        cur_y = 0.7

        # SSCC
        if not df_sscc.empty:
            df_su = df_sscc[df_sscc["unidad"] == u].head(6)
            if not df_su.empty:
                _txb(sl, f"SSCC ({len(df_sscc[df_sscc['unidad']==u])} instrucciones)", 0.3, cur_y, 6, 0.3,
                     size=11, bold=True, color=RGB_GREEN)
                cur_y += 0.32
                for _, row in df_su.iterrows():
                    txt = (f"{str(row.get('fecha',''))[:10]}  {str(row.get('inicio_periodo',''))[:5]}–"
                           f"{str(row.get('fin_periodo',''))[:5]}  [{row.get('instruccion_sscc','')}]  "
                           f"{str(row.get('motivo','') or '')[:55]}")
                    _txb(sl, txt, 0.4, cur_y, 12.5, 0.3, size=9, color=RGB_DARK)
                    cur_y += 0.3

        cur_y += 0.1

        # Limitaciones
        if not df_lim.empty and "_unidad" in df_lim.columns:
            df_lu = df_lim[df_lim["_unidad"] == u].head(5)
            if not df_lu.empty:
                _txb(sl, f"Limitaciones ({len(df_lim[df_lim['_unidad']==u])})", 0.3, cur_y, 6, 0.3,
                     size=11, bold=True, color=RGB_AMBER)
                cur_y += 0.32
                for _, row in df_lu.iterrows():
                    corr = str(int(float(row["correlativo"]))) if pd.notna(row.get("correlativo")) else "—"
                    pot  = f"{int(float(row['potencia']))} MW" if pd.notna(row.get("potencia")) and float(row["potencia"]) > 0 else ""
                    txt  = (f"N.{corr}  [{row.get('status','')}]  "
                            f"{str(row.get('fecha_perturbacion',''))[:16]}  {pot}  "
                            f"{'[Afecta SSCC]' if row.get('afecta_sscc') else ''}")
                    _txb(sl, txt, 0.4, cur_y, 12.5, 0.3, size=9, color=RGB_DARK)
                    cur_y += 0.3

        cur_y += 0.1

        # Bitácora
        try:
            novedades = qry(
                "SELECT fecha, hora, comentario FROM bitacora "
                "WHERE unidad=%s AND fecha BETWEEN %s AND %s ORDER BY fecha, hora",
                (u, start_str, end_str)
            )
        except: novedades = pd.DataFrame()

        if not novedades.empty and cur_y < 6.8:
            _txb(sl, "Bitácora", 0.3, cur_y, 6, 0.3, size=11, bold=True, color=RGB_DARK)
            cur_y += 0.32
            for _, row in novedades.head(4).iterrows():
                try: fd = datetime.strptime(str(row["fecha"]), "%Y-%m-%d").strftime("%d/%m/%Y")
                except: fd = str(row["fecha"])
                _txb(sl, f"{fd} {str(row['hora'])[:5]} — {str(row['comentario'])[:90]}",
                     0.4, cur_y, 12.5, 0.32, size=9, color=RGB_DARK)
                cur_y += 0.32

    # ── SLIDE FINAL: LIMITACIONES RESUMEN ─────────────────────
    if not df_lim.empty:
        sl = _add_slide()
        _bg(sl, RGB_BG)
        _rect(sl, 0, 0, 13.33, 0.55, RGB_AMBER)
        _txb(sl, "Limitaciones de Transmisión — Resumen", 0.3, 0.08, 12, 0.4,
             size=18, bold=True, color=RGB_WHITE)
        cur_y = 0.7
        for _, row in df_lim.head(12).iterrows():
            corr   = str(int(float(row["correlativo"]))) if pd.notna(row.get("correlativo")) else "—"
            unidad = row.get("_unidad", "") if "_unidad" in df_lim.columns else ""
            pot    = f"{int(float(row['potencia']))} MW" if pd.notna(row.get("potencia")) and float(row["potencia"]) > 0 else "—"
            txt = (f"N.{corr}  {unidad}  [{row.get('status','')}]  "
                   f"Apertura: {str(row.get('fecha_perturbacion',''))[:16]}  "
                   f"Potencia: {pot}  "
                   f"{'[Afecta SSCC]' if row.get('afecta_sscc') else ''}")
            _txb(sl, txt, 0.3, cur_y, 12.7, 0.35, size=9, color=RGB_DARK)
            cur_y += 0.38
            if cur_y > 7.0: break

    buf = _io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()
