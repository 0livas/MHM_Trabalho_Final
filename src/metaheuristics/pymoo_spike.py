"""Minimal pymoo integration spike for machine -> [(job, mode, wait), ...].

Run from the repository root:
    python src/metaheuristics/pymoo_spike.py
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
from pymoo.algorithms.moo.moead import MOEAD
from pymoo.algorithms.moo.spea2 import SPEA2
from pymoo.algorithms.moo.spea2 import SPEA2Survival
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.sampling import Sampling
from pymoo.optimize import minimize

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from problem import (  # noqa: E402
    Instance,
    energy_scale,
    generate_choices,
    read_instance,
)
from schedule import (  # noqa: E402
    Schedule,
    ScheduleEvaluation as Evaluation,
    evaluate_schedule,
)

decode_and_evaluate = evaluate_schedule


@dataclass
class SpikeTrace:
    samples: int = 0
    crossovers: int = 0
    mutations: int = 0
    evaluations: int = 0
    survival_calls: int = 0
    replacements: int = 0
    evaluated_f: list[tuple[float, float]] | None = None

    def __post_init__(self):
        if self.evaluated_f is None:
            self.evaluated_f = []


def seed_schedule(instance: Instance) -> Schedule:
    """Deterministic feasible seed for the small fixture; no baseline is read."""
    machines: list[list[tuple[int, int, int]]] = [[] for _ in range(instance.m)]
    for job in range(instance.n):
        machine = job % instance.m
        mode = min(range(instance.modes),
                   key=lambda candidate: instance.duration(job, machine, candidate))
        machines[machine].append((job, mode, 0))
    schedule = tuple(tuple(sequence) for sequence in machines)
    decode_and_evaluate(instance, schedule)
    return schedule


class ScheduleProblem(ElementwiseProblem):
    """A single object-valued variable holds the native schedule structure."""

    def __init__(self, instance: Instance, *, declare_constraint: bool = False,
                 trace: SpikeTrace | None = None):
        super().__init__(n_var=1, n_obj=2,
                         n_ieq_constr=1 if declare_constraint else 0, vtype=object)
        self.instance = instance
        self.trace = trace or SpikeTrace()

    def _evaluate(self, x, out, *args, **kwargs):
        evaluation = decode_and_evaluate(self.instance, x[0])
        out["F"] = np.array([evaluation.cmax, evaluation.tec], dtype=float)
        self.trace.evaluations += 1
        self.trace.evaluated_f.append((float(evaluation.cmax), evaluation.tec))


class ScheduleSampling(Sampling):
    def __init__(self, trace: SpikeTrace | None = None):
        super().__init__()
        self.trace = trace

    def _do(self, problem, n_samples, **kwargs):
        if self.trace is not None:
            self.trace.samples += n_samples
        samples = np.empty((n_samples, 1), dtype=object)
        seed = seed_schedule(problem.instance)
        for index in range(n_samples):
            candidate = [list(sequence) for sequence in seed]
            if index > 0:
                job = (index - 1) % problem.instance.n
                for sequence in candidate:
                    for position, (current_job, mode, wait) in enumerate(sequence):
                        if current_job == job:
                            alternate_mode = (mode + 1) % problem.instance.modes
                            sequence[position] = (current_job, alternate_mode, wait)
                            break
            schedule = tuple(tuple(sequence) for sequence in candidate)
            try:
                decode_and_evaluate(problem.instance, schedule)
            except ValueError:
                schedule = seed
            samples[index, 0] = deepcopy(schedule)
        return samples


class CopyCrossover(Crossover):
    """Keep one parent's schedule intact; mutation supplies the variation."""

    def __init__(self, trace: SpikeTrace | None = None):
        super().__init__(n_parents=2, n_offsprings=1)
        self.trace = trace

    def _do(self, problem, x, **kwargs):
        if self.trace is not None:
            self.trace.crossovers += x.shape[1]
        offspring = np.empty((1, x.shape[1], 1), dtype=object)
        for mating in range(x.shape[1]):
            offspring[0, mating, 0] = deepcopy(x[0, mating, 0])
        return offspring


class SwapWithinMachine(Mutation):
    """Swap two operations on a machine; reject swaps outside horizon."""

    def __init__(self, trace: SpikeTrace | None = None):
        super().__init__()
        self.trace = trace

    def _do(self, problem, x, random_state=None, **kwargs):
        if self.trace is not None:
            self.trace.mutations += len(x)
        result = np.empty_like(x, dtype=object)
        rng = random_state if random_state is not None else np.random.default_rng()
        for index, row in enumerate(x):
            original = row[0]
            child = original
            moves = [(machine, a, b)
                     for machine, sequence in enumerate(original)
                     for a in range(len(sequence))
                     for b in range(a + 1, len(sequence))]
            for move_index in rng.permutation(len(moves)):
                machine, a, b = moves[int(move_index)]
                changed = [list(sequence) for sequence in original]
                changed[machine][a], changed[machine][b] = changed[machine][b], changed[machine][a]
                candidate = tuple(tuple(sequence) for sequence in changed)
                try:
                    decode_and_evaluate(problem.instance, candidate)
                except ValueError:
                    continue
                child = candidate
                break
            result[index, 0] = deepcopy(child)
        return result


