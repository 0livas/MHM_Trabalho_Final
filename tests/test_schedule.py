from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from problem import (  # noqa: E402
    Instance,
    dominates,
    energy_scale,
    generate_choices,
    insert_pareto,
    interval_cost_units,
    read_instance,
)
from schedule import (  # noqa: E402
    ScheduleValidationError,
    evaluate_schedule,
    schedule_from_result_rows,
)


def small_instance() -> Instance:
    return Instance(
        path=Path("small-fixture.dat"), digest="small-fixture",
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


class EvaluateScheduleTests(unittest.TestCase):
    def setUp(self):
        self.instance = small_instance()
        self.schedule = (((0, 0, 0), (1, 0, 1)), ((2, 0, 0),))

    def test_known_valid_schedule_decodes_and_evaluates_exactly(self):
        result = evaluate_schedule(self.instance, self.schedule)
        self.assertEqual(result.cmax, 10)
        self.assertEqual(result.tec_scale, 1)
        self.assertEqual(result.tec_units, 204)
        self.assertEqual(result.tec_exact, Fraction(204))
        self.assertEqual(result.objective_key, (10, 204))
        self.assertEqual(
            [(op.machine, op.job, op.mode, op.start, op.end)
             for op in result.operations],
            [(0, 0, 0, 0, 4), (0, 1, 0, 7, 10), (1, 2, 0, 0, 2)],
        )

    def test_empty_machine_is_allowed(self):
        result = evaluate_schedule(self.instance, (((0, 0, 0), (1, 0, 0), (2, 0, 0)), ()))
        self.assertEqual(len(result.operations), self.instance.n)
        self.assertTrue(all(operation.machine == 0 for operation in result.operations))

    def test_missing_job_is_reported(self):
        with self.assertRaisesRegex(ScheduleValidationError, "Jobs ausentes"):
            evaluate_schedule(self.instance, (((0, 0, 0),), ()))

    def test_duplicate_job_is_reported(self):
        with self.assertRaisesRegex(ScheduleValidationError, "Job duplicado"):
            evaluate_schedule(self.instance, (((0, 0, 0), (0, 0, 0)), ((2, 0, 0),)))

    def test_job_outside_domain_is_reported(self):
        with self.assertRaisesRegex(ScheduleValidationError, "Job fora do domínio"):
            evaluate_schedule(self.instance, (((3, 0, 0),), ((1, 0, 0), (2, 0, 0))))

    def test_invalid_mode_is_reported(self):
        with self.assertRaisesRegex(ScheduleValidationError, "Modo fora do domínio"):
            evaluate_schedule(self.instance, (((0, 2, 0), (1, 0, 0)), ((2, 0, 0),)))

    def test_negative_wait_is_reported(self):
        with self.assertRaisesRegex(ScheduleValidationError, "Espera negativa"):
            evaluate_schedule(self.instance, (((0, 0, -1), (1, 0, 0)), ((2, 0, 0),)))

    def test_wrong_machine_count_is_reported(self):
        with self.assertRaisesRegex(ScheduleValidationError, "Número incorreto de máquinas"):
            evaluate_schedule(self.instance, (((0, 0, 0),),))

    def test_malformed_machine_sequence_and_item_are_reported(self):
        with self.assertRaisesRegex(ScheduleValidationError, "Lista inválida para máquina"):
            evaluate_schedule(self.instance, ("bad", ((1, 0, 0), (2, 0, 0))))
        with self.assertRaisesRegex(ScheduleValidationError, "esperado \(job, modo, espera\)"):
            evaluate_schedule(self.instance, (((0, 0), (1, 0, 0)), ((2, 0, 0),)))

    def test_horizon_overrun_is_reported(self):
        with self.assertRaisesRegex(ScheduleValidationError, "além do horizonte"):
            evaluate_schedule(self.instance, (((0, 0, 20), (1, 0, 0)), ((2, 0, 0),)))

    def test_sequence_dependent_setup_and_residual_wait(self):
        result = evaluate_schedule(self.instance, self.schedule)
        by_job = {op.job: op for op in result.operations}
        self.assertEqual(by_job[1].start, by_job[0].end + self.instance.setup[0][0][1] + 1)

    def test_asymmetric_setup_changes_schedule_by_order(self):
        forward = evaluate_schedule(self.instance, (((0, 0, 0), (1, 0, 0)), ((2, 0, 0),)))
        reverse = evaluate_schedule(self.instance, (((1, 0, 0), (0, 0, 0)), ((2, 0, 0),)))
        forward_starts = {op.job: op.start for op in forward.operations}
        reverse_starts = {op.job: op.start for op in reverse.operations}
        self.assertEqual(forward_starts[1], 4 + self.instance.setup[0][0][1])
        self.assertEqual(reverse_starts[0], 3 + self.instance.setup[0][1][0])
        self.assertNotEqual(forward_starts[1], reverse_starts[0])

    def test_first_task_has_no_initial_setup(self):
        result = evaluate_schedule(self.instance, (((1, 0, 0), (0, 0, 0)), ((2, 0, 0),)))
        first = next(op for op in result.operations if op.job == 1)
        self.assertEqual(first.start, 0)

    def test_machine_choice_changes_processing_duration(self):
        on_machine_zero = evaluate_schedule(self.instance, (((0, 0, 0), (1, 0, 0)), ((2, 0, 0),)))
        on_machine_one = evaluate_schedule(self.instance, (((1, 0, 0), (2, 0, 0)), ((0, 0, 0),)))
        self.assertEqual(self.instance.duration(0, 0, 0), 4)
        self.assertEqual(self.instance.duration(0, 1, 0), 8)
        self.assertEqual(next(op.end for op in on_machine_zero.operations if op.job == 0), 4)
        self.assertEqual(next(op.end for op in on_machine_one.operations if op.job == 0), 8)

    def test_mode_changes_processing_duration(self):
        slower = evaluate_schedule(self.instance, (((0, 1, 0), (1, 0, 0)), ((2, 0, 0),)))
        self.assertEqual(self.instance.duration(0, 0, 1), 2)
        self.assertEqual(next(op.end for op in slower.operations if op.job == 0), 2)

    def test_wait_can_move_processing_across_tariff_boundary(self):
        early = evaluate_schedule(self.instance, (((0, 0, 0), (1, 0, 0)), ((2, 0, 0),)))
        delayed = evaluate_schedule(self.instance, (((0, 0, 2), (1, 0, 0)), ((2, 0, 0),)))
        early_job = next(op for op in early.operations if op.job == 0)
        delayed_job = next(op for op in delayed.operations if op.job == 0)
        self.assertEqual((early_job.start, early_job.end), (0, 4))
        self.assertEqual((delayed_job.start, delayed_job.end), (2, 6))
        self.assertNotEqual(early_job.tec_units, delayed_job.tec_units)

    def test_setup_and_wait_do_not_add_energy_directly(self):
        flat_tariff = replace(self.instance, peak_rate=Fraction(1), off_rate=Fraction(1))
        no_wait = evaluate_schedule(flat_tariff, (((0, 0, 0), (1, 0, 0)), ((2, 0, 0),)))
        wait = evaluate_schedule(flat_tariff, (((0, 0, 2), (1, 0, 3)), ((2, 0, 0),)))
        self.assertEqual(no_wait.tec_units, wait.tec_units)

    def test_energy_cost_matches_choice_table_for_all_options(self):
        scale, prices = energy_scale(self.instance)
        choices = generate_choices(self.instance, prices)
        prices_by_key = {(machine, mode): (on, off)
                         for machine, mode, on, off in prices}
        self.assertEqual(scale, 1)
        for job_choices in choices:
            for choice in job_choices:
                duration = choice.end - choice.start
                on, off = prices_by_key[choice.machine, choice.mode]
                original_formula = on * sum(
                    max(0, min(choice.end, peak_end) - max(choice.start, peak_start))
                    for peak_start, peak_end in self.instance.peaks
                )
                peak_slots = sum(
                    max(0, min(choice.end, peak_end) - max(choice.start, peak_start))
                    for peak_start, peak_end in self.instance.peaks
                )
                original_formula += off * (duration - peak_slots)
                self.assertEqual(choice.cost_units, original_formula)
                self.assertEqual(
                    choice.cost_units,
                    interval_cost_units(self.instance, choice.start, choice.end, on, off),
                )

    def test_evaluator_matches_generate_choices_for_represented_schedule(self):
        result = evaluate_schedule(self.instance, self.schedule)
        _, prices = energy_scale(self.instance)
        choices = generate_choices(self.instance, prices)
        by_job = {job: options for job, options in enumerate(choices)}
        for operation in result.operations:
            matching = next(choice for choice in by_job[operation.job]
                            if (choice.machine, choice.mode, choice.start)
                            == (operation.machine, operation.mode, operation.start))
            self.assertEqual(matching.end, operation.end)
            self.assertEqual(matching.cost_units, operation.tec_units)

    def test_serialization_keeps_existing_result_fields_and_exact_cost(self):
        result = evaluate_schedule(self.instance, self.schedule).to_result_dict(self.instance)
        self.assertEqual(result["makespan"], 10)
        self.assertEqual(result["tec_exact"], {"numerator": 204, "denominator": 1})
        self.assertEqual(len(result["schedule"]), self.instance.n)
        self.assertEqual(len(result["x_nonzero"]), self.instance.n)
        restored = schedule_from_result_rows(self.instance, result["schedule"])
        self.assertEqual(evaluate_schedule(self.instance, restored).objective_key, (10, 204))

    def test_result_rows_with_setup_violation_are_rejected(self):
        rows = [
            {"job": 0, "machine": 0, "mode": 0, "start": 0, "end": 4},
            {"job": 1, "machine": 0, "mode": 0, "start": 5, "end": 8},
            {"job": 2, "machine": 1, "mode": 0, "start": 0, "end": 2},
        ]
        with self.assertRaisesRegex(ScheduleValidationError, "Setup/ordem inviável"):
            schedule_from_result_rows(self.instance, rows)


class ParetoTests(unittest.TestCase):
    def test_dominance_uses_exact_scaled_integers(self):
        large = 2**60
        self.assertTrue(dominates((12, large), (12, large + 1)))
        self.assertFalse(dominates((12, large), (12, large)))
        archive = [((12, large + 1), "old")]
        self.assertTrue(insert_pareto(archive, (12, large), "better exact TEC"))
        self.assertEqual(archive, [((12, large), "better exact TEC")])

    def test_archive_rejects_dominated_and_duplicate_points(self):
        archive = [((10, 100), "a"), ((12, 90), "b")]
        self.assertFalse(insert_pareto(archive, (13, 110), "dominated"))
        self.assertFalse(insert_pareto(archive, (10, 100), "duplicate"))
        self.assertTrue(insert_pareto(archive, (9, 80), "dominates both"))
        self.assertEqual(archive, [((9, 80), "dominates both")])


class BaselineAndExactRegressionTests(unittest.TestCase):
    def setUp(self):
        self.instance_path = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"
        self.baseline_path = ROOT / "data/baselines/6_2_1439_3_S_1-9_custom_exact_dp.json"
        self.instance = read_instance(self.instance_path)
        self.baseline = json.loads(self.baseline_path.read_text(encoding="utf-8-sig"))

    def test_selected_complete_baseline_schedules_round_trip_exactly(self):
        self.assertEqual(self.baseline["status"], "complete")
        self.assertTrue(self.baseline["pareto_proven"])
        self.assertEqual(self.baseline["instance_sha256"], self.instance.digest)
        front = self.baseline["front"]
        for point in (front[0], front[len(front) // 2], front[-1]):
            schedule = schedule_from_result_rows(self.instance, point["schedule"])
            result = evaluate_schedule(self.instance, schedule)
            self.assertEqual(result.cmax, point["makespan"])
            expected_tec = Fraction(point["tec_exact"]["numerator"],
                                    point["tec_exact"]["denominator"])
            self.assertEqual(result.tec_exact, expected_tec)

    def test_exact_makespan_dp_result_still_matches_shared_evaluator(self):
        sys.path.insert(0, str(ROOT / "src/exact_methods"))
        from custom_exact_dp import minimum_makespan

        exact_result = minimum_makespan(self.instance)
        representation = schedule_from_result_rows(self.instance, exact_result["schedule"])
        evaluated = evaluate_schedule(self.instance, representation)
        self.assertEqual(exact_result["status"], "optimal")
        self.assertEqual(evaluated.cmax, exact_result["minimum_makespan"])
        self.assertEqual(evaluated.cmax, self.baseline["minimum_makespan"])


if __name__ == "__main__":
    unittest.main()
