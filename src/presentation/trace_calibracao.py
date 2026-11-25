"""Resume os estudos de calibração já gravados. Só lê CSV e JSON; não executa calibração."""

import argparse
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
import statistics
from fractions import Fraction

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "data" / "output" / "hyperparameters_tuning"
SAIDA = HERE / "data" / "trace_calibracao.json"
ESTUDOS = {
    "vns_vnd": "vns_vnd/vns_vnd_tpe_v7", "spea2": "spea2/spea2_tpe_v6_pedro",
    "moead": "moead/moead_tpe_v6", "age": "age/age_tpe_v6", "vns_v6": "vns_vnd/vns_vnd_tpe_v6",
}
CAMPANHA = {"spea2": "experiments", "moead": "experiments", "age": "experiments",
            "vns_vnd": "experiments_vns_new"}
TRIAL_NOTA = 0          # referência do protocolo, primeira sugestão do SPEA2
FAIXA_TPE = "mutation_probability"
HASHES = {}


def ler(path):
    raw = path.read_bytes()
    HASHES[path.relative_to(ROOT).as_posix()] = sha256(raw).hexdigest()
    return raw.decode("utf-8")


def ler_json(path):
    return json.loads(ler(path))


def ler_csv(path):
    return list(csv.DictReader(ler(path).splitlines()))


def numero(value):
    return None if value == "" else json.loads(value)


def promover(configs, scores, fraction, slots):
    """Mesma regra de confirm.promote (o módulo importa optuna, ausente no ambiente do vídeo)."""
    ranked = sorted(configs, key=lambda c: (-scores[c["trial"]], c["trial"]))
    count = max(1, math.ceil(len(ranked) * fraction - 1e-12))
    chosen = ranked[:count - min(slots, count - 1)]
    merit = len(chosen)
    rest = [c for c in ranked if c not in chosen]
    while len(chosen) < count:
        def distance(c):
            return min(sum(c["parameters"].get(k) != o["parameters"].get(k) for k in c["parameters"])
                       for o in chosen)
        pick = max(rest, key=lambda c: (distance(c), -ranked.index(c)))
        chosen.append(pick)
        rest.remove(pick)
    return [c["trial"] for c in chosen[:merit]], [c["trial"] for c in chosen[merit:]]


def media(values):
    return float(sum(map(Fraction, values)) / len(values))


