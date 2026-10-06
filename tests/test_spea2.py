from __future__ import annotations

from pathlib import Path
import sys
import unittest
import warnings
from unittest.mock import patch

import numpy as np
from pymoo.algorithms.moo.spea2 import SPEA2Survival, spea_binary_tournament
from pymoo.core.population import Population
from pymoo.core.problem import Problem

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from problem import dominates, read_instance  # noqa: E402
from schedule import ScheduleValidationError, evaluate_schedule  # noqa: E402
from metaheuristics.spea2 import (  # noqa: E402
    SPEA2Config,
    SPEA2Trace,
    ScheduleCrossover,
    ScheduleMutation,
    ScheduleProblem,
    ScheduleSampling,
    _final_front,
    _random_schedule,
    run_spea2,
)

import pymoo.algorithms.moo.spea2 as pymoo_spea2_module  # noqa: E402


class SPEA2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance = read_instance(ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")

    def test_sampling_returns_complete_feasible_schedules(self):
        problem = ScheduleProblem(self.instance, SPEA2Trace())
        samples = ScheduleSampling().do(problem, 8, random_state=np.random.default_rng(21))
        self.assertEqual(samples.get("X").shape, (8, 1))
        for row in samples.get("X"):
            schedule = row[0]
            evaluation = evaluate_schedule(self.instance, schedule)
            self.assertEqual(sorted(job for machine in schedule for job, _, _ in machine),
                             list(range(self.instance.n)))
            self.assertTrue(all(wait >= 0 for seq in schedule for _, _, wait in seq))
            self.assertIsNotNone(evaluation)

    def test_sampling_does_not_call_complete_evaluator(self):
        problem = ScheduleProblem(self.instance, SPEA2Trace())
        with patch("metaheuristics.spea2.evaluate_schedule",
                   side_effect=AssertionError("sampling called full evaluator")):
            samples = ScheduleSampling().do(problem, 4, random_state=np.random.default_rng(6))
        self.assertEqual(len(samples), 4)

    def test_32_small_instance_samples_vary_structurally_and_by_mode(self):
        problem = ScheduleProblem(self.instance, SPEA2Trace())
        samples = ScheduleSampling().do(
            problem, 32, random_state=np.random.default_rng(1)).get("X")
        schedules = [row[0] for row in samples]
        allocations = {
            tuple(next(machine for machine, seq in enumerate(schedule)
                       if any(job == target for job, _, _ in seq))
                  for target in range(self.instance.n))
            for schedule in schedules
        }
        orders = {tuple(tuple(job for job, _, _ in seq) for seq in schedule)
                  for schedule in schedules}
        mode_patterns = {tuple(tuple((job, mode) for job, mode, _ in seq)
                               for seq in schedule) for schedule in schedules}
        self.assertGreater(len(mode_patterns), 1)
        self.assertGreater(len(allocations), 1)
        self.assertGreater(len(orders), 1)

    def test_total_full_evaluator_calls_during_search_equal_budget(self):
        result_holder = {}

        def capture_before_final_front(instance, population):
            result_holder["search_evaluator_calls"] = full_evaluator.call_count
            return _final_front(instance, population)

        with patch("metaheuristics.spea2.evaluate_schedule",
                   wraps=evaluate_schedule) as full_evaluator, \
                patch("metaheuristics.spea2._final_front",
                      side_effect=capture_before_final_front):
            result = run_spea2(self.instance, SPEA2Config(
                seed=1, max_evaluations=40, population_size=8))
        self.assertEqual(result_holder["search_evaluator_calls"], 40)
        self.assertEqual(result.attempts, 40)
        self.assertEqual(result.pymoo_evaluations, 40)
        # Independent final-front re-evaluations happen after the search cap.
        self.assertEqual(full_evaluator.call_count,
                         result.attempts + result.post_search_validations)

    def test_population_initialization_can_consume_entire_budget(self):
        result = run_spea2(self.instance, SPEA2Config(
            seed=3, max_evaluations=8, population_size=8))
        self.assertEqual(result.attempts, 8)
        self.assertEqual(result.pymoo_evaluations, 8)

    def test_spea2_survival_values_are_finite_for_constant_objective_axes(self):
        cases = {
            "constant_cmax": [(97, value) for value in (10, 20, 30, 40, 50, 60, 70, 80)],
            "constant_tec": [(value, 100) for value in (10, 20, 30, 40, 50, 60, 70, 80)],
            "both_constant": [(97, 100)] * 8,
        }
        problem = Problem(n_var=1, n_obj=2, n_ieq_constr=1)
        for name, objectives in cases.items():
            with self.subTest(name=name):
                pop = Population.new(
                    "F", np.asarray(objectives, dtype=float),
                    "G", np.full((len(objectives), 1), -1.0),
                )
                observed_distances = []
                vectorized_cdist = pymoo_spea2_module.vectorized_cdist

                def capture_distances(*args, **kwargs):
                    distances = vectorized_cdist(*args, **kwargs)
                    observed_distances.append(np.asarray(distances).copy())
                    return distances

                with patch.object(pymoo_spea2_module, "vectorized_cdist",
                                  side_effect=capture_distances):
                    survivors = SPEA2Survival(normalize=False).do(
                        problem, pop, n_survive=len(objectives))
                self.assertEqual(len(survivors), len(objectives))
                for field in ("SPEA_F", "SPEA_R", "SPEA_D"):
                    self.assertTrue(np.isfinite(pop.get(field)).all(), field)
                self.assertTrue(observed_distances)
                for distances in observed_distances:
                    off_diagonal = distances[~np.eye(len(objectives), dtype=bool)]
                    self.assertTrue(np.isfinite(off_diagonal).all(), name)

    def test_dominated_candidate_cannot_win_spea2_tournament(self):
        objectives = np.asarray([(value, value) for value in range(8)], dtype=float)
        pop = Population.new("F", objectives, "G", np.full((8, 1), -1.0))
        problem = Problem(n_var=1, n_obj=2, n_ieq_constr=1)
        SPEA2Survival(normalize=False).do(problem, pop, n_survive=len(objectives))
        self.assertTrue(np.isfinite(pop.get("SPEA_F")).all())
        pairs = np.tile(np.asarray([[7, 0]], dtype=int), (100, 1))
        winners = spea_binary_tournament(pop, pairs, None,
                                         random_state=np.random.default_rng(91))
        self.assertTrue(np.all(winners == 0))

    def test_previous_nan_case_runs_with_finite_spea2_fitness_each_survival(self):
        snapshots = []
        original_do = SPEA2Survival._do

        def checked_do(survival, problem, pop, *args, **kwargs):
            survivors = original_do(survival, problem, pop, *args, **kwargs)
            snapshots.append({field: pop.get(field).copy()
                              for field in ("SPEA_F", "SPEA_R", "SPEA_D")})
            return survivors

        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            with patch.object(SPEA2Survival, "_do", checked_do):
                result = run_spea2(self.instance, SPEA2Config(
                    seed=2, max_evaluations=16, population_size=8))
        self.assertTrue(snapshots)
        for snapshot in snapshots:
            for field, values in snapshot.items():
                self.assertTrue(np.isfinite(values).all(), field)
        self.assertEqual(result.attempts, 16)
        self.assertTrue(result.front)

    def test_crossover_combines_both_parents_and_preserves_jobs(self):
        parent_a = tuple(tuple((job, 0, 0) for job in range(self.instance.n))
                         if machine == 0 else () for machine in range(self.instance.m))
        parent_b = tuple(tuple((job, 1, 0) for job in reversed(range(self.instance.n)))
                         if machine == 1 else () for machine in range(self.instance.m))
        x = np.empty((2, 1, 1), dtype=object)
        x[0, 0, 0], x[1, 0, 0] = parent_a, parent_b
        child = ScheduleCrossover()._do(ScheduleProblem(self.instance, SPEA2Trace()), x,
                                        random_state=np.random.default_rng(3))[0, 0, 0]
        jobs = [job for seq in child for job, _, _ in seq]
        self.assertEqual(sorted(jobs), list(range(self.instance.n)))
        self.assertTrue(any(mode == 0 for seq in child for _, mode, _ in seq))
        self.assertTrue(any(mode == 1 for seq in child for _, mode, _ in seq))
        self.assertTrue(any(machine == 0 for machine, seq in enumerate(child) if seq))
        self.assertTrue(any(machine == 1 for machine, seq in enumerate(child) if seq))

    def test_crossover_pipeline_always_preserves_job_uniqueness(self):
        problem = ScheduleProblem(self.instance, SPEA2Trace())
        rng = np.random.default_rng(12)
        samples = ScheduleSampling().do(problem, 20, random_state=rng).get("X")
        x = np.empty((2, len(samples) // 2, 1), dtype=object)
        for mating in range(x.shape[1]):
            x[0, mating, 0] = samples[mating, 0]
            x[1, mating, 0] = samples[mating + x.shape[1], 0]
        children = ScheduleCrossover()._do(problem, x, random_state=np.random.default_rng(42))
        for row in children[0]:
            jobs = [job for seq in row[0] for job, _, _ in seq]
            self.assertEqual(sorted(jobs), list(range(self.instance.n)))

    def test_mutation_keeps_schedule_structure_and_varies_components(self):
        source = _random_schedule(self.instance, np.random.default_rng(4))
        x = np.empty((1, 1), dtype=object)
        x[0, 0] = source
        problem = ScheduleProblem(self.instance, SPEA2Trace())
        observed = set()
        for seed in range(180):
            child = ScheduleMutation()._do(problem, x, random_state=np.random.default_rng(seed))[0, 0]
            self.assertEqual(sorted(job for seq in child for job, _, _ in seq),
                             list(range(self.instance.n)))
            self.assertTrue(all(0 <= mode < self.instance.modes and wait >= 0
                                for seq in child for _, mode, wait in seq))
            if child != source:
                old = {job: (machine, mode, wait, position)
                       for machine, seq in enumerate(source)
                       for position, (job, mode, wait) in enumerate(seq)}
                new = {job: (machine, mode, wait, position)
                       for machine, seq in enumerate(child)
                       for position, (job, mode, wait) in enumerate(seq)}
                for job in old:
                    if old[job][1] != new[job][1]:
                        observed.add("mode")
                    if old[job][2] != new[job][2]:
                        observed.add("wait")
                    if old[job][0] != new[job][0]:
                        observed.add("machine")
                    if old[job][3] != new[job][3]:
                        observed.add("position")
        self.assertEqual(observed, {"mode", "wait", "machine", "position"})

    def test_invalid_complete_candidate_is_counted_and_marked_infeasible(self):
        trace = SPEA2Trace()
        problem = ScheduleProblem(self.instance, trace)
        invalid = (((0, 0, self.instance.horizon + 1),),
                   tuple((job, 0, 0) for job in range(1, self.instance.n)))
        with self.assertRaises(ScheduleValidationError):
            evaluate_schedule(self.instance, invalid)
        out = {}
        individual = np.empty(1, dtype=object)
        individual[0] = invalid
        problem._evaluate(individual, out)
        self.assertEqual(trace.attempts, 1)
        self.assertEqual(trace.feasible, 0)
        self.assertEqual(trace.rejected, 1)
        self.assertGreater(out["G"][0], 0)

    def test_invalid_offspring_consumes_one_search_budget_unit(self):
        def always_invalid(self, problem, x, random_state=None, **kwargs):
            result = np.empty_like(x, dtype=object)
            for index, row in enumerate(x):
                changed = [list(sequence) for sequence in row[0]]
                machine = next(m for m, sequence in enumerate(changed) if sequence)
                job, mode, _ = changed[machine][0]
                changed[machine][0] = (job, mode, problem.instance.horizon + 1)
                result[index, 0] = tuple(tuple(sequence) for sequence in changed)
            return result

        with patch.object(ScheduleMutation, "_do", always_invalid):
            result = run_spea2(self.instance, SPEA2Config(
                seed=1, max_evaluations=3, population_size=2,
                crossover_probability=0.0, mutation_probability=1.0))
        self.assertEqual(result.attempts, 3)
        self.assertEqual(result.feasible_evaluations, 2)
        self.assertEqual(result.rejected_evaluations, 1)
        self.assertEqual(result.pymoo_evaluations, 3)
        self.assertTrue(result.front)

    def test_run_respects_budget_and_final_front_is_unique_feasible_exact_pareto(self):
        result = run_spea2(self.instance, SPEA2Config(seed=8, max_evaluations=31,
                                                       population_size=8))
        self.assertEqual(result.attempts, 31)
        self.assertEqual(result.pymoo_evaluations, 31)
        self.assertLessEqual(result.attempts, result.config.max_evaluations)
        self.assertEqual(result.feasible_evaluations + result.rejected_evaluations,
                         result.attempts)
        keys = [point.key for point in result.front]
        self.assertEqual(len(keys), len(set(keys)))
        for index, point in enumerate(result.front):
            checked = evaluate_schedule(self.instance, point.schedule)
            self.assertEqual(checked.objective_key, point.key)
            self.assertFalse(any(dominates(other, point.key)
                                 for j, other in enumerate(keys) if j != index))

    def test_exported_schedules_reevaluate_to_exact_objectives(self):
        result = run_spea2(self.instance, SPEA2Config(seed=2, max_evaluations=16,
                                                       population_size=8))
        exported = result.to_result_dict()
        self.assertEqual(exported["instance_sha256"], self.instance.digest)
        for row, solution in zip(exported["front"], result.front):
            representation = tuple(tuple(tuple(item) for item in machine)
                                   for machine in row["representation"])
            checked = evaluate_schedule(self.instance, representation)
            self.assertEqual(checked.objective_key, solution.key)
            self.assertEqual(row["tec_exact"], {
                "numerator": checked.tec_units, "denominator": checked.tec_scale})

    def test_same_seed_and_configuration_reproduces_front_and_counters(self):
        config = SPEA2Config(seed=14, max_evaluations=24, population_size=8)
        first = run_spea2(self.instance, config)
        second = run_spea2(self.instance, config)
        self.assertEqual([(s.schedule, s.key) for s in first.front],
                         [(s.schedule, s.key) for s in second.front])
        self.assertEqual((first.attempts, first.feasible_evaluations, first.rejected_evaluations),
                         (second.attempts, second.feasible_evaluations, second.rejected_evaluations))

    def test_search_code_does_not_reference_baselines_or_exact_methods(self):
        source = (ROOT / "src/metaheuristics/spea2.py").read_text(encoding="utf-8")
        self.assertNotIn("data/baselines", source)
        self.assertNotIn("exact_methods", source)

    def test_budget_must_cover_initial_population(self):
        with self.assertRaises(ValueError):
            SPEA2Config(max_evaluations=7, population_size=8)

    def test_real_50_job_initialization_and_run_is_feasible_and_reproducible(self):
        instance = read_instance(ROOT / "data/input/set2/50_10_1439_5_S_1-9.dat")
        for seed in (1, 2, 7):
            rng = np.random.default_rng(seed)
            schedules = [_random_schedule(instance, rng) for _ in range(2)]
            repeat_rng = np.random.default_rng(seed)
            self.assertEqual(schedules, [_random_schedule(instance, repeat_rng) for _ in range(2)])
            self.assertNotEqual(schedules[0], schedules[1])
            self.assertNotEqual(
                tuple(tuple(job for job, _, _ in seq) for seq in schedules[0]),
                tuple(tuple(job for job, _, _ in seq) for seq in schedules[1]))
            for schedule in schedules:
                evaluation = evaluate_schedule(instance, schedule)
                self.assertEqual(len(evaluation.operations), instance.n)
            result = run_spea2(instance, SPEA2Config(
                seed=seed, max_evaluations=2, population_size=2))
            self.assertEqual(result.attempts, 2)
            self.assertTrue(result.front)

    def test_real_250_job_initialization_for_reported_seeds(self):
        instance = read_instance(ROOT / "data/input/set2/250_10_1439_5_S_1-9.dat")
        for seed in (1, 2, 7):
            rng = np.random.default_rng(seed)
            schedules = [_random_schedule(instance, rng) for _ in range(2)]
            repeat_rng = np.random.default_rng(seed)
            self.assertEqual(schedules, [_random_schedule(instance, repeat_rng) for _ in range(2)])
            self.assertNotEqual(schedules[0], schedules[1])
            self.assertNotEqual(
                tuple(tuple(job for job, _, _ in seq) for seq in schedules[0]),
                tuple(tuple(job for job, _, _ in seq) for seq in schedules[1]))
            for schedule in schedules:
                evaluation = evaluate_schedule(instance, schedule)
                self.assertEqual(len(evaluation.operations), instance.n)
                self.assertLessEqual(evaluation.cmax, instance.horizon)
            result = run_spea2(instance, SPEA2Config(
                seed=seed, max_evaluations=2, population_size=2))
            self.assertEqual(result.attempts, 2)
            self.assertEqual(result.feasible_evaluations, 2)
            self.assertTrue(result.front)


if __name__ == "__main__":
    unittest.main()
