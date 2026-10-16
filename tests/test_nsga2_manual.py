from __future__ import annotations

import json
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/heuristics/nsga2_manual"))

import operadores  # noqa: E402
from avaliacao import Avaliador, Individuo  # noqa: E402
from nsga2_manual import (Parametros, crowding_distance, domina, executar,  # noqa: E402
                          ordenacao_nao_dominada, sobrevivencia, tempo_do_artigo)
from problem import read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402

SMALL = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"
MEDIUM = ROOT / "data/input/set2/50_10_1439_5_S_1-9.dat"


def ponto(cmax: int, tec: int, excesso: int = 0) -> Individuo:
    return Individuo([[]], [cmax], [tec], cmax - excesso)


def tarefas(maquinas) -> list[int]:
    return sorted(job for seq in maquinas for job, _ in seq)


class AvaliacaoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance = read_instance(MEDIUM)
        cls.avaliador = Avaliador(cls.instance)

    def test_matches_common_evaluator(self):
        rng = random.Random(0)
        for _ in range(100):
            ind = self.avaliador.avaliar(operadores.aleatorio(self.avaliador, rng))
            self.assertEqual(ind.excesso, 0)
            self.assertEqual(evaluate_schedule(self.instance, ind.schedule()).objective_key,
                             ind.objetivos)

    def test_insertion_probe_matches_full_recalculation(self):
        rng = random.Random(1)
        jobs = list(range(self.instance.n))
        for machine in range(3):
            rng.shuffle(jobs)
            # 30 tarefas numa só máquina passam por várias pontas diárias.
            seq = [(job, rng.randrange(self.instance.modes)) for job in jobs[:30]]
            gene = (jobs[30], rng.randrange(self.instance.modes))
            for position, end, cost in self.avaliador.insercoes(machine, seq, gene):
                expected = self.avaliador.maquina(machine, seq[:position] + [gene] + seq[position:])
                self.assertEqual((end, cost), expected)


class OperadoresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance = read_instance(MEDIUM)
        cls.avaliador = Avaliador(cls.instance)

    def test_operators_keep_every_job_exactly_once(self):
        rng = random.Random(2)
        populacao = operadores.populacao_inicial(self.avaliador, rng, 10)
        everyone = list(range(self.instance.n))
        for ind in populacao:
            self.assertEqual(tarefas(ind.maquinas), everyone)
        for _ in range(50):
            for filho in operadores.cruzamento(self.avaliador, rng, *rng.sample(populacao, 2)):
                self.assertEqual(tarefas(filho), everyone)
                operadores.mutacao(filho, rng, self.instance)
                self.assertEqual(tarefas(filho), everyone)
                self.assertTrue(all(0 <= mode < self.instance.modes for seq in filho for _, mode in seq))

    def test_greedy_individuals_use_the_paper_modes(self):
        rng = random.Random(3)
        fastest = max(range(self.instance.modes), key=lambda o: self.instance.speed[o])
        cheapest = min(range(self.instance.modes), key=lambda o: self.instance.power_factor[o])
        for objetivo, mode in (("cmax", fastest), ("tec", cheapest)):
            maquinas = operadores.guloso(self.avaliador, rng, objetivo)
            self.assertEqual({m for seq in maquinas for _, m in seq}, {mode})


class SelecaoTests(unittest.TestCase):
    def test_constrained_dominance(self):
        self.assertTrue(domina(ponto(5, 5), ponto(6, 5)))
        self.assertFalse(domina(ponto(5, 6), ponto(6, 5)))
        self.assertTrue(domina(ponto(9, 9), ponto(1, 1, excesso=1)))   # viável vence
        self.assertTrue(domina(ponto(9, 9, 1), ponto(1, 1, excesso=2)))  # menor excesso

    def test_sorting_and_crowding(self):
        populacao = [ponto(1, 4), ponto(2, 2), ponto(4, 1), ponto(3, 3), ponto(5, 5)]
        self.assertEqual([sorted(f) for f in ordenacao_nao_dominada(populacao)], [[0, 1, 2], [3], [4]])
        distancia = crowding_distance(populacao, [0, 1, 2])
        self.assertEqual(distancia[0], float("inf"))
        self.assertAlmostEqual(distancia[1], 2.0)   # (4-1)/3 + (4-1)/3
        kept = sobrevivencia(populacao, 4)
        self.assertEqual([p.objetivos for p in kept], [(1, 4), (2, 2), (4, 1), (3, 3)])


class ExecucaoTests(unittest.TestCase):
    def test_paper_time_limit(self):
        self.assertAlmostEqual(tempo_do_artigo(read_instance(SMALL)), 4.16, places=2)
        self.assertAlmostEqual(tempo_do_artigo(read_instance(MEDIUM)), 115.13, places=2)

    def test_reproducible_and_never_beyond_exact_front(self):
        instance = read_instance(SMALL)
        parametros = Parametros(tamanho_populacao=30, geracoes=30, seed=5)
        primeira, segunda = executar(instance, parametros), executar(instance, parametros)
        self.assertEqual([i.objetivos for i in primeira.frente], [i.objetivos for i in segunda.frente])
        self.assertEqual(primeira.geracoes, 30)
        self.assertEqual(primeira.avaliacoes, 30 + 30 * 30)

        exact = json.loads((ROOT / "data/baselines/6_2_1439_3_S_1-9_custom_exact_dp.json")
                           .read_text(encoding="utf-8"))["front"]
        exact_keys = [(p["makespan"], p["tec_exact"]["numerator"] * primeira.escala
                       // p["tec_exact"]["denominator"]) for p in exact]
        for ind in primeira.frente:
            for cmax, tec in exact_keys:
                self.assertFalse(domina(ind, ponto(cmax, tec)), ind.objetivos)


if __name__ == "__main__":
    unittest.main()
