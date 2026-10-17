"""Heurística construtiva gulosa ponderada + ajuste guloso de modos.

Não é uma meta-heurística: não há população, iterações de busca nem
aleatoriedade. A mesma entrada sempre gera a mesma fronteira.

A fronteira é obtida em três etapas, sobre a modelagem de ``problem.py``
(sem setup inicial, duração ceil(p/v), ponta por dia, TEC exato em inteiros)
e com o formato de solução de ``schedule.py`` (por máquina, triplas
``(tarefa, modo, espera)``, aqui sempre com espera 0):

1. Construção gulosa ponderada (generalização do Algoritmo 3 do artigo):
   para um peso alfa e uma regra de ordenação LPT, cada tarefa é inserida na
   combinação máquina x modo x posição que minimiza

       f = alfa * Cmax / H + (1 - alfa) * TEC / max_cost

   sobre a solução parcial, sem ultrapassar o horizonte H. Como as máquinas
   são não relacionadas, há três regras LPT (soma, mínimo e máximo dos tempos
   de processamento da tarefa nas máquinas).
2. Varredura de pesos: alfa em {0; 0,1; ...; 1}, o conjunto D do Algoritmo 1
   (soma ponderada) do artigo. Cada par (regra, alfa) dá uma solução.
3. Ajuste guloso de modos: a partir de cada solução construída distinta, a
   cada passo troca-se o modo da tarefa com maior economia de TEC por unidade
   de Cmax acrescentada, registrando cada solução intermediária, até nenhuma
   troca reduzir o TEC.

Por fim, só as soluções não dominadas são mantidas e revalidadas por
``schedule.evaluate_schedule``.

Run from the repository root::

    python src/heuristics/construtiva/construtiva.py data/input/set1/6_2_1439_3_S_1-9.dat
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from problem import Instance, atomic_json, energy_scale, insert_pareto, read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402

Gene = tuple[int, int]          # (tarefa, modo)
Maquinas = list[list[Gene]]     # sequência de genes de cada máquina


# ----- avaliação por máquina ------------------------------------------------
class Avaliador:
    """Durações, preços inteiros e custo de energia, com atalhos por máquina.

    Cmax é o maior término entre as máquinas e TEC é a soma dos custos das
    máquinas; por isso cada alteração só exige recalcular a máquina mudada.
    """

    def __init__(self, instance: Instance):
        self.instance = instance
        self.scale, prices = energy_scale(instance)
        self.precos = [[(0, 0)] * instance.modes for _ in range(instance.m)]
        for machine, mode, on, off in prices:
            self.precos[machine][mode] = (on, off)
        self.duracao = [[[instance.duration(job, machine, mode) for mode in range(instance.modes)]
                         for machine in range(instance.m)] for job in range(instance.n)]
        self.setup = instance.setup
        self.horizonte = instance.horizon
        # acumulado[t] = slots de ponta em [0, t); as pontas ficam dentro do
        # horizonte, então depois dele o acumulado é constante.
        self.acumulado = [0] * (instance.horizon + 1)
        for t in range(instance.horizon):
            dentro = any(a <= t < b for a, b in instance.peaks)
            self.acumulado[t + 1] = self.acumulado[t] + dentro

    def ponta(self, start: int, end: int) -> int:
        """Slots de [start, end) dentro da ponta, em O(1)."""
        h = self.horizonte
        return self.acumulado[min(end, h)] - self.acumulado[min(start, h)]

    def custo(self, machine: int, mode: int, start: int, end: int) -> int:
        """Integral da potência x tarifa em [start, end): on*ponta + off*fora."""
        on, off = self.precos[machine][mode]
        ponta = self.ponta(start, end)
        return on * ponta + off * (end - start - ponta)

    def linha_do_tempo(self, machine: int, seq: list[Gene]):
        """Inícios, términos e custo acumulado (prefixos) de uma máquina, sem espera."""
        starts, ends, prefix = [], [], [0]
        t, previous = 0, None
        for job, mode in seq:
            start = t + (self.setup[machine][previous][job] if previous is not None else 0)
            end = start + self.duracao[job][machine][mode]
            starts.append(start)
            ends.append(end)
            prefix.append(prefix[-1] + self.custo(machine, mode, start, end))
            t, previous = end, job
        return starts, ends, prefix

    def maquina(self, machine: int, seq: list[Gene]) -> tuple[int, int]:
        """(término, custo) de uma máquina."""
        _, ends, prefix = self.linha_do_tempo(machine, seq)
        return (ends[-1] if ends else 0), prefix[-1]

    def _sufixo(self, machine, seq, starts, ends, prefix, p, delta) -> int:
        """Custo das tarefas p.. deslocadas por delta.

        Sem espera, o sufixo inteiro anda o mesmo delta. Se ele não encosta em
        nenhuma ponta antes nem depois do deslocamento, o custo não muda.
        """
        if p >= len(seq):
            return 0
        if delta == 0 or not (self.ponta(starts[p], ends[-1])
                              or self.ponta(starts[p] + delta, ends[-1] + delta)):
            return prefix[-1] - prefix[p]
        return sum(self.custo(machine, seq[k][1], starts[k] + delta, ends[k] + delta)
                   for k in range(p, len(seq)))

    def insercoes(self, machine: int, seq: list[Gene], gene: Gene):
        """(posição, novo término, novo custo) da máquina para cada posição de inserção."""
        job, mode = gene
        starts, ends, prefix = self.linha_do_tempo(machine, seq)
        duration = self.duracao[job][machine][mode]
        for p in range(len(seq) + 1):
            start = ends[p - 1] + self.setup[machine][seq[p - 1][0]][job] if p else 0
            end = start + duration
            own = prefix[p] + self.custo(machine, mode, start, end)
            if p == len(seq):
                yield p, end, own
                continue
            delta = end + self.setup[machine][job][seq[p][0]] - starts[p]
            yield p, ends[-1] + delta, own + self._sufixo(machine, seq, starts, ends, prefix, p, delta)

    def trocas_de_modo(self, machine: int, seq: list[Gene]):
        """(posição, novo modo, novo término, novo custo) para cada troca de modo."""
        starts, ends, prefix = self.linha_do_tempo(machine, seq)
        for p, (job, current) in enumerate(seq):
            for mode in range(self.instance.modes):
                if mode == current:
                    continue
                end = starts[p] + self.duracao[job][machine][mode]
                delta = end - ends[p]
                cost = (prefix[p] + self.custo(machine, mode, starts[p], end)
                        + self._sufixo(machine, seq, starts, ends, prefix, p + 1, delta))
                yield p, mode, ends[-1] + delta, cost


@dataclass(slots=True)
class Solucao:
    maquinas: Maquinas
    fim: list[int]       # término de cada máquina
    custo: list[int]     # custo escalado de cada máquina
    origem: str          # como a solução foi obtida (alfa ou passo do ajuste)

    @property
    def objetivos(self) -> tuple[int, int]:
        """(Cmax, TEC escalado), a chave exata usada na dominância."""
        return max(self.fim), sum(self.custo)

    def copia(self, origem: str) -> "Solucao":
        return Solucao([list(seq) for seq in self.maquinas], list(self.fim), list(self.custo), origem)

    def schedule(self):
        """Formato comum do repositório: (tarefa, modo, espera=0) por máquina."""
        return tuple(tuple((job, mode, 0) for job, mode in seq) for seq in self.maquinas)


# ----- etapa 1: construção gulosa ponderada ---------------------------------
# Regras LPT (maior tempo primeiro). Em máquinas não relacionadas o tempo da
# tarefa muda com a máquina, então "maior" pode ser medido de três formas, e
# nenhuma é melhor em todas as instâncias; a heurística usa as três.
ORDENS = {
    "lpt_soma": lambda instance, job: sum(instance.processing[job]),
    "lpt_min": lambda instance, job: min(instance.processing[job]),
    "lpt_max": lambda instance, job: max(instance.processing[job]),
}


def ordenar(instance: Instance, regra: str) -> list[int]:
    """Tarefas em ordem decrescente pelo critério da regra (desempate: índice)."""
    medida = ORDENS[regra]
    return sorted(range(instance.n), key=lambda job: (-medida(instance, job), job))


def construir(avaliador: Avaliador, alfa: float, regra: str = "lpt_soma") -> Solucao | None:
    """Insere cada tarefa, na ordem da regra, na combinação máquina x modo x posição de menor f.

    Devolve None se alguma tarefa não couber no horizonte em nenhuma opção.
    """
    instance = avaliador.instance
    h, max_cost = instance.horizon, float(instance.max_cost) * avaliador.scale
    maquinas: Maquinas = [[] for _ in range(instance.m)]
    fim, custo = [0] * instance.m, [0] * instance.m
    for job in ordenar(instance, regra):
        total = sum(custo)
        best = None
        for machine in range(instance.m):
            others = max((fim[i] for i in range(instance.m) if i != machine), default=0)
            for mode in range(instance.modes):
                for position, end, cost in avaliador.insercoes(machine, maquinas[machine], (job, mode)):
                    if end > h:
                        continue
                    cmax, tec = max(end, others), total - custo[machine] + cost
                    # f decide. No empate, vence o menor término da máquina
                    # (deixa espaço para as próximas tarefas) e depois o TEC.
                    key = (alfa * cmax / h + (1 - alfa) * tec / max_cost, end, tec)
                    if best is None or key < best[0]:
                        best = key, machine, mode, position, end, cost
        if best is None:
            return None
        _, machine, mode, position, end, cost = best
        maquinas[machine].insert(position, (job, mode))
        fim[machine], custo[machine] = end, cost
    return Solucao(maquinas, fim, custo, f"{regra}, alfa={alfa:.2f}")


# ----- etapa 3: ajuste guloso de modos --------------------------------------
def ajustar_modos(avaliador: Avaliador, inicial: Solucao) -> list[Solucao]:
    """Desaceleração gulosa: a cada passo, a troca de modo de maior economia de
    TEC por unidade de Cmax acrescentada; registra todas as soluções do caminho.

    Trocas que reduzem o TEC sem aumentar o Cmax têm prioridade (razão
    infinita). Cada passo reduz o TEC em inteiros, então o laço termina.
    """
    h = avaliador.horizonte
    atual = inicial.copia(f"{inicial.origem}, ajuste 0")
    caminho = [atual]

    def candidatas(machine: int) -> list[tuple[int, int, int, int, int]]:
        """Trocas que reduzem o custo da máquina sem passar do horizonte:
        (economia, novo término, posição, modo, novo custo). Dependem só da
        própria máquina, então só a máquina alterada é recalculada a cada passo."""
        return [(atual.custo[machine] - cost, end, position, mode, cost)
                for position, mode, end, cost in avaliador.trocas_de_modo(machine, atual.maquinas[machine])
                if cost < atual.custo[machine] and end <= h]

    cache = [candidatas(machine) for machine in range(len(atual.maquinas))]
    while True:
        cmax = max(atual.fim)
        best = None
        for machine, options in enumerate(cache):
            others = max((t for i, t in enumerate(atual.fim) if i != machine), default=0)
            for saving, end, position, mode, cost in options:
                increase = max(end, others) - cmax
                # razão economia/aumento; sem aumento de Cmax a razão é infinita
                key = (increase <= 0, saving / increase if increase > 0 else saving, saving)
                if best is None or key > best[0]:
                    best = key, machine, position, mode, end, cost
        if best is None:
            return caminho
        _, machine, position, mode, end, cost = best
        atual = atual.copia(f"{inicial.origem}, ajuste {len(caminho)}")
        job, _ = atual.maquinas[machine][position]
        atual.maquinas[machine][position] = (job, mode)
        atual.fim[machine], atual.custo[machine] = end, cost
        caminho.append(atual)
        cache[machine] = candidatas(machine)


# ----- execução completa ----------------------------------------------------
@dataclass(slots=True)
class Resultado:
    instance: Instance
    escala: int                  # TEC real = TEC escalado / escala
    frente: list[Solucao]
    construidas: int             # soluções geradas pela varredura de pesos
    ajustes: int                 # soluções geradas pelo ajuste de modos
    segundos: float


def pesos(quantidade: int) -> list[float]:
    if quantidade < 2:
        raise ValueError("São necessários pelo menos 2 pesos")
    return [k / (quantidade - 1) for k in range(quantidade)]


def executar(instance: Instance, n_pesos: int = 11) -> Resultado:
    inicio = time.perf_counter()
    avaliador = Avaliador(instance)
    construidas = [s for s in (construir(avaliador, alfa, regra)
                               for regra in ORDENS for alfa in pesos(n_pesos)) if s]
    ajustes = []
    distintas = {s.objetivos: s for s in reversed(construidas)}   # a primeira que chegou a cada par
    for inicial in sorted(distintas.values(), key=lambda s: s.objetivos):
        ajustes.extend(ajustar_modos(avaliador, inicial))
    archive: list = []
    for solucao in construidas + ajustes:
        insert_pareto(archive, solucao.objetivos, solucao)
    frente = [solucao for _, solucao in sorted(archive, key=lambda item: item[0])]
    for solucao in frente:   # confere com o avaliador comum do repositório
        if evaluate_schedule(instance, solucao.schedule()).objective_key != solucao.objetivos:
            raise RuntimeError("Avaliação própria diverge de evaluate_schedule")
    return Resultado(instance, avaliador.scale, frente, len(construidas), len(ajustes),
                     time.perf_counter() - inicio)


def para_json(resultado: Resultado, n_pesos: int) -> dict:
    instance = resultado.instance
    pontos = []
    for solucao in resultado.frente:
        ponto = evaluate_schedule(instance, solucao.schedule()).to_result_dict(instance)
        ponto["origem"] = solucao.origem
        ponto["representation"] = [[[job, mode, 0] for job, mode in seq] for seq in solucao.maquinas]
        pontos.append(ponto)
    return {
        "format_version": 1,
        "algorithm": "Heurística construtiva ponderada + ajuste de modos",
        "method": "heuristica_construtiva",
        "instance": instance.path.name,
        "instance_sha256": instance.digest,
        "pareto_proven": False,
        "horizon": instance.horizon,
        "run_parameters": {"pesos": n_pesos, "ordens": list(ORDENS), "espera": 0},
        "constructed_solutions": resultado.construidas,
        "mode_adjustment_solutions": resultado.ajustes,
        "elapsed_seconds": resultado.segundos,
        "points": len(pontos),
        "front": pontos,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", nargs="?", type=Path,
                        default=ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat",
                        help="arquivo .dat ou pasta com arquivos .dat")
    parser.add_argument("--pesos", type=int, default=11,
                        help="quantidade de pesos alfa (padrão 11: 0; 0,1; ...; 1, como no artigo)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/output/heuristica_construtiva")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    paths = sorted(args.input.glob("*.dat")) if args.input.is_dir() else [args.input]
    if not paths:
        parser.error("Nenhuma instância encontrada")
    try:
        pesos(args.pesos)
    except ValueError as error:
        parser.error(str(error))
    for path in paths:
        output = args.output_dir / f"{path.stem}.json"
        if output.exists() and not args.overwrite:
            parser.error(f"Resultado já existe: {output}; use --overwrite para substituir")
        resultado = executar(read_instance(path), args.pesos)
        atomic_json(output, para_json(resultado, args.pesos))
        print(f"{path.name}: construídas={resultado.construidas}, ajustes={resultado.ajustes}, "
              f"pontos={len(resultado.frente)}, tempo={resultado.segundos:.2f}s, saída={output}")


if __name__ == "__main__":
    main()
