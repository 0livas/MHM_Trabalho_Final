"""Contratos do tuning: métrica exata, limites, persistência e processos reais."""
from dataclasses import replace
from fractions import Fraction
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import importlib
from unittest.mock import patch

import optuna

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hyperparameters_tuning.main import main, menu, parser, resolve_inputs, load_space, DEFAULT_INPUTS
from hyperparameters_tuning.common import TrialTimeout
from hyperparameters_tuning.confirm import confirm
from hyperparameters_tuning.moead import (
    calculate_bounds, calibrate, evaluate_parameters, normalized_hv, study_lock, suggest_parameters,
    SEARCH_SPACE, validate_space, resolve_parameters,
)
from problem import energy_scale, generate_choices, read_instance


class TuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"

    def test_piecewise_bounds_match_exhaustive_individual_choices(self):
        original = read_instance(self.path)
        tiny = replace(original, n=2, m=1, modes=2, days=1, slots_per_day=10,
            peaks=((3, 7),), peak_rate=Fraction(3), off_rate=Fraction(1),
            speed=(Fraction(1), Fraction(2)), power_factor=(Fraction(1), Fraction(3)),
            power=(Fraction(1),), processing=((2,), (3,)), setup=(((0, 1), (2, 0)),))
        for peak, off in ((3, 1), (1, 3), (0, 0)):
            instance = replace(tiny, peak_rate=Fraction(peak), off_rate=Fraction(off))
            _, prices = energy_scale(instance)
            choices = generate_choices(instance, prices)
            bounds = calculate_bounds(instance)
            self.assertEqual(bounds["tec_lower"], sum(min(c.cost_units for c in row) for row in choices))
            self.assertEqual(bounds["tec_upper"], sum(max(c.cost_units for c in row) for row in choices))

    def test_hv_reference_and_constant_axis(self):
        bounds = dict(cmax_lower=2, cmax_upper=10, tec_lower=3, tec_upper=20)
        self.assertAlmostEqual(normalized_hv([(2, 3)], bounds), 1.0)
        self.assertAlmostEqual(normalized_hv([(10, 20)], bounds), 0.05**2/1.05**2)
        self.assertEqual(normalized_hv([], bounds), 0)
        self.assertAlmostEqual(normalized_hv([(2, 0)], {**bounds, "tec_lower": 0, "tec_upper": 0}), 1)
        with self.assertRaises(ValueError):
            normalized_hv([(1, 3)], bounds)

    def test_conditional_neighbors_and_population_fit_budget(self):
        study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=17))
        for _ in range(12):
            trial = study.ask()
            params = suggest_parameters(trial, 40, "evaluations")
            self.assertEqual(params["population_size"], 20)
            self.assertTrue(2 <= params["n_neighbors"] <= 20)
            study.tell(trial, 0.0)

    def test_paths_resolve_from_project(self):
        self.assertEqual(resolve_inputs(["data/input/set1/6_2_1439_3_S_1-9.dat"]), [self.path])
        with self.assertRaises(ValueError):
            resolve_inputs(["data/input/not_here.dat"])

    def test_initialization_failure_scores_zero_but_technical_error_propagates(self):
        instance = read_instance(self.path)
        cases = [dict(path=str(self.path), sha256=instance.digest, bounds=calculate_bounds(instance))]
        params = dict(population_size=20, n_neighbors=5, prob_neighbor_mating=.9,
                      crossover_probability=.9, mutation_probability=.3)
        with patch("hyperparameters_tuning.moead.run_moead", side_effect=RuntimeError(
                "Sampling construtivo não encontrou posição viável para job 5")):
            result = evaluate_parameters(params, cases, (11,), 40)
            self.assertEqual(result["score"], 0)
            self.assertEqual(result["runs"][0]["status"], "initialization_failed")
        with patch("hyperparameters_tuning.moead.run_moead", side_effect=RuntimeError("Technical failure")):
            with self.assertRaisesRegex(RuntimeError, "Technical failure"):
                evaluate_parameters(params, cases, (11,), 40)

    def test_lock_rejects_second_coordinator(self):
        with tempfile.TemporaryDirectory() as folder:
            with study_lock(Path(folder) / "study.lock"):
                with self.assertRaises(RuntimeError):
                    with study_lock(Path(folder) / "study.lock"):
                        self.fail("Second lock acquired")

    def test_real_parallel_calibration_resume_and_protocol_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            args = dict(seeds=(11,), budget=40, workers=2, study_name="test_tuning", output_dir=output,
                        budget_mode="evaluations")
            report = calibrate([self.path], n_trials=2, **args)
            self.assertEqual(report["completed_trials"], 2)
            for number in range(2):
                data = json.loads((output / "trials" / f"trial_{number:06d}.json").read_text())
                self.assertEqual(data["runs"][0]["attempts"], 40)
                self.assertTrue(0 <= data["score"] <= 1)
                self.assertNotEqual(data["worker_pid"], os.getpid())
            resumed = calibrate([self.path], n_trials=3, resume=True, **args)
            self.assertEqual(resumed["completed_trials"], 3)
            unchanged = calibrate([self.path], n_trials=3, resume=True, **args)
            self.assertEqual(unchanged["completed_trials"], 3)
            with self.assertRaises(ValueError):
                calibrate([self.path], n_trials=4, resume=True, **{**args, "budget": 41})
            with self.assertRaises(ValueError):
                calibrate([self.path], n_trials=4, **args)

    def test_real_sequential_calibration(self):
        with tempfile.TemporaryDirectory() as folder:
            report = calibrate([self.path], seeds=(11, 29), n_trials=1, budget=40,
                               output_dir=folder, study_name="sequential_test", budget_mode="evaluations")
            self.assertEqual(report["completed_trials"], 1)
            data = json.loads((Path(folder) / "trials/trial_000000.json").read_text())
            self.assertEqual(len(data["runs"]), 2)
            self.assertEqual(sum(row["attempts"] for row in data["runs"]), 80)

    def test_gpu_rejected_before_creating_study(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "must_not_exist"
            with self.assertRaises(SystemExit) as result:
                main(["--device", "gpu", "--output-dir", str(path)])
            self.assertEqual(result.exception.code, 2)
            self.assertFalse(path.exists())

    def test_menu_parallel_cpu_choice(self):
        answers = ["1", "2", "2", str(self.path), "11,29", "2", "20", "42", "2", "40", "0", "", "menu_test", "n"]
        with patch("builtins.input", side_effect=answers):
            args = menu()
        self.assertEqual((args.algorithm, args.workers, args.trials, args.max_evaluations),
                         ("moead", 2, 2, 40))
        self.assertIsNone(args.trial_timeout)
        self.assertEqual(args.startup_trials, 20)
        self.assertEqual(args.sampler_seed, 42)

    def test_default_grid_covers_exact_native_fields_and_five_levels(self):
        from dataclasses import fields
        from metaheuristics.moead import MOEADConfig
        self.assertEqual(set(SEARCH_SPACE), {field.name for field in fields(MOEADConfig)} - {"seed"})
        for name, values in SEARCH_SPACE.items():
            self.assertGreaterEqual(len(set(values)), 5, name)
        study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=31))
        for _ in range(20):
            trial = study.ask()
            params = suggest_parameters(trial, 40, "effort")
            self.assertEqual(set(trial.params), set(SEARCH_SPACE))
            MOEADConfig(seed=11, **params)
            study.tell(trial, 0.5)

    def test_custom_native_effort_runs_and_records_exact_parameters(self):
        space = {key: list(values) for key, values in SEARCH_SPACE.items()}
        space.update(population_size=[4], max_evaluations=[12], n_neighbors=[2])
        with tempfile.TemporaryDirectory() as folder:
            report = calibrate([self.path], seeds=(11,), n_trials=1, output_dir=folder,
                               study_name="native_test", search_space=space, budget_mode="effort")
            config = report["moead_config"]
            self.assertEqual((config["population_size"], config["max_evaluations"], config["n_neighbors"]), (4, 12, 2))
            self.assertEqual(set(config), set(SEARCH_SPACE))
            data = json.loads((Path(folder) / "trials/trial_000000.json").read_text())
            self.assertEqual(data["runs"][0]["attempts"], 12)
            self.assertEqual(data["runs"][0]["full_generations"], 3)
            with self.assertRaises(ValueError):
                calibrate([self.path], seeds=(11,), n_trials=2, output_dir=folder, resume=True,
                    study_name="native_test", search_space={**space, "max_evaluations": [16]}, budget_mode="effort")

    def test_invalid_spaces_and_json_customization(self):
        for change in ({"mutation_method": ["bitflip"]}, {"n_neighbors": [21]},
                       {"max_evaluations": [10]}, {"population_size": [[1]]},
                       {"mutation_probability": [float("nan")]}, {"n_neighbors": [True]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_space({**SEARCH_SPACE, **change}, 8000, "effort")
        with self.assertRaises(ValueError):
            validate_space(SEARCH_SPACE, 8000, "generations")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "space.json"
            path.write_text(json.dumps(SEARCH_SPACE), encoding="utf-8")
            self.assertEqual(load_space(path), SEARCH_SPACE)

    def test_reordered_json_has_same_native_parameters(self):
        reversed_space = dict(reversed(list(SEARCH_SPACE.items())))
        study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=1))
        parameters = suggest_parameters(study.ask(), 8000, "effort", reversed_space)
        self.assertEqual(set(parameters), set(SEARCH_SPACE))
        self.assertEqual(list(validate_space(reversed_space, 8000, "effort")), list(SEARCH_SPACE))

    def test_every_other_algorithm_parallel_history_and_resume(self):
        for algorithm in ("spea2", "age", "vns_vnd"):
            plugin = importlib.import_module("hyperparameters_tuning."+algorithm)
            with self.subTest(algorithm=algorithm), tempfile.TemporaryDirectory() as folder:
                args = dict(seeds=(11,), budget=40, workers=2, study_name="parallel_"+algorithm,
                            output_dir=folder, budget_mode="evaluations")
                report = plugin.calibrate([self.path], n_trials=2, **args)
                self.assertEqual(report["algorithm"], algorithm)
                self.assertEqual(report["completed_trials"], 2)
                result = json.loads((Path(folder) / "trials/trial_000000.json").read_text())
                self.assertLessEqual(result["runs"][0]["attempts"], 40)
                self.assertTrue(0 <= report["best_score"] <= 1)
                resumed = plugin.calibrate([self.path], n_trials=3, resume=True, **args)
                self.assertEqual(resumed["completed_trials"], 3)

    def test_all_algorithms_default_to_fixed_evaluations_and_effort_runs_custom_caps(self):
        for algorithm in ("moead", "spea2", "age", "vns_vnd"):
            plugin = importlib.import_module("hyperparameters_tuning."+algorithm)
            self.assertEqual(plugin.SUPPORTED_BUDGET_MODES[0], "evaluations")
            space = {name: [values[0]] for name, values in plugin.SEARCH_SPACE.items()}
            space["max_evaluations"] = [25]
            if "population_size" in space:
                space["population_size"] = [4]
            if "n_neighbors" in space:
                space["n_neighbors"] = [2]
            trial = optuna.create_study().ask()
            parameters = plugin.suggest_parameters(trial, 8000, "effort", search_space=space)
            self.assertEqual(set(trial.params), set(plugin.SEARCH_SPACE))
            with self.subTest(algorithm=algorithm), tempfile.TemporaryDirectory() as folder:
                report = plugin.calibrate([self.path], seeds=(11,), n_trials=1, budget_mode="effort",
                    search_space=space, output_dir=folder, study_name="effort_"+algorithm)
                self.assertEqual(report["budget_mode"], "effort")
                self.assertEqual(report["solver_config"]["max_evaluations"], 25)
                self.assertEqual(set(report["solver_config"]), set(plugin.SEARCH_SPACE))
                data = json.loads((Path(folder) / "trials/trial_000000.json").read_text())
                self.assertEqual(data["parameters"], report["solver_config"])
                self.assertLessEqual(data["runs"][0]["attempts"], 25)

    def test_protocol_defaults_follow_group_decision(self):
        args = parser().parse_args([])
        self.assertEqual((args.trials, args.max_evaluations, args.seeds, args.trial_timeout),
                         (60, 8000, "11,29,47", None))
        self.assertEqual(len(DEFAULT_INPUTS), 6)
        sizes = sorted(read_instance(path).n for path in resolve_inputs(DEFAULT_INPUTS))
        self.assertEqual(sizes, [6, 14, 50, 50, 250, 250])

    def test_timeout_fails_only_the_slow_trial(self):
        instance = read_instance(self.path)
        cases = [dict(path=str(self.path), sha256=instance.digest, bounds=calculate_bounds(instance))]
        params = dict(population_size=20, n_neighbors=5, prob_neighbor_mating=.9,
                      crossover_probability=.9, mutation_probability=.3)
        with self.assertRaises(TrialTimeout):
            evaluate_parameters(params, cases, (11, 29), 40, trial_timeout=1e-9)
        with tempfile.TemporaryDirectory() as folder:
            report = calibrate([self.path], seeds=(11, 29), n_trials=2, budget=40, output_dir=folder,
                               study_name="timeout_test", budget_mode="evaluations", trial_timeout=1e-9)
            self.assertEqual((report["completed_trials"], report["failed_trials"]), (0, 2))
            protocol = json.loads((Path(folder) / "protocol.json").read_text())
            self.assertEqual((protocol["version"], protocol["trial_timeout"]), (6, 1e-9))
            with self.assertRaises(ValueError):
                calibrate([self.path], seeds=(11, 29), n_trials=3, budget=40, output_dir=folder, resume=True,
                          study_name="timeout_test", budget_mode="evaluations", trial_timeout=60)

    def test_confirm_reruns_top_configs_per_budget_and_resumes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            calibrate([self.path], seeds=(11,), n_trials=3, budget=40, output_dir=output,
                      study_name="confirm_test", budget_mode="evaluations")
            report = confirm(output, top=2, budgets=(40, 60))
            self.assertEqual(len(report["configurations"]), 2)
            self.assertEqual(set(report["ranking"]), {"40", "60"})
            self.assertEqual(report["recommended"]["budget"], 60)
            self.assertEqual(report["recommended"]["solver_config"]["max_evaluations"], 60)
            for config in report["configurations"]:
                data = json.loads((output / f"confirmation/trial_{config['trial']:06d}_E60.json").read_text())
                self.assertEqual(data["runs"][0]["attempts"], 60)
            self.assertEqual(len(list((output / "confirmation").glob("trial_*.json"))), 4)
            with patch("hyperparameters_tuning.confirm.evaluate_parameters",
                       side_effect=AssertionError("reexecutou")):
                self.assertEqual(confirm(output, top=2, budgets=(40, 60))["ranking"], report["ranking"])
            protocol = json.loads((output / "protocol.json").read_text())
            protocol["source_sha256"] = {}
            (output / "protocol.json").write_text(json.dumps(protocol))
            with self.assertRaises(ValueError):
                confirm(output, top=2, budgets=(40, 60))

    def test_list_space_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "unused"
            self.assertEqual(main(["--list-space", "--output-dir", str(path)]), 0)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
