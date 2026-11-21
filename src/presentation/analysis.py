"""Recalcula os indicadores da apresentação a partir dos resultados arquivados.

Execute `python src/presentation/analysis.py` a partir da raiz. Nenhum solver é
executado. As duas campanhas de 30 réplicas e as saídas individuais têm painéis
distintos. Os resultados da comparação anterior (A/B/C) não são misturados.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
import statistics
import sys

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))

from experiments.adapters import nondominated
from experiments.config import DEFAULT_RUNS, INSTANCES
from experiments.metrics import HV_REFERENCE, describe, hypervolume_2d, normalize
from problem import PROJECT_ROOT, read_instance, energy_scale


SOURCE = PROJECT_ROOT / "data/output"
DESTINATION = Path(__file__).resolve().parent / "data"
CAMPAIGNS = ("experiments", "experiments_vns_new")
ALGORITHMS = ("exact_dp", "ociosidade", "age", "moead", "spea2", "vns_vnd", "vns_vnd_new")
INDIVIDUAL_METHODS = ("cpsat", "custom_exact", "custom_exact_dp", "heuristica_construtiva", "heuristica_ociosidade")
METRICS = ("HV", "Purity", "Eq36", "wall_s")


@dataclass(frozen=True)
class Run:
    algorithm: str
    instance: str
    run_id: int
    seed: int | None
    status: str
    wall_s: float | None
    points: tuple[tuple[int, int], ...]
    proven: bool
    source: str
    stop_reason: str | None


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def ranks(points):
    """Separa a união em camadas Pareto, com índices que começam em 1."""
    layers = {}
    remaining = sorted(set(points))
    rank = 0
    while remaining:
        rank += 1
        dominated = []
        best_y = float("inf")
        for point in remaining:
            if point[1] < best_y:
                layers[point] = rank
                best_y = point[1]
            else:
                dominated.append(point)
        remaining = dominated
    return layers, rank


def summary(values):
    values = [value for value in values if value is not None]
    result = describe(values)
    if len(values) > 1:
        q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    else:
        q1 = q3 = values[0] if values else None
        result["std"] = None
    return dict(result, q1=q1, q3=q3)


def make_reference(points):
    return dict(ideal=[min(axis) for axis in zip(*points)], nadir=[max(axis) for axis in zip(*points)])


def value_hv(points, reference):
    return hypervolume_2d(normalize(points, reference["ideal"], reference["nadir"]))


def load_campaigns():
    runs = defaultdict(list)
    audits = Counter()
    digests = defaultdict(set)
    published = read_json(SOURCE / CAMPAIGNS[0] / "metrics/reference_fronts.json")
    for campaign in CAMPAIGNS:
        base = SOURCE / campaign
        references = read_json(base / "metrics/reference_fronts.json")
        for row in read_csv(base / "metrics/per_run_metrics.csv"):
            instance = Path(row["instance"]).stem
            algorithm = row["algorithm"] if campaign == CAMPAIGNS[0] else "vns_vnd_new"
            run_id = int(row["run_id"])
            path = base / "runs" / row["algorithm"] / instance / f"run_{run_id:02}.json"
            data = read_json(path)
            if (data["instance"], data["algorithm"], data["run_id"], data["status"], data["seed"]) != (
                row["instance"], row["algorithm"], run_id, row["status"], int(row["seed"]) if row["seed"] else None
            ):
                raise ValueError(f"Metadados divergentes em {path}")
            digests[instance].add(data["instance_sha256"])
            points = tuple(nondominated(map(tuple, data["points"])))
            if len(points) != len(data["points"]) or len(points) != int(row["NDS"]):
                raise ValueError(f"A frente arquivada em {path} não é o conjunto anunciado")
            run = Run(algorithm, instance, run_id, data["seed"], row["status"], float(row["wall_s"]),
                      points, data["pareto_proven"], path.relative_to(PROJECT_ROOT).as_posix(), data.get("stop_reason"))
            runs[instance].append(run)

            # Cada tabela antiga é verificada na sua própria referência e com sua
            # convenção de zero quando falta uma frente de saída.
            reference = references[row["instance"]]
            reference_points = set(map(tuple, reference["points"]))
            hv = value_hv(points, reference)
            purity = len(reference_points.intersection(points)) / len(reference_points)
            if not (isclose(hv, float(row["HV"]), abs_tol=1e-12) and
                    isclose(purity, float(row["R_PF"]), abs_tol=1e-12)):
                raise ValueError(f"HV ou R_PF diverge da tabela arquivada para {path}")
            audits[campaign] += 1

    for spec in INSTANCES:
        instance = spec.path.stem
        if not digests[instance] or not digests[instance] <= input_digests(spec.path):
            raise ValueError(f"Identidade da entrada diverge em {spec.path}")
        for algorithm in ALGORITHMS:
            selected = [run for run in runs[instance] if run.algorithm == algorithm]
            expected = 1 if algorithm in ("exact_dp", "ociosidade") else DEFAULT_RUNS
            ids = sorted(run.run_id for run in selected)
            if ids != list(range(1, expected + 1)):
                raise ValueError(f"Cobertura de execuções incompleta em {instance}, {algorithm}: {ids}")
    return runs, {Path(name).stem: ref for name, ref in published.items()}, dict(audits)


def input_digests(path):
    """Considera o mesmo texto antes/depois da conversão LF/CRLF do Git."""
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {sha256(text).hexdigest() for text in (raw, raw.replace(b"\n", b"\r\n"))}


def load_individuals():
    inputs = {path.stem: path for path in (PROJECT_ROOT / "data/input").glob("*/*.dat")}
    runs = defaultdict(list)
    tec_scales = {}
    for method in INDIVIDUAL_METHODS:
        paths = sorted((SOURCE / method).glob("*.json"))
        for path in paths:
            if path.stem not in inputs:
                continue
            data = read_json(path)
            input_path = inputs[path.stem]
            if data["instance_sha256"] not in input_digests(input_path):
                raise ValueError(f"Identidade da entrada diverge em {path}")
            if path.stem not in tec_scales:
                tec_scales[path.stem], _ = energy_scale(read_instance(input_path))
            scale = tec_scales[path.stem]
            points = []
            # O snapshot CP-SAT de 6 tarefas usa `proven_points` sem `front`.
            for point in data.get("front") or data.get("proven_points", []):
                exact = point.get("tec_exact")
                tec = (Fraction(exact["numerator"], exact["denominator"]) if exact else
                       Fraction(point["tec_numerator"], point["tec_denominator"]))
                units = tec * scale
                if units.denominator != 1:
                    raise ValueError(f"Custo fora da escala da entrada em {path}")
                points.append((point["makespan"], units.numerator))
            runs[path.stem].append(Run(
                method, path.stem, 1, None, data.get("status", "completed"), data.get("elapsed_seconds"),
                tuple(nondominated(points)), bool(data.get("pareto_proven")),
                path.relative_to(PROJECT_ROOT).as_posix(), data.get("stop_reason"),
            ))
    return runs, tec_scales


def analyze_instance(runs, hv_reference=None):
    layers, rank_count = ranks(point for run in runs for point in run.points)
    first_layer = {point for point, layer in layers.items() if layer == 1}
    for run in runs:
        if run.proven and set(run.points) != first_layer:
            raise ValueError(f"A união contradiz a fronteira comprovada de {run.source}")
    if hv_reference is None and first_layer:
        source = "fronteira exata comprovada" if any(run.proven for run in runs) else "união não dominada das saídas individuais"
        hv_reference = dict(make_reference(first_layer), source=source, points=sorted(first_layer))

    per_run = []
    grouped = defaultdict(list)
    for run in runs:
        hv = purity = equation = None
        if run.points:
            hv = value_hv(run.points, hv_reference)
            purity = len(first_layer.intersection(run.points)) / len(first_layer)
            equation = statistics.fmean(rank_count + 1 - layers[point] for point in run.points)
        row = dict(
            instance=run.instance, algorithm=run.algorithm, run_id=run.run_id, seed=run.seed,
            status=run.status, stop_reason=run.stop_reason, front_size=len(run.points),
            pareto_proven=run.proven, HV=hv, Purity=purity, Eq36=equation, wall_s=run.wall_s, source=run.source,
        )
        grouped[run.algorithm].append(row)
        per_run.append(row)

    result = dict(
        reference=hv_reference["source"] if hv_reference else None,
        reference_size=len(hv_reference["points"]) if hv_reference else 0,
        purity_reference_size=len(first_layer),
        purity_points_added=len(first_layer.difference(map(tuple, hv_reference["points"]))) if hv_reference else 0,
        rank_count=rank_count,
        algorithms={
            algorithm: dict(
                runs=len(rows), fronts=sum(row["front_size"] > 0 for row in rows),
                statuses=dict(Counter(row["status"] for row in rows)),
                metrics={metric: summary([row[metric] for row in rows]) for metric in METRICS},
            )
            for algorithm, rows in grouped.items()
        },
    )
    return result, per_run, layers


def summarize_tiers(instances):
    by_tier = defaultdict(list)
    for result in instances.values():
        by_tier[result["tier"]].append(result)
    return {
        tier: dict(instances=len(results), algorithms={
            algorithm: dict(
                runs=sum(result["algorithms"][algorithm]["runs"] for result in results),
                fronts=sum(result["algorithms"][algorithm]["fronts"] for result in results),
                metrics={metric: summary([
                    result["algorithms"][algorithm]["metrics"][metric]["mean"] for result in results
                ]) for metric in ("HV", "Purity", "wall_s")},
                Eq36_div_R=summary([
                    result["algorithms"][algorithm]["metrics"]["Eq36"]["mean"] / result["rank_count"]
                    for result in results if result["algorithms"][algorithm]["metrics"]["Eq36"]["n"] > 0
                ]),
            ) for algorithm in ALGORITHMS
        }) for tier, results in by_tier.items()
    }


def evaluate():
    campaign_runs, hv_references, audits = load_campaigns()
    individual_runs, scales = load_individuals()
    instances = {}
    individual = {}
    per_run = []
    aggregate = []
    result_examples = {}

    for cohort, entries, destination in (
        ("campaign", campaign_runs, instances), ("individual", individual_runs, individual),
    ):
        order = [spec.path.stem for spec in INSTANCES] if cohort == "campaign" else sorted(entries, key=lambda k: (int(k.split("_")[0]), k))
        for instance in order:
            reference = hv_references[instance] if cohort == "campaign" else None
            result, records, layers = analyze_instance(entries[instance], reference)
            result["tier"] = next((spec.tier for spec in INSTANCES if spec.path.stem == instance), "small")
            destination[instance] = result
            per_run.extend(dict(cohort=cohort, **record) for record in records)
            for algorithm, details in result["algorithms"].items():
                for metric in METRICS:
                    aggregate.append(dict(
                        cohort=cohort, instance=instance, tier=result["tier"], algorithm=algorithm, metric=metric,
                        runs=details["runs"], fronts=details["fronts"], **details["metrics"][metric],
                        statuses=json.dumps(details["statuses"], sort_keys=True),
                    ))
            if cohort == "individual" and instance == "6_2_1439_3_S_1-9":
                result_examples["individual_6"] = {
                    run.algorithm: [[x, y / scales[instance]] for x, y in run.points] for run in entries[instance]
                }
            if cohort == "campaign" and instance == "750_10_1439_5_S_1-9":
                result_examples["giant_1001"] = {
                    run.algorithm: normalize(run.points, reference["ideal"], reference["nadir"])
                    for run in entries[instance] if run.seed == 1001 or run.algorithm == "ociosidade"
                }
            if cohort == "campaign" and instance == "6_2_1439_3_S_1-9":
                result_examples["campaign_6_1001"] = {
                    run.algorithm: [(*normalized, layers[point]) for normalized, point in zip(
                        normalize(run.points, reference["ideal"], reference["nadir"]), run.points
                    )] for run in entries[instance] if run.seed == 1001 or run.algorithm in ("exact_dp", "ociosidade")
                }

    result = dict(
        provenance=dict(
            campaigns=[f"data/output/{name}" for name in CAMPAIGNS],
            individual=[f"data/output/{method}" for method in INDIVIDUAL_METHODS],
            hv_reference=[HV_REFERENCE, HV_REFERENCE],
            campaign_hv_geometry="ideal/nadir da PF* publicada em experiments/metrics/reference_fronts.json",
            purity="|F ∩ P*| / |P*|, com P* igual à primeira camada do conjunto analisado",
            equation="z = média de R + 1 − R_p sobre F, com as camadas fixas da união por instância",
            missing="HV, Purity e z indefinidos para saídas sem frente. Desvio amostral indefinido se n < 2.",
            tier_aggregation="Média das médias por instância disponível. Para z entre instâncias, usa z/R; a Equação 3.6 permanece sem reescala por instância.",
            audited_legacy_rows=audits,
        ),
        instances=instances,
        tiers=summarize_tiers(instances),
        individual=individual,
        examples=result_examples,
    )
    return result, per_run, aggregate


def main():
    result, per_run, aggregate = evaluate()
    DESTINATION.mkdir(exist_ok=True)
    write_csv(DESTINATION / "metrics_per_run.csv", per_run)
    write_csv(DESTINATION / "metrics_summary.csv", aggregate)
    (DESTINATION / "results.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(per_run)} execuções arquivadas e {len(aggregate)} linhas de resumo")


if __name__ == "__main__":
    main()
