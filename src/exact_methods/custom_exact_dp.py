"""Varredura epsilon totalmente própria: somente biblioteca padrão do Python.

Programação dinâmica por subconjuntos, último job e rótulos (término, energia).
As tabelas das máquinas são compartilhadas pelos subproblemas Cmax <= epsilon.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from problem import (PROJECT_ROOT, Instance, archive_output, atomic_json, energy_scale,
                     generate_choices, has_valid_setups, insert_pareto,
                     overlaps_any, read_instance)


FORMAT_VERSION = 1
DEFAULT_MAX_JOBS = 13
DEFAULT_TOTAL_SECONDS = 600
DEFAULT_MEMORY_MIB = 1024


@lru_cache(None)
def memory_reader():
    """Leitura nativa de RSS; não instala dependências de monitoramento."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        api = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        api.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        api.GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = kernel.GetCurrentProcess()

        def read():
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if not api.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                raise ctypes.WinError(ctypes.get_last_error())
            return dict(rss_mib=counters.WorkingSetSize / 2**20,
                        peak_rss_mib=counters.PeakWorkingSetSize / 2**20,
                        private_mib=counters.PrivateUsage / 2**20,
                        peak_private_mib=counters.PeakPagefileUsage / 2**20,
                        source="Windows GetProcessMemoryInfo")
        return read
    import resource

    def read():
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak = value / (2**20 if sys.platform == "darwin" else 1024)
        rss = None
        if sys.platform.startswith("linux"):
            import os
            rss = int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20
        return dict(rss_mib=rss, peak_rss_mib=peak, source="resource.getrusage; /proc quando disponível")
    return read


def publish_baseline(instance, report):
    """Publica somente a fronteira completa, com schedules para avaliação futura."""
    if report.get("status") != "complete" or not report.get("pareto_proven"):
        return
    baseline = {key: report[key] for key in (
        "instance", "instance_sha256", "method", "status", "pareto_proven",
        "horizon", "minimum_makespan", "cost_scale", "front")}
    baseline["front"] = [{key: value for key, value in point.items() if key != "x_nonzero"}
                         for point in baseline["front"]]
    baseline["baseline_version"] = 1
    baseline["source_result"] = str(PROJECT_ROOT / "data/output/custom_exact_dp" / (instance.path.stem + ".json"))
    atomic_json(PROJECT_ROOT / "data/baselines" / f"{instance.path.stem}_custom_exact_dp.json", baseline)


def export_profile(instance, report, output):
    """Uma linha por execução medida, sem criar logs ou um gerador separado."""
    path = Path(output).parent / "desempenho.csv"
    metrics, stats = report.get("run_metrics", {}), report.get("preparation_stats", {})
    row = dict(instance=instance.path.name, instance_sha256=instance.digest, n=instance.n,
               m=instance.m, modes=instance.modes, horizon=instance.horizon,
               status=report["status"], pareto_proven=report["pareto_proven"],
               stop_reason=report["stop_reason"], points=len(report["front"]),
               epsilons=len(report["sweep"]), wall_seconds=metrics.get("wall_seconds"),
               cpu_seconds=metrics.get("cpu_seconds"), peak_rss_mib=metrics.get("peak_rss_mib"),
               peak_private_mib=metrics.get("peak_private_mib"),
               rss_initial_mib=metrics.get("rss_initial_mib"),
               preparation_seconds=stats.get("preparation_seconds"),
               transitions=stats.get("transitions"), inserted_labels=stats.get("inserted_labels"),
               rejected_labels=stats.get("rejected_labels"), removed_labels=stats.get("removed_labels"),
               peak_active_state_labels=stats.get("peak_active_state_labels"),
               retained_subset_labels=stats.get("retained_subset_labels"),
               memory_source=metrics.get("source"), code_sha256=report.get("code_sha256"),
               version="cache_liberado", run_kind="resume" if report.get("run_parameters",{}).get("resume") else "fresh")
    previous = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as stream:
            previous = list(csv.DictReader(stream))
    previous.append(row)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerows(sorted(previous, key=lambda item: (int(item["n"]), item["instance"])))


