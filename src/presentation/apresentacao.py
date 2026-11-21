"""Apresentação de MHM. As seções Manim são os pontos de pausa da fala."""

from collections import Counter

from manim import (
    Arrow, Create, DashedLine, Dot, FadeIn, FadeOut, GrowFromCenter, Indicate, LaggedStart,
    Line, Polygon, Rectangle, Transform, VGroup, VMobject,
)
import numpy as np

from visual import (
    COLORS, CORAL, CYAN, FUNDO, GIANT, GOLD, GREEN, GRID, HERE, INK, MUTED, OUTPUT,
    SMALL, DeckScene, axes, dots, formula, gantt, left, lines, pos, pt,
    read_json, rule, small_fronts, staircase, table, text,
)


def note(statement, color=MUTED, y=-2.90):
    return left(text(statement, 22, color), -6.55, y)


def side(*statements, y=1.13, x=1.05, width=5.42):
    return lines(statements, x, y, width=width, size=28, gap=.71)


def labeled_dots(axis, coordinates, color):
    return VGroup(*(VGroup(point, text(name, 24, color, bold=True).move_to(point.get_center() + pos(dx, dy)))
                    for (x, y, name, dx, dy), point in zip(coordinates, dots(axis, [(x, y) for x, y, *_ in coordinates], color))))


def data_path(*parts):
    return OUTPUT.joinpath(*parts)


class Abertura(DeckScene):
    chapter, number = "INTRODUÇÃO", 1

    def construct(self):
        self.beat("pergunta", "Escalonamento com custo de energia", "Rego et al. (2022) · PeerJ Computer Science 8:e844",
                  "Máquinas paralelas não relacionadas · UPMSP")
        axis, labels = axes(center=(2.7, -.59), width=6.35, height=3.45,
                            x_label="Tempo de conclusão", y_label="Custo de energia")
        front = [(1.1, 4.5), (2.2, 3.15), (3.5, 2.45), (4.85, 1.65), (6.0, 1.1)]
        q = lines(("Quando termina a produção?", "Quanto custa a energia?"), -6.5, .78, width=5.6, size=39, gap=1.09)
        self.reveal(q)
        self.play(Create(axis), FadeIn(labels), run_time=.6)
        self.play(Create(staircase(axis, front, GOLD)), FadeIn(dots(axis, front, GOLD)), run_time=1.08)
        self.reveal(note("Cada ponto representa um escalonamento.", y=-3.12))
        self.hold()

        self.beat("objetivos", "Objetivos do estudo", "README.md · implementação e campanha experimental",
                  "Minimizar simultaneamente o makespan e o custo total de energia.")
        objectives = [
            ("Certificar", "Obter fronteiras de referência para instâncias pequenas."),
            ("Construir", "Testar alocação, mudança de modo e inserção de ociosidade."),
            ("Comparar", "Medir cinco implementações com as configurações registradas."),
        ]
        blocks = VGroup(*(VGroup(left(text(key, 36, color, bold=True), -6.35, 1.24 - i * 1.12),
                                 left(text(value, 28, width=9.4), -3.21, 1.24 - i * 1.12),
                                 rule(.77 - i * 1.12))
                          for i, ((key, value), color) in enumerate(zip(objectives, (GOLD, CYAN, GREEN)))))
        self.play(LaggedStart(*(FadeIn(row) for row in blocks), lag_ratio=.27), run_time=1.4)
        self.reveal(note("O estudo usa o modelo do artigo como ponto de partida e avalia outras estratégias de busca."))
        self.hold()


class Fundamentos(DeckScene):
    chapter, number = "REFERENCIAL TEÓRICO", 2

    def construct(self):
        self.beat("escalonamento", "O que muda de uma máquina para outra?",
                  "Rego et al. (2022) · problem.py · schedule.py", "A mesma tarefa pode ter durações diferentes em cada máquina.")
        chart, job = gantt([(0, 0, 0, 2), (0, 1, 2.5, 5), (1, 2, 0, 1.4), (1, 3, 4, 6)],
                           total=8, x=-5.45, y=.62, width=8.35, lane=1.02,
                           peaks=[(3.1, 4.4)], setups=[(0, 2, 2.5), (1, 1.4, 1.9)])
        self.reveal(chart)
        self.play(LaggedStart(*(GrowFromCenter(block) for block in job), lag_ratio=.24), run_time=1.15)
        self.reveal(lines(("Faixa coral · tarifa de ponta", "Bloco cinza · preparação", "Lacuna · espera opcional"),
                          3.24, .90, size=24, width=3.18, gap=.65))
        finish_x = -5.45 + 8.35 * 6 / 8
        mark = DashedLine(pos(finish_x, 1.34), pos(finish_x, -.97), color=GOLD)
        self.play(Create(mark), FadeIn(text("Cmax", 25, GOLD).move_to(pos(finish_x, 1.64))), run_time=.65)
        self.reveal(note("Exemplo esquemático · cada tarefa ocupa a máquina até terminar, sem interrupção."))
        self.hold()

        self.beat("formulacao", "Decisões, restrições e objetivos", "problem.py · schedule.py · cpsat.py",
                  "Escolher máquina, modo e início para cada tarefa j.")
        equations = VGroup(
            formula(r"\sum_{i,h,\ell} X_{ijh\ell}=1 \quad (\forall j)", 6.1).move_to(pos(-3.26, .91)),
            formula(r"d_{ij\ell}=\left\lceil p_{ji}/v_\ell\right\rceil,\quad C_j=h_j+d_{ij\ell}", 6.35).move_to(pos(-3.26, -.02)),
            formula(r"h_k\geq C_j+s_{ijk},\quad 0\leq h_j<C_j\leq H", 6.35).move_to(pos(-3.26, -.95)),
        )
        self.reveal(equations[0], left(text("Uma escolha por tarefa", 25, CYAN), .47, .91))
        self.reveal(equations[1], left(text("Duração inteira e instante de término", 25, CYAN), .47, -.02))
        self.reveal(equations[2], left(text("Sem sobreposição, com setup e horizonte", 25, CYAN), .47, -.95))
        obj = formula(r"\min\,(C_{\mathrm{max}},\,TEC),\qquad C_{\mathrm{max}}=\max_j C_j,\qquad"
                      r"TEC=\sum_j\pi_{i_j}\lambda_{\ell_j}\frac{24}{N_{\mathrm{dia}}}\sum_{t=h_j}^{C_j-1}\tau_t",
                      width=12.05, height=.87, color=GOLD).move_to(pos(0, -2.24))
        self.reveal(rule(-1.55), obj, note("N_dia é o número de intervalos por dia. Setup e espera ficam fora do TEC.", y=-3.04))
        self.hold()

        self.beat("pareto", "Dominância e fronteira de Pareto", "problem.py · Rego et al. (2022)",
                  "Os dois objetivos são de minimização.")
        axis, labels = axes()
        front = [(1.0, 4.8), (2.5, 3), (4.2, 1.85), (5.65, .85)]
        dominated = [(3.67, 4.26), (5.4, 3.4), (6.17, 2.35)]
        corner = axis.c2p(6.75, 5.72)
        start = axis.c2p(*front[1])
        shadow = Polygon(start, pos(corner[0], start[1]), corner, pos(start[0], corner[1]),
                         fill_color=CYAN, fill_opacity=.11, stroke_width=0)
        self.reveal(axis, labels, dots(axis, front, GOLD), dots(axis, dominated, MUTED))
        self.reveal(shadow, side("P domina Q se for tão bom", "nos dois objetivos e melhor", "em pelo menos um.", y=1.15))
        self.reveal(labeled_dots(axis, [(2.5, 3, "P", -.20, -.24)], GOLD),
                    labeled_dots(axis, [(3.67, 4.26, "Q", .22, .23)], MUTED))
        self.play(Create(staircase(axis, front, GOLD)), run_time=.88)
        self.reveal(note("A fronteira reúne os compromissos não dominados. Pontos e comprimentos esquemáticos."))
        self.hold()


