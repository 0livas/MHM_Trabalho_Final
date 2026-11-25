"""Captura uma execução real do SPEA2 na instância didática, sem alterar o algoritmo."""

import argparse
import copy
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]

import numpy as np  # noqa: E402
import pymoo  # noqa: E402
from pymoo.operators.selection.tournament import TournamentSelection  # noqa: E402
from pymoo.util.dominator import Dominator  # noqa: E402
from pymoo.util.misc import vectorized_cdist  # noqa: E402

from problem import read_instance  # noqa: E402
from schedule import ScheduleValidationError, evaluate_schedule  # noqa: E402
from metaheuristics import spea2  # noqa: E402

ENTRADA = HERE / "data" / "didatica.dat"
SAIDA = HERE / "data" / "trace_spea2.json"
SEED = 20525
DEMO = dict(population_size=12, crossover_probability=.7, mutation_probability=.5)
AVALIACOES = 1012
OPERADORES = ("modo", "espera", "insercao", "troca", "realocacao")
# Eventos escolhidos para mostrar; a busca é registrada inteira em "rodadas".
EVENTOS = dict(insercao=55, realocacao=78, troca=200, modo=240, espera=487, inviavel=502, truncamento=676)


def nativo(schedule):
    return [[list(item) for item in sequence] for sequence in schedule]


def empacotar(instance, schedule):
    """Blocos de um plano, completo ou parcial, com a regra início = fim anterior + setup + espera."""
    blocks = []
    for machine, sequence in enumerate(schedule):
        previous, end = None, 0
        for job, mode, wait in sequence:
            setup = 0 if previous is None else instance.setup[machine][previous][job]
            start = end + setup + wait
            end = start + instance.duration(job, machine, mode)
            blocks.append(dict(job=job, machine=machine, mode=mode, setup=setup, wait=wait, start=start, end=end))
            previous = job
    return blocks


def montar(instance, schedule):
    """Plano reavaliado por evaluate_schedule; inviável tem Cmax e TEC nulos."""
    blocks = empacotar(instance, schedule)
    try:
        result = evaluate_schedule(instance, schedule)
    except ScheduleValidationError as error:
        return dict(cmax=None, tec=None, erro=str(error), blocks=blocks)
    operations = {op.job: op for op in result.operations}
    assert all((operations[b["job"]].start, operations[b["job"]].end) == (b["start"], b["end"]) for b in blocks)
    return dict(cmax=result.cmax, tec=result.tec, blocks=blocks)


def operacao(antes, depois):
    """Operador deduzido pela diferença; None quando nada mudou, 'ambigua' quando dois explicam."""
    if antes == depois:
        return None, []
    local = {job: (m, p, mode, wait) for m, s in enumerate(antes) for p, (job, mode, wait) in enumerate(s)}
    novo = {job: (m, p, mode, wait) for m, s in enumerate(depois) for p, (job, mode, wait) in enumerate(s)}
    modos = [j for j in local if local[j][2] != novo[j][2]]
    esperas = [j for j in local if local[j][3] != novo[j][3]]
    if modos or esperas:
        assert len(modos) + len(esperas) == 1
        return ("modo", modos) if modos else ("espera", esperas)
    mudaram = [j for j in local if local[j][0] != novo[j][0]]
    if len(mudaram) == 1:
        return "realocacao", mudaram
    if len(mudaram) == 2:
        return "troca", mudaram
    assert not mudaram
    machine = next(m for m in range(len(antes)) if antes[m] != depois[m])
    a, b = list(antes[machine]), list(depois[machine])
    trocas = [(i, j) for i in range(len(a)) for j in range(i + 1, len(a))
              if [*a[:i], a[j], *a[i + 1:j], a[i], *a[j + 1:]] == b]
    insercoes = []
    for i in range(len(a)):
        resto = a[:i] + a[i + 1:]
        insercoes += [i for t in range(len(a)) if t != i and resto[:t] + [a[i]] + resto[t:] == b]
    if trocas and insercoes:
        return "ambigua", [a[i][0] for i in trocas[0]]
    if trocas:
        return "troca", [a[i][0] for i in trocas[0]]
    assert insercoes
    return "insercao", [a[insercoes[0]][0]]


class Captura:
    def __init__(self):
        self.individuos, self.ids = [], {}
        self.cruzamento = self.mutacao = self.duelos = None
        self.rodadas, self.construcoes = [], []
        self.atual = None

    def ident(self, individual):
        if id(individual) not in self.ids:
            self.ids[id(individual)] = len(self.individuos)
            self.individuos.append(individual)
        return self.ids[id(individual)]


