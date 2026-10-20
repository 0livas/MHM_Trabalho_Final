"""Menu e CLI de calibração. Execute sem argumentos para abrir o menu."""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

GPU_MESSAGE = (
    "GPU indisponível: os algoritmos e o avaliador atuais executam na CPU. "
    "Optuna/Ray não convertem esses operadores para CUDA. "
    "Escolha CPU sequencial ou CPU paralela."
)
ALGORITHMS = {"moead": "MOEA/D", "spea2": "SPEA2 incremental", "age": "AGE-MOEA", "vns_vnd": "VNS/VND"}
DEFAULT_INPUTS = (
    "data/input/set1/6_2_1439_3_S_1-9.dat",
    "data/input/set1/7_2_1439_3_S_1-9.dat",
    "data/input/set1/8_2_1439_3_S_1-9.dat",
    "data/input/set1/9_2_1439_3_S_1-9.dat",
    "data/input/set1/10_2_1439_3_S_1-9.dat",
    "data/input/set1/10_2_1439_3_S_1-9_derivada.dat",
    "data/input/set1/11_2_1439_3_S_1-9_derivada.dat",
    "data/input/set1/12_2_1439_3_S_1-9_derivada.dat",
    "data/input/set1/13_2_1439_3_S_1-9_derivada.dat",
    "data/input/set1/14_2_1439_3_S_1-9_derivada.dat",
    "data/input/set2/50_10_1439_5_S_1-9.dat",
    "data/input/set2/250_10_1439_5_S_1-9.dat",
)


