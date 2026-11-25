"""Introdução e explicação do problema. As seções Manim são os pontos de pausa da fala."""

from math import ceil

from manim import (
    Create, DashedLine, Dot, FadeIn, FadeOut, GrowFromEdge, Indicate, LaggedStart, Line, Rectangle,
    ReplacementTransform, SurroundingRectangle, Transform, VGroup, ValueTracker,
    always_redraw, linear, smooth, LEFT,
)

from fabrica import (
    CORES, DADOS, EIXO, ESTADOS, FAIXAS, FORA, NA_PONTA, PONTA, CenaContinua, Eixo, custo_ate, estado,
    maquina, medidor, plano, relogio, rotulo,
)
from visual import (
    CORAL, CYAN, GOLD, GREEN, GRID, INK, MUTED, axes, dots, formula, left, pos, pt, staircase, text,
)

RAPIDO, MEIO, BARATO = plano(12), plano(15), plano(20)
FRENTE = [(p["cmax"], p["tec"]) for p in DADOS["front"]]


def moeda(value):
    return f"$ {pt(value, 1)}"


def plano_objetivos(center, width, height):
    return axes((10, 22, 2), (400, 900, 100), center=center, width=width, height=height,
                x_label="Cmax (h)", y_label="TEC ($)", numbers=True)


def quadro_objetivo():
    axis, labels = plano_objetivos((-2.5, -.40), 6.6, 3.9)
    points = dots(axis, [FRENTE[0], FRENTE[-1]], GOLD, .12)
    names = VGroup(text("rápido", 24, GOLD).next_to(points[0], pos(1, 0), buff=.16),
                   text("barato", 24, GOLD).next_to(points[1], pos(0, 1), buff=.16))
    question = VGroup(left(text("Como encontrar os", 32), 1.75, .85),
                      left(text("melhores compromissos?", 32, GOLD, bold=True), 1.75, .30),
                      left(text("Referência do problema", 21, MUTED), 1.75, -1.05),
                      left(text("Rego et al. (2022) · PeerJ CS 8:e844", 22, width=4.8), 1.75, -1.45))
    return VGroup(axis, labels), points, names, question


