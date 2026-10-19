from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import warnings
from unittest.mock import patch

import numpy as np
from pymoo.algorithms.moo.age import AGEMOEASurvival
from pymoo.core.population import Population

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from problem import dominates, read_instance
from schedule import evaluate_schedule
from metaheuristics.age import AGEConfig, _final_front, run_age, write_result
from metaheuristics.spea2 import ScheduleCrossover, ScheduleMutation, _random_schedule


class AGETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance = read_instance(ROOT / "data/input/set1/10_2_1439_3_S_1-9.dat")

    def test_original_sets_reproduce_evolution_and_export_exact_front(self):
        for instance in (self.instance, read_instance(ROOT / "data/input/set2/50_10_1439_5_S_1-9.dat")):
            with self.subTest(instance=instance.path.name), warnings.catch_warnings():
                warnings.simplefilter("error", RuntimeWarning)
                config = AGEConfig(seed=23, max_evaluations=41, population_size=8)
                with patch.object(ScheduleCrossover, "_do", autospec=True,
                                  side_effect=ScheduleCrossover._do) as cross, \
                     patch.object(ScheduleMutation, "_do", autospec=True,
                                  side_effect=ScheduleMutation._do) as mutate, \
                     patch.object(AGEMOEASurvival, "_do", autospec=True,
                                  side_effect=AGEMOEASurvival._do) as survival, \
                     patch("metaheuristics.spea2.evaluate_schedule", wraps=evaluate_schedule) as search, \
                     patch("metaheuristics.age.evaluate_schedule", wraps=evaluate_schedule) as final:
                    first = run_age(instance, config)
                self.assertGreater(cross.call_count, 0)
                self.assertGreater(mutate.call_count, 0)
                self.assertEqual(survival.call_count, 6)
                self.assertEqual(search.call_count, 41)
                self.assertEqual(final.call_count, 8)
                second = run_age(instance, config)
                one, two = first.to_result_dict(), second.to_result_dict()
                one.pop("elapsed_seconds")
                two.pop("elapsed_seconds")
                self.assertEqual(one, two)
                self.assertEqual(first.evaluation_batches, (8, 8, 8, 8, 8, 1))
                self.assertEqual(first.attempts, first.pymoo_evaluations)
                self.assertEqual(first.feasible_evaluations + first.rejected_evaluations, 41)
                keys = [point.key for point in first.front]
                self.assertTrue(keys)
                self.assertEqual(len(keys), len(set(keys)))
                for point, row in zip(first.front, one["front"]):
                    checked = evaluate_schedule(instance, row["representation"])
                    self.assertEqual(checked, point.evaluation)
                    self.assertEqual(row["tec_exact"], {"numerator": checked.tec_units,
                                                      "denominator": checked.tec_scale})
                    self.assertFalse(any(dominates(other, point.key) for other in keys))
                self.assertEqual(one["instance_sha256"], instance.digest)
                self.assertFalse(one["pareto_proven"])

    def test_budget_boundaries(self):
        for budget, batches in ((8, (8,)), (9, (8, 1)), (16, (8, 8)), (19, (8, 8, 3))):
            with self.subTest(budget=budget):
                result = run_age(self.instance, AGEConfig(max_evaluations=budget, population_size=8))
                self.assertEqual(result.attempts, budget)
                self.assertEqual(result.pymoo_evaluations, budget)
                self.assertEqual(result.evaluation_batches, batches)
                self.assertEqual(result.post_search_validations, 8)

    def test_infeasible_offspring_are_counted_without_repair(self):
        def invalid(operator, problem, pop, **kwargs):
            x = pop.get("X").copy()
            for row in x:
                machines = [list(seq) for seq in row[0]]
                sequence = next(seq for seq in machines if seq)
                job, mode, _ = sequence[0]
                sequence[0] = (job, mode, problem.instance.horizon + 1)
                row[0] = tuple(tuple(seq) for seq in machines)
            pop.set("X", x)
            return pop

        with patch.object(ScheduleMutation, "do", autospec=True, side_effect=invalid), \
             patch("metaheuristics.spea2.evaluate_schedule", wraps=evaluate_schedule) as search:
            result = run_age(self.instance, AGEConfig(max_evaluations=25, population_size=8))
        self.assertEqual(search.call_count, 25)
        self.assertEqual(result.attempts, 25)
        self.assertEqual(result.pymoo_evaluations, 25)
        self.assertEqual(result.rejected_evaluations, 17)
        self.assertEqual(result.feasible_evaluations, 8)
        self.assertTrue(result.front)

    def test_identical_schedules_consume_budget_and_export_one_point(self):
        schedule = _random_schedule(self.instance, np.random.default_rng(1))
        with patch("metaheuristics.spea2._random_schedule", return_value=schedule), \
             warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            result = run_age(self.instance, AGEConfig(max_evaluations=25, population_size=8,
                                                     crossover_probability=0, mutation_probability=0))
        self.assertEqual(result.attempts, 25)
        self.assertEqual(result.pymoo_evaluations, 25)
        self.assertEqual(result.post_search_validations, 8)
        self.assertEqual(len(result.front), 1)
        self.assertEqual(result.front[0].schedule, schedule)

    def test_exact_filter_resolves_float_collision_and_duplicate_keys(self):
        schedule = _random_schedule(self.instance, np.random.default_rng(1))
        base = evaluate_schedule(self.instance, schedule)
        # Adjacent integers collapse to the same float. Worse point arrives first.
        evaluations = [replace(base, tec_units=value, tec_scale=1)
                       for value in (2**53 + 1, 2**53, 2**53)]
        x = np.empty((3, 1), dtype=object)
        for row in x:
            row[0] = schedule
        population = Population.new("X", x, "F", np.array([
            [ev.cmax, ev.tec] for ev in evaluations]), "G", -np.ones((3, 1)))
        with patch("metaheuristics.age.evaluate_schedule", side_effect=evaluations):
            front = _final_front(self.instance, population)
        self.assertEqual(len(front), 1)
        self.assertEqual(front[0].evaluation.tec_units, 2**53)

    def test_final_objective_mismatch_fails(self):
        schedule = _random_schedule(self.instance, np.random.default_rng(1))
        x = np.empty((1, 1), dtype=object)
        x[0, 0] = schedule
        population = Population.new("X", x, "F", np.array([[0., 0.]]), "G", np.array([[-1.]]))
        with self.assertRaisesRegex(RuntimeError, "divergem"):
            _final_front(self.instance, population)

    def test_invalid_configuration_and_version(self):
        for kwargs in ({"seed": -1}, {"seed": True}, {"seed": 1.2},
                       {"population_size": 1}, {"population_size": 2.5},
                       {"max_evaluations": 7, "population_size": 8},
                       {"max_evaluations": False}, {"crossover_probability": -0.1},
                       {"mutation_probability": 1.1}, {"mutation_probability": float("nan")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                AGEConfig(**kwargs)
        with patch("metaheuristics.age.pymoo.__version__", "0.6.3"), \
             self.assertRaisesRegex(RuntimeError, "0.6.2"):
            run_age(self.instance)

    def test_sampling_failure_is_not_hidden(self):
        with patch("metaheuristics.spea2._random_schedule", side_effect=RuntimeError("no position")), \
             self.assertRaisesRegex(RuntimeError, "no position"):
            run_age(self.instance, AGEConfig(max_evaluations=8, population_size=8))

    def test_writer_and_cli_do_not_overwrite_without_flag(self):
        result = run_age(self.instance, AGEConfig(max_evaluations=8, population_size=8))
        with TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "result.json"
            write_result(result, output)
            self.assertEqual(json.loads(output.read_text()), result.to_result_dict())
            with self.assertRaises(FileExistsError):
                write_result(result, output)
            write_result(result, output, overwrite=True)
            command = [sys.executable, str(ROOT / "src/metaheuristics/age.py"),
                       str(self.instance.path), "--output-dir", directory,
                       "--seed", "23", "--max-evaluations", "9", "--population-size", "8"]
            first = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(first.returncode, 0, first.stderr)
            path = Path(directory) / f"{self.instance.path.stem}.json"
            saved = path.read_bytes()
            self.assertEqual(json.loads(saved)["evaluations"], 9)
            second = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("--overwrite", second.stderr)
            self.assertEqual(path.read_bytes(), saved)
            third = subprocess.run(command + ["--overwrite"], capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(third.returncode, 0, third.stderr)


if __name__ == "__main__":
    unittest.main()
