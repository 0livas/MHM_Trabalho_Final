"""MOEA/D: o leque de holofotes e o coral de vizinhos. As cenas só leem data/trace_moead.json."""

from manim import (
    AnimationGroup, Create, DashedLine, Dot, FadeIn, FadeOut, Flash, GrowFromEdge, GrowFromPoint, LaggedStart, Line, Polygon,
    Rectangle, ReplacementTransform, RoundedRectangle, Star, Transform, TransformFromCopy, Triangle, ValueTracker,
    VGroup, VMobject, always_redraw, linear, there_and_back, wiggle, LEFT, DOWN, PI,
)
import numpy as np

from fabrica import CORES, DADOS, EIXO, CenaContinua, Eixo, plano, rotulo
from visual import (
    COLORS, CORAL, CYAN, FUNDO, GOLD, GREEN, GRID, HERE, INK, MUTED, axes, dots, left, pos, pt, read_json,
    staircase, text,
)

T = read_json(HERE / "data" / "trace_moead.json")
PLANOS, EVENTOS, DIR, DEST = T["planos"], T["eventos"], T["direcoes"], T["destaques"]
H, CUSTO, P_, VIZ = T["horizon"], T["max_cost"], T["demonstracao"]["population_size"], T["demonstracao"]["n_neighbors"]
COR = COLORS["moead"]
EIXO2 = Eixo(-6.0, .225, (1.5, .8, .1), .42, 24)
XMAX, YMAX = 23.7, 1480
ZOOM = (20.7, 1192)
REDUZ = 1.16


def ideal(f):
    return f[0] * H, f[1] * CUSTO


def custo(i):
    return PLANOS[i]["cmax"], PLANOS[i]["tec"]


def moeda(i):
    return f"{custo(i)[0]} h · $ {pt(custo(i)[1], 1)}"


def grande():
    return axes((10, 24, 2), (400, 1500, 300), center=(3.3, -.3), width=5.4, height=3.9,
                x_label="Cmax (h)", y_label="TEC ($)", numbers=True)


def perto():
    return axes((12, 21, 2), (900, 1200, 100), center=(3.3, -.3), width=5.4, height=3.9,
                x_label="Cmax (h)", y_label="TEC ($)", numbers=True)


def pequeno():
    return axes((10, 24, 2), (400, 900, 100), center=(5.02, .35), width=2.75, height=2.7,
                x_label="Cmax (h)", y_label="TEC ($)", numbers=True)


def fim_feixe(w, z, lim=(XMAX, YMAX)):
    """Encontro do feixe com a borda; nele os dois lados ponderados são iguais."""
    d = (w[1] * H, w[0] * CUSTO)
    t = min([(m - a) / b for m, a, b in ((lim[0], z[0], d[0]), (lim[1], z[1], d[1])) if b > 1e-9])
    return z[0] + t * d[0], z[1] + t * d[1]


def cunha(axis, w, z, opacity=.35, cor=COR, graus=1.5, lim=(XMAX, YMAX)):
    a, b = axis.c2p(*z), axis.c2p(*fim_feixe(w, z, lim))
    v = b - a
    side = np.array([-v[1], v[0], 0]) * np.tan(graus * PI / 180)
    return Polygon(a, b + side, b - side, stroke_width=0, fill_color=cor, fill_opacity=opacity)


def lado_tecla(k):
    # Mesma ordem do leque na tela: tempo à esquerda, energia à direita.
    return -5.94 + (P_ - 1 - k) * .40


class Gantt:
    """Barras por tarefa; ir() devolve as transformações para outro plano."""

    def __init__(self, p, eixo):
        self.eixo, self.tarefas, self.setups, self.esperas = eixo, {}, {}, {}
        for b in p["blocks"]:
            self.tarefas[b["job"]], self.setups[b["job"]] = eixo.bloco(b), eixo.setup(b)
            self.esperas[b["job"]] = eixo.espera(b)

    def todos(self):
        return [*self.setups.values(), *self.esperas.values(), *self.tarefas.values()]

    def ir(self, p, eixo=None, jobs=None):
        self.eixo = eixo or self.eixo
        return [Transform(m[b["job"]], f(b)) for b in p["blocks"] if jobs is None or b["job"] in jobs
                for m, f in ((self.setups, self.eixo.setup), (self.esperas, self.eixo.espera),
                             (self.tarefas, self.eixo.bloco))]


def mini(p, x, y=-2.06, cor=GRID):
    eixo = Eixo(x - .48, .96 / 24, (y + .22, y, y - .22), .14, 24)
    caixa = RoundedRectangle(width=1.06, height=.78, corner_radius=.06, stroke_color=cor, stroke_width=1.5,
                             fill_color=FUNDO, fill_opacity=1).move_to(pos(x, y))
    barras = VGroup(*(eixo.caixa(b["machine"], b["start"], b["end"], DADOS["factor"][b["mode"]],
                                 fill_color=CORES[b["job"]]) for b in sorted(p["blocks"], key=lambda b: b["job"])))
    return VGroup(caixa, barras)


def rodape():
    c = T["demonstracao"]
    return left(text(f"Demonstração · instância didática · {c['population_size']} feixes · {c['n_neighbors']} vizinhos"
                     f" · seed {c['seed']} (caso escolhido) · {c['max_evaluations']} avaliações", 17, MUTED), -6.55, -3.60)


