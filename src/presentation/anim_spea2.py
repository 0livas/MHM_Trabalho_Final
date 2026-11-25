"""SPEA2 incremental: a arena de influência. Todos os números vêm de data/trace_spea2.json."""

from math import sqrt

from manim import (
    Circle, Create, DashedLine, Dot, FadeIn, FadeOut, Flash, GrowArrow, GrowFromEdge, Indicate, LaggedStart,
    Line, Polygon, Rectangle, ReplacementTransform, RoundedRectangle, Transform, VGroup, ValueTracker, Arrow,
    always_redraw, Circumscribe, linear, rush_into, smooth, there_and_back, DOWN, LEFT, UP,
)
import numpy as np

from fabrica import CORES, DADOS, EIXO, FAIXAS, CenaContinua, Eixo, plano, rotulo
from visual import (
    COLORS, CORAL, CYAN, FUNDO, GOLD, GREEN, GRID, HERE, INK, MUTED, axes, dots, left, pos, pt, read_json,
    staircase, text,
)

T = read_json(HERE / "data" / "trace_spea2.json")
COR = COLORS["spea2"]
DEMO, CAMPANHA = T["demonstracao"], T["campanha"]
INI = {l["id"]: l for l in T["inicial"]["linhas"]}
PRI = {l["id"]: l for l in T["primeira"]["linhas"]}
TRU = {l["id"]: l for l in T["truncamento"]["linhas"]}
PONTOS = {i: tuple(l["ponto"]) for i, l in INI.items()}
PAIS = tuple(d["vence"] for d in T["primeira"]["duelos"])
FILHO = T["primeira"]["filho"]
EXATA = [(p["cmax"], p["tec"]) for p in DADOS["front"]]
FRENTE = [(p["cmax"], p["tec"]) for p in T["frente"]]
FLUTUAM = tuple(T["inicial"]["frente"])
PESADO = 10         # plano usado na câmera lenta do peso
NOMES = dict(modo="modo", espera="espera", insercao="inserção", troca="troca", realocacao="realocação")
ORDEM = list(T["mutacoes"])
FACE = {nome: i + 1 for i, nome in enumerate(("modo", "espera", "insercao", "troca", "realocacao"))}
XR, YR = (12, 17, 1), (800, 1600, 100)
LARGA = ((10, 26, 2), (400, 1600, 200))
PERTO = ((10, 26, 2), (400, 900, 100))
PERTO_BASE = ((10, 26, 4), (400, 900, 100))
assert all(XR[0] <= x <= XR[1] and YR[0] <= y <= YR[1] for x, y in (*PONTOS.values(), tuple(PRI[FILHO]["ponto"])))


def moeda(v):
    return f"$ {pt(v, 1)}"


def par(p):
    return f"{p[0]} h · {moeda(p[1])}"


def grande(xr=XR, yr=YR):
    return axes(xr, yr, center=(-2.55, -.30), width=7.0, height=4.15, x_label="Cmax (h)", y_label="TEC ($)", numbers=True)


def pequeno(xr, yr):
    return axes(xr, yr, center=(5.02, .35), width=2.75, height=2.7, x_label="Cmax (h)", y_label="TEC ($)", numbers=True)


def gantt(p, eixo, textos=True):
    """Dicionários job → (preparo, espera, tarefa)."""
    out = {}
    for b in p["blocks"]:
        tarefa = eixo.bloco(b)
        if not textos:
            tarefa = VGroup(tarefa[0])
        out[b["job"]] = VGroup(eixo.setup(b), eixo.espera(b), tarefa)
    return out


def grupo(g):
    return VGroup(*(g[j][0] for j in g), *(g[j][1] for j in g), *(g[j][2] for j in g))


def mini(p, centro, passo=.055):
    eixo = Eixo(x=centro[0] - 8 * passo, passo=passo, faixas=tuple(centro[1] + d for d in (.17, 0, -.17)), altura=.1)
    return VGroup(*(eixo.bloco(b)[0] for b in p["blocks"]))


class Plateia(CenaContinua):
    total = 3

    def abrir(self, titulo=None):
        super().abrir(titulo)
        self.cabecalho[4].become(left(text(
            f"Demonstração na instância didática · P = {DEMO['population_size']}, cruzamento {pt(DEMO['crossover_probability'], 1)}, "
            f"mutação {pt(DEMO['mutation_probability'], 1)} · seed {T['seed']}", 17, MUTED, width=11.8), -6.55, -3.60))


def ponto_dot(axis, p, color=COR, radius=.078):
    return Dot(axis.c2p(*p), radius=radius, color=color)


def pulsa(m, fator=1.14):
    return m.animate(rate_func=there_and_back).scale(fator)


def painel_eixo():
    return Eixo(x=2.55, passo=3.9 / 18, faixas=(.95, .25, -.45), altura=.40, total=18)


def quadro_duelo():
    """Fim da arena e começo dos operadores: só os dois pais, acesos."""
    axis, labels = grande()
    bolas = {i: ponto_dot(axis, p, COR if i in PAIS else MUTED).set_opacity(1 if i in PAIS else .25)
             for i, p in PONTOS.items()}
    cartas = VGroup()
    for k, d in enumerate(T["primeira"]["duelos"]):
        perde = d["a"] if d["vence"] == d["b"] else d["b"]
        F = {d["a"]: d["Fa"], d["b"]: d["Fb"]}
        y = .95 - 1.75 * k
        caixa = RoundedRectangle(width=3.9, height=1.35, corner_radius=.12, stroke_color=GRID, stroke_width=2).move_to(pos(4.6, y))
        cartas.add(VGroup(caixa, Dot(pos(3.1, y + .12), radius=.16, color=COR), rotulo("AB"[k], 22, FUNDO, True).move_to(pos(3.1, y + .12)),
                          rotulo(pt(F[d["vence"]], 2), 30, COR, True).move_to(pos(3.95, y + .12)),
                          rotulo("<", 26, MUTED).move_to(pos(4.65, y + .12)),
                          rotulo(pt(F[perde], 2), 26, MUTED).move_to(pos(5.35, y + .12)),
                          Dot(pos(6.1, y + .12), radius=.1, color=GRID),
                          rotulo(par(PONTOS[d["vence"]]), 17, MUTED).move_to(pos(3.75, y - .42))))
    titulo = rotulo("aptidão: menor vence", 19, MUTED).move_to(pos(4.6, 1.98))
    return axis, labels, bolas, cartas, titulo


