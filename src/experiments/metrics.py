"""Indicadores multiobjetivo, fronteira de referência PF* e testes estatísticos.

Objetivos minimizados: (Cmax, TEC em unidades inteiras exatas). Para cada
instância, PF* é a fronteira exata provada (execução Exata da campanha ou
baseline publicada em data/baselines) ou, na falta dela, a união não dominada
de todos os métodos e replicações. Distâncias e volumes usam o espaço
normalizado por ideal/nadir de PF*.
"""
from __future__ import annotations

import csv
from itertools import combinations
import json
import math
from pathlib import Path
import statistics

from problem import PROJECT_ROOT, atomic_json
from experiments.adapters import nondominated
from experiments.ledger import TERMINAL

HV_REFERENCE = 1.1
METRICS = ("HV", "IGD", "IGD_plus", "GD", "EPS_add", "Spacing", "Spread", "NDS", "R_PF", "wall_s", "cpu_s",
           "peak_rss_mib", "peak_rss_delta_mib")
HIGHER_IS_BETTER = {"HV", "NDS", "R_PF"}


# ------------------------------------------------------------------ indicadores
def normalize(points, ideal, nadir):
    ranges = [(n - i) if n > i else 1.0 for i, n in zip(ideal, nadir)]
    return [tuple((p[k] - ideal[k]) / ranges[k] for k in range(2)) for p in points]


def hypervolume_2d(points, reference=(HV_REFERENCE, HV_REFERENCE)):
    """HV exato em 2D (minimização); pontos fora da caixa de referência não contribuem."""
    inside = sorted(p for p in points if p[0] < reference[0] and p[1] < reference[1])
    volume, best_y = 0.0, reference[1]
    for x, y in inside:
        if y < best_y:
            volume += (reference[0] - x) * (best_y - y)
            best_y = y
    return volume


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def igd(approx, reference):
    return statistics.fmean(min(_dist(r, a) for a in approx) for r in reference)


def igd_plus(approx, reference):
    """IGD+ (Ishibuchi et al., 2015): d+(a, r) = ||max(a - r, 0)||."""
    return statistics.fmean(min(math.hypot(max(a[0] - r[0], 0), max(a[1] - r[1], 0)) for a in approx)
                            for r in reference)


def gd(approx, reference):
    """GD com p=1 (média das distâncias euclidianas a PF*)."""
    return statistics.fmean(min(_dist(a, r) for r in reference) for a in approx)


def epsilon_additive(approx, reference):
    """I_eps+(A, PF*): menor eps tal que todo r em PF* é fracamente dominado por algum a - eps."""
    return max(min(max(a[0] - r[0], a[1] - r[1]) for a in approx) for r in reference)


def spacing(approx):
    """Spacing de Schott com distância L1 ao vizinho mais próximo; |A| < 2 → 0."""
    if len(approx) < 2:
        return 0.0
    d = [min(abs(a[0] - b[0]) + abs(a[1] - b[1]) for j, b in enumerate(approx) if j != i)
         for i, a in enumerate(approx)]
    mean = statistics.fmean(d)
    return math.sqrt(sum((x - mean) ** 2 for x in d) / (len(d) - 1))


def spread(approx, reference):
    """Δ de Deb et al. (2002) com extremos de PF*; denominador nulo → 0."""
    ordered = sorted(approx)
    extremes = min(reference), min(reference, key=lambda p: (p[1], p[0]))
    d_f, d_l = _dist(extremes[0], ordered[0]), _dist(extremes[1], ordered[-1])
    gaps = [_dist(a, b) for a, b in zip(ordered, ordered[1:])]
    mean = statistics.fmean(gaps) if gaps else 0.0
    denominator = d_f + d_l + len(gaps) * mean
    return (d_f + d_l + sum(abs(g - mean) for g in gaps)) / denominator if denominator > 0 else 0.0


def coverage(a_points, b_points):
    """C(A, B): fração de B fracamente dominada por algum ponto de A (Zitzler & Thiele, 1999)."""
    if not b_points:
        return 0.0
    return sum(any(a[0] <= b[0] and a[1] <= b[1] for a in a_points) for b in b_points) / len(b_points)


def run_indicators(points, pf_star, ideal, nadir):
    if not points:   # falha de inicialização / corte sem pontos: HV 0, distâncias indefinidas
        return dict(HV=0.0, IGD=None, IGD_plus=None, GD=None, EPS_add=None, Spacing=None, Spread=None,
                    NDS=0, R_PF=0.0)
    a, r = normalize(points, ideal, nadir), normalize(pf_star, ideal, nadir)
    reference_set = set(map(tuple, pf_star))
    return dict(HV=hypervolume_2d(a), IGD=igd(a, r), IGD_plus=igd_plus(a, r), GD=gd(a, r),
                EPS_add=epsilon_additive(a, r), Spacing=spacing(a), Spread=spread(a, r), NDS=len(points),
                R_PF=sum(tuple(p) in reference_set for p in points) / len(pf_star))


