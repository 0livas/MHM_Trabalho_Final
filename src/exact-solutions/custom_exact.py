"""Solver exato próprio: backtracking com propagação e limites de Pareto.

Não usa soluções anteriores nem uma biblioteca de otimização. A fronteira
começa vazia; cada solução viável é descoberta pela própria busca.
"""

from __future__ import annotations

import argparse
import json
from math import prod
from pathlib import Path
import time

from problem import (PROJECT_ROOT, Choice, Instance, archive_output, atomic_json,
                   dominates_or_equals, energy_scale, generate_choices,
                   has_valid_setups, insert_pareto, read_instance)


FORMAT_VERSION = 1


class Domains:
    """Domínios de inícios como máscaras de bits, uma por job/máquina/modo."""

    def __init__(self, instance: Instance, choices: tuple[tuple[Choice, ...], ...]):
        self.instance = instance
        self.choices = choices
        self.groups = instance.m * instance.modes
        self.counts = tuple(len(job_choices) for job_choices in choices)
        self.lengths = [[0] * self.groups for _ in range(instance.n)]
        self.durations = [[0] * self.groups for _ in range(instance.n)]
        self.cost_masks: list[list[list[tuple[int, int]]]] = []
        self.ordered_indices = []
        for job, job_choices in enumerate(choices):
            buckets = [[] for _ in range(self.groups)]
            for choice in job_choices:
                group = choice.machine * instance.modes + choice.mode
                self.lengths[job][group] += 1
                self.durations[job][group] = choice.end - choice.start
                buckets[group].append(choice)
            grouped_costs = []
            for group_choices in buckets:
                masks: dict[int, int] = {}
                for choice in group_choices:
                    masks[choice.cost_units] = masks.get(choice.cost_units, 0) | (1 << choice.start)
                grouped_costs.append(sorted(masks.items()))
            self.cost_masks.append(grouped_costs)
            self.ordered_indices.append(tuple(sorted(
                range(len(job_choices)),
                key=lambda index: (job_choices[index].end, job_choices[index].cost_units,
                                   job_choices[index].machine, job_choices[index].mode,
                                   job_choices[index].start),
            )))
        self.initial = [[(1 << count) - 1 for count in lengths]
                        for lengths in self.lengths]

    def allowed(self, masks: list[list[int]], job: int, choice: Choice) -> bool:
        group = choice.machine * self.instance.modes + choice.mode
        return bool(masks[job][group] & (1 << choice.start))

    def after(self, masks: list[list[int]], selected_job: int, choice: Choice,
              selected_indices: list[int]) -> list[list[int]]:
        updated = [row.copy() for row in masks]
        for job in range(self.instance.n):
            if job == selected_job or selected_indices[job] >= 0:
                continue
            for mode in range(self.instance.modes):
                group = choice.machine * self.instance.modes + mode
                count = self.lengths[job][group]
                if not count:
                    continue
                duration = self.durations[job][group]
                low = max(0, choice.start - duration + 1)
                high = min(count - 1, choice.end - 1)
                if low <= high:
                    updated[job][group] &= ~(((1 << (high - low + 1)) - 1) << low)
        return updated

    def choose_job(self, masks: list[list[int]], remaining: list[int]) -> int:
        return min(remaining, key=lambda job: (
            sum(mask.bit_count() for mask in masks[job]),
            -min((duration for duration in self.durations[job] if duration), default=0), job,
        ))

    def candidate_indices(self, masks: list[list[int]], job: int) -> list[int]:
        return [index for index in self.ordered_indices[job]
                if self.allowed(masks, job, self.choices[job][index])]

    def optimistic_objectives(self, masks: list[list[int]], selected_indices: list[int]) -> tuple[int, int] | None:
        makespan = 0
        cost = 0
        for job, index in enumerate(selected_indices):
            if index >= 0:
                choice = self.choices[job][index]
                makespan = max(makespan, choice.end)
                cost += choice.cost_units
                continue
            min_completion = None
            min_cost = None
            for group, mask in enumerate(masks[job]):
                if not mask:
                    continue
                first_start = (mask & -mask).bit_length() - 1
                completion = first_start + self.durations[job][group]
                min_completion = completion if min_completion is None else min(min_completion, completion)
                for candidate_cost, cost_mask in self.cost_masks[job][group]:
                    if mask & cost_mask:
                        min_cost = candidate_cost if min_cost is None else min(min_cost, candidate_cost)
                        break
            if min_completion is None or min_cost is None:
                return None
            makespan = max(makespan, min_completion)
            cost += min_cost
        return makespan, cost


