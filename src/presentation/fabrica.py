"""Fábrica persistente da introdução: máquinas, linha do tempo, relógio e medidores."""

from functools import lru_cache

from manim import (
    Circle, Dot, FadeIn, FadeOut, Line, Rectangle, RoundedRectangle,
    ValueTracker, VGroup, VMobject, AnnularSector, always_redraw, PI, RIGHT,
)
import numpy as np

from visual import (
    CORAL, CYAN, FUNDO, GOLD, GREEN, GRID, HERE, INK, JOBS, MUTED,
    DeckScene, left, pos, pt, read_json, rule, text,
)

DADOS = read_json(HERE / "data" / "didatica.json")
PONTA = tuple(DADOS["peak"])
FORA, NA_PONTA = DADOS["rates"]
TOTAL = 20
CORES = (*JOBS, "#F2A6C8", "#B9D66B")
FAIXAS = (1.15, .05, -1.05)
ALTURA = .52
ESTADOS = {"processando": GREEN, "setup": MUTED, "espera": GOLD, "livre": GRID}


def plano(cmax):
    return next(p for p in DADOS["front"] if p["cmax"] == cmax)


def hora(t):
    minutes = round(((DADOS["inicio_relogio"] + t) % 24) * 60) % 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def custo_ate(p, t):
    """TEC acumulado até t; cada intervalo contribui na proporção já executada."""
    return sum(c * min(1, max(0, t - b["start"] - k))
               for b in p["blocks"] for k, c in enumerate(b["costs"]))


@lru_cache(maxsize=None)
def _rotulo(value, size, color, bold):
    return text(value, size, color, bold=bold)


def rotulo(value, size=24, color=INK, bold=False):
    return _rotulo(value, size, color, bold).copy()


class Eixo:
    """Conversão tempo → tela; as mesmas barras servem ao Gantt grande e aos pequenos."""

    def __init__(self, x=-5.2, passo=.40, faixas=FAIXAS, altura=ALTURA, total=TOTAL):
        self.x, self.passo, self.faixas, self.altura, self.total = x, passo, faixas, altura, total

    def at(self, t):
        return self.x + t * self.passo

    def caixa(self, machine, start, end, fator=1.0, **estilo):
        opts = dict(stroke_width=0, fill_opacity=1) | estilo
        return Rectangle(width=max(1e-3, (end - start) * self.passo), height=self.altura * fator,
                         **opts).move_to(pos(self.at((start + end) / 2), self.faixas[machine]))

    def tarefa(self, job, machine, start, end, mode=1):
        # A altura representa o fator de potência do modo.
        rect = self.caixa(machine, start, end, DADOS["factor"][mode], fill_color=CORES[job])
        label = rotulo(f"T{job + 1}", 19 if self.altura > .4 else 13, FUNDO, True)
        limit = min(rect.width * .8 / label.width, rect.height * .8 / label.height, 1)
        return VGroup(rect, label.scale(limit).move_to(rect))

    def bloco(self, b):
        return self.tarefa(b["job"], b["machine"], b["start"], b["end"], b["mode"])

    def setup(self, b):
        end = b["start"] - b["wait"]
        box = self.caixa(b["machine"], end - b["setup"], end, .45, fill_color=MUTED,
                         fill_opacity=.6 if b["setup"] else 0)
        return box

    def espera(self, b):
        return self.caixa(b["machine"], b["start"] - b["wait"], b["start"], .45, fill_color=GOLD,
                          fill_opacity=.12 if b["wait"] else 0, stroke_color=GOLD,
                          stroke_width=1.5 if b["wait"] else 0)

    def faixa_ponta(self):
        top, low = self.faixas[0] + self.altura * .95, self.faixas[-1] - self.altura * .95
        return Rectangle(width=(PONTA[1] - PONTA[0]) * self.passo, height=top - low, stroke_width=0,
                         fill_color=CORAL, fill_opacity=.16).move_to(
                             pos(self.at(sum(PONTA) / 2), (top + low) / 2))

    def trilhos(self):
        return VGroup(*(Line(pos(self.x, y), pos(self.at(self.total), y), color=GRID, stroke_width=1.5)
                        for y in self.faixas))

    def horas(self, y, salto=2, size=15):
        return VGroup(*(VGroup(Line(pos(self.at(t), y + .12), pos(self.at(t), y + .04), color=MUTED, stroke_width=1),
                               text(f"{(8 + t) % 24}h", size, MUTED).move_to(pos(self.at(t), y - .10)))
                        for t in range(0, self.total + 1, salto)))

    def cursor(self, tracker, color=INK):
        top, low = self.faixas[0] + self.altura, self.faixas[-1] - self.altura
        return always_redraw(lambda: Line(pos(self.at(tracker.get_value()), top),
                                          pos(self.at(tracker.get_value()), low), color=color, stroke_width=2.5))

    def progresso(self, b, tracker):
        """Sombra fixa mais preenchimento que acompanha o cursor."""
        def fill():
            t = min(b["end"], max(b["start"], tracker.get_value()))
            return self.caixa(b["machine"], b["start"], t, DADOS["factor"][b["mode"]],
                              fill_color=CORES[b["job"]], fill_opacity=1 if t > b["start"] else 0)
        ghost = self.bloco(b)
        ghost[0].set_fill(opacity=.25)
        name = ghost[1]
        name.set_color(INK)

        def pintar(m):
            m.set_color(FUNDO if tracker.get_value() >= (b["start"] + b["end"]) / 2 else INK)
        name.add_updater(pintar)
        return ghost[0], always_redraw(fill), name


