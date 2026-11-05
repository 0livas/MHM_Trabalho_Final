"""Isolated campaign identity and VNS diagnostics tests; never starts tuning."""
from copy import deepcopy
from types import SimpleNamespace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from experiments import adapters, campaign, config
from experiments.runner import Campaign, build_tasks, result_path
from metaheuristics.vns_vnd import VNSVND
from problem import read_instance


def tree_bytes(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob('*') if p.is_file()}


class CampaignIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'new-campaign'
        self.instances = config.select_instances(['small'])[:1]
        self.options = dict(total_seconds=1, memory_limit_mib=64, max_jobs=6, grace_seconds=1)

    def new_campaign(self, **kwargs):
        return Campaign(self.output, base_seed=1000, exact_options=self.options, budget=16, **kwargs)

    def prepare(self):
        c = self.new_campaign()
        c.run(['vns_vnd'], self.instances, 1, stop_after=0)
        return c

    def assert_blocked_unchanged(self, c, message):
        before = tree_bytes(self.output)
        with patch.object(c, '_execute', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(ValueError, message):
                c.run(['vns_vnd'], self.instances, 1)
        self.assertEqual(tree_bytes(self.output), before)

    def test_compatible_resume_keeps_completed_results_and_source_identity(self):
        c = self.prepare()
        task = build_tasks(['vns_vnd'], self.instances, 1, 1000)[0]
        target = result_path(self.output, task)
        target.parent.mkdir(parents=True)
        target.write_bytes(b'historical result sentinel')
        sidecar = target.with_suffix('.schedules.json.gz')
        sidecar.write_bytes(b'compressed result sentinel')
        c.ledger.state['runs'][task.key] = dict(algorithm='vns_vnd', instance=task.instance.name,
                                             status='COMPLETED', wall_seconds=1,
                                             result_file=str(target.relative_to(self.output)))
        c.ledger.save()
        manifest_before = json.loads((self.output/'experiment_manifest.json').read_text())
        c = self.new_campaign()
        with patch.object(c, '_execute', side_effect=AssertionError('must not rerun completed task')):
            outcome = c.run(['vns_vnd'], self.instances, 1)
        self.assertEqual(outcome['completed'], [])
        self.assertEqual(target.read_bytes(), b'historical result sentinel')
        self.assertEqual(sidecar.read_bytes(), b'compressed result sentinel')
        after = json.loads((self.output/'experiment_manifest.json').read_text())
        self.assertEqual(after['source_sha256'], manifest_before['source_sha256'])
        self.assertEqual(len(after['history']), 2)

    def test_unchanged_instance_allows_adding_another_instance(self):
        self.prepare()
        path = self.output/'experiment_manifest.json'
        before = json.loads(path.read_text())['instances'][self.instances[0].name]
        instances = config.select_instances(['small'])[:2]
        self.new_campaign().run(['vns_vnd'], instances, 1, stop_after=0)
        after = json.loads(path.read_text())['instances']
        self.assertEqual(after[self.instances[0].name], before)
        self.assertIn(instances[1].name, after)

    def test_modified_instance_blocks_resume_before_any_campaign_write(self):
        original = self.instances[0]
        path = Path(self.temp.name) / original.name
        path.write_bytes(original.path.read_bytes())
        spec = SimpleNamespace(path=path, name=original.name,
                               relative=original.relative, tier=original.tier)
        campaign = self.new_campaign()
        campaign.run(['vns_vnd'], [spec], 1, stop_after=0)
        task = build_tasks(['vns_vnd'], [spec], 1, 1000)[0]
        target = result_path(self.output, task)
        target.parent.mkdir(parents=True)
        target.write_bytes(b'existing result')
        campaign.ledger.state['runs'][task.key] = dict(
            algorithm='vns_vnd', instance=spec.name, status='COMPLETED',
            wall_seconds=1, result_file=str(target.relative_to(self.output)))
        campaign.ledger.save()
        path.write_bytes(path.read_bytes() + b'\n')
        before = tree_bytes(self.output)
        with self.assertRaisesRegex(ValueError, 'Instância.*incompatível'):
            self.new_campaign().run(['vns_vnd'], [spec], 2, stop_after=0)
        self.assertEqual(tree_bytes(self.output), before)
        self.assertEqual(target.read_bytes(), b'existing result')

    def test_changed_unselected_instance_blocks_resume(self):
        fake_root = Path(self.temp.name) / 'project'
        specs = []
        for original in config.select_instances(['small'])[:2]:
            path = fake_root / 'data/input' / original.relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original.path.read_bytes())
            specs.append(SimpleNamespace(path=path, name=original.name,
                                         relative=original.relative, tier=original.tier))
        sources = self.new_campaign().source_fingerprints()
        with patch('experiments.runner.PROJECT_ROOT', fake_root), \
             patch.object(Campaign, 'source_fingerprints', return_value=sources):
            self.new_campaign().run(['vns_vnd'], specs, 1, stop_after=0)
            specs[1].path.write_bytes(specs[1].path.read_bytes() + b'\n')
            before = tree_bytes(self.output)
            with self.assertRaisesRegex(ValueError, 'Instância.*incompatível'):
                self.new_campaign().run(['vns_vnd'], specs[:1], 1, stop_after=0)
            self.assertEqual(tree_bytes(self.output), before)

    def test_direct_manifest_write_rejects_changed_instance(self):
        original = self.instances[0]
        path = Path(self.temp.name) / original.name
        path.write_bytes(original.path.read_bytes())
        spec = SimpleNamespace(path=path, name=original.name,
                               relative=original.relative, tier=original.tier)
        c = self.new_campaign()
        c.run(['vns_vnd'], [spec], 1, stop_after=0)
        path.write_bytes(path.read_bytes() + b'\n')
        before = tree_bytes(self.output)
        with self.assertRaisesRegex(ValueError, 'Instância.*incompatível'):
            c.write_manifest(['vns_vnd'], [spec], 1, c.ledger.state['configurations'])
        self.assertEqual(tree_bytes(self.output), before)

    def test_missing_instance_digest_blocks_resume(self):
        self.prepare()
        path = self.output/'experiment_manifest.json'
        manifest = json.loads(path.read_text())
        del manifest['instances'][self.instances[0].name]['sha256']
        path.write_text(json.dumps(manifest))
        self.assert_blocked_unchanged(self.new_campaign(), 'sem identidade persistida')

    def test_source_change_blocks_before_checkpoint_or_manifest_write(self):
        self.prepare()
        c = self.new_campaign()
        sources = c.source_fingerprints()
        sources['src/metaheuristics/vns_vnd.py'] = 'changed'
        with patch.object(c, 'source_fingerprints', return_value=sources):
            self.assert_blocked_unchanged(c, 'Fontes incompatíveis')

    def test_checkpoint_source_change_is_not_overwritten_by_manifest(self):
        c = self.prepare()
        c.ledger.state['source_sha256']['src/metaheuristics/vns_vnd.py'] = 'changed'
        c.ledger.save()
        self.assert_blocked_unchanged(self.new_campaign(), 'Fontes incompatíveis')

    def test_configuration_change_blocks_even_without_completed_runs(self):
        self.prepare()
        changed = deepcopy(config.resolve_configuration('vns_vnd', exact_options=self.options, budget=16))
        changed['parameters']['shaking_attempts'] += 1
        with patch('experiments.runner.resolve_configuration', return_value=changed):
            self.assert_blocked_unchanged(self.new_campaign(), 'Configuração')
            # The legacy API flag cannot bypass the guard either.
            self.assert_blocked_unchanged(self.new_campaign(force_config=True), 'Configuração')

    def test_reset_cannot_modify_an_incompatible_custom_campaign(self):
        self.prepare()
        before = tree_bytes(self.output)
        args = campaign.parse_args(['--output-dir', str(self.output), '--budget', '16', '--yes'])
        sources = self.new_campaign().source_fingerprints()
        sources['src/metaheuristics/vns_vnd.py'] = 'changed'
        with patch.object(Campaign, 'source_fingerprints', return_value=sources):
            with self.assertRaisesRegex(ValueError, 'Fontes incompatíveis'):
                campaign.do_reset(args, 'vns_vnd')
        self.assertEqual(tree_bytes(self.output), before)

    def test_manifest_configuration_mismatch_blocks_without_mutating_checkpoint(self):
        self.prepare()
        path = self.output/'experiment_manifest.json'
        manifest = json.loads(path.read_text())
        manifest['configurations']['vns_vnd']['parameters']['shaking_attempts'] += 1
        path.write_text(json.dumps(manifest))
        self.assert_blocked_unchanged(self.new_campaign(), 'Configuração')

    def test_missing_manifest_and_orphan_results_are_not_adopted(self):
        self.output.mkdir()
        sentinel = self.output/'old-result.json'
        sentinel.write_bytes(b'old')
        self.assert_blocked_unchanged(self.new_campaign(), 'sem checkpoint')
        # A checkpoint without its manifest is also insufficient provenance.
        sentinel.unlink()  # only the test fixture, inside TemporaryDirectory
        c = self.new_campaign()
        c.ledger.save()
        self.assert_blocked_unchanged(self.new_campaign(), 'sem manifesto')

    def test_direct_manifest_write_rechecks_sources(self):
        c = self.prepare()
        sources = c.source_fingerprints()
        sources['src/metaheuristics/vns_vnd.py'] = 'changed'
        before = tree_bytes(self.output)
        with patch.object(c, 'source_fingerprints', return_value=sources):
            with self.assertRaisesRegex(ValueError, 'Fontes incompatíveis'):
                c.write_manifest(['vns_vnd'], self.instances, 1, c.ledger.state['configurations'])
        self.assertEqual(tree_bytes(self.output), before)

    def test_legacy_windows_source_paths_are_compared_without_rewriting_hashes(self):
        c = self.prepare()
        path = self.output/'experiment_manifest.json'
        manifest = json.loads(path.read_text())
        manifest['source_sha256'] = {k.replace('/', '\\'): v for k,v in manifest['source_sha256'].items()}
        path.write_text(json.dumps(manifest))
        sources, _ = self.new_campaign().validate_identity()
        self.assertEqual(sources, c.source_fingerprints())

    def test_historical_output_and_descendants_are_protected_for_mutating_actions(self):
        self.assertNotEqual(config.DEFAULT_OUTPUT, config.LEGACY_OUTPUT)
        before = tree_bytes(self.output) if self.output.exists() else {}
        with patch('experiments.config.LEGACY_OUTPUT', self.output):
            for destination in (self.output, self.output/'child'):
                with self.assertRaisesRegex(ValueError, 'histórico'):
                    Campaign(destination, base_seed=1000, exact_options=self.options)
                args = campaign.parse_args(['--output-dir', str(destination)])
                with self.assertRaisesRegex(ValueError, 'histórico'):
                    campaign.run_metrics(args)
                with self.assertRaisesRegex(ValueError, 'histórico'):
                    campaign.do_reset(args, 'vns_vnd')
        self.assertFalse(self.output.exists())
        self.assertEqual(before, {})

    def test_vns_configuration_is_explicitly_inherited_and_provisional(self):
        loaded = config.resolve_configuration('vns_vnd', exact_options=self.options, budget=16)
        self.assertEqual(loaded['status'], 'provisional_inherited_pre_lpt')
        self.assertEqual(loaded['initialization_strategy'], 'randomized_lpt_earliest_end_v1')
        self.assertEqual([loaded['parameters'][k] for k in
                          ('initial_solutions', 'max_candidates_per_neighborhood', 'shaking_attempts')],
                         [16, 10, 20])
        self.assertIn('não calibrada para LPT', loaded['calibration_compatibility'])

    def test_tiny_spawned_run_persists_initialization_and_resumes(self):
        c = self.new_campaign()
        c.snapshot_interval = None
        outcome = c.run(['vns_vnd'], self.instances, 1)
        self.assertEqual(outcome['completed'][0]['status'], 'COMPLETED')
        task = build_tasks(['vns_vnd'], self.instances, 1, 1000)[0]
        target = result_path(self.output, task)
        data = json.loads(target.read_text())
        init = data['initialization']
        self.assertEqual(init['strategy'], 'randomized_lpt_earliest_end_v1')
        self.assertEqual((init['construction_attempts'], init['obtained'], init['initial_evaluations']), (16,16,16))
        self.assertGreater(init['unique_schedules'], 0)
        self.assertEqual(data['evaluations'], 16)
        saved = target.read_bytes()
        self.new_campaign().run(['vns_vnd'], self.instances, 1)
        self.assertEqual(target.read_bytes(), saved)

    def test_failed_initialization_diagnostics_survive_adapter(self):
        instance = read_instance(self.instances[0].path)
        with patch('metaheuristics.vns_vnd._random_greedy_schedule', return_value=None):
            outcome = adapters._run_metaheuristic('vns_vnd', instance,
                dict(initial_solutions=1, max_evaluations=1, max_candidates_per_neighborhood=10, shaking_attempts=20),
                1001, self.output, None, lambda: {}, 0)
        self.assertEqual(outcome['status'], 'INIT_FAILED')
        self.assertEqual(outcome['initialization']['construction_attempts'], 50)
        self.assertEqual(outcome['initialization']['obtained'], 0)
        self.assertEqual(outcome['initialization']['initial_evaluations'], 0)

    def test_vns_snapshot_keeps_available_initialization(self):
        instance = read_instance(self.instances[0].path)
        self.output.mkdir()
        snapshot = self.output/'snapshot.json'
        with patch.object(VNSVND, '_evaluate', VNSVND._evaluate):
            adapters.install_vns_snapshots(instance, snapshot, 0,
                lambda: dict(peak_rss_mib=1, source='test'), 0)
            from metaheuristics.vns_vnd import VNSConfig
            result = VNSVND(instance, VNSConfig(max_evaluations=5, initial_solutions=1)).run()
        data = json.loads(snapshot.read_text())
        self.assertEqual(data['initialization'], result.initialization)


if __name__ == '__main__':
    unittest.main()
