"""NSGA-II (pymoo) com cromossomo de quatro vetores para o UPMSP-SDS.

O indivíduo é ``[seq | machine | mode | avoid]`` (ver ``decoder.py``). O NSGA-II
nativo do pymoo faz a ordenação não dominada, a crowding distance e o torneio
binário; os inviáveis (término após o horizonte) são tratados pela dominância
com restrições, usando o excesso sobre o horizonte como violação.

Run from the repository root::

    python src/heuristics/nsga2/nsga2.py data/input/set1/6_2_1439_3_S_1-9.dat
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
import time

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from decoder import Decoder, upper_bounds  # noqa: E402
from operators import ChromosomeSampling, MixedCrossover, MixedMutation  # noqa: E402
from problem import PROJECT_ROOT, Instance, atomic_json, insert_pareto, read_instance  # noqa: E402
from schedule import Schedule, ScheduleEvaluation, evaluate_schedule  # noqa: E402


@dataclass(frozen=True, slots=True)
class NSGA2Config:
    seed: int = 1
    max_evaluations: int = 10_000
    population_size: int = 100
    crossover_probability: float = 0.9
    mutation_probability: float = 0.3

    def __post_init__(self):
        if self.max_evaluations < 1:
            raise ValueError("max_evaluations deve ser positivo")
        if self.population_size < 2:
            raise ValueError("population_size deve ser pelo menos 2")
        if self.max_evaluations < self.population_size:
            raise ValueError("max_evaluations não pode ser menor que population_size")
        for name, value in (("crossover_probability", self.crossover_probability),
                            ("mutation_probability", self.mutation_probability)):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} deve estar entre 0 e 1")

    def as_dict(self) -> dict:
        return {"seed": self.seed, "max_evaluations": self.max_evaluations,
                "population_size": self.population_size,
                "crossover_probability": self.crossover_probability,
                "mutation_probability": self.mutation_probability,
                "representation": "seq|machine|mode|avoid"}


@dataclass(slots=True)
class NSGA2Trace:
    attempts: int = 0
    feasible: int = 0
    rejected: int = 0


@dataclass(frozen=True, slots=True)
class ParetoSolution:
    chromosome: tuple[int, ...]
    schedule: Schedule
    evaluation: ScheduleEvaluation

    @property
    def key(self) -> tuple[int, int]:
        return self.evaluation.objective_key


class ChromosomeProblem(ElementwiseProblem):
    """F = (Cmax, TEC); G = excesso sobre o horizonte (<= 0 é viável)."""

    def __init__(self, instance: Instance, trace: NSGA2Trace):
        super().__init__(n_var=4 * instance.n, n_obj=2, n_ieq_constr=1,
                         xl=0, xu=upper_bounds(instance), vtype=int)
        self.instance = instance
        self.decoder = Decoder(instance)
        self.trace = trace

    def _evaluate(self, x, out, *args, **kwargs):
        self.trace.attempts += 1
        decoded = self.decoder.decode(x)
        if decoded.feasible:
            self.trace.feasible += 1
        else:
            self.trace.rejected += 1
        out["F"] = np.array([decoded.cmax, decoded.tec_units / decoded.tec_scale], dtype=float)
        out["G"] = np.array([float(decoded.overflow)])


@dataclass(slots=True)
class NSGA2Result:
    instance: Instance
    config: NSGA2Config
    front: tuple[ParetoSolution, ...]
    attempts: int
    feasible_evaluations: int
    rejected_evaluations: int
    generations: int
    post_search_validations: int
    elapsed_seconds: float

    def to_result_dict(self) -> dict:
        return {
            "format_version": 1,
            "algorithm": "NSGA-II",
            "method": "nsga2_pymoo",
            "instance": self.instance.path.name,
            "instance_sha256": self.instance.digest,
            "pareto_proven": False,
            "horizon": self.instance.horizon,
            "cost_scale": self.front[0].evaluation.tec_scale if self.front else None,
            "run_parameters": self.config.as_dict(),
            "budget": self.config.max_evaluations,
            "evaluations": self.attempts,
            "attempts": self.attempts,
            "feasible_evaluations": self.feasible_evaluations,
            "rejected_evaluations": self.rejected_evaluations,
            "generations": self.generations,
            "post_search_validations": self.post_search_validations,
            "elapsed_seconds": self.elapsed_seconds,
            "points": len(self.front),
            "front": [self._solution_to_result(solution) for solution in self.front],
        }

    def _solution_to_result(self, solution: ParetoSolution) -> dict:
        result = solution.evaluation.to_result_dict(self.instance)
        result["representation"] = [[[job, mode, wait] for job, mode, wait in machine]
                                    for machine in solution.schedule]
        result["chromosome"] = list(solution.chromosome)
        return result


def _final_front(instance: Instance, decoder: Decoder, population) -> tuple[ParetoSolution, ...]:
    """Reavalia os sobreviventes viáveis com o avaliador comum, fora do orçamento."""
    archive: list[tuple[tuple[int, int], ParetoSolution]] = []
    for individual in population:
        decoded = decoder.decode(individual.X)
        if not decoded.feasible:
            continue
        evaluation = evaluate_schedule(instance, decoded.schedule)
        if evaluation.objective_key != (decoded.cmax, decoded.tec_units):
            raise RuntimeError("Decodificador diverge do avaliador comum")
        solution = ParetoSolution(tuple(int(v) for v in individual.X), decoded.schedule, evaluation)
        insert_pareto(archive, solution.key, solution)
    return tuple(solution for _, solution in archive)


def run_nsga2(instance: Instance, config: NSGA2Config = NSGA2Config()) -> NSGA2Result:
    trace = NSGA2Trace()
    problem = ChromosomeProblem(instance, trace)
    algorithm = NSGA2(pop_size=config.population_size,
                      sampling=ChromosomeSampling(),
                      crossover=MixedCrossover(prob=config.crossover_probability),
                      mutation=MixedMutation(prob=config.mutation_probability),
                      eliminate_duplicates=True)
    started = time.monotonic()
    algorithm.setup(problem, seed=config.seed, verbose=False)
    generations = 0
    empty_asks = 0
    # Driver ask/tell: o último lote é truncado para respeitar o orçamento literal.
    while trace.attempts < config.max_evaluations:
        candidates = algorithm.ask()
        remaining = config.max_evaluations - trace.attempts
        if candidates is None or len(candidates) == 0:
            # Todos os descendentes eram duplicatas; desiste após várias tentativas.
            empty_asks += 1
            if empty_asks >= 100:
                break
            continue
        empty_asks = 0
        candidates = candidates[:remaining]
        algorithm.evaluator.eval(problem, candidates)
        algorithm.tell(infills=candidates)
        generations += 1
    elapsed = time.monotonic() - started
    if trace.attempts > config.max_evaluations or trace.feasible + trace.rejected != trace.attempts:
        raise RuntimeError("Contagem de avaliações inconsistente")
    post_search_validations = sum(1 for individual in algorithm.pop
                                  if np.all(individual.G <= 0))
    front = _final_front(instance, problem.decoder, algorithm.pop)
    return NSGA2Result(instance, config, front, trace.attempts, trace.feasible, trace.rejected,
                       generations, post_search_validations, elapsed)


def write_result(result: NSGA2Result, output: Path | str, *, overwrite: bool = False) -> Path:
    path = Path(output)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Resultado já existe: {path}; passe overwrite=True para substituir")
    atomic_json(path, result.to_result_dict())
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path,
                        default=PROJECT_ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/output/nsga2")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-evaluations", type=int, default=10_000)
    parser.add_argument("--population-size", type=int, default=100)
    parser.add_argument("--crossover-probability", type=float, default=0.9)
    parser.add_argument("--mutation-probability", type=float, default=0.3)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    paths = sorted(args.input.glob("*.dat")) if args.input.is_dir() else [args.input]
    if not paths:
        parser.error("Nenhuma instância encontrada")
    try:
        config = NSGA2Config(args.seed, args.max_evaluations, args.population_size,
                             args.crossover_probability, args.mutation_probability)
    except ValueError as error:
        parser.error(str(error))
    for path in paths:
        instance = read_instance(path)
        output = args.output_dir / f"{path.stem}.json"
        if output.exists() and not args.overwrite:
            parser.error(f"Resultado já existe: {output}; use --overwrite para substituir")
        result = run_nsga2(instance, config)
        write_result(result, output, overwrite=args.overwrite)
        print(f"{path.name}: avaliações={result.attempts}, viáveis={result.feasible_evaluations}, "
              f"inviáveis={result.rejected_evaluations}, gerações={result.generations}, "
              f"pontos={len(result.front)}, tempo={result.elapsed_seconds:.3f}s, saída={output}")


if __name__ == "__main__":
    main()
