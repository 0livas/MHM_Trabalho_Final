"""Interpretação final: ranking dos algoritmos por três métricas.

Execute `python src/interpretacao_final.py` a partir da raiz. Lê os resultados
arquivados das campanhas; nenhum solver é executado. Métricas, maior é melhor:

- hv: hipervolume na referência publicada da campanha;
- participacao: |F ∩ P*| / |P*|, com P* igual à fronteira de rank 1;
- rank: z/R, com z = média de R + 1 − rank(p) sobre os pontos da solução.

P* e os ranks vêm da união dos seis algoritmos, sem o VNS/VND original.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from pathlib import Path
import statistics
import sys

SRC = Path(__file__).resolve().parent
sys.path[:0] = [str(SRC), str(SRC / "presentation")]

from analysis import Run, analyze_instance, load_campaigns, ranks, value_hv
from experiments.adapters import nondominated
from experiments.config import INSTANCES
from problem import PROJECT_ROOT

DESTINO = PROJECT_ROOT / "data/output/interpretacao_final"
ALGORITMOS = ("exact_dp", "ociosidade", "age", "spea2", "moead", "vns_vnd_new")
NAO_EXATOS = ALGORITMOS[1:]
METRICAS = {"hv": "HV", "participacao": "Purity", "rank": "Eq36"}
# Nomes e cores iguais aos de presentation/visual.py, que exige Manim.
NOMES = {
    "exact_dp": "DP própria", "ociosidade": "Ociosidade", "age": "AGE-MOEA",
    "spea2": "SPEA2", "moead": "MOEA/D", "vns_vnd_new": "VNS revisto",
}
CORES = {
    "exact_dp": "#b18a11", "ociosidade": "#478c9b", "age": "#8e52aa",
    "spea2": "#087b9a", "moead": "#ce7110", "vns_vnd_new": "#347d36",
}
TITULOS = {
    "hv": "Hipervolume", "participacao": "Participação na melhor fronteira",
    "rank": "Rank ponderado (z/R)",
}
PORTES = {"small": "pequeno", "medium": "médio", "large": "grande", "giant": "gigante"}
TOLERANCIA = 1e-12


# ------------------------------------------------------------------ cálculo puro
def posicoes(valores):
    """Posição 1 = maior valor; empates recebem a posição média; None fica sem posição."""
    ordem = sorted((a for a in valores if valores[a] is not None), key=lambda a: -valores[a])
    resultado = dict.fromkeys(valores)
    inicio = 0
    while inicio < len(ordem):
        fim = inicio + 1
        while fim < len(ordem) and valores[ordem[inicio]] - valores[ordem[fim]] <= TOLERANCIA:
            fim += 1
        for algoritmo in ordem[inicio:fim]:
            resultado[algoritmo] = (inicio + 1 + fim) / 2
        inicio = fim
    return resultado


def proporcoes(valores):
    """Razão para o melhor, vencedores e vantagem percentual do 1º sobre o 2º.

    A vantagem é None se não há segundo colocado ou se o segundo vale zero.
    """
    presentes = {a: v for a, v in valores.items() if v is not None}
    if not presentes:
        return dict(razao=dict.fromkeys(valores), vencedores=(), vantagem_pct=None)
    melhor, *demais = sorted(presentes.values(), reverse=True)
    segundo = demais[0] if demais else None
    vantagem = (melhor / segundo - 1) * 100 if segundo else None
    if segundo is not None and melhor - segundo <= TOLERANCIA:
        vantagem = 0.0
    return dict(
        razao={a: None if v is None else v / melhor if melhor else None for a, v in valores.items()},
        vencedores=tuple(a for a, v in presentes.items() if melhor - v <= TOLERANCIA),
        vantagem_pct=vantagem,
    )


def uniao_por_algoritmo(execucoes):
    """Frente não dominada de todas as execuções de cada algoritmo."""
    pontos = defaultdict(list)
    for execucao in execucoes:
        pontos[execucao.algorithm].extend(execucao.points)
    return {algoritmo: nondominated(lista) for algoritmo, lista in pontos.items()}


def agregar(linhas, algoritmos):
    """Posição média e vitórias de um conjunto de (instância, métrica) já ordenado."""
    resultado = {}
    for algoritmo in algoritmos:
        proprias = [l for l in linhas if l["algoritmo"] == algoritmo and l["posicao"] is not None]
        razoes = [l["razao_melhor"] for l in proprias if l["razao_melhor"] is not None]
        resultado[algoritmo] = dict(
            instancias=len(proprias),
            posicao_media=statistics.fmean(l["posicao"] for l in proprias) if proprias else None,
            vitorias=sum(l["vencedor"] and not l["empate_no_topo"] for l in proprias),
            empates_no_topo=sum(l["vencedor"] and l["empate_no_topo"] for l in proprias),
            razao_media_melhor=statistics.fmean(razoes) if razoes else None,
        )
    return resultado


# ------------------------------------------------------------------ tabelas
def calcular():
    campanhas, referencias, _ = load_campaigns()
    por_execucao, por_instancia, unioes = [], [], []
    for spec in INSTANCES:
        instancia = spec.path.stem
        execucoes = [e for e in campanhas[instancia] if e.algorithm in ALGORITMOS]
        resumo, registros, camadas = analyze_instance(execucoes, referencias[instancia])
        total = resumo["rank_count"]
        melhor = {p for p, camada in camadas.items() if camada == 1}
        porte = PORTES[spec.tier]
        for r in registros:
            z = r["Eq36"]
            por_execucao.append(dict(
                instancia=instancia, porte=porte, algoritmo=r["algorithm"], execucao=r["run_id"], seed=r["seed"],
                status=r["status"], pontos=r["front_size"], hv=r["HV"], participacao=r["Purity"],
                z=z, rank=None if z is None else z / total, fonte=r["source"],
            ))
        for metrica, chave in METRICAS.items():
            divisor = total if metrica == "rank" else 1
            estat = {a: resumo["algorithms"][a]["metrics"][chave] for a in ALGORITMOS}
            medias = {a: None if e["mean"] is None else e["mean"] / divisor for a, e in estat.items()}
            for escopo, grupo in (("todos", ALGORITMOS), ("nao_exatos", NAO_EXATOS)):
                valores = {a: medias[a] for a in grupo}
                pos, prop = posicoes(valores), proporcoes(valores)
                for a in grupo:
                    e = estat[a]
                    por_instancia.append(dict(
                        instancia=instancia, porte=porte, escopo=escopo, metrica=metrica, algoritmo=a,
                        execucoes_com_frente=e["n"], media=medias[a],
                        desvio=None if e["std"] is None else e["std"] / divisor,
                        z_medio=e["mean"] if metrica == "rank" else None, posicao=pos[a],
                        razao_melhor=prop["razao"][a], vencedor=a in prop["vencedores"],
                        empate_no_topo=len(prop["vencedores"]) > 1,
                        vantagem_1o_sobre_2o_pct=prop["vantagem_pct"], R=total, tamanho_P=len(melhor),
                        comprovada=any(x.proven for x in execucoes),
                    ))
        for a, frente in uniao_por_algoritmo(execucoes).items():
            z = statistics.fmean(total + 1 - camadas[p] for p in frente) if frente else None
            unioes.append(dict(
                instancia=instancia, porte=porte, algoritmo=a, pontos=len(frente),
                hv=value_hv(frente, referencias[instancia]) if frente else None,
                participacao=len(melhor.intersection(frente)) / len(melhor) if frente else None,
                z=z, rank=None if z is None else z / total, R=total, tamanho_P=len(melhor),
            ))
    return por_execucao, por_instancia, unioes


def ranking_geral(por_instancia):
    """(a) não exatos em todas as instâncias; (b) os seis onde há fronteira provada."""
    saida = []
    for nome, escopo, grupo, filtro in (
        ("nao_exatos", "nao_exatos", NAO_EXATOS, lambda l: True),
        ("com_exato", "todos", ALGORITMOS, lambda l: l["comprovada"]),
    ):
        for porte in ("todos", *PORTES.values()):
            for metrica in METRICAS:
                linhas = [l for l in por_instancia if l["escopo"] == escopo and l["metrica"] == metrica
                          and filtro(l) and porte in ("todos", l["porte"])]
                if linhas:
                    saida += [dict(escopo=nome, porte=porte, metrica=metrica, algoritmo=a, **d)
                              for a, d in agregar(linhas, grupo).items()]
    return saida


def gravar_csv(caminho, linhas):
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)


# ------------------------------------------------------------------ LaTeX
def escapar(texto):
    return "".join({"_": r"\_", "%": r"\%", "&": r"\&", "#": r"\#"}.get(c, c) for c in texto)


def nome_curto(instancia):
    return instancia.replace("_1439_", "_").replace("_derivada", "*")


def ambiente(titulo, rotulo, colunas, cabecalho, corpo):
    return "\n".join([
        "% Requer \\usepackage{booktabs,graphicx}", r"\begin{table}[htbp]", r"\centering\scriptsize",
        rf"\caption{{{titulo}}}", rf"\label{{tab:{rotulo}}}", r"\resizebox{\linewidth}{!}{%",
        rf"\begin{{tabular}}{{{colunas}}}", r"\toprule",
        " & ".join(cabecalho) + r" \\", r"\midrule", *[" & ".join(c) + r" \\" for c in corpo],
        r"\bottomrule", r"\end{tabular}}", r"\end{table}", "",
    ])


def tabela_metrica(por_instancia, metrica, titulo, rotulo, bruto=False):
    corpo = []
    for spec in INSTANCES:
        grupo = [l for l in por_instancia if l["escopo"] == "todos" and l["metrica"] == metrica
                 and l["instancia"] == spec.path.stem]
        celulas = [escapar(nome_curto(spec.path.stem))]
        if metrica != "hv":
            celulas.append(str(grupo[0]["R" if bruto else "tamanho_P"]))
        for l in grupo:
            if l["media"] is None:
                celulas.append("--")
                continue
            fator, casas = (l["R"], 2) if bruto else (1, 3)
            valor = f"{l['media'] * fator:.{casas}f}"
            if l["vencedor"]:
                valor = rf"\textbf{{{valor}}}"
            if l["desvio"] is not None:
                valor += rf" $\pm$ {l['desvio'] * fator:.{casas}f}"
            celulas.append(valor)
        corpo.append(celulas)
    extra = [] if metrica == "hv" else ["$R$" if bruto else "$|P^*|$"]
    return ambiente(titulo, rotulo, "l" + "r" * (len(extra) + len(ALGORITMOS)),
                    ["Instância", *extra, *map(NOMES.get, ALGORITMOS)], corpo)


def gravar_tabelas(pasta, por_instancia, geral):
    nota = " Média e desvio das execuções; melhor em negrito; -- indica ausência de frente; * instância derivada."
    conteudo = {
        "hv": tabela_metrica(por_instancia, "hv", "Hipervolume na referência da campanha." + nota
                             + " Zero indica frente fora da caixa de referência.", "hv"),
        "participacao": tabela_metrica(por_instancia, "participacao",
                                       "Participação na melhor fronteira, $|F \\cap P^*|/|P^*|$." + nota, "participacao"),
        "rank_ponderado": tabela_metrica(por_instancia, "rank",
                                         "Rank ponderado $z$, de máximo $R$ em cada instância." + nota, "rank", bruto=True),
    }
    corpo = []
    for escopo, rotulo in (("nao_exatos", "Não exatos"), ("com_exato", "Com exato")):
        for metrica in METRICAS:
            linhas = [l for l in geral if (l["escopo"], l["porte"], l["metrica"]) == (escopo, "todos", metrica)]
            for l in sorted(linhas, key=lambda l: l["posicao_media"]):
                corpo.append([rotulo, TITULOS[metrica], NOMES[l["algoritmo"]], str(l["instancias"]),
                              f"{l['posicao_media']:.2f}", str(l["vitorias"]), str(l["empates_no_topo"]),
                              f"{l['razao_media_melhor']:.3f}"])
    conteudo["ranking_geral"] = ambiente(
        "Posição média (1 é a melhor), vitórias isoladas, empates no topo e razão média para o melhor.",
        "ranking", "lllrrrrr",
        ["Escopo", "Métrica", "Algoritmo", "Inst.", "Posição", "Vitórias", "Empates", "Razão"], corpo)
    for nome, texto in conteudo.items():
        (pasta / f"{nome}.tex").write_text(texto, encoding="utf-8")


# ------------------------------------------------------------------ figuras
def gravar_figuras(pasta, por_execucao, por_instancia, unioes, geral):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.ticker import PercentFormatter

    # `vert` foi descontinuado em 3.11; `orientation` só existe a partir de 3.10.
    horizontal = dict(vert=False) if matplotlib.__version_info__[:2] < (3, 10) else dict(orientation="horizontal")
    tinta, suave, grade = "#22252b", "#5c6370", "#e3e5e9"
    plt.rcParams.update({
        "font.size": 9, "text.color": tinta, "axes.labelcolor": suave, "xtick.color": suave, "ytick.color": tinta,
        "axes.edgecolor": grade, "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True,
    })
    nomes = [NOMES[a] for a in ALGORITMOS]
    instancias = [spec.path.stem for spec in INSTANCES]
    todos = {(l["metrica"], l["instancia"], l["algoritmo"]): l for l in por_instancia if l["escopo"] == "todos"}
    avisos = {
        "hv": "HV = 0: frente fora da caixa de referência, não ausência de solução. A referência publicada inclui o VNS original.",
        "participacao": "Sem fronteira exata (14 tarefas ou mais), P* é a melhor união observada, não um ótimo provado.",
        "rank": "z/R não penaliza frentes pequenas; compare junto com HV e participação.",
    }

    def salvar(fig, nome, titulo, nota):
        fig.suptitle(titulo, x=.01, ha="left", fontsize=13, fontweight="bold")
        fig.text(.01, .008, nota, color=suave, fontsize=8)
        fig.tight_layout(rect=(0, .03, 1, .98))
        fig.savefig(pasta / f"{nome}.png", dpi=160, facecolor="white")
        plt.close(fig)

    def paineis():
        fig, eixos = plt.subplots(3, 3, figsize=(12, 9.2), sharey=True)
        for eixo, instancia in zip(eixos.flat, instancias):
            eixo.set_title(nome_curto(instancia), loc="left", fontsize=10)
            eixo.grid(axis="x", color=grade, linewidth=.8)
            eixo.tick_params(length=0)
            eixo.set_yticks(range(len(ALGORITMOS)), nomes)
            eixo.set_ylim(len(ALGORITMOS) - .4, -.6)
        return fig, list(zip(eixos.flat, instancias))

    def barras(valores, formato):
        fig, grupos = paineis()
        for eixo, instancia in grupos:
            eixo.set_xlim(0, 1.18)
            eixo.set_xticks((0, .5, 1))
            eixo.xaxis.set_major_formatter(PercentFormatter(1))
            for y, a in enumerate(ALGORITMOS):
                valor = valores(instancia, a)
                if valor is not None:
                    eixo.barh(y, valor, height=.6, color=CORES[a])
                eixo.text((valor or 0) + .02, y, "— sem frente" if valor is None else formato(valor),
                          va="center", fontsize=8, color=suave if valor is None else tinta)
        return fig

    def percentual(v):
        return "<0.1%" if 0 < v < .0005 else f"{v:.1%}"

    azul = LinearSegmentedColormap.from_list("azul", ["#f3f8fe", "#86b6ef", "#2a78d6", "#0d366b"])
    for metrica, titulo in TITULOS.items():
        fig, eixo = plt.subplots(figsize=(9.5, 5.8))
        matriz = [[todos[metrica, i, a]["media"] for a in ALGORITMOS] for i in instancias]
        limite = max(v for linha in matriz for v in linha if v is not None)
        eixo.imshow([[0 if v is None else v for v in linha] for linha in matriz], cmap=azul, vmin=0, vmax=limite, aspect="auto")
        for y, linha in enumerate(matriz):
            for x, v in enumerate(linha):
                if v is None:
                    eixo.add_patch(plt.Rectangle((x - .5, y - .5), 1, 1, facecolor="#f1f1f1"))
                vence = todos[metrica, instancias[y], ALGORITMOS[x]]["vencedor"]
                eixo.text(x, y, "—" if v is None else f"{v:.3f}" + (" ★" if vence else ""), ha="center", va="center",
                          fontweight="bold" if vence else "normal", fontfamily="DejaVu Sans",
                          color="white" if v is not None and v / limite > .55 else tinta)
        eixo.set_xticks(range(len(ALGORITMOS)), nomes)
        eixo.set_yticks(range(len(instancias)), [nome_curto(i) for i in instancias])
        eixo.tick_params(length=0)
        eixo.set_xticks([x + .5 for x in range(len(ALGORITMOS) - 1)], minor=True)
        eixo.set_yticks([y + .5 for y in range(len(instancias) - 1)], minor=True)
        eixo.grid(which="minor", color="white", linewidth=2)
        eixo.tick_params(which="minor", length=0)
        for borda in eixo.spines.values():
            borda.set_visible(False)
        salvar(fig, f"heatmap_{metrica}", f"{titulo}: média por instância", f"★ melhor da instância; — sem frente. {avisos[metrica]}")

        fig = barras(lambda i, a, m=metrica: todos[m, i, a]["razao_melhor"], percentual)
        salvar(fig, f"proporcao_{metrica}", f"{titulo}: proporção em relação ao melhor da instância", avisos[metrica])

        fig, grupos = paineis()
        for eixo, instancia in grupos:
            for y, a in enumerate(ALGORITMOS):
                dados = [l[metrica] for l in por_execucao
                         if l["instancia"] == instancia and l["algoritmo"] == a and l[metrica] is not None]
                if len(dados) > 1:
                    caixa = eixo.boxplot(dados, positions=[y], **horizontal, widths=.55, patch_artist=True, manage_ticks=False,
                                         flierprops=dict(marker="o", markersize=3, markeredgecolor=CORES[a]),
                                         medianprops=dict(color=tinta, linewidth=1.5))
                    caixa["boxes"][0].set(facecolor=CORES[a], alpha=.65, edgecolor=CORES[a])
                elif dados:
                    eixo.plot(dados, [y], marker="D", markersize=8, color=CORES[a], clip_on=False)
                else:
                    eixo.text(.02, y, "— sem frente", transform=eixo.get_yaxis_transform(), va="center", fontsize=8, color=suave)
            eixo.margins(x=.04)
        salvar(fig, f"boxplot_{metrica}", f"{titulo}: distribuição das execuções",
               f"Caixas: 30 execuções. Losangos: método determinístico (1 execução). Escalas por instância. {avisos[metrica]}")

    parcelas = {(l["instancia"], l["algoritmo"]): l["participacao"] for l in unioes}
    fig = barras(lambda i, a: parcelas[i, a], percentual)
    salvar(fig, "composicao_fronteira", "Parcela da melhor fronteira (P*) encontrada pela união das execuções",
           "Pontos compartilhados contam para cada algoritmo; as parcelas podem somar mais de 100%. União de 30 execuções para as metaheurísticas.")

    fig, eixos = plt.subplots(2, 3, figsize=(12, 6.6), sharex=True)
    for linha, (escopo, rotulo) in enumerate((("nao_exatos", "5 não exatos, 9 instâncias"),
                                              ("com_exato", "6 algoritmos, 2 instâncias provadas"))):
        for eixo, metrica in zip(eixos[linha], METRICAS):
            itens = sorted((l for l in geral if (l["escopo"], l["porte"], l["metrica"]) == (escopo, "todos", metrica)),
                           key=lambda l: l["posicao_media"])
            for y, l in enumerate(itens):
                eixo.hlines(y, 1, l["posicao_media"], color=grade, linewidth=2)
                eixo.plot(l["posicao_media"], y, "o", markersize=9, color=CORES[l["algoritmo"]], clip_on=False)
                eixo.text(l["posicao_media"] + .18, y, f"{l['posicao_media']:.2f}", va="center", fontsize=8)
            eixo.set_yticks(range(len(itens)), [NOMES[l["algoritmo"]] for l in itens])
            eixo.set_ylim(len(itens) - .5, -.5)
            eixo.set_xlim(.8, 6.6)
            eixo.tick_params(length=0)
            eixo.set_title(f"{TITULOS[metrica]}\n{rotulo}", loc="left", fontsize=9.5)
    salvar(fig, "ranking_medio", "Posição média por métrica (1 é a melhor)",
           "Empates recebem a posição média. HV: as quatro metaheurísticas empatam em zero nas instâncias de 750 tarefas.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=DESTINO)
    destino = parser.parse_args().output_dir
    for pasta in (destino / "figuras", destino / "tabelas"):
        pasta.mkdir(parents=True, exist_ok=True)
    por_execucao, por_instancia, unioes = calcular()
    geral = ranking_geral(por_instancia)
    for nome, linhas in (("por_execucao", por_execucao), ("por_instancia", por_instancia),
                         ("ranking_geral", geral), ("uniao_30", unioes)):
        gravar_csv(destino / f"{nome}.csv", linhas)
    gravar_tabelas(destino / "tabelas", por_instancia, geral)
    gravar_figuras(destino / "figuras", por_execucao, por_instancia, unioes, geral)
    print(f"{len(por_execucao)} execuções interpretadas em {destino}")


if __name__ == "__main__":
    main()
