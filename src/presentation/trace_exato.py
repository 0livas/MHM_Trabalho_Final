"""Captura, em memória, a programação dinâmica da instância didática. Não publica baseline."""

import argparse
from bisect import bisect_right
from hashlib import sha256
import json
from pathlib import Path
import platform
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE.parent), str(HERE.parent / "exact_methods")]

from problem import read_instance  # noqa: E402
from schedule import ScheduleValidationError, evaluate_schedule, schedule_from_result_rows  # noqa: E402
import custom_exact_dp as dp_module  # noqa: E402
from cenario import plano  # noqa: E402

ENTRADA = HERE / "data" / "didatica.dat"
SAIDA = HERE / "data" / "trace_exato.json"
SEED = 7
PASSO = 32              # uma partícula a cada 32 transições
EPSILON_PARTICAO = 12
CMAX_NUVEM, TEC_NUVEM = 20, 900     # limites dos planos sorteados da abertura
REAL = ROOT / "data" / "input" / "set1" / "6_2_1439_3_S_1-9.dat"
FONTES = ("src/problem.py", "src/schedule.py", "src/exact_methods/custom_exact_dp.py",
          "src/presentation/cenario.py", "src/presentation/data/didatica.dat",
          "data/input/set1/6_2_1439_3_S_1-9.dat")


def digest(path):
    return sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def estaveis(stats):
    return {k: v for k, v in stats.items() if k != "preparation_seconds"}


def tabela(dp):
    """Fronteiras fundidas em forma comparável, com a cadeia de ponteiros."""
    return [[[(l.end, l.energy, l.job, l.index, cadeia(dp, l)) for l in front] for front in machine]
            for machine in dp.frontiers]


def cadeia(dp, label):
    rows = []
    while label.job >= 0:
        c = dp.choices[label.job][label.index]
        rows.append((label.job, c.mode, c.start, c.end))
        label = label.previous
    return tuple(reversed(rows))


class Captura:
    """Embrulha insert_label; chamadas da fusão final reapresentam rótulos já vistos."""

    def __init__(self, dp):
        self.dp, self.original = dp, dp_module.insert_label
        self.eventos, self.vistos = [], {}
        self.fusoes = 0

    def __call__(self, front, candidate):
        antes = list(front)
        aceito = self.original(front, candidate)
        if id(candidate) in self.vistos or candidate.job < 0:
            self.fusoes += 1
            return aceito
        k = len(self.eventos)
        # Guardar o próprio rótulo impede que o id seja reaproveitado.
        self.vistos[id(candidate)] = k
        vivos = {id(l) for l in front}
        mortos = [l for l in antes if id(l) not in vivos]
        self.eventos.append(dict(label=candidate, aceito=aceito, morre=None, por=None))
        if not aceito:
            testemunha = [l for l in antes if l.end <= candidate.end and l.energy <= candidate.energy][-1]
            self.eventos[k]["por"] = testemunha
        for l in mortos:
            alvo = self.eventos[self.vistos[id(l)]]
            alvo["morre"], alvo["por"] = k, candidate
        return aceito


def subconjunto(label):
    s = 0
    while label.job >= 0:
        s |= 1 << label.job
        label = label.previous
    return s


def maquina_de(dp, label):
    return dp.choices[label.job][label.index].machine


def resumo(instance, dp, label):
    """Plano parcial de uma máquina, com custo conferido intervalo a intervalo."""
    machine = maquina_de(dp, label)
    blocos, anterior, fim, total = [], None, 0, 0.0
    for job, mode, start, end in cadeia(dp, label):
        setup = 0 if anterior is None else instance.setup[machine][anterior][job]
        power = instance.power[machine] * instance.power_factor[mode] * 24 / instance.slots_per_day
        costs = [float(power * (instance.peak_rate if any(a <= t < b for a, b in instance.peaks)
                                else instance.off_rate)) for t in range(start, end)]
        assert start >= fim + setup
        blocos.append(dict(job=job, machine=machine, mode=mode, setup=setup, wait=start - fim - setup,
                           start=start, end=end, costs=costs))
        anterior, fim, total = job, end, total + sum(costs)
    assert fim == label.end and abs(total - label.energy / dp.scale) < 1e-9
    return dict(end=label.end, energy=label.energy / dp.scale, blocks=blocos)