class Exatos(DeckScene):
    chapter, number = "METODOLOGIA · MÉTODOS EXATOS", 3

    def construct(self):
        self.beat("cp_sat", "CP-SAT certifica pontos por limites sucessivos", "cpsat.py · OR-Tools",
                  "Um intervalo opcional por tarefa, máquina e modo. Um circuito por máquina.")
        axis, labels = axes()
        coords = [(1.2, 5.0), (2.4, 3.55), (3.85, 2.5), (5.65, .95)]
        self.reveal(axis, labels)
        desc = side("Minimiza Cmax", "Desempata por TEC", "Aperta o limite de TEC")
        self.reveal(desc[0])
        for i, point in enumerate(coords):
            cap_y = max(.55, point[1] - .36)
            cap = DashedLine(axis.c2p(0, cap_y), axis.c2p(6.65, cap_y), color=CYAN, dash_length=.14)
            self.play(FadeIn(dots(axis, [point], GOLD)), Create(cap), run_time=.48)
            if i < len(coords) - 1:
                self.play(FadeOut(cap), run_time=.16)
        self.reveal(desc[1], desc[2], note("Varredura esquemática. O status do solver determina se há certificado."))
        self.hold()

        self.beat("backtracking", "Backtracking poda atribuições parciais", "custom_exact.py · problem.py",
                  "Cada nível atribui uma posição (máquina, modo, início) a uma tarefa.")
        coords = [(-2.60, 1.37), (-4.53, .38), (-.65, .38), (-5.63, -.73), (-3.54, -.73), (-1.74, -.73), (.46, -.73)]
        edges = VGroup(*(Line(pos(*coords[a]), pos(*coords[b]), color=GRID, stroke_width=2)
                         for a, b in [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)]))
        nodes = VGroup(*(VGroup(Rectangle(width=1.22, height=.48, stroke_width=1.3, stroke_color=accent,
                                            fill_color=FUNDO, fill_opacity=1).move_to(pos(*point)),
                                 text(label, 20, accent, width=1.14).move_to(pos(*point)))
                         for point, label, accent in zip(coords, ("início", "posição A", "posição B", "colisão", "viável", "limite", "viável"),
                                                         (INK, INK, INK, CORAL, GOLD, CORAL, GOLD))))
        self.play(Create(edges), FadeIn(nodes), run_time=.85)
        self.play(*(Indicate(nodes[i], color=CORAL, scale_factor=1.12) for i in (3, 5)), run_time=.7)
        self.play(*(FadeOut(node) for node in (nodes[3], nodes[5], edges[2], edges[4])), run_time=.42)
        self.reveal(side("Filtra sobreposições", "Usa limites otimistas", "Verifica adjacência e setup", "quando a ordem se define", x=1.28, y=1.35, width=5.07),
                    note("A posição futura de uma tarefa ainda pode alterar quem é consecutivo."))
        self.hold()

        self.beat("dp", "A DP reaproveita estados por subconjunto", "custom_exact_dp.py",
                  "O prefixo relevante termina em uma tarefa e carrega um rótulo de tempo e energia.")
        groups = [
            ("Estado parcial", "{A, B} · última B", -4.37, CYAN),
            ("Adição de tarefa", "setup B→C + C", 0, GOLD),
            ("Novo estado", "{A, B, C} · última C", 4.37, GREEN),
        ]
        panels = VGroup(*(VGroup(text(name, 27, accent).move_to(pos(x, .75)),
                                  text(value, 31, bold=True, width=3.66).move_to(pos(x, .03)))
                          for name, value, x, accent in groups))
        arrows = VGroup(*(Arrow(pos(x - .34, .03), pos(x + .34, .03), buff=0, color=MUTED, stroke_width=2)
                          for x in (-2.17, 2.17)))
        self.reveal(panels[0])
        self.play(Create(arrows[0]), FadeIn(panels[1]), run_time=.75)
        self.play(Create(arrows[1]), FadeIn(panels[2]), run_time=.75)
        self.reveal(left(text("Mesmo estado", 26, MUTED), -6.15, -1.08))
        keep = formula(r"(t_A,e_A)", height=.28, color=GREEN).move_to(pos(-2.4, -1.08))
        remove = formula(r"(t_B,e_B)", height=.28, color=CORAL).move_to(pos(-.12, -1.08))
        criterion = formula(r"t_A\leq t_B,\quad e_A\leq e_B", height=.29, color=MUTED).move_to(pos(3.4, -1.08))
        self.reveal(keep, remove, criterion)
        self.play(FadeOut(remove), run_time=.43)
        self.reveal(left(text("Entre máquinas: particiona tarefas sob cada limite de makespan.", 27, width=12.1), -6.15, -1.90))
        self.reveal(note("O número de subconjuntos cresce exponencialmente. O problema geral é NP-difícil."))
        self.hold()

        self.beat("certificados", "O que ficou certificado nas instâncias pequenas?", "data/output/analise_metodos_exatos.json",
                  "Tempos dos resultados históricos registrados, em segundos.")
        all_results = read_json(data_path("analise_metodos_exatos.json"))["resumo_resultados"]["results"]
        rows = []
        for n, fragment, name in ((6, "cp_sat", "CP-SAT"), (6, "custom_exact_propagation", "Backtracking"),
                                  (6, "epsilon_exact_dp", "DP própria"), (10, "cp_sat", "CP-SAT"),
                                  (10, "epsilon_exact_dp", "DP própria")):
            row = next(r for r in all_results if r["instance"].startswith(f"{n}_2_") and "derivada" not in r["instance"]
                       and fragment in r["method"])
            rows.append((n, name, row["points"], pt(row["elapsed_seconds"], 2),
                         "Provada" if row["pareto_proven"] else "Parcial"))
        grid = table(("Tarefas", "Método", "Pontos", "Tempo (s)", "Fronteira"), rows,
                     (1.65, 3.15, 1.75, 2.5, 3.35), colors=[GOLD, CORAL, GOLD, CORAL, GOLD])
        self.reveal(grid)
        self.reveal(note("Provar a frente exige mais que encontrar pontos viáveis. A DP seguiu para a campanha."))
        self.hold()


