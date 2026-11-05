"""Infraestrutura comum de calibração: HV, TPE, persistência e processos CPU."""
from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from fractions import Fraction
from hashlib import sha256
import csv
import importlib
import importlib.metadata
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import re
import random
import statistics
import time
import numpy as np
import optuna
from optuna.trial import TrialState
from pymoo.indicators.hv import HV
from problem import PROJECT_ROOT, atomic_json, energy_scale, interval_cost_units, read_instance
REFERENCE = (1.05, 1.05)
PROTOCOL_VERSION = 6


def _unseen_parameters(space, budget_mode, seen, rng):
    """Sorteia uniformemente uma posição livre da grade sem materializá-la."""
    active = {k: v for k, v in space.items() if k != "max_evaluations" or budget_mode == "effort"}
    total = math.prod(map(len, active.values()))
    used = set()
    for key in seen:
        values = dict(key)
        index = 0
        for name, choices in active.items():
            index = index * len(choices) + choices.index(values[name])
        used.add(index)
    if len(used) == total:
        return None
    index = rng.randrange(total - len(used))
    for occupied in sorted(used):
        if occupied > index:
            break
        index += 1
    selected = {}
    for name, choices in reversed(list(active.items())):
        index, digit = divmod(index, len(choices))
        selected[name] = choices[digit]
    return selected


def _save_sampler_state(study, rng):
    # Estados numéricos em JSON; não carrega objetos executáveis de pickle.
    states = []
    for generator in (study.sampler._rng.rng, study.sampler._random_sampler._rng.rng):
        name, keys, pos, gaussian, cached = generator.get_state()
        states.append([name, keys.tolist(), pos, gaussian, cached])
    study.set_user_attr("rng_checkpoint", dict(tpe=states, exploration=rng.getstate()))


def _restore_sampler_state(study, rng):
    checkpoint = study.user_attrs.get("rng_checkpoint")
    if checkpoint:
        for generator, state in zip((study.sampler._rng.rng, study.sampler._random_sampler._rng.rng), checkpoint["tpe"]):
            generator.set_state((state[0], np.asarray(state[1], dtype=np.uint32), *state[2:]))
        def tuples(value):
            return tuple(map(tuples, value)) if isinstance(value, list) else value
        rng.setstate(tuples(checkpoint["exploration"]))


class TrialTimeout(RuntimeError):
    """Trial excedeu o limite de segurança; vira FAIL sem abortar o estudo."""


def validate_native_space(space, defaults, config_type, budget, budget_mode):
    """Grade dos campos nativos; todas as combinações devem formar Config válido."""
    from dataclasses import fields
    if budget_mode not in ("effort", "evaluations"):
        raise ValueError("Use effort ou evaluations; gerações não são um parâmetro nativo")
    if type(budget) is not int or budget < 1:
        raise ValueError("budget deve ser inteiro positivo")
    native = {field.name for field in fields(config_type)} - {"seed"}
    if set(defaults) != native:
        raise ValueError("A grade deve cobrir exatamente os parâmetros nativos, exceto seed")
    if not isinstance(space, dict) or set(space) != native:
        raise ValueError(f"A grade deve conter exatamente: {', '.join(defaults)}")
    result = {}
    integer_fields = {"population_size", "max_evaluations", "n_neighbors"}
    for name in defaults:
        values = space[name]
        if not isinstance(values, list) or not values:
            raise ValueError(f"Lista vazia ou inválida: {name}")
        if name in integer_fields:
            minimum = 2 if name in ("population_size", "n_neighbors") else 1
            if any(type(v) is not int or v < minimum for v in values):
                raise ValueError(f"Inteiros >= {minimum} exigidos em {name}")
        elif any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError(f"Probabilidades finitas em [0,1] exigidas em {name}")
        if len(values) != len(set(values)):
            raise ValueError(f"Valores repetidos: {name}")
        result[name] = list(values)
    if budget_mode == "evaluations":
        result["population_size"] = [v for v in result["population_size"] if v <= budget]
        if not result["population_size"]:
            raise ValueError("Nenhuma população da grade cabe no orçamento")
    # Checa extremos suficientes para as restrições P<=E e 2<=N<=P.
    if budget_mode == "effort" and max(result["population_size"]) > min(result["max_evaluations"]):
        raise ValueError("Toda população deve caber no menor max_evaluations da grade")
    if "n_neighbors" in result and max(result["n_neighbors"]) > min(result["population_size"]):
        raise ValueError("Todo n_neighbors deve ser <= à menor população; ajuste a grade")
    return result


