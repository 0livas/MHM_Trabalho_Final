"""Fronteira de Pareto da heurística construtiva x método exato (formato da Fig. 9A).

Executa a heurística na instância e desenha a frente em azul sobre a
fronteira exata da DP em vermelho (``data/baselines/<entrada>_custom_exact_dp.json``),
com makespan no eixo x e TEC no eixo y, como a Fig. 9A do artigo base. Se não
houver fronteira exata para a entrada, desenha só a frente da heurística.

Run from the repository root::

    python src/heuristics/construtiva/grafico.py
    python src/heuristics/construtiva/grafico.py data/input/set2/50_10_1439_5_S_1-9.dat
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

from construtiva import executar  # noqa: E402
from problem import read_instance  # noqa: E402

INSTANCE = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"
OUTPUT = ROOT / "data/output/heuristica_construtiva"
HEURISTIC_COLOR, EXACT_COLOR = "#2a78d6", "#d03b3b"  # azul e vermelho, como no artigo


def fronteira_exata(instance_path: Path) -> list[tuple[int, float]]:
    """Fronteira exata da DP, ordenada por makespan (vazia se não houver)."""
    path = ROOT / "data/baselines" / f"{instance_path.stem}_custom_exact_dp.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted((p["makespan"], p["tec"]) for p in data["front"])


def desenhar(heuristica: list[tuple[int, float]], exata: list[tuple[int, float]], titulo: str,
             output: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4.5), layout="constrained")
    if exata:
        ax.plot(*zip(*exata), color=EXACT_COLOR, marker="o", markersize=4, linewidth=1,
                label=f"Exato (DP) — {len(exata)} pontos")
    ax.plot(*zip(*heuristica), color=HEURISTIC_COLOR, marker="o", markersize=7,
            markerfacecolor="none", linewidth=1,
            label=f"Heurística construtiva — {len(heuristica)} pontos")
    ax.set(xlabel="makespan", ylabel="TEC", title=titulo)
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
    parser.add_argument("--pesos", type=int, default=11, help="quantidade de pesos alfa (padrão 11)")
    parser.add_argument("--output", type=Path, help="PNG de saída")
    args = parser.parse_args()

    resultado = executar(read_instance(args.instance), args.pesos)
    pontos = [(s.objetivos[0], s.objetivos[1] / resultado.escala) for s in resultado.frente]
    exata = fronteira_exata(args.instance)
    output = args.output or OUTPUT / f"pareto_{args.instance.stem}.png"
    desenhar(pontos, exata, f"Fronteira de Pareto — {args.instance.stem}", output)

    chaves_exatas = {(c, round(t, 6)) for c, t in exata}
    comuns = sum((c, round(t, 6)) in chaves_exatas for c, t in pontos)
    print(f"Heurística: {len(pontos)} pontos em {resultado.segundos:.2f}s; exato: {len(exata)} pontos; "
          f"em comum: {comuns}; figura: {output}")


if __name__ == "__main__":
    main()