class Spea2Arena(Plateia):
    chapter, number = "SPEA2 INCREMENTAL", 1

    def construct(self):
        self.abrir()
        itens = self.base()
        p = plano(15)
        g = gantt(p, EIXO)
        pequeno_axis, pequeno_labels = pequeno((10, 22, 2), (400, 900, 100))
        marco = Dot(pequeno_axis.c2p(p["cmax"], p["tec"]), radius=.11, color=GOLD)
        self.add(*itens, grupo(g), pequeno_axis, pequeno_labels, marco)

        # ---------------------------------------------------------------- população
        self.beat("populacao", "Como comparar planos que ganham em coisas diferentes?")
        self.play(*(Transform(x, Dot(marco.get_center(), radius=.02, color=GOLD, fill_opacity=0)) for v in g.values() for x in v),
                  *(FadeOut(x) for x in itens), run_time=.9, rate_func=rush_into)
        self.remove(*(x for v in g.values() for x in v))
        axis, labels = grande()
        self.play(ReplacementTransform(pequeno_axis, axis), FadeOut(pequeno_labels), FadeOut(marco, scale=2), FadeIn(labels),
                  run_time=.8)

        eixo = painel_eixo()
        molde = VGroup(eixo.faixa_ponta(), eixo.trilhos(), *(rotulo(f"M{i + 1}", 16, MUTED).move_to(
            pos(2.25, eixo.faixas[i])) for i in range(3))).set_z_index(-1)
        # Uma construção real do LPT aleatório: fila por duração, janela, menor término.
        lpt = T["lpt"]
        nascente = T["planos"][str(lpt["id"])]
        blocos = {b["job"]: b for b in nascente["blocks"]}
        fila = lpt["passos"][0]["fila"]
        ficha = {}
        for k, j in enumerate(fila):
            w = .17 * lpt["menor_duracao"][j]
            ficha[j] = VGroup(Rectangle(width=.42, height=w, stroke_width=0, fill_color=CORES[j], fill_opacity=1),
                              rotulo(f"T{j + 1}", 14, FUNDO, True)).move_to(pos(2.75 + .49 * k, 1.62), aligned_edge=DOWN)
        self.play(FadeIn(molde), LaggedStart(*(FadeIn(f, shift=pos(0, -.2)) for f in ficha.values()), lag_ratio=.06), run_time=.6)

        def janela(passo):
            alvo = VGroup(*(ficha[j] for j in passo["fila"][:passo["janela"]]))
            return RoundedRectangle(width=alvo.width + .1, height=.82, corner_radius=.08, stroke_color=COR, stroke_width=2.5).move_to(
                pos(alvo.get_center()[0], 1.96))
        moldura = janela(lpt["passos"][0])
        self.play(Create(moldura), run_time=.35)
        montado = VGroup()
        for k, passo in enumerate(lpt["passos"]):
            b = blocos[passo["job"]]
            assert b["end"] == passo["end"] and b["machine"] == passo["machine"]
            if k:
                moldura.become(janela(passo))
            alvo, prep = eixo.bloco(b), eixo.setup(b)
            self.add(prep)
            resta = [j for j in passo["fila"] if j != passo["job"]]
            self.play(ReplacementTransform(ficha[passo["job"]], alvo, path_arc=.5), FadeIn(prep),
                      *(ficha[j].animate.set_x(2.75 + .49 * q) for q, j in enumerate(resta)),
                      run_time=.75 if k == 0 else .5 if k == 1 else .26)
            montado.add(prep, alvo)
        self.play(FadeOut(moldura), run_time=.2)
        bolas = {lpt["id"]: ponto_dot(axis, PONTOS[lpt["id"]])}
        self.play(ReplacementTransform(montado, bolas[lpt["id"]], path_arc=.4), run_time=.8)
        outros = [i for i in PONTOS if i != lpt["id"]]
        for i in outros:
            bolas[i] = ponto_dot(axis, PONTOS[i])
        pistas = {i: mini(T["planos"][str(i)], (3.05 + 1.0 * (k % 4), 1.9 - .72 * (k // 4)), .05) for k, i in enumerate(outros)}
        self.play(FadeOut(molde), LaggedStart(*(FadeIn(pistas[i], shift=pos(0, -.3)) for i in outros), lag_ratio=.07), run_time=.9)
        self.play(LaggedStart(*(ReplacementTransform(pistas[i], bolas[i], path_arc=.7) for i in outros), lag_ratio=.12), run_time=2.0)
        conta = left(rotulo(f"{len(PONTOS)} planos", 34, COR, True), 2.55, 2.0)
        self.play(FadeIn(conta, shift=pos(0, .1)), run_time=.3)
        for i in (8, 0):
            foco = Circle(radius=.18, color=INK, stroke_width=2.5).move_to(bolas[i])
            q = T["planos"][str(i)]
            aberto = grupo(gantt(q, eixo))
            nome = left(rotulo(par(PONTOS[i]), 24, INK, True), 2.55, -1.15)
            origem = bolas[i].copy()
            self.play(Create(foco), FadeIn(molde), ReplacementTransform(origem, aberto), FadeIn(nome), run_time=.7)
            self.wait(.55)
            self.play(Transform(aberto, bolas[i].copy()), FadeOut(foco), FadeOut(nome), FadeOut(molde), run_time=.5)
            self.remove(aberto)
        self.hold()

        # ---------------------------------------------------------------- força
        self.beat("forca", "Quem vence quem?", conta)
        centro = {i: bolas[i].get_center() for i in bolas}

        def seta(a, b, opac=.9, largura=2.2):
            return Arrow(centro[a], centro[b], buff=.1, stroke_width=largura, tip_length=.12, max_tip_length_to_length_ratio=.35,
                         max_stroke_width_to_length_ratio=40, color=COR).set_opacity(opac)
        setas = {}
        for ordem, i in enumerate(FLUTUAM):
            n = ValueTracker(0)
            contador = always_redraw(lambda i=i, n=n: rotulo(f"S = {round(n.get_value())}", 26, COR, True).next_to(
                centro[i], DOWN if i == 3 else LEFT, buff=.16 if i == 3 else .3))
            self.play(Flash(bolas[i], color=COR, line_length=.12), FadeIn(contador), run_time=.4)
            for k, j in enumerate(sorted(INI[i]["dominados"], key=lambda j: PONTOS[j][1])):
                setas[i, j] = seta(i, j)
                rt = (.42 if k < 3 else .2) if ordem == 0 else .12
                self.play(GrowArrow(setas[i, j]), n.animate.set_value(k + 1), run_time=rt)
            assert round(n.get_value()) == INI[i]["S"]
            self.wait(.35)
            contador.clear_updaters()
            self.play(FadeOut(contador), *(s.animate.set_opacity(.25) for (a, _), s in setas.items() if a == i), run_time=.3)
        resto = [(i, j) for i in bolas for j in INI[i]["dominados"] if i not in FLUTUAM]
        for a, b in resto:
            setas[a, b] = seta(a, b, .25)
        self.play(LaggedStart(*(GrowArrow(setas[x]) for x in resto), lag_ratio=.03), run_time=1.0)

        # A lagoa: cada plano boia na linha d'água, na ordem de R, com sua força S em cima.
        por_peso = sorted(INI, key=lambda i: (INI[i]["R"], i))
        coluna = {i: 2.62 + .345 * k for k, i in enumerate(por_peso)}
        AGUA, ESCALA = 1.25, .078
        agua = Line(pos(2.3, AGUA), pos(6.65, AGUA), color=CYAN, stroke_width=2)
        boias = {i: Dot(pos(coluna[i], AGUA), radius=.11, color=COR) for i in por_peso}
        nomes_s = {i: rotulo(str(INI[i]["S"]), 18, COR, True).move_to(pos(coluna[i], AGUA + .45)) for i in por_peso}
        letra_s = rotulo("S", 22, COR, True).move_to(pos(2.18, AGUA + .45))
        self.play(FadeIn(agua), FadeIn(letra_s), *(ReplacementTransform(bolas[i].copy(), boias[i]) for i in por_peso),
                  *(FadeIn(n) for n in nomes_s.values()), run_time=.9)
        fundo = {i: AGUA for i in por_peso}
        pilhas = {i: VGroup() for i in por_peso}

        def bloco_peso(i, j, topo):
            h = INI[i]["S"] * ESCALA
            return Rectangle(width=.25, height=h, stroke_color=FUNDO, stroke_width=1.5, fill_color=COR, fill_opacity=.75).move_to(
                pos(coluna[j], topo - h / 2))
        # Câmera lenta: os dominadores de um plano despejam a própria força sobre ele.
        j = PESADO
        donos = sorted((i for i in INI if j in INI[i]["dominados"]), key=lambda i: -INI[i]["S"])
        aro = Circle(radius=.17, color=INK, stroke_width=2.5).move_to(bolas[j])
        aro2 = Circle(radius=.19, color=INK, stroke_width=2).move_to(boias[j])
        self.play(Create(aro), Create(aro2), *(setas[i, j].animate.set_opacity(1) for i in donos), run_time=.4)
        soma = ValueTracker(0)
        leitura = always_redraw(lambda: rotulo(f"R = {round(soma.get_value())}", 24, INK, True).move_to(
            pos(coluna[j], boias[j].get_center()[1] - .42)))
        self.add(leitura)
        for i in donos:
            h = INI[i]["S"] * ESCALA
            peso = bloco_peso(i, j, fundo[j])
            self.play(ReplacementTransform(setas.pop((i, j)), peso), run_time=.45)
            fundo[j] -= h
            self.play(boias[j].animate.move_to(pos(coluna[j], fundo[j] - .11)), aro2.animate.move_to(pos(coluna[j], fundo[j] - .11)),
                      soma.animate.set_value(soma.get_value() + INI[i]["S"]), run_time=.3, rate_func=rush_into)
            pilhas[j].add(peso)
        assert round(soma.get_value()) == INI[j]["R"]
        self.wait(.5)
        leitura.clear_updaters()
        self.play(FadeOut(aro), FadeOut(aro2), FadeOut(leitura), run_time=.25)
        # Um único movimento: todas as outras setas viram massa e o conjunto afunda.
        anims, quedas = [], []
        for b in por_peso:
            for i in sorted((i for i in INI if b in INI[i]["dominados"] and (i, b) in setas), key=lambda i: -INI[i]["S"]):
                peso = bloco_peso(i, b, fundo[b])
                fundo[b] -= INI[i]["S"] * ESCALA
                anims.append(ReplacementTransform(setas[i, b], peso))
                pilhas[b].add(peso)
            if b != j and INI[b]["R"]:
                quedas.append(boias[b].animate.move_to(pos(coluna[b], fundo[b] - .11)).set_color(MUTED))
        quedas.append(boias[j].animate.set_color(MUTED))
        for b in por_peso:
            assert abs((AGUA - fundo[b]) / ESCALA - INI[b]["R"]) < 1e-6
        self.play(*anims, *quedas, run_time=1.5, rate_func=rush_into)
        self.play(*(x.animate.shift(pos(0, -.06)) for b in por_peso if INI[b]["R"] for x in (pilhas[b], boias[b])),
                  run_time=.25, rate_func=there_and_back)
        nomes_r = {i: rotulo(str(INI[i]["R"]), 17, INK, True).move_to(pos(coluna[i], fundo[i] - .36)) for i in por_peso}
        letra_r = rotulo("R", 22, INK, True).move_to(pos(2.18, AGUA - .36))
        self.play(FadeIn(letra_r), *(FadeIn(n) for n in nomes_r.values()),
                  *(bolas[i].animate.set_color(MUTED).set_opacity(.4) for i in bolas if i not in FLUTUAM),
                  *(Flash(boias[i], color=COR, line_length=.1) for i in FLUTUAM),
                  *(bolas[i].animate.scale(1.35) for i in FLUTUAM), run_time=.7)
        self.hold()

        # ---------------------------------------------------------------- densidade
        lagoa = [agua, letra_s, letra_r, *boias.values(), *nomes_s.values(), *nomes_r.values(), *pilhas.values()]
        self.beat("densidade", "Entre dois igualmente bons, quem sobra?", *lagoa)
        (xa, ya), (xb, yb) = axis.c2p(XR[0], YR[0])[:2], axis.c2p(XR[1], YR[1])[:2]
        uy = (yb - ya) / (YR[1] - YR[0])
        ux = (xb - xa) / (XR[1] - XR[0])
        meio = (xa + xb) / 2
        e = ValueTracker(0)         # 0: arena; 1: 1 hora ocupa o mesmo que 1 unidade de custo

        def escala():
            return ux * (uy / ux) ** e.get_value()

        def lugar(p):
            return pos(meio + (p[0] - (XR[0] + XR[1]) / 2) * escala(), ya + (p[1] - YR[0]) * uy)
        for i, b in bolas.items():
            b.add_updater(lambda m, i=i: m.move_to(lugar(PONTOS[i])))
        raios = {i: ValueTracker(0) for i in FLUTUAM}

        def bolha(i, s, cor, opac):
            """Círculo de raio s em unidades brutas, recortado pela arena."""
            c, sx = lugar(PONTOS[i]), escala()
            a, b = max(xa, c[0] - s * sx), min(xb, c[0] + s * sx)
            xs = np.linspace(a, b, 60) if b - a > 1e-6 else np.array([c[0], c[0] + 1e-3])
            hs = [uy * sqrt(max(0, s * s - ((x - c[0]) / sx) ** 2)) + 1e-4 for x in xs]
            pts = [pos(x, c[1] + h) for x, h in zip(xs, hs)] + [pos(x, c[1] - h) for x, h in zip(xs[::-1], hs[::-1])]
            return Polygon(*pts, stroke_color=cor, stroke_width=2, fill_color=cor, fill_opacity=opac)
        tons = {FLUTUAM[0]: CYAN, FLUTUAM[1]: GREEN}
        bolhas = {i: always_redraw(lambda i=i: bolha(i, max(.01, raios[i].get_value()), tons[i], .16)) for i in FLUTUAM}
        rotx = labels[0]
        numx = VGroup(*(l for l in labels[2:] if abs(l.get_center()[1] - (ya - .20)) < .03))
        eixo_x = axis.x_axis
        eixo_x.save_state()
        regua = always_redraw(lambda: Line(pos(meio - 2.5 * escala(), ya), pos(meio + 2.5 * escala(), ya), color=GOLD, stroke_width=5))
        self.play(FadeOut(numx), FadeOut(rotx), eixo_x.animate.set_opacity(.15), FadeIn(regua), run_time=.4)
        nota = left(rotulo("1 h = $ 1", 28, GOLD, True), 2.55, 1.95)
        self.play(e.animate.set_value(1), FadeIn(nota), run_time=1.6)
        self.wait(.4)
        self.add(*bolhas.values())
        leituras = VGroup()
        for n, i in enumerate(FLUTUAM):
            y = .9 - 1.75 * n
            k = T["inicial"]["k"] + 1
            dist = INI[i]["distancias"][:k]
            viz = INI[i]["vizinhos"][:k]
            valor = always_redraw(lambda i=i, y=y: left(rotulo(f"σ = {pt(raios[i].get_value(), 1)}", 32, tons[i], True), 2.55, y))
            self.add(valor)
            for q, (d, v) in enumerate(zip(dist, viz)):
                alvo = lugar(PONTOS[v])
                marca = left(rotulo(f"{q + 1}º vizinho" + (f" · k = {k - 1}" if q == k - 1 else ""), 20, MUTED), 2.55, y - .5)
                self.add(marca)
                self.play(raios[i].animate.set_value(d), run_time=.45 if n == 0 else .28)
                self.play(Flash(alvo, color=tons[i], line_length=.1, num_lines=8, flash_radius=.12), run_time=.16)
                if q < k - 1:
                    self.remove(marca)
                else:
                    leituras.add(marca)
            assert abs(raios[i].get_value() - INI[i]["sigma"]) < 1e-6
            valor.clear_updaters()
            leituras.add(valor, left(rotulo(f"D = {pt(INI[i]['D'], 4)}", 24, INK), 2.55, y - .9))
            self.play(FadeIn(leituras[-1]), run_time=.2)
        self.play(e.animate.set_value(0), FadeOut(nota), run_time=1.5)
        livre = left(rotulo("espaço livre", 28, GREEN, True), 2.55, 1.95)
        self.play(FadeIn(livre), eixo_x.animate.set_opacity(1), FadeOut(regua), FadeIn(numx), FadeIn(rotx), run_time=.5)
        self.wait(.5)
        # Palpite que falha: o par mais próximo não é o que parece na arena.
        a = min(INI, key=lambda i: INI[i]["distancias"][0])
        b = INI[a]["vizinhos"][0]
        elo = Line(lugar(PONTOS[a]), lugar(PONTOS[b]), color=CORAL, stroke_width=3)
        par_dist = rotulo(f"distância {pt(INI[a]['distancias'][0], 1)}", 22, CORAL, True).next_to(elo, UP, buff=.1)
        for x in bolhas.values():
            x.clear_updaters()
        self.play(*(FadeOut(x) for x in bolhas.values()), FadeOut(leituras), FadeOut(livre),
                  *(bolas[i].animate.set_color(CORAL).set_opacity(1) for i in (a, b)), run_time=.4)
        self.play(Create(elo), FadeIn(par_dist), run_time=.5)
        self.wait(.9)
        for x in bolas.values():
            x.clear_updaters()
        # Torneio: duas disputas reais, vencidas pela menor aptidão.
        axis2, labels2, alvo_bolas, cartas, tit = quadro_duelo()
        self.play(FadeOut(elo), FadeOut(par_dist), *(Transform(bolas[i], alvo_bolas[i]) for i in bolas), FadeIn(tit), run_time=.5)
        for k, d in enumerate(T["primeira"]["duelos"]):
            perde = d["a"] if d["vence"] == d["b"] else d["b"]
            carta = cartas[k]
            va, vb = bolas[d["vence"]].copy(), bolas[perde].copy().set_opacity(1)
            self.play(FadeIn(carta[0]), ReplacementTransform(va, carta[1]), ReplacementTransform(vb, carta[6]),
                      FadeIn(carta[3]), FadeIn(carta[5]), run_time=.6)
            self.play(FadeIn(carta[4]), FadeIn(carta[2]), FadeIn(carta[7]), Indicate(carta[3], color=COR), run_time=.45)
        self.hold()


# ------------------------------------------------------------------------------------------------ operadores
EA = Eixo(x=-5.55, passo=.43, faixas=(1.98, 1.54, 1.10), altura=.265, total=17)
EF = Eixo(x=-5.55, passo=.43, faixas=(.20, -.24, -.68), altura=.265, total=17)
EB = Eixo(x=-5.55, passo=.43, faixas=(-1.58, -2.02, -2.46), altura=.265, total=17)
E24 = Eixo(x=-5.2, passo=.315, faixas=FAIXAS, total=24)
CRUZ = T["cruzamento"]


def moldura_tres(eixo, nome, cor):
    return VGroup(eixo.trilhos(), eixo.faixa_ponta(),
                  *(rotulo(f"M{i + 1}", 14, MUTED).move_to(pos(-5.85, eixo.faixas[i])) for i in range(3)),
                  rotulo(nome, 26 if len(nome) == 1 else 19, cor, True).move_to(pos(-6.42, eixo.faixas[1]))).set_z_index(-1)


def cenario_mutacao():
    """Fábrica com horizonte de 24 h, plano e dado."""
    pecas = VGroup(E24.faixa_ponta(), E24.trilhos(), E24.horas(-1.72, 3), *(rotulo(f"M{i + 1}", 22, MUTED, True).move_to(
        pos(-5.75, FAIXAS[i])) for i in range(3))).set_z_index(-1)
    x = E24.at(T["horizonte"])
    fim = VGroup(DashedLine(pos(x, 1.8), pos(x, -1.6), color=CORAL), rotulo("horizonte", 16, CORAL).move_to(pos(x - .1, 1.98)))
    axis, labels = pequeno((10, 26, 4), (400, 1200, 200))
    return pecas, fim, axis, labels


def dado(face, giro=0):
    lado = .72
    c = pos(-5.75, -2.65)
    pips = {1: [(0, 0)], 2: [(-1, 1), (1, -1)], 3: [(-1, 1), (0, 0), (1, -1)], 4: [(-1, 1), (1, 1), (-1, -1), (1, -1)],
            5: [(-1, 1), (1, 1), (0, 0), (-1, -1), (1, -1)]}[face]
    g = VGroup(RoundedRectangle(width=lado, height=lado, corner_radius=.14, stroke_color=COR, stroke_width=3, fill_color=FUNDO,
                                fill_opacity=1), *(Dot(pos(.19 * a, .19 * b), radius=.055, color=COR) for a, b in pips))
    return g.rotate(giro).move_to(c)


def quadro_inviavel():
    """Fim dos operadores: a fábrica esmaecida, o ponto parado e a avaliação gasta."""
    m = T["mutacoes"]["inviavel"]
    pecas, fim, axis, labels = cenario_mutacao()
    g = gantt(m["antes"], E24)
    del g[0]
    corpo = grupo(g).set_opacity(.25)
    ponto = Dot(axis.c2p(m["antes"]["cmax"], m["antes"]["tec"]), radius=.1, color=MUTED)
    conta = rotulo(f"avaliação {m['avaliacao']}", 24, INK, True).move_to(pos(5.0, -2.98))
    nota = rotulo("inviável", 28, CORAL, True).move_to(pos(5.0, -2.42))
    face = VGroup(dado(FACE[m["op"]]), left(rotulo(NOMES[m["op"]], 32, COR, True), -5.15, -2.65))
    return pecas, fim, axis, labels, corpo, ponto, conta, nota, face


class Spea2Operadores(Plateia):
    chapter, number = "SPEA2 INCREMENTAL", 2

    def construct(self):
        self.abrir("Entre dois igualmente bons, quem sobra?")
        axis, labels, bolas, cartas, tit = quadro_duelo()
        self.add(axis, labels, *bolas.values(), cartas, tit)

        # ---------------------------------------------------------------- cruzamento
        self.beat("cruzamento", "Como dois pais viram um filho?")
        A, B = (gantt(p, e) for p, e in zip(CRUZ["pais"], (EA, EB)))
        molA, molB, molF = moldura_tres(EA, "A", COR), moldura_tres(EB, "B", COR), moldura_tres(EF, "filho", INK)
        ga, gb = grupo(A), grupo(B)
        self.play(FadeOut(axis), FadeOut(labels), FadeOut(tit), *(FadeOut(b) for i, b in bolas.items() if i not in PAIS),
                  ReplacementTransform(cartas[0], ga), ReplacementTransform(cartas[1], gb),
                  ReplacementTransform(bolas[PAIS[0]], molA), ReplacementTransform(bolas[PAIS[1]], molB), run_time=1.1)
        self.play(FadeIn(molF), run_time=.3)

        linhas, moedas = {}, {}
        for s in CRUZ["sorteios"]:
            y = 1.98 - .52 * s["job"]
            chip = VGroup(Rectangle(width=.55, height=.36, stroke_width=0, fill_color=CORES[s["job"]], fill_opacity=1),
                          rotulo(f"T{s['job'] + 1}", 17, FUNDO, True)).move_to(pos(3.0, y))
            moedas[s["job"]] = VGroup(Circle(radius=.2, color=COR, stroke_width=3, fill_color=FUNDO, fill_opacity=1),
                                      rotulo("?", 18, COR, True)).move_to(pos(3.75, y))
            linhas[s["job"]] = VGroup(chip, moedas[s["job"]])
        dica = rotulo("moeda por tarefa", 22, MUTED).move_to(pos(5.5, 1.98))
        self.play(LaggedStart(*(FadeIn(l) for l in linhas.values()), lag_ratio=.05), FadeIn(dica), run_time=.6)
        filho = {}
        for n, s in enumerate(CRUZ["sorteios"]):
            j, origem = s["job"], (A, B)[s["origem"]]
            rt = (.7, .5, .35)[min(n, 2)]
            moeda_ = moedas[j]
            self.play(moeda_.animate.stretch(.05, 0), run_time=rt * .3)
            nova = VGroup(Circle(radius=.2, color=COR, stroke_width=3, fill_color=COR, fill_opacity=1),
                          rotulo("AB"[s["origem"]], 19, FUNDO, True)).move_to(moeda_)
            moeda_.become(nova.copy().stretch(.05, 0))
            self.play(Transform(moeda_, nova), origem[j][2].animate.set_stroke(INK, 2, family=False), run_time=rt * .4)
            b = next(b for b in CRUZ["passos"][n] if b["job"] == j)
            alvo = VGroup(EF.setup(b), EF.espera(b), EF.bloco(b))
            viajante = origem[j][2].copy()
            self.add(alvo[0], alvo[1])
            rejeitado = (A, B)[1 - s["origem"]][j][2]
            self.play(ReplacementTransform(viajante, alvo[2], path_arc=.4), FadeIn(alvo[0]),
                      rejeitado.animate.set_opacity(.28), run_time=rt * 1.1)
            filho[j] = alvo
        self.wait(.3)

        # Colisão na mesma máquina: posição em A + posição em B + ruído.
        M = CRUZ["filho"]["blocks"]
        disputa = [b["job"] for b in M if b["machine"] == 0]
        somas = {s["job"]: s for s in CRUZ["sorteios"]}
        rivais = sorted(disputa, key=lambda j: somas[j]["soma"])[1:]
        tremor = [filho[j][2] for j in rivais]
        self.play(*(FadeOut(l) for l in linhas.values()), FadeOut(dica), *(pulsa(t, 1.2) for t in tremor),
                  run_time=.6)
        reguas, u, x0 = VGroup(), 1.15, 3.35
        guia = VGroup(*(VGroup(Line(pos(x0 + q * u, 1.75), pos(x0 + q * u, -.1), color=GRID, stroke_width=1.5),
                               rotulo(str(q), 16, MUTED).move_to(pos(x0 + q * u, 1.95))) for q in range(3)))
        self.play(FadeIn(guia), run_time=.25)
        for n, j in enumerate(rivais[::-1]):
            s, y = somas[j], 1.3 - .95 * n
            chip = VGroup(Rectangle(width=.55, height=.36, stroke_width=0, fill_color=CORES[j], fill_opacity=1),
                          rotulo(f"T{j + 1}", 17, FUNDO, True)).move_to(pos(2.85, y))
            partes, x = VGroup(), x0
            for v, cor, letra in ((s["posicoes"][0], COR, "A"), (s["posicoes"][1], MUTED, "B"), (s["ruido"], CORAL, "")):
                if v:
                    seg = Rectangle(width=v * u, height=.38, stroke_color=FUNDO, stroke_width=1.5, fill_color=cor, fill_opacity=.85)
                    seg.move_to(pos(x + v * u / 2, y))
                    partes.add(VGroup(seg, rotulo(letra, 17, FUNDO, True).move_to(seg)))
                    x += v * u
            self.play(ReplacementTransform(filho[j][2][0].copy(), chip), run_time=.35)
            for parte in partes:
                self.play(GrowFromEdge(parte, LEFT), run_time=.35)
            total = rotulo(pt(s["soma"], 2), 22, INK, True).move_to(pos(x + .38, y))
            self.play(FadeIn(total), run_time=.2)
            reguas.add(VGroup(chip, partes, total))
        ruido = rotulo("ruído decide", 22, CORAL, True).move_to(pos(5.0, -.45))
        self.play(FadeIn(ruido), Indicate(reguas[1][2], color=GREEN), run_time=.6)
        # Reordena todas as máquinas e refaz os setups.
        final = gantt(CRUZ["filho"], EF)
        sobe = [filho[j][2].animate.shift(pos(0, .12)) for j in filho]
        self.play(*sobe, run_time=.25)
        self.play(*(Transform(filho[j][2], final[j][2], path_arc=-.9) for j in filho),
                  *(Transform(filho[j][k], final[j][k]) for j in filho for k in (0, 1)), run_time=1.0)
        pais_pts = [(p["cmax"], p["tec"]) for p in CRUZ["pais"]]
        fp = (CRUZ["filho"]["cmax"], CRUZ["filho"]["tec"])
        etiquetas = VGroup(*(rotulo(par(v), 22, c, w).move_to(pos(3.6, y)) for v, c, w, y in
                             ((pais_pts[0], MUTED, False, 1.54), (fp, GREEN, True, -.24), (pais_pts[1], MUTED, False, -2.02))))
        self.play(FadeOut(guia), FadeOut(reguas), FadeOut(ruido), run_time=.25)
        self.play(FadeIn(etiquetas[0]), FadeIn(etiquetas[2]), run_time=.3)
        self.play(FadeIn(etiquetas[1], scale=1.2), *(Circumscribe(filho[j][2], color=GREEN, buff=.03) for j in filho), run_time=.6)
        self.hold()

        # ---------------------------------------------------------------- mutações
        self.beat("mutacoes", "E se os pais não bastarem?", ga, gb, molA, molB, molF, etiquetas[0], etiquetas[2])
        pecas, fim, axis, labels = cenario_mutacao()
        m = T["mutacoes"][ORDEM[0]]
        g = gantt(m["antes"], E24)
        ponto = Dot(axis.c2p(m["antes"]["cmax"], m["antes"]["tec"]), radius=.1, color=COR)
        self.play(FadeIn(pecas), FadeIn(fim), Create(axis), FadeIn(labels),
                  *(ReplacementTransform(filho[j], g[j]) for j in g), ReplacementTransform(etiquetas[1], ponto), run_time=1.0)
        cont = ValueTracker(T["primeira"]["avaliacao"])
        leitura = always_redraw(lambda: rotulo(f"avaliação {round(cont.get_value())}", 24, INK, True).move_to(pos(5.0, -2.98)))
        self.play(FadeIn(leitura), run_time=.2)
        cubo, nome, valores = dado(1), None, None
        self.play(FadeIn(cubo), run_time=.2)
        for n, chave in enumerate(ORDEM):
            m = T["mutacoes"][chave]
            antes, depois, jobs = m["antes"], m["depois"], m["jobs"]
            saem = [FadeOut(x) for x in (nome, valores) if x is not None]
            if n:
                novo = gantt(antes, E24)
                self.play(*(Transform(g[j], novo[j]) for j in g), ponto.animate.move_to(axis.c2p(antes["cmax"], antes["tec"])),
                          cont.animate.set_value(m["avaliacao"] - 1), *saem, run_time=.55)
            else:
                self.play(cont.animate.set_value(m["avaliacao"] - 1), run_time=.4)
            pv = (antes["cmax"], antes["tec"])
            origem = rotulo(par(pv), 22, MUTED).move_to(pos(5.0, -2.12))
            for giro, f in ((.6, 1 + (FACE[m["op"]] % 5)), (-.5, 1 + ((FACE[m["op"]] + 1) % 5))):
                self.play(Transform(cubo, dado(f, giro)), FadeIn(origem), run_time=.12)
            self.play(Transform(cubo, dado(FACE[m["op"]])), run_time=.18)
            depois_g = gantt(depois, E24)
            antec = [pulsa(g[j][2]) for j in jobs]
            if chave == "inviavel":
                self.inviavel(m, g, depois_g, cont)
                nome = left(rotulo(NOMES[m["op"]], 32, COR, True), -5.15, -2.65)
                nota = rotulo("inviável", 28, CORAL, True).move_to(pos(5.0, -2.42))
                self.play(FadeIn(nome), FadeIn(nota), FadeOut(origem), ponto.animate.set_color(MUTED), run_time=.35)
                break
            fp = (depois["cmax"], depois["tec"])
            destino = axis.c2p(*fp)
            rastro = Line(ponto.get_center(), destino, color=COR, stroke_width=2.5).set_opacity(.5)
            move_ponto = [ponto.animate.move_to(destino), Create(rastro), cont.animate.set_value(m["avaliacao"])]
            self.play(*antec, run_time=.3)
            self.operar(m["op"], jobs, g, depois_g, move_ponto)
            nome = left(rotulo(NOMES[m["op"]], 32, COR, True), -5.15, -2.65)
            valores = VGroup(rotulo(par(fp), 25, GREEN, True).move_to(pos(5.0, -2.52)), origem, rastro)
            self.play(FadeIn(nome), FadeIn(valores[0]), *(Circumscribe(g[j][2], color=GREEN, buff=.04) for j in jobs), run_time=.6)
            self.wait(.35)
        leitura.clear_updaters()
        self.remove(*self.mobjects)
        self.add(self.cabecalho, self.titulo, *quadro_inviavel())
        self.hold()

    def operar(self, op, jobs, g, novo, extra):
        """Coreografia comum do guia; as vizinhas e o ponto se movem junto com a ação."""
        outros = [Transform(g[j][k], novo[j][k]) for j in g for k in (0, 1)]
        outros += [Transform(g[j][2], novo[j][2]) for j in g if j not in jobs]
        j = jobs[0]
        if op == "insercao":
            self.play(g[j][2].animate.shift(pos(0, .62)), run_time=.3)
            alto = novo[j][2].copy().shift(pos(0, .62))
            self.play(Transform(g[j][2], alto), *outros, *extra, run_time=.95)
            self.play(Transform(g[j][2], novo[j][2]), run_time=.3)
        elif op == "troca":
            self.bring_to_front(*(g[k][2] for k in jobs))
            self.play(*(Transform(g[k][2], novo[k][2], path_arc=1.5) for k in jobs), *outros, *extra, run_time=1.2)
        elif op == "realocacao":
            self.bring_to_front(g[j][2])
            self.play(Transform(g[j][2], novo[j][2], path_arc=-1.4), *outros, *extra, run_time=1.2)
        else:
            self.play(Transform(g[j][2], novo[j][2]), *outros, *extra, run_time=1.1)

    def inviavel(self, m, g, novo, cont):
        self.play(Indicate(g[m["jobs"][0]][1], color=GOLD), run_time=.3)
        self.play(*(Transform(g[j][k], novo[j][k]) for j in g for k in range(3)), run_time=.9)
        tudo = VGroup(*(g[j] for j in g))
        for dx in (.06, -.12, .12, -.06):
            self.play(tudo.animate.shift(pos(dx, 0)), run_time=.07)
        quebra = next(b["job"] for b in m["depois"]["blocks"] if b["end"] > T["horizonte"])
        assert quebra == 0
        r = g[quebra][2][0]
        metades = VGroup(*(Rectangle(width=r.width / 2, height=r.height, stroke_width=0, fill_color=CORES[quebra], fill_opacity=1)
                           .move_to(r.get_center() + pos(d * r.width / 4, 0)) for d in (-1, 1)))
        self.remove(g[quebra][2])
        self.add(metades)
        self.play(metades[0].animate.shift(pos(-.15, -.5)).rotate(.5).set_opacity(0),
                  metades[1].animate.shift(pos(.15, -.6)).rotate(-.6).set_opacity(0),
                  *(FadeOut(x) for x in (g[quebra][0], g[quebra][1])), cont.animate.set_value(m["avaliacao"]), run_time=.8)
        voltar = gantt(m["antes"], E24)
        self.play(*(Transform(g[j], self.esmaecer(voltar[j])) for j in g if j != quebra), run_time=.4)

    @staticmethod
    def esmaecer(x):
        x.set_opacity(.25)
        return x


# ------------------------------------------------------------------------------------------------ busca
def posicoes_por_rodada():
    """Vaga de cada sobrevivente após cada rodada; a vaga do removido passa ao descendente."""
    vagas = [l["id"] for l in T["inicial"]["linhas"]]
    pontos = {i: tuple(p) for i, p in PONTOS.items()}
    historia = [[pontos[i] for i in vagas]]
    for r in T["rodadas"]:
        if r["removido"] != r["filho"]:
            pontos[r["filho"]] = tuple(r["ponto"])
            vagas[vagas.index(r["removido"])] = r["filho"]
        historia.append([pontos[i] for i in vagas])
    assert sorted(vagas) == sorted(T["final"])
    return np.array(historia, float)


class Spea2Busca(Plateia):
    chapter, number = "SPEA2 INCREMENTAL", 3

    def construct(self):
        self.abrir("E se os pais não bastarem?")
        quadro = quadro_inviavel()
        self.add(*quadro)

        # ---------------------------------------------------------------- expulsão
        self.beat("expulsao", "Entrou um: quem sai?", *(x for k, x in enumerate(quadro) if k not in (2, 3)))
        axis, labels = grande()
        bolas = {i: ponto_dot(axis, p) for i, p in PONTOS.items()}
        self.play(ReplacementTransform(quadro[2], axis), FadeOut(quadro[3]), FadeIn(labels),
                  LaggedStart(*(FadeIn(b, scale=.3) for b in bolas.values()), lag_ratio=.03), run_time=.8)
        por_peso = sorted(INI, key=lambda i: (PRI[i]["R"], i))
        coluna = {i: 2.72 + .315 * k for k, i in enumerate([FILHO, *por_peso])}
        AGUA, ESCALA = 1.3, .06
        agua = Line(pos(2.35, AGUA), pos(6.65, AGUA), color=CYAN, stroke_width=2)
        pilha = {i: Rectangle(width=.22, height=max(.001, INI[i]["R"] * ESCALA), stroke_width=0, fill_color=COR, fill_opacity=.6 if INI[i]["R"] else 0)
                 .move_to(pos(coluna[i], AGUA - INI[i]["R"] * ESCALA / 2)) for i in por_peso}
        boia = {i: Dot(pos(coluna[i], AGUA - INI[i]["R"] * ESCALA - (.1 if INI[i]["R"] else 0)), radius=.1,
                       color=MUTED if INI[i]["R"] else COR) for i in por_peso}
        conta = rotulo(f"P = {len(PONTOS)}", 30, INK, True).move_to(pos(4.6, 2.15))
        self.play(FadeIn(agua), *(FadeIn(x) for x in (*pilha.values(), *boia.values())), FadeIn(conta), run_time=.5)
        # O filho do cruzamento cai na arena.
        eixo = Eixo(x=-4.0, passo=.17, faixas=(2.0, 1.68, 1.36), altura=.2, total=17)
        corpo = grupo(gantt(CRUZ["filho"], eixo))
        bf = ponto_dot(axis, PRI[FILHO]["ponto"], GREEN, .11)
        self.play(FadeIn(corpo, shift=pos(0, -.2)), run_time=.35)
        mais = rotulo(f"P + 1 = {len(PRI)}", 30, GREEN, True).move_to(conta)
        bb = Dot(pos(coluna[FILHO], AGUA), radius=.1, color=GREEN)
        self.play(ReplacementTransform(corpo, bf), run_time=.7)
        self.play(ReplacementTransform(bf.copy(), bb), FadeOut(conta, shift=pos(0, .1)), FadeIn(mais, shift=pos(0, .1)), Flash(bf, color=GREEN), run_time=.5)
        doms = PRI[FILHO]["dominados"]
        setas = {j: Arrow(bf.get_center(), bolas[j].get_center(), buff=.1, stroke_width=2.2, tip_length=.12, color=GREEN,
                          max_tip_length_to_length_ratio=.35, max_stroke_width_to_length_ratio=40) for j in doms}
        self.play(LaggedStart(*(GrowArrow(s) for s in setas.values()), lag_ratio=.06), run_time=.7)
        novos, quedas = {}, []
        h = PRI[FILHO]["S"] * ESCALA
        for j in doms:
            assert PRI[j]["R"] == INI[j]["R"] + PRI[FILHO]["S"]
            base = AGUA - INI[j]["R"] * ESCALA
            novos[j] = Rectangle(width=.22, height=h, stroke_color=FUNDO, stroke_width=1, fill_color=GREEN, fill_opacity=.8).move_to(
                pos(coluna[j], base - h / 2))
            quedas.append(boia[j].animate.move_to(pos(coluna[j], base - h - .1)).set_color(MUTED))
        self.play(*(ReplacementTransform(setas[j], novos[j]) for j in doms), *quedas, run_time=.9, rate_func=rush_into)
        fora = T["primeira"]["removido"]
        assert fora == max(PRI, key=lambda i: PRI[i]["F"])
        valor = rotulo(f"R = {PRI[fora]['R']}", 24, CORAL, True).move_to(pos(5.85, -2.95))
        aro = Circle(radius=.18, color=CORAL, stroke_width=3).move_to(bolas[fora])
        self.play(FadeIn(valor), Create(aro), boia[fora].animate.set_color(CORAL), bolas[fora].animate.set_color(CORAL), run_time=.4)
        self.wait(.5)
        volta = rotulo("P + 1 → P", 30, INK, True).move_to(mais)
        self.play(VGroup(pilha[fora], novos[fora], boia[fora]).animate.shift(pos(0, -.5)).set_opacity(0),
                  VGroup(bolas[fora], aro).animate.shift(pos(0, -.8)).set_opacity(0), FadeOut(valor),
                  FadeOut(mais), FadeIn(volta), run_time=.8, rate_func=rush_into)
        self.remove(bolas.pop(fora), aro, pilha.pop(fora), novos.pop(fora), boia.pop(fora))
        self.wait(.3)

        # Segundo caso real: todos não dominados.
        axis2, labels2 = grande(*PERTO)
        ids = [i for i in TRU if i != T["truncamento"]["filho"]]
        bf_ids = [FILHO, *bolas]
        todas = {FILHO: bf} | bolas
        novas = {i: ponto_dot(axis2, TRU[i]["ponto"], COR, .095) for i in ids}
        cont = ValueTracker(T["primeira"]["avaliacao"])
        leitura = always_redraw(lambda: rotulo(f"avaliação {round(cont.get_value())}", 22, INK, True).move_to(pos(-.45, 1.6)))
        self.add(leitura)
        self.play(*(FadeOut(x) for x in (agua, bb, volta, *pilha.values(), *novos.values(), *boia.values())),
                  ReplacementTransform(axis, axis2), FadeOut(labels), FadeIn(labels2),
                  *(ReplacementTransform(todas[a], novas[b]) for a, b in zip(sorted(bf_ids, key=lambda i: PRI[i]["ponto"]),
                                                                             sorted(ids, key=lambda i: TRU[i]["ponto"]))),
                  cont.animate.set_value(T["truncamento"]["avaliacao"]), run_time=1.5)
        self.remove(*todas.values())
        leitura.clear_updaters()
        filho = T["truncamento"]["filho"]
        entra = ponto_dot(axis2, TRU[filho]["ponto"], GREEN, .11)
        partida = Dot(axis2.c2p(TRU[filho]["ponto"][0], 890), radius=.11, color=GREEN)
        self.play(ReplacementTransform(partida, entra), run_time=.6)
        self.play(Flash(entra, color=GREEN), run_time=.25)
        novas[filho] = entra
        # Cartas abertas: distâncias ordenadas dos três mais apertados.
        saiu = T["truncamento"]["removido"]
        ordem = sorted(TRU, key=lambda i: TRU[i]["distancias"])
        assert tuple(TRU[saiu]["distancias"]) == tuple(TRU[ordem[0]]["distancias"])
        casos, vistos = [], set()
        for i in ordem:
            if tuple(TRU[i]["ponto"]) not in vistos:
                vistos.add(tuple(TRU[i]["ponto"]))
                casos.append(i)
        casos = casos[:3]
        gemeos = VGroup()
        for i in casos:
            reps = sum(l["ponto"] == TRU[i]["ponto"] for l in TRU.values())
            if reps > 1:
                c = novas[i].get_center()
                gemeos.add(VGroup(Circle(radius=.17, color=INK, stroke_width=2).move_to(c), rotulo(f"×{reps}", 18, INK, True).move_to(c + pos(.36, .16))))
        self.play(FadeIn(gemeos), run_time=.3)
        tons = (CORAL, GOLD, MUTED)
        cabec = VGroup(*(rotulo(f"{q + 1}º vizinho", 17, MUTED).move_to(pos(4.35 + 1.45 * q, 1.75)) for q in range(2)))
        self.play(FadeIn(cabec), run_time=.2)
        cartas = {}
        for n, i in enumerate(casos):
            y = 1.05 - 1.1 * n
            aro = Circle(radius=.24, color=tons[n], stroke_width=3).move_to(novas[i])
            rot = rotulo(f"{TRU[i]['ponto'][0]} h", 24, tons[n], True).move_to(pos(2.95, y))
            verso = [RoundedRectangle(width=1.2, height=.8, corner_radius=.1, stroke_color=tons[n], stroke_width=2,
                                      fill_color=GRID, fill_opacity=.6).move_to(pos(4.35 + 1.45 * q, y)) for q in range(2)]
            cartas[i] = dict(aro=aro, rot=rot, verso=verso, num=[])
        self.play(*(Create(c["aro"]) for c in cartas.values()), *(FadeIn(c["rot"]) for c in cartas.values()),
                  *(FadeIn(v) for c in cartas.values() for v in c["verso"]), run_time=.4)

        def virar(q, quais):
            elos = VGroup(*(Line(novas[i].get_center(), novas[TRU[i]["vizinhos"][q]].get_center(), color=cartas[i]["rot"][0].get_color(), stroke_width=3)
                            for i in quais))
            nums = []
            for i in quais:
                v = cartas[i]["verso"][q]
                nums.append(rotulo(pt(TRU[i]["distancias"][q], 1), 25, INK, True).move_to(v))
                cartas[i]["num"].append(nums[-1])
            self.play(*(cartas[i]["verso"][q].animate.stretch(.05, 0) for i in quais), run_time=.18)
            self.play(*(cartas[i]["verso"][q].animate.stretch(20, 0).set_fill(FUNDO, 1) for i in quais),
                      *(FadeIn(x) for x in nums), *(Create(e) for e in elos), run_time=.3)
            return elos
        elos = virar(0, casos)
        self.wait(.4)
        self.play(VGroup(cartas[casos[2]]["rot"], *cartas[casos[2]]["verso"], *cartas[casos[2]]["num"]).animate.set_opacity(.2),
                  FadeOut(cartas[casos[2]]["aro"]), FadeOut(elos), run_time=.3)
        elos = virar(1, casos[:2])
        self.wait(.5)
        sai = novas.pop(saiu)
        marca = cartas[casos[0]]["num"][1]
        self.play(Indicate(marca, color=CORAL, scale_factor=1.3), run_time=.4)
        seta = rotulo("P + 1 → P", 28, INK, True).move_to(pos(4.6, -2.6))
        sai.set_color(CORAL)
        self.add(sai)
        self.play(sai.animate.shift(pos(1.2, 1.4)).set_opacity(0), FadeOut(elos), FadeIn(seta),
                  *(FadeOut(c["aro"]) for c in (cartas[casos[0]], cartas[casos[1]])), FadeOut(gemeos), run_time=.8)
        self.remove(sai)
        self.hold()

        # ---------------------------------------------------------------- busca
        soltos = [cabec, seta]
        for c in cartas.values():
            soltos += [c["rot"], *c["verso"], *c["num"]]
        self.beat("busca", f"E depois de {len(T['rodadas'])} rodadas?", *soltos, leitura)
        hist = posicoes_por_rodada()
        axis3, labels3 = grande(*LARGA)
        volta = ValueTracker(T["truncamento"]["avaliacao"])
        rodada = ValueTracker(0)
        assert (hist[:, :, 0] >= 10).all() and (hist[:, :, 0] <= 26).all() and (hist[:, :, 1] >= 400).all() and (hist[:, :, 1] <= 1600).all()
        nuvem = VGroup(*(Dot(axis3.c2p(*p), radius=.085, color=COR) for p in hist[0]))
        conta = always_redraw(lambda: rotulo(f"{round(volta.get_value())}", 54, COR, True).move_to(pos(4.4, 1.0)))
        nome = rotulo("avaliações", 22, MUTED).move_to(pos(4.4, .4))
        antigos = VGroup(*(x for x in self.mobjects if isinstance(x, Dot)))
        self.play(ReplacementTransform(axis2, axis3), FadeOut(labels2), FadeIn(labels3), FadeOut(antigos), FadeIn(nuvem),
                  FadeIn(conta), FadeIn(nome), volta.animate.set_value(DEMO["population_size"]), run_time=1.0)
        exata = VGroup(dots(axis3, EXATA, GOLD, .045).set_fill(opacity=.45), staircase(axis3, EXATA, GOLD, 1.5)).set_stroke(opacity=.45)
        self.play(FadeIn(exata), run_time=.4)
        volta.clear_updaters()
        conta.clear_updaters()
        self.remove(conta)
        conta = always_redraw(lambda: rotulo(f"{DEMO['population_size'] + int(rodada.get_value())}", 54, COR, True).move_to(pos(4.4, 1.0)))
        self.add(conta)
        chuva = VGroup(*(Dot(pos(0, 0), radius=.045, color=MUTED, fill_opacity=0) for _ in range(18)))
        fugas = VGroup(*(Dot(pos(0, 0), radius=.06, color=CORAL, fill_opacity=0) for _ in range(8)))

        def mover(m):
            r = rodada.get_value()
            k = min(int(r), len(hist) - 2)
            f = smooth(min(1, r - k))
            a, b = hist[k], hist[k + 1]
            for d, p, q in zip(m, a, b):
                d.move_to(axis3.c2p(*(p + (q - p) * f)))

        def chover(m):
            k = int(rodada.get_value())
            for n, d in enumerate(m):
                r = T["rodadas"][k - n] if 0 <= k - n < len(T["rodadas"]) else None
                if r is None or r["ponto"] is None or r["removido"] != r["filho"] or rodada.get_value() >= len(T["rodadas"]):
                    d.set_fill(opacity=0)
                else:
                    d.move_to(axis3.c2p(*r["ponto"])).set_fill(opacity=.55 * (1 - n / 18))

        def fugir(m):
            k = int(rodada.get_value())
            for n, d in enumerate(m):
                t = k - n
                if not 0 <= t < len(T["rodadas"]) or T["rodadas"][t]["removido"] == T["rodadas"][t]["filho"]:
                    d.set_fill(opacity=0)
                    continue
                v = int(np.argmax(np.abs(hist[t + 1] - hist[t]).sum(axis=1)))
                d.move_to(axis3.c2p(*hist[t][v]) + pos(0, .05 * n)).set_fill(opacity=.6 * (1 - n / 8))
        nuvem.add_updater(mover)
        chuva.add_updater(chover)
        fugas.add_updater(fugir)
        self.add(chuva, fugas, nuvem)
        self.play(rodada.animate.set_value(6), run_time=2.6, rate_func=linear)
        self.play(rodada.animate.set_value(60), run_time=2.2, rate_func=linear)
        self.play(rodada.animate.set_value(len(T["rodadas"])), run_time=4.2, rate_func=lambda t: t ** 1.6)
        for x in (nuvem, chuva, fugas, conta):
            x.clear_updaters()
        self.remove(chuva, fugas)
        ultimo = [Dot(axis3.c2p(*p), radius=.085, color=COR) for p in hist[-1]]
        for d, u in zip(nuvem, ultimo):
            d.become(u)
        assert {tuple(p) for p in hist[-1]} == set(FRENTE)
        self.wait(.5)

        # Quadro-base: a população final vira a frente e um dos planos volta a ser Gantt.
        itens = self.base()
        ax, lb = pequeno(*PERTO_BASE)
        alvo_exata = VGroup(dots(ax, EXATA, GOLD, .045).set_fill(opacity=.45), staircase(ax, EXATA, GOLD, 1.5)).set_stroke(opacity=.45)
        alvo = [Dot(ax.c2p(*p), radius=.07, color=COR) for p in hist[-1]]
        self.play(FadeOut(conta), FadeOut(nome), FadeOut(labels3), ReplacementTransform(axis3, ax), FadeIn(lb),
                  ReplacementTransform(exata, alvo_exata), *(Transform(d, u) for d, u in zip(nuvem, alvo)), run_time=1.2)
        melhor = next(p for p in T["frente"] if p["cmax"] == 15)
        escolhido = Dot(ax.c2p(melhor["cmax"], melhor["tec"]), radius=.11, color=COR)
        degrau = staircase(ax, FRENTE, COR, 2)
        self.play(Create(degrau), FadeIn(escolhido, scale=2), *(FadeIn(x) for x in itens), run_time=.6)
        g = gantt(melhor, EIXO)
        semente = escolhido.copy()
        self.play(ReplacementTransform(semente, grupo(g)), run_time=1.0)
        valor = rotulo(par((melhor["cmax"], melhor["tec"])), 24, COR, True).move_to(pos(5.0, -2.25))
        campanha = rotulo(f"campanha: {CAMPANHA['population_size']} · {pt(CAMPANHA['crossover_probability'], 1)} · "
                          f"{pt(CAMPANHA['mutation_probability'], 1)}", 22, MUTED).move_to(pos(5.0, -2.75))
        self.play(FadeIn(valor), FadeIn(campanha), run_time=.4)
        self.hold()
