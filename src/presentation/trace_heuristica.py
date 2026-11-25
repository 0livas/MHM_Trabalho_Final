"""Captura as duas heurísticas na instância didática, sem alterar o código delas."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent / "heuristics" / "construtiva"),
                str(HERE.parent / "heuristics" / "ociosidade")]

from problem import read_instance  # noqa: E402
from schedule import evaluate_schedule  # noqa: E402
import construtiva  # noqa: E402
import ociosidade  # noqa: E402

ENTRADA = HERE / "data" / "didatica.dat"
EXATA = HERE / "data" / "didatica.json"
SAIDA = HERE / "data" / "trace_heuristica.json"
REGRA, ALFA = "lpt_min", .5             # construção mostrada sonda a sonda
REGRA_MODOS, ALFA_MODOS = "lpt_soma", .5   # partida mostrada no ajuste de modos e na ociosidade
INF = ociosidade.INF


def plano(instance, schedule):
    """Plano reavaliado por evaluate_schedule; aceita solução parcial.

    Numa solução parcial, avalia a instância restrita às tarefas já inseridas.
    """
    jobs = sorted(job for seq in schedule for job, _, _ in seq)
    novo = {job: k for k, job in enumerate(jobs)}
    parte = replace(instance, n=len(jobs), processing=tuple(instance.processing[j] for j in jobs),
                    setup=tuple(tuple(tuple(m[a][b] for b in jobs) for a in jobs) for m in instance.setup))
    local = tuple(tuple((novo[j], mode, wait) for j, mode, wait in seq) for seq in schedule)
    result = evaluate_schedule(parte, local)
    operations = {jobs[op.job]: op for op in result.operations}
    blocks = []
    for machine, seq in enumerate(schedule):
        previous = None
        for job, mode, wait in seq:
            op = operations[job]
            power = instance.power[machine] * instance.power_factor[mode] * 24 / instance.slots_per_day
            costs = [float(power * (instance.peak_rate if any(a <= t < b for a, b in instance.peaks)
                                    else instance.off_rate)) for t in range(op.start, op.end)]
            assert abs(sum(costs) - op.tec_units / result.tec_scale) < 1e-9
            blocks.append(dict(job=job, machine=machine, mode=mode, wait=wait, start=op.start, end=op.end,
                               setup=0 if previous is None else instance.setup[machine][previous][job],
                               costs=costs))
            previous = job
    return dict(cmax=result.cmax, tec=result.tec, blocks=blocks), result.objective_key


def sem_espera(maquinas):
    return tuple(tuple((job, mode, 0) for job, mode in seq) for seq in maquinas)


def capturar_construcao(instance, avaliador, alfa, regra):
    """Mesmo laço de ``construir``, guardando todas as sondas."""
    h, max_cost = instance.horizon, float(instance.max_cost) * avaliador.scale
    maquinas, fim, custo, passos = [[] for _ in range(instance.m)], [0] * instance.m, [0] * instance.m, []
    for job in construtiva.ordenar(instance, regra):
        total, best, sondas = sum(custo), None, []
        for machine in range(instance.m):
            others = max((fim[i] for i in range(instance.m) if i != machine), default=0)
            for mode in range(instance.modes):
                for position, end, cost in avaliador.insercoes(machine, maquinas[machine], (job, mode)):
                    if end > h:
                        continue
                    cmax, tec = max(end, others), total - custo[machine] + cost
                    key = (alfa * cmax / h + (1 - alfa) * tec / max_cost, end, tec)
                    start = 0
                    if position:
                        _, ends, _ = avaliador.linha_do_tempo(machine, maquinas[machine])
                        start = ends[position - 1] + instance.setup[machine][maquinas[machine][position - 1][0]][job]
                    sondas.append(dict(machine=machine, mode=mode, position=position, start=start,
                                       end=start + avaliador.duracao[job][machine][mode], cmax=cmax,
                                       tec=tec / avaliador.scale, tempo=alfa * cmax / h,
                                       energia=(1 - alfa) * tec / max_cost, f=key[0]))
                    if best is None or key < best[0]:
                        best = key, machine, mode, position, end, cost
                        escolha = len(sondas) - 1
        _, machine, mode, position, end, cost = best
        maquinas[machine].insert(position, (job, mode))
        fim[machine], custo[machine] = end, cost
        depois, chave = plano(instance, sem_espera(maquinas))
        assert chave == (max(fim), sum(custo))
        # A sonda vencedora precisa estar no lugar em que a tarefa ficou.
        bloco = next(b for b in depois["blocks"] if b["job"] == job)
        assert (bloco["start"], bloco["end"]) == (sondas[escolha]["start"], sondas[escolha]["end"])
        passos.append(dict(job=job, tamanho=len(maquinas[machine]) - 1, sondas=sondas, escolha=escolha, depois=depois))
    normal = construtiva.construir(avaliador, alfa, regra)
    assert normal.maquinas == maquinas and normal.objetivos == (max(fim), sum(custo))
    return dict(regra=regra, alfa=alfa, testadas=sum(len(p["sondas"]) for p in passos), passos=passos)


def capturar_ajuste(instance, avaliador, inicial):
    """Caminho real e, em cada passo, as trocas que economizam (mesma chave de ``ajustar_modos``)."""
    caminho, passos = construtiva.ajustar_modos(avaliador, inicial), []
    for k, s in enumerate(caminho):
        cmax, trocas = max(s.fim), []
        for machine, seq in enumerate(s.maquinas):
            others = max(t for i, t in enumerate(s.fim) if i != machine)
            for position, mode, end, cost in avaliador.trocas_de_modo(machine, seq):
                if cost < s.custo[machine] and end <= avaliador.horizonte:
                    aumento, economia = max(end, others) - cmax, s.custo[machine] - cost
                    trocas.append(((aumento <= 0, economia / aumento if aumento > 0 else economia, economia),
                                   dict(job=seq[position][0], mode=mode, machine=machine, aumento=aumento,
                                        economia=economia / avaliador.scale)))
        item = dict(plano=plano(instance, s.schedule())[0], trocas=[t for _, t in trocas], escolha=None)
        if k + 1 < len(caminho):
            item["escolha"] = max(range(len(trocas)), key=lambda i: (trocas[i][0], -i))
            troca, prox = trocas[item["escolha"]][1], caminho[k + 1]
            assert (troca["job"], troca["mode"]) in prox.maquinas[troca["machine"]]
            assert s.custo[troca["machine"]] - prox.custo[troca["machine"]] == round(troca["economia"] * avaliador.scale)
        else:
            assert not trocas
        passos.append(item)
    return passos


def capturar_curva(dados, machine, sequencia):
    """Recalcula f e g de cada tarefa e confere com os prefixos de ``programar_maquina``."""
    h, g, previous, tarefas = dados.horizonte, [0] * (dados.horizonte + 1), None, []
    for k, (job, _) in enumerate(sequencia):
        setup = 0 if previous is None else dados.setup[machine][previous][job]
        f, modo, parcela = [INF] * (h + 1), [-1] * (h + 1), [None] * (h + 1)
        for mode in range(dados.instance.modes):
            d = dados.duracao[job][machine][mode]
            on, off = dados.precos[machine][mode]
            for t in range(setup + d, h + 1):
                before, peak = g[t - d - setup], dados.acumulado[t] - dados.acumulado[t - d]
                if before + on * peak + off * (d - peak) < f[t]:
                    f[t], modo[t], parcela[t] = before + on * peak + off * (d - peak), mode, before
        g = [min(f[:t + 1]) for t in range(h + 1)]
        real = ociosidade.programar_maquina(dados, machine, sequencia[:k + 1])
        assert real.custo_ate == g and real.modo[k] == modo
        num = lambda v: None if v is None or v == INF else v / dados.scale  # noqa: E731
        tarefas.append(dict(job=job, setup=setup, modo=modo, f=[num(v) for v in f], g=[num(v) for v in g],
                            antes=[num(v) for v in parcela],
                            duracao=[dados.duracao[job][machine][o] for o in range(dados.instance.modes)]))
        previous = job
    return dict(machine=machine, tarefas=tarefas, custo_ate=tarefas[-1]["g"])


def capturar_soltura(instance, dados, inicial, frente):
    """Deslizamentos de um plano real, com a ordem e os modos mantidos."""
    ordem = inicial.schedule()

    def adiar(**esperas):
        return tuple(tuple((job, mode, esperas.get(f"T{job + 1}", 0)) for job, mode, _ in seq) for seq in ordem)
    casos = {nome: plano(instance, adiar(**esperas))[0] for nome, esperas in dict(
        antes={}, t2_na_ponta=dict(T2=2), t2_depois=dict(T2=7), t8=dict(T8=1), depois=dict(T8=1, T6=1)).items()}
    # O plano final é também o ponto de 16 h da frente de campanha.
    assert adiar(T8=1, T6=1) == next(p.schedule for p in frente if p.objetivos[0] == casos["depois"]["cmax"])
    return casos


def calcular():
    instance = read_instance(ENTRADA)
    avaliador = construtiva.Avaliador(instance)
    escala = avaliador.scale
    ordens = {r: construtiva.ordenar(instance, r) for r in construtiva.ORDENS}
    medidas = {r: [medida(instance, j) for j in range(instance.n)] for r, medida in construtiva.ORDENS.items()}

    construidas, linhas = [], []
    for regra in construtiva.ORDENS:
        for alfa in construtiva.pesos(11):
            s = construtiva.construir(avaliador, alfa, regra)
            construidas.append(s)
            p, chave = plano(instance, s.schedule())
            assert chave == s.objetivos
            linhas.append(dict(regra=regra, alfa=alfa, plano=p))
    distintas = {s.objetivos: s for s in reversed(construidas)}
    caminhos = []
    for inicial in sorted(distintas.values(), key=lambda s: s.objetivos):
        caminho = construtiva.ajustar_modos(avaliador, inicial)
        caminhos.append(dict(origem=inicial.origem, pontos=[[s.objetivos[0], s.objetivos[1] / escala] for s in caminho]))
    resultado = construtiva.executar(instance)
    assert resultado.construidas == len(linhas)
    assert resultado.ajustes == sum(len(c["pontos"]) for c in caminhos)
    frente_c = [dict(plano(instance, s.schedule())[0], origem=s.origem) for s in resultado.frente]

    inicial = construtiva.construir(avaliador, ALFA_MODOS, REGRA_MODOS)
    ajuste = capturar_ajuste(instance, avaliador, inicial)
    dados = ociosidade.Dados(instance)
    livre, fixo = ociosidade.executar(instance), ociosidade.executar(instance, modos_fixos=True)
    base = tuple(tuple(seq) for seq in inicial.maquinas)
    curvas = [capturar_curva(dados, m, seq) for m, seq in enumerate(base)]
    soma, last = [], INF
    for e in range(instance.horizon + 1):
        partes = [c["custo_ate"][e] for c in curvas]
        total = None if None in partes else sum(partes)
        soma.append(dict(epsilon=e, partes=partes, total=total, novo=total is not None and total < last))
        last = total if soma[-1]["novo"] else last
    real = [[p.objetivos[0], p.objetivos[1] / escala] for p in ociosidade.fronteira_da_base(dados, base, "")]
    assert [p[0] for p in real] == [s["epsilon"] for s in soma if s["novo"]]
    assert all(abs(p[1] - s["total"]) < 1e-9 for p, s in zip(real, (s for s in soma if s["novo"])))

    def frente_o(r):
        itens = []
        for p in r.frente:
            item, chave = plano(instance, p.schedule)
            assert chave == p.objetivos
            itens.append(dict(item, origem=p.origem))
        return itens
    exata = [[p["cmax"], p["tec"]] for p in json.loads(EXATA.read_text(encoding="utf-8"))["front"]]
    frente_livre = frente_o(livre)
    tabela = []
    for cmax, tec in exata:
        nosso = next((p["tec"] for p in frente_livre if p["cmax"] == cmax), None)
        tabela.append(dict(cmax=cmax, exata=tec, ociosidade=nosso,
                           lacuna=None if nosso is None else round(nosso - tec, 6)))
    plano3 = next(s for s in construtiva.ajustar_modos(avaliador, inicial)
                  if s.objetivos == (15, round(568.8 * escala)))
    return dict(
        sha256=instance.digest, horizon=instance.horizon, versao_python=platform.python_version().rsplit(".", 1)[0],
        seed=None, parametros=dict(pesos=11, ordens=list(construtiva.ORDENS), bases="construtiva", modos="livres"),
        ordens=ordens, medidas=medidas,
        construcao=capturar_construcao(instance, avaliador, ALFA, REGRA),
        construcoes=linhas, objetivos_distintos=len(distintas),
        caminhos=caminhos, solucoes_ajuste=resultado.ajustes, ajuste=dict(origem=inicial.origem, passos=ajuste),
        frente_construtiva=frente_c, soltura=capturar_soltura(instance, dados, plano3, livre.frente),
        base=[list(map(list, seq)) for seq in base], curvas=curvas, soma=soma,
        sequencias=livre.bases, frente_ociosidade=frente_livre,
        variante_modos_fixos=dict(aviso="variante modos_fixos=True, fora da campanha", sequencias=fixo.bases,
                                  frente=[[p.objetivos[0], p.objetivos[1] / escala] for p in fixo.frente]),
        exata=exata, confronto=tabela)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Recalcula e compara com o JSON salvo.")
    args = parser.parse_args()
    data = json.loads(json.dumps(calcular()))
    if args.check:
        if json.loads(SAIDA.read_text(encoding="utf-8")) != data:
            raise SystemExit("trace_heuristica.json diverge da execução.")
        print("trace confere")
    else:
        SAIDA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("sondas", data["construcao"]["testadas"], "distintos", data["objetivos_distintos"],
          "ajustes", data["solucoes_ajuste"], data["confronto"])


if __name__ == "__main__":
    main()
