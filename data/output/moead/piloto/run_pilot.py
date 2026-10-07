"""Run the paired, bounded MOEA/D pilot. Results are never overwritten."""

from __future__ import annotations

import csv
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import platform
import statistics
import sys
import time
from unittest.mock import patch

import numpy as np
import pymoo
from pymoo.algorithms.moo.moead import MOEAD

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

import schedule as schedule_module  # noqa: E402
from problem import atomic_json, read_instance  # noqa: E402
from schedule import dominates, evaluate_schedule  # noqa: E402
from metaheuristics import moead  # noqa: E402

OUT = Path(__file__).resolve().parent
RUNS = OUT / "runs"
SEEDS = (11, 29, 47)
INSTANCES = (
    ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat",
    ROOT / "data/input/set1/14_2_1439_3_S_1-9_derivada.dat",
    ROOT / "data/input/set2/50_10_1439_5_S_1-9.dat",
    ROOT / "data/input/set2/250_10_1439_5_S_1-9.dat",
)
OPERATORS = {"crossover_probability": 0.9, "mutation_probability": 0.3,
             "sampling": "randomized_lpt", "crossover": "ScheduleCrossover",
             "mutation": "ScheduleMutation"}
FIELDS = (
    "instance", "instance_sha256", "n", "m", "configuration", "seed",
    "population_size", "reference_directions", "n_neighbors", "prob_neighbor_mating",
    "crossover_probability", "mutation_probability", "sampling", "crossover", "mutation",
    "decomposition", "objective_scaling", "max_evaluations", "attempts",
    "feasible_evaluations", "rejected_evaluations", "rejection_rate", "fallbacks",
    "fallback_rate", "pymoo_evaluations", "post_search_validations", "elapsed_seconds",
    "milliseconds_per_evaluation", "front_size", "cmax_min", "tec_min_exact",
    "population_distinct_schedules", "population_allocations", "population_orders",
    "population_modes", "population_waits", "front_distinct_schedules", "front_allocations",
    "front_orders", "front_modes", "front_waits", "cmax_h_min", "cmax_h_max",
    "tec_normalized_min", "tec_normalized_max", "cmax_bins_5", "tec_bins_5",
    "min_cmax_endpoint", "min_tec_endpoint", "independent_front_revalidations",
    "independent_population_revalidations", "validation_status", "result_file",
    "baseline_points", "baseline_equal", "approx_points_dominated_by_baseline",
    "approx_points_dominating_baseline",
)


def configurations():
    for population in (20, 50, 100):
        for budget in (2_000, 8_000):
            yield f"pop{population}_b{budget}", population, budget, 20, 0.9
    # One factor at a time around the P=50, budget=2,000 default control.
    for label, neighbors, local_probability in (
        ("neighbors05", 5, 0.9),
        ("neighbors40", 40, 0.9),
        ("mating_global", 20, 0.0),
    ):
        yield label, 50, 2_000, neighbors, local_probability


def signatures(schedule):
    location = {job: machine for machine, seq in enumerate(schedule) for job, _, _ in seq}
    return {
        "schedule": schedule,
        "allocation": tuple(location[job] for job in range(len(location))),
        "order": tuple(tuple(job for job, _, _ in seq) for seq in schedule),
        "mode": tuple(mode for _, mode in sorted((job, mode) for seq in schedule for job, mode, _ in seq)),
        "wait": tuple(wait for _, wait in sorted((job, wait) for seq in schedule for job, _, wait in seq)),
    }


def diversity(schedules):
    rows = [signatures(s) for s in schedules]
    return {
        "schedules": len({row["schedule"] for row in rows}),
        "allocations": len({row["allocation"] for row in rows}),
        "orders": len({row["order"] for row in rows}),
        "modes": len({row["mode"] for row in rows}),
        "waits": len({row["wait"] for row in rows}),
    }


def histogram(values, bins=5):
    if not values:
        return [0] * bins
    low, high = min(values), max(values)
    counts = [0] * bins
    for value in values:
        index = 0 if high == low else min(bins - 1, int((value - low) / (high - low) * bins))
        counts[index] += 1
    return counts


