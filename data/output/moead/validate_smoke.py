"""Small integration audit, not a pilot or parameter tuning experiment.

Run from the repository root; outputs are never overwritten.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
from unittest.mock import patch

import numpy as np
import pymoo
from pymoo.algorithms.moo.moead import MOEAD

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

import schedule as schedule_module  # noqa: E402
from problem import atomic_json, dominates, energy_scale, read_instance  # noqa: E402
from metaheuristics import moead, spea2  # noqa: E402


def signature(result):
    return ([(s.schedule, s.key) for s in result.front], result.attempts,
            result.feasible_evaluations, result.rejected_evaluations,
            result.pymoo_evaluations, result.post_search_validations)


def audit(instance, config):
    raw_evaluate = schedule_module.evaluate_schedule
    calls = {"search": 0, "post_search": 0}
    stage = "search"
    populations = []
    native_final = moead._final_front
    native_replace = MOEAD._replace

    def instrumented(instance, schedule):
        calls[stage] += 1
        return raw_evaluate(instance, schedule)

    def post_search(instance, population):
        nonlocal stage
        stage = "post_search"
        populations.append([(ind.X[0], ind.F.copy()) for ind in population])
        return native_final(instance, population)

    def capture(algorithm, k, off):
        native_replace(algorithm, k, off)
        populations.append([(ind.X[0], ind.F.copy()) for ind in algorithm.pop])

    # Instrument all complete-evaluator entrypoints used by the search/operators.
    with patch.object(moead, "evaluate_schedule", side_effect=instrumented), \
            patch.object(spea2, "evaluate_schedule", side_effect=instrumented), \
            patch.object(schedule_module, "evaluate_schedule", side_effect=instrumented), \
            patch.object(moead, "_final_front", side_effect=post_search), \
            patch.object(MOEAD, "_replace", capture):
        result = moead.run_moead(instance, config)

    assert calls["search"] == result.attempts == result.pymoo_evaluations == config.max_evaluations
    assert result.feasible_evaluations + result.rejected_evaluations == result.attempts
    assert calls["post_search"] == result.post_search_validations == config.population_size
    diagnostic_validations = 0
    for population in populations:
        assert len(population) == config.population_size
        for schedule, objectives in population:
            checked = raw_evaluate(instance, schedule)
            diagnostic_validations += 1
            np.testing.assert_array_equal(objectives, [checked.cmax / instance.horizon,
                float(checked.tec_exact / instance.max_cost)])
    keys = [solution.key for solution in result.front]
    assert keys and len(keys) == len(set(keys))
    for row, solution in zip(result.to_result_dict()["front"], result.front):
        checked = raw_evaluate(instance, row["representation"])
        diagnostic_validations += 1
        assert checked.objective_key == solution.key
        assert row["makespan"] == checked.cmax
        assert row["tec_exact"] == {"numerator": checked.tec_units, "denominator": checked.tec_scale}
        assert not any(dominates(other, solution.key) for other in keys)
    return result, {"independent_search_calls": calls["search"],
                    "independent_post_search_calls": calls["post_search"],
                    "diagnostic_validations_after_run": diagnostic_validations,
                    "population_snapshots": len(populations),
                    "all_population_schedules_viable_and_F_consistent": True,
                    "front_viable_unique_exact_nondominated": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "validation")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error(f"Diretório já existe: {args.output_dir}; escolha outro destino")
    report = {"purpose": "integration smoke, no tuning or convergence claims",
              "python": platform.python_version(), "pymoo": pymoo.__version__,
              "numpy": np.__version__, "runs": [], "precision_bounds": []}
    for source in (ROOT / "src/metaheuristics/moead.py", ROOT / "src/metaheuristics/spea2.py",
                   ROOT / "src/schedule.py", Path(__file__)):
        report.setdefault("source_sha256", {})[str(source.relative_to(ROOT))] = sha256(source.read_bytes()).hexdigest()
    for n in (6, 50, 250, 750):
        group = "set1" if n == 6 else "set2"
        name = f"{n}_{2 if n == 6 else 10}_1439_{3 if n == 6 else 5}_S_1-9.dat"
        instance = read_instance(ROOT / "data/input" / group / name)
        results = []
        for label, seed in (("seed11", 11), ("seed11_repeat", 11), ("seed29", 29)):
            config = moead.MOEADConfig(seed=seed, population_size=4 if n == 750 else 12,
                n_neighbors=2 if n == 750 else 4, max_evaluations=4 if n == 750 else 61)
            result, checks = audit(instance, config)
            path = args.output_dir / "runs" / f"{instance.path.stem}__{label}.json"
            moead.write_result(result, path)
            results.append(result)
            report["runs"].append({"instance": name, "label": label, "seed": seed,
                "path": str(path.relative_to(args.output_dir)), "attempts": result.attempts,
                "feasible": result.feasible_evaluations, "rejected": result.rejected_evaluations,
                "front_points": len(result.front), "elapsed_seconds": result.elapsed_seconds, **checks})
            print(f"{n} jobs / {label}: {result.attempts} attempts, {len(result.front)} points, "
                  f"{result.elapsed_seconds:.3f}s", flush=True)
        assert signature(results[0]) == signature(results[1])
        assert signature(results[0]) != signature(results[2])
    # After every search: conservative numerical evidence for all current inputs.
    for path in sorted((ROOT / "data/input").glob("*/*.dat")):
        instance = read_instance(path)
        scale, prices = energy_scale(instance)
        bound = instance.m * instance.horizon * max(max(on, off) for _, _, on, off in prices)
        assert bound < 2**51
        report["precision_bounds"].append({"instance": path.name, "tec_units_upper_bound": bound,
                                          "tec_scale": scale, "below_2_pow_51": True})
    report["same_seed_front_and_counters_identical"] = True
    report["different_seed_changes_schedules_or_exact_front"] = True
    atomic_json(args.output_dir / "audit.json", report)
    print(json.dumps({"runs": len(report["runs"]), "audit": str(args.output_dir / "audit.json")}))


if __name__ == "__main__":
    main()