EIXO = Eixo()


def maquina(indice):
    y = FAIXAS[indice]
    body = RoundedRectangle(width=1.18, height=.86, corner_radius=.12, stroke_color=GRID, stroke_width=2,
                            fill_color=FUNDO, fill_opacity=1).move_to(pos(-6.12, y))
    center = pos(-5.86, y + .05)
    wheel = VGroup(Circle(radius=.21, color=MUTED, stroke_width=3).move_to(center),
                   *(Line(center, center + .21 * np.array([np.cos(a), np.sin(a), 0]), color=MUTED, stroke_width=3)
                     for a in (PI / 2, PI / 2 + 2 * PI / 3, PI / 2 + 4 * PI / 3)))
    return VGroup(body, text(f"M{indice + 1}", 24, bold=True).move_to(pos(-6.4, y + .05)), wheel)


def curva_tarifa(eixo=EIXO, y=-2.95):
    """Altura proporcional ao preço do intervalo."""
    low, high = y + .25, y + .75
    points = [(0, low), (PONTA[0], low), (PONTA[0], high), (PONTA[1], high), (PONTA[1], low), (TOTAL, low)]
    line = VMobject(color=GOLD, stroke_width=3).set_points_as_corners([pos(eixo.at(t), v) for t, v in points])
    labels = VGroup(text("tarifa", 17, MUTED).move_to(pos(-5.75, low)),
                    text(f"fora da ponta · $ {pt(FORA, 2)}", 17, GOLD).move_to(pos(eixo.at(4.7), low + .20)),
                    text(f"$ {pt(NA_PONTA, 2)}", 17, CORAL, bold=True).move_to(pos(eixo.at(15), high - .05)),)
    return line, labels


def relogio(tracker, centro=(4.95, 1.34), raio=.72):
    cx, cy = centro

    def angulo(t):
        return PI / 2 - 2 * PI * ((8 + t) % 24) / 24

    peak = AnnularSector(inner_radius=raio * .78, outer_radius=raio, start_angle=angulo(PONTA[1]),
                         angle=angulo(PONTA[0]) - angulo(PONTA[1]), color=CORAL,
                         fill_opacity=.85, stroke_width=0)
    peak.shift(pos(cx, cy) - peak.get_arc_center())
    ring = Circle(radius=raio, color=MUTED, stroke_width=2.5).move_to(pos(cx, cy))
    marks = VGroup(*(text(str(h), 13, MUTED).move_to(
        pos(cx + raio * 1.2 * np.cos(PI / 2 - h * PI / 12), cy + raio * 1.2 * np.sin(PI / 2 - h * PI / 12)))
        for h in (0, 6, 12, 18)))
    hand = always_redraw(lambda: Line(pos(cx, cy), pos(cx + raio * .74 * np.cos(angulo(tracker.get_value())),
                                                        cy + raio * .74 * np.sin(angulo(tracker.get_value()))),
                                      color=INK, stroke_width=4))
    digital = always_redraw(lambda: rotulo(hora(tracker.get_value()), 27, INK, True).move_to(pos(cx, cy - raio - .48)))
    return VGroup(ring, peak, marks, Dot(pos(cx, cy), radius=.05, color=INK)), hand, digital


