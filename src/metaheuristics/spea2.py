# SPEA2 incremental para sequências nativas de máquinas usando pymoo.

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
import time

import numpy as np
from pymoo.algorithms.moo.spea2 import SPEA2, SPEA2Survival
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.sampling import Sampling
from pymoo.optimize import minimize

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from problem import (  # noqa: E402
    PROJECT_ROOT,
    Instance,
    atomic_json,
    insert_pareto,
    read_instance,
)
from schedule import (  # noqa: E402
    Schedule,
    ScheduleEvaluation,
    ScheduleValidationError,
    evaluate_schedule,
)


@dataclass(frozen=True, slots=True)
class SPEA2Config:
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
                "n_offsprings": 1, "regime": "incremental"}


@dataclass(slots=True)
class SPEA2Trace:
    attempts: int = 0
    feasible: int = 0
    rejected: int = 0


@dataclass(frozen=True, slots=True)
class ParetoSolution:
    schedule: Schedule
    evaluation: ScheduleEvaluation

    @property
    def key(self) -> tuple[int, int]:
        return self.evaluation.objective_key


def _as_schedule(value) -> Schedule:
    return tuple(tuple((int(job), int(mode), int(wait)) for job, mode, wait in machine)
                 for machine in value)


def _random_schedule(instance: Instance, rng: np.random.Generator) -> Schedule:
    # Constrói uma solução viável sem avaliações ou tentativas extras.
    # A prioridade LPT e a escolha aleatória controlada geram variedade.
    difficulty = []
    for job in range(instance.n):
        shortest = min(instance.duration(job, machine, mode)
                       for machine in range(instance.m) for mode in range(instance.modes))
        difficulty.append((job, shortest))
    remaining = [job for job, _ in sorted(difficulty, key=lambda item: (-item[1], item[0]))]

    machine_jobs: list[list[tuple[int, int, int]]] = [[] for _ in range(instance.m)]
    machine_end = [0] * instance.m
    machine_last: list[int | None] = [None] * instance.m
    while remaining:
        # LPT aleatório: escolhe entre os jobs mais difíceis.
        # A janela cresce sublinearmente e mantém variedade.
        window_size = int(np.ceil(np.sqrt(len(remaining))))
        job = remaining.pop(int(rng.integers(window_size)))
        options: list[tuple[int, int, int]] = []
        for machine in range(instance.m):
            previous = machine_last[machine]
            setup = instance.setup[machine][previous][job] if previous is not None else 0
            for mode in range(instance.modes):
                end = machine_end[machine] + setup + instance.duration(job, machine, mode)
                if end <= instance.horizon:
                    options.append((end, machine, mode))
        if not options:
            raise RuntimeError(
                f"Sampling construtivo não encontrou posição viável para job {job} "
                f"(H={instance.horizon}); nenhuma avaliação foi consumida"
            )
        earliest_end = min(option[0] for option in options)
        tied_options = [option for option in options if option[0] == earliest_end]
        end, machine, mode = tied_options[int(rng.integers(len(tied_options)))]
        machine_jobs[machine].append((job, mode, 0))
        machine_end[machine] = end
        machine_last[machine] = job

    return tuple(tuple(sequence) for sequence in machine_jobs)


class ScheduleProblem(ElementwiseProblem):
    # Uma variável-objeto do pymoo armazena a solução nativa.

    def __init__(self, instance: Instance, trace: SPEA2Trace):
        # Candidatos inválidos são contabilizados e marcados por G.
        super().__init__(n_var=1, n_obj=2, n_ieq_constr=1, vtype=object)
        self.instance = instance
        self.trace = trace

    def _evaluate(self, x, out, *args, **kwargs):
        self.trace.attempts += 1
        try:
            evaluation = evaluate_schedule(self.instance, x[0])
        except ScheduleValidationError:
            self.trace.rejected += 1
            # Com G > 0, o pymoo ignora os objetivos e não os exporta.
            out["F"] = np.array([0.0, 0.0])
            out["G"] = np.array([1.0])
            return
        self.trace.feasible += 1
        out["F"] = np.array([evaluation.cmax, evaluation.tec], dtype=float)
        out["G"] = np.array([-1.0])


