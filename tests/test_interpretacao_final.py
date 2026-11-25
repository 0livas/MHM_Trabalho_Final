from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from interpretacao_final import (
    Run, agregar, analyze_instance, calcular, escapar, posicoes, proporcoes, ranking_geral, ranks, uniao_por_algoritmo,
)


def execucao(algoritmo, pontos, numero=1):
    return Run(algoritmo, "x", numero, None, "COMPLETED", 1.0, tuple(pontos), False, "x", None)


class MetricasTests(unittest.TestCase):
    def test_camadas_removidas_em_sequencia(self):
        camadas, total = ranks([(1, 3), (3, 1), (2, 3), (4, 4), (1, 3)])
        self.assertEqual(total, 3)
        self.assertEqual(camadas, {(1, 3): 1, (3, 1): 1, (2, 3): 2, (4, 4): 3})

    def test_ponto_compartilhado_e_rank_ponderado(self):
        a, b = execucao("a", [(1, 3), (3, 1)]), execucao("b", [(1, 3), (4, 2)])
        resumo, linhas, _ = analyze_instance([a, b, execucao("c", [])])
        self.assertEqual(resumo["rank_count"], 2)
        self.assertEqual([l["Purity"] for l in linhas], [1.0, .5, None])
        self.assertEqual([l["Eq36"] for l in linhas], [2.0, 1.5, None])

    def test_fronteira_unica_tem_z_igual_a_R(self):
        resumo, linhas, _ = analyze_instance([execucao("a", [(1, 3), (3, 1)])])
        self.assertEqual(linhas[0]["Eq36"], resumo["rank_count"])

    def test_uniao_remove_dominados(self):
        uniao = uniao_por_algoritmo([execucao("a", [(1, 3), (4, 4)]), execucao("a", [(3, 1)], 2)])
        self.assertEqual(uniao, {"a": [(1, 3), (3, 1)]})


class RankingTests(unittest.TestCase):
    def test_posicoes_com_empate_e_ausencia(self):
        self.assertEqual(posicoes(dict(a=1.0, b=0.0, c=0.0, d=None)), dict(a=1.0, b=2.5, c=2.5, d=None))

    def test_proporcoes(self):
        r = proporcoes(dict(a=2.0, b=1.0, c=None))
        self.assertEqual(r, dict(razao=dict(a=1.0, b=.5, c=None), vencedores=("a",), vantagem_pct=100.0))
        self.assertIsNone(proporcoes(dict(a=2.0, b=0.0))["vantagem_pct"])
        self.assertIsNone(proporcoes(dict(a=2.0))["vantagem_pct"])
        self.assertEqual(proporcoes(dict(a=0.0, b=0.0))["razao"], dict(a=None, b=None))
        empate = proporcoes(dict(a=1.0, b=1.0, c=.5))
        self.assertEqual((empate["vencedores"], empate["vantagem_pct"]), (("a", "b"), 0.0))

    def test_agregar_separa_vitoria_de_empate(self):
        base = dict(algoritmo="a", posicao=1.0, razao_melhor=1.0, vencedor=True)
        r = agregar([dict(base, empate_no_topo=False), dict(base, posicao=1.5, empate_no_topo=True)], ("a", "b"))
        self.assertEqual((r["a"]["vitorias"], r["a"]["empates_no_topo"], r["a"]["posicao_media"]), (1, 1, 1.25))
        self.assertEqual((r["b"]["instancias"], r["b"]["posicao_media"]), (0, None))

    def test_escapar_latex(self):
        self.assertEqual(escapar("6_2&%"), r"6\_2\&\%")


class DadosArquivadosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.execucoes, cls.instancias, cls.unioes = calcular()

    def valor(self, instancia, metrica, algoritmo):
        return next(l for l in self.instancias if (l["instancia"], l["metrica"], l["algoritmo"], l["escopo"])
                    == (instancia, metrica, algoritmo, "todos"))

    def test_valores_conhecidos(self):
        dez = "10_2_1439_3_S_1-9"
        for metrica, esperado in (("hv", 1.036), ("participacao", .204), ("rank", .906)):
            self.assertAlmostEqual(self.valor(dez, metrica, "age")["media"], esperado, places=3)
        for metrica in ("participacao", "rank"):
            self.assertEqual(self.valor(dez, metrica, "exact_dp")["media"], 1.0)
        quatorze = self.valor("14_2_1439_3_S_1-9_derivada", "rank", "age")
        self.assertEqual((quatorze["R"], quatorze["tamanho_P"]), (73, 258))
        self.assertAlmostEqual(self.valor("250_20_1439_5_S_1-124", "rank", "vns_vnd_new")["media"], .774, places=3)

    def test_vns_original_fora_e_cobertura(self):
        self.assertNotIn("vns_vnd", {l["algoritmo"] for l in self.execucoes})
        self.assertEqual(len(self.execucoes), 9 * (4 * 30 + 2))
        geral = ranking_geral(self.instancias)
        self.assertEqual({(l["escopo"], l["instancias"]) for l in geral if l["porte"] == "todos"},
                         {("nao_exatos", 9), ("com_exato", 2)})


if __name__ == "__main__":
    unittest.main()
