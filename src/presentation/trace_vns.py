"""Reproduz a primeira construção das duas versões de VNS/VND em uma instância."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from metaheuristics import vns_vnd, vns_vnd_original
from problem import read_instance
from schedule import evaluate_schedule


INSTANCE = Path("data/input/set2/750_10_1439_5_S_1-9.dat")
OUTPUT = HERE / "data" / "vns_trace.json"
SEED = 1001


def observe_constructor(instance, constructor):
    """Captura o estado no retorno da função sem alterar a implementação ou o RNG."""
    snapshot = {}

    def on_return(frame, event, _value):
        if event == "return":
            state = frame.f_locals
            snapshot.update(
                machine_ends=list(state["machine_end"]),
                jobs_per_machine=[len(jobs) for jobs in state["machine_jobs"]],
                last_jobs=list(state["machine_last"]),
                final_job=state["job"],
            )
        return on_return

    def on_call(frame, event, _value):
        if event == "call" and frame.f_code is constructor.__code__:
            frame.f_trace_lines = False
            return on_return
        return None

    previous_trace = sys.gettrace()
    sys.settrace(on_call)
    try:
        schedule = constructor(instance, random.Random(SEED))
    finally:
        sys.settrace(previous_trace)

    ends = snapshot["machine_ends"]
    counts = snapshot["jobs_per_machine"]
    assigned = sum(counts)
    blocked_job = minimum_end = ends_by_machine = makespan = None

    if schedule is None:
        blocked_job = snapshot["final_job"]
        ends_by_machine = []
        for machine, (end, prior) in enumerate(zip(ends, snapshot["last_jobs"], strict=True)):
            setup = instance.setup[machine][prior][blocked_job] if prior is not None else 0
            best_duration = min(
                instance.duration(blocked_job, machine, mode) for mode in range(instance.modes)
            )
            ends_by_machine.append(end + setup + best_duration)
        minimum_end = min(ends_by_machine)
        if not (assigned < instance.n and minimum_end > instance.horizon):
            raise RuntimeError("A construção interrompida não coincide com o diagnóstico de horizonte")
    else:
        evaluation = evaluate_schedule(instance, schedule)
        makespan = evaluation.cmax
        verified_ends = [0] * instance.m
        for operation in evaluation.operations:
            verified_ends[operation.machine] = max(verified_ends[operation.machine], operation.end)
        if assigned != instance.n or ends != verified_ends or makespan != max(ends):
            raise RuntimeError("O estado capturado difere do escalonamento validado")

    return {
        "assigned": assigned,
        "machine_ends": ends,
        "jobs_per_machine": counts,
        "completed": schedule is not None,
        "blocked_job_zero_based": blocked_job,
        "minimum_candidate_end": minimum_end,
        "minimum_candidate_ends_by_machine": ends_by_machine,
        "makespan": makespan,
    }


def build_trace():
    instance = read_instance(ROOT / INSTANCE)
    sources = (INSTANCE, Path("src/problem.py"), Path("src/schedule.py"),
               Path("src/metaheuristics/vns_vnd_original.py"), Path("src/metaheuristics/vns_vnd.py"))
    return {
        "scope": "primeira construção por versão, sem busca VNS/VND e fora da campanha experimental",
        "instance": INSTANCE.name,
        "seed": SEED,
        "construction": 1,
        "jobs": instance.n,
        "machines": instance.m,
        "modes": instance.modes,
        "days": instance.days,
        "slots_per_day": instance.slots_per_day,
        "horizon": instance.horizon,
        "peak_intervals": [list(interval) for interval in instance.peaks],
        "original": observe_constructor(instance, vns_vnd_original._random_greedy_schedule),
        "revised": observe_constructor(instance, vns_vnd._random_greedy_schedule),
        "source_sha256_lf": {
            source.as_posix(): sha256((ROOT / source).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for source in sources
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verifica o JSON já salvo sem alterá-lo.")
    args = parser.parse_args()
    trace = build_trace()
    if args.check:
        # Use os resultados para verificar o arquivo mesmo com conversão de quebras de linha pelo Git.
        actual = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if actual != trace:
            parser.exit(1, f"O trace atual diverge de {OUTPUT}\n")
        print(f"Trace verificado: {OUTPUT}")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Trace registrado: {OUTPUT}")


if __name__ == "__main__":
    main()