def validate_population_flow(instance: Instance) -> tuple[Schedule, Evaluation, Schedule, Evaluation]:
    trace = SpikeTrace()
    problem = ScheduleProblem(instance, trace=trace)
    sampling = ScheduleSampling(trace)
    mutation = SwapWithinMachine(trace)
    population = sampling.do(problem, 1)
    population.set("F", problem.evaluate(population.get("X"), return_values_of=["F"]))
    before = deepcopy(population[0].X[0])

    offspring = mutation.do(problem, deepcopy(population), random_state=np.random.default_rng(1))
    offspring.set("F", problem.evaluate(offspring.get("X"), return_values_of=["F"]))
    after = offspring[0].X[0]
    assert after != before, "Mutation should generate a distinct valid schedule on this fixture"
    before_eval = decode_and_evaluate(instance, before)
    after_eval = decode_and_evaluate(instance, after)
    assert sorted(job for machine in after for job, _, _ in machine) == list(range(instance.n))
    assert all(0 <= mode < instance.modes and wait >= 0
               for machine in after for _, mode, wait in machine)
    np.testing.assert_allclose(offspring[0].F, [after_eval.cmax, after_eval.tec])
    assert trace.samples == 1 and trace.mutations == 1 and trace.evaluations == 2
    return before, before_eval, after, after_eval


def check_algorithm_compatibility(problem: ScheduleProblem) -> dict[str, str]:
    sampling = ScheduleSampling()
    crossover = CopyCrossover()
    mutation = SwapWithinMachine()
    spea2 = SPEA2(pop_size=4, sampling=sampling, crossover=crossover, mutation=mutation)
    moead = MOEAD(
        ref_dirs=np.array([[1.0, 0.0], [0.67, 0.33], [0.33, 0.67], [0.0, 1.0]]),
        n_neighbors=2,
        sampling=sampling,
        crossover=crossover,
        mutation=mutation,
    )
    # MOEA/D's setup explicitly rejects declared constraints. Rejection in the
    # sampling/variation/evaluator boundary keeps this prototype unconstrained.
    spea2.setup(problem, termination=("n_gen", 1), seed=1, verbose=False)
    moead.setup(problem, termination=("n_gen", 1), seed=1, verbose=False)
    constrained_problem = ScheduleProblem(problem.instance, declare_constraint=True)
    constrained_moead = MOEAD(
        ref_dirs=np.array([[1.0, 0.0], [0.67, 0.33], [0.33, 0.67], [0.0, 1.0]]),
        n_neighbors=2,
        sampling=sampling,
        crossover=crossover,
        mutation=mutation,
    )
    try:
        constrained_moead.setup(constrained_problem, seed=1, verbose=False)
    except AssertionError as error:
        moead_constraint_limit = str(error)
    else:
        raise AssertionError("Expected pymoo MOEA/D to reject declared constraints")
    return {"SPEA2": type(spea2).__name__, "MOEA/D": type(moead).__name__,
            "MOEA/D_constraints": moead_constraint_limit}


class TracingSPEA2Survival(SPEA2Survival):
    """Count SPEA2 environmental survival calls during the one-generation spike."""

    def __init__(self, trace: SpikeTrace):
        super().__init__(normalize=True)
        self.trace = trace

    def _do(self, problem, pop, *args, **kwargs):
        self.trace.survival_calls += 1
        return super()._do(problem, pop, *args, **kwargs)


class TracingMOEAD(MOEAD):
    """Count MOEA/D neighborhood replacements during its reproduction sweep."""

    def __init__(self, trace: SpikeTrace, **kwargs):
        super().__init__(**kwargs)
        self.trace = trace

    def _replace(self, k, off):
        self.trace.replacements += 1
        return super()._replace(k, off)