def executar(instance, seed, avaliacoes=AVALIACOES, instrumentar=True):
    config = spea2.SPEA2Config(seed=seed, max_evaluations=avaliacoes, **DEMO)
    if not instrumentar:
        return spea2.run_spea2(instance, config), None
    cap = Captura()
    originais = {name: getattr(spea2, name) for name in
                 ("ScheduleCrossover", "ScheduleMutation", "SPEA2Survival", "SPEA2", "_random_schedule")}

    def construir(instance, rng):
        estado = copy.deepcopy(rng.bit_generator.state)
        out = originais["_random_schedule"](instance, rng)
        cap.construcoes.append((estado, out))
        return out

    class Cruzamento(originais["ScheduleCrossover"]):
        def _do(self, problem, x, random_state=None, **kwargs):
            # Cópia do estado: ler não consome números aleatórios.
            estado = copy.deepcopy(random_state.bit_generator.state)
            out = super()._do(problem, x, random_state=random_state, **kwargs)
            cap.cruzamento = dict(estado=estado, pais=[spea2._as_schedule(x[p, 0, 0]) for p in range(2)],
                                  filho=spea2._as_schedule(out[0, 0, 0]))
            return out

    class Mutacao(originais["ScheduleMutation"]):
        def do(self, problem, pop, *args, **kwargs):
            antes = spea2._as_schedule(pop[0].X[0])
            out = super().do(problem, pop, *args, **kwargs)
            cap.mutacao = dict(antes=antes, depois=spea2._as_schedule(out[0].X[0]))
            return out

    class Sobrevivencia(originais["SPEA2Survival"]):
        def _do(self, problem, pop, *args, **kwargs):
            out = super()._do(problem, pop, *args, **kwargs)
            F = pop.get("F").astype(float)
            M = Dominator().calc_domination_matrix(F)
            S = (M == 1).sum(axis=1)
            assert (((M == -1) * S).sum(axis=1) == pop.get("SPEA_R")).all()
            cap.atual = dict(ids=[cap.ident(i) for i in pop], S=S.tolist(), R=[int(v) for v in pop.get("SPEA_R")],
                             D=pop.get("SPEA_D").tolist(), F=pop.get("SPEA_F").tolist(),
                             k=min(int(np.sqrt(len(pop))), len(pop) - 1),
                             dominados={cap.ident(pop[i]): [cap.ident(pop[j]) for j in np.where(M[i] == 1)[0]]
                                        for i in range(len(pop))},
                             frente=[cap.ident(pop[i]) for i in np.where(np.all(M >= 0, axis=1))[0]],
                             dists=vectorized_cdist(F, F, fill_diag_with_inf=True))
            return out

        def do(self, problem, pop, *args, **kwargs):
            entrada = [cap.ident(i) for i in pop]
            out = super().do(problem, pop, *args, **kwargs)
            saida = [cap.ident(i) for i in out]
            row = dict(avaliacao=len(entrada) if not cap.rodadas else cap.rodadas[-1]["avaliacao"] + 1,
                       entrada=entrada, saida=saida, sobrevivencia=cap.atual,
                       cruzamento=cap.cruzamento, mutacao=cap.mutacao, duelos=cap.duelos)
            cap.rodadas.append(row)
            cap.cruzamento = cap.mutacao = cap.duelos = None
            return out

    def selecao(pop, P, algorithm, **kwargs):
        from pymoo.algorithms.moo.spea2 import spea_binary_tournament
        S = spea_binary_tournament(pop, P, algorithm, **kwargs)
        cap.duelos = [dict(a=cap.ident(pop[a]), b=cap.ident(pop[b]), vence=cap.ident(pop[v]),
                           Fa=float(pop[a].get("SPEA_F")), Fb=float(pop[b].get("SPEA_F")))
                      for (a, b), (v,) in zip(P, S)]
        return S

    class Algoritmo(originais["SPEA2"]):
        def __init__(self, **kwargs):
            super().__init__(selection=TournamentSelection(selecao), **kwargs)

    try:
        spea2.ScheduleCrossover, spea2.ScheduleMutation = Cruzamento, Mutacao
        spea2.SPEA2Survival, spea2.SPEA2 = Sobrevivencia, Algoritmo
        spea2._random_schedule = construir
        result = spea2.run_spea2(instance, config)
    finally:
        for name, value in originais.items():
            setattr(spea2, name, value)
    return result, cap


def igual(a, b):
    limpar = lambda r: {k: v for k, v in r.to_result_dict().items() if k != "elapsed_seconds"}  # noqa: E731
    return limpar(a) == limpar(b)


def ponto(individual):
    return None if individual.G[0] > 0 else [int(individual.F[0]), float(individual.F[1])]


