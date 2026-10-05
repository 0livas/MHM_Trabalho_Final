from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/metaheuristics"))

from problem import Instance, dominates, read_instance  # noqa: E402
from schedule import ScheduleEvaluation, evaluate_schedule  # noqa: E402
from vns_vnd import (  # noqa: E402
    NEIGHBORHOODS,
    ParetoSolution,
    VNSConfig,
    VNSVND,
    _candidate_at_rank,
    _candidate_schedules,
    _movement_count,
)


def small_instance() -> Instance:
    return Instance(
        path=Path("small-vns-fixture.dat"), digest="small-vns-fixture",
        n=3, m=2, days=1, slots_per_day=20, modes=2,
        peak_rate=Fraction(3), off_rate=Fraction(1), max_cost=Fraction(1000),
        peaks=((5, 10),), speed=(Fraction(1), Fraction(2)),
        power_factor=(Fraction(1), Fraction(2)),
        power=(Fraction(10), Fraction(20)),
        processing=((4, 8), (3, 6), (5, 2)),
        setup=(
            ((0, 2, 5), (1, 0, 4), (3, 6, 0)),
            ((0, 3, 1), (2, 0, 4), (5, 2, 0)),
        ),
    )


def machine_extended_instance(machine_count: int) -> Instance:
    instance = small_instance()
    extra = machine_count - instance.m
    return replace(
        instance,
        m=machine_count,
        power=instance.power + (instance.power[0],) * extra,
        processing=tuple(row + (row[0],) * extra for row in instance.processing),
        setup=instance.setup + (instance.setup[0],) * extra,
    )


SCHEDULE = (((0, 0, 0), (1, 0, 0)), ((2, 0, 0),))