def embaralhar(instance, inicio):
    """Passeio aleatório por realocações, trocas e mudanças de modo, reavaliado pelo projeto."""
    rng = random.Random(SEED)
    atual = [list(map(tuple, seq)) for seq in
             schedule_from_result_rows(instance, [dict(b) for b in inicio["blocks"]])]
    passos, tentativas = [], 0
    while len(passos) < 40:
        tentativas += 1
        op = ("realocar", "trocar", "modo")[len(passos) % 3]
        novo = [list(seq) for seq in atual]
        a = rng.choice([i for i, s in enumerate(novo) if s])
        p = rng.randrange(len(novo[a]))
        job, mode, wait = novo[a][p]
        if op == "modo":
            novo[a][p] = job, rng.choice([x for x in range(instance.modes) if x != mode]), wait
        elif op == "realocar":
            b = rng.choice([x for x in range(instance.m) if x != a])
            novo[a].pop(p)
            novo[b].insert(rng.randint(0, len(novo[b])), (job, mode, wait))
        else:
            b = rng.choice([x for x in range(instance.m) if x != a and novo[x]] or [a])
            q = rng.randrange(len(novo[b]))
            if a == b:
                continue
            novo[a][p], novo[b][q] = novo[b][q], novo[a][p]
        schedule = tuple(tuple(s) for s in novo)
        try:
            r = evaluate_schedule(instance, schedule)
        except ScheduleValidationError:
            continue
        if r.cmax > CMAX_NUVEM or r.tec > TEC_NUVEM:
            continue
        rows = [dict(job=o.job, machine=o.machine, mode=o.mode, start=o.start, end=o.end) for o in r.operations]
        passos.append(dict(op=op, **plano(instance, rows)))
        atual = novo
    return passos, tentativas


def particoes(instance, dp, epsilon):
    """Melhoras sucessivas do laço de nível superior de solve(): conjunto dado à M3."""
    options = [[dp_module.best_before(front, epsilon) for front in table] for table in dp.frontiers]
    full = (1 << instance.n) - 1

    def dois(resto):
        best = None
        assigned = resto
        while True:
            a, b = options[0][resto ^ assigned], options[1][assigned]
            if a is not None and b is not None:
                cand = (a.energy + b.energy, max(a.end, b.end))
                if best is None or cand < best[0]:
                    best = cand, assigned
            if assigned == 0:
                return best
            assigned = (assigned - 1) & resto
    melhoras, exames, best, examinados, assigned = [], [], None, 0, full
    while True:
        examinados += 1
        label, par = options[2][assigned], dois(full ^ assigned)
        if label is not None and par is not None:
            cand = par[0][0] + label.energy, max(par[0][1], label.end)
            if best is None or cand < best:
                best = cand
                sets = [full ^ assigned ^ par[1], par[1], assigned]
                melhoras.append(dict(
                    ordem=examinados, total=cand[0] / dp.scale, cmax=cand[1],
                    maquinas=[dict(jobs=[j for j in range(instance.n) if s >> j & 1],
                                   energy=options[m][s].energy / dp.scale, end=options[m][s].end,
                                   curva=[[l.end, l.energy / dp.scale] for l in dp.frontiers[m][s]])
                              for m, s in enumerate(sets)]))
        exames.append(None if label is None or par is None else (par[0][0] + label.energy) / dp.scale)
        if assigned == 0:
            break
        assigned = (assigned - 1) & full
    return melhoras, exames


