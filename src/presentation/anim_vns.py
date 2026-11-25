"""VNS/VND multiobjetivo: o explorador e as cinco portas. Os dados vêm de data/trace_vns.json."""

import math

from manim import (
    Arc, ArcBetweenPoints, Circle, Create, DashedLine, Dot, FadeIn, FadeOut, GrowFromCenter, GrowFromEdge, GrowFromPoint,
    Indicate, LaggedStart, Line, MoveAlongPath, Polygon, Rectangle, ReplacementTransform, RoundedRectangle, Transform,
    UpdateFromAlphaFunc, VGroup, VMobject, ValueTracker, always_redraw, linear, rush_into, smooth, there_and_back,
    DOWN, LEFT, PI,
)

from fabrica import CORES, EIXO, FAIXAS, FORA, NA_PONTA, PONTA, CenaContinua, DADOS, Eixo, maquina, plano, rotulo
from visual import (
    COLORS, CORAL, FUNDO, GOLD, GREEN, GRID, HERE, INK, MUTED, axes, dots, left, pos, pt, read_json, staircase, text,
)

TRACE = read_json(HERE / "data" / "trace_vns.json")
COR = COLORS["vns_vnd"]
PORTAS = ("N1", "N2", "N3", "N4", "N5")
NOMES = ("modo", "espera", "inserção", "realocação", "troca")
EX = Eixo(-5.2, 1 / 3, total=TRACE["horizonte"])
FRENTE = [(p["cmax"], p["tec"]) for p in DADOS["front"]]
FRENTE_VNS = [(p["cmax"], p["tec"]) for p in TRACE["frente"]]
CENTRO, LADO = (5.35, .35), (2.15, 2.7)
DETALHE = ((12, 22, 2), (650, 1150, 100))
ZOOM = ((12, 16, 1), (760, 900, 20))
XP = 3.95  # margem esquerda dos números sob o plano


def moeda(v):
    return f"$ {pt(v, 1)}"


def par(p):
    return f"{p['cmax']} h · {moeda(p['tec'])}"


def P(n):
    return TRACE["planos"][str(n)]


def objetivo(n):
    return P(n)["cmax"], P(n)["tec"]


def rejeitadas(n):
    return sum(p is None for p in TRACE["pontos"][:n])


class Quadro:
    """Barras, setups e esperas de um plano, indexados por tarefa."""

    def __init__(self, p, eixo=EX):
        self.eixo, self.p = eixo, p
        self.barras = {b["job"]: eixo.bloco(b) for b in p["blocks"]}
        self.setups = {b["job"]: eixo.setup(b) for b in p["blocks"]}
        self.esperas = {b["job"]: eixo.espera(b) for b in p["blocks"]}

    def itens(self):
        return [*self.setups.values(), *self.esperas.values(), *self.barras.values()]

    def ir(self, p, eixo=None, so=None, partes="bse"):
        """Animações que levam as tarefas em `so` (ou todas) até o plano p."""
        eixo = eixo or self.eixo
        anims = []
        for b in p["blocks"]:
            j = b["job"]
            if so is not None and j not in so:
                continue
            if "b" in partes:
                anims.append(Transform(self.barras[j], eixo.bloco(b)))
            if "s" in partes:
                anims.append(Transform(self.setups[j], eixo.setup(b)))
            if "e" in partes:
                anims.append(Transform(self.esperas[j], eixo.espera(b)))
        return anims

    def bloco(self, j):
        return next(b for b in self.p["blocks"] if b["job"] == j)


def icone(k):
    """Ícone do movimento de cada porta."""
    s = dict(stroke_width=0, fill_opacity=1)
    if k == 0:
        return VGroup(Rectangle(width=.22, height=.12, fill_color=GREEN, **s).shift(pos(-.11, -.08)),
                      Rectangle(width=.10, height=.28, fill_color=CORAL, **s).shift(pos(.14, 0)))
    if k == 1:
        mola = VMobject(color=GOLD, stroke_width=2.5).set_points_as_corners(
            [pos(-.2 + .06 * i, .07 * (-1) ** i) for i in range(5)])
        return VGroup(mola, Rectangle(width=.14, height=.2, fill_color=INK, **s).shift(pos(.15, 0)))
    if k == 2:
        return VGroup(*(Rectangle(width=.12, height=.14, fill_color=c, **s).shift(pos(x, -.1))
                        for c, x in ((INK, -.18), (MUTED, 0), (MUTED, .18))),
                      Arc(radius=.16, start_angle=PI, angle=-PI, color=INK, stroke_width=2.5).shift(pos(0, -.02)))
    if k == 3:
        return VGroup(*(Line(pos(-.22, y), pos(.22, y), color=MUTED, stroke_width=2) for y in (.13, -.13)),
                      Rectangle(width=.16, height=.1, fill_color=INK, **s).shift(pos(-.1, .13)),
                      Line(pos(.02, .12), pos(.14, -.08), color=INK, stroke_width=2.5),
                      Dot(pos(.14, -.1), radius=.045, color=INK))
    return VGroup(Arc(radius=.19, start_angle=.2, angle=PI - .4, color=CORAL, stroke_width=2.5),
                  Arc(radius=.19, start_angle=PI + .2, angle=PI - .4, color=GREEN, stroke_width=2.5),
                  Dot(pos(-.19, 0), radius=.06, color=CORAL), Dot(pos(.19, 0), radius=.06, color=GREEN))


class Elevador:
    """Cinco portas empilhadas; a cabine leva o explorador."""

    def __init__(self, x=3.22, base=-1.45, passo=.72):
        self.x, self.base, self.passo = x, base, passo
        self.portas = VGroup()
        for k in range(5):
            box = RoundedRectangle(width=.62, height=.6, corner_radius=.08, stroke_color=GRID, stroke_width=1.8,
                                   fill_color=FUNDO, fill_opacity=1)
            nome = text(PORTAS[k], 14, MUTED, bold=True).move_to(pos(0, .19))
            self.portas.add(VGroup(box, nome, icone(k).scale(.85).shift(pos(0, -.08))).move_to(self.em(k)))
        self.trilho = Line(pos(x, base - .4), pos(x, base + 4 * passo + .4), color=GRID, stroke_width=2)
        self.cabine = VGroup(RoundedRectangle(width=.70, height=.68, corner_radius=.1, stroke_color=COR, stroke_width=4,
                                              fill_color=COR, fill_opacity=.18).move_to(self.em(0)),
                             Dot(self.em(0) + pos(-.35, .34), radius=.07, color=COR))

    def em(self, k):
        return pos(self.x, self.base + k * self.passo)

    def queda(self, k):
        """Rastro da queda da porta k até N1."""
        return Line(self.em(k), self.em(0), color=GREEN, stroke_width=9).set_opacity(.65)


def explorador(ponto):
    return VGroup(Dot(ponto, radius=.2, color=COR).set_opacity(.25), Dot(ponto, radius=.095, color=COR))