def minimum_makespan(instance: Instance, *, max_jobs: int = 16) -> dict:
    """Considera todas as sequências e partições; permite máquinas vazias.

    Todos os jobs estão disponíveis em zero. Sem objetivo de energia, usar
    o modo mais rápido e remover ociosidade nunca aumenta o makespan.
    Não há setup inicial no modelo compartilhado.
    """
    if instance.n > max_jobs:
        raise ValueError(f"DP exponencial limitada a {max_jobs} jobs; entrada tem {instance.n}")
    started = time.monotonic()
    n, m = instance.n, instance.m
    full = (1 << n) - 1
    modes = [[min(range(instance.modes), key=lambda l: instance.duration(j, i, l))
              for j in range(n)] for i in range(m)]
    duration = [[instance.duration(j, i, modes[i][j]) for j in range(n)] for i in range(m)]

    @lru_cache(None)
    def ending(i, subset, last):
        before = subset ^ (1 << last)
        if not before:
            return duration[i][last]
        return duration[i][last] + min(
            ending(i, before, j) + instance.setup[i][j][last]
            for j in range(n) if before & (1 << j))

    @lru_cache(None)
    def machine_time(i, subset):
        return min((ending(i, subset, j) for j in range(n) if subset & (1 << j)), default=0)

    @lru_cache(None)
    def partition(count, subset):
        if count == 1:
            return machine_time(0, subset), subset
        best = (float("inf"), 0)
        assigned = subset
        while True:
            value = max(machine_time(count - 1, assigned), partition(count - 1, subset ^ assigned)[0])
            if value < best[0]:
                best = value, assigned
            if assigned == 0:
                break
            assigned = (assigned - 1) & subset
        return best

    optimum = partition(m, full)[0]
    schedule = []
    subset = full
    for count in range(m, 0, -1):
        machine = count - 1
        assigned = partition(count, subset)[1]
        subset ^= assigned
        if not assigned:
            continue
        last = min((j for j in range(n) if assigned & (1 << j)),
                   key=lambda j: ending(machine, assigned, j))
        reversed_sequence = []
        while assigned:
            reversed_sequence.append(last)
            before = assigned ^ (1 << last)
            if before:
                previous = min((j for j in range(n) if before & (1 << j)),
                               key=lambda j: ending(machine, before, j) + instance.setup[machine][j][last])
                last = previous
            assigned = before
        finish, previous = 0, None
        for job in reversed(reversed_sequence):
            start = finish + (instance.setup[machine][previous][job] if previous is not None else 0)
            finish = start + duration[machine][job]
            schedule.append(dict(job=job, machine=machine, mode=modes[machine][job], start=start, end=finish))
            previous = job
    return dict(instance=str(instance.path), instance_sha256=instance.digest,
                method="makespan_dp", status="optimal" if optimum <= instance.horizon else "infeasible",
                minimum_makespan=optimum, horizon=instance.horizon,
                schedule=sorted(schedule, key=lambda row: row["job"]),
                elapsed_seconds=time.monotonic() - started)


@dataclass(frozen=True, slots=True)
class Label:
    end: int
    energy: int
    job: int
    index: int
    previous: Label | None


def insert_label(front, candidate):
    """Mantém términos crescentes e energias estritamente decrescentes."""
    low, high = 0, len(front)
    while low < high:
        middle = (low + high) // 2
        if front[middle].end <= candidate.end:
            low = middle + 1
        else:
            high = middle
    if low and front[low - 1].energy <= candidate.energy:
        return False
    position = low
    if position and front[position - 1].end == candidate.end:
        position -= 1
    stop = position
    while stop < len(front) and front[stop].energy >= candidate.energy:
        stop += 1
    front[position:stop] = [candidate]
    return True


def next_cheaper(costs):
    """Próximo início com custo estritamente menor, em O(horizonte)."""
    result, stack = [len(costs)] * len(costs), []
    for start in range(len(costs) - 1, -1, -1):
        while stack and costs[stack[-1]] >= costs[start]:
            stack.pop()
        if stack:
            result[start] = stack[-1]
        stack.append(start)
    return result