class Heuristicas(DeckScene):
    chapter, number = "METODOLOGIA · HEURÍSTICAS", 4

    def construct(self):
        self.beat("construtiva", "A construtiva testa onde inserir a tarefa", "heuristics/construtiva/construtiva.py",
                  "Três ordens LPT × 11 pesos por padrão. A inserção altera máquina, posição e modo.")
        chart, blocks = gantt([(0, 0, 0, 2), (0, 1, 2.5, 4.4), (0, 2, 5, 6.8),
                               (1, 3, 0, 1.4), (1, 4, 2.05, 4.1), (1, 2, 4.7, 7.55)],
                              total=8.2, x=-5.35, width=10.0, y=.94, lane=1.06,
                              setups=[(0, 2, 2.5), (1, 1.4, 2.05)])
        self.reveal(chart, VGroup(blocks[0], blocks[1], blocks[3], blocks[4]))
        self.play(FadeIn(blocks[2]), FadeIn(blocks[5]), run_time=.62)
        self.play(Indicate(blocks[2], color=GOLD), FadeOut(blocks[5]), run_time=.65)
        score = formula(r"\alpha\frac{C_{\mathrm{max}}}{H}+(1-\alpha)\frac{TEC}{\mathrm{max\_cost}}",
                        color=GOLD).move_to(pos(0, -1.72))
        self.reveal(score, note("Esquema de duas alternativas. Depois da construção, trocas de modo podem economizar TEC."))
        self.hold()

        self.beat("ociosidade", "A ociosidade muda quando a tarefa roda", "heuristics/ociosidade/ociosidade.py",
                  "A alocação e a ordem vêm da construtiva. A DP escolhe tempos e, por padrão, também modos.")
        initial = [(0, 0, 0, 1.8), (0, 1, 2.15, 4.4), (1, 2, 0, 1.42), (1, 3, 1.8, 3.10)]
        chart, start = gantt(initial, total=8.4, x=-5.45, width=10.3, y=.86, lane=.98,
                             peaks=[(2.7, 4.7)], setups=[(0, 1.8, 2.15), (1, 1.42, 1.8)])
        _, end = gantt([initial[0], (0, 1, 4.7, 6.95), initial[2], initial[3]],
                       total=8.4, x=-5.45, width=10.3, y=.86, lane=.98)
        self.reveal(chart, start)
        self.play(Transform(start[1], end[1]), run_time=1.35)
        self.reveal(lines(("A segunda tarefa da M1 passa para fora da ponta.",
                           "Cada limite de término permite um novo balanço entre Cmax e TEC."),
                          -5.5, -1.64, width=12, gap=.65), note("Exemplo esquemático · tarefa, máquina e sequência preservadas."))
        self.hold()

        self.beat("comparacao", "Ajustar inícios recupera pontos da fronteira", "data/baselines · saídas das duas heurísticas",
                  "Instância de seis tarefas. Os eixos mostram os dois objetivos nas unidades registradas.")
        axis, labels = axes((90, 235, 35), (120, 255, 30), center=(-2.36, -.31), width=7.35, height=3.65,
                            x_label="Cmax (min)", y_label="TEC", numbers=True)
        self.reveal(axis, labels)
        fronts = small_fronts()
        for i, alg in enumerate(("exact_dp", "construtiva", "ociosidade")):
            coordinates = [(p["makespan"], p["tec"]) for p in fronts[alg]]
            color = COLORS[alg]
            name = {"exact_dp": "DP certificada", "construtiva": "Construtiva", "ociosidade": "Ociosidade"}[alg]
            plot = staircase(axis, coordinates, color, width=3.75 - i * .75)
            legend = left(text(f"{name}  ·  {len(coordinates)} pontos", 27, color, width=4.26), 2.1, .95 - i * .71)
            self.play(Create(plot), FadeIn(legend), run_time=.76)
        self.reveal(note("As cadeias se sobrepõem onde devolvem o mesmo par de objetivos.", y=-3.13))
        self.hold()