class IntroFabrica(CenaContinua):
    chapter, number = "INTRODUÇÃO", 1

    def construct(self):
        self.abrir()
        self.beat("fabrica", "Produzir custa tempo e energia")
        faixa, trilhos, maquinas, horas, linha, rotulos = self.base()
        self.play(LaggedStart(*(FadeIn(m, shift=pos(.4, 0)) for m in maquinas), lag_ratio=.3), run_time=1.2)
        self.play(Create(trilhos), FadeIn(horas), run_time=.8)
        t = ValueTracker(0)
        face, hand, digital = relogio(t)
        self.play(FadeIn(face), FadeIn(hand), FadeIn(digital), run_time=.6)
        self.play(Create(linha), FadeIn(rotulos), run_time=1.2)
        self.play(FadeIn(faixa), FadeIn(tag := text("ponta 18h–21h", 18, CORAL).move_to(
            pos(EIXO.at(11.5), FAIXAS[0] + .76))), run_time=.6)
        # As três máquinas ligadas o dia todo, em modo normal.
        potencia = sum(DADOS["power"])

        def gasto():
            now = t.get_value()
            peak = max(0, min(now, PONTA[1]) - PONTA[0])
            return potencia * (FORA * (now - peak) + NA_PONTA * peak)
        nome, valor = medidor("custo com tudo ligado", lambda: moeda(gasto()), -.80)
        taxa_nome, taxa = medidor("por hora", lambda: moeda(
            potencia * (NA_PONTA if PONTA[0] <= t.get_value() < PONTA[1] else FORA)), -1.75, CYAN, size=28)
        self.play(FadeIn(nome), FadeIn(valor), FadeIn(taxa_nome), FadeIn(taxa), run_time=.4)
        fluxo = always_redraw(lambda: VGroup(*(EIXO.caixa(i, 0, max(.001, t.get_value()), .5,
                                                        fill_color=CYAN, fill_opacity=.35) for i in range(3))))
        cursor = EIXO.cursor(t)
        self.add(fluxo, cursor)
        self.rodas(lambda i: "processando")
        self.play(t.animate.set_value(10), run_time=3, rate_func=linear)
        self.play(t.animate.set_value(13), run_time=2.4, rate_func=linear)
        self.play(t.animate.set_value(20), run_time=2, rate_func=linear)
        self.parar_rodas()
        self.hold()

        tudo = [faixa, trilhos, maquinas, horas, linha, rotulos, face, hand, digital, tag,
                nome, valor, taxa_nome, taxa, fluxo, cursor]
        self.beat("conflito", "Mesmas tarefas, dois planos", *tudo)
        t = ValueTracker(0)
        mini = [Eixo(-6.05, .275, (1.0, .3, -.4), .42), Eixo(1.0, .275, (1.0, .3, -.4), .42)]
        quadros, conjuntos = VGroup(), []
        for eixo, p, name, cor in zip(mini, (RAPIDO, BARATO), ("Terminar cedo", "Gastar menos"), (CYAN, GREEN)):
            quadros.add(VGroup(eixo.faixa_ponta(), eixo.trilhos(), eixo.horas(-.95, 4, 14),
                               left(text(name, 27, cor, bold=True), eixo.x, 1.85),
                               *(text(f"M{i + 1}", 17, MUTED).move_to(pos(eixo.x - .3, y))
                                 for i, y in enumerate(eixo.faixas))))
            itens = [parte for b in p["blocks"] for parte in eixo.progresso(b, t)]
            preparos = VGroup(*(eixo.setup(b) for b in p["blocks"]), *(eixo.espera(b) for b in p["blocks"]))
            a, b_ = medidor("tempo", lambda p=p: f"{min(p['cmax'], int(t.get_value()))} h", -1.75, cor, eixo.x)
            c, d = medidor("TEC", lambda p=p: moeda(custo_ate(p, t.get_value())), -1.75, GOLD, eixo.x + 2.2)
            conjuntos.append([preparos, *itens, eixo.cursor(t), a, b_, c, d])
        self.play(FadeIn(quadros), run_time=.7)
        self.play(*(FadeIn(m) for grupo in conjuntos for m in grupo), run_time=.8)
        self.play(t.animate.set_value(12), run_time=5, rate_func=linear)
        self.play(t.animate.set_value(20), run_time=4, rate_func=linear)
        queda = 100 * (1 - BARATO["tec"] / RAPIDO["tec"])
        fala = text(f"{BARATO['cmax'] - RAPIDO['cmax']} h a mais · {pt(queda, 0)}% mais barato", 30, GOLD, bold=True
                    ).move_to(pos(0, -2.78))
        self.play(FadeIn(fala, shift=pos(0, .15)), run_time=.6)
        self.hold()

        eixos, pontos, nomes, pergunta = quadro_objetivo()
        resumos = [VGroup(*(m.copy().clear_updaters() for m in g[-4:])) for g in conjuntos]
        self.beat("objetivo", "Cada plano vira um ponto", quadros, fala, *(m for g in conjuntos for m in g[:-4]))
        self.remove(*(m for g in conjuntos for m in g[-4:]))
        self.add(*resumos)
        self.play(Create(eixos[0]), FadeIn(eixos[1]), *(r.animate.scale(.6).move_to(pos(x, 1.9))
                                                      for r, x in zip(resumos, (-3.8, 2.2))), run_time=1)
        self.play(*(ReplacementTransform(r, p) for r, p in zip(resumos, pontos)), run_time=1.2)
        self.play(FadeIn(nomes), Create(seta := DashedLine(pontos[0].get_center(), pontos[1].get_center(), color=MUTED)),
                  run_time=.8)
        self.play(FadeOut(seta), *(FadeIn(q, shift=pos(0, .1)) for q in pergunta), run_time=.9)
        self.hold()


def celula(i, j, value, x=4.25, y=1.2, dx=.75, dy=.40, color=INK, bold=False):
    return text(str(value), 22, color, bold=bold).move_to(pos(x + j * dx, y - i * dy))


