from __future__ import annotations

from dataclasses import replace
from itertools import product
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/heuristics/ociosidade"))

import ociosidade  # noqa: E402  (inclui o caminho de construtiva)
import construtiva  # noqa: E402
from problem import atomic_json, dominates, read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402

SMALL = ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat"


def tiny_instance():
    """3 tarefas, 1 máquina, 3 modos, horizonte 30 e ponta em [10, 18)."""
    base = read_instance(SMALL)
    return replace(base, n=3, m=1, days=1, slots_per_day=30, peaks=((10, 18),),
                   power=base.power[:1], processing=((5,), (4,), (6,)),
                   setup=(((0, 1, 2), (1, 0, 1), (2, 1, 0)),))


def brute_force(dados, sequence):
    """Menor custo para cada limite de término, enumerando modos e esperas."""
    h = dados.horizonte
    best = [ociosidade.INF] * (h + 1)
    modes = range(dados.instance.modes)
    for combo in product(modes, repeat=len(sequence)):
        for waits in product(range(h + 1), repeat=len(sequence)):
            t, cost, previous = 0, 0, None
            for job, mode, wait in zip(sequence, combo, waits):
                start = t + wait + (dados.setup[0][previous][job] if previous is not None else 0)
                end = start + dados.duracao[job][0][mode]
                if end > h:
                    break
                on, off = dados.precos[0][mode]
                peak = dados.acumulado[end] - dados.acumulado[start]
                cost += on * peak + off * (end - start - peak)
                t, previous = end, job
            else:
                for limit in range(t, h + 1):
                    best[limit] = min(best[limit], cost)
    return best


class ProgramacaoDinamicaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance = tiny_instance()
        cls.dados = ociosidade.Dados(cls.instance)
        cls.sequence = (2, 0, 1)

    def test_machine_dp_is_optimal_for_every_deadline(self):
        curva = ociosidade.programar_maquina(self.dados, 0, tuple((job, 0) for job in self.sequence))
        self.assertEqual(curva.custo_ate, brute_force(self.dados, self.sequence))

    def test_reconstruction_matches_common_evaluator(self):
        base = (tuple((job, 0) for job in self.sequence),)
        pontos = ociosidade.fronteira_da_base(self.dados, base, "teste")
        self.assertGreater(len(pontos), 1)
        for ponto in pontos:
            self.assertTrue(all(wait >= 0 for seq in ponto.schedule for _, _, wait in seq))
            self.assertEqual(evaluate_schedule(self.instance, ponto.schedule).objective_key, ponto.objetivos)

    def test_waiting_avoids_the_peak(self):
        # Com modos fixos, o ponto de menor TEC espera a ponta passar.
        base = (tuple((job, 0) for job in self.sequence),)
        pontos = ociosidade.fronteira_da_base(self.dados, base, "teste", modos_fixos=True)
        sem_espera, menor_tec = pontos[0], pontos[-1]
        self.assertEqual(sum(w for seq in sem_espera.schedule for _, _, w in seq), 0)
        self.assertGreater(sum(w for seq in menor_tec.schedule for _, _, w in seq), 0)
        self.assertLess(menor_tec.objetivos[1], sem_espera.objetivos[1])

    def test_fixed_modes_are_kept(self):
        base = (((2, 1), (0, 2), (1, 0)),)
        for ponto in ociosidade.fronteira_da_base(self.dados, base, "teste", modos_fixos=True):
            self.assertEqual([mode for _, mode, _ in ponto.schedule[0]], [1, 2, 0])


class ExecucaoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance = read_instance(SMALL)
        cls.base = construtiva.executar(cls.instance)
        cls.bases = [(ociosidade.base_de_schedule(s.schedule()), s.origem) for s in cls.base.frente]
        cls.resultado = ociosidade.executar(cls.instance, cls.bases)

    def test_front_is_nondominated_and_never_worse_than_its_base(self):
        keys = [p.objetivos for p in self.resultado.frente]
        self.assertEqual(keys, sorted(keys))
        for a in keys:
            self.assertFalse(any(dominates(b, a) for b in keys))
        # Cada ponto da construtiva é igualado ou dominado: a DP inclui a solução sem espera.
        for solucao in self.base.frente:
            self.assertTrue(any(k == solucao.objetivos or dominates(k, solucao.objetivos) for k in keys))

    def test_never_beyond_exact_front(self):
        exact = json.loads((ROOT / "data/baselines/6_2_1439_3_S_1-9_custom_exact_dp.json")
                           .read_text(encoding="utf-8"))
        scale = self.resultado.escala
        exact_keys = [(p["makespan"], p["tec_exact"]["numerator"] * scale // p["tec_exact"]["denominator"])
                      for p in exact["front"]]
        for ponto in self.resultado.frente:
            self.assertFalse(any(dominates(ponto.objetivos, key) for key in exact_keys))

    def test_bases_from_result_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "base.json"
            atomic_json(path, construtiva.para_json(self.base, 11))
            bases = ociosidade.bases_de_json(self.instance, path)
        self.assertEqual([b for b, _ in bases], [b for b, _ in self.bases])
        again = ociosidade.executar(self.instance, bases)
        self.assertEqual([p.objetivos for p in again.frente], [p.objetivos for p in self.resultado.frente])

    def test_json_output(self):
        data = ociosidade.para_json(self.resultado, "teste", False)
        self.assertEqual(data["points"], len(self.resultado.frente))
        self.assertFalse(data["pareto_proven"])


if __name__ == "__main__":
    unittest.main()