def resolve_native_parameters(parameters, budget, budget_mode, config_type):
    """Sem conversões de operadores ou gerações; saída reutilizável no Config."""
    if budget_mode not in ("effort", "evaluations"):
        raise ValueError("Use effort ou evaluations")
    result = dict(parameters)
    if budget_mode == "evaluations":
        result["max_evaluations"] = budget
    config_type(seed=0, **result)
    return result


def suggest_native_parameters(trial, budget, budget_mode, space, config_type):
    selected = {name: trial.suggest_categorical(name, values) for name, values in space.items()
                if name != "max_evaluations" or budget_mode == "effort"}
    return resolve_native_parameters(selected, budget, budget_mode, config_type)


def algorithm_module(name):
    if name not in ('moead','spea2','age','vns_vnd'):
        raise ValueError('Meta-heurística desconhecida')
    return importlib.import_module('hyperparameters_tuning.'+name)

def calculate_bounds(instance):
    """Limites individuais exatos da entrada, sem conhecer a fronteira ótima.

    O custo varia linearmente entre bordas da tarifa. Seus extremos ocorrem
    nos endpoints do domínio ou em a-d, b-d, a, b para cada ponta [a,b).
    """
    scale, prices = energy_scale(instance)
    minima, lower, upper, cache = [], 0, 0, {}
    for job in range(instance.n):
        durations, costs = [], []
        for machine, mode, on, off in prices:
            duration = instance.duration(job, machine, mode)
            last = instance.horizon - duration
            if last < 0:
                continue
            durations.append(duration)
            key = duration, on, off
            if key not in cache:
                starts = {0, last}
                for a, b in instance.peaks:
                    starts.update(s for s in (a-duration, b-duration, a, b) if 0 <= s <= last)
                values = [interval_cost_units(instance, s, s+duration, on, off) for s in starts]
                cache[key] = min(values), max(values)
            costs.append(cache[key])
        if not costs:
            raise ValueError(f"Tarefa {job} não cabe individualmente em {instance.path.name}")
        minima.append(min(durations))
        lower += min(pair[0] for pair in costs)
        upper += max(pair[1] for pair in costs)
    c_lower = max(max(minima), math.ceil(Fraction(sum(minima), instance.m)))
    if c_lower > instance.horizon:
        raise ValueError(f"Limite inferior excede o horizonte: {instance.path.name}")
    return dict(cmax_lower=c_lower, cmax_upper=instance.horizon,
                tec_lower=lower, tec_upper=upper, cost_scale=scale)


def normalized_hv(points, bounds):
    """HV de pontos exatos normalizados em [0,1]²; eixo constante vira zero."""
    normalized = []
    for cmax, units in points:
        coordinates = []
        for value, lower, upper in (
            (cmax, bounds["cmax_lower"], bounds["cmax_upper"]),
            (units, bounds["tec_lower"], bounds["tec_upper"]),
        ):
            if not lower <= value <= upper:
                raise ValueError("Objetivo fora dos limites da entrada; normalização não usa clipping")
            coordinates.append(float(Fraction(value-lower, upper-lower)) if upper > lower else 0.0)
        normalized.append(coordinates)
    return float(HV(ref_point=np.asarray(REFERENCE))(np.asarray(normalized))) / math.prod(REFERENCE) if normalized else 0.0


