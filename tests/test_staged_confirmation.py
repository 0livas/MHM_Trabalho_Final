"""Promotion, independent seeds and resumable confirmation contracts."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hyperparameters_tuning.confirm import confirm, promote, select_top


class ConfirmationStagesTests(unittest.TestCase):
    def test_initial_selection_keeps_winner_and_adds_diversity(self):
        trials = [SimpleNamespace(number=i, value=1-i*.1, user_attrs={
            'effective_parameters': dict(population_size=p, mutation=m, max_evaluations=40)})
            for i, (p, m) in enumerate([(50, .1), (50, .2), (300, .9), (100, .1)])]
        study = SimpleNamespace(get_trials=lambda **kwargs: trials)
        self.assertEqual([c['trial'] for c in select_top(study, 2, 1)], [0, 2])

    def test_diversity_preserves_winner_and_distinct_population(self):
        configs = [dict(trial=i, parameters=dict(population_size=p, mutation=m))
                   for i, (p, m) in enumerate([(50, .1), (50, .2), (300, .9), (100, .1)])]
        results = {(i, 8000): {'score': 1-i*.1} for i in range(4)}
        selected = promote(configs, results, 8000, .5, 1)
        self.assertEqual([c['trial'] for c in selected], [0, 2])

    def test_stages_new_seeds_resume_and_plan_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / 'study.sqlite3').touch()
            protocol = dict(algorithm='age', cases=[dict(path='case', sha256='digest')],
                            seeds=[11, 29, 47], study_name='test', source_sha256={})
            (output / 'protocol.json').write_text(json.dumps(protocol))
            trials = [SimpleNamespace(number=i, value=1-i*.1, user_attrs={
                'effective_parameters': dict(population_size=20+i, max_evaluations=40)}) for i in range(4)]
            study = SimpleNamespace(get_trials=lambda **kwargs: trials)
            plugin = SimpleNamespace(resolve_parameters=lambda params, budget, mode:
                                     dict(params, max_evaluations=budget))
            calls = []
            def evaluate(params, cases, seeds, budget, **kwargs):
                calls.append((params, seeds, budget))
                return dict(parameters=params, score=1/params['population_size'],
                            instance_scores=[dict(instance='case', median_score=.5)], runs=[])
            with patch('hyperparameters_tuning.confirm.source_fingerprint', return_value={}), \
                 patch('hyperparameters_tuning.confirm.read_instance', return_value=SimpleNamespace(digest='digest')), \
                 patch('hyperparameters_tuning.confirm.algorithm_module', return_value=plugin), \
                 patch('hyperparameters_tuning.confirm.optuna.storages.RDBStorage'), \
                 patch('hyperparameters_tuning.confirm.optuna.load_study', return_value=study), \
                 patch('hyperparameters_tuning.confirm.evaluate_parameters', side_effect=evaluate):
                report = confirm(output, top=4, budgets=(40, 60, 80), promote_fraction=.5)
                self.assertEqual(len(calls), 7)
                self.assertEqual([len(report['ranking'][str(b)]) for b in (40, 60, 80)], [4, 2, 1])
                self.assertEqual(len(report['seeds']), 5)
                self.assertFalse(set(report['seeds']) & set(protocol['seeds']))
                calls.clear()
                self.assertEqual(confirm(output, top=4, budgets=(40, 60, 80),
                                         promote_fraction=.5)['ranking'], report['ranking'])
                self.assertFalse(calls)
                with self.assertRaises(ValueError):
                    confirm(output, top=4, budgets=(40, 60, 80), seeds=(11, 101), promote_fraction=.5)
                with self.assertRaises(ValueError):
                    confirm(output, top=4, budgets=(40, 60, 80), seeds=(201, 202), promote_fraction=.5)


if __name__ == '__main__':
    unittest.main()
