"""Validate stored MOEA/D results and consolidate the completed pilot."""

from __future__ import annotations

import csv
from fractions import Fraction
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from problem import dominates, read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402

OUT = Path(__file__).resolve().parent
RUNS = OUT / "runs"
MOEAD_LABELS = ("pop20_b2000", "pop20_b8000", "pop50_b2000", "pop50_b8000",
                "pop100_b2000", "pop100_b8000")


def load_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def exact_points(path, instance):
    data = json.loads(path.read_text(encoding="utf-8"))
    points = []
    for item in data["front"]:
        schedule = tuple(tuple(tuple(int(v) for v in op) for op in machine)
                         for machine in item["representation"])
        evaluation = evaluate_schedule(instance, schedule)
        exact = Fraction(item["tec_exact"]["numerator"], item["tec_exact"]["denominator"])
        if evaluation.cmax != item["makespan"] or evaluation.tec_exact != exact:
            raise AssertionError(f"Exatidão divergente: {path}")
        points.append((evaluation.objective_key, schedule))
    keys = [key for key, _ in points]
    if not keys or len(keys) != len(set(keys)):
        raise AssertionError(f"Frente vazia ou duplicada: {path}")
    if any(dominates(a, b) for a in keys for b in keys if a != b):
        raise AssertionError(f"Frente dominada: {path}")
    if data["attempts"] != data["max_evaluations"] or data["pymoo_evaluations"] != data["max_evaluations"]:
        raise AssertionError(f"Hard cap divergente: {path}")
    if data["feasible_evaluations"] + data["rejected_evaluations"] != data["attempts"]:
        raise AssertionError(f"Contadores divergentes: {path}")
    return data, points


def median(values):
    return statistics.median(values)


def frac_text(value):
    return f"{value.numerator}/{value.denominator}"


