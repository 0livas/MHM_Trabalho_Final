"""Método exato: rótulos, gavetas e a escada do epsilon. Todos os números vêm de trace_exato.json."""

from math import sqrt

import numpy as np
from manim import (
    ArcBetweenPoints, Circle, Create, DashedLine, Dot, FadeIn, FadeOut, GrowFromEdge, Indicate, LaggedStart, Line,
    Polygon, Rectangle, ReplacementTransform, RoundedRectangle, Square, Transform, UpdateFromAlphaFunc,
    VGroup, VMobject, ValueTracker, Wiggle, always_redraw, linear, smooth, there_and_back, DOWN, LEFT, UP, RIGHT,
)

from fabrica import CORES, EIXO, CenaContinua, Eixo, curva_tarifa, maquina, plano, rotulo
from visual import (
    COLORS, CORAL, FUNDO, GOLD, GREEN, GRID, HERE, INK, MUTED, axes, formula, left, pos, pt, read_json,
    staircase, text,
)

D = read_json(HERE / "data" / "trace_exato.json")
OURO = COLORS["exact_dp"]
CINZA = "#6B7686"
MEIO = plano(15)
VARREDURA = D["varredura"]
FRENTE = [(p["cmax"], p["tec"]) for p in VARREDURA if p["novo"]]
NOMES = ("rápido", "normal", "econômico")
LARGO = Eixo(passo=.335, total=24)
FAIXA3 = Eixo(faixas=(1.5, 1.5, 1.5))


def moeda(v):
    return f"$ {pt(v, 1)}"


def inteiro(v):
    return f"{v:,}".replace(",", ".")


def plano_eixos():
    axis, labels = axes((10, 26, 2), (400, 900, 100), center=(5.02, .35), width=2.75, height=2.7,
                        x_label="Cmax (h)", y_label="TEC ($)", numbers=True)
    axis.x_axis.tip.scale(.5, about_edge=RIGHT)
    return axis, labels


def valor_ponto(cmax, tec):
    return text(f"{cmax} h · {moeda(tec)}", 25, GOLD, bold=True).move_to(pos(5.0, -2.12))


class Quadro:
    """Barras de um plano, indexadas por tarefa, sobre um eixo qualquer."""

    def __init__(self, p, eixo=EIXO):
        self.eixo = eixo
        self.maq = {b["job"]: b["machine"] for b in p["blocks"]}
        self.barras = {b["job"]: eixo.bloco(b) for b in p["blocks"]}
        self.setups = {b["job"]: eixo.setup(b) for b in p["blocks"]}
        self.esperas = {b["job"]: eixo.espera(b) for b in p["blocks"]}

    def tudo(self):
        return [*self.setups.values(), *self.esperas.values(), *self.barras.values()]

    def ir(self, p, eixo=None, so=None, menos=()):
        eixo = eixo or self.eixo
        anims = []
        for b in p["blocks"]:
            j = b["job"]
            if (so is not None and j not in so) or j in menos:
                continue
            kw = dict(path_arc=.9) if self.maq[j] != b["machine"] else {}
            anims += [Transform(self.barras[j], eixo.bloco(b), **kw), Transform(self.setups[j], eixo.setup(b)),
                      Transform(self.esperas[j], eixo.espera(b))]
            self.maq[j] = b["machine"]
        return anims


def chip(j, lado=.30):
    caixa = Square(lado, stroke_width=0, fill_color=CORES[j], fill_opacity=1)
    nome = rotulo(f"T{j + 1}", 15, FUNDO, True)
    return VGroup(caixa, nome.scale(min(1, lado * .72 / nome.width)).move_to(caixa))


def etiqueta(jobs, ultima):
    """{tarefas} · última."""
    conjunto = VGroup(*(chip(j) for j in jobs)).arrange(RIGHT, buff=.06)
    partes = VGroup(text("{", 24, MUTED), conjunto, text("}  ·", 24, MUTED), chip(ultima, .34)).arrange(RIGHT, buff=.09)
    partes[3][0].set_stroke(INK, 2)
    return partes


def ficha(dados, escala=1.0, cor=OURO):
    caixa = RoundedRectangle(width=2.25, height=.76, corner_radius=.1, stroke_color=cor, stroke_width=2.4,
                             fill_color="#241f12", fill_opacity=.95)
    halo = RoundedRectangle(width=2.37, height=.88, corner_radius=.14, stroke_color=cor, stroke_width=7,
                            stroke_opacity=.16)
    mini = Eixo(x=-.98, passo=.098, faixas=(.17,) * 3, altura=.22)
    trilho = Line(pos(-.98, .17), pos(.98, .17), color=GRID, stroke_width=1)
    barras = VGroup(trilho, *(mini.setup(b) for b in dados["blocks"]), *(mini.bloco(b) for b in dados["blocks"]))
    numeros = rotulo(f"{dados['end']} h · {moeda(dados['energy'])}", 18, INK, True).move_to(pos(0, -.17))
    return VGroup(halo, caixa, barras, numeros).scale(escala)


def gaveta(x0, x1, y0, y1, cor=OURO):
    return VMobject(stroke_color=cor, stroke_width=3).set_points_as_corners(
        [pos(x0, y1), pos(x0, y0), pos(x1, y0), pos(x1, y1)])


def rachar(card):
    """Duas metades com borda em zigue-zague para substituir a ficha."""
    c, w, h = card[1].get_center(), card[1].width, card[1].height
    xs = (.12, -.10, .14, -.12, .08)
    borda = [c + pos(dx * w * .5, h * (.5 - k / 4)) for k, dx in enumerate(xs)]
    esq = Polygon(c + pos(-w / 2, h / 2), *borda, c + pos(-w / 2, -h / 2))
    dir_ = Polygon(c + pos(w / 2, h / 2), *borda, c + pos(w / 2, -h / 2))
    for m in (esq, dir_):
        m.set_stroke(CINZA, 2).set_fill("#2a2e36", 1)
    fenda = VMobject(stroke_color=CORAL, stroke_width=5).set_points_as_corners(borda)
    return fenda, VGroup(esq, dir_)


def faixa_m3():
    """Só a M3, no alto: faixa usada pelos rótulos."""
    m = maquina(2)
    m.shift(pos(0, FAIXA3.faixas[2] - m[0].get_center()[1]))
    trilho = Line(pos(EIXO.x, 1.5), pos(EIXO.at(20), 1.5), color=GRID, stroke_width=1.5)
    return VGroup(FAIXA3.faixa_ponta(), trilho, m, EIXO.horas(.93, 2, 14))


# ---------------------------------------------------------------- chuva
CENTROS = (-4.36, 0, 4.36)
PASSO_COL = .47
PISO, TOPO, CEU = -2.5, -.1, 1.45
QUEDA = .55
TEMPO_CHUVA = 7.2


