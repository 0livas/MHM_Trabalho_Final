"""Native pymoo 0.6.2 MOEA/D with feasible schedules and a literal attempt cap.

The public ask/tell driver can stop between subproblems. Selection, ideal-point
updates, Tchebycheff decomposition and neighborhood replacement belong to pymoo.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from numbers import Integral
from pathlib import Path
import sys
import time

import numpy as np
import pymoo
from pymoo.algorithms.moo.moead import MOEAD
from pymoo.core.evaluator import Evaluator
from pymoo.core.population import Population
from pymoo.core.problem import ElementwiseProblem
from pymoo.decomposition.tchebicheff import Tchebicheff
from pymoo.util.ref_dirs import get_reference_directions

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from problem import PROJECT_ROOT, Instance, atomic_json, insert_pareto, read_instance  # noqa: E402
from schedule import ScheduleValidationError, evaluate_schedule  # noqa: E402
from metaheuristics.spea2 import (  # noqa: E402
    ParetoSolution,
    ScheduleCrossover,
    ScheduleMutation,
    ScheduleSampling,
    _as_schedule,
)


@dataclass(frozen=True, slots=True)
class MOEADConfig:
    seed: int = 1
    max_evaluations: int = 10_000
    population_size: int = 100
    n_neighbors: int = 20
    prob_neighbor_mating: float = 0.9
    crossover_probability: float = 0.9
    mutation_probability: float = 0.3

    def __post_init__(self):
        for name in ("seed", "max_evaluations", "population_size", "n_neighbors"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise ValueError(f"{name} deve ser inteiro")
        if self.seed < 0:
            raise ValueError("seed deve ser não negativa")
        if self.population_size < 2:
            raise ValueError("population_size deve ser pelo menos 2")
        if self.max_evaluations < self.population_size:
            raise ValueError("max_evaluations deve cobrir a população inicial")
        if not 2 <= self.n_neighbors <= self.population_size:
            raise ValueError("n_neighbors deve estar entre 2 e population_size")
        for name in ("prob_neighbor_mating", "crossover_probability", "mutation_probability"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} deve estar entre 0 e 1")

    def as_dict(self) -> dict:
        return {**asdict(self), "decomposition": "Tchebycheff", "decomposition_eps": 0.0,
                "objective_scaling": "Cmax/H, TEC/max_cost",
                "reference_directions": {"method": "uniform", "n_obj": 2,
                                         "n_partitions": self.population_size - 1},
                "offspring_per_subproblem": 1,
                "infeasibility_policy": "cached_uniform_population_fallback"}


def reference_directions(population_size: int) -> np.ndarray:
    if (isinstance(population_size, bool) or not isinstance(population_size, Integral)
            or population_size < 2):
        raise ValueError("population_size deve ser inteiro e pelo menos 2")
    return get_reference_directions("uniform", 2, n_partitions=population_size - 1)


@dataclass(slots=True)
class MOEADTrace:
    attempts: int = 0
    feasible: int = 0
    rejected: int = 0


class ScheduleProblem(ElementwiseProblem):
    """No declared constraints: rejected candidates never reach MOEA/D."""

    def __init__(self, instance: Instance, trace: MOEADTrace, max_evaluations: int):
        super().__init__(n_var=1, n_obj=2, vtype=object)
        self.instance = instance
        self.trace = trace
        self.max_evaluations = max_evaluations
        # These are input constants, not estimated objective ranges or optima.
        if instance.horizon <= 0 or instance.max_cost <= 0:
            raise ValueError("H e max_cost devem ser positivos")

    def _evaluate(self, x, out, *args, **kwargs):
        if self.trace.attempts >= self.max_evaluations:
            raise RuntimeError("Orçamento de avaliações esgotado")
        self.trace.attempts += 1
        try:
            evaluation = evaluate_schedule(self.instance, x[0])
        except ScheduleValidationError:
            self.trace.rejected += 1
            raise
        self.trace.feasible += 1
        # Convert the exact ratio once, rather than rounding TEC before scaling.
        out["F"] = np.array([evaluation.cmax / self.instance.horizon,
                             float(evaluation.tec_exact / self.instance.max_cost)])
        if not np.isfinite(out["F"]).all():
            raise ValueError("Objetivos normalizados não finitos")


class FeasibleEvaluator(Evaluator):
    """Charge the original attempt, then substitute cached feasible X/F if rejected.

    Evaluator.eval owns n_eval bookkeeping, including rejected attempts. Only its
    evaluation hook is adapted; no scalarization or replacement is overridden.
    Initial construction failure aborts explicitly rather than using invalid F.
    """

    def __init__(self):
        super().__init__(skip_already_evaluated=False, evaluate_values_of=["F"])
        self.fallback = None

    def _eval(self, problem, pop, evaluate_values_of, **kwargs):
        if len(pop) > problem.max_evaluations - problem.trace.attempts:
            raise RuntimeError("Batch de avaliação excederia o orçamento")
        for individual in pop:
            try:
                super()._eval(problem, Population.create(individual), evaluate_values_of, **kwargs)
            except ScheduleValidationError as error:
                if self.fallback is None:
                    raise RuntimeError("Sampling produziu schedule inviável") from error
                cached = self.fallback()
                # Native schedules are immutable tuples; copy the object array and F.
                individual.X = cached.X.copy()
                individual.F = cached.F.copy()
                individual.evaluated.update(evaluate_values_of)


@dataclass(slots=True)
class MOEADResult:
    instance: Instance
    config: MOEADConfig
    front: tuple[ParetoSolution, ...]
    attempts: int
    feasible_evaluations: int
    rejected_evaluations: int
    pymoo_evaluations: int
    post_search_validations: int
    elapsed_seconds: float

    def to_result_dict(self) -> dict:
        front = []
        for solution in self.front:
            row = solution.evaluation.to_result_dict(self.instance)
            row["representation"] = [[[job, mode, wait] for job, mode, wait in machine]
                                     for machine in solution.schedule]
            front.append(row)
        return {
            "format_version": 1, "algorithm": "MOEA/D", "method": "moead_pymoo",
            "variant": "Tchebycheff with fixed instance scaling and feasible fallback",
            "pymoo_version": pymoo.__version__,
            "instance": self.instance.path.name, "instance_sha256": self.instance.digest,
            "pareto_proven": False, "stop_reason": "budget_reached",
            "horizon": self.instance.horizon,
            "cost_scale": self.front[0].evaluation.tec_scale if self.front else None,
            "run_parameters": self.config.as_dict(),
            "objective_scaling": {
                "cmax_divisor": self.instance.horizon,
                "tec_divisor_exact": {"numerator": self.instance.max_cost.numerator,
                                      "denominator": self.instance.max_cost.denominator}},
            "reference_directions": reference_directions(self.config.population_size).tolist(),
            "population_size": self.config.population_size, "n_neighbors": self.config.n_neighbors,
            "budget": self.config.max_evaluations, "max_evaluations": self.config.max_evaluations,
            "evaluations": self.attempts, "attempts": self.attempts,
            "feasible_evaluations": self.feasible_evaluations,
            "rejected_evaluations": self.rejected_evaluations,
            "pymoo_evaluations": self.pymoo_evaluations,
            "post_search_validations": self.post_search_validations,
            "elapsed_seconds": self.elapsed_seconds, "points": len(front), "front": front,
        }


def _final_front(instance: Instance, population) -> tuple[ParetoSolution, ...]:
    archive: list[tuple[tuple[int, int], ParetoSolution]] = []
    for individual in population:
        schedule = _as_schedule(individual.X[0])
        evaluation = evaluate_schedule(instance, schedule)
        solution = ParetoSolution(schedule, evaluation)
        insert_pareto(archive, solution.key, solution)
    return tuple(solution for _, solution in archive)


def run_moead(instance: Instance, config: MOEADConfig = MOEADConfig()) -> MOEADResult:
    # The integration is validated against this version's loopwise evaluation API.
    if pymoo.__version__ != "0.6.2":
        raise RuntimeError("MOEA/D requer pymoo 0.6.2; revalide a integração antes de atualizar")
    trace = MOEADTrace()
    problem = ScheduleProblem(instance, trace, config.max_evaluations)
    evaluator = FeasibleEvaluator()
    algorithm = MOEAD(ref_dirs=reference_directions(config.population_size),
                      n_neighbors=config.n_neighbors, decomposition=Tchebicheff(eps=0.0),
                      prob_neighbor_mating=config.prob_neighbor_mating,
                      sampling=ScheduleSampling(),
                      crossover=ScheduleCrossover(prob=config.crossover_probability),
                      mutation=ScheduleMutation(prob=config.mutation_probability),
                      evaluator=evaluator)
    started = time.monotonic()
    algorithm.setup(problem, termination=("n_eval", config.max_evaluations),
                    seed=config.seed, verbose=False)
    while trace.attempts < config.max_evaluations:
        candidates = algorithm.ask()
        if candidates is None:
            # The native generator can finish a sweep without yielding a candidate.
            continue
        evaluator.eval(problem, candidates)
        algorithm.tell(infills=candidates)
        if evaluator.fallback is None:
            evaluator.fallback = lambda: algorithm.pop[
                int(algorithm.random_state.integers(len(algorithm.pop)))]
    elapsed = time.monotonic() - started
    if not (trace.attempts == evaluator.n_eval == config.max_evaluations
            and trace.feasible + trace.rejected == trace.attempts):
        raise RuntimeError("Contagem de avaliações inconsistente")
    # Read pop directly: algorithm.opt may be stale during an incomplete sweep.
    # These independent complete evaluations cannot affect the completed search.
    front = _final_front(instance, algorithm.pop)
    return MOEADResult(instance, config, front, trace.attempts, trace.feasible,
                       trace.rejected, int(evaluator.n_eval), len(algorithm.pop), elapsed)


def write_result(result: MOEADResult, output: Path | str, *, overwrite: bool = False) -> Path:
    path = Path(output)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Resultado já existe: {path}; passe overwrite=True para substituir")
    atomic_json(path, result.to_result_dict())
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path,
                        default=PROJECT_ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/output/moead")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-evaluations", type=int, default=10_000)
    parser.add_argument("--population-size", type=int, default=100)
    parser.add_argument("--n-neighbors", type=int, default=20)
    parser.add_argument("--prob-neighbor-mating", type=float, default=0.9)
    parser.add_argument("--crossover-probability", type=float, default=0.9)
    parser.add_argument("--mutation-probability", type=float, default=0.3)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        config = MOEADConfig(args.seed, args.max_evaluations, args.population_size,
                             args.n_neighbors, args.prob_neighbor_mating,
                             args.crossover_probability, args.mutation_probability)
    except ValueError as error:
        parser.error(str(error))
    paths = sorted(args.input.glob("*.dat")) if args.input.is_dir() else [args.input]
    if not paths:
        parser.error("Nenhuma instância encontrada")
    for path in paths:
        output = args.output_dir / f"{path.stem}.json"
        if output.exists() and not args.overwrite:
            parser.error(f"Resultado já existe: {output}; use --overwrite para substituir")
        result = run_moead(read_instance(path), config)
        write_result(result, output, overwrite=args.overwrite)
        print(f"{path.name}: tentativas={result.attempts}, viáveis={result.feasible_evaluations}, "
              f"rejeições={result.rejected_evaluations}, pontos={len(result.front)}, "
              f"tempo={result.elapsed_seconds:.3f}s, saída={output}")


if __name__ == "__main__":
    main()
