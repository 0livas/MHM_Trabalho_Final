"""Contrato único de execução para os seis métodos.

``execute`` roda dentro de um processo filho (ver runner.py) e devolve um
dicionário serializável: pontos exatos (Cmax, TEC em unidades inteiras), auditoria
de viabilidade/dominância e metadados do método. Nenhuma implementação é alterada.
"""
from __future__ import annotations

from pathlib import Path
import sys
import time

from problem import PROJECT_ROOT, atomic_json, dominates_or_equals, read_instance
from schedule import ScheduleValidationError, evaluate_schedule, schedule_from_result_rows

def memory_reader():
    """Leitor nativo de memória do próprio processo (o mesmo da DP exata)."""
    sys.path.insert(0, str(PROJECT_ROOT / "src/exact_methods"))
    from custom_exact_dp import memory_reader as reader
    return reader()


def memory_fields(read, baseline):
    """Pico de memória do processo da execução: absoluto e acima do estado inicial."""
    now = read()
    return dict(peak_rss_mib=now["peak_rss_mib"], peak_private_mib=now.get("peak_private_mib"),
                baseline_rss_mib=baseline, peak_rss_delta_mib=now["peak_rss_mib"] - (baseline or 0),
                memory_source=now["source"])


INIT_FAILURE_MESSAGES = (
    "Sampling construtivo não encontrou posição viável",
    "Inicialização aleatória não encontrou schedule completo",
    "Inicialização não produziu nenhum schedule viável",
)


def nondominated(points):
    """Filtro não dominado com deduplicação; ordenado por Cmax."""
    front = []
    for point in sorted(set(map(tuple, points))):
        if not front or point[1] < front[-1][1]:
            front.append(point)
    return front


def audit(instance, candidates):
    """Reavalia cada schedule pelo avaliador comum e remove inviáveis/dominados.

    ``candidates``: lista de (chave declarada, schedule em triplas ou None).
    """
    valid, infeasible, mismatched = [], 0, 0
    for key, schedule in candidates:
        key = tuple(int(v) for v in key)
        if schedule is not None:
            try:
                evaluated = evaluate_schedule(instance, schedule).objective_key
            except ScheduleValidationError:
                infeasible += 1
                continue
            if evaluated != key:
                mismatched += 1
                key = evaluated
        valid.append((key, schedule))
    front = nondominated([key for key, _ in valid])
    keep = set(front)
    schedules = {}
    for key, schedule in valid:
        if key in keep and key not in schedules:
            schedules[key] = schedule
    return dict(points=[list(p) for p in front], raw_size=len(candidates), infeasible=infeasible,
                objective_mismatches=mismatched, filtered_size=len(front),
                schedules=[[[list(op) for op in machine] for machine in schedules[p]] if schedules[p] else None
                           for p in front])


def _run_exact(instance, parameters, scratch: Path):
    sys.path.insert(0, str(PROJECT_ROOT / "src/exact_methods"))
    import custom_exact_dp as dp
    max_jobs = parameters["max_jobs"]
    if instance.n > max_jobs:
        return dict(status="TIMEOUT_OR_MEM_LIMIT", stop_reason=f"exceeds_max_jobs ({instance.n} > {max_jobs})",
                    candidates=[], pareto_proven=False)
    # A campanha não sobrescreve as baselines publicadas do repositório.
    dp.publish_baseline = lambda *args, **kwargs: None
    report = dp.solve_front(instance, output=scratch / "exact_report.json", restart=True,
                            total_seconds=parameters["total_seconds"], max_jobs=max_jobs,
                            memory_limit_mib=parameters["memory_limit_mib"])
    candidates = [((p["makespan"], p["tec_exact"]["numerator"]), schedule_from_result_rows(instance, p["schedule"]))
                  for p in report["front"]]
    proven = bool(report.get("pareto_proven"))
    return dict(status="COMPLETED" if proven else "TIMEOUT_OR_MEM_LIMIT", stop_reason=report.get("stop_reason"),
                candidates=candidates, pareto_proven=proven, next_epsilon=report.get("next_epsilon"))


def _run_heuristic(instance, parameters, scratch: Path):
    sys.path.insert(0, str(PROJECT_ROOT / "src/heuristics/ociosidade"))
    sys.path.insert(0, str(PROJECT_ROOT / "src/heuristics/construtiva"))
    import ociosidade
    result = ociosidade.executar(instance)
    return dict(status="COMPLETED", candidates=[(p.objetivos, p.schedule) for p in result.frente],
                base_sequences=result.bases, pareto_proven=False)


