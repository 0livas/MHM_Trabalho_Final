"""Calcula os dados da instância didática da introdução com o próprio modelo do projeto."""

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent / "exact_methods")]

from problem import energy_scale, generate_choices, read_instance  # noqa: E402
from schedule import evaluate_schedule, schedule_from_result_rows  # noqa: E402
import custom_exact_dp  # noqa: E402

ENTRADA = HERE / "data" / "didatica.dat"
SAIDA = HERE / "data" / "didatica.json"


def plano(instance, rows):
    schedule = schedule_from_result_rows(instance, rows)
    result = evaluate_schedule(instance, schedule)
    operations = {op.job: op for op in result.operations}
    blocks = []
    for machine, sequence in enumerate(schedule):
        previous = None
        for job, mode, wait in sequence:
            op = operations[job]
            setup = 0 if previous is None else instance.setup[machine][previous][job]
            power = instance.power[machine] * instance.power_factor[mode] * 24 / instance.slots_per_day
            costs = [float(power * (instance.peak_rate if any(a <= t < b for a, b in instance.peaks)
                                    else instance.off_rate)) for t in range(op.start, op.end)]
            assert abs(sum(costs) - op.tec_units / result.tec_scale) < 1e-9
            blocks.append(dict(job=job, machine=machine, mode=mode, setup=setup, wait=wait,
                               start=op.start, end=op.end, costs=costs))
            previous = job
    return dict(cmax=result.cmax, tec=result.tec, blocks=blocks)


def calcular():
    instance = read_instance(ENTRADA)
    scale, prices = energy_scale(instance)
    choices = generate_choices(instance, prices)
    minimum = custom_exact_dp.minimum_makespan(instance)["minimum_makespan"]
    dp = custom_exact_dp.EnergyDP(instance)
    dp.prepare()
    front, seen = [], set()
    for epsilon in range(minimum, instance.horizon + 1):
        point, indices = dp.solve(epsilon)
        if point in seen:
            continue
        seen.add(point)
        rows = [dict(job=j, machine=c.machine, mode=c.mode, start=c.start, end=c.end)
                for j, c in enumerate(choices[j][k] for j, k in enumerate(indices))]
        row = plano(instance, rows)
        assert row["cmax"] == point[0] and abs(row["tec"] - point[1] / scale) < 1e-9
        front.append(row)
    return dict(sha256=instance.digest, n=instance.n, m=instance.m, horizon=instance.horizon,
                inicio_relogio=8, peak=list(instance.peaks[0]),
                rates=[float(instance.off_rate), float(instance.peak_rate)],
                power=[float(v) for v in instance.power], speed=[float(v) for v in instance.speed],
                factor=[float(v) for v in instance.power_factor],
                processing=[list(row) for row in instance.processing],
                setup=[[list(row) for row in matrix] for matrix in instance.setup], front=front)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Confere o JSON salvo sem regravar.")
    args = parser.parse_args()
    data = calcular()
    if args.check:
        if json.loads(SAIDA.read_text(encoding="utf-8")) != data:
            raise SystemExit("didatica.json diverge da instância.")
    else:
        SAIDA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print([(p["cmax"], p["tec"]) for p in data["front"]])


if __name__ == "__main__":
    main()
