"""Executa o AGE-MOEA do projeto e grava os eventos reais usados pela animação."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import platform
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]

import numba  # noqa: E402
import pymoo  # noqa: E402
import pymoo.algorithms.moo.age as pymoo_age  # noqa: E402

from problem import read_instance  # noqa: E402
from schedule import ScheduleValidationError, evaluate_schedule  # noqa: E402
from metaheuristics import age, spea2  # noqa: E402

ENTRADA = HERE / "data" / "didatica.dat"
SAIDA = HERE / "data" / "trace_age.json"
PARAMETROS = dict(seed=1235, population_size=16, crossover_probability=.9, mutation_probability=.7,
                  max_evaluations=329)
OPERADORES = ("modo", "espera", "insercao", "troca", "realocacao")

SurvivalOriginal = pymoo_age.AGEMOEASurvival


class Registro:
    def __init__(self):
        self.ids, self.objetos, self.filhos, self.geracoes, self.lote = {}, [], {}, [], None

    def id(self, individual):
        key = id(individual)
        if key not in self.ids:
            self.ids[key] = len(self.objetos)
            self.objetos.append(individual)      # mantém vivo: id() não é reaproveitado
        return self.ids[key]


def capturar(instance, parametros):
    """Executa run_age com subclasses que chamam super() e só copiam o que observam."""
    reg = Registro()

    class Survival(SurvivalOriginal):
        def do(self, problem, pop, *args, **kwargs):
            reg.atual = dict(arena=[reg.id(i) for i in pop],
                             inviaveis=[reg.id(i) for i in pop if not i.FEAS[0]])
            survivors = super().do(problem, pop, *args, **kwargs)
            reg.atual["sobreviventes"] = [reg.id(i) for i in survivors]
            reg.geracoes.append(reg.atual)
            return survivors

        def _do(self, problem, pop, *args, n_survive=None, **kwargs):
            result = super()._do(problem, pop, *args, n_survive=n_survive, **kwargs)
            posto = pop.get("rank")
            limite = np.iinfo(int).max
            reg.atual.update(
                vagas=int(n_survive), viaveis=[reg.id(i) for i in pop],
                F=np.array(pop.get("F"), dtype=float).copy().tolist(),
                posto=[None if r == limite else int(r) for r in posto],
                escore=[None if np.isinf(c) else float(c) for c in pop.get("crowding")])
            return result

        def survival_score(self, front, ideal_point):
            copia, ideal = front.copy(), ideal_point.copy()
            result = super().survival_score(front, ideal_point)
            reg.atual["geometria"] = geometria(copia, ideal, *result)
            return result

    class Crossover(age.ScheduleCrossover):
        def do(self, problem, pop, parents=None, *args, random_state=None, **kwargs):
            pares = [pop[m] for m in parents] if parents is not None else pop
            reg.lote = [dict(pais=[reg.id(p) for p in par]) for par in pares]
            espelho = deepcopy(random_state)
            mask = espelho.random(len(pares)) < self.prob.get()
            off = super().do(problem, pop, parents, *args, random_state=random_state, **kwargs)
            for item, cruzou, filho in zip(reg.lote, mask, off):
                item.update(cruzou=bool(cruzou), antes=spea2._as_schedule(filho.X[0]))
                reg.filhos[reg.id(filho)] = item
            return off

    class Mutation(age.ScheduleMutation):
        def _do(self, problem, x, random_state=None, **kwargs):
            partes = []
            for index in range(len(x)):
                original = spea2._as_schedule(x[index][0])
                espelho = deepcopy(random_state)
                partes.append(super()._do(problem, x[index:index + 1], random_state=random_state, **kwargs))
                # O lote pode estar sendo mutado logo após o cruzamento que o criou.
                reg.lote[index]["op"] = OPERADORES[int(espelho.integers(5))]
                reg.lote[index]["job"] = alvo(reg.lote[index]["op"], original, espelho)
                reg.lote[index]["candidato"] = spea2._as_schedule(partes[-1][0, 0])
            mask = deepcopy(random_state).random(len(x)) <= self.prob.get()
            for item, mudou in zip(reg.lote, mask):
                item["mutou"] = bool(mudou)
            return np.concatenate(partes)

    trocas = [(pymoo_age, "AGEMOEASurvival", Survival), (age, "ScheduleCrossover", Crossover),
              (age, "ScheduleMutation", Mutation)]
    antigos = [getattr(m, n) for m, n, _ in trocas]
    try:
        for modulo, nome, novo in trocas:
            setattr(modulo, nome, novo)
        resultado = age.run_age(instance, age.AGEConfig(**parametros))
    finally:
        for (modulo, nome, _), antigo in zip(trocas, antigos):
            setattr(modulo, nome, antigo)
    for ident, item in reg.filhos.items():
        esperado = item["candidato"] if item["mutou"] else item["antes"]
        assert spea2._as_schedule(reg.objetos[ident].X[0]) == esperado, "registro diverge do filho avaliado"
    return resultado, reg


def alvo(op, original, rng):
    """Repete o sorteio do operador num gerador espelho para saber qual tarefa ele moveu."""
    posicoes = [(m, p) for m, seq in enumerate(original) for p in range(len(seq))]
    if op == "insercao":
        movel = [(m, a, b) for m, seq in enumerate(original) for a in range(len(seq))
                 for b in range(len(seq)) if a != b]
        m, a, _ = movel[int(rng.integers(len(movel)))]
        return [original[m][a][0]]
    if op == "troca":
        return [original[posicoes[int(k)][0]][posicoes[int(k)][1]][0]
                for k in rng.choice(len(posicoes), size=2, replace=False)]
    m, p = posicoes[int(rng.integers(len(posicoes)))]
    return [original[m][p][0]]


def geometria(front, ideal, escore, p, normalizacao):
    """Refaz survival_score passo a passo e exige o mesmo resultado do pymoo."""
    m, n = front.shape
    if m < n:
        return dict(m=m, p=float(p), degenerada=True)
    bruto = np.round(front, 12) - ideal
    extremos = pymoo_age.find_corner_solutions(bruto)
    unit, norma = pymoo_age.normalize(bruto, extremos)
    assert np.array_equal(norma, normalizacao)
    conferido = SurvivalOriginal.compute_geometry(unit, extremos, n)
    assert conferido == p
    d = pymoo_age.point_2_line_distance(unit, np.zeros(n), np.ones(n))
    d[extremos] = np.inf
    ref = int(np.argmin(d))
    media = float(np.mean(unit[ref]))
    with np.errstate(divide="ignore", invalid="ignore"):
        cru = float(np.log(n) / np.log(1 / media)) if media not in (0., 1.) else None
    nn = np.linalg.norm(unit, p, axis=1)
    nn[nn < 1e-8] = 1
    dist = SurvivalOriginal.pairwise_distances(unit, p)
    dist[dist < 1e-8] = 1e-8
    dist = dist / nn[:, None]              # linha = ponto já selecionado
    dentro = [int(e) for e in extremos]
    marca = np.zeros(m, dtype=bool)
    marca[extremos] = True
    resto, entradas = [i for i in range(m) if not marca[i]], []
    while resto:
        sel = np.flatnonzero(marca)
        notas = []
        for i in resto:
            col = dist[sel, i]
            k = sel[np.argsort(col, kind="stable")[:2]]
            notas.append((float(np.sum(np.sort(col)[:2])), [int(v) for v in k]))
        melhor = int(np.argmax([v for v, _ in notas]))
        i = resto[melhor]
        assert np.isclose(notas[melhor][0], escore[i], rtol=1e-12, atol=1e-15)
        entradas.append(dict(i=i, escore=float(escore[i]), vizinhos=notas[melhor][1],
                             notas=[[j, float(v), k] for j, (v, k) in zip(resto, notas)]))
        resto.pop(melhor)
        marca[i] = True
    assert all(np.isinf(escore[e]) for e in dentro)
    return dict(m=m, degenerada=False, ideal=ideal.tolist(), extremos=dentro, norma=norma.tolist(),
                F=front.tolist(), unit=unit.tolist(), ref=ref, media=media, p_cru=cru, p=float(p),
                p_ajustado=bool(cru is None or cru != float(p)), entradas=entradas)


def plano(instance, schedule):
    """Mesmo formato de cenario.plano, a partir da representação nativa; aceita inviável."""
    try:
        ev = evaluate_schedule(instance, schedule)
    except ScheduleValidationError as erro:
        ev, motivo = None, str(erro)
    blocks = []
    ends = {op.job: op for op in ev.operations} if ev else {}
    for machine, sequence in enumerate(schedule):
        previous, end = None, 0
        for job, mode, wait in sequence:
            setup = 0 if previous is None else instance.setup[machine][previous][job]
            start = end + setup + wait
            end = start + instance.duration(job, machine, mode)
            assert not ev or (ends[job].start, ends[job].end) == (start, end)
            blocks.append(dict(job=job, machine=machine, mode=mode, setup=setup, wait=wait, start=start, end=end))
            previous = job
    result = dict(blocks=blocks, representacao=[[list(t) for t in seq] for seq in schedule])
    if ev:
        return result | dict(viavel=True, cmax=ev.cmax, tec=ev.tec)
    return result | dict(viavel=False, motivo=motivo, termino=max(b["end"] for b in blocks),
                         horizonte=instance.horizon)


def evento(instance, reg, ident):
    item = reg.filhos[ident]
    return dict(id=ident, pais=item["pais"], planos_pais=[plano(instance, spea2._as_schedule(reg.objetos[p].X[0]))
                                                          for p in item["pais"]],
                cruzou=item["cruzou"], mutou=item["mutou"], op=item["op"], jobs=item["job"],
                antes=plano(instance, item["antes"]), depois=plano(instance, item["candidato"]))


def calcular(parametros=PARAMETROS):
    instance = read_instance(ENTRADA)
    resultado, reg = capturar(instance, parametros)
    normal = age.run_age(instance, age.AGEConfig(**parametros))
    a, b = resultado.to_result_dict(), normal.to_result_dict()
    a.pop("elapsed_seconds"), b.pop("elapsed_seconds")
    assert a == b, "execução instrumentada diverge da normal"
    return montar(instance, parametros, resultado, reg, ESCOLHA)


# Gerações mostradas em detalhe; só índices, nenhum resultado é digitado aqui.
ESCOLHA = dict(geracao=3, outra=20)


def fontes(item, reg):
    """De qual pai (0 ou 1) vieram máquina, modo e espera de cada tarefa; empate fica com o primeiro."""
    onde = [{job: (m, mode, wait) for m, seq in enumerate(spea2._as_schedule(reg.objetos[p].X[0]))
             for job, mode, wait in seq} for p in item["pais"]]
    result = {}
    for m, seq in enumerate(item["antes"]):
        for job, mode, wait in seq:
            opcoes = [k for k in (0, 1) if onde[k][job] == (m, mode, wait)]
            assert opcoes
            result[str(job)] = opcoes[0]
    return result


def montar(instance, parametros, resultado, reg, escolha):
    P, G = parametros["population_size"], escolha["geracao"]
    lote = reg.geracoes[G]["arena"][P:]
    eventos = {}
    for op in ("espera", "insercao"):
        opcoes = []
        for ident in lote:
            item = reg.filhos[ident]
            if not (item["mutou"] and item["op"] == op):
                continue
            antes, depois = plano(instance, item["antes"]), plano(instance, item["candidato"])
            if antes["viavel"] and depois["viavel"] and depois["cmax"] <= antes["cmax"]:
                opcoes.append((antes["tec"] - depois["tec"], ident))
        ganho, ident = max(opcoes)
        assert ganho > 0
        eventos[op] = evento(instance, reg, ident) | dict(fontes=fontes(reg.filhos[ident], reg))
    ruins = []
    for g, ger in enumerate(reg.geracoes):
        for ident in ger["inviaveis"]:
            item = reg.filhos[ident]
            if item["mutou"] and plano(instance, item["antes"])["viavel"]:
                ruins.append((plano(instance, item["candidato"])["termino"], ident, g))
    _, ident, g = max(ruins)
    eventos["inviavel"] = evento(instance, reg, ident) | dict(geracao=g)
    assert ident not in reg.geracoes[g]["sobreviventes"]

    geracoes, total = [], 0
    for g, ger in enumerate(reg.geracoes):
        tamanho = resultado.evaluation_batches[g]
        total += tamanho
        geo = dict(ger["geometria"])
        if g != G:
            geo.pop("entradas", None)
        if not geo["degenerada"]:
            geo["c_ref"] = float(sum(v ** geo["p"] for v in geo["unit"][geo["ref"]]))
        ranqueados = [r for r in ger["posto"] if r is not None]
        ultimo = max(ranqueados)
        escores_corte = [e for e, r in zip(ger["escore"], ger["posto"]) if r == ultimo]
        geracoes.append(dict(
            g=g, lote=tamanho, avaliacoes=total, arena=ger["arena"], inviaveis=ger["inviaveis"],
            viaveis=ger["viaveis"], F=ger["F"], posto=ger["posto"], escore=ger["escore"],
            sobreviventes=ger["sobreviventes"], vagas=ger["vagas"],
            camadas=[ranqueados.count(r) for r in range(ultimo + 1)], sem_posto=ger["posto"].count(None),
            corte=dict(camada=ultimo, todos_zero=all(e == 0 for e in escores_corte)), geometria=geo))
        assert set(ger["sobreviventes"]) <= set(ger["viaveis"])
    frente = [plano(instance, s.schedule) for s in resultado.front]
    f = np.array([[p["cmax"], p["tec"]] for p in frente])
    unit = (f - f.min(0)) / np.ptp(f, axis=0)
    # Compromisso exibido: ponto interno da frente mais próximo da diagonal, o mesmo critério da curvatura.
    d = np.abs(unit[:, 0] - unit[:, 1])
    d[[0, -1]] = np.inf
    return dict(
        descricao="Demonstração do AGE-MOEA na instância didática; seed escolhida por conter eventos didáticos.",
        parametros=parametros, instancia_sha256=instance.digest,
        versoes=dict(python=platform.python_version(), numpy=np.__version__, pymoo=pymoo.__version__,
                     numba=numba.__version__),
        campanha=dict(population_size=100, crossover_probability=.9, mutation_probability=.7,
                      max_evaluations=10000, fonte="documentacao/main.tex, calibração e campanha final"),
        evaluation_batches=list(resultado.evaluation_batches), avaliacoes=resultado.attempts,
        viaveis=resultado.feasible_evaluations, inviaveis=resultado.rejected_evaluations,
        escolha=escolha, eventos=eventos, geracoes=geracoes, frente=frente, compromisso=int(np.argmin(d)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Confere o JSON salvo sem regravar.")
    args = parser.parse_args()
    data = json.loads(json.dumps(calcular()))
    if args.check:
        if json.loads(SAIDA.read_text(encoding="utf-8")) != data:
            raise SystemExit("trace_age.json diverge da execução.")
        print("trace_age.json confere; execução instrumentada idêntica à normal.")
    else:
        SAIDA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
