"""Componentes Manim e dados já registrados no repositório."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

from manim import (
    Axes, DashedLine, Dot, FadeIn, Line, ManimColor, Rectangle, Scene, SVGMobject,
    Text, VGroup, VMobject, config, DOWN, LEFT, RIGHT, UP, WHITE, interpolate_color,
)
from matplotlib import rc_context
from matplotlib.mathtext import math_to_image
from manimpango import list_fonts
import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / "data" / "output"
SMALL = "6_2_1439_3_S_1-9"
GIANT = "750_10_1439_5_S_1-9"
FUNDO = "#14171c"
INK = "#F1F3F9"
MUTED = "#B5C0D0"
GRID = "#435063"
GOLD = "#F4D35E"
CYAN = "#78D7E9"
CORAL = "#FF967F"
GREEN = "#8BD49C"
COLORS = {
    key: interpolate_color(ManimColor(color), WHITE, 0.35)
    for key, color in {
        "age": "#8e52aa", "spea2": "#087b9a", "moead": "#ce7110",
        "vns_vnd": "#bd3c5a", "vns_vnd_new": "#347d36",
        "exact_dp": "#b18a11", "ociosidade": "#478c9b", "construtiva": "#a269b3",
    }.items()
}
LABELS = {
    "age": "AGE-MOEA", "spea2": "SPEA2", "moead": "MOEA/D",
    "vns_vnd": "VNS original", "vns_vnd_new": "VNS revisto",
    "exact_dp": "DP própria", "ociosidade": "Ociosidade", "construtiva": "Construtiva",
}
JOBS = (GOLD, CYAN, GREEN, CORAL, "#C1A5EE", "#92B3FA")


# Fora do Windows, a fonte padrão pode ser larga demais para as margens.
FONTE = "Lato" if sys.platform != "win32" and "Lato" in list_fonts() else ""


def pos(x, y):
    return np.array([x, y, 0.0])


def text(value, size=30, color=INK, width=12.85, bold=False):
    label = Text(value, font_size=size, color=color, weight="BOLD" if bold else "NORMAL",
                 line_spacing=1.0, font=FONTE)
    if label.width > width:
        label.scale_to_fit_width(width)
    return label


def left(obj, x, y):
    return obj.move_to(pos(x, y), aligned_edge=LEFT)


def lines(values, x, y, *, width=4.9, size=28, gap=0.7, color=INK):
    return VGroup(*(left(text(value, size, color, width), x, y - i * gap)
                    for i, value in enumerate(values)))


def rule(y, x0=-6.55, x1=6.55):
    return Line(pos(x0, y), pos(x1, y), color=GRID, stroke_width=1)


def formula(source, width=11.8, height=0.69, color=INK):
    """Renderiza fonte LaTeX compatível com MathText em SVG, sem TeX externo."""
    location = Path(config.media_dir) / "formulas"
    location.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(f"transparent:{color}:{source}".encode()).hexdigest()[:16]
    path = location / f"{fingerprint}.svg"
    if not path.is_file():
        with rc_context({"savefig.transparent": True}):
            math_to_image(f"${source}$", path, format="svg", color=color)
    obj = SVGMobject(str(path), height=height, color=color)
    if obj.width > width:
        obj.scale_to_fit_width(width)
    return obj


def table(headings, rows, widths, *, x=-6.3, y=1.65, gap=0.59, size=26, colors=None):
    anchors = np.cumsum([x, *widths[:-1]])
    header = VGroup(*(left(text(value, size - 2, MUTED, width - .22, bold=True), at, y)
                      for value, at, width in zip(headings, anchors, widths)))
    result = VGroup(header, rule(y - gap * .49, x, x + sum(widths)))
    for index, row in enumerate(rows):
        color = colors[index] if colors else INK
        result.add(VGroup(*(left(text(str(value), size, color if col == 0 else INK, width - .22,
                                      bold=col == 0), at, y - gap * (index + 1))
                            for col, (value, at, width) in enumerate(zip(row, anchors, widths)))))
    return result


def axes(x_range=(0, 7, 1), y_range=(0, 6, 1), *, center=(-2.55, -.38), width=6.9,
         height=3.65, x_label="Cmax", y_label="TEC", numbers=False):
    opts = {"include_ticks": numbers, "include_numbers": False, "font_size": 19,
            "color": MUTED, "stroke_width": 1.6}
    axis = Axes(x_range=x_range, y_range=y_range, x_length=width, y_length=height,
                tips=True, axis_config=opts).move_to(pos(*center))
    labels = VGroup(
        text(x_label, 21, MUTED).next_to(axis.x_axis, DOWN, buff=.49 if numbers else .22),
        text(y_label, 21, MUTED).next_to(axis.y_axis, UP, buff=.13).align_to(axis.y_axis, LEFT),
    )
    if numbers:
        x0, y0 = axis.x_axis.get_start(), axis.y_axis.get_start()
        for tick in axis.x_axis.get_tick_range():
            p = axis.x_axis.n2p(tick)
            labels.add(text(f"{tick:g}".replace(".", ","), 16, MUTED).move_to(pos(p[0], x0[1] - .20)))
        for tick in axis.y_axis.get_tick_range():
            p = axis.y_axis.n2p(tick)
            if p[1] > x0[1] + .10:
                labels.add(text(f"{tick:g}".replace(".", ","), 16, MUTED).move_to(pos(y0[0] - .31, p[1])))
    return axis, labels


def dots(axis, points, color, radius=.08):
    return VGroup(*(Dot(axis.c2p(*point), radius=radius, color=color) for point in points))


def staircase(axis, points, color, width=2.5):
    front = sorted(points)
    vertices = [axis.c2p(*front[0])]
    for (x0, y0), (x1, y1) in zip(front, front[1:]):
        vertices.extend((axis.c2p(x1, y0), axis.c2p(x1, y1)))
    return VMobject(stroke_color=color, stroke_width=width).set_points_as_corners(vertices)


def gantt(rows, *, total, x=-5.6, y=.7, width=9.3, lane=.87, bar=.49, peaks=(),
          setups=(), time_label="tempo"):
    """Barras (máquina, tarefa, início, fim) e faixas para os intervalos de ponta."""
    def at(t):
        return x + t / total * width

    last = max(m for m, *_ in rows)
    chart = VGroup()
    for start, end in peaks:
        chart.add(Rectangle(width=at(end) - at(start), height=lane * (last + 1) + .14,
                            stroke_width=0, fill_color=CORAL, fill_opacity=.15)
                  .move_to(pos((at(start) + at(end)) / 2, y - last * lane / 2)))
    for machine in range(last + 1):
        level = y - machine * lane
        chart.add(Line(pos(x, level), pos(at(total), level), color=GRID, stroke_width=1.5),
                  text(f"M{machine + 1}", 22, MUTED).move_to(pos(x - .45, level)))
    for machine, start, end in setups:
        chart.add(Rectangle(width=at(end) - at(start), height=bar * .65, stroke_width=0,
                            fill_color=MUTED, fill_opacity=.58)
                  .move_to(pos((at(start) + at(end)) / 2, y - machine * lane)))
    blocks = VGroup()
    for machine, job, start, end in rows:
        start_x, end_x = at(start), at(end)
        rect = Rectangle(width=end_x - start_x, height=bar, stroke_width=0,
                         fill_color=JOBS[job % len(JOBS)], fill_opacity=1)
        rect.move_to(pos((start_x + end_x) / 2, y - machine * lane))
        job_label = text(str(job + 1), 23, FUNDO, max(rect.width - .08, .15), bold=True).move_to(rect)
        blocks.add(VGroup(rect, job_label))
    if time_label:
        chart.add(left(text(time_label, 21, MUTED), x, y - last * lane - .58))
    return chart, blocks


@lru_cache(maxsize=None)
def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def small_fronts():
    return {
        "exact_dp": read_json(ROOT / "data" / "baselines" / f"{SMALL}_custom_exact_dp.json")["front"],
        "construtiva": read_json(OUTPUT / "heuristica_construtiva" / f"{SMALL}.json")["front"],
        "ociosidade": read_json(OUTPUT / "heuristica_ociosidade" / f"{SMALL}.json")["front"],
    }


def pt(value, decimals=3):
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}".translate(str.maketrans(",.", ".,"))


class DeckScene(Scene):
    chapter = ""
    number = 0

    def beat(self, identifier, title, source, subtitle=None):
        self.clear()
        self.camera.background_color = FUNDO
        self.next_section(identifier)
        chapter = left(text(self.chapter, 21, CYAN, bold=True), -6.55, 3.52)
        heading = left(text(title, 46, bold=True), -6.55, 2.80)
        footer = left(text(source, 17, MUTED, width=11.85), -6.55, -3.60)
        number = text(f"{self.number:02d} / 10", 17, MUTED).move_to(pos(6.55, -3.60), aligned_edge=RIGHT)
        progress = Line(pos(-6.55, 3.88), pos(-6.55 + 13.1 * self.number / 10, 3.88),
                        color=CYAN, stroke_width=3)
        self.add(rule(-3.35), rule(3.88), progress, chapter, heading, footer, number)
        if subtitle:
            self.add(left(text(subtitle, 23, MUTED), -6.55, 2.14))

    def reveal(self, *items, run_time=.55):
        self.play(*(FadeIn(item, shift=UP * .09) for item in items), run_time=run_time)

    def hold(self):
        # Verifica margens de todos os elementos da composição final da seção.
        for item in self.mobjects:
            if (item.get_left()[0] < -6.9 or item.get_right()[0] > 6.9
                    or item.get_bottom()[1] < -3.91 or item.get_top()[1] > 3.94):
                raise ValueError(f"Elemento fora da margem em {type(self).__name__}: {item}")
        self.wait(.62)
