"""AGE-MOEA do pymoo com schedules nativos e último lote parcial."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from numbers import Integral
from pathlib import Path
import sys
import time

import numpy as np
import pymoo
from pymoo.algorithms.moo.age import AGEMOEA

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from problem import PROJECT_ROOT, Instance, atomic_json, insert_pareto, read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402
from metaheuristics.spea2 import (  # noqa: E402
    ParetoSolution, ScheduleProblem, SPEA2Trace,
    ScheduleSampling, ScheduleCrossover, ScheduleMutation,
)


@dataclass(frozen=True, slots=True)
class AGEConfig:
    seed: int = 1
    max_evaluations: int = 10_000
    population_size: int = 100
    crossover_probability: float = 0.9
    mutation_probability: float = 0.3

    def __post_init__(self):
        for name in ("seed", "max_evaluations", "population_size"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise ValueError(f"{name} deve ser inteiro")
        if self.seed < 0:
            raise ValueError("seed deve ser não negativa")
        if self.population_size < 2:
            raise ValueError("population_size deve ser pelo menos 2")
        if self.max_evaluations < self.population_size:
            raise ValueError("max_evaluations deve cobrir a população inicial")
        for name in ("crossover_probability", "mutation_probability"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} deve estar entre 0 e 1")

    def as_dict(self) -> dict:
        return {**asdict(self), "n_offsprings": self.population_size,
                "regime": "generational_with_partial_final_batch",
                "infeasibility_policy": "native_constraint_filtering",
                "eliminate_duplicates": False,
                "objective_scaling": "raw Cmax, float TEC; native AGE normalization"}


@dataclass(slots=True)
class AGEResult:
    instance: Instance
    config: AGEConfig
    front: tuple[ParetoSolution, ...]
    attempts: int
    feasible_evaluations: int
    rejected_evaluations: int
    pymoo_evaluations: int
    post_search_validations: int
    elapsed_seconds: float
    evaluation_batches: tuple[int, ...]

    def to_result_dict(self) -> dict:
        front = []
        for solution in self.front:
            row = solution.evaluation.to_result_dict(self.instance)
            row["representation"] = [[[job, mode, wait] for job, mode, wait in machine]
                                     for machine in solution.schedule]
            front.append(row)
        return {
            "format_version": 1, "algorithm": "AGE-MOEA", "method": "age_pymoo",
            "variant": "generational with partial final batch",
            "pymoo_version": pymoo.__version__,
            "instance": self.instance.path.name, "instance_sha256": self.instance.digest,
            "pareto_proven": False, "stop_reason": "budget_reached",
            "horizon": self.instance.horizon,
            "cost_scale": self.front[0].evaluation.tec_scale if self.front else None,
            "run_parameters": self.config.as_dict(),
            "population_size": self.config.population_size,
            "budget": self.config.max_evaluations, "max_evaluations": self.config.max_evaluations,
            "evaluations": self.attempts, "attempts": self.attempts,
            "feasible_evaluations": self.feasible_evaluations,
            "rejected_evaluations": self.rejected_evaluations,
            "pymoo_evaluations": self.pymoo_evaluations,
            "post_search_validations": self.post_search_validations,
            "evaluation_batches": list(self.evaluation_batches),
            "elapsed_seconds": self.elapsed_seconds, "points": len(front), "front": front,
        }


def _final_front(instance: Instance, population) -> tuple[ParetoSolution, ...]:
    archive: list[tuple[tuple[int, int], ParetoSolution]] = []
    for individual in population:
        if not individual.FEAS[0]:
            raise RuntimeError("AGE-MOEA retornou sobrevivente inviável")
        schedule = individual.X[0]
        evaluation = evaluate_schedule(instance, schedule)
        if not np.array_equal(individual.F, [evaluation.cmax, evaluation.tec]):
            raise RuntimeError("Objetivos armazenados divergem da reavaliação")
        solution = ParetoSolution(schedule, evaluation)
        insert_pareto(archive, solution.key, solution)
    return tuple(solution for _, solution in archive)


def run_age(instance: Instance, config: AGEConfig = AGEConfig()) -> AGEResult:
    if pymoo.__version__ != "0.6.2":
        raise RuntimeError("AGE-MOEA requer pymoo 0.6.2; revalide antes de atualizar")
    trace = SPEA2Trace()
    problem = ScheduleProblem(instance, trace)
    algorithm = AGEMOEA(
        pop_size=config.population_size, n_offsprings=config.population_size,
        sampling=ScheduleSampling(),
        crossover=ScheduleCrossover(prob=config.crossover_probability),
        mutation=ScheduleMutation(prob=config.mutation_probability),
        eliminate_duplicates=False,
    )
    started = time.monotonic()
    algorithm.setup(problem, termination=("n_eval", config.max_evaluations),
                    seed=config.seed, verbose=False)
    batches = []
    while algorithm.has_next():
        remaining = config.max_evaluations - trace.attempts
        if remaining <= 0:
            raise RuntimeError("AGE-MOEA não terminou após esgotar o orçamento")
        # Reduz a quantidade antes do mating: nenhum candidato é descartado.
        algorithm.n_offsprings = min(config.population_size, remaining)
        candidates = algorithm.ask()
        if candidates is None or not 0 < len(candidates) <= remaining:
            raise RuntimeError("Lote AGE-MOEA vazio ou maior que o orçamento restante")
        algorithm.evaluator.eval(problem, candidates)
        if not np.isfinite(candidates.get("F")).all():
            raise RuntimeError("Objetivos AGE-MOEA não finitos")
        if not batches and not candidates.get("FEAS").all():
            raise RuntimeError("Inicialização AGE-MOEA produziu schedule inviável")
        algorithm.tell(infills=candidates)
        batches.append(len(candidates))
    elapsed = time.monotonic() - started
    if not (trace.attempts == algorithm.evaluator.n_eval == config.max_evaluations
            and trace.feasible + trace.rejected == trace.attempts):
        raise RuntimeError("Contagem de avaliações inconsistente")
    if len(algorithm.pop) != config.population_size:
        raise RuntimeError("Tamanho da população final inconsistente")
    # Avaliações independentes após o cap; filtro e deduplicação por inteiros exatos.
    front = _final_front(instance, algorithm.pop)
    return AGEResult(instance, config, front, trace.attempts, trace.feasible,
                     trace.rejected, int(algorithm.evaluator.n_eval), len(algorithm.pop),
                     elapsed, tuple(batches))


def write_result(result: AGEResult, output: Path | str, *, overwrite: bool = False) -> Path:
    path = Path(output)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Resultado já existe: {path}; passe overwrite=True para substituir")
    atomic_json(path, result.to_result_dict())
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/output/age")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-evaluations", type=int, default=10_000)
    parser.add_argument("--population-size", type=int, default=100)
    parser.add_argument("--crossover-probability", type=float, default=0.9)
    parser.add_argument("--mutation-probability", type=float, default=0.3)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        config = AGEConfig(args.seed, args.max_evaluations, args.population_size,
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
        result = run_age(read_instance(path), config)
        write_result(result, output, overwrite=args.overwrite)
        print(f"{path.name}: tentativas={result.attempts}, viáveis={result.feasible_evaluations}, "
              f"rejeições={result.rejected_evaluations}, pontos={len(result.front)}, "
              f"tempo={result.elapsed_seconds:.3f}s, saída={output}")


if __name__ == "__main__":
    main()
