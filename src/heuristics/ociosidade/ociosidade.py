"""Heurística de inserção ótima de ociosidade (sequência fixa, tempos ótimos).

É uma heurística de decomposição "sequenciar e depois programar no tempo"
(sequencing + timing). A alocação das tarefas às máquinas e a ordem em cada
máquina vêm de uma solução de partida e ficam fixas. Para essa sequência, os
instantes de início (com espera voluntária) e os modos são escolhidos de forma
**ótima** por programação dinâmica, sem regra gulosa: nenhuma decisão é tomada
olhando só o passo atual.

Por que esperar pode compensar: espera e setup não consomem energia (modelo de
``problem.py``). Atrasar uma tarefa que começaria na ponta para depois dela
troca slots caros por slots baratos, ao custo de aumentar o término.

Programação dinâmica de uma máquina com sequência j1, ..., jk::

    f_i(t) = menor custo das tarefas 1..i com a tarefa i terminando exatamente em t
    f_i(t) = min sobre o modo o de  custo(o, t - d_o, t) + g_{i-1}(t - d_o - setup)
    g_i(x) = min_{t <= x} f_i(t)          (a espera é "qualquer folga" antes do início)

com d_o = ceil(p / velocidade do modo), g_0(x) = 0 e setup = 0 para a primeira
tarefa. A curva da máquina é F(e) = g_k(e): menor custo terminando até e.

Como Cmax = max das máquinas e TEC = soma das máquinas, para cada limite
e de Cmax o menor TEC é a soma dos F_m(e). Varrendo e de 0 a H obtém-se a
fronteira de Pareto **exata da sequência fixa**; a fronteira final é a união
não dominada das fronteiras de todas as sequências de partida. A heurística
está em fixar a sequência: os métodos exatos também escolhem alocação e ordem.

Run from the repository root::

    python src/heuristics/ociosidade/ociosidade.py data/input/set1/6_2_1439_3_S_1-9.dat
    python src/heuristics/ociosidade/ociosidade.py <entrada> --base data/output/spea2/<entrada>.json
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/heuristics/construtiva"))

from problem import Instance, atomic_json, energy_scale, insert_pareto, read_instance  # noqa: E402
from schedule import evaluate_schedule, schedule_from_result_rows  # noqa: E402

INF = float("inf")
Sequencia = tuple[tuple[int, int], ...]   # (tarefa, modo de partida) na ordem da máquina
Base = tuple[Sequencia, ...]             # uma sequência por máquina


# ----- dados da instância ---------------------------------------------------
class Dados:
    """Durações, preços inteiros e slots de ponta acumulados."""

    def __init__(self, instance: Instance):
        self.instance = instance
        self.horizonte = instance.horizon
        self.scale, prices = energy_scale(instance)
        self.precos = [[(0, 0)] * instance.modes for _ in range(instance.m)]
        for machine, mode, on, off in prices:
            self.precos[machine][mode] = (on, off)
        self.duracao = [[[instance.duration(job, machine, mode) for mode in range(instance.modes)]
                         for machine in range(instance.m)] for job in range(instance.n)]
        self.setup = instance.setup
        # acumulado[t] = slots de ponta em [0, t)
        self.acumulado = [0] * (instance.horizon + 1)
        for t in range(instance.horizon):
            self.acumulado[t + 1] = self.acumulado[t] + any(a <= t < b for a, b in instance.peaks)


# ----- programação dinâmica de uma máquina -----------------------------------
@dataclass(slots=True)
class CurvaMaquina:
    """Resultado da DP de uma máquina com sequência fixa."""
    machine: int
    sequencia: Sequencia
    custo_ate: list            # F(e): menor custo terminando até e (INF se impossível)
    fim_ate: list[int]         # término que realiza F(e)
    modo: list[list[int]]      # modo[i][t]: modo ótimo da tarefa i terminando em t
    anterior: list[list[int]]  # anterior[i][x]: término de i que realiza g_i(x)

    def reconstruir(self, dados: Dados, fim: int) -> list[tuple[int, int, int, int]]:
        """(tarefa, modo, início, término) de cada tarefa, terminando a máquina em ``fim``."""
        resultado = []
        t = fim
        for i in range(len(self.sequencia) - 1, -1, -1):
            job = self.sequencia[i][0]
            mode = self.modo[i][t]
            start = t - dados.duracao[job][self.machine][mode]
            resultado.append((job, mode, start, t))
            if i:
                previous = self.sequencia[i - 1][0]
                t = self.anterior[i - 1][start - dados.setup[self.machine][previous][job]]
        return resultado[::-1]


def programar_maquina(dados: Dados, machine: int, sequencia: Sequencia,
                      modos_fixos: bool = False) -> CurvaMaquina:
    """DP exata de tempos (e modos) para a sequência fixa de uma máquina."""
    h = dados.horizonte
    if not sequencia:
        return CurvaMaquina(machine, sequencia, [0] * (h + 1), [0] * (h + 1), [], [])
    acumulado = dados.acumulado
    g = [0] * (h + 1)            # g_0: nada processado, custo 0 para qualquer limite
    modos_por_tarefa, anteriores = [], []
    previous = None
    for job, start_mode in sequencia:
        setup = dados.setup[machine][previous][job] if previous is not None else 0
        f = [INF] * (h + 1)
        best_mode = [-1] * (h + 1)
        modes = [start_mode] if modos_fixos else range(dados.instance.modes)
        for mode in modes:
            d = dados.duracao[job][machine][mode]
            on, off = dados.precos[machine][mode]
            for t in range(setup + d, h + 1):
                s = t - d
                before = g[s - setup]
                if before == INF:
                    continue
                peak = acumulado[t] - acumulado[s]
                value = before + on * peak + off * (d - peak)
                if value < f[t]:
                    f[t], best_mode[t] = value, mode
        # prefixo mínimo: g_i(x) = min_{t <= x} f_i(t) e o t que o realiza
        g = [INF] * (h + 1)
        arg = [-1] * (h + 1)
        best, best_t = INF, -1
        for t in range(h + 1):
            if f[t] < best:
                best, best_t = f[t], t
            g[t], arg[t] = best, best_t
        modos_por_tarefa.append(best_mode)
        anteriores.append(arg)
        previous = job
    return CurvaMaquina(machine, sequencia, g, anteriores[-1], modos_por_tarefa, anteriores)


# ----- fronteira de uma sequência --------------------------------------------
@dataclass(slots=True)
class Ponto:
    objetivos: tuple[int, int]                 # (Cmax, TEC escalado)
    schedule: tuple[tuple[tuple[int, int, int], ...], ...]   # (tarefa, modo, espera)
    origem: str


def fronteira_da_base(dados: Dados, base: Base, origem: str, modos_fixos: bool = False) -> list[Ponto]:
    """Fronteira exata (Cmax, TEC) da alocação e sequência fixas."""
    curvas = [programar_maquina(dados, machine, seq, modos_fixos) for machine, seq in enumerate(base)]
    pontos, last = [], INF
    for limite in range(dados.horizonte + 1):
        tec = sum(curva.custo_ate[limite] for curva in curvas)
        if tec >= last:          # só registra quando o limite maior reduz o TEC
            continue
        last = tec
        schedule = []
        for curva in curvas:
            ops = curva.reconstruir(dados, curva.fim_ate[limite]) if curva.sequencia else []
            seq, end, prev = [], 0, None
            for job, mode, start, finish in ops:
                setup = dados.setup[curva.machine][prev][job] if prev is not None else 0
                seq.append((job, mode, start - end - setup))
                end, prev = finish, job
            schedule.append(tuple(seq))
        cmax = max(curva.fim_ate[limite] for curva in curvas)
        pontos.append(Ponto((cmax, tec), tuple(schedule), origem))
    return pontos


# ----- soluções de partida ---------------------------------------------------
def base_de_schedule(schedule) -> Base:
    """Alocação e ordem (com o modo de partida) de um schedule (tarefa, modo, espera)."""
    return tuple(tuple((job, mode) for job, mode, _ in seq) for seq in schedule)


def bases_construtivas(instance: Instance) -> list[tuple[Base, str]]:
    """Sequências da fronteira da heurística construtiva."""
    import construtiva
    resultado = construtiva.executar(instance)
    return [(base_de_schedule(s.schedule()), f"construtiva ({s.origem})") for s in resultado.frente]


def bases_de_json(instance: Instance, path: Path) -> list[tuple[Base, str]]:
    """Sequências dos pontos de um JSON de resultado de qualquer método do repositório."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("instance_sha256") not in (None, instance.digest):
        raise ValueError(f"{path} foi gerado para outra entrada (hash diferente)")
    return [(base_de_schedule(schedule_from_result_rows(instance, point["schedule"])),
             f"{path.stem} ponto {index}") for index, point in enumerate(data["front"])]


