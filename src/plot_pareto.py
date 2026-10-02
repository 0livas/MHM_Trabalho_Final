"""Plota os JSONs existentes, sem executar nenhum solver.

Exemplo: python src/plot_pareto.py
Aceita arquivos ou pastas; gera um PNG por instância e distingue resultados parciais.
"""

import argparse
from fractions import Fraction
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METHOD_NAMES = {"cp_sat_epsilon_constraint": "CP-SAT", "epsilon_milp": "MILP epsilon-restrição",
                "custom_exact_dp": "DP própria epsilon-restrição",
                "epsilon_exact_dp": "DP própria epsilon-restrição",
                "custom_exact_propagation": "Backtracking",
                "backtracking_cpu_overlap_only": "Backtracking histórico"}


def point_values(point, scale=1):
    if "tec_exact" in point:
        energy = point["tec_exact"]
        return point["makespan"], Fraction(energy["numerator"], energy["denominator"])
    if "tec_numerator" in point:
        return point["makespan"], Fraction(point["tec_numerator"], point["tec_denominator"])
    if "point" in point:
        c, e = point["point"]
        return c, Fraction(e, scale)
    return point["makespan"], Fraction(str(point["tec"]))


def nondominated(points):
    front, best = [], None
    for c, e in sorted(set(points)):
        if best is None or e < best:
            front.append((c, e))
            best = e
    return front


def load_reports(paths):
    """Prefere a execução completa; caso contrário, a parcial mais recente.

    Mantém métodos diferentes separados. Não mistura hashes diferentes mesmo
    quando as instâncias têm o mesmo nome. Checkpoints não são relatórios.
    """
    files = set()
    for path in map(Path, paths):
        files.update(path.rglob("*.json") if path.is_dir() else [path])
    reports = {}
    for path in sorted(files):
        if path.name.endswith(".checkpoint.json"):
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            raw = report.get("front", report.get("proven_points", []))
            if not isinstance(raw, list):
                continue
            scale = report.get("cost_scale", 1)
            points = nondominated([point_values(p, scale) for p in raw])
            candidate = report.get("candidate")
            candidate = point_values(candidate, scale) if candidate else None
            if not points and candidate is None:
                continue
            name = Path(report["instance"].replace("\\", "/")).stem
            digest = report.get("instance_sha256", "sem-hash")
            method = report.get("method", path.stem)
            complete = report.get("pareto_proven", False) and report.get("status") == "complete"
            item = dict(name=name, digest=digest, method=method, complete=complete,
                        points=points, candidate=candidate, path=path,
                        modified=path.stat().st_mtime)
            key = name, digest, method
            previous = reports.get(key)
            rank = lambda r: (r["complete"], r["modified"])
            if previous is None or rank(item) > rank(previous):
                reports[key] = item
        except (OSError, ValueError, TypeError, KeyError) as error:
            print(f"Ignorado {path}: {error}")
    return list(reports.values())


def plot_reports(paths, output_dir, show=False):
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    reports = load_reports(paths)
    groups = {}
    for report in reports:
        groups.setdefault((report["name"], report["digest"]), []).append(report)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for (name, digest), group in sorted(groups.items()):
        fig, ax = plt.subplots(figsize=(9, 5.5), layout="constrained")
        for number, report in enumerate(sorted(group, key=lambda r: r["method"])):
            method = METHOD_NAMES.get(report["method"], report["method"])
            qualifier = ("completa" if report["complete"] else
                         "provisória" if "backtracking" in report["method"] or "custom_exact" in report["method"]
                         else "parcial; pontos provados")
            color = f"C{number % 10}"
            points = report["points"]
            if points:
                ax.plot([p[0] for p in points], [float(p[1]) for p in points],
                        marker=("o", "s", "^", "D")[number % 4],
                        markerfacecolor="none", markersize=5, linewidth=1,
                        linestyle="-" if report["complete"] else "--", color=color,
                        label=f"{method} — {qualifier} ({len(points)} pontos)")
            if report["candidate"]:
                c, e = report["candidate"]
                ax.scatter([c], [float(e)], marker="x", s=70, color=color,
                           label=f"{method} — candidato sem prova de otimalidade")
            print(f"{name}: {method}, {len(points)} pontos, fonte={report['path']}")
        ax.set(title=f"Fronteiras de Pareto — {name}", xlabel="Makespan (intervalos de tempo)",
               ylabel="Custo total de energia (TEC)")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
        filename = f"{name}_{digest[:8]}.png"
        output = output_dir / filename
        fig.savefig(output, dpi=180)
        outputs.append(output)
        if not show:
            plt.close(fig)
    if show and groups:
        plt.show()
    if not groups:
        print("Nenhum relatório com pontos encontrado. Execute um solver ou informe os JSONs de resultados.")
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/output/plots")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    paths = args.paths or [ROOT / "data/baselines", ROOT / "data/output"]
    for output in plot_reports(paths, args.output_dir, args.show):
        print(f"Gráfico: {output}")


if __name__ == "__main__":
    main()