def estudo(nome, pasta):
    d = BASE / pasta
    protocolo, melhor = ler_json(d / "protocol.json"), ler_json(d / "best_parameters.json")
    grade = {k: v for k, v in protocolo["search_space"].items() if k != "max_evaluations"}
    tamanho = math.prod(map(len, grade.values()))
    assert tamanho == melhor["search_space_size"]
    trials, recorde, topo = [], [], -1
    for row in ler_csv(d / "trials.csv"):
        t = dict(trial=int(row["trial"]), state=row["state"], source=row["proposal_source"] or None,
                 score=numero(row["score"]), parameters={k: numero(row[k]) for k in grade},
                 duplicate_of=numero(row["duplicate_of"]))
        erro = row["error"]
        t["failure"] = None if t["state"] != "FAIL" else "timeout" if erro.startswith("timeout") \
            else "interrupted" if erro.startswith("KeyboardInterrupt") else "other"
        if t["state"] == "PRUNED":
            assert t["duplicate_of"] is not None
        if t["state"] == "COMPLETE":
            saved = ler_json(d / "trials" / f"trial_{t['trial']:06d}.json")
            assert abs(saved["score"] - t["score"]) < 1e-12
            # Recalcula a agregação a partir das 18 execuções.
            por = {}
            for run in saved["runs"]:
                por.setdefault(run["instance"], []).append(run["score"])
            assert len(por) == 6 and all(len(v) == 3 for v in por.values())
            assert abs(media([statistics.median(v) for v in por.values()]) - t["score"]) < 1e-12
            if t["score"] > topo:
                topo = t["score"]
                recorde.append(dict(trial=t["trial"], score=topo, source=t["source"]))
        trials.append(t)
    assert recorde[-1]["trial"] == melhor["best_trial"]
    tentativas = [t for t in trials if t["state"] != "PRUNED"]
    out = dict(study=protocolo["study_name"], grid=grade, size=tamanho, trials=trials, record=recorde,
               counts=dict(complete=sum(t["state"] == "COMPLETE" for t in trials),
                           fail=sum(t["state"] == "FAIL" for t in trials),
                           timeout=sum(t["failure"] == "timeout" for t in trials),
                           interrupted=sum(t["failure"] == "interrupted" for t in trials),
                           duplicate=sum(t["state"] == "PRUNED" for t in trials),
                           attempts=len(tentativas),
                           exploration=sum(t["source"] == "exploration" for t in trials),
                           tpe=sum(t["source"] == "tpe" for t in trials)),
               best=dict(trial=melhor["best_trial"], score=melhor["best_score"],
                         parameters={k: melhor["solver_config"][k] for k in grade}),
               protocol={k: protocolo[k] for k in ("seeds", "budget_per_run", "reference", "startup_trials",
                         "multivariate", "pruning", "sampler_seed", "aggregation", "python", "packages")},
               instances=[c["path"].replace("\\", "/").rsplit("/", 1)[-1] for c in protocolo["cases"]],
               source_sha256={k.replace("\\", "/"): v for k, v in protocolo["source_sha256"].items()})
    assert out["counts"]["attempts"] == 60 and out["counts"]["exploration"] == 20
    if not (d / "confirmation.json").exists():
        return out
    conf, plano = ler_json(d / "confirmation.json"), ler_json(d / "confirmation" / "plan.json")
    por_csv = {}
    for row in ler_csv(d / "confirmation.csv"):
        por_csv.setdefault((int(row["trial"]), row["budget"]), []).append(row)
    configs = conf["configurations"]
    for c in configs:
        for budget, score in c["scores"].items():
            rows = por_csv[c["trial"], budget]
            assert len(rows) == 6 and float(rows[0]["score"]) == score
            assert abs(media([float(r["median_score"]) for r in rows]) - score) < 1e-12
    etapas, ativos = [], configs
    for k, budget in enumerate(conf["budgets"]):
        key = str(budget)
        scores = {c["trial"]: c["scores"][key] for c in configs if key in c["scores"]}
        assert set(scores) == {c["trial"] for c in ativos}
        ranking = sorted(scores, key=lambda n: (-scores[n], n))
        assert ranking == conf["ranking"][key]
        etapa = dict(budget=budget, ranking=ranking, scores={str(n): s for n, s in scores.items()})
        if k < len(conf["budgets"]) - 1:
            merito, diverso = promover(ativos, scores, plano["promote_fraction"], plano["diversity_slots"])
            etapa.update(promoted_by_score=merito, promoted_by_diversity=diverso,
                         eliminated=[n for n in ranking if n not in merito + diverso])
            ativos = [c for c in ativos if c["trial"] in merito + diverso]
        etapas.append(etapa)
    rec = conf["recommended"]
    out["confirmation"] = dict(
        budgets=conf["budgets"], seeds=conf["seeds"], promote_fraction=plano["promote_fraction"],
        diversity_slots=plano["diversity_slots"], stages=etapas,
        candidates=[dict(trial=c["trial"], search_score=c["search_score"], parameters=c["parameters"])
                    for c in configs],
        recommended=dict(trial=rec["trial"], budget=rec["budget"],
                         parameters={k: rec["solver_config"][k] for k in grade}))
    assert rec["trial"] != melhor["best_trial"]
    return out


def nota():
    """As 18 execuções de um trial real e a agregação que vira o score."""
    d = BASE / ESTUDOS["spea2"]
    t = ler_json(d / "trials" / f"trial_{TRIAL_NOTA:06d}.json")
    linhas = []
    for item in t["instance_scores"]:
        runs = [(r["seed"], r["score"]) for r in t["runs"] if r["instance"] == item["instance"]]
        assert statistics.median(s for _, s in runs) == item["median_score"]
        linhas.append(dict(instance=item["instance"], runs=[dict(seed=a, score=b) for a, b in runs],
                           median=item["median_score"]))
    return dict(method="spea2", trial=TRIAL_NOTA, parameters=t["parameters"], rows=linhas, score=t["score"])


