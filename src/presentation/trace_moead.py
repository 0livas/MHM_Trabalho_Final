"""Captura uma execução pequena e real do MOEA/D na instância didática."""

import argparse
import copy
from fractions import Fraction
import json
from pathlib import Path
import platform
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]

import pymoo  # noqa: E402
from pymoo.algorithms.moo import moead as pymoo_moead  # noqa: E402
from problem import read_instance  # noqa: E402
from schedule import ScheduleValidationError, evaluate_schedule  # noqa: E402
from metaheuristics import moead  # noqa: E402

SAIDA = HERE / "data" / "trace_moead.json"
MANIFESTO = HERE.parents[1] / "data" / "output" / "experiments" / "experiment_manifest.json"
OPERACOES = ("modo", "espera", "insercao", "troca", "realocacao")
MEDIDA_PESOS, MEDIDA_FEIXES = (7, 4), (14, 6)
# Eventos exibidos: três pulos (o último é a cascata), substituição parcial e rejeição.
DESTAQUES = dict(fuga=8, cinza=9, cascata=10, parcial=11, rejeicao=80)
CONFIG = moead.MOEADConfig(seed=320, max_evaluations=615, population_size=15, n_neighbors=5,
                           prob_neighbor_mating=.9, crossover_probability=.9, mutation_probability=.7)


class Gravador:
    """Repassa as chamadas ao gerador original e anota o que ele devolveu."""

    def __init__(self, rng):
        self.rng, self.calls = rng, []

    def __getattr__(self, name):
        original = getattr(self.rng, name)
        if not callable(original):
            return original

        def chamada(*args, **kwargs):
            value = original(*args, **kwargs)
            self.calls.append((name, value))
            return value
        return chamada


def lista(schedule):
    return [[[int(v) for v in item] for item in seq] for seq in schedule]


def montar(instance, schedule):
    """Blocos para o Gantt. Planos viáveis são conferidos por evaluate_schedule."""
    blocks = []
    for machine, sequence in enumerate(schedule):
        previous, end = None, 0
        for job, mode, wait in sequence:
            setup = 0 if previous is None else instance.setup[machine][previous][job]
            start = end + setup + wait
            end = start + instance.duration(job, machine, mode)
            power = instance.power[machine] * instance.power_factor[mode] * 24 / instance.slots_per_day
            custos = [float(power * (instance.peak_rate if any(a <= t < b for a, b in instance.peaks)
                                     else instance.off_rate)) for t in range(start, end)]
            blocks.append(dict(job=job, machine=machine, mode=mode, setup=setup, wait=wait,
                               start=start, end=end, costs=custos))
            previous = job
    row = dict(schedule=lista(schedule), blocks=blocks)
    try:
        result = evaluate_schedule(instance, schedule)
    except ScheduleValidationError as error:
        return row | dict(viavel=False, cmax=max(b["end"] for b in blocks), tec=None, erro=str(error))
    fim = {op.job: (op.machine, op.start, op.end, op.mode) for op in result.operations}
    assert all(fim[b["job"]] == (b["machine"], b["start"], b["end"], b["mode"]) for b in blocks)
    assert abs(sum(sum(b["costs"]) for b in blocks) - result.tec) < 1e-9
    return row | dict(viavel=True, cmax=result.cmax, tec=result.tec)