def coluna_x(m, ultima):
    return CENTROS[m] + (ultima - 3.5) * PASSO_COL


def armario(m):
    largura = 8 * PASSO_COL
    x0 = CENTROS[m] - largura / 2
    paredes = VGroup(*(Line(pos(x0 + k * PASSO_COL, PISO), pos(x0 + k * PASSO_COL, TOPO), color=OURO,
                            stroke_width=1.6, stroke_opacity=.75) for k in range(9)),
                     Line(pos(x0, PISO), pos(x0 + largura, PISO), color=OURO, stroke_width=2.5))
    pes = VGroup(*(chip(j, .26).move_to(pos(coluna_x(m, j), PISO - .22)) for j in range(8)))
    return VGroup(paredes, pes)


def vivos_por_maquina():
    return [[e for e in D["chuva"] if e[0] == m and e[5] and e[6] < 0] for m in range(3)]


def colunas():
    """Quadro que liga as duas cenas: rótulos restantes, uma coluna por máquina."""
    grupo = VGroup()
    for m, vivos in enumerate(vivos_por_maquina()):
        pilha = VGroup(*(Dot(pos(CENTROS[m] + (k % 9 - 4) * .18, PISO + .12 + (k // 9) * .18), radius=.065,
                             color=OURO) for k in range(len(vivos))))
        base = Line(pos(CENTROS[m] - .9, PISO), pos(CENTROS[m] + .9, PISO), color=OURO, stroke_width=3)
        nome = text(f"M{m + 1}", 26, bold=True).move_to(pos(CENTROS[m], PISO - .27))
        conta = text(f"{D['por_maquina'][m]['apos_fusao']} rótulos", 22, OURO, bold=True).move_to(
            pos(CENTROS[m], -.35))
        grupo.add(VGroup(pilha, base, nome, conta))
    return grupo


class Exato(CenaContinua):
    chapter, total = "MÉTODO EXATO", 2

    def rodape(self, valor):
        novo = left(text(valor, 17, MUTED), -6.55, -3.60)
        self.cabecalho[4].become(novo)

    RODAPE = "Instância didática · 8 tarefas · 3 máquinas · calculada com o modelo do projeto"


class ExatoEstados(Exato):
    number = 1

    def construct(self):
        self.abrir()
        self.pergunta()
        self.rotulos()
        self.poda()

    # ------------------------------------------------------------ pergunta
    def pergunta(self):
        fixos = self.base()
        q = Quadro(MEIO)
        axis, labels = plano_eixos()
        ponto = Dot(axis.c2p(MEIO["cmax"], MEIO["tec"]), radius=.11, color=GOLD)
        valor = valor_ponto(MEIO["cmax"], MEIO["tec"])
        self.add(*fixos, *q.tudo(), axis, labels, ponto, valor)
        self.beat("pergunta", "E se existir um plano melhor?")
        self.rodape(f"Instância didática · planos sorteados para ilustrar, seed {D['seed']} · "
                    f"só os com Cmax ≤ {D['parametros']['cmax_nuvem']} h e TEC ≤ $ {D['parametros']['tec_nuvem']}")
        self.wait(.3)
        passos = D["embaralho"]["passos"]
        rastros = VGroup()

        def rastro():
            d = Dot(ponto.get_center(), radius=.045, color=CINZA)
            rastros.add(d)
            self.add(d)
            self.bring_to_front(ponto)

        # Primeira mudança em câmera lenta: só a tarefa realocada salta, depois o resto reage.
        p = passos[0]
        movida = next(b["job"] for b in p["blocks"] if b["machine"] != q.maq[b["job"]])
        self.play(Indicate(q.barras[movida], color=INK, scale_factor=1.12), run_time=.35)
        rastro()
        self.bring_to_front(q.barras[movida])
        self.play(*q.ir(p), ponto.animate.move_to(axis.c2p(p["cmax"], p["tec"])), FadeOut(valor), run_time=1.3)
        # Cada tarefa multiplica as possibilidades por nove.
        opcoes = D["contagem"]["opcoes_por_tarefa"]
        conta = rotulo("1", 38, OURO, True).move_to(pos(5.0, -2.12))
        for k, p in enumerate(passos[1:9]):
            rastro()
            novo = rotulo(inteiro(opcoes ** (k + 1)), 38, OURO, True).move_to(pos(5.0, -2.12))
            brilho = q.barras[k][0].copy().set_fill(opacity=0).set_stroke(INK, 3)
            self.remove(conta)
            self.add(novo)
            self.play(*q.ir(p), ponto.animate.move_to(axis.c2p(p["cmax"], p["tec"])), FadeOut(brilho, scale=1.3),
                      run_time=(.75, .55, .42, .34, .28, .24, .2, .18)[k])
            conta = novo
        nuvem, astros = VGroup(), VGroup()
        for p in passos[9:]:
            nuvem.add(VGroup(*(EIXO.caixa(b["machine"], b["start"], b["end"], .6 + .4 * b["mode"] / 2,
                                          fill_color=CORES[b["job"]], fill_opacity=.17) for b in p["blocks"])))
            astros.add(Dot(axis.c2p(p["cmax"], p["tec"]), radius=.05, color=CINZA))
        grande = VGroup(rotulo(inteiro(D["contagem"]["total"]), 64, INK, True),
                        VGroup(text("só máquina e modo:", 26, OURO),
                               formula(rf"{opcoes}^{{{D['contagem']['tarefas']}}}", 1, .36, str(OURO.to_hex()))).arrange(RIGHT, buff=.16)
                        ).arrange(DOWN, buff=.25).move_to(pos(-1.2, -.02))
        painel = RoundedRectangle(width=grande.width + .7, height=grande.height + .5, corner_radius=.15, stroke_width=0,
                                  fill_color=FUNDO, fill_opacity=.86).move_to(grande)
        self.play(LaggedStart(*(FadeIn(g) for g in nuvem), lag_ratio=.12),
                  LaggedStart(*(FadeIn(a) for a in astros), lag_ratio=.12),
                  *(b.animate.set_opacity(.35) for b in q.barras.values()), run_time=1.5)
        self.play(FadeIn(painel), run_time=.2)
        self.bring_to_front(conta)
        self.play(ReplacementTransform(conta, grande[0]), FadeIn(grande[1], shift=UP * .1), run_time=.8)
        self.wait(.9)
        # A nuvem congela e condensa na faixa da M3.
        alvo = faixa_m3()
        y = 1.5
        self.play(FadeOut(painel), FadeOut(grande), FadeOut(astros), FadeOut(rastros), FadeOut(ponto),
                  FadeOut(axis), FadeOut(labels), FadeOut(self.tarifa), FadeOut(self.tarifa_rotulos), run_time=.5)
        resto = VGroup(nuvem, *q.tudo())
        self.play(resto.animate.stretch_to_fit_height(.02).move_to(pos(EIXO.at(10), y)).set_opacity(.5),
                  FadeOut(self.maquinas[:2]), FadeOut(self.trilhos[:2]),
                  self.maquinas[2].animate.move_to(alvo[2]), self.trilhos[2].animate.move_to(alvo[1]),
                  Transform(self.faixa, alvo[0]), ReplacementTransform(self.horas, alvo[3]), run_time=1.2)
        self.remove(*q.tudo(), self.maquinas, self.trilhos, self.faixa, self.maquinas[2], self.trilhos[2])
        self.remove(nuvem, resto)
        self.lane = alvo
        self.remove(alvo[3])
        self.add(alvo)
        self.hold()

    # ------------------------------------------------------------- rótulos
    def rotulos(self):
        self.rodape(self.RODAPE)
        self.beat("rotulos", "O que lembrar de um começo?")
        base = D["rotulo"]["base"]
        total = ValueTracker(0)
        fim = ValueTracker(0)
        nomes = VGroup(left(text("término", 20, MUTED), 3.75, 1.85), left(text("energia", 20, MUTED), 5.2, 1.85))
        n1 = always_redraw(lambda: left(rotulo(f"{round(fim.get_value())} h", 32, INK, True), 3.75, 1.42))
        n2 = always_redraw(lambda: left(rotulo(moeda(total.get_value()), 32, GOLD, True), 5.2, 1.42))
        self.play(FadeIn(nomes), FadeIn(n1), FadeIn(n2), run_time=.3)
        barras, preparos = [], []
        for b in base["blocks"]:
            viva = FAIXA3.bloco(b)
            prep = FAIXA3.setup(b)
            if b["setup"]:
                self.play(GrowFromEdge(prep, LEFT), run_time=.3)
                preparos.append(prep)
            self.play(FadeIn(viva, shift=DOWN * .7), fim.animate.set_value(b["end"]),
                      total.animate.set_value(total.get_value() + sum(b["costs"])), run_time=.8)
            barras.append(viva)
        # A história vira uma ficha.
        card = ficha(base).move_to(pos(-5.1, -1.35))
        voo = VGroup(*(m.copy() for m in (*preparos, *barras)))
        self.play(voo.animate.scale(.245).move_to(card[2], aligned_edge=LEFT).set_opacity(.9),
                  FadeIn(card, scale=1.6), run_time=1.1)
        self.remove(voo)
        jobs = sorted(b["job"] for b in base["blocks"])
        u = gaveta(-6.45, -3.75, -1.98, -.75)
        tag = etiqueta(jobs, base["blocks"][-1]["job"]).move_to(pos(-5.1, -2.33))
        self.play(Create(u), FadeIn(tag, shift=UP * .1), run_time=.7)
        self.play(tag[3].animate(rate_func=there_and_back).scale(1.5), Indicate(card[3], color=GOLD), run_time=.7)

        # Leque de modos para a próxima tarefa.
        job, inicio = D["rotulo"]["tarefa"], D["rotulo"]["inicio"]
        prep = FAIXA3.caixa(2, base["end"], inicio, .45, fill_color=MUTED, fill_opacity=.6)
        self.play(GrowFromEdge(prep, LEFT), run_time=.25)
        viva, cards, galhos = None, {}, {}
        for mode, y in ((0, -.98), (2, -2.68), (1, -1.83)):
            info = D["rotulo"]["modos"][mode]
            f = info["fichas"][0]
            nova = FAIXA3.tarefa(job, 2, inicio, inicio + info["duracao"], mode)
            c = ficha(f, .9).move_to(pos(-.9, y))
            galho = Line(card.get_right(), c.get_left(), color=OURO, stroke_width=2.5)
            nome = text(NOMES[mode], 18, MUTED).next_to(c, RIGHT, buff=.12)
            anims = [fim.animate.set_value(f["end"]), total.animate.set_value(f["energy"])]
            anims.append(FadeIn(nova, shift=DOWN * .5) if viva is None else Transform(viva, nova))
            self.play(*anims, run_time=.55)
            viva = nova if viva is None else viva
            self.play(Create(galho), FadeIn(c, target_position=viva, scale=.4), FadeIn(nome), run_time=.55)
            cards[mode], galhos[mode] = VGroup(c, nome), galho
        # Colina de custos: só interessa o próximo início mais barato.
        info = D["rotulo"]["modos"][1]
        dim = [cards[0], cards[2], galhos[0], galhos[2], card, u, tag]
        chao = -.34
        escala = .62 / max(v for _, v in info["custos"])
        for m in dim:
            m.save_state()
        self.play(*(m.animate.fade(.78) for m in dim), run_time=.35)
        colina = VGroup(*(Rectangle(width=.28, height=v * escala, stroke_width=0, fill_color=MUTED, fill_opacity=.55)
                          .move_to(pos(EIXO.at(s), chao), aligned_edge=DOWN) for s, v in info["custos"]))
        colina[0].set_fill(CORAL, .95)
        leg = left(text("custo se começar aqui", 17, MUTED), 3.1, chao + .2)
        self.play(LaggedStart(*(GrowFromEdge(b, DOWN) for b in colina), lag_ratio=.12), FadeIn(leg), run_time=.8)
        a, z = info["inicios"][0], info["inicios"][-1]
        s = ValueTracker(a)
        elastico = always_redraw(lambda: FAIXA3.caixa(2, a, max(a + .01, s.get_value()), .45, fill_color=GOLD,
                                                      fill_opacity=.22, stroke_color=GOLD, stroke_width=2))
        bola = Dot(colina[0].get_top() + UP * .08, radius=.08, color=GOLD)
        self.add(elastico)
        self.bring_to_front(viva)
        self.play(FadeIn(bola, scale=2), Indicate(viva, color=CORAL), run_time=.5)
        arco = ArcBetweenPoints(bola.get_center(), colina[-1].get_top() + UP * .08, angle=-1.1)
        ficha2 = info["fichas"][-1]
        dest = FAIXA3.tarefa(job, 2, z, z + info["duracao"], 1)
        self.play(s.animate.set_value(z), viva.animate(path_arc=-.5).move_to(dest),
                  UpdateFromAlphaFunc(bola, lambda m, t: m.move_to(arco.point_from_proportion(t))),
                  fim.animate.set_value(ficha2["end"]), total.animate.set_value(ficha2["energy"]), run_time=1.6)
        self.play(colina[-1].animate.set_fill(GREEN, 1), Indicate(viva, color=GREEN), run_time=.45)
        self.wait(.4)
        c = ficha(ficha2, .9).move_to(pos(3.1, -1.83))
        galho = Line(cards[1].get_right() + RIGHT * .05, c.get_left(), color=OURO, stroke_width=2.5)
        self.play(*(FadeOut(m) for m in (colina, leg, bola)), *(m.animate.restore() for m in dim),
                  Create(galho), FadeIn(c, target_position=viva, scale=.4),
                  run_time=.7)
        lema = text("término · energia", 26, OURO, bold=True).move_to(pos(4.9, -2.75))
        self.play(FadeIn(lema, shift=UP * .1), run_time=.4)
        sobra = VGroup(nomes, *barras, *preparos, prep, viva, u, tag, card, lema, galho, *galhos.values(), cards[0], cards[2],
                       cards[1][1])
        self.vencedora, self.saltou = cards[1][0], c
        self.sai = [sobra, n1, n2, elastico, c, self.lane]
        self.hold()

    # ---------------------------------------------------------------- poda
    def poda(self):
        self.beat("poda", "Dois começos, o mesmo lugar", *self.sai)
        duelo = D["duelo"]
        eixo = Eixo(x=-5.75, passo=.385, faixas=(1.35, .2, .2), altura=.52)
        linhas = {"vence": 0, "perde": 1}
        pal = VGroup(eixo.faixa_ponta(), *(Line(pos(eixo.x, y), pos(eixo.at(20), y), color=GRID, stroke_width=1.5)
                                           for y in eixo.faixas[:2]), eixo.horas(-.35, 2, 14))
        axis, labels = axes((10, 20, 2), (200, 500, 100), center=(5.0, .62), width=2.75, height=2.1,
                            x_label="término (h)", y_label="energia ($)", numbers=True)
        g = gaveta(-6.3, -.75, -2.65, -1.5)
        tag = etiqueta((0, 5, 6), 6).move_to(pos(-3.5, -2.98))
        perde = ficha(duelo["perde"], .9).move_to(pos(-2.1, -2.13))
        vence = self.vencedora

        def barra(lado, bloco):
            return eixo.bloco(dict(bloco, machine=linhas[lado]))

        def prep(lado, bloco):
            return eixo.setup(dict(bloco, machine=linhas[lado]))
        # A perdedora chega primeiro; a vencedora cai depois na mesma gaveta.
        self.play(Create(g), FadeIn(tag), FadeIn(pal), FadeIn(axis), FadeIn(labels), run_time=.6)
        self.play(FadeIn(perde, shift=DOWN * 1.1), run_time=.45)
        self.play(vence.animate(path_arc=.6).move_to(pos(-4.95, -2.13)), run_time=.8)
        self.play(Wiggle(perde, scale_value=1.04), Wiggle(vence, scale_value=1.04), run_time=.6)
        corpos = {}
        pontos = {}
        for lado, card in (("vence", vence), ("perde", perde)):
            blocos = duelo[lado]["blocks"]
            corpos[lado] = VGroup(*(prep(lado, b) for b in blocos), *(barra(lado, b) for b in blocos))
            pontos[lado] = Dot(axis.c2p(duelo[lado]["end"], duelo[lado]["energy"]), radius=.1,
                               color=OURO if lado == "vence" else INK)
        self.play(*(FadeIn(corpos[lado], target_position=card[2], scale=.3)
                    for lado, card in (("vence", vence), ("perde", perde))),
                  *(FadeIn(pontos[lado], target_position=card[3])
                    for lado, card in (("vence", vence), ("perde", perde))), run_time=1)
        dominio = Polygon(*(axis.c2p(*p) for p in ((duelo["vence"]["end"], duelo["vence"]["energy"]), (20, duelo["vence"]["energy"]),
                                                   (20, 500), (duelo["vence"]["end"], 500))),
                          stroke_width=0, fill_color=OURO, fill_opacity=.14)
        self.play(FadeIn(dominio), run_time=.35)
        # A mesma continuação, no mesmo instante.
        novos = {lado: duelo["continua"][lado]["blocks"][-1] for lado in linhas}
        inicio = novos["perde"]["start"]
        guia = DashedLine(pos(eixo.at(inicio), 1.8), pos(eixo.at(inicio), -.2), color=INK, stroke_width=2)
        setups = [prep(lado, novos[lado]) for lado in linhas]
        setups += [eixo.espera(dict(novos["vence"], machine=0))]
        quedas = {lado: barra(lado, novos[lado]) for lado in linhas}
        self.play(Create(guia), *(GrowFromEdge(m, LEFT) for m in setups), run_time=.45)
        fim = {lado: duelo["continua"][lado] for lado in linhas}
        self.play(*(FadeIn(b, shift=DOWN * .45) for b in quedas.values()),
                  *(pontos[lado].animate.move_to(axis.c2p(fim[lado]["end"], fim[lado]["energy"])) for lado in linhas),
                  FadeOut(dominio), run_time=1.1)
        numeros = VGroup(*(text(moeda(fim[lado]["energy"]), 20, OURO if lado == "vence" else INK, bold=True).next_to(
            quedas[lado], RIGHT, buff=.12) for lado in linhas))
        self.play(FadeIn(numeros), run_time=.35)
        self.wait(.4)

        # Descendentes da perdedora, que somem com ela.
        raiz = perde.get_right()
        nos, arvore = [], VGroup()
        for dy in (.38, 0, -.38):
            n1 = raiz + pos(.75, dy)
            arvore.add(Line(raiz, n1, color=OURO, stroke_width=2), Dot(n1, radius=.06, color=OURO))
            for dz in (.12, -.12):
                n2 = n1 + pos(.75, dz)
                arvore.add(Line(n1, n2, color=OURO, stroke_width=1.6), Dot(n2, radius=.045, color=OURO))
                for dw in (.05, -.05):
                    n3 = n2 + pos(.6, dw)
                    arvore.add(Line(n2, n3, color=OURO, stroke_width=1), Dot(n3, radius=.03, color=OURO))
        self.play(LaggedStart(*(FadeIn(m) for m in arvore), lag_ratio=.04), run_time=.7)
        fenda, metades = rachar(perde)
        self.play(Create(fenda), vence[1].animate.set_stroke(GREEN), run_time=.3)
        self.remove(perde)
        self.add(metades)
        self.bring_to_front(fenda)
        self.play(metades[0].animate.shift(pos(-.12, -.06)).rotate(.12), metades[1].animate.shift(pos(.14, -.06)).rotate(-.14),
                  FadeOut(fenda), arvore.animate.set_color(CINZA), corpos["perde"].animate.fade(.8), numeros[1].animate.set_color(CINZA),
                  quedas["perde"].animate.fade(.8), pontos["perde"].animate.set_color(CINZA), run_time=.5)
        self.play(LaggedStart(*(FadeOut(m, shift=DOWN * .25) for m in (metades[0], metades[1], *arvore)), lag_ratio=.02),
                  run_time=.8)
        self.wait(.25)
        velhos = [pal, axis, labels, g, tag, vence, *corpos.values(), *pontos.values(), guia, *setups, *quedas.values(), numeros]
        self.play(*(FadeOut(m) for m in velhos), run_time=.45)
        self.paredes()
        self.chuva()
        self.hold()

    def paredes(self):
        """Mesmo conjunto, última tarefa diferente: não há comparação."""
        dados = D["gavetas"]
        x = (-2.95, 2.95)
        cards, caixas, tags = [], VGroup(), VGroup()
        for k, f in enumerate(dados["fichas"]):
            caixas.add(gaveta(x[k] - 2.75, x[k] + 2.75, -1.75, -.15))
            tags.add(etiqueta(sorted(b["job"] for b in f["blocks"]), f["blocks"][-1]["job"]).move_to(pos(x[k], -2.15)))
            cards.append(ficha(f, 1.15).move_to(pos(x[k], -1.0)))
        muro = Rectangle(width=.4, height=1.75, stroke_width=0, fill_color=OURO, fill_opacity=.55).move_to(pos(0, -.95))
        self.play(FadeIn(caixas), FadeIn(tags), *(FadeIn(c, shift=DOWN * .4) for c in cards), run_time=.5)
        self.play(GrowFromEdge(muro, DOWN), run_time=.3)
        self.play(*(c.animate.move_to(pos(1.62 * (1 if k else -1), -1.0)) for k, c in enumerate(cards)),
                  run_time=.45, rate_func=lambda t: t * t)
        self.play(muro.animate(rate_func=there_and_back).set_fill(INK, .95),
                  *(c.animate.move_to(pos(x[k], -1.0)) for k, c in enumerate(cards)), run_time=.5)
        # O preparo seguinte depende da última tarefa: números de uma instância do conjunto, em minutos.
        self.rodape(f"Setups na M{dados['maquina'] + 1} da instância {dados['instancia'].removesuffix('.dat')}, em minutos · "
                    "fichas da instância didática")
        prox = dados["proxima"]
        linhas = VGroup()
        for k, (ult, custo) in enumerate(dados["ultimas"]):
            y = 1.0
            a = chip(ult, .5).move_to(pos(x[k] - 1.8, y))
            barra = Rectangle(width=.26 * custo, height=.24, stroke_width=0, fill_color=MUTED, fill_opacity=.75)
            barra.next_to(a, RIGHT, buff=.06)
            b = chip(prox, .5).next_to(barra, RIGHT, buff=.06)
            linhas.add(VGroup(a, barra, b, text(f"setup {custo}", 20, MUTED).next_to(barra, UP, buff=.18)))
        self.play(*(LaggedStart(FadeIn(g[0]), GrowFromEdge(g[1], LEFT), FadeIn(g[3]), FadeIn(g[2]), lag_ratio=.4)
                    for g in linhas), run_time=1.1)
        lema = text("mesma gaveta, mesma comparação", 25, OURO, bold=True).move_to(pos(0, -2.85))
        self.play(FadeIn(lema, shift=UP * .1), run_time=.3)
        self.wait(.7)
        self.play(*(FadeOut(m) for m in (caixas, tags, *cards, muro, linhas, lema)), run_time=.4)

    def chuva(self):
        passo = D["parametros"]["passo_amostragem"]
        total = D["stats"]["transitions"]
        self.rodape(f"Instância didática · chuva amostrada: 1 partícula = {passo} transições")
        armarios = VGroup(*(armario(m) for m in range(3)))
        nomes = VGroup(*(text(f"M{m + 1}", 20, MUTED, bold=True).move_to(pos(CENTROS[m], -3.08)) for m in range(3)))
        self.play(FadeIn(armarios), FadeIn(nomes), run_time=.4)
        eventos = D["chuva"]
        # Vagas reaproveitadas: um rótulo removido libera o lugar na gaveta.
        n = len(eventos)

        def instante(k):
            return (TEMPO_CHUVA - QUEDA - .5) * sqrt(k / total)
        ocupadas, agenda = {}, []
        for i, (m, _s, ultima, _e, _c, aceito, morre) in enumerate(eventos):
            t0 = instante(i * passo)
            vaga = None
            if aceito:
                fila = ocupadas.setdefault((m, ultima), [])
                vaga = next((v for v, livre in enumerate(fila) if livre <= t0), len(fila))
                fim = instante(morre) + QUEDA + .45 if morre >= 0 else 1e9
                if vaga == len(fila):
                    fila.append(fim)
                else:
                    fila[vaga] = fim
            agenda.append((t0, coluna_x(m, ultima), vaga, instante(morre) + QUEDA if morre >= 0 else None, CORES[ultima]))
        altura_vaga = min(.2, (TOPO - PISO - .2) / max(len(f) for f in ocupadas.values()))
        gotas = VGroup(*(Dot(pos(a[1], CEU), radius=.07, color=a[4], fill_opacity=0) for a in agenda))

        def cair(grupo, alpha):
            t = alpha * TEMPO_CHUVA
            for gota, (t0, x, vaga, morte, cor) in zip(grupo, agenda):
                u = (t - t0) / QUEDA
                if u < 0 or t - t0 > 2 and gota.get_fill_opacity() == 0:
                    continue
                alvo = TOPO + .08 if vaga is None else PISO + .12 + vaga * altura_vaga
                if u <= 1:
                    gota.move_to(pos(x, CEU + (alvo - CEU) * u * u)).set_fill(cor, 1)
                elif vaga is None:
                    v = min(1, (u - 1) / .8)
                    gota.move_to(pos(x + .12 * v, alvo + .28 * v - .3 * v * v)).set_fill(CINZA, 1 - v)
                elif morte is not None and t > morte:
                    gota.set_fill(CINZA, max(0, 1 - (t - morte) / .45)).move_to(pos(x, alvo))
                else:
                    gota.move_to(pos(x, alvo)).set_fill(cor, 1)
        linhas = D["contadores"]
        campos = (("transições", INK), ("recusas", CINZA), ("inserções", OURO), ("removidos depois", CORAL))
        xs = (-6.35, -2.9, .2, 3.3)
        rotulos = VGroup(*(left(text(nome, 18, MUTED), x, 2.2) for (nome, _), x in zip(campos, xs)))
        t = ValueTracker(0)

        def lido():
            vistas = total * min(1, max(0, t.get_value() - QUEDA) / (TEMPO_CHUVA - QUEDA - .5)) ** 2
            return max((r for r in linhas if r[0] <= vistas + 1e-6), default=[0, 0, 0, 0])
        valores = [always_redraw(lambda i=i, x=x, cor=cor: left(rotulo(inteiro(lido()[i]), 34, cor, True), x, 1.82))
                   for i, ((_, cor), x) in enumerate(zip(campos, xs))]
        self.add(gotas, *valores)
        self.play(FadeIn(rotulos), run_time=.3)
        self.play(UpdateFromAlphaFunc(gotas, cair), t.animate.set_value(TEMPO_CHUVA), run_time=TEMPO_CHUVA, rate_func=linear)
        self.wait(.7)
        # Fusão ao fim de cada máquina: some a última tarefa, caem as paredes.
        final = colunas()
        vivas = [VGroup(*(g for g, e in zip(gotas, eventos) if e[0] == m and e[5] and e[6] < 0)) for m in range(3)]
        mortas = [g for g, e in zip(gotas, eventos) if not (e[5] and e[6] < 0)]
        self.remove(gotas, *mortas)
        self.add(*vivas)
        self.play(*(FadeOut(a) for a in armarios), FadeOut(nomes),
                  *(v.animate.set_color(OURO) for v in vivas), run_time=.5)
        self.play(*(Transform(v, f[0]) for v, f in zip(vivas, final)),
                  *(FadeIn(f[k]) for f in final for k in (1, 2)), run_time=.9)
        self.remove(*vivas)
        self.add(final)
        self.remove(*(f[3] for f in final))
        self.play(*(FadeIn(f[3]) for f in final), FadeOut(rotulos), *(FadeOut(v) for v in valores), run_time=.4)
        self.rodape(self.RODAPE)
        assert n == len(gotas)


# ===================================================================== cena 2
PAINEL_X = (-4.36, 0, 4.36)
CURVA_MAX = 600
BANDEJA_Y = -.95


def painel_curva(m):
    return axes((0, 24, 6), (0, CURVA_MAX, 200), center=(PAINEL_X[m], 1.0), width=3.1, height=1.5,
                x_label="término", y_label="energia")


class ExatoEscada(Exato):
    number = 2

    def construct(self):
        self.abrir("Dois começos, o mesmo lugar")
        self.col = colunas()
        self.add(self.col)
        self.particao()
        self.epsilon()
        self.limite()

    def curva(self, axis, pontos, eps, cor=OURO):
        """Rótulos do subconjunto: cinza depois do teto, aceso o melhor antes dele."""
        g = VGroup()
        if len(pontos) > 1:
            g.add(staircase(axis, pontos, GRID, 2))
        melhor = max((p for p in pontos if p[0] <= eps), default=None)
        for p in pontos:
            d = Dot(axis.c2p(*p), radius=.06, color=cor if p[0] <= eps else CINZA)
            if p == melhor:
                d.scale(1.7)
            g.add(d)
        return g if len(g) else VGroup(Dot(axis.c2p(0, 0), radius=.001, fill_opacity=0))

    # ------------------------------------------------------------ partição
    def particao(self):
        self.beat("particao", "Quem fica com cada tarefa?")
        dados = D["particao"]
        eps = dados["epsilon"]
        for t in dados["tentativas"]:
            for m in t["maquinas"]:
                assert all(p[1] <= CURVA_MAX and p[0] <= 24 for p in m["curva"])
        paineis = [painel_curva(m) for m in range(3)]
        for axis, labels in paineis:
            labels[0].scale(.8)
            labels[1].scale(.8)
        bandejas = VGroup(*(gaveta(x - 1.75, x + 1.75, BANDEJA_Y - .32, BANDEJA_Y + .22) for x in PAINEL_X))
        nomes = VGroup(*(text(f"M{m + 1}", 22, MUTED, bold=True).move_to(pos(PAINEL_X[m] + 1.45, 1.85))
                         for m in range(3)))
        tetos = VGroup(*(DashedLine(a.c2p(eps, 0), a.c2p(eps, CURVA_MAX), color=OURO, stroke_width=2.5)
                         for a, _ in paineis))
        marca = VGroup(*(text(f"{eps} h", 16, OURO).next_to(t, UP, buff=.05) for t in tetos))

        def lugar(tent):
            destino = {}
            for m, x in enumerate(PAINEL_X):
                jobs = tent["maquinas"][m]["jobs"]
                for k, j in enumerate(jobs):
                    destino[j] = pos(x + (k - (len(jobs) - 1) / 2) * .42, BANDEJA_Y - .07)
            return destino
        tentativas = dados["tentativas"]
        chips = {j: chip(j, .38).move_to(p) for j, p in lugar(tentativas[0]).items()}

        def custos(tent):
            g = VGroup()
            for m, x in enumerate(PAINEL_X):
                v = tent["maquinas"][m]["energy"]
                g.add(text("não cabe" if v is None else moeda(v), 24, CORAL if v is None else INK, bold=True).move_to(
                    pos(x, BANDEJA_Y - .62)))
            return g

        def soma(tent, cor=INK):
            v = tent["total"]
            return text("Σ  —" if v is None else f"Σ  {moeda(v)}", 34, CINZA if v is None else cor, bold=True).move_to(
                pos(0, -2.2))
        curvas = [self.curva(a, tentativas[0]["maquinas"][m]["curva"], eps) for m, (a, _) in enumerate(paineis)]
        self.play(*(FadeOut(c[k]) for c in self.col for k in (1, 2, 3)),
                  *(FadeIn(m) for a, l in paineis for m in (a, l)), FadeIn(nomes),
                  *(c[0].animate.scale(.15).move_to(a.c2p(0, 0)).set_opacity(0) for c, (a, _) in zip(self.col, paineis)),
                  *(FadeIn(cv) for cv in curvas), run_time=.9)
        self.remove(self.col)
        self.play(*(Create(t) for t in tetos), FadeIn(marca), Create(bandejas),
                  LaggedStart(*(FadeIn(c, shift=DOWN * .4) for c in chips.values()), lag_ratio=.06), run_time=.9)
        # Régua com os 256 conjuntos examinados para a M3.
        exames = dados["exames"]
        x0, dx = -5.6, 11.2 / len(exames)
        regua = VGroup(*(Line(pos(x0 + k * dx, -2.98), pos(x0 + k * dx, -2.98 + (.10 if v is None else .26)),
                              color=GRID if v is None else OURO, stroke_width=1.6 if v is None else 4)
                         for k, v in enumerate(exames)))
        rlabel = text(f"{len(exames)} conjuntos para a M3", 16, MUTED).move_to(pos(0, -3.18))
        ordem = [1, None, dados["melhoras"][0]["ordem"], dados["melhoras"][1]["ordem"]]
        c_atual, s_atual = custos(tentativas[0]), soma(tentativas[0])
        self.play(FadeIn(c_atual), FadeIn(s_atual), FadeIn(regua), FadeIn(rlabel), run_time=.4)
        cursor = Dot(pos(x0, -2.85), radius=.06, color=INK)
        self.add(cursor)
        self.wait(.25)
        for k, tent in enumerate(tentativas[1:], 1):
            destino = lugar(tent)
            movidos = [j for j in chips if np.linalg.norm(chips[j].get_center() - destino[j]) > 1e-3]
            novas = [self.curva(a, tent["maquinas"][m]["curva"], eps) for m, (a, _) in enumerate(paineis)]
            c_novo, s_novo = custos(tent), soma(tent, GREEN if k == len(tentativas) - 1 else INK)
            self.play(FadeOut(c_atual), FadeOut(s_atual), *(FadeOut(c) for c in curvas), run_time=.2)
            anims = [chips[j].animate(path_arc=-1.1).move_to(destino[j]) for j in movidos]
            if ordem[k]:
                anims.append(cursor.animate.move_to(pos(x0 + (ordem[k] - 1) * dx, -2.6)))
            self.play(*anims, run_time=.9)
            self.play(*(FadeIn(c) for c in novas), FadeIn(c_novo), FadeIn(s_novo), run_time=.35)
            self.wait(.45)
            curvas, c_atual, s_atual = novas, c_novo, s_novo
        self.play(cursor.animate.move_to(pos(x0 + (len(exames) - 1) * dx, -2.85)), run_time=.4)
        regra = text("min Σ energia · término ≤ ε", 22, OURO).move_to(pos(4.4, -2.2))
        self.play(*(b.animate.set_stroke(GREEN) for b in bandejas), FadeIn(regra),
                  Indicate(s_atual, color=GREEN, scale_factor=1.12), run_time=.6)
        self.wait(.3)

        # O Gantt se reconstrói de trás para frente, seguindo os ponteiros.
        p = VARREDURA[0]
        maquinas = VGroup(*(maquina(i) for i in range(3)))
        trilhos, horas, faixa = LARGO.trilhos(), LARGO.horas(-1.72, 2, 14), LARGO.faixa_ponta()
        axis, labels = plano_eixos()
        self.play(*(FadeOut(m) for m in (*curvas, *(x for par in paineis for x in par), tetos, marca, nomes, bandejas,
                                         c_atual, regua, rlabel, cursor, regra)),
                  *(chips[j].animate.move_to(pos(-4.2 + .55 * k, -2.55)) for k, j in enumerate(sorted(chips))),
                  s_atual.animate.move_to(pos(5.0, -2.12)), run_time=.6)
        self.play(*(FadeIn(m) for m in (faixa, trilhos, maquinas, horas)), run_time=.4)
        for c in chips.values():
            self.bring_to_front(c)
        q = Quadro(p, LARGO)
        por_maquina = [sorted((b for b in p["blocks"] if b["machine"] == m), key=lambda b: -b["start"]) for m in range(3)]
        for onda in range(max(map(len, por_maquina))):
            atuais = [(seq[onda], seq[onda - 1] if onda else None) for seq in por_maquina if len(seq) > onda]
            setas = VGroup(*(ArcBetweenPoints(q.barras[d["job"]].get_top(), LARGO.bloco(b).get_top(), angle=.9,
                                              color=OURO, stroke_width=3) for b, d in atuais if d))
            if len(setas):
                self.play(Create(setas), run_time=.2)
            self.play(*(ReplacementTransform(chips[b["job"]], q.barras[b["job"]], path_arc=.4) for b, _ in atuais),
                      *(FadeIn(q.setups[d["job"]]) for b, d in atuais if d), run_time=.5)
            if len(setas):
                self.play(FadeOut(setas), run_time=.12)
        for m in q.tudo():
            self.add(m)
        for b in q.barras.values():
            self.bring_to_front(b)
        ponto = Dot(axis.c2p(p["cmax"], p["tec"]), radius=.1, color=GOLD)
        self.play(FadeIn(axis), FadeIn(labels), ReplacementTransform(s_atual, ponto), run_time=.6)
        self.q, self.axis, self.labels, self.ponto = q, axis, labels, ponto
        self.fabrica = [faixa, trilhos, maquinas, horas]
        self.e = ValueTracker(eps)
        self.parede(OURO)
        self.play(*(FadeIn(m, shift=UP * .2) for m in self.muros), run_time=.5)
        self.hold()

    def parede(self, cor):
        e, axis = self.e, self.axis

        def muro_gantt():
            x = LARGO.at(e.get_value())
            return VGroup(Rectangle(width=.34, height=3.2, stroke_width=0, fill_color=OURO, fill_opacity=.13),
                          Rectangle(width=.10, height=3.2, stroke_width=0, fill_color=OURO, fill_opacity=.6)
                          ).move_to(pos(x, .05))

        def muro_plano():
            x = axis.c2p(e.get_value(), 400)[0]
            y0, y1 = axis.c2p(10, 400)[1], axis.c2p(10, 900)[1]
            return VGroup(Rectangle(width=.2, height=y1 - y0, stroke_width=0, fill_color=OURO, fill_opacity=.13),
                          Rectangle(width=.05, height=y1 - y0, stroke_width=0, fill_color=OURO, fill_opacity=.7)
                          ).move_to(pos(x, (y0 + y1) / 2))

        def etiqueta_eps():
            return rotulo(f"ε = {int(e.get_value() + 1e-6)} h", 24, OURO, True).move_to(
                pos(min(LARGO.at(e.get_value()), 2.5), 2.02))
        self.muros = [always_redraw(muro_gantt), always_redraw(muro_plano), always_redraw(etiqueta_eps)]

    # ------------------------------------------------------------- epsilon
    def epsilon(self):
        self.beat("epsilon", "E se permitirmos uma hora a mais?")
        # O hold retira os ValueTracker; eles voltam com a próxima animação.
        axis, q = self.axis, self.q
        valor = valor_ponto(*FRENTE[0])
        intervalo = text("ε = 12 … 24 h", 22, OURO).move_to(pos(-1.2, -2.45))
        fixo = Dot(self.ponto.get_center(), radius=.065, color=GOLD)
        self.play(FadeIn(valor), FadeIn(intervalo), Indicate(self.ponto, color=INK), run_time=.5)
        self.add(fixo)
        degraus, marcos, ant = VGroup(), [fixo], VARREDURA[0]
        for k, p in enumerate(VARREDURA[1:]):
            lento = 1.0 if k < 2 else .6
            self.play(self.e.animate.set_value(p["epsilon"]), run_time=.55 * lento, rate_func=smooth)
            if not p["novo"]:
                apagada = Rectangle(width=.4, height=3.2, stroke_width=0, fill_color=CINZA, fill_opacity=.85).move_to(
                    pos(LARGO.at(p["epsilon"]), .05))
                x = axis.c2p(p["epsilon"], 400)[0]
                apagada2 = Rectangle(width=.16, height=2.7, stroke_width=0, fill_color=CINZA, fill_opacity=.85).move_to(
                    pos(x, .35))
                self.play(FadeIn(apagada, rate_func=there_and_back), FadeIn(apagada2, rate_func=there_and_back), run_time=.45)
                self.remove(apagada, apagada2)
                continue
            novo_valor = valor_ponto(p["cmax"], p["tec"])
            self.remove(valor)
            self.play(*q.ir(p), self.ponto.animate.move_to(axis.c2p(p["cmax"], p["tec"])), FadeIn(novo_valor),
                      run_time=1.15 * lento)
            valor = novo_valor
            a, c, b = axis.c2p(ant["cmax"], ant["tec"]), axis.c2p(p["cmax"], ant["tec"]), axis.c2p(p["cmax"], p["tec"])
            degrau = VMobject(stroke_color=OURO, stroke_width=3.5).set_points_as_corners([a, c, b])
            onda = Circle(radius=.06, color=OURO, stroke_width=3).move_to(b)
            marco = Dot(b, radius=.065, color=GOLD)
            self.add(marco)
            self.play(Create(degrau), onda.animate.scale(6).set_stroke(opacity=0), run_time=.4 if k > 1 else .55)
            self.remove(onda)
            marcos.append(marco)
            degraus.add(degrau)
            ant = p
        assert len(marcos) == len(FRENTE)
        self.remove(*degraus)
        escada = staircase(axis, FRENTE, GOLD, 4)
        self.add(escada)
        self.bring_to_front(*marcos, self.ponto)
        self.play(FadeOut(VGroup(*(m.copy().clear_updaters() for m in self.muros[:2]))),
                  FadeOut(self.muros[2]), FadeOut(intervalo),
                  LaggedStart(*(Indicate(m, color=INK, scale_factor=2) for m in marcos), lag_ratio=.12),
                  escada.animate(rate_func=there_and_back).set_stroke(INK, 7), run_time=1.1)
        self.remove(*self.muros)
        for m in self.muros:
            self.remove(m)
        self.escada, self.marcos, self.valor = escada, marcos, valor
        self.hold()

    # -------------------------------------------------------------- limite
    def limite(self):
        self.beat("limite", "Até onde isso vai?")
        self.rodape("Fronteiras completas: data/baselines/*_custom_exact_dp.json · max_jobs = 13 na campanha")
        x0, x1, y0, y1 = -6.85, 6.85, -3.22, 2.4
        pares = D["conjuntos"]
        ultimo = pares[-1][0]
        tela = VGroup()

        def larg(n):
            return (x1 - x0) * 2 ** (n - ultimo)
        conta = None
        for n, total in pares:
            w = larg(n)
            bloco = Rectangle(width=w, height=y1 - y0, stroke_color=OURO, stroke_width=1.2, fill_color="#3a3115",
                              fill_opacity=1).move_to(pos(x0 + w / 2, (y0 + y1) / 2))
            fios = VGroup(*(Line(pos(x0 + w * f, y0), pos(x0 + w * f, y1), color=OURO, stroke_width=.8, stroke_opacity=.35)
                            for f in np.linspace(.5, 1, 9)[:-1]))
            fios.add(*(Line(pos(x0 + (w / 2 if len(tela) else 0), y), pos(x0 + w, y), color=OURO, stroke_width=.8,
                            stroke_opacity=.35) for y in np.linspace(y0, y1, 15)[1:-1]))
            peca = VGroup(bloco, fios)
            nova = VGroup(formula(rf"2^{{{n}}}", 2, .62, INK), text(f"= {inteiro(total)} conjuntos", 34, INK, bold=True)
                          ).arrange(RIGHT, buff=.2).move_to(pos(-1.0, -2.62))
            fundo = RoundedRectangle(width=nova.width + .5, height=nova.height + .4, corner_radius=.12, stroke_width=0,
                                     fill_color=FUNDO, fill_opacity=.85).move_to(nova)
            nova = VGroup(fundo, nova)
            if conta is not None:
                self.remove(conta)
            peca.save_state()
            peca.stretch(.5 if len(tela) else .05, 0, about_point=pos(x0, 0))
            self.add(peca, nova)
            self.play(peca.animate.restore(), run_time=.42 if n < ultimo else .6)
            tela.add(peca)
            conta = nova
        self.play(conta.animate.scale(1.35).move_to(pos(0, .7)), run_time=.45)
        base = D["baselines"]
        selos = VGroup()
        for k, b in enumerate(base):
            c = pos(-5.2 + 1.3 * k, -2.1)
            anel = VGroup(Circle(radius=.42, color=GOLD, stroke_width=4, fill_color=FUNDO, fill_opacity=1),
                          Circle(radius=.34, color=GOLD, stroke_width=1.2)).move_to(c)
            selos.add(VGroup(anel, text(str(b["n"]), 25, GOLD, bold=True).move_to(c),
                             text(f"{b['pontos']} pontos", 16, INK, bold=True).move_to(c + pos(0, -.62))))
        lema = text(f"certificado até {base[-1]['n']} tarefas", 34, GOLD, bold=True).move_to(pos(0, -1.1))
        self.play(LaggedStart(*(FadeIn(s, scale=1.8) for s in selos), lag_ratio=.15), FadeIn(lema), run_time=1.3)
        self.wait(1.1)
        # Retorno ao quadro-base, com a escada dourada.
        p = VARREDURA[-1]
        q = self.q
        horas, trilhos, faixa = EIXO.horas(-1.72), EIXO.trilhos(), EIXO.faixa_ponta()
        linha, rotulos = curva_tarifa()
        velha_faixa, velhos_trilhos, _maquinas, velhas_horas = self.fabrica
        for antigo, novo in ((velha_faixa, faixa), (velhos_trilhos, trilhos), (velhas_horas, horas)):
            antigo.become(novo)
        for b in p["blocks"]:
            j = b["job"]
            for antigo, novo in ((q.barras[j], EIXO.bloco(b)), (q.setups[j], EIXO.setup(b)), (q.esperas[j], EIXO.espera(b))):
                antigo.become(novo)
        # Entram sob a parede, que ainda cobre tudo.
        self.add(linha, rotulos)
        self.bring_to_front(tela, lema, selos)
        self.remove(conta)
        self.play(FadeOut(selos), FadeOut(lema), run_time=.3)
        self.play(tela.animate.stretch_to_fit_width(.02).move_to(pos(x1, (y0 + y1) / 2)), run_time=.8)
        self.remove(tela)
        self.rodape(self.RODAPE)
        self.play(Indicate(self.ponto, color=INK), run_time=.5)
        self.hold()
