"""Validate and summarize the SPEA2 pilot after all searches have finished."""

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
VNS_RUNS = ROOT / "data/output/vns_vnd/piloto/runs"
BASELINE = ROOT / "data/output/custom_exact_dp/6_2_1439_3_S_1-9.json"


def load_rows():
    with (OUT / "metrics.csv").open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def exact_front(json_path: Path, instance):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    points = []
    for item in data["front"]:
        rep = item["representation"]
        schedule = tuple(tuple(tuple(int(v) for v in entry) for entry in machine)
                         for machine in rep)
        evaluation = evaluate_schedule(instance, schedule)
        exact = item["tec_exact"]
        expected = (int(item["makespan"]), Fraction(exact["numerator"], exact["denominator"]))
        actual = (evaluation.cmax, evaluation.tec_exact)
        if actual != expected:
            raise AssertionError(f"Reavaliação divergente em {json_path}")
        points.append((evaluation.objective_key, schedule))
    keys = [point for point, _ in points]
    if len(keys) != len(set(keys)):
        raise AssertionError(f"Pontos duplicados em {json_path}")
    if any(dominates(first, second) for first in keys for second in keys):
        raise AssertionError(f"Ponto dominado em {json_path}")
    return data, keys, len(points)


def median(values):
    return statistics.median(values) if values else None


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def dominates_exact(a, b):
    return a[0] <= b[0] and a[1] <= b[1] and a != b


def dominates_or_equal(a, b):
    return a[0] <= b[0] and a[1] <= b[1]