class NeighborhoodTests(unittest.TestCase):
    def setUp(self):
        self.instance = small_instance()

    def candidates(self, neighborhood):
        return list(_candidate_schedules(self.instance, SCHEDULE, neighborhood,
                                         random.Random(7), 1000))

    def assert_complete_unique_jobs(self, schedule):
        jobs = [job for machine in schedule for job, _, _ in machine]
        self.assertEqual(sorted(jobs), list(range(self.instance.n)))

    def test_mode_change_preserves_structure(self):
        candidates = self.candidates(0)
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assert_complete_unique_jobs(candidate)
            self.assertNotEqual(candidate, SCHEDULE)
            self.assertTrue(all(0 <= mode < self.instance.modes
                                for machine in candidate for _, mode, _ in machine))

    def test_wait_moves_never_make_wait_negative(self):
        candidates = self.candidates(1)
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assert_complete_unique_jobs(candidate)
            self.assertTrue(all(wait >= 0 for machine in candidate for _, _, wait in machine))
        # Includes waits that align starts/ends around a tariff boundary, beyond ±1.
        waits = {wait for candidate in candidates for machine in candidate
                 for job, _, wait in machine if job == 0}
        self.assertTrue(any(wait >= 2 for wait in waits))

    def test_insertion_preserves_job_uniqueness(self):
        candidates = self.candidates(2)
        self.assertEqual(len(candidates), 1)
        for candidate in candidates:
            self.assert_complete_unique_jobs(candidate)

    def test_relocation_preserves_uniqueness_and_changes_machine(self):
        candidates = self.candidates(3)
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assert_complete_unique_jobs(candidate)
            old = {job: machine for machine, seq in enumerate(SCHEDULE) for job, _, _ in seq}
            new = {job: machine for machine, seq in enumerate(candidate) for job, _, _ in seq}
            self.assertTrue(any(old[job] != new[job] for job in old))

    def test_swap_preserves_job_uniqueness(self):
        candidates = self.candidates(4)
        self.assertEqual(len(candidates), 3)
        for candidate in candidates:
            self.assert_complete_unique_jobs(candidate)

    def test_indexed_moves_match_full_neighborhood_and_sample_without_replacement(self):
        for neighborhood in range(5):
            all_candidates = list(_candidate_schedules(
                self.instance, SCHEDULE, neighborhood, random.Random(9), 1000))
            indexed = [_candidate_at_rank(self.instance, SCHEDULE, neighborhood, rank)
                       for rank in range(len(all_candidates))]
            self.assertEqual(indexed, all_candidates)
            sampled = list(_candidate_schedules(
                self.instance, SCHEDULE, neighborhood, random.Random(9), 2))
            self.assertLessEqual(len(sampled), 2)
            self.assertEqual(len(sampled), len(set(sampled)))

    def test_n3_empty_singleton_and_multitask_machines_have_consistent_moves(self):
        instance = machine_extended_instance(3)
        schedule = ((), ((0, 0, 0),), ((1, 0, 0), (2, 0, 0)))
        generated = list(_candidate_schedules(instance, schedule, 2, random.Random(2), 100))
        indexed = [_candidate_at_rank(instance, schedule, 2, rank)
                   for rank in range(_movement_count(instance, schedule, 2))]
        self.assertEqual(_movement_count(instance, schedule, 2), 1)
        self.assertEqual(indexed, generated)
        self.assertTrue(all(candidate[0] == () and len(candidate[1]) == 1
                            for candidate in generated))

    def test_n3_zero_moves_with_empty_and_singleton_machines_is_safe(self):
        instance = machine_extended_instance(4)
        schedule = (((0, 0, 0),), ((1, 0, 0),), ((2, 0, 0),), ())
        self.assertEqual(_movement_count(instance, schedule, 2), 0)
        self.assertEqual(list(_candidate_schedules(
            instance, schedule, 2, random.Random(2), 100)), [])
        with self.assertRaises(IndexError):
            _candidate_at_rank(instance, schedule, 2, 0)

        evaluation = evaluate_schedule(instance, schedule)
        origin = ParetoSolution(schedule, evaluation)
        runner = VNSVND(instance, VNSConfig(max_evaluations=5, initial_solutions=1))
        shaken, expanded = runner._shake(origin, 2)
        self.assertIsNone(shaken)
        self.assertFalse(expanded)
        self.assertEqual(runner.evaluations, 0)
        self.assertEqual(runner.trace[-1]["reason"], "empty_neighborhood")

    def test_n3_shaking_handles_empty_machine_and_valid_insertions(self):
        instance = machine_extended_instance(3)
        schedule = ((), ((0, 0, 0),), ((1, 0, 0), (2, 0, 0)))
        origin = ParetoSolution(schedule, evaluate_schedule(instance, schedule))
        runner = VNSVND(instance, VNSConfig(seed=17, max_evaluations=5,
                                             initial_solutions=1, shaking_attempts=5))
        shaken, _ = runner._shake(origin, 2)
        self.assertIsNotNone(shaken)
        self.assertEqual(shaken.schedule[0], ())
        self.assertEqual(evaluate_schedule(instance, shaken.schedule).objective_key,
                         shaken.key)

    def test_over_horizon_candidate_is_rejected_and_charged(self):
        runner = VNSVND(self.instance, VNSConfig(max_evaluations=1, initial_solutions=1))
        invalid = (((0, 0, 20), (1, 0, 0)), ((2, 0, 0),))
        self.assertIsNone(runner._evaluate(invalid))
        self.assertEqual((runner.evaluations, runner.rejected_evaluations), (1, 1))


class VNSBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.instance = small_instance()

    def test_same_seed_and_parameters_reproduce_front_and_counts(self):
        config = VNSConfig(seed=21, max_evaluations=80, initial_solutions=3,
                           max_candidates_per_neighborhood=6, shaking_attempts=3)
        first = VNSVND(self.instance, config).run()
        second = VNSVND(self.instance, config).run()
        self.assertEqual([(item.key, item.schedule) for item in first.front],
                         [(item.key, item.schedule) for item in second.front])
        self.assertEqual(first.evaluations, second.evaluations)
        self.assertEqual(first.trace, second.trace)

    def test_evaluation_budget_is_never_exceeded(self):
        config = VNSConfig(seed=4, max_evaluations=37, initial_solutions=3,
                           max_candidates_per_neighborhood=9, shaking_attempts=5)
        result = VNSVND(self.instance, config).run()
        self.assertLessEqual(result.evaluations, config.max_evaluations)
        self.assertEqual(result.evaluations,
                         result.feasible_evaluations + result.rejected_evaluations)

    def test_final_archive_contains_only_unique_nondominated_points(self):
        result = VNSVND(self.instance, VNSConfig(max_evaluations=60, initial_solutions=2,
                                                 max_candidates_per_neighborhood=5,
                                                 shaking_attempts=3)).run()
        keys = [solution.key for solution in result.front]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(not dominates(a, b) for a in keys for b in keys if a != b))

    def test_all_exported_schedules_revalidate_and_preserve_objectives(self):
        result = VNSVND(self.instance, VNSConfig(max_evaluations=60, initial_solutions=2,
                                                 max_candidates_per_neighborhood=5,
                                                 shaking_attempts=3)).run()
        output = result.to_result_dict()
        self.assertEqual(output["points"], len(output["front"]))
        for row in output["front"]:
            representation = tuple(tuple(tuple(item) for item in machine)
                                   for machine in row["representation"])
            evaluation = evaluate_schedule(self.instance, representation)
            self.assertEqual(evaluation.cmax, row["makespan"])
            self.assertEqual(evaluation.tec_units, row["tec_exact"]["numerator"])
            self.assertEqual(evaluation.tec_scale, row["tec_exact"]["denominator"])

    def test_vnd_accepts_strict_dominance_and_restarts_at_n1(self):
        current_eval = ScheduleEvaluation(10, 100, 1, ())
        candidate_eval = ScheduleEvaluation(9, 90, 1, ())
        current = ParetoSolution(SCHEDULE, current_eval)
        candidate_schedule = (((0, 1, 0), (1, 0, 0)), ((2, 0, 0),))
        runner = VNSVND(self.instance, VNSConfig(max_evaluations=10, initial_solutions=1))
        runner.archive.append((current.key, current))
        with patch("vns_vnd._candidate_schedules", return_value=iter([candidate_schedule])), \
             patch("vns_vnd.evaluate_schedule", return_value=candidate_eval):
            final, _ = runner._vnd(current)
        self.assertEqual(final.key, candidate_eval.objective_key)
        visits = [event["name"] for event in runner.trace if event["event"] == "vnd_neighborhood"]
        self.assertEqual(visits[:2], [NEIGHBORHOODS[0], NEIGHBORHOODS[0]])
        self.assertTrue(any(event.get("event") == "vnd_accept" and event.get("restart") == "N1"
                            for event in runner.trace))

    def test_incomparable_candidate_enters_archive_without_replacing_current(self):
        current = ParetoSolution(SCHEDULE, ScheduleEvaluation(10, 100, 1, ()))
        candidate_schedule = (((0, 1, 0), (1, 0, 0)), ((2, 0, 0),))
        incomparable = ScheduleEvaluation(9, 110, 1, ())
        runner = VNSVND(self.instance, VNSConfig(max_evaluations=1, initial_solutions=1))
        runner.archive.append((current.key, current))
        with patch("vns_vnd._candidate_schedules", return_value=iter([candidate_schedule])), \
             patch("vns_vnd.evaluate_schedule", return_value=incomparable):
            final, expanded = runner._vnd(current)
        self.assertIs(final, current)
        self.assertTrue(expanded)
        self.assertIn(incomparable.objective_key, [point for point, _ in runner.archive])

    def test_shaking_advances_after_no_archive_expansion(self):
        runner = VNSVND(self.instance, VNSConfig(max_evaluations=10, initial_solutions=1))
        with patch.object(VNSVND, "_shake", return_value=(None, False)):
            result = runner.run(initial_schedules=[SCHEDULE])
        visits = [event["name"] for event in result.trace
                  if event["event"] == "shake_neighborhood"]
        self.assertEqual(visits, list(NEIGHBORHOODS))
        self.assertEqual(result.trace[-1]["reason"], "no_evaluable_moves")

    def test_least_explored_archive_point_is_selected_first(self):
        runner = VNSVND(self.instance, VNSConfig(max_evaluations=3, initial_solutions=1, seed=5))
        one = ParetoSolution(SCHEDULE, ScheduleEvaluation(10, 100, 1, ()))
        two = ParetoSolution(SCHEDULE, ScheduleEvaluation(9, 110, 1, ()))
        runner.archive.extend(((one.key, one), (two.key, two)))
        runner.explored_origins.update({one.key: 8, two.key: 1})
        self.assertIs(runner._origin(), two)

    def test_real_set1_instance_runs_and_every_result_is_valid(self):
        instance = read_instance(ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
        result = VNSVND(instance, VNSConfig(seed=13, max_evaluations=120,
                                             initial_solutions=3,
                                             max_candidates_per_neighborhood=8,
                                             shaking_attempts=4)).run()
        self.assertGreater(result.feasible_evaluations, 0)
        self.assertTrue(result.front)
        for solution in result.front:
            checked = evaluate_schedule(instance, solution.schedule)
            self.assertEqual(checked.objective_key, solution.key)


if __name__ == "__main__":
    unittest.main()
