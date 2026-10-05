"""Manual multiobjective VNS with VND for machine-sequence schedules.

Run a small experiment from the repository root with::

    python src/metaheuristics/vns_vnd.py data/input/set1/6_2_1439_3_S_1-9.dat \
        --max-evaluations 500 --seed 1
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from problem import PROJECT_ROOT, Instance, atomic_json, dominates, insert_pareto, read_instance  # noqa: E402
from schedule import (  # noqa: E402
    Schedule,
    ScheduleEvaluation,
    ScheduleValidationError,
    evaluate_schedule,
)


NEIGHBORHOODS = ("N1_mode", "N2_wait", "N3_insert", "N4_relocate", "N5_swap")


@dataclass(frozen=True, slots=True)
class VNSConfig:
    seed: int = 1
    max_evaluations: int = 10_000
    initial_solutions: int = 4
    max_candidates_per_neighborhood: int = 100
    shaking_attempts: int = 20

    def __post_init__(self):
        if self.max_evaluations < 1:
            raise ValueError("max_evaluations deve ser positivo")
        if self.initial_solutions < 1:
            raise ValueError("initial_solutions deve ser positivo")
        if self.max_candidates_per_neighborhood < 1:
            raise ValueError("max_candidates_per_neighborhood deve ser positivo")
        if self.shaking_attempts < 1:
            raise ValueError("shaking_attempts deve ser positivo")
        if self.initial_solutions > self.max_evaluations:
            raise ValueError("initial_solutions não pode exceder max_evaluations")

    def as_dict(self) -> dict[str, int]:
        return {
            "seed": self.seed,
            "max_evaluations": self.max_evaluations,
            "initial_solutions": self.initial_solutions,
            "max_candidates_per_neighborhood": self.max_candidates_per_neighborhood,
            "shaking_attempts": self.shaking_attempts,
        }


@dataclass(frozen=True, slots=True)
class ParetoSolution:
    schedule: Schedule
    evaluation: ScheduleEvaluation

    @property
    def key(self) -> tuple[int, int]:
        return self.evaluation.objective_key


@dataclass(slots=True)
class VNSResult:
    instance: Instance
    config: VNSConfig
    front: tuple[ParetoSolution, ...]
    evaluations: int
    feasible_evaluations: int
    rejected_evaluations: int
    elapsed_seconds: float
    stop_reason: str
    explored_origins: dict[tuple[int, int], int]
    trace: tuple[dict, ...] = field(default_factory=tuple)

    def to_result_dict(self) -> dict:
        return {
            "format_version": 1,
            "algorithm": "VNS/VND multiobjetivo",
            "method": "vns_vnd",
            "instance": self.instance.path.name,
            "instance_sha256": self.instance.digest,
            "status": self.stop_reason,
            "stop_reason": self.stop_reason,
            "pareto_proven": False,
            "horizon": self.instance.horizon,
            "cost_scale": self.front[0].evaluation.tec_scale if self.front else None,
            "run_parameters": self.config.as_dict(),
            "evaluations": self.evaluations,
            "feasible_evaluations": self.feasible_evaluations,
            "rejected_evaluations": self.rejected_evaluations,
            "elapsed_seconds": self.elapsed_seconds,
            "origin_selection_counts": [
                {"objective_key": list(point), "selections": count}
                for point, count in sorted(self.explored_origins.items())
            ],
            "points": len(self.front),
            "front": [self._solution_to_result(solution) for solution in self.front],
        }

    def _solution_to_result(self, solution: ParetoSolution) -> dict:
        result = solution.evaluation.to_result_dict(self.instance)
        result["representation"] = [
            [[job, mode, wait] for job, mode, wait in machine]
            for machine in solution.schedule
        ]
        return result


def _random_greedy_schedule(instance: Instance, rng: random.Random) -> Schedule | None:
    """Construct an earliest-start schedule using randomized feasible extensions."""
    machine_jobs: list[list[tuple[int, int, int]]] = [[] for _ in range(instance.m)]
    machine_end = [0] * instance.m
    machine_last: list[int | None] = [None] * instance.m
    jobs = list(range(instance.n))
    rng.shuffle(jobs)
    for job in jobs:
        options: list[tuple[int, int, int]] = []
        for machine in range(instance.m):
            previous = machine_last[machine]
            setup = instance.setup[machine][previous][job] if previous is not None else 0
            start = machine_end[machine] + setup
            for mode in range(instance.modes):
                if start + instance.duration(job, machine, mode) <= instance.horizon:
                    options.append((machine, mode, start))
        if not options:
            return None
        machine, mode, _ = rng.choice(options)
        previous = machine_last[machine]
        wait = 0
        end = machine_end[machine]
        if previous is not None:
            end += instance.setup[machine][previous][job]
        end += instance.duration(job, machine, mode)
        machine_jobs[machine].append((job, mode, wait))
        machine_end[machine] = end
        machine_last[machine] = job
    return tuple(tuple(sequence) for sequence in machine_jobs)


def _sample_ranks(total: int, limit: int, rng: random.Random) -> list[int]:
    if total <= 0:
        return []
    count = min(total, limit)
    if count == total:
        return list(range(total))
    return rng.sample(range(total), count)


def _wait_moves(instance: Instance, schedule: Schedule) -> list[tuple[int, int, int]]:
    """Return unique (machine, position, new_wait) moves at tariff boundaries."""
    boundaries = {0, instance.horizon}
    for day in range(instance.days):
        boundaries.add(day * instance.slots_per_day)
        boundaries.add((day + 1) * instance.slots_per_day)
    for start, end in instance.peaks:
        boundaries.update((start, end))
    moves: set[tuple[int, int, int]] = set()
    for machine, sequence in enumerate(schedule):
        previous_job: int | None = None
        previous_end = 0
        for position, (job, mode, current_wait) in enumerate(sequence):
            setup = instance.setup[machine][previous_job][job] if previous_job is not None else 0
            earliest = previous_end + setup
            duration = instance.duration(job, machine, mode)
            waits = {0, max(0, current_wait - 1), current_wait + 1}
            for boundary in boundaries:
                for target_start in (boundary, boundary - duration):
                    for offset in (-1, 0, 1):
                        waits.add(target_start + offset - earliest)
            for wait in waits:
                if wait >= 0 and wait != current_wait:
                    moves.add((machine, position, wait))
            previous_end = earliest + current_wait + duration
            previous_job = job
    return sorted(moves)


def _candidate_schedules(instance: Instance, schedule: Schedule, neighborhood: int,
                         rng: random.Random, limit: int) -> Iterable[Schedule]:
    """Yield up to `limit` distinct movements without building quadratic lists."""
    mutable = [list(sequence) for sequence in schedule]
    if neighborhood == 0:  # N1 mode
        moves = [(machine, position, mode)
                 for machine, sequence in enumerate(schedule)
                 for position, (job, current_mode, _) in enumerate(sequence)
                 for mode in range(instance.modes) if mode != current_mode]
        for machine, position, mode in (moves[i] for i in _sample_ranks(len(moves), limit, rng)):
            changed = [list(sequence) for sequence in mutable]
            job, _, wait = changed[machine][position]
            changed[machine][position] = (job, mode, wait)
            yield tuple(tuple(sequence) for sequence in changed)
        return

    if neighborhood == 1:  # N2 wait at relevant tariff boundaries
        moves = _wait_moves(instance, schedule)
        for machine, position, wait in (moves[i] for i in _sample_ranks(len(moves), limit, rng)):
            changed = [list(sequence) for sequence in mutable]
            job, mode, _ = changed[machine][position]
            changed[machine][position] = (job, mode, wait)
            yield tuple(tuple(sequence) for sequence in changed)
        return

    if neighborhood == 2:  # N3 insertion within one machine
        total = sum(_insertion_count(sequence) for sequence in schedule)
        for rank in _sample_ranks(total, limit, rng):
            offset = rank
            for machine, sequence in enumerate(schedule):
                count = _insertion_count(sequence)
                if offset >= count:
                    offset -= count
                    continue
                source = 0
                while True:
                    source_count = len(sequence) - 1 if source == 0 else len(sequence) - 2
                    if offset < source_count:
                        break
                    offset -= source_count
                    source += 1
                target_code = offset
                if source > 0 and target_code >= source - 1:
                    target_code += 1
                target = target_code if target_code < source else target_code + 1
                changed = [list(row) for row in mutable]
                item = changed[machine].pop(source)
                changed[machine].insert(target, item)
                yield tuple(tuple(row) for row in changed)
                break
        return

    if neighborhood == 3:  # N4 relocation to another machine
        total = sum(len(schedule[source]) * (len(schedule[target]) + 1)
                    for source in range(instance.m) for target in range(instance.m)
                    if source != target)
        for rank in _sample_ranks(total, limit, rng):
            offset = rank
            for source in range(instance.m):
                for position, _ in enumerate(schedule[source]):
                    for target in range(instance.m):
                        if source == target:
                            continue
                        target_positions = len(schedule[target]) + 1
                        if offset >= target_positions:
                            offset -= target_positions
                            continue
                        changed = [list(row) for row in mutable]
                        item = changed[source].pop(position)
                        changed[target].insert(offset, item)
                        yield tuple(tuple(row) for row in changed)
                        break
                    else:
                        continue
                    break
                else:
                    continue
                break
        return

    if neighborhood == 4:  # N5 any pair, intra- or inter-machine
        total_jobs = instance.n
        total = total_jobs * (total_jobs - 1) // 2
        positions = [(machine, position) for machine, sequence in enumerate(schedule)
                     for position in range(len(sequence))]
        for rank in _sample_ranks(total, limit, rng):
            offset = rank
            first = 0
            while offset >= total_jobs - first - 1:
                offset -= total_jobs - first - 1
                first += 1
            second = first + 1 + offset
            changed = [list(row) for row in mutable]
            machine_a, position_a = positions[first]
            machine_b, position_b = positions[second]
            changed[machine_a][position_a], changed[machine_b][position_b] = (
                changed[machine_b][position_b], changed[machine_a][position_a])
            yield tuple(tuple(row) for row in changed)
        return

    raise ValueError(f"Índice de vizinhança inválido: {neighborhood}")


class VNSVND:
    """Budgeted, reproducible VNS/VND runner backed by the shared evaluator."""

    def __init__(self, instance: Instance, config: VNSConfig):
        self.instance = instance
        self.config = config
        self.rng = random.Random(config.seed)
        self.archive: list[tuple[tuple[int, int], ParetoSolution]] = []
        self.evaluations = 0
        self.feasible_evaluations = 0
        self.rejected_evaluations = 0
        self.explored_origins: dict[tuple[int, int], int] = {}
        self.trace: list[dict] = []
        self.started = 0.0

    def _evaluate(self, schedule: Schedule) -> ParetoSolution | None:
        if self.evaluations >= self.config.max_evaluations:
            return None
        self.evaluations += 1
        try:
            evaluation = evaluate_schedule(self.instance, schedule)
        except ScheduleValidationError as error:
            self.rejected_evaluations += 1
            self.trace.append({"event": "rejected", "reason": str(error)})
            return None
        self.feasible_evaluations += 1
        normalized = tuple(tuple(tuple(item) for item in machine) for machine in schedule)
        solution = ParetoSolution(normalized, evaluation)
        added = insert_pareto(self.archive, solution.key, solution)
        self.trace.append({"event": "evaluation", "key": list(solution.key),
                           "archive_inserted": added})
        return solution

    def _origin(self) -> ParetoSolution:
        if not self.archive:
            raise RuntimeError("Arquivo Pareto vazio: não existe solução viável para explorar")
        minimum = min(self.explored_origins.get(point, 0) for point, _ in self.archive)
        least_explored = [entry for entry in self.archive
                          if self.explored_origins.get(entry[0], 0) == minimum]
        point, solution = self.rng.choice(least_explored)
        self.explored_origins[point] = self.explored_origins.get(point, 0) + 1
        self.trace.append({"event": "origin", "key": list(point),
                           "selection_count": self.explored_origins[point]})
        return solution

    def _vnd(self, initial: ParetoSolution) -> tuple[ParetoSolution, bool]:
        current = initial
        archive_expanded = False
        neighborhood = 0
        while neighborhood < len(NEIGHBORHOODS) and self.evaluations < self.config.max_evaluations:
            self.trace.append({"event": "vnd_neighborhood", "name": NEIGHBORHOODS[neighborhood],
                               "current": list(current.key)})
            improved = False
            for candidate_schedule in _candidate_schedules(
                    self.instance, current.schedule, neighborhood, self.rng,
                    self.config.max_candidates_per_neighborhood):
                if self.evaluations >= self.config.max_evaluations:
                    break
                candidate = self._evaluate(candidate_schedule)
                if candidate is None:
                    continue
                # _evaluate() records insertion explicitly; look at its latest trace event.
                archive_expanded |= self.trace[-1].get("archive_inserted", False)
                if dominates(candidate.key, current.key):
                    self.trace.append({"event": "vnd_accept", "from": list(current.key),
                                       "to": list(candidate.key), "restart": "N1"})
                    current = candidate
                    neighborhood = 0
                    improved = True
                    break
            if improved:
                continue
            neighborhood += 1
        return current, archive_expanded

    def _shake(self, origin: ParetoSolution, neighborhood: int) -> tuple[ParetoSolution | None, bool]:
        total = _movement_count(self.instance, origin.schedule, neighborhood)
        if total == 0:
            self.trace.append({"event": "shake_failed", "name": NEIGHBORHOODS[neighborhood],
                               "reason": "empty_neighborhood"})
            return None, False
        ranks = self.rng.sample(range(total), min(total, self.config.shaking_attempts))
        for rank in ranks:
            if self.evaluations >= self.config.max_evaluations:
                return None, False
            candidate_schedule = _candidate_at_rank(self.instance, origin.schedule,
                                                    neighborhood, rank)
            candidate = self._evaluate(candidate_schedule)
            if candidate is not None:
                inserted = self.trace[-1].get("archive_inserted", False)
                self.trace.append({"event": "shake_success", "name": NEIGHBORHOODS[neighborhood],
                                   "key": list(candidate.key)})
                return candidate, inserted
        self.trace.append({"event": "shake_failed", "name": NEIGHBORHOODS[neighborhood],
                           "reason": "no_feasible_move"})
        return None, False

    def run(self, initial_schedules: Iterable[Schedule] | None = None) -> VNSResult:
        self.started = time.monotonic()
        stop_reason = "budget_reached"
        if initial_schedules is None:
            seeds: list[Schedule] = []
            attempts = 0
            max_construction_attempts = max(20, self.config.initial_solutions * 50)
            while (len(seeds) < self.config.initial_solutions
                   and attempts < max_construction_attempts):
                attempts += 1
                candidate = _random_greedy_schedule(self.instance, self.rng)
                if candidate is not None:
                    seeds.append(candidate)
            if not seeds:
                raise RuntimeError("Inicialização aleatória não encontrou schedule completo")
        else:
            seeds = list(initial_schedules)
            if not seeds:
                raise ValueError("initial_schedules não pode ser vazio")
            if len(seeds) > self.config.max_evaluations:
                raise ValueError("Há mais schedules iniciais que o orçamento de avaliações")

        for schedule in seeds:
            if self.evaluations >= self.config.max_evaluations:
                break
            self._evaluate(schedule)
        if not self.archive:
            raise RuntimeError("Inicialização não produziu nenhum schedule viável")

        while self.evaluations < self.config.max_evaluations:
            origin = self._origin()
            sweep_start_evaluations = self.evaluations
            neighborhood = 0
            while neighborhood < len(NEIGHBORHOODS) and self.evaluations < self.config.max_evaluations:
                self.trace.append({"event": "shake_neighborhood", "name": NEIGHBORHOODS[neighborhood],
                                   "origin": list(origin.key)})
                shaken, expanded = self._shake(origin, neighborhood)
                if shaken is None:
                    neighborhood += 1
                    continue
                _, vnd_expanded = self._vnd(shaken)
                expanded |= vnd_expanded
                if expanded:
                    self.trace.append({"event": "archive_expansion", "restart": "N1"})
                    neighborhood = 0
                else:
                    neighborhood += 1
            # Empty movement families consume no evaluation budget. Stop if an
            # entire five-neighborhood sweep had no evaluable candidate, avoiding
            # an infinite loop on degenerate instances (for example n=1, modes=1).
            if self.evaluations == sweep_start_evaluations:
                self.trace.append({"event": "stop", "reason": "no_evaluable_moves"})
                stop_reason = "no_evaluable_moves"
                break

        elapsed = time.monotonic() - self.started
        return VNSResult(
            self.instance, self.config,
            tuple(solution for _, solution in self.archive),
            self.evaluations, self.feasible_evaluations, self.rejected_evaluations,
            elapsed, stop_reason, dict(self.explored_origins), tuple(self.trace),
        )


def _movement_count(instance: Instance, schedule: Schedule, neighborhood: int) -> int:
    if neighborhood == 0:
        return sum(sum(mode != current_mode for mode in range(instance.modes))
                   for sequence in schedule for _, current_mode, _ in sequence)
    if neighborhood == 1:
        return len(_wait_moves(instance, schedule))
    if neighborhood == 2:
        return sum(_insertion_count(sequence) for sequence in schedule)
    if neighborhood == 3:
        return sum(len(schedule[source]) * (len(schedule[target]) + 1)
                   for source in range(instance.m) for target in range(instance.m)
                   if source != target)
    if neighborhood == 4:
        return instance.n * (instance.n - 1) // 2
    raise ValueError(f"Índice de vizinhança inválido: {neighborhood}")


def _insertion_count(sequence: Sequence) -> int:
    """Unique nontrivial insertions; empty/singleton sequences have none."""
    movable = len(sequence) - 1
    return movable * movable if movable > 0 else 0


def _candidate_at_rank(instance: Instance, schedule: Schedule, neighborhood: int,
                       rank: int) -> Schedule:
    """Apply one movement by its rank; used by shaking's bounded random sample."""
    total = _movement_count(instance, schedule, neighborhood)
    if not 0 <= rank < total:
        raise IndexError(f"Movimento {rank} fora da vizinhança {NEIGHBORHOODS[neighborhood]}")
    changed = [list(sequence) for sequence in schedule]
    if neighborhood == 0:
        for machine, sequence in enumerate(schedule):
            for position, (job, current_mode, wait) in enumerate(sequence):
                for mode in range(instance.modes):
                    if mode == current_mode:
                        continue
                    if rank == 0:
                        changed[machine][position] = (job, mode, wait)
                        return tuple(tuple(row) for row in changed)
                    rank -= 1
    elif neighborhood == 1:
        machine, position, wait = _wait_moves(instance, schedule)[rank]
        job, mode, _ = changed[machine][position]
        changed[machine][position] = (job, mode, wait)
        return tuple(tuple(row) for row in changed)
    elif neighborhood == 2:
        for machine, sequence in enumerate(schedule):
            count = _insertion_count(sequence)
            if rank >= count:
                rank -= count
                continue
            source = 0
            while True:
                source_count = len(sequence) - 1 if source == 0 else len(sequence) - 2
                if rank < source_count:
                    break
                rank -= source_count
                source += 1
            target_code = rank
            if source > 0 and target_code >= source - 1:
                target_code += 1
            target = target_code if target_code < source else target_code + 1
            item = changed[machine].pop(source)
            changed[machine].insert(target, item)
            return tuple(tuple(row) for row in changed)
    elif neighborhood == 3:
        for source in range(instance.m):
            for position in range(len(schedule[source])):
                for target in range(instance.m):
                    if source == target:
                        continue
                    positions = len(schedule[target]) + 1
                    if rank >= positions:
                        rank -= positions
                        continue
                    item = changed[source].pop(position)
                    changed[target].insert(rank, item)
                    return tuple(tuple(row) for row in changed)
    elif neighborhood == 4:
        total_jobs = instance.n
        first = 0
        while rank >= total_jobs - first - 1:
            rank -= total_jobs - first - 1
            first += 1
        second = first + 1 + rank
        positions = [(machine, position) for machine, sequence in enumerate(schedule)
                     for position in range(len(sequence))]
        machine_a, position_a = positions[first]
        machine_b, position_b = positions[second]
        changed[machine_a][position_a], changed[machine_b][position_b] = (
            changed[machine_b][position_b], changed[machine_a][position_a])
        return tuple(tuple(row) for row in changed)
    raise IndexError(f"Movimento {rank} fora da vizinhança {NEIGHBORHOODS[neighborhood]}")


