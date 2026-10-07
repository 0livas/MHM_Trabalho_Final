"""Selective 20k confirmation for 250 jobs, P=50; no baseline is read."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_pilot  # noqa: E402
from problem import atomic_json, read_instance  # noqa: E402
from schedule import dominates  # noqa: E402

OUT = Path(__file__).resolve().parent
INSTANCE_PATH = ROOT / "data/input/set2/250_10_1439_5_S_1-9.dat"


def main():
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise SystemExit("Finalize o piloto principal antes da confirmação seletiva")
    if manifest.get("confirmation_20k"):
        raise SystemExit("Confirmação já registrada; preservando os resultados")
    instance = read_instance(INSTANCE_PATH)
    rows, data = [], []
    started = time.monotonic()
    for seed in (11, 29, 47):
        row, payload = run_pilot.run_one(INSTANCE_PATH, "pop50_b20000", 50, 20_000,
                                         20, 0.9, seed)
        rows.append(row)
        data.append(payload)
        print(f"250 jobs P=50 20k seed={seed}: {row['elapsed_seconds']:.2f}s "
              f"front={row['front_size']}", flush=True)
    fields = run_pilot.FIELDS
    with (OUT / "confirmation_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    paired = []
    for row, payload in zip(rows, data):
        previous_path = OUT / "runs" / f"{INSTANCE_PATH.stem}__pop50_b8000__s{row['seed']}.json"
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        old = [(int(p["makespan"]), int(p["tec_exact"]["numerator"])) for p in previous["front"]]
        new = [(int(p["makespan"]), int(p["tec_exact"]["numerator"])) for p in payload["front"]]
        paired.append({"instance": INSTANCE_PATH.name, "seed": row["seed"],
            "population_size": 50, "n_neighbors": 20, "prob_neighbor_mating": 0.9,
            "budget_8000_front": len(old), "budget_20000_front": len(new),
            "coverage_20000_by_8000": sum(any(dominates(a, b) or a == b for a in old)
                                                for b in new) / len(new),
            "coverage_8000_by_20000": sum(any(dominates(a, b) or a == b for a in new)
                                                for b in old) / len(old),
            "cmax_min_8000": min(a[0] for a in old), "cmax_min_20000": min(a[0] for a in new),
            "tec_min_8000_units": min(a[1] for a in old), "tec_min_20000_units": min(a[1] for a in new),
            "attempts": row["attempts"], "rejected": row["rejected_evaluations"],
            "seconds": row["elapsed_seconds"], "milliseconds_per_evaluation": row["milliseconds_per_evaluation"]})
    with (OUT / "confirmation_paired.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(paired[0]))
        writer.writeheader()
        writer.writerows(paired)

    entry = {"reason": "TEC minima improved for all three seeds from 2k to 8k on 250 jobs; check continuation",
        "instance": str(INSTANCE_PATH.relative_to(ROOT)), "seeds": [11, 29, 47],
        "population_size": 50, "reference_directions": 50, "n_neighbors": 20,
        "prob_neighbor_mating": 0.9, "max_evaluations": 20_000,
        "attempts": sum(int(r["attempts"]) for r in rows),
        "rejected_evaluations": sum(int(r["rejected_evaluations"]) for r in rows),
        "elapsed_seconds_sum": sum(float(r["elapsed_seconds"]) for r in rows),
        "executions": 3, "baseline_read": False,
        "metrics": "confirmation_metrics.csv", "paired": "confirmation_paired.csv"}
    atomic_json(manifest_path, {**manifest, "confirmation_20k": entry,
        "total_executions_including_confirmation": int(manifest["completed_executions"]) + 3,
        "total_attempts_including_confirmation": int(manifest["completed_attempts"]) + entry["attempts"]})
    print(json.dumps(entry, indent=2))


if __name__ == "__main__":
    main()