def dado(valor=1, lado=.34):
    pips = {1: [(0, 0)], 2: [(-1, 1), (1, -1)], 3: [(-1, 1), (0, 0), (1, -1)]}[valor]
    return VGroup(RoundedRectangle(width=lado, height=lado, corner_radius=.06, stroke_width=0, fill_color=INK, fill_opacity=1),
                  *(Dot(pos(a * lado * .26, b * lado * .26), radius=.035, color=FUNDO) for a, b in pips))


def bandeira(ponto, cor=COR, escala=1.0):
    pe = Dot(ponto, radius=.055 * escala, color=cor)
    haste = Line(ponto, ponto + pos(0, .46 * escala), color=INK, stroke_width=2.2)
    pano = Polygon(ponto + pos(0, .46 * escala), ponto + pos(.27 * escala, .36 * escala), ponto + pos(0, .25 * escala),
                   stroke_width=0, fill_color=cor, fill_opacity=1)
    return VGroup(haste, pano, pe)


def eixos(limites, centro=CENTRO, lado=LADO):
    return axes(*limites, center=centro, width=lado[0], height=lado[1], x_label="Cmax (h)", y_label="TEC ($)", numbers=True)


def tarifa24(y=-2.95):
    low, high = y + .25, y + .75
    pts = [(0, low), (PONTA[0], low), (PONTA[0], high), (PONTA[1], high), (PONTA[1], low), (24, low)]
    line = VMobject(color=GOLD, stroke_width=3).set_points_as_corners([pos(EX.at(t), v) for t, v in pts])
    labels = VGroup(text("tarifa", 17, MUTED).move_to(pos(-5.75, low)),
                    text(f"fora da ponta · $ {pt(FORA, 2)}", 17, GOLD).move_to(pos(EX.at(4.7), low + .20)),
                    text(f"$ {pt(NA_PONTA, 2)}", 17, CORAL, bold=True).move_to(pos(EX.at(15), high - .05)))
    return line, labels


def horizonte():
    x = EX.at(24)
    return DashedLine(pos(x, 1.75), pos(x, -1.6), color=CORAL, stroke_width=2.5, dash_length=.09)


def pontilhado(a, b, cor=COR):
    return Line(a, b, color=cor, stroke_width=3).set_opacity(.45)


class Cena(CenaContinua):
    chapter = "META-HEURÍSTICA VNS/VND"

    def abrir(self, titulo=None):
        super().abrir(titulo)
        c = TRACE["parametros"]
        self.cabecalho[4].become(left(text(
            f"Demonstração · instância didática · seed {c['seed']}, escolhida · {c['initial_solutions']} partidas · "
            f"{c['max_candidates_per_neighborhood']} candidatos · {c['shaking_attempts']} tentativas · "
            f"{pt(c['max_evaluations'], 0)} avaliações", 17, MUTED), -6.55, -3.60))
        self.n = ValueTracker(0)

    # Componentes do quadro de detalhe -------------------------------------------------
    def fabrica24(self):
        linha, rot = tarifa24()
        return [EX.faixa_ponta(), EX.trilhos(), VGroup(*(maquina(i) for i in range(3))), EX.horas(-1.72), linha, rot]

    def contador(self, valor):
        self.n.set_value(valor)
        n = self.n
        return VGroup(left(text("avaliação", 17, MUTED), XP, -2.62), left(text("rejeitadas", 17, MUTED), XP + 1.35, -2.62)), \
            always_redraw(lambda: left(rotulo(pt(round(n.get_value()), 0), 25, INK, True), XP, -2.97)), \
            always_redraw(lambda: left(rotulo(str(rejeitadas(round(n.get_value()))), 25, CORAL, True), XP + 1.35, -2.97))

    def detalhe(self, avaliacao, n, limites=DETALHE):
        """Quadro de detalhe: Gantt de 24 h, plano Cmax × TEC, valor e contador."""
        self.fab = self.fabrica24()
        self.hz = VGroup(horizonte())
        self.q = Quadro(P(avaliacao))
        self.axis, self.labels = eixos(limites)
        self.expl = explorador(self.axis.c2p(*objetivo(avaliacao)))
        self.valor = self.texto_valor(avaliacao)
        self.cont = self.contador(n)
        return [*self.fab, *self.hz, *self.q.itens(), self.axis, self.labels, self.expl, self.valor, *self.cont]

    def texto_valor(self, avaliacao, cor=COR, y=-2.15):
        return text(par(P(avaliacao)), 23, cor, bold=True).move_to(pos(CENTRO[0] - .1, y))

    def troca_valor(self, avaliacao, rt=.25, cor=COR):
        novo = self.texto_valor(avaliacao, cor)
        velho, self.valor = self.valor, novo
        self.play(FadeOut(velho, shift=pos(0, .1)), FadeIn(novo, shift=pos(0, .1)), run_time=rt)

    def contar(self, alvo, rt):
        self.play(self.n.animate.set_value(alvo), run_time=rt, rate_func=linear)

    # Coreografia dos operadores ------------------------------------------------------
    def operar(self, avaliacao, mov, v=1.0, junto=lambda: [], ponto=None, valor=True):
        """Antecipação, ação e consequência; `ponto` move-se com as tarefas seguintes."""
        q, novo = self.q, P(avaliacao)
        antes = {b["job"]: b for b in q.p["blocks"]}
        depois = {b["job"]: b for b in novo["blocks"]}
        jobs = mov["tarefas"]
        for j in jobs:
            self.bring_to_front(q.barras[j])
        resto = [j for j in antes if j not in jobs]
        mexidas = {antes[j]["machine"] for j in jobs} | {depois[j]["machine"] for j in jobs}
        tipo = mov["tipo"]
        if tipo in ("trocar", "realocar", "inserir"):
            self.play(*(q.barras[j].animate.shift(pos(0, .22)) for j in jobs), run_time=.3 * v)
        else:
            self.play(*(q.barras[j].animate(rate_func=there_and_back).scale(1.12) for j in jobs), run_time=.3 * v)
        some = [q.setups[j].animate.set_fill(opacity=0) for j in antes
                if antes[j]["machine"] in mexidas and tipo in ("trocar", "realocar", "inserir")]
        if tipo == "trocar":
            a, b = jobs
            anims = [Transform(q.barras[j], EX.bloco(depois[j]), path_arc=arco) for j, arco in ((a, 1.7), (b, 1.7))]
            self.play(*anims, *some, run_time=1.1 * v)
        elif tipo == "realocar":
            destino = [j for j in resto if depois[j]["machine"] == depois[jobs[0]]["machine"]]
            self.play(*q.ir(novo, so=destino, partes="b"), Transform(q.barras[jobs[0]], EX.bloco(depois[jobs[0]]), path_arc=-.9),
                      *some, run_time=1.1 * v)
        elif tipo == "inserir":
            j = jobs[0]
            alto = EX.bloco(depois[j]).shift(pos(0, .55))
            self.play(q.barras[j].animate.shift(pos(0, .33)), *some, run_time=.3 * v)
            vizinhas = [k for k in resto if depois[k]["machine"] == depois[j]["machine"]]
            self.play(Transform(q.barras[j], alto), *q.ir(novo, so=vizinhas, partes="b"), run_time=.8 * v)
        # Modo e espera empurram as seguintes e movem o ponto no mesmo instante.
        fim = [*q.ir(novo), *junto()]
        if ponto is not None:
            fim.append(ponto)
        if valor:
            t = self.texto_valor(avaliacao)
            fim += [FadeOut(self.valor), FadeIn(t)]
            self.valor = t
        self.play(*fim, run_time=(1.3 if tipo in ("modo", "espera") else .6) * v)
        q.p = novo

    def mover(self, avaliacao, arco=0.0):
        return Transform(self.expl, explorador(self.axis.c2p(*objetivo(avaliacao))), path_arc=arco)

    def rastro(self, de, para, cor=COR):
        linha = pontilhado(self.axis.c2p(*objetivo(de)), self.axis.c2p(*objetivo(para)), cor)
        return linha

    def voltar(self, avaliacao, v=1.0, extra=()):
        self.q.p = P(avaliacao)
        t = self.texto_valor(avaliacao)
        self.play(*self.q.ir(P(avaliacao)), FadeOut(self.valor), FadeIn(t), *extra, run_time=.45 * v)
        self.valor = t

    def terremoto(self, objetos, rt=.9, forca=.07):
        grupo = VGroup(*objetos)
        estado = {"d": pos(0, 0)}

        def tremer(m, alpha):
            k = forca * math.sin(PI * alpha)
            novo = pos(k * math.sin(40 * alpha), k * math.cos(57 * alpha)) if 0 < alpha < 1 else pos(0, 0)
            m.shift(novo - estado["d"])
            estado["d"] = novo
        self.play(UpdateFromAlphaFunc(grupo, tremer), run_time=rt)