def coverage(a, b):
    """Fraction of B weakly dominated by an exact point in A."""
    return sum(any(x[0] <= y[0] and x[1] <= y[1] for x in a) for y in b) / len(b)


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    metrics = load_csv(OUT / "metrics.csv")
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "complete" or len(metrics) != 108:
        raise AssertionError(f"Piloto incompleto: status={manifest.get('status')} runs={len(metrics)}")

    cache = {}
    front_revalidations = 0
    for row in metrics:
        n = int(row["n"])
        source = next(p for p in manifest["instances"] if Path(p).name == row["instance"])
        instance = read_instance(ROOT / source)
        if row["instance_sha256"] != instance.digest:
            raise AssertionError("Hash de instância divergiu")
        result_path = OUT / row["result_file"]
        data, points = exact_points(result_path, instance)
        front_revalidations += len(points)
        cache[(row["instance"], row["configuration"], int(row["seed"]))] = (data, points)

    confirmation_rows = (load_csv(OUT / "confirmation_metrics.csv")
                         if (OUT / "confirmation_metrics.csv").exists() else [])
    confirmation_front_revalidations = 0
    for row in confirmation_rows:
        instance = read_instance(ROOT / "data/input/set2" / row["instance"])
        if row["instance_sha256"] != instance.digest:
            raise AssertionError("Hash divergente na confirmação de 20k")
        _, points = exact_points(OUT / row["result_file"], instance)
        confirmation_front_revalidations += len(points)

    # Recompute six-job baseline comparisons after search, with exact units.
    baseline_path = ROOT / manifest["baseline_path"]
    baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline = [(int(item["makespan"]), int(item["tec_exact"]["numerator"]))
                for item in baseline_data["front"]]
    if len(baseline) != 43 or not baseline_data["pareto_proven"]:
        raise AssertionError("Baseline não corresponde à referência completa de 43 pontos")
    for row in metrics:
        if int(row["n"]) != 6:
            continue
        data, points = cache[(row["instance"], row["configuration"], int(row["seed"]))]
        keys = [key for key, _ in points]
        equal = sum(key in baseline for key in keys)
        dominated = sum(any(b[0] <= key[0] and b[1] <= key[1] and b != key for b in baseline)
                        for key in keys)
        conflicts = [key for key in keys if any(key[0] <= b[0] and key[1] <= b[1] and key != b
                                                for b in baseline)]
        if conflicts:
            raise AssertionError(f"Ponto MOEA/D domina baseline: {row['result_file']} {conflicts}")
        row.update({"baseline_points": len(baseline), "baseline_equal": equal,
                    "approx_points_dominated_by_baseline": dominated,
                    "approx_points_dominating_baseline": 0})
    write_csv(OUT / "metrics.csv", metrics)

    summaries = []
    for instance_name in sorted({r["instance"] for r in metrics}):
        for label in MOEAD_LABELS:
            group = [r for r in metrics if r["instance"] == instance_name and r["configuration"] == label]
            if len(group) != 3:
                raise AssertionError(f"Célula principal incompleta: {instance_name} {label}")
            summaries.append({
                "instance": instance_name, "n": group[0]["n"], "configuration": label,
                "population_size": group[0]["population_size"], "max_evaluations": group[0]["max_evaluations"],
                "front_median": median([int(r["front_size"]) for r in group]),
                "front_min": min(int(r["front_size"]) for r in group),
                "front_max": max(int(r["front_size"]) for r in group),
                "cmax_min_median": median([int(r["cmax_min"]) for r in group]),
                "tec_min_median_float": median([float(Fraction(r["tec_min_exact"])) for r in group]),
                "tec_min_exact_by_seed": ";".join(f"s{r['seed']}:{r['tec_min_exact']}" for r in group),
                "rejection_rate_median": median([float(r["rejection_rate"]) for r in group]),
                "fallbacks_median": median([int(r["fallbacks"]) for r in group]),
                "seconds_median": median([float(r["elapsed_seconds"]) for r in group]),
                "milliseconds_per_evaluation_median": median([float(r["milliseconds_per_evaluation"]) for r in group]),
                "population_schedules_median": median([int(r["population_distinct_schedules"]) for r in group]),
                "front_schedules_median": median([int(r["front_distinct_schedules"]) for r in group]),
                "population_allocation_order_mode_wait_medians": "/".join(
                    str(median([int(r[k]) for r in group])) for k in
                    ("population_allocations", "population_orders", "population_modes", "population_waits")),
                "front_allocation_order_mode_wait_medians": "/".join(
                    str(median([int(r[k]) for r in group])) for k in
                    ("front_allocations", "front_orders", "front_modes", "front_waits")),
                "cmax_h_range_union": f"{min(float(r['cmax_h_min']) for r in group):.6f}-"
                                      f"{max(float(r['cmax_h_max']) for r in group):.6f}",
                "tec_max_cost_range_union": f"{min(float(r['tec_normalized_min']) for r in group):.6f}-"
                                            f"{max(float(r['tec_normalized_max']) for r in group):.6f}",
            })
    write_csv(OUT / "summary.csv", summaries)

    coverage_rows = []
    for instance_name in sorted({r["instance"] for r in metrics}):
        for population in (20, 50, 100):
            for seed in (11, 29, 47):
                _, small = cache[(instance_name, f"pop{population}_b2000", seed)]
                _, large = cache[(instance_name, f"pop{population}_b8000", seed)]
                small_keys = [k for k, _ in small]
                large_keys = [k for k, _ in large]
                coverage_rows.append({"instance": instance_name, "population_size": population,
                    "seed": seed, "coverage_8000_by_2000": coverage(small_keys, large_keys),
                    "coverage_2000_by_8000": coverage(large_keys, small_keys),
                    "front_2000": len(small_keys), "front_8000": len(large_keys)})
    write_csv(OUT / "paired_coverage.csv", coverage_rows)

    sensitivity = []
    controls = {(r["instance"], int(r["seed"])): r for r in metrics
                if r["configuration"] == "pop50_b2000"}
    for label in ("neighbors05", "neighbors40", "mating_global"):
        for instance_name in sorted({controls_i for controls_i, _ in controls}):
            for seed in (11, 29, 47):
                control = controls[(instance_name, seed)]
                variant = next(r for r in metrics if r["instance"] == instance_name
                               and r["configuration"] == label and int(r["seed"]) == seed)
                a = cache[(instance_name, "pop50_b2000", seed)][1]
                b = cache[(instance_name, label, seed)][1]
                sensitivity.append({"instance": instance_name, "seed": seed, "variant": label,
                    "control_n_neighbors": control["n_neighbors"],
                    "variant_n_neighbors": variant["n_neighbors"],
                    "control_prob_neighbor_mating": control["prob_neighbor_mating"],
                    "variant_prob_neighbor_mating": variant["prob_neighbor_mating"],
                    "front_control": len(a), "front_variant": len(b),
                    "variant_covered_by_control": coverage([k for k, _ in a], [k for k, _ in b]),
                    "control_covered_by_variant": coverage([k for k, _ in b], [k for k, _ in a]),
                    "cmax_min_control": control["cmax_min"], "cmax_min_variant": variant["cmax_min"],
                    "tec_min_control": control["tec_min_exact"], "tec_min_variant": variant["tec_min_exact"],
                    "rejection_control": control["rejection_rate"], "rejection_variant": variant["rejection_rate"],
                    "population_schedules_control": control["population_distinct_schedules"],
                    "population_schedules_variant": variant["population_distinct_schedules"]})
    write_csv(OUT / "sensitivity_paired.csv", sensitivity)

    # Compare only identical instance, seed and search budget.
    spea_rows = load_csv(ROOT / "data/output/spea2/piloto/metrics.csv")
    vns_rows = load_csv(ROOT / "data/output/vns_vnd/piloto/metrics.csv")
    comparison = []
    for row in metrics:
        label = row["configuration"]
        if label not in MOEAD_LABELS:
            continue
        budget, seed, instance_name = int(row["max_evaluations"]), int(row["seed"]), row["instance"]
        population = int(row["population_size"])
        spea_metric = next(r for r in spea_rows if r["instance"] == instance_name
            and int(r["seed"]) == seed and int(r["max_evaluations"]) == budget
            and int(r["population_size"]) == 50 and float(r["crossover_probability"]) == 0.9
            and float(r["mutation_probability"]) == 0.3)
        vns_label = "reference" if budget == 2000 else "budget_8000"
        vns_metric = next(r for r in vns_rows if r["instance"] == instance_name
                          and int(r["seed"]) == seed and int(r["max_evaluations"]) == budget
                          and r["configuration"] == vns_label)
        vns_instance_path = next(p for p in (ROOT / "data/input").glob("*/*.dat")
                                 if p.name == instance_name)
        vns_data = json.loads((ROOT / "data/output/vns_vnd/piloto/runs"
            / f"{Path(instance_name).stem}_{vns_label}_seed{seed}.json").read_text(encoding="utf-8"))
        vns_instance_data = read_instance(vns_instance_path)
        vns_tec = min((evaluate_schedule(vns_instance_data,
            tuple(tuple(tuple(op) for op in machine) for machine in point["representation"])).tec_exact
            for point in vns_data["front"]))
        comparison.append({"instance": instance_name, "seed": seed, "budget": budget,
            "moead_population": population,
            "moead_front": row["front_size"], "moead_cmax_min": row["cmax_min"],
            "moead_tec_min_exact": row["tec_min_exact"], "moead_seconds": row["elapsed_seconds"],
            "moead_ms_per_evaluation": row["milliseconds_per_evaluation"],
            "moead_rejection_rate": row["rejection_rate"],
            "spea2_front": spea_metric["front_size"], "spea2_cmax_min": spea_metric["cmax_min"],
            "spea2_tec_min_exact": spea_metric["tec_min_exact"],
            "spea2_seconds": spea_metric["elapsed_seconds"],
            "spea2_ms_per_evaluation": spea_metric["milliseconds_per_evaluation"],
            "spea2_rejection_rate": spea_metric["rejection_rate"],
            "vns_front": vns_metric["front_size"], "vns_cmax_min": vns_metric["cmax_min"],
            "vns_tec_min_exact": frac_text(vns_tec),
            "vns_seconds": vns_metric["seconds"],
            "vns_ms_per_evaluation": vns_metric["milliseconds_per_evaluation"],
            "vns_rejection_rate": vns_metric["rejection_rate"]})
    write_csv(OUT / "comparison_paired.csv", comparison)

    comparison_summary = []
    for instance_name in sorted({r["instance"] for r in comparison}):
        for budget in (2000, 8000):
            for algorithm in ("moead", "spea2", "vns"):
                group = [r for r in comparison if r["instance"] == instance_name and r["budget"] == budget]
                # P=50 is the common MOEA/D population in the paired summary;
                # this also deduplicates the identical SPEA2/VNS rows across P.
                group = [r for r in group if r["moead_population"] == 50]
                comparison_summary.append({"instance": instance_name, "budget": budget,
                    "algorithm": algorithm, "front_median": median([int(r[f"{algorithm}_front"]) for r in group]),
                    "cmax_min_median": median([int(r[f"{algorithm}_cmax_min"]) for r in group]),
                    "tec_min_median": median([float(Fraction(r[f"{algorithm}_tec_min_exact"])) for r in group]),
                    "tec_min_exact_by_seed": ";".join(f"s{r['seed']}:{r[f'{algorithm}_tec_min_exact']}" for r in group),
                    "seconds_median": median([float(r[f"{algorithm}_seconds"]) for r in group]),
                    "ms_per_evaluation_median": median([float(r[f"{algorithm}_ms_per_evaluation"]) for r in group]),
                    "rejection_rate_median": median([float(r[f"{algorithm}_rejection_rate"]) for r in group])})
    write_csv(OUT / "comparison_summary.csv", comparison_summary)

    total_attempts = sum(int(r["attempts"]) for r in metrics)
    total_rejected = sum(int(r["rejected_evaluations"]) for r in metrics)
    confirmation_attempts = sum(int(r["attempts"]) for r in confirmation_rows)
    confirmation_rejected = sum(int(r["rejected_evaluations"]) for r in confirmation_rows)
    confirmation_caps = all(int(r["attempts"]) == int(r["max_evaluations"])
                            for r in confirmation_rows)
    summary_data = {"execution_count": len(metrics), "attempts": total_attempts,
        "confirmation_execution_count": len(confirmation_rows),
        "confirmation_attempts": confirmation_attempts,
        "total_execution_count": len(metrics) + len(confirmation_rows),
        "total_attempts": total_attempts + confirmation_attempts,
        "rejected": total_rejected, "rejection_rate": total_rejected / total_attempts,
        "total_rejected": total_rejected + confirmation_rejected,
        "total_rejection_rate": (total_rejected + confirmation_rejected)
                                / (total_attempts + confirmation_attempts),
        "post_search_validations": sum(int(r["post_search_validations"]) for r in metrics),
        "confirmation_post_search_validations": sum(
            int(r["post_search_validations"]) for r in confirmation_rows),
        "independent_front_revalidations": front_revalidations,
        "confirmation_independent_front_revalidations": confirmation_front_revalidations,
        "independent_population_revalidations": sum(
            int(r["independent_population_revalidations"]) for r in metrics),
        "confirmation_independent_population_revalidations": sum(
            int(r["independent_population_revalidations"]) for r in confirmation_rows),
        "all_fronts_unique_viable_exact_nondominated": True,
        "all_hard_caps_exact": (all(int(r["attempts"]) == int(r["max_evaluations"]) for r in metrics)
                                and confirmation_caps),
        "confirmation_hard_caps_exact": confirmation_caps,
        "baseline_points": len(baseline),
        "baseline_approx_equal_points": sum(int(r.get("baseline_equal") or 0) for r in metrics),
        "baseline_approx_dominated_points": sum(
            int(r.get("approx_points_dominated_by_baseline") or 0) for r in metrics),
        "baseline_conflicting_points": 0}
    (OUT / "summary.json").write_text(json.dumps(summary_data, indent=2) + "\n", encoding="utf-8")

    # Human-readable report from the preserved per-run and paired metrics.
    report = [
        "# Piloto experimental MOEA/D — síntese provisória",
        "",
        "Execução do MOEA/D nativo do pymoo 0.6.2; algoritmo aprovado no release-check mantido sem alterações. "
        "Resultados diagnósticos de três seeds, não conclusões estatísticas nem tuning definitivo.",
        "",
        "## Desenho e execução",
        "",
        "Instâncias: `set1/6_2_1439_3_S_1-9.dat`, `set1/14_2_1439_3_S_1-9_derivada.dat`, "
        "`set2/50_10_1439_5_S_1-9.dat` e `set2/250_10_1439_5_S_1-9.dat`; seeds 11/29/47. "
        "Grade principal: P=20/50/100 × 2.000/8.000 avaliações. Sensibilidade isolada em P=50/2.000: "
        "n_neighbors 5/40 e mating global (probabilidade local 0); controle usa os defaults 20/0,9. "
        "Todos os casos mantêm crossover 0,9, mutation 0,3, sampling/crossover/mutation SPEA2, "
        "Tchebycheff e `Cmax/H`, `TEC/max_cost`.",
        "",
        f"Foram executadas {len(metrics)} buscas principais e {total_attempts:,} tentativas, "
        f"mais {len(confirmation_rows)} confirmações seletivas de {confirmation_attempts:,} tentativas "
        f"({summary_data['total_attempts']:,} no total), com "
        f"{summary_data['post_search_validations'] + summary_data['confirmation_post_search_validations']:,} "
        f"validações pymoo pós-busca e "
        f"{front_revalidations + confirmation_front_revalidations:,} reavaliações independentes das frentes. "
        f"Rejeições/fallbacks: {total_rejected:,} ({total_rejected / total_attempts:.3%}). "
        "Cada execução atingiu exatamente seu hard cap. A duração inclui setup e busca e exclui as validações posteriores. "
        f"Ambiente: Python {manifest['runtime']['python'].split()[0]}, NumPy {manifest['runtime']['numpy']}, "
        f"pymoo {manifest['runtime']['pymoo']}; tempo acumulado da grade principal "
        f"{sum(float(r['elapsed_seconds']) for r in metrics):.1f} s e da confirmação "
        f"{sum(float(r['elapsed_seconds']) for r in confirmation_rows):.1f} s.",
        "",
        "## Grade principal por população e orçamento",
        "",
        "Cmax e TEC mínimos são extremos separados; `TEC med.` está arredondado para leitura, enquanto "
        "`metrics.csv` conserva a fração exata por seed. Diversidade `pop A/O/M/W` conta assinaturas distintas "
        "de alocação, ordem, modo e espera na população final. `ms/eval` usa tentativas, inclusive rejeições.",
        "",
        "| n | P | Avaliações | Frente med. [min–max] | Cmax mín. med. | TEC mín. med. | s med. | ms/eval | pop A/O/M/W med. |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in summaries:
        report.append(f"| {r['n']} | {r['population_size']} | {int(r['max_evaluations']):,} "
            f"| {r['front_median']} [{r['front_min']}–{r['front_max']}] | {r['cmax_min_median']:.0f} "
            f"| {r['tec_min_median_float']:.3f} | {r['seconds_median']:.2f} "
            f"| {r['milliseconds_per_evaluation_median']:.3f} | {r['population_allocation_order_mode_wait_medians']} |")

    report += [
        "",
        "P=100 aumenta a quantidade de pontos/frontes e diversidade em várias células, com maior custo de replacement; "
        "não vence uniformemente. P=20 deixa menos trabalho na população inicial (1% de 2k; 0,25% de 8k), "
        "P=50 consome 2,5%/0,625% e P=100 5%/1,25%. P=50 é compromisso provisório entre tamanho de frente, "
        "diversidade e custo; 250 tarefas mostra casos em que P=20 ou 100 supera P=50.",
        "",
        "## Sensibilidade a orçamento, vizinhança e mating",
        "",
        "Coverage é a fração da frente-alvo dominada ou igualada pela outra frente, calculada por objetivos exatos; "
        "usa seeds pareadas e não é uma métrica de qualidade global.",
        "",
        "| n | P | Coverage 8k por 2k (med.) | Coverage 2k por 8k (med.) |",
        "|---:|---:|---:|---:|",
    ]
    for n in (6, 14, 50, 250):
        path = next(p for p in manifest["instances"] if Path(p).name.startswith(f"{n}_"))
        for psize in (20, 50, 100):
            group = [r for r in coverage_rows if r["instance"] == Path(path).name
                     and int(r["population_size"]) == psize]
            report.append(f"| {n} | {psize} | {median([r['coverage_8000_by_2000'] for r in group]):.1%} "
                          f"| {median([r['coverage_2000_by_8000'] for r in group]):.1%} |")
    report += ["", "Aumentar de 2k para 8k melhora TEC nas três seeds em 14, 50 e 250 tarefas; "
        "em 6 tarefas o TEC já estabilizou. Em 250, Cmax muda pouco e TEC continua a melhorar: P=50 reduz "
        "o TEC mínimo em cada seed, de aproximadamente 2.061/2.091/2.108 para 1.799/1.966/1.935. "
        "Por isso foi feita confirmação seletiva P=50/20k em três seeds. Cmax mínimo ficou idêntico ao de 8k "
        "nas três seeds; TEC mínimo caiu de 2.159e8/2.359e8/2.322e8 para 2.034e8/2.147e8/2.037e8 unidades "
        "exatas (~5,8%/9,0%/12,3%). A cobertura da frente 8k pela de 20k foi 87,5%/100%/100%; "
        "a frente 20k introduz novos pontos não dominados, sem reduzir schedules/população distintos. "
        "Cada execução levou ~76–77 s. É evidência de ganho adicional em TEC para n=250, não motivo para tornar "
        "20k orçamento comum sem comparação pareada equivalente. Detalhes em `confirmation_metrics.csv` e "
        "`confirmation_paired.csv`.", "",
        "Sensibilidade P=50/2k, medianas pareadas sobre quatro instâncias e três seeds:", "",
        "| Variante | n_neighbors | Prob. local | Frente mediana | Rejeições | Leitura |"]
    report.append("|---|---:|---:|---:|---:|---|")
    for label, neighbors, probability in (("neighbors05", 5, 0.9), ("neighbors40", 40, 0.9),
                                          ("mating_global", 20, 0.0)):
        group = [r for r in metrics if r["configuration"] == label]
        report.append(f"| {label} | {neighbors} | {probability:g} | "
            f"{median([int(r['front_size']) for r in group]):g} | "
            f"{sum(int(r['rejected_evaluations']) for r in group)} | efeito varia por instância/seed; "
            f"detalhes pareados em `sensitivity_paired.csv` |")
    report += ["", "Vizinhança 40 teve queda forte de diversidade/frente em alguns casos de 250 tarefas "
        "(1 ponto para seed 11), mas efeito não é consistente em outros tamanhos. Mating global teve frente e TEC "
        "piores que o controle em 250 nas três seeds; Cmax foi melhor em duas e pior em uma. Evidência favorece "
        "manter a vizinhança 20 e mating local 0,9 como provisórios, sem declarar ótimo.",
        "", "## Diversidade, rejeições e escala", "",
        "Não houve rejeições nas 108 execuções naturais; fallback ocorreu zero vezes, inclusive em 250 tarefas. "
        "Logo o piloto não observou perda de diversidade atribuível ao fallback. A população mantém em geral "
        "diversidade de schedules/modos maior que a frente; ordens e alocações ficam mais restritas nas instâncias grandes. "
        "Medianas por execução e por seed estão em `metrics.csv`.", "",
        "Para P=50/8k, as faixas observadas sobre as três seeds são:", "",
        "| n | Cmax/H | TEC/max_cost | bins Cmax (5) | bins TEC (5) |",
        "|---:|---:|---:|---|---|"]
    for n in (6, 14, 50, 250):
        instance_name = next(Path(p).name for p in manifest["instances"] if Path(p).name.startswith(f"{n}_"))
        group = [r for r in metrics if r["instance"] == instance_name and r["configuration"] == "pop50_b8000"]
        report.append(f"| {n} | {min(float(r['cmax_h_min']) for r in group):.3f}–"
            f"{max(float(r['cmax_h_max']) for r in group):.3f} | "
            f"{min(float(r['tec_normalized_min']) for r in group):.3f}–"
            f"{max(float(r['tec_normalized_max']) for r in group):.3f} | "
            f"{'; '.join(r['cmax_bins_5'] for r in group)} | "
            f"{'; '.join(r['tec_bins_5'] for r in group)} |")
    report += ["", "As directions distribuem pesos uniformemente, não pontos na frente. No n=50 e n=250, "
        "a amplitude observada de TEC/max_cost é cerca de três vezes a de Cmax/H em P=50/8k; "
        "isso pode concentrar a scalarização Tchebycheff e não garante cobertura uniforme. Não houve overflow, "
        "valores não finitos ou sinais de perda de ordenação; os divisores ficaram inalterados. "
        "A diferença de amplitude é limitação metodológica concreta para considerar em análises futuras.",
        "", "## Comparação pareada preliminar", "",
        "MOEA/D com P=50 contra SPEA2 (P=50, operadores 0,9/0,3) e VNS/VND (configuração de referência), "
        "mesma instância, seed e orçamento. Medianas de três seeds; o TEC por seed exato consta no CSV. "
        "Os tempos incluem overhead distinto de cada implementação e não constituem ranking de eficiência isolado.", "",
        "| n | Orçamento | Algoritmo | Frente med. | Cmax mín. med. | TEC mín. med. | Tempo med. (s) | ms/eval med. | Rejeição med. |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for r in comparison_summary:
        report.append(f"| {Path(r['instance']).name.split('_')[0]} | {r['budget']:,} | {r['algorithm']} "
            f"| {r['front_median']:g} | {r['cmax_min_median']:g} | {r['tec_min_median']:.3f} "
            f"| {r['seconds_median']:.2f} | {r['ms_per_evaluation_median']:.3f} "
            f"| {r['rejection_rate_median']:.1%} |")
    report += ["", "MOEA/D fica entre VNS/VND e SPEA2 em tempo por avaliação na maior parte das células. "
        "Qualidade varia por instância: em 50/250 tarefas SPEA2 frequentemente acha menor Cmax, enquanto "
        "MOEA/D mantém desempenho competitivo em TEC e tamanho de frente. VNS/VND tem menos custo por avaliação, "
        "mas nos 250 jobs seus extremos são limitados pelo horizonte e rejeição mais alta. Isso é diagnóstico, "
        "não uma conclusão de algoritmo vencedor. Dados pareados completos: `comparison_paired.csv` e `comparison_summary.csv`.",
        "", "## Baseline exato de 6 tarefas", "",
        "Baseline completo de 43 pontos lido apenas depois das buscas; nenhum ponto aproximado dominou o baseline. "
        "Entre as frentes das 27 execuções de seis tarefas (grade principal mais sensibilidades), 229 ocorrências "
        "de pontos coincidiram exatamente com a frente e 328 foram dominadas por ela; zero conflitos. "
        "Contagens por execução estão em `metrics.csv`.",
        "", "## Decisão provisória", "",
        "Usar P=50, n_neighbors=20, mating local 0,9, crossover 0,9, mutation 0,3, Tchebycheff e escala aprovada "
        "para comparação inicial. Orçamento comum recomendado: 8.000 tentativas; 2.000 serve para triagem. "
        "P=100 é alternativa quando tamanho de frente/diversidade pesa mais, especialmente em n=14/50, e P=20 reduz "
        "custo por avaliação. Não há evidência de bug ou motivo para alterar o MOEA/D antes dos experimentos finais. "
        "A confirmação de 20k é seletiva e não altera o orçamento comum.",
        "", "Riscos: três seeds e uma instância por escala não sustentam inferência estatística; referências uniformes "
        "não equilibram automaticamente amplitudes efetivas; o piloto não avaliou hipervolume nem convergência global.",
        "", "Artefatos: `manifest.json`, `metrics.csv`, `summary.csv`, `paired_coverage.csv`, `sensitivity_paired.csv`, "
        "`comparison_paired.csv`, `comparison_summary.csv`, `summary.json`, `runs/` e os scripts `run_pilot.py`, "
        "`run_confirmation.py` e `summarize_pilot.py`."]
    (OUT / "relatorio.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary_data, indent=2))


if __name__ == "__main__":
    main()
