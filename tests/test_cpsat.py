"""O modelo CP-SAT deve provar a mesma fronteira que a enumeração pequena."""

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "exact-solutions"))
import exact
import cpsat


class CpSatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cpsat.ortools_module()
        except ValueError:
            raise unittest.SkipTest("OR-Tools opcional não instalado")

    def test_same_complete_front_as_backtracking(self):
        for path in sorted((ROOT / "tests" / "fixtures").glob("*.dat")):
            with self.subTest(path=path.name), tempfile.TemporaryDirectory() as temp:
                instance = exact.read_instance(path)
                root = Path(temp)
                brute = exact.search(instance, checkpoint=root / "brute-state.json",
                                     output=root / "brute.json", time_limit=None)
                sat = cpsat.solve_front(instance, output=root / "sat.json",
                                        seconds_per_solve=10, workers=2)
                self.assertEqual(sat["status"], "complete")
                self.assertTrue(sat["pareto_proven"])
                self.assertEqual([(point["makespan"], point["tec_exact"])
                                  for point in sat["front"]],
                                 [(point["makespan"], point["tec_exact"])
                                  for point in brute["front"]])

    def test_resume_between_proven_points(self):
        instance = exact.read_instance(ROOT / "tests" / "fixtures" / "01_single_job_modes.dat")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "sat.json"
            full = cpsat.solve_front(instance, output=output, seconds_per_solve=10, workers=2)
            partial = dict(full)
            partial["status"] = "incomplete"
            partial["pareto_proven"] = False
            partial["proven_points"] = full["proven_points"][:1]
            partial["front"] = full["front"][:1]
            partial["next_cost_cap"] = full["proven_points"][0]["point"][1] - 1
            output.write_text(json.dumps(partial), encoding="utf-8")
            resumed = cpsat.solve_front(instance, output=output, seconds_per_solve=10,
                                        workers=2, resume=True)
            self.assertEqual(resumed["status"], "complete")
            self.assertEqual(resumed["front"], full["front"])


if __name__ == "__main__":
    unittest.main()