# ----- execução completa ----------------------------------------------------
@dataclass(slots=True)
class Resultado:
    instance: Instance
    escala: int
    frente: list[Ponto]
    bases: int            # sequências distintas programadas
    segundos: float


def executar(instance: Instance, bases: list[tuple[Base, str]] | None = None,
             modos_fixos: bool = False) -> Resultado:
    inicio = time.perf_counter()
    dados = Dados(instance)
    if bases is None:
        bases = bases_construtivas(instance)
    # Com modos livres, só alocação e ordem importam: bases que diferem apenas
    # nos modos geram a mesma DP.
    distintas: dict = {}
    for base, origem in bases:
        chave = base if modos_fixos else tuple(tuple(job for job, _ in seq) for seq in base)
        distintas.setdefault(chave, (base, origem))
    archive: list = []
    for base, origem in distintas.values():
        for ponto in fronteira_da_base(dados, base, origem, modos_fixos):
            insert_pareto(archive, ponto.objetivos, ponto)
    frente = [ponto for _, ponto in sorted(archive, key=lambda item: item[0])]
    for ponto in frente:   # confere com o avaliador comum do repositório
        if evaluate_schedule(instance, ponto.schedule).objective_key != ponto.objetivos:
            raise RuntimeError("Programação dinâmica diverge de evaluate_schedule")
    return Resultado(instance, dados.scale, frente, len(distintas), time.perf_counter() - inicio)


