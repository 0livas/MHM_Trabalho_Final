"""Fase 2: reavalia as melhores configurações de um estudo em vários orçamentos.

A busca TPE compara configurações sob um único cap de avaliações. Aqui as
``top`` melhores são reexecutadas nas mesmas entradas e seeds do protocolo com
outros caps, para verificar se o ranking se mantém e quanto o HV ainda cresce
(convergência). O banco Optuna é apenas lido; o estudo não é alterado.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import csv
import json
import multiprocessing
from pathlib import Path

import optuna
from optuna.trial import TrialState

from hyperparameters_tuning.common import (
    _worker_setup, algorithm_module, evaluate_parameters, source_fingerprint, study_lock,
)
from problem import atomic_json, read_instance


def select_top(study, top):
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
        if len(selected) == top:
            break
    return selected


def confirm(output_dir, *, top=5, budgets=(8000, 20000, 50000), workers=1):
    output = Path(output_dir).resolve()
    protocol_file, database = output / "protocol.json", output / "study.sqlite3"
    if not protocol_file.exists() or not database.exists():
        raise ValueError(f"Estudo não encontrado em {output}")
    budgets = tuple(budgets)
    if (min(top, workers) < 1 or not budgets or len(set(budgets)) != len(budgets)
            or any(type(budget) is not int or budget < 1 for budget in budgets)):
        raise ValueError("top/workers positivos; orçamentos inteiros positivos e distintos")
    protocol = json.loads(protocol_file.read_text(encoding="utf-8"))
    algorithm, cases, seeds = protocol["algorithm"], protocol["cases"], tuple(protocol["seeds"])
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
            selected = select_top(study, top)
        finally:
            storage.engine.dispose()
        if not selected:
            raise ValueError("Estudo sem trials completos")
        folder.mkdir(exist_ok=True)
        jobs, results = [], {}
        for config in selected:
            for budget in budgets:
                parameters = plugin.resolve_parameters(config["parameters"], budget, "evaluations")
                path = folder / f"trial_{config['trial']:06d}_E{budget}.json"
                if path.exists():
                    saved = json.loads(path.read_text(encoding="utf-8"))
                    if saved["parameters"] != parameters or saved["seeds"] != list(seeds):
                        raise ValueError(f"Arquivo de confirmação incompatível: {path}")
                    results[config["trial"], budget] = saved
                else:
                    jobs.append((config["trial"], budget, parameters, path))
        print(f"{len(jobs)} execuções de configuração pendentes; {len(selected)} configurações × "
              f"orçamentos {list(budgets)}; {len(cases)} entradas × {len(seeds)} seeds.", flush=True)
        pool = ProcessPoolExecutor(max_workers=min(workers, len(jobs)),
            mp_context=multiprocessing.get_context("spawn"), initializer=_worker_setup) if workers > 1 and jobs else None
        try:
            futures = [pool.submit(evaluate_parameters, parameters, cases, seeds, budget, algorithm=algorithm)
                       if pool else None for _, budget, parameters, _ in jobs]
            for (number, budget, parameters, path), future in zip(jobs, futures):
                payload = future.result() if future else evaluate_parameters(
                    parameters, cases, seeds, budget, algorithm=algorithm)
                payload = dict(trial=number, budget=budget, seeds=list(seeds), **payload)
                atomic_json(path, payload)
                results[number, budget] = payload
                print(f"Trial {number} com {budget} avaliações: score={payload['score']:.6f}", flush=True)
        finally:
            if pool:
                pool.shutdown(wait=True, cancel_futures=True)
        return export_confirmation(output, protocol, selected, budgets, results)


def export_confirmation(output, protocol, selected, budgets, results):
    with (output / "confirmation.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["trial", "budget", "instance", "median_score", "score"])
        writer.writeheader()
        for config in selected:
            for budget in budgets:
                payload = results[config["trial"], budget]
                for row in payload["instance_scores"]:
                    writer.writerow(dict(trial=config["trial"], budget=budget, instance=row["instance"],
                                         median_score=row["median_score"], score=payload["score"]))
    ranking = {}
    for budget in budgets:
        ordered = sorted(selected, key=lambda c: (-results[c["trial"], budget]["score"], c["trial"]))
        ranking[str(budget)] = [config["trial"] for config in ordered]
    configs = []
    for config in selected:
        scores = [results[config["trial"], budget]["score"] for budget in budgets]
        configs.append(dict(config,
            scores={str(budget): score for budget, score in zip(budgets, scores)},
            ranks={str(budget): ranking[str(budget)].index(config["trial"])+1 for budget in budgets},
            gains={f"{a}->{b}": sb-sa for a, b, sa, sb in zip(budgets, budgets[1:], scores, scores[1:])}))
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
