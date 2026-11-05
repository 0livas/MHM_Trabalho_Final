"""Orquestrador: uma execução por processo filho, heartbeat, timeout e parada segura.

Cada (algoritmo, instância, run_id) roda num processo ``spawn`` isolado. O
processo principal só espera, escreve o heartbeat e trata sinais: Ctrl+C/SIGTERM
apenas ligam uma flag, então nenhuma escrita de checkpoint é cortada ao meio.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import gzip
import importlib.metadata
import json
import multiprocessing
import os
from pathlib import Path
import platform
import shutil
import signal
import statistics
import sys
import time
import traceback

from problem import PROJECT_ROOT, atomic_json, read_instance
from experiments.config import ALGORITHM_BY_ID, InstanceSpec, resolve_configuration, require_campaign_output
from experiments.ledger import TERMINAL, Ledger, now_iso, run_key

SRC = PROJECT_ROOT / "src"


@dataclass(frozen=True)
class Task:
    algorithm: str
    instance: InstanceSpec
    run_id: int
    seed: int | None

    @property
    def key(self):
        return run_key(self.algorithm, self.instance.name, self.run_id)


def build_tasks(algorithms, instances, runs, base_seed):
    """Ordem instância → replicação → algoritmo: campanhas parciais ficam pareadas."""
    tasks = []
    for spec in instances:
        for run_id in range(1, runs + 1):
            for algorithm in algorithms:
                deterministic = ALGORITHM_BY_ID[algorithm].deterministic
                if deterministic and run_id > 1:
                    continue
                tasks.append(Task(algorithm, spec, run_id, None if deterministic else base_seed + run_id))
    return tasks


def result_path(output: Path, task: Task) -> Path:
    return output / "runs" / task.algorithm / Path(task.instance.name).stem / f"run_{task.run_id:02d}.json"


# ------------------------------------------------------------------ processo filho
def _child(task_payload, result_file, log_file):
    sys.path.insert(0, str(SRC))
    with open(log_file, "a", encoding="utf-8") as log:
        sys.stdout = sys.stderr = log
        signal.signal(signal.SIGINT, signal.SIG_IGN)   # o pai decide quando parar
        try:
            from threadpoolctl import threadpool_limits
            threadpool_limits(limits=1)
        except ImportError:
            pass
        from experiments.adapters import execute
        started = time.perf_counter()
        try:
            outcome = execute(**task_payload)
        except MemoryError as error:
            outcome = dict(status="TIMEOUT_OR_MEM_LIMIT", error=f"MemoryError: {error}", points=[], schedules=[])
        except Exception as error:
            traceback.print_exc()
            outcome = dict(status="FAILED", error=f"{type(error).__name__}: {error}", points=[], schedules=[])
        outcome["wall_seconds_child"] = time.perf_counter() - started
        atomic_json(Path(result_file), outcome)


# ------------------------------------------------------------------ campanha
class Campaign:
    def __init__(self, output: Path, *, base_seed: int, heartbeat_seconds: float = 2.0,
                 exact_options: dict, mh_timeout: float | None = None, budget: int | None = None,
                 force_config=False):
        self.output = Path(output)
        require_campaign_output(self.output)
        self.ledger = Ledger(self.output)
        self.base_seed = base_seed
        self.heartbeat_seconds = heartbeat_seconds
        self.exact_options = exact_options
        self.mh_timeout = mh_timeout
        self.budget = budget
        self.snapshot_interval = 15.0
        self.force_config = force_config
        self.stop_requested = None
        self.simulate_interrupt_after = None

    # -------------------------------------------------------------- configuração
    def source_fingerprints(self):
        sources = sorted([*(SRC / "metaheuristics").glob("*.py"), *(SRC / "experiments").glob("*.py"),
                          SRC / "exact_methods/custom_exact_dp.py", SRC / "heuristics/ociosidade/ociosidade.py",
                          SRC / "problem.py", SRC / "schedule.py"])
        return {p.relative_to(PROJECT_ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in sources}

    def validate_identity(self, *, allow_initial_manifest=False):
        """Confere a identidade persistida antes de qualquer escrita de retomada."""
        current = self.source_fingerprints()
        path = self.output / "experiment_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        state = self.ledger.state
        if not self.ledger.state_path.exists() and any(self.output.iterdir()):
            raise ValueError("Diretório não vazio sem checkpoint; use um novo --output-dir")
        if (self.ledger.state_path.exists() and manifest is None
                and not (allow_initial_manifest and getattr(self, "_manifest_pending", False))):
            raise ValueError("Checkpoint sem manifesto de identidade; use um novo --output-dir")
        for saved in ([manifest] if manifest is not None else []) + ([state] if self.ledger.state_path.exists() else []):
            sources = saved.get("source_sha256")
            # Checkpoints antigos guardavam as fontes somente no manifesto.
            if sources is None and saved is state and manifest is not None:
                continue
            normalized = {k.replace("\\", "/"): v for k, v in (sources or {}).items()}
            if normalized != current:
                raise ValueError("Fontes incompatíveis com a campanha; use um novo --output-dir")
            if saved.get("base_seed") not in (None, self.base_seed):
                raise ValueError("base_seed incompatível com a campanha")
        return current, manifest

    def lock_configurations(self, algorithms, *, save=True):
        """Valida tudo antes de salvar; não permite mistura nem com --force-config."""
        sources, manifest = self.validate_identity()
        state = self.ledger.state
        if state["base_seed"] not in (None, self.base_seed):
            raise ValueError(f"Campanha iniciada com base_seed={state['base_seed']}; use o mesmo valor")
        configurations = {}
        for algorithm in algorithms:
            config = resolve_configuration(algorithm, exact_options=self.exact_options, budget=self.budget)
            for stored in (state["configurations"], (manifest or {}).get("configurations", {})):
                saved = stored.get(algorithm)
                if saved and saved["parameters"] != config["parameters"]:
                    raise ValueError(f"Configuração de {algorithm} incompatível; use um novo --output-dir")
            configurations[algorithm] = state["configurations"].get(algorithm, config)
        if not save:
            return configurations
        self._manifest_pending = manifest is None
        state["base_seed"] = self.base_seed
        state["source_sha256"] = sources
        state["configurations"].update(configurations)
        self.ledger.save()
        return configurations

    def write_manifest(self, algorithms, instances, runs, configurations):
        packages = {}
        for name in ("pymoo", "numpy", "scipy", "numba", "optuna"):
            try:
                packages[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name] = None
        sources, _ = self.validate_identity(allow_initial_manifest=True)
        info = []
        for spec in instances:
            instance = read_instance(spec.path)
            info.append(dict(name=spec.name, tier=spec.tier, path=spec.relative, sha256=instance.digest,
                             n=instance.n, m=instance.m, horizon=instance.horizon))
        manifest_path = self.output / "experiment_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else dict(history=[])
        manifest.update(updated=now_iso(), base_seed=self.base_seed, seed_rule="SEED_k = BASE_SEED + k (k = 1..R), compartilhada entre MHs",
                        configurations=self.ledger.state["configurations"], python=platform.python_version(),
                        platform=platform.platform(), cpu_count=os.cpu_count(), packages=packages,
                        source_sha256=sources)
        manifest.setdefault("instances", {}).update({i["name"]: i for i in info})
        manifest["history"].append(dict(session=self.ledger.session["id"] if self.ledger.session else None,
                                        at=now_iso(), algorithms=list(algorithms), runs=runs,
                                        instances=[s.name for s in instances],
                                        configurations={a: configurations[a] for a in algorithms}))
        atomic_json(manifest_path, manifest)
        self._manifest_pending = False

    # -------------------------------------------------------------- sinais
    def _on_signal(self, signum, frame):
        if self.stop_requested is None:
            self.stop_requested = signal.Signals(signum).name
            print(f"\n[{signal.Signals(signum).name}] parada solicitada — salvando o estado...", flush=True)

    def _install_signals(self):
        previous = {}
        for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            if hasattr(signal, name):
                sig = getattr(signal, name)
                previous[sig] = signal.signal(sig, self._on_signal)
        return previous

    # -------------------------------------------------------------- execução
    def run(self, algorithms, instances, runs, *, stop_after=None, argv=()):
        tasks = build_tasks(algorithms, instances, runs, self.base_seed)
        pending = [t for t in tasks if self.ledger.status_of(t.key) not in TERMINAL]
        configurations = self.lock_configurations(algorithms)
        session = self.ledger.start_session(argv)
        self.write_manifest(algorithms, instances, runs, configurations)
        print(f"Sessão {session['id']}: {len(tasks) - len(pending)} execuções já concluídas, "
              f"{len(pending)} pendentes.", flush=True)
        for algorithm in algorithms:
            print(f"  {algorithm:<10} {configurations[algorithm]['parameters']}  ({configurations[algorithm]['source']})")
        previous = self._install_signals()
        session_t0 = time.perf_counter()
        done_now, interrupted = [], None
        reason = "completed"
        try:
            for index, task in enumerate(pending, 1):
                if self.stop_requested:
                    reason = "signal:" + self.stop_requested
                    break
                if stop_after is not None and len(done_now) >= stop_after:
                    reason = f"stop_after={stop_after}"
                    break
                record = self._execute(task, configurations[task.algorithm], index, len(pending), session_t0)
                if record["status"] == "INTERRUPTED_PARTIAL":
                    interrupted = record
                    reason = "signal:" + (self.stop_requested or "SIGINT")
                    break
                done_now.append(record)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            self.ledger.end_session(reason)
            self.print_timing_summary(done_now, interrupted, reason)
        return dict(reason=reason, completed=done_now, interrupted=interrupted)

    def _execute(self, task, configuration, index, total, session_t0):
        spec = ALGORITHM_BY_ID[task.algorithm]
        target = result_path(self.output, task)
        scratch = self.output / "scratch" / target.parent.relative_to(self.output / "runs") / target.stem
        if scratch.exists():
            shutil.rmtree(scratch)
        scratch.mkdir(parents=True)
        result_file, log_file = scratch / "result.json", scratch / "child.log"
        payload = dict(algorithm=task.algorithm, kind=spec.kind, instance_path=str(task.instance.path),
                       parameters=configuration["parameters"], seed=task.seed, scratch=str(scratch),
                       snapshot_interval=self.snapshot_interval if spec.kind == "metaheuristic" else None)
        hard_limit = (self.exact_options["total_seconds"] + self.exact_options["grace_seconds"]
                      if spec.kind == "exact" and self.exact_options["total_seconds"] else
                      self.mh_timeout if spec.kind == "metaheuristic" else None)
        prior = [v["wall_seconds"] for v in self.ledger.state["runs"].values()
                 if v["algorithm"] == task.algorithm and v["instance"] == task.instance.name and v["status"] in TERMINAL]
        group_before = sum(prior)
        start_ts, t0 = now_iso(), time.perf_counter()
        process = multiprocessing.get_context("spawn").Process(target=_child, args=(payload, str(result_file), str(log_file)),
                                                               daemon=True)
        process.start()
        status, error = None, None
        last_print = 0.0
        while process.is_alive():
            process.join(min(0.5, self.heartbeat_seconds))
            elapsed = time.perf_counter() - t0
            if (self.simulate_interrupt_after is not None and not self.stop_requested
                    and time.perf_counter() - session_t0 >= self.simulate_interrupt_after):
                signal.raise_signal(signal.SIGINT)   # mesmo caminho de um Ctrl+C real
            if self.stop_requested:
                status = "INTERRUPTED_PARTIAL"
                break
            if hard_limit is not None and elapsed > hard_limit:
                status, error = "TIMEOUT_OR_MEM_LIMIT", f"hard timeout {hard_limit:.0f}s"
                break
            if elapsed - last_print >= self.heartbeat_seconds:
                last_print = elapsed
                totals = self.ledger.totals()
                beat = dict(session=self.ledger.session["id"], pid=os.getpid(), child_pid=process.pid, run_key=task.key,
                            algorithm=task.algorithm, instance=task.instance.name, run_id=task.run_id, seed=task.seed,
                            progress=f"{index}/{total}", current_run_elapsed_s=round(elapsed, 3),
                            algorithm_instance_accumulated_s=round(group_before + elapsed, 3),
                            session_active_s=round(time.perf_counter() - session_t0, 3),
                            campaign_active_total_s=round(totals["total_cumulative_wall_time_s"] + elapsed, 3))
                self.ledger.heartbeat(beat)
                line = (f"[{index}/{total}] {task.algorithm} {task.instance.name} run {task.run_id:02d} "
                        f"| run {_fmt(elapsed)} | alg×inst {_fmt(group_before + elapsed)} "
                        f"| campanha {_fmt(beat['campaign_active_total_s'])}")
                print("\r" + line.ljust(118), end="" if sys.stdout.isatty() else "\n", flush=True)
        wall_parent = time.perf_counter() - t0
        end_ts = now_iso()
        if process.is_alive():
            process.terminate()
            process.join(10)
            if process.is_alive():
                process.kill()
                process.join()
        outcome = {}
        snapshot = scratch / "snapshot.json"
        if status == "TIMEOUT_OR_MEM_LIMIT" and spec.kind == "metaheuristic" and snapshot.exists():
            # Fronteira da população no último snapshot antes do corte (orçamento parcial).
            outcome = json.loads(snapshot.read_text(encoding="utf-8"))
            status = "TIMEOUT_PARTIAL"
            outcome.update(stop_reason=f"time_limit {hard_limit:.0f}s; snapshot {outcome['snapshot_elapsed_s']:.1f}s, "
                                       f"{outcome['evaluations']} avaliações", pareto_proven=False)
        if status is None and self.stop_requested and not result_file.exists():
            status = "INTERRUPTED_PARTIAL"   # filho caiu junto com o Ctrl+C do console
        if status is None:
            if result_file.exists():
                outcome = json.loads(result_file.read_text(encoding="utf-8"))
                status = outcome["status"]
                error = outcome.get("error")
            else:
                status = "FAILED"
                error = f"processo filho terminou com código {process.exitcode} sem resultado; ver {log_file}"
        wall = outcome.get("wall_seconds_child", wall_parent)
        if status == "TIMEOUT_PARTIAL":
            wall = wall_parent
        record = dict(algorithm=task.algorithm, instance=task.instance.name, tier=task.instance.tier,
                      run_id=task.run_id, seed=task.seed, status=status, start_timestamp=start_ts,
                      end_timestamp=end_ts, wall_seconds=round(wall, 6),
                      cpu_seconds=round(outcome["cpu_seconds_child"], 6) if "cpu_seconds_child" in outcome else None,
                      peak_rss_mib=_round(outcome.get("peak_rss_mib")), peak_rss_delta_mib=_round(outcome.get("peak_rss_delta_mib")),
                      nds=outcome.get("filtered_size"), evaluations=outcome.get("evaluations"), raw_size=outcome.get("raw_size"),
                      infeasible=outcome.get("infeasible"), stop_reason=outcome.get("stop_reason"), error=error)
        if status == "INTERRUPTED_PARTIAL":
            record.update(interrupted_timestamp=end_ts, elapsed_seconds_before_stop=round(wall_parent, 6))
        if status in TERMINAL:
            outcome.setdefault("points", [])   # corte rígido pelo pai: execução sem fronteira
            schedules = outcome.pop("schedules", [])
            target.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(target.with_suffix(".schedules.json.gz"), "wt", encoding="utf-8") as stream:
                json.dump(schedules, stream)
            atomic_json(target, dict(record, process_wall_seconds=wall_parent,
                                     parameters=payload["parameters"], **outcome))
            record["result_file"] = str(target.relative_to(self.output))
            shutil.rmtree(scratch, ignore_errors=True)
        self.ledger.record(task.key, record)
        mark = {"COMPLETED": "ok", "INTERRUPTED_PARTIAL": "INTERROMPIDA"}.get(status, status)
        print(f"\r[{index}/{total}] {task.algorithm} {task.instance.name} run {task.run_id:02d} → {mark} "
              f"em {_fmt(wall)} (NDS={record['nds']})".ljust(118), flush=True)
        return record

    # -------------------------------------------------------------- resumo
    def print_timing_summary(self, done_now, interrupted, reason):
        totals = self.ledger.totals()
        print("\n" + "=" * 72)
        print(f"RESUMO DE TEMPOS — sessão {self.ledger.session['id']} encerrada ({reason})")
        by_alg, memory = {}, {}
        for record in done_now:
            by_alg.setdefault(record["algorithm"], []).append(record["wall_seconds"])
            if record.get("peak_rss_mib") is not None:
                memory.setdefault(record["algorithm"], []).append(record["peak_rss_mib"])
        print(f"Execuções terminadas nesta sessão: {len(done_now)}")
        for algorithm, values in sorted(by_alg.items()):
            print(f"  {algorithm:<10} n={len(values):<3} total={_fmt(sum(values))} média={_fmt(statistics.mean(values))} "
                  f"min={_fmt(min(values))} max={_fmt(max(values))}"
                  + (f" pico RAM={max(memory[algorithm]):.0f} MiB" if algorithm in memory else ""))
        if interrupted:
            print(f"Execução interrompida: {interrupted['algorithm']} {interrupted['instance']} run "
                  f"{interrupted['run_id']:02d} após {_fmt(interrupted['elapsed_seconds_before_stop'])} "
                  f"(início {interrupted['start_timestamp']}, parada {interrupted['interrupted_timestamp']})")
        print(f"Acumulado de todas as sessões ({totals['sessions']}): válido={_fmt(totals['valid_wall_s'])} "
              f"interrompido={_fmt(totals['interrupted_wall_s'])} falhas={_fmt(totals['failed_wall_s'])} "
              f"total={_fmt(totals['total_cumulative_wall_time_s'])}")
        print("=" * 72, flush=True)


def _round(value, digits=1):
    return round(value, digits) if value is not None else None


def _fmt(seconds):
    seconds = float(seconds or 0)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{int(hours):d}h{int(minutes):02d}m{secs:06.3f}s" if hours else f"{int(minutes):02d}m{secs:06.3f}s"


def status_dashboard(ledger: Ledger, algorithms, instances, runs, base_seed):
    """Tabela algoritmo × instância com concluídas, pendentes, falhas e ETA."""
    tasks = build_tasks(algorithms, instances, runs, base_seed)
    runs_state = ledger.state["runs"]
    rows, eta_total = [], 0.0
    for spec in instances:
        for algorithm in algorithms:
            group = [t for t in tasks if t.algorithm == algorithm and t.instance.name == spec.name]
            states = [ledger.status_of(t.key) for t in group]
            durations = [runs_state[t.key]["wall_seconds"] for t in group if ledger.status_of(t.key) in TERMINAL]
            if not durations:  # estimativa pela mesma faixa
                durations = [v["wall_seconds"] for v in runs_state.values()
                             if v["algorithm"] == algorithm and v["status"] in TERMINAL
                             and next((s.tier for s in instances if s.name == v["instance"]), None) == spec.tier]
            remaining = sum(s not in TERMINAL for s in states)
            mean = statistics.mean(durations) if durations else None
            eta = mean * remaining if mean is not None else None
            eta_total += eta or 0.0
            peaks = [runs_state[t.key].get("peak_rss_mib") for t in group if t.key in runs_state]
            peaks = [p for p in peaks if p is not None]
            rows.append(dict(peak_rss_mib=max(peaks) if peaks else None, instance=spec.name, tier=spec.tier, algorithm=algorithm, total=len(group),
                             completed=states.count("COMPLETED"), timeout=states.count("TIMEOUT_OR_MEM_LIMIT") + states.count("TIMEOUT_PARTIAL"),
                             init_failed=states.count("INIT_FAILED"), failed=states.count("FAILED"),
                             interrupted=states.count("INTERRUPTED_PARTIAL"), pending=states.count("PENDING"),
                             mean_s=mean, eta_s=eta))
    return rows, eta_total
