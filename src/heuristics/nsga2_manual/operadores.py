"""População inicial, cruzamento e mutação do artigo base, implementados à mão.

- População inicial: dois indivíduos gulosos (Algoritmo 3) e o resto aleatório.
- Cruzamento: One Point Order Crossover de Vallada & Ruiz (2011), adaptado a
  máquinas paralelas (Fig. 3).
- Mutação: troca (swap), inserção e troca de modo (Figs. 4 a 6).

Todos os operadores recebem um ``random.Random`` para que a execução seja
reproduzível pela seed.
"""

from __future__ import annotations

import random

from avaliacao import Avaliador, Gene, Individuo, Maquinas

OBJETIVOS = ("cmax", "tec")


def _chave(objetivo: str, end: int, cost: int) -> tuple[int, int]:
    """Critério da melhor posição: um objetivo e o outro como desempate."""
    return (end, cost) if objetivo == "cmax" else (cost, end)


def melhor_posicao(avaliador: Avaliador, machine: int, seq: list[Gene], gene: Gene,
                   objetivo: str) -> tuple[int, int, int]:
    """(posição, término, custo) da melhor inserção do gene nesta máquina."""
    return min(avaliador.insercoes(machine, seq, gene),
               key=lambda option: _chave(objetivo, option[1], option[2]))


# ----- população inicial -----------------------------------------------------
def guloso(avaliador: Avaliador, rng: random.Random, objetivo: str) -> Maquinas:
    """Algoritmo 3: insere tarefas em ordem aleatória na melhor máquina e posição.

    ``cmax`` usa sempre o modo de maior velocidade e escolhe a inserção que
    resulta no menor makespan; ``tec`` usa o modo de menor fator de consumo e
    escolhe a que menos aumenta o custo de energia.
    """
    instance = avaliador.instance
    if objetivo == "cmax":
        mode = max(range(instance.modes), key=lambda o: instance.speed[o])
    else:
        mode = min(range(instance.modes), key=lambda o: instance.power_factor[o])
    maquinas: Maquinas = [[] for _ in range(instance.m)]
    fim, custo = [0] * instance.m, [0] * instance.m
    jobs = list(range(instance.n))
    rng.shuffle(jobs)
    for job in jobs:
        best = None
        for machine, seq in enumerate(maquinas):
            others = max((fim[i] for i in range(instance.m) if i != machine), default=0)
            for position, end, cost in avaliador.insercoes(machine, seq, (job, mode)):
                if objetivo == "cmax":
                    key = (max(end, others), end, cost - custo[machine])
                else:
                    key = (cost - custo[machine], end)
                if best is None or key < best[0]:
                    best = key, machine, position, end, cost
        _, machine, position, end, cost = best
        maquinas[machine].insert(position, (job, mode))
        fim[machine], custo[machine] = end, cost
    return maquinas


def aleatorio(avaliador: Avaliador, rng: random.Random) -> Maquinas:
    """Tarefas em ordem aleatória, cada uma com máquina e modo aleatórios."""
    instance = avaliador.instance
    maquinas: Maquinas = [[] for _ in range(instance.m)]
    jobs = list(range(instance.n))
    rng.shuffle(jobs)
    for job in jobs:
        maquinas[rng.randrange(instance.m)].append((job, rng.randrange(instance.modes)))
    return maquinas


def populacao_inicial(avaliador: Avaliador, rng: random.Random, tamanho: int) -> list[Individuo]:
    solucoes = [guloso(avaliador, rng, objetivo) for objetivo in OBJETIVOS[:tamanho]]
    while len(solucoes) < tamanho:
        solucoes.append(aleatorio(avaliador, rng))
    return [avaliador.avaliar(maquinas) for maquinas in solucoes]


# ----- cruzamento ------------------------------------------------------------
def cruzamento(avaliador: Avaliador, rng: random.Random, pai1: Individuo,
               pai2: Individuo) -> tuple[Maquinas, Maquinas]:
    """One Point Order Crossover adaptado (Fig. 3 do artigo).

    1. sorteia um ponto de corte em cada máquina do pai 1;
    2. o filho 1 recebe os genes à esquerda do corte; o filho 2, os da direita;
    3. marca no pai 2 os genes que cada filho já tem;
    4. insere os genes não marcados do pai 2, na ordem em que aparecem nele, na
       mesma máquina que ocupam no pai 2 e na posição que dá o menor valor de
       um objetivo sorteado para este cruzamento (o outro desempata).

    Os genes carregam o modo de operação, então o modo vem do pai que cedeu a
    tarefa.
    """
    objetivo = rng.choice(OBJETIVOS)
    cortes = [rng.randint(0, len(seq)) for seq in pai1.maquinas]
    filhos = ([seq[:cut] for seq, cut in zip(pai1.maquinas, cortes)],
              [seq[cut:] for seq, cut in zip(pai1.maquinas, cortes)])
    for filho in filhos:
        presentes = {job for seq in filho for job, _ in seq}
        for machine, seq in enumerate(pai2.maquinas):
            for gene in seq:
                if gene[0] not in presentes:
                    position, _, _ = melhor_posicao(avaliador, machine, filho[machine], gene, objetivo)
                    filho[machine].insert(position, gene)
    return filhos


# ----- mutação ---------------------------------------------------------------
def _posicoes(maquinas: Maquinas) -> list[tuple[int, int]]:
    return [(machine, position) for machine, seq in enumerate(maquinas) for position in range(len(seq))]


def troca(maquinas: Maquinas, rng: random.Random, instance) -> None:
    """Swap (Fig. 4): duas tarefas trocam de lugar, possivelmente entre máquinas."""
    positions = _posicoes(maquinas)
    if len(positions) < 2:
        return
    (i1, a), (i2, b) = rng.sample(positions, 2)
    maquinas[i1][a], maquinas[i2][b] = maquinas[i2][b], maquinas[i1][a]


def insercao(maquinas: Maquinas, rng: random.Random, instance) -> None:
    """Inserção (Fig. 5): uma tarefa sai da máquina i1 e entra em posição aleatória de i2 != i1."""
    i1, a = rng.choice(_posicoes(maquinas))
    others = [machine for machine in range(len(maquinas)) if machine != i1] or [i1]
    i2 = rng.choice(others)
    gene = maquinas[i1].pop(a)
    maquinas[i2].insert(rng.randint(0, len(maquinas[i2])), gene)


def troca_de_modo(maquinas: Maquinas, rng: random.Random, instance) -> None:
    """Troca de modo (Fig. 6): uma tarefa aleatória recebe outro modo aleatório."""
    if instance.modes < 2:
        return
    machine, position = rng.choice(_posicoes(maquinas))
    job, mode = maquinas[machine][position]
    maquinas[machine][position] = (job, rng.choice([o for o in range(instance.modes) if o != mode]))


MUTACOES = (troca, insercao, troca_de_modo)


def mutacao(maquinas: Maquinas, rng: random.Random, instance) -> None:
    """Aplica um dos três operadores, sorteado com igual probabilidade."""
    rng.choice(MUTACOES)(maquinas, rng, instance)