def final_total(melhoras):
    return melhoras[-1]["total"]


def tentativa(instance, dp, epsilon, conjuntos):
    """Uma partição qualquer avaliada nas tabelas; None quando nenhum rótulo termina até epsilon."""
    maquinas = []
    for m, jobs in enumerate(conjuntos):
        front = dp.frontiers[m][sum(1 << j for j in jobs)]
        label = dp_module.best_before(front, epsilon)
        maquinas.append(dict(jobs=sorted(jobs), curva=[[l.end, l.energy / dp.scale] for l in front],
                             energy=None if label is None else label.energy / dp.scale,
                             end=None if label is None else label.end))
    ok = all(m["energy"] is not None for m in maquinas)
    return dict(total=sum(m["energy"] for m in maquinas) if ok else None, maquinas=maquinas)


def calcular():
    instance = read_instance(ENTRADA)
    didatica = json.loads((HERE / "data" / "didatica.json").read_text(encoding="utf-8"))
    assert didatica["sha256"] == instance.digest

    normal = dp_module.EnergyDP(instance)
    assert normal.prepare()
    dp = dp_module.EnergyDP(instance)
    captura = Captura(dp)
    dp_module.insert_label = captura
    try:
        assert dp.prepare()
    finally:
        dp_module.insert_label = captura.original
    # A instrumentação precisa ser invisível.
    assert estaveis(dp.stats) == estaveis(normal.stats)
    assert tabela(dp) == tabela(normal)
    ev = captura.eventos
    assert len(ev) == dp.stats["transitions"]
    assert sum(e["aceito"] for e in ev) == dp.stats["inserted_labels"]
    assert sum(not e["aceito"] for e in ev) == dp.stats["rejected_labels"]
    assert sum(e["aceito"] and e["morre"] is not None for e in ev) == dp.stats["removed_labels"]

    minimo = dp_module.minimum_makespan(instance)["minimum_makespan"]
    varredura, vistos = [], set()
    for epsilon in range(minimo, instance.horizon + 1):
        resposta = dp.solve(epsilon)
        assert resposta == normal.solve(epsilon)
        point, indices = resposta
        rows = [dict(job=j, machine=c.machine, mode=c.mode, start=c.start, end=c.end)
                for j, c in enumerate(dp.choices[j][k] for j, k in enumerate(indices))]
        p = plano(instance, rows)
        assert p["cmax"] == point[0] and abs(p["tec"] - point[1] / dp.scale) < 1e-9
        varredura.append(dict(epsilon=epsilon, novo=point not in vistos, **p))
        vistos.add(point)
    assert [(p["cmax"], p["tec"]) for p in varredura if p["novo"]] == [
        (p["cmax"], p["tec"]) for p in didatica["front"]]

    # Exemplo da M3: T6, T1 e extensão pela T7 (modos 0 rápido, 1 normal, 2 econômico).
    por_cadeia = {(maquina_de(dp, e["label"]), cadeia(dp, e["label"])): e for e in ev}
    def achar(*linhas):
        return por_cadeia[2, linhas]
    base = achar((5, 1, 0, 2), (0, 1, 3, 6))
    assert base["aceito"]
    inicio = base["label"].end + instance.setup[2][0][6]
    modos = []
    for mode in range(instance.modes):
        dur = instance.duration(6, 2, mode)
        ks = [k for k, c in enumerate(dp.choices[6]) if c.machine == 2 and c.mode == mode]
        custos = [dp.choices[6][k].cost_units for k in ks]
        salto = dp_module.next_cheaper(custos)
        s, inicios = inicio, []
        while s < len(ks):
            inicios.append(s)
            s = salto[s]
        fichas = []
        for s in inicios:
            e = achar((5, 1, 0, 2), (0, 1, 3, 6), (6, mode, s, s + dur))
            fichas.append(dict(resumo(instance, dp, e["label"]), start=s, aceito=e["aceito"],
                               removido=e["morre"] is not None))
        modos.append(dict(mode=mode, duracao=dur, inicios=inicios, fichas=fichas,
                          custos=[[s, custos[s] / dp.scale] for s in range(inicio, 14)]))

    vence = achar((5, 1, 0, 2), (0, 1, 3, 6), (6, 1, 7, 11))
    perde = achar((0, 1, 0, 3), (5, 1, 5, 7), (6, 1, 8, 12))
    assert perde["aceito"] and perde["por"] is vence["label"]
    # A mesma continuação, nos mesmos instantes, vale para as duas histórias.
    job, mode = 2, 1
    start = perde["label"].end + instance.setup[2][6][job]
    c = dp.choices[job][dp.lookup[job][2, mode, start]]
    continuar = {}
    for nome, e in (("vence", vence), ("perde", perde)):
        novo = dp_module.Label(c.end, e["label"].energy + c.cost_units, job, dp.lookup[job][2, mode, start], e["label"])
        continuar[nome] = dict(resumo(instance, dp, novo))
    duelo = dict(vence=resumo(instance, dp, vence["label"]), perde=resumo(instance, dp, perde["label"]),
                 continua=continuar, evento="a perdedora entrou antes e foi removida quando a vencedora chegou")

    # Mesmo subconjunto {T1, T6}, últimas diferentes: um dominaria o outro se fossem comparados.
    outra = achar((0, 1, 0, 3), (5, 1, 5, 7))
    assert outra["aceito"] and base["label"].end < outra["label"].end and base["label"].energy <= outra["label"].energy
    real = read_instance(REAL)
    assert real.slots_per_day == 1440
    gavetas = dict(instancia=REAL.name, maquina=0, fichas=[resumo(instance, dp, base["label"]), resumo(instance, dp, outra["label"])],
                   proxima=3, unidade="min",
                   ultimas=[[j, real.setup[0][j][3]] for j in (0, 2)],
                   nota="na instância didática o setup depende só da tarefa seguinte")
    assert all(len({instance.setup[m][i][j] for i in range(8) if i != j}) == 1 for m in range(3) for j in range(8))

    chuva = []
    for k in range(0, len(ev), PASSO):
        e = ev[k]
        l = e["label"]
        chuva.append([maquina_de(dp, l), subconjunto(l), l.job, l.end, l.energy / dp.scale,
                      int(e["aceito"]), -1 if e["morre"] is None else e["morre"]])
    # Estado dos contadores ao fim de cada máquina.
    por_maquina = []
    for m in range(3):
        grupo = [e for e in ev if maquina_de(dp, e["label"]) == m]
        por_maquina.append(dict(
            transicoes=len(grupo), recusas=sum(not e["aceito"] for e in grupo),
            insercoes=sum(e["aceito"] for e in grupo),
            removidos=sum(e["aceito"] and e["morre"] is not None for e in grupo),
            antes_fusao=dp.stats["machine_state_labels"][m],
            apos_fusao=sum(len(f) for f in dp.frontiers[m])))
    contadores = []
    acum = [0, 0, 0]
    mortes = sorted(e["morre"] for e in ev if e["aceito"] and e["morre"] is not None)
    for k, e in enumerate(ev):
        acum[0] += 1
        acum[1] += not e["aceito"]
        acum[2] += e["aceito"]
        if k % (PASSO * 8) == 0 or k == len(ev) - 1:
            contadores.append([*acum, bisect_right(mortes, k)])
    assert sum(p["apos_fusao"] for p in por_maquina) == dp.stats["retained_subset_labels"]

    melhoras, exames = particoes(instance, dp, EPSILON_PARTICAO)
    barata = varredura[-1]
    tentativas_particao = [
        tentativa(instance, dp, EPSILON_PARTICAO, [[], [], list(range(8))]),
        tentativa(instance, dp, EPSILON_PARTICAO,
                  [[b["job"] for b in barata["blocks"] if b["machine"] == m] for m in range(3)]),
        *(tentativa(instance, dp, EPSILON_PARTICAO, [x["jobs"] for x in row["maquinas"]]) for row in melhoras)]
    assert abs(tentativas_particao[-1]["total"] - final_total(melhoras)) < 1e-9
    final, alvo = melhoras[-1], varredura[EPSILON_PARTICAO - minimo]
    assert abs(final["total"] - alvo["tec"]) < 1e-9 and final["cmax"] == alvo["cmax"]
    for m, row in enumerate(final["maquinas"]):
        assert row["jobs"] == sorted(b["job"] for b in alvo["blocks"] if b["machine"] == m)

    passos, tentativas = embaralhar(instance, next(p for p in didatica["front"] if p["cmax"] == 15))
    baselines = []
    for path in sorted((ROOT / "data" / "baselines").glob("*_custom_exact_dp.json")):
        b = json.loads(path.read_text(encoding="utf-8"))
        assert b["status"] == "complete" and b["pareto_proven"]
        baselines.append(dict(arquivo=path.name, n=int(path.name.split("_")[0]), pontos=len(b["front"])))
    baselines.sort(key=lambda b: (b["n"], b["pontos"]))
    campanha = []
    for path in sorted((ROOT / "data/output/experiments/runs/exact_dp").glob("*/run_01.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        campanha.append(dict(instancia=r["instance"], status=r["status"], motivo=r["stop_reason"],
                             max_jobs=r["parameters"]["max_jobs"]))
    assert {r["max_jobs"] for r in campanha} == {13}
    assert any("exceeds_max_jobs (14 > 13)" in r["motivo"] for r in campanha)
    return dict(
        escopo="instância didática, método de referência em memória, sem publicar baseline",
        versoes=dict(python=platform.python_version()), seed=SEED,
        parametros=dict(passo_amostragem=PASSO, epsilon_particao=EPSILON_PARTICAO, cmax_nuvem=CMAX_NUVEM,
                        tec_nuvem=TEC_NUVEM, horizonte=instance.horizon, max_jobs=dp_module.DEFAULT_MAX_JOBS),
        sha256=instance.digest, fontes={f: digest(f) for f in FONTES},
        instrumentada_igual_a_normal=True,
        contagem=dict(opcoes_por_tarefa=instance.m * instance.modes, tarefas=instance.n,
                      total=(instance.m * instance.modes) ** instance.n,
                      o_que_conta="pares máquina × modo por tarefa, sem ordem nem espera"),
        stats=estaveis(dp.stats), por_maquina=por_maquina, contadores=contadores,
        embaralho=dict(tentativas=tentativas, passos=passos),
        rotulo=dict(base=resumo(instance, dp, base["label"]), tarefa=6, inicio=inicio, modos=modos),
        duelo=duelo, gavetas=gavetas, chuva=chuva,
        particao=dict(epsilon=EPSILON_PARTICAO, exames=exames, viaveis=sum(x is not None for x in exames),
                      particoes_possiveis=instance.m ** instance.n, melhoras=melhoras,
                      tentativas=tentativas_particao),
        varredura=varredura, conjuntos=[[n, 2 ** n] for n in range(6, 14)],
        baselines=baselines, campanha=campanha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Recalcula e compara com o JSON salvo.")
    args = parser.parse_args()
    dados = calcular()
    if args.check:
        # As tuplas do cálculo viram listas no JSON.
        salvo = json.loads(SAIDA.read_text(encoding="utf-8"))
        if salvo != json.loads(json.dumps(dados)):
            raise SystemExit("trace_exato.json diverge do cálculo atual.")
        print("Trace verificado.")
    else:
        SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(dados["stats"], len(dados["chuva"]), len(dados["particao"]["melhoras"]))


if __name__ == "__main__":
    main()
