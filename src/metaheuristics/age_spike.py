"""Spike isolado AGE-MOEA; não participa da campanha experimental."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pymoo
from pymoo.algorithms.moo.age import AGEMOEA

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from problem import read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402
from metaheuristics.spea2 import (  # noqa: E402
    ScheduleProblem, SPEA2Trace, ScheduleSampling, ScheduleCrossover, ScheduleMutation,
)


def run_spike(instance, *, seed=23, budget=41, population_size=8, offspring_size=8):
    if pymoo.__version__ != "0.6.2":
        raise RuntimeError("Spike validado somente com pymoo 0.6.2")
    if population_size < 2 or budget < population_size or offspring_size < 1:
        raise ValueError("População >= 2, orçamento >= população e descendentes >= 1")
    trace = SPEA2Trace()
    problem = ScheduleProblem(instance, trace)
    algorithm = AGEMOEA(
        pop_size=population_size, n_offsprings=offspring_size,
        sampling=ScheduleSampling(), crossover=ScheduleCrossover(prob=0.9),
        mutation=ScheduleMutation(prob=0.3), eliminate_duplicates=False,
    )
    algorithm.setup(problem, termination=("n_eval", budget), seed=seed, verbose=False)
    initial = set()
    novel = 0
    batches = []
    while algorithm.has_next():
        # API pública: reduz somente o último lote, antes de gerar/avaliar candidatos.
        algorithm.n_offsprings = min(offspring_size, budget - trace.attempts)
        candidates = algorithm.ask()
        if candidates is None or len(candidates) == 0:
            raise RuntimeError("AGE-MOEA terminou sem consumir o orçamento")
        if not batches:
            initial = {individual.X[0] for individual in candidates}
        else:
            novel += sum(individual.X[0] not in initial for individual in candidates)
        algorithm.evaluator.eval(problem, candidates)
        batches.append(len(candidates))
        algorithm.tell(infills=candidates)
    if not (trace.attempts == algorithm.evaluator.n_eval == budget
            and trace.feasible + trace.rejected == budget):
        raise AssertionError("Contagem de avaliações inconsistente")
    survivors = []
    for individual in algorithm.pop:
        if not individual.FEAS[0]:
            raise AssertionError("Sobrevivente inviável")
        checked = evaluate_schedule(instance, individual.X[0])
        np.testing.assert_array_equal(individual.F, [checked.cmax, checked.tec])
        survivors.append({"representation": individual.X[0],
                          "cmax": checked.cmax, "tec_units": checked.tec_units,
                          "tec_scale": checked.tec_scale})
    return {"pymoo": pymoo.__version__, "instance": instance.path.name,
            "instance_sha256": instance.digest, "seed": seed, "budget": budget,
            "population_size": population_size, "offspring_size": offspring_size,
            "crossover_probability": 0.9, "mutation_probability": 0.3,
            "evaluations": trace.attempts, "pymoo_evaluations": algorithm.evaluator.n_eval,
            "feasible": trace.feasible, "rejected": trace.rejected,
            "batches": batches, "novel_offspring": novel,
            "novel_survivors": sum(ind.X[0] not in initial for ind in algorithm.pop),
            "post_search_validations": len(survivors), "survivors": survivors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--budget", type=int, default=41)
    parser.add_argument("--population-size", type=int, default=8)
    parser.add_argument("--offspring-size", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(run_spike(read_instance(args.instance), seed=args.seed,
                              budget=args.budget, population_size=args.population_size,
                              offspring_size=args.offspring_size), indent=2))


if __name__ == "__main__":
    main()
