"""Fase 2: reavalia as melhores configurações de um estudo em vários orçamentos.

A busca TPE compara configurações sob um único cap de avaliações. Aqui as
``top`` melhores são reexecutadas nas mesmas entradas, com seeds novas e promoção opcional entre etapas com
outros caps, para verificar se o ranking se mantém e quanto o HV ainda cresce
(convergência). O banco Optuna é apenas lido; o estudo não é alterado.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import json
import multiprocessing
import math
from pathlib import Path

import optuna
from optuna.trial import TrialState

from hyperparameters_tuning.common import (
    _worker_setup, algorithm_module, evaluate_parameters, source_fingerprint, study_lock,
)
from problem import atomic_json, read_instance


def select_top(study, top, diversity_slots=0):
    """Trials COMPLETE por score decrescente, sem configurações repetidas."""
    completed = sorted(study.get_trials(deepcopy=False, states=(TrialState.COMPLETE,)),
                       key=lambda trial: (-trial.value, trial.number))
    selected, seen = [], set()
    for trial in completed:
        # Em evaluations o cap não faz parte da configuração; é imposto por orçamento.
        parameters = {name: value for name, value in trial.user_attrs["effective_parameters"].items()
                      if name != "max_evaluations"}
        key = tuple(sorted(parameters.items()))
        if key in seen:
            continue
        seen.add(key)
        selected.append(dict(trial=trial.number, search_score=trial.value, parameters=parameters))
        if len(selected) == top and not diversity_slots:
            break
    if diversity_slots and selected:
        # Usa o mesmo seletor das etapas; mantém o melhor e inclui regiões distintas.
        results = {(c['trial'], 0): {'score': c['search_score']} for c in selected}
        return promote(selected, results, 0, min(top, len(selected))/len(selected), diversity_slots)
    return selected


def promote(configs, results, budget, fraction, diversity_slots):
    """Preserva o vencedor e reserva vagas por distância entre parâmetros."""
    ranked = sorted(configs, key=lambda c: (-results[c['trial'], budget]['score'], c['trial']))
    count = max(1, math.ceil(len(ranked) * fraction - 1e-12))
    selected = ranked[:count-min(diversity_slots, count-1)]
    remaining = [c for c in ranked if c not in selected]
    while len(selected) < count:
        def distance(config):
            return min(sum(config['parameters'].get(k) != other['parameters'].get(k)
                           for k in config['parameters']) for other in selected)
        candidate = max(remaining, key=lambda c: (distance(c), -ranked.index(c)))
        selected.append(candidate)
        remaining.remove(candidate)
    return selected


def confirm(output_dir, *, top=5, budgets=(8000, 20000, 50000), workers=1,
            seeds=None, promote_fraction=1.0, diversity_slots=1):
    output = Path(output_dir).resolve()
    protocol_file, database = output / "protocol.json", output / "study.sqlite3"
    if not protocol_file.exists() or not database.exists():
        raise ValueError(f"Estudo não encontrado em {output}")
    budgets = tuple(budgets)
    if (min(top, workers) < 1 or not budgets or len(set(budgets)) != len(budgets)
            or any(type(budget) is not int or budget < 1 for budget in budgets)):
        raise ValueError("top/workers positivos; orçamentos inteiros positivos e distintos")
    protocol = json.loads(protocol_file.read_text(encoding="utf-8"))
    algorithm, cases = protocol["algorithm"], protocol["cases"]
    if seeds is None:
        seeds = []
        candidate = 101
        while len(seeds) < max(5, len(protocol['seeds'])):
            if candidate not in protocol['seeds']:
                seeds.append(candidate)
            candidate += 1
    seeds = tuple(seeds)
    if (not seeds or any(type(s) is not int or s < 0 for s in seeds)
            or len(set(seeds)) != len(seeds) or set(seeds) & set(protocol['seeds'])):
        raise ValueError('Seeds de confirmação devem ser distintas, não negativas e novas')
    if (not 0 < promote_fraction <= 1 or type(diversity_slots) is not int or diversity_slots < 0
            or tuple(sorted(budgets)) != budgets):
        raise ValueError('Promoção em (0,1], diversidade >= 0 e orçamentos crescentes exigidos')
    plugin = algorithm_module(algorithm)
    if protocol.get("source_sha256") != source_fingerprint():
        raise ValueError("Código mudou desde a calibração; a confirmação não seria comparável")
    for case in cases:
        if read_instance(case["path"]).digest != case["sha256"]:
            raise ValueError(f"Entrada mudou desde a calibração: {case['path']}")
    folder = output / "confirmation"
    with study_lock(output / "study.lock"):
        storage = optuna.storages.RDBStorage(url="sqlite:///" + database.as_posix())
        try:
            study = optuna.load_study(study_name=protocol["study_name"], storage=storage)
            selected = select_top(study, top, diversity_slots)
        finally:
            storage.engine.dispose()
        if not selected:
            raise ValueError("Estudo sem trials completos")
        folder.mkdir(exist_ok=True)
        plan = dict(version=1, study_name=protocol["study_name"], top=top,
                    budgets=list(budgets), seeds=list(seeds), promote_fraction=promote_fraction,
                    diversity_slots=diversity_slots, selected=selected,
                    source_sha256=protocol["source_sha256"], cases=cases)
        plan_file = folder / "plan.json"
        if plan_file.exists() and json.loads(plan_file.read_text(encoding="utf-8")) != plan:
            raise ValueError("Plano de confirmação mudou; use outra pasta de estudo")
        atomic_json(plan_file, plan)
        results, active = {}, selected
        pool = ProcessPoolExecutor(max_workers=workers,
            mp_context=multiprocessing.get_context("spawn"), initializer=_worker_setup) if workers > 1 else None
        if pool is None:
            _worker_setup()
        try:
            for index, budget in enumerate(budgets):
                jobs = []
                for config in active:
                    parameters = plugin.resolve_parameters(config["parameters"], budget, "evaluations")
                    path = folder / f"trial_{config['trial']:06d}_E{budget}.json"
                    if path.exists():
                        saved = json.loads(path.read_text(encoding="utf-8"))
                        if (saved["parameters"] != parameters or saved["seeds"] != list(seeds)
                                or saved.get("trial") != config["trial"] or saved.get("budget") != budget):
                            raise ValueError(f"Arquivo de confirmação incompatível: {path}")
                        results[config["trial"], budget] = saved
                    else:
                        jobs.append((config["trial"], parameters, path))
                def save(job, payload):
                    number, parameters, path = job
                    payload = dict(trial=number, budget=budget, seeds=list(seeds), **payload)
                    atomic_json(path, payload)
                    results[number, budget] = payload
                    print(f"Trial {number} com {budget} avaliações: score={payload['score']:.6f}", flush=True)
                if pool:
                    pending = {pool.submit(evaluate_parameters, parameters, cases, seeds, budget,
                        algorithm=algorithm): job for job in jobs for _, parameters, _ in [job]}
                    for future in as_completed(pending):
                        save(pending[future], future.result())
                else:
                    for job in jobs:
                        save(job, evaluate_parameters(job[1], cases, seeds, budget, algorithm=algorithm))
                if index < len(budgets)-1:
                    active = promote(active, results, budget, promote_fraction, diversity_slots)
        finally:
            if pool:
                pool.shutdown(wait=True, cancel_futures=True)
        return export_confirmation(output, {**protocol, "seeds": list(seeds)}, selected, budgets, results)


def export_confirmation(output, protocol, selected, budgets, results):
    with (output / "confirmation.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["trial", "budget", "instance", "median_score", "score"])
        writer.writeheader()
        for config in selected:
            for budget in budgets:
                if (config["trial"], budget) not in results:
                    continue
                payload = results[config["trial"], budget]
                for row in payload["instance_scores"]:
                    writer.writerow(dict(trial=config["trial"], budget=budget, instance=row["instance"],
                                         median_score=row["median_score"], score=payload["score"]))
    ranking = {}
    for budget in budgets:
        ordered = sorted([c for c in selected if (c["trial"], budget) in results], key=lambda c: (-results[c["trial"], budget]["score"], c["trial"]))
        ranking[str(budget)] = [config["trial"] for config in ordered]
    configs = []
    for config in selected:
        evaluated = [b for b in budgets if (config["trial"], b) in results]
        scores = [results[config["trial"], budget]["score"] for budget in evaluated]
        configs.append(dict(config,
            scores={str(budget): score for budget, score in zip(evaluated, scores)},
            ranks={str(budget): ranking[str(budget)].index(config["trial"])+1 for budget in evaluated},
            gains={f"{a}->{b}": sb-sa for a, b, sa, sb in zip(evaluated, evaluated[1:], scores, scores[1:])}))
    largest = max(budgets)
    winner = ranking[str(largest)][0]
    best = next(config for config in selected if config["trial"] == winner)
    report = dict(algorithm=protocol["algorithm"], study_name=protocol["study_name"],
        budgets=list(budgets), seeds=protocol["seeds"], configurations=configs, ranking=ranking,
        recommended=dict(trial=winner, budget=largest,
            solver_config=algorithm_module(protocol["algorithm"]).resolve_parameters(
                best["parameters"], largest, "evaluations")),
        criterion="mean_over_instances(median_over_seeds(normalized_HV / 1.05^2))",
        status="provisional_calibration", pareto_proven=False,
        evidence="confirmation/trial_<n>_E<orçamento>.json")
    atomic_json(output / "confirmation.json", report)
    return report
