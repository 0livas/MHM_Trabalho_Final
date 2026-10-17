"""Fronteira de Pareto da inserção ótima de ociosidade (formato da Fig. 9A do artigo).

Desenha, com makespan no eixo x e TEC no eixo y:

- a fronteira exata da DP em vermelho, se ``data/baselines/<entrada>_custom_exact_dp.json`` existir;
- a fronteira da heurística construtiva (as sequências de partida) em cinza;
- a fronteira após a inserção ótima de ociosidade em azul.

Run from the repository root::

    python src/heuristics/ociosidade/grafico.py
    python src/heuristics/ociosidade/grafico.py data/input/set2/250_10_1439_5_S_1-9.dat --modos-fixos
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

from ociosidade import base_de_schedule, executar  # noqa: E402
from problem import read_instance  # noqa: E402

import construtiva  # noqa: E402  (caminho incluído por ociosidade.py)

INSTANCE = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"
OUTPUT = ROOT / "data/output/heuristica_ociosidade"
IDLE_COLOR, BASE_COLOR, EXACT_COLOR = "#2a78d6", "#8a8984", "#d03b3b"


def fronteira_exata(instance_path: Path) -> list[tuple[int, float]]:
    """Fronteira exata da DP, ordenada por makespan (vazia se não houver)."""
    path = ROOT / "data/baselines" / f"{instance_path.stem}_custom_exact_dp.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted((p["makespan"], p["tec"]) for p in data["front"])


def desenhar(series: list[tuple[str, list[tuple[int, float]], dict]], titulo: str, output: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 4.8), layout="constrained")
    for label, pontos, style in series:
        if pontos:
            ax.plot(*zip(*pontos), label=f"{label} — {len(pontos)} pontos", linewidth=1, **style)
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
    parser.add_argument("--modos-fixos", action="store_true",
                        help="mantém os modos da solução de partida e otimiza só as esperas")
    parser.add_argument("--output", type=Path, help="PNG de saída")
    args = parser.parse_args()

    instance = read_instance(args.instance)
    base = construtiva.executar(instance)
    bases = [(base_de_schedule(s.schedule()), f"construtiva ({s.origem})") for s in base.frente]
    resultado = executar(instance, bases, args.modos_fixos)

    exata = fronteira_exata(args.instance)
    construida = [(s.objetivos[0], s.objetivos[1] / base.escala) for s in base.frente]
    ociosa = [(p.objetivos[0], p.objetivos[1] / resultado.escala) for p in resultado.frente]
    rotulo = "Inserção de ociosidade" + (" (modos fixos)" if args.modos_fixos else "")
    output = args.output or OUTPUT / f"pareto_{args.instance.stem}.png"
    desenhar([
        ("Exato (DP)", exata, dict(color=EXACT_COLOR, marker="o", markersize=4)),
        ("Construtiva (partida)", construida,
         dict(color=BASE_COLOR, marker="s", markersize=5, markerfacecolor="none", linestyle="--")),
        (rotulo, ociosa, dict(color=IDLE_COLOR, marker="o", markersize=6, markerfacecolor="none")),
    ], f"Fronteira de Pareto — {args.instance.stem}", output)

    chaves_exatas = {(c, round(t, 6)) for c, t in exata}
    comuns = sum((c, round(t, 6)) in chaves_exatas for c, t in ociosa)
    com_espera = sum(any(wait > 0 for seq in p.schedule for _, _, wait in seq) for p in resultado.frente)
    print(f"Construtiva: {len(construida)} pontos; ociosidade: {len(ociosa)} pontos "
          f"({com_espera} com espera) em {resultado.segundos:.2f}s; exato: {len(exata)} pontos; "
          f"em comum com o exato: {comuns}; figura: {output}")


if __name__ == "__main__":
    main()
