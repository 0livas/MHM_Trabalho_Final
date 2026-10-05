"""Shared native schedule representation, decoding, validation, and evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from numbers import Integral
from typing import TypeAlias

from problem import (
    Choice,
    Instance,
    dominates,
    dominates_or_equals,
    energy_scale,
    has_valid_setups,
    insert_pareto,
    interval_cost_units,
    overlaps_any,
)

Schedule: TypeAlias = tuple[tuple[tuple[int, int, int], ...], ...]


class ScheduleValidationError(ValueError):
    """A schedule is malformed or violates a model feasibility rule."""


@dataclass(frozen=True, slots=True)
class ScheduledOperation:
    machine: int
    job: int
    mode: int
    start: int
    end: int
    tec_units: int

    def to_result_row(self) -> dict[str, int]:
        return {"job": self.job, "machine": self.machine, "mode": self.mode,
                "start": self.start, "end": self.end}


@dataclass(frozen=True, slots=True)
class ScheduleEvaluation:
    cmax: int
    tec_units: int
    tec_scale: int
    operations: tuple[ScheduledOperation, ...]

    @property
    def tec_exact(self) -> Fraction:
        return Fraction(self.tec_units, self.tec_scale)

    @property
    def tec(self) -> float:
        """Float view for existing JSON formats and libraries such as pymoo."""
        return float(self.tec_exact)

    @property
    def objective_key(self) -> tuple[int, int]:
        """Authoritative exact minimization key: (Cmax, scaled TEC)."""
        return self.cmax, self.tec_units

    def to_result_dict(self, instance: Instance) -> dict:
        """Return the existing exact-result shape, preserving exact TEC units."""
        rows = [operation.to_result_row()
                for operation in sorted(self.operations, key=lambda item: item.job)]
        x_nonzero = [{"i": row["machine"], "j": row["job"],
                      "h": row["start"], "l": row["mode"]} for row in rows]
        return {
            "makespan": self.cmax,
            "tec": self.tec,
            "tec_exact": {"numerator": self.tec_units, "denominator": self.tec_scale},
            "normalized_makespan": self.cmax / instance.horizon,
            "normalized_tec": float(self.tec_exact / instance.max_cost),
            "x_nonzero": x_nonzero,
            "schedule": rows,
        }


def _integer(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ScheduleValidationError(f"{field} deve ser inteiro; recebido {value!r}")
    return int(value)


def evaluate_schedule(instance: Instance, schedule: Schedule | Sequence) -> ScheduleEvaluation:
    """Validate and decode machine sequences of ``(job, mode, wait)`` triples."""
    if not isinstance(schedule, (list, tuple)):
        raise ScheduleValidationError("Schedule deve ser uma lista/tupla por máquina")
    if len(schedule) != instance.m:
        raise ScheduleValidationError(
            f"Número incorreto de máquinas: esperado {instance.m}, recebido {len(schedule)}"
        )

    tec_scale, prices = energy_scale(instance)
    unit_prices = {(machine, mode): (on_price, off_price)
                   for machine, mode, on_price, off_price in prices}
    seen: set[int] = set()
    decoded: list[ScheduledOperation] = []
    selected: list[Choice | None] = [None] * instance.n

    for machine, sequence in enumerate(schedule):
        if not isinstance(sequence, (list, tuple)):
            raise ScheduleValidationError(f"Lista inválida para máquina {machine}")
        previous_job: int | None = None
        previous_end = 0
        for position, item in enumerate(sequence):
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise ScheduleValidationError(
                    f"Máquina {machine}, posição {position}: esperado (job, modo, espera)"
                )
            job = _integer(item[0], "job")
            mode = _integer(item[1], "modo")
            wait = _integer(item[2], "espera")
            if not 0 <= job < instance.n:
                raise ScheduleValidationError(f"Job fora do domínio: {job}")
            if job in seen:
                raise ScheduleValidationError(f"Job duplicado: {job}")
            seen.add(job)
            if not 0 <= mode < instance.modes:
                raise ScheduleValidationError(f"Modo fora do domínio para job {job}: {mode}")
            if wait < 0:
                raise ScheduleValidationError(f"Espera negativa para job {job}: {wait}")

            setup = (instance.setup[machine][previous_job][job]
                     if previous_job is not None else 0)
            start = previous_end + setup + wait
            end = start + instance.duration(job, machine, mode)
            if end > instance.horizon:
                raise ScheduleValidationError(
                    f"Job {job} termina em {end}, além do horizonte {instance.horizon}"
                )
            on_price, off_price = unit_prices[machine, mode]
            operation_units = interval_cost_units(instance, start, end, on_price, off_price)
            choice = Choice(machine, start, mode, end, operation_units)
            selected[job] = choice
            decoded.append(ScheduledOperation(machine, job, mode, start, end, operation_units))
            previous_job, previous_end = job, end

    missing = sorted(set(range(instance.n)) - seen)
    if missing:
        raise ScheduleValidationError(f"Jobs ausentes: {missing}")
    choices = [choice for choice in selected if choice is not None]
    if len(choices) != instance.n:
        raise ScheduleValidationError("Schedule incompleto")
    if overlaps_any(choices):
        raise ScheduleValidationError("Schedule contém sobreposição na mesma máquina")
    if not has_valid_setups(instance, choices):
        raise ScheduleValidationError("Schedule viola setup entre tarefas consecutivas")

    return ScheduleEvaluation(
        cmax=max(operation.end for operation in decoded),
        tec_units=sum(operation.tec_units for operation in decoded),
        tec_scale=tec_scale,
        operations=tuple(decoded),
    )


def schedule_from_result_rows(instance: Instance, rows: Sequence[Mapping]) -> Schedule:
    """Convert result-format rows with starts into residual-wait representation."""
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ScheduleValidationError("schedule de resultado deve ser uma sequência de objetos")
    if len(rows) != instance.n:
        raise ScheduleValidationError(
            f"Schedule de resultado deve conter {instance.n} linhas, recebeu {len(rows)}"
        )

    by_machine: list[list[tuple[int, int, int]]] = [[] for _ in range(instance.m)]
    jobs: set[int] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ScheduleValidationError(f"Linha {index} do schedule não é um objeto")
        try:
            job = _integer(row["job"], "job")
            machine = _integer(row["machine"], "máquina")
            mode = _integer(row["mode"], "modo")
            start = _integer(row["start"], "start")
            end = _integer(row["end"], "end")
        except KeyError as error:
            raise ScheduleValidationError(f"Campo ausente no schedule de resultado: {error.args[0]}") from error
        if not 0 <= job < instance.n:
            raise ScheduleValidationError(f"Job fora do domínio no resultado: {job}")
        if job in jobs:
            raise ScheduleValidationError(f"Job duplicado no resultado: {job}")
        jobs.add(job)
        if not 0 <= machine < instance.m:
            raise ScheduleValidationError(f"Máquina fora do domínio para job {job}: {machine}")
        if not 0 <= mode < instance.modes:
            raise ScheduleValidationError(f"Modo fora do domínio para job {job}: {mode}")
        by_machine[machine].append((start, job, mode, end))

    if len(jobs) != instance.n:
        raise ScheduleValidationError(f"Jobs ausentes no resultado: {sorted(set(range(instance.n)) - jobs)}")

    result: list[tuple[tuple[int, int, int], ...]] = []
    for machine, machine_rows in enumerate(by_machine):
        machine_rows.sort(key=lambda row: row[0])
        sequence: list[tuple[int, int, int]] = []
        previous_job: int | None = None
        previous_end = 0
        for start, job, mode, claimed_end in machine_rows:
            expected_end = start + instance.duration(job, machine, mode)
            if claimed_end != expected_end:
                raise ScheduleValidationError(
                    f"Término inconsistente no job {job}: esperado {expected_end}, recebido {claimed_end}"
                )
            setup = instance.setup[machine][previous_job][job] if previous_job is not None else 0
            wait = start - previous_end - setup
            if wait < 0:
                raise ScheduleValidationError(
                    f"Setup/ordem inviável entre jobs {previous_job} e {job} na máquina {machine}"
                )
            sequence.append((job, mode, wait))
            previous_job, previous_end = job, claimed_end
        result.append(tuple(sequence))

    schedule = tuple(result)
    evaluate_schedule(instance, schedule)
    return schedule


# Re-export exact Pareto operations next to the shared solution API.
__all__ = [
    "Schedule", "ScheduleEvaluation", "ScheduleValidationError", "ScheduledOperation",
    "dominates", "dominates_or_equals", "evaluate_schedule", "insert_pareto",
    "schedule_from_result_rows",
]