def write_metrics(rows):
    with (OUT / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run_one(path, label, population, budget, neighbors, local_probability, seed):
    instance = read_instance(path)
    config = moead.MOEADConfig(seed=seed, max_evaluations=budget,
        population_size=population, n_neighbors=neighbors,
        prob_neighbor_mating=local_probability,
        crossover_probability=OPERATORS["crossover_probability"],
        mutation_probability=OPERATORS["mutation_probability"])
    counts = {"search": 0, "post_search": 0}
    phase = "search"
    final_population = []
    native_final = moead._final_front
    raw_evaluate = schedule_module.evaluate_schedule

    def instrument(instance_arg, schedule):
        counts[phase] += 1
        return raw_evaluate(instance_arg, schedule)

    def capture_final(instance_arg, population_arg):
        nonlocal phase
        phase = "post_search"
        final_population.extend(ind.X[0] for ind in population_arg)
        return native_final(instance_arg, population_arg)

    with patch.object(moead, "evaluate_schedule", side_effect=instrument), \
            patch.object(schedule_module, "evaluate_schedule", side_effect=instrument), \
            patch.object(moead, "_final_front", side_effect=capture_final):
        result = moead.run_moead(instance, config)

    if counts["search"] != result.attempts or counts["search"] != budget:
        raise AssertionError(f"Evaluator independente divergiu: {path.name} {label} seed {seed}")
    if not (counts["post_search"] == result.post_search_validations == population):
        raise AssertionError("Contagem de validação posterior divergente")
    if result.pymoo_evaluations != budget or result.attempts != budget:
        raise AssertionError("Hard cap divergente")
    if result.feasible_evaluations + result.rejected_evaluations != budget:
        raise AssertionError("Viáveis/rejeitadas não somam o orçamento")

    population_keys = []
    for schedule in final_population:
        evaluation = raw_evaluate(instance, schedule)
        population_keys.append(evaluation.objective_key)
    pop_div = diversity(final_population)

    payload = result.to_result_dict()
    front_keys, normalized_cmax, normalized_tec = [], [], []
    for row, solution in zip(payload["front"], result.front):
        representation = tuple(tuple(tuple(int(v) for v in item) for item in machine)
                                for machine in row["representation"])
        evaluation = raw_evaluate(instance, representation)
        expected_tec = Fraction(row["tec_exact"]["numerator"], row["tec_exact"]["denominator"])
        if (evaluation.objective_key != solution.key or evaluation.cmax != row["makespan"]
                or evaluation.tec_exact != expected_tec):
            raise AssertionError("Reavaliação exata da frente divergiu")
        front_keys.append(evaluation.objective_key)
        normalized_cmax.append(evaluation.cmax / instance.horizon)
        normalized_tec.append(float(evaluation.tec_exact / instance.max_cost))
    if len(front_keys) != len(set(front_keys)) or any(
            dominates(a, b) for a in front_keys for b in front_keys if a != b):
        raise AssertionError("Frente exportada não é única e Pareto exata")
    front_div = diversity([solution.schedule for solution in result.front])

    output = RUNS / f"{path.stem}__{label}__s{seed}.json"
    overwrite = False
    if output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        previous_config = previous.get("run_parameters", {})
        expected = {"seed": seed, "max_evaluations": budget, "population_size": population,
                    "n_neighbors": neighbors, "prob_neighbor_mating": local_probability,
                    "crossover_probability": config.crossover_probability,
                    "mutation_probability": config.mutation_probability}
        if previous.get("instance_sha256") != instance.digest or any(
                previous_config.get(key) != value for key, value in expected.items()):
            raise FileExistsError(f"Artefato existente não corresponde a esta execução: {output}")
        # Recovery of this incomplete campaign: only overwrite the matching output
        # after reproducing its same seed/configuration; source directory started empty.
        overwrite = True
    moead.write_result(result, output, overwrite=overwrite)
    tec_exact = min((s.evaluation.tec_exact for s in result.front), default=None)
    row = {
        "instance": path.name, "instance_sha256": instance.digest, "n": instance.n, "m": instance.m,
        "configuration": label, "seed": seed, "population_size": population,
        "reference_directions": population, "n_neighbors": neighbors,
        "prob_neighbor_mating": local_probability,
        "crossover_probability": config.crossover_probability,
        "mutation_probability": config.mutation_probability,
        "sampling": OPERATORS["sampling"], "crossover": OPERATORS["crossover"],
        "mutation": OPERATORS["mutation"], "decomposition": "Tchebycheff",
        "objective_scaling": "Cmax/H; TEC/max_cost",
        "max_evaluations": budget, "attempts": result.attempts,
        "feasible_evaluations": result.feasible_evaluations,
        "rejected_evaluations": result.rejected_evaluations,
        "rejection_rate": result.rejected_evaluations / budget,
        "fallbacks": result.rejected_evaluations,
        "fallback_rate": result.rejected_evaluations / budget,
        "pymoo_evaluations": result.pymoo_evaluations,
        "post_search_validations": result.post_search_validations,
        "elapsed_seconds": result.elapsed_seconds,
        "milliseconds_per_evaluation": result.elapsed_seconds * 1000 / budget,
        "front_size": len(result.front), "cmax_min": min((k[0] for k in front_keys), default=""),
        "tec_min_exact": f"{tec_exact.numerator}/{tec_exact.denominator}" if tec_exact is not None else "",
        "population_distinct_schedules": pop_div["schedules"],
        "population_allocations": pop_div["allocations"], "population_orders": pop_div["orders"],
        "population_modes": pop_div["modes"], "population_waits": pop_div["waits"],
        "front_distinct_schedules": front_div["schedules"], "front_allocations": front_div["allocations"],
        "front_orders": front_div["orders"], "front_modes": front_div["modes"],
        "front_waits": front_div["waits"],
        "cmax_h_min": min(normalized_cmax), "cmax_h_max": max(normalized_cmax),
        "tec_normalized_min": min(normalized_tec), "tec_normalized_max": max(normalized_tec),
        "cmax_bins_5": json.dumps(histogram(normalized_cmax)),
        "tec_bins_5": json.dumps(histogram(normalized_tec)),
        "min_cmax_endpoint": sum(k[0] == min(q[0] for q in front_keys) for k in front_keys),
        "min_tec_endpoint": sum(k[1] == min(q[1] for q in front_keys) for k in front_keys),
        "independent_front_revalidations": len(front_keys),
        "independent_population_revalidations": len(population_keys),
        "validation_status": "viable_unique_exact_nondominated",
        "result_file": str(output.relative_to(OUT)),
    }
    return row, payload


def manifest_base():
    sources = [ROOT / "src/metaheuristics/moead.py", ROOT / "src/metaheuristics/spea2.py",
               ROOT / "src/metaheuristics/vns_vnd.py", ROOT / "src/schedule.py",
               ROOT / "src/problem.py", Path(__file__)]
    return {
        "status": "running", "algorithm": "pymoo 0.6.2 native MOEA/D",
        "seeds": SEEDS, "instances": [str(p.relative_to(ROOT)) for p in INSTANCES],
        "primary_design": {"populations": [20, 50, 100], "budgets": [2000, 8000],
                           "seeds_per_cell": 3, "executions": 72},
        "sensitivity": {"population": 50, "budget": 2000, "seeds": SEEDS,
            "one_factor_conditions": [
                {"label": "default_control", "n_neighbors": 20, "prob_neighbor_mating": 0.9},
                {"label": "neighbors05", "n_neighbors": 5, "prob_neighbor_mating": 0.9},
                {"label": "neighbors40", "n_neighbors": 40, "prob_neighbor_mating": 0.9},
                {"label": "mating_global", "n_neighbors": 20, "prob_neighbor_mating": 0.0}],
            "additional_executions": 36},
        "expected_executions": 108, "expected_attempts": 432000,
        "operators": OPERATORS, "decomposition": "Tchebycheff",
        "objective_scaling": "Cmax/H; TEC/max_cost; unchanged",
        "timing": "Sequential MOEA/D run timer; includes setup/search and excludes post-search exact validations.",
        "runtime": {"python": sys.version, "platform": platform.platform(),
                    "numpy": np.__version__, "pymoo": pymoo.__version__},
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sources},
        "instance_sha256": {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in INSTANCES},
        "baseline_policy": "6-job exact baseline read only after all 108 searches complete",
        "comparators": {"spea2": "population 50, crossover .9, mutation .3; paired prior pilot",
                        "vns_vnd": "reference defaults, budget_8000 variant; paired prior pilot"},
    }