def capturar(instance, config):
    """Executa run_moead com subclasses que só observam; devolve resultado, eventos e população."""
    log = dict(eventos=[], inicial=None, direcoes=None, vizinhos=None, ideal0=None)
    atual = {}

    class Vizinhanca(pymoo_moead.NeighborhoodSelection):
        def _do(self, problem, pop, n_select, n_parents, neighbors=None, random_state=None, **kwargs):
            rng = Gravador(random_state)
            parents = super()._do(problem, pop, n_select, n_parents, neighbors=neighbors, random_state=rng, **kwargs)
            atual.clear()
            atual.update(sorteio=float(rng.calls[0][1]), local=rng.calls[1][0] == "choice",
                         pais=[int(v) for v in parents[0]],
                         planos_pais=[lista(pop[int(v)].X[0]) for v in parents[0]])
            return parents

    class Cruzamento(moead.ScheduleCrossover):
        def do(self, problem, pop, parents=None, *args, random_state=None, **kwargs):
            rng = Gravador(random_state)
            off = super().do(problem, pop, parents, *args, random_state=rng, **kwargs)
            atual.update(cruzou=bool(rng.calls[0][1][0] < config.crossover_probability),
                         cruzado=lista(off[0].X[0]))
            # As origens são os sorteios de um único pai entre dois, na ordem das tarefas.
            atual["origem"] = [int(v) for n, v in rng.calls if n == "integers"] if atual["cruzou"] else None
            return off

    class Mutacao(moead.ScheduleMutation):
        def do(self, problem, pop, inplace=True, *args, random_state=None, **kwargs):
            antes = lista(pop[0].X[0])
            rng = Gravador(random_state)
            off = super().do(problem, pop, inplace, *args, random_state=rng, **kwargs)
            sorteio = next(v for n, v in rng.calls if n == "integers")
            moeda = float(rng.calls[-1][1][0])
            atual.update(mutou=moeda <= config.mutation_probability, operacao=OPERACOES[int(sorteio)],
                         filho=lista(off[0].X[0]))
            atual["mudou"] = atual["filho"] != antes
            return off

    class Avaliador(moead.FeasibleEvaluator):
        def _eval(self, problem, pop, evaluate_values_of, **kwargs):
            original, rejeitadas = self.fallback, problem.trace.rejected
            if original is not None:
                def observada():
                    # Prevê o índice numa cópia do gerador, sem consumir o original.
                    algorithm = original.__closure__[0].cell_contents
                    atual["copia_de"] = int(copy.deepcopy(algorithm.random_state).integers(len(algorithm.pop)))
                    escolhido = original()
                    assert escolhido is algorithm.pop[atual["copia_de"]]
                    return escolhido
                self.fallback = observada
            try:
                super()._eval(problem, pop, evaluate_values_of, **kwargs)
            finally:
                self.fallback = original
            atual["rejeitado"] = problem.trace.rejected > rejeitadas
            atual["avaliacao"] = problem.trace.attempts

    class Algoritmo(pymoo_moead.MOEAD):
        def _initialize_advance(self, infills=None, **kwargs):
            super()._initialize_advance(infills=infills, **kwargs)
            log.update(inicial=[lista(i.X[0]) for i in self.pop], direcoes=self.ref_dirs.tolist(),
                       vizinhos=self.neighbors.tolist(), ideal0=self.ideal.tolist())
            self.anterior = self.ideal.copy()

        def _replace(self, k, off):
            viz, antes = self.neighbors[k], [i.X[0] for i in self.pop]
            fv = self.decomposition.do(self.pop[viz].get("F"), weights=self.ref_dirs[viz], ideal_point=self.ideal)
            fo = self.decomposition.do(off.F[None, :], weights=self.ref_dirs[viz], ideal_point=self.ideal)
            objetos, f_antes = list(self.pop), self.pop[viz].get("F").copy()
            super()._replace(k, off)
            trocados = [int(i) for i in viz if self.pop[i] is off and objetos[i] is not off]
            assert trocados == [int(i) for i in viz[fo < fv]]
            assert all(a is self.pop[i].X[0] for i, a in enumerate(antes) if i not in trocados)
            evento = copy.deepcopy(atual) | dict(
                k=int(k), vizinhos=viz.tolist(), ideal_antes=self.anterior.tolist(), ideal_depois=self.ideal.tolist(),
                f=off.F.tolist(), plano=lista(off.X[0]), g_antes=fv.tolist(), g_filho=fo.tolist(), trocados=trocados,
                g_ideal_anterior=self.decomposition.do(f_antes, weights=self.ref_dirs[viz], ideal_point=self.anterior).tolist())
            log["eventos"].append(evento)
            self.anterior = self.ideal.copy()

    trocas = [(moead, "MOEAD", Algoritmo), (moead, "FeasibleEvaluator", Avaliador),
              (moead, "ScheduleCrossover", Cruzamento), (moead, "ScheduleMutation", Mutacao),
              (pymoo_moead, "NeighborhoodSelection", Vizinhanca)]
    originais = [(m, n, getattr(m, n)) for m, n, _ in trocas]
    try:
        for modulo, nome, novo in trocas:
            setattr(modulo, nome, novo)
        result = moead.run_moead(instance, config)
    finally:
        for modulo, nome, antigo in originais:
            setattr(modulo, nome, antigo)
    return result, log


def medidas(instance, planos, inicial, log):
    """Tchebycheff de dois planos iniciais para dois pesos; o vencedor se inverte."""
    saida = []
    for k in MEDIDA_PESOS:
        peso, linhas = np.array(log["direcoes"][k]), []
        for dono in MEDIDA_FEIXES:
            p = planos[inicial[dono]]
            f = np.array([p["cmax"] / instance.horizon, float(Fraction(p["tec"]) / instance.max_cost)])
            lados = np.abs(f - log["ideal0"]) * peso
            valor = float(moead.Tchebicheff(eps=0.0).do(f[None, :], weights=peso[None, :],
                                                        ideal_point=np.array(log["ideal0"])).item())
            assert abs(valor - lados.max()) < 1e-12
            linhas.append(dict(feixe=dono, plano=inicial[dono], lados=lados.tolist(), valor=valor))
        saida.append(dict(k=k, peso=peso.tolist(), linhas=linhas))
    return saida


