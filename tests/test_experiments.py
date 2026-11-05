"""Campanha final: indicadores com respostas conhecidas, ledger e registro."""
from pathlib import Path
import sys
import unittest
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from experiments import metrics as m
from experiments.adapters import nondominated
from experiments.config import ALGORITHM_BY_ID, INSTANCES, load_hyperparameters, select_instances
from experiments.ledger import Ledger
from experiments.runner import build_tasks


class IndicatorTests(unittest.TestCase):
    ref = [(0.0, 1.0), (0.5, 0.5), (1.0, 0.0)]

    def test_hv_of_reference_corners(self):
        self.assertAlmostEqual(m.hypervolume_2d([(0.0, 0.0)]), 1.21)
        # pontos fora da caixa não contribuem
        self.assertEqual(m.hypervolume_2d([(2.0, 2.0)]), 0.0)

    def test_hv_exact_staircase(self):
        # (0,1): 1.1×0.1 ; (0.5,0.5): 0.6×0.5 ; (1,0): 0.1×0.5
        self.assertAlmostEqual(m.hypervolume_2d(self.ref), 0.11 + 0.30 + 0.05)

    def test_distances_zero_on_reference(self):
        for f in (m.igd, m.igd_plus, m.gd):
            self.assertEqual(f(self.ref, self.ref), 0.0)
        self.assertEqual(m.epsilon_additive(self.ref, self.ref), 0.0)

    def test_igd_plus_ignores_dominating_points(self):
        better = [(-0.1, -0.1)]
        self.assertEqual(m.igd_plus(better, [(0.0, 0.0)]), 0.0)
        self.assertGreater(m.igd(better, [(0.0, 0.0)]), 0.0)
        self.assertAlmostEqual(m.epsilon_additive(better, [(0.0, 0.0)]), -0.1)

    def test_epsilon_translation(self):
        shifted = [(x + 0.2, y + 0.2) for x, y in self.ref]
        self.assertAlmostEqual(m.epsilon_additive(shifted, self.ref), 0.2)

    def test_spacing_uniform_and_degenerate(self):
        self.assertAlmostEqual(m.spacing(self.ref), 0.0)
        self.assertEqual(m.spacing([(0.3, 0.3)]), 0.0)
        self.assertAlmostEqual(m.spread(self.ref, self.ref), 0.0)

    def test_coverage(self):
        self.assertEqual(m.coverage([(0, 0)], self.ref), 1.0)
        self.assertEqual(m.coverage(self.ref, [(0, 0)]), 0.0)
        self.assertEqual(m.coverage([], []), 0.0)

    def test_empty_front_is_not_nan(self):
        row = m.run_indicators([], [(1, 2)], (1, 2), (1, 2))
        self.assertEqual(row["HV"], 0.0)
        self.assertIsNone(row["IGD"])

    def test_single_point_reference_no_division_by_zero(self):
        row = m.run_indicators([(10, 20)], [(10, 20)], (10, 20), (10, 20))
        self.assertAlmostEqual(row["HV"], 1.21)
        self.assertEqual(row["R_PF"], 1.0)

    def test_nondominated_filter(self):
        self.assertEqual(nondominated([(3, 1), (1, 3), (2, 2), (2, 3), (1, 3)]), [(1, 3), (2, 2), (3, 1)])

    def test_holm_monotone(self):
        self.assertEqual(m.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])


class RegistryTests(unittest.TestCase):
    def test_nine_instances_four_tiers(self):
        self.assertEqual(len(INSTANCES), 9)
        self.assertEqual([len(select_instances([t])) for t in ("small", "medium", "large", "giant")], [3, 2, 2, 2])
        self.assertTrue(all(spec.path.exists() for spec in INSTANCES))

    def test_vns_default_follows_calibration_and_tuned_loaded(self):
        from experiments.config import default_algorithms, vns_calibrated
        self.assertEqual("vns_vnd" in default_algorithms(), vns_calibrated())
        for algorithm in ("spea2", "moead", "age", "vns_vnd"):
            self.assertIsNotNone(load_hyperparameters(algorithm))

    def test_paired_seeds_and_single_deterministic_run(self):
        tasks = build_tasks(["exact_dp", "spea2", "age"], select_instances(["small"])[:1], 3, 1000)
        self.assertEqual(sum(t.algorithm == "exact_dp" for t in tasks), 1)
        seeds = {a: [t.seed for t in tasks if t.algorithm == a] for a in ("spea2", "age")}
        self.assertEqual(seeds["spea2"], [1001, 1002, 1003])
        self.assertEqual(seeds["spea2"], seeds["age"])


class LedgerTests(unittest.TestCase):
    def test_times_accumulate_across_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            for session, (status, wall) in enumerate((("COMPLETED", 2.0), ("INTERRUPTED_PARTIAL", 1.5)), 1):
                ledger = Ledger(Path(folder))
                ledger.start_session([])
                ledger.record(f"spea2|x.dat|0{session}", dict(algorithm="spea2", instance="x.dat", run_id=session,
                              seed=1000 + session, status=status, wall_seconds=wall, cpu_seconds=wall))
                ledger.end_session("test")
            totals = Ledger(Path(folder)).totals()
            self.assertEqual((totals["valid_wall_s"], totals["interrupted_wall_s"], totals["sessions"]), (2.0, 1.5, 2))
            lines = (Path(folder) / "execution_times_live.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