class ProblemaMaquinas(CenaContinua):
    chapter, number = "O PROBLEMA", 2

    def construct(self):
        self.abrir("Cada plano vira um ponto")
        anterior = quadro_objetivo()
        self.add(*anterior)
        self.beat("nao_relacionadas", "A duração depende da máquina", *anterior)
        faixa, trilhos, maquinas, horas, linha, rotulos = self.base()
        self.play(FadeIn(trilhos), FadeIn(horas), LaggedStart(*(FadeIn(m) for m in maquinas), lag_ratio=.2), run_time=.9)
        cab = VGroup(text("horas", 18, MUTED).move_to(pos(3.5, 1.65)),
                     *(text(f"M{j + 1}", 20, MUTED, bold=True).move_to(pos(4.25 + .75 * j, 1.65)) for j in range(3)))
        self.play(FadeIn(cab), run_time=.4)
        linhas = VGroup()
        barras = VGroup()
        for ordem, job in enumerate((0, 1)):
            origem = 1 + 7 * ordem
            nome = text(f"T{job + 1}", 21, CORES[job], bold=True).move_to(pos(3.5, 1.2 - .4 * job))
            valores = DADOS["processing"][job]
            melhor = valores.index(min(valores))
            viva = EIXO.tarefa(job, 0, origem, origem + valores[0])
            self.play(FadeIn(viva), FadeIn(nome), run_time=.5)
            grupo = VGroup(nome)
            for m, d in enumerate(valores):
                if m:
                    ghost = viva.copy().set_opacity(.22)
                    self.add(ghost)
                    barras.add(ghost)
                    self.play(Transform(viva, EIXO.tarefa(job, m, origem, origem + d)), run_time=.9)
                alvo = celula(job, m, d, color=GREEN if m == melhor else INK, bold=m == melhor)
                voo = text(f"{d} h", 22).next_to(viva, pos(1, 0), buff=.15)
                self.play(FadeIn(voo), run_time=.25)
                self.play(ReplacementTransform(voo, alvo), run_time=.6)
                grupo.add(alvo)
            fim = EIXO.tarefa(job, melhor, origem, origem + valores[melhor])
            self.play(Transform(viva, fim), run_time=.7)
            self.play(Indicate(viva, color=GREEN), run_time=.6)
            barras.add(viva)
            linhas.add(grupo)
        resto = VGroup(*(VGroup(text(f"T{j + 1}", 21, CORES[j], bold=True).move_to(pos(3.5, 1.2 - .4 * j)),
                                *(celula(j, m, d, color=GREEN if d == min(DADOS["processing"][j]) else INK,
                                         bold=d == min(DADOS["processing"][j]))
                                  for m, d in enumerate(DADOS["processing"][j]))) for j in range(2, 8)))
        self.play(LaggedStart(*(FadeIn(r, shift=pos(-.2, 0)) for r in resto), lag_ratio=.2), run_time=1.5)
        self.play(FadeIn(regra := text("verde · máquina mais rápida", 18, GREEN).move_to(pos(5.0, -2.25))), run_time=.4)
        self.hold()

        self.beat("modos", "O modo troca velocidade por potência", barras, linhas, resto, cab, regra)
        job, m = 4, 0
        base = DADOS["processing"][job][m]
        duracoes = [ceil(round(base / v, 9)) for v in DADOS["speed"]]
        self.play(maquinas[1:].animate.set_opacity(.15), trilhos[1:].animate.set_opacity(.15), run_time=.5)
        viva = EIXO.tarefa(job, m, 0, duracoes[1], 1)
        # A animação dos modos usa uma faixa ampliada para comparar as áreas.
        zoom = Eixo(-4.9, .85, (.05,), 1.2, 9)
        chao = Line(pos(-4.9, -.95), pos(2.75, -.95), color=GRID, stroke_width=2)
        self.play(GrowFromEdge(viva, LEFT), run_time=.6)

        def barra(mode):
            b = zoom.tarefa(job, 0, 0, duracoes[mode], mode)
            return b.shift(pos(0, -.95 - b.get_bottom()[1]))
        self.play(FadeOut(maquinas[0]), FadeOut(maquinas[1:]), FadeOut(trilhos), FadeOut(horas),
                  Create(chao), Transform(viva, barra(1)), run_time=1)
        eixo_txt = VGroup(text("largura = duração", 19, MUTED).move_to(pos(-1.0, -1.35)),
                          text("altura = potência", 19, MUTED).rotate(1.5708).move_to(pos(-5.25, .0)))
        self.play(FadeIn(eixo_txt), run_time=.4)
        quadro = VGroup(*(left(text(v, 18, MUTED), x, 1.65) for v, x in
                          zip(("modo", "horas", "energia"), (3.1, 4.75, 5.5))))
        self.play(FadeIn(quadro), run_time=.3)
        restos = VGroup()
        for k, (mode, nome, cor) in enumerate(((1, "normal", INK), (0, "rápido", CORAL), (2, "econômico", GREEN))):
            if k:
                ghost = viva[0].copy().set_fill(opacity=.12).set_stroke(MUTED, 1)
                self.add(ghost)
                restos.add(ghost)
                self.bring_to_front(viva)
                self.play(Transform(viva, barra(mode)), run_time=1.3)
            kwh = DADOS["power"][m] * DADOS["factor"][mode] * duracoes[mode]
            linha_modo = VGroup(left(text(nome, 22, cor, bold=True, width=1.4), 3.1, 1.1 - .62 * k),
                                left(text(f"{duracoes[mode]} h", 22), 4.75, 1.1 - .62 * k),
                                left(text(f"{pt(kwh, 0)} kWh", 22), 5.5, 1.1 - .62 * k))
            self.play(FadeIn(linha_modo, shift=pos(-.15, 0)), run_time=.6)
            restos.add(linha_modo)
        self.hold()

        self.beat("setup", "A ordem muda a preparação", viva, chao, eixo_txt, quadro, restos)
        faixa, trilhos, maquinas, horas, linha, rotulos = self.base()
        self.play(FadeIn(trilhos), FadeIn(horas), FadeIn(maquinas), run_time=.6)
        self.play(*(x.animate.set_opacity(.15) for x in (maquinas[1:], trilhos[1:])), run_time=.3)
        matriz = DADOS["setup"][0]
        grade = VGroup(left(text("setup em M1 (h)", 19, MUTED), 3.45, 1.75),
                       *(text(f"T{j + 1}", 20, CORES[j], bold=True).move_to(pos(4.35 + .7 * j, 1.25)) for j in range(3)),
                       *(text(f"T{i + 1}", 20, CORES[i], bold=True).move_to(pos(3.7, .7 - .55 * i)) for i in range(3)))
        cel = [[text("–" if i == j else str(matriz[i][j]), 24).move_to(pos(4.35 + .7 * j, .7 - .55 * i))
                for j in range(3)] for i in range(3)]
        grade.add(*(c for row in cel for c in row))
        grade.add(left(text("linha: anterior · coluna: próxima", 16, MUTED, width=3.2), 3.45, -1.0))
        a, b = 0, 1
        dur = [DADOS["processing"][j][0] for j in (a, b)]

        def ordem(x, y):
            s = matriz[x][y]
            return (EIXO.tarefa(x, 0, 2, 2 + dur[x]), EIXO.tarefa(y, 0, 2 + dur[x] + s, 2 + dur[x] + s + dur[y]),
                    EIXO.caixa(0, 2 + dur[x], 2 + dur[x] + s, .45, fill_color=MUTED, fill_opacity=.65))
        p1, p2, prep = ordem(a, b)
        self.play(FadeIn(grade), FadeIn(p1), FadeIn(p2), run_time=.7)
        foco = SurroundingRectangle(cel[a][b], color=GOLD, buff=.12)
        rot = text(f"setup {matriz[a][b]} h", 20, MUTED).next_to(prep, pos(0, -1), buff=.3)
        self.play(GrowFromEdge(prep, LEFT), Create(foco), FadeIn(rot), run_time=.9)
        self.wait(.6)
        q1, q2, prep2 = ordem(b, a)
        rot2 = text(f"setup {matriz[b][a]} h", 20, MUTED).next_to(prep2, pos(0, -1), buff=.3)
        self.play(p1.animate(path_arc=1.6).move_to(q2), p2.animate(path_arc=1.6).move_to(q1),
                  Transform(prep, prep2), Transform(rot, rot2),
                  Transform(foco, SurroundingRectangle(cel[b][a], color=GOLD, buff=.12)), run_time=1.8)
        seta = text(f"termina {matriz[a][b] - matriz[b][a]} h antes", 21, GREEN).move_to(pos(EIXO.at(16), FAIXAS[0] + .3))
        self.play(FadeIn(seta), run_time=.5)
        self.hold()

        self.beat("ponta", "O instante de início define o custo", grade, foco, rot, seta, p1, p2, prep)
        self.play(*(FadeIn(x) for x in (faixa, linha, rotulos)), run_time=.6)
        self.ponta()

    def ponta(self):
        job, m = 2, 0
        state = dict(job=job, dur=DADOS["processing"][job][m])
        power = DADOS["power"][m]
        s = ValueTracker(2)

        def custo():
            peak = max(0, min(s.get_value() + state["dur"], PONTA[1]) - max(s.get_value(), PONTA[0]))
            return power * (FORA * (state["dur"] - peak) + NA_PONTA * peak)

        def corpo():
            start, end = s.get_value(), s.get_value() + state["dur"]
            g = VGroup(*EIXO.tarefa(state["job"], m, start, end))
            a, b = max(start, PONTA[0]), min(end, PONTA[1])
            if b > a:
                g.insert(1, EIXO.caixa(m, a, b, fill_color=CORAL))
            return g
        bloco = always_redraw(corpo)
        nome, valor = medidor("custo desta tarefa", lambda: moeda(custo()), .95)
        self.play(FadeIn(bloco), FadeIn(nome), FadeIn(valor), run_time=.5)
        caso = None
        # Ordem do percurso; o número é o do caso em Rego et al. (2022).
        for numero, descr, start, pequena in ((1, "termina antes da ponta", 4, 0), (2, "entra na ponta", 7, 0),
                                              (6, "atravessa a ponta inteira", 9, 0), (3, "fica dentro da ponta", 10, 1),
                                              (4, "começa na ponta e sai", 11, 0), (5, "começa depois da ponta", 13, 0)):
            novo = VGroup(left(text(f"Caso {numero}", 30, CYAN, bold=True), 3.75, -.25),
                          left(text(descr, 20, width=2.9), 3.75, -.75))
            job2 = 7 if pequena else 2
            if job2 != state["job"]:
                self.play(FadeOut(bloco), *([FadeOut(caso)] if caso is not None else []), run_time=.3)
                caso = None
                state.update(job=job2, dur=DADOS["processing"][job2][m])
                s.set_value(start)
                bloco = always_redraw(corpo)
                self.play(FadeIn(bloco), run_time=.3)
            anims = [s.animate.set_value(start), FadeIn(novo)]
            if caso is not None:
                anims.append(FadeOut(caso))
            self.play(*anims, run_time=1.3)
            self.wait(.5)
            caso = novo
        # T8 → T3 em M1: a preparação e a espera ficam antes do início deslocado.
        prep = DADOS["setup"][0][7][2]
        antes = EIXO.tarefa(7, 0, 4, 7)
        box = EIXO.caixa(0, 7, 7 + prep, .45, fill_color=MUTED, fill_opacity=.65)
        self.play(FadeIn(antes), FadeIn(box), s.animate.set_value(7 + prep), FadeOut(caso), run_time=1.2)
        caso = VGroup(left(text("Sem espera", 30, CORAL, bold=True), 3.75, -.25),
                      left(text("começa logo após o setup", 20, width=2.9), 3.75, -.75))
        self.play(FadeIn(caso), run_time=.4)
        self.wait(.6)
        fim = VGroup(left(text("Espera voluntária", 28, GOLD, bold=True, width=2.95), 3.75, -.25),
                     left(text("termina depois e custa menos", 20, width=2.9), 3.75, -.75))
        espera = always_redraw(lambda: EIXO.caixa(0, 7 + prep, s.get_value(), .45, fill_color=GOLD,
                                                  fill_opacity=.15, stroke_color=GOLD, stroke_width=1.5))
        self.add(espera)
        self.play(s.animate.set_value(13), FadeOut(caso), FadeIn(fim), run_time=2.2)
        leg = VGroup(text("setup", 17, MUTED).move_to(pos(EIXO.at(7 + prep / 2), FAIXAS[0] - .42)),
                     text("espera", 17, GOLD).move_to(pos(EIXO.at(11), FAIXAS[0] - .42)))
        self.play(FadeIn(leg), run_time=.4)
        self.hold()