class Palco(CenaContinua):
    total = 3
    lim = (XMAX, YMAX)

    def iniciar(self, titulo=None):
        self.abrir(titulo)
        self.remove(self.cabecalho)
        # Troca só o texto do rodapé padrão.
        self.cabecalho.submobjects[4] = rodape()
        self.add(self.cabecalho)
        self.conta = None

    def moldura(self):
        """Faixas e máquinas reduzidas, com o horizonte inteiro de 24 h."""
        return dict(faixa=EIXO2.faixa_ponta(), trilhos=EIXO2.trilhos(), horas=EIXO2.horas(-.46, 2, 13),
                    maquinas=VGroup(*(text(f"M{i + 1}", 18, MUTED).move_to(pos(-6.32, y))
                                      for i, y in enumerate(EIXO2.faixas))))

    def contador(self, valor):
        self.aval = ValueTracker(valor)
        nome = text("avaliações", 18, MUTED).move_to(pos(5.15, 3.52))
        numero = always_redraw(lambda: rotulo(str(round(self.aval.get_value())), 30, COR, True).move_to(pos(6.2, 3.52)))
        self.conta = VGroup(nome), numero
        return self.conta

    def contar(self, n):
        return self.aval.animate.set_value(n)

    def estrela_em(self, z):
        return Star(4, outer_radius=.17, inner_radius=.06, stroke_width=0, fill_color=INK,
                    fill_opacity=1).move_to(self.axis.c2p(*z))

    def leque(self, opacity=.45):
        def desenhar():
            z = self.axis.p2c(self.estrela.get_center())[:2]
            g = VGroup()
            for w in DIR:
                fim = self.axis.c2p(*fim_feixe(w, z, self.lim))
                g.add(Line(self.estrela.get_center(), fim, color=COR, stroke_width=1.5, stroke_opacity=opacity),
                      Dot(fim, radius=.045, color=COR))
            return g
        return always_redraw(desenhar)

    def holofotes(self, ks, opacity=.35):
        return always_redraw(lambda: VGroup(*(cunha(self.axis, DIR[k], self.axis.p2c(self.estrela.get_center())[:2], opacity)
                                              for k in ks)))

    def pontos_de(self, pop):
        return VGroup(*(Dot(self.axis.c2p(*custo(i)), radius=.07, color=COR).set_stroke(FUNDO, 1) for i in pop))

    def mover(self, pop, ks=None):
        return [self.pontos[k].animate.move_to(self.axis.c2p(*custo(pop[k])))
                for k in (range(P_) if ks is None else ks)
                if np.linalg.norm(self.pontos[k].get_center() - self.axis.c2p(*custo(pop[k]))) > 1e-6]

    def mover_ideal(self, e):
        z = self.axis.c2p(*ideal(e["ideal_depois"]))
        return [self.estrela.animate.move_to(z)] if np.linalg.norm(z - self.estrela.get_center()) > 1e-6 else []

    def montar(self, pop, f, ativo, zoom=False):
        self.m = self.moldura()
        self.axis, self.rotulos = perto() if zoom else grande()
        self.lim = ZOOM if zoom else (XMAX, YMAX)
        self.estrela = self.estrela_em(ideal(f))
        self.fan = self.leque()
        self.pontos = self.pontos_de(pop)
        self.extremos = extremos()
        self.g = Gantt(PLANOS[ativo], EIXO2)
        if zoom:
            donos = [l["feixe"] for l in T["medidas"][0]["linhas"]]
            self.pontos = VGroup(*(p for k, p in enumerate(self.pontos) if k in donos))
            self.lupa = lupa()
        self.add(*self.m.values(), self.axis, self.rotulos, self.fan, self.lupa if zoom else self.extremos,
                 self.pontos, self.estrela, *self.g.todos())

    def criar_teclas(self):
        self.teclas = VGroup(*(RoundedRectangle(width=.33, height=.44, corner_radius=.05, stroke_color=COR, stroke_width=1.2,
                                                fill_color=GRID, fill_opacity=.45).move_to(pos(lado_tecla(k), -1.24)) for k in range(P_)))
        self.tecla_nomes = VGroup(left(text("só tempo", 14, MUTED), -6.1, -.87),
                                  text("só energia", 14, MUTED).move_to(pos(-.17, -.87), aligned_edge=-LEFT))
        return self.teclas, self.tecla_nomes

    def pintar(self, ks, cor, opacity=.9):
        return [self.teclas[k].animate.set_fill(cor, opacity) for k in ks]

    def normal(self, ks=range(P_)):
        return self.pintar(ks, GRID, .45)

    def acelerar(self, n0, n1, passo, dt, foco=None):
        """Estado real ao fim de cada bloco de eventos, com os feixes trocados acesos."""
        n = n0
        while n < n1:
            fim = min(n + passo, n1)
            e = EVENTOS[fim - 1]
            mudou = sorted({k for x in EVENTOS[n:fim] for k in x["trocados"]})
            fora = [k for k in range(P_) if k not in mudou]
            anims = [*self.mover(e["pop_depois"]), *self.mover_ideal(e), self.contar(e["avaliacao"]),
                     *self.pintar(mudou, COR), *self.normal(fora)]
            if foco is not None and e["pop_depois"][foco] != self.exibido:
                self.exibido = e["pop_depois"][foco]
                anims += self.g.ir(PLANOS[self.exibido])
            self.play(*anims, run_time=dt, rate_func=linear)
            n = fim


def extremos():
    return VGroup(text("só tempo", 15, COR).move_to(pos(2.2, 1.93)), text("só energia", 15, COR).move_to(pos(5.62, -2.68)))


def lupa():
    return text("zoom no ideal", 16, MUTED).move_to(pos(5.35, 1.95))


