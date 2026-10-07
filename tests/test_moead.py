from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import sys
import tempfile
import unittest
import warnings
from unittest.mock import patch

import numpy as np
from pymoo.algorithms.moo.moead import MOEAD
from pymoo.core.population import Population
from pymoo.decomposition.tchebicheff import Tchebicheff

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from problem import dominates, energy_scale, read_instance  # noqa: E402
from schedule import ScheduleValidationError, evaluate_schedule  # noqa: E402
from metaheuristics import moead, spea2  # noqa: E402
from metaheuristics.moead import (  # noqa: E402
    FeasibleEvaluator, MOEADConfig, MOEADTrace, ScheduleProblem,
    reference_directions, run_moead, write_result,
)


def invalid_mutation(self, problem, x, random_state=None, **kwargs):
    children = np.empty_like(x, dtype=object)
    for index, row in enumerate(x):
        changed = [list(sequence) for sequence in row[0]]
        machine = next(m for m, seq in enumerate(changed) if seq)
        job, mode, _ = changed[machine][0]
        changed[machine][0] = (job, mode, problem.instance.horizon + 1)
        children[index, 0] = tuple(tuple(seq) for seq in changed)
    return children


class MOEADTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance = read_instance(ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")

    def config(self, **kwargs):
        return MOEADConfig(**{"seed": 3, "population_size": 8, "n_neighbors": 3,
                              "max_evaluations": 31, **kwargs})

    def problem(self, instance=None, budget=100):
        return ScheduleProblem(instance or self.instance, MOEADTrace(), budget)

    def test_reference_directions_are_uniform_deterministic_with_extremes(self):
        for size in (2, 3, 8, 100):
            directions = reference_directions(size)
            self.assertEqual(directions.shape, (size, 2))
            np.testing.assert_array_equal(directions, reference_directions(size))
            np.testing.assert_allclose(directions[:, 0], np.linspace(0, 1, size))
            np.testing.assert_allclose(directions.sum(axis=1), 1)
            np.testing.assert_array_equal(directions[[0, -1]], [[0, 1], [1, 0]])

    def test_invalid_parameters_fail_clearly(self):
        for parameters in ({"population_size": 1}, {"max_evaluations": 7},
                           {"n_neighbors": 1}, {"n_neighbors": 9}, {"seed": -1},
                           {"population_size": 8.5}, {"max_evaluations": True},
                           {"n_neighbors": 2.5}, {"prob_neighbor_mating": -0.1},
                           {"mutation_probability": float("nan")},
                           {"crossover_probability": 1.1}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                self.config(**parameters)
        for size in (1, 2.5, True):
            with self.assertRaises(ValueError):
                reference_directions(size)

    def test_native_moead_population_decomposition_and_replacement(self):
        snapshots = []
        native_replace = MOEAD._replace

        def checked(algorithm, k, off):
            self.assertIs(type(algorithm), MOEAD)
            self.assertEqual(algorithm.pop_size, 8)
            self.assertEqual(len(algorithm.pop), len(algorithm.ref_dirs))
            self.assertEqual(algorithm.neighbors.shape, (8, 3))
            self.assertIs(type(algorithm.decomposition), Tchebicheff)
            self.assertFalse(algorithm.problem.has_constraints())
            snapshots.append(algorithm.neighbors.copy())
            checked_off = evaluate_schedule(self.instance, off.X[0])
            np.testing.assert_array_equal(off.F, [checked_off.cmax / self.instance.horizon,
                float(checked_off.tec_exact / self.instance.max_cost)])
            native_replace(algorithm, k, off)
            for individual in algorithm.pop:
                evaluate_schedule(self.instance, individual.X[0])

        with patch.object(MOEAD, "_replace", checked):
            result = run_moead(self.instance, self.config())
        self.assertEqual(len(snapshots), result.attempts - 8)
        for snapshot in snapshots[1:]:
            np.testing.assert_array_equal(snapshot, snapshots[0])
        for k, neighbors in enumerate(snapshots[0]):
            self.assertIn(k, neighbors)

    def test_budget_initialization_partial_sweeps_and_single_offspring(self):
        for budget in (8, 9, 15, 16, 17, 31):
            replacements = []
            original = MOEAD._replace

            def counted(algorithm, k, off):
                replacements.append(k)
                return original(algorithm, k, off)

            with self.subTest(budget=budget), patch.object(MOEAD, "_replace", counted):
                result = run_moead(self.instance, self.config(max_evaluations=budget))
            self.assertEqual(result.attempts, budget)
            self.assertEqual(result.pymoo_evaluations, budget)
            self.assertEqual(result.post_search_validations, 8)
            self.assertEqual(len(replacements), budget - 8)
            self.assertEqual(result.feasible_evaluations + result.rejected_evaluations, budget)

    def test_smallest_population_and_both_mating_branches(self):
        for probability in (0.0, 1.0):
            result = run_moead(self.instance, self.config(
                population_size=2, n_neighbors=2, max_evaluations=7,
                prob_neighbor_mating=probability))
            self.assertEqual(result.attempts, 7)
            self.assertTrue(result.front)

    def test_operators_are_reused_without_spea2_search(self):
        self.assertIs(moead.ScheduleSampling, spea2.ScheduleSampling)
        self.assertIs(moead.ScheduleCrossover, spea2.ScheduleCrossover)
        self.assertIs(moead.ScheduleMutation, spea2.ScheduleMutation)
        with patch.object(spea2, "run_spea2", side_effect=AssertionError("SPEA2 search")):
            run_moead(self.instance, self.config())

    def test_sampling_feasible_diverse_reproducible_without_full_evaluation(self):
        problem = self.problem()
        with patch.object(moead, "evaluate_schedule", side_effect=AssertionError("hidden eval")), \
                patch.object(spea2, "evaluate_schedule", side_effect=AssertionError("hidden eval")):
            a = moead.ScheduleSampling().do(problem, 32, random_state=np.random.default_rng(1))
            b = moead.ScheduleSampling().do(problem, 32, random_state=np.random.default_rng(1))
        schedules = [row[0] for row in a.get("X")]
        self.assertEqual(schedules, [row[0] for row in b.get("X")])
        self.assertGreater(len(set(schedules)), 1)
        orders = {tuple(tuple(job for job, _, _ in seq) for seq in s) for s in schedules}
        allocations = {tuple(next(m for m, seq in enumerate(s) if any(j == job for j, _, _ in seq))
                             for job in range(self.instance.n)) for s in schedules}
        modes = {tuple(sorted((j, mode) for seq in s for j, mode, _ in seq)) for s in schedules}
        for patterns in (orders, allocations, modes):
            self.assertGreater(len(patterns), 1)
        for schedule in schedules:
            evaluate_schedule(self.instance, schedule)

    def test_crossover_recombines_both_parents(self):
        a = (tuple((j, 0, 0) for j in range(self.instance.n)), ())
        b = ((), tuple((j, 1, 2) for j in reversed(range(self.instance.n))))
        x = np.empty((2, 1, 1), dtype=object)
        x[0, 0, 0], x[1, 0, 0] = a, b
        child = moead.ScheduleCrossover()._do(self.problem(), x,
            random_state=np.random.default_rng(3))[0, 0, 0]
        self.assertEqual(sorted(j for seq in child for j, _, _ in seq), list(range(self.instance.n)))
        self.assertTrue(all(child))
        self.assertEqual({mode for seq in child for _, mode, _ in seq}, {0, 1})
        self.assertEqual({wait for seq in child for _, _, wait in seq}, {0, 2})
        self.assertNotIn(child, (a, b))

    def test_mutation_can_change_machine_position_mode_and_wait(self):
        problem = self.problem()
        source = moead.ScheduleSampling().do(problem, 1, random_state=np.random.default_rng(4))[0].X[0]
        x = np.empty((1, 1), dtype=object)
        x[0, 0] = source

        def components(schedule):
            return {j: (m, position, mode, wait) for m, seq in enumerate(schedule)
                    for position, (j, mode, wait) in enumerate(seq)}

        original = components(source)
        observed = set()
        for seed in range(180):
            child = moead.ScheduleMutation()._do(problem, x,
                random_state=np.random.default_rng(seed))[0, 0]
            current = components(child)
            self.assertEqual(set(current), set(original))
            for job in original:
                observed.update(i for i in range(4) if original[job][i] != current[job][i])
        self.assertEqual(observed, {0, 1, 2, 3})

    def test_rejected_candidate_is_charged_without_invalid_objectives(self):
        problem = self.problem(budget=1)
        out = {}
        x = np.empty(1, dtype=object)
        x[0] = (((0, 0, self.instance.horizon + 1),), ())
        with self.assertRaises(ScheduleValidationError):
            problem._evaluate(x, out)
        self.assertEqual((problem.trace.attempts, problem.trace.feasible, problem.trace.rejected), (1, 0, 1))
        self.assertNotIn("F", out)
        self.assertNotIn("G", out)
        with self.assertRaises(RuntimeError):
            problem._evaluate(x, {})
        self.assertEqual(problem.trace.attempts, 1)

    def test_evaluator_rejects_oversized_batch_before_any_complete_call(self):
        problem = self.problem(budget=1)
        evaluator = FeasibleEvaluator()
        schedules = moead.ScheduleSampling().do(problem, 2, random_state=np.random.default_rng(3))
        population = Population.create(*schedules)
        with patch.object(moead, "evaluate_schedule", wraps=evaluate_schedule) as full, \
                self.assertRaisesRegex(RuntimeError, "Batch"):
            evaluator.eval(problem, population)
        self.assertEqual(full.call_count, 0)
        self.assertEqual(problem.trace.attempts, 0)
        self.assertEqual(evaluator.n_eval, 0)

    def test_all_invalid_offspring_use_cached_feasible_fallback_and_literal_cap(self):
        calls = []
        native_replace = MOEAD._replace

        def checked(algorithm, k, off):
            self.assertIn(off.X[0], [individual.X[0] for individual in algorithm.pop])
            evaluation = evaluate_schedule(self.instance, off.X[0])
            np.testing.assert_array_equal(off.F, [evaluation.cmax / self.instance.horizon,
                float(evaluation.tec_exact / self.instance.max_cost)])
            calls.append(off.X[0])
            return native_replace(algorithm, k, off)

        with patch.object(moead.ScheduleMutation, "_do", invalid_mutation), \
                patch.object(MOEAD, "_replace", checked), \
                patch.object(moead, "evaluate_schedule", wraps=evaluate_schedule) as full:
            result = run_moead(self.instance, self.config(mutation_probability=1.0))
        self.assertEqual((result.attempts, result.feasible_evaluations, result.rejected_evaluations,
                          result.pymoo_evaluations), (31, 8, 23, 31))
        self.assertEqual(len(calls), 23)
        self.assertEqual(full.call_count, 31 + 8)
        for point in result.front:
            evaluate_schedule(self.instance, point.schedule)

    def test_invalid_initialization_aborts_instead_of_accepting_infeasibility(self):
        with patch.object(moead.ScheduleSampling, "_do",
                          return_value=np.array([[None]] * 8, dtype=object)), \
                self.assertRaisesRegex(RuntimeError, "Sampling produziu"):
            run_moead(self.instance, self.config())

    def test_complete_evaluator_calls_equal_budget_without_hidden_or_duplicate_calls(self):
        stages = []
        original_final = moead._final_front

        def final(instance, population):
            stages.append(full.call_count)
            return original_final(instance, population)

        with patch.object(moead, "evaluate_schedule", wraps=evaluate_schedule) as full, \
                patch.object(spea2, "evaluate_schedule", side_effect=AssertionError("hidden eval")), \
                patch.object(moead, "_final_front", side_effect=final):
            result = run_moead(self.instance, self.config())
        self.assertEqual(stages, [31])
        self.assertEqual(full.call_count, result.attempts + result.post_search_validations)

    def test_final_and_exported_front_is_exact_feasible_unique_nondominated(self):
        result = run_moead(self.instance, self.config())
        keys = [point.key for point in result.front]
        self.assertTrue(keys)
        self.assertEqual(len(keys), len(set(keys)))
        exported = result.to_result_dict()
        self.assertEqual(exported["instance_sha256"], self.instance.digest)
        for row, point in zip(exported["front"], result.front):
            schedule = tuple(tuple(tuple(item) for item in machine) for machine in row["representation"])
            checked = evaluate_schedule(self.instance, schedule)
            self.assertEqual(checked.objective_key, point.key)
            self.assertEqual(row["makespan"], checked.cmax)
            self.assertEqual(row["tec_exact"], {"numerator": checked.tec_units,
                                               "denominator": checked.tec_scale})
            self.assertFalse(any(dominates(key, point.key) for key in keys))

    def test_same_seed_reproduces_front_and_counters_and_other_seed_varies(self):
        def signature(result):
            return ([(s.schedule, s.key) for s in result.front], result.attempts,
                    result.feasible_evaluations, result.rejected_evaluations, result.pymoo_evaluations)
        first = run_moead(self.instance, self.config())
        self.assertEqual(signature(first), signature(run_moead(self.instance, self.config())))
        self.assertNotEqual(signature(first), signature(run_moead(self.instance, self.config(seed=7))))

    def test_rejections_are_also_reproducible(self):
        config = self.config(mutation_probability=1.0)
        with patch.object(moead.ScheduleMutation, "_do", invalid_mutation):
            a, b = run_moead(self.instance, config), run_moead(self.instance, config)
        self.assertEqual([(s.schedule, s.key) for s in a.front], [(s.schedule, s.key) for s in b.front])
        self.assertEqual(a.rejected_evaluations, b.rejected_evaluations)

    def test_fixed_scaling_matches_project_convention_without_observed_ranges(self):
        problem = self.problem()
        schedule = moead.ScheduleSampling().do(problem, 1, random_state=np.random.default_rng(3))[0].X
        evaluation = evaluate_schedule(self.instance, schedule[0])
        out = {}
        problem._evaluate(schedule, out)
        np.testing.assert_array_equal(out["F"], [evaluation.cmax / self.instance.horizon,
                                    float(evaluation.tec_exact / self.instance.max_cost)])
        exported = run_moead(self.instance, self.config()).to_result_dict()
        self.assertEqual(exported["objective_scaling"]["tec_divisor_exact"],
                         {"numerator": 649, "denominator": 1})
        self.assertEqual(exported["run_parameters"]["decomposition"], "Tchebycheff")

    def test_zero_and_low_objective_amplitude_remain_finite_deterministic(self):
        for instance in (replace(self.instance, peak_rate=Fraction(0), off_rate=Fraction(0)),
                         replace(self.instance, peak_rate=Fraction(1, 10**9),
                                 off_rate=Fraction(1, 10**9))):
            with warnings.catch_warnings():
                warnings.simplefilter("error", RuntimeWarning)
                a = run_moead(instance, self.config())
                b = run_moead(instance, self.config())
            self.assertEqual([(s.schedule, s.key) for s in a.front], [(s.schedule, s.key) for s in b.front])
            self.assertTrue(all(np.isfinite(float(s.evaluation.tec_exact / instance.max_cost)) for s in a.front))
        decomposition = Tchebicheff()
        for objectives in (np.zeros((8, 2)), np.full((8, 2), 0.5)):
            self.assertTrue(np.isfinite(decomposition.do(objectives,
                reference_directions(8), ideal_point=objectives.min(axis=0))).all())

    def test_no_baseline_or_exact_search_dependencies(self):
        source = (ROOT / "src/metaheuristics/moead.py").read_text()
        self.assertNotIn("data/baselines", source)
        self.assertNotIn("exact_methods", source)
        with patch("problem.generate_choices", side_effect=AssertionError("exact choices")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("search read file")), \
                patch.object(Path, "read_text", side_effect=AssertionError("search read file")):
            run_moead(self.instance, self.config())

    def test_output_preserves_metadata_and_does_not_overwrite_without_authorization(self):
        result = run_moead(self.instance, self.config())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            write_result(result, path)
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_result(result, path)
            self.assertEqual(before, path.read_bytes())
            write_result(result, path, overwrite=True)
        out = result.to_result_dict()
        self.assertEqual(out["population_size"], len(out["reference_directions"]))
        for key in ("attempts", "feasible_evaluations", "rejected_evaluations", "pymoo_evaluations",
                    "post_search_validations", "elapsed_seconds", "max_evaluations"):
            self.assertIn(key, out)

    def test_other_pymoo_versions_require_revalidation(self):
        with patch.object(moead.pymoo, "__version__", "0.7.0"), self.assertRaisesRegex(RuntimeError, "0.6.2"):
            run_moead(self.instance, self.config())

    def test_real_50_and_250_job_initialization_and_partial_sweep(self):
        for n in (50, 250):
            instance = read_instance(ROOT / f"data/input/set2/{n}_10_1439_5_S_1-9.dat")
            result = run_moead(instance, self.config(population_size=4, n_neighbors=2, max_evaluations=7))
            self.assertEqual(result.attempts, 7)
            for point in result.front:
                self.assertEqual(evaluate_schedule(instance, point.schedule).objective_key, point.key)

    def test_dataset_integer_energy_bound_and_scaled_float_resolution(self):
        # Processing intervals cannot occupy more than m*H slots. This check
        # strengthens the existing integer-unit evidence for the normalized ratio.
        for path in (ROOT / "data/input").glob("*/*.dat"):
            instance = read_instance(path)
            scale, prices = energy_scale(instance)
            upper = instance.m * instance.horizon * max(max(on, off) for _, _, on, off in prices)
            self.assertLess(upper, 2**51)
            if upper:
                a = float(Fraction(upper - 1, scale) / instance.max_cost)
                b = float(Fraction(upper, scale) / instance.max_cost)
                self.assertLess(a, b)


if __name__ == "__main__":
    unittest.main()
