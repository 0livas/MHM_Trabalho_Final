"""Cena Manim "cebola": non-dominated sorting, Purity e Eq. 3.6 com dados reais.

Renderizar (a partir da raiz do repositório):
    py -3.12 -m manim -pql src/presentation/cebola.py CebolaPareto   # prévia rápida
    py -3.12 -m manim -qh src/presentation/cebola.py CebolaPareto    # 1080p

Variáveis de ambiente opcionais:
    CEBOLA_INSTANCIA   (padrão 50_10_1439_5_S_1-124)
    CEBOLA_EXPERIMENTO (padrão A)
    CEBOLA_SEED        (padrão 307; vazio = menor seed comum a todos os algoritmos)

Não usa LaTeX: todo texto é Text/MarkupText (Pango).
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from pathlib import Path

from manim import *

ROOT = Path(__file__).resolve().parents[2]
PONTOS = ROOT / "data/output/final_comparison/normalized_points.csv"
# Padrão escolhido por ser didático: os três algoritmos têm pontos em P* e as
# camadas misturam algoritmos. Não é uma execução "típica"; os números da
# comparação vêm da campanha completa.
INSTANCIA = os.environ.get("CEBOLA_INSTANCIA", "50_10_1439_5_S_1-124")
EXPERIMENTO = os.environ.get("CEBOLA_EXPERIMENTO", "A")
SEED = os.environ.get("CEBOLA_SEED", "307")

ORDEM = ["vns_vnd", "vns_vnd_new", "spea2", "moead", "age"]
NOMES = {
    "vns_vnd": "VNS/VND",
    "vns_vnd_new": "VNS/VND (novo)",
    "spea2": "SPEA2",
    "moead": "MOEA/D",
    "age": "AGE-MOEA",
}
# Mesmas cores do dashboard (src/dashboard_template.html), clareadas para fundo escuro.
_BASE = {
    "age": "#8e52aa",
    "spea2": "#087b9a",
    "moead": "#ce7110",
    "vns_vnd": "#bd3c5a",
    "vns_vnd_new": "#347d36",
}
CORES = {k: interpolate_color(ManimColor(v), WHITE, 0.25) for k, v in _BASE.items()}
FUNDO = "#14171c"
RANK_TOPO = ManimColor("#f4d35e")
RANK_FUNDO = ManimColor("#4a5260")

config.background_color = FUNDO


def carregar():
    """Retorna (seed, {algoritmo: [(cmax_norm, tec_norm), ...]})."""
    por_execucao = defaultdict(set)
    with open(PONTOS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["experiment"] != EXPERIMENTO or Path(row["instance"]).stem != INSTANCIA:
                continue
            ponto = (float(row["cmax_norm"]), float(row["tec_norm"]))
            por_execucao[(row["algorithm"], int(row["seed"]))].add(ponto)
    if not por_execucao:
        raise SystemExit(f"Sem pontos para {EXPERIMENTO}/{INSTANCIA} em {PONTOS}")
    algs = sorted({a for a, _ in por_execucao}, key=lambda a: ORDEM.index(a) if a in ORDEM else 99)
    if SEED:
        seed = int(SEED)
    else:
        comuns = set.intersection(*({s for a, s in por_execucao if a == alg} for alg in algs))
        seed = min(comuns)
    return seed, {a: sorted(por_execucao[(a, seed)]) for a in algs}


def non_dominated_sorting(pontos):
    """Minimização nos dois objetivos. Retorna {ponto: rank}, rank começando em 1."""
    restantes, rank, k = set(pontos), {}, 1
    while restantes:
        camada = {
            p for p in restantes
            if not any(q != p and q[0] <= p[0] and q[1] <= p[1] for q in restantes)
        }
        for p in camada:
            rank[p] = k
        restantes -= camada
        k += 1
    return rank


def escada(axes, pts, **kw):
    """Linha em escada ligando pontos não dominados (ordenados por Cmax)."""
    pts = sorted(pts)
    vertices = [axes.c2p(*pts[0])]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        vertices += [axes.c2p(x1, y0), axes.c2p(x1, y1)]
    if len(vertices) == 1:
        return Dot(vertices[0], radius=0.02, **kw)
    return VMobject(**kw).set_points_as_corners(vertices)


class CebolaPareto(Scene):
    def construct(self):
        seed, fronts = carregar()
        algs = list(fronts)
        todos = sorted({p for pts in fronts.values() for p in pts})
        rank = non_dominated_sorting(todos)
        R = max(rank.values())
        R_star = R + 1
        p_star = sorted(p for p in todos if rank[p] == 1)
        cor_rank = {k: interpolate_color(RANK_TOPO, RANK_FUNDO, (k - 1) / max(R - 1, 1)) for k in range(1, R + 1)}

        # ------------------------------------------------------------ eixos
        xs, ys = [p[0] for p in todos], [p[1] for p in todos]
        px, py = 0.08 * (max(xs) - min(xs)), 0.08 * (max(ys) - min(ys))
        x0, x1, y0, y1 = min(xs) - px, max(xs) + px, min(ys) - py, max(ys) + py
        axes = Axes(
            x_range=[x0, x1, x1 - x0],
            y_range=[y0, y1, y1 - y0],
            x_length=7.0,
            y_length=5.0,
            tips=True,
            axis_config={"include_ticks": False, "color": GREY_B, "stroke_width": 2},
        ).move_to(LEFT * 2.8 + DOWN * 0.45)
        xl = Text("Cmax normalizado  (menor é melhor)", font_size=20, color=GREY_B).next_to(axes.x_axis, DOWN, buff=0.2)
        yl = Text("TEC normalizado", font_size=20, color=GREY_B).rotate(PI / 2).next_to(axes.y_axis, LEFT, buff=0.2)

        dots = {a: VGroup(*[Dot(axes.c2p(*p), radius=0.075, color=CORES[a]) for p in fronts[a]]) for a in algs}
        pontos_de = {a: dict(zip(fronts[a], dots[a])) for a in algs}

        def dots_do_rank(k):
            return [d for a in algs for p, d in pontos_de[a].items() if rank[p] == k]

        titulo = Text("Juntando as fronteiras", font_size=36).to_edge(UP, buff=0.3)
        sub = Text(f"Instância {INSTANCIA} · 1 execução por algoritmo (seed {seed})", font_size=18, color=GREY_B)
        sub.next_to(titulo, DOWN, buff=0.12)

        # ======================================================== 1. juntar
        self.next_section("juntar")
        self.play(Write(titulo), FadeIn(sub))
        self.play(Create(axes), FadeIn(xl), FadeIn(yl))

        legenda = VGroup()
        for a in algs:
            row = VGroup(Dot(radius=0.09, color=CORES[a]), Text(f"{NOMES.get(a, a)} · {len(fronts[a])} pontos", font_size=22))
            row.arrange(RIGHT, buff=0.2)
            legenda.add(row)
        legenda.arrange(DOWN, aligned_edge=LEFT, buff=0.22).move_to(RIGHT * 4.6 + UP * 1.7)

        for a, row in zip(algs, legenda):
            self.play(
                LaggedStart(*[GrowFromCenter(d) for d in dots[a]], lag_ratio=0.06, run_time=1.2),
                FadeIn(row, shift=LEFT * 0.2),
            )
        nota = Text(
            "Cada algoritmo devolve\numa fronteira própria.\n\nA referência é construída\ncom todos os pontos juntos.",
            font_size=20, line_spacing=0.9, color=GREY_A,
        ).next_to(legenda, DOWN, buff=0.6, aligned_edge=LEFT)
        self.play(FadeIn(nota))
        self.wait(1.5)

        # ===================================================== 2. dominância
        self.next_section("dominancia")
        # par (p, q) com a dominância mais visível: maior folga relativa nos dois eixos
        pares = [(p, q) for q in todos if rank[q] == 2 for p in p_star if p[0] <= q[0] and p[1] <= q[1]]
        par = max(
            pares,
            key=lambda pq: min((pq[1][0] - pq[0][0]) / (x1 - x0), (pq[1][1] - pq[0][1]) / (y1 - y0)),
            default=None,
        )
        if par:
            p, q = par
            cp = axes.c2p(*p)
            canto = axes.c2p(x1, y1)
            sombra = Polygon(cp, [canto[0], cp[1], 0], canto, [cp[0], canto[1], 0],
                             stroke_width=1.5, stroke_color=WHITE, fill_color=WHITE, fill_opacity=0.12)
            dp = next(d for a in algs for pp, d in pontos_de[a].items() if pp == p)
            dq = next(d for a in algs for pp, d in pontos_de[a].items() if pp == q)
            lp = Text("p", font_size=24, weight=BOLD).next_to(dp, DL, buff=0.08)
            lq = Text("q", font_size=24, weight=BOLD).next_to(dq, UR, buff=0.08)
            texto = Text(
                "p domina q:\nnão é pior em nenhum objetivo\ne é melhor em pelo menos um.",
                font_size=20, line_spacing=0.9,
            ).move_to(nota, aligned_edge=UL)
            self.play(FadeOut(nota), FadeIn(lp), FadeIn(lq))
            self.play(FadeIn(sombra), FadeIn(texto))
            self.play(Indicate(dq, scale_factor=1.8, color=WHITE))
            self.wait(1.5)
            self.play(FadeOut(sombra), FadeOut(lp), FadeOut(lq), FadeOut(texto))
        else:
            self.play(FadeOut(nota))

        # ======================================================= 3. cebola
        self.next_section("cebola")
        self.play(Transform(titulo, Text("Non-dominated sorting: descascando a cebola", font_size=36).to_edge(UP, buff=0.3)))
        escadas, rotulos = {}, {}
        contador = Text("camadas: 0", font_size=24).move_to(RIGHT * 4.6 + DOWN * 0.6)
        self.play(FadeIn(contador))
        for k in range(1, R + 1):
            camada = dots_do_rank(k)
            pts_k = [p for p in todos if rank[p] == k]
            escadas[k] = escada(axes, pts_k, stroke_color=cor_rank[k], stroke_width=3.5)
            rotulos[k] = Text(f"r = {k}", font_size=20, color=cor_rank[k]).next_to(axes.c2p(*max(pts_k)), RIGHT, buff=0.15)
            self.play(*[d.animate.scale(1.6) for d in camada], run_time=0.4)
            self.play(
                Create(escadas[k]),
                FadeIn(rotulos[k]),
                *[d.animate.scale(1 / 1.6) for d in camada],
                Transform(contador, Text(f"camadas: {k}", font_size=24).move_to(contador)),
                run_time=0.9,
            )
            # descascar: a camada recua para revelar a próxima
            self.play(
                *[d.animate.set_opacity(0.3) for d in camada],
                escadas[k].animate.set_stroke(opacity=0.45),
                run_time=0.35,
            )
        resumo = Text(f"R = {R} camadas\nR* = R + 1 = {R_star}", font_size=24, line_spacing=0.9)
        resumo.next_to(contador, DOWN, buff=0.35, aligned_edge=LEFT)
        self.play(FadeIn(resumo))

        # destaca P*
        self.play(
            *[d.animate.set_opacity(1) for d in dots_do_rank(1)],
            escadas[1].animate.set_stroke(opacity=1, width=5),
        )
        pstar_txt = Text(f"r = 1  →  P*  (|P*| = {len(p_star)})", font_size=22, color=RANK_TOPO)
        pstar_txt.next_to(resumo, DOWN, buff=0.35, aligned_edge=LEFT)
        self.play(FadeIn(pstar_txt), Indicate(escadas[1], color=RANK_TOPO, scale_factor=1.02))
        self.wait(1.5)

        # ======================================================= 4. Purity
        self.next_section("purity")
        self.play(Transform(titulo, Text("Purity: quanto de P* cada algoritmo encontrou", font_size=36).to_edge(UP, buff=0.3)))
        todos_dots = VGroup(*[d for a in algs for d in dots[a]])
        outras = VGroup(*[escadas[k] for k in range(2, R + 1)], *[rotulos[k] for k in range(2, R + 1)])
        sockets = VGroup(*[Circle(radius=0.1, color=WHITE, stroke_width=2.5).move_to(axes.c2p(*p)) for p in p_star])
        self.play(
            FadeOut(todos_dots), FadeOut(outras), FadeOut(legenda), FadeOut(contador),
            FadeOut(resumo), FadeOut(pstar_txt),
        )
        self.play(LaggedStart(*[Create(s) for s in sockets], lag_ratio=0.05))
        formula = MarkupText("Purity(F) = |F ∩ P*| / |P*|", font_size=26).move_to(RIGHT * 4.3 + UP * 2.4)
        self.play(Write(formula))

        socket_de = dict(zip(p_star, sockets))
        linhas = VGroup()
        barra_max = 2.6
        for i, a in enumerate(algs):
            acertos = [p for p in fronts[a] if rank[p] == 1]
            dentro = VGroup(*[pontos_de[a][p] for p in acertos])
            fora = VGroup(*[d for p, d in pontos_de[a].items() if rank[p] != 1])
            for d in dots[a]:
                d.set_opacity(1)
            self.play(FadeIn(dots[a]), run_time=0.5)
            self.play(fora.animate.set_opacity(0.15), run_time=0.4)
            if acertos:
                self.play(
                    *[socket_de[p].animate.set_fill(CORES[a], opacity=1).set_stroke(CORES[a]) for p in acertos],
                    *[Flash(d, color=CORES[a], line_length=0.12, flash_radius=0.18) for d in dentro],
                    run_time=0.8,
                )
            frac = len(acertos) / len(p_star)
            nome = Text(NOMES.get(a, a), font_size=22, color=CORES[a])
            valor = Text(f"{len(acertos)}/{len(p_star)} = {frac:.2f}", font_size=22)
            fundo_barra = Rectangle(width=barra_max, height=0.16, stroke_color=GREY_D, stroke_width=1)
            barra = Rectangle(width=max(barra_max * frac, 0.001), height=0.16, stroke_width=0,
                              fill_color=CORES[a], fill_opacity=1).align_to(fundo_barra, LEFT)
            linha = VGroup(VGroup(nome, valor).arrange(RIGHT, buff=0.3), VGroup(fundo_barra, barra))
            linha.arrange(DOWN, aligned_edge=LEFT, buff=0.12)
            linha.move_to(RIGHT * 4.3 + UP * (1.3 - 1.05 * i)).align_to(formula, LEFT).shift(RIGHT * 0.1)
            linhas.add(linha)
            self.play(FadeIn(linha[0]), FadeIn(fundo_barra), GrowFromEdge(barra, LEFT))
            self.play(FadeOut(dots[a]), run_time=0.4)
        obs = Text("Pontos repetidos entre algoritmos\ncontam para cada um deles.", font_size=17, color=GREY_B, line_spacing=0.9)
        obs.next_to(linhas, DOWN, buff=0.4, aligned_edge=LEFT)
        self.play(FadeIn(obs))
        self.wait(2)

        # ====================================================== 5. Eq. 3.6
        self.next_section("eq36")
        self.play(FadeOut(linhas), FadeOut(obs), FadeOut(formula), FadeOut(sockets))
        self.play(Transform(titulo, Text("Eq. 3.6: em que camada estão os pontos?", font_size=36).to_edge(UP, buff=0.3)))
        for a in algs:
            for d in dots[a]:
                d.set_opacity(1)
        outras_esc = VGroup(*[escadas[k] for k in range(1, R + 1)], *[rotulos[k] for k in range(2, R + 1)])
        for k in range(1, R + 1):
            escadas[k].set_stroke(opacity=0.6, width=3)
        self.play(FadeIn(todos_dots), FadeIn(outras_esc))

        grafico = VGroup(axes, xl, yl, outras_esc, rotulos[1], todos_dots)
        self.play(grafico.animate.scale(0.58).to_corner(DL, buff=0.35))

        equacao = MarkupText(
            "Norm(F) = (1/|F|) · Σ<sub>p∈F</sub> (R* − r<sub>p</sub>)",
            font_size=30,
        ).move_to(RIGHT * 2.4 + UP * 2.35)
        legenda_eq = Text(f"R* = {R_star}   ·   rank 1 vale {R_star - 1}, rank {R} vale 1", font_size=18, color=GREY_B)
        legenda_eq.next_to(equacao, DOWN, buff=0.18)
        self.play(Write(equacao), FadeIn(legenda_eq))

        base_y = -2.75
        u = min(0.85, 3.6 / R)
        col_w = 2.45
        centros = [RIGHT * (x) for x in (-0.25 + col_w * i for i in range(len(algs)))]
        if len(algs) > 3:
            col_w = 7.2 / len(algs)
            centros = [RIGHT * (-0.9 + col_w * (i + 0.5)) for i in range(len(algs))]
        resultados = VGroup()
        for i, a in enumerate(algs):
            pts = sorted(fronts[a], key=lambda p: (rank[p], p))
            n = len(pts)
            w = min(0.28, (col_w - 0.35) / n)
            barras = VGroup()
            for j, p in enumerate(pts):
                h = (R_star - rank[p]) * u
                b = Rectangle(width=w * 0.82, height=h, stroke_width=0, fill_color=cor_rank[rank[p]], fill_opacity=0.95)
                b.move_to([centros[i][0] - (n * w) / 2 + w * (j + 0.5), base_y + h / 2, 0])
                barras.add(b)
            chao = Line([centros[i][0] - col_w / 2 + 0.1, base_y, 0], [centros[i][0] + col_w / 2 - 0.1, base_y, 0],
                        color=GREY_C, stroke_width=1.5)
            nome = Text(NOMES.get(a, a), font_size=20, color=CORES[a]).next_to(chao, DOWN, buff=0.12)
            origem = [pontos_de[a][p].copy() for p in pts]
            self.play(FadeIn(chao), FadeIn(nome))
            self.play(LaggedStart(*[ReplacementTransform(o, b) for o, b in zip(origem, barras)], lag_ratio=0.04, run_time=1.4))

            media = sum(R_star - rank[p] for p in pts) / n
            linha_media = DashedLine([chao.get_left()[0], base_y + media * u, 0], [chao.get_right()[0], base_y + media * u, 0],
                                     color=WHITE, stroke_width=2)
            soma = sum(R_star - rank[p] for p in pts)
            conta = Text(f"{soma} / {n}", font_size=18, color=GREY_A).next_to(linha_media, UP, buff=0.1)
            self.play(Create(linha_media), FadeIn(conta))
            bloco = Rectangle(width=n * w, height=media * u, stroke_width=0, fill_color=CORES[a], fill_opacity=0.55)
            bloco.move_to([centros[i][0], base_y + media * u / 2, 0])
            valor = Text(f"{media:.2f}", font_size=26, weight=BOLD).next_to(linha_media, UP, buff=0.1)
            norm01 = Text(f"÷ (R*−1) = {media / (R_star - 1):.2f}", font_size=17, color=GREY_B).next_to(valor, UP, buff=0.18)
            self.play(ReplacementTransform(barras, bloco), ReplacementTransform(conta, valor), run_time=1.0)
            self.play(FadeIn(norm01))
            resultados.add(VGroup(chao, nome, bloco, linha_media, valor, norm01))

        fecho = Text(
            "Dividir por |F| evita favorecer fronteiras com mais pontos.\n"
            "R* muda de uma instância para outra: compare Norm(F) dentro\n"
            "da mesma instância, ou use Norm(F) ÷ (R*−1), que fica em [0, 1].",
            font_size=16, color=GREY_A, line_spacing=0.9,
        ).next_to(legenda_eq, DOWN, buff=0.25)
        if fecho.get_right()[0] > config.frame_x_radius - 0.3:
            fecho.shift(LEFT * (fecho.get_right()[0] - config.frame_x_radius + 0.3))
        self.play(FadeIn(fecho))
        self.wait(3)