def best_before(front, epsilon):
    """Menor energia entre os rótulos cujo término não excede epsilon."""
    low, high = 0, len(front)
    while low < high:
        middle = (low + high) // 2
        if front[middle].end <= epsilon:
            low = middle + 1
        else:
            high = middle
    return front[low - 1] if low else None


class EnergyDP:
    def __init__(self, instance, *, max_jobs=DEFAULT_MAX_JOBS):
        if instance.n > max_jobs:
            raise ValueError(f"DP limitada a {max_jobs} tarefas; use --max-jobs para ampliação controlada")
        self.instance = instance
        self.scale, prices = energy_scale(instance)
        self.choices = generate_choices(instance, prices)
        self.lower_bound = sum(min(c.cost_units for c in row) for row in self.choices)
        self.groups = [[[] for _ in range(instance.n)] for _ in range(instance.m)]
        self.lookup = []
        for job, options in enumerate(self.choices):
            self.lookup.append({(c.machine, c.mode, c.start): k for k, c in enumerate(options)})
            for machine in range(instance.m):
                for mode in range(instance.modes):
                    indices = [k for k, c in enumerate(options) if c.machine == machine and c.mode == mode]
                    if indices:
                        costs = [options[k].cost_units for k in indices]
                        self.groups[machine][job].append((indices, next_cheaper(costs)))
        self.frontiers = []
        self.ready = False
        self.stats = dict(transitions=0, inserted_labels=0, rejected_labels=0, machines_completed=0)

    def prepare(self, *, deadline=None, max_transitions=None, memory_limit_mib=None):
        """Enumera todos os subconjuntos/sequências, podando rótulos dominados.

        Para o mesmo subconjunto e último job, acabar antes com menor ou igual
        energia permite imitar qualquer continuação do rótulo dominado.
        Somente após concluir TODAS as máquinas é permitido provar um epsilon.
        """
        instance = self.instance
        count = 1 << instance.n
        started, last_progress = time.monotonic(), time.monotonic()
        self.frontiers = []
        self.ready = False
        self.stats = dict(transitions=0, inserted_labels=0, rejected_labels=0, machines_completed=0,
                          removed_labels=0, peak_active_state_labels=0, machine_state_labels=[])
        for machine in range(instance.m):
            states = [{} for _ in range(count)]
            states[0][-1] = [Label(0, 0, -1, -1, None)]
            active_labels = 1
            self.stats["peak_active_state_labels"] = max(self.stats["peak_active_state_labels"], 1)
            for subset in range(count):
                for last, labels in states[subset].items():
                    for label in labels:
                        for job in range(instance.n):
                            if subset & (1 << job):
                                continue
                            earliest = label.end + (instance.setup[machine][last][job] if last >= 0 else 0)
                            for indices, cheaper in self.groups[machine][job]:
                                start = earliest
                                while start < len(indices):
                                    if ((deadline is not None and time.monotonic() >= deadline)
                                            or (max_transitions is not None and self.stats["transitions"] >= max_transitions)):
                                        self.stats["preparation_seconds"] = time.monotonic() - started
                                        self.stats["stop_reason"] = "preparation_interrupted"
                                        return False
                                    # Limite cooperativo: a memória é amostrada a cada 4096 transições.
                                    if memory_limit_mib and self.stats["transitions"] % 4096 == 0:
                                        memory = memory_reader()()
                                        if (memory["rss_mib"] or memory["peak_rss_mib"]) >= memory_limit_mib:
                                            self.stats["preparation_seconds"] = time.monotonic() - started
                                            self.stats["stop_reason"] = "memory_limit"
                                            return False
                                    self.stats["transitions"] += 1
                                    index = indices[start]
                                    choice = self.choices[job][index]
                                    candidate = Label(choice.end, label.energy + choice.cost_units, job, index, label)
                                    target = states[subset | (1 << job)].setdefault(job, [])
                                    before = len(target)
                                    inserted = insert_label(target, candidate)
                                    self.stats["inserted_labels" if inserted else "rejected_labels"] += 1
                                    active_labels += len(target) - before
                                    if inserted:
                                        self.stats["removed_labels"] += before + 1 - len(target)
                                    self.stats["peak_active_state_labels"] = max(
                                        self.stats["peak_active_state_labels"], active_labels)
                                    # Inícios posteriores de custo igual ou maior são
                                    # dominados por este início, no mesmo modo/job.
                                    start = cheaper[start]
                now = time.monotonic()
                if now - last_progress >= 10:
                    print(f"[{instance.path.name}] DP energia: máquina {machine + 1}/{instance.m}, "
                          f"subconjunto {subset + 1}/{count}, transições={self.stats['transitions']}", flush=True)
                    last_progress = now
            merged = []
            for state in states:
                front = []
                for labels in state.values():
                    for label in labels:
                        insert_label(front, label)
                merged.append(front)
            self.frontiers.append(merged)
            self.stats["machines_completed"] += 1
            self.stats["machine_state_labels"].append(active_labels)
            del states
        self.ready = True
        self.stats["preparation_seconds"] = time.monotonic() - started
        self.stats["retained_subset_labels"] = sum(len(f) for machine in self.frontiers for f in machine)
        return True

    def solve(self, epsilon):
        """Particiona jobs entre máquinas minimizando a energia com o teto dado."""
        if not self.ready:
            raise ValueError("As tabelas de energia ainda não foram concluídas")
        if not 0 <= epsilon <= self.instance.horizon:
            raise ValueError("epsilon fora do horizonte")
        options = [[best_before(front, epsilon) for front in table] for table in self.frontiers]
        infinity = float("inf")

        @lru_cache(None)
        def partition(count, subset):
            if count == 1:
                label = options[0][subset]
                return (label.energy, label.end, subset) if label else (infinity, infinity, 0)
            best = infinity, infinity, 0
            assigned = subset
            while True:
                label = options[count - 1][assigned]
                if label is not None:
                    cost, end, _ = partition(count - 1, subset ^ assigned)
                    candidate = cost + label.energy, max(end, label.end), assigned
                    if candidate[:2] < best[:2]:
                        best = candidate
                if assigned == 0:
                    break
                assigned = (assigned - 1) & subset
            return best

        subset = (1 << self.instance.n) - 1
        cost, end, _ = partition(self.instance.m, subset)
        if cost == infinity:
            partition.cache_clear()
            partition = None
            return None
        indices = [-1] * self.instance.n
        for count in range(self.instance.m, 0, -1):
            assigned = partition(count, subset)[2]
            subset ^= assigned
            label = options[count - 1][assigned]
            while label.job >= 0:
                if indices[label.job] >= 0:
                    raise AssertionError("Tarefa repetida na partição")
                indices[label.job] = label.index
                label = label.previous
        selected = [self.choices[j][k] for j, k in enumerate(indices)]
        if (any(k < 0 for k in indices) or overlaps_any(selected) or not has_valid_setups(self.instance, selected)
                or max(c.end for c in selected) != end or end > epsilon
                or sum(c.cost_units for c in selected) != cost):
            raise AssertionError("Falha na reconstrução da solução exata")
        # A função recursiva fecha sobre si própria: quebrar o ciclo libera
        # imediatamente as tabelas, que só servem para este epsilon.
        partition.cache_clear()
        partition = None
        return (end, cost), tuple(indices)

    def indices_from_schedule(self, schedule):
        """Converte um escalonamento conhecido, como o da DP de makespan."""
        indices = [-1] * self.instance.n
        for row in schedule:
            indices[row["job"]] = self.lookup[row["job"]][row["machine"], row["mode"], row["start"]]
        return tuple(indices)


