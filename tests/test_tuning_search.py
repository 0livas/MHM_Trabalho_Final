"""Regression checks for finite search coverage and reproducible continuation."""
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

import optuna

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hyperparameters_tuning import common, moead


class SearchTests(unittest.TestCase):
    path = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"

    def test_multivariate_parallel_resume_matches_uninterrupted_search(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            args = dict(seeds=(11,), budget=20, workers=2, startup_trials=0,
                        study_name="resume_equivalence")
            moead.calibrate([self.path], n_trials=6, output_dir=left, **args)
            moead.calibrate([self.path], n_trials=2, output_dir=right, **args)
            moead.calibrate([self.path], n_trials=6, output_dir=right, resume=True, **args)
            def parameters(folder):
                return [json.loads(p.read_text())["parameters"]
                        for p in sorted(Path(folder, "trials").glob("trial_*.json"))]
            self.assertEqual(parameters(left), parameters(right))

    def test_forced_duplicate_tpe_uses_unseen_fallback(self):
        space = {name: [values[0]] for name, values in moead.SEARCH_SPACE.items()}
        space.update(population_size=[4], n_neighbors=[2], mutation_probability=[.1, .5])
        def first_choice(sampler, study, trial, name, distribution):
            return .5 if name == "mutation_probability" else distribution.choices[0]
        def repeated_relative(sampler, study, trial, search_space):
            return {name: first_choice(sampler, study, trial, name, distribution)
                    for name, distribution in search_space.items()}
        with tempfile.TemporaryDirectory() as folder, patch.object(
                optuna.samplers.TPESampler, "sample_independent", first_choice), patch.object(
                optuna.samplers.TPESampler, "sample_relative", repeated_relative):
            report = moead.calibrate([self.path], seeds=(11,), n_trials=2, budget=12,
                output_dir=folder, study_name="fallback", search_space=space, startup_trials=0)
            self.assertEqual(report["completed_trials"], 2)
            storage = optuna.storages.RDBStorage("sqlite:///" + Path(folder, "study.sqlite3").as_posix())
            try:
                study = optuna.load_study(study_name="fallback", storage=storage)
                completed = study.get_trials(states=(optuna.trial.TrialState.COMPLETE,))
                self.assertEqual(len({tuple(sorted(t.params.items())) for t in completed}), 2)
                self.assertEqual(completed[1].user_attrs["proposal_source"], "fallback")
            finally:
                storage.engine.dispose()

    def test_unseen_fallback_exhausts_active_grid_without_repeating(self):
        space = {"population_size": [4, 8], "max_evaluations": [12, 20],
                 "mutation_probability": [0.1, 0.5]}
        seen, rng = set(), random.Random(12)
        for _ in range(4):
            params = common._unseen_parameters(space, "evaluations", seen, rng)
            self.assertNotIn("max_evaluations", params)
            key = tuple(sorted(params.items()))
            self.assertNotIn(key, seen)
            seen.add(key)
        self.assertIsNone(common._unseen_parameters(space, "evaluations", seen, rng))

    def test_sampler_checkpoint_restores_next_suggestions(self):
        study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=7))
        rng = random.Random(11)
        for _ in range(12):
            trial = study.ask()
            x = trial.suggest_categorical("x", list(range(20)))
            study.tell(trial, float(x))
        common._save_sampler_state(study, rng)
        expected_random = rng.random()
        trial = study.ask()
        expected = trial.suggest_categorical("x", list(range(20)))
        study.tell(trial, state=optuna.trial.TrialState.FAIL)
        # FAILED trials are ignored by TPE; restore the pre-suggestion RNG state.
        study.sampler = optuna.samplers.TPESampler(seed=999)
        replacement_rng = random.Random(999)
        common._restore_sampler_state(study, replacement_rng)
        self.assertEqual(replacement_rng.random(), expected_random)
        actual = study.ask().suggest_categorical("x", list(range(20)))
        self.assertEqual(actual, expected)

    def test_real_search_exhaustion_and_resume_never_repeat_configuration(self):
        space = {name: [values[0]] for name, values in moead.SEARCH_SPACE.items()}
        space.update(population_size=[4], n_neighbors=[2], mutation_probability=[.1, .5])
        with tempfile.TemporaryDirectory() as folder:
            args = dict(seeds=(11,), budget=12, workers=1, output_dir=folder,
                        study_name="finite_grid", search_space=space, startup_trials=20)
            first = moead.calibrate([self.path], n_trials=1, **args)
            self.assertEqual(first["completed_trials"], 1)
            second = moead.calibrate([self.path], n_trials=5, resume=True, **args)
            self.assertEqual(second["completed_trials"], 2)
            third = moead.calibrate([self.path], n_trials=5, resume=True, **args)
            self.assertEqual(third["completed_trials"], 2)
            payloads = [json.loads(p.read_text()) for p in Path(folder, "trials").glob("trial_*.json")]
            self.assertEqual(len({json.dumps(p["parameters"], sort_keys=True) for p in payloads}), 2)


if __name__ == "__main__":
    unittest.main()
