"""Regression tests for the instance-only external indicator bounds."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'data/output/final_comparison'))
from problem import read_instance, interval_cost_units, energy_scale, generate_choices
from normalization import calculate_bounds, energy_extrema, normalize, normalize_exact


class IndicatorBoundsTests(unittest.TestCase):
    def setUp(self):
        self.source = read_instance(ROOT/'data/input/set1/6_2_1439_3_S_1-9.dat')

    def test_breakpoints_match_every_integer_start_with_multiple_peaks(self):
        instance = replace(self.source, days=2, slots_per_day=10, peaks=((2,5),(12,18)))
        for duration in range(1,21):
            for on, off in [(3,7),(7,3),(0,0),(2,2)]:
                values=[interval_cost_units(instance,s,s+duration,on,off)
                        for s in range(instance.horizon-duration+1)]
                self.assertEqual(energy_extrema(instance,duration,on,off),(min(values),max(values)))

    def test_bounds_equal_exhaustive_individual_option_relaxation(self):
        # Tiny horizon exercises duration exclusion without enumerating schedules.
        instance=replace(self.source,n=2,days=1,slots_per_day=20,peaks=((4,11),),
                         processing=((2,3),(5,4)),setup=(((0,0),(0,0)),((0,0),(0,0))))
        scale,prices=energy_scale(instance)
        options=generate_choices(instance,prices)
        bounds=calculate_bounds(instance)
        self.assertEqual(bounds['tec_scale'],scale)
        self.assertEqual(bounds['TEC_LB_units'],sum(min(c.cost_units for c in job) for job in options))
        self.assertEqual(bounds['TEC_UB_units'],sum(max(c.cost_units for c in job) for job in options))
        self.assertEqual(bounds['C_LB'],max(max(min(c.end-c.start for c in job) for job in options),
                         (sum(min(c.end-c.start for c in job) for job in options)+instance.m-1)//instance.m))

    def test_normalized_endpoints_and_no_clipping(self):
        b=dict(C_LB=2,C_UB=10,TEC_LB_units=100,TEC_UB_units=500)
        self.assertEqual(normalize(2,100,b),(0.,0.))
        self.assertEqual(normalize(10,500,b),(1.,1.))
        for c,e in [(1,100),(11,100),(2,99),(2,501)]:
            with self.assertRaises(ValueError): normalize(c,e,b)

    def test_degenerate_bounds_stop(self):
        # All energy zero: UB==LB must be rejected, not given an ad-hoc scale.
        with self.assertRaisesRegex(ValueError,'Degenerate'):
            calculate_bounds(replace(self.source, power=tuple(0 for _ in self.source.power)))

    def test_bounds_ignore_max_cost_and_rng(self):
        a=calculate_bounds(self.source)
        b=calculate_bounds(replace(self.source,max_cost=self.source.max_cost*100))
        self.assertEqual(a,b)


class GeometricIndicatorTests(unittest.TestCase):
    def test_known_hypervolume_and_igd_plus(self):
        import analyze_final as analysis
        b=dict(C_LB=0,C_UB=10,TEC_LB_units=0,TEC_UB_units=10)
        front=[dict(makespan=2,tec_exact=dict(numerator=8,denominator=1)),
               dict(makespan=8,tec_exact=dict(numerator=2,denominator=1))]
        expected=(1.05-.2)*(1.05-.8)+(1.05-.8)*(1.05-.2)-(1.05-.8)**2
        self.assertAlmostEqual(analysis.hv(front,b),expected)
        self.assertAlmostEqual(float(analysis.IGDPlus(analysis.points(front,b))(analysis.points(front,b))),0.)

    def test_exact_pareto_keeps_distinctions_beyond_float_precision(self):
        import analyze_final as analysis
        def row(c,e):return dict(makespan=c,tec_exact=dict(numerator=e,denominator=1))
        n=2**54
        rows=[row(1,n+1),row(2,n),row(3,n+2),row(1,n+1)]
        self.assertEqual([analysis.key(r) for r in analysis.pareto(rows)],[(1,n+1),(2,n)])
        self.assertEqual(analysis.coverage([(1,n+1)],[(2,n)]),0.)
        self.assertEqual(analysis.coverage([(1,n+1)],[(1,n+1),(3,n+2)]),1.)

    def test_baselines_guarded_before_all_searches(self):
        import analyze_final as analysis
        with self.assertRaises(AssertionError):
            analysis.reference_fronts(dict(status='running'),{},ROOT)


class CellOutcomeTests(unittest.TestCase):
    def test_initialization_failure_has_no_quality_values_or_search_attempts(self):
        import run_final as runner
        spec=dict(experiment='B',instance='data/input/set2/750_10_1439_5_S_1-9.dat',
            instance_sha256='instance-hash',algorithm='vns_vnd',seed=101,budget=2000,
            block=135,order_in_block=['vns_vnd','spea2','moead'],
            file='runs/B__750_10_1439_5_S_1-9__vns_vnd__b2000__s101.json')
        sources={name:'source-hash' for name in runner.SOURCES}
        outcome=runner.initialization_failure_outcome(spec,initialization_attempts=200,
            elapsed_seconds=None,failure_reason='initializer exhausted',source_sha256=sources,
            occurred_utc='2026-10-08T12:12:04+00:00',provenance='official manifest')
        self.assertEqual(outcome['status'],'initialization_failed')
        self.assertEqual(outcome['failure_stage'],'initialization')
        self.assertEqual(outcome['planned_max_evaluations'],2000)
        self.assertEqual(outcome['search_attempts'],0)
        self.assertEqual((outcome['feasible_evaluations'],outcome['rejected_evaluations']),(0,0))
        self.assertEqual(outcome['initialization_attempts'],200)
        self.assertIsNone(outcome['elapsed_seconds'])
        self.assertTrue(all(v is None for v in outcome['quality_metrics'].values()))
        runner.seal_outcome(outcome)
        self.assertEqual(runner.validate_outcome(outcome,spec,{}),'initialization_failed')

    def test_outcome_statuses_and_failure_accounting_validation(self):
        import run_final as runner
        spec=dict(experiment='B',instance='data/input/x.dat',instance_sha256='h',algorithm='vns_vnd',
                  seed=1,budget=2000,block=0,order_in_block=['vns_vnd','spea2','moead'],file='runs/x.json')
        sources={name:'h' for name in runner.SOURCES}
        failure=runner.initialization_failure_outcome(spec,initialization_attempts=200,elapsed_seconds=1.,
            failure_reason='known',source_sha256=sources,occurred_utc='now',provenance='test')
        runner.seal_outcome(failure)
        failure['search_attempts']=1;runner.seal_outcome(failure)
        with self.assertRaisesRegex(ValueError,'contaminated'):
            runner.validate_outcome(failure,spec,{})
        failure['search_attempts']=0;runner.seal_outcome(failure)
        failure['status']='mystery';runner.seal_outcome(failure)
        with self.assertRaisesRegex(ValueError,'Unknown cell outcome'):
            runner.validate_outcome(failure,spec,{})

    def test_execution_failed_is_technical_and_metrics_are_null(self):
        # The execution_failed record contains no synthetic front or score.
        failure=dict(status='execution_failed',run_completed=False,failure_stage='execution',
                     search_attempts=None,feasible_evaluations=None,rejected_evaluations=None,
                     quality_metrics=None)
        self.assertEqual(failure['status'],'execution_failed')
        self.assertIsNone(failure['quality_metrics'])


if __name__=='__main__': unittest.main()
