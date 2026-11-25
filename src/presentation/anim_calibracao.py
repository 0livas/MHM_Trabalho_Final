"""Calibração: mesa de som (Optuna/TPE) e torneio de orçamentos (confirmação)."""

from math import prod

from manim import (
    AnimationGroup, Circle, Create, DashedLine, Dot, Ellipse, FadeIn, FadeOut, Flash, GrowFromEdge, Indicate,
    LaggedStart, Line, Rectangle, RoundedRectangle, Square, Succession, Transform, Triangle, ValueTracker, VGroup,
    VMobject, always_redraw, linear, rate_functions, there_and_back, DOWN, LEFT, ORIGIN, PI, RIGHT, UP,
)

from fabrica import DADOS, EIXO, CenaContinua, plano, rotulo
from introducao import FRENTE, plano_objetivos
from visual import (
    COLORS, CORAL, FUNDO, GOLD, GRID, HERE, INK, MUTED,
    dots, left, pos, pt, read_json, staircase, text,
)

D = read_json(HERE / "data" / "trace_calibracao.json")
EST = D["studies"]
NOMES = {
    "population_size": "população", "crossover_probability": "cruzamento", "mutation_probability": "mutação",
    "n_neighbors": "vizinhos", "prob_neighbor_mating": "acasalamento", "initial_solutions": "partidas",
    "max_candidates_per_neighborhood": "candidatos", "shaking_attempts": "shake",
}
METODOS = ("vns_vnd", "spea2", "moead", "age")
ROTULOS = {"vns_vnd": "VNS/VND", "spea2": "SPEA2", "moead": "MOEA/D", "age": "AGE-MOEA"}
COR = {m: COLORS[m] for m in METODOS}
FONTE = "Estudos gravados em data/output/hyperparameters_tuning · Gantt: ilustração com a instância didática"


def n(valor):
    return f"{valor:g}".replace(".", ",")


def mil(valor):
    return f"{valor:,}".replace(",", ".")


# --- mesa de som -----------------------------------------------------------------------------

def y_faixa(valores, valor, y0, y1):
    return y0 + (y1 - y0) * valores.index(valor) / (len(valores) - 1)


def faixa(x, y0, y1, chave, valores, valor, cor, esp, size):
    """trilho, degraus, valores, nome, botão (índice 4)."""
    trilho = Line(pos(x, y0 - .1), pos(x, y1 + .1), color=GRID, stroke_width=5)
    ys = [y_faixa(valores, v, y0, y1) for v in valores]
    degraus = VGroup(*(Line(pos(x - .1, y), pos(x + .1, y), color=MUTED, stroke_width=1.5) for y in ys))
    nums = VGroup(*(text(n(v), size, MUTED).move_to(pos(x - .24, y), aligned_edge=RIGHT) for v, y in zip(valores, ys)))
    nome = text(NOMES[chave], size + 1, INK, width=esp * .93).move_to(pos(x, y0 - .36))
    botao = RoundedRectangle(width=.32, height=.17, corner_radius=.05, stroke_color=FUNDO, stroke_width=1.5,
                             fill_color=cor, fill_opacity=1).move_to(pos(x, y_faixa(valores, valor, y0, y1)))
    return VGroup(trilho, degraus, nums, nome, botao)


def mesa(m, caixa, valores, size=13, produto=True):
    """painel, título, faixas, produto."""
    x0, x1, y0, y1 = caixa
    grade = EST[m]["grid"]
    esp = (x1 - x0 - .1) / len(grade)
    painel = RoundedRectangle(width=x1 - x0, height=y1 - y0, corner_radius=.12, stroke_color=COR[m], stroke_width=1.5,
                              fill_color="#1b2028", fill_opacity=1).move_to(pos((x0 + x1) / 2, (y0 + y1) / 2))
    nome = text(ROTULOS[m], 20, COR[m], bold=True).move_to(pos((x0 + x1) / 2, y1 - .24))
    base = y0 + (.98 if produto else .72)
    faixas = VGroup(*(faixa(x0 + .05 + esp * (i + .6), base, y1 - .62, k, v, valores[k], COR[m], esp, size)
                      for i, (k, v) in enumerate(grade.items())))
    conta = VGroup()
    if produto:
        tamanhos = [len(v) for v in grade.values()]
        assert prod(tamanhos) == EST[m]["size"]
        conta = text(f"{' × '.join(map(str, tamanhos))} = {mil(EST[m]['size'])}", 18, COR[m], x1 - x0 - .2,
                     bold=True).move_to(pos((x0 + x1) / 2, y0 + .28))
    return VGroup(painel, nome, faixas, conta)


def caixas(y0, y1):
    """Quatro mesas lado a lado, com largura proporcional ao número de faixas."""
    x, out = -6.6, {}
    unidade = (13.2 - .54) / sum(len(EST[m]["grid"]) for m in METODOS)
    for m in METODOS:
        w = unidade * len(EST[m]["grid"])
        out[m] = (x, x + w, y0, y1)
        x += w + .18
    return out


def alvos(m, mesa_, caixa, valores, produto=True):
    """Posições dos botões para uma configuração."""
    x0, x1, y0, y1 = caixa
    base = y0 + (.98 if produto else .72)
    return [(f[4], pos(f[0].get_center()[0], y_faixa(v, valores[k], base, y1 - .62)))
            for f, (k, v) in zip(mesa_[2], EST[m]["grid"].items())]


def mover(m, mesa_, caixa, valores):
    return [b.animate.move_to(p) for b, p in alvos(m, mesa_, caixa, valores)]