def irreparable_setup(instance: Instance, domains: Domains,
                      selected_indices: list[int]) -> bool:
    remaining = [job for job, index in enumerate(selected_indices) if index < 0]
    for machine in range(instance.m):
        sequence = sorted(
            ((job, domains.choices[job][index]) for job, index in enumerate(selected_indices)
             if index >= 0 and domains.choices[job][index].machine == machine),
            key=lambda pair: pair[1].start,
        )
        shortest_future = min(
            (domains.durations[job][machine * instance.modes + mode]
             for job in remaining for mode in range(instance.modes)
             if domains.durations[job][machine * instance.modes + mode]),
            default=instance.horizon + 1,
        )
        for (previous_job, previous), (next_job, following) in zip(sequence, sequence[1:]):
            gap = following.start - previous.end
            if gap < instance.setup[machine][previous_job][next_job] and gap < shortest_future:
                return True
    return False


def search(instance: Instance, *, checkpoint: Path, output: Path,
           time_limit: float | None = 10.0, progress_interval: float = 2.0,
           checkpoint_interval: float = 5.0, max_decisions: int | None = None,
           resume: bool = False, restart: bool = False) -> dict:
    if resume and restart:
        raise ValueError("Escolha --resume ou --restart")
    if time_limit is not None and time_limit < 0:
        raise ValueError("Limite de tempo inválido")
    if progress_interval <= 0 or checkpoint_interval <= 0:
        raise ValueError("Intervalos devem ser positivos")
    if max_decisions is not None and max_decisions < 0:
        raise ValueError("Limite de decisões inválido")
    if resume and not checkpoint.exists():
        raise ValueError("Checkpoint não encontrado")
    if not resume and not restart and (checkpoint.exists() or output.exists()):
        raise ValueError("Resultado anterior existe; use --resume ou --restart")

    preparation_start = time.monotonic()
    scale, prices = energy_scale(instance)
    choices = generate_choices(instance, prices)
    domains = Domains(instance, choices)
    total = prod(domains.counts)

    if resume:
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
        if (state.get("format_version") != FORMAT_VERSION
                or state.get("instance_sha256") != instance.digest
                or state.get("cost_scale") != scale
                or state.get("option_counts") != list(domains.counts)):
            raise ValueError("Checkpoint incompatível")
        selected = state["selected_indices"]
        frames = state["frames"]
        archive = [(tuple(entry["point"]), tuple(entry["indices"])) for entry in state["archive"]]
        stats = state["stats"]
        if len(selected) != instance.n or len(frames) > instance.n:
            raise ValueError("Pilha inválida no checkpoint")
        masks_stack = [domains.initial]
        replay_selected = [-1] * instance.n
        for frame in frames[:-1]:
            job = frame["job"]
            index = selected[job]
            if replay_selected[job] >= 0 or not 0 <= index < domains.counts[job]:
                raise ValueError("Decisão inválida no checkpoint")
            replay_selected[job] = index
            masks_stack.append(domains.after(masks_stack[-1], job, choices[job][index], replay_selected))
        if len(masks_stack) != len(frames) and frames:
            raise ValueError("Pilha inválida no checkpoint")
        if frames and (selected[frames[-1]["job"]] >= 0 or replay_selected != selected):
            raise ValueError("Seleção inválida no checkpoint")
        if not frames and any(index >= 0 for index in selected):
            raise ValueError("Checkpoint concluído contém jobs selecionados")
    else:
        selected = [-1] * instance.n
        archive = []
        stats = {"candidate_decisions": 0, "covered_combinations": 0,
                 "complete_assignments": 0, "valid_schedules": 0,
                 "invalid_setups": 0, "propagation_pruned_combinations": 0,
                 "setup_pruned_combinations": 0, "dominance_pruned_combinations": 0}
        masks_stack = [domains.initial]
        root_job = domains.choose_job(domains.initial, list(range(instance.n)))
        frames = [{"job": root_job, "candidates": domains.candidate_indices(domains.initial, root_job),
                   "cursor": 0}]
        state = {"format_version": FORMAT_VERSION, "instance_sha256": instance.digest,
                 "cost_scale": scale, "option_counts": list(domains.counts),
                 "elapsed_seconds": 0.0, "complete": False}

    preparation_seconds = time.monotonic() - preparation_start
    elapsed_before = state["elapsed_seconds"]
    started = time.monotonic()
    next_progress = started + progress_interval
    next_checkpoint = started + checkpoint_interval
    decisions_this_run = 0
    stop_reason = None

    def record(reason: str, combinations: int) -> None:
        stats[reason + "_pruned_combinations"] += combinations
        stats["covered_combinations"] += combinations

    def save(complete: bool, reason: str | None) -> dict:
        state.update(frames=frames, selected_indices=selected,
                     archive=[{"point": list(point), "indices": list(indices)}
                              for point, indices in archive],
                     stats=stats, complete=complete,
                     elapsed_seconds=elapsed_before + time.monotonic() - started)
        report = {"instance": str(instance.path), "instance_sha256": instance.digest,
                  "method": "custom_exact_propagation", "status": "complete" if complete else "incomplete",
                  "pareto_proven": complete, "stop_reason": reason,
                  "cost_scale": scale, "option_counts": list(domains.counts),
                  "cartesian_combinations": str(total), "stats": dict(stats),
                  "elapsed_seconds": state["elapsed_seconds"],
                  "preparation_seconds_this_run": preparation_seconds,
                  "front": archive_output(instance, choices, scale, archive),
                  "checkpoint": str(checkpoint)}
        atomic_json(checkpoint, state)
        atomic_json(output, report)
        return report

    def show_progress() -> None:
        print(f"[{instance.path.name}] {100 * stats['covered_combinations'] / total:.8f}% "
              f"coberto; decisões={stats['candidate_decisions']:,}; "
              f"viáveis={stats['valid_schedules']:,}; Pareto={len(archive)}; "
              f"tempo={elapsed_before + time.monotonic() - started:.1f}s", flush=True)

    if state["complete"]:
        return save(True, "já concluído")

    try:
        while frames:
            now = time.monotonic()
            if time_limit is not None and now - preparation_start >= time_limit:
                stop_reason = "time_limit"
                break
            if max_decisions is not None and decisions_this_run >= max_decisions:
                stop_reason = "decision_limit"
                break
            if now >= next_progress:
                show_progress()
                next_progress = now + progress_interval
            if now >= next_checkpoint:
                save(False, "em execução")
                next_checkpoint = now + checkpoint_interval

            frame = frames[-1]
            if frame["cursor"] == len(frame["candidates"]):
                frames.pop()
                masks_stack.pop()
                if frames:
                    selected[frames[-1]["job"]] = -1
                continue
            job = frame["job"]
            index = frame["candidates"][frame["cursor"]]
            frame["cursor"] += 1
            selected[job] = index
            decisions_this_run += 1
            stats["candidate_decisions"] += 1
            remaining = [other for other, current in enumerate(selected) if current < 0]
            descendants = prod(domains.counts[other] for other in remaining)
            choice = choices[job][index]
            if not remaining:
                stats["complete_assignments"] += 1
                stats["covered_combinations"] += 1
                schedule = [choices[other][current] for other, current in enumerate(selected)]
                if has_valid_setups(instance, schedule):
                    stats["valid_schedules"] += 1
                    point = (max(item.end for item in schedule), sum(item.cost_units for item in schedule))
                    if insert_pareto(archive, point, tuple(selected)):
                        print(f"[{instance.path.name}] Pareto provisório: Cmax={point[0]}, "
                              f"TEC={point[1]}/{scale}", flush=True)
                else:
                    stats["invalid_setups"] += 1
                selected[job] = -1
                continue

            next_masks = domains.after(masks_stack[-1], job, choice, selected)
            if irreparable_setup(instance, domains, selected):
                record("setup", descendants)
                selected[job] = -1
                continue
            lower_bound = domains.optimistic_objectives(next_masks, selected)
            if lower_bound is None:
                record("propagation", descendants)
                selected[job] = -1
                continue
            if any(dominates_or_equals(point, lower_bound) for point, _ in archive):
                record("dominance", descendants)
                selected[job] = -1
                continue
            next_job = domains.choose_job(next_masks, remaining)
            candidates = domains.candidate_indices(next_masks, next_job)
            filtered = (domains.counts[next_job] - len(candidates)) * prod(
                domains.counts[other] for other in remaining if other != next_job)
            record("propagation", filtered)
            frames.append({"job": next_job, "candidates": candidates, "cursor": 0})
            masks_stack.append(next_masks)
    except KeyboardInterrupt:
        stop_reason = "keyboard_interrupt"

    if not frames and stats["covered_combinations"] != total:
        raise AssertionError("Busca terminou sem cobrir todas as combinações brutas")
    report = save(not frames, None if not frames else stop_reason)
    show_progress()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Solver exato próprio por backtracking e propagação")
    parser.add_argument("input", nargs="?", type=Path, default=PROJECT_ROOT / "data" / "input" / "set1")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "data" / "output" / "custom_exact")
    parser.add_argument("--time-limit", type=float, default=10.0,
                        help="segundos por instância; 0 = sem limite")
    parser.add_argument("--progress-interval", type=float, default=2.0)
    parser.add_argument("--checkpoint-interval", type=float, default=5.0)
    parser.add_argument("--max-decisions", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args(argv)
    paths = sorted(args.input.glob("*.dat")) if args.input.is_dir() else [args.input]
    if not paths or any(not path.is_file() for path in paths):
        parser.error("Nenhum arquivo .dat encontrado")
    for path in paths:
        try:
            instance = read_instance(path)
            report = search(instance,
                            checkpoint=args.output_dir / f"{path.stem}.checkpoint.json",
                            output=args.output_dir / f"{path.stem}.json",
                            time_limit=None if args.time_limit == 0 else args.time_limit,
                            progress_interval=args.progress_interval,
                            checkpoint_interval=args.checkpoint_interval,
                            max_decisions=args.max_decisions, resume=args.resume,
                            restart=args.restart)
            print(f"{path.name}: {report['status']}, Pareto={len(report['front'])}", flush=True)
            if report["stop_reason"] == "keyboard_interrupt":
                break
        except (OSError, ValueError) as error:
            parser.error(f"{path.name}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
