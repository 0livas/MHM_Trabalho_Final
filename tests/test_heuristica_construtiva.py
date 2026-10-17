from __future__ import annotations

import json
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/heuristics/construtiva"))

import construtiva  # noqa: E402
from problem import dominates, read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402

SMALL = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"
MEDIUM = ROOT / "data/input/set2/50_10_1439_5_S_1-9.dat"


def tarefas(maquinas) -> list[int]:
    return sorted(job for seq in maquinas for job, _ in seq)


class AvaliadorTests(unittest.TestCase):
    """Os atalhos por máquina precisam coincidir com o recálculo completo."""

    @classmethod
    def setUpClass(cls):
        cls.instance = read_instance(MEDIUM)
        cls.avaliador = construtiva.Avaliador(cls.instance)
        rng = random.Random(1)
        jobs = list(range(cls.instance.n))
        rng.shuffle(jobs)
        # 30 tarefas numa só máquina terminam depois da ponta (1080-1260).
        cls.seq = [(job, rng.randrange(cls.instance.modes)) for job in jobs[:30]]
        cls.gene = (jobs[30], 2)

    def test_sequence_crosses_the_peak(self):
        self.assertGreater(self.avaliador.maquina(0, self.seq)[0], 1260)

    def test_insertion_probe_matches_full_recalculation(self):
        for machine in range(3):
            for position, end, cost in self.avaliador.insercoes(machine, self.seq, self.gene):
                changed = self.seq[:position] + [self.gene] + self.seq[position:]
                self.assertEqual((end, cost), self.avaliador.maquina(machine, changed))

    def test_mode_swap_probe_matches_full_recalculation(self):
        for machine in range(3):
            for position, mode, end, cost in self.avaliador.trocas_de_modo(machine, self.seq):
                changed = list(self.seq)
                changed[position] = (changed[position][0], mode)
                self.assertEqual((end, cost), self.avaliador.maquina(machine, changed))


class ConstrucaoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance = read_instance(MEDIUM)
        cls.avaliador = construtiva.Avaliador(cls.instance)

    def test_every_construction_is_complete_and_matches_common_evaluator(self):
        for regra in construtiva.ORDENS:
            for alfa in (0.0, 0.5, 1.0):
                solucao = construtiva.construir(self.avaliador, alfa, regra)
                self.assertEqual(tarefas(solucao.maquinas), list(range(self.instance.n)))
                evaluation = evaluate_schedule(self.instance, solucao.schedule())
                self.assertEqual(evaluation.objective_key, solucao.objetivos)

    def test_weights_trade_makespan_for_energy(self):
        fast = construtiva.construir(self.avaliador, 1.0).objetivos
        cheap = construtiva.construir(self.avaliador, 0.0).objetivos
        self.assertLess(fast[0], cheap[0])
        self.assertLess(cheap[1], fast[1])

    def test_lpt_orders(self):
        order = construtiva.ordenar(self.instance, "lpt_min")
        mins = [min(self.instance.processing[job]) for job in order]
        self.assertEqual(mins, sorted(mins, reverse=True))

    def test_mode_adjustment_strictly_reduces_energy(self):
        inicial = construtiva.construir(self.avaliador, 1.0)
        caminho = construtiva.ajustar_modos(self.avaliador, inicial)
        self.assertGreater(len(caminho), 1)
        self.assertEqual(caminho[0].objetivos, inicial.objetivos)
        energies = [solucao.objetivos[1] for solucao in caminho]
        self.assertEqual(energies, sorted(energies, reverse=True))
        self.assertEqual(len(set(energies)), len(energies))
        for solucao in caminho:
            self.assertEqual(evaluate_schedule(self.instance, solucao.schedule()).objective_key,
                             solucao.objetivos)


class ExecucaoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance = read_instance(SMALL)
        cls.resultado = construtiva.executar(cls.instance)

    def test_deterministic(self):
        again = construtiva.executar(self.instance)
        self.assertEqual([s.objetivos for s in again.frente], [s.objetivos for s in self.resultado.frente])
        self.assertEqual(self.resultado.construidas, 3 * 11)

    def test_front_is_mutually_nondominated(self):
        keys = [s.objetivos for s in self.resultado.frente]
        self.assertEqual(keys, sorted(keys))
        for a in keys:
            self.assertFalse(any(dominates(b, a) for b in keys))

    def test_never_beyond_exact_front_and_reaches_its_extremes(self):
        exact = json.loads((ROOT / "data/baselines/6_2_1439_3_S_1-9_custom_exact_dp.json")
                           .read_text(encoding="utf-8"))
        scale = self.resultado.escala
        exact_keys = [(p["makespan"], p["tec_exact"]["numerator"] * scale // p["tec_exact"]["denominator"])
                      for p in exact["front"]]
        for solucao in self.resultado.frente:
            self.assertFalse(any(dominates(solucao.objetivos, key) for key in exact_keys))
        self.assertEqual(self.resultado.frente[0].objetivos, min(exact_keys))       # menor Cmax
        self.assertEqual(self.resultado.frente[-1].objetivos[1], min(t for _, t in exact_keys))  # menor TEC

    def test_json_output(self):
        data = construtiva.para_json(self.resultado, 11)
        self.assertEqual(data["points"], len(self.resultado.frente))
        self.assertFalse(data["pareto_proven"])
        self.assertTrue(all("origem" in point for point in data["front"]))


if __name__ == "__main__":
    unittest.main()