def positive_int(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("Informe um inteiro positivo")
    return result


def resolve_inputs(values):
    """Caminhos relativos são resolvidos a partir da raiz do projeto."""
    paths = []
    for value in values:
        path = Path(value)
        path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
        entries = sorted(path.glob("*.dat")) if path.is_dir() else [path]
        if not entries:
            raise ValueError(f"Pasta sem arquivos .dat: {path}")
        for entry in entries:
            if not entry.is_file() or entry.suffix.lower() != ".dat":
                raise ValueError(f"Entrada .dat não encontrada: {entry}")
            if entry not in paths:
                paths.append(entry)
    return paths


def prompt(label, default, convert=str):
    while True:
        value = input(f"{label} [{default}]: ").strip()
        try:
            return convert(value or str(default))
        except (ValueError, argparse.ArgumentTypeError) as error:
            print(f"Valor inválido: {error}")


def get_plugin(algorithm):
    from hyperparameters_tuning.common import algorithm_module
    return algorithm_module(algorithm)


def load_space(path=None, algorithm="moead"):
    SEARCH_SPACE = get_plugin(algorithm).SEARCH_SPACE
    if path is None:
        return {name: list(values) for name, values in SEARCH_SPACE.items()}
    path = Path(path)
    path = ROOT / path if not path.is_absolute() else path
    return json.loads(path.read_text(encoding="utf-8"))


def show_space(space, algorithm="moead", budget_mode=None):
    plugin = get_plugin(algorithm)
    budget_mode = budget_mode or plugin.SUPPORTED_BUDGET_MODES[0]
    print("\nValores disponíveis para calibração:")
    for name, values in space.items():
        inactive = budget_mode == "evaluations" and name == "max_evaluations"
        print(f"  {name}: {values}" + (" (não calibrado no modo de avaliações fixas)" if inactive else ""))
    print(plugin.GENERATION_DEFINITION)
    print("Calibração limitada aos parâmetros nativos; operadores mantêm os métodos originais.")
    print("Sementes são replicações; escolhas fixas registradas no protocolo.")


def menu():
    print("\nCalibração de hiperparâmetros — Optuna/TPE")
    for index, label in enumerate(ALGORITHMS.values(), 1):
        print(f"{index} - {label}")
    print("0 - Sair")
    while True:
        choice = input("Meta-heurística: ").strip()
        if choice == "0":
            return None
        if choice in tuple(str(i) for i in range(1, 5)):
            algorithm = tuple(ALGORITHMS)[int(choice)-1]
            break
        print("Escolha 1 a 4, ou 0 para sair.")
    while True:
        print("\n1 - CPU sequencial\n2 - CPU paralela (processos)")
        print("3 - GPU (indisponível nesta implementação)")
        choice = input("Execução: ").strip()
        if choice == "3":
            print(GPU_MESSAGE)
        elif choice in ("1", "2"):
            break
        else:
            print("Escolha 1, 2 ou 3.")
    workers = 1 if choice == "1" else prompt(
        "Processos simultâneos", min(4, max(1, (os.cpu_count() or 1) - 1)), positive_int)
    print("\nEntradas padrão de calibração:")
    for entry in DEFAULT_INPUTS:
        print(f"  {entry}")
    text = input("Outros arquivos/pastas separados por ; (Enter mantém padrão): ").strip()
    inputs = [entry.strip().strip('"') for entry in text.split(";") if entry.strip()] if text else DEFAULT_INPUTS
    seeds = prompt("Seeds separadas por vírgula", "11,29,47")
    trials = prompt("Total desejado de configurações (trials)", 30, positive_int)
    while True:
        mode = prompt("Esforço: 1=calibrar limite de avaliações; 2=avaliações fixas", "1")
        if mode in ("1", "2"):
            break
        print("Escolha 1 ou 2.")
    budget_mode = get_plugin(algorithm).SUPPORTED_BUDGET_MODES[0] if mode == "1" else "evaluations"
    budget = prompt("Cap de avaliações por instância e seed", 8000, positive_int) if mode == "2" else 8000
    space_path = input("Arquivo JSON de grade personalizada (Enter usa padrões): ").strip().strip('"')
    show_space(load_space(space_path or None, algorithm), algorithm, budget_mode)
    if budget_mode != "evaluations":
        print("O esforço varia entre configurações. Confirme depois com orçamento comum.")
    study_name = prompt("Nome do estudo", f"{algorithm}_tpe_v4")
    resume = prompt("Retomar estudo existente? s/n", "n").lower()
    if resume not in ("s", "n"):
        raise ValueError("Retomada deve ser s ou n")
    return argparse.Namespace(algorithm=algorithm, inputs=inputs, seeds=seeds,
        trials=trials, max_evaluations=budget, workers=workers, study_name=study_name,
        sampler_seed=42, resume=resume == "s", device="cpu", output_dir=None,
        budget_mode=budget_mode, search_space=Path(space_path) if space_path else None, list_space=False)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--algorithm", choices=ALGORITHMS, default="moead")
    result.add_argument("--inputs", nargs="+", default=DEFAULT_INPUTS,
                        help="arquivos/pastas de calibração; caminhos relativos à raiz")
    result.add_argument("--seeds", default="11,29,47", help="seeds do algoritmo separadas por vírgula")
    result.add_argument("--trials", type=positive_int, default=30,
                        help="total desejado, incluindo trials anteriores em --resume")
    result.add_argument("--budget-mode", choices=["effort", "evaluations"],
                        help="padrão: effort calibra o limite nativo; evaluations fixa esforço")
    result.add_argument("--max-evaluations", type=positive_int, default=8000,
                        help="cap por busca em evaluations; não se aplica a effort")
    result.add_argument("--search-space", type=Path, help="JSON com listas de valores; padrão tem >=5 níveis numéricos")
    result.add_argument("--list-space", action="store_true", help="mostrar grade e sair")
    result.add_argument("--workers", type=positive_int, default=1,
                        help="configurações simultâneas em processos CPU separados")
    result.add_argument("--study-name", help="padrão <algoritmo>_tpe_v4")
    result.add_argument("--sampler-seed", type=int, default=42)
    result.add_argument("--resume", action="store_true")
    result.add_argument("--device", choices=["cpu", "gpu"], default="cpu")
    result.add_argument("--output-dir", type=Path,
                        help="pasta exata do estudo; padrão data/output/hyperparameters_tuning/<algoritmo>/<nome>")
    return result


def main(argv=None):
    cli = parser()
    argv = sys.argv[1:] if argv is None else argv
    try:
        args = cli.parse_args(argv) if argv else menu()
        if args is None:
            return 0
        if args.device == "gpu":
            raise ValueError(GPU_MESSAGE)
        plugin = get_plugin(args.algorithm)
        args.budget_mode = args.budget_mode or plugin.SUPPORTED_BUDGET_MODES[0]
        if args.budget_mode not in plugin.SUPPORTED_BUDGET_MODES:
            raise ValueError(f"{args.algorithm} admite apenas {plugin.SUPPORTED_BUDGET_MODES}")
        args.study_name = args.study_name or f"{args.algorithm}_tpe_v4"
        space = load_space(args.search_space, args.algorithm)
        if args.list_space:
            show_space(space, args.algorithm, args.budget_mode)
            return 0
        seeds = tuple(int(value.strip()) for value in args.seeds.split(","))
        if not seeds or any(seed < 0 for seed in seeds) or len(set(seeds)) != len(seeds):
            raise ValueError("Seeds devem ser inteiros não negativos distintos")
        paths = resolve_inputs(args.inputs)
        if args.output_dir is not None and not args.output_dir.is_absolute():
            args.output_dir = ROOT / args.output_dir
        report = plugin.calibrate(paths, seeds=seeds, n_trials=args.trials,
            budget=args.max_evaluations, workers=args.workers, study_name=args.study_name,
            sampler_seed=args.sampler_seed, resume=args.resume, output_dir=args.output_dir,
            budget_mode=args.budget_mode, search_space=space)
        print(f"\nConcluído: {report['completed_trials']} trials completos; "
              f"melhor score={report['best_score']}. Saída: {report['output_dir']}")
        return 0
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        cli.exit(2, f"Erro: {error}\n")
    except (KeyboardInterrupt, EOFError):
        print("\nInterrompido. O histórico foi preservado; use --resume para continuar.")
        return 130


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