class ScheduleSampling(Sampling):
    def _do(self, problem, n_samples, random_state=None, **kwargs):
        rng = random_state if random_state is not None else np.random.default_rng()
        samples = np.empty((n_samples, 1), dtype=object)
        for index in range(n_samples):
            samples[index, 0] = _random_schedule(problem.instance, rng)
        return samples


class ScheduleCrossover(Crossover):
    # Recombina alocação, modos, esperas e posições dos pais.

    def __init__(self, prob: float = 0.9):
        super().__init__(n_parents=2, n_offsprings=1, prob=prob)

    def _do(self, problem, x, random_state=None, **kwargs):
        rng = random_state if random_state is not None else np.random.default_rng()
        offspring = np.empty((1, x.shape[1], 1), dtype=object)
        for mating in range(x.shape[1]):
            parents = [_as_schedule(x[parent, mating, 0]) for parent in range(2)]
            locations = []
            ranks: list[dict[int, int]] = []
            for schedule in parents:
                loc, rank = {}, {}
                for machine, sequence in enumerate(schedule):
                    for position, (job, _, _) in enumerate(sequence):
                        loc[job] = (machine, position)
                        rank[job] = position
                locations.append(loc)
                ranks.append(rank)
            child: list[list[tuple[int, int, int]]] = [[] for _ in range(problem.instance.m)]
            score: dict[int, float] = {}
            for job in range(problem.instance.n):
                source = int(rng.integers(2))
                machine, _ = locations[source][job]
                _, mode, wait = parents[source][machine][locations[source][job][1]]
                child[machine].append((job, mode, wait))
                score[job] = (float(ranks[0][job]) + float(ranks[1][job])
                              + float(rng.random()) * 0.5)
            for sequence in child:
                sequence.sort(key=lambda item: score[item[0]])
            offspring[0, mating, 0] = tuple(tuple(sequence) for sequence in child)
        return offspring


class ScheduleMutation(Mutation):
    # Aplica uma de cinco alterações; soluções inviáveis são rejeitadas.

    def _do(self, problem, x, random_state=None, **kwargs):
        rng = random_state if random_state is not None else np.random.default_rng()
        result = np.empty_like(x, dtype=object)
        instance = problem.instance
        for index, row in enumerate(x):
            original = _as_schedule(row[0])
            changed = [list(sequence) for sequence in original]
            operation = int(rng.integers(5))
            positions = [(machine, pos) for machine, sequence in enumerate(original)
                         for pos in range(len(sequence))]
            if operation == 0 and positions:  # mode
                machine, pos = positions[int(rng.integers(len(positions)))]
                job, mode, wait = changed[machine][pos]
                changed[machine][pos] = (job, (mode + 1 + int(rng.integers(instance.modes - 1)))
                                         % instance.modes if instance.modes > 1 else mode, wait)
            elif operation == 1 and positions:  # wait
                machine, pos = positions[int(rng.integers(len(positions)))]
                job, mode, wait = changed[machine][pos]
                changed[machine][pos] = (job, mode, max(0, wait + int(rng.choice([-3, -1, 1, 3]))))
            elif operation == 2:  # insertion / order
                movable = [(m, a, b) for m, seq in enumerate(original)
                           for a in range(len(seq)) for b in range(len(seq)) if a != b]
                if movable:
                    machine, source, target = movable[int(rng.integers(len(movable)))]
                    item = changed[machine].pop(source)
                    changed[machine].insert(target, item)
            elif operation == 3 and len(positions) >= 2:  # swap, including cross-machine swap
                a, b = rng.choice(len(positions), size=2, replace=False)
                ma, pa = positions[int(a)]
                mb, pb = positions[int(b)]
                changed[ma][pa], changed[mb][pb] = changed[mb][pb], changed[ma][pa]
            elif operation == 4 and instance.m > 1 and positions:  # relocation
                machine, pos = positions[int(rng.integers(len(positions)))]
                target = int(rng.integers(instance.m - 1))
                if target >= machine:
                    target += 1
                item = changed[machine].pop(pos)
                target_pos = int(rng.integers(len(changed[target]) + 1))
                changed[target].insert(target_pos, item)
            result[index, 0] = tuple(tuple(sequence) for sequence in changed)
        return result


