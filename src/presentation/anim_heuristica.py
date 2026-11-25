"""Heurísticas: construção ponderada e inserção ótima de ociosidade. Só lê data/trace_heuristica.json."""

from math import cos, sin

from manim import (
    AnimationGroup, Arc, Circle, Create, DashedLine, Dot, DoubleArrow, FadeIn, FadeOut, Indicate, LaggedStart,
    Line, Rectangle, ReplacementTransform, RoundedRectangle, SurroundingRectangle, Transform, Triangle, VGroup,
    VMobject, ValueTracker, always_redraw, interpolate_color, linear, smooth, there_and_back, BLACK, PI,
)

from fabrica import (
    CORES, DADOS, EIXO, FAIXAS, FORA, NA_PONTA, PONTA, CenaContinua, Eixo, medidor, plano, rotulo,
)
from visual import (
    COLORS, CORAL, CYAN, FUNDO, GOLD, GREEN, GRID, HERE, INK, MUTED, axes, dots, left, pos, pt, read_json,
    staircase, text,
)

T = read_json(HERE / "data" / "trace_heuristica.json")
COR_C, COR_O = COLORS["construtiva"], COLORS["ociosidade"]
REGRAS = {"lpt_min": "mínimo", "lpt_max": "máximo", "lpt_soma": "soma"}
CONSTRUCAO, AJUSTE, SOLTURA = T["construcao"], T["ajuste"]["passos"], T["soltura"]
FRENTE_C = [(p["cmax"], p["tec"]) for p in T["frente_construtiva"]]
FRENTE_O = [(p["cmax"], p["tec"]) for p in T["frente_ociosidade"]]
EXATA = [tuple(p) for p in T["exata"]]
LIMITES = (10, 26, 4), (400, 1000, 100)
assert all(LIMITES[0][0] < x < LIMITES[0][1] and LIMITES[1][0] < y < LIMITES[1][1] for x, y in
           [*FRENTE_C, *FRENTE_O, *EXATA, *((c["plano"]["cmax"], c["plano"]["tec"]) for c in T["construcoes"]),
            *(tuple(p) for c in T["caminhos"] for p in c["pontos"])])


def moeda(value):
    return f"$ {pt(value, 1)}"


def par(p):
    return f"{p['cmax']} h · {moeda(p['tec'])}"


def objetivos():
    axis, labels = axes(*LIMITES, center=(5.02, .35), width=2.75, height=2.7,
                        x_label="Cmax (h)", y_label="TEC ($)", numbers=True)
    return axis, labels


def ficha(job, x, y, w=.72, h=.42):
    return VGroup(Rectangle(width=w, height=h, stroke_width=0, fill_color=CORES[job], fill_opacity=1),
                  rotulo(f"T{job + 1}", 19, FUNDO, True)).move_to(pos(x, y))


class Gantt:
    """Blocos de um plano, com as transições para outro plano que contenha as mesmas tarefas."""

    def __init__(self, p=None, eixo=EIXO):
        self.eixo, self.tarefas, self.setups, self.esperas = eixo, {}, {}, {}
        for b in (p or dict(blocks=[]))["blocks"]:
            self.incluir(b)

    def incluir(self, b):
        j = b["job"]
        self.tarefas[j], self.setups[j], self.esperas[j] = self.eixo.bloco(b), self.eixo.setup(b), self.eixo.espera(b)

    def itens(self):
        return [*self.setups.values(), *self.esperas.values(), *self.tarefas.values()]

    def para(self, p, so=None, **opts):
        anims = []
        for b in p["blocks"]:
            j = b["job"]
            if j in self.tarefas and (so is None or j in so):
                anims += [Transform(self.tarefas[j], self.eixo.bloco(b), **opts),
                          Transform(self.setups[j], self.eixo.setup(b)),
                          Transform(self.esperas[j], self.eixo.espera(b))]
        return anims


def marca_cmax(cmax):
    x = EIXO.at(cmax)
    return VGroup(DashedLine(pos(x, 1.75), pos(x, -1.6), color=CYAN),
                  rotulo("Cmax", 22, CYAN, True).move_to(pos(x, 1.98)))


def mola(a, b, amplitude=.11, voltas=5, cor=GOLD):
    """Ziguezague entre dois pontos da tela."""
    v = b - a
    n = pos(-v[1], v[0]) / max(1e-6, (v[0] ** 2 + v[1] ** 2) ** .5)
    pontos = [a] + [a + v * (k + .5) / (2 * voltas) + n * amplitude * (1 if k % 2 else -1)
                    for k in range(2 * voltas)] + [b]
    return VMobject(stroke_color=cor, stroke_width=2).set_points_as_corners(pontos)


def molinha(b):
    """Mola comprimida na base da barra; não ocupa tempo."""
    x, y = EIXO.at(b["start"]), FAIXAS[b["machine"]] - EIXO.altura * DADOS["factor"][b["mode"]] / 2 - .08
    return mola(pos(x + .04, y), pos(EIXO.at(b["end"]) - .04, y), .05, 2 * round(b["end"] - b["start"]))


def cadeado(x, y):
    corpo = RoundedRectangle(width=.24, height=.19, corner_radius=.04, stroke_width=0, fill_color=COR_O, fill_opacity=1)
    arco = Arc(radius=.075, start_angle=0, angle=PI, color=COR_O, stroke_width=3).next_to(corpo, pos(0, 1), buff=0)
    return VGroup(corpo, arco, Dot(corpo.get_center(), radius=.025, color=FUNDO)).move_to(pos(x, y))


def cadeados(p):
    """Um cadeado por par de tarefas vizinhas: a ordem está fixa."""
    travas = VGroup()
    for m in range(3):
        seq = [b for b in p["blocks"] if b["machine"] == m]
        for a, b in zip(seq, seq[1:]):
            travas.add(cadeado(EIXO.at((a["end"] + b["start"]) / 2), FAIXAS[m] + .40))
    return travas


class CenaHeuristica(CenaContinua):
    total = 2

    def texto_valor(self):
        """Valor lido da posição do ponto, para os dois mudarem juntos."""
        def ler():
            x, y = self.axis.p2c(self.ponto.get_center())[:2]
            return rotulo(f"{round(x)} h · {moeda(y)}", 25, GOLD, True).move_to(pos(5.0, -2.12))
        return always_redraw(ler)

    def gantt_a_frente(self):
        self.bring_to_front(*self.gantt.setups.values(), *self.gantt.esperas.values(), *self.gantt.tarefas.values())

    def quadro_travado(self):
        """Último quadro da primeira cena e primeiro da segunda."""
        p = SOLTURA["antes"]
        base = self.base()
        axis, labels = objetivos()
        frente = VGroup(staircase(axis, FRENTE_C, COR_C, 2), *dots(axis, FRENTE_C, COR_C, .06))
        ponto = Dot(axis.c2p(p["cmax"], p["tec"]), radius=.11, color=GOLD)
        valor = rotulo(par(p), 25, GOLD, True).move_to(pos(5.0, -2.12))
        resumo = text(resumo_frente(), 19, COR_C, width=3.3).move_to(pos(5.0, -2.62))
        return dict(base=base, axis=axis, labels=labels, frente=frente, ponto=ponto, valor=valor, resumo=resumo,
                    gantt=Gantt(p), marca=marca_cmax(p["cmax"]), travas=cadeados(p))