def solve_front(instance, *, output, total_seconds=DEFAULT_TOTAL_SECONDS, epsilon_max=None,
                resume=False, restart=False, max_transitions=None, max_jobs=DEFAULT_MAX_JOBS,
                memory_limit_mib=DEFAULT_MEMORY_MIB, profile=False):
    """Salva cada epsilon provado; a retomada reconstrói as tabelas de energia."""
    output = Path(output)
    if (total_seconds < 0 or (max_transitions is not None and max_transitions < 0)
            or max_jobs < 1 or memory_limit_mib < 0 or (resume and restart)):
        raise ValueError("Parâmetros inválidos")
    if instance.n > max_jobs:
        raise ValueError(f"DP limitada a {max_jobs} tarefas; entrada tem {instance.n}. Amplie com --max-jobs")
    maximum = instance.horizon if epsilon_max is None else epsilon_max
    if not 0 <= maximum <= instance.horizon:
        raise ValueError("epsilon máximo fora do horizonte")
    if resume and not output.exists():
        raise ValueError("Relatório não encontrado")
    if not resume and not restart and output.exists():
        raise ValueError("Resultado já existe; use --resume ou --restart")
    started = time.monotonic()
    code_digest = sha256(Path(__file__).read_bytes()).hexdigest()
    cpu_started = time.process_time()
    memory_initial = memory_reader()()
    deadline = started + total_seconds if total_seconds else None
    if resume:
        report = json.loads(output.read_text(encoding="utf-8"))
        if (report.get("format_version") != FORMAT_VERSION or report.get("method") not in ("epsilon_exact_dp", "custom_exact_dp")
                or report.get("instance_sha256") != instance.digest):
            raise ValueError("Relatório incompatível")
        if report["pareto_proven"]:
            publish_baseline(instance, report)
            return report
        if maximum < report["next_epsilon"] - 1:
            raise ValueError("Novo teto é menor que a faixa já provada")
        report["epsilon_max"] = maximum
    else:
        dp = minimum_makespan(instance, max_jobs=max(16, max_jobs))
        report = dict(format_version=FORMAT_VERSION, instance=str(instance.path), instance_sha256=instance.digest,
                      method="custom_exact_dp", status="incomplete", pareto_proven=False,
                      minimum_makespan=dp["minimum_makespan"], makespan_dp=dp,
                      horizon=instance.horizon, epsilon_max=maximum, next_epsilon=dp["minimum_makespan"],
                      sweep=[], front=[], proven_points=[], candidate=None, elapsed_seconds=0.0)
        if dp["status"] == "infeasible":
            report.update(status="complete", pareto_proven=True, stop_reason="instance_infeasible",
                          cost_scale=energy_scale(instance)[0],
                          run_metrics=dict(memory_reader()(), wall_seconds=time.monotonic() - started,
                                           cpu_seconds=time.process_time() - cpu_started,
                                           rss_initial_mib=memory_initial["rss_mib"]),
                          elapsed_seconds=time.monotonic() - started)
            atomic_json(output, report)
            publish_baseline(instance, report)
            if profile:
                export_profile(instance, report, output)
            return report
    if maximum < report["minimum_makespan"]:
        raise ValueError("epsilon máximo abaixo do makespan mínimo")
    initialization_started = time.monotonic()
    energy = EnergyDP(instance, max_jobs=max_jobs)
    initialization_seconds = time.monotonic() - initialization_started
    report.update(cost_scale=energy.scale, energy_lower_bound_units=energy.lower_bound,
                  method="custom_exact_dp",
                  code_sha256=code_digest,
                  run_parameters=dict(max_jobs=max_jobs, memory_limit_mib=memory_limit_mib,
                                      total_seconds=total_seconds, profile=profile, resume=resume),
                  solver="Programação dinâmica própria; biblioteca padrão Python")
    archive = [(tuple(p["point"]), tuple(p["indices"])) for p in report["proven_points"]]
    elapsed_before = report["elapsed_seconds"]
    if not archive:
        indices = energy.indices_from_schedule(report["makespan_dp"]["schedule"])
        point = report["minimum_makespan"], sum(energy.choices[j][k].cost_units for j, k in enumerate(indices))
        report["candidate"] = archive_output(instance, energy.choices, energy.scale, [(point, indices)])[0]

    def save(reason):
        finished = report["next_epsilon"] > maximum
        complete = finished and maximum == instance.horizon
        report.update(status="complete" if complete else "incomplete", pareto_proven=complete,
                      sweep_complete=finished, stop_reason=reason, preparation_stats=dict(energy.stats),
                      elapsed_seconds=elapsed_before + time.monotonic() - started,
                      proven_points=[dict(point=list(p), indices=list(idx)) for p, idx in archive],
                      front=archive_output(instance, energy.choices, energy.scale, archive))
        report["run_metrics"] = dict(memory_reader()(), wall_seconds=time.monotonic() - started,
                                     cpu_seconds=time.process_time() - cpu_started,
                                     rss_initial_mib=memory_initial["rss_mib"],
                                     energy_initialization_seconds=initialization_seconds,
                                     timing_context="Métricas da chamada atual; elapsed_seconds inclui retomadas")
        atomic_json(output, report)
        if complete:
            publish_baseline(instance, report)
        if profile and reason != "preparing_energy_tables" and reason != "running":
            export_profile(instance, report, output)
        return report

    save("preparing_energy_tables")
    try:
        if not energy.prepare(deadline=deadline, max_transitions=max_transitions, memory_limit_mib=memory_limit_mib):
            return save(energy.stats.get("stop_reason", "preparation_interrupted"))
        for epsilon in range(report["next_epsilon"], maximum + 1):
            if deadline is not None and time.monotonic() >= deadline:
                return save("total_time_limit")
            if memory_limit_mib:
                memory = memory_reader()()
                if (memory["rss_mib"] or memory["peak_rss_mib"]) >= memory_limit_mib:
                    return save("memory_limit")
            tick = time.monotonic()
            solution = energy.solve(epsilon)
            if solution is None:
                raise AssertionError("epsilon >= makespan mínimo deve ser viável")
            point, indices = solution
            changed = insert_pareto(archive, point, indices)
            report["candidate"] = None
            report["sweep"].append(dict(epsilon=epsilon, makespan=point[0], energy_units=point[1],
                                         proof="exact_dynamic_programming", seconds=time.monotonic() - tick))
            report["next_epsilon"] = epsilon + 1
            if changed or epsilon % 100 == 0 or epsilon == maximum:
                save("running")
                print(f"[{instance.path.name}] epsilon={epsilon}, Cmax={point[0]}, "
                      f"TEC={float(Fraction(point[1], energy.scale)):.9f}, Pareto={len(archive)}", flush=True)
    except KeyboardInterrupt:
        return save("keyboard_interrupt")
    return save("horizon_reached" if maximum == instance.horizon else "epsilon_max_reached")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=PROJECT_ROOT / "data/input/set1/6_2_1439_3_S_1-9.dat")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/output/custom_exact_dp")
    parser.add_argument("--total-time-limit", type=float, default=DEFAULT_TOTAL_SECONDS, help="segundos por execução; 0 sem limite")
    parser.add_argument("--epsilon-max", type=int)
    parser.add_argument("--max-jobs", type=int, default=DEFAULT_MAX_JOBS,
                        help="teto de tarefas permitido nesta execução")
    parser.add_argument("--memory-limit-mb", type=float, default=DEFAULT_MEMORY_MIB,
                        help="limite cooperativo de RSS em MiB; 0 sem limite")
    parser.add_argument("--profile", action="store_true", help="salva tempo, memória e rótulos em desempenho.csv")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()
    paths = sorted(args.input.glob("*.dat")) if args.input.is_dir() else [args.input]
    if not paths:
        parser.error("Nenhuma instância encontrada")
    for path in paths:
        try:
            report = solve_front(read_instance(path), output=args.output_dir / f"{path.stem}.json",
                                 total_seconds=args.total_time_limit, epsilon_max=args.epsilon_max,
                                 resume=args.resume, restart=args.restart, max_jobs=args.max_jobs,
                                 memory_limit_mib=args.memory_limit_mb, profile=args.profile)
            print(f"{path.name}: {report['status']}, pontos={len(report['front'])}, motivo={report['stop_reason']}")
        except (OSError, ValueError) as error:
            parser.error(str(error))


if __name__ == "__main__":
    main()
