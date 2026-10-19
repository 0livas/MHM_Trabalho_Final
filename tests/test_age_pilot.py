"""Contracts for the bounded pilot, without running the campaign in tests."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data/output/age/piloto'))
import run_pilot as pilot
import summarize as analysis


class AGEPilotTests(unittest.TestCase):
    def test_matrix_is_paired_and_excludes_reserved_seeds(self):
        cells = list(pilot.cells())
        self.assertEqual(len(cells), 72)
        self.assertEqual(len(set(cells)), 72)
        self.assertFalse(set(pilot.SEEDS) & set(pilot.RESERVED))
        self.assertEqual({(p,m) for _,p,m,_ in cells}, {(p,m) for p in (25,50,100) for m in (.1,.3)})
        for path in pilot.INSTANCES:
            for seed in pilot.SEEDS:
                self.assertEqual(sum(p==path and s==seed for p,_,_,s in cells), 6)

    def test_measured_run_counts_real_calls_and_revalidations(self):
        data = pilot.measured_run(pilot.INSTANCES[0], 8, .3, 11, 19)
        self.assertEqual(data['evaluation_batches'], [8, 8, 3])
        self.assertEqual(data['pilot']['independent_search_calls'], 19)
        self.assertEqual(data['pilot']['independent_post_calls'], 8)
        self.assertEqual(data['pilot']['independent_population_revalidations'], 8)
        self.assertEqual(data['pilot']['independent_front_revalidations'], data['points'])
        with self.assertRaisesRegex(ValueError, 'Reserved'):
            pilot.measured_run(pilot.INSTANCES[0], 8, .3, 101, 19)

    def test_diversity_counts_duplicates_and_component_changes(self):
        a = (((0,0,0),(1,0,0)), ())
        b = (((1,0,0),(0,1,1)), ())
        result = pilot.diversity([a,a,b])
        self.assertEqual(result, dict(schedules=2, allocations=1, orders=2, modes=2, waits=2))

    def test_known_indicators_and_exact_union(self):
        def row(c,e):
            return dict(makespan=c, tec_exact=dict(numerator=e,denominator=1))
        bounds = dict(C_LB=0,C_UB=10,TEC_LB_units=0,TEC_UB_units=10)
        front = [row(5,5)]
        hv, igd = analysis.indicators(front, front, bounds)
        self.assertAlmostEqual(hv, .55**2)
        self.assertEqual(igd, 0.)
        _, igd = analysis.indicators([row(6,5)], front, bounds)
        self.assertAlmostEqual(igd, .1)
        n = 2**54
        result = analysis.pareto([row(1,n+1), row(2,n), row(3,n+2), row(1,n+1)])
        self.assertEqual([(r['makespan'],r['tec_exact']['numerator']) for r in result],[(1,n+1),(2,n)])
        with self.assertRaises(ValueError):
            analysis.indicators([row(11,5)], front, bounds)

    def test_analysis_requires_completed_manifest_before_references(self):
        with TemporaryDirectory() as directory:
            out = Path(directory)
            (out/'manifest.json').write_text(json.dumps(dict(status='running',runs=[])))
            (out/'protocol.json').write_text('{}')
            with patch.object(analysis, 'OUT', out), self.assertRaisesRegex(ValueError, 'before all'):
                analysis.main()


if __name__ == '__main__':
    unittest.main()
