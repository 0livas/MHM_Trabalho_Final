"""Cria uma grade finita ampliada ao redor dos melhores trials de um estudo."""
from pathlib import Path
import json
import optuna
from hyperparameters_tuning.common import algorithm_module, study_lock
from hyperparameters_tuning.confirm import select_top
from problem import atomic_json


def refined_space(space, configurations, budget_mode):
    """Preserva a grade e inclui pontos médios nos intervalos vizinhos aos líderes."""
    result = {name: list(values) for name, values in space.items()}
    for name, values in space.items():
        if name == "max_evaluations" and budget_mode == "evaluations":
            continue
        ordered = sorted(values)
        additions = set()
        for config in configurations:
            value = config[name]
            index = ordered.index(value)
            for neighbor in (index-1, index+1):
                if 0 <= neighbor < len(ordered):
                    midpoint = (value + ordered[neighbor]) / 2
                    if all(type(v) is int for v in values):
                        midpoint = round(midpoint)
                    additions.add(midpoint)
        result[name] = sorted(set(values) | additions)
    return result


def refine(output_dir, destination, *, top=5):
    output, destination = Path(output_dir).resolve(), Path(destination).resolve()
    if type(top) is not int or top < 1:
        raise ValueError("top deve ser inteiro positivo")
    if destination.exists():
        raise ValueError("Arquivo de grade já existe; escolha outro destino")
    with study_lock(output / "study.lock"):
        protocol = json.loads((output / "protocol.json").read_text(encoding="utf-8"))
        database = output / "study.sqlite3"
        if not database.is_file():
            raise ValueError("Banco do estudo ausente")
        storage = optuna.storages.RDBStorage(url="sqlite:///" + database.as_posix())
        try:
            study = optuna.load_study(study_name=protocol["study_name"], storage=storage)
            configurations = select_top(study, top)
            by_number = {trial.number: trial for trial in study.trials}
        finally:
            storage.engine.dispose()
        if not configurations:
            raise ValueError("Estudo sem configurações concluídas")
        # select_top remove o cap; em effort ele é necessário para refinar a grade.
        selected = [dict(config["parameters"]) for config in configurations]
        if protocol["budget_mode"] == "effort":
            selected = [by_number[c["trial"]].user_attrs["effective_parameters"] for c in configurations]
        space = refined_space(protocol["search_space"], selected, protocol["budget_mode"])
        plugin = algorithm_module(protocol["algorithm"])
        budget = protocol.get("budget_per_run") or min(space["max_evaluations"])
        space = plugin.validate_space(space, budget, protocol["budget_mode"])
        atomic_json(destination, space)
    return space
