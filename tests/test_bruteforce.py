"""Verificação independente da enumeração e da retomada em uma instância pequena."""

import importlib.util
import json
from itertools import product
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bruteforce_exact", ROOT / "src" / "exact-solutions" / "exact.py")
exact = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = exact
SPEC.loader.exec_module(exact)


TOY = """n 2
m 1
n_day 1
hl 5
o 2
rate_in_peak 3
rate_off_peak 1
max_cost 10
peak_start 2
peak_end 3
v 1 2
lambda 1 3
pi 1
processing 2 2
setup 0 1 2 0
"""


class BruteForceTest(unittest.TestCase):
    def test_resume_exhausted_cursor(self):
        instance = exact.read_instance(ROOT / "tests" / "fixtures" / "06_reparable_setup.dat")
        scale, prices = exact.energy_scale(instance)
        choices = exact.generate_choices(instance, prices)
        state = exact.initial_state(instance, choices, scale)
        state["selected_indices"] = [0, 1]
        state["stack_next"] = [1, 2, len(choices[2])]
        state["stats"]["covered_combinations"] = len(choices[2])
        with tempfile.TemporaryDirectory() as temp:
            checkpoint = Path(temp) / "state.json"
            output = Path(temp) / "result.json"
            checkpoint.write_text(json.dumps(state), encoding="utf-8")
            report = exact.search(instance, checkpoint=checkpoint, output=output,
                                  resume=True, time_limit=None, max_decisions=1)
            self.assertEqual(report["stop_reason"], "decision_limit")
            self.assertEqual(report["stats"]["candidate_decisions"], 1)

    def test_fixture_suite_against_independent_oracle(self):
        for path in sorted((ROOT / "tests" / "fixtures").glob("*.dat")):
            with self.subTest(path=path.name), tempfile.TemporaryDirectory() as temp:
                instance = exact.read_instance(path)
                scale, prices = exact.energy_scale(instance)
                choices = exact.generate_choices(instance, prices)
                points = []
                raw_count = 0
                overlap_count = 0
                setup_count = 0
                for selected in product(*choices):
                    raw_count += 1
                    timeline = {}
                    for job, choice in enumerate(selected):
                        timeline.setdefault(choice.machine, []).append((choice.start, choice.end, job, choice))
                    if any(a[1] > b[0] for seq in timeline.values()
                           for a, b in zip(sorted(seq), sorted(seq)[1:])):
                        overlap_count += 1
                        continue
                    if any(b[0] < a[1] + instance.setup[machine][a[2]][b[2]]
                           for machine, seq in timeline.items()
                           for a, b in zip(sorted(seq), sorted(seq)[1:])):
                        setup_count += 1
                        continue
                    energy = Fraction(0)
                    for choice in selected:
                        for slot in range(choice.start, choice.end):
                            peak = any(begin <= slot < end for begin, end in instance.peaks)
                            rate = instance.peak_rate if peak else instance.off_rate
                            energy += instance.power[choice.machine] * instance.power_factor[choice.mode] * rate * Fraction(24, instance.slots_per_day)
                    points.append((max(choice.end for choice in selected), int(energy * scale)))
                expected = {p for p in points if not any(q != p and exact.dominates_or_equals(q, p) for q in points)}
                checkpoint = Path(temp) / "state.json"
                output = Path(temp) / "report.json"
                result = exact.search(instance, checkpoint=checkpoint, output=output, time_limit=None)
                observed = {(p["makespan"], p["tec_exact"]["numerator"]) for p in result["front"]}
                self.assertEqual(observed, expected)
                self.assertEqual(result["status"], "complete")
                self.assertEqual(result["stats"]["complete_assignments"]
                                 + result["stats"]["overlap_pruned_combinations"]
                                 + result["stats"]["setup_pruned_combinations"], raw_count)
                self.assertLessEqual(result["stats"]["invalid_setups"], setup_count)
                self.assertAlmostEqual(result["backtracking_reduction_percent"],
                                       100 * (result["stats"]["overlap_pruned_combinations"]
                                              + result["stats"]["setup_pruned_combinations"]) / raw_count)
                self.assertEqual(result["stats"]["valid_schedules"], len(points))
                self.assertEqual(int(result["cartesian_combinations"]), raw_count)
                for point in result["front"]:
                    for term in point["x_nonzero"]:
                        self.assertEqual(term["j"], point["x_nonzero"].index(term))

    def test_gpu_matches_cpu_and_can_resume_checkpoint(self):
        try:
            import cupy
            if not cupy.cuda.runtime.getDeviceCount():
                self.skipTest("Nenhuma GPU CUDA")
        except (ImportError, RuntimeError):
            self.skipTest("CuPy/CUDA indisponível")
        for path in sorted((ROOT / "tests" / "fixtures").glob("*.dat")):
            with self.subTest(path=path.name), tempfile.TemporaryDirectory() as temp:
                instance = exact.read_instance(path)
                root = Path(temp)
                cpu = exact.search(instance, checkpoint=root / "cpu-state.json", output=root / "cpu.json",
                                   time_limit=None)
                partial = exact.search(instance, checkpoint=root / "gpu-state.json", output=root / "gpu.json",
                                       time_limit=None, max_decisions=5, backend="gpu", batch_size=3)
                self.assertEqual(partial["status"], "incomplete")
                gpu = exact.search(instance, checkpoint=root / "gpu-state.json", output=root / "gpu.json",
                                   time_limit=None, resume=True, backend="gpu", batch_size=3)
                self.assertEqual(gpu["front"], cpu["front"])
                self.assertEqual(gpu["stats"], cpu["stats"])
                if path.name == "04_two_days.dat":
                    exact.search(instance, checkpoint=root / "mixed-state.json", output=root / "mixed.json",
                                 time_limit=None, max_decisions=7, backend="cpu")
                    mixed = exact.search(instance, checkpoint=root / "mixed-state.json", output=root / "mixed.json",
                                         time_limit=None, resume=True, backend="gpu", batch_size=4)
                    self.assertEqual(mixed["front"], cpu["front"])
                    self.assertEqual(mixed["stats"], cpu["stats"])

    def test_complete_front_and_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "toy.dat"
            path.write_text(TOY, encoding="utf-8")
            instance = exact.read_instance(path)
            scale, prices = exact.energy_scale(instance)
            choices = exact.generate_choices(instance, prices)

            # Oráculo simples: produto cartesiano, filtro de conflitos e dominância.
            valid = []
            for pair in product(*choices):
                if exact.overlaps(pair[1], [pair[0]]):
                    continue
                first, second = pair
                if first.start < second.start:
                    feasible = second.start >= first.end + 1
                else:
                    feasible = first.start >= second.end + 2
                if feasible:
                    valid.append((max(first.end, second.end), first.cost_units + second.cost_units))
            expected = {
                point for point in valid
                if not any(other != point and exact.dominates_or_equals(other, point) for other in valid)
            }

            checkpoint = root / "state.json"
            output = root / "result.json"
            partial = exact.search(instance, checkpoint=checkpoint, output=output,
                                   time_limit=None, max_decisions=3)
            self.assertEqual(partial["status"], "incomplete")
            self.assertFalse(partial["pareto_proven"])
            result = exact.search(instance, checkpoint=checkpoint, output=output,
                                  time_limit=None, resume=True)
            self.assertEqual(result["status"], "complete")
            self.assertEqual({(row["makespan"], row["tec_exact"]["numerator"]) for row in result["front"]}, expected)
            self.assertEqual(result["stats"]["covered_combinations"], int(result["cartesian_combinations"]))
            self.assertEqual(result["stats"]["valid_schedules"], len(valid))

            fresh = exact.search(instance, checkpoint=root / "fresh-state.json",
                                 output=root / "fresh-result.json", time_limit=None)
            self.assertEqual(result["front"], fresh["front"])
            self.assertEqual(result["stats"], fresh["stats"])


if __name__ == "__main__":
    unittest.main()