def evaluate_parameters(parameters, cases, seeds, budget, *, algorithm, trial_timeout=None):
    """Worker sem acesso ao armazenamento Optuna; cada trial usa os mesmos casos.

    trial_timeout é verificado antes de cada execução (instância × seed);
    uma execução já iniciada nunca é interrompida.
    """
    plugin = algorithm_module(algorithm)
    parameters = {**parameters, "max_evaluations": parameters.get("max_evaluations", budget)}
    target = parameters["max_evaluations"]
    started, rows, instance_scores = time.monotonic(), [], []
    for case in cases:
        instance = read_instance(case["path"])
        if instance.digest != case["sha256"]:
            raise ValueError(f"Entrada mudou durante a calibração: {instance.path}")
        scores = []
        for seed in seeds:
            tick = time.monotonic()
            if trial_timeout is not None and tick-started > trial_timeout:
                raise TrialTimeout(f"limite de {trial_timeout} s excedido após {len(rows)} execuções")
            row = dict(instance=instance.path.name, instance_sha256=instance.digest, seed=seed,
                       target_evaluations=target)
            row.update(plugin.generation_metrics(parameters, 0))
            try:
                result = plugin.run_single(instance, parameters, seed)
            except RuntimeError as error:
                # Falha construtiva conhecida é desempenho do método, não prova de inviabilidade.
                if not any(message in str(error) for message in (
                    "Sampling construtivo não encontrou posição viável",
                    "Inicialização aleatória não encontrou schedule completo",
                    "Inicialização não produziu nenhum schedule viável")):
                    raise
                row.update(status="initialization_failed", score=0.0, error=str(error),
                           attempts=0, points=[])
            else:
                attempts = result.evaluations if algorithm == "vns_vnd" else result.attempts
                if (not 0 <= attempts <= target or
                    (algorithm != "vns_vnd" and (attempts != target or result.pymoo_evaluations != target))):
                    raise RuntimeError(f"{algorithm} não respeitou o orçamento de avaliações")
                points = [list(solution.key) for solution in result.front]
                if any(solution.evaluation.tec_scale != case["bounds"]["cost_scale"] for solution in result.front):
                    raise ValueError("Escala de custo inconsistente")
                row.update(status="complete", score=normalized_hv(points, case["bounds"]),
                           attempts=attempts, rejected=result.rejected_evaluations,
                           stop_reason=getattr(result, "stop_reason", "target_reached"),
                           post_search_validations=getattr(result, "post_search_validations", None), points=points)
                row.update(plugin.generation_metrics(parameters, attempts))
            row["wall_seconds"] = time.monotonic()-tick
            scores.append(row["score"])
            rows.append(row)
        instance_scores.append(dict(instance=instance.path.name, median_score=statistics.median(scores)))
    return dict(parameters=parameters, worker_pid=os.getpid(), score=statistics.mean(r["median_score"] for r in instance_scores),
                instance_scores=instance_scores, runs=rows, wall_seconds=time.monotonic()-started)


@contextmanager
def study_lock(path):
    """Trava nativa liberada pelo SO mesmo se o coordenador terminar abruptamente."""
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Outro coordenador já está usando esta pasta de estudo") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _worker_setup():
    """Evita paralelismo BLAS aninhado; o paralelismo aqui é entre trials."""
    from threadpoolctl import threadpool_limits
    threadpool_limits(limits=1)