def resumo_sobrevivencia(cap, row):
    """Uma linha por solução da disputa, com os números do pymoo."""
    s = row["sobrevivencia"]
    dists, linhas = s["dists"], []
    for i, ident in enumerate(s["ids"]):
        ordem = sorted((float(d), s["ids"][j]) for j, d in enumerate(dists[i]) if j != i)
        linhas.append(dict(id=ident, ponto=ponto(cap.individuos[ident]), S=s["S"][i], R=s["R"][i], D=s["D"][i],
                           F=s["F"][i], sigma=ordem[s["k"]][0], vizinho=ordem[s["k"]][1],
                           dominados=s["dominados"][ident], distancias=[d for d, _ in ordem],
                           vizinhos=[v for _, v in ordem]))
        assert abs(1 / (linhas[-1]["sigma"] + 2) - s["D"][i]) < 1e-12
    removido = [i for i in row["entrada"] if i not in row["saida"]]
    return dict(avaliacao=row["avaliacao"], k=s["k"], frente=s["frente"], linhas=linhas,
                removido=removido[0] if removido else None)


def refazer_cruzamento(instance, dados):
    """Fora da execução, repete os sorteios a partir do estado salvo e confere o filho."""
    rng = np.random.default_rng(0)
    rng.bit_generator.state = dados["estado"]
    posicao = [{job: p for s in pai for p, (job, _, _) in enumerate(s)} for pai in dados["pais"]]
    genes = [{job: (m, mode, wait) for m, s in enumerate(pai) for job, mode, wait in s} for pai in dados["pais"]]
    filho, sorteios, passos = [[] for _ in range(instance.m)], [], []
    for job in range(instance.n):
        origem = int(rng.integers(2))
        ruido = float(rng.random()) * .5
        machine, mode, wait = genes[origem][job]
        filho[machine].append((job, mode, wait))
        sorteios.append(dict(job=job, origem=origem, posicoes=[p[job] for p in posicao], ruido=ruido,
                             soma=float(posicao[0][job]) + float(posicao[1][job]) + ruido,
                             igual=genes[0][job] == genes[1][job]))
        passos.append(empacotar(instance, filho))
    chegada = montar(instance, tuple(tuple(s) for s in filho))
    for sequence in filho:
        sequence.sort(key=lambda item: sorteios[item[0]]["soma"])
    assert tuple(tuple(s) for s in filho) == dados["filho"]
    return dict(sorteios=sorteios, passos=passos, chegada=chegada)


def refazer_lpt(instance, estado, esperado):
    """Fora da execução, repete o LPT aleatório do projeto passo a passo a partir do estado salvo."""
    rng = np.random.default_rng(0)
    rng.bit_generator.state = estado
    menor = {j: min(instance.duration(j, m, k) for m in range(instance.m) for k in range(instance.modes))
             for j in range(instance.n)}
    fila = sorted(menor, key=lambda j: (-menor[j], j))
    plano, fim, passos = [[] for _ in range(instance.m)], [0] * instance.m, []
    while fila:
        janela = int(np.ceil(np.sqrt(len(fila))))
        antes = list(fila)
        job = fila.pop(int(rng.integers(janela)))
        opcoes = []
        for m in range(instance.m):
            setup = instance.setup[m][plano[m][-1][0]][job] if plano[m] else 0
            opcoes += [(fim[m] + setup + instance.duration(job, m, k), m, k) for k in range(instance.modes)
                       if fim[m] + setup + instance.duration(job, m, k) <= instance.horizon]
        empate = [o for o in opcoes if o[0] == min(opcoes)[0]]
        end, m, k = empate[int(rng.integers(len(empate)))]
        plano[m].append((job, k, 0))
        fim[m] = end
        passos.append(dict(fila=antes, janela=janela, job=job, machine=m, mode=k, end=end))
    assert tuple(tuple(x) for x in plano) == esperado
    return dict(menor_duracao=[menor[j] for j in range(instance.n)], passos=passos)


def mutacoes(instance, cap):
    """Mutações efetivas, uma por rodada; 'antes' é cópia de um pai quando não houve cruzamento."""
    out = []
    for row in cap.rodadas[1:]:
        m = row["mutacao"]
        op, jobs = operacao(m["antes"], m["depois"])
        if op is None:
            continue
        filho = row["entrada"][-1]
        pais = [d["vence"] for d in row["duelos"]]
        out.append(dict(avaliacao=row["avaliacao"], op=op, jobs=jobs, cruzou=row["cruzamento"] is not None,
                        pai=next((p for p in pais if spea2._as_schedule(cap.individuos[p].X[0]) == m["antes"]), None),
                        antes=m["antes"], depois=m["depois"], filho=filho, sobreviveu=filho in row["saida"],
                        frente=filho in row["sobrevivencia"]["frente"]))
    return out


