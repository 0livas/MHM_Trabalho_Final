"""Calibração por parâmetros nativos, sem alterar a meta-heurística."""
from dataclasses import fields
from pathlib import Path
import sys
import unittest
import optuna

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hyperparameters_tuning import age as tuning
from metaheuristics.age import AGEConfig
from problem import read_instance
from schedule import evaluate_schedule


class NativeTuningTests(unittest.TestCase):
    def test_grid_matches_native_config_and_five_values(self):
        self.assertEqual(set(tuning.SEARCH_SPACE), {f.name for f in fields(AGEConfig)} - {"seed"})
        self.assertTrue(all(len(set(v)) >= 5 for v in tuning.SEARCH_SPACE.values()))
        study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=11))
        for _ in range(10):
            trial = study.ask()
            params = tuning.suggest_parameters(trial, 40, "effort", dict(reversed(list(tuning.SEARCH_SPACE.items()))))
            self.assertEqual(set(trial.params), set(tuning.SEARCH_SPACE))
            AGEConfig(seed=11, **params)
            study.tell(trial, 0)

    def test_fixed_evaluations_short_run_validates_final_front(self):
        trial = optuna.trial.FixedTrial(dict(population_size=20, crossover_probability=.7, mutation_probability=.3))
        params = tuning.suggest_parameters(trial, 25, "evaluations")
        self.assertEqual(params["max_evaluations"], 25)
        self.assertNotIn("max_evaluations", trial.params)
        instance = read_instance(ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
        result = tuning.run_single(instance, params, 11)
        self.assertEqual(result.attempts, 25)
        for point in result.front:
            self.assertEqual(evaluate_schedule(instance, point.schedule).objective_key, point.key)

    def test_rejects_non_native_and_incompatible_combinations(self):
        for change in ({"generations": [50]}, {"max_evaluations": [10]}, {"mutation_probability": [float("nan")]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                tuning.validate_space({**tuning.SEARCH_SPACE, **change}, 8000, "effort")
        with self.assertRaises(ValueError):
            tuning.validate_space(tuning.SEARCH_SPACE, 8000, "generations")


if __name__ == "__main__":
    unittest.main()
