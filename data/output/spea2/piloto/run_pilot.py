"""Reproduce the bounded SPEA2 pilot; run from the repository root."""

from __future__ import annotations

import csv
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from metaheuristics.spea2 import SPEA2Config, run_spea2, write_result  # noqa: E402
from problem import read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402


OUT = Path(__file__).resolve().parent
RUNS = OUT / "runs"
SEEDS = (11, 29, 47)
INSTANCES = (
    ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat",
    ROOT / "data/input/set1/14_2_1439_3_S_1-9_derivada.dat",
    ROOT / "data/input/set2/50_10_1439_5_S_1-9.dat",
    ROOT / "data/input/set2/250_10_1439_5_S_1-9.dat",
)
CSV_FIELDS = (
    "instance", "instance_sha256", "n", "m", "configuration", "seed",
    "population_size", "crossover_probability", "mutation_probability",
    "max_evaluations", "attempts", "feasible_evaluations", "rejected_evaluations",
    "rejection_rate", "pymoo_evaluations", "post_search_validations",
    "elapsed_seconds", "milliseconds_per_evaluation", "front_size", "cmax_min",
    "tec_min_exact", "allocation_signatures", "order_signatures", "mode_signatures",
    "wait_signatures", "independent_front_revalidations", "validation_status",
)


def configurations():
    # Population/budget sensitivity: three representative sizes, same operators.
    for population in (20, 50, 100):
        for budget in (2_000, 8_000):
            yield f"pop{population}", population, budget, 0.9, 0.3
    # One-factor operator checks at the intermediate population and short budget.
    for label, crossover, mutation in (
        ("mutation01", 0.9, 0.1),
        ("mutation05", 0.9, 0.5),
        ("crossover06", 0.6, 0.3),
    ):
        yield label, 50, 2_000, crossover, mutation


def front_diversity(front):
    allocations, orders, modes, waits = set(), set(), set(), set()
    for item in front:
        rep = item["representation"]
        allocations.add(tuple(tuple(entry[0] for entry in machine) for machine in rep))
        orders.add(tuple(tuple(entry[0] for entry in machine) for machine in rep))
        modes.add(tuple(sorted((entry[0], entry[1]) for machine in rep for entry in machine)))
        waits.add(tuple(sorted((entry[0], entry[2]) for machine in rep for entry in machine)))
    # Allocation signatures preserve the assigned job set per machine; order signatures
    # preserve sequence within each machine.
    allocation_signatures = len({tuple(tuple(sorted(machine)) for machine in sig)
                                  for sig in allocations})
    return allocation_signatures, len(orders), len(modes), len(waits)


def run_one(instance_path: Path, label: str, population: int, budget: int,
             crossover: float, mutation: float, seed: int) -> dict:
    instance = read_instance(instance_path)
    config = SPEA2Config(seed, budget, population, crossover, mutation)
    result = run_spea2(instance, config)
    name = f"{instance_path.stem}__{label}__b{budget}__s{seed}.json"
    write_result(result, RUNS / name)

    # Independent exact re-evaluation after search; never enters SPEA2 or its budget.
    validation_count = 0
    keys = []
    for solution in result.front:
        reevaluated = evaluate_schedule(instance, solution.schedule)
        validation_count += 1
        if reevaluated.objective_key != solution.evaluation.objective_key:
            raise AssertionError(f"Objetivos divergentes na frente: {name}")
        if reevaluated.objective_key in keys:
            raise AssertionError(f"Ponto duplicado na frente: {name}")
        keys.append(reevaluated.objective_key)
    for first in keys:
        for second in keys:
            if first != second and first[0] <= second[0] and first[1] <= second[1]:
                raise AssertionError(f"Frente dominada: {name}")
    if result.attempts != budget or result.pymoo_evaluations != budget:
        raise AssertionError(f"Orçamento divergente: {name}: {result.attempts}/{budget}")
    if result.feasible_evaluations + result.rejected_evaluations != budget:
        raise AssertionError(f"Contagem de viáveis/rejeitadas divergente: {name}")

    payload = result.to_result_dict()
    diversity = front_diversity(payload["front"])
    cmax_min = min((s.evaluation.cmax for s in result.front), default=None)
    tec_min = min((s.evaluation.tec_exact for s in result.front), default=None)
    return {
        "instance": instance_path.name, "instance_sha256": instance.digest,
        "n": instance.n, "m": instance.m, "configuration": label, "seed": seed,
        "population_size": population, "crossover_probability": crossover,
        "mutation_probability": mutation, "max_evaluations": budget,
        "attempts": result.attempts, "feasible_evaluations": result.feasible_evaluations,
        "rejected_evaluations": result.rejected_evaluations,
        "rejection_rate": result.rejected_evaluations / budget,
        "pymoo_evaluations": result.pymoo_evaluations,
        "post_search_validations": result.post_search_validations,
        "elapsed_seconds": result.elapsed_seconds,
        "milliseconds_per_evaluation": result.elapsed_seconds * 1000 / budget,
        "front_size": len(result.front), "cmax_min": cmax_min,
        "tec_min_exact": f"{tec_min.numerator}/{tec_min.denominator}" if tec_min is not None else "",
        "allocation_signatures": diversity[0], "order_signatures": diversity[1],
        "mode_signatures": diversity[2], "wait_signatures": diversity[3],
        "independent_front_revalidations": validation_count,
        "validation_status": "viable_unique_exact_nondominated",
    }


def main():
    if RUNS.exists() and any(RUNS.iterdir()):
        raise SystemExit(f"Pasta de resultados não vazia; recusando sobrescrever: {RUNS}")
    RUNS.mkdir(parents=True, exist_ok=True)
    rows = []
    total = sum(1 for _ in configurations()) * len(INSTANCES) * len(SEEDS)
    index = 0
    for path in INSTANCES:
        for label, population, budget, crossover, mutation in configurations():
            for seed in SEEDS:
                index += 1
                row = run_one(path, label, population, budget, crossover, mutation, seed)
                rows.append(row)
                print(f"[{index}/{total}] {path.name} {label} b={budget} seed={seed}: "
                      f"{row['elapsed_seconds']:.2f}s, front={row['front_size']}, "
                      f"rejeição={row['rejection_rate']:.1%}", flush=True)
                # Checkpoint the CSV after each run so an interruption keeps an index.
                with (OUT / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
                    writer.writeheader()
                    writer.writerows(rows)
    manifest = {
        "algorithm": "SPEA2 incremental (pymoo 0.6.2)",
        "seeds": SEEDS,
        "instance_paths": [str(path.relative_to(ROOT)) for path in INSTANCES],
        "configurations": [
            {"label": label, "population_size": pop, "max_evaluations": budget,
             "crossover_probability": cx, "mutation_probability": mut}
            for label, pop, budget, cx, mut in configurations()
        ],
        "execution_count": len(rows),
        "search_attempts": sum(int(row["attempts"]) for row in rows),
        "runtime_environment": {
            "python": sys.version,
            "platform": sys.platform,
            "pymoo": version("pymoo"),
            "run_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Concluído: {len(rows)} execuções, {manifest['search_attempts']} tentativas.")


if __name__ == "__main__":
    main()