class Metaheuristicas(DeckScene):
    chapter, number = "METODOLOGIA · META-HEURÍSTICAS", 5

    def construct(self):
        self.beat("representacao", "O que a busca consegue mudar?", "schedule.py · spea2.py · age.py · moead.py · vns_vnd.py",
                  "Uma sequência por máquina. Cada tarefa é uma tripla (tarefa, modo, espera).")
        start_rows = [(0, 0, 0, 2.1), (0, 1, 2.4, 4.7), (1, 2, 0, 1.7), (1, 3, 2.3, 4.9)]
        chart, start = gantt(start_rows, total=7.7, x=-5.4, width=10.0, y=.75, lane=.88)
        end_rows = [start_rows[0], (1, 1, 4.15, 6.05), start_rows[2], (1, 3, 2.1, 3.88)]
        _, end = gantt(end_rows, total=7.7, x=-5.4, width=10.0, y=.75, lane=.88)
        self.reveal(chart, start)
        self.play(Transform(start[1], end[1]), Transform(start[3], end[3]), run_time=1.25)
        self.reveal(lines(("Na M2, a tripla da tarefa 2 registra tarefa, modo e espera.",
                           "O mesmo avaliador verifica todas as soluções e calcula Cmax e TEC."),
                          -5.4, -1.6, width=12.1, gap=.66), note("Exemplo esquemático de alteração de máquina e modo."))
        self.hold()

        self.beat("spea2", "SPEA2 usa força e densidade para selecionar", "spea2.py · pymoo 0.6.2 · Zitzler, Laumanns e Thiele (2001)",
                  "A versão incremental gera um descendente por iteração após a partida.")
        axis, labels = axes()
        support = [(1.35, 4.27), (2.77, 2.73), (4.07, 1.98), (4.55, 1.66), (5.5, .88)]
        dominated = [(3.68, 3.50), (5.2, 3.66), (5.96, 2.48)]
        survivors = dots(axis, support, COLORS["spea2"])
        below = dots(axis, dominated, MUTED)
        self.reveal(axis, labels, survivors, below)
        p, q = axis.c2p(*support[1]), axis.c2p(*dominated[0])
        strength = Arrow(p, q, buff=.1, color=GOLD, stroke_width=2)
        distance = DashedLine(axis.c2p(*support[2]), axis.c2p(*support[3]), dash_length=.05, color=GOLD)
        self.play(Create(strength), Create(distance), run_time=.72)
        self.reveal(side("Força · quantos pontos domina", "Densidade · distância local", "Prioriza os não dominados", "Completa ou poda a população", y=1.18),
                    note("A seleção mantém uma população de tamanho fixo. Geometria esquemática."))
        self.hold()

        self.beat("moead", "MOEA/D decompõe a busca em subproblemas", "moead.py · pymoo 0.6.2 · Zhang e Li (2007)",
                  "Cada direção define pesos para um subproblema escalar de Tchebycheff.")
        axis, labels = axes()
        ideal = axis.c2p(.28, .25)
        targets = [(1.20, 4.85), (2.1, 4.0), (3.0, 3.09), (4.4, 2.45), (5.9, 1.1)]
        vectors = VGroup(*(Arrow(ideal, axis.c2p(*p), buff=0, color=COLORS["moead"], stroke_width=2.1)
                           for p in targets))
        self.reveal(axis, labels, dots(axis, [(.28, .25)], CYAN))
        self.play(LaggedStart(*(Create(vector) for vector in vectors), lag_ratio=.17), run_time=1.25)
        nearby = dots(axis, [targets[i] for i in (1, 2, 3)], GOLD, radius=.072)
        self.play(Indicate(vectors[2], color=GOLD, scale_factor=1), FadeIn(nearby), run_time=.69)
        self.reveal(side("Uma direção por indivíduo", "Acasalamento usa vizinhos", "Ideal atualizado pela busca", y=1.14),
                    note("As setas representam direções de referência. Os pontos obtidos podem ter outro espaçamento."))
        self.hold()

        self.beat("age", "AGE-MOEA estima a geometria da frente", "age.py · pymoo 0.6.2 · Panichella (2019)",
                  "A primeira frente normaliza os objetivos e orienta a estimativa de curvatura.")
        axis, labels = axes()
        pts = [(x, 1.0 + 3.5 * (1 - (x - 1) / 5.15) ** 2) for x in np.linspace(1, 6.15, 8)]
        estimates = [(x, 4.55 - 3.61 * (x - 1) / 5.15) for x, _ in pts]
        def curve(pairs, color):
            return VMobject(stroke_width=3, stroke_color=color).set_points_smoothly([axis.c2p(*pair) for pair in pairs])

        geometry = curve(estimates, MUTED)
        self.reveal(axis, labels, dots(axis, pts, COLORS["age"]))
        self.play(Create(geometry), run_time=.65)
        self.play(Transform(geometry, curve(pts, COLORS["age"])), run_time=1.1)
        self.reveal(side("Estima o expoente da norma", "Equilibra distância ao ideal", "e espaçamento entre vizinhos", "Gera descendentes em lotes", y=1.3),
                    note("A curva ilustra a adaptação da medida de distância. A busca trabalha com pontos discretos."))
        self.hold()

        self.beat("vns", "VNS/VND alterna perturbação e busca local", "vns_vnd_original.py · vns_vnd.py · Mladenović e Hansen (1997)",
                  "As duas versões compartilham a mesma busca. A construção da primeira solução mudou.")
        stages = [("Arquivo Pareto", "Origem menos explorada", -4.33, GOLD),
                  ("VNS", "Perturbação em uma vizinhança", 0, CORAL),
                  ("VND", "Primeira melhora dominante", 4.33, GREEN)]
        for idx, (name, description, x, color) in enumerate(stages):
            block = VGroup(text(name, 36, color, bold=True).move_to(pos(x, .98)),
                           text(description, 23, width=3.53).move_to(pos(x, .29)))
            self.reveal(block)
            if idx < 2:
                edge = Arrow(pos(x + 1.90, .98), pos(x + 2.55, .98), buff=0, color=MUTED, stroke_width=2.1)
                self.play(Create(edge), run_time=.27)
        neighborhoods = lines(("N1 · mudar modo     N2 · mudar espera     N3 · reinserir na mesma máquina",
                               "N4 · mover para outra máquina     N5 · trocar duas tarefas"),
                              -6.25, -.58, width=12.3, size=23, gap=.38)
        self.reveal(rule(-.16), neighborhoods)
        original = [(0, 0, 0, 2.4), (0, 1, 2.9, 4.9), (1, 2, 0, 1.7)]
        options = dict(total=7.7, x=-5.45, y=-1.64, width=6.8, lane=.48, bar=.33, time_label=None)
        chart, tasks = gantt(original, **options)
        _, moved = gantt([original[0], (1, 1, 2.25, 4.9), original[2]], **options)
        _, tuned = gantt([original[0], (1, 1, 2.25, 4.15), original[2]], **options)
        stage = left(text("Perturbar · realocar tarefa", 22, CORAL, width=4.65), 1.72, -1.63)
        self.reveal(chart, tasks, stage)
        self.play(Transform(tasks[1], moved[1]), run_time=.68)
        self.play(Transform(tasks[1], tuned[1]), Transform(stage, left(text("Busca local · mudar modo", 22, GREEN, width=4.65), 1.72, -1.63)),
                  run_time=.68)
        self.reveal(note("Esquema. O VND volta a N1 após dominância estrita. O arquivo pode receber candidatos viáveis."))
        self.hold()


def protocol(alg, study):
    return read_json(data_path("hyperparameters_tuning", alg, study, "protocol.json"))