# ------------------------------------------------------------------ estatística
def describe(values):
    values = [v for v in values if v is not None]
    if not values:
        return dict(n=0, mean=None, std=None, median=None, iqr=None, min=None, max=None)
    ordered = sorted(values)
    q1, q3 = (statistics.quantiles(ordered, n=4, method="inclusive")[i] for i in (0, 2)) if len(values) > 1 else (ordered[0],) * 2
    return dict(n=len(values), mean=statistics.fmean(values), std=statistics.stdev(values) if len(values) > 1 else 0.0,
                median=statistics.median(values), iqr=q3 - q1, min=ordered[0], max=ordered[-1])


def _pvalue(test, *samples):
    from scipy import stats
    try:
        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore")
            p = float(getattr(stats, test)(*samples).pvalue)
        return p if math.isfinite(p) else 1.0
    except ValueError:      # amostras idênticas/sem variação: nenhuma diferença detectável
        return 1.0


def holm(pvalues):
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted, running = [None] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


# ------------------------------------------------------------------ pipeline
def _load_runs(output: Path, ledger_state):
    runs = []
    for key, entry in sorted(ledger_state["runs"].items()):
        if entry["status"] not in TERMINAL or not entry.get("result_file"):
            continue
        data = json.loads((output / entry["result_file"]).read_text(encoding="utf-8"))
        runs.append(dict(key=key, algorithm=entry["algorithm"], instance=entry["instance"], run_id=entry["run_id"],
                         seed=entry["seed"], status=entry["status"], points=[tuple(p) for p in data["points"]],
                         pareto_proven=data.get("pareto_proven", False), wall_s=entry["wall_seconds"],
                         cpu_s=entry["cpu_seconds"], raw_size=data.get("raw_size"), infeasible=data.get("infeasible"),
                         evaluations=data.get("evaluations"), peak_rss_mib=data.get("peak_rss_mib"),
                         peak_rss_delta_mib=data.get("peak_rss_delta_mib"),
                         sha=data.get("instance_sha256")))
    return runs


def _baseline_front(instance_name, sha):
    path = PROJECT_ROOT / "data/baselines" / f"{Path(instance_name).stem}_custom_exact_dp.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("pareto_proven") or data.get("instance_sha256") != sha:
        return None
    return nondominated([(p["makespan"], p["tec_exact"]["numerator"]) for p in data["front"]])


def build_reference(runs_of_instance, instance_name):
    exact = [r for r in runs_of_instance if r["algorithm"] == "exact_dp" and r["pareto_proven"]]
    union = nondominated([p for r in runs_of_instance for p in r["points"]])
    if exact:
        return nondominated(exact[0]["points"]), "exact_dp (campanha, pareto_proven)", union
    baseline = _baseline_front(instance_name, runs_of_instance[0]["sha"]) if runs_of_instance else None
    if baseline:
        return baseline, "data/baselines (custom_exact_dp, pareto_proven)", union
    return union, "união não dominada de todos os métodos e replicações", union