def run_real_cycle(name: str, instance: Instance) -> tuple[SpikeTrace, int, int]:
    """Run initialization plus one real reproduction/survival generation."""
    trace = SpikeTrace()
    problem = ScheduleProblem(instance, trace=trace)
    sampling = ScheduleSampling(trace)
    crossover = CopyCrossover(trace)
    mutation = SwapWithinMachine(trace)

    if name == "SPEA2":
        algorithm = SPEA2(
            pop_size=4,
            n_offsprings=4,
            sampling=sampling,
            crossover=crossover,
            mutation=mutation,
            survival=TracingSPEA2Survival(trace),
            eliminate_duplicates=False,
        )
    elif name == "MOEA/D":
        algorithm = TracingMOEAD(
            trace,
            ref_dirs=np.array([[1.0, 0.0], [0.67, 0.33], [0.33, 0.67], [0.0, 1.0]]),
            n_neighbors=2,
            sampling=sampling,
            crossover=crossover,
            mutation=mutation,
        )
    else:
        raise ValueError(name)

    result = minimize(problem, algorithm, termination=("n_gen", 2), seed=23,
                      verbose=False, copy_algorithm=False)
    final_population = result.algorithm.pop
    assert len(final_population) == 4
    for individual in final_population:
        schedule = individual.X[0]
        evaluation = decode_and_evaluate(instance, schedule)
        np.testing.assert_allclose(individual.F, [evaluation.cmax, evaluation.tec])

    assert trace.samples == 4, (name, "initial sampling", trace.samples)
    assert trace.crossovers > 0, (name, "crossover", trace.crossovers)
    assert trace.mutations > 0, (name, "mutation", trace.mutations)
    assert trace.evaluations > trace.samples, (name, "offspring evaluation", trace.evaluations)
    if name == "SPEA2":
        assert trace.survival_calls >= 2, (name, "survival", trace.survival_calls)
    else:
        assert trace.replacements > 0, (name, "MOEA/D replacement", trace.replacements)
    return trace, result.algorithm.n_gen, len(final_population)


def verify_cost_against_existing_choices(instance: Instance, schedule: Schedule,
                                         evaluation: Evaluation) -> None:
    """Cross-check the shared interval cost against exact-method Choice tables."""
    scale, prices = energy_scale(instance)
    by_job = generate_choices(instance, prices)
    exact_units = 0
    for machine, sequence in enumerate(schedule):
        previous_end = 0
        previous_job = None
        for job, mode, wait in sequence:
            start = previous_end + (instance.setup[machine][previous_job][job]
                                    if previous_job is not None else 0) + wait
            choice = next(choice for choice in by_job[job]
                          if (choice.machine, choice.mode, choice.start) == (machine, mode, start))
            exact_units += choice.cost_units
            previous_end = choice.end
            previous_job = job
    assert evaluation.tec_scale == scale and evaluation.tec_units == exact_units


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", nargs="?", default="data/input/set1/6_2_1439_3_S_1-9.dat")
    args = parser.parse_args(argv)
    instance = read_instance(ROOT / args.instance)
    before, before_eval, after, after_eval = validate_population_flow(instance)
    verify_cost_against_existing_choices(instance, before, before_eval)
    verify_cost_against_existing_choices(instance, after, after_eval)
    compatibility = check_algorithm_compatibility(ScheduleProblem(instance))
    real_cycles = {name: run_real_cycle(name, instance) for name in ("SPEA2", "MOEA/D")}

    # A malformed wait-independent overrun is explicitly refused by the decoder.
    valid_seed = seed_schedule(instance)
    invalid_machines = [list(sequence) for sequence in valid_seed]
    job, mode, wait = invalid_machines[0][0]
    invalid_machines[0][0] = (job, mode, wait + instance.horizon)
    overrun = tuple(tuple(sequence) for sequence in invalid_machines)
    try:
        decode_and_evaluate(instance, overrun)
    except ValueError as error:
        rejection = str(error)
    else:
        raise AssertionError("Expected an over-horizon schedule to be rejected")

    print(f"pymoo={__import__('pymoo').__version__}; instance={instance.path.name}")
    print(f"seed F=(Cmax={before_eval.cmax}, TEC={before_eval.tec:.9f}); schedule={before}")
    print(f"offspring F=(Cmax={after_eval.cmax}, TEC={after_eval.tec:.9f}); schedule={after}")
    print(f"pymoo offspring F={validate_population_f_values(after, instance)}")
    print(f"algorithms setup OK: {compatibility}")
    print(f"over-horizon policy: rejected ({rejection})")
    print(f"exact TEC seed={before_eval.tec_units}/{before_eval.tec_scale}; "
          f"offspring={after_eval.tec_units}/{after_eval.tec_scale}")
    print("TEC matches src/problem.py generate_choices for both schedules")
    for name, (trace, generations, population_size) in real_cycles.items():
        print(f"{name} real cycle: generations={generations}, population={population_size}, "
              f"samples={trace.samples}, crossover={trace.crossovers}, "
              f"mutation={trace.mutations}, evaluations={trace.evaluations}, "
              f"survival={trace.survival_calls}, replacements={trace.replacements}, "
              f"offspring_F={trace.evaluated_f[trace.samples:]}")
    return 0


def validate_population_f_values(schedule: Schedule, instance: Instance) -> list[float]:
    evaluation = decode_and_evaluate(instance, schedule)
    return [float(evaluation.cmax), evaluation.tec]


if __name__ == "__main__":
    raise SystemExit(main())