class Medida:
    """Réguas ponderadas e contornos em L, ligados a um peso contínuo."""

    LINHAS = (("A", -1.40), ("B", -2.16))
    X0, ESCALA = -4.9, 34

    def __init__(self, cena, peso):
        self.c, self.w = cena, peso
        self.z = T["ideal0"]
        self.planos = [r["plano"] for r in T["medidas"][0]["linhas"]]

    def lados(self, i):
        f = custo(self.planos[i])
        w = self.w.get_value()
        return abs(f[0] / H - self.z[0]) * w, abs(f[1] / CUSTO - self.z[1]) * (1 - w)

    def barras(self, i):
        _, y = self.LINHAS[i]
        lados = self.lados(i)
        maior = int(lados[1] > lados[0])
        g = VGroup()
        for j, (v, cor) in enumerate(zip(lados, (CYAN, GOLD))):
            aceso = j == maior
            r = Rectangle(width=max(.02, v * self.ESCALA), height=.23, fill_color=cor, fill_opacity=1 if aceso else .22,
                          stroke_color=INK, stroke_width=2 if aceso else 0)
            g.add(left(r, self.X0, y - .28 * j))
        valor = rotulo(pt(max(lados) + 1e-12, 4), 24, INK, True)
        g.add(valor.move_to(pos(self.X0 + max(lados) * self.ESCALA + .58, y - .28 * maior)))
        return g

    def melhor(self):
        i = int(max(self.lados(1)) < max(self.lados(0)))
        y = self.LINHAS[i][1]
        return RoundedRectangle(width=5.75, height=.72, corner_radius=.08, stroke_color=GREEN,
                                stroke_width=2.5).move_to(pos(-3.2, y - .14))

    def contorno(self, i):
        w, g = self.w.get_value(), max(self.lados(i))
        z = ideal(self.z)
        x, y = z[0] + g / w * H, z[1] + g / (1 - w) * CUSTO
        a = self.c.axis
        return VMobject(stroke_color=INK, stroke_width=3, stroke_opacity=.8).set_points_as_corners(
            [a.c2p(z[0], y), a.c2p(x, y), a.c2p(x, z[1])])

    def feixe(self):
        w = self.w.get_value()
        return cunha(self.c.axis, (w, 1 - w), ideal(self.z), .5, lim=self.c.lim)

    def peso(self):
        w = self.w.get_value()
        return VGroup(left(rotulo("peso", 19, MUTED), -6.0, -.93), left(rotulo(f"tempo {pt(w, 2)}", 21, CYAN, True), -4.9, -.93),
                      left(rotulo(f"custo {pt(1 - w, 2)}", 21, GOLD, True), -3.2, -.93))

    def nomes(self):
        return [left(text(n, 26, INK, bold=True), -5.75, y - .14) for n, y in self.LINHAS]

    def letras(self):
        a = self.c.axis
        return VGroup(*(text(n, 22, INK, bold=True).move_to(a.c2p(*custo(i)) + d) for (n, _), i, d in
                        zip(self.LINHAS, self.planos, (pos(.24, -.24), pos(.26, -.24)))))

    def reguas(self, i):
        a, z, f = self.c.axis, ideal(self.z), custo(self.planos[i])
        o, x, y = a.c2p(*z), a.c2p(f[0], z[1]), a.c2p(z[0], f[1])
        estilo = dict(height=.1, stroke_width=0, fill_opacity=1)
        tempo = Rectangle(width=max(.02, x[0] - o[0]), fill_color=CYAN, **estilo).move_to(o, aligned_edge=LEFT)
        gasto = Rectangle(width=max(.02, y[1] - o[1]), fill_color=GOLD, **estilo).rotate(PI / 2).move_to((o + y) / 2)
        return tempo, gasto


FRASE = (-3.2, -3.06)


def frase(valor, cor=INK):
    return text(valor, 25, cor, bold=True, width=6.0).move_to(pos(*FRASE))


def quadro_medida(cena):
    """Quadro final de MoeadLeque, refeito na cena seguinte."""
    m = Medida(cena, ValueTracker(T["medidas"][1]["peso"][0]))
    return [m.feixe(), m.contorno(0), m.contorno(1), m.letras(), m.peso(), *m.nomes(), m.barras(0), m.barras(1),
            m.melhor(), frase("a maior das duas")]