def compute(output: Path, ledger_state, metrics_dir: Path | None = None, alpha=0.05):
    output = Path(output)
    metrics_dir = Path(metrics_dir or output / "metrics")
    metrics_dir.mkdir(parents=True, exist_ok=True)
    runs = _load_runs(output, ledger_state)
    by_instance = {}
    for run in runs:
        by_instance.setdefault(run["instance"], []).append(run)
    per_run, references, audits, coverage_rows = [], {}, [], []
    for instance, items in sorted(by_instance.items()):
        pf_star, source, union = build_reference(items, instance)
        ideal = (min(p[0] for p in pf_star), min(p[1] for p in pf_star)) if pf_star else (0, 0)
        nadir = (max(p[0] for p in pf_star), max(p[1] for p in pf_star)) if pf_star else (1, 1)
        leaks = [p for p in union if not any(r[0] <= p[0] and r[1] <= p[1] for r in pf_star)] if pf_star else []
        references[instance] = dict(source=source, ideal=list(ideal), nadir=list(nadir), size=len(pf_star),
                                    points=[list(p) for p in pf_star], dominance_leaks=[list(p) for p in leaks])
        for run in items:
            row = dict(instance=instance, algorithm=run["algorithm"], run_id=run["run_id"], seed=run["seed"],
                       status=run["status"], evaluations=run["evaluations"], raw_size=run["raw_size"], infeasible=run["infeasible"],
                       wall_s=run["wall_s"], cpu_s=run["cpu_s"], peak_rss_mib=run["peak_rss_mib"],
                       peak_rss_delta_mib=run["peak_rss_delta_mib"])
            row.update(run_indicators(run["points"], pf_star, ideal, nadir) if pf_star else {})
            per_run.append(row)
        # C-metric pareada por replicação; métodos determinísticos entram com sua única fronteira.
        algorithms = sorted({r["algorithm"] for r in items})
        fronts = {a: {r["run_id"]: r["points"] for r in items if r["algorithm"] == a} for a in algorithms}
        for a, b in ((a, b) for a in algorithms for b in algorithms if a != b):
            ids = sorted(set(fronts[a]) | set(fronts[b]))
            values = []
            for k in ids:
                fa = fronts[a].get(k) or (fronts[a].get(1) if len(fronts[a]) == 1 else None)
                fb = fronts[b].get(k) or (fronts[b].get(1) if len(fronts[b]) == 1 else None)
                if fa is not None and fb is not None:
                    values.append(coverage(fa, fb))
            union_a = nondominated([p for f in fronts[a].values() for p in f])
            union_b = nondominated([p for f in fronts[b].values() for p in f])
            stats_ = describe(values)
            coverage_rows.append(dict(instance=instance, A=a, B=b, pairs=stats_["n"], C_mean=stats_["mean"],
                                      C_median=stats_["median"], C_union=coverage(union_a, union_b)))
        for algorithm in algorithms:
            union_alg = nondominated([p for r in items if r["algorithm"] == algorithm for p in r["points"]])
            audits.append(dict(instance=instance, algorithm=algorithm,
                               R_PF_union=sum(p in set(pf_star) for p in union_alg) / len(pf_star) if pf_star else None,
                               union_size=len(union_alg),
                               infeasible_total=sum(r["infeasible"] or 0 for r in items if r["algorithm"] == algorithm),
                               raw_total=sum(r["raw_size"] or 0 for r in items if r["algorithm"] == algorithm)))
    # ---------------- agregação
    summary = []
    for instance in sorted(by_instance):
        for algorithm in sorted({r["algorithm"] for r in per_run if r["instance"] == instance}):
            rows = [r for r in per_run if r["instance"] == instance and r["algorithm"] == algorithm]
            for metric in METRICS:
                d = describe([r.get(metric) for r in rows])
                best, worst = ((d["max"], d["min"]) if metric in HIGHER_IS_BETTER else (d["min"], d["max"]))
                summary.append(dict(instance=instance, algorithm=algorithm, metric=metric, n=d["n"], mean=d["mean"],
                                    std=d["std"], median=d["median"], iqr=d["iqr"], best=best, worst=worst))
    tests = statistical_tests(per_run, alpha)
    # ---------------- exportação
    _write_csv(metrics_dir / "per_run_metrics.csv", per_run)
    _write_csv(metrics_dir / "summary.csv", summary)
    _write_csv(metrics_dir / "coverage.csv", coverage_rows)
    _write_csv(metrics_dir / "pf_contribution.csv", audits)
    _write_csv(metrics_dir / "statistical_tests.csv", tests)
    atomic_json(metrics_dir / "reference_fronts.json", references)
    (metrics_dir / "summary.md").write_text(_markdown(summary, tests, references, alpha), encoding="utf-8")
    (metrics_dir / "summary.tex").write_text(_latex(summary), encoding="utf-8")
    atomic_json(metrics_dir / "metrics_manifest.json", dict(
        hv_reference=[HV_REFERENCE] * 2, normalization="(f - ideal(PF*)) / (nadir(PF*) - ideal(PF*)); eixo constante → divisor 1",
        indicators=dict(GD="p=1, euclidiana", IGD="p=1, euclidiana", IGD_plus="Ishibuchi 2015", EPS_add="I_eps+(A, PF*)",
                        Spacing="Schott, L1", Spread="Deb 2002 Δ", C="Zitzler, dominância fraca"),
        statistics=dict(alpha=alpha, pairwise="Wilcoxon rank-sum (scipy.stats.ranksums) + signed-rank pareado por seed; Holm",
                        omnibus="Friedman por instância, blocos = seeds comuns (MHs)"),
        runs=len(per_run), instances=len(by_instance)))
    return dict(per_run=per_run, summary=summary, tests=tests, references=references, coverage=coverage_rows)


