"""Fronteira de Pareto do NSGA-II x método exato, no formato da Fig. 9A do artigo.

A Fig. 9A de Rego et al. (2022) compara uma execução do NSGA-II (azul) com a
fronteira do método exato (vermelho) na instância de 6 jobs e 2 máquinas, com
makespan no eixo x e TEC no eixo y. Este script refaz o mesmo gráfico: executa
o NSGA-II na instância e sobrepõe a fronteira exata da DP do repositório
(``data/baselines/<instância>_custom_exact_dp.json``).

Run from the repository root::

    python src/heuristics/nsga2/plots.py
    python src/heuristics/nsga2/plots.py --seed 7 --max-evaluations 20000
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from nsga2 import NSGA2Config, run_nsga2  # noqa: E402
from problem import read_instance  # noqa: E402

INSTANCE = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"
OUTPUT = ROOT / "data/output/nsga2"
NSGA2_COLOR, EXACT_COLOR = "#2a78d6", "#d03b3b"  # azul e vermelho, como no artigo


def exact_front(instance_path: Path) -> list[tuple[int, float]]:
    """Fronteira exata da DP, ordenada por makespan (vazia se não houver)."""
    path = ROOT / "data/baselines" / f"{instance_path.stem}_custom_exact_dp.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted((p["makespan"], p["tec"]) for p in data["front"])


def plot(nsga2: list[tuple[int, float]], exact: list[tuple[int, float]], title: str,
         output: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4.5), layout="constrained")
    if exact:
        ax.plot(*zip(*exact), color=EXACT_COLOR, marker="o", markersize=4, linewidth=1,
                label=f"Exato (DP) — {len(exact)} pontos")
    ax.plot(*zip(*nsga2), color=NSGA2_COLOR, marker="o", markersize=7, markerfacecolor="none",
            linewidth=1, label=f"NSGA-II — {len(nsga2)} pontos")
    ax.set(xlabel="makespan", ylabel="TEC", title=title)
    ax.grid(color="#e4e3df", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("instance", nargs="?", type=Path, default=INSTANCE)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-evaluations", type=int, default=10_000)
    parser.add_argument("--population-size", type=int, default=100)
    parser.add_argument("--output", type=Path, help="PNG de saída")
    args = parser.parse_args()

    instance = read_instance(args.instance)
    result = run_nsga2(instance, NSGA2Config(seed=args.seed, max_evaluations=args.max_evaluations,
                                             population_size=args.population_size))
    nsga2 = sorted((s.evaluation.cmax, s.evaluation.tec) for s in result.front)
    exact = exact_front(args.instance)
    output = args.output or OUTPUT / f"pareto_{args.instance.stem}.png"
    plot(nsga2, exact, f"Fronteira de Pareto — {args.instance.stem}", output)

    exact_keys = {(c, round(t, 6)) for c, t in exact}
    common = sum((c, round(t, 6)) in exact_keys for c, t in nsga2)
    print(f"NSGA-II: {len(nsga2)} pontos em {result.elapsed_seconds:.1f}s; "
          f"exato: {len(exact)} pontos; em comum: {common}; figura: {output}")


if __name__ == "__main__":
    main()