def medidor(nome, valor, y, color=GOLD, x=3.75, size=36):
    """Rótulo fixo e número refeito a cada quadro."""
    return (left(text(nome, 19, MUTED), x, y + .34),
            always_redraw(lambda: left(rotulo(valor(), size, color, True), x, y - .10)))


class CenaContinua(DeckScene):
    """Trechos que não limpam a tela: só o título muda, a fábrica permanece."""

    total = 3
    cabecalho = None
    titulo = None

    def abrir(self, titulo=None):
        self.camera.background_color = FUNDO
        self.cabecalho = VGroup(rule(-3.35), rule(3.88),
                                Line(pos(-6.55, 3.88), pos(-6.55 + 13.1 * self.number / self.total, 3.88),
                                     color=CYAN, stroke_width=3),
                                left(text(self.chapter, 21, CYAN, bold=True), -6.55, 3.52),
                                left(text("Instância didática · 8 tarefas · 3 máquinas · calculada com o modelo do projeto",
                                          17, MUTED), -6.55, -3.60),
                                text(f"{self.number:02d} / {self.total:02d}", 17, MUTED).move_to(
                                    pos(6.55, -3.60), aligned_edge=RIGHT))
        self.add(self.cabecalho)
        if titulo:
            self.titulo = self._titulo(titulo)
            self.add(self.titulo)

    def _titulo(self, value):
        return left(text(value, 40, bold=True), -6.55, 2.86)

    def beat(self, identifier, title, *sair):
        self.next_section(identifier)
        new = self._titulo(title)
        anims = [FadeIn(new, shift=pos(0, .12))]
        if self.titulo is not None:
            anims.append(FadeOut(self.titulo, shift=pos(0, .12)))
        anims += [FadeOut(item) for item in sair]
        self.play(*anims, run_time=.6)
        self.titulo = new

    def hold(self):
        # ValueTracker guarda o tempo na coordenada x e não é desenhado.
        self.remove(*(m for m in self.mobjects if isinstance(m, ValueTracker)))
        super().hold()

    def base(self):
        """Componentes fixos da fábrica, na ordem de desenho."""
        line, labels = curva_tarifa()
        self.maquinas = VGroup(*(maquina(i) for i in range(3)))
        self.trilhos, self.horas = EIXO.trilhos(), EIXO.horas(-1.72)
        self.faixa, self.tarifa, self.tarifa_rotulos = EIXO.faixa_ponta(), line, labels
        return [self.faixa, self.trilhos, self.maquinas, self.horas, line, labels]

    def rodas(self, ativa, velocidade=3.5):
        """Cada roda gira e muda de cor conforme o estado da máquina."""
        for i, m in enumerate(self.maquinas):
            def girar(w, dt, i=i, m=m):
                estado = ativa(i)
                color = ESTADOS[estado]
                w.set_stroke(color if estado != "livre" else MUTED)
                m[0].set_stroke(color)
                if estado == "processando":
                    w.rotate(-velocidade * dt, about_point=w[0].get_center())
            m[2].add_updater(girar)

    def parar_rodas(self):
        for m in self.maquinas:
            m[2].clear_updaters()
            m[2].set_stroke(MUTED)
            m[0].set_stroke(GRID)


def estado(p, machine, t):
    blocks = [b for b in p["blocks"] if b["machine"] == machine]
    for b in blocks:
        if b["start"] <= t < b["end"]:
            return "processando"
        if b["start"] - b["wait"] <= t < b["start"]:
            return "espera"
        if b["start"] - b["wait"] - b["setup"] <= t < b["start"]:
            return "setup"
    return "livre"