def nuvens(trials):
    """Leitura simplificada do TPE em uma faixa: conta níveis entre bons e demais.

    Optuna usa gamma(n) = min(ceil(0,1 n), 25) trials como 'bons'. Aqui a razão é entre
    frequências com +1 por nível, uma faixa de cada vez; o TPE real é multivariado.
    """
    grade, out = None, []
    for limite in (20,):
        done = [t for t in trials if t["state"] == "COMPLETE" and (limite is None or t["trial"] < limite)]
        done.sort(key=lambda t: (-t["score"], t["trial"]))
        n = math.ceil(.1 * len(done))
        bons, demais = done[:n], done[n:]
        grade = sorted({t["parameters"][FAIXA_TPE] for t in trials})
        def freq(grupo):
            c = [sum(t["parameters"][FAIXA_TPE] == v for t in grupo) for v in grade]
            return c, [(x + 1) / (len(grupo) + len(grade)) for x in c]
        (a, fa), (b, fb) = freq(bons), freq(demais)
        out.append(dict(completed=len(done), good=[t["trial"] for t in bons], rest=[t["trial"] for t in demais],
                        levels=grade, good_count=a, rest_count=b, ratio=[x / y for x, y in zip(fa, fb)]))
    return out


def calcular():
    HASHES.clear()
    dados = {nome: estudo(nome, pasta) for nome, pasta in ESTUDOS.items()}
    referencia = next(t for t in dados["spea2"]["trials"] if t["trial"] == 0)
    assert referencia["parameters"] == dict(population_size=100, crossover_probability=.9, mutation_probability=.3)
    campanha, instancias = {}, {}
    for nome, pasta in CAMPANHA.items():
        m = ler_json(ROOT / "data" / "output" / pasta / "experiment_manifest.json")
        c = m["configurations"][nome]
        grid = dados[nome]["grid"]
        params = {k: c["parameters"][k] for k in grid}
        assert params == dados[nome]["confirmation"]["recommended"]["parameters"]
        assert c["trial"] == dados[nome]["confirmation"]["recommended"]["trial"]
        campanha[nome] = dict(parameters=params, max_evaluations=c["parameters"]["max_evaluations"],
                              tuned_max_evaluations=c["tuned_max_evaluations"], status=c["status"],
                              trial=c["trial"], study=c["study"])
        instancias[nome] = [k for k in m["instances"]]
    ig = set(dados["spea2"]["instances"])
    assert all(set(d["instances"]) == ig for d in dados.values())
    v6, v7 = dados["vns_v6"], dados["vns_vnd"]
    diferentes = sorted(k for k in v7["source_sha256"] if v6["source_sha256"].get(k) != v7["source_sha256"][k])
    atual = sha256((ROOT / "src/metaheuristics/vns_vnd.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    original = sha256((ROOT / "src/metaheuristics/vns_vnd_original.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    fonte = dict(changed_between_v6_and_v7=diferentes,
                 v6_matches_vns_vnd_original=v6["source_sha256"]["src/metaheuristics/vns_vnd.py"] == original,
                 v7_matches_current_vns_vnd=v7["source_sha256"]["src/metaheuristics/vns_vnd.py"] == atual,
                 current_has_lpt=b"randomized_lpt_earliest_end_v1" in (ROOT / "src/metaheuristics/vns_vnd.py").read_bytes())
    for d in dados.values():
        d.pop("source_sha256")
    return dict(studies=dados, score_demo=nota(),
                clouds=nuvens(dados["spea2"]["trials"]), cloud_parameter=FAIXA_TPE,
                campaign=campanha, overlap_instances=sorted(ig & set(instancias["spea2"])),
                vns_source=fonte, sha256=dict(sorted(HASHES.items())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    dados = json.loads(json.dumps(calcular()))
    if args.check:
        salvo = json.loads(SAIDA.read_text(encoding="utf-8"))
        ruins = [k for k in sorted(set(dados) | set(salvo)) if dados.get(k) != salvo.get(k)]
        if ruins:
            raise SystemExit(f"Trace difere dos arquivos em: {', '.join(ruins)}")
        print(f"Trace confere com {len(dados['sha256'])} arquivos (Python {platform.python_version()}).")
    else:
        SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(SAIDA, SAIDA.stat().st_size)


if __name__ == "__main__":
    main()
