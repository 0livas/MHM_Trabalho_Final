"""Dados, opções e regras compartilhadas pelos solvers exatos do UPMSP."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from math import ceil, lcm
from pathlib import Path
import json
import os
import time
from typing import TypeVar


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


def interval_cost_units(instance: Instance, start: int, end: int,
                        on_price: int, off_price: int) -> int:
    """Custo escalado do processamento em [start, end), sem setup ou espera."""
    peak_slots = sum(max(0, min(end, b) - max(start, a)) for a, b in instance.peaks)
    duration = end - start
    return on_price * peak_slots + off_price * (duration - peak_slots)


def generate_choices(instance: Instance, prices: tuple[tuple[int, int, int, int], ...]) -> tuple[tuple[Choice, ...], ...]:
    """Gera posições individuais de X que cabem no horizonte, em ordem fixa."""
    by_job = []
    for job in range(instance.n):
        choices = []
        for machine, mode, on_price, off_price in prices:
            duration = instance.duration(job, machine, mode)
            for start in range(instance.horizon - duration + 1):
                end = start + duration
                cost_units = interval_cost_units(instance, start, end, on_price, off_price)
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


def dominates_or_equals(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] <= b[0] and a[1] <= b[1]


def dominates(a: tuple[int, int], b: tuple[int, int]) -> bool:
    """True when exact minimization point a strictly dominates point b."""
    return dominates_or_equals(a, b) and a != b


ParetoPayload = TypeVar("ParetoPayload")


def insert_pareto(archive: list[tuple[tuple[int, int], ParetoPayload]],
                  point: tuple[int, int], payload: ParetoPayload) -> bool:
    """Insert a nondominated exact (Cmax, TEC-units) point; deduplicate equals."""
    if any(dominates_or_equals(existing, point) for existing, _ in archive):
        return False
    archive[:] = [(existing, existing_payload) for existing, existing_payload in archive
                  if not dominates_or_equals(point, existing)]
    archive.append((point, payload))
    archive.sort(key=lambda entry: (entry[0][0], entry[0][1]))
    return True


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    # No Windows, um leitor/antivírus pode manter o destino aberto brevemente.
    # Preserva a atomicidade: nunca remove o relatório anterior antes do replace.
    for attempt in range(12):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if os.name != "nt" or attempt == 11:
                raise
            time.sleep(min(0.02 * 2**attempt, 0.5))


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



def overlaps_any(selected: list[Choice]) -> bool:
    return any(overlaps(choice, selected[:job]) for job, choice in enumerate(selected))
