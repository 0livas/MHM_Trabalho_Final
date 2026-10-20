"""Controles nativos do VNS/VND: soluções iniciais, vizinhança e shaking.

VNS não tem população evolutiva, gerações, crossover ou mutação. O regime
``effort`` calibra o limite de avaliações; ``evaluations`` mantém esse limite
fixo entre trials. Ambos preservam o VNS/VND original e o avaliador comum.
"""
from __future__ import annotations

from metaheuristics.vns_vnd import VNSConfig, VNSVND

ALGORITHM_ID = "vns_vnd"
SUPPORTED_BUDGET_MODES = ("effort", "evaluations")
SEARCH_SPACE = {
    "initial_solutions": [1, 2, 4, 8, 16],
    "max_candidates_per_neighborhood": [10, 25, 50, 100, 200],
    "shaking_attempts": [1, 5, 10, 20, 40],
    "max_evaluations": [2000, 4000, 8000, 12000, 20000],
}
GENERATION_DEFINITION = (
    "Não há gerações no VNS/VND. effort calibra o cap de avaliações; "
    "evaluations fixa esse cap. Famílias vazias podem encerrar a busca antes do cap."
)
FIXED_CHOICES = {
    "neighborhoods": "modo, espera, inserção, realocação, troca; nesta ordem",
    "construction": "construtiva aleatória viável; max(20, 50×initial_solutions) tentativas",
    "origin_selection": "sorteio entre pontos Pareto menos explorados",
    "acceptance": "dominância; reinicia N1 após melhoria/expansão",
    "constraint_policy": "validação exata de horizonte, setups e tarefa única; rejeição conta avaliação",
    "archive": "não dominado, sem cap artificial",
    "seeds": "replicações; não calibradas",
}


def validate_space(space, budget, budget_mode):
    """Valida e canoniza propriedades JSON; orçamento fixo filtra inicializações."""
    if budget_mode not in SUPPORTED_BUDGET_MODES:
        raise ValueError("VNS/VND admite budget_mode effort ou evaluations")
    if type(budget) is not int or budget < 1:
        raise ValueError("budget deve ser inteiro positivo")
    if not isinstance(space, dict) or set(space) != set(SEARCH_SPACE):
        raise ValueError(f"A grade VNS/VND deve conter exatamente: {', '.join(SEARCH_SPACE)}")
    result = {}
    for name in SEARCH_SPACE:
        values = space[name]
        if (not isinstance(values, list) or not values
                or any(type(value) is not int or value < 1 for value in values)
                or len(values) != len(set(values))):
            raise ValueError(f"{name} deve conter inteiros positivos distintos")
        result[name] = list(values)
    if budget_mode == "evaluations":
        result["initial_solutions"] = [value for value in result["initial_solutions"] if value <= budget]
        if not result["initial_solutions"]:
            raise ValueError("Nenhuma quantidade de soluções iniciais cabe no orçamento")
    elif max(result["initial_solutions"]) > min(result["max_evaluations"]):
        raise ValueError("Toda quantidade de soluções iniciais deve caber no menor cap da grade")
    return result


def resolve_parameters(parameters, budget, budget_mode):
    """Produz argumentos diretamente reutilizáveis em VNSConfig, sem seed."""
    if budget_mode not in SUPPORTED_BUDGET_MODES:
        raise ValueError("VNS/VND admite budget_mode effort ou evaluations")
    result = dict(parameters)
    if budget_mode == "evaluations":
        result["max_evaluations"] = budget
    elif "max_evaluations" not in result:
        raise ValueError("Modo effort exige max_evaluations na configuração")
    VNSConfig(seed=0, **result)
    return result


def suggest_parameters(trial, budget, budget_mode="effort", search_space=None):
    space = validate_space(SEARCH_SPACE if search_space is None else search_space, budget, budget_mode)
    selected = {name: trial.suggest_categorical(name, values)
                for name, values in space.items()
                if name != "max_evaluations" or budget_mode == "effort"}
    return resolve_parameters(selected, budget, budget_mode)


def run_single(instance, parameters, seed):
    return VNSVND(instance, VNSConfig(seed=seed, **parameters)).run()


def generation_metrics(parameters, attempts):
    """Não apresenta avaliações como se fossem gerações/ciclos de VNS."""
    return dict(target_evaluations=parameters["max_evaluations"],
                target_generations=None, full_generations=None,
                offspring_in_partial_generation=None,
                effort_definition=GENERATION_DEFINITION)


def calibrate(paths, **kwargs):
    from hyperparameters_tuning.common import calibrate as shared_calibrate
    kwargs.setdefault("budget_mode", "effort")
    kwargs.setdefault("study_name", "vns_vnd_tpe_v4")
    return shared_calibrate(paths, algorithm=ALGORITHM_ID, **kwargs)


def evaluate_parameters(parameters, cases, seeds, budget):
    from hyperparameters_tuning.common import evaluate_parameters as shared_evaluate
    return shared_evaluate(parameters, cases, seeds, budget, algorithm=ALGORITHM_ID)