def exata_esmaecida(axis, raio):
    # A opacidade vai em cada parte: no grupo, a escada ganharia preenchimento.
    return VGroup(staircase(axis, EXATA, GOLD, 2).set_stroke(opacity=.45), *dots(axis, EXATA, GOLD, raio).set_opacity(.5))


def resumo_frente():
    return f"({FRENTE_C[0][0]}; {pt(FRENTE_C[0][1], 1)}) a ({FRENTE_C[-1][0]}; {pt(FRENTE_C[-1][1], 1)})"


TITULO_FINAL_1 = "Dá para economizar sem mexer na ordem?"


class HeuristicaConstrutiva(CenaHeuristica):
    chapter, number = "HEURÍSTICA · CONSTRUIR", 1

    def construct(self):
        self.abrir()
        base = self.base()
        axis, labels = objetivos()
        inicio = plano(15)
        gantt = Gantt(inicio)
        ponto = Dot(axis.c2p(inicio["cmax"], inicio["tec"]), radius=.11, color=GOLD)
        self.add(*base, *gantt.itens(), axis, labels, ponto)
        self.pergunta(base, axis, labels, gantt, ponto)
        self.sondas()
        self.pesos()
        self.modos()

    # ----- 1 -----------------------------------------------------------------
    def pergunta(self, base, axis, labels, gantt, ponto):
        self.beat("pergunta", "Dá para achar um bom plano sem testar todos?")
        xs, y = [-4.6 + .97 * k for k in range(8)], -2.0
        fichas = {j: ficha(j, xs[j], y) for j in range(8)}
        self.play(*(m.animate.scale(1.08) for m in gantt.tarefas.values()), run_time=.3)
        self.play(*(FadeOut(m) for m in (*base, *gantt.setups.values(), *gantt.esperas.values(), ponto, axis, labels)),
                  *(ReplacementTransform(gantt.tarefas[j], fichas[j], path_arc=.5) for j in range(8)), run_time=1.1)
        escala = .19
        barras = {}
        for j in range(8):
            grupo = VGroup()
            for k, regra in enumerate(("lpt_soma", "lpt_min", "lpt_max")):
                h = T["medidas"][regra][j]
                c = Rectangle(width=.2, height=h * escala, stroke_width=0, fill_color=CORES[j], fill_opacity=.9)
                c.move_to(pos(xs[j] - .25 + .25 * k, y + .30 + h * escala / 2))
                n = rotulo(str(h), 15, INK).next_to(c, pos(0, 1), buff=.06)
                grupo.add(VGroup(c, n))
            barras[j] = grupo
        self.play(LaggedStart(*(FadeIn(barras[j], shift=pos(0, .25)) for j in range(8)), lag_ratio=.08), run_time=.9)
        frase = text("as maiores primeiro", 30, COR_C, bold=True).move_to(pos(4.95, -.1))
        pares, nome = {j: VGroup(fichas[j], barras[j]) for j in range(8)}, None
        ordem_atual = list(range(8))
        for regra, k in (("lpt_soma", 0), ("lpt_max", 2), ("lpt_min", 1)):
            novo = text({"lpt_min": "na melhor máquina", "lpt_max": "na pior máquina",
                         "lpt_soma": "somando as três"}[regra], 25, INK).move_to(pos(4.95, -.65))
            foco = [barras[j][i].animate.set_opacity(1 if i == k else .16) for j in range(8) for i in range(3)]
            extra = [FadeIn(frase)] if nome is None else [FadeOut(nome)]
            self.play(*foco, FadeIn(novo), *extra, run_time=.4)
            nome, anims = novo, []
            for destino, j in enumerate(T["ordens"][regra]):
                d = xs[destino] - xs[ordem_atual.index(j)]
                if d:
                    anims.append(pares[j].animate(path_arc=-.7 if d > 0 else .7).shift(pos(d, 0)))
            self.play(*anims, run_time=1.1)
            ordem_atual = T["ordens"][regra]
            self.wait(.25)
        self.ordem = T["ordens"][CONSTRUCAO["regra"]]
        self.fila, self.restos = fichas, [frase, nome, *barras.values()]
        self.hold()

    # ----- 2 -----------------------------------------------------------------
    def sondas(self):
        self.beat("sondas", "Onde cabe a próxima?", *self.restos)
        faixa, trilhos, maquinas, horas, *_ = self.base()
        self.axis_p, self.labels_p = axes((0, 24, 6), (0, 1000, 250), center=(5.02, 1.02), width=2.75, height=1.55,
                                          x_label="Cmax (h)", y_label="TEC ($) parcial", numbers=True)
        chao = Line(pos(3.5, -2.75), pos(6.7, -2.75), color=GRID, stroke_width=2)
        legenda = VGroup(rotulo("preço  =", 17, MUTED), rotulo("tempo", 17, CYAN, True), rotulo("+", 17, MUTED),
                         rotulo("energia", 17, GOLD, True)).arrange(pos(1, 0), buff=.12).move_to(pos(5.1, -3.03))
        self.feitas = ValueTracker(0)
        nome, conta = medidor("opções testadas", lambda: str(round(self.feitas.get_value())), -2.55, COR_C, -5.2, 34)
        dica = text("máquina × modo × posição", 24, INK).move_to(pos(.1, -2.45))
        self.play(*(FadeIn(m) for m in (faixa, trilhos, maquinas, horas, self.axis_p, self.labels_p, chao, legenda, nome, conta)),
                  *(self.fila[j].animate.move_to(pos(-4.6 + .92 * k, 2.10)) for k, j in enumerate(self.ordem)), run_time=.9)
        self.gantt, self.ponto = Gantt(), None
        for k, passo in enumerate(CONSTRUCAO["passos"]):
            entre = 0 < passo["sondas"][passo["escolha"]]["position"] < passo["tamanho"]
            self.passo(passo, "lenta" if k == 0 or entre else "rapida", entre)
            if k == 0:
                self.play(FadeIn(dica), run_time=.4)
        self.wait(.4)
        # O plano inteiro encolhe até virar o ponto do plano de objetivos.
        self.axis, self.labels = objetivos()
        fim = CONSTRUCAO["passos"][-1]["depois"]
        alvo = Dot(self.axis.c2p(fim["cmax"], fim["tec"]), radius=.11, color=GOLD)
        self.play(*(FadeOut(m) for m in (self.axis_p, self.labels_p, chao, legenda, self.ponto, dica, nome, conta)),
                  FadeIn(self.axis), FadeIn(self.labels), run_time=.6)
        miniatura = VGroup(*(m.copy() for m in self.gantt.tarefas.values()))
        self.play(ReplacementTransform(miniatura, alvo), run_time=1)
        self.ponto, self.itens_base = alvo, (faixa, trilhos, maquinas, horas)
        self.valor_txt = self.texto_valor()
        self.play(FadeIn(self.valor_txt), run_time=.3)
        self.hold()

    def passo(self, passo, ritmo, entre):
        sondas, job, lenta = passo["sondas"], passo["job"], ritmo == "lenta"
        n, teto = len(sondas), max(s["f"] for s in sondas)
        largura, altura = min(.26, 3.1 / n * .75), 1.95
        fantasmas, colunas, pontos = VGroup(), VGroup(), VGroup()
        for i, s in enumerate(sondas):
            fantasmas.add(EIXO.caixa(s["machine"], s["start"], s["end"], DADOS["factor"][s["mode"]], fill_color=CORES[job],
                                     fill_opacity=.10, stroke_color=INK if entre else CORES[job], stroke_width=1.6))
            x = 5.1 + (i - (n - 1) / 2) * 3.1 / n
            h1, h2 = (altura * s[c] / teto for c in ("tempo", "energia"))
            colunas.add(VGroup(
                Rectangle(width=largura, height=h1, stroke_width=0, fill_color=CYAN, fill_opacity=.9).move_to(pos(x, -2.75 + h1 / 2)),
                Rectangle(width=largura, height=h2, stroke_width=0, fill_color=GOLD, fill_opacity=.9).move_to(pos(x, -2.75 + h1 + h2 / 2))))
            pontos.add(Dot(self.axis_p.c2p(s["cmax"], s["tec"]), radius=.045, color=CORES[job]).set_opacity(.55))
        ficha_ = self.fila[job]
        self.play(Indicate(ficha_, color=CORES[job], scale_factor=1.25), run_time=.45 if lenta else .2)
        self.play(LaggedStart(*(AnimationGroup(FadeIn(g, shift=pos(0, -.08)), FadeIn(c, shift=pos(0, .12)), FadeIn(d))
                                for g, c, d in zip(fantasmas, colunas, pontos)), lag_ratio=.35 if lenta else .02),
                  self.feitas.animate.set_value(self.feitas.get_value() + n), run_time=2.0 if lenta else .4)
        # As mais caras caem primeiro.
        ordem = sorted(range(n), key=lambda i: -sondas[i]["f"])
        e = passo["escolha"]
        quedas = [AnimationGroup(FadeOut(colunas[i], shift=pos(0, -.25)), FadeOut(fantasmas[i]), FadeOut(pontos[i]))
                  for i in ordem if i != e]
        self.play(LaggedStart(*quedas, lag_ratio=.25 if lenta else .01), run_time=1.7 if lenta else .3)
        self.remove(fantasmas, colunas, pontos)
        self.add(fantasmas[e], colunas[e], pontos[e])
        s, depois = sondas[e], passo["depois"]
        novo = next(b for b in depois["blocks"] if b["job"] == job)
        preco = None
        if lenta:
            preco = VGroup(rotulo(pt(s["tempo"], 3), 19, CYAN, True), rotulo("+", 19, MUTED),
                           rotulo(pt(s["energia"], 3), 19, GOLD, True), rotulo("=", 19, MUTED),
                           rotulo(pt(s["f"], 3), 19, INK, True)).arrange(pos(1, 0), buff=.10).move_to(pos(.1, -2.95))
            borda = SurroundingRectangle(colunas[e], color=COR_C, buff=.06)
            self.play(fantasmas[e].animate.set_stroke(COR_C, 4).set_fill(opacity=.3), Create(borda), FadeIn(preco), run_time=.5)
            self.wait(.4)
        # Primeiro as vizinhas abrem espaço; depois a tarefa encaixa.
        abre = self.gantt.para(depois)
        mudou = any(b["job"] in self.gantt.tarefas and abs(self.gantt.tarefas[b["job"]].get_center()[0]
                                                           - EIXO.at((b["start"] + b["end"]) / 2)) > .01
                    for b in depois["blocks"])
        if abre and (mudou or not lenta):
            self.play(*abre, ficha_.animate.move_to(pos(EIXO.at((novo["start"] + novo["end"]) / 2), FAIXAS[novo["machine"]] + .55))
                      if entre else ficha_.animate.shift(pos(0, .05)), run_time=1.1 if lenta else .25)
        self.gantt.incluir(novo)
        j = job
        destino = Dot(self.axis_p.c2p(depois["cmax"], depois["tec"]), radius=.10, color=GOLD)
        mov = FadeIn(destino) if self.ponto is None else ReplacementTransform(self.ponto, destino)
        self.add(self.gantt.setups[j], self.gantt.esperas[j])
        self.play(ReplacementTransform(ficha_, self.gantt.tarefas[j], path_arc=-.4), FadeOut(fantasmas[e]),
                  FadeOut(pontos[e]), mov, run_time=.8 if lenta else .35)
        self.ponto = destino
        self.gantt_a_frente()
        self.play(FadeOut(colunas[e]), *([FadeOut(preco), FadeOut(borda)] if preco else []), run_time=.4 if lenta else .12)
        if entre:
            self.wait(.4)

    # ----- 3 -----------------------------------------------------------------
    def pesos(self):
        self.beat("pesos", "E se a energia valer mais que o tempo?")
        centro, raio = pos(-1.2, -3.1), .95
        a = ValueTracker(CONSTRUCAO["alfa"])
        mostrador = VGroup(Arc(radius=raio, start_angle=0, angle=PI, color=MUTED, stroke_width=3).move_arc_center_to(centro),
                           *(Line(centro + .83 * pos(cos(k * PI / 10), sin(k * PI / 10)),
                                  centro + .95 * pos(cos(k * PI / 10), sin(k * PI / 10)), color=MUTED, stroke_width=2)
                             for k in range(11)), Dot(centro, radius=.07, color=COR_C),
                           text("tempo", 22, CYAN, bold=True).move_to(centro + pos(-1.6, .25)),
                           text("energia", 22, GOLD, bold=True).move_to(centro + pos(1.68, .25)))
        agulha = always_redraw(lambda: Line(centro, centro + .8 * pos(cos(a.get_value() * PI), sin(a.get_value() * PI)),
                                            color=COR_C, stroke_width=6))
        leitura = always_redraw(lambda: rotulo(f"α = {pt(a.get_value(), 1)}", 28, COR_C, True).move_to(pos(2.1, -2.55)))
        self.play(FadeIn(mostrador), FadeIn(agulha), FadeIn(leitura), run_time=.5)
        serie = {round(c["alfa"], 1): c["plano"] for c in T["construcoes"] if c["regra"] == CONSTRUCAO["regra"]}
        rastro = VGroup()
        atual = serie[.5]
        for k in (10, *range(9, -1, -1)):
            p = serie[k / 10]
            igual = (p["cmax"], p["tec"]) == (atual["cmax"], atual["tec"])
            if igual:
                self.play(a.animate.set_value(k / 10), run_time=.2)
                continue
            marca = Dot(self.ponto.get_center(), radius=.055, color=COR_C)
            fio = Line(self.ponto.get_center(), self.axis.c2p(p["cmax"], p["tec"]), color=COR_C, stroke_width=1.5)
            self.add(marca)
            self.play(a.animate.set_value(k / 10), *self.gantt.para(p, path_arc=.7),
                      self.ponto.animate.move_to(self.axis.c2p(p["cmax"], p["tec"])), Create(fio),
                      run_time=1.1 if k != 10 else .9)
            rastro.add(marca, fio)
            atual = p
        # Surpresa: só energia não dá o menor TEC da série.
        melhor = min(serie.values(), key=lambda p: p["tec"])
        aviso = VGroup(left(text(f"só energia: {moeda(serie[0]['tec'])}", 20, CORAL, bold=True), -6.4, -2.45),
                       left(text(f"α 0,2: {moeda(melhor['tec'])}", 20, GREEN, bold=True), -6.4, -2.85))
        assert melhor is serie[.2]
        eco = Dot(self.axis.c2p(melhor["cmax"], melhor["tec"]), radius=.09, color=GREEN)
        self.play(FadeIn(aviso), FadeIn(eco, scale=2), run_time=.5)
        self.wait(.8)

        # As três filas disparam as 33 construções.
        faixa, trilhos, maquinas, horas = self.itens_base
        filas, nomes = {}, VGroup()
        for m, regra in enumerate(REGRAS):
            filas[regra] = [ficha(j, -4.7 + .82 * i, FAIXAS[m], .66, .42) for i, j in enumerate(T["ordens"][regra])]
            nomes.add(text(REGRAS[regra], 20, COR_C, bold=True).move_to(pos(-6.05, FAIXAS[m])))
        ativa = CONSTRUCAO["regra"]
        por_job = dict(zip(T["ordens"][ativa], filas[ativa]))
        self.play(*(FadeOut(m) for m in (aviso, eco, mostrador, agulha, leitura, rastro, self.valor_txt, self.ponto, faixa, trilhos, maquinas, horas,
                                         *self.gantt.setups.values(), *self.gantt.esperas.values())),
                  *(ReplacementTransform(self.gantt.tarefas[j], por_job[j], path_arc=.5) for j in range(8)),
                  *(FadeIn(f) for r in filas if r != ativa for f in filas[r]), FadeIn(nomes), run_time=1)
        self.remove(a)
        feitas = ValueTracker(0)
        nome, conta = medidor("construções", lambda: str(round(feitas.get_value())), -2.55, COR_C, -5.2, 36)
        nome2 = left(text("objetivos distintos", 19, MUTED), -2.4, -2.21)
        valor2 = left(rotulo(str(T["objetivos_distintos"]), 36, GOLD, True), -2.4, -2.65)
        self.play(FadeIn(nome), FadeIn(conta), run_time=.2)
        particulas, vistos, repetidas, anims = [], set(), [], []
        for k in range(11):   # as três filas em paralelo
            for m, regra in enumerate(REGRAS):
                c = next(c for c in T["construcoes"] if c["regra"] == regra and abs(c["alfa"] - (10 - k) / 10) < 1e-9)
                chave = c["plano"]["cmax"], c["plano"]["tec"]
                d = Dot(pos(1.75, FAIXAS[m]), radius=.06, color=COR_C).set_opacity(0)
                anims.append(d.animate(path_arc=-.9 + .6 * m).set_opacity(1).move_to(self.axis.c2p(*chave)))
                (repetidas if chave in vistos else particulas).append(d)
                vistos.add(chave)
        assert len(particulas) == T["objetivos_distintos"]
        self.play(LaggedStart(*anims, lag_ratio=.06), feitas.animate.set_value(len(T["construcoes"])), run_time=2.4)
        aneis = [Circle(radius=.07, color=GOLD, stroke_width=2).move_to(d) for d in repetidas]
        self.add(*aneis)
        self.play(*(r.animate.scale(3).set_stroke(opacity=0) for r in aneis), *(FadeOut(d) for d in repetidas),
                  FadeIn(nome2), FadeIn(valor2), run_time=.8)
        self.remove(*aneis)
        self.wait(.4)
        # Um ponto escolhido aproxima-se e a fila dele monta o plano.
        p = AJUSTE[0]["plano"]
        self.particulas = VGroup(*particulas)
        self.ponto = Dot(self.axis.c2p(p["cmax"], p["tec"]), radius=.11, color=GOLD)
        self.gantt = Gantt(p)
        soma = dict(zip(T["ordens"]["lpt_soma"], filas["lpt_soma"]))
        self.valor_txt = self.texto_valor()
        self.play(FadeIn(self.ponto, scale=2.5), self.particulas.animate.set_opacity(.30), FadeIn(self.valor_txt), run_time=.5)
        base = self.base()
        self.itens_base = base[:4]
        self.add(*self.itens_base)
        self.bring_to_front(*soma.values())
        self.play(*(FadeOut(f) for r in filas if r != "lpt_soma" for f in filas[r]), FadeOut(nomes),
                  *(FadeIn(m) for m in (*self.itens_base, *self.gantt.setups.values())),
                  *(ReplacementTransform(soma[j], self.gantt.tarefas[j], path_arc=.4) for j in range(8)),
                  FadeOut(nome), FadeOut(conta), FadeOut(nome2), FadeOut(valor2), run_time=1)
        self.add(*self.gantt.esperas.values())
        self.remove(feitas)
        self.bring_to_front(*self.gantt.setups.values(), *self.gantt.tarefas.values())
        self.hold()

    # ----- 4 -----------------------------------------------------------------
    def modos(self):
        self.beat("modos", TITULO_FINAL_1)
        marca = marca_cmax(AJUSTE[0]["plano"]["cmax"])
        dica = text("economia por hora", 24, INK).move_to(pos(-1.2, -2.55))
        self.play(Create(marca[0]), FadeIn(marca[1]), FadeIn(dica), run_time=.5)
        trilha = VGroup()
        for k, passo in enumerate(AJUSTE[:-1]):
            blocos = {b["job"]: b for b in passo["plano"]["blocks"]}
            setas = VGroup()
            for t in passo["trocas"]:
                livre = t["aumento"] <= 0
                taxa = t["economia"] / max(1, t["aumento"])
                b = blocos[t["job"]]
                topo = FAIXAS[b["machine"]] + EIXO.altura * DADOS["factor"][b["mode"]] / 2 + .05
                h, x = .14 + .0042 * taxa, EIXO.at(b["start"]) + .05
                cor = GREEN if livre else GOLD
                seta = VGroup(Line(pos(x, topo + h), pos(x, topo + .08), color=cor, stroke_width=4),
                              Triangle(color=cor, fill_opacity=1, stroke_width=0).scale(.07).rotate(PI).move_to(pos(x, topo + .06)))
                fala = f"{moeda(t['economia'])} · 0 h" if livre else f"{moeda(taxa)}/h"
                setas.add(VGroup(seta, left(rotulo(fala, 18, cor, True), x + .10, topo + .18)))
            e = passo["escolha"]
            t, ritmo = passo["trocas"][e], (1 if k < 2 else .7)
            self.play(LaggedStart(*(FadeIn(s, shift=pos(0, -.12)) for s in setas), lag_ratio=.2), run_time=.8 * ritmo)
            self.play(*(s.animate.set_opacity(.18) for i, s in enumerate(setas) if i != e),
                      Indicate(setas[e], color=setas[e][0][0].get_color(), scale_factor=1.35), run_time=.6 * ritmo)
            if k == 0:
                self.wait(.5)
            novo = AJUSTE[k + 1]["plano"]
            marca_no_caminho = Dot(self.ponto.get_center(), radius=.055, color=COR_C)
            fio = Line(self.ponto.get_center(), self.axis.c2p(novo["cmax"], novo["tec"]), color=COR_C, stroke_width=2)
            self.add(marca_no_caminho)
            trilha.add(marca_no_caminho, fio)
            self.play(FadeOut(setas), self.gantt.tarefas[t["job"]].animate.stretch(.9, 0), run_time=.25)
            self.play(*self.gantt.para(novo), Transform(marca, marca_cmax(novo["cmax"])), Create(fio),
                      self.ponto.animate.move_to(self.axis.c2p(novo["cmax"], novo["tec"])), run_time=1.1 * ritmo)
            if k < 2:
                self.wait(.35)
        # Todas as partidas descem a própria escada.
        feitas = ValueTracker(0)
        nome, conta = medidor("soluções nos caminhos", lambda: str(round(feitas.get_value())), -2.55, COR_C, -5.2, 36)
        escadas = VGroup()
        for c in T["caminhos"]:
            if len(c["pontos"]) > 1:
                escadas.add(VMobject(stroke_color=COR_C, stroke_width=1.5).set_points_as_corners(
                    [self.axis.c2p(*p) for p in c["pontos"]]))
        self.play(FadeOut(dica), FadeIn(nome), FadeIn(conta), run_time=.3)
        self.play(LaggedStart(*(Create(e) for e in escadas), lag_ratio=.15),
                  feitas.animate.set_value(T["solucoes_ajuste"]), run_time=1.8)
        fim = self.quadro_travado()
        base_nova = fim["base"]
        self.remove(*self.itens_base)
        self.add(*base_nova[:4])
        self.bring_to_front(*self.gantt.setups.values(), *self.gantt.esperas.values(), *self.gantt.tarefas.values(), marca)
        self.play(FadeOut(escadas), FadeOut(trilha), FadeOut(self.particulas), FadeIn(fim["frente"]), FadeIn(fim["resumo"]), run_time=.8)
        self.bring_to_front(self.ponto)
        self.wait(.3)
        # Um ponto da frente fornece a sequência; os cadeados a prendem.
        self.play(*self.gantt.para(SOLTURA["antes"]), Transform(marca, marca_cmax(SOLTURA["antes"]["cmax"])),
                  self.ponto.animate.move_to(fim["ponto"]), FadeOut(nome), FadeOut(conta),
                  FadeIn(base_nova[4]), FadeIn(base_nova[5]), run_time=.8)
        self.play(LaggedStart(*(FadeIn(c, shift=pos(0, -.45)) for c in fim["travas"]), lag_ratio=.15), run_time=.8)
        self.hold()


