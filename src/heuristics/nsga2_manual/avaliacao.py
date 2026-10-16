"""Representação direta e avaliação, sem bibliotecas externas.

Um indivíduo é uma lista por máquina de genes ``(tarefa, modo)``, na ordem de
processamento, como na Fig. 3 do artigo base (Rego et al., 2022). Não há
espera: cada tarefa começa assim que a anterior termina e o setup é feito.
No formato comum do repositório (``schedule.Schedule``), isso equivale a
triplas ``(tarefa, modo, 0)``.

Regras do modelo (iguais às de ``problem.py`` e ``schedule.evaluate_schedule``):

- não há setup antes da primeira tarefa de cada máquina;
- duração = ceil(p / velocidade do modo);
- o TEC é calculado em inteiros exatos (``energy_scale``): o custo de uma
  tarefa em ``[início, fim)`` é ``on * slots_na_ponta + off * slots_fora``;
- uma solução que termina após o horizonte é inviável (``excesso > 0``).

Como Cmax e TEC são decompostos por máquina (máximo e soma dos valores de
cada máquina), o indivíduo guarda o término e o custo de cada máquina. Assim,
inserir uma tarefa só exige recalcular a máquina que mudou.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from problem import Instance, energy_scale  # noqa: E402

Gene = tuple[int, int]            # (tarefa, modo)
Maquinas = list[list[Gene]]       # uma sequência de genes por máquina


@dataclass(slots=True)
class Individuo:
    """Solução avaliada; os objetivos são calculados uma vez, na criação."""
    maquinas: Maquinas
    fim: list[int]       # término de cada máquina
    custo: list[int]     # custo escalado de cada máquina
    horizonte: int
    objetivos: tuple[int, int] = field(init=False)   # (Cmax, TEC escalado)
    excesso: int = field(init=False)                 # quanto passa do horizonte (0 = viável)

    def __post_init__(self):
        self.objetivos = (max(self.fim), sum(self.custo))
        self.excesso = max(0, self.objetivos[0] - self.horizonte)

    @property
    def cmax(self) -> int:
        return self.objetivos[0]

    @property
    def tec_units(self) -> int:
        return self.objetivos[1]

    def schedule(self) -> tuple[tuple[tuple[int, int, int], ...], ...]:
        """Formato comum do repositório: (tarefa, modo, espera=0) por máquina."""
        return tuple(tuple((job, mode, 0) for job, mode in seq) for seq in self.maquinas)


class Avaliador:
    """Pré-calcula durações e preços inteiros e conta as avaliações completas."""

    def __init__(self, instance: Instance):
        self.instance = instance
        self.scale, prices = energy_scale(instance)
        self.precos = [[(0, 0)] * instance.modes for _ in range(instance.m)]
        for machine, mode, on, off in prices:
            self.precos[machine][mode] = (on, off)
        self.duracao = [[[instance.duration(job, machine, mode) for mode in range(instance.modes)]
                         for machine in range(instance.m)] for job in range(instance.n)]
        self.setup = instance.setup
        # acumulado[t] = slots de ponta em [0, t); as pontas ficam dentro do
        # horizonte, então depois dele o acumulado é constante.
        self.horizonte = instance.horizon
        self.acumulado = [0] * (instance.horizon + 1)
        for t in range(instance.horizon):
            dentro = any(a <= t < b for a, b in instance.peaks)
            self.acumulado[t + 1] = self.acumulado[t] + dentro
        self.avaliacoes = 0

    # ----- custo de energia -------------------------------------------------
    def custo(self, machine: int, mode: int, start: int, end: int) -> int:
        """Integral da potência x tarifa em [start, end), em unidades inteiras."""
        on, off = self.precos[machine][mode]
        ponta = self.slots_de_ponta(start, end)
        return on * ponta + off * (end - start - ponta)

    def slots_de_ponta(self, start: int, end: int) -> int:
        """Slots de [start, end) dentro da ponta, em O(1) pelo acumulado."""
        h = self.horizonte
        return self.acumulado[min(end, h)] - self.acumulado[min(start, h)]

    # ----- uma máquina ------------------------------------------------------
    def linha_do_tempo(self, machine: int, seq: list[Gene]) -> tuple[list[int], list[int], list[int]]:
        """Inícios, términos e custos das tarefas de uma máquina, sem espera."""
        starts, ends, costs = [], [], []
        t, previous = 0, None
        for job, mode in seq:
            start = t + (self.setup[machine][previous][job] if previous is not None else 0)
            end = start + self.duracao[job][machine][mode]
            starts.append(start)
            ends.append(end)
            costs.append(self.custo(machine, mode, start, end))
            t, previous = end, job
        return starts, ends, costs

    def maquina(self, machine: int, seq: list[Gene]) -> tuple[int, int]:
        """(término, custo) de uma máquina."""
        _, ends, costs = self.linha_do_tempo(machine, seq)
        return (ends[-1] if ends else 0), sum(costs)

    def insercoes(self, machine: int, seq: list[Gene], gene: Gene) -> list[tuple[int, int, int]]:
        """(posição, novo término, novo custo) da máquina para cada posição de inserção.

        Sem espera, inserir o gene na posição p desloca todo o sufixo pelo mesmo
        delta. O término passa a ser ``fim_antigo + delta``; o custo do sufixo só
        muda se ele encostar em uma ponta antes ou depois do deslocamento, e só
        nesse caso é recalculado. Fora disso, cada posição custa O(1).
        """
        job, mode = gene
        starts, ends, costs = self.linha_do_tempo(machine, seq)
        prefix = [0]
        for cost in costs:
            prefix.append(prefix[-1] + cost)
        total, size = prefix[-1], len(seq)
        duration = self.duracao[job][machine][mode]
        result = []
        for p in range(size + 1):
            if p == 0:
                start = 0
            else:
                start = ends[p - 1] + self.setup[machine][seq[p - 1][0]][job]
            end = start + duration
            cost = prefix[p] + self.custo(machine, mode, start, end)
            if p == size:
                result.append((p, end, cost))
                continue
            delta = end + self.setup[machine][job][seq[p][0]] - starts[p]
            last = ends[-1]
            if delta == 0 or not (self.slots_de_ponta(starts[p], last)
                                  or self.slots_de_ponta(starts[p] + delta, last + delta)):
                suffix = total - prefix[p]
            else:
                suffix = sum(self.custo(machine, seq[k][1], starts[k] + delta, ends[k] + delta)
                             for k in range(p, size))
            result.append((p, last + delta, cost + suffix))
        return result

    # ----- solução completa -------------------------------------------------
    def avaliar(self, maquinas: Maquinas) -> Individuo:
        """Avalia uma solução completa; cada chamada conta uma avaliação."""
        self.avaliacoes += 1
        fim, custo = [], []
        for machine, seq in enumerate(maquinas):
            end, cost = self.maquina(machine, seq)
            fim.append(end)
            custo.append(cost)
        return Individuo(maquinas, fim, custo, self.instance.horizon)

    def tec(self, individuo: Individuo) -> Fraction:
        return Fraction(individuo.tec_units, self.scale)
