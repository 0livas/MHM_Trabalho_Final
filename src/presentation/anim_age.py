"""AGE-MOEA: a membrana que descobre a forma da frente. Todos os números vêm de data/trace_age.json."""

from collections import Counter

from manim import (
    Circle, Create, DashedLine, Dot, FadeIn, FadeOut, GrowFromCenter, Indicate, LaggedStart, Line,
    Polygon, ReplacementTransform, Square, Transform, TransformFromCopy, VGroup, VMobject, ValueTracker,
    always_redraw, linear, smooth, there_and_back, PI,
)
import numpy as np

from fabrica import DADOS, EIXO, CenaContinua, Eixo, maquina, plano, rotulo
from visual import (
    COLORS, CORAL, FUNDO, GOLD, GREEN, GRID, HERE, INK, MUTED, axes, dots, formula, left, pos, pt, read_json,
    staircase, text,
)

T = read_json(HERE / "data" / "trace_age.json")
PAR, EV, GER = T["parametros"], T["eventos"], T["geracoes"]
G, G2 = T["escolha"]["geracao"], T["escolha"]["outra"]
P = PAR["population_size"]
COR = COLORS["age"]
EXATA = [(p["cmax"], p["tec"]) for p in DADOS["front"]]
FRENTE = [(p["cmax"], p["tec"]) for p in T["frente"]]
ESMAECIDO = .18


def moeda(v):
    return f"$ {pt(v, 1)}"


def valor_txt(p, color=GOLD):
    return text(f"{p['cmax']} h · {moeda(p['tec'])}", 25, color, bold=True).move_to(pos(5.02, -2.12))


def eixos_base():
    # Limites tirados do trace: Cmax até 24 h, TEC de 478,8 (exata) até o maior da população inicial.
    todos = [f for g in GER for f in g["F"]] + [list(p) for p in EXATA]
    assert all(10 <= c <= 26 and 400 <= t <= 1600 for c, t in todos)
    return axes((10, 26, 4), (400, 1600, 200), center=(5.02, .35), width=2.75, height=2.7,
                x_label="Cmax (h)", y_label="TEC ($)", numbers=True)


def eixos_nuvem():
    assert all(10 <= c <= 26 and 600 <= t <= 1200 for c, t in GER[G]["F"])
    return axes((10, 26, 2), (600, 1200, 100), center=(-1.9, -.25), width=7.4, height=3.8,
                x_label="Cmax (h)", y_label="TEC ($)", numbers=True)


def bola(filho, r=.09):
    if filho:
        return Dot(radius=r, color=COR)
    return Circle(radius=r, color=COR, stroke_width=2.5, fill_color=FUNDO, fill_opacity=1)


class Gantt:
    """Barras, setups e esperas por tarefa; `ir` devolve as animações até outro plano."""

    def __init__(self, p, eixo=EIXO):
        self.eixo = eixo
        self.t = {b["job"]: eixo.bloco(b) for b in p["blocks"]}
        self.s = {b["job"]: eixo.setup(b) for b in p["blocks"]}
        self.e = {b["job"]: eixo.espera(b) for b in p["blocks"]}

    def grupo(self):
        return VGroup(*self.s.values(), *self.e.values(), *self.t.values())

    def itens(self):
        return [*self.s.values(), *self.e.values(), *self.t.values()]

    def ir(self, p, fora=(), **kw):
        anims = []
        for b in p["blocks"]:
            j = b["job"]
            anims += [Transform(self.s[j], self.eixo.setup(b), **kw), Transform(self.e[j], self.eixo.espera(b), **kw)]
            if j not in fora:
                anims.append(Transform(self.t[j], self.eixo.bloco(b), **kw))
        return anims

    def alvo(self, p, j):
        return self.eixo.bloco(next(b for b in p["blocks"] if b["job"] == j))


# ---------------------------------------------------------------- quadro unitário e membrana

class Quadro:
    """Quadrado unitário da frente normalizada."""
    ox, oy, lado = -4.9, -2.5, 4.1

    def at(self, u, v):
        return pos(self.ox + u * self.lado, self.oy + v * self.lado)

    def moldura(self):
        return VGroup(Polygon(self.at(0, 0), self.at(1, 0), self.at(1, 1), self.at(0, 1),
                              stroke_color=GRID, stroke_width=1.5),
                      Line(self.at(0, 0), self.at(1, 0), color=MUTED, stroke_width=2),
                      Line(self.at(0, 0), self.at(0, 1), color=MUTED, stroke_width=2))

    def marcas(self):
        return VGroup(text("0", 20, MUTED).move_to(self.at(0, 0) + pos(0, -.25)),
                      text("1", 20, MUTED).move_to(self.at(1, 0) + pos(0, -.25)),
                      text("0", 20, MUTED).move_to(self.at(0, 0) + pos(-.25, 0)),
                      text("1", 20, MUTED).move_to(self.at(0, 1) + pos(-.25, 0)))


Q = Quadro()


def lp(p, c=1.0, n=90):
    """Curva |x|^p + |y|^p = c no primeiro quadrante."""
    a = np.linspace(0, PI / 2, n)
    return np.cos(a) ** (2 / p) * c ** (1 / p), np.sin(a) ** (2 / p) * c ** (1 / p)


def membrana(p, c=1.0):
    pts = [Q.at(x, y) for x, y in zip(*lp(p, c))]
    pele = VMobject(stroke_width=0, fill_color=COR, fill_opacity=.12).set_points_as_corners(
        [Q.at(0, 0), *pts, Q.at(0, 0)])
    fios = [VMobject(stroke_color=COR, stroke_width=w, stroke_opacity=o).set_points_as_corners(pts)
            for w, o in ((16, .12), (8, .25), (3, 1))]
    return VGroup(pele, *fios)


