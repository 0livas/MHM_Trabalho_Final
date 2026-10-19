from pathlib import Path
import sys
import unittest
import warnings
from unittest.mock import patch

import numpy as np
from pymoo.algorithms.moo.age import AGEMOEASurvival
from pymoo.core.population import Population
from pymoo.core.problem import Problem

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from problem import read_instance
from schedule import evaluate_schedule
from metaheuristics.age_spike import run_spike
from metaheuristics.spea2 import ScheduleCrossover, ScheduleMutation


class AgeSpikeTests(unittest.TestCase):
    def test_original_instances_evolve_and_repeat_exactly(self):
        for path in ("set1/10_2_1439_3_S_1-9.dat", "set2/50_10_1439_5_S_1-9.dat"):
            instance = read_instance(ROOT / "data/input" / path)
            with self.subTest(path=path), warnings.catch_warnings():
                warnings.simplefilter("error", RuntimeWarning)
                with patch.object(ScheduleCrossover, "_do", autospec=True,
                                  side_effect=ScheduleCrossover._do) as crossover, \
                     patch.object(ScheduleMutation, "_do", autospec=True,
                                  side_effect=ScheduleMutation._do) as mutation, \
                     patch.object(AGEMOEASurvival, "_do", autospec=True,
                                  side_effect=AGEMOEASurvival._do) as survival, \
                     patch("metaheuristics.spea2.evaluate_schedule", wraps=evaluate_schedule) as search, \
                     patch("metaheuristics.age_spike.evaluate_schedule", wraps=evaluate_schedule) as final:
                    result = run_spike(instance)
                self.assertGreater(crossover.call_count, 0)
                self.assertGreater(mutation.call_count, 0)
                self.assertEqual(survival.call_count, len(result["batches"]))
                self.assertEqual(search.call_count, 41)
                self.assertEqual(final.call_count, 8)
                self.assertEqual(result, run_spike(instance))
                self.assertEqual(result["batches"], [8, 8, 8, 8, 8, 1])
                self.assertEqual(result["evaluations"], result["pymoo_evaluations"])
                self.assertEqual(result["feasible"] + result["rejected"], 41)
                self.assertGreater(result["novel_offspring"], 0)
                self.assertGreater(result["novel_survivors"], 0)

    def test_initialization_only_and_incremental_budget(self):
        instance = read_instance(ROOT / "data/input/set1/10_2_1439_3_S_1-9.dat")
        self.assertEqual(run_spike(instance, budget=8)["batches"], [8])
        result = run_spike(instance, budget=11, offspring_size=1)
        self.assertEqual(result["batches"], [8, 1, 1, 1])
        with self.assertRaises(ValueError):
            run_spike(instance, budget=7)

    def test_infeasible_offspring_consumes_budget_and_is_filtered(self):
        def invalid(self, problem, x, **kwargs):
            changed = x.copy()
            for row in changed:
                machines = [list(seq) for seq in row[0]]
                machine = next(seq for seq in machines if seq)
                job, mode, _ = machine[0]
                machine[0] = (job, mode, problem.instance.horizon + 1)
                row[0] = tuple(tuple(seq) for seq in machines)
            return changed

        instance = read_instance(ROOT / "data/input/set1/10_2_1439_3_S_1-9.dat")
        with patch.object(ScheduleMutation, "do", autospec=True) as mutation:
            # Apply the injected mutation to every descendant, independent of prob=0.3.
            def mutate(operator, problem, pop, **kwargs):
                pop.set("X", invalid(operator, problem, pop.get("X")))
                return pop
            mutation.side_effect = mutate
            result = run_spike(instance, budget=17)
        self.assertEqual(result["rejected"], 9)
        self.assertEqual(result["feasible"], 8)
        self.assertEqual(result["evaluations"], 17)
        self.assertEqual(result["novel_survivors"], 0)

    def test_survival_with_duplicates_and_constant_axes(self):
        for objectives in ([(97, 10)] * 8,
                           [(97, value) for value in range(10, 18)],
                           [(value, 10) for value in range(97, 105)],
                           [(97, 20), (98, 19)] * 4):
            with self.subTest(objectives=objectives), warnings.catch_warnings():
                warnings.simplefilter("error", RuntimeWarning)
                pop = Population.new("F", np.array(objectives, dtype=float))
                survivors = AGEMOEASurvival().do(Problem(n_var=1, n_obj=2), pop,
                                               n_survive=4)
                self.assertEqual(len(survivors), 4)
                self.assertFalse(np.isnan(pop.get("crowding")).any())
                self.assertFalse(np.isnan(pop.get("rank")).any())
                # Infinite scores are intentional for extreme solutions.
                self.assertTrue(np.isfinite(survivors.get("F")).all())


if __name__ == "__main__":
    unittest.main()