# ----- segunda cena -----------------------------------------------------------
def deslocado(b, horas):
    return dict(b, start=b["start"] + horas, end=b["end"] + horas, wait=b["wait"] + horas)


def custo_bloco(b, start):
    """Custo contínuo, só para o contador andar; nas horas inteiras é o do modelo."""
    end = start + b["end"] - b["start"]
    ponta = max(0, min(end, PONTA[1]) - max(start, PONTA[0]))
    taxa = DADOS["power"][b["machine"]] * DADOS["factor"][b["mode"]]
    return taxa * (NA_PONTA * ponta + FORA * (end - start - ponta))


ZOOM = Eixo(-5.4, .40, (1.60,), .5, 24)
CHAO, ALTO = -2.62, 3.15


class HeuristicaOciosidade(CenaHeuristica):
    chapter, number = "HEURÍSTICA · INSERIR OCIOSIDADE", 2

    def construct(self):
        self.abrir(TITULO_FINAL_1)
        q = self.quadro_travado()
        self.add(*q["base"], *q["gantt"].itens(), q["marca"], q["travas"], q["axis"], q["labels"], q["frente"],
                 q["ponto"], q["valor"], q["resumo"])
        self.soltar(q)
        self.curvas()
        self.confronto()

    # ----- 5 -----------------------------------------------------------------
    def soltar(self, q):
        self.beat("soltar", "E se a melhor jogada for não fazer nada?", q["resumo"])
        antes = {b["job"]: b for b in SOLTURA["antes"]["blocks"]}
        moveis = {1: ValueTracker(0), 7: ValueTracker(0), 5: ValueTracker(0)}
        fixos = sum(sum(b["costs"]) for j, b in antes.items() if j not in moveis)

        def cmax():
            return max(b["end"] + (max(0, moveis[j].get_value()) if j in moveis else 0) for j, b in antes.items())

        def tec():
            return fixos + sum(custo_bloco(antes[j], antes[j]["start"] + max(0, v.get_value())) for j, v in moveis.items())
        assert abs(tec() - SOLTURA["antes"]["tec"]) < 1e-6

        def barra(j):
            def corpo():
                d = moveis[j].get_value()
                b = deslocado(antes[j], d)
                g = VGroup(EIXO.bloco(b), molinha(b))
                if d > .02:
                    y = FAIXAS[b["machine"]]
                    g.add(EIXO.espera(b), mola(pos(EIXO.at(b["start"] - d), y), pos(EIXO.at(b["start"]), y), .10, 4))
                return g
            return always_redraw(corpo)
        molas = VGroup(*(molinha(b) for j, b in antes.items() if j not in moveis))
        dica = text("a ordem fica, o relógio solta", 24, INK).move_to(pos(-1.2, -3.06))
        arranque = [molinha(antes[j]) for j in moveis]
        self.play(LaggedStart(*(Create(m) for m in (*molas, *arranque)), lag_ratio=.1),
                  FadeIn(dica), run_time=.9)
        # Troca as três barras que vão andar por versões ligadas aos relógios.
        self.remove(*arranque)
        for j in moveis:
            self.remove(q["gantt"].tarefas[j], q["gantt"].esperas[j])
        vivas = {j: barra(j) for j in moveis}
        ponto = always_redraw(lambda: Dot(q["axis"].c2p(cmax(), tec()), radius=.11, color=GOLD))
        valor = always_redraw(lambda: rotulo(f"{round(cmax())} h · {moeda(tec())}", 25, GOLD, True).move_to(pos(5.0, -2.12)))
        marca = always_redraw(lambda: marca_cmax(cmax()))
        self.remove(q["ponto"], q["valor"], q["marca"])
        self.add(*vivas.values(), marca, ponto, valor)
        self.bring_to_front(q["travas"])
        esmaecer = [q["gantt"].tarefas[j] for j in antes if j not in moveis]
        # 1) T2: adiar não compensa, nem dentro da ponta nem depois dela.
        self.play(*(m.animate.set_opacity(.25) for m in esmaecer), run_time=.3)
        self.play(moveis[1].animate.set_value(2), run_time=1.1)
        assert abs(tec() - SOLTURA["t2_na_ponta"]["tec"]) < 1e-6
        ruim = text(f"+ {moeda(SOLTURA['t2_na_ponta']['tec'] - SOLTURA['antes']['tec'])}", 27, CORAL, bold=True).move_to(pos(5.0, -2.62))
        self.play(FadeIn(ruim, scale=1.3), run_time=.3)
        self.wait(.5)
        self.play(moveis[1].animate.set_value(7), FadeOut(ruim), run_time=1.2)
        assert abs(tec() - SOLTURA["t2_depois"]["tec"]) < 1e-6 and round(cmax()) == SOLTURA["t2_depois"]["cmax"]
        nada = text("$ 0,0 ganho · + 1 h", 25, CORAL, bold=True).move_to(pos(5.0, -2.62))
        self.play(FadeIn(nada), run_time=.3)
        self.wait(.5)
        self.play(moveis[1].animate.set_value(0), FadeOut(nada), run_time=.6)
        # 2) T8 e T6 invadem a ponta: recuam, batem no setup e saltam para depois dela.
        self.play(moveis[7].animate.set_value(-.25), moveis[5].animate.set_value(-.25), run_time=.4)
        self.play(moveis[7].animate.set_value(0), moveis[5].animate.set_value(0), run_time=.2)
        self.play(*(c.animate.shift(pos(0, -.07)) for c in q["travas"]), run_time=.25)
        self.play(moveis[7].animate.set_value(1), moveis[5].animate.set_value(1),
                  q["base"][0].animate(rate_func=there_and_back).set_fill(opacity=.55), run_time=2.4)
        fim = SOLTURA["depois"]
        assert abs(tec() - fim["tec"]) < 1e-6 and round(cmax()) == fim["cmax"]
        bom = VGroup(text(f"− {moeda(SOLTURA['antes']['tec'] - fim['tec'])}", 27, GREEN, bold=True),
                     text("mesma ordem, mesmos modos", 18, MUTED)).arrange(pos(0, -1), buff=.10).move_to(pos(5.0, -2.75))
        vazia = text("ponta vazia", 18, CORAL).move_to(pos(EIXO.at(11.5), FAIXAS[0] + .76))
        self.play(FadeIn(bom, scale=1.2), FadeIn(vazia), *(m.animate.set_opacity(1) for m in esmaecer), run_time=.5)
        estaticos = [VGroup(*(x.copy().clear_updaters() for x in v.submobjects)) for v in vivas.values()]
        fixas = [m.copy().clear_updaters() for m in (marca, ponto, valor)]
        self.remove(*vivas.values(), marca, ponto, valor)
        self.add(*estaticos, *fixas)
        self.bring_to_front(q["travas"])
        self.q, self.sair = q, [*estaticos, *fixas, bom, vazia, dica, molas]
        self.hold()

    # ----- 6 -----------------------------------------------------------------
    def curvas(self):
        q = self.q
        ordem = [t["job"] for t in T["curvas"][0]["tarefas"]]
        self.beat("curvas", "Como escolher o melhor instante de cada uma?", *self.sair, *q["base"][3:], q["base"][0],
                  q["base"][1], q["base"][2][1], q["base"][2][2], q["travas"], q["axis"], q["labels"], q["frente"], *q["gantt"].setups.values(),
                  *q["gantt"].esperas.values(), *(q["gantt"].tarefas[j] for j in range(8) if j not in ordem))
        m1 = q["base"][2][0]
        trilho = Line(pos(ZOOM.x, 1.6), pos(ZOOM.at(24), 1.6), color=GRID, stroke_width=1.5)
        faixa = Rectangle(width=3 * ZOOM.passo, height=2.05 - CHAO, stroke_width=0, fill_color=CORAL, fill_opacity=.14).move_to(
            pos(ZOOM.at(11.5), (2.05 + CHAO) / 2))
        chao = Line(pos(ZOOM.x, CHAO), pos(ZOOM.at(24) + .25, CHAO), color=MUTED, stroke_width=2)
        horas = VGroup(*(text(f"{(8 + t) % 24}h", 15, MUTED).move_to(pos(ZOOM.at(t), CHAO - .20)) for t in range(0, 25, 2)))
        chips = {j: ficha(j, 4.95 + .78 * k, 1.60, .66, .4) for k, j in enumerate(ordem)}
        origem = {}
        for j in ordem:
            m = q["gantt"].tarefas[j]
            if m not in self.mobjects:   # a barra móvel saiu com os demais restos
                b = next(b for b in SOLTURA["depois"]["blocks"] if b["job"] == j)
                m = EIXO.bloco(b)
            origem[j] = m
        self.play(*(ReplacementTransform(origem[j], chips[j]) for j in ordem), m1.animate.shift(pos(0, .45)),
                  FadeIn(trilho), FadeIn(faixa), FadeIn(chao), FadeIn(horas), run_time=.9)
        tarefas = T["curvas"][0]["tarefas"]
        leg = VGroup(left(text("f: exatamente em t", 20, INK, bold=True, width=2.1), 4.65, .85),
                     left(text("g: até t", 20, COR_O, bold=True), 4.65, -.35))
        self.play(FadeIn(leg), run_time=.3)

        def reconstruir(i, t):
            blocos = []
            while i >= 0:
                tt = tarefas[i]
                mode = tt["modo"][t]
                start = t - tt["duracao"][mode]
                b = dict(job=tt["job"], machine=0, mode=mode, start=start, end=t, setup=tt["setup"], wait=0)
                if i:
                    ant = tarefas[i - 1]
                    u = next(u for u, v in enumerate(ant["f"]) if v is not None and v == ant["g"][start - tt["setup"]])
                    b["wait"] = start - tt["setup"] - u
                    t = u
                else:
                    b["wait"] = start
                blocos.append(b)
                i -= 1
            return blocos

        anterior, corrente = None, None
        for i, (tt, teto, dur) in enumerate(zip(tarefas, (125, 225, 330), (3.6, 2.8, 2.0))):
            ini = next(t for t, v in enumerate(tt["f"]) if v is not None)
            relogio_t = ValueTracker(ini)

            def y(v, teto=teto):
                return CHAO + ALTO * v / teto

            def agora(r=relogio_t):
                return min(24, int(r.get_value() + 1e-6))

            def colunas(tt=tt, ini=ini, y=y, agora=agora, r=relogio_t):
                g = VGroup()
                for t in range(ini, agora() + 1):
                    frac = r.get_value() - t
                    pulso = 1 + (.10 * sin(PI * min(1, frac)) if t == agora() and t < 24 else 0)
                    base_ = tt["antes"][t] or 0
                    h0, h1 = (y(base_) - CHAO) * pulso, (y(tt["f"][t] - base_) - CHAO) * pulso
                    if base_:
                        g.add(Rectangle(width=.22, height=h0, stroke_width=0, fill_color=MUTED, fill_opacity=.55).move_to(pos(ZOOM.at(t), CHAO + h0 / 2)))
                    g.add(Rectangle(width=.22, height=h1, stroke_width=0, fill_color=CORES[tt["job"]], fill_opacity=.95).move_to(
                        pos(ZOOM.at(t), CHAO + h0 + h1 / 2)))
                return g

            def cortina(tt=tt, ini=ini, y=y, agora=agora):
                topo, pts = CHAO + ALTO + .12, []
                for t in range(ini, agora() + 1):
                    pts += [pos(ZOOM.at(t) - .2, y(tt["g"][t])), pos(ZOOM.at(t) + .2, y(tt["g"][t]))]
                agua = VMobject(stroke_width=0, fill_color=COR_O, fill_opacity=.30).set_points_as_corners(
                    [pos(pts[0][0], topo), *pts, pos(pts[-1][0], topo), pos(pts[0][0], topo)])
                beira = VMobject(stroke_color=COR_O, stroke_width=4).set_points_as_corners(pts)
                return VGroup(agua, beira)

            def barras(i=i, tt=tt, agora=agora):
                blocos = reconstruir(i, agora())
                g = VGroup()
                for b in blocos:
                    g.add(ZOOM.setup(b), ZOOM.espera(b), ZOOM.bloco(b))
                g.add(DashedLine(pos(ZOOM.at(agora()), 1.3), pos(ZOOM.at(agora()), CHAO), color=INK, stroke_width=1.5))
                return g
            nf = always_redraw(lambda: left(rotulo(moeda(tt["f"][agora()]), 32, INK, True), 4.65, .38))
            ng = always_redraw(lambda: left(rotulo(moeda(tt["g"][agora()]), 32, COR_O, True), 4.65, -.82))
            agua, cols, barras_ = always_redraw(cortina), always_redraw(colunas), always_redraw(barras)
            nota = []
            if i:
                nota = [VGroup(left(text("cinza: g da anterior,", 18, MUTED, width=2.1), 4.65, -1.55),
                              left(text("depois do setup", 18, MUTED, width=2.1), 4.65, -1.88))] if i == 1 else []
            self.play(FadeOut(chips[tt["job"]]), FadeIn(agua), FadeIn(cols), FadeIn(barras_), FadeIn(nf), FadeIn(ng),
                      *(FadeIn(n) for n in nota), *([FadeOut(anterior)] if anterior is not None else []), run_time=.4)
            if nota:
                leg_nota = nota[0]
            if i == 0:   # câmera lenta na subida da ponta, onde f e g se separam
                self.play(relogio_t.animate.set_value(10), run_time=1.2, rate_func=linear)
                self.play(relogio_t.animate.set_value(13), run_time=1.6, rate_func=linear)
                alto = VGroup(text("f sobe", 20, INK, bold=True).move_to(pos(ZOOM.at(13) + .75, y(tt["f"][13]) + .2)),
                              text("g não", 20, COR_O, bold=True).move_to(pos(ZOOM.at(13) + .75, y(tt["g"][13]) + .25)))
                self.play(FadeIn(alto), run_time=.3)
                self.wait(.7)
                self.play(FadeOut(alto), run_time=.2)
                self.play(relogio_t.animate.set_value(24), run_time=1.2, rate_func=linear)
            else:
                self.play(relogio_t.animate.set_value(24), run_time=dur, rate_func=linear)
            self.wait(.25)
            fixo = [m.copy().clear_updaters() for m in (agua, cols, barras_, nf, ng)]
            self.remove(agua, cols, barras_, nf, ng, relogio_t)
            self.add(*fixo)
            if i < 2:
                # A beira da cortina anda o setup e vira o piso da próxima tarefa.
                prox, teto2 = tarefas[i + 1], (125, 225, 330)[i + 1]
                piso = []
                for t in range(ini, 25 - prox["setup"]):
                    piso += [pos(ZOOM.at(t + prox["setup"]) - .2, CHAO + ALTO * tt["g"][t] / teto2),
                             pos(ZOOM.at(t + prox["setup"]) + .2, CHAO + ALTO * tt["g"][t] / teto2)]
                linha = VMobject(stroke_color=MUTED, stroke_width=3).set_points_as_corners(piso)
                self.play(FadeOut(fixo[0][0]), ReplacementTransform(fixo[0][1], linha), *(FadeOut(m) for m in fixo[1:]), run_time=.6)
                anterior = linha
            else:
                corrente = fixo
        # Três curvas, uma por máquina, caem umas sobre as outras.
        eps = [s for s in T["soma"] if 12 <= s["epsilon"] <= 20]
        escala, dx = .0042, .74
        xe = {s["epsilon"]: -5.3 + dx * k for k, s in enumerate(eps)}
        tons = [COR_O, interpolate_color(COR_O, BLACK, .30), interpolate_color(COR_O, BLACK, .55)]
        linhas_y = (.05, -1.30, CHAO)
        grupos, quedas = [], []
        for m in range(3):
            g = VGroup()
            for s in eps:
                v = s["partes"][m]
                if v is None:
                    continue
                h = v * escala
                r = Rectangle(width=.55, height=h, stroke_color=FUNDO, stroke_width=1, fill_color=tons[m], fill_opacity=1).move_to(
                    pos(xe[s["epsilon"]], linhas_y[m] + h / 2))
                g.add(r)
                abaixo = sum(s["partes"][k] for k in range(m + 1, 3)) * escala
                quedas.append((r, pos(xe[s["epsilon"]], CHAO + abaixo + h / 2)))
            grupos.append(g)
        nomes = VGroup(*(text(f"g · M{m + 1}", 18, COR_O, bold=True).move_to(pos(-6.2, linhas_y[m] + .4)) for m in range(3)))
        tempos = VGroup(*(text(f"{s['epsilon']} h", 17, MUTED).move_to(pos(xe[s["epsilon"]], CHAO - .22)) for s in eps))
        self.play(*(FadeOut(m) for m in (*corrente, trilho, faixa, horas, leg, leg_nota, m1)),
                  FadeIn(grupos[0], shift=pos(-.6, .3)), FadeIn(grupos[1]), FadeIn(grupos[2]),
                  FadeIn(nomes), FadeIn(tempos), run_time=.9)
        self.wait(.3)
        self.play(*(r.animate.move_to(d) for r, d in quedas), FadeOut(nomes), run_time=1.0)
        self.axis, labels = objetivos()
        self.play(FadeIn(self.axis), FadeIn(labels), run_time=.3)
        varre = Line(pos(xe[12], CHAO - .1), pos(xe[12], 1.0), color=GOLD, stroke_width=3)
        eps_rot, totais, pontos = None, VGroup(), VGroup()
        for s in eps:
            novo = rotulo(f"ε = {s['epsilon']} h", 22, GOLD, True).move_to(pos(xe[s["epsilon"]], 1.25))
            self.play(varre.animate.move_to(pos(xe[s["epsilon"]], (CHAO + .9) / 2)) if s is not eps[0] else Create(varre),
                      FadeIn(novo), *([FadeOut(eps_rot)] if eps_rot else []), run_time=.22)
            eps_rot = novo
            if s["total"] is None:
                if s is eps[0]:
                    x = text("M1 não cabe", 18, CORAL, bold=True).move_to(pos(xe[12] + dx / 2, -.40))
                    self.play(FadeIn(x), run_time=.2)
                    totais.add(x)
            elif s["novo"]:
                topo = pos(xe[s["epsilon"]], CHAO + s["total"] * escala + .17)
                r = rotulo(pt(s["total"], 1), 18, GOLD, True).move_to(topo)
                d = Dot(topo, radius=.08, color=COR_O)
                self.add(d)
                self.play(FadeIn(r), d.animate(path_arc=-.5).move_to(self.axis.c2p(s["epsilon"], s["total"])), run_time=.5)
                totais.add(r)
                pontos.add(d)
        escada = staircase(self.axis, [(s["epsilon"], s["total"]) for s in eps if s["novo"]], COR_O)
        self.play(Create(escada), run_time=.5)
        self.labels, self.pontos, self.escada = labels, pontos, escada
        self.sair = [*grupos, tempos, totais, varre, eps_rot, chao]
        self.hold()

    # ----- 7 -----------------------------------------------------------------
    def confronto(self):
        self.beat("confronto", "Quanto a espera rendeu?", *self.sair)
        grande, rot = axes((10, 22, 2), (400, 900, 100), center=(-1.5, -.45), width=7.9, height=3.7,
                           x_label="Cmax (h)", y_label="TEC ($)", numbers=True)
        c = {x: y for x, y in FRENTE_C}
        o = dict(FRENTE_O)
        usados = [x for x, _ in FRENTE_O if x >= 14]
        bolinhas = VGroup(*(Dot(grande.c2p(x, o[x]), radius=.10, color=COR_O) for x in usados))
        fundo = exata_esmaecida(grande, .06)
        cinza = VGroup(staircase(grande, FRENTE_C, MUTED, 2), *dots(grande, FRENTE_C, MUTED, .07))
        leg = VGroup(*(VGroup(Dot(pos(4.2, 1.5 - .42 * k), radius=.08, color=cor), left(text(n, 20, cor), 4.4, 1.5 - .42 * k))
                       for k, (n, cor) in enumerate((("construtiva", MUTED), ("espera + modos", COR_O), ("exata", GOLD)))))
        self.play(ReplacementTransform(self.axis, grande), FadeOut(self.labels), FadeIn(rot), FadeOut(self.escada),
                  *(ReplacementTransform(a, b) for a, b in zip(self.pontos, bolinhas)), FadeIn(leg), run_time=1)
        self.play(FadeIn(cinza), FadeIn(fundo), FadeOut(bolinhas), run_time=.6)
        # Cada ponto parte da construtiva (ou do degrau dela) e é puxado pela mola.
        puxados, molas = VGroup(), []
        for x, y_o in FRENTE_O:
            y_c = c.get(x, min(v for k, v in FRENTE_C if k <= x))
            d = Dot(grande.c2p(x, y_c), radius=.10, color=COR_O)
            puxados.add(d)
            if y_c - y_o > 1:
                molas.append(always_redraw(lambda d=d, a=grande.c2p(x, y_o): mola(a, d.get_center() if abs(d.get_center()[1] - a[1]) > .02 else a + pos(0, .02), .09, 4)))
        self.play(FadeIn(puxados), *(Create(m) for m in molas), run_time=.5)
        self.add(*molas)
        self.play(*(d.animate(rate_func=smooth).move_to(grande.c2p(*p)) for d, p in zip(puxados, FRENTE_O)), run_time=1.2)
        self.remove(*molas)
        linha_o = staircase(grande, FRENTE_O, COR_O)
        iguais = [r for r in T["confronto"] if r["lacuna"] == 0]
        aneis = [Circle(radius=.16, color=GREEN, stroke_width=4).move_to(grande.c2p(r["cmax"], r["exata"])) for r in iguais]
        self.play(Create(linha_o), *(Create(a) for a in aneis), run_time=.7)
        lacunas = VGroup()
        for r in T["confronto"]:
            if r["lacuna"]:
                a, b = grande.c2p(r["cmax"], r["exata"]), grande.c2p(r["cmax"], r["ociosidade"])
                lacunas.add(DoubleArrow(a, b, color=CORAL, buff=0, stroke_width=4, tip_length=.10, max_tip_length_to_length_ratio=.4))
            elif r["ociosidade"] is None:
                lacunas.add(Circle(radius=.13, color=CORAL, stroke_width=3).move_to(grande.c2p(r["cmax"], r["exata"])))
        difs = {r["lacuna"] for r in T["confronto"] if r["lacuna"]}
        assert len(difs) == 1
        lacunas.add(text(f"faltam {moeda(difs.pop())}", 20, CORAL, bold=True).move_to(grande.c2p(15.8, 800)),
                    text("não alcança", 20, CORAL, bold=True).move_to(grande.c2p(20.2, 550)))
        frase = text(f"{T['sequencias']} sequências", 34, COR_O, bold=True).move_to(pos(5.0, -.4))
        self.play(FadeIn(lacunas), run_time=.6)
        self.play(FadeIn(frase, scale=1.2), run_time=.4)
        self.wait(1)
        # Quadro-base final.
        axis, labels = objetivos()
        p = next(p for p in T["frente_ociosidade"] if (p["cmax"], p["tec"]) == (SOLTURA["depois"]["cmax"], SOLTURA["depois"]["tec"]))
        base, gantt = self.base(), Gantt(p)
        fundo2 = exata_esmaecida(axis, .05)
        frente2 = dots(axis, FRENTE_O, COR_O, .065)
        valor = rotulo(par(p), 25, GOLD, True).move_to(pos(5.0, -2.12))
        ponto = Dot(axis.c2p(p["cmax"], p["tec"]), radius=.11, color=GOLD)
        self.play(*(FadeOut(m) for m in (cinza, leg, lacunas, frase, rot, *aneis)), run_time=.4)
        self.play(ReplacementTransform(grande, axis), FadeIn(labels), ReplacementTransform(fundo, fundo2),
                  ReplacementTransform(linha_o, staircase(axis, FRENTE_O, COR_O)),
                  *(ReplacementTransform(a, b) for a, b in zip(puxados, frente2)), run_time=1)
        self.play(*(FadeIn(m) for m in (*base, *gantt.itens())), FadeIn(ponto), FadeIn(valor), run_time=.8)
        self.hold()
