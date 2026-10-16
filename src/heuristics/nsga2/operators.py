"""Amostragem, crossover e mutação do pymoo para o cromossomo de quatro vetores."""

from __future__ import annotations

import numpy as np
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.core.sampling import Sampling

from decoder import join, split
from problem import Instance


def greedy_individual(instance: Instance, rng: np.random.Generator, objective: str) -> np.ndarray:
    """Algoritmo 3 do artigo, anexando cada tarefa ao fim de uma máquina.

    Tarefas são escolhidas em ordem aleatória e vão para a máquina de menor
    término projetado. ``objective="cmax"`` usa sempre o modo mais rápido; o
    ``"tec"`` usa o modo de menor fator de potência. Nenhuma avaliação é gasta.
    """
    if objective == "cmax":
        mode = max(range(instance.modes), key=lambda o: instance.speed[o])
    elif objective == "tec":
        mode = min(range(instance.modes), key=lambda o: instance.power_factor[o])
    else:
        raise ValueError(f"Objetivo desconhecido: {objective}")
    order = rng.permutation(instance.n)
    free_time = [0] * instance.m
    last_job: list[int | None] = [None] * instance.m
    machines = []
    for job in order.tolist():
        def end_on(machine: int) -> int:
            previous = last_job[machine]
            setup = instance.setup[machine][previous][job] if previous is not None else 0
            return free_time[machine] + setup + instance.duration(job, machine, mode)
        machine = min(range(instance.m), key=end_on)
        free_time[machine] = end_on(machine)
        last_job[machine] = job
        machines.append(machine)
    n = instance.n
    return join(order, machines, [mode] * n, [0] * n)


def random_individual(instance: Instance, rng: np.random.Generator) -> np.ndarray:
    n = instance.n
    return join(rng.permutation(n), rng.integers(instance.m, size=n),
                rng.integers(instance.modes, size=n), rng.integers(2, size=n))


class ChromosomeSampling(Sampling):
    """Dois indivíduos gulosos (Cmax e TEC) e o restante aleatório."""

    def _do(self, problem, n_samples, random_state=None, **kwargs):
        rng = random_state if random_state is not None else np.random.default_rng()
        instance = problem.instance
        samples = []
        for objective in ("cmax", "tec")[:n_samples]:
            samples.append(greedy_individual(instance, rng, objective))
        while len(samples) < n_samples:
            samples.append(random_individual(instance, rng))
        return np.array(samples, dtype=int)


def pmx(parent1: np.ndarray, parent2: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Partially Mapped Crossover: o segmento [a, b] vem de parent1."""
    n = len(parent1)
    a, b = sorted(rng.choice(n, size=2, replace=False)) if n > 1 else (0, 0)
    child = np.full(n, -1, dtype=int)
    child[a:b + 1] = parent1[a:b + 1]
    position_in_p2 = {int(value): index for index, value in enumerate(parent2)}
    segment = set(child[a:b + 1].tolist())
    for index in range(a, b + 1):
        value = int(parent2[index])
        if value in segment:
            continue
        # Segue o mapeamento p1[i] <-> p2[i] até cair fora do segmento.
        target = index
        while a <= target <= b:
            target = position_in_p2[int(parent1[target])]
        child[target] = value
    empty = child < 0
    child[empty] = parent2[empty]
    return child


class MixedCrossover(Crossover):
    """PMX na sequência e crossover uniforme em máquina, modo e avoid."""

    def __init__(self, prob: float = 0.9):
        super().__init__(n_parents=2, n_offsprings=2, prob=prob)

    def _do(self, problem, x, random_state=None, **kwargs):
        rng = random_state if random_state is not None else np.random.default_rng()
        instance = problem.instance
        _, n_matings, _ = x.shape
        offspring = np.empty((2, n_matings, x.shape[2]), dtype=int)
        for mating in range(n_matings):
            seq1, *genes1 = split(instance, x[0, mating])
            seq2, *genes2 = split(instance, x[1, mating])
            mask = rng.random(instance.n) < 0.5
            child1 = [np.where(mask, g1, g2) for g1, g2 in zip(genes1, genes2)]
            child2 = [np.where(mask, g2, g1) for g1, g2 in zip(genes1, genes2)]
            offspring[0, mating] = join(pmx(seq1, seq2, rng), *child1)
            offspring[1, mating] = join(pmx(seq2, seq1, rng), *child2)
        return offspring


class MixedMutation(Mutation):
    """Swap na sequência; reset aleatório em máquina/modo; bit-flip no avoid.

    Com o indivíduo selecionado para mutação (probabilidade ``prob`` do pymoo),
    sempre ocorre um swap, e cada gene de máquina, modo e avoid muda com
    probabilidade 1/N.
    """

    def _do(self, problem, x, random_state=None, **kwargs):
        rng = random_state if random_state is not None else np.random.default_rng()
        instance = problem.instance
        n = instance.n
        result = np.array(x, dtype=int, copy=True)
        rate = 1.0 / n
        for row in result:
            seq, machine, mode, avoid = split(instance, row)
            seq, machine, mode, avoid = seq.copy(), machine.copy(), mode.copy(), avoid.copy()
            if n > 1:
                i, j = rng.choice(n, size=2, replace=False)
                seq[i], seq[j] = seq[j], seq[i]
            reset = rng.random(n) < rate
            machine[reset] = rng.integers(instance.m, size=int(reset.sum()))
            reset = rng.random(n) < rate
            mode[reset] = rng.integers(instance.modes, size=int(reset.sum()))
            flip = rng.random(n) < rate
            avoid[flip] = 1 - avoid[flip]
            row[:] = join(seq, machine, mode, avoid)
        return result