def calcular():
    instance = read_instance(ENTRADA)
    result, cap = executar(instance, SEED)
    normal, _ = executar(instance, SEED, instrumentar=False)
    assert igual(result, normal), "A instrumentação alterou a execução."
    planos = [montar(instance, spea2._as_schedule(i.X[0])) for i in cap.individuos]
    for p, i in zip(planos, cap.individuos):
        assert ponto(i) == (None if p["cmax"] is None else [p["cmax"], p["tec"]])
    inicio, primeira = cap.rodadas[0], cap.rodadas[1]
    cruz = primeira["cruzamento"]
    assert cruz and primeira["mutacao"]["antes"] == primeira["mutacao"]["depois"]
    assert [spea2._as_schedule(cap.individuos[d["vence"]].X[0]) for d in primeira["duelos"]] == cruz["pais"]
    assert [c[1] for c in cap.construcoes] == [spea2._as_schedule(i.X[0]) for i in cap.individuos[:len(inicio["entrada"])]]
    todas = mutacoes(instance, cap)
    escolhidas = {}
    for nome in sorted((*OPERADORES, "inviavel"), key=EVENTOS.get):
        m = next(m for m in todas if m["avaliacao"] == EVENTOS[nome])
        assert not m["cruzou"] and m["pai"] is not None
        assert nome == "inviavel" or m["op"] == nome
        escolhidas[nome] = {k: v for k, v in m.items() if k not in ("antes", "depois")} | dict(
            antes=montar(instance, m["antes"]), depois=montar(instance, m["depois"]))
    trunc = next(r for r in cap.rodadas if r["avaliacao"] == EVENTOS["truncamento"])
    t = resumo_sobrevivencia(cap, trunc)
    assert len(t["frente"]) == len(t["linhas"]) == DEMO["population_size"] + 1
    contagem = {}
    for m in todas:
        contagem[m["op"]] = contagem.get(m["op"], 0) + 1
    mostrados = {l["id"] for l in t["linhas"]} | set(inicio["entrada"]) | {primeira["entrada"][-1]}
    return dict(
        seed=SEED, demonstracao=DEMO | dict(max_evaluations=AVALIACOES, n_offsprings=1, normalize=False),
        campanha=dict(population_size=200, crossover_probability=.7, mutation_probability=.5, max_evaluations=10_000),
        versoes=dict(python=platform.python_version(), pymoo=pymoo.__version__, numpy=np.__version__),
        instancia_sha256=instance.digest, horizonte=instance.horizon, execucao_igual_a_normal=True,
        contagem=dict(avaliacoes=result.attempts, viaveis=result.feasible_evaluations,
                      inviaveis=result.rejected_evaluations, mutacoes=contagem,
                      duplicatas_na_populacao_final=DEMO["population_size"] - len(
                          {tuple(ponto(cap.individuos[i])) for i in cap.rodadas[-1]["saida"]})),
        planos={str(i): planos[i] for i in sorted(mostrados)},
        inicial=resumo_sobrevivencia(cap, inicio) | dict(ids=inicio["entrada"]),
        lpt=dict(id=3, **refazer_lpt(instance, *cap.construcoes[3])),
        primeira=resumo_sobrevivencia(cap, primeira) | dict(filho=primeira["entrada"][-1], duelos=primeira["duelos"]),
        cruzamento=dict(pais=[montar(instance, p) for p in cruz["pais"]], filho=montar(instance, cruz["filho"]),
                        **refazer_cruzamento(instance, cruz)),
        mutacoes=escolhidas, truncamento=t | dict(filho=trunc["entrada"][-1]),
        rodadas=[dict(avaliacao=r["avaliacao"], ponto=ponto(cap.individuos[r["entrada"][-1]]), filho=r["entrada"][-1],
                      removido=[i for i in r["entrada"] if i not in r["saida"]][0],
                      nao_dominados=len(r["sobrevivencia"]["frente"]))
                 for r in cap.rodadas[1:]],
        final=cap.rodadas[-1]["saida"],
        frente=[montar(instance, s.schedule) for s in sorted(result.front, key=lambda s: s.key)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Recalcula e confere o JSON salvo.")
    args = parser.parse_args()
    data = json.loads(json.dumps(calcular()))
    if args.check:
        if json.loads(SAIDA.read_text(encoding="utf-8")) != data:
            raise SystemExit("trace_spea2.json diverge da execução.")
        print("ok")
    else:
        SAIDA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(data["contagem"], [(p["cmax"], p["tec"]) for p in data["frente"]])


if __name__ == "__main__":
    main()
