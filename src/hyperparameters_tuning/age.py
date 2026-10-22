"""Calibração age: somente parâmetros já aceitos pela implementação original."""
from metaheuristics.age import AGEConfig, run_age
from hyperparameters_tuning.common import (
    validate_native_space, resolve_native_parameters, suggest_native_parameters,
    calculate_bounds, normalized_hv, study_lock,
    calibrate as _calibrate, evaluate_parameters as _evaluate_parameters,
)

ALGORITHM_ID = "age"
SUPPORTED_BUDGET_MODES = ("evaluations", "effort")
GENERATION_DEFINITION = 'Inicialização P; depois lotes/varreduras P, com última etapa parcial se necessário.'
FIXED_CHOICES = {'survival': 'AGE-MOEA nativo pymoo 0.6.2', 'sampling': 'LPT aleatório', 'scaling': 'Cmax e TEC brutos; normalização nativa AGE', 'constraints': 'filtragem nativa', 'eliminate_duplicates': False, 'crossover': 'ScheduleCrossover original; método fixo', 'mutation': 'ScheduleMutation original; método fixo', 'seeds': 'replicações; não calibradas', 'implementation_policy': 'somente campos Config atuais; fontes preservadas'}
SEARCH_SPACE = {
    "population_size": [20, 50, 100, 150, 200, 300],
    "max_evaluations": [2000, 4000, 8000, 12000, 20000],
    "crossover_probability": [0.2, 0.4, 0.6, 0.7, 0.9, 1.0],
    "mutation_probability": [0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7],
}


def validate_space(space, budget, budget_mode):
    return validate_native_space(space, SEARCH_SPACE, AGEConfig, budget, budget_mode)


def resolve_parameters(parameters, budget, budget_mode):
    return resolve_native_parameters(parameters, budget, budget_mode, AGEConfig)


def suggest_parameters(trial, budget, budget_mode="evaluations", search_space=None):
    space = validate_space(SEARCH_SPACE if search_space is None else search_space, budget, budget_mode)
    return suggest_native_parameters(trial, budget, budget_mode, space, AGEConfig)


def run_single(instance, parameters, seed):
    return run_age(instance, AGEConfig(seed=seed, **parameters))


def generation_metrics(parameters, attempts):
    # Métrica derivada do consumo; gerações não são passadas ao solver.
    population = parameters["population_size"]
    return dict(target_generations=None, full_generations=attempts // population,
                offspring_in_partial_generation=attempts % population)


def calibrate(paths, **kwargs):
    return _calibrate(paths, algorithm=ALGORITHM_ID, **kwargs)


def evaluate_parameters(parameters, cases, seeds, budget, **kwargs):
    return _evaluate_parameters(parameters, cases, seeds, budget, algorithm=ALGORITHM_ID, **kwargs)