class MoeadLeque(Palco):
    chapter, number = "META-HEURÍSTICA · MOEA/D", 1

    def construct(self):
        self.iniciar()
        faixa, trilhos, maquinas, horas, linha, rotulos = self.base()
        inicio = plano(15)
        self.g = Gantt(inicio, EIXO)
        eixo0, nomes0 = pequeno()
        ponto = Dot(eixo0.c2p(inicio["cmax"], inicio["tec"]), radius=.11, color=GOLD)
        self.add(faixa, trilhos, maquinas, horas, linha, rotulos, eixo0, nomes0, *self.g.todos(), ponto)
        self.beat("direcoes", "E se dividíssemos a pergunta?")
        self.m = self.moldura()
        self.axis, self.rotulos = grande()
        z15 = (inicio["cmax"], inicio["tec"])
        self.play(*(ReplacementTransform(a, self.m[n]) for a, n in ((faixa, "faixa"), (trilhos, "trilhos"), (horas, "horas"))),
                  FadeOut(maquinas), FadeIn(self.m["maquinas"]), FadeOut(linha), FadeOut(rotulos), FadeOut(nomes0),
                  ReplacementTransform(eixo0, self.axis), FadeIn(self.rotulos), *self.g.ir(inicio, EIXO2),
                  ponto.animate.move_to(self.axis.c2p(*z15)), run_time=1.4)
        # O leque abre do ponto conhecido: ainda não há população nem ideal.
        raios = VGroup(*(VGroup(Line(self.axis.c2p(*z15), self.axis.c2p(*fim_feixe(w, z15)), color=COR, stroke_width=1.5, stroke_opacity=.6),
                                Dot(self.axis.c2p(*fim_feixe(w, z15)), radius=.045, color=COR)) for w in reversed(DIR)))
        self.extremos = extremos()
        fr = frase("um peso, um plano")
        self.play(LaggedStart(*(GrowFromPoint(r, self.axis.c2p(*z15)) for r in raios), lag_ratio=.08), run_time=2.2)
        self.play(FadeIn(self.extremos), FadeIn(fr), ponto.animate.set_opacity(.35).scale(.7), run_time=.4)
        pop = T["inicial"]
        self.pontos = self.pontos_de(pop)
        self.estrela = self.estrela_em(z15)
        self.fan = self.leque()
        self.add(self.fan)
        self.remove(raios, *raios)
        origem = VGroup(*self.g.tarefas.values()).get_center()
        self.play(*self.g.ir(PLANOS[pop[0]]), run_time=.5)
        for a, b in ((0, 7), (7, 15)):
            self.play(LaggedStart(*(FadeIn(self.pontos[k], target_position=origem) for k in range(a, b)), lag_ratio=.25),
                      *self.g.ir(PLANOS[pop[b - 1]]), run_time=1.6)
        fios = VGroup(*(Line(self.axis.c2p(*fim_feixe(w, z15)), p.get_center(), color=COR, stroke_width=1, stroke_opacity=.5)
                        for w, p in zip(DIR, self.pontos)))
        self.play(LaggedStart(*(Create(f) for f in fios), lag_ratio=.05), run_time=.9)
        self.wait(.4)
        # O menor de cada objetivo na população define o ideal; o leque desliza para lá.
        z = ideal(T["ideal0"])
        guias = VGroup(DashedLine(self.axis.c2p(z[0], 400), self.axis.c2p(z[0], YMAX), color=CYAN, stroke_width=2),
                       DashedLine(self.axis.c2p(10, z[1]), self.axis.c2p(XMAX, z[1]), color=GOLD, stroke_width=2))
        self.play(Create(guias[0]), Create(guias[1]), FadeOut(fios), run_time=.7)
        self.play(self.estrela.animate.move_to(self.axis.c2p(*z)), FadeOut(ponto), run_time=1.8)
        self.add(self.estrela)
        self.play(FadeOut(guias), Flash(self.estrela.get_center(), color=INK, line_length=.12), run_time=.5)
        k0 = T["medidas"][0]["k"]
        foco = self.holofotes([k0], .5)
        self.play(FadeIn(foco), run_time=.4)
        self.hold()

        self.beat("medida", "Como um feixe mede um plano?", fr)
        peso = ValueTracker(T["medidas"][0]["peso"][0])
        m = Medida(self, peso)
        donos = [r["feixe"] for r in T["medidas"][0]["linhas"]]
        # A vista se aproxima do ideal; os outros planos ficam fora da janela e voltam na cena seguinte.
        axis2, rot2 = perto()
        alvo = {k: axis2.c2p(*custo(T["inicial"][k])) for k in donos}
        self.play(FadeOut(foco), FadeOut(self.fan), FadeOut(self.extremos),
                  *(FadeOut(p) for k, p in enumerate(self.pontos) if k not in donos), run_time=.4)
        antigos = (self.axis, self.rotulos)
        self.axis, self.rotulos, self.lim = axis2, rot2, ZOOM
        self.play(ReplacementTransform(antigos[0], axis2), FadeOut(antigos[1]), FadeIn(rot2), FadeIn(lupa()),
                  *(self.pontos[k].animate.move_to(alvo[k]) for k in donos),
                  self.estrela.animate.move_to(axis2.c2p(*ideal(T["ideal0"]))), *self.g.ir(PLANOS[m.planos[0]]), run_time=1)
        self.fan = self.leque()
        feixe, ps, letras = always_redraw(m.feixe), always_redraw(m.peso), m.letras()
        self.play(FadeIn(self.fan), FadeIn(feixe), FadeIn(ps), FadeIn(letras), self.pontos[donos[0]].animate.scale(1.5), run_time=.5)
        self.add(*(self.pontos[k] for k in donos), self.estrela)
        nomes, barras, contornos = m.nomes(), [], []
        fr = frase("a maior das duas")
        for i, vel in ((0, 1.0), (1, .7)):
            if i:
                self.play(*self.g.ir(PLANOS[m.planos[1]]), self.pontos[donos[1]].animate.scale(1.5), run_time=.6)
            tempo, gasto = m.reguas(i)
            self.play(GrowFromEdge(tempo, LEFT), FadeIn(nomes[i]), run_time=.6 * vel)
            self.play(GrowFromEdge(gasto, DOWN), run_time=.6 * vel)
            alvo = m.barras(i)
            self.play(ReplacementTransform(tempo, alvo[0]), ReplacementTransform(gasto, alvo[1], path_arc=-PI / 2), FadeIn(alvo[2]), run_time=.9 * vel)
            self.remove(*alvo, alvo)
            viva = always_redraw(lambda i=i: m.barras(i))
            barras.append(viva)
            self.add(viva)
            cont = always_redraw(lambda i=i: m.contorno(i))
            contornos.append(cont)
            esboco = m.contorno(i)
            self.play(Create(esboco), *([FadeIn(fr)] if not i else []), run_time=.8 * vel)
            self.remove(esboco)
            self.add(cont)
            self.wait(.3)
        melhor = m.melhor()
        self.play(Create(melhor), run_time=.5)
        self.wait(.6)
        # Os mesmos dois planos, outro peso: a régua vencedora e o melhor plano se invertem.
        self.remove(melhor)
        vivo = always_redraw(m.melhor)
        self.add(vivo)
        self.play(peso.animate.set_value(T["medidas"][1]["peso"][0]), run_time=3.2)
        self.wait(.4)
        # Congela os valores ligados ao peso antes da verificação final.
        fixo = quadro_medida(self)[:-1]
        self.remove(feixe, ps, *barras, *contornos, vivo, letras, *nomes)
        self.add(*fixo, self.estrela)
        self.hold()