def statistical_tests(per_run, alpha=0.05):
    rows = []
    instances = sorted({r["instance"] for r in per_run})
    for instance in instances:
        mh = sorted({r["algorithm"] for r in per_run if r["instance"] == instance and r["seed"] is not None})
        for metric in ("HV", "IGD", "IGD_plus", "GD", "EPS_add", "Spacing", "NDS", "wall_s"):
            samples = {a: {r["seed"]: r.get(metric) for r in per_run
                           if r["instance"] == instance and r["algorithm"] == a and r.get(metric) is not None}
                       for a in mh}
            pairs = [(a, b) for a, b in combinations(mh, 2) if len(samples[a]) >= 2 and len(samples[b]) >= 2]
            raw = [_pvalue("ranksums", list(samples[a].values()), list(samples[b].values())) for a, b in pairs]
            for (a, b), p, p_holm in zip(pairs, raw, holm(raw) if raw else []):
                common = sorted(set(samples[a]) & set(samples[b]))
                p_signed = (_pvalue("wilcoxon", [samples[a][s] for s in common], [samples[b][s] for s in common])
                            if len(common) >= 2 else None)
                ma, mb = statistics.median(samples[a].values()), statistics.median(samples[b].values())
                better = (a if (ma > mb) == (metric in HIGHER_IS_BETTER) else b) if ma != mb else "="
                rows.append(dict(instance=instance, metric=metric, test="wilcoxon_rank_sum", A=a, B=b,
                                 n_A=len(samples[a]), n_B=len(samples[b]), p_value=p, p_holm=p_holm,
                                 p_signed_rank_paired=p_signed, median_A=ma, median_B=mb, better=better,
                                 significant=p_holm < alpha))
            common = set.intersection(*(set(s) for s in samples.values())) if samples else set()
            if len(mh) >= 3 and len(common) >= 2:
                blocks = [[samples[a][s] for s in sorted(common)] for a in mh]
                p = _pvalue("friedmanchisquare", *blocks)
                rows.append(dict(instance=instance, metric=metric, test="friedman", A="+".join(mh), B="",
                                 n_A=len(common), n_B=len(common), p_value=p, p_holm=p, p_signed_rank_paired=None,
                                 median_A=None, median_B=None, better="", significant=p < alpha))
    return rows


def _write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row)) or ["empty"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _f(value, digits=4):
    if value is None:
        return "—"
    return f"{value:.{digits}g}" if isinstance(value, float) else str(value)


def _markdown(summary, tests, references, alpha):
    lines = ["# Resumo da campanha", "", "## Fronteiras de referência (PF*)", "",
             "| Instância | Fonte | |PF*| | Ideal | Nadir | Vazamentos |", "|---|---|---|---|---|---|"]
    for name, ref in references.items():
        lines.append(f"| {name} | {ref['source']} | {ref['size']} | {ref['ideal']} | {ref['nadir']} | {len(ref['dominance_leaks'])} |")
    lines += ["", "## Indicadores (média ± desvio; mediana [IQR])", ""]
    for metric in METRICS:
        rows = [r for r in summary if r["metric"] == metric and r["n"]]
        if not rows:
            continue
        lines += [f"### {metric}", "", "| Instância | Algoritmo | n | Média | Desvio | Mediana | IQR | Melhor | Pior |",
                  "|---|---|---|---|---|---|---|---|---|"]
        lines += [f"| {r['instance']} | {r['algorithm']} | {r['n']} | {_f(r['mean'])} | {_f(r['std'])} | "
                  f"{_f(r['median'])} | {_f(r['iqr'])} | {_f(r['best'])} | {_f(r['worst'])} |" for r in rows]
        lines.append("")
    lines += [f"## Testes estatísticos (α = {alpha})", "",
              "| Instância | Métrica | Teste | A | B | p | p (Holm) | p pareado | Melhor | Sig. |", "|---|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {t['instance']} | {t['metric']} | {t['test']} | {t['A']} | {t['B']} | {_f(t['p_value'])} | {_f(t['p_holm'])} | "
              f"{_f(t['p_signed_rank_paired'])} | {t['better']} | {'sim' if t['significant'] else 'não'} |" for t in tests]
    return "\n".join(lines) + "\n"


def _latex(summary):
    lines = ["% Gerado por src/experiments/metrics.py", "\\begin{tabular}{llrrrrr}", "\\hline",
             "Instância & Algoritmo & HV média & HV desvio & IGD$^+$ média & Tempo (s) & RAM pico (MiB) \\\\", "\\hline"]
    index = {(r["instance"], r["algorithm"], r["metric"]): r for r in summary}
    for instance, algorithm in sorted({(r["instance"], r["algorithm"]) for r in summary}):
        hv, igdp, wall, ram = (index.get((instance, algorithm, m), {}) for m in ("HV", "IGD_plus", "wall_s", "peak_rss_mib"))
        esc = lambda s: s.replace("_", "\\_")
        lines.append(f"{esc(instance)} & {esc(algorithm)} & {_f(hv.get('mean'))} & {_f(hv.get('std'))} & "
                     f"{_f(igdp.get('mean'))} & {_f(wall.get('mean'))} & {_f(ram.get('max'))} \\\\")
    lines += ["\\hline", "\\end{tabular}"]
    return "\n".join(lines) + "\n"
