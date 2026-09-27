"""O solver próprio começa vazio, pode retomar e conserva a fronteira exata."""

from pathlib import Path
import random
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "exact-solutions"))
import problem
from reference import brute_front
import custom_exact


class CustomExactTest(unittest.TestCase):
    def test_random_small_instances_match_oracle(self):
        for seed in range(6):
            rng = random.Random(seed)
            n, m = 3, 2
            processing = [rng.randint(1, 3) for _ in range(n * m)]
            setup = [0 if previous == following else rng.randint(0, 2)
                     for _machine in range(m)
                     for previous in range(n) for following in range(n)]
            contents = ("n 3\nm 2\nn_day 1\nhl 5\no 2\n"
                        "rate_in_peak 3\nrate_off_peak 1\nmax_cost 1000\n"
                        "peak_start 2\npeak_end 3\nv 1 2\nlambda 1 3\n"
                        f"pi {rng.randint(1, 3)} {rng.randint(1, 3)}\n"
                        f"processing {' '.join(map(str, processing))}\n"
                        f"setup {' '.join(map(str, setup))}\n")
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path = root / "random.dat"
                path.write_text(contents, encoding="utf-8")
                instance = problem.read_instance(path)
                own = custom_exact.search(instance, checkpoint=root / "own-state.json",
                                          output=root / "own.json", time_limit=None)
                self.assertEqual([(p["makespan"], p["tec_exact"]) for p in own["front"]],
                                 [(c, {"numerator": e, "denominator": problem.energy_scale(instance)[0]}) for c, e in brute_front(instance)])
                self.assertEqual(own["stats"]["covered_combinations"],
                                 int(own["cartesian_combinations"]))

    def test_complete_front_matches_oracle(self):
        for path in sorted((ROOT / "tests" / "fixtures").glob("*.dat")):
            with self.subTest(path=path.name), tempfile.TemporaryDirectory() as temp:
                instance = problem.read_instance(path)
                root = Path(temp)
                own = custom_exact.search(instance, checkpoint=root / "own-state.json",
                                          output=root / "own.json", time_limit=None)
                self.assertEqual(own["status"], "complete")
                self.assertTrue(own["pareto_proven"])
                self.assertEqual([(p["makespan"], p["tec_exact"]) for p in own["front"]],
                                 [(c, {"numerator": e, "denominator": problem.energy_scale(instance)[0]}) for c, e in brute_front(instance)])
                self.assertEqual(own["stats"]["covered_combinations"],
                                 int(own["cartesian_combinations"]))

    def test_resume_preserves_search_and_empty_start(self):
        instance = problem.read_instance(ROOT / "tests" / "fixtures" / "05_three_jobs.dat")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            partial = custom_exact.search(instance, checkpoint=root / "state.json",
                                          output=root / "result.json", time_limit=None,
                                          max_decisions=10)
            self.assertEqual(partial["status"], "incomplete")
            self.assertGreater(len(partial["front"]), 0)
            resumed = custom_exact.search(instance, checkpoint=root / "state.json",
                                          output=root / "result.json", time_limit=None,
                                          resume=True)
            fresh = custom_exact.search(instance, checkpoint=root / "fresh-state.json",
                                        output=root / "fresh.json", time_limit=None)
            self.assertEqual(resumed["front"], fresh["front"])
            self.assertEqual(resumed["stats"], fresh["stats"])
            self.assertGreater(resumed["stats"]["dominance_pruned_combinations"], 0)


if __name__ == "__main__":
    unittest.main()
