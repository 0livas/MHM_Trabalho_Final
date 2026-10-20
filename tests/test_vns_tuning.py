"""Contratos VNS/VND: controles reais e esforço sem gerações artificiais."""
from dataclasses import fields
from pathlib import Path
import sys
import unittest

import optuna

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hyperparameters_tuning.vns_vnd import (
    SEARCH_SPACE, generation_metrics, resolve_parameters, run_single,
    suggest_parameters, validate_space,
)
from problem import read_instance
from metaheuristics.vns_vnd import VNSConfig


class VNSTuningTests(unittest.TestCase):
    def test_defaults_have_five_levels_for_all_native_controls(self):
        self.assertEqual(set(SEARCH_SPACE), {"initial_solutions", "max_candidates_per_neighborhood",
                                            "shaking_attempts", "max_evaluations"})
        self.assertEqual(set(SEARCH_SPACE), {f.name for f in fields(VNSConfig)} - {"seed"})
        for values in SEARCH_SPACE.values():
            self.assertGreaterEqual(len(set(values)), 5)

    def test_fixed_budget_ignores_effort_grid_and_filters_initial_solutions(self):
        study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=3))
        trial = study.ask()
        params = suggest_parameters(trial, 3, "evaluations")
        self.assertEqual(params["max_evaluations"], 3)
        self.assertLessEqual(params["initial_solutions"], 3)
        self.assertNotIn("max_evaluations", trial.params)

    def test_effort_samples_cap_and_custom_json_order_is_irrelevant(self):
        reversed_space = dict(reversed(list(SEARCH_SPACE.items())))
        self.assertEqual(list(validate_space(reversed_space, 8000, "effort")), list(SEARCH_SPACE))
        study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=7))
        trial = study.ask()
        params = suggest_parameters(trial, 8000, "effort", reversed_space)
        self.assertIn(params["max_evaluations"], SEARCH_SPACE["max_evaluations"])
        self.assertIn("max_evaluations", trial.params)
        metrics = generation_metrics(params, params["max_evaluations"])
        self.assertIsNone(metrics["full_generations"])
        self.assertIsNone(metrics["target_generations"])

    def test_rejects_generation_mode_and_incompatible_caps(self):
        with self.assertRaises(ValueError):
            validate_space(SEARCH_SPACE, 8000, "generations")
        with self.assertRaises(ValueError):
            validate_space({**SEARCH_SPACE, "max_evaluations": [2]}, 8000, "effort")
        with self.assertRaises(ValueError):
            validate_space({**SEARCH_SPACE, "initial_solutions": [True]}, 8000, "effort")

    def test_real_short_run_respects_cap_and_produces_valid_archive(self):
        instance = read_instance(ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
        params = resolve_parameters(dict(initial_solutions=2,
            max_candidates_per_neighborhood=2, shaking_attempts=1), 20, "evaluations")
        result = run_single(instance, params, 11)
        self.assertLessEqual(result.evaluations, 20)
        self.assertEqual(result.evaluations, result.feasible_evaluations+result.rejected_evaluations)
        self.assertTrue(result.front)
        self.assertTrue(all(solution.evaluation.cmax <= instance.horizon for solution in result.front))


if __name__ == "__main__":
    unittest.main()
