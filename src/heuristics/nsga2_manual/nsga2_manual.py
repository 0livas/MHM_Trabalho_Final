"""NSGA-II implementado do zero (sem pymoo/numpy), seguindo o Algoritmo 2 do artigo.

Laço principal::

    P0 <- população inicial (2 gulosos + aleatórios);  Q0 <- vazio
    enquanto o critério de parada não for satisfeito:
        R  <- P ∪ Q
        F  <- ordenação rápida não dominada de R
        P  <- melhores frentes de F; a última que não cabe inteira é ordenada
              pela crowding distance e completa a população
        Q  <- cruzamento de pares escolhidos por torneio binário, cada filho
              mutado com probabilidade probmut
    devolve as soluções não dominadas viáveis

Critério de parada (como no artigo): tempo de CPU de n * ln(m) segundos. O
artigo não escreve a fórmula, mas os tempos das Tabelas 7 e 10 batem com ela
em todas as instâncias. Para execuções reproduzíveis, ``--geracoes`` troca o
tempo por um número fixo de gerações.

Viabilidade: soluções que passam do horizonte usam a dominância com
restrições de Deb: viável vence inviável; entre inviáveis, vence o menor
excesso.

Run from the repository root::

    python src/heuristics/nsga2_manual/nsga2_manual.py data/input/set1/6_2_1439_3_S_1-9.dat
    python src/heuristics/nsga2_manual/nsga2_manual.py data/input/set1/6_2_1439_3_S_1-9.dat --geracoes 100 --seed 3
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import math
from pathlib import Path
import random
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from avaliacao import Avaliador, Individuo  # noqa: E402
from operadores import OBJETIVOS, cruzamento, mutacao, populacao_inicial  # noqa: E402
from problem import Instance, atomic_json, read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402


@dataclass(frozen=True, slots=True)
class Parametros:
    """Padrões = melhores valores do Irace no artigo (Tabela 5)."""
    tamanho_populacao: int = 110
    prob_mutacao: float = 0.05
    seed: int = 1
    tempo_limite: float | None = None   # None = n * ln(m) segundos
    geracoes: int | None = None         # se definido, substitui o tempo


def tempo_do_artigo(instance: Instance) -> float:
    """Tempo limite inferido das Tabelas 7 e 10 do artigo: n * ln(m) segundos."""
    return instance.n * math.log(max(instance.m, 2))


# ----- dominância e ordenação ------------------------------------------------
def domina(a: Individuo, b: Individuo) -> bool:
    """Dominância com restrições (Deb): viabilidade primeiro, depois Pareto."""
    if a.excesso != b.excesso:
        return a.excesso < b.excesso
    (a1, a2), (b1, b2) = a.objetivos, b.objetivos
    return a1 <= b1 and a2 <= b2 and (a1 < b1 or a2 < b2)


def ordenacao_nao_dominada(populacao: list[Individuo]) -> list[list[int]]:
    """Fast non-dominated sorting (Deb et al., 2002); devolve índices por frente."""
    dominados = [[] for _ in populacao]      # S_p: quem p domina
    contador = [0] * len(populacao)          # n_p: quantos dominam p
    frentes: list[list[int]] = [[]]
    for p, a in enumerate(populacao):
        for q, b in enumerate(populacao):
            if domina(a, b):
                dominados[p].append(q)
            elif domina(b, a):
                contador[p] += 1
        if contador[p] == 0:
            frentes[0].append(p)
    while frentes[-1]:
        proxima = []
        for p in frentes[-1]:
            for q in dominados[p]:
                contador[q] -= 1
                if contador[q] == 0:
                    proxima.append(q)
        frentes.append(proxima)
    return frentes[:-1]


def crowding_distance(populacao: list[Individuo], frente: list[int]) -> dict[int, float]:
    """Distância de aglomeração: soma, por objetivo, do lado do cuboide vizinho."""
    distancia = {i: 0.0 for i in frente}
    for k in range(2):
        ordem = sorted(frente, key=lambda i: populacao[i].objetivos[k])
        menor, maior = populacao[ordem[0]].objetivos[k], populacao[ordem[-1]].objetivos[k]
        distancia[ordem[0]] = distancia[ordem[-1]] = math.inf
        if maior == menor:
            continue
        for anterior, atual, seguinte in zip(ordem, ordem[1:], ordem[2:]):
            distancia[atual] += (populacao[seguinte].objetivos[k]
                                 - populacao[anterior].objetivos[k]) / (maior - menor)
    return distancia


def sobrevivencia(populacao: list[Individuo], tamanho: int) -> list[Individuo]:
    """Linhas 6-21 do Algoritmo 2: frentes inteiras e, na última, maior crowding."""
    proxima: list[Individuo] = []
    for frente in ordenacao_nao_dominada(populacao):
        if len(proxima) + len(frente) <= tamanho:
            proxima.extend(populacao[i] for i in frente)
            continue
        distancia = crowding_distance(populacao, frente)
        frente = sorted(frente, key=lambda i: distancia[i], reverse=True)
        proxima.extend(populacao[i] for i in frente[:tamanho - len(proxima)])
        break
    return proxima


def torneio(populacao: list[Individuo], rng: random.Random) -> Individuo:
    """Torneio binário do artigo: vence quem domina; se nenhum domina, um
    objetivo sorteado decide (empate total: sorteio)."""
    a, b = rng.sample(populacao, 2) if len(populacao) > 1 else (populacao[0],) * 2
    if domina(a, b):
        return a
    if domina(b, a):
        return b
    k = OBJETIVOS.index(rng.choice(OBJETIVOS))
    if a.objetivos[k] != b.objetivos[k]:
        return a if a.objetivos[k] < b.objetivos[k] else b
    return rng.choice((a, b))


def nao_dominados(populacao: list[Individuo]) -> list[Individuo]:
    """Soluções viáveis não dominadas, uma por par (Cmax, TEC), ordenadas por Cmax."""
    unicos = {ind.objetivos: ind for ind in populacao if ind.excesso == 0}
    frente = [ind for ind in unicos.values()
              if not any(domina(outro, ind) for outro in unicos.values())]
    return sorted(frente, key=lambda ind: ind.objetivos)


# ----- laço principal --------------------------------------------------------
@dataclass(slots=True)
class Resultado:
    instance: Instance
    parametros: Parametros
    frente: list[Individuo]
    escala: int          # TEC real = tec_units / escala
    geracoes: int
    avaliacoes: int
    tempo_limite: float | None
    segundos: float


def executar(instance: Instance, parametros: Parametros = Parametros()) -> Resultado:
    if parametros.tamanho_populacao < 2:
        raise ValueError("tamanho_populacao deve ser pelo menos 2")
    rng = random.Random(parametros.seed)
    avaliador = Avaliador(instance)
    limite = None
    if parametros.geracoes is None:
        limite = parametros.tempo_limite if parametros.tempo_limite is not None else tempo_do_artigo(instance)
    inicio = time.process_time()

    def esgotou() -> bool:
        return limite is not None and time.process_time() - inicio >= limite

    tamanho = parametros.tamanho_populacao
    pais = populacao_inicial(avaliador, rng, tamanho)
    filhos: list[Individuo] = []
    geracao = 0
    while not (esgotou() if limite is not None else geracao >= parametros.geracoes):
        pais = sobrevivencia(pais + filhos, tamanho)
        filhos = []
        while len(filhos) < tamanho and not esgotou():
            for maquinas in cruzamento(avaliador, rng, torneio(pais, rng), torneio(pais, rng)):
                if rng.random() < parametros.prob_mutacao:
                    mutacao(maquinas, rng, instance)
                filhos.append(avaliador.avaliar(maquinas))
        filhos = filhos[:tamanho]
        geracao += 1
    frente = nao_dominados(pais + filhos)
    for individuo in frente:   # confere com o avaliador comum do repositório
        if evaluate_schedule(instance, individuo.schedule()).objective_key != individuo.objetivos:
            raise RuntimeError("Avaliação própria diverge de evaluate_schedule")
    return Resultado(instance, parametros, frente, avaliador.scale, geracao, avaliador.avaliacoes, limite,
                     time.process_time() - inicio)


def para_json(resultado: Resultado) -> dict:
    instance = resultado.instance
    pontos = []
    for individuo in resultado.frente:
        ponto = evaluate_schedule(instance, individuo.schedule()).to_result_dict(instance)
        ponto["representation"] = [[[job, mode, 0] for job, mode in seq] for seq in individuo.maquinas]
        pontos.append(ponto)
    return {
        "format_version": 1,
        "algorithm": "NSGA-II (manual)",
        "method": "nsga2_manual",
        "instance": instance.path.name,
        "instance_sha256": instance.digest,
        "pareto_proven": False,
        "horizon": instance.horizon,
        "run_parameters": asdict(resultado.parametros),
        "stopping_criterion": ("geracoes" if resultado.tempo_limite is None
                               else f"tempo de CPU {resultado.tempo_limite:.2f} s"),
        "generations": resultado.geracoes,
        "evaluations": resultado.avaliacoes,
        "elapsed_seconds": resultado.segundos,
        "points": len(pontos),
        "front": pontos,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", nargs="?", type=Path,
                        default=ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--populacao", type=int, default=110)
    parser.add_argument("--prob-mutacao", type=float, default=0.05)
    parser.add_argument("--tempo", type=float, help="tempo limite em s (padrão: n * ln(m))")
    parser.add_argument("--geracoes", type=int, help="número fixo de gerações (substitui o tempo)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/output/nsga2_manual")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    instance = read_instance(args.input)
    output = args.output_dir / f"{args.input.stem}.json"
    if output.exists() and not args.overwrite:
        parser.error(f"Resultado já existe: {output}; use --overwrite para substituir")
    parametros = Parametros(args.populacao, args.prob_mutacao, args.seed, args.tempo, args.geracoes)
    resultado = executar(instance, parametros)
    atomic_json(output, para_json(resultado))
    print(f"{args.input.name}: gerações={resultado.geracoes}, avaliações={resultado.avaliacoes}, "
          f"pontos={len(resultado.frente)}, tempo={resultado.segundos:.2f}s, saída={output}")


if __name__ == "__main__":
    main()