def membrana_fraca(p):
    g = membrana(p)
    g[0].set_fill(opacity=.08)
    for fio, o in zip(g[1:], (.05, .10, .4)):
        fio.set_stroke(opacity=o)
    return g


def bola_lp(u, r, p):
    """Bola Lp em torno de um ponto: a régua curva do escore."""
    x, y = lp(p, r ** p, 40)
    xs = np.concatenate([x, -x[::-1], -x, x[::-1]])
    ys = np.concatenate([y, y[::-1], -y, -y[::-1]])
    return VMobject(stroke_color=COR, stroke_width=2.5, fill_color=COR, fill_opacity=.10).set_points_as_corners(
        [Q.at(u[0] + a, u[1] + b) for a, b in zip(xs, ys)])


def geo(g):
    return GER[g]["geometria"]


def distintos(g):
    """Pontos únicos da camada 0 no quadro unitário e quantas cópias cada um tem."""
    x = geo(g)
    if x["degenerada"]:
        return []
    return sorted(Counter((round(a, 9), round(b, 9)) for a, b in x["unit"]).items())


def pontos_unit(g, r=.10):
    return VGroup(*(Dot(Q.at(*u), radius=r, color=COR) for u, _ in distintos(g)))


def p_txt(p, x=.75, y=1.0, size=54):
    return left(rotulo(f"p = {pt(p, 2)}", size, COR, True), x, y)


def ger_txt(g):
    return left(text(f"geração {g}", 24, MUTED), .75, 1.6)


def quadro_primeira():
    """Fim de AgeCamadas: a primeira camada no plano grande."""
    eixo, labels = eixos_nuvem()
    f = geo(G)["F"]
    pts = VGroup(*(bola(i >= 0, .11).move_to(eixo.c2p(*q)) for i, q in enumerate(f)))
    ordem = sorted(f)
    casca = VMobject(stroke_color=COR, stroke_width=9, stroke_opacity=.45).set_points_as_corners(
        [eixo.c2p(*q) for q in ordem])
    return eixo, labels, casca, pts


# ---------------------------------------------------------------- lista do escore

def linha_nota(k, nota, f, cor=INK):
    y = 1.35 - .42 * k
    return VGroup(left(text(nota, 24, COR, bold=True), 2.35, y),
                  left(text(f"{f[0]:.0f} h · {moeda(f[1])}", 22, cor), 3.55, y))


def linhas_escore():
    x = geo(G)
    linhas = [linha_nota(k, "∞", x["F"][i]) for k, i in enumerate(x["extremos"])]
    linhas += [linha_nota(k + 2, pt(e["escore"], 2), x["F"][e["i"]]) for k, e in enumerate(x["entradas"])]
    return linhas


def linhas_outras():
    r = GER[G]
    meio = [e for e, q in zip(r["escore"], r["posto"]) if q is not None and 0 < q < r["corte"]["camada"]]
    assert r["corte"]["todos_zero"] and pt(min(meio), 4) == pt(max(meio), 4)
    cortada = r["corte"]["camada"]
    return [VGroup(left(text(pt(meio[0], 4), 22, MUTED, bold=True), 2.35, -1.45),
                   left(text(f"camadas 1–{cortada - 1} · 1 ÷ distância", 18, MUTED), 3.5, -1.45)),
            VGroup(left(text("0", 22, MUTED, bold=True), 2.35, -1.87),
                   left(text(f"camada {cortada}, a cortada", 18, MUTED), 3.5, -1.87))]


def titulo_lista():
    return left(text("ordem de entrada", 20, MUTED), 2.35, 1.82)


def frase_escore():
    return left(text("longe dos já escolhidos", 25, COR, bold=True), 2.35, -2.55)


class CenaAge(CenaContinua):
    chapter, total = "META-HEURÍSTICA · AGE-MOEA", 3

    def abrir(self, titulo=None):
        super().abrir(titulo)
        pe = left(text(f"Demonstração · instância didática · população {P} · {PAR['max_evaluations']} avaliações · "
                       f"cruzamento {pt(PAR['crossover_probability'], 1)} · mutação {pt(PAR['mutation_probability'], 1)} · "
                       f"seed {PAR['seed']} (caso escolhido)", 17, MUTED, width=11.6), -6.55, -3.60)
        self.remove(self.cabecalho)
        self.cabecalho = VGroup(*self.cabecalho[:4], pe, self.cabecalho[5])
        self.add(self.cabecalho)


# ================================================================ 1