REF = EST["spea2"]["trials"][0]["parameters"]
MEIO = {m: {k: v[len(v) // 2] for k, v in EST[m]["grid"].items()} for m in METODOS}
LINHA = caixas(-3.15, .72)
FOCO = (-6.6, -2.75, -3.15, .98)


# --- osciloscópio ------------------------------------------------------------------------------

def barras_de(p):
    return VGroup(*(VGroup(EIXO.setup(b), EIXO.espera(b), EIXO.bloco(b))
                    for b in sorted(p["blocks"], key=lambda b: b["job"])))


OSC = {"linha": (.235, pos(0, 1.73)), "foco": (.2, pos(-4.67, 1.86))}


def mini(mob, modo):
    s, c = OSC[modo]
    return mob.scale(s, about_point=ORIGIN).shift(c)


def moldura(modo):
    s, c = OSC[modo]
    q = RoundedRectangle(width=13.9 * s, height=6.1 * s, corner_radius=.1, stroke_color=MUTED, stroke_width=2.5,
                         fill_color="#101318", fill_opacity=1).move_to(c + pos(0, -.35 * s))
    tag = text("ilustração", 14, MUTED).next_to(q, RIGHT, buff=.12)
    if modo == "foco":
        tag.rotate(PI / 2).next_to(q, RIGHT, buff=.07)
    q.set_z_index(-1)
    return VGroup(q, tag)


def tela(cena, cmax=15):
    """Gantt e plano em escala cheia; devolve as peças que mudam com a configuração."""
    fundo = VGroup(*cena.base())
    barras = barras_de(plano(cmax))
    axis, labels = plano_objetivos((5.02, .35), 2.75, 2.7)
    p = plano(cmax)
    ponto = Dot(axis.c2p(p["cmax"], p["tec"]), radius=.11, color=GOLD)
    return fundo, barras, VGroup(axis, labels), ponto


def tocar(barras, ponto, cmax, modo):
    """A tela muda de plano: só ilustra que outra mixagem soa diferente."""
    axis, _ = plano_objetivos((5.02, .35), 2.75, 2.7)
    p = plano(cmax)
    alvo = mini(Dot(axis.c2p(p["cmax"], p["tec"]), radius=.11, color=GOLD), modo)
    return [Transform(barras, mini(barras_de(p), modo)), ponto.animate.move_to(alvo)]


# --- gráfico de scores --------------------------------------------------------------------------

TRIALS = EST["spea2"]["trials"]
CONT = EST["spea2"]["counts"]
TX = {t["trial"]: t for t in TRIALS}
LINHAS = {"timeout": -2.08, "interrupted": -2.46, "duplicate": -2.84}
LIN_COR = {"timeout": CORAL, "interrupted": GOLD, "duplicate": MUTED}


def gx(trial):
    return -1.0 + 7.2 * trial / 75


def gy(score):
    return -1.6 + 3.5 * (score - .92) / .03


def grafico():
    assert all(.92 <= t["score"] <= .95 for t in TRIALS if t["score"] is not None)
    g = VGroup(Line(pos(-1.15, gy(.92)), pos(6.35, gy(.92)), color=MUTED, stroke_width=1.6),
               Line(pos(-1.15, gy(.92)), pos(-1.15, gy(.95) + .1), color=MUTED, stroke_width=1.6))
    for v in (.92, .93, .94, .95):
        g.add(text(pt(v, 2), 15, MUTED).move_to(pos(-1.45, gy(v))),
              Line(pos(-1.15, gy(v)), pos(6.35, gy(v)), color=GRID, stroke_width=.8, stroke_opacity=.6))
    g.add(left(text("score", 17, MUTED), -2.1, gy(.95) + .3), text("trial", 15, MUTED).move_to(pos(6.2, gy(.92) - .2)))
    return g


def ponto_de(t):
    return Dot(pos(gx(t["trial"]), gy(t["score"])), radius=.075, color=COR["spea2"])


def marca_de(t):
    """FAIL e PRUNED têm forma, cor e linha próprias."""
    x = gx(t["trial"])
    tipo = t["failure"] or "duplicate"
    y = LINHAS[tipo]
    if tipo == "timeout":
        return VGroup(*(Line(pos(x - .07, y - s * .07), pos(x + .07, y + s * .07), color=CORAL, stroke_width=3)
                        for s in (1, -1)))
    if tipo == "interrupted":
        return VGroup(*(Line(pos(x + d, y - .08), pos(x + d, y + .08), color=GOLD, stroke_width=4) for d in (-.035, .035)))
    return VGroup(Circle(radius=.065, color=MUTED, stroke_width=2).move_to(pos(x, y)))


def linhas_rotulos(tipos=("timeout", "interrupted", "duplicate")):
    nomes = {"timeout": "timeout", "interrupted": "interrompido", "duplicate": "duplicata"}
    return VGroup(*(text(nomes[k], 15, LIN_COR[k]).move_to(pos(-1.2, LINHAS[k]), aligned_edge=RIGHT) for k in tipos))


def totais():
    return VGroup(*(text(str(CONT[k]), 19, LIN_COR[k], bold=True).move_to(pos(6.5, y)) for k, y in LINHAS.items()))


def degrau(k):
    """Trecho da escada do recorde que começa no registro k."""
    r = EST["spea2"]["record"]
    fim = r[k + 1]["trial"] if k + 1 < len(r) else 75
    pts = [pos(gx(r[k]["trial"]), gy(r[k]["score"])), pos(gx(fim), gy(r[k]["score"]))]
    if k:
        pts.insert(0, pos(gx(r[k]["trial"]), gy(r[k - 1]["score"])))
    return VMobject(stroke_color=INK, stroke_width=2.5).set_points_as_corners(pts)


def faixas_topo():
    y = 2.25
    div = DashedLine(pos(gx(19.5), gy(.92)), pos(gx(19.5), 2.4), color=GRID, stroke_width=2)
    return VGroup(text("20 explorações", 20, INK).move_to(pos(gx(9.6), y)), div,
                  text("40 por TPE", 20, COR["spea2"], bold=True).move_to(pos(gx(47), y)))


def anel_ref():
    c = pos(gx(0), gy(TX[0]["score"]))
    return VGroup(Circle(radius=.14, color=INK, stroke_width=2).move_to(c),
                  left(text("referência", 14, INK), gx(0) + .16, gy(TX[0]["score"]) + .2))


def contador(v):
    return rotulo(f"{CONT['complete']} completos · {v} tentativas" if v == 60 else f"{v} tentativas", 18, INK, True).move_to(
        pos(6.5, 2.86), aligned_edge=RIGHT)


TITULO_TPE = "Onde tentar agora?"


def quadro_tpe(cena):
    """Último quadro de CalibracaoMesa e primeiro de CalibracaoTorneio."""
    fundo, barras, plan, ponto = tela(cena, 12)
    osc = VGroup(moldura("foco"), mini(fundo, "foco"), mini(barras, "foco"), mini(plan, "foco"), mini(ponto, "foco"))
    desk = mesa("spea2", FOCO, TX[51]["parameters"], 15)
    pts = {t["trial"]: ponto_de(t) for t in TRIALS if t["state"] == "COMPLETE"}
    marcas = VGroup(*(marca_de(t) for t in TRIALS if t["state"] != "COMPLETE"))
    resto = VGroup(osc, desk, grafico(), linhas_rotulos(), totais(), faixas_topo(), anel_ref(), marcas,
                   *(degrau(k) for k in range(len(EST["spea2"]["record"]))), contador(60))
    return resto, pts


class Calibracao(CenaContinua):
    chapter, total = "CALIBRAÇÃO", 2

    def abrir(self, titulo=None):
        super().abrir(titulo)
        self.cabecalho[4].become(left(text(FONTE, 17, MUTED, width=11.85), -6.55, -3.60))


class CalibracaoMesa(Calibracao):
    number = 1

    def construct(self):
        self.abrir()
        self.partes = tela(self)
        self.add(*self.partes)
        self.botoes()
        self.score()
        self.exploracao()
        self.tpe()

    # 00:00
    def botoes(self):
        fundo, barras, plan, ponto = self.partes
        self.beat("botoes", "Quem decide o volume de cada botão?")
        self.wait(.4)
        mold = moldura("linha")
        self.play(FadeIn(mold[0], scale=2.5),
                  *(mob.animate.scale(OSC["linha"][0], about_point=ORIGIN).shift(OSC["linha"][1])
                    for mob in (fundo, barras, plan, ponto)), run_time=1.5)
        self.play(FadeIn(mold[1]), run_time=.3)
        mesas = {m: mesa(m, LINHA[m], MEIO[m]) for m in METODOS}
        corpo = VGroup(*(VGroup(*mesas[m][:3]) for m in METODOS))
        self.play(LaggedStart(*(FadeIn(c, shift=pos(0, 1.6)) for c in corpo), lag_ratio=.25), run_time=1.9)
        # As combinações nascem do produto dos degraus.
        self.play(LaggedStart(*(AnimationGroup(*(Indicate(f[1], color=COR[m], scale_factor=1.25) for f in mesas[m][2]),
                                               FadeIn(mesas[m][3], shift=pos(0, .25))) for m in METODOS),
                              lag_ratio=.35), run_time=2.4)
        for cmax, sinal in ((12, 1), (20, 0)):
            novo = {m: {k: v[(i * 2 + 1 + 3 * sinal) % len(v)] for i, (k, v) in enumerate(EST[m]["grid"].items())}
                    for m in METODOS}
            self.play(*(a for m in METODOS for a in mover(m, mesas[m], LINHA[m], novo[m])),
                      *tocar(barras, ponto, cmax, "linha"), run_time=1.0)
        self.play(Indicate(mesas["moead"][3], color=INK, scale_factor=1.2), run_time=.8)
        self.wait(.4)
        # Foco na mesa do SPEA2.
        grande = mesa("spea2", FOCO, REF, 15)
        mf = moldura("foco")
        s, c = OSC["foco"]
        s0, c0 = OSC["linha"]
        fora = [FadeOut(mesas[m], shift=pos(-.6 if m == "vns_vnd" else .8, 0)) for m in METODOS if m != "spea2"]
        self.play(*fora, Transform(mesas["spea2"], grande), Transform(mold, mf),
                  *(mob.animate.shift(-c0).scale(s / s0, about_point=ORIGIN).shift(c)
                    for mob in (fundo, barras, plan, ponto)), run_time=1.3)
        self.remove(mold[0], mold[1])
        self.bring_to_back(mold)  # antes do Gantt também na camada estática
        self.mesa = mesas["spea2"]
        self.osc = (mold, fundo, barras, plan, ponto)
        self.hold()

    def ajustar(self, valores):
        return mover("spea2", self.mesa, FOCO, valores)

    # 00:30
    def score(self):
        self.beat("score", "Como dar nota a uma configuração?")
        demo = D["score_demo"]
        assert demo["parameters"] | {} == REF | {"max_evaluations": 8000}

        def my(v):
            return -1.95 + 3.6 * (v - .84) / .16

        def mx(i):
            return -1.15 + 1.4 * i
        base = my(.84)
        regua = VGroup(Line(pos(-1.95, base), pos(6.45, base), color=MUTED, stroke_width=1.5),
                       *(text(pt(v, 2), 15, MUTED).move_to(pos(-2.25, my(v))) for v in (.84, .92, 1.0)),
                       *(Line(pos(-1.95, my(v)), pos(6.45, my(v)), color=GRID, stroke_width=.8) for v in (.92, 1.0)))
        nomes = VGroup(*(text(" × ".join(r["instance"].split("_")[:2]), 18, INK).move_to(pos(mx(i), base - .28))
                         for i, r in enumerate(demo["rows"])))
        nota = text("tarefas × máquinas · seeds 11, 29, 47 · 8.000 avaliações", 16, MUTED).move_to(pos(2.3, base - .72))
        barras, pos_x = [], []
        for i, r in enumerate(demo["rows"]):
            col = []
            for j, run in enumerate(r["runs"]):
                h = my(run["score"]) - base
                col.append(Rectangle(width=.28, height=h, stroke_width=0, fill_color=COR["spea2"], fill_opacity=.85)
                           .move_to(pos(mx(i) + .36 * (j - 1), base), aligned_edge=DOWN))
            barras.append(col)
        self.play(FadeIn(regua), FadeIn(nomes), FadeIn(nota),
                  *self.ajustar(REF), *tocar(self.osc[2], self.osc[4], 15, "foco"), run_time=.8)
        todas = [b for col in barras for b in col]
        self.play(LaggedStart(*(GrowFromEdge(b, DOWN) for b in todas), lag_ratio=.12), run_time=2.6)

        def ordem(i):
            return sorted(range(3), key=lambda j: demo["rows"][i]["runs"][j]["score"])

        def ordenar(i):
            return [barras[i][j].animate(path_arc=.9).move_to(pos(mx(i) + .36 * (k - 1), base), aligned_edge=DOWN)
                    for k, j in enumerate(ordem(i))]

        def colapsar(i):
            o = ordem(i)
            meio = barras[i][o[1]]
            return [barras[i][o[0]].animate.move_to(meio, aligned_edge=DOWN).set_opacity(0),
                    barras[i][o[2]].animate.move_to(meio, aligned_edge=DOWN).set_opacity(0)]

        valores = VGroup(*(text(pt(r["median"]), 19, INK, bold=True).move_to(pos(mx(i), my(r["median"]) + .22))
                           for i, r in enumerate(demo["rows"])))
        # Câmera lenta na segunda instância, onde as três seeds mais divergem.
        foco = 1
        self.play(*(b.animate.set_opacity(.18) for i in range(6) if i != foco for b in barras[i]), run_time=.4)
        self.play(*ordenar(foco), run_time=1.1)
        self.wait(.3)
        self.play(*colapsar(foco), run_time=.8)
        med = text("mediana", 22, GOLD, bold=True).move_to(pos(mx(foco), my(.955) + .62))
        self.play(FadeIn(valores[foco]), FadeIn(med), run_time=.4)
        self.wait(.4)
        resto = [i for i in range(6) if i != foco]
        self.play(*(b.animate.set_opacity(.85) for i in resto for b in barras[i]), run_time=.3)
        self.play(*(a for i in resto for a in ordenar(i)), run_time=.7)
        self.play(*(a for i in resto for a in colapsar(i)), run_time=.7)
        self.play(FadeOut(med), LaggedStart(*(FadeIn(valores[i]) for i in resto), lag_ratio=.1), run_time=.6)
        # Vasos comunicantes: seis alturas viram uma só.
        colunas = VGroup(*(barras[i][ordem(i)[1]] for i in range(6)))
        self.remove(*(b for col in barras for b in col))
        self.add(colunas)
        canos = VGroup(*(Rectangle(width=1.4, height=my(r["median"]) - base, stroke_width=0, fill_color=COR["spea2"],
                                   fill_opacity=.75).move_to(pos(mx(i), base), aligned_edge=DOWN)
                         for i, r in enumerate(demo["rows"])))
        self.play(Transform(colunas, canos), run_time=.7)
        alvo = my(demo["score"])
        nivel = VGroup(*(Rectangle(width=1.4, height=alvo - base, stroke_width=0, fill_color=COR["spea2"],
                                   fill_opacity=.75).move_to(pos(mx(i), base), aligned_edge=DOWN) for i in range(6)))
        self.play(Transform(colunas, nivel), FadeOut(valores, shift=pos(0, -.15)), run_time=1.5,
                  rate_func=rate_functions.ease_in_out_sine)
        linha = Line(pos(mx(0) - .7, alvo), pos(mx(5) + .7, alvo), color=GOLD, stroke_width=3)
        media = VGroup(text("média", 22, GOLD, bold=True).move_to(pos(1.6, alvo + .32)),
                       text(pt(demo["score"]), 28, INK, bold=True).move_to(pos(3.1, alvo + .34)))
        self.play(Create(linha), FadeIn(media), run_time=.6)
        self.wait(.6)
        # O nível vira um ponto e salta para o gráfico.
        self.graf = grafico()
        bola = ponto_de(TX[0])
        salto = Dot(linha.get_center(), radius=.12, color=COR["spea2"])
        self.play(Transform(linha, salto), FadeOut(colunas), FadeOut(regua), FadeOut(nomes), FadeOut(nota),
                  FadeOut(media[0]), media[1].animate.scale(.6).next_to(salto, UP, buff=.1), run_time=.6)
        self.play(FadeIn(self.graf), linha.animate(path_arc=1.1).become(bola),
                  media[1].animate(path_arc=1.1).move_to(pos(gx(0) + .55, gy(TX[0]["score"]) + .28)), run_time=1.0)
        self.remove(linha)
        self.pts = {0: bola}
        self.add(bola)
        self.valor0 = media[1]
        self.hold()

    # 01:00
    def exploracao(self):
        self.beat("exploracao", "Por onde começar sem saber nada?", self.valor0)
        self.topo, self.anel = faixas_topo(), anel_ref()
        self.play(FadeIn(self.anel), FadeIn(self.topo[0]), run_time=.6)
        self.cont = ValueTracker(1)
        self.num = always_redraw(lambda: contador(round(self.cont.get_value())))
        self.add(self.num)
        self.rotl = linhas_rotulos(("timeout",))
        self.marcas = []
        # Rastros nos botões: cada exploração marca o degrau visitado.
        self.rastros, visitas = VGroup(), {}

        def rastro(t):
            novos = []
            for f, (k, v) in zip(self.mesa[2], EST["spea2"]["grid"].items()):
                val = t["parameters"][k]
                q = visitas[k, val] = visitas.get((k, val), -1) + 1
                y = y_faixa(v, val, FOCO[2] + .98, FOCO[3] - .62)
                novos.append(Dot(pos(f[0].get_center()[0] + .22 + .048 * q, y), radius=.022, color=COR["spea2"]))
            return novos
        for d in rastro(TX[0]):
            self.rastros.add(d)
        self.add(self.rastros)
        soltos = []
        for i in range(1, 20):
            t = TX[i]
            lento = i in (1, 2, 12)
            novos = rastro(t)
            soltos += novos
            anims = [*self.ajustar(t["parameters"]), self.cont.animate.set_value(i + 1), *(FadeIn(d) for d in novos)]
            if t["state"] == "COMPLETE":
                d = ponto_de(t)
                haste = Line(pos(gx(i), gy(.92)), d.get_center(), color=COR["spea2"], stroke_width=5, stroke_opacity=.45)
                self.pts[i] = d
                anims += [FadeIn(d, shift=pos(0, -.5 if not lento else -1.2)), FadeIn(haste, rate_func=there_and_back)]
            else:
                m = marca_de(t)
                self.marcas.append(m)
                anims += [FadeIn(m, scale=2.5), FadeIn(self.rotl)]
            if i in (4, 8, 16):
                anims += tocar(self.osc[2], self.osc[4], {4: 12, 8: 20, 16: 15}[i], "foco")
            self.play(*anims, run_time=.75 if lento else .3)
            if t["state"] == "COMPLETE":
                self.remove(haste)
        self.soltos = soltos
        self.esc = [VMobject(stroke_color=INK, stroke_width=2.5).set_points_as_corners(
            [pos(gx(0), gy(TX[0]["score"])), pos(gx(19), gy(TX[0]["score"]))])]
        self.play(Create(self.esc[0]), run_time=.7)
        self.wait(.3)
        self.hold()
        self.cont = ValueTracker(20)

    # 01:20
    def tpe(self):
        self.remove(self.num)
        num = contador(20)
        self.add(num)
        self.beat("tpe", TITULO_TPE)
        nv = D["clouds"][0]
        niveis = nv["levels"]

        def lx(i):
            return -1.25 + 1.15 * i
        y0 = -.35
        bons, demais = nv["good"], nv["rest"]
        trilho = VGroup(Line(pos(lx(0) - .3, y0), pos(lx(6) + .3, y0), color=GRID, stroke_width=7),
                        *(text(n(v), 17, MUTED).move_to(pos(lx(i), y0 - .25)) for i, v in enumerate(niveis)),
                        text("mutação", 19, INK, bold=True).move_to(pos(6.0, y0 + .32)))
        rot = VGroup(text("bons", 18, COR["spea2"], bold=True).move_to(pos(-2.15, y0 + .35)),
                     text("demais", 18, MUTED, bold=True).move_to(pos(-2.15, y0 - .65)))
        destinos, conta = {}, {}
        for tr in bons + demais:
            i = niveis.index(TX[tr]["parameters"]["mutation_probability"])
            alto = tr in bons
            k = conta[i, alto] = conta.get((i, alto), -1) + 1
            destinos[tr] = pos(lx(i), y0 + .3 + .2 * k if alto else y0 - .58 - .2 * k)
        nevoas = VGroup()
        for i in range(7):
            for c, y, s, cor in ((nv["good_count"][i], y0 + .3, 1, COR["spea2"]), (nv["rest_count"][i], y0 - .58, -1, MUTED)):
                if c:
                    nevoas.add(Ellipse(width=.95, height=.42 + .2 * c, stroke_width=0, fill_color=cor, fill_opacity=.2)
                               .move_to(pos(lx(i), y + s * .1 * (c - 1))))
        fora = VGroup(self.graf, self.anel, self.esc[0], self.rotl, self.topo[0], *self.marcas)
        # VGroup auxiliar só para a animação; os pontos voam do gráfico para a faixa.
        guardado = fora.copy()
        self.play(FadeOut(fora), FadeOut(self.rastros), *(FadeOut(s) for s in self.soltos),
                  *(self.pts[k].animate.move_to(p) for k, p in destinos.items()),
                  *(self.pts[k].animate.move_to(destinos[k]).set_color(MUTED) for k in demais),
                  FadeIn(trilho), FadeIn(rot), run_time=1.5)
        self.play(FadeIn(nevoas), run_time=.5)
        razao = nv["ratio"]
        teto = max(razao)
        ry = lambda v: y0 + .95 + 1.25 * v / teto
        curva = VMobject(stroke_color=INK, stroke_width=3).set_points_as_corners([pos(lx(i), ry(v)) for i, v in enumerate(razao)])
        rr = VGroup(text("razão bons ÷ demais", 17, INK).move_to(pos(-1.0, 1.75)),
                    text("leitura simplificada: uma faixa por vez", 14, MUTED).move_to(pos(4.7, -2.75)))
        i_best = razao.index(teto)
        seta = Triangle(color=GOLD, fill_opacity=1, stroke_width=0).scale(.13).rotate(PI).move_to(pos(lx(1), y0 + .13))
        self.play(Create(curva), FadeIn(rr), FadeIn(seta), run_time=1.0)
        alvo = dict(TX[19]["parameters"], mutation_probability=niveis[i_best])
        self.play(seta.animate.move_to(pos(lx(i_best), y0 + .13)), *self.ajustar(alvo), run_time=1.2,
                  rate_func=rate_functions.ease_in_out_back)
        self.wait(.6)
        self.graf, self.anel, self.esc[0], self.rotl = guardado[0], guardado[1], guardado[2], guardado[3]
        topo20, self.marcas = guardado[4], list(guardado[5:])
        self.play(FadeOut(VGroup(trilho, rot, nevoas, curva, rr, seta)),
                  *(FadeIn(g) for g in guardado),
                  *(self.pts[k].animate.move_to(ponto_de(TX[k])).set_color(COR["spea2"]) for k in destinos), run_time=1.0)
        self.topo = VGroup(topo20, *self.topo[1:])
        novos_rot = linhas_rotulos(("interrupted", "duplicate"))
        self.play(Create(self.topo[1]), FadeIn(self.topo[2]), FadeIn(novos_rot), run_time=.4)
        # Quarenta tentativas, com duplicatas rejeitadas no caminho.
        tent = 20
        lote = []
        recs = {r["trial"]: k for k, r in enumerate(EST["spea2"]["record"])}

        def descarregar():
            nonlocal lote, num
            if lote:
                novo = contador(tent)
                self.play(LaggedStart(*lote, lag_ratio=.35), Succession(FadeOut(num, run_time=.05), FadeIn(novo, run_time=.05)),
                          run_time=max(.35, .13 * len(lote)))
                num, lote = novo, []

        vistos = set()
        for t in TRIALS[20:]:
            tr = t["trial"]
            if t["state"] == "COMPLETE":
                tent += 1
                d = ponto_de(t)
                self.pts[tr] = d
                if tr in recs:
                    descarregar()
                    k = recs[tr]
                    antes = EST["spea2"]["record"][k - 1]
                    linha = Line(pos(gx(19 if k == 1 else antes["trial"]), gy(antes["score"])),
                                 pos(gx(tr), gy(antes["score"])), color=INK, stroke_width=2.5)
                    sobe = Line(pos(gx(tr), gy(antes["score"])), d.get_center(), color=INK, stroke_width=2.5)
                    tela_c = {26: 20, 37: 15, 51: 12}[tr]
                    self.play(Create(linha), *self.ajustar(t["parameters"]), FadeIn(d, shift=pos(0, -.8)),
                              *tocar(self.osc[2], self.osc[4], tela_c, "foco"), run_time=.8)
                    self.play(Create(sobe), Flash(d, color=INK, line_length=.12, flash_radius=.2), run_time=.4)
                    self.esc += [linha, sobe]
                else:
                    lote.append(FadeIn(d, shift=pos(0, -.6)))
            else:
                tipo = t["failure"] or "duplicate"
                tent += tipo != "duplicate"
                m = marca_de(t)
                self.marcas.append(m)
                if tipo not in vistos and tipo != "interrupted":
                    descarregar()
                    vistos.add(tipo)
                    if tipo == "timeout":
                        # A tentativa sobe, esgota o tempo e se apaga.
                        g = Dot(pos(gx(tr), 1.3), radius=.09, color=COR["spea2"])
                        self.play(FadeIn(g), run_time=.25)
                        self.play(g.animate.move_to(m).set_color(CORAL).set_opacity(.2), run_time=.7)
                        self.remove(g)
                        self.play(FadeIn(m, scale=2), run_time=.25)
                    else:
                        # A sugestão cai sobre o ponto repetido, faz uma onda e é rejeitada.
                        orig = TX[int(t["duplicate_of"])]
                        alvo_p = pos(gx(orig["trial"]), gy(orig["score"])) if orig["score"] else marca_de(orig).get_center()
                        g = Circle(radius=.09, color=MUTED, stroke_width=3).move_to(pos(gx(tr), 1.7))
                        self.play(g.animate.move_to(alvo_p), run_time=.6)
                        ondas = [Circle(radius=.1, color=MUTED, stroke_width=2).move_to(alvo_p) for _ in range(2)]
                        self.play(LaggedStart(*(o.animate.scale(4).set_stroke(opacity=0) for o in ondas), lag_ratio=.3),
                                  g.animate(path_arc=-1).become(m[0]), run_time=.8)
                        self.remove(g, *ondas)
                        self.add(m)
                else:
                    lote.append(FadeIn(m, scale=2, shift=pos(.25, 0)))
        descarregar()
        ult = EST["spea2"]["record"][-1]
        fim = Line(pos(gx(ult["trial"]), gy(ult["score"])), pos(gx(75), gy(ult["score"])), color=INK, stroke_width=2.5)
        tot = totais()
        novo = contador(60)
        self.play(Create(fim), LaggedStart(*(FadeIn(x) for x in tot), lag_ratio=.3), FadeOut(num), FadeIn(novo),
                  *self.ajustar(TX[51]["parameters"]), run_time=.9)
        assert tent == 60 == CONT["attempts"]
        self.hold()


# --- torneio ------------------------------------------------------------------------------------

class Pista:
    """Comprimento = orçamento (linear); altura = score. Só as balizas são medidas."""

    def __init__(self, m, caixa, grande=False):
        self.m, self.grande = m, grande
        self.x0, self.x1, self.y0, self.y1 = caixa
        c = EST[m]["confirmation"]
        self.c = c
        self.cand = {k["trial"]: k["search_score"] for k in c["candidates"]}
        todos = [*self.cand.values(), *(s for e in c["stages"] for s in e["scores"].values())]
        folga = (max(todos) - min(todos)) * .07
        self.lo, self.hi = min(todos) - folga * (2.4 if grande else 1), max(todos) + folga
        self.campeao, self.rec = EST[m]["best"]["trial"], c["recommended"]["trial"]
        self.diverso = {t for e in c["stages"] for t in e.get("promoted_by_diversity", ())}

    def x(self, budget):
        return self.x0 + (self.x1 - self.x0) * budget / 50000

    def y(self, score):
        return self.y0 + (self.y1 - self.y0) * (score - self.lo) / (self.hi - self.lo)

    def p(self, trial, budget):
        if budget == 0:
            return pos(self.x(0), self.y(self.cand[trial]))
        s = next(e for e in self.c["stages"] if e["budget"] == budget)["scores"][str(trial)]
        return pos(self.x(budget), self.y(s))

    def trechos(self, trial):
        bs = [0, *(e["budget"] for e in self.c["stages"] if str(trial) in e["scores"])]
        return list(zip(bs, bs[1:]))

    def desenho(self):
        size = 17 if self.grande else 13
        g = VGroup(Line(pos(self.x0, self.y0), pos(self.x1 + .15, self.y0), color=GRID, stroke_width=1.5))
        for b in (0, 8000, 20000, 50000):
            tem = b == 0 or b in self.c["budgets"]
            g.add(DashedLine(pos(self.x(b), self.y0), pos(self.x(b), self.y1), color=MUTED if tem else GRID,
                             stroke_width=2 if tem else 1, stroke_opacity=1 if tem else .35))
            nome = "busca" if b == 0 else f"{b // 1000} mil"
            g.add(text(nome, size, MUTED if tem else GRID).move_to(pos(self.x(b), self.y0 - (.24 if self.grande else .16))))
        if self.grande:
            for v in (.932, .936, .940, .944):
                g.add(text(pt(v), 14, MUTED).move_to(pos(self.x0 - 1.75, self.y(v))))
        g.add(text(ROTULOS[self.m], 22 if self.grande else 18, COR[self.m], bold=True).move_to(
            pos(self.x0 + .1, self.y1 + .22), aligned_edge=LEFT))
        return g

    def corredor(self, trial, budget=0):
        r = .1 if self.grande else .065
        p = self.p(trial, budget)
        if trial == self.rec:
            # Recomendada: anel claro. Vaga de diversidade: losango. Campeã da busca: cor cheia.
            return VGroup(Dot(p, radius=r, color=COR[self.m]), Circle(radius=r * 1.35, color=INK, stroke_width=2.5).move_to(p))
        if trial in self.diverso:
            return VGroup(Square(side_length=r * 1.9, stroke_width=0, fill_color=COR[self.m], fill_opacity=1).rotate(PI / 4).move_to(p))
        if trial == self.campeao:
            return VGroup(Dot(p, radius=r, color=COR[self.m]), Dot(p, radius=r * .45, color=FUNDO))
        return VGroup(Dot(p, radius=r, color=COR[self.m], fill_opacity=.5))

    def trilha(self, trial, a, b):
        forte = trial in (self.campeao, self.rec)
        return Line(self.p(trial, a), self.p(trial, b), color=COR[self.m], stroke_width=3 if forte else 1.5,
                    stroke_opacity=.9 if forte else .4)


GRANDE = (-3.9, 5.9, -2.55, 1.85)
MINI = {"vns_vnd": (-5.6, -1.3, -.15, 1.85), "spea2": (1.0, 5.3, -.15, 1.85),
        "moead": (-5.6, -1.3, -2.95, -.95), "age": (1.0, 5.3, -2.95, -.95)}


def legenda():
    c, y = COR["vns_vnd"], 2.12
    xs = (-.2, 2.1, 4.1)
    marcas = (VGroup(Dot(pos(xs[0], y), radius=.09, color=c), Dot(pos(xs[0], y), radius=.04, color=FUNDO)),
              VGroup(Dot(pos(xs[1], y), radius=.09, color=c), Circle(radius=.12, color=INK, stroke_width=2.5).move_to(pos(xs[1], y))),
              Square(side_length=.17, stroke_width=0, fill_color=c, fill_opacity=1).rotate(PI / 4).move_to(pos(xs[2], y)))
    return VGroup(*marcas, *(left(text(t, 15, MUTED), x + .2, y)
                             for x, t in zip(xs, ("campeã da busca", "recomendada", "vaga de diversidade"))))


class CalibracaoTorneio(Calibracao):
    number = 2

    def construct(self):
        self.abrir(TITULO_TPE)
        resto, pts = quadro_tpe(self)
        self.add(resto, *pts.values())
        self.confirmacao(resto, pts)
        self.escolhidos()

    # 02:00
    def confirmacao(self, resto, pts):
        pistas = {m: Pista(m, MINI[m]) for m in METODOS}
        sp = pistas["spea2"]
        self.beat("confirmacao", "O melhor da busca vence a corrida longa?")
        cinco = list(sp.cand)
        self.play(*(FadeOut(p) for k, p in pts.items() if k not in cinco),
                  resto.animate.set_opacity(.12), *(pts[k].animate.scale(1.5) for k in cinco), run_time=.6)
        des = {m: pistas[m].desenho() for m in METODOS}
        corr = {m: {t: pistas[m].corredor(t) for t in pistas[m].cand} for m in METODOS}
        self.play(FadeOut(resto), *(FadeIn(d) for d in des.values()),
                  *(Transform(pts[k], corr["spea2"][k][0].copy()) for k in cinco),
                  *(FadeIn(c) for m in METODOS if m != "spea2" for c in corr[m].values()), run_time=1.1)
        self.remove(*(pts[k] for k in cinco))
        self.add(*corr["spea2"].values())
        # O VNS ocupa a tela.
        g = Pista("vns_vnd", GRANDE, True)
        outros = [des[m] for m in METODOS if m != "vns_vnd"] + [c for m in METODOS if m != "vns_vnd" for c in corr[m].values()]
        gd = g.desenho()
        gc = {t: g.corredor(t) for t in g.cand}
        rotulos, y_ant = VGroup(), 9
        for t in sorted(g.cand, key=lambda t: -g.cand[t]):
            y = min(g.y(g.cand[t]), y_ant - .26)
            y_ant = y
            rotulos.add(VGroup(text(f"trial {t}", 15, INK).move_to(pos(g.x0 - .4, y), aligned_edge=RIGHT),
                               Line(pos(g.x0 - .36, y), pos(g.x0 - .13, g.y(g.cand[t])), color=GRID, stroke_width=1)))
        leg = legenda()
        self.play(*(FadeOut(o) for o in outros), FadeOut(des["vns_vnd"]), FadeIn(gd),
                  *(Transform(corr["vns_vnd"][t], gc[t]) for t in g.cand), run_time=1.0)
        self.remove(*corr["vns_vnd"].values())
        self.add(*gc.values())
        self.play(FadeIn(rotulos), FadeIn(leg), run_time=.4)
        trilhas = {}

        def correr(a, b, quem, tempo, f=linear):
            anims = []
            for t in quem:
                tr = g.trilha(t, a, b)
                trilhas[t, b] = tr
                anims += [Create(tr, rate_func=f), gc[t].animate(rate_func=f).move_to(g.p(t, b))]
            self.play(*anims, run_time=tempo)
            self.add(*(gc[t] for t in quem))
        e8, e20, e50 = g.c["stages"]
        correr(0, 8000, e8["ranking"], 1.4)
        # 31 e 38 saem; a última colocada segue pela vaga de diversidade.
        tag10 = text("5.ª colocada segue", 16, INK).next_to(g.p(10, 8000), DOWN, buff=.1).shift(pos(1.0, 0))
        self.play(*(gc[t].animate.set_color(GRID).scale(.7) for t in e8["eliminated"]), run_time=.4)
        self.play(FadeIn(tag10), Indicate(gc[10], color=INK), run_time=.8)
        # Até 97,5% do segundo trecho em velocidade normal; o resto, na lupa.
        f0 = .975
        ult = ValueTracker(0)
        ini = {t: g.p(t, 8000) for t in e20["ranking"]}
        fim = {t: g.p(t, 20000) for t in e20["ranking"]}
        vivas = {}
        for t in e20["ranking"]:
            forte = t in (g.campeao, g.rec)
            vivas[t] = always_redraw(lambda t=t, forte=forte: Line(
                ini[t], ini[t] + (fim[t] - ini[t]) * max(ult.get_value(), 1e-3), color=COR["vns_vnd"],
                stroke_width=3 if forte else 1.5, stroke_opacity=.9 if forte else .4))
            gc[t].add_updater(lambda m, t=t: m.move_to(ini[t] + (fim[t] - ini[t]) * ult.get_value()))
        self.add(*vivas.values(), *(gc[t] for t in e20["ranking"]))
        self.play(ult.animate.set_value(f0), run_time=1.8, rate_func=linear)
        lupa, atualiza = self.lupa(g, e8, e20, ult, f0)
        alvo = fim[65]
        fio = VGroup(Circle(radius=.2, color=INK, stroke_width=2).move_to(alvo),
                     Line(alvo + pos(.14, -.16), lupa[0].get_corner(UP + LEFT), color=INK, stroke_width=1.2))
        self.play(FadeIn(lupa), Create(fio), run_time=.6)
        self.add(*atualiza)
        self.play(ult.animate.set_value(1), run_time=3.2, rate_func=linear)
        for m in gc.values():
            m.clear_updaters()
        for t in e20["ranking"]:
            self.remove(vivas[t])
            trilhas[t, 20000] = g.trilha(t, 8000, 20000)
            self.add(trilhas[t, 20000], gc[t])
        parados = [a.copy().clear_updaters() for a in atualiza]
        self.remove(*atualiza)
        self.add(*parados)
        lab = VGroup(*(text(f"trial {t}: {pt(e20['scores'][str(t)], 5)}", 16, INK if t == 65 else MUTED, bold=t == 65)
                       for t in (65, 32))).arrange(DOWN, buff=.1, aligned_edge=LEFT).next_to(lupa[0], LEFT, buff=.25)
        self.play(FadeIn(lab), run_time=.4)
        self.wait(1.0)
        self.play(FadeOut(lupa), FadeOut(fio), FadeOut(lab), *(FadeOut(x) for x in parados), FadeOut(tag10),
                  *(gc[t].animate.set_color(GRID).scale(.7) for t in e20["eliminated"]), run_time=.6)
        fica = text("campeã da busca para aqui", 16, MUTED).next_to(g.p(32, 20000), LEFT, buff=.25).shift(pos(0, .28))
        self.play(FadeIn(fica), run_time=.3)
        correr(20000, 50000, e50["ranking"], 1.8)
        self.play(Flash(gc[65], color=INK), run_time=.5)
        self.wait(.3)
        # As quatro corridas lado a lado: em todas a recomendada não é a campeã da busca.
        peq = VGroup(*(pistas["vns_vnd"].trilha(t, a, b) for t in pistas["vns_vnd"].cand for a, b in pistas["vns_vnd"].trechos(t)))
        chaves = [(t, b) for t in pistas["vns_vnd"].cand for a, b in pistas["vns_vnd"].trechos(t)]
        grandes = VGroup(*(trilhas[k] for k in chaves))
        self.remove(*trilhas.values())
        self.add(grandes)
        fimv = {t: self.final(pistas["vns_vnd"], t) for t in g.cand}
        for m in ("spea2", "moead", "age"):
            des[m] = pistas[m].desenho()
            corr[m] = {t: pistas[m].corredor(t) for t in pistas[m].cand}
        des["vns_vnd"] = pistas["vns_vnd"].desenho()
        corr["vns_vnd"] = fimv
        self.play(*(FadeOut(x) for x in (gd, rotulos, fica, leg)), run_time=.35)
        self.play(Transform(grandes, peq), *(Transform(gc[t], fimv[t]) for t in g.cand), FadeIn(des["vns_vnd"]),
                  *(FadeIn(des[m]) for m in ("spea2", "moead", "age")),
                  *(FadeIn(c) for m in ("spea2", "moead", "age") for c in corr[m].values()), run_time=1.2)
        self.remove(*gc.values())
        self.add(*fimv.values())
        feito = VGroup()
        for a0, b0, dur in ((0, 8000, .8), (8000, 20000, 1.0), (20000, 50000, 1.4)):
            anims = []
            for m in ("spea2", "moead", "age"):
                p = pistas[m]
                a1, b1 = a0, b0
                for t in p.cand:
                    for a, b in p.trechos(t):
                        # SPEA2 não tem baliza de 8 mil: um único trecho até 20 mil.
                        if (a1, b1) == (a, b) or (m == "spea2" and (a, b) == (0, 20000) and b1 == 20000):
                            tr = p.trilha(t, a, b)
                            feito.add(tr)
                            anims += [Create(tr, rate_func=linear), corr[m][t].animate(rate_func=linear).move_to(p.p(t, b))]
            self.play(*anims, run_time=dur)
            saem = [corr[m][t].animate.set_color(GRID).scale(.8) for m in ("spea2", "moead", "age")
                    for e in pistas[m].c["stages"] if e["budget"] == b0 for t in e.get("eliminated", ())]
            if saem:
                self.play(*saem, run_time=.25)
        self.placar = VGroup()
        for m in METODOS:
            p = pistas[m]
            ultimo = {t: p.trechos(t)[-1][1] for t in (p.rec, p.campeao)}
            onde = f"parou em {ultimo[p.campeao] // 1000} mil" if ultimo[p.campeao] < 50000 else \
                f"{pt(p.c['stages'][-1]['scores'][str(p.campeao)], 5)}"
            self.placar.add(VGroup(
                text(f"{p.rec}", 18, INK, bold=True).move_to(pos(p.x1 + .42, p.y(p.c["stages"][-1]["scores"][str(p.rec)]) + .05)),
                text(f"campeã {p.campeao}: {onde}" + (f" · {p.rec}: {pt(p.c['stages'][-1]['scores'][str(p.rec)], 5)}" if m == "spea2" else ""),
                     14, MUTED, width=3.0).move_to(pos(p.x1 + .1, p.y1 + .2), aligned_edge=RIGHT)))
        self.play(LaggedStart(*(FadeIn(x) for x in self.placar), lag_ratio=.15), run_time=.7)
        self.pistas, self.corr = pistas, corr
        self.cena_pistas = [grandes, feito, *des.values()]
        self.remove(grandes, *feito)
        self.add(grandes, feito, *(c for m in METODOS for c in corr[m].values()))
        self.hold()

    def final(self, p, t):
        b = p.trechos(t)[-1][1]
        c = p.corredor(t, b)
        if b != 50000:
            c.set_color(GRID).scale(.8)
        return c

    def lupa(self, g, e8, e20, ult, f0):
        """Ampliação vertical real em torno da baliza de 20 mil."""
        cx, cy, larg, alt = 3.75, -1.22, 2.7, 2.35
        esc = 9000
        centro = e20["scores"]["65"] - 3e-5
        vezes = round(esc / ((g.y1 - g.y0) / (g.hi - g.lo)))
        box = RoundedRectangle(width=larg, height=alt, corner_radius=.12, stroke_color=INK, stroke_width=2.5,
                               fill_color="#101318", fill_opacity=1).move_to(pos(cx, cy))
        gate = DashedLine(pos(cx + .95, cy - alt / 2), pos(cx + .95, cy + alt / 2), color=MUTED, stroke_width=1.5)
        tit = text(f"lupa vertical ×{vezes}", 14, MUTED).move_to(pos(cx - .35, cy + alt / 2 - .2))

        def ponto(t, f):
            s = e8["scores"][str(t)] + (e20["scores"][str(t)] - e8["scores"][str(t)]) * f
            return pos(cx - 1.1 + 2.05 * (f - f0) / (1 - f0), cy + .35 + esc * (s - centro))
        vivos = []
        for t in (32, 65):
            vivos.append(always_redraw(lambda t=t: Line(ponto(t, f0), ponto(t, max(ult.get_value(), f0 + 1e-4)),
                                                       color=COR["vns_vnd"], stroke_width=3 if t == 65 else 2,
                                                       stroke_opacity=.9 if t == 65 else .5)))
        for t in (32, 65):
            def corpo(t=t):
                p = ponto(t, max(ult.get_value(), f0))
                d = VGroup(Dot(p, radius=.09, color=COR["vns_vnd"]))
                d.add(Circle(radius=.12, color=INK, stroke_width=2.5).move_to(p) if t == 65 else Dot(p, radius=.04, color=FUNDO))
                return d
            vivos.append(always_redraw(corpo))
        for t in (32, 65):
            assert all(abs(ponto(t, f)[1] - cy) < alt / 2 - .1 for f in (f0, 1)), (t, ponto(t, f0), ponto(t, 1))
        return VGroup(box, gate, tit), vivos

    # 02:40
    def escolhidos(self):
        self.beat("escolhidos", "O que a campanha recebeu?", self.placar)
        cxs = caixas(-.75, 2.35)
        rec = {m: D["campaign"][m]["parameters"] for m in METODOS}
        mesas = {m: mesa(m, cxs[m], MEIO[m], 11, produto=False) for m in METODOS}
        venc = {m: self.corr[m][self.pistas[m].rec] for m in METODOS}
        fora = [c for m in METODOS for t, c in self.corr[m].items() if t != self.pistas[m].rec]
        for c in venc.values():
            c.set_z_index(2)
        self.play(*(FadeOut(x) for x in [*self.cena_pistas, *fora]),
                  *(FadeIn(mesas[m], shift=pos(0, -.3)) for m in METODOS),
                  *(venc[m].animate.move_to(mesas[m][1].get_right() + pos(.22, 0)) for m in METODOS), run_time=1.1)
        self.add(*venc.values())
        self.play(*(b.animate.move_to(p) for m in METODOS for b, p in alvos(m, mesas[m], cxs[m], rec[m], False)), run_time=1.0)
        # Os valores recomendados acendem na escala.
        acesos = VGroup(*(rot.copy().set_color(INK).scale(1.35) for m in METODOS
                          for f, (k, v) in zip(mesas[m][2], EST[m]["grid"].items()) for rot in (f[2][v.index(rec[m][k])],)))
        self.play(FadeIn(acesos), run_time=.4)
        # Régua: o comprimento continua sendo o orçamento.
        rx = lambda b: -5.6 + 11.2 * b / 50000
        y = -1.45
        assert all(D["campaign"][m]["max_evaluations"] == 10000 and D["campaign"][m]["tuned_max_evaluations"] == 50000 for m in METODOS)
        pista = VGroup(Line(pos(rx(0), y), pos(rx(50000), y), color=GRID, stroke_width=2),
                       Line(pos(rx(10000), y - .42), pos(rx(10000), y + .42), color=INK, stroke_width=4),
                       DashedLine(pos(rx(50000), y - .35), pos(rx(50000), y + .35), color=MUTED),
                       text("campanha: 10 mil", 16, INK, bold=True).move_to(pos(rx(10000) + .95, y + .3)),
                       text("confirmação: 50 mil", 16, MUTED).move_to(pos(rx(50000) - 1.1, y + .3)))
        frase = text("recomendadas a 50 mil, rodadas com 10 mil", 20, INK).move_to(pos(1.6, y - .28))
        copias = [venc[m].copy() for m in METODOS]
        self.play(FadeIn(pista), *(c.animate.move_to(pos(rx(0), y + .27 - .18 * i)) for i, c in enumerate(copias)), run_time=.8)
        self.play(*(c.animate.move_to(pos(rx(10000), y + .27 - .18 * i)) for i, c in enumerate(copias)), FadeIn(frase), run_time=1.0)
        self.wait(.8)
        # v6 e v7 do VNS na mesma escala de 0 a 1.
        bx = lambda s: -4.5 + 8 * s
        v6, v7 = EST["vns_v6"]["best"]["score"], EST["vns_vnd"]["best"]["score"]
        barras = VGroup()
        for yy, nome, s, op, obs in ((-2.35, "VNS v6", v6, .4, ""), (-2.9, "VNS v7", v7, 1, "com a nova inicialização (LPT)")):
            b = Rectangle(width=bx(s) - bx(0), height=.3, stroke_width=0, fill_color=COR["vns_vnd"], fill_opacity=op
                          ).move_to(pos(bx(0), yy), aligned_edge=LEFT)
            num = text(pt(s), 20, INK, bold=True).next_to(b, RIGHT, buff=.15)
            barras.add(VGroup(text(nome, 18, INK).move_to(pos(-4.65, yy), aligned_edge=RIGHT), b, num))
            if obs:
                barras[-1].add(text(obs, 16, FUNDO, bold=True).move_to(b))
        barras.add(text("melhor score da busca (8 mil)", 15, MUTED).move_to(pos(5.15, -2.35)))
        self.play(*(FadeIn(b[0]) for b in barras[:2]), *(GrowFromEdge(b[1], LEFT) for b in barras[:2]), FadeIn(barras[2]),
                  *(o.animate.set_opacity(.25) for o in (frase, pista)), run_time=1.0)
        self.play(*(FadeIn(x) for b in barras[:2] for x in b[2:]), run_time=.4)
        self.wait(1.4)
        # Quadro-base final; a fronteira é a exata da instância didática.
        fundo, gantt, plan, ponto = tela(self, 15)
        axis = plan[0]
        exata = VGroup(staircase(axis, FRENTE, GOLD), dots(axis, FRENTE, GOLD, .05)).set_opacity(.35)
        exata[0].set_fill(opacity=0)
        nota = text("ilustração", 17, MUTED).move_to(pos(5.0, -2.1))
        self.play(*(FadeOut(x, shift=pos(0, .4)) for x in [*mesas.values(), *venc.values(), acesos, pista, frase, *copias, barras]),
                  run_time=.5)
        mini(fundo, "linha"), mini(gantt, "linha"), mini(plan, "linha"), mini(exata, "linha"), mini(ponto, "linha")
        s, c = OSC["linha"]
        grupo = [fundo, gantt, plan, exata, ponto]
        self.play(*(FadeIn(x) for x in grupo), run_time=.3)
        self.play(*(x.animate.shift(-c).scale(1 / s, about_point=ORIGIN) for x in grupo), run_time=1.1)
        self.play(FadeIn(nota), run_time=.3)
        self.hold()