def main():
    existing = (OUT / "manifest.json").exists() or (OUT / "metrics.csv").exists()
    if existing:
        if not (OUT / "manifest.json").exists() or not (OUT / "metrics.csv").exists():
            raise SystemExit(f"Artefatos parciais sem índice seguro; preservando: {OUT}")
        old_manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
        if old_manifest.get("status") != "running":
            raise SystemExit(f"Piloto já finalizado; recusando sobrescrever: {OUT}")
        with (OUT / "metrics.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if any(not (OUT / row["result_file"]).is_file() for row in rows):
            raise SystemExit("Métricas existentes apontam para resultados ausentes; preservando pasta")
        if len({(r["instance"], r["configuration"], r["seed"]) for r in rows}) != len(rows):
            raise SystemExit("Há execuções duplicadas no checkpoint; preservando pasta")
    else:
        if (OUT / "runs").exists() and any((OUT / "runs").iterdir()):
            raise SystemExit(f"Pasta de resultados sem manifesto; preservando: {RUNS}")
        rows = []
    RUNS.mkdir(parents=True, exist_ok=True)
    manifest = manifest_base()
    atomic_json(OUT / "manifest.json", manifest)
    all_configs = list(configurations())
    expected = len(INSTANCES) * len(SEEDS) * len(all_configs)
    completed = {(r["instance"], r["configuration"], int(r["seed"])) for r in rows}
    index = len(rows)
    for path in INSTANCES:
        for label, population, budget, neighbors, local_probability in all_configs:
            for seed in SEEDS:
                key = (path.name, label, seed)
                if key in completed:
                    continue
                index += 1
                row, payload = run_one(path, label, population, budget, neighbors, local_probability, seed)
                rows.append(row)
                completed.add(key)
                write_metrics(rows)
                atomic_json(OUT / "manifest.json", {**manifest, "completed_executions": index,
                    "completed_attempts": sum(int(r["attempts"]) for r in rows)})
                print(f"[{index}/{expected}] n={row['n']} {label} seed={seed} "
                      f"t={row['elapsed_seconds']:.2f}s front={row['front_size']} "
                      f"reject={row['rejection_rate']:.1%}", flush=True)

    # Baseline is read after every search has completed.
    baseline_path = ROOT / "data/output/custom_exact_dp/6_2_1439_3_S_1-9.json"
    baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    if not baseline_data.get("pareto_proven") or baseline_data.get("status") != "complete":
        raise AssertionError("Baseline de 6 jobs não está completo/provado")
    six = read_instance(INSTANCES[0])
    if baseline_data["instance_sha256"] != six.digest:
        raise AssertionError("Hash do baseline não corresponde à instância")
    baseline_keys = []
    for item in baseline_data["front"]:
        tec = item["tec_exact"]
        baseline_keys.append((int(item["makespan"]), int(tec["numerator"])))
    if len(baseline_keys) != len(set(baseline_keys)):
        raise AssertionError("Baseline tem objetivos duplicados")
    for row in rows:
        if row["n"] != 6:
            continue
        payload = json.loads((OUT / row["result_file"]).read_text(encoding="utf-8"))
        approx = [(int(s["makespan"]), int(s["tec_exact"]["numerator"])) for s in payload["front"]]
        equal = sum(p in baseline_keys for p in approx)
        dominated_by_baseline = sum(any(dominates(b, p) for b in baseline_keys) for p in approx)
        dominates_baseline = [p for p in approx if any(dominates(p, b) for b in baseline_keys)]
        if dominates_baseline:
            raise AssertionError(f"MOEA/D parece dominar baseline exato: {row['result_file']} {dominates_baseline}")
        row.update({"baseline_points": len(baseline_keys), "baseline_equal": equal,
                    "approx_points_dominated_by_baseline": dominated_by_baseline,
                    "approx_points_dominating_baseline": len(dominates_baseline)})
    write_metrics(rows)
    manifest = {**manifest, "status": "complete", "completed_executions": len(rows),
                "completed_attempts": sum(int(r["attempts"]) for r in rows),
                "total_elapsed_seconds": sum(float(r["elapsed_seconds"]) for r in rows),
                "baseline_read_after_search": True,
                "baseline_path": str(baseline_path.relative_to(ROOT)),
                "baseline_sha256": sha256(baseline_path.read_bytes()).hexdigest()}
    atomic_json(OUT / "manifest.json", manifest)
    print(f"Searches complete: {len(rows)} runs, {manifest['completed_attempts']} attempts.", flush=True)


if __name__ == "__main__":
    main()
