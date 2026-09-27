"""Modelo CP-SAT exato para a fronteira de Pareto do UPMSP.

Usa intervalos opcionais para máquina/modo e um circuito por máquina para
representar *somente* os setups entre jobs consecutivos. A fronteira é obtida
por problemas lexicográficos sucessivos com restrição de custo inteiro.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from problem import (PROJECT_ROOT, Choice, Instance, archive_output, atomic_json,
                   energy_scale, generate_choices, has_valid_setups, overlaps_any,
                   read_instance)


def ortools_module():
    try:
        from ortools.sat.python import cp_model
    except ImportError as error:
        raise ValueError("CP-SAT requer OR-Tools: python -m pip install --user -r requirements-cpsat.txt") from error
    return cp_model


def build_model(instance: Instance, choices: tuple[tuple[Choice, ...], ...],
                cost_cap: int | None, makespan_cap: int | None, objective: str):
    """Constrói a mesma região viável da busca exaustiva, sem tensor X denso."""
    cp_model = ortools_module()
    model = cp_model.CpModel()
    horizon = instance.horizon
    options: dict[tuple[int, int, int], list[Choice]] = {}
    for job, job_choices in enumerate(choices):
        for choice in job_choices:
            options.setdefault((job, choice.machine, choice.mode), []).append(choice)
    present = {}
    start = {}
    end = {}
    costs = []
    machine_intervals = [[] for _ in range(instance.m)]
    selected_start = {}
    selected_end = {}
    assigned = {}
    job_end = []

    for job in range(instance.n):
        job_presence = []
        last_end = model.NewIntVar(0, horizon, f"job_end_{job}")
        job_end.append(last_end)
        for machine in range(instance.m):
            assigned[job, machine] = model.NewBoolVar(f"assigned_{job}_{machine}")
            selected_start[job, machine] = model.NewIntVar(0, horizon, f"start_{job}_{machine}")
            selected_end[job, machine] = model.NewIntVar(0, horizon, f"end_{job}_{machine}")
            machine_presence = []
            for mode in range(instance.modes):
                key = (job, machine, mode)
                if key not in options:
                    continue
                group = options[key]
                duration = group[0].end - group[0].start
                p = model.NewBoolVar(f"x_{job}_{machine}_{mode}")
                s = model.NewIntVar(0, horizon - duration, f"s_{job}_{machine}_{mode}")
                e = model.NewIntVar(duration, horizon, f"e_{job}_{machine}_{mode}")
                interval = model.NewOptionalIntervalVar(s, duration, e, p,
                                                        f"interval_{job}_{machine}_{mode}")
                machine_intervals[machine].append(interval)
                table = [choice.cost_units for choice in group]
                energy = model.NewIntVar(min(table), max(table), f"energy_{job}_{machine}_{mode}")
                model.AddElement(s, table, energy)
                contribution = model.NewIntVar(0, max(table), f"paid_{job}_{machine}_{mode}")
                model.Add(contribution == energy).OnlyEnforceIf(p)
                model.Add(contribution == 0).OnlyEnforceIf(p.Not())
                model.Add(selected_start[job, machine] == s).OnlyEnforceIf(p)
                model.Add(selected_end[job, machine] == e).OnlyEnforceIf(p)
                model.Add(last_end == e).OnlyEnforceIf(p)
                present[key], start[key], end[key] = p, s, e
                machine_presence.append(p)
                job_presence.append(p)
                costs.append(contribution)
            model.Add(sum(machine_presence) == assigned[job, machine])
        model.AddExactlyOne(job_presence)

    for machine in range(instance.m):
        model.AddNoOverlap(machine_intervals[machine])
        empty = model.NewBoolVar(f"empty_machine_{machine}")
        used = sum(assigned[job, machine] for job in range(instance.n))
        model.Add(used == 0).OnlyEnforceIf(empty)
        model.Add(used >= 1).OnlyEnforceIf(empty.Not())
        arcs = [(0, 0, empty)]
        for job in range(instance.n):
            node = job + 1
            arcs.append((node, node, assigned[job, machine].Not()))
            first = model.NewBoolVar(f"first_{machine}_{job}")
            last = model.NewBoolVar(f"last_{machine}_{job}")
            model.AddImplication(first, assigned[job, machine])
            model.AddImplication(last, assigned[job, machine])
            arcs.extend(((0, node, first), (node, 0, last)))
        for predecessor in range(instance.n):
            for successor in range(instance.n):
                if predecessor == successor:
                    continue
                arc = model.NewBoolVar(f"next_{machine}_{predecessor}_{successor}")
                model.AddImplication(arc, assigned[predecessor, machine])
                model.AddImplication(arc, assigned[successor, machine])
                model.Add(selected_start[successor, machine] >=
                          selected_end[predecessor, machine]
                          + instance.setup[machine][predecessor][successor]).OnlyEnforceIf(arc)
                arcs.append((predecessor + 1, successor + 1, arc))
        model.AddCircuit(arcs)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, job_end)
    max_energy = sum(max(choice.cost_units for choice in job_choices) for job_choices in choices)
    if max_energy > 2**63 - 1:
        raise ValueError("Custo escalado excede int64, limite do CP-SAT")
    total_energy = model.NewIntVar(0, max_energy, "total_energy")
    model.Add(total_energy == sum(costs))
    if cost_cap is not None:
        model.Add(total_energy <= cost_cap)
    if makespan_cap is not None:
        model.Add(makespan <= makespan_cap)
    model.Minimize(makespan if objective == "makespan" else total_energy)
    return model, makespan, total_energy, present, start


def decode_solution(instance: Instance, choices: tuple[tuple[Choice, ...], ...],
                    solver, presence: dict, starts: dict, makespan: int,
                    energy: int) -> tuple[int, ...]:
    indices = []
    for job in range(instance.n):
        selected = [(machine, mode, solver.Value(starts[job, machine, mode]))
                    for machine in range(instance.m) for mode in range(instance.modes)
                    if (job, machine, mode) in presence and solver.Value(presence[job, machine, mode])]
        if len(selected) != 1:
            raise ValueError("O solver não selecionou exatamente uma posição por job")
        machine, mode, beginning = selected[0]
        index = next(index for index, choice in enumerate(choices[job])
                     if (choice.machine, choice.mode, choice.start) == (machine, mode, beginning))
        indices.append(index)
    schedule = [choices[job][index] for job, index in enumerate(indices)]
    if (overlaps_any(schedule) or not has_valid_setups(instance, schedule)
            or max(choice.end for choice in schedule) != makespan
            or sum(choice.cost_units for choice in schedule) != energy):
        raise ValueError("O escalonamento CP-SAT não coincide com a avaliação do backtracking")
    return tuple(indices)


def solve_front(instance: Instance, *, output: Path, seconds_per_solve: float = 60.0,
                workers: int = 8, resume: bool = False, restart: bool = False) -> dict:
    cp_model = ortools_module()
    if seconds_per_solve < 0 or workers < 1 or (resume and restart):
        raise ValueError("Parâmetros de execução inválidos")
    if resume and not output.exists():
        raise ValueError("Relatório anterior não encontrado para --resume")
    if not resume and not restart and output.exists():
        raise ValueError("Relatório anterior existe; use --resume ou --restart")
    scale, prices = energy_scale(instance)
    choices = generate_choices(instance, prices)
    if resume:
        report = json.loads(output.read_text(encoding="utf-8"))
        if report.get("instance_sha256") != instance.digest or report.get("cost_scale") != scale:
            raise ValueError("Relatório incompatível com esta instância")
        if report["status"] == "complete":
            return report
        archive = [(tuple(point["point"]), tuple(point["indices"])) for point in report["proven_points"]]
        cap = report["next_cost_cap"]
    else:
        archive = []
        cap = None
        report = {"instance": str(instance.path), "instance_sha256": instance.digest,
                  "method": "cp_sat_epsilon_constraint", "status": "incomplete",
                  "pareto_proven": False, "cost_scale": scale, "proven_points": [],
                  "next_cost_cap": None, "iterations": [], "elapsed_seconds": 0.0}
    elapsed_before_run = report["elapsed_seconds"]
    started = time.monotonic()

    def save(status: str, candidate: dict | None = None) -> dict:
        report.update(status=status, pareto_proven=status == "complete",
                      next_cost_cap=cap,
                      proven_points=[{"point": list(point), "indices": list(indices)}
                                     for point, indices in archive],
                      front=archive_output(instance, choices, scale, archive),
                      candidate=candidate,
                      elapsed_seconds=elapsed_before_run + time.monotonic() - started)
        atomic_json(output, report)
        return report

    def one_solve(cost_limit: int | None, makespan_limit: int | None, objective: str):
        model, makespan, energy, presence, starts = build_model(
            instance, choices, cost_limit, makespan_limit, objective)
        solver = cp_model.CpSolver()
        if seconds_per_solve:
            solver.parameters.max_time_in_seconds = seconds_per_solve
        solver.parameters.num_search_workers = workers
        status = solver.Solve(model)
        report["iterations"].append({"cost_cap": cost_limit, "makespan_cap": makespan_limit,
                                     "objective": objective, "solver_status": solver.StatusName(status),
                                     "solver_seconds": solver.WallTime(),
                                     "best_bound": solver.BestObjectiveBound() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None})
        candidate = None
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            point = (solver.Value(makespan), solver.Value(energy))
            indices = decode_solution(instance, choices, solver, presence, starts, *point)
            candidate = {"point": list(point), "indices": list(indices)}
        return status, candidate

    try:
        while True:
            status, candidate = one_solve(cap, None, "makespan")
            if status == cp_model.INFEASIBLE:
                return save("complete")
            if status != cp_model.OPTIMAL:
                return save("incomplete", candidate)
            best_makespan = candidate["point"][0]
            status, candidate = one_solve(cap, best_makespan, "energy")
            if status != cp_model.OPTIMAL:
                return save("incomplete", candidate)
            point = tuple(candidate["point"])
            archive.append((point, tuple(candidate["indices"])))
            archive.sort(key=lambda entry: entry[0])
            cap = point[1] - 1
            print(f"[{instance.path.name}] Pareto provado: Cmax={point[0]}, TEC={point[1]}/{scale}", flush=True)
            if cap < 0:
                return save("complete")
            save("incomplete")
    except KeyboardInterrupt:
        return save("incomplete")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fronteira exata via CP-SAT e ε-restrição")
    parser.add_argument("input", nargs="?", type=Path, default=PROJECT_ROOT / "data" / "input" / "set1")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "output" / "cpsat")
    parser.add_argument("--time-limit", type=float, default=60.0,
                        help="segundos por chamada do solver; 0 = sem limite")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args(argv)
    paths = sorted(args.input.glob("*.dat")) if args.input.is_dir() else [args.input]
    if not paths or any(not path.is_file() for path in paths):
        parser.error("Nenhum arquivo .dat encontrado")
    for path in paths:
        try:
            instance = read_instance(path)
            output = args.output_dir / f"{path.stem}.json"
            report = solve_front(instance, output=output, seconds_per_solve=args.time_limit,
                                 workers=args.workers, resume=args.resume, restart=args.restart)
            print(f"{path.name}: {report['status']}, pontos provados={len(report['front'])}, saída={output}", flush=True)
        except (OSError, ValueError) as error:
            parser.error(f"{path.name}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