class MoeadVizinhos(Palco):
    chapter, number = "META-HEURÍSTICA · MOEA/D", 2

    def construct(self):
        self.iniciar("Como um feixe mede um plano?")
        self.montar(T["inicial"], T["ideal0"], T["medidas"][0]["linhas"][1]["plano"], zoom=True)
        for p in self.pontos:
            p.scale(1.5)
        resto = quadro_medida(self)
        self.add(*resto, self.estrela)
        self.pais(resto)
        self.cascata()
        self.inviavel()

    def marcador(self):
        """Régua do sorteio: 90% vizinhança, 10% população inteira."""
        prob = T["demonstracao"]["prob_neighbor_mating"]
        x0, largura, y = -6.0, 5.6, -2.0
        dentro = left(Rectangle(width=largura * prob, height=.26, stroke_width=0, fill_color=COR, fill_opacity=.75), x0, y)
        fora = left(Rectangle(width=largura * (1 - prob), height=.26, stroke_width=0, fill_color=CORAL, fill_opacity=.75),
                    x0 + largura * prob, y)
        nomes = VGroup(text("pais da vizinhança", 17, FUNDO, bold=True).move_to(dentro),
                       text("todos", 14, FUNDO, bold=True).move_to(fora))
        agulha = Triangle(stroke_width=0, fill_color=INK, fill_opacity=1).scale(.11).rotate(0).move_to(pos(x0, y - .30))
        return VGroup(dentro, fora, nomes), agulha, lambda v: pos(x0 + largura * v, y - .30)

    def pais(self, resto):
        self.beat("pais", "De quem vem o próximo plano?", *resto)
        teclas, tn = self.criar_teclas()
        conta = self.contador(P_)
        # Volta à visão geral.
        z, axis2 = ideal(T["ideal0"]), grande()
        ab = sorted(l["feixe"] for l in T["medidas"][0]["linhas"])
        todos = VGroup(*(Dot(axis2[0].c2p(*custo(i)), radius=.07, color=COR).set_stroke(FUNDO, 1) for i in T["inicial"]))
        antigos = (self.axis, self.rotulos)
        self.play(FadeOut(self.fan), FadeOut(self.lupa), run_time=.3)
        self.axis, self.rotulos = axis2
        self.lim = (XMAX, YMAX)
        self.play(ReplacementTransform(antigos[0], self.axis), FadeOut(antigos[1]), FadeIn(self.rotulos),
                  *(ReplacementTransform(p, todos[k]) for p, k in zip(self.pontos, ab)),
                  *(FadeIn(d) for k, d in enumerate(todos) if k not in ab),
                  self.estrela.animate.move_to(self.axis.c2p(*z)), run_time=.9)
        self.pontos, self.fan, self.extremos = todos, self.leque(), extremos()
        self.play(FadeIn(self.fan), FadeIn(self.extremos), run_time=.3)
        self.add(*self.pontos, self.estrela)
        # As teclas são os próprios feixes: saem das pontas do leque.
        self.play(LaggedStart(*(GrowFromPoint(teclas[k], self.axis.c2p(*fim_feixe(DIR[k], z))) for k in range(P_)), lag_ratio=.03),
                  FadeIn(tn), *(FadeIn(c) for c in conta), run_time=1)
        regua, agulha, onde = self.marcador()
        self.play(FadeIn(regua), FadeIn(agulha), run_time=.4)
        fr = frase("vizinhos, 90% das vezes")
        self.exibido = None
        # Os primeiros oito subproblemas da varredura, na ordem sorteada real.
        for e in EVENTOS[:DEST["fuga"]]:
            self.play(*self.pintar([e["k"]], COR), agulha.animate.move_to(onde(e["sorteio"])), *self.mover(e["pop_depois"]),
                      *self.g.ir(PLANOS[e["plano"]]), self.contar(e["avaliacao"]), run_time=.3)
            self.teclas[e["k"]].set_fill(GRID, .45)
        # Pulo 1: o sorteio escapa; pulo 2: vizinhos, sem melhora.
        for n, dt in ((DEST["fuga"], .7), (DEST["cinza"], .45)):
            e = EVENTOS[n]
            luz = self.holofotes([e["k"]], .5)
            coral = [k for k in e["vizinhos"] if k != e["k"]]
            self.play(*self.pintar([e["k"]], INK, 1), *self.pintar(coral, COR, .55), FadeIn(luz), run_time=dt)
            self.play(agulha.animate.move_to(onde(e["sorteio"])), *([FadeIn(fr)] if fr not in self.mobjects else []), run_time=dt)
            arcos = VGroup(*(Line(self.teclas[q].get_top(), self.teclas[e["k"]].get_top(),
                                  color=CORAL if not e["local"] else COR, stroke_width=4, path_arc=-.9 if q > e["k"] else .9)
                             for q in e["pais"] if q != e["k"]))
            self.play(Create(arcos), *(self.pontos[q].animate.scale(1.6) for q in e["pais"]), run_time=dt)
            aro = Dot(self.axis.c2p(*custo(e["plano"])), radius=.08, color=MUTED)
            self.play(FadeIn(aro), *self.g.ir(PLANOS[e["plano"]]), self.contar(e["avaliacao"]), *self.pintar(e["vizinhos"], MUTED, .8), run_time=.35)
            self.play(FadeOut(aro), FadeOut(arcos), FadeOut(luz), *self.normal(),
                      *(self.pontos[q].animate.scale(1 / 1.6) for q in e["pais"]), run_time=.35)
        # Pulo 3: câmera lenta no subproblema da cascata.
        e = EVENTOS[DEST["cascata"]]
        self.e, self.ordem = e, sorted(e["vizinhos"], reverse=True)
        self.luz = self.holofotes(self.ordem, .20)
        self.play(*self.pintar([e["k"]], INK, 1), *self.pintar([k for k in self.ordem if k != e["k"]], COR, .55),
                  agulha.animate.move_to(onde(e["sorteio"])), FadeIn(self.luz), run_time=.8)
        self.minis = self.criar_minis(e["pop_antes"], self.ordem)
        self.play(FadeOut(regua), FadeOut(agulha), *(x.animate.set_opacity(.12) for x in self.g.todos()),
                  *(p.animate.set_opacity(.15) for k, p in enumerate(self.pontos) if k not in self.ordem),
                  LaggedStart(*(GrowFromPoint(self.minis[k], self.teclas[k].get_center()) for k in self.ordem), lag_ratio=.1), run_time=.9)
        a, b = e["pais"]
        cores = {a: CYAN, b: CORAL}
        self.play(*(self.minis[q][0].animate.set_stroke(cores[q], 4) for q in (a, b)), run_time=.4)
        # Cada tarefa vem de um dos pais, conforme o sorteio real do cruzamento.
        cruz = PLANOS[e["cruzado"]]
        velho = self.g
        self.g = Gantt(cruz, EIXO2)
        voos = [TransformFromCopy(self.minis[e["pais"][e["origem"][j]]][1][j], t[0]) for j, t in sorted(self.g.tarefas.items())]
        self.vago = Dot(self.axis.c2p(*custo(e["cruzado"])), radius=.1, fill_opacity=0, stroke_color=INK, stroke_width=3)
        self.play(*(FadeOut(x) for x in velho.todos()), LaggedStart(*voos, lag_ratio=.12), run_time=1.6)
        self.remove(*(t[0] for t in self.g.tarefas.values()))
        self.add(*self.g.todos())
        self.play(FadeIn(self.vago), *(FadeIn(x) for x in (*self.g.setups.values(), *self.g.esperas.values())), run_time=.4)
        # Realocação: antecipação, salto com mudança de largura e consequência.
        filho = PLANOS[e["filho"]]
        antes = {b_["job"]: b_["machine"] for b_ in cruz["blocks"]}
        movida = next(x["job"] for x in filho["blocks"] if x["machine"] != antes[x["job"]])
        destino = next(x["machine"] for x in filho["blocks"] if x["job"] == movida)
        abrir = {x["job"] for x in filho["blocks"] if x["machine"] == destino and x["job"] != movida}
        self.realocar(filho, movida, abrir, lambda: [self.vago.animate.move_to(self.axis.c2p(*custo(e["filho"])))])
        self.frase = fr
        self.hold()

    def realocar(self, alvo, job, abrir, junto=lambda: []):
        bar = self.g.tarefas[job]
        self.bring_to_front(bar)
        self.play(bar.animate.shift(pos(0, .22)), run_time=.3)
        b = next(x for x in alvo["blocks"] if x["job"] == job)
        self.play(Transform(bar, EIXO2.bloco(b), path_arc=-.8), *self.g.ir(alvo, jobs=abrir), run_time=1)
        self.play(*self.g.ir(alvo), *junto(), run_time=.6)

    def criar_minis(self, pop, ordem):
        return {k: mini(PLANOS[pop[k]], -5.52 + REDUZ * i) for i, k in enumerate(ordem)}

    def barra_valor(self, i, v, cor, dx):
        # Altura proporcional ao Tchebycheff; base comum acima do rodapé.
        return Rectangle(width=.15, height=max(.012, v * 2.8), stroke_width=0, fill_color=cor,
                         fill_opacity=1).move_to(pos(-5.52 + REDUZ * i + dx, -3.24), aligned_edge=DOWN)

    def numero_valor(self, i, v, cor, lado):
        return text(pt(v, 3), 14, cor, bold=True).move_to(pos(-5.52 + REDUZ * i + .27 * lado, -2.64))

    def valores(self, e, campo, cor, lado):
        pos_ = {k: i for i, k in enumerate(self.ordem)}
        dic = dict(zip(e["vizinhos"], e[campo]))
        return {k: VGroup(self.barra_valor(i, dic[k], cor, .27 * lado), self.numero_valor(i, dic[k], cor, lado))
                for k, i in pos_.items()}

    def cascata(self):
        e = self.e
        self.beat("cascata", "Um filho pode servir a quantos?", self.frase)
        valor = text(moeda(e["filho"]), 21, GREEN, bold=True).next_to(self.vago, pos(1, -.6), buff=.10)
        # O filho é avaliado só agora, depois da mutação.
        filho = Dot(self.axis.c2p(*custo(e["filho"])), radius=.11, color=GREEN)
        self.play(ReplacementTransform(self.vago, filho), FadeIn(valor), self.contar(e["avaliacao"]), run_time=.6)
        velhos = self.valores(e, "g_ideal_anterior", MUTED, -1)
        self.play(*(FadeIn(velhos[k]) for k in self.ordem), run_time=.6)
        self.wait(.3)
        # Primeiro o ideal desce e os valores antigos são recalculados.
        novos = self.valores(e, "g_antes", MUTED, -1)
        guia = DashedLine(self.axis.c2p(13, custo(e["filho"])[1]), filho.get_center(), color=GOLD, stroke_width=2)
        aviso = text("ideal desce", 18, INK, bold=True).move_to(self.axis.c2p(*ideal(e["ideal_depois"])) + pos(0, -.32))
        self.play(Create(guia), FadeIn(aviso), run_time=.6)
        self.play(*self.mover_ideal(e), *(Transform(velhos[k][0], novos[k][0]) for k in self.ordem),
                  *(FadeOut(velhos[k][1]) for k in self.ordem), run_time=2)
        self.wait(.3)
        self.play(*(FadeIn(novos[k][1]) for k in self.ordem), FadeOut(guia), FadeOut(aviso), run_time=.4)
        self.wait(.4)
        # Depois, a comparação real do filho com cada vizinho.
        meus = self.valores(e, "g_filho", GREEN, 1)
        self.remove(*(m for k in self.ordem for m in velhos[k]))
        self.add(*(novos[k] for k in self.ordem))
        for k in self.ordem:
            raio = cunha(self.axis, DIR[k], ideal(e["ideal_depois"]), .6, INK)
            self.play(FadeIn(raio, rate_func=there_and_back), FadeIn(meus[k], shift=pos(0, -.1)), run_time=.85)
            self.remove(raio)
        self.wait(.7)
        # A cascata: todos trocam no mesmo passo; a onda de 0,08 s só torna a troca visível.
        acesos = [cunha(self.axis, DIR[k], ideal(e["ideal_depois"]), .55, GREEN) for k in self.ordem]
        alvo = {k: mini(PLANOS[e["plano"]], -5.52 + REDUZ * i, cor=GREEN) for i, k in enumerate(self.ordem)}
        self.remove(self.luz)
        lag = .08
        anims = [AnimacaoConjunta(Transform(self.minis[k], alvo[k]), FadeIn(acesos[i]),
                                  self.teclas[k].animate.set_fill(GREEN, 1).shift(pos(0, .08)),
                                  self.pontos[k].animate.move_to(self.axis.c2p(*custo(e["plano"]))).set_color(GREEN))
                 for i, k in enumerate(self.ordem)]
        self.play(LaggedStart(*anims, lag_ratio=lag / .6), run_time=.6 + 4 * lag)
        n = text(f"{len(e['trocados'])} de {len(e['vizinhos'])}", 40, GREEN, bold=True).move_to(pos(5.0, 1.45))
        self.play(FadeIn(n, scale=1.4), Flash(filho.get_center(), color=GREEN, line_length=.2, flash_radius=.25), run_time=.5)
        fr = text("substitui todos que melhora", 23, INK, bold=True).move_to(pos(4.05, .98))
        self.play(FadeIn(fr), run_time=.4)
        self.wait(1.3)

        # Segunda ocorrência, em velocidade normal: aqui nem todos melhoram.
        e2 = EVENTOS[DEST["parcial"]]
        ordem_velha, self.ordem = self.ordem, sorted(e2["vizinhos"], reverse=True)
        novas = self.criar_minis(e2["pop_antes"], self.ordem)
        luz = self.holofotes(self.ordem, .20)
        self.play(FadeOut(n), FadeOut(valor), FadeOut(filho), *(FadeOut(a) for a in acesos),
                  *(FadeOut(x) for k in ordem_velha for x in (novos[k], meus[k], self.minis[k])),
                  *(self.teclas[k].animate.set_fill(GRID, .45).shift(pos(0, -.08)) for k in ordem_velha),
                  *(p.animate.set_opacity(1 if k in self.ordem else .15).set_color(COR) for k, p in enumerate(self.pontos)), run_time=.5)
        self.play(FadeIn(luz), *(FadeIn(novas[k]) for k in self.ordem), *self.g.ir(PLANOS[e2["filho"]]),
                  *self.pintar([k for k in self.ordem if k != e2["k"]], COR, .55), *self.pintar([e2["k"]], INK, 1), run_time=.7)
        filho = Dot(self.axis.c2p(*custo(e2["filho"])), radius=.11, color=GREEN)
        a_, b_ = self.valores(e2, "g_antes", MUTED, -1), self.valores(e2, "g_filho", GREEN, 1)
        for k in self.ordem:
            if k not in e2["trocados"]:
                b_[k].set_color(MUTED)
        self.play(FadeIn(filho), self.contar(e2["avaliacao"]), *(FadeIn(x[k]) for x in (a_, b_) for k in self.ordem), run_time=.6)
        self.wait(.3)
        sim = [k for k in self.ordem if k in e2["trocados"]]
        nao = [k for k in self.ordem if k not in e2["trocados"]]
        self.play(LaggedStart(*(AnimacaoConjunta(
            Transform(novas[k], mini(PLANOS[e2["plano"]], -5.52 + REDUZ * self.ordem.index(k), cor=GREEN)),
            self.teclas[k].animate.set_fill(GREEN, 1), self.pontos[k].animate.move_to(filho.get_center())) for k in sim), lag_ratio=lag / .6),
            *self.pintar(nao, MUTED, .7), run_time=.8)
        n = text(f"{len(sim)} de {len(e2['vizinhos'])}", 40, GREEN, bold=True).move_to(pos(5.0, 1.45))
        self.play(FadeIn(n, scale=1.3), *(novas[k].animate.set_opacity(.3) for k in nao), run_time=.4)
        self.hold()
        self.limpar = [n, fr, filho, luz, *(x[k] for x in (a_, b_, novas) for k in self.ordem)]

    def inviavel(self):
        self.beat("inviavel", "E quando o plano não cabe?", *self.limpar)
        e = EVENTOS[DEST["rejeicao"]]
        self.play(*(p.animate.set_opacity(1).set_color(COR).set_stroke(FUNDO, 1) for p in self.pontos), *self.normal(), run_time=.3)
        self.exibido = None
        self.acelerar(DEST["parcial"] + 1, DEST["rejeicao"], 4, .09, 7)
        cruz, filho = PLANOS[e["cruzado"]], PLANOS[e["filho"]]
        luz = self.holofotes([e["k"]], .5)
        x = EIXO2.at(H)
        limite = VGroup(Line(pos(x, 1.92), pos(x, -.28), color=CORAL, stroke_width=3), text(f"{H} h", 17, CORAL, bold=True).move_to(pos(x, 2.1)))
        self.play(*self.g.ir(cruz), FadeIn(limite), FadeIn(luz), *self.normal(), *self.pintar([e["k"]], INK, 1),
                  *(self.pontos[k].animate.set_opacity(.25) for k in range(P_)), run_time=.6)
        antes = {b["job"]: b["machine"] for b in cruz["blocks"]}
        movida = next(b for b in filho["blocks"] if b["machine"] != antes[b["job"]])
        abrir = {b["job"] for b in filho["blocks"] if b["machine"] == movida["machine"] and b["job"] != movida["job"]}
        self.realocar(filho, movida["job"], abrir)
        ruim = max(filho["blocks"], key=lambda b: b["end"])
        grupo = VGroup(*self.g.todos())
        self.play(grupo.animate(rate_func=wiggle).shift(pos(.07, 0)), self.g.tarefas[ruim["job"]][0].animate.set_stroke(CORAL, 4), run_time=.45)
        # A barra racha na linha do horizonte e o filho se dissolve; a avaliação já foi gasta.
        a, b = (EIXO2.caixa(ruim["machine"], s, f, DADOS["factor"][ruim["mode"]], fill_color=CORES[ruim["job"]])
                for s, f in ((ruim["start"], H), (H, ruim["end"])))
        self.remove(grupo, *self.g.todos())
        outros = [o for o in self.g.todos() if o is not self.g.tarefas[ruim["job"]]]
        self.add(*outros, a, b)
        fr = frase("conta, mas vira cópia")
        self.play(a.animate.rotate(.12).shift(pos(-.08, .06)), b.animate.rotate(-.5).shift(pos(.06, -.25)),
                  self.contar(e["avaliacao"]), Flash(self.conta[1].get_center(), color=CORAL, line_length=.15, flash_radius=.35), run_time=.5)
        self.play(*(FadeOut(o) for o in (*outros, a, b)), FadeOut(limite), run_time=.5)
        # A cópia sai de um feixe sorteado em toda a população; não é reparo do filho.
        dono = e["copia_de"]
        self.g = Gantt(PLANOS[e["plano"]], EIXO2)
        molde = mini(PLANOS[e["plano"]], lado_tecla(dono), cor=COR)
        self.play(*self.pintar([dono], COR, 1), GrowFromPoint(molde, self.teclas[dono].get_center()),
                  self.pontos[dono].animate.set_opacity(1).scale(1.5), run_time=.5)
        por_job = sorted(self.g.tarefas)
        self.play(*(TransformFromCopy(molde[1][j], self.g.tarefas[j][0]) for j in por_job),
                  *(FadeIn(m) for m in (*self.g.setups.values(), *self.g.esperas.values())), FadeIn(fr), run_time=.7)
        self.remove(*(t[0] for t in self.g.tarefas.values()))
        self.add(*self.g.todos())
        self.play(*self.pintar(e["vizinhos"], MUTED, .9), run_time=.3)
        n = text(f"{len(e['trocados'])} de {len(e['vizinhos'])}", 34, MUTED, bold=True).move_to(pos(5.0, 1.45))
        self.play(FadeIn(n), FadeOut(molde), *self.normal(), FadeOut(luz), self.pontos[dono].animate.scale(1 / 1.5),
                  *(p.animate.set_opacity(1).set_stroke(FUNDO, 1) for p in self.pontos if p is not self.pontos[dono]), run_time=.4)
        self.hold()