def export_study(study, output, budget, budget_mode="evaluations", *, algorithm):
    """Resumo legível e parâmetros reutilizáveis; não modifica defaults do solver."""
    plugin = algorithm_module(algorithm)
    trials = study.get_trials(deepcopy=False)
    with (output / "trials.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["trial", "state", "score", *plugin.SEARCH_SPACE, "target_evaluations", "wall_seconds", "error", "duplicate_of", "proposal_source"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for trial in trials:
            effective = trial.user_attrs.get("effective_parameters", {})
            writer.writerow(dict(trial=trial.number, state=trial.state.name, score=trial.value,
                **trial.params,
                target_evaluations=effective.get("max_evaluations"), wall_seconds=trial.user_attrs.get("wall_seconds"),
                error=trial.user_attrs.get("error"), duplicate_of=trial.user_attrs.get("duplicate_parameters"),
                proposal_source=trial.user_attrs.get("proposal_source")))
    completed = [trial for trial in trials if trial.state == TrialState.COMPLETE]
    report = dict(algorithm=algorithm, study_name=study.study_name, output_dir=str(output),
        completed_trials=len(completed), failed_trials=sum(t.state == TrialState.FAIL for t in trials),
        best_score=None, best_parameters=None, budget_mode=budget_mode,
        fixed_evaluations=budget if budget_mode == "evaluations" else None,
        status="provisional_calibration", pareto_proven=False,
        criterion="mean_over_instances(median_over_seeds(normalized_HV / 1.05^2))")
    if completed:
        best = study.best_trial
        resolved = plugin.resolve_parameters(best.params, budget, budget_mode)
        report.update(best_trial=best.number, best_score=best.value, best_parameters=resolved,
            search_parameters=best.params, solver_config=resolved,
            evidence=f"trials/trial_{best.number:06d}.json")
        report[f"{algorithm}_config"] = resolved
    active = study.user_attrs.get("active_space", {})
    report.update(search_space_size=math.prod(map(len, active.values())) if active else None,
        rejected_duplicate_suggestions=sum("duplicate_parameters" in t.user_attrs for t in trials),
        total_evaluation_seconds=sum(t.user_attrs.get("wall_seconds", 0) for t in trials),
        search_exhausted=study.user_attrs.get("search_exhausted", False))
    report["worker_pids"] = sorted({t.user_attrs["worker_pid"] for t in completed if "worker_pid" in t.user_attrs})
    per_instance = {}
    for trial in completed:
        for name, seconds in trial.user_attrs.get("run_seconds", {}).items():
            per_instance.setdefault(name, []).extend(seconds)
    report["median_seconds_per_instance"] = {name: statistics.median(seconds) for name, seconds in per_instance.items()}
    report["estimated_30_runs_serial_seconds"] = 30 * sum(report["median_seconds_per_instance"].values())
    report["timing_estimate_scope"] = "calibration configurations and budgets only; remeasure frozen configuration at final budget"
    atomic_json(output / "best_parameters.json", report)
    return report


def source_fingerprint():
    """SHA-256 das fontes que determinam o resultado de uma avaliação."""
    source_paths = [*sorted(Path(__file__).parent.glob("*.py")),
        *sorted((PROJECT_ROOT / "src/metaheuristics").glob("*.py")),
        PROJECT_ROOT / "src/problem.py", PROJECT_ROOT / "src/schedule.py"]
    return {str(path.relative_to(PROJECT_ROOT)): sha256(path.read_bytes()).hexdigest() for path in source_paths}


def protocol_differences(saved, current):
    """Compara conteúdo das entradas; caminhos absolutos podem mudar de máquina."""
    differences = []
    for key in sorted(set(saved) | set(current)):
        left, right = saved.get(key), current.get(key)
        if key == "cases" and isinstance(left, list) and isinstance(right, list):
            left = [{k: v for k, v in case.items() if k != "path"} for case in left]
            right = [{k: v for k, v in case.items() if k != "path"} for case in right]
        if left != right:
            differences.append(key)
    return differences


def calibrate(paths, *, seeds=(11, 29, 47), n_trials=60, budget=8000, workers=1,
              study_name=None, sampler_seed=42, resume=False, output_dir=None,
              budget_mode=None, search_space=None, trial_timeout=None, startup_trials=20, algorithm):
    """TPE ask/tell coordenado; workers só calculam, SQLite recebe um escritor.

    n_trials é o total desejado de tentativas (COMPLETE/FAIL), inclusive retomadas.
    Propostas usam lotes fixos; resultados são salvos assim que cada processo termina.
    """
    plugin = algorithm_module(algorithm)
    study_name = study_name or f"{algorithm}_tpe_v6"
    if type(startup_trials) is not int or startup_trials < 0:
        raise ValueError("startup_trials deve ser inteiro não negativo")
    budget_mode = budget_mode or plugin.SUPPORTED_BUDGET_MODES[0]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", study_name):
        raise ValueError("Nome do estudo: 1–80 letras ASCII, números, _ ou -, começando por letra/número")
    if min(n_trials, workers, budget) < 1 or not 0 <= sampler_seed < 2**32:
        raise ValueError("Trials/workers/avaliações positivos; sampler-seed entre 0 e 2^32-1")
    if not seeds or any(not isinstance(seed, int) or seed < 0 for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("Seeds devem ser inteiros não negativos distintos")
    if trial_timeout is not None and (isinstance(trial_timeout, bool) or not trial_timeout > 0):
        raise ValueError("Limite por trial deve ser positivo, em segundos")
    space = plugin.validate_space(plugin.SEARCH_SPACE if search_space is None else search_space, budget, budget_mode)
    paths = list(dict.fromkeys(Path(path).resolve() for path in paths))
    if not paths:
        raise ValueError("Selecione pelo menos uma instância")
    cases = []
    for path in paths:
        instance = read_instance(path)
        if any(c["sha256"] == instance.digest for c in cases):
            raise ValueError("Entradas com conteúdo idêntico duplicariam o peso de uma instância")
        cases.append(dict(path=str(path), sha256=instance.digest, bounds=calculate_bounds(instance)))
    output = Path(output_dir or PROJECT_ROOT / "data/output/hyperparameters_tuning" / algorithm / study_name).resolve()
    protocol = dict(version=PROTOCOL_VERSION, algorithm=algorithm, tuner="Optuna TPE", cases=cases,
        seeds=list(seeds), budget_mode=budget_mode,
        budget_per_run=budget if budget_mode == "evaluations" else None, workers=workers, sampler_seed=sampler_seed,
        study_name=study_name, search_space=space, reference=list(REFERENCE),
        generation_definition=plugin.GENERATION_DEFINITION,
        cost_policy="mesmo cap por busca; esforço real registrado" if budget_mode == "evaluations" else "qualidade sob esforço variável; confirmar orçamento comum",
        fixed_choices=plugin.FIXED_CHOICES,
        aggregation="mean(instance median(seed normalized_HV / 1.05^2))",
        normalization="input_only_individual_option_extrema_v1; constant_axis=0",
        pruning=False, trial_timeout=trial_timeout, backend="CPU processes; fixed ordered batches; single SQLite writer",
        sampler_rng="JSON checkpoint after batch proposals; orphan RUNNING trials become FAIL",
        startup_trials=startup_trials, multivariate=True, duplicate_policy="reject then uniform unseen fallback",
        python=platform.python_version(),
        packages={name: importlib.metadata.version(name) for name in (
            "optuna", "pymoo", "numpy", "scipy", "moocore", "threadpoolctl", *(("numba", "llvmlite") if algorithm == "age" else ()))},
        source_sha256=source_fingerprint())
    output.mkdir(parents=True, exist_ok=True)
    with study_lock(output / "study.lock"):
        protocol_file, database = output / "protocol.json", output / "study.sqlite3"
        if protocol_file.exists():
            if not resume:
                raise ValueError("Estudo já existe; use --resume ou escolha outro nome/pasta")
            saved = json.loads(protocol_file.read_text(encoding="utf-8"))
            changed = protocol_differences(saved, protocol)
            if changed:
                raise ValueError(f"Estudo incompatível; campos diferentes: {', '.join(changed)}. "
                                 "Preserve o estudo e confira ambiente, código e opções")
            if not database.exists():
                raise ValueError("Banco do estudo ausente; não é possível retomar")
        elif resume:
            raise ValueError("Estudo não encontrado para --resume")
        else:
            if database.exists():
                raise ValueError("Banco sem protocolo; escolha outra pasta para preservar os dados")
            atomic_json(protocol_file, protocol)
        storage = optuna.storages.RDBStorage(url="sqlite:///" + database.as_posix())
        sampler = optuna.samplers.TPESampler(seed=sampler_seed, constant_liar=True, multivariate=True,
                                           n_startup_trials=startup_trials)
        study = optuna.create_study(storage=storage, study_name=study_name, sampler=sampler,
                                    direction="maximize", load_if_exists=resume)
        rng = random.Random(sampler_seed)
        _restore_sampler_state(study, rng)
        active_space = {k: v for k, v in space.items() if k != "max_evaluations" or budget_mode == "effort"}
        study.set_user_attr("active_space", active_space)
        (output / "trials").mkdir(exist_ok=True)
        # Só este coordenador escreve; após interrupção abrupta, trials órfãos viram FAIL.
        for stale in study.get_trials(states=(TrialState.RUNNING,)):
            study.tell(stale.number, state=TrialState.FAIL)
        if not study.trials:
            control = {name: values[len(values)//2] for name, values in space.items()}
            preferred = dict(population_size=100, n_neighbors=20,
                prob_neighbor_mating=.9, crossover_probability=.9, mutation_probability=.3,
                initial_solutions=4, max_candidates_per_neighborhood=100, shaking_attempts=20, max_evaluations=8000)
            control.update({name: value for name, value in preferred.items() if name in space and value in space[name]})
            if budget_mode == "evaluations":
                control.pop("max_evaluations", None)
            study.enqueue_trial(control)
        total_before = sum(t.state in (TrialState.COMPLETE, TrialState.FAIL) for t in study.trials)
        remaining = max(0, n_trials-total_before)
        effort = f"cap {budget} avaliações/busca" if budget_mode == "evaluations" else plugin.GENERATION_DEFINITION
        print(f"{remaining} trials novos; {len(cases)} entradas × {len(seeds)} seeds; {effort}.", flush=True)
        print(f"CPU: até {min(workers, remaining)} processos entre configurações; BLAS limitado a 1 thread/processo.", flush=True)
        if trial_timeout is not None:
            print(f"Limite de segurança: {trial_timeout} s por trial; excedido vira FAIL.", flush=True)
        pool = ProcessPoolExecutor(max_workers=min(workers, remaining),
            mp_context=multiprocessing.get_context("spawn"), initializer=_worker_setup) if workers > 1 and remaining else None
        if pool is None:
            _worker_setup()
        try:
            while remaining:
                batch = []
                try:
                    for _ in range(min(workers, remaining)):
                        seen = {tuple(sorted(t.params.items())) for t in study.get_trials(deepcopy=False)
                                if t.state in (TrialState.COMPLETE, TrialState.RUNNING, TrialState.FAIL)
                                and set(t.params) == set(active_space)}
                        unseen = _unseen_parameters(space, budget_mode, seen, rng)
                        if unseen is None:
                            study.set_user_attr("search_exhausted", True)
                            break
                        explore = n_trials - remaining + len(batch) < startup_trials
                        if explore and not study.get_trials(states=(TrialState.WAITING,)):
                            study.enqueue_trial(unseen)
                        for attempt in range(11):
                            if attempt == 10:
                                study.enqueue_trial(unseen)
                            trial = study.ask()
                            batch.append((trial, None, None))
                            parameters = plugin.suggest_parameters(trial, budget, budget_mode, space)
                            if tuple(sorted(trial.params.items())) not in seen:
                                break
                            previous = next(t.number for t in study.get_trials(deepcopy=False)
                                            if t.number != trial.number and t.params == trial.params)
                            trial.set_user_attr("duplicate_parameters", previous)
                            study.tell(trial, state=TrialState.PRUNED)
                            _save_sampler_state(study, rng)
                            batch.pop()
                        trial.set_user_attr("proposal_source", "exploration" if explore else "fallback" if attempt == 10 else "tpe")
                        trial.set_user_attr("effective_parameters", parameters)
                        _save_sampler_state(study, rng)
                        future = pool.submit(evaluate_parameters, parameters, cases, seeds, budget,
                            algorithm=algorithm, trial_timeout=trial_timeout) if pool else None
                        batch[-1] = trial, future, parameters
                    _save_sampler_state(study, rng)
                    pending = {future: (trial, future, parameters) for trial, future, parameters in batch} if pool else {}
                    ordered_results = (pending[future] for future in as_completed(pending)) if pool else batch
                    for trial, future, parameters in ordered_results:
                        try:
                            payload = future.result() if future else evaluate_parameters(
                                parameters, cases, seeds, budget, algorithm=algorithm, trial_timeout=trial_timeout)
                        except TrialTimeout as error:
                            # Só o trial lento falha; o estudo segue com os demais.
                            trial.set_user_attr("error", f"timeout: {error}")
                            study.tell(trial, state=TrialState.FAIL)
                            print(f"Trial {trial.number}: FAIL por timeout ({error}); {trial.params}", flush=True)
                            continue
                        atomic_json(output / "trials" / f"trial_{trial.number:06d}.json", dict(trial=trial.number, **payload))
                        trial.set_user_attr("wall_seconds", payload["wall_seconds"])
                        trial.set_user_attr("worker_pid", payload["worker_pid"])
                        run_seconds = {}
                        for row in payload["runs"]:
                            run_seconds.setdefault(row["instance"], []).append(row["wall_seconds"])
                        trial.set_user_attr("run_seconds", run_seconds)
                        study.tell(trial, payload["score"])
                        print(f"Trial {trial.number}: score={payload['score']:.6f}; {trial.params}", flush=True)
                except BaseException as error:
                    for trial, future, _ in batch:
                        if future is not None:
                            future.cancel()
                        state = next(t.state for t in study.get_trials(deepcopy=False) if t.number == trial.number)
                        if state == TrialState.RUNNING:
                            trial.set_user_attr("error", f"{type(error).__name__}: {error}")
                            study.tell(trial, state=TrialState.FAIL)
                    raise
                remaining -= len(batch)
                export_study(study, output, budget, budget_mode, algorithm=algorithm)
                if not batch or study.user_attrs.get("search_exhausted"):
                    break
        finally:
            if pool:
                pool.shutdown(wait=True, cancel_futures=True)
            report = export_study(study, output, budget, budget_mode, algorithm=algorithm)
            storage.engine.dispose()
    return report


