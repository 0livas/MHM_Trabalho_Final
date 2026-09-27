from fractions import Fraction
from itertools import product

import problem


def brute_front(instance):
    """Oráculo exaustivo somente para instâncias pequenas de teste."""
    scale, prices = problem.energy_scale(instance)
    choices = problem.generate_choices(instance, prices)
    points = set()
    for selected in product(*choices):
        sequences = [[] for _ in range(instance.m)]
        for job, choice in enumerate(selected):
            sequences[choice.machine].append((choice.start, choice.end, job))
        if any(next_start < end + instance.setup[machine][job][next_job]
               for machine, sequence in enumerate(sequences)
               for (_start, end, job), (next_start, _next_end, next_job)
               in zip(sorted(sequence), sorted(sequence)[1:])):
            continue
        energy = Fraction(0)
        for choice in selected:
            for slot in range(choice.start, choice.end):
                peak = any(start <= slot < end for start, end in instance.peaks)
                rate = instance.peak_rate if peak else instance.off_rate
                energy += (instance.power[choice.machine] * instance.power_factor[choice.mode]
                           * rate * Fraction(24, instance.slots_per_day))
        points.add((max(choice.end for choice in selected), int(energy * scale)))
    return sorted(point for point in points if not any(
        other != point and other[0] <= point[0] and other[1] <= point[1]
        for other in points))