class MoeadBusca(Palco):
    chapter, number = "META-HEURÍSTICA · MOEA/D", 3

    def construct(self):
        self.iniciar("E quando o plano não cabe?")
        e = EVENTOS[DEST["rejeicao"]]
        self.montar(e["pop_depois"], e["ideal_depois"], e["plano"])
        self.add(*self.criar_teclas())
        self.add(*self.contador(e["avaliacao"]))
        fr = frase("conta, mas vira cópia")
        n = text(f"{len(e['trocados'])} de {len(e['vizinhos'])}", 34, MUTED, bold=True).move_to(pos(5.0, 1.45))
        self.add(fr, n)
        self.beat("busca", "O que nasce de quinze pedidos?", fr, n)
        foco, self.exibido = 7, e["plano"]
        perdido = T["perdido"]["evento"]
        self.acelerar(DEST["rejeicao"] + 1, perdido, 15, .18, foco)
        # Surpresa: o menor custo já visto move o ideal, mas nenhum vizinho o adota.
        x = EVENTOS[perdido]
        bola = Dot(self.axis.c2p(*custo(x["plano"])), radius=.10, color=GREEN)
        legenda = text(moeda(x["plano"]), 18, GREEN, bold=True).move_to(bola.get_center() + pos(-.75, .62))
        self.play(FadeIn(bola, scale=2), FadeIn(legenda), self.contar(x["avaliacao"]), *self.mover_ideal(x),
                  *self.g.ir(PLANOS[x["plano"]]), *self.normal(), run_time=.8)
        ninguem = text(f"{len(x['trocados'])} de {len(x['vizinhos'])} · ninguém guarda", 23, MUTED, bold=True).move_to(pos(4.5, 1.45))
        self.play(*self.pintar(x["vizinhos"], MUTED, .9), bola.animate.set_color(MUTED), FadeIn(ninguem), run_time=.5)
        self.wait(.6)
        self.play(FadeOut(bola), FadeOut(legenda), FadeOut(ninguem), *self.normal(),
                  *self.g.ir(PLANOS[self.exibido]), run_time=.5)
        self.acelerar(perdido + 1, len(EVENTOS), 20, .18, foco)
        # Teclas com o mesmo plano se unem: não há eliminação de duplicatas.
        final = T["final"]
        grupos = []
        for k in reversed(range(P_)):
            if grupos and final[grupos[-1][-1]] == final[k]:
                grupos[-1].append(k)
            else:
                grupos.append([k])
        lacos = VGroup()
        for g in grupos:
            if len(g) > 1:
                a, b = lado_tecla(g[0]) - .17, lado_tecla(g[-1]) + .17
                lacos.add(VGroup(Line(pos(a, -1.60), pos(b, -1.60), color=COR, stroke_width=4),
                                 text(f"×{len(g)}", 18, COR).move_to(pos((a + b) / 2, -1.86))))
        fr = text(f"{T['planos_distintos_final']} planos em {P_} feixes", 25, INK, bold=True).move_to(pos(-3.2, -2.45))
        self.play(*(Create(l[0]) for l in lacos), *(FadeIn(l[1]) for l in lacos), FadeIn(fr), run_time=.8)
        self.wait(.7)

        # Quadro-base: a frente vem da população final, sobre a exata esmaecida.
        frente = [(p["cmax"], p["tec"]) for p in T["frente"]]
        escolhida = next(p for p in T["frente"] if p["cmax"] == 15)
        faixa, trilhos, maquinas, horas, linha, rotulos = self.base()
        axis2, nomes2 = pequeno()
        exata = [(p["cmax"], p["tec"]) for p in DADOS["front"]]
        sombra = VGroup(staircase(axis2, exata, GOLD, 2).set_stroke(opacity=.35), dots(axis2, exata, GOLD, .05).set_opacity(.35))
        # Só os pontos da frente viajam para o plano pequeno; os demais saem.
        usados, viagem = set(), []
        for k, i in enumerate(final):
            c = custo(i)
            if c in frente and c not in usados:
                usados.add(c)
                viagem.append(self.pontos[k].animate.move_to(axis2.c2p(*c)))
            else:
                viagem.append(FadeOut(self.pontos[k]))
        self.play(*(FadeOut(m) for m in (lacos, fr, self.teclas, self.tecla_nomes, self.fan, self.estrela, self.extremos,
                                         self.rotulos, *self.conta)), run_time=.5)
        self.play(*(ReplacementTransform(self.m[n], alvo) for n, alvo in (("faixa", faixa), ("trilhos", trilhos), ("horas", horas))),
                  FadeOut(self.m["maquinas"]), FadeIn(maquinas), FadeIn(linha), FadeIn(rotulos),
                  ReplacementTransform(self.axis, axis2), FadeIn(nomes2), *self.g.ir(PLANOS[escolhida["plano"]], EIXO), *viagem, run_time=1.4)
        marca = Dot(axis2.c2p(escolhida["cmax"], escolhida["tec"]), radius=.11, fill_opacity=0, stroke_color=INK, stroke_width=2.5)
        nota = text("exata", 15, GOLD).move_to(axis2.c2p(18.2, 450))
        valor = text(moeda(escolhida["plano"]), 24, COR, bold=True).move_to(pos(5.0, -2.2))
        c = T["campanha"]
        rot = VGroup(text(f"campanha: {c['population_size']} · {c['n_neighbors']}", 24, COR, bold=True),
                     text("feixes · vizinhos", 16, MUTED)).arrange(DOWN, buff=.1).move_to(pos(5.0, -2.82))
        self.play(FadeIn(marca), FadeIn(valor), FadeIn(nota), FadeIn(sombra), Create(staircase(axis2, frente, COR)), FadeIn(rot), run_time=.8)
        self.hold()


def AnimacaoConjunta(*anims):
    return AnimationGroup(*anims, run_time=.6)
