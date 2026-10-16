"""Cromossomo de quatro vetores e decodificador para o NSGA-II do UPMSP-SDS.

O indivíduo é um único vetor inteiro de tamanho 4N, concatenando::

    [ seq (N) | machine (N) | mode (N) | avoid (N) ]

- ``seq``: permutação de 0..N-1 com a ordem de inserção das tarefas;
- ``machine[k]``: máquina (0..M-1) da tarefa inserida na posição k;
- ``mode[k]``: modo de operação (0..O-1) da tarefa da posição k;
- ``avoid[k]``: 0/1; se 1 e o início cair na ponta, espera a ponta terminar.

Os genes de máquina/modo/espera são alinhados à **posição** k, não ao número
da tarefa, como na especificação original. Todos os índices começam em 0; a
especificação em 1..N/1..M/1..O equivale a subtrair 1 de cada valor.

Diferenças deliberadas em relação ao enunciado, para manter o modelo de
``problem.py`` (e assim comparar com os métodos exatos e baselines):

- não há setup inicial: a matriz de setup das entradas é M x N x N e a
  primeira tarefa de cada máquina começa sem preparação;
- há um horário de ponta por dia (``instance.peaks``), como intervalos
  semiabertos ``[início, fim + 1)``;
- o TEC é calculado em inteiros exatos (``energy_scale``) e convertido para
  fração só na saída.

Execute este arquivo diretamente para um teste com dados fictícios::

    python src/heuristics/nsga2/decoder.py
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from problem import Instance, energy_scale, interval_cost_units  # noqa: E402
from schedule import Schedule  # noqa: E402


def split(instance: Instance, x) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Separa o vetor 4N em (seq, machine, mode, avoid)."""
    n = instance.n
    x = np.asarray(x, dtype=int)
    if x.shape != (4 * n,):
        raise ValueError(f"Cromossomo deve ter tamanho {4 * n}, recebeu {x.shape}")
    return x[:n], x[n:2 * n], x[2 * n:3 * n], x[3 * n:]


def join(seq, machine, mode, avoid) -> np.ndarray:
    """Concatena os quatro vetores no layout usado pelo pymoo."""
    return np.concatenate([np.asarray(part, dtype=int) for part in (seq, machine, mode, avoid)])


def upper_bounds(instance: Instance) -> np.ndarray:
    """Limite superior inclusivo de cada gene (limite inferior é sempre 0)."""
    n = instance.n
    return join([n - 1] * n, [instance.m - 1] * n, [instance.modes - 1] * n, [1] * n)


@dataclass(frozen=True, slots=True)
class Decoded:
    cmax: int
    tec_units: int
    tec_scale: int
    overflow: int
    schedule: Schedule

    @property
    def feasible(self) -> bool:
        return self.overflow == 0

    @property
    def tec(self) -> Fraction:
        return Fraction(self.tec_units, self.tec_scale)


class Decoder:
    """Pré-calcula preços inteiros por (máquina, modo) e decodifica indivíduos."""

    def __init__(self, instance: Instance):
        self.instance = instance
        self.scale, prices = energy_scale(instance)
        self.prices = {(machine, mode): (on, off) for machine, mode, on, off in prices}

    def peak_end_if_inside(self, time: int) -> int | None:
        """Fim (exclusivo) da ponta que contém ``time``, ou None fora da ponta."""
        for start, end in self.instance.peaks:
            if start <= time < end:
                return end
        return None

    def decode(self, x) -> Decoded:
        instance = self.instance
        seq, machines, modes, avoids = split(instance, x)
        if sorted(seq.tolist()) != list(range(instance.n)):
            raise ValueError("Sequência não é uma permutação das tarefas")

        free_time = [0] * instance.m            # Machine_Free_Time
        last_job: list[int | None] = [None] * instance.m  # Last_Job_On_Machine
        sequences: list[list[tuple[int, int, int]]] = [[] for _ in range(instance.m)]
        tec_units = 0

        for k in range(instance.n):
            job, machine, mode, avoid = (int(seq[k]), int(machines[k]),
                                         int(modes[k]), int(avoids[k]))
            duration = instance.duration(job, machine, mode)  # ceil(p / v)
            previous = last_job[machine]
            setup = instance.setup[machine][previous][job] if previous is not None else 0
            base_start = free_time[machine] + setup

            # Regra de ociosidade: com avoid=1, um início dentro da ponta é
            # adiado para o primeiro instante fora dela. Um início fora da ponta
            # não é alterado, mesmo que o processamento avance sobre a ponta.
            start = base_start
            if avoid:
                peak_end = self.peak_end_if_inside(base_start)
                if peak_end is not None:
                    start = peak_end
            end = start + duration

            # Custo de energia da tarefa (integral da potência no tempo).
            #
            # A potência da tarefa é constante: pi[maq] * lambda[modo] kW. A
            # tarifa é constante por trechos: rate_in_peak dentro da ponta e
            # rate_off_peak fora. Com o tempo discretizado em sizeD slots por dia,
            # cada slot dura 24/sizeD horas; logo, o preço de um slot é
            #     pi * lambda * rate * 24 / sizeD.
            # ``energy_scale`` calcula esses dois preços (ponta, fora de ponta)
            # para cada (máquina, modo) e os multiplica por um denominador comum
            # (``scale``), de modo que todos virem inteiros exatos.
            #
            # Assim, a integral se reduz a contar slots: com o processamento em
            # [start, end), os slots de ponta são a soma, sobre os dias, de
            #     max(0, min(end, b) - max(start, a))   para cada ponta [a, b),
            # e os demais (end - start - ponta) são fora de ponta. Os seis casos
            # do artigo (Fig. 1 e Tabela 3: antes da ponta, entra na ponta,
            # dentro dela, sai da ponta, depois dela, atravessa a ponta inteira)
            # são exatamente os valores possíveis dessa interseção.
            # ``interval_cost_units`` devolve on * slots_ponta + off * slots_fora.
            #
            # Setup e espera não consomem energia, então só [start, end) entra.
            on_price, off_price = self.prices[machine, mode]
            tec_units += interval_cost_units(instance, start, end, on_price, off_price)

            sequences[machine].append((job, mode, start - base_start))
            free_time[machine] = end
            last_job[machine] = job

        cmax = max(free_time)
        overflow = max(0, cmax - instance.horizon)
        schedule = tuple(tuple(sequence) for sequence in sequences)
        return Decoded(cmax, tec_units, self.scale, overflow, schedule)