def write_result(result: VNSResult, output: Path | str, *, overwrite: bool = False) -> Path:
    path = Path(output)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Resultado já existe: {path}; passe overwrite=True para substituir")
    atomic_json(path, result.to_result_dict())
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path,
                        default=PROJECT_ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/output/vns_vnd")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-evaluations", type=int, default=10_000)
    parser.add_argument("--initial-solutions", type=int, default=4)
    parser.add_argument("--max-candidates-per-neighborhood", type=int, default=100)
    parser.add_argument("--shaking-attempts", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    paths = sorted(args.input.glob("*.dat")) if args.input.is_dir() else [args.input]
    if not paths:
        parser.error("Nenhuma instância encontrada")
    config = VNSConfig(args.seed, args.max_evaluations, args.initial_solutions,
                       args.max_candidates_per_neighborhood, args.shaking_attempts)
    for path in paths:
        instance = read_instance(path)
        output = args.output_dir / f"{path.stem}.json"
        result = VNSVND(instance, config).run()
        try:
            write_result(result, output, overwrite=args.overwrite)
        except FileExistsError as error:
            parser.error(str(error))
        print(f"{path.name}: avaliações={result.evaluations}, pontos={len(result.front)}, "
              f"tempo={result.elapsed_seconds:.3f}s, saída={output}")


if __name__ == "__main__":
    main()