def fila_chip(job, x, y=2.08):
    w = .22 * TRACE["dificuldade"][job]
    return VGroup(Rectangle(width=w, height=.40, stroke_width=0, fill_color=CORES[job], fill_opacity=1),
                  rotulo(f"T{job + 1}", 18, FUNDO, True)).move_to(pos(x + w / 2, y))


def chips_da(fila):
    x, grupo = -5.2, {}
    for j in fila:
        grupo[j] = fila_chip(j, x)
        x += .22 * TRACE["dificuldade"][j] + .12
    return grupo


def rotulo_janela(r):
    w = math.isqrt(r - 1) + 1
    return VGroup(left(text("janela ⌈√r⌉", 24, GOLD, bold=True), 3.75, 2.2),
                  left(text(f"⌈√{r}⌉ = {w}", 34, GOLD, bold=True), 3.75, 1.62))


class VnsPartida(Cena):
    number = 1

    def construct(self):
        self.abrir()
        self.camera.background_color = FUNDO
        itens = self.base()
        q0 = Quadro(plano(15), EIXO)
        axis, labels = axes((10, 24, 2), (400, 900, 100), center=(5.02, .35), width=2.75, height=2.7,
                            x_label="Cmax (h)", y_label="TEC ($)", numbers=True)
        ponto = Dot(axis.c2p(plano(15)["cmax"], plano(15)["tec"]), radius=.11, color=GOLD)
        self.add(*itens, *q0.itens(), axis, labels, ponto)
        self.beat("partida", "Por onde começar a explorar?")

        # As tarefas saem do Gantt e formam a fila por dificuldade.
        passos = TRACE["partidas"][0]
        chips = chips_da(passos[0]["fila"])
        fab = self.fabrica24()
        destino = VGroup(*fab[:2], fab[3])
        self.play(FadeOut(VGroup(axis, labels, ponto)), *(FadeOut(s) for s in (*q0.setups.values(), *q0.esperas.values())),
                  *(ReplacementTransform(q0.barras[j], chips[j], path_arc=.3) for j in chips),
                  Transform(VGroup(self.faixa, self.trilhos, self.horas), destino), Transform(self.tarifa, fab[4]),
                  Transform(self.tarifa_rotulos, fab[5]), run_time=1.3)
        base24 = [self.faixa, self.trilhos, self.maquinas, self.horas, self.tarifa, self.tarifa_rotulos]
        # As barras que chegam da fila ficam à frente dos trilhos.
        self.bring_to_back(*base24)
        dica = VGroup(left(text("fila por dificuldade:", 20, MUTED), 3.75, 1.0),
                      left(text("maior duração mínima", 20, MUTED), 3.75, .66))
        self.play(FadeIn(dica), run_time=.3)

        janela = None
        nome = None
        feitas = []
        for k, s in enumerate(passos):
            v = 1.0 if k == 0 else (.55 if k == 1 else .30)
            fila = s["fila"]
            arrumada = chips_da(fila)
            dentro = VGroup(*(arrumada[j] for j in fila[:s["janela"]]))
            moldura = Rectangle(width=dentro.width + .14, height=.58, stroke_color=GOLD, stroke_width=3.5).move_to(dentro)
            novo_nome = rotulo_janela(len(fila))
            if janela is None:
                janela, nome = moldura, novo_nome
                self.play(Create(janela), FadeIn(nome), run_time=.5)
                self.play(Indicate(janela, color=GOLD, scale_factor=1.06), run_time=.5)
                d = dado(1).move_to(chips[fila[0]].get_center() + pos(0, -.40))
                self.play(FadeIn(d), run_time=.2)
            else:
                self.play(Transform(janela, moldura), *(chips[j].animate.move_to(arrumada[j]) for j in fila), FadeOut(nome), FadeIn(novo_nome), run_time=.25 * max(v, .6))
                nome = novo_nome
            # O dado percorre a janela e para na tarefa sorteada.
            rota = (list(range(s["janela"])) + [s["indice"]]) if k < 2 else [s["indice"]]
            for i in rota:
                self.play(Transform(d, dado(i + 1).move_to(chips[fila[i]].get_center() + pos(0, -.40))),
                          run_time=.18 if k < 2 else .12)
            job = s["job"]
            bloco = dict(job=job, machine=s["maquina"], mode=s["modo"], start=s["inicio"], end=s["fim"], setup=s["setup"], wait=0)
            alvo, setup = EX.bloco(bloco), EX.setup(bloco)
            if k < 2:
                # Sondas: o menor término possível em cada máquina.
                sondas = VGroup()
                for m in range(3):
                    end, _, modo = min(o for o in s["opcoes"] if o[1] == m)
                    dur = math.ceil(round(DADOS["processing"][job][m] / DADOS["speed"][modo], 9))
                    g = EX.tarefa(job, m, end - dur, end, modo)
                    g[0].set_fill(opacity=.15).set_stroke(CORES[job], 1.5)
                    g[1].set_opacity(0)
                    sondas.add(g, left(rotulo(f"{end} h", 16, GREEN if m == s["maquina"] else MUTED, m == s["maquina"]),
                                       EX.at(end) + .08, FAIXAS[m]))
                self.play(LaggedStart(*(FadeIn(g) for g in sondas), lag_ratio=.1), run_time=.7 * v)
                self.wait(.25 * v)
                self.play(FadeOut(sondas), FadeIn(setup), ReplacementTransform(chips[job], alvo, path_arc=-.5), run_time=.9 * v)
            else:
                self.play(FadeIn(setup), ReplacementTransform(chips[job], alvo, path_arc=-.5), run_time=.9 * v)
            feitas += [setup, alvo]
        self.play(FadeOut(janela), FadeOut(nome), FadeOut(d), FadeOut(dica), run_time=.25)

        # As outras três construções, aceleradas; cada plano vira uma miniatura.
        minis, valores = [], []
        for k in range(4):
            if k:
                chips = chips_da(TRACE["partidas"][k][0]["fila"])
                self.play(*(FadeIn(c, shift=pos(0, -.15)) for c in chips.values()), run_time=.2)
                feitas, anims = [], []
                for s in TRACE["partidas"][k]:
                    b = next(b for b in P(k + 1)["blocks"] if b["job"] == s["job"])
                    alvo, setup = EX.bloco(b), EX.setup(b)
                    anims += [ReplacementTransform(chips[s["job"]], alvo, path_arc=-.5), FadeIn(setup)]
                    feitas += [setup, alvo]
                self.play(LaggedStart(*anims, lag_ratio=.12), run_time=1.0)
            y = 1.55 - .98 * k
            m = Quadro(P(k + 1), Eixo(3.8, .105, (y, y - .2, y - .4), .17, 24))
            mini = VGroup(*m.itens())
            vt = left(text(par(P(k + 1)), 17, MUTED, bold=True), 3.8, y + .28)
            copia = VGroup(*feitas)
            self.play(ReplacementTransform(copia, mini), FadeIn(vt), run_time=.45)
            minis.append(mini)
            valores.append(vt)
        self.hold()

        # Arquivo ------------------------------------------------------------------------
        self.beat("arquivo", "O que vale a pena guardar?", *base24)
        mapa, rot = eixos(((12, 17, 1), (1000, 1600, 100)), (-1.9, -.35), (8.2, 4.0))
        self.play(FadeIn(mapa), FadeIn(rot), run_time=.6)
        bandeiras, sombras = {}, {}
        for k in range(4):
            p = objetivo(k + 1)
            fim = mapa.c2p(*p)
            alvo = bandeira(fim, escala=1.3)
            self.play(ReplacementTransform(minis[k], alvo, path_arc=.4), FadeOut(valores[k]), run_time=.65 if k else .9)
            bandeiras[k] = alvo
            if TRACE["iniciais"][k]["inserido"]:
                canto = mapa.c2p(17, 1600)
                sombras[k] = Rectangle(width=canto[0] - fim[0], height=canto[1] - fim[1], stroke_width=0, fill_color=COR,
                                       fill_opacity=.13).move_to((canto + fim) / 2)
                self.play(GrowFromPoint(sombras[k], fim), run_time=.4)
            else:
                self.play(alvo.animate(rate_func=rush_into).rotate(-PI / 2 * .92, about_point=fim), run_time=.45)
                self.play(alvo.animate.set_color(GRID), run_time=.25)
        self.wait(.4)
        vivos = [k for k in range(4) if TRACE["iniciais"][k]["inserido"]]
        visitas = {}
        for k in vivos:
            c = bandeiras[k].get_top() + pos(.1, .24)
            visitas[k] = VGroup(Circle(radius=.17, stroke_color=GOLD, stroke_width=2, fill_color=FUNDO, fill_opacity=1),
                                text("0", 17, GOLD, bold=True)).move_to(c)
        lado = VGroup(left(text("visitas", 22, GOLD, bold=True), 3.9, 1.2), left(text("menos explorada", 25, INK, bold=True), 3.9, .62),
                      left(text("empate em 0: sorteio", 20, MUTED), 3.9, .14))
        self.play(*(GrowFromCenter(v) for v in visitas.values()), FadeIn(lado[0]), FadeIn(lado[1]), run_time=.6)
        escolha = TRACE["origem"]["avaliacao"] - 1
        d = dado(1).move_to(bandeiras[vivos[0]].get_center() + pos(-.42, 0))
        self.play(FadeIn(d), FadeIn(lado[2]), run_time=.25)
        for k in (vivos[1], vivos[0], vivos[1], escolha):
            self.play(Transform(d, dado(2 - k // 2 if k else 1).move_to(bandeiras[k].get_center() + pos(-.42, 0))), run_time=.2)
        farol = VGroup(*(Circle(radius=r, stroke_width=0, fill_color=GOLD, fill_opacity=o).move_to(bandeiras[escolha][2])
                         for r, o in ((.75, .10), (.5, .14), (.28, .22))))
        um = text("1", 17, GOLD, bold=True).move_to(visitas[escolha])
        self.play(FadeIn(farol, scale=.4), bandeiras[escolha][1].animate.set_color(GOLD), FadeOut(visitas[escolha][1]), FadeIn(um),
                  *(b.animate.set_opacity(.35) for k, b in bandeiras.items() if k != escolha), run_time=.6)
        self.wait(.7)
        # A câmera entra no plano da origem.
        foco = bandeiras[escolha][2].get_center()
        resto = VGroup(mapa, rot, *sombras.values(), *(b for k, b in bandeiras.items() if k != escolha), visitas[vivos[0]])
        quadro = self.detalhe(escolha + 1, 4)
        gantt = VGroup(*self.q.itens())
        self.play(resto.animate.scale(2.6, about_point=foco).set_opacity(0), FadeOut(lado), FadeOut(d), FadeOut(um),
                  FadeOut(visitas[escolha][0]), FadeOut(farol, scale=3), run_time=.8)
        self.remove(resto)
        fundo = [m for m in quadro if m not in gantt.submobjects and m is not self.expl]
        self.play(*(FadeIn(m) for m in fundo), GrowFromPoint(gantt, foco),
                  ReplacementTransform(bandeiras[escolha], self.expl), run_time=1.0)
        self.remove(gantt)
        self.add(*self.q.itens(), self.expl)
        self.hold()


class VnsDescida(Cena):
    number = 2

    def construct(self):
        self.abrir("O que vale a pena guardar?")
        self.origem = TRACE["origem"]["avaliacao"]
        self.add(*self.detalhe(self.origem, 4))
        self.shake()
        self.portas()
        self.reinicio()

    def shake(self):
        self.beat("shake", "Como sair de onde já estamos?")
        sh, origem = TRACE["shakes"], self.origem
        marca = VGroup(Circle(radius=.16, stroke_color=GOLD, stroke_width=2.5).move_to(self.axis.c2p(*objetivo(origem))))
        rotm = text("origem", 15, GOLD).next_to(marca, DOWN, buff=.06)
        self.play(Create(marca), FadeIn(rotm), run_time=.4)
        chao = lambda: [self.fab[1], self.fab[2], *self.q.itens()]

        def onda(porta):
            t = VGroup(text(f"shake em {PORTAS[porta]}", 24, GOLD, bold=True)).move_to(pos(-1.2, 2.12))
            self.play(FadeIn(t, scale=1.3), run_time=.2)
            return t
        tag = onda(0)
        self.terremoto(chao(), 1.0)
        n1 = sh["primeiro"]["avaliacao"]
        rastros = VGroup(self.rastro(origem, n1))
        self.play(self.n.animate.set_value(n1), run_time=.15)
        self.operar(n1, sh["primeiro"]["movimento"], 1.1, ponto=self.mover(n1), junto=lambda: [Create(rastros[0])])
        self.wait(.5)

        # A mesma origem, mais tarde: um sorteio inviável em N2 e o seguinte, pior.
        ruim, bom = sh["tremor"]["avaliacoes"]
        self.play(FadeOut(rastros), run_time=.2)
        self.voltar(origem, extra=[self.mover(origem), self.n.animate.set_value(ruim - 1), FadeOut(tag)])
        tag = onda(sh["tremor"]["porta"])
        self.terremoto(chao(), .7)
        plano_ruim = P(ruim)
        j = sh["tremor"]["movimentos"][0]["tarefas"][0]
        lado = [self.axis, self.labels, self.expl, marca, rotm]
        self.play(*(m.animate.set_opacity(.12) for m in lado), FadeOut(self.valor), run_time=.25)
        jobs = [b["job"] for b in plano_ruim["blocks"] if b["end"] > 24 or b["job"] == j]
        for k in jobs:
            self.bring_to_front(self.q.barras[k])
        hz = text("horizonte", 16, CORAL, bold=True).next_to(self.hz, pos(0, 1), buff=.06)
        self.play(FadeIn(hz), *self.q.ir(plano_ruim, so=jobs), run_time=1.2)
        self.terremoto(chao(), .5, .09)
        cacos, quebradas = VGroup(), []
        for k in jobs:
            r = self.q.barras[k][0]
            l_, d_, t_, b_ = r.get_left()[0], r.get_right()[0], r.get_top()[1], r.get_bottom()[1]
            x = (l_ + d_) / 2
            zig = [pos(x, t_), pos(x + .1, (2 * t_ + b_) / 3), pos(x - .1, (t_ + 2 * b_) / 3), pos(x, b_)]
            for lado_pts in ([pos(l_, t_), *zig, pos(l_, b_)], [pos(d_, t_), *zig, pos(d_, b_)]):
                cacos.add(Polygon(*lado_pts, stroke_color=CORAL, stroke_width=2, fill_color=CORES[k], fill_opacity=1))
            quebradas += [self.q.barras[k], self.q.setups[k], self.q.esperas[k]]
        self.remove(*quebradas)
        self.add(cacos)
        xis = text("inviável · conta 1 avaliação", 20, CORAL, bold=True).move_to(pos(-1.2, -2.0 + .05)).shift(pos(0, 4.07))
        self.play(FadeOut(tag), FadeIn(xis), self.n.animate.set_value(ruim), run_time=.3)
        self.play(*(c.animate.shift(pos(.18 * (-1) ** (i + 1), -.35)).rotate(.35 * (-1) ** i) for i, c in enumerate(cacos)), run_time=.35)
        self.play(FadeOut(cacos, shift=pos(0, -.4)), run_time=.35)
        self.q = self._recria(origem, quebradas)
        self.valor = self.texto_valor(origem)
        mostra = [m for k in jobs for m in (self.q.setups[k], self.q.esperas[k], self.q.barras[k])]
        self.axis_restaura(lado, marca, rotm, [*(FadeIn(m) for m in mostra), FadeIn(self.valor), FadeOut(hz), FadeOut(xis)])
        tag = onda(sh["tremor"]["porta"])
        self.terremoto(chao(), .5)
        self.play(self.n.animate.set_value(bom), run_time=.1)
        rast = VGroup(self.rastro(origem, bom, CORAL))
        pior = text("pode piorar", 22, CORAL, bold=True).move_to(pos(5.45, -.05))
        self.operar(bom, sh["tremor"]["movimentos"][1], 1.0, ponto=self.mover(bom), junto=lambda: [Create(rast[0]), FadeIn(pior)])
        self.wait(.8)

        # O shake que abre a descida mostrada a seguir.
        ent = sh["entrada"]
        self.play(FadeOut(rast), FadeOut(pior), FadeOut(tag), run_time=.2)
        self.voltar(origem, extra=[self.mover(origem), self.n.animate.set_value(ent["avaliacao"] - 1)])
        tag = onda(ent["porta"])
        self.terremoto(chao(), .4)
        self.play(self.n.animate.set_value(ent["avaliacao"]), run_time=.1)
        self.operar(ent["avaliacao"], ent["movimento"], .6, ponto=self.mover(ent["avaliacao"]))
        self.el = Elevador()
        self.add(self.el.trilho)
        self.play(FadeOut(tag), FadeOut(marca), FadeOut(rotm), LaggedStart(*(FadeIn(p, shift=pos(0, -.2)) for p in self.el.portas),
                  lag_ratio=.1), run_time=.7)
        semente = explorador(self.expl.get_center())
        self.add(semente)
        self.play(ReplacementTransform(semente, self.el.cabine, path_arc=1.0), run_time=.6)
        self.hold()

    def _recria(self, avaliacao, quebradas):
        q = Quadro(P(avaliacao))
        velho = self.q
        fora = {id(m) for m in quebradas}
        self.remove(*quebradas)
        for k in velho.barras:
            if id(velho.barras[k]) not in fora:
                q.barras[k], q.setups[k], q.esperas[k] = velho.barras[k], velho.setups[k], velho.esperas[k]
        return q

    def axis_restaura(self, lado, marca, rotm, extras):
        """O plano esmaecido é trocado por cópias novas, sem opacidade residual."""
        axis, labels = eixos(DETALHE)
        expl = explorador(axis.c2p(*objetivo(self.origem)))
        m2 = Circle(radius=.16, stroke_color=GOLD, stroke_width=2.5).move_to(marca)
        r2 = text("origem", 15, GOLD).move_to(rotm)
        anims = [Transform(a, b) for a, b in zip(lado, (axis, labels, expl, VGroup(m2), r2))]
        self.play(*anims, *extras, run_time=.5)

    def nome_porta(self, k, velho=None):
        novo = text(f"{PORTAS[k]} · {NOMES[k]}", 27, COR, bold=True).move_to(pos(-1.2, 2.12))
        self.play(FadeIn(novo, shift=pos(0, .1)), *([FadeOut(velho, shift=pos(0, .1))] if velho is not None else []), run_time=.3)
        return novo

    def acende(self, k):
        return self.el.portas[k][0].animate.set_stroke(COR, 3)

    def apaga(self, k):
        return self.el.portas[k][0].animate.set_stroke(GRID, 1.8)

    def cabine_em(self, k):
        c = self.el.cabine
        return c.animate.move_to(self.el.em(k) + (c.get_center() - c[0].get_center()))

    def portas(self):
        self.beat("portas", "Qual mudança ajuda?")
        nome = None
        # N1 aceita duas melhorias antes de a descida chegar ao plano examinado nas cinco portas.
        nome = self.nome_porta(0)
        for i, a in enumerate(TRACE["aceites"][:2]):
            v = 1.35 if i == 0 else .75
            self.play(self.n.animate.set_value(a["para"]), self.acende(0), run_time=.25)
            r = self.rastro(a["de"], a["para"], GREEN)
            self.operar(a["para"], a["movimento"], v, ponto=self.mover(a["para"]), junto=lambda: [Create(r)])
            self.play(Indicate(self.q.barras[a["movimento"]["tarefas"][0]], color=GREEN, scale_factor=1.1), FadeOut(r), run_time=.4)
        corrente = TRACE["corrente"]
        for item in TRACE["portas"]:
            k, n = item["porta"], item["principal"]
            if k:
                nome = self.nome_porta(k, nome)
                self.play(self.cabine_em(k), self.apaga(k - 1), self.acende(k), run_time=.35)
            vis = next(v for v in TRACE["descida"] if v["porta"] == k and v["corrente"] == corrente)
            # Fantasmas: três candidatos reais desta visita.
            fant = {m: Circle(radius=.085, stroke_color=INK, stroke_width=2.2, fill_color=FUNDO, fill_opacity=.6).move_to(
                self.axis.c2p(*objetivo(m))) for m in item["fantasmas"]}
            g = fant[n]
            base = Dot(self.expl.get_center(), radius=.06, color=INK)
            viagem = ReplacementTransform(base, g)
            self.add(base)
            self.operar(n, item["movimento"], 1.0 if k else .8, ponto=viagem,
                        junto=lambda: [self.n.animate.set_value(n)])
            self.play(*(FadeIn(fant[m], scale=1.6) for m in item["fantasmas"] if m != n), run_time=.3)
            self.play(Create(seta := Line(self.expl.get_center(), g.get_center(), color=MUTED, stroke_width=2)), run_time=.25)
            if item["aceito"]:
                self.wait(.3)
                outros = [fant[m] for m in item["fantasmas"] if m != n]
                self.play(g.animate.set_stroke(GREEN, 4).set_fill(GREEN, 1), *(FadeOut(o) for o in outros), FadeOut(seta), run_time=.35)
                self.voltar(corrente)
                self.play(Indicate(g, color=GREEN, scale_factor=1.8), run_time=.6)
                self.lit = g
            else:
                self.wait(.35)
                self.play(*(f.animate.set_stroke(GRID).set_opacity(.35) for f in fant.values()), FadeOut(seta),
                          self.n.animate.set_value(vis["candidatos"][-1]), run_time=.25)
                self.voltar(corrente, extra=[FadeOut(f) for f in fant.values()])
        self.nome = nome
        self.hold()

    def sombra(self, n):
        """Região dominada pelo ponto: tudo à direita e acima."""
        x1, y1 = self.axis.x_range[1], self.axis.y_range[1]
        a, b = self.axis.c2p(*objetivo(n)), self.axis.c2p(x1, y1)
        return Rectangle(width=b[0] - a[0], height=b[1] - a[1], stroke_width=0, fill_color=GREEN, fill_opacity=.18).move_to((a + b) / 2)

    def despenca(self, a, v):
        """Um único movimento: cabine, ponto e Gantt."""
        k, n, q = a["porta"], a["para"], self.q
        novo = P(n)
        jobs = a["movimento"]["tarefas"]
        for j in jobs:
            self.bring_to_front(q.barras[j])
        s = self.sombra(n)
        alvo = explorador(self.axis.c2p(*objetivo(n)))
        cand = Dot(alvo.get_center(), radius=.08, color=GREEN)
        self.play(FadeIn(cand, scale=2), GrowFromPoint(s, cand.get_center()),
                  *(q.barras[j].animate.shift(pos(0, .2)) for j in jobs), run_time=.5 * v)
        if v > .8:
            self.wait(.5)
        arco = 1.7 if a["movimento"]["tipo"] == "trocar" else .9
        barras = []
        for b in novo["blocks"]:
            j = b["job"]
            barras.append(Transform(q.barras[j], EX.bloco(b), path_arc=arco if j in jobs else 0))
        queda = self.el.queda(k)
        rastro = self.rastro(a["de"], n, GREEN)
        t = self.texto_valor(n, GREEN)
        velho, self.valor = self.valor, t
        self.play(self.cabine_em(0), FadeIn(queda), Transform(self.expl, alvo), Create(rastro),
                  *barras, *q.ir(novo, partes="se"), FadeOut(velho), FadeIn(t), self.apaga(k), self.acende(0),
                  self.n.animate.set_value(n), run_time=1.15 * v, rate_func=rush_into)
        q.p = novo
        self.play(*(Indicate(q.barras[j], color=GREEN, scale_factor=1.12) for j in jobs), FadeOut(queda), FadeOut(s),
                  FadeOut(cand), FadeOut(rastro), run_time=.45 * v)

    def sobe(self, visitas, v):
        """Subida sem melhora: cada porta consome as avaliações da visita."""
        for vis in visitas:
            k = vis["porta"]
            anims = [self.n.animate.set_value(vis["candidatos"][-1] - (1 if vis["aceito"] else 0))]
            if k:
                anims += [self.cabine_em(k), self.apaga(k - 1), self.acende(k)]
            self.play(*anims, run_time=.42 * v, rate_func=smooth)

    def reinicio(self):
        self.beat("reinicio", "E quando uma mudança melhora?", self.nome)
        # Aproxima o plano: só a região das próximas melhorias.
        axis, labels = eixos(ZOOM)
        velhos = [self.axis, self.labels]
        atual = TRACE["corrente"]
        alvo = explorador(axis.c2p(*objetivo(atual)))
        lit = self.lit.copy().move_to(axis.c2p(*objetivo(TRACE["portas"][-1]["principal"])))
        self.play(*(FadeOut(m) for m in velhos), FadeIn(axis), FadeIn(labels), Transform(self.expl, alvo),
                  Transform(self.lit, lit), run_time=.8)
        self.axis, self.labels = axis, labels
        self.bring_to_front(self.lit, self.expl)
        altas = [a for a in TRACE["aceites"] if a["porta"] >= 2]
        regra = text("volta a N1", 27, GREEN, bold=True).move_to(pos(-1.2, 2.12))
        for i, a in enumerate(altas):
            v = (1.15, .72, .5)[i]
            if i:
                self.sobe([x for x in TRACE["descida"] if x["corrente"] == a["de"] and x["porta"] <= a["porta"]], (1, .8, .5)[i])
            self.despenca(a, v)
            if i == 0:
                self.remove(self.lit)
                self.play(FadeIn(regra), run_time=.3)
                self.wait(.6)
        for a in TRACE["aceites"][-2:]:
            t = self.texto_valor(a["para"], GREEN)
            velho, self.valor = self.valor, t
            self.play(*self.q.ir(P(a["para"])), self.mover(a["para"]), FadeOut(velho), FadeIn(t),
                      Indicate(self.el.cabine, color=GREEN, scale_factor=1.1), self.n.animate.set_value(a["para"]), run_time=.45)
            self.q.p = P(a["para"])
        ultimo = TRACE["aceites"][-1]["para"]
        self.play(FadeOut(regra), run_time=.2)
        self.sobe([x for x in TRACE["descida"] if x["corrente"] == ultimo], 1.0)
        sai = text("sem melhora: fim da descida", 25, MUTED, bold=True).move_to(pos(-1.2, 2.12))
        self.play(self.el.cabine.animate.shift(pos(0, .75)).set_opacity(0), self.apaga(4), FadeIn(sai), run_time=.6)
        self.remove(self.el.cabine)
        self.play(FadeOut(sai), run_time=.3)
        self.hold()


MAPA = ((11, 25, 2), (400, 1600, 200))
MC, ML = (1.65, -.22), (8.6, 4.15)


class VnsBusca(Cena):
    number = 3

    def construct(self):
        self.abrir("E quando uma mudança melhora?")
        ultimo = TRACE["aceites"][-1]["para"]
        self.detalhe(ultimo, TRACE["avaliacoes"], ZOOM)
        self.valor = self.texto_valor(ultimo, GREEN)
        el = Elevador()
        # `detalhe` criou o valor na cor do método; a cena anterior termina em verde.
        inicio = [*self.fab, *self.hz, *self.q.itens(), self.axis, self.labels, self.expl, self.valor, *self.cont, el.trilho, el.portas]
        self.add(*inicio)
        self.busca(inicio, el)
        self.fecho()

    def flag(self, p):
        return bandeira(self.mapa.c2p(*p), escala=.95)

    def busca(self, inicio, el):
        self.beat("busca", "E se ninguém domina, mas é novo?")
        self.mapa, self.rot = eixos(MAPA, MC, ML)
        inc = TRACE["incomparavel"]
        atual, cand = inc["corrente"], inc["avaliacao"]
        fixos = [m for m in inicio if m not in (self.axis, self.labels, self.expl, *self.cont[1:])]
        self.play(*(FadeOut(m) for m in fixos), FadeOut(self.axis, scale=.5), FadeOut(self.labels),
                  FadeIn(self.mapa), FadeIn(self.rot), FadeOut(self.cont[1]), FadeOut(self.cont[2]),
                  Transform(self.expl, explorador(self.mapa.c2p(*objetivo(atual)))), run_time=1.0)
        self.remove(*self.cont)
        n = self.n
        n.set_value(cand - 1)
        # Coluna de números à esquerda.
        nums = VGroup(left(text("avaliação", 19, MUTED), -6.5, 1.95), left(text("rejeitadas", 19, MUTED), -6.5, .95),
                      left(text("no arquivo", 19, MUTED), -6.5, -.05))

        def no_arquivo(x):
            return len(self.arquivo_em(x))
        vivo = [always_redraw(lambda: left(rotulo(pt(round(n.get_value()), 0), 34, INK, True), -6.5, 1.52)),
                always_redraw(lambda: left(rotulo(str(rejeitadas(round(n.get_value()))), 34, CORAL, True), -6.5, .52)),
                always_redraw(lambda: left(rotulo(str(no_arquivo(round(n.get_value()))), 34, COR, True), -6.5, -.48))]
        # Portas do shake: fila dourada, distinta do elevador do VND.
        portas = VGroup()
        for k in range(5):
            portas.add(VGroup(RoundedRectangle(width=.46, height=.4, corner_radius=.06, stroke_color=GRID, stroke_width=1.8),
                              text(PORTAS[k], 14, MUTED, bold=True)).move_to(pos(-6.27 + .54 * k, -2.3)))
        sh_rot = left(text("shake", 19, GOLD, bold=True), -6.5, -1.5)
        pont = Polygon(pos(-.09, .16), pos(.09, .16), pos(0, 0), stroke_width=0, fill_color=GOLD, fill_opacity=1)
        pont.move_to(portas[0].get_top() + pos(0, .14))
        origem = objetivo(TRACE["origem"]["avaliacao"])
        # Arquivo imediatamente antes do candidato.
        flags = {tuple(p): self.flag(p) for p in self.arquivo_em(cand - 1)}
        anel = Circle(radius=.2, stroke_color=GOLD, stroke_width=3).move_to(self.mapa.c2p(*origem))
        anel_rot = text("origem", 17, GOLD, bold=True).next_to(anel, pos(-1, 0), buff=.12).shift(pos(0, -.02))
        self.play(FadeIn(nums), *(FadeIn(v) for v in vivo), FadeIn(portas), FadeIn(sh_rot), FadeIn(pont),
                  *(FadeIn(f) for f in flags.values()), Create(anel), FadeIn(anel_rot), run_time=.6)
        self.bring_to_front(self.expl)
        # Candidato incomparável: cruz do corrente e ponto fora dos quadrantes decisivos.
        c = self.mapa.c2p(*objetivo(atual))
        x0, x1, y0, y1 = self.mapa.c2p(11, 400)[0], self.mapa.c2p(25, 400)[0], self.mapa.c2p(11, 400)[1], self.mapa.c2p(11, 1600)[1]

        def quad(a, b, cor):
            return Rectangle(width=abs(a[0] - b[0]), height=abs(a[1] - b[1]), stroke_width=0, fill_color=cor,
                             fill_opacity=.13).move_to(pos((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
        melhor, pior = quad(c, pos(x0, y0), GREEN), quad(c, pos(x1, y1), CORAL)
        cruz = VGroup(DashedLine(pos(x0, c[1]), pos(x1, c[1]), color=MUTED, stroke_width=1.5),
                      DashedLine(pos(c[0], y0), pos(c[0], y1), color=MUTED, stroke_width=1.5))
        self.play(Create(cruz), FadeIn(melhor), FadeIn(pior), run_time=.6)
        novo = Dot(c, radius=.08, color=INK)
        self.add(novo)
        self.play(novo.animate.move_to(self.mapa.c2p(*objetivo(cand))), n.animate.set_value(cand), run_time=.9)
        p = tuple(objetivo(cand))
        depois = {tuple(q) for q in self.arquivo_em(cand)}
        assert p in depois
        f = self.flag(p)
        entra = text("entra no mapa", 24, COR, bold=True).next_to(f, pos(1, .6), buff=.5)
        saem = [q for q in flags if q not in depois]
        self.play(ReplacementTransform(novo, f), FadeIn(entra), *(self.tomba(flags.pop(q)) for q in saem), run_time=.6)
        flags[p] = f
        self.play(Indicate(self.expl, color=COR, scale_factor=1.6), run_time=.6)  # o corrente não muda
        self.wait(.7)
        # Expansão do arquivo: o shake volta a N1 sobre a mesma origem.
        fim = inc["fim_da_descida"]
        self.play(FadeOut(cruz), FadeOut(melhor), FadeOut(pior), FadeOut(entra), run_time=.3)
        flags = self.acelera(flags, cand, fim, 2.2)
        onda = VGroup(*(Circle(radius=.2, stroke_color=GOLD, stroke_width=4).move_to(anel) for _ in range(3)))
        arco = ArcBetweenPoints(self.expl.get_center(), anel.get_center(), angle=-1.2)
        aviso = left(text("mapa cresceu: N1 de novo", 18, GOLD, bold=True, width=2.9), -6.5, -2.82)
        self.play(FadeIn(aviso), MoveAlongPath(self.expl, arco), run_time=.7)
        self.play(LaggedStart(*(o.animate.scale(4).set_stroke(opacity=0) for o in onda), lag_ratio=.25),
                  Indicate(portas[0], color=GOLD, scale_factor=1.35), run_time=.9)
        self.remove(onda)
        self.play(FadeOut(aviso), run_time=.25)
        # A busca inteira, pelos shakes reais.
        suc = TRACE["shakes"]["sucessos"]
        for k, s in enumerate(suc[1:]):
            ate = suc[k + 2]["avaliacao"] - 1 if k + 2 < len(suc) else TRACE["avaliacoes"]
            self.play(pont.animate.move_to(portas[s["porta"]].get_top() + pos(0, .14)),
                      Transform(self.expl, explorador(self.mapa.c2p(*s["ponto"])), path_arc=.8),
                      n.animate.set_value(s["avaliacao"]), run_time=.35)
            flags = self.acelera(flags, s["avaliacao"], ate, 1.5)
            expandiu = ate in TRACE["expansoes"]
            volta = [Transform(self.expl, explorador(self.mapa.c2p(*origem)), path_arc=.8)]
            if expandiu:
                volta.append(Indicate(portas[0], color=GOLD, scale_factor=1.3))
            if k + 2 < len(suc):
                self.play(*volta, run_time=.3)
        self.flags = flags
        self.sobras = [nums, *vivo, portas, sh_rot, pont, anel, anel_rot]
        self.wait(.3)
        self.hold()

    def arquivo_em(self, x):
        atual = []
        for k, pts in TRACE["arquivos"]:
            if k > x:
                break
            atual = pts
        return [tuple(p) for p in atual]

    def tomba(self, f):
        pe = f[2].get_center()

        def cair(m, alpha, base=f.copy()):
            m.become(base.copy().rotate(-PI / 2 * alpha, about_point=pe).set_opacity(1 - alpha))
        return UpdateFromAlphaFunc(f, cair, remover=True)

    def acelera(self, flags, de, ate, rt):
        """Trechos reais de avaliações: pontos novos, bandeiras e contador."""
        blocos = max(1, math.ceil((ate - de) / 60))
        if not hasattr(self, "vistos"):
            self.vistos, self.nuvem = set(), []
        marcos = [de + round((ate - de) * (k + 1) / blocos) for k in range(blocos)]
        ini = de
        for m in marcos:
            novos = {tuple(p) for p in TRACE["pontos"][ini - 1:m] if p} - self.vistos
            self.vistos |= novos
            grupo = VGroup(*(Dot(self.mapa.c2p(*p), radius=.032, color=COR).set_opacity(.35) for p in sorted(novos)))
            alvo = self.arquivo_em(m)
            anims = [self.n.animate.set_value(m)]
            if len(grupo):
                anims.append(FadeIn(grupo))
                self.nuvem.append(grupo)
            for q in [q for q in flags if q not in alvo]:
                anims.append(self.tomba(flags.pop(q)))
            for q in alvo:
                if q not in flags:
                    flags[q] = self.flag(q)
                    anims.append(GrowFromEdge(flags[q], DOWN))
            for a in TRACE["aceites"]:
                if ini < a["para"] <= m:
                    ultimo = a["para"]
                    anims = [x for x in anims if getattr(x, "mobject", None) is not self.expl]
                    anims.append(Transform(self.expl, explorador(self.mapa.c2p(*objetivo(ultimo)))))
            self.play(*anims, run_time=rt / blocos, rate_func=linear)
            ini = m
        return flags

    def fecho(self):
        self.beat("fecho", "O que encontramos?", *self.sobras)
        melhor = TRACE["frente"][TRACE["melhor"]]
        axis, labels = axes((10, 24, 2), (400, 900, 100), center=(5.02, .35), width=2.75, height=2.7,
                            x_label="Cmax (h)", y_label="TEC ($)", numbers=True)
        exata = VGroup(staircase(axis, FRENTE, GOLD).set_stroke(opacity=.35), dots(axis, FRENTE, GOLD, .05).set_opacity(.35))
        pontos = dots(axis, FRENTE_VNS, COR, .075)
        ordem = [self.flags[p] for p in FRENTE_VNS]
        foco = ordem[TRACE["melhor"]]
        itens = self.base()
        q = Quadro(melhor, EIXO)
        gantt = VGroup(*q.itens())
        self.play(Indicate(foco, color=GOLD, scale_factor=1.6), run_time=.5)
        centro = foco.get_center()
        self.play(*(FadeOut(g) for g in self.nuvem), FadeOut(self.mapa), FadeOut(self.rot), FadeOut(self.expl),
                  FadeIn(axis), FadeIn(labels), *(FadeIn(m) for m in itens), GrowFromPoint(gantt, centro),
                  *(ReplacementTransform(f, p) for f, p in zip(ordem, pontos)), run_time=1.4)
        escada = staircase(axis, FRENTE_VNS, COR, 3)
        self.play(FadeIn(exata), Create(escada), run_time=.9)
        anel = Circle(radius=.15, stroke_color=INK, stroke_width=2.5).move_to(pontos[TRACE["melhor"]])
        valor = text(par(melhor), 24, COR, bold=True).move_to(pos(5.0, -2.2))
        c = TRACE["campanha"]["parametros"]
        selo = VGroup(RoundedRectangle(width=3.1, height=.74, corner_radius=.1, stroke_color=GOLD, stroke_width=2),
                      VGroup(text(f"campanha: {c['initial_solutions']} · {c['max_candidates_per_neighborhood']} · "
                                  f"{c['shaking_attempts']}", 21, GOLD, bold=True),
                             text(f"{pt(c['max_evaluations'], 0)} avaliações", 18, MUTED)).arrange(DOWN, buff=.09)
                      ).move_to(pos(5.0, -2.88))
        self.play(Create(anel), FadeIn(valor), FadeIn(selo, scale=1.2), run_time=.7)
        self.wait(.8)
        self.hold()