def para_json(resultado: Resultado, fonte: str, modos_fixos: bool) -> dict:
    instance = resultado.instance
    pontos = []
    for ponto in resultado.frente:
        item = evaluate_schedule(instance, ponto.schedule).to_result_dict(instance)
        item["origem"] = ponto.origem
        item["representation"] = [[list(op) for op in seq] for seq in ponto.schedule]
        pontos.append(item)
    return {
        "format_version": 1,
        "algorithm": "Heurística de inserção ótima de ociosidade",
        "method": "heuristica_ociosidade",
        "instance": instance.path.name,
        "instance_sha256": instance.digest,
        "pareto_proven": False,
        "horizon": instance.horizon,
        "run_parameters": {"base": fonte, "modos": "fixos" if modos_fixos else "livres"},
        "base_sequences": resultado.bases,
        "elapsed_seconds": resultado.segundos,
        "points": len(pontos),
        "front": pontos,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", nargs="?", type=Path,
                        default=ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
    parser.add_argument("--base", type=Path,
                        help="JSON de resultado com as sequências de partida (padrão: heurística construtiva)")
    parser.add_argument("--modos-fixos", action="store_true",
                        help="mantém os modos da solução de partida e otimiza só as esperas")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/output/heuristica_ociosidade")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    instance = read_instance(args.input)
    output = args.output_dir / f"{args.input.stem}.json"
    if output.exists() and not args.overwrite:
        parser.error(f"Resultado já existe: {output}; use --overwrite para substituir")
    try:
        bases = bases_de_json(instance, args.base) if args.base else None
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    resultado = executar(instance, bases, args.modos_fixos)
    fonte = str(args.base) if args.base else "heurística construtiva"
    atomic_json(output, para_json(resultado, fonte, args.modos_fixos))
    print(f"{args.input.name}: sequências={resultado.bases}, pontos={len(resultado.frente)}, "
          f"tempo={resultado.segundos:.2f}s, saída={output}")


if __name__ == "__main__":
    main()
