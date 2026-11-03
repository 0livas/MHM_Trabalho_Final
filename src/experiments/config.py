"""Registro de instâncias, algoritmos e carregamento dos hiperparâmetros calibrados."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from problem import PROJECT_ROOT

TUNING_DIR = PROJECT_ROOT / "data/output/hyperparameters_tuning"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/output/experiments"
DEFAULT_RUNS = 30
DEFAULT_BASE_SEED = 1000   # distinto das seeds de calibração (11, 29, 47) e confirmação (101..105)

TIERS = {
    "small": ("set1/6_2_1439_3_S_1-9.dat", "set1/10_2_1439_3_S_1-9.dat",
              "set1/14_2_1439_3_S_1-9_derivada.dat"),
    "medium": ("set2/50_10_1439_5_S_1-9.dat", "set2/50_20_1439_5_S_1-124.dat"),
    "large": ("set2/250_10_1439_5_S_1-9.dat", "set2/250_20_1439_5_S_1-124.dat"),
    "giant": ("set2/750_10_1439_5_S_1-9.dat", "set2/750_20_1439_5_S_1-124.dat"),
}


@dataclass(frozen=True)
class InstanceSpec:
    tier: str
    relative: str

    @property
    def path(self) -> Path:
        return PROJECT_ROOT / "data/input" / self.relative

    @property
    def name(self) -> str:
        return Path(self.relative).name


INSTANCES = tuple(InstanceSpec(tier, rel) for tier, rels in TIERS.items() for rel in rels)


@dataclass(frozen=True)
class AlgorithmSpec:
    id: str
    label: str
    kind: str            # exact | heuristic | metaheuristic
    deterministic: bool
    default_selected: bool
    tuned: bool          # exige hiperparâmetros calibrados


ALGORITHMS = (
    AlgorithmSpec("exact_dp", "Exato — DP própria (custom_exact_dp)", "exact", True, True, False),
    AlgorithmSpec("ociosidade", "Heurística — inserção ótima de ociosidade", "heuristic", True, True, False),
    AlgorithmSpec("spea2", "MH1 — SPEA2", "metaheuristic", False, True, True),
    AlgorithmSpec("moead", "MH2 — MOEA/D", "metaheuristic", False, True, True),
    AlgorithmSpec("vns_vnd", "MH3 — VNS/VND", "metaheuristic", False, False, True),
    AlgorithmSpec("age", "MH4 — AGE-MOEA", "metaheuristic", False, True, True),
)
ALGORITHM_BY_ID = {spec.id: spec for spec in ALGORITHMS}


def vns_calibrated(tuning_dir: Path = TUNING_DIR) -> bool:
    return any((tuning_dir / "vns_vnd").glob("*/best_parameters.json"))


def default_algorithms() -> list[str]:
    """Seleção padrão; VNS/VND entra quando sua calibração existe."""
    return [s.id for s in ALGORITHMS if s.default_selected or (s.id == "vns_vnd" and vns_calibrated())]

# Fallback do VNS/VND enquanto não há calibração: defaults do VNSConfig com o mesmo
# orçamento de avaliações recomendado aos demais métodos.
VNS_FALLBACK = dict(max_evaluations=50_000, initial_solutions=4,
                    max_candidates_per_neighborhood=100, shaking_attempts=20)


def select_instances(tiers=None, names=None) -> list[InstanceSpec]:
    tiers = set(tiers or ["all"])
    if "all" in tiers:
        tiers = set(TIERS)
    unknown = tiers - set(TIERS)
    if unknown:
        raise ValueError(f"Faixas desconhecidas: {', '.join(sorted(unknown))}")
    selected = [spec for spec in INSTANCES if spec.tier in tiers]
    if names:
        wanted = {Path(n).name for n in names}
        missing = wanted - {spec.name for spec in INSTANCES}
        if missing:
            raise ValueError(f"Instâncias fora do registro: {', '.join(sorted(missing))}")
        selected = [spec for spec in selected if spec.name in wanted]
    return selected


def _study_version(name: str) -> int:
    match = re.search(r"_v(\d+)", name)
    return int(match.group(1)) if match else 0


def load_hyperparameters(algorithm: str, tuning_dir: Path = TUNING_DIR) -> dict | None:
    """Configuração final do estudo mais recente do algoritmo.

    Prioridade: ``confirmation.json['recommended']`` (confirmação em estágios,
    maior orçamento) e, na falta dela, ``best_parameters.json['solver_config']``.
    Retorna ``None`` quando não existe calibração.
    """
    root = Path(tuning_dir) / algorithm
    if not root.is_dir():
        return None
    studies = sorted((d for d in root.iterdir() if d.is_dir() and (d / "best_parameters.json").exists()),
                     key=lambda d: (_study_version(d.name), d.name))
    for study in reversed(studies):
        confirmation = study / "confirmation.json"
        if confirmation.exists():
            data = json.loads(confirmation.read_text(encoding="utf-8"))
            recommended = data.get("recommended") or {}
            if recommended.get("solver_config"):
                return dict(parameters=dict(recommended["solver_config"]), study=study.name,
                            source=str(confirmation.relative_to(PROJECT_ROOT)), selection="confirmation.recommended",
                            trial=recommended.get("trial"), budget=recommended.get("budget"),
                            status=data.get("status"))
        best = json.loads((study / "best_parameters.json").read_text(encoding="utf-8"))
        if best.get("solver_config"):
            return dict(parameters=dict(best["solver_config"]), study=study.name,
                        source=str((study / "best_parameters.json").relative_to(PROJECT_ROOT)),
                        selection="best_parameters.solver_config", trial=best.get("best_trial"),
                        budget=best["solver_config"].get("max_evaluations"), status=best.get("status"))
    return None


def resolve_configuration(algorithm: str, *, exact_options: dict, budget: int | None = None,
                          tuning_dir: Path = TUNING_DIR) -> dict:
    """Configuração auditável que será gravada no manifesto e usada em todas as execuções.

    ``budget`` substitui ``max_evaluations`` das meta-heurísticas (orçamento comum);
    o valor calibrado original fica registrado em ``tuned_max_evaluations``.
    """
    config = _resolve(algorithm, exact_options, tuning_dir)
    if budget and ALGORITHM_BY_ID[algorithm].kind == "metaheuristic":
        config["tuned_max_evaluations"] = config["parameters"]["max_evaluations"]
        config["parameters"]["max_evaluations"] = budget
        config["budget_override"] = budget
    return config


def _resolve(algorithm, exact_options, tuning_dir):
    spec = ALGORITHM_BY_ID[algorithm]
    if spec.kind == "exact":
        return dict(parameters=dict(exact_options), source="CLI (salvaguardas de tempo/memória)",
                    selection="exact_options", status="deterministic")
    if spec.kind == "heuristic":
        return dict(parameters=dict(bases="construtiva", modos="livres"), source="ociosidade.executar defaults",
                    selection="defaults", status="deterministic")
    loaded = load_hyperparameters(algorithm, tuning_dir)
    if loaded is None:
        if algorithm != "vns_vnd":
            raise FileNotFoundError(f"Sem calibração para {algorithm} em {tuning_dir}")
        return dict(parameters=dict(VNS_FALLBACK), source="VNS_FALLBACK (VNSConfig defaults + 50000 avaliações)",
                    selection="fallback_pending_calibration", status="hyperparameters_pending")
    return loaded