def decode(instance: Instance, x) -> Decoded:
    return Decoder(instance).decode(x)


def decode_objectives(instance: Instance, x) -> tuple[int, Fraction]:
    """Tupla (Makespan, TEC) do indivíduo, com TEC exato em fração."""
    decoded = decode(instance, x)
    return decoded.cmax, decoded.tec


def _mock_instance() -> Instance:
    """Uma máquina, 4 tarefas, um dia de 24 slots (1 h cada) e ponta [18, 21).

    Os parâmetros seguem o exemplo das Fig. 1/2 do artigo: pi=100, lambda=1,
    tarifas 0,10 (ponta) e 0,05 (fora). Preço por slot = 100*1*rate*24/24, ou
    seja, 10 na ponta e 5 fora dela.
    """
    one = Fraction(1)
    return Instance(
        path=Path("mock.dat"), digest="mock", n=4, m=1, days=1, slots_per_day=24,
        modes=2, peak_rate=Fraction("0.10"), off_rate=Fraction("0.05"),
        max_cost=Fraction(1000), peaks=((18, 21),),
        speed=(one, Fraction(2)), power_factor=(one, Fraction(3, 2)), power=(Fraction(100),),
        # [job][máquina]
        processing=((11,), (2,), (3,), (2,)),
        # [máquina][anterior][próxima]
        setup=(((0, 2, 2, 2), (1, 0, 1, 1), (1, 1, 0, 1), (1, 1, 1, 0)),),
    )


if __name__ == "__main__":
    from dataclasses import replace

    from schedule import evaluate_schedule

    instance = _mock_instance()
    decoder = Decoder(instance)

    def show(label: str, x) -> Decoded:
        result = decoder.decode(x)
        print(f"\n{label}: Cmax={result.cmax}, TEC={float(result.tec):g}, "
              f"viável={result.feasible}")
        for job, mode, wait in result.schedule[0]:
            print(f"  job {job}  modo {mode}  espera {wait}")
        reference = evaluate_schedule(instance, result.schedule)
        assert (reference.cmax, reference.tec_exact) == (result.cmax, result.tec)
        return result

    # Ordem 0,1,2,3, todos no modo 0 (velocidade 1, lambda 1), sem evitar ponta.
    # job0 [0,11)  -> 11 fora                = 55
    # job1 [13,15) -> setup 2, 2 fora         = 10
    # job2 [16,19) -> setup 1, 2 fora + 1 on  = 10 + 10 = 20
    # job3 [20,22) -> setup 1, 1 on + 1 fora  = 10 + 5  = 15
    plain = show("Sem evitar ponta", join([0, 1, 2, 3], [0] * 4, [0] * 4, [0] * 4))
    assert (plain.cmax, plain.tec) == (22, 100)

    # Igual, mas job3 com avoid=1: início base 20 está na ponta [18,21) e
    # é adiado para 21; job3 [21,23) -> 2 fora = 10.
    avoided = show("job3 evitando ponta", join([0, 1, 2, 3], [0] * 4, [0] * 4, [0, 0, 0, 1]))
    assert (avoided.cmax, avoided.tec) == (23, 95)
    assert avoided.schedule[0][3] == (3, 0, 1)

    # avoid=1 em job2 não muda nada: o início 16 está fora da ponta, embora o
    # processamento invada a ponta (a regra olha só o instante de início).
    same = show("job2 com avoid (início fora da ponta)",
                join([0, 1, 2, 3], [0] * 4, [0] * 4, [0, 0, 1, 0]))
    assert (same.cmax, same.tec) == (plain.cmax, plain.tec)

    # job0 no modo 1: ceil(11/2)=6 slots, potência 1,5x -> preço 7,5 fora.
    # job0 [0,6) = 45; job1 [8,10) = 10; job2 [11,14) = 15; job3 [15,17) = 10.
    fast = show("job0 rápido", join([0, 1, 2, 3], [0] * 4, [1, 0, 0, 0], [0] * 4))
    assert (fast.cmax, fast.tec) == (17, 80)

    # Com horizonte de 20 slots, a ordem simples (Cmax=22) fica inviável: o
    # decodificador não rejeita, mas informa overflow=2 para a restrição G.
    short = replace(instance, slots_per_day=20, peaks=((15, 18),))
    late = Decoder(short).decode(join([0, 1, 2, 3], [0] * 4, [0] * 4, [0] * 4))
    print(f"\nHorizonte 20: Cmax={late.cmax}, overflow={late.overflow}")
    assert (late.cmax, late.overflow, late.feasible) == (22, 2, False)

    print("\nTodos os asserts do decodificador passaram.")
