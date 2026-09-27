"""Busca exaustiva por backtracking para o UPMSP-SDS biobjetivo.

Cada decisão escolhe uma posição X[i,j,h,l] = 1. As outras posições de X
permanecem zero. A matriz densa nunca é materializada: isso evita armazenar
muitos zeros e deixa a enumeração de candidatos separada da futura avaliação
em lotes numa GPU. O backtracking usa CPU; a avaliação das folhas pode usar CUDA.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from math import ceil, lcm, prod
from pathlib import Path
import json
import os
import time


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORMAT_VERSION = 1


@dataclass(frozen=True)
class Instance:
    path: Path
    digest: str
    n: int
    m: int
    days: int
    slots_per_day: int
    modes: int
    peak_rate: Fraction
    off_rate: Fraction
    max_cost: Fraction
    peaks: tuple[tuple[int, int], ...]
    speed: tuple[Fraction, ...]
    power_factor: tuple[Fraction, ...]
    power: tuple[Fraction, ...]
    processing: tuple[tuple[int, ...], ...]  # [job][machine]
    setup: tuple[tuple[tuple[int, ...], ...], ...]  # [machine][previous][next]

    @property
    def horizon(self) -> int:
        return self.days * self.slots_per_day

    def duration(self, job: int, machine: int, mode: int) -> int:
        ratio = Fraction(self.processing[job][machine]) / self.speed[mode]
        return ceil(ratio)


@dataclass(frozen=True, slots=True)
class Choice:
    """Uma das posições X[i,j,h,l] possíveis para um job conhecido."""

    machine: int
    start: int
    mode: int
    end: int
    cost_units: int


def read_instance(path: Path | str) -> Instance:
    path = Path(path).resolve()
    raw = path.read_bytes()
    tokens = raw.decode("utf-8-sig").split()
    position = 0

    def take(key: str, count: int, convert):
        nonlocal position
        if position >= len(tokens) or tokens[position] != key:
            raise ValueError(f"Esperado '{key}' no token {position} de {path.name}")
        position += 1
        if position + count > len(tokens):
            raise ValueError(f"Faltam valores em '{key}'")
        values = tuple(convert(value) for value in tokens[position:position + count])
        position += count
        return values

    n = take("n", 1, int)[0]
    m = take("m", 1, int)[0]
    days = take("n_day", 1, int)[0]
    slots_per_day = take("hl", 1, int)[0] + 1
    modes = take("o", 1, int)[0]
    if min(n, m, days, slots_per_day, modes) <= 0:
        raise ValueError("Todas as dimensões devem ser positivas")
    peak_rate = take("rate_in_peak", 1, Fraction)[0]
    off_rate = take("rate_off_peak", 1, Fraction)[0]
    max_cost = take("max_cost", 1, Fraction)[0]
    peak_starts = take("peak_start", days, int)
    peak_ends = take("peak_end", days, int)
    speed = take("v", modes, Fraction)
    power_factor = take("lambda", modes, Fraction)
    power = take("pi", m, Fraction)
    processing_values = take("processing", n * m, int)
    setup_values = take("setup", m * n * n, int)
    if position != len(tokens):
        raise ValueError(f"Dados adicionais inesperados em {path.name}")
    if min(peak_rate, off_rate, *power_factor, *power) < 0 or min(speed) <= 0 or max_cost <= 0:
        raise ValueError("Tarifas, potência, velocidade ou max_cost inválidos")
    processing = tuple(processing_values[j * m:(j + 1) * m] for j in range(n))
    setup = tuple(
        tuple(setup_values[i * n * n + j * n:i * n * n + (j + 1) * n] for j in range(n))
        for i in range(m)
    )
    if any(value <= 0 for row in processing for value in row):
        raise ValueError("Tempos de processamento devem ser positivos")
    if any(value < 0 for matrix in setup for row in matrix for value in row):
        raise ValueError("Tempos de setup devem ser não negativos")
    peaks = tuple((start, end + 1) for start, end in zip(peak_starts, peak_ends))
    for day, (start, end) in enumerate(peaks):
        if not day * slots_per_day <= start < end <= (day + 1) * slots_per_day:
            raise ValueError("Horário de ponta fora do respectivo dia")
    return Instance(path, sha256(raw).hexdigest(), n, m, days, slots_per_day, modes,
                    peak_rate, off_rate, max_cost, peaks, speed, power_factor,
                    power, processing, setup)


def energy_scale(instance: Instance) -> tuple[int, tuple[tuple[int, int, int, int], ...]]:
    """Custo exato como inteiro / escala, evitando erros na dominância."""
    multiplier = Fraction(24, instance.slots_per_day)
    prices = tuple(
        (instance.power[machine] * instance.power_factor[mode] * multiplier * instance.peak_rate,
         instance.power[machine] * instance.power_factor[mode] * multiplier * instance.off_rate)
        for machine in range(instance.m) for mode in range(instance.modes)
    )
    scale = lcm(*(value.denominator for pair in prices for value in pair))
    integer_prices = tuple(
        (machine, mode, int(on * scale), int(off * scale))
        for (machine, mode), (on, off) in zip(
            ((machine, mode) for machine in range(instance.m) for mode in range(instance.modes)), prices
        )
    )
    return scale, integer_prices


def generate_choices(instance: Instance, prices: tuple[tuple[int, int, int, int], ...]) -> tuple[tuple[Choice, ...], ...]:
    """Gera posições individuais de X que cabem no horizonte, em ordem fixa."""
    by_job = []
    for job in range(instance.n):
        choices = []
        for machine, mode, on_price, off_price in prices:
            duration = instance.duration(job, machine, mode)
            for start in range(instance.horizon - duration + 1):
                end = start + duration
                peak_slots = sum(max(0, min(end, b) - max(start, a)) for a, b in instance.peaks)
                cost_units = on_price * peak_slots + off_price * (duration - peak_slots)
                choices.append(Choice(machine, start, mode, end, cost_units))
        if not choices:
            raise ValueError(f"Job {job} não cabe no horizonte em nenhuma máquina/modo")
        by_job.append(tuple(choices))
    return tuple(by_job)


def overlaps(choice: Choice, selected: list[Choice]) -> bool:
    """Sobreposição de processamento nunca pode ser reparada por futuros jobs."""
    return any(
        previous.machine == choice.machine
        and choice.start < previous.end
        and previous.start < choice.end
        for previous in selected
    )


def has_valid_setups(instance: Instance, selected: list[Choice]) -> bool:
    """Setup é validado na folha: futuros jobs podem mudar a adjacência."""
    for machine in range(instance.m):
        sequence = sorted(
            ((job, choice) for job, choice in enumerate(selected) if choice.machine == machine),
            key=lambda pair: pair[1].start,
        )
        for (previous_job, previous), (next_job, following) in zip(sequence, sequence[1:]):
            if following.start < previous.end + instance.setup[machine][previous_job][next_job]:
                return False
    return True


def has_irreparable_setup(instance: Instance, selected: list[Choice],
                          minimum_future_duration: tuple[int, ...]) -> bool:
    """Detecta pares com setup violado sem espaço para inserir um job futuro.

    Um job posterior só poderia reparar a adjacência entre dois jobs já
    escolhidos se coubesse integralmente no intervalo entre eles.
    """
    for machine in range(instance.m):
        sequence = sorted(
            ((job, choice) for job, choice in enumerate(selected) if choice.machine == machine),
            key=lambda pair: pair[1].start,
        )
        for (previous_job, previous), (next_job, following) in zip(sequence, sequence[1:]):
            gap = following.start - previous.end
            if (gap < instance.setup[machine][previous_job][next_job]
                    and gap < minimum_future_duration[machine]):
                return True
    return False


def dominates_or_equals(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] <= b[0] and a[1] <= b[1]


def insert_pareto(archive: list[tuple[tuple[int, int], tuple[int, ...]]],
                  point: tuple[int, int], choice_indices: tuple[int, ...]) -> bool:
    if any(dominates_or_equals(existing, point) for existing, _ in archive):
        return False
    archive[:] = [(existing, indices) for existing, indices in archive
                  if not dominates_or_equals(point, existing)]
    archive.append((point, choice_indices))
    archive.sort(key=lambda entry: (entry[0][0], entry[0][1]))
    return True


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def archive_output(instance: Instance, choices: tuple[tuple[Choice, ...], ...], scale: int,
                   archive: list[tuple[tuple[int, int], tuple[int, ...]]]) -> list[dict]:
    result = []
    for (makespan, energy_units), indices in sorted(archive, key=lambda entry: entry[0]):
        selected = [choices[job][index] for job, index in enumerate(indices)]
        result.append({
            "makespan": makespan,
            "tec": float(Fraction(energy_units, scale)),
            "tec_exact": {"numerator": energy_units, "denominator": scale},
            "normalized_makespan": makespan / instance.horizon,
            "normalized_tec": float(Fraction(energy_units, scale) / instance.max_cost),
            "x_nonzero": [
                {"i": choice.machine, "j": job, "h": choice.start, "l": choice.mode}
                for job, choice in enumerate(selected)
            ],
            "schedule": [
                {"job": job, "machine": choice.machine, "mode": choice.mode,
                 "start": choice.start, "end": choice.end}
                for job, choice in enumerate(selected)
            ],
        })
    return result


def initial_state(instance: Instance, choices: tuple[tuple[Choice, ...], ...], scale: int) -> dict:
    return {
        "format_version": FORMAT_VERSION,
        "instance_sha256": instance.digest,
        "cost_scale": scale,
        "option_counts": [len(job_choices) for job_choices in choices],
        "stack_next": [0],
        "selected_indices": [],
        "archive": [],
        "stats": {
            "candidate_decisions": 0,
            "covered_combinations": 0,
            "complete_assignments": 0,
            "valid_schedules": 0,
            "overlap_prunes": 0,
            "overlap_pruned_combinations": 0,
            "setup_pruned_combinations": 0,
            "invalid_setups": 0,
        },
        "elapsed_seconds": 0.0,
        "complete": False,
    }


def restore_state(path: Path, instance: Instance, choices: tuple[tuple[Choice, ...], ...], scale: int) -> dict:
    state = json.loads(path.read_text(encoding="utf-8"))
    if (state.get("format_version") != FORMAT_VERSION or state.get("instance_sha256") != instance.digest
            or state.get("cost_scale") != scale
            or state.get("option_counts") != [len(options) for options in choices]):
        raise ValueError(f"Checkpoint incompatível com {instance.path.name}")
    selected_indices = state["selected_indices"]
    stack_next = state["stack_next"]
    if len(stack_next) != len(selected_indices) + 1 or len(stack_next) > instance.n:
        if not (state.get("complete") and not stack_next and not selected_indices):
            raise ValueError("Pilha inválida no checkpoint")
    for job, index in enumerate(selected_indices):
        if not 0 <= index < len(choices[job]) or stack_next[job] != index + 1:
            raise ValueError("Decisão inválida no checkpoint")
    for depth, next_index in enumerate(stack_next):
        if not 0 <= next_index <= len(choices[depth]):
            raise ValueError("Cursor inválido no checkpoint")
    for entry in state["archive"]:
        indices = entry["choices"]
        if len(indices) != instance.n or any(not 0 <= index < len(choices[job]) for job, index in enumerate(indices)):
            raise ValueError("Solução inválida no checkpoint")
        selected = [choices[job][index] for job, index in enumerate(indices)]
        if overlaps_any(selected) or not has_valid_setups(instance, selected):
            raise ValueError("Escalonamento inválido no checkpoint")
        if [max(choice.end for choice in selected), sum(choice.cost_units for choice in selected)] != entry["point"]:
            raise ValueError("Objetivos inválidos no checkpoint")
    return state


def overlaps_any(selected: list[Choice]) -> bool:
    return any(overlaps(choice, selected[:job]) for job, choice in enumerate(selected))


CUDA_LEAF_KERNEL = r"""
extern "C" __global__ void evaluate_leaves(
    const int n, const int batch,
    const int* prefix_machine, const int* prefix_start, const int* prefix_end,
    const long long* prefix_cost,
    const int* leaf_machine, const int* leaf_start, const int* leaf_end,
    const long long* leaf_cost, const int* setup,
    int* status, int* makespan, long long* total_cost)
{
    int row = blockIdx.x * blockDim.x + threadIdx.x;
    if (row >= batch) return;
    int last = n - 1;
    int machine = leaf_machine[row];
    int start = leaf_start[row];
    int end = leaf_end[row];
    for (int j = 0; j < last; ++j) {
        if (prefix_machine[j] == machine && start < prefix_end[j] && prefix_start[j] < end) {
            status[row] = 0; return;
        }
    }
    int max_end = end;
    long long cost = leaf_cost[row];
    for (int j = 0; j < last; ++j) {
        if (prefix_end[j] > max_end) max_end = prefix_end[j];
        cost += prefix_cost[j];
    }
    // Para cada job, acha o sucessor imediato na mesma máquina.
    for (int a = 0; a < n; ++a) {
        int a_machine = a == last ? machine : prefix_machine[a];
        int a_start = a == last ? start : prefix_start[a];
        int a_end = a == last ? end : prefix_end[a];
        int successor = -1;
        int next_start = 2147483647;
        for (int b = 0; b < n; ++b) {
            if (a == b) continue;
            int b_machine = b == last ? machine : prefix_machine[b];
            int b_start = b == last ? start : prefix_start[b];
            if (b_machine == a_machine && b_start > a_start && b_start < next_start) {
                successor = b; next_start = b_start;
            }
        }
        if (successor >= 0 && next_start < a_end + setup[a_machine * n * n + a * n + successor]) {
            status[row] = 1; return;
        }
    }
    status[row] = 2;
    makespan[row] = max_end;
    total_cost[row] = cost;
}
"""


class CudaLeafEvaluator:
    """Avalia uma faixa de folhas do último nível; não altera a pilha DFS."""

    def __init__(self, instance: Instance, choices: tuple[tuple[Choice, ...], ...]):
        try:
            import cupy as cp
        except ImportError as error:
            raise ValueError("GPU requer CuPy: instale cupy-cuda12x[ctk] no Python usado") from error
        try:
            if cp.cuda.runtime.getDeviceCount() == 0:
                raise ValueError("Nenhuma GPU CUDA disponível")
            self.kernel = cp.RawKernel(CUDA_LEAF_KERNEL, "evaluate_leaves")
        except cp.cuda.runtime.CUDARuntimeError as error:
            raise ValueError(f"CUDA indisponível: {error}") from error
        self.cp = cp
        self.instance = instance
        self.choices = choices
        self.setup = cp.asarray([value for matrix in instance.setup for row in matrix for value in row], dtype=cp.int32)
        if sum(max(choice.cost_units for choice in job_choices) for job_choices in choices) > 2**63 - 1:
            raise ValueError("Custos excedem int64; use --backend cpu para manter a aritmética exata")
        if instance.horizon + max(value for matrix in instance.setup for row in matrix for value in row) > 2**31 - 1:
            raise ValueError("Tempos excedem int32; use --backend cpu")

    def evaluate(self, selected: list[Choice], leaves: tuple[Choice, ...]) -> tuple[list[int], list[int], list[int]]:
        cp = self.cp
        count = len(leaves)
        p_machine = cp.asarray([choice.machine for choice in selected], dtype=cp.int32)
        p_start = cp.asarray([choice.start for choice in selected], dtype=cp.int32)
        p_end = cp.asarray([choice.end for choice in selected], dtype=cp.int32)
        p_cost = cp.asarray([choice.cost_units for choice in selected], dtype=cp.int64)
        l_machine = cp.asarray([choice.machine for choice in leaves], dtype=cp.int32)
        l_start = cp.asarray([choice.start for choice in leaves], dtype=cp.int32)
        l_end = cp.asarray([choice.end for choice in leaves], dtype=cp.int32)
        l_cost = cp.asarray([choice.cost_units for choice in leaves], dtype=cp.int64)
        status = cp.empty(count, dtype=cp.int32)
        makespan = cp.empty(count, dtype=cp.int32)
        cost = cp.empty(count, dtype=cp.int64)
        self.kernel(((count + 255) // 256,), (256,),
                    (self.instance.n, count, p_machine, p_start, p_end, p_cost,
                     l_machine, l_start, l_end, l_cost, self.setup, status, makespan, cost))
        return cp.asnumpy(status).tolist(), cp.asnumpy(makespan).tolist(), cp.asnumpy(cost).tolist()


def show_progress(instance: Instance, state: dict, total: int) -> None:
    stats = state["stats"]
    covered = stats["covered_combinations"]
    percentage = 100 * covered / total
    print(
        f"[{instance.path.name}] {percentage:.8f}% do produto cartesiano coberto; "
        f"decisões={stats['candidate_decisions']:,}; folhas={stats['complete_assignments']:,}; "
        f"combinações podadas={stats['overlap_pruned_combinations'] + stats['setup_pruned_combinations']:,}; "
        f"viáveis={stats['valid_schedules']:,}; Pareto={len(state['archive'])}; "
        f"tempo={state['elapsed_seconds']:.1f}s",
        flush=True,
    )


def search(instance: Instance, *, checkpoint: Path, output: Path,
           time_limit: float | None = 10.0, progress_interval: float = 2.0,
           checkpoint_interval: float = 5.0, max_decisions: int | None = None,
           resume: bool = False, restart: bool = False, backend: str = "cpu",
           batch_size: int = 4096) -> dict:
    """Enumera X por job; só declara completa a fronteira quando a pilha esvazia.

    A GPU avalia lotes no último nível; a árvore e o arquivo Pareto ficam na CPU.
    """
    if resume and restart:
        raise ValueError("Escolha --resume ou --restart")
    if time_limit is not None and time_limit < 0:
        raise ValueError("O limite de tempo não pode ser negativo")
    if progress_interval <= 0 or checkpoint_interval <= 0:
        raise ValueError("Intervalos de progresso e checkpoint devem ser positivos")
    if max_decisions is not None and max_decisions < 0:
        raise ValueError("O limite de decisões não pode ser negativo")
    if backend not in ("cpu", "gpu") or batch_size <= 0:
        raise ValueError("Backend ou tamanho de lote inválido")
    if resume and not checkpoint.exists():
        raise ValueError(f"Checkpoint não encontrado: {checkpoint}")
    if not resume and not restart and (checkpoint.exists() or output.exists()):
        raise ValueError(f"Resultado anterior existe para {instance.path.name}; use --resume ou --restart")

    preparation_start = time.monotonic()
    scale, prices = energy_scale(instance)
    choices = generate_choices(instance, prices)
    gpu = CudaLeafEvaluator(instance, choices) if backend == "gpu" else None
    option_counts = [len(options) for options in choices]
    total = prod(option_counts)
    suffix_products = [1] * (instance.n + 1)
    for job in range(instance.n - 1, -1, -1):
        suffix_products[job] = suffix_products[job + 1] * option_counts[job]
    infinite_duration = instance.horizon + 1
    min_future_duration = [[infinite_duration] * instance.m for _ in range(instance.n + 1)]
    for job in range(instance.n - 1, -1, -1):
        for machine in range(instance.m):
            min_future_duration[job][machine] = min(
                min_future_duration[job + 1][machine],
                *(instance.duration(job, machine, mode) for mode in range(instance.modes)),
            )
    state = restore_state(checkpoint, instance, choices, scale) if resume else initial_state(instance, choices, scale)
    archive = [(tuple(entry["point"]), tuple(entry["choices"])) for entry in state["archive"]]
    selected_indices = list(state["selected_indices"])
    selected = [choices[job][index] for job, index in enumerate(selected_indices)]
    stack_next = list(state["stack_next"])
    stats = state["stats"]
    stats.setdefault("overlap_pruned_combinations",
                     stats["covered_combinations"] - stats["complete_assignments"])
    stats.setdefault("setup_pruned_combinations", 0)
    preparation_seconds = time.monotonic() - preparation_start
    started = time.monotonic()
    next_progress = started + progress_interval
    next_checkpoint = started + checkpoint_interval
    decisions_this_run = 0
    stop_reason = None

    def snapshot(complete: bool) -> dict:
        state.update(
            stack_next=list(stack_next), selected_indices=list(selected_indices),
            archive=[{"point": list(point), "choices": list(indices)} for point, indices in archive],
            elapsed_seconds=state["elapsed_seconds"] + time.monotonic() - started,
            complete=complete,
        )
        return state

    def write(complete: bool, reason: str | None) -> dict:
        snap = snapshot(complete)
        # snapshot() acumula tempo; reinicia a origem para não contá-lo duas vezes.
        nonlocal started
        started = time.monotonic()
        report = {
            "instance": str(instance.path), "instance_sha256": instance.digest,
            "status": "complete" if complete else "incomplete",
            "stop_reason": reason,
            "backend": backend,
            "batch_size": batch_size if gpu else None,
            "pareto_proven": complete,
            "n": instance.n, "m": instance.m, "modes": instance.modes,
            "horizon": instance.horizon,
            "option_counts": option_counts,
            "cartesian_combinations": str(total),
            "backtracking_skipped_combinations": str(
                stats["overlap_pruned_combinations"] + stats["setup_pruned_combinations"]),
            "backtracking_reduction_percent":
                100 * (stats["overlap_pruned_combinations"] + stats["setup_pruned_combinations"]) / total
                if complete else None,
            "stats": dict(stats),
            "elapsed_seconds": snap["elapsed_seconds"],
            "preparation_seconds_this_run": preparation_seconds,
            "cost_scale": scale,
            "max_cost_normalizer": float(instance.max_cost),
            "front": archive_output(instance, choices, scale, archive),
            "checkpoint": str(checkpoint),
        }
        atomic_json(checkpoint, snap)
        atomic_json(output, report)
        return report

    if state["complete"]:
        return write(True, "já concluído")

    try:
        while stack_next:
            now = time.monotonic()
            if time_limit is not None and now - preparation_start >= time_limit:
                stop_reason = "time_limit"
                break
            if max_decisions is not None and decisions_this_run >= max_decisions:
                stop_reason = "decision_limit"
                break
            if now >= next_progress:
                snapshot(False)
                # Reiniciar somente o relógio acumulado do relatório.
                started = time.monotonic()
                show_progress(instance, state, total)
                next_progress = now + progress_interval
            if now >= next_checkpoint:
                write(False, "em execução")
                next_checkpoint = now + checkpoint_interval

            depth = len(selected)
            if stack_next[-1] == option_counts[depth]:
                stack_next.pop()
                if selected:
                    selected.pop()
                    selected_indices.pop()
                continue
            if has_irreparable_setup(instance, selected, tuple(min_future_duration[depth])):
                remaining = (option_counts[depth] - stack_next[-1]) * suffix_products[depth + 1]
                stats["setup_pruned_combinations"] += remaining
                stats["covered_combinations"] += remaining
                stack_next[-1] = option_counts[depth]
                continue

            if gpu is not None and depth == instance.n - 1:
                remaining = option_counts[depth] - stack_next[-1]
                if max_decisions is not None:
                    remaining = min(remaining, max_decisions - decisions_this_run)
                count = min(batch_size, remaining)
                begin = stack_next[-1]
                leaf_batch = choices[depth][begin:begin + count]
                statuses, makespans, costs = gpu.evaluate(selected, leaf_batch)
                for offset, status in enumerate(statuses):
                    index = begin + offset
                    stack_next[-1] += 1
                    decisions_this_run += 1
                    stats["candidate_decisions"] += 1
                    if status == 0:
                        stats["overlap_prunes"] += 1
                        stats["overlap_pruned_combinations"] += 1
                    else:
                        stats["complete_assignments"] += 1
                        if status == 1:
                            stats["invalid_setups"] += 1
                        else:
                            stats["valid_schedules"] += 1
                            insert_pareto(archive, (makespans[offset], costs[offset]),
                                          tuple(selected_indices + [index]))
                    stats["covered_combinations"] += 1
                continue

            index = stack_next[-1]
            stack_next[-1] += 1
            choice = choices[depth][index]
            decisions_this_run += 1
            stats["candidate_decisions"] += 1
            descendant_count = suffix_products[depth + 1]
            if overlaps(choice, selected):
                stats["overlap_prunes"] += 1
                stats["overlap_pruned_combinations"] += descendant_count
                stats["covered_combinations"] += descendant_count
                continue

            if depth + 1 < instance.n and has_irreparable_setup(
                    instance, selected + [choice], tuple(min_future_duration[depth + 1])):
                stats["setup_pruned_combinations"] += descendant_count
                stats["covered_combinations"] += descendant_count
                continue

            makespan = max((existing.end for existing in selected), default=0)
            makespan = max(makespan, choice.end)
            cost = sum(existing.cost_units for existing in selected) + choice.cost_units
            if depth + 1 == instance.n:
                stats["complete_assignments"] += 1
                stats["covered_combinations"] += 1
                candidate = selected + [choice]
                if has_valid_setups(instance, candidate):
                    stats["valid_schedules"] += 1
                    insert_pareto(archive, (makespan, cost), tuple(selected_indices + [index]))
                else:
                    stats["invalid_setups"] += 1
            else:
                selected.append(choice)
                selected_indices.append(index)
                stack_next.append(0)
    except KeyboardInterrupt:
        stop_reason = "keyboard_interrupt"

    complete = not stack_next
    report = write(complete, None if complete else stop_reason)
    show_progress(instance, state, total)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Força bruta multiobjetivo por backtracking")
    parser.add_argument("input", nargs="?", type=Path, default=PROJECT_ROOT / "data" / "input" / "set1",
                        help="arquivo .dat ou pasta de instâncias (padrão: data/input/set1)")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "output" / "bruteforce")
    parser.add_argument("--time-limit", type=float, default=10.0,
                        help="segundos por instância, incluindo preparação; 0 = sem limite")
    parser.add_argument("--progress-interval", type=float, default=2.0)
    parser.add_argument("--checkpoint-interval", type=float, default=5.0)
    parser.add_argument("--max-decisions", type=int, help="limite de decisões por execução (útil para depuração)")
    parser.add_argument("--resume", action="store_true", help="continua checkpoints existentes")
    parser.add_argument("--restart", action="store_true", help="reinicia resultados anteriores desta busca")
    parser.add_argument("--backend", choices=("cpu", "gpu"), default="cpu",
                        help="avaliação das folhas: CPU padrão ou CUDA via CuPy")
    parser.add_argument("--batch-size", type=int, default=4096,
                        help="número de folhas por lote CUDA (padrão: 4096)")
    args = parser.parse_args(argv)
    paths = sorted(args.input.glob("*.dat")) if args.input.is_dir() else [args.input]
    if not paths or any(not path.is_file() for path in paths):
        parser.error("Nenhum arquivo .dat encontrado")
    for path in paths:
        try:
            instance = read_instance(path)
            output = args.output_dir / f"{path.stem}.json"
            checkpoint = args.output_dir / f"{path.stem}.checkpoint.json"
            report = search(instance, checkpoint=checkpoint, output=output,
                            time_limit=None if args.time_limit == 0 else args.time_limit,
                            progress_interval=args.progress_interval,
                            checkpoint_interval=args.checkpoint_interval,
                            max_decisions=args.max_decisions, resume=args.resume,
                            restart=args.restart, backend=args.backend, batch_size=args.batch_size)
            print(f"{path.name}: {report['status']}, Pareto={len(report['front'])}, saída={output}", flush=True)
            if report["stop_reason"] == "keyboard_interrupt":
                break
        except (OSError, ValueError) as error:
            parser.error(f"{path.name}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
