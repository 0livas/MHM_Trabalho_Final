from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/heuristics/nsga2"))

from problem import read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402
from decoder import Decoder, join, split, upper_bounds  # noqa: E402
from operators import (  # noqa: E402
    ChromosomeSampling, MixedCrossover, MixedMutation, greedy_individual, pmx, random_individual,
)
from nsga2 import ChromosomeProblem, NSGA2Config, NSGA2Trace, run_nsga2  # noqa: E402

SMALL = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"
BASELINE = ROOT / "data/baselines/6_2_1439_3_S_1-9_custom_exact_dp.json"


def assert_valid_chromosome(test: unittest.TestCase, instance, x) -> None:
    seq, *_ = split(instance, x)
    test.assertEqual(sorted(seq.tolist()), list(range(instance.n)))
    test.assertTrue(np.all(np.asarray(x) >= 0))
    test.assertTrue(np.all(np.asarray(x) <= upper_bounds(instance)))


class DecoderTests(unittest.TestCase):
    def setUp(self):
        self.instance = read_instance(SMALL)
        self.decoder = Decoder(self.instance)
        self.rng = np.random.default_rng(7)

    def test_matches_shared_evaluator_on_random_chromosomes(self):
        for _ in range(300):
            decoded = self.decoder.decode(random_individual(self.instance, self.rng))
            self.assertTrue(decoded.feasible)
            evaluation = evaluate_schedule(self.instance, decoded.schedule)
            self.assertEqual(evaluation.objective_key, (decoded.cmax, decoded.tec_units))

    def test_avoid_peak_delays_start_to_peak_end(self):
        # Ponta [0, 50): o primeiro job começa em 0, dentro dela.
        instance = replace(self.instance, peaks=((0, 50),))
        decoder = Decoder(instance)
        n = instance.n
        base = join(range(n), [0] * n, [0] * n, [0] * n)
        avoid = join(range(n), [0] * n, [0] * n, [1] + [0] * (n - 1))
        plain, delayed = decoder.decode(base), decoder.decode(avoid)
        self.assertEqual(plain.schedule[0][0][2], 0)
        self.assertEqual(delayed.schedule[0][0], (0, 0, 50))
        self.assertEqual(delayed.cmax, plain.cmax + 50)

    def test_start_outside_peak_is_not_delayed(self):
        n = self.instance.n
        x = join(range(n), [0] * n, [0] * n, [1] * n)
        decoded = self.decoder.decode(x)
        self.assertTrue(all(wait == 0 for _, _, wait in decoded.schedule[0]))

    def test_overflow_is_reported_instead_of_raising(self):
        instance = replace(self.instance, slots_per_day=50, peaks=((10, 20),))
        n = instance.n
        decoded = Decoder(instance).decode(join(range(n), [0] * n, [0] * n, [0] * n))
        self.assertFalse(decoded.feasible)
        self.assertEqual(decoded.overflow, decoded.cmax - 50)

    def test_rejects_non_permutation(self):
        n = self.instance.n
        with self.assertRaises(ValueError):
            self.decoder.decode(join([0] * n, [0] * n, [0] * n, [0] * n))


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.instance = read_instance(SMALL)
        self.problem = ChromosomeProblem(self.instance, NSGA2Trace())
        self.rng = np.random.default_rng(3)

    def test_pmx_keeps_permutation(self):
        for size in (2, 5, 30):
            for _ in range(200):
                p1, p2 = self.rng.permutation(size), self.rng.permutation(size)
                child = pmx(p1, p2, self.rng)
                self.assertEqual(sorted(child.tolist()), list(range(size)))

    def test_crossover_and_mutation_keep_bounds(self):
        parents = np.array([[random_individual(self.instance, self.rng)
                             for _ in range(20)] for _ in range(2)])
        offspring = MixedCrossover(prob=1.0)._do(self.problem, parents, random_state=self.rng)
        for child in offspring.reshape(-1, 4 * self.instance.n):
            assert_valid_chromosome(self, self.instance, child)
        mutated = MixedMutation()._do(self.problem, offspring[0], random_state=self.rng)
        for child in mutated:
            assert_valid_chromosome(self, self.instance, child)

    def test_sampling_has_greedy_individuals(self):
        samples = ChromosomeSampling()._do(self.problem, 10, random_state=self.rng)
        self.assertEqual(samples.shape, (10, 4 * self.instance.n))
        fastest = max(range(self.instance.modes), key=lambda o: self.instance.speed[o])
        _, _, modes, avoid = split(self.instance, samples[0])
        self.assertTrue(np.all(modes == fastest) and np.all(avoid == 0))
        for objective in ("cmax", "tec"):
            x = greedy_individual(self.instance, self.rng, objective)
            self.assertTrue(Decoder(self.instance).decode(x).feasible)


class RunTests(unittest.TestCase):
    def test_budget_is_literal_and_front_is_consistent(self):
        instance = read_instance(SMALL)
        result = run_nsga2(instance, NSGA2Config(seed=5, max_evaluations=137, population_size=20))
        self.assertEqual(result.attempts, 137)
        self.assertEqual(result.feasible_evaluations + result.rejected_evaluations, 137)
        keys = [solution.key for solution in result.front]
        self.assertEqual(len(keys), len(set(keys)))
        for a in keys:
            self.assertFalse(any(b[0] <= a[0] and b[1] <= a[1] and b != a for b in keys))
        data = result.to_result_dict()
        self.assertEqual(data["evaluations"], 137)
        self.assertEqual(len(data["front"]), len(result.front))

    def test_front_never_beats_exact_baseline(self):
        instance = read_instance(SMALL)
        result = run_nsga2(instance, NSGA2Config(seed=1, max_evaluations=1000, population_size=40))
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        exact = [(p["makespan"], Fraction(p["tec_exact"]["numerator"], p["tec_exact"]["denominator"]))
                 for p in baseline["front"]]
        for solution in result.front:
            point = (solution.evaluation.cmax, solution.evaluation.tec_exact)
            self.assertFalse(any(point[0] <= q[0] and point[1] <= q[1] and point != q
                                 for q in exact), point)


if __name__ == "__main__":
    unittest.main()