def quadro_ponta(cena):
    """Quadro final de ProblemaMaquinas, refeito sem updaters."""
    itens = cena.base()
    cena.maquinas[1:].set_opacity(.15)
    cena.trilhos[1:].set_opacity(.15)
    prep = DADOS["setup"][0][7][2]
    dur = DADOS["processing"][2][0]
    custo = DADOS["power"][0] * FORA * dur
    local = VGroup(EIXO.tarefa(7, 0, 4, 7),
                   EIXO.caixa(0, 7, 7 + prep, .45, fill_color=MUTED, fill_opacity=.65),
                   EIXO.caixa(0, 7 + prep, 13, .45, fill_color=GOLD, fill_opacity=.15, stroke_color=GOLD, stroke_width=1.5),
                   EIXO.tarefa(2, 0, 13, 13 + dur),
                   left(text("custo desta tarefa", 19, MUTED), 3.75, 1.29), left(rotulo(moeda(custo), 36, GOLD, True), 3.75, .85),
                   left(text("Espera voluntária", 28, GOLD, bold=True, width=2.95), 3.75, -.25),
                   left(text("termina depois e custa menos", 20, width=2.9), 3.75, -.75),
                   text("setup", 17, MUTED).move_to(pos(EIXO.at(7 + prep / 2), FAIXAS[0] - .42)),
                   text("espera", 17, GOLD).move_to(pos(EIXO.at(11), FAIXAS[0] - .42)))
    return itens, local