class Calibracao(DeckScene):
    chapter, number = "METODOLOGIA · CALIBRAÇÃO E EXECUÇÃO", 6

    def construct(self):
        self.beat("protocolo", "Como se avaliou cada configuração?",
                  "hyperparameters_tuning/common.py · protocolos v6 e v7", "Optuna TPE · orçamento fixo por busca")
        setup = protocol("age", "age_tpe_v6")
        phases = [(str(len(setup["cases"])), "instâncias de 3 portes", -4.37, CYAN),
                  (pt(setup["budget_per_run"], 0), "tentativas por execução", 0, GOLD),
                  (str(len(setup["seeds"])), "seeds por instância", 4.37, GREEN)]
        for value, label, x, color in phases:
            self.reveal(VGroup(text(value, 63, color, bold=True).move_to(pos(x, .85)),
                               text(label, 25, width=3.85).move_to(pos(x, -.02))))
        self.reveal(rule(-.58), lines(("Em cada instância: mediana de HV / 1,05² entre seeds.",
                                      "No trial: média dessas medianas. A confirmação usa seeds novas."),
                                     -6.27, -1.18, width=12.2, size=28, gap=.58),
                    note("A referência da calibração é (1,05, 1,05), com limites derivados da entrada."))
        self.hold()

        self.beat("busca", "Espaços de busca registrados", "protocol.json · estudos v6 e v7",
                  "Os três evolucionários compartilham população, cruzamento e mutação.")
        evolutionary = protocol("moead", "moead_tpe_v6")["search_space"]
        vns = protocol("vns_vnd", "vns_vnd_tpe_v7")["search_space"]
        spaces = [("Evolucionários", "População", evolutionary["population_size"]),
                  ("Evolucionários", "Prob. cruzamento", evolutionary["crossover_probability"]),
                  ("Evolucionários", "Prob. mutação", evolutionary["mutation_probability"]),
                  ("MOEA/D", "Vizinhos", evolutionary["n_neighbors"]),
                  ("MOEA/D", "Prob. acasalamento local", evolutionary["prob_neighbor_mating"]),
                  ("VNS/VND", "Partidas", vns["initial_solutions"]),
                  ("VNS/VND", "Candidatos por vizinhança", vns["max_candidates_per_neighborhood"]),
                  ("VNS/VND", "Tentativas de perturbação", vns["shaking_attempts"])]
        rows = [(alg, parameter, "  /  ".join(str(value).replace(".", ",") for value in values))
                for alg, parameter, values in spaces]
        self.reveal(table(("Família", "Parâmetro", "Valores candidatos"), rows, (2.78, 4.21, 5.72),
                          y=1.63, gap=.462, size=23))
        self.reveal(note("Os protocolos registram opções de orçamento. Nesta busca, o orçamento fica fixo em 8.000."))
        self.hold()

        self.beat("selecionados", "Configurações escolhidas para a campanha", "experiment_manifest.json · orig. e experiments_vns_new",
                  "Trial recomendado na confirmação, quando disponível.")
        original = read_json(data_path("experiments", "experiment_manifest.json"))["configurations"]
        revised = read_json(data_path("experiments_vns_new", "experiment_manifest.json"))["configurations"]["vns_vnd"]
        rows = []
        for k, name in (("age", "AGE-MOEA"), ("moead", "MOEA/D"), ("spea2", "SPEA2")):
            run = original[k]
            p = run["parameters"]
            choices = [f"P {p['population_size']}", f"cruz. {pt(p['crossover_probability'], 1)}",
                       f"mut. {pt(p['mutation_probability'], 1)}"]
            if k == "moead":
                choices.extend((f"T {p['n_neighbors']}", f"acasal. local {pt(p['prob_neighbor_mating'], 1)}"))
            rows.append((name, f"v6 · {run['trial']}", "   /   ".join(choices)))
        for version, run in (("original", original["vns_vnd"]), ("revisto", revised)):
            p = run["parameters"]
            rows.append((f"VNS {version}", f"{run['study'][-2:]} · {run['trial']}",
                         f"{p['initial_solutions']} partidas  /  {p['max_candidates_per_neighborhood']} candidatos  /  {p['shaking_attempts']} tentativas"))
        self.reveal(table(("Método", "Estudo · trial", "Parâmetros usados"), rows, (2.75, 2.20, 7.71),
                          gap=.56, colors=[COLORS[k] for k in ("age", "moead", "spea2", "vns_vnd", "vns_vnd_new")]))
        changes = []
        for key in ("age", "moead", "spea2", "vns_vnd"):
            run = revised if key == "vns_vnd" else original[key]
            initial = read_json(data_path("hyperparameters_tuning", key, run["study"], "best_parameters.json"))["best_trial"]
            changes.append(f"{SHORT[key] if key != 'vns_vnd' else 'VNS v7'} {initial}→{run['trial']}")
        self.reveal(left(text("Trials após confirmação    " + "   /   ".join(changes), 22, CYAN, width=12.65), -6.30, -1.92))
        self.reveal(note("O VNS revisto herdou o trial v7, calibrado ainda com a construção anterior."))
        self.hold()

        self.beat("execucao", "Protocolo da campanha experimental", "experiments/config.py · manifests e registros das duas campanhas",
                  "9 entradas nos portes 6–14, 50, 250 e 750 tarefas.")
        self.reveal(table(("Métodos", "Por entrada", "Orçamento ou condição"), [
            ("DP própria", "1 execução", "Até 13 tarefas, 3.600 s e 4.096 MiB"),
            ("Ociosidade", "1 execução", "Base construtiva e modos livres"),
            ("Meta-heurísticas", "30 execuções", "10.000 tentativas por execução"),
        ], (3.67, 2.63, 6.23), y=1.44, gap=.7, size=28))
        self.reveal(rule(-1.05), left(text("Seeds 1001–1030 · a mesma seed identifica a réplica de cada método estocástico.",
                                          24, CYAN), -6.28, -1.57),
                    note("CP-SAT, backtracking e construtiva também têm saídas individuais fora da campanha."))
        self.hold()


def results_data():
    return read_json(HERE / "data" / "results.json")


def load_profile(machine_ends, horizon, color):
    """Mostra o término em cada máquina desde a origem até o horizonte comum."""
    x0, x1 = -5.85, .85
    background, bars = VGroup(), VGroup()
    for i, end in enumerate(machine_ends):
        y = 1.49 - i * .36
        background.add(text(f"M{i + 1}", 18, MUTED).move_to(pos(x0 - .40, y)),
                       Line(pos(x0, y), pos(x1, y), color=GRID, stroke_width=1))
        bars.add(Line(pos(x0, y), pos(x0 + (x1 - x0) * end / horizon, y), color=color, stroke_width=7))
    background.add(DashedLine(pos(x1, 1.80), pos(x1, -1.98), color=GOLD, dash_length=.11),
                   left(text("0", 19, MUTED), x0, -2.12), text(f"H = {pt(horizon, 0)} min", 19, GOLD).move_to(pos(x1 - .50, -2.12)))
    return background, bars