def install_snapshots(algorithm, instance, snapshot: Path, interval: float, read_memory, baseline):
    """Salva periodicamente a fronteira da população corrente (pymoo ``tell``).

    Usa o próprio ``_final_front`` do método, igual ao fim normal da busca; nada no
    solver muda. Se o pai cortar a execução pelo limite de tempo, usa o último snapshot.
    """
    import importlib
    from pymoo.core.algorithm import Algorithm
    final_front = importlib.import_module(f"metaheuristics.{algorithm}")._final_front
    original = Algorithm.advance
    last = [time.perf_counter()]

    def advance(self, *args, **kwargs):
        value = original(self, *args, **kwargs)
        if time.perf_counter() - last[0] >= interval and self.pop is not None and len(self.pop):
            front = final_front(instance, self.pop)
            data = audit(instance, [(s.key, s.schedule) for s in front])
            data.update(evaluations=int(self.evaluator.n_eval), snapshot_elapsed_s=time.perf_counter() - started,
                        **memory_fields(read_memory, baseline))
            atomic_json(snapshot, data)
            last[0] = time.perf_counter()
        return value

    started = time.perf_counter()
    Algorithm.advance = advance


def install_vns_snapshots(instance, snapshot: Path, interval: float, read_memory, baseline):
    """VNS/VND: salva o arquivo não dominado (a fronteira que ``run`` devolve) após avaliações."""
    from metaheuristics.vns_vnd import VNSVND
    original = VNSVND._evaluate
    last = [time.perf_counter()]
    started = time.perf_counter()

    def _evaluate(self, schedule):
        value = original(self, schedule)
        if time.perf_counter() - last[0] >= interval and self.archive:
            data = audit(instance, [(key, solution.schedule) for key, solution in self.archive])
            data.update(initialization=dict(self.initialization),
                        evaluations=self.evaluations, snapshot_elapsed_s=time.perf_counter() - started,
                        **memory_fields(read_memory, baseline))
            atomic_json(snapshot, data)
            last[0] = time.perf_counter()
        return value

    VNSVND._evaluate = _evaluate


def _run_metaheuristic(algorithm, instance, parameters, seed, scratch: Path, snapshot_interval, read_memory, baseline):
    from hyperparameters_tuning.common import algorithm_module
    plugin = algorithm_module(algorithm)
    if snapshot_interval and algorithm == "vns_vnd":
        install_vns_snapshots(instance, scratch / "snapshot.json", snapshot_interval, read_memory, baseline)
    elif snapshot_interval:
        install_snapshots(algorithm, instance, scratch / "snapshot.json", snapshot_interval, read_memory, baseline)
    try:
        result = plugin.run_single(instance, dict(parameters), seed)
    except RuntimeError as error:
        if any(message in str(error) for message in INIT_FAILURE_MESSAGES):
            outcome = dict(status="INIT_FAILED", error=str(error), candidates=[], pareto_proven=False)
            if algorithm == "vns_vnd" and hasattr(error, "initialization"):
                outcome["initialization"] = dict(error.initialization)
            return outcome
        raise
    attempts = result.evaluations if algorithm == "vns_vnd" else result.attempts
    outcome = dict(status="COMPLETED", candidates=[(s.key, s.schedule) for s in result.front],
                   evaluations=attempts, rejected_evaluations=result.rejected_evaluations,
                   stop_reason=getattr(result, "stop_reason", "target_reached"), pareto_proven=False)
    if algorithm == "vns_vnd":
        outcome["initialization"] = dict(result.initialization)
    return outcome


def execute(algorithm: str, kind: str, instance_path: str, parameters: dict, seed, scratch: str,
            snapshot_interval: float | None = None) -> dict:
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    instance = read_instance(instance_path)
    read_memory = memory_reader()
    baseline = read_memory()["rss_mib"]
    cpu0 = time.process_time()
    if kind == "exact":
        outcome = _run_exact(instance, parameters, scratch)
    elif kind == "heuristic":
        outcome = _run_heuristic(instance, parameters, scratch)
    else:
        outcome = _run_metaheuristic(algorithm, instance, parameters, seed, scratch, snapshot_interval,
                                     read_memory, baseline)
    cpu = time.process_time() - cpu0
    candidates = outcome.pop("candidates")
    outcome.update(audit(instance, candidates))
    outcome.update(instance_sha256=instance.digest, cpu_seconds_child=cpu, **memory_fields(read_memory, baseline))
    return outcome


def check_dominance_consistency(reference, points):
    """Pontos do conjunto que dominam estritamente a referência (vazamento)."""
    return [p for p in points if any(dominates_or_equals(p, r) and tuple(p) != tuple(r) for r in reference)]