class ProblemaSimulacao(CenaContinua):
    chapter, number = "O PROBLEMA EM EXECUÇÃO", 3

    def construct(self):
        self.abrir("O instante de início define o custo")
        itens, local = quadro_ponta(self)
        self.add(*itens, local)
        self.beat("alocacao", "Montando um plano", local)
        novas = VGroup(*(maquina(i) for i in range(3)))
        trilhos = EIXO.trilhos()
        self.play(Transform(self.maquinas, novas), Transform(self.trilhos, trilhos), run_time=.4)
        p = MEIO
        fila = VGroup(*(VGroup(Rectangle(width=.72, height=.42, stroke_width=0, fill_color=CORES[j], fill_opacity=1),
                               rotulo(f"T{j + 1}", 19, "#14171c", True)).move_to(pos(-4.6 + .92 * j, 2.08)) for j in range(8)))
        self.play(LaggedStart(*(FadeIn(f, shift=pos(0, -.3)) for f in fila), lag_ratio=.12), run_time=1.1)
        nomes = ("rápido", "normal", "econômico")
        guia = left(text("(tarefa, modo, espera)", 20, MUTED), 3.55, 1.65)
        self.play(FadeIn(guia), run_time=.3)
        tarefas, preparos, esperas, triplas = {}, {}, {}, VGroup()
        for k, b in enumerate(sorted(p["blocks"], key=lambda b: (b["start"], b["machine"]))):
            j = b["job"]
            preparos[j], esperas[j], alvo = EIXO.setup(b), EIXO.espera(b), EIXO.bloco(b)
            tripla = left(text(f"M{b['machine'] + 1}  ( T{j + 1}, {nomes[b['mode']]}, {b['wait']} h )", 20, CORES[j], width=3.1),
                          3.55, 1.22 - .38 * k)
            pre = []
            if b["setup"]:
                pre.append(GrowFromEdge(preparos[j], LEFT))
            else:
                self.add(preparos[j])
            if b["wait"]:
                pre.append(FadeIn(esperas[j]))
            else:
                self.add(esperas[j])
            if pre:
                self.play(*pre, run_time=.4)
            self.play(ReplacementTransform(fila[j], alvo, path_arc=-.5), FadeIn(tripla), run_time=.9)
            tarefas[j] = alvo
            triplas.add(tripla)
        self.hold()

        self.beat("execucao", "O plano em execução", guia, triplas)
        t = ValueTracker(0)
        face, hand, digital = relogio(t)
        a, b_ = medidor("TEC acumulado", lambda: moeda(custo_ate(p, t.get_value())), -.75, GOLD, 3.75, 34)
        c, d = medidor("Cmax", lambda: f"{p['cmax']} h" if t.get_value() >= p["cmax"] - 1e-6 else "—", -1.65, CYAN, 3.75, 34)
        self.play(*(FadeIn(x) for x in (face, hand, digital, a, b_, c, d)), run_time=.6)
        vivos = [x for b in p["blocks"] for x in EIXO.progresso(b, t)]
        self.remove(*tarefas.values())
        self.add(*vivos)
        cursor = EIXO.cursor(t)
        estados = always_redraw(lambda: VGroup(*(rotulo(e, 14, ESTADOS[e] if e != "livre" else MUTED).move_to(
            pos(-6.12, FAIXAS[i] - .30)) for i in range(3) for e in (estado(p, i, t.get_value()),))))
        self.play(FadeIn(cursor), FadeIn(estados), run_time=.4)
        self.rodas(lambda i: estado(p, i, t.get_value()))
        self.play(t.animate.set_value(10), run_time=7, rate_func=linear)
        self.play(t.animate.set_value(13), run_time=4, rate_func=linear)
        self.play(t.animate.set_value(15), run_time=2.4, rate_func=linear)
        self.parar_rodas()
        x = EIXO.at(p["cmax"])
        marca = VGroup(DashedLine(pos(x, 1.75), pos(x, -1.6), color=CYAN),
                       text("Cmax", 22, CYAN, bold=True).move_to(pos(x, 1.98)))
        assert abs(custo_ate(p, t.get_value()) - p["tec"]) < 1e-6
        self.play(Create(marca[0]), FadeIn(marca[1]), run_time=.7)
        self.hold()

        fixos = [EIXO.bloco(b) for b in p["blocks"]]
        self.remove(*vivos)
        self.add(*fixos)
        tarefas = {b["job"]: f for b, f in zip(p["blocks"], fixos)}
        self.beat("compromisso", "Mudar o plano move o ponto", face, hand, digital, a, b_, c, d, cursor, estados)
        axis, labels = plano_objetivos((5.02, .35), 2.75, 2.7)
        ponto = Dot(axis.c2p(MEIO["cmax"], MEIO["tec"]), radius=.11, color=GOLD)
        valor = text(f"{MEIO['cmax']} h · {moeda(MEIO['tec'])}", 25, GOLD, bold=True).move_to(pos(5.0, -2.12))
        self.play(Create(axis), FadeIn(labels), FadeIn(ponto), FadeIn(valor), run_time=.9)
        for q in (RAPIDO, BARATO, MEIO):
            self.add(Dot(ponto.get_center(), radius=.06, color=MUTED))
            x = EIXO.at(q["cmax"])
            anims = [Transform(marca, VGroup(DashedLine(pos(x, 1.75), pos(x, -1.6), color=CYAN),
                                             text("Cmax", 22, CYAN, bold=True).move_to(pos(x, 1.98)))),
                     ponto.animate.move_to(axis.c2p(q["cmax"], q["tec"])),
                     Transform(valor, text(f"{q['cmax']} h · {moeda(q['tec'])}", 25, GOLD, bold=True).move_to(pos(5.0, -2.12)))]
            for b in q["blocks"]:
                j = b["job"]
                anims += [Transform(tarefas[j], EIXO.bloco(b)), Transform(preparos[j], EIXO.setup(b)),
                          Transform(esperas[j], EIXO.espera(b))]
            self.play(*anims, run_time=2.2, rate_func=smooth)
            self.wait(.7)
        todos = dots(axis, FRENTE, GOLD, .06)
        self.play(LaggedStart(*(FadeIn(x) for x in todos), lag_ratio=.15), run_time=1.2)
        self.play(Create(staircase(axis, FRENTE, GOLD)), run_time=1)
        modelo = VGroup(text("decidir: máquina · ordem · modo · espera", 22, INK).move_to(pos(-3.2, -2.45)),
                        text("respeitar: uma vez cada tarefa · setup · horizonte", 22, MUTED).move_to(pos(-3.2, -2.95)),
                        formula(r"\min\;(C_{\mathrm{max}},\;TEC)", 3.6, .38, GOLD).move_to(pos(4.6, -2.86)))
        self.play(FadeOut(self.tarifa), FadeOut(self.tarifa_rotulos), run_time=.4)
        self.play(LaggedStart(*(FadeIn(x, shift=pos(0, .12)) for x in modelo), lag_ratio=.35), run_time=1.3)
        self.hold()