class CasoVNS(DeckScene):
    chapter, number = "ESTUDO DE CASO · INSTÂNCIA GIGANTE", 7

    def construct(self):
        trace = read_json(HERE / "data" / "vns_trace.json")
        horizon = trace["horizon"]
        old, new = trace["original"], trace["revised"]
        self.beat("instancia", "Uma instância de 750 tarefas", "data/input/set2 · problem.py",
                  trace["instance"])
        facts = [(trace["jobs"], "tarefas", -4.37, CYAN), (trace["machines"], "máquinas", 0, GOLD),
                 (trace["modes"], "modos por máquina", 4.37, GREEN)]
        for value, label, x, color in facts:
            self.reveal(text(str(value), 67, color, bold=True).move_to(pos(x, .79)),
                        text(label, 27).move_to(pos(x, -.03)))
        x0, width, y = -6.08, 12.15, -1.43
        timeline = VGroup(Line(pos(x0, y), pos(x0 + width, y), color=GRID, stroke_width=4))
        for start, end in trace["peak_intervals"]:
            left_x, right_x = x0 + width * start / horizon, x0 + width * end / horizon
            timeline.add(Line(pos(left_x, y), pos(right_x, y), color=CORAL, stroke_width=8),
                         text("Ponta", 20, CORAL).move_to(pos((left_x + right_x) / 2, y + .34)))
        for day in range(trace["days"] + 1):
            x = x0 + width * day / trace["days"]
            timeline.add(text(pt(day * trace["slots_per_day"], 0), 19, MUTED).move_to(pos(x, y - .35)))
        self.reveal(timeline, note(f"Horizonte de {pt(horizon,0)} minutos. A faixa de ponta reaparece no mesmo horário a cada dia."))
        self.hold()
        self.beat("antes", "O sorteio original esgotou a folga", "vns_vnd_original.py · replay com trace_vns.py",
                  f"Primeira construção · seed {trace['seed']} · barras mostram o fim da carga alocada")
        frame, load = load_profile(old["machine_ends"], horizon, COLORS["vns_vnd"])
        self.reveal(frame)
        self.play(LaggedStart(*(Create(bar) for bar in load), lag_ratio=.06), run_time=1.1)
        old_text = lines(("Embaralha todas as tarefas", "Sorteia máquina e modo viáveis", f"{old['assigned']} de {trace['jobs']} tarefas alocadas"),
                         1.66, 1.22, width=4.7, size=29, gap=.59)
        self.reveal(old_text)
        blocker = lines((f"Tarefa {old['blocked_job_zero_based']+1} bloqueada", f"Melhor término: {pt(old['minimum_candidate_end'],0)} min"),
                        1.66, -.85, width=4.8, size=28, gap=.61, color=CORAL)
        self.reveal(blocker, note("Todas as combinações para a próxima tarefa excedem o horizonte. A construção é descartada."))
        self.hold()

        self.beat("depois", "O LPT aleatório preservou folga", "vns_vnd.py · commit 35f4330 · replay com trace_vns.py",
                  f"Primeira construção · seed {trace['seed']} · mesma escala e mesmo horizonte")
        frame, load = load_profile(old["machine_ends"], horizon, COLORS["vns_vnd"])
        _, balanced = load_profile(new["machine_ends"], horizon, COLORS["vns_vnd_new"])
        self.reveal(frame, load)
        description = lines(("Prioriza tarefas mais longas", "Sorteia entre as primeiras da fila", "Escolhe o menor término viável"),
                            1.66, 1.29, width=4.85, size=28, gap=.57)
        self.reveal(description)
        self.play(Transform(load, balanced), run_time=1.15)
        completion = lines((f"{new['assigned']} de {trace['jobs']} tarefas alocadas", f"Makespan inicial: {pt(new['makespan'],0)} min"),
                           1.66, -.79, width=4.85, size=29, gap=.61, color=GREEN)
        self.reveal(completion, note("Dificuldade é a menor duração da tarefa entre todas as combinações máquina–modo."))
        self.hold()

        self.beat("evidencia", "O VNS revisto começou as 30 buscas", "experiments · experiments_vns_new · instância 750_10_1439_5_S_1-9",
                  "Resultados arquivados da campanha principal, depois da comparação da primeira construção.")
        algs = results_data()["instances"][GIANT]["algorithms"]
        rows = []
        for key, name in (("vns_vnd", "VNS original"), ("vns_vnd_new", "VNS revisto")):
            data = algs[key]
            rows.append((name, data["runs"], data["statuses"].get("INIT_FAILED", 0), data["statuses"].get("COMPLETED", 0)))
        self.reveal(table(("Versão", "Seeds", "Falhas de partida", "Execuções completas"), rows,
                          (3.16, 1.66, 3.7, 4.07), y=1.36, gap=.71, size=27, colors=[COLORS["vns_vnd"], COLORS["vns_vnd_new"]]))
        self.reveal(rule(-.75), lines(("O replay comparou apenas os construtores.",
                                      "Na campanha, variou também o limite de candidatos por vizinhança."),
                                     -6.25, -1.27, width=12.25, size=27, gap=.62),
                    note("LPT viabilizou a partida observada. A construção gulosa ainda pode falhar em outras entradas."))
        self.hold()


def metric_axes():
    return axes((0, 1.18, .2), (0, 1.18, .2), center=(-2.68, -.36), width=6.45, height=3.28,
                x_label="Cmax normalizado", y_label="TEC normalizado", numbers=True)


def diagram_points(record):
    return [(x, y) for x, y, _ in record]


EQUATION_36 = r"z=\frac{1}{|F|}\ast\sum_{p\in F}(R^{*}-R_p)"