class AgeCamadas(CenaAge):
    number = 1

    def construct(self):
        self.abrir()
        base = self.base()
        inicial = Gantt(plano(15))
        eixo, labels = eixos_base()
        ponto = Dot(eixo.c2p(15, plano(15)["tec"]), radius=.11, color=GOLD)
        valor = valor_txt(plano(15))
        self.add(*base, *inicial.itens(), eixo, labels, ponto, valor)
        self.beat("lote", "Um plano por vez, ou uma turma inteira?")
        arena = GER[G]["arena"]
        passo, x0, yp, yf = .53, -5.0, 2.28, 1.92
        pais = {i: bola(False).move_to(pos(x0 + passo * k, yp)) for k, i in enumerate(arena[:P])}
        esteira = Line(pos(-5.3, 2.1), pos(x0 + passo * P, 2.1), color=GRID, stroke_width=2)
        ev = EV["espera"]
        self.play(Create(esteira), FadeOut(VGroup(*inicial.itens())), FadeOut(valor), FadeOut(ponto),
                  FadeOut(self.tarifa), FadeOut(self.tarifa_rotulos),
                  LaggedStart(*(FadeIn(b, shift=pos(-.6, 0)) for b in reversed(pais.values())), lag_ratio=.06),
                  run_time=1.3)
        # A dupla de pais vira dois Gantts pequenos sob o grande.
        minis = []
        for k, (pid, pp) in enumerate(zip(ev["pais"], ev["planos_pais"])):
            e = Eixo(-5.75 + 4.75 * k, .20, (-2.28, -2.63, -2.98), .27)
            gm = Gantt(pp, e)
            quadro = VGroup(e.trilhos(), gm.grupo())
            self.play(Indicate(pais[pid], color=INK, scale_factor=1.6),
                      FadeIn(quadro, target_position=pais[pid], scale=.1), run_time=.7)
            minis.append((gm, quadro))
        antes, depois = ev["antes"], ev["depois"]
        filho = Gantt(antes)
        self.play(LaggedStart(*(TransformFromCopy(minis[ev["fontes"][str(b["job"])]][0].t[b["job"]],
                                                  filho.t[b["job"]], path_arc=-.5)
                                for b in antes["blocks"]), lag_ratio=.12), run_time=1.5)
        cv, tv = ValueTracker(antes["cmax"]), ValueTracker(antes["tec"])
        ponto = always_redraw(lambda: bola(True, .11).move_to(eixo.c2p(cv.get_value(), tv.get_value())))
        valor = always_redraw(lambda: rotulo(f"{round(cv.get_value())} h · {moeda(tv.get_value())}", 25, COR,
                                             True).move_to(pos(5.02, -2.12)))

        def ate(p):
            return [cv.animate.set_value(p["cmax"]), tv.animate.set_value(p["tec"])]

        def pouso(b):
            # Cópia sem updater: objeto com updater não deve sofrer Transform.
            return TransformFromCopy(ponto.copy().clear_updaters(), b, path_arc=.6)
        self.play(*(FadeIn(m) for m in (*filho.s.values(), *filho.e.values())), FadeIn(ponto), FadeIn(valor),
                  *(m[1].animate.set_opacity(ESMAECIDO) for m in minis), run_time=.5)
        # Espera: antecipação, elástico, consequência no mesmo instante do ponto.
        job = ev["jobs"][0]
        self.play(Indicate(filho.t[job], color=GOLD, scale_factor=1.12), run_time=.4)
        self.add(rastro := Dot(ponto.get_center(), radius=.05, color=MUTED))
        self.play(*filho.ir(depois), *ate(depois), run_time=1.3)
        self.play(Indicate(filho.t[job], color=GREEN, scale_factor=1.12), run_time=.4)
        # O primeiro filho desce e espera a turma.
        filhos = {i: bola(True).move_to(pos(x0 + passo * k, yf)) for k, i in enumerate(arena[P:])}
        b1 = filhos[ev["id"]]
        self.play(pouso(b1), run_time=.6)
        # Segunda vez, mais rápido: inserção.
        ei = EV["insercao"]
        self.play(FadeOut(VGroup(*filho.itens())), FadeOut(rastro), run_time=.25)
        seg = Gantt(ei["antes"])
        self.play(*(FadeIn(m) for m in seg.itens()), *ate(ei["antes"]), run_time=.45)
        job = ei["jobs"][0]
        barra = seg.t[job]
        self.bring_to_front(barra)
        self.play(barra.animate.shift(pos(0, .55)), run_time=.35)
        rastro = Dot(ponto.get_center(), radius=.05, color=MUTED)
        self.add(rastro)
        alvo = seg.alvo(ei["depois"], job)
        self.play(*seg.ir(ei["depois"], fora=(job,)), Transform(barra, alvo.copy().shift(pos(0, .55))), *ate(ei["depois"]), run_time=.9)
        self.play(Transform(barra, alvo), run_time=.3)
        self.play(Indicate(barra, color=GREEN, scale_factor=1.12),
                  pouso(filhos[ei["id"]]), run_time=.5)
        # O resto da turma chega de uma vez.
        resto = [b for i, b in filhos.items() if i not in (ev["id"], ei["id"])]
        self.play(LaggedStart(*(FadeIn(b, shift=pos(0, -.35)) for b in resto), lag_ratio=.05),
                  *(FadeOut(m[1]) for m in minis), run_time=.8)
        conta = VGroup(text(f"{P} pais + {P} filhos", 30, COR, bold=True)).move_to(pos(-2.3, -2.5))
        self.play(FadeIn(conta, shift=pos(0, .12)), run_time=.4)
        self.hold()

        # ------------------------------------------------ camadas
        ponto.clear_updaters()
        valor.clear_updaters()
        self.beat("camadas", "Quem passa primeiro?", VGroup(*seg.itens()), conta, rastro, ponto, valor, labels,
                  self.maquinas, self.trilhos, self.horas, self.faixa, esteira)
        grande, gl = eixos_nuvem()
        r = GER[G]
        assert r["viaveis"] == arena
        f = dict(zip(r["viaveis"], r["F"]))
        posto = dict(zip(r["viaveis"], r["posto"]))
        escore = dict(zip(r["viaveis"], r["escore"]))
        todas = pais | filhos
        # Posto 0 fica por cima quando há coincidência de coordenadas.
        self.play(ReplacementTransform(eixo, grande), FadeIn(gl),
                  LaggedStart(*(b.animate(path_arc=.4).move_to(grande.c2p(*f[i])) for i, b in todas.items()),
                              lag_ratio=.02), run_time=1.5)
        vagas = VGroup(*(Circle(radius=.15, color=GRID, stroke_width=1.5).move_to(
            pos(4.15 + .6 * (k % 4), .95 - .6 * (k // 4))) for k in range(P)))
        rot_v = text(f"{r['vagas']} vagas", 22, MUTED).move_to(pos(5.05, 1.6))
        a, b = bola(False).move_to(pos(4.0, -1.85)), bola(True).move_to(pos(5.35, -1.85))
        leg = VGroup(a, text("pai", 19, MUTED).next_to(a, pos(1, 0), buff=.12),
                     b, text("filho", 19, MUTED).next_to(b, pos(1, 0), buff=.12))
        self.play(FadeIn(vagas), FadeIn(rot_v), FadeIn(leg), run_time=.4)
        ultima, n, casca0, extras, copias = r["corte"]["camada"], 0, None, VGroup(), VGroup()
        tempos = (1.1, .75, .6)
        for k in range(ultima + 1):
            membros = sorted((i for i in todas if posto[i] == k), key=lambda i: tuple(f[i]))
            cor_op = (.55, .38, .28, .22)[k]
            casca = VMobject(stroke_color=COR, stroke_width=13 - 2 * k, stroke_opacity=cor_op).set_points_as_corners(
                [grande.c2p(*f[i]) for i in membros])
            nome = text(f"{k}", 20, COR, bold=True).next_to(grande.c2p(*f[membros[-1]]), pos(1, 0), buff=.2)
            self.play(Create(casca), FadeIn(nome),
                      *(todas[i].animate.set_fill(INK if i >= arena[P] else FUNDO).scale(1.15) for i in membros),
                      run_time=tempos[min(k, 2)])
            ficam = [i for i in membros if i in r["sobreviventes"]]
            if k < ultima:
                assert ficam == membros
            else:
                # Empate em zero: no pymoo a camada cortada ainda não recebeu escore.
                assert all(escore[i] == 0 for i in membros) and len(ficam) < len(membros)
                notas = VGroup(*(text("0", 22, GOLD, bold=True).move_to(
                    todas[i].get_center() + pos(0, .29)) for i in membros))
                self.play(FadeIn(notas, shift=pos(0, .1)), run_time=.4)
                frase = text("nota 0: empate na camada cortada", 22, GOLD).move_to(pos(-1.2, 1.95))
                self.play(FadeIn(frase), run_time=.3)
                extras.add(notas, frase)
                self.wait(.5)
            novas = [todas[i].copy().set_fill(COR if i >= arena[P] else FUNDO).move_to(vagas[n + q])
                     for q, i in enumerate(ficam)]
            anims = [TransformFromCopy(todas[i], c, path_arc=-.4) for i, c in zip(ficam, novas)]
            if k == ultima:
                # A casca parte: os segmentos até os descartados se soltam.
                fora = [i for i in membros if i not in ficam]
                pedacos = VGroup(*(Line(grande.c2p(*f[x]), grande.c2p(*f[y]), color=MUTED, stroke_width=5,
                                        stroke_opacity=.5) for x, y in zip(membros, membros[1:])))
                self.remove(casca)
                self.add(pedacos)
                anims += [s.animate.shift(pos(0, -.25)).rotate(.12 * (-1) ** q).set_opacity(0)
                          for q, s in enumerate(pedacos)]
                anims += [todas[i].animate.set_color(MUTED).set_opacity(.35) for i in fora]
                anims += [todas[i].animate.set_color(MUTED).set_opacity(.2) for i in todas if posto[i] is None]
                extras.add(nome)
            self.play(*anims, run_time=.9 if k else 1.1)
            copias.add(*novas)
            n += len(ficam)
            if k == 0:
                casca0, nome0 = casca, nome
            elif k < ultima:
                extras.add(casca, nome)
        assert n == r["vagas"]
        frase2 = text("casca por casca", 26, COR, bold=True).move_to(pos(5.05, -2.45))
        self.play(FadeIn(frase2), run_time=.4)
        self.wait(.7)
        eixo2, l2, casca_f, pts_f = quadro_primeira()
        zero = [i for i in todas if posto[i] == 0]
        ordem = [next(i for i in zero if f[i] == q) for q in geo(G)["F"]]
        resto = [todas[i] for i in todas if i not in zero]
        self.remove(pedacos)
        self.play(FadeOut(extras), FadeOut(copias), FadeOut(vagas), FadeOut(rot_v), FadeOut(leg), FadeOut(frase2),
                  FadeOut(nome0), *(FadeOut(m) for m in resto), ReplacementTransform(casca0, casca_f),
                  *(ReplacementTransform(todas[i], q) for i, q in zip(ordem, pts_f)), run_time=.9)
        self.hold()


# ================================================================ 2

class AgeGeometria(CenaAge):
    number = 2

    def construct(self):
        self.abrir("Quem passa primeiro?")
        eixo, labels, casca, pts = quadro_primeira()
        self.add(eixo, labels, casca, *pts)
        self.beat("extremos", "Em que escala medir?")
        x = geo(G)
        (c0, t1), (c1, t0) = (x["F"][i] for i in sorted(x["extremos"], key=lambda i: x["F"][i][0]))
        assert x["ideal"] == [c0, t0] and np.allclose(x["norma"], [c1 - c0, t1 - t0])
        pinos = VGroup()
        for i in x["extremos"]:
            c = pts[i].get_center()
            pinos.add(VGroup(Line(c, c + pos(.22, .5), color=INK, stroke_width=3),
                             Dot(c + pos(.22, .5), radius=.12, color=CORAL)))
        self.play(LaggedStart(*(FadeIn(p, shift=pos(-.3, -.7)) for p in pinos), lag_ratio=.5), run_time=1.1)
        self.play(*(Indicate(pts[i], color=INK, scale_factor=1.7) for i in x["extremos"]), run_time=.5)
        o, dx, dy = eixo.c2p(c0, t0), eixo.c2p(c1, t0), eixo.c2p(c0, t1)
        topo = eixo.c2p(c1, t1)
        caixa = VGroup(Polygon(o, dx, topo, dy, stroke_color=GRID, stroke_width=1.5),
                       Line(o, dx, color=MUTED, stroke_width=2), Line(o, dy, color=MUTED, stroke_width=2))
        # Números antigos, um em cada ponta da régua.
        velhos = VGroup(text(f"{c0:.0f} h", 21, INK, bold=True).move_to(o + pos(.18, -.28)),
                        text(f"{c1:.0f} h", 21, INK, bold=True).move_to(dx + pos(0, -.28)),
                        text(moeda(t0), 21, INK, bold=True).move_to(o + pos(-.62, 0)),
                        text(moeda(t1), 21, INK, bold=True).move_to(dy + pos(-.62, 0)))
        for v in velhos:
            v.add_background_rectangle(color=FUNDO, opacity=.9, buff=.05)
        conta = VGroup(left(text(f"{c1:.0f} − {c0:.0f} = {x['norma'][0]:.0f} h  →  1", 21), 2.35, .55),
                       left(text(f"{pt(t1, 1)} − {pt(t0, 1)} = {moeda(x['norma'][1])}  →  1", 21), 2.35, .05))
        self.play(Create(caixa), eixo.animate.set_opacity(.2), labels.animate.set_opacity(.15), run_time=.9)
        self.play(FadeIn(velhos), run_time=.4)
        self.wait(.4)
        self.wait(.6)
        self.play(FadeIn(conta), run_time=.6)
        self.wait(.8)
        unit = VGroup(*(Dot(Q.at(*u), radius=.11, color=COR) for u in x["unit"]))
        moldura, marcas = Q.moldura(), Q.marcas()
        casca_u = VMobject(stroke_color=COR, stroke_width=9, stroke_opacity=.45).set_points_as_corners(
            [Q.at(*u) for u in sorted(x["unit"])])
        desl = [Q.at(*x["unit"][i]) - pts[i].get_center() for i in x["extremos"]]
        lugares = [m.get_center() for m in marcas]
        lugares[2], lugares[3] = lugares[2] + pos(-.35, 0), lugares[3] + pos(-.35, 0)
        self.play(FadeOut(eixo), FadeOut(labels), ReplacementTransform(caixa, moldura),
                  ReplacementTransform(casca, casca_u), *(ReplacementTransform(a, b) for a, b in zip(pts, unit)),
                  *(p.animate.shift(d) for p, d in zip(pinos, desl)),
                  *(v.animate.move_to(q) for v, q in zip(velhos, lugares)), run_time=1.6)
        self.play(FadeOut(velhos), FadeIn(marcas), run_time=.4)
        frase = left(text("extremos fixam a régua", 25, COR, bold=True), 2.35, -.75)
        self.play(FadeIn(frase), *(Indicate(m, color=INK, scale_factor=1.5) for m in (marcas[1], marcas[3])),
                  run_time=.6)
        diag = Line(Q.at(0, 0), Q.at(1, 1), color=INK, stroke_width=2, stroke_opacity=.6)
        self.play(Create(diag), run_time=.6)
        self.hold()

        # ------------------------------------------------ membrana
        self.beat("membrana", "Qual é a curvatura desta frente?", conta, frase)
        self.play(FadeOut(casca_u), run_time=.3)

        def perpendicular(u, **kw):
            m = sum(u) / 2
            return Line(Q.at(*u), Q.at(m, m), color=MUTED, stroke_width=2, **kw)
        internos = [i for i in range(len(x["unit"])) if i not in x["extremos"]]
        linhas = VGroup(*(perpendicular(x["unit"][i]) for i in internos))
        self.play(LaggedStart(*(Create(m) for m in linhas), lag_ratio=.25), run_time=1)
        ref = x["ref"]
        m = x["media"]
        pe = Dot(Q.at(m, m), radius=.07, color=INK)
        halo = Circle(radius=.22, color=INK, stroke_width=3).move_to(Q.at(*x["unit"][ref]))
        media = left(text(f"média das coordenadas {pt(m, 3)}", 22, INK), .75, -.02)
        self.play(*(FadeOut(a) for a, i in zip(linhas, internos) if i != ref), Create(halo),
                  linhas[internos.index(ref)].animate.set_stroke(INK, 3), FadeIn(pe), run_time=.7)
        self.play(FadeIn(media, shift=pos(-.2, 0)), run_time=.4)
        pv = ValueTracker(1.0)
        pele = always_redraw(lambda: membrana(pv.get_value()))
        num = always_redraw(lambda: p_txt(pv.get_value()))
        gl = ger_txt(G)

        def forma():
            p = pv.get_value()
            s = "para dentro" if p < .97 else "reta" if p <= 1.03 else "para fora"
            return left(rotulo(s, 24, MUTED), .75, .42)
        estado = always_redraw(forma)
        fixo = VGroup(linhas[internos.index(ref)], halo, pe)
        self.play(FadeIn(pele), FadeIn(num), FadeIn(gl), FadeIn(estado), run_time=.5)
        self.bring_to_front(*unit, fixo, pinos)
        self.wait(.3)
        self.play(pv.animate.set_value(.5), run_time=1.3, rate_func=smooth)
        self.wait(.3)
        self.play(pv.animate.set_value(2), run_time=2.2, rate_func=smooth)
        self.wait(.3)
        self.play(pv.animate.set_value(x["p"]), run_time=1.1, rate_func=smooth)
        for fator in (1.07, .95, 1.03, 1):
            self.play(pv.animate.set_value(x["p"] * fator), run_time=.14)
        lei = formula(r"p=\frac{\ln 2}{\ln(1/\bar{z})}", 2.6, .85, INK)
        left(lei, .75, -.85)
        self.play(FadeIn(lei), Indicate(media, color=COR, scale_factor=1.05), run_time=.8)
        self.wait(1.4)
        # A mesma membrana, noutra geração.
        y = geo(G2)
        unit2, fixo2, media2, gl2, mult = self.geracao(G2)
        pool = self.morfo(unit, unit2)
        self.play(*pool, FadeOut(fixo), FadeOut(media), ReplacementTransform(gl, gl2), run_time=1.4)
        self.remove(*unit)
        self.add(*unit2)
        self.play(FadeIn(fixo2), FadeIn(media2), FadeIn(mult), run_time=.5)
        self.play(pv.animate.set_value(y["p"]), run_time=1.8, rate_func=smooth)
        for fator in (.94, 1.05, 1):
            self.play(pv.animate.set_value(y["p"] * fator), run_time=.14)
        self.bring_to_front(*unit2, fixo2, pinos)
        self.hold()

        # ------------------------------------------------ escore (volta à geração da camada descascada)
        self.beat("escore", "Quem merece ficar?", fixo2, media2, mult, lei, diag)
        self.add(pv)
        gl3 = ger_txt(G)
        unit = VGroup(*(Dot(Q.at(*u), radius=.11, color=COR) for u in x["unit"]))
        fora = self.morfo(unit2, unit)
        self.play(*fora, pv.animate.set_value(x["p"]), ReplacementTransform(gl2, gl3), run_time=1)
        self.remove(*unit2, estado, num, pele, gl3)
        fixa = membrana(x["p"])
        self.add(fixa, *unit, pinos)
        cab = titulo_lista()
        ptxt = p_txt(x["p"], .0, 1.35, 34)
        self.play(FadeIn(cab), FadeIn(ptxt), Transform(fixa, membrana_fraca(x["p"])), FadeOut(pinos), *(
            unit[i].animate.set_color(MUTED) for i in internos), run_time=.4)
        linhas = linhas_escore()
        self.play(*(unit[i].animate.set_color(COR).scale(1.1) for i in x["extremos"]),
                  *(TransformFromCopy(unit[i], ln) for i, ln in zip(x["extremos"], linhas)), run_time=.8)
        for rodada, e in enumerate(x["entradas"]):
            i, lento = e["i"], rodada == 0
            notas = VGroup(*(text(pt(v, 2), 19, INK if j == i else MUTED, bold=j == i).move_to(
                Q.at(*x["unit"][j]) + (pos(.36, .22) if x["unit"][j][0] > .45 else pos(-.05, .32))) for j, v, _ in e["notas"]))
            u = np.array(x["unit"][i])
            viz = sorted(e["vizinhos"], key=lambda k: np.sum(np.abs(u - x["unit"][k]) ** x["p"]))
            raio = float(np.sum(np.abs(u - x["unit"][viz[0]]) ** x["p"]) ** (1 / x["p"]))
            todos = VGroup(*(Line(Q.at(*x["unit"][j]), Q.at(*x["unit"][k]), color=MUTED, stroke_width=1.5,
                                  stroke_opacity=.5) for j, _, ks in e["notas"] for k in ks))
            bola_ = bola_lp(u, raio, x["p"])
            elos = VGroup(*(Line(Q.at(*u), Q.at(*x["unit"][k]), color=INK, stroke_width=3) for k in viz))
            self.play(Create(todos), FadeIn(notas), run_time=1.2 if lento else .5)
            self.play(FadeOut(todos), Create(elos), GrowFromCenter(bola_), run_time=.8 if lento else .35)
            self.wait(1.1 if lento else .3)
            self.bring_to_front(unit[i])
            self.play(unit[i].animate.set_color(COR).scale(1.1), TransformFromCopy(notas[[j for j, *_ in e["notas"]].index(i)],
                                                                         linhas[rodada + 2]),
                      FadeOut(notas), FadeOut(elos), FadeOut(bola_), run_time=.8 if lento else .5)
        outras = linhas_outras()
        frase = frase_escore()
        self.play(FadeIn(frase), run_time=.4)
        self.play(LaggedStart(*(FadeIn(o, shift=pos(-.2, 0)) for o in outras), lag_ratio=.5), run_time=.9)
        self.hold()

    @staticmethod
    def morfo(de, para):
        """Cada ponto velho vai a um novo; quantidades diferentes dividem ou fundem pontos."""
        a, b = (sorted(g, key=lambda d: d.get_center()[0]) for g in (de, para))
        n = max(len(a), len(b))
        return [ReplacementTransform(a[k] if k < len(a) else a[-1].copy(), b[min(k, len(b) - 1)].copy()
                                     if k >= len(b) else b[k]) for k in range(n)]

    @staticmethod
    def geracao(g):
        y = geo(g)
        unit = pontos_unit(g, .11)
        u, m = y["unit"][y["ref"]], y["media"]
        fixo = VGroup(Line(Q.at(*u), Q.at(m, m), color=INK, stroke_width=3),
                      Circle(radius=.22, color=INK, stroke_width=3).move_to(Q.at(*u)),
                      Dot(Q.at(m, m), radius=.07, color=INK))
        media = left(text(f"média das coordenadas {pt(m, 3)}", 22, INK), .75, -.02)
        mult = VGroup(*(text(f"×{n}", 18, MUTED).move_to(Q.at(*v) + pos(.34, .16))
                        for v, n in distintos(g) if n > 1))
        return unit, fixo, media, ger_txt(g), mult


# ================================================================ 3

def quadro_escore():
    """Fim de AgeGeometria."""
    x = geo(G)
    fixa = membrana_fraca(x["p"])
    return VGroup(Q.moldura(), Q.marcas()), fixa, VGroup(*(Dot(Q.at(*u), radius=.121, color=COR) for u in x["unit"])), \
        VGroup(titulo_lista(), *linhas_escore(), *linhas_outras(), frase_escore()), p_txt(x["p"], .0, 1.35, 34)


class AgeBusca(CenaAge):
    number = 3

    def construct(self):
        self.abrir("Quem merece ficar?")
        base_u, fixa, unit, lista, ptxt = quadro_escore()
        self.add(base_u, fixa, *unit, lista, ptxt)
        self.beat("busca", "E depois de muitas turmas?", lista, ptxt)
        eixo, labels = eixos_base()
        exata = VGroup(staircase(eixo, EXATA, GOLD, 1.5).set_stroke(opacity=.4),
                       dots(eixo, EXATA, GOLD, .035).set_opacity(.4))
        pv, gv, av = ValueTracker(geo(G)["p"]), ValueTracker(G), ValueTracker(GER[G]["avaliacoes"])
        pele = always_redraw(lambda: membrana(pv.get_value()))
        num = always_redraw(lambda: p_txt(pv.get_value(), .0, 1.35, 34))
        n_lotes = len(T["evaluation_batches"])
        cont = always_redraw(lambda: VGroup(
            left(rotulo(f"lote {round(gv.get_value()) + 1} / {n_lotes}", 23, INK), 3.6, -2.1),
            left(rotulo(f"avaliações {round(av.get_value())} / {T['avaliacoes']}", 23, COR, True), 3.6, -2.48)))
        pos_de = dict(zip(GER[G]["viaveis"], GER[G]["F"]))
        # Uma partícula por sobrevivente; quem sai cede a partícula ao filho que entra.
        nuvem = {i: Dot(eixo.c2p(*pos_de[i]), radius=.055, color=COR) for i in GER[G]["sobreviventes"]}
        strip = self.faixa(G)
        casca = self.casca(G, eixo)
        pool = [Dot(d.get_center(), radius=.12, color=COR) for d in unit]
        pool += [pool[-1].copy() for _ in range(12 - len(pool))]
        self.remove(fixa, *unit)
        self.add(pele, *pool)
        self.play(FadeIn(eixo), FadeIn(labels), FadeIn(exata), FadeIn(num), FadeIn(cont),
                  *(FadeIn(d) for d in nuvem.values()), FadeIn(strip), Create(casca), run_time=.7)
        ruim = EV["inviavel"]
        for g in range(G + 1, len(GER)):
            novo = self.faixa(g)
            dur = 1.1 if g == G + 1 else 1.3 if g == len(GER) - 1 else .36
            if g == ruim["geracao"]:
                left_mobs = VGroup(base_u)
                self.remove(pele, num)
                foto = VGroup(membrana(pv.get_value()), p_txt(pv.get_value(), .0, 1.35, 34),
                              *(d.copy() for d in pool))
                self.remove(*pool)
                self.add(foto)
                self.play(FadeOut(foto), FadeOut(left_mobs), ReplacementTransform(strip, novo),
                          gv.animate.set_value(g), av.animate.set_value(GER[g]["avaliacoes"]), run_time=.5)
                strip = novo
                self.inviavel(ruim, strip, g)
                anims = self.mover(nuvem, g, eixo) + self.unitario(pool, g)
                self.play(FadeIn(base_u), *anims, Transform(casca, self.casca(g, eixo)), pv.animate.set_value(geo(g)["p"]), run_time=.6)
                self.remove(*pool)
                self.add(pele, num, *pool)
                continue
            self.play(*self.mover(nuvem, g, eixo), *self.unitario(pool, g), ReplacementTransform(strip, novo), Transform(casca, self.casca(g, eixo)),
                      pv.animate.set_value(geo(g)["p"]), gv.animate.set_value(g),
                      av.animate.set_value(GER[g]["avaliacoes"]), run_time=dur, rate_func=smooth if dur > .5 else linear)
            strip = novo
        parcial = text(f"último lote: {GER[-1]['lote']}", 19, GOLD, bold=True).move_to(pos(5.0, -3.12))
        self.play(FadeIn(parcial), Indicate(strip, color=GOLD, scale_factor=1.06), run_time=.6)
        self.wait(.5)
        # O compromisso vira o Gantt.
        fim = T["frente"][T["compromisso"]]
        assert fim["cmax"] <= EIXO.total
        base = self.base()
        gantt = Gantt(fim)
        frente = dots(eixo, FRENTE, COR, .065)
        escolhido = Dot(eixo.c2p(fim["cmax"], fim["tec"]), radius=.11, color=COR)
        foto = VGroup(membrana(pv.get_value()), p_txt(pv.get_value(), .0, 1.35, 34), *(d.copy() for d in pool))
        cfoto = cont.copy().clear_updaters()
        self.remove(pele, num, cont, *pool)
        self.add(foto, cfoto)
        self.play(FadeOut(foto), FadeOut(base_u), FadeOut(cfoto), FadeOut(strip), FadeOut(parcial), FadeOut(casca), run_time=.6)
        self.play(*(FadeIn(b) for b in base), *(FadeOut(d) for d in nuvem.values()), FadeIn(frente),
                  Create(staircase(eixo, FRENTE, COR, 2)), GrowFromCenter(escolhido), run_time=.7)
        self.bring_to_front(frente, escolhido)
        self.play(LaggedStart(*(TransformFromCopy(escolhido, gantt.t[j], path_arc=.5) for j in gantt.t), lag_ratio=.08),
                  run_time=1.3)
        c = T["campanha"]
        camp = text(f"campanha: {c['population_size']} · {pt(c['crossover_probability'], 1)} · "
                    f"{pt(c['mutation_probability'], 1)}", 21, MUTED).move_to(pos(4.95, -2.7))
        self.play(*(FadeIn(m) for m in (*gantt.s.values(), *gantt.e.values())), FadeIn(valor_txt(fim, COR)),
                  FadeIn(camp), run_time=.6)
        self.hold()

    @staticmethod
    def faixa(g):
        """O lote como P vagas: cheia, vazia (lote parcial) ou coral (inviável)."""
        novos = GER[g]["arena"][-GER[g]["lote"]:]
        ruins = set(GER[g]["inviaveis"])
        return VGroup(*(Square(.13, stroke_width=1.2, stroke_color=GRID, fill_opacity=1 if k < len(novos) else 0,
                               fill_color=(CORAL if novos[k] in ruins else COR) if k < len(novos) else GRID)
                        .move_to(pos(3.7 + .178 * k, -2.84)) for k in range(P)))

    @staticmethod
    def casca(g, eixo):
        f = sorted({tuple(q) for q in geo(g)["F"]})
        return VMobject(stroke_color=COR, stroke_width=5, stroke_opacity=.4).set_points_as_corners(
            [eixo.c2p(*q) for q in f])

    @staticmethod
    def mover(nuvem, g, eixo):
        r = GER[g]
        f = dict(zip(r["viaveis"], r["F"]))
        vivos = set(r["sobreviventes"])
        livres = [nuvem.pop(i) for i in list(nuvem) if i not in vivos]
        anims = []
        for i in r["sobreviventes"]:
            if i not in nuvem:
                nuvem[i] = livres.pop()
                anims.append(nuvem[i].animate.move_to(eixo.c2p(*f[i])))
        assert not livres
        return anims

    @staticmethod
    def unitario(pool, g):
        us = [u for u, _ in distintos(g)]
        assert len(us) <= len(pool)
        return [d.animate.move_to(Q.at(*us[min(k, len(us) - 1)])) for k, d in enumerate(pool)]

    def inviavel(self, ev, strip, g):
        e = Eixo(-5.2, .265, total=30)
        horiz = ev["depois"]["horizonte"]
        assert ev["depois"]["termino"] <= e.total
        gm = Gantt(ev["antes"], e)
        fundo = VGroup(e.faixa_ponta(), e.trilhos(), *(maquina(i) for i in range(3)), e.horas(-1.72, 4))
        x = e.at(horiz)
        marca = VGroup(DashedLine(pos(x, 1.75), pos(x, -1.6), color=CORAL),
                       text("horizonte", 19, CORAL).move_to(pos(x, 1.98)))
        self.play(FadeIn(fundo), FadeIn(marca), *(FadeIn(m) for m in gm.itens()), run_time=.5)
        job = ev["jobs"][0]
        barra = gm.t[job]
        self.bring_to_front(barra)
        self.play(*gm.ir(ev["depois"], fora=(job,)),
                  Transform(barra, gm.alvo(ev["depois"], job), path_arc=-.9), run_time=1.0)
        tudo = VGroup(*gm.itens())
        for d in (.07, -.14, .14, -.07):
            self.play(tudo.animate.shift(pos(d, 0)), run_time=.07)
        # Racha e some, mas a vaga coral permanece no lote já contado.
        fim = max(ev["depois"]["blocks"], key=lambda b: b["end"])
        alvo = gm.t[fim["job"]]
        r = alvo[0]
        w, h, c = r.width / 2, r.height, r.get_center()
        metades = VGroup(*(r.copy().stretch_to_fit_width(w).move_to(c + pos(s * w / 2, 0)) for s in (-1, 1)))
        self.remove(*tudo)
        self.add(*[m for m in gm.itens() if m is not alvo], metades)
        novos = GER[g]["arena"][-GER[g]["lote"]:]
        vaga = strip[novos.index(ev["id"])]
        self.play(metades[0].animate.rotate(.35).shift(pos(-.1, -.35)).set_opacity(0),
                  metades[1].animate.rotate(-.4).shift(pos(.15, -.4)).set_opacity(0),
                  *(FadeOut(m) for m in gm.itens() if m is not alvo),
                  Indicate(vaga, color=CORAL, scale_factor=2.2, rate_func=there_and_back), run_time=.8)
        self.remove(metades)
        self.play(FadeOut(fundo), FadeOut(marca), run_time=.3)
