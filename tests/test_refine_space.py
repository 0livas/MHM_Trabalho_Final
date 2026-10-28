"""Focused finite-grid enlargement and CLI controls."""
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hyperparameters_tuning.refine import refined_space, refine
from hyperparameters_tuning.main import parser


class RefineSpaceTests(unittest.TestCase):
    def test_preserves_originals_and_adds_neighbor_midpoints(self):
        original = dict(population_size=[20, 50, 100], mutation_probability=[.1, .5, .9],
                        max_evaluations=[2000, 8000])
        actual = refined_space(original, [dict(population_size=50, mutation_probability=.5)],
                               "evaluations")
        self.assertEqual(actual["population_size"], [20, 35, 50, 75, 100])
        self.assertAlmostEqual(actual["mutation_probability"][1], .3)
        self.assertAlmostEqual(actual["mutation_probability"][-2], .7)
        self.assertEqual(actual["max_evaluations"], [2000, 8000])
        self.assertEqual(original["population_size"], [20, 50, 100])

    def test_adjacent_integer_levels_do_not_create_invalid_values(self):
        self.assertEqual(refined_space({"n_neighbors": [2, 3]}, [{"n_neighbors": 2}],
                                       "evaluations"), {"n_neighbors": [2, 3]})

    def test_effort_can_refine_budget(self):
        self.assertEqual(refined_space({"max_evaluations": [2000, 8000]},
                         [{"max_evaluations": 2000}], "effort")["max_evaluations"],
                         [2000, 5000, 8000])

    def test_startup_can_be_disabled_from_cli(self):
        self.assertEqual(parser().parse_args(["--startup-trials", "0"]).startup_trials, 0)

    def test_study_refinement_validates_and_refuses_overwrite(self):
        from hyperparameters_tuning import moead
        params = {name: values[0] for name, values in moead.SEARCH_SPACE.items()}
        params["max_evaluations"] = 8000
        trial = SimpleNamespace(number=0, value=.8, user_attrs={"effective_parameters": params})
        study = SimpleNamespace(get_trials=lambda **kw: [trial], trials=[trial])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "study.sqlite3").touch()
            protocol = dict(study_name="test", search_space=moead.SEARCH_SPACE,
                            budget_mode="evaluations", budget_per_run=8000, algorithm="moead")
            (root / "protocol.json").write_text(json.dumps(protocol))
            destination = root / "new.json"
            with patch("hyperparameters_tuning.refine.optuna.storages.RDBStorage"), \
                 patch("hyperparameters_tuning.refine.optuna.load_study", return_value=study):
                actual = refine(root, destination, top=1)
                self.assertEqual(json.loads(destination.read_text()), actual)
                for name, values in moead.SEARCH_SPACE.items():
                    self.assertTrue(set(values) <= set(actual[name]))
                with self.assertRaises(ValueError):
                    refine(root, destination, top=1)


if __name__ == "__main__":
    unittest.main()
