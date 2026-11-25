"""Dados reais do VNS/VND: replay da construção (vns_trace.json) e demonstração animada (trace_vns.json)."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import platform
from pathlib import Path
import random
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from metaheuristics import vns_vnd, vns_vnd_original
from problem import dominates, read_instance
from schedule import ScheduleValidationError, evaluate_schedule


INSTANCE = Path("data/input/set2/750_10_1439_5_S_1-9.dat")
OUTPUT = HERE / "data" / "vns_trace.json"
SEED = 1001


def observe_constructor(instance, constructor):
    """Captura o estado no retorno da função sem alterar a implementação ou o RNG."""
    snapshot = {}

    def on_return(frame, event, _value):
        if event == "return":
            state = frame.f_locals
            snapshot.update(
                machine_ends=list(state["machine_end"]),
                jobs_per_machine=[len(jobs) for jobs in state["machine_jobs"]],
                last_jobs=list(state["machine_last"]),
                final_job=state["job"],
            )
        return on_return

    def on_call(frame, event, _value):
        if event == "call" and frame.f_code is constructor.__code__:
            frame.f_trace_lines = False
            return on_return
        return None

    previous_trace = sys.gettrace()
    sys.settrace(on_call)
    try:
        schedule = constructor(instance, random.Random(SEED))
    finally:
        sys.settrace(previous_trace)

    ends = snapshot["machine_ends"]
    counts = snapshot["jobs_per_machine"]
    assigned = sum(counts)
    blocked_job = minimum_end = ends_by_machine = makespan = None

    if schedule is None:
        blocked_job = snapshot["final_job"]
        ends_by_machine = []
        for machine, (end, prior) in enumerate(zip(ends, snapshot["last_jobs"], strict=True)):
            setup = instance.setup[machine][prior][blocked_job] if prior is not None else 0
            best_duration = min(
                instance.duration(blocked_job, machine, mode) for mode in range(instance.modes)
            )
            ends_by_machine.append(end + setup + best_duration)
        minimum_end = min(ends_by_machine)
        if not (assigned < instance.n and minimum_end > instance.horizon):
            raise RuntimeError("A construção interrompida não coincide com o diagnóstico de horizonte")
    else:
        evaluation = evaluate_schedule(instance, schedule)
        makespan = evaluation.cmax
        verified_ends = [0] * instance.m
        for operation in evaluation.operations:
            verified_ends[operation.machine] = max(verified_ends[operation.machine], operation.end)
        if assigned != instance.n or ends != verified_ends or makespan != max(ends):
            raise RuntimeError("O estado capturado difere do escalonamento validado")

    return {
        "assigned": assigned,
        "machine_ends": ends,
        "jobs_per_machine": counts,
        "completed": schedule is not None,
        "blocked_job_zero_based": blocked_job,
        "minimum_candidate_end": minimum_end,
        "minimum_candidate_ends_by_machine": ends_by_machine,
        "makespan": makespan,
    }


def build_trace():
    instance = read_instance(ROOT / INSTANCE)
    sources = (INSTANCE, Path("src/problem.py"), Path("src/schedule.py"),
               Path("src/metaheuristics/vns_vnd_original.py"), Path("src/metaheuristics/vns_vnd.py"))
    return {
        "scope": "primeira construção por versão, sem busca VNS/VND e fora da campanha experimental",
        "instance": INSTANCE.name,
        "seed": SEED,
        "construction": 1,
        "jobs": instance.n,
        "machines": instance.m,
        "modes": instance.modes,
        "days": instance.days,
        "slots_per_day": instance.slots_per_day,
        "horizon": instance.horizon,
        "peak_intervals": [list(interval) for interval in instance.peaks],
        "original": observe_constructor(instance, vns_vnd_original._random_greedy_schedule),
        "revised": observe_constructor(instance, vns_vnd._random_greedy_schedule),
        "source_sha256_lf": {
            source.as_posix(): sha256((ROOT / source).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for source in sources
        },
    }


# --- Demonstração do deck "vns" -------------------------------------------------------

DIDATICA = HERE / "data" / "didatica.dat"
DEMO = HERE / "data" / "trace_vns.json"
CAMPANHA = ROOT / "data" / "output" / "experiments_vns_new" / "runs" / "vns_vnd"
# Seed escolhida por conter, em ordem, um shake N2 com inviável e três melhorias
# seguidas vindas de portas altas. O orçamento termina junto com essa descida.
DEMO_CONFIG = dict(seed=6653, max_evaluations=1532, initial_solutions=4,
                   max_candidates_per_neighborhood=25, shaking_attempts=20)


class Sorteio(random.Random):
    """Anota os sorteios da construção sem consumir números adicionais."""

    def __init__(self, seed):
        super().__init__(seed)
        self.notas = []

    def randrange(self, *args):
        valor = super().randrange(*args)
        self.notas.append(("janela", args[0], valor))
        return valor

    def choice(self, seq):
        valor = super().choice(seq)
        self.notas.append(("escolha", list(seq), valor))
        return valor


class Gravador(vns_vnd.VNSVND):
    """Guarda o escalonamento de cada avaliação e os limites de cada fase."""

    def __init__(self, instance, config):
        super().__init__(instance, config)
        self.rng = Sorteio(config.seed)
        self.registro, self.fases = [], []

    def _evaluate(self, schedule):
        antes = self.evaluations
        solution = super()._evaluate(schedule)
        if self.evaluations > antes:
            evento = self.trace[-1]
            self.registro.append(dict(
                schedule=schedule, key=solution.key if solution else None,
                inserted=bool(solution) and evento["archive_inserted"],
                reason=None if solution else evento["reason"],
                archive=[point for point, _ in self.archive]))
        return solution

    def _fase(self, tipo, inicio, trace):
        self.fases.append(dict(tipo=tipo, de=inicio + 1, ate=self.evaluations, trace=[trace, len(self.trace)]))

    def _shake(self, origin, neighborhood):
        inicio, trace = self.evaluations, len(self.trace)
        resultado = super()._shake(origin, neighborhood)
        self._fase("shake", inicio, trace)
        self.fases[-1].update(vizinhanca=neighborhood, origem=list(origin.key), expandiu=resultado[1])
        return resultado

    def _vnd(self, initial):
        inicio, trace = self.evaluations, len(self.trace)
        resultado = super()._vnd(initial)
        self._fase("vnd", inicio, trace)
        self.fases[-1].update(inicial=list(initial.key), expandiu=resultado[1])
        return resultado


def plano_demo(instance, schedule):
    """Decodifica sem validar o horizonte: serve também para o plano rejeitado."""
    blocks = []
    for machine, sequence in enumerate(schedule):
        previous, clock = None, 0
        for job, mode, wait in sequence:
            setup = 0 if previous is None else instance.setup[machine][previous][job]
            start = clock + setup + wait
            end = start + instance.duration(job, machine, mode)
            power = instance.power[machine] * instance.power_factor[mode] * 24 / instance.slots_per_day
            costs = [float(power * (instance.peak_rate if any(a <= t < b for a, b in instance.peaks)
                                    else instance.off_rate)) for t in range(start, end)]
            blocks.append(dict(job=job, machine=machine, mode=mode, setup=setup, wait=wait,
                               start=start, end=end, costs=costs))
            previous, clock = job, end
    row = dict(blocks=blocks, viavel=True)
    try:
        result = evaluate_schedule(instance, schedule)
    except ScheduleValidationError as error:
        return row | dict(viavel=False, motivo=str(error), cmax=max(b["end"] for b in blocks), tec=None)
    by_job = {op.job: op for op in result.operations}
    for b in blocks:
        op = by_job[b["job"]]
        assert (op.start, op.end, op.machine) == (b["start"], b["end"], b["machine"])
        assert abs(sum(b["costs"]) - op.tec_units / result.tec_scale) < 1e-9
    return row | dict(cmax=result.cmax, tec=result.tec)


def movimento(antes, depois):
    """Identifica a operação pelo par de escalonamentos."""
    onde = [{job: (m, p) for m, seq in enumerate(s) for p, (job, *_) in enumerate(seq)} for s in (antes, depois)]
    dados = [{job: (mode, wait) for seq in s for job, mode, wait in seq} for s in (antes, depois)]
    mudou = [j for j in dados[0] if dados[0][j] != dados[1][j]]
    if mudou:
        (job,) = mudou
        (m0, w0), (m1, w1) = dados[0][job], dados[1][job]
        if m0 != m1:
            return dict(tipo="modo", tarefas=[job], de=m0, para=m1)
        return dict(tipo="espera", tarefas=[job], de=w0, para=w1)
    outra = [j for j in onde[0] if onde[0][j][0] != onde[1][j][0]]
    if len(outra) == 1:
        return dict(tipo="realocar", tarefas=outra, de=list(onde[0][outra[0]]), para=list(onde[1][outra[0]]))
    if len(outra) == 2:
        return dict(tipo="trocar", tarefas=outra)
    # Mesma máquina: N3 ou N5; em tarefas adjacentes as duas operações coincidem.
    moveu = [j for j in onde[0] if onde[0][j] != onde[1][j]]
    if not moveu:
        return dict(tipo="nenhum", tarefas=[])
    m = onde[0][moveu[0]][0]
    for j in moveu:
        resto = [[x[0] for x in s[m] if x[0] != j] for s in (antes, depois)]
        if resto[0] == resto[1]:
            return dict(tipo="inserir", tarefas=[j], de=onde[0][j][1], para=onde[1][j][1])
    return dict(tipo="trocar", tarefas=moveu)


def construcoes(instance, notas, quantidade):
    """Refaz cada construção a partir dos sorteios anotados e confere as opções."""
    dificuldade = [min(instance.duration(j, m, k) for m in range(instance.m) for k in range(instance.modes))
                   for j in range(instance.n)]
    partidas = []
    fila_notas = iter(notas)
    for _ in range(quantidade):
        restantes = sorted(range(instance.n), key=lambda j: (-dificuldade[j], j))
        fim, ultimo, passos = [0] * instance.m, [None] * instance.m, []
        while restantes:
            tipo, janela, indice = next(fila_notas)
            assert tipo == "janela" and indice < janela
            fila, job = list(restantes), restantes.pop(indice)
            opcoes = []
            for m in range(instance.m):
                setup = instance.setup[m][ultimo[m]][job] if ultimo[m] is not None else 0
                for k in range(instance.modes):
                    end = fim[m] + setup + instance.duration(job, m, k)
                    if end <= instance.horizon:
                        opcoes.append((end, m, k))
            empate = [o for o in opcoes if o[0] == min(opcoes)[0]]
            tipo, lista, (end, m, k) = next(fila_notas)
            assert tipo == "escolha" and lista == empate
            setup = instance.setup[m][ultimo[m]][job] if ultimo[m] is not None else 0
            passos.append(dict(fila=fila, janela=janela, indice=indice, job=job, opcoes=[list(o) for o in opcoes],
                               empates=len(empate), maquina=m, modo=k, fim=end, inicio=fim[m] + setup, setup=setup))
            fim[m], ultimo[m] = end, job
        partidas.append(passos)
    return dificuldade, partidas


def visitas(gravador, fase):
    """Quebra um VND em visitas a portas, com os candidatos examinados em cada uma."""
    n, portas = fase["de"] - 1, []
    for evento in gravador.trace[slice(*fase["trace"])]:
        if evento["event"] == "vnd_neighborhood":
            portas.append(dict(porta=vns_vnd.NEIGHBORHOODS.index(evento["name"]), candidatos=[], aceito=None))
        elif evento["event"] in ("evaluation", "rejected"):
            n += 1
            portas[-1]["candidatos"].append(n)
        elif evento["event"] == "vnd_accept":
            portas[-1]["aceito"] = n
    assert n == fase["ate"]
    atual = fase["de"] - 1
    for visita in portas:
        visita["corrente"] = atual
        atual = visita["aceito"] or atual
    return portas


def campanha():
    distintos, total = set(), 0
    for path in sorted(CAMPANHA.glob("*/run_*.json")):
        distintos.add(json.dumps(json.loads(path.read_text(encoding="utf-8"))["parameters"], sort_keys=True))
        total += 1
    (unico,) = distintos
    return dict(fonte=CAMPANHA.relative_to(ROOT).as_posix(), execucoes=total, parametros=json.loads(unico))


def montar_demo():
    instance = read_instance(DIDATICA)
    config = vns_vnd.VNSConfig(**DEMO_CONFIG)
    gravador = Gravador(instance, config)
    result = gravador.run()
    normal = vns_vnd.VNSVND(instance, config).run()
    iguais = (result.trace == normal.trace
              and [(s.key, s.schedule) for s in result.front] == [(s.key, s.schedule) for s in normal.front])
    if not iguais:
        raise RuntimeError("A execução instrumentada difere da normal")
    reg, escala = gravador.registro, result.front[0].evaluation.tec_scale
    assert len(reg) == config.max_evaluations

    def ponto(key):
        return [key[0], key[1] / escala]

    fases = gravador.fases
    vnds = [f for f in fases if f["tipo"] == "vnd"]
    shakes = [f for f in fases if f["tipo"] == "shake"]
    descida = visitas(gravador, vnds[-1])
    primeira = visitas(gravador, vnds[0])
    # Shake em N2 com um inviável e, depois, um viável pior que a origem.
    tremor = next(f for f in shakes if f["vizinhanca"] and reg[f["de"] - 1]["key"] is None
                  and reg[f["ate"] - 1]["key"] is not None
                  and dominates(tuple(f["origem"]), reg[f["ate"] - 1]["key"]))
    # Incomparável: entra no arquivo e o VND não o aceita, sem que a origem o domine.
    livre = next(dict(avaliacao=n, corrente=v["corrente"]) for v in primeira for n in v["candidatos"]
                 if reg[n - 1]["inserted"] and n != v["aceito"])
    chave = [reg[n - 1]["key"] for n in livre.values()]
    assert not dominates(*chave) and not dominates(*reversed(chave))

    volta = next(k for k, v in enumerate(descida) if v["porta"] == 4 and v["aceito"])
    passagem = descida[volta - 4:volta + 1]
    assert [v["porta"] for v in passagem] == [0, 1, 2, 3, 4] and len({v["corrente"] for v in passagem}) == 1
    origem = next(n for n, r in enumerate(reg, 1) if r["key"] == tuple(tremor["origem"]))
    corrente = passagem[0]["corrente"]
    portas = []
    for visita in passagem:
        base = reg[visita["corrente"] - 1]
        lista = []
        for n in visita["candidatos"]:
            r = reg[n - 1]
            lista.append(dict(avaliacao=n, ponto=ponto(r["key"]) if r["key"] else None,
                              movimento=movimento(base["schedule"], r["schedule"])))
        tipos = ("modo", "espera", "inserir", "realocar", "trocar")
        bons = [c for c in lista if c["ponto"] and c["movimento"]["tipo"] == tipos[visita["porta"]]]
        x0, y0 = ponto(base["key"])
        # Em N2, a espera na borda da ponta que mais reduz o custo; nas demais portas,
        # o vizinho viável mais próximo do corrente que altere algum objetivo.
        if visita["porta"] == 1:
            def na_borda(c):
                p = plano_demo(instance, reg[c["avaliacao"] - 1]["schedule"])
                b = next(b for b in p["blocks"] if b["job"] == c["movimento"]["tarefas"][0])
                return b["start"] in instance.peaks[0] or b["end"] in instance.peaks[0]
            bons = [c for c in bons if na_borda(c)] or bons
        mudam = [c for c in bons if c["ponto"] != [x0, y0]] or bons
        mudam.sort(key=lambda c: (c["ponto"][1] if visita["porta"] == 1 else
                                  abs(c["ponto"][0] - x0) / 12 + abs(c["ponto"][1] - y0) / 400, c["avaliacao"]))
        principal = visita["aceito"] or mudam[0]["avaliacao"]
        viaveis = [c["avaliacao"] for c in lista if c["ponto"]]
        fantasmas = [principal]
        for n in viaveis:
            if len(fantasmas) == 3:
                break
            if reg[n - 1]["key"] not in {reg[f - 1]["key"] for f in fantasmas} | {base["key"]}:
                fantasmas.append(n)
        portas.append(dict(porta=visita["porta"], corrente=visita["corrente"], principal=principal,
                           aceito=visita["aceito"], fantasmas=fantasmas, examinados=len(lista),
                           inviaveis=sum(c["ponto"] is None for c in lista),
                           movimento=next(c["movimento"] for c in lista if c["avaliacao"] == principal)))

    aceites = []
    for visita in descida:
        if visita["aceito"]:
            de, para = reg[visita["corrente"] - 1], reg[visita["aceito"] - 1]
            aceites.append(dict(porta=visita["porta"], de=visita["corrente"], para=visita["aceito"],
                                movimento=movimento(de["schedule"], para["schedule"])))
    final = [dict(ponto=ponto(s.key), **plano_demo(instance, s.schedule)) for s in sorted(result.front, key=lambda s: s.key)]
    # Melhor compromisso: menor distância ao ideal na escala da própria frente.
    xs, ys = [p["cmax"] for p in final], [p["tec"] for p in final]
    melhor = min(range(len(final)), key=lambda k: ((xs[k] - min(xs)) / (max(xs) - min(xs))) ** 2
                 + ((ys[k] - min(ys)) / (max(ys) - min(ys))) ** 2)

    usados = {1, 2, 3, 4, origem, shakes[0]["ate"], vnds[-1]["de"] - 1, *range(tremor["de"], tremor["ate"] + 1),
              *livre.values(), *(a[k] for a in aceites for k in ("de", "para")),
              *(n for p in portas for n in p["fantasmas"])}
    dificuldade, partidas = construcoes(instance, gravador.rng.notas, config.initial_solutions)
    for passos, r in zip(partidas, reg):
        feito = [[(s["job"], s["modo"], 0) for s in passos if s["maquina"] == m] for m in range(instance.m)]
        assert feito == [list(seq) for seq in r["schedule"]]
    expansoes = []
    for f, g in zip(shakes, vnds):
        if f["expandiu"] or g["expandiu"]:
            expansoes.append(g["ate"])
    fontes = (Path("src/problem.py"), Path("src/schedule.py"), Path("src/metaheuristics/vns_vnd.py"))
    return dict(
        escopo="demonstração na instância didática; seed escolhida por conter os eventos mostrados",
        parametros=config.as_dict(), python=platform.python_version(), instancia_sha256=instance.digest,
        fontes_sha256={f.as_posix(): sha256((ROOT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for f in fontes},
        instrumentada_igual_a_normal=iguais, horizonte=instance.horizon, campanha=campanha(),
        construcao=dict(gravador.initialization) and {k: v for k, v in gravador.initialization.items() if "seconds" not in k},
        dificuldade=dificuldade, partidas=partidas,
        iniciais=[dict(avaliacao=n, ponto=ponto(r["key"]), inserido=r["inserted"]) for n, r in enumerate(reg[:4], 1)],
        arquivo_inicial=[ponto(p) for p in sorted(reg[3]["archive"])],
        origem=dict(avaliacao=origem, ponto=ponto(reg[origem - 1]["key"]),
                    visitas=[[*ponto(k), v] for k, v in sorted(result.explored_origins.items())]),
        shakes=dict(primeiro=dict(avaliacao=shakes[0]["ate"], movimento=movimento(
                        reg[origem - 1]["schedule"], reg[shakes[0]["ate"] - 1]["schedule"])),
                    tremor=dict(porta=tremor["vizinhanca"], avaliacoes=list(range(tremor["de"], tremor["ate"] + 1)),
                                movimentos=[movimento(reg[origem - 1]["schedule"], reg[n - 1]["schedule"])
                                            for n in range(tremor["de"], tremor["ate"] + 1)]),
                    entrada=dict(porta=shakes[-1]["vizinhanca"], avaliacao=vnds[-1]["de"] - 1,
                                 movimento=movimento(reg[origem - 1]["schedule"], reg[vnds[-1]["de"] - 2]["schedule"])),
                    sucessos=[dict(porta=f["vizinhanca"], avaliacao=f["ate"], ponto=ponto(reg[f["ate"] - 1]["key"]))
                              for f in shakes if reg[f["ate"] - 1]["key"]]),
        corrente=corrente, portas=portas, descida=descida, aceites=aceites,
        incomparavel=livre | dict(fim_da_descida=vnds[0]["ate"], proximo_shake=shakes[1]["vizinhanca"],
                                  mesma_origem=shakes[0]["origem"] == shakes[1]["origem"]),
        expansoes=expansoes,
        planos={str(n): plano_demo(instance, reg[n - 1]["schedule"]) for n in sorted(usados)},
        pontos=[ponto(r["key"]) if r["key"] else None for r in reg],
        arquivos=[[n, [ponto(p) for p in sorted(r["archive"])]] for n, r in enumerate(reg, 1) if r["inserted"]],
        avaliacoes=result.evaluations, rejeitadas=result.rejected_evaluations, viaveis=result.feasible_evaluations,
        parada=result.stop_reason, frente=final, melhor=melhor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verifica os JSONs já salvos sem alterá-los.")
    args = parser.parse_args()
    for output, trace, indent in ((OUTPUT, build_trace(), 2), (DEMO, montar_demo(), None)):
        # A comparação usa os valores, para tolerar conversão de quebras de linha pelo Git.
        trace = json.loads(json.dumps(trace))
        if args.check:
            if json.loads(output.read_text(encoding="utf-8")) != trace:
                parser.exit(1, f"O trace atual diverge de {output}\n")
            print(f"Trace verificado: {output}")
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.is_file() and json.loads(output.read_text(encoding="utf-8")) == trace:
            print(f"Trace já atualizado: {output}")
            continue
        output.write_text(json.dumps(trace, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"Trace registrado: {output}")


if __name__ == "__main__":
    main()