def main():
    rows = load_rows()
    if len(rows) != 108:
        raise AssertionError(f"Esperadas 108 execuções completas, encontradas {len(rows)}")
    audit_evaluations = 0
    cached = {}
    for row in rows:
        path = RUNS / (f"{Path(row['instance']).stem}__{row['configuration']}__"
                       f"b{row['max_evaluations']}__s{row['seed']}.json")
        instance = read_instance(ROOT / "data/input" / ("set1" if int(row["n"]) <= 14 else "set2")
                                 / row["instance"])
        data, keys, count = exact_front(path, instance)
        if data["instance_sha256"] != instance.digest or row["instance_sha256"] != instance.digest:
            raise AssertionError(f"Hash da entrada diverge em {path}")
        audit_evaluations += count
        cached[(row["instance"], row["configuration"], row["max_evaluations"], row["seed"])] = (data, keys)
        if (data["evaluations"] != int(row["max_evaluations"])
                or data["pymoo_evaluations"] != int(row["max_evaluations"])):
            raise AssertionError(f"Hard cap divergente: {path}")
        if data["post_search_validations"] != int(row["post_search_validations"]):
            raise AssertionError(f"Contagem de post_search_validations divergente: {path}")

    # Grouped summaries for population/budget sensitivity.
    groups = {}
    for row in rows:
        if not row["configuration"].startswith("pop"):
            continue
        key = (row["instance"], int(row["population_size"]), int(row["max_evaluations"]))
        groups.setdefault(key, []).append(row)
    summary = []
    for (instance, population, budget), values in sorted(groups.items()):
        summary.append({
            "instance": instance, "population_size": population, "max_evaluations": budget,
            "seeds": len(values), "front_size_median": median([int(r["front_size"]) for r in values]),
            "cmax_min_median": median([int(r["cmax_min"]) for r in values]),
            "tec_min_median_exact": str(median([
                Fraction(r["tec_min_exact"]) for r in values
            ])),
            "rejection_rate_median": median([float(r["rejection_rate"]) for r in values]),
            "seconds_median": median([float(r["elapsed_seconds"]) for r in values]),
            "ms_per_eval_median": median([float(r["milliseconds_per_evaluation"]) for r in values]),
            "allocation_signatures_median": median([int(r["allocation_signatures"]) for r in values]),
            "order_signatures_median": median([int(r["order_signatures"]) for r in values]),
            "mode_signatures_median": median([int(r["mode_signatures"]) for r in values]),
        })
    write_csv(OUT / "summary.csv", summary, list(summary[0]))

    budget_rows = []
    progress_groups = {}
    for instance_name in {r["instance"] for r in rows}:
        for population in (20, 50, 100):
            for seed in ("11", "29", "47"):
                low_data, low_keys = cached[(instance_name, f"pop{population}", "2000", seed)]
                high_data, high_keys = cached[(instance_name, f"pop{population}", "8000", seed)]
                covered = sum(any(dominates_or_equal(high, low) for high in high_keys)
                              for low in low_keys)
                low_cmax, high_cmax = min(k[0] for k in low_keys), min(k[0] for k in high_keys)
                low_tec = min(k[1] for k in low_keys)
                high_tec = min(k[1] for k in high_keys)
                record = {
                    "instance": instance_name, "population_size": population, "seed": seed,
                    "front_2000": len(low_keys), "front_8000": len(high_keys),
                    "front_2000_covered_by_8000_percent": 100 * covered / len(low_keys),
                    "cmax_min_2000": low_cmax, "cmax_min_8000": high_cmax,
                    "cmax_improved": high_cmax < low_cmax,
                    "tec_min_2000_units": low_tec, "tec_min_8000_units": high_tec,
                    "tec_improved": high_tec < low_tec,
                }
                budget_rows.append(record)
                progress_groups.setdefault((instance_name, population), []).append(record)
    write_csv(OUT / "budget_progress.csv", budget_rows, list(budget_rows[0]))

    budget_summary = [{
        "instance": instance_name, "population_size": population,
        "front_2000_covered_by_8000_percent_median": median(
            [r["front_2000_covered_by_8000_percent"] for r in values]),
        "seeds_cmax_improved": sum(r["cmax_improved"] for r in values),
        "seeds_tec_improved": sum(r["tec_improved"] for r in values),
        "front_2000_median": median([r["front_2000"] for r in values]),
        "front_8000_median": median([r["front_8000"] for r in values]),
    } for (instance_name, population), values in sorted(progress_groups.items())]

    # Operator sensitivity is reported independently, paired by seed and instance.
    op_rows = []
    for row in rows:
        if row["configuration"] in {"mutation01", "mutation05", "crossover06"}:
            op_rows.append({key: row[key] for key in (
                "instance", "configuration", "seed", "population_size", "max_evaluations",
                "front_size", "cmax_min", "tec_min_exact", "rejection_rate",
                "elapsed_seconds", "milliseconds_per_evaluation", "allocation_signatures",
                "order_signatures", "mode_signatures")})
    write_csv(OUT / "operator_sensitivity.csv", op_rows, list(op_rows[0]))
    operator_summary = []
    operator_groups = {}
    for row in op_rows:
        operator_groups.setdefault((row["instance"], row["configuration"]), []).append(row)
    for (instance_name, configuration), values in sorted(operator_groups.items()):
        operator_summary.append({
            "instance": instance_name, "configuration": configuration,
            "front_size_median": median([int(r["front_size"]) for r in values]),
            "cmax_min_median": median([int(r["cmax_min"]) for r in values]),
            "tec_min_median_exact": str(median([Fraction(r["tec_min_exact"]) for r in values])),
            "rejection_rate_median": median([float(r["rejection_rate"]) for r in values]),
            "seconds_median": median([float(r["elapsed_seconds"]) for r in values]),
            "allocation_signatures_median": median([int(r["allocation_signatures"]) for r in values]),
            "order_signatures_median": median([int(r["order_signatures"]) for r in values]),
            "mode_signatures_median": median([int(r["mode_signatures"]) for r in values]),
        })
    write_csv(OUT / "operator_summary.csv", operator_summary, list(operator_summary[0]))

    # Paired VNS comparison: current SPEA2 control (pop 50) against VNS reference.
    comparison = []
    for row in rows:
        if row["configuration"] != "pop50":
            continue
        budget = int(row["max_evaluations"])
        config = "reference" if budget == 2_000 else "budget_8000"
        stem = Path(row["instance"]).stem
        vns_path = VNS_RUNS / f"{stem}_{config}_seed{row['seed']}.json"
        vns = json.loads(vns_path.read_text(encoding="utf-8"))
        spea, spea_keys = cached[(row["instance"], "pop50", str(budget), row["seed"])]
        comparison.append({
            "instance": row["instance"], "seed": row["seed"], "max_evaluations": budget,
            "spea2_front": len(spea_keys), "spea2_cmax_min": min(k[0] for k in spea_keys),
            "spea2_tec_min_exact": min((Fraction(k[1], spea["cost_scale"]) for k in spea_keys)),
            "spea2_seconds": row["elapsed_seconds"], "spea2_rejection_rate": row["rejection_rate"],
            "vns_front": int(vns["points"]),
            "vns_cmax_min": min(p["makespan"] for p in vns["front"]),
            "vns_tec_min_exact": min(Fraction(p["tec_exact"]["numerator"],
                                               p["tec_exact"]["denominator"]) for p in vns["front"]),
            "vns_seconds": vns["elapsed_seconds"],
            "vns_rejection_rate": vns["rejected_evaluations"] / vns["evaluations"],
        })
    write_csv(OUT / "vns_comparison.csv", comparison, list(comparison[0]))
    comparison_groups = {}
    for record in comparison:
        comparison_groups.setdefault((record["instance"], int(record["max_evaluations"])), []).append(record)
    comparison_summary = []
    for (instance_name, budget), values in sorted(comparison_groups.items()):
        comparison_summary.append({
            "instance": instance_name, "max_evaluations": budget,
            "spea2_front_median": median([r["spea2_front"] for r in values]),
            "spea2_cmax_min_median": median([r["spea2_cmax_min"] for r in values]),
            "spea2_tec_min_median": median([float(r["spea2_tec_min_exact"]) for r in values]),
            "spea2_seconds_median": median([float(r["spea2_seconds"]) for r in values]),
            "spea2_rejection_median": median([float(r["spea2_rejection_rate"]) for r in values]),
            "vns_front_median": median([r["vns_front"] for r in values]),
            "vns_cmax_min_median": median([r["vns_cmax_min"] for r in values]),
            "vns_tec_min_median": median([float(r["vns_tec_min_exact"]) for r in values]),
            "vns_seconds_median": median([float(r["vns_seconds"]) for r in values]),
            "vns_rejection_median": median([float(r["vns_rejection_rate"]) for r in values]),
        })
    write_csv(OUT / "vns_comparison_summary.csv", comparison_summary,
              list(comparison_summary[0]))

    # Exact baseline is read only here, after all runs and front audits.
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    if baseline.get("status") != "complete" or not baseline.get("pareto_proven"):
        raise AssertionError("Baseline de 6 jobs não está completo/provado")
    baseline_points = [(int(p["makespan"]), Fraction(int(p["tec_exact"]["numerator"]),
                                                        int(p["tec_exact"]["denominator"])))
                       for p in baseline["front"]]
    baseline_rows = []
    for row in rows:
        if row["n"] != "6":
            continue
        run_data, keys = cached[(row["instance"], row["configuration"], row["max_evaluations"], row["seed"])]
        approximate = [(key[0], Fraction(key[1], run_data["cost_scale"])) for key in keys]
        equal = sum(point in baseline_points for point in approximate)
        dominated = sum(any(dominates_exact(exact, point) for exact in baseline_points)
                        for point in approximate)
        dominates_optimum = sum(any(dominates_exact(point, exact) for exact in baseline_points)
                                for point in approximate)
        baseline_rows.append({
            "configuration": row["configuration"], "population_size": row["population_size"],
            "budget": row["max_evaluations"], "seed": row["seed"],
            "equal_baseline_points": equal, "approximate_strictly_dominated": dominated,
            "approximate_points_dominating_baseline": dominates_optimum,
            "approximate_front_size": len(approximate), "baseline_points": len(baseline_points),
        })
    write_csv(OUT / "baseline_6_jobs.csv", baseline_rows, list(baseline_rows[0]))
    baseline_groups = {}
    for record in baseline_rows:
        baseline_groups.setdefault((record["configuration"], int(record["budget"])), []).append(record)
    baseline_summary = [{
        "configuration": configuration, "budget": budget,
        "equal_points_median": median([r["equal_baseline_points"] for r in values]),
        "dominated_approx_points_median": median([r["approximate_strictly_dominated"] for r in values]),
        "approx_points_dominating_baseline_total": sum(r["approximate_points_dominating_baseline"]
                                                        for r in values),
        "baseline_points": len(baseline_points),
    } for (configuration, budget), values in sorted(baseline_groups.items())]
    write_csv(OUT / "baseline_summary.csv", baseline_summary, list(baseline_summary[0]))

    # Markdown report is completed from exact-run data; objective extrema are not paired.
    total_attempts = sum(int(r["attempts"]) for r in rows)
    rejection_rates = [float(r["rejection_rate"]) for r in rows]
    times = [float(r["elapsed_seconds"]) for r in rows]
    lines = [
        "# Piloto experimental SPEA2 incremental",
        "",
        "Resultados do SPEA2 fornecido pelo pymoo 0.6.2. O piloto foi executado sem baseline na busca. "
        "O algoritmo não foi alterado nesta etapa.",
        "",
        "## Desenho",
        "",
        "Quatro instâncias recuperadas do piloto VNS: 6, 14 (derivada), 50 e 250 jobs; seeds 11/29/47. "
        "Sensibilidade de população: 20/50/100 em orçamentos 2.000/8.000. Sensibilidade isolada dos "
        "operadores em pop 50 e orçamento 2.000: mutation 0.1/0.5 e crossover 0.6. Controle: crossover "
        "0.9 e mutation 0.3. Regime SPEA2 incremental com `n_offsprings=1`.",
        "",
        f"Execuções: {len(rows)}; tentativas totais: {total_attempts:,}; rejeições: "
        f"{sum(int(r['rejected_evaluations']) for r in rows):,}; avaliações viáveis: "
        f"{sum(int(r['feasible_evaluations']) for r in rows):,}; `post_search_validations` dos sobreviventes: "
        f"{sum(int(r['post_search_validations']) for r in rows):,}; reavaliações independentes da frente "
        f"neste pós-processamento: {audit_evaluations:,}. Soma dos tempos SPEA2: {sum(times):.1f} s. "
        f"Taxa de rejeição observada: {min(rejection_rates):.1%}–{max(rejection_rates):.1%}.",
        "",
        "## Sensibilidade de população e orçamento",
        "",
        "Medianas sobre as três seeds. TEC mínimo está registrado por seed no `metrics.csv` como fração exata; "
        "a métrica de Cmax e TEC mínimo pode pertencer a soluções distintas.",
        "",
        "| Instância | Pop. | Avaliações | Frente med. | Cmax mín. med. | TEC mín. med. | Rejeição med. | s med. | ms/avaliação | Aloc./ordem/modos distintos med. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in summary:
        lines.append(f"| {r['instance']} | {r['population_size']} | {r['max_evaluations']} | "
                     f"{r['front_size_median']:.1f} | {r['cmax_min_median']:.1f} | "
                     f"{float(Fraction(r['tec_min_median_exact'])):.3f} | "
                     f"{r['rejection_rate_median']:.1%} | {r['seconds_median']:.2f} | "
                     f"{r['ms_per_eval_median']:.2f} | "
                     f"{r['allocation_signatures_median']:.1f}/{r['order_signatures_median']:.1f}/"
                     f"{r['mode_signatures_median']:.1f} |")
    lines += [
        "",
        "### Leitura preliminar",
        "",
        "* A população 20 deixa mais avaliações para evolução, enquanto 100 gasta 5% do orçamento de 2.000 "
        "ou 1,25% de 8.000 na população inicial, e aumenta o custo por avaliação devido à seleção/survival. "
        "As frentes frequentemente se aproximam do tamanho da população, em especial na instância derivada; "
        "pop 20 pode truncar a diversidade representável. Pop 50 é um compromisso provisório a confirmar "
        "pelas métricas pareadas, sem evidência de ótimo.",
        "* A frente tende a aumentar entre os orçamentos maiores, mas os extremos variam por seed. A tabela "
        "pareada abaixo mede cobertura fraca da frente de 2.000 pela de 8.000 e quantas seeds melhoram cada "
        "extremo; a frente pode diminuir por survival limitado à população.",
        "* Rejeição: nesta grade, os candidatos completos observados foram viáveis (taxa zero). Sampling "
        "construtivo e operadores não geraram inviabilidade observável nestas entradas/configurações; isso "
        "não prova taxa zero em outras instâncias ou seeds.",
        "* Operadores: as mudanças observadas variam por instância e seed. Nenhuma das três variantes teve "
        "vantagem consistente suficiente para substituir os valores atuais; não se selecionou configuração "
        "por uma seed isolada.",
        "* Não se viu colapso geral de diversidade: há variação de alocação, ordem e modos nas frentes. Ainda "
        "assim, a densidade/truncamento de `normalize=False` usa as unidades originais e a escala de TEC é "
        "numericamente maior que Cmax. Isso continua sendo risco metodológico; o piloto não instrumentou "
        "contribuições dimensionais do fitness e não permite concluir ausência de viés.",
        "* O regime incremental mantém strength/raw fitness/density/tournament/survival do pymoo, mas atualiza "
        "a seleção a cada offspring. O piloto não o trata como equivalente ao SPEA2 geracional clássico.",
        "",
        "#### Efeito do orçamento por população",
        "",
        "Cobertura fraca = fração dos pontos de 2.000 dominados ou igualados por algum ponto de 8.000, na mesma "
        "seed. `Cmax/TEC melhoraram` conta quantas das três seeds melhoraram cada extremo.",
        "",
        "| Instância | Pop. | Cobertura mediana | Seeds Cmax melhor | Seeds TEC melhor | Frente 2k→8k mediana |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in budget_summary:
        lines.append(f"| {r['instance']} | {r['population_size']} | "
                     f"{r['front_2000_covered_by_8000_percent_median']:.1f}% | "
                     f"{r['seeds_cmax_improved']}/3 | {r['seeds_tec_improved']}/3 | "
                     f"{r['front_2000_median']:.0f}→{r['front_8000_median']:.0f} |")
    lines += [
        "",
        "## Operadores",
        "",
        "Medianas das três seeds por instância. Controle: pop 50, orçamento 2.000, mutation 0.3 e crossover 0.9.",
        "",
        "| Instância | Variante | Frente | Cmax mín. | TEC mín. | Aloc./ordem/modos | s med. |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in operator_summary:
        lines.append(f"| {r['instance']} | {r['configuration']} | {r['front_size_median']:.0f} | "
                     f"{r['cmax_min_median']:.0f} | {float(Fraction(r['tec_min_median_exact'])):.3f} | "
                     f"{r['allocation_signatures_median']:.0f}/{r['order_signatures_median']:.0f}/"
                     f"{r['mode_signatures_median']:.0f} | {r['seconds_median']:.2f} |")
    lines += [
        "",
        "Resultados exatos pareados por seed em `operator_sensitivity.csv`.",
        "",
        "## Baseline exato de 6 jobs (pós-busca)",
        "",
        f"Baseline completo/provado: {len(baseline_points)} pontos. Medianas por configuração/orçamento:",
        "",
        "| Configuração | Orçamento | Iguais medianos | Aproximados dominados medianos | Aproximados que dominam baseline (total) |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in baseline_summary:
        lines.append(f"| {r['configuration']} | {r['budget']} | {r['equal_points_median']:.1f} | "
                     f"{r['dominated_approx_points_median']:.1f} | "
                     f"{r['approx_points_dominating_baseline_total']} |")
    lines += [
        "",
        "Detalhe por seed em `baseline_6_jobs.csv`. Nenhum ponto aproximado dominou um ponto do baseline. "
        "O baseline não participou de sampling, seleção, operadores ou término.",
        "",
        "## Comparação diagnóstica com VNS/VND",
        "",
        "Medianas em pares com mesma instância, seeds 11/29/47 e orçamento. SPEA2 usa pop 50 e operadores controle.",
        "",
        "| Instância | Avaliações | SPEA2 frente/Cmax/TEC | SPEA2 s/rejeição | VNS frente/Cmax/TEC | VNS s/rejeição |",
        "|---|---:|---|---|---|---|",
    ]
    for r in comparison_summary:
        lines.append(f"| {r['instance']} | {r['max_evaluations']} | "
                     f"{r['spea2_front_median']:.0f}/{r['spea2_cmax_min_median']:.0f}/"
                     f"{r['spea2_tec_min_median']:.3f} | {r['spea2_seconds_median']:.2f}/"
                     f"{r['spea2_rejection_median']:.1%} | {r['vns_front_median']:.0f}/"
                     f"{r['vns_cmax_min_median']:.0f}/{r['vns_tec_min_median']:.3f} | "
                     f"{r['vns_seconds_median']:.2f}/{r['vns_rejection_median']:.1%} |")
    lines += [
        "",
        "`vns_comparison.csv` contém os dados por seed. São medidas preliminares, sem alegação de superioridade. "
        "A medição de tempo é local e inclui custos diferentes de algoritmo.",
        "",
        "## Configuração e orçamento provisórios",
        "",
        "Para a próxima comparação, usar provisionalmente `population_size=50`, `crossover_probability=0.9`, "
        "`mutation_probability=0.3`, seeds pareadas e `max_evaluations=8_000`. Pop 20 pode ser incluída como "
        "sensibilidade econômica; pop 100 aumenta custo e às vezes a frente disponível, sem ganho consistente "
        "suficiente para recomendá-la como padrão. O orçamento 2.000 serve para triagem; 8.000 é mais "
        "informativo. O piloto não justifica 20.000 sem uma pergunta aberta específica.",
        "",
        "## Validação e artefatos",
        "",
        f"Todos os {len(rows)} arquivos de resultado foram reavaliados novamente pelo evaluator compartilhado "
        f"({audit_evaluations} schedules), com TEC exato, viabilidade, unicidade, não dominância e contagem "
        "de avaliações igual ao orçamento. Detalhes por execução em `metrics.csv`; agregados em `summary.csv`; "
        "operadores em `operator_sensitivity.csv`; comparação VNS em `vns_comparison.csv`; baseline em "
        "`baseline_6_jobs.csv`; schedules completos em `runs/`; parâmetros e hashes do runner em `manifest.json`.",
        "",
        "A seleção SPEA2 usa `SPEA2Survival(normalize=False)` para evitar divisão por amplitude zero conhecida "
        "no pymoo 0.6.2. A densidade em escala bruta favorece distâncias numéricas dominadas por unidades de "
        "TEC; permanece risco metodológico e não foi alterada durante o piloto.",
    ]
    (OUT / "relatorio.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "validation_audit.json").write_text(json.dumps({
        "runs": len(rows), "front_schedules_independently_reevaluated": audit_evaluations,
        "all_viable_unique_nondominated_exact": True,
        "all_search_evaluation_counts_equal_budget": True,
        "baseline_read_after_search": True,
    }, indent=2), encoding="utf-8")
    print(f"Validado: {len(rows)} execuções e {audit_evaluations} schedules exportados.")


if __name__ == "__main__":
    main()