class Metricas(DeckScene):
    chapter, number = "AVALIAÇÃO · INDICADORES", 8

    def construct(self):
        source = results_data()
        sample = source["examples"]["campaign_6_1001"]
        instance = source["instances"][SMALL]
        reference = diagram_points(sample["exact_dp"])
        approx = sample["age"]
        caption = "Seis tarefas · execução de exemplo do AGE-MOEA com seed 1001"
        color = COLORS["age"]

        self.beat("hv", "Hipervolume mede área dominada", "experiments/metrics.py · ideal e nadir da campanha original", caption)
        axis, labels = metric_axes()
        anchor = tuple(source["provenance"]["hv_reference"])
        anchor_pt = axis.c2p(*anchor)
        points = sorted(diagram_points(approx))
        strips = VGroup()
        for i, (x, y) in enumerate(points):
            next_x = points[i + 1][0] if i + 1 < len(points) else anchor[0]
            lo, hi = axis.c2p(x, y), axis.c2p(next_x, anchor[1])
            if hi[0] > lo[0] and hi[1] > lo[1]:
                strips.add(Rectangle(width=hi[0] - lo[0], height=hi[1] - lo[1],
                                     stroke_width=0, fill_color=color, fill_opacity=.32).move_to((lo + hi) / 2))
        self.reveal(axis, labels)
        self.reveal(dots(axis, points, color, radius=.046), dots(axis, [anchor], GOLD),
                    text("r", 25, GOLD, bold=True).move_to(anchor_pt + pos(.22, .19)))
        rectangles = VGroup()
        for point in (points[len(points) // 4], points[3 * len(points) // 4]):
            p = axis.c2p(*point)
            rectangles.add(Rectangle(width=anchor_pt[0] - p[0], height=anchor_pt[1] - p[1],
                                     stroke_width=2.2, stroke_color=GOLD, fill_opacity=0).move_to((p + anchor_pt) / 2))
        self.play(*(Create(shape) for shape in rectangles), run_time=.7)
        self.play(FadeOut(rectangles), run_time=.30)
        self.play(LaggedStart(*(FadeIn(strip) for strip in strips), lag_ratio=.04), run_time=1.3)
        self.play(Create(staircase(axis, points, color)), run_time=.65)
        side_text = side("Um ponto cobre um retângulo", "até a referência r.", "O HV soma a união das áreas.",
                         "Área maior indica maior HV.", y=1.22)
        r_label = formula(r"r=(1{,}10;\,1{,}10)", 4.3, height=.33, color=GOLD).move_to(pos(3.25, -1.78))
        self.reveal(side_text, r_label,
                    note("A normalização usa ideal e nadir por instância. A área fora da caixa de r fica de fora.", y=-3.12))
        self.hold()

        self.beat("purity", "Purity mede a cobertura da primeira camada", "cebola.py · adaptação de R_PF para a união das campanhas", caption)
        axis, labels = metric_axes()
        all_ref = dots(axis, reference, MUTED, radius=.039)
        hits = [(x, y) for x, y, rank in approx if rank == 1]
        misses = [(x, y) for x, y, rank in approx if rank > 1]
        self.reveal(axis, labels, all_ref, staircase(axis, reference, MUTED, width=.9))
        self.reveal(dots(axis, misses, CORAL, radius=.043))
        self.play(LaggedStart(*(GrowFromCenter(p) for p in dots(axis, hits, color, radius=.049)), lag_ratio=.06), run_time=1.15)
        purity = formula(r"\mathrm{Purity}(F)=\frac{|F\cap P^{*}|}{|P^{*}|}", 5.28, height=.80, color=GOLD).move_to(pos(3.82, 1.02))
        ratio = f"{len(hits)} / {instance['purity_reference_size']} = {pt(len(hits) / instance['purity_reference_size'],3)}"
        self.reveal(purity, left(text(ratio, 34, GOLD, bold=True), 1.15, -.05),
                    lines(("P* · primeira camada da união", "Roxo · ponto do AGE que pertence a P*", "Coral · ponto do AGE fora de P*"),
                          1.15, -.73, width=5.45, size=23, gap=.51),
                    note("A interseção usa pares (Cmax, TEC) exatos. Pontos repetidos contam uma vez por frente.", y=-3.12))
        self.hold()

        self.beat("eq36", "Equação 3.6 mede a profundidade média", "Miranda (2025), p. 39 · união das frentes por instância", caption)
        equation = formula(EQUATION_36, 8, height=1.04, color=GOLD).move_to(pos(-2.77, 1.05))
        rank_counts = Counter(p[2] for p in approx)
        layers = instance["rank_count"]
        rstar = layers + 1
        total = sum((rstar - rank) * count for rank, count in rank_counts.items())
        rows = [(r, rank_counts[r], rstar - r) for r in sorted(rank_counts)]
        rank_table = table(("Camada", "Pontos", "Peso por ponto"), rows, (1.73, 1.44, 2.36),
                           x=.93, y=1.58, size=23, gap=.51)
        layer_axes, layer_labels = metric_axes()
        first = VGroup(staircase(layer_axes, reference, GOLD, width=2.2), dots(layer_axes, reference, GOLD, radius=.046))
        next_rank = sorted({(x, y) for method in sample.values() for x, y, rank in method if rank == 2})
        second = dots(layer_axes, next_rank, CYAN, radius=.056)
        phase1 = side("Camada 1 · pontos não dominados", "Retire esses pontos da união.", y=.96)
        phase2 = side("Camada 2 · próximos não dominados", "Repita até esgotar os pontos.", y=.96)
        self.reveal(layer_axes, layer_labels, first, phase1)
        self.play(FadeOut(first), FadeOut(phase1), FadeIn(second), FadeIn(phase2), run_time=.80)
        self.wait(.36)
        self.play(FadeOut(layer_axes), FadeOut(layer_labels), FadeOut(second), FadeOut(phase2), run_time=.4)
        self.reveal(equation)
        rank_symbol = left(formula(r"R_p", height=.24), -6.1, -.50)
        self.reveal(left(text(f"R* = {layers} camadas + 1 = {rstar}", 26), -6.1, .02), rank_symbol,
                    left(text("é a camada do ponto p.", 26), -5.54, -.50),
                    left(text(f"|F| = {len(approx)} pontos nesta frente.", 26), -6.1, -1.02))
        self.reveal(rank_table)
        z = formula(rf"z=\frac{{{total}}}{{{len(approx)}}}\approx {pt(total / len(approx),2).replace(',', '{,}')}",
                    5.6, height=.72, color=GOLD).move_to(pos(-3.04, -1.95))
        self.reveal(z, note("Remove-se a primeira camada para revelar a próxima. Pontos nas camadas iniciais valem mais."))
        self.hold()


ALGORITHMS = ("exact_dp", "ociosidade", "spea2", "age", "moead", "vns_vnd", "vns_vnd_new")
META = ALGORITHMS[2:]
SHORT = {"exact_dp": "DP própria", "ociosidade": "Ociosidade", "spea2": "SPEA2", "age": "AGE-MOEA",
         "moead": "MOEA/D", "vns_vnd": "VNS original", "vns_vnd_new": "VNS revisto"}


def distributions(instance):
    """Mínimo e máximo, caixa Q1–Q3 e traço da mediana, por métrica."""
    plot = VGroup()
    columns = [("HV", "Hipervolume", .90, 1.02), ("Purity", "Purity", 0, 1),
               ("Eq36", "Equação 3.6", 10, instance["rank_count"])]
    x_points = [-3.70, -.28, 3.22]
    width = 2.82
    for x, (metric, name, lo, hi) in zip(x_points, columns):
        plot.add(left(text(name, 25, GOLD, bold=True), x, 1.48),
                 Line(pos(x, 1.05), pos(x, -1.98), color=GRID, stroke_width=1),
                 Line(pos(x + width, 1.05), pos(x + width, -1.98), color=GRID, stroke_width=1),
                 text(pt(lo, 2 if metric == "HV" else 0), 19, MUTED).move_to(pos(x, -2.25)),
                 text(pt(hi, 2 if metric == "HV" else 0), 19, MUTED).move_to(pos(x + width, -2.25)))
        for i, algorithm in enumerate(ALGORITHMS):
            y = .94 - i * .46
            summary = instance["algorithms"][algorithm]["metrics"][metric]
            if summary["n"] == 0:
                continue
            coords = [x + (summary[k] - lo) / (hi - lo) * width for k in ("min", "q1", "median", "q3", "max")]
            if summary["min"] < lo or summary["max"] > hi:
                raise ValueError(f"Limite gráfico insuficiente para {algorithm}/{metric}")
            col = COLORS[algorithm]
            if summary["n"] == 1 or summary["max"] == summary["min"]:
                plot.add(Dot(pos(coords[2], y), radius=.078, color=col))
            else:
                plot.add(Line(pos(coords[0], y), pos(coords[4], y), color=col, stroke_width=2),
                         Rectangle(width=max(coords[3] - coords[1], .012), height=.22,
                                   fill_color=col, fill_opacity=.87, stroke_width=0)
                         .move_to(pos((coords[1] + coords[3]) / 2, y)),
                         Line(pos(coords[2], y - .12), pos(coords[2], y + .12), color=INK, stroke_width=2.6))
    for i, key in enumerate(ALGORITHMS):
        label = f"{SHORT[key]} ({instance['algorithms'][key]['fronts']})"
        plot.add(left(text(label, 24, COLORS[key], 2.72, bold=True), -6.54, .94 - i * .46))
    return plot


class Resultados(DeckScene):
    chapter, number = "RESULTADOS E DISCUSSÃO", 9

    def construct(self):
        data = results_data()
        small = data["instances"][SMALL]
        giant = data["instances"][GIANT]
        ten = data["instances"]["10_2_1439_3_S_1-9"]["algorithms"]
        self.beat("dispersao", "Três métricas, três distribuições", "Apêndice estatístico · nove instâncias · metrics_summary.csv",
                  "Seis tarefas · número de execuções com frente entre parênteses.")
        self.reveal(distributions(small), run_time=.9)
        self.reveal(note("Linha: mín.–máx.  Caixa: Q1–Q3.  Traço: mediana.  Ponto: uma execução. Escalas por coluna."))
        self.hold()

        self.beat("portes", "Proximidade geométrica e coincidência exata", "Campanhas principal e VNS revisto · métricas por instância",
                  "Para cada porte, média das médias de HV por instância com frente.")
        bands = (("small", "6–14"), ("medium", "50"), ("large", "250"), ("giant", "750"))
        rows = [(SHORT[alg], *(pt(data["tiers"][band]["algorithms"][alg]["metrics"]["HV"]["mean"], 3)
                               for band, _ in bands)) for alg in ("ociosidade", *META)]
        self.reveal(table(("Método", *(name for _, name in bands)), rows, (3.02, 1.34, 1.34, 1.34, 1.34),
                          y=1.62, x=-6.48, gap=.52, size=23,
                          colors=[COLORS[k] for k in ("ociosidade", *META)]))
        dp, he = (ten[key]["metrics"] for key in ("exact_dp", "ociosidade"))
        distinct = lines(("Instância de 10 tarefas", f"HV da DP: {pt(dp['HV']['mean'],4)}",
                          f"HV da ociosidade: {pt(he['HV']['mean'],4)}", "Purity: 100% e 0%"),
                         2.18, 1.54, width=4.28, size=24, gap=.58)
        distinct[0].set_color(GOLD)
        self.reveal(distinct, left(text("Maior HV médio entre as meta-heurísticas: SPEA2 em 6. AGE em 10, 14, 50 e 250.",
                                       22, CYAN, width=12.45), -6.48, -2.31),
                    note("Para VNS original em 750, a média representa 1 de 2 entradas. Ociosidade contribui para P* empírico."))
        self.hold()

        self.beat("discussao", "Partir com sucesso e alcançar a referência", "Campanhas principal e VNS revisto · instância 750_10_1439_5_S_1-9",
                  "Médias entre execuções com frente. Na meta-heurística original, a construção falhou.")
        entries = []
        for alg in META:
            result = giant["algorithms"][alg]
            values = result["metrics"]
            entries.append((SHORT[alg], f"{result['fronts']}/{result['runs']}",
                            pt(values["HV"]["mean"], 2), pt(values["Purity"]["mean"], 2), pt(values["Eq36"]["mean"], 2)))
        self.reveal(table(("Método", "Frentes", "HV", "Purity", "Eq. 3.6"), entries, (3, 1.40, 1.23, 1.42, 1.74),
                          x=-6.47, y=1.63, gap=.55, size=23, colors=[COLORS[i] for i in META]))
        side_plot, side_labels = axes((0, .32, .1), (0, 3.3, 1), center=(4.61, -.33), width=3.2, height=2.65,
                                      x_label="Cmax norm.", y_label="TEC norm.")
        sample = data["examples"]["giant_1001"]
        r = side_plot.c2p(.32, 1.1)
        hv_line = DashedLine(side_plot.c2p(0, 1.1), r, color=GOLD, dash_length=.09)
        points = VGroup(*(dots(side_plot, sample[alg], COLORS[alg], radius=.043) for alg in META if sample[alg]))
        self.reveal(side_plot, side_labels, hv_line, left(text("TEC de r = 1,10", 17, GOLD), 3.06, -1.01), points)
        self.reveal(note("Amostra à direita: seed 1001, zoom em Cmax. Todas as 120 frentes meta-heurísticas ficaram fora da caixa do HV."))
        self.hold()


class Fechamento(DeckScene):
    chapter, number = "CONCLUSÃO E REFERÊNCIAS", 10

    def construct(self):
        self.beat("conclusao", "O que a campanha mostrou?", "Resultados arquivados · duas campanhas de 30 seeds")
        lessons = [("Certificação", "A DP provou as frentes de 6 e 10 tarefas na campanha.", GOLD),
                   ("Escala", "Ociosidade foi um comparador forte nas entradas maiores.", CYAN),
                   ("Viabilidade", "O VNS revisto completou 30 réplicas nas seeds em que o original falhou.", GREEN)]
        for i, (key, value, color) in enumerate(lessons):
            y = 1.51 - i * .86
            self.reveal(left(text(key, 31, color, bold=True), -6.42, y),
                        left(text(value, 27, width=9.79), -3.66, y))
        self.reveal(rule(-.68), left(text("Próximo experimento", 29, CYAN, bold=True), -6.42, -1.20),
                    lines(("Isolar o efeito do inicializador com os mesmos parâmetros de busca.",
                           "Medir a qualidade ao longo do orçamento e testar entradas inéditas."),
                          -6.42, -1.84, width=12.7, size=27, gap=.55))
        self.hold()

        self.beat("referencias", "Referências", "Referências completas e links no roteiro",
                  "Artigo-base, métrica de camadas, algoritmos e bibliotecas.")
        refs = [
            ("Rego, Pinto, Cota e Souza (2022)", "UPMSP, makespan e tarifas por horário · PeerJ CS 8:e844"),
            ("Eduardo G. R. Miranda (2025)", "Dissertação UFSJ · Equação 3.6, p. 39"),
            ("Zitzler, Laumanns e Thiele (2001)", "SPEA2 · ETH Zürich, relatório TIK 103"),
            ("Zhang e Li (2007)", "MOEA/D · IEEE Transactions on Evolutionary Computation"),
            ("Panichella (2019)", "AGE-MOEA · GECCO"),
            ("Mladenović e Hansen (1997)", "VNS · Computers & Operations Research"),
        ]
        self.reveal(table(("Referência", "Contribuição"), refs, (5.61, 7.02), x=-6.43, y=1.65, gap=.49, size=22))
        self.reveal(note("Bibliotecas · OR-Tools / CP-SAT, pymoo 0.6.2, Numba, Optuna, Manim Community e Matplotlib."))
        self.hold()