@dataclass(slots=True)
class SPEA2Result:
    instance: Instance
    config: SPEA2Config
    front: tuple[ParetoSolution, ...]
    attempts: int
    feasible_evaluations: int
    rejected_evaluations: int
    pymoo_evaluations: int
    post_search_validations: int
    elapsed_seconds: float

    def to_result_dict(self) -> dict:
        return {
            "format_version": 1,
            "algorithm": "SPEA2",
            "method": "spea2_pymoo",
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
            "pymoo_evaluations": self.pymoo_evaluations,
            "post_search_validations": self.post_search_validations,
            "elapsed_seconds": self.elapsed_seconds,
            "points": len(self.front),
            "front": [self._solution_to_result(solution) for solution in self.front],
        }

    def _solution_to_result(self, solution: ParetoSolution) -> dict:
        result = solution.evaluation.to_result_dict(self.instance)
        result["representation"] = [[[job, mode, wait] for job, mode, wait in machine]
                                    for machine in solution.schedule]
        return result


def _final_front(instance: Instance, population) -> tuple[ParetoSolution, ...]:
    # Reavalia os sobreviventes viáveis após o fim do orçamento.
    archive: list[tuple[tuple[int, int], ParetoSolution]] = []
    for individual in population:
        if individual.get("G") is not None and np.any(individual.G > 0):
            continue
        schedule = _as_schedule(individual.X[0])
        evaluation = evaluate_schedule(instance, schedule)
        solution = ParetoSolution(schedule, evaluation)
        insert_pareto(archive, solution.key, solution)
    return tuple(solution for _, solution in archive)


def run_spea2(instance: Instance, config: SPEA2Config = SPEA2Config()) -> SPEA2Result:
    trace = SPEA2Trace()
    problem = ScheduleProblem(instance, trace)
    algorithm = SPEA2(pop_size=config.population_size,
                      n_offsprings=1,
                      sampling=ScheduleSampling(),
                      crossover=ScheduleCrossover(prob=config.crossover_probability),
                      mutation=ScheduleMutation(prob=config.mutation_probability),
                      # A sobrevivência sem normalização evita divisão por zero.
                      survival=SPEA2Survival(normalize=False),
                      eliminate_duplicates=False)
    started = time.monotonic()
    result = minimize(problem, algorithm, termination=("n_eval", config.max_evaluations),
                      seed=config.seed, verbose=False, copy_algorithm=False)
    elapsed = time.monotonic() - started
    # Estas verificações ocorrem após o fim e fora do orçamento de busca.
    post_search_validations = sum(
        1 for individual in result.algorithm.pop
        if individual.get("G") is None or not np.any(individual.G > 0)
    )
    front = _final_front(instance, result.algorithm.pop)
    reported = int(result.algorithm.evaluator.n_eval)
    if trace.attempts != reported or reported > config.max_evaluations:
        raise RuntimeError(f"Contagem de avaliações inconsistente: evaluator={trace.attempts}, "
                           f"pymoo={reported}, orçamento={config.max_evaluations}")
    return SPEA2Result(instance, config, front, trace.attempts, trace.feasible,
                       trace.rejected, reported, post_search_validations, elapsed)


def write_result(result: SPEA2Result, output: Path | str, *, overwrite: bool = False) -> Path:
    path = Path(output)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Resultado já existe: {path}; passe overwrite=True para substituir")
    atomic_json(path, result.to_result_dict())
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path,
                        default=PROJECT_ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/output/spea2")
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
        config = SPEA2Config(args.seed, args.max_evaluations, args.population_size,
                             args.crossover_probability, args.mutation_probability)
    except ValueError as error:
        parser.error(str(error))
    for path in paths:
        instance = read_instance(path)
        result = run_spea2(instance, config)
        output = args.output_dir / f"{path.stem}.json"
        try:
            write_result(result, output, overwrite=args.overwrite)
        except FileExistsError as error:
            parser.error(str(error))
        print(f"{path.name}: tentativas={result.attempts}, viáveis={result.feasible_evaluations}, "
              f"rejeições={result.rejected_evaluations}, pontos={len(result.front)}, "
              f"tempo={result.elapsed_seconds:.3f}s, saída={output}")


if __name__ == "__main__":
    main()