def frente(result):
    return [(s.key, s.schedule) for s in result.front]


def gerar(config=CONFIG):
    instance = read_instance(HERE / "data" / "didatica.dat")
    normal = moead.run_moead(instance, config)
    result, log = capturar(instance, config)
    if (frente(normal), normal.attempts, normal.rejected_evaluations) != (
            frente(result), result.attempts, result.rejected_evaluations):
        raise RuntimeError("A execução instrumentada diverge da normal")
    planos, indice = [], {}

    def guardar(schedule):
        key = json.dumps(schedule)
        if key not in indice:
            indice[key] = len(planos)
            planos.append(montar(instance, tuple(tuple(map(tuple, s)) for s in schedule)))
        return indice[key]

    pop = [guardar(s) for s in log["inicial"]]
    inicial, melhores = list(pop), []
    for n, e in enumerate(log["eventos"]):
        e["pais_planos"] = [guardar(s) for s in e.pop("planos_pais")]
        assert e["pais_planos"] == [pop[i] for i in e["pais"]]
        for nome in ("cruzado", "filho", "plano"):
            e[nome] = guardar(e[nome])
        e["pop_antes"] = list(pop)
        for i in e["trocados"]:
            pop[i] = e["plano"]
        e["pop_depois"] = list(pop)
        e["varredura"], e["posicao"] = n // config.population_size, n % config.population_size
        # O viável tem F exatamente igual aos objetivos escalados; o rejeitado tem F da cópia.
        p = planos[e["plano"]]
        esperado = [p["cmax"] / instance.horizon, float(Fraction(p["tec"]) / instance.max_cost)]
        assert np.allclose(e["f"], esperado, rtol=0, atol=1e-12)
        assert e["rejeitado"] == (not planos[e["filho"]]["viavel"])
        if e["rejeitado"]:
            assert e["plano"] == e["pop_antes"][e["copia_de"]]
    finais = {tuple((s.key[0], s.evaluation.tec)) for s in result.front}
    assert finais <= {(planos[i]["cmax"], planos[i]["tec"]) for i in pop}
    final = sorted(({"plano": guardar(lista(s.schedule)), "cmax": s.key[0], "tec": s.evaluation.tec}
                    for s in result.front), key=lambda r: r["cmax"])
    campanha = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    custos = [planos[i]["tec"] for i in pop]
    visto = min((planos[e["plano"]]["tec"], n) for n, e in enumerate(log["eventos"]))
    perdido = dict(melhor_tec_visto=visto[0], evento=visto[1], melhor_tec_final=min(custos),
                   ideal_final_tec=log["eventos"][-1]["ideal_depois"][1] * float(instance.max_cost))
    assert abs(perdido["ideal_final_tec"] - visto[0]) < 1e-9
    return dict(
        descricao="demonstração do MOEA/D na instância didática; não é a campanha", instancia=instance.path.name,
        sha256=instance.digest, horizon=instance.horizon, max_cost=float(instance.max_cost),
        versoes=dict(python=platform.python_version(), numpy=np.__version__, pymoo=pymoo.__version__),
        demonstracao=config.as_dict(), campanha=campanha["configurations"]["moead"]["parameters"],
        direcoes=log["direcoes"], vizinhos=log["vizinhos"], ideal0=log["ideal0"],
        destaques=DESTAQUES, medidas=medidas(instance, planos, inicial, log), perdido=perdido,
        planos_distintos_final=len(set(pop)), planos=planos, inicial=inicial, eventos=log["eventos"], final=pop, frente=final,
        tentativas=result.attempts, viaveis=result.feasible_evaluations, rejeitadas=result.rejected_evaluations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Recalcula e compara com o JSON salvo.")
    args = parser.parse_args()
    data = json.loads(json.dumps(gerar()))
    if args.check:
        if json.loads(SAIDA.read_text(encoding="utf-8")) != data:
            raise SystemExit("trace_moead.json diverge da execução.")
        print("Trace verificado; execução instrumentada idêntica à normal.")
    else:
        SAIDA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{SAIDA}: {len(data['eventos'])} eventos, {data['rejeitadas']} rejeições, "
              f"frente {[(p['cmax'], p['tec']) for p in data['frente']]}")


if __name__ == "__main__":
    main()
