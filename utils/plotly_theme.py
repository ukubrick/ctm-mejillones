"""
utils/plotly_theme.py — Tema Plotly compartido del dashboard (patrón Pulsar).

Centraliza el layout que antes se copiaba a mano en cada componente
(costo, gen_unidad, sscc, despacho_cmg, limitaciones, ml_analysis) y los
helpers de estilo de series de tiempo. Portado de Pulsar
(ernc-aes-dashboard/components/graficos.py) y extendido.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from config import BG, BG_TRANSP, C_GRID, C_MUTED, C_TEXTO, SERIE

TZ_CHILE = ZoneInfo("America/Santiago")


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """'#RRGGBB' → 'rgba(r,g,b,a)' para fills translúcidos."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def add_linea_ahora(fig, x_min=None, x_max=None):
    """Línea vertical punteada en el instante actual (hora Santiago).

    Separa el pasado (gen. real) del proyectado (PCP/PID/forecast). Solo se
    dibuja si el 'ahora' cae dentro del rango visible [x_min, x_max].
    """
    ahora = datetime.now(TZ_CHILE).replace(tzinfo=None)
    if x_min is not None and ahora < x_min:
        return
    if x_max is not None and ahora > x_max:
        return
    fig.add_vline(
        x=ahora, line_dash="dash", line_color=C_MUTED, line_width=1,
        annotation_text="ahora", annotation_position="top",
        annotation_font_size=9, annotation_font_color=C_MUTED,
    )


def apply_aes_layout(fig, title=None, height=300, transparent=True,
                     y_title=None, x_time=True, legend_bottom=False, **kw):
    """Layout AES estándar. `transparent=False` usa el fondo gris BG."""
    bg = BG_TRANSP if transparent else BG
    legend = (dict(orientation="h", y=-0.2, font=dict(size=10, color="#475569"))
              if legend_bottom else
              dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                   font=dict(size=10, color="#475569"), bgcolor=BG_TRANSP))
    layout = dict(
        template="plotly_white", height=height,
        margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        plot_bgcolor=bg, paper_bgcolor=BG_TRANSP,
        legend=legend, hovermode="x unified",
        hoverlabel=dict(bgcolor="#1A1F36", font_color="#F5F7FA", bordercolor="#3B4CE8"),
    )
    if title:
        layout["title"] = dict(text=title, font=dict(size=13, color=C_TEXTO), x=0)
    layout.update(kw)
    fig.update_layout(**layout)
    fig.update_xaxes(showgrid=False, tickfont=dict(color=C_MUTED, size=10),
                     **({"tickformat": "%d/%m\n%H:%M"} if x_time else {}))
    fig.update_yaxes(gridcolor=C_GRID, zeroline=False,
                     tickfont=dict(color=C_MUTED, size=10),
                     title_font=dict(color=C_MUTED, size=10))
    if y_title:
        fig.update_yaxes(title_text=y_title)
    return fig


# Convención de series de tiempo (patrón Pulsar): la Real es la línea
# protagonista (sólida, gruesa, con fill suave); PCP dashed, PID dotted.
def estilo_serie(tipo: str) -> dict:
    # Jerarquía de trazo: Real sólida y gruesa (protagonista, con área) >
    # PID ámbar discontinua (programa operativo) > PCP gris punteada (referencia).
    estilos = {
        "real":     dict(line=dict(color=SERIE["real"], width=2.6, shape="spline", smoothing=0.4),
                         fill="tozeroy", fillcolor=hex_to_rgba(SERIE["real"], 0.07)),
        "prog":     dict(line=dict(color=SERIE["prog"], width=1.6, dash="dot")),
        "prog_pid": dict(line=dict(color=SERIE["prog_pid"], width=2.2, dash="dash")),
        "cmg":      dict(line=dict(color=SERIE["cmg"], width=2.4, shape="spline", smoothing=0.4),
                         fill="tozeroy", fillcolor=SERIE["cmg_fill"]),
        "cmg_prog": dict(line=dict(color=SERIE["cmg_prog"], width=1.8, dash="dash")),
        "demanda":  dict(line=dict(color=SERIE["demanda"], width=1.4, dash="dot")),
    }
    return estilos[tipo]


def hover(nombre: str, unidad_medida: str, extra: str = "") -> str:
    """Hovertemplate estándar: valor + unidad y <extra> explicativo (didáctico)."""
    fmt = "%{y:,.0f}" if unidad_medida == "MWh" else "%{y:.1f}"
    tail = f"<extra>{extra}</extra>" if extra else "<extra></extra>"
    return f"<b>{nombre}</b> %{{x|%d/%m %H:%M}}<br>{fmt} {unidad_medida}{tail}"
