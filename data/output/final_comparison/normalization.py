"""External indicator normalization only. Never changes any search scaling.

Independent individual options are exactly the relaxation in generate_choices.
For duration d, overlap of [s,s+d) with each peak [a,b) is piecewise affine
in s, with integer breakpoints a-d,b-d,a,b. Its extrema on integer
0 <= s <= H-d therefore occur at these breakpoints or domain endpoints.
Evaluating them with interval_cost_units gives exact extrema, without
materializing choices or using any search result.
"""
from fractions import Fraction
from math import isfinite
from problem import energy_scale, interval_cost_units

METHOD = 'individual_option_extrema_piecewise_exact_v1'
REFERENCE = (1.05, 1.05)


def energy_extrema(instance, duration, on_price, off_price):
    last = instance.horizon-duration
    if last < 0:
        raise ValueError('Individual duration exceeds horizon')
    starts = {0, last}
    for a, b in instance.peaks:
        starts.update(s for s in (a-duration, b-duration, a, b) if 0 <= s <= last)
    costs = [interval_cost_units(instance, s, s+duration, on_price, off_price)
             for s in sorted(starts)]
    return min(costs), max(costs)


def calculate_bounds(instance):
    scale, prices = energy_scale(instance)
    minima, lower, upper = [], 0, 0
    cache = {}
    for job in range(instance.n):
        durations, costs = [], []
        for machine, mode, on, off in prices:
            d = instance.duration(job, machine, mode)
            if d > instance.horizon:
                continue
            durations.append(d)
            key = (d, on, off)
            if key not in cache:
                cache[key] = energy_extrema(instance, *key)
            costs.append(cache[key])
        if not costs:
            raise ValueError(f'Job {job} has no individual feasible option')
        minima.append(min(durations))
        lower += min(v[0] for v in costs)
        upper += max(v[1] for v in costs)
    c_lb = max(max(minima), (sum(minima)+instance.m-1)//instance.m)
    result = dict(method=METHOD, instance_sha256=instance.digest,
        C_LB=c_lb, C_UB=instance.horizon, TEC_LB_units=lower,
        TEC_UB_units=upper, tec_scale=scale,
        TEC_LB_exact=str(Fraction(lower, scale)), TEC_UB_exact=str(Fraction(upper, scale)),
        individual_min_duration_sum=sum(minima))
    if c_lb >= instance.horizon or lower >= upper:
        raise ValueError(f'Degenerate/nonpositive denominator: {result}')
    return result


def normalize_exact(cmax, tec_units, bounds):
    c = Fraction(cmax-bounds['C_LB'], bounds['C_UB']-bounds['C_LB'])
    e = Fraction(tec_units-bounds['TEC_LB_units'], bounds['TEC_UB_units']-bounds['TEC_LB_units'])
    if not (0 <= c <= 1 and 0 <= e <= 1):
        raise ValueError(f'A priori bounds violated: {cmax}, {tec_units} -> {c}, {e}')
    return c, e


def normalize(cmax, tec_units, bounds):
    exact = normalize_exact(cmax, tec_units, bounds)
    point = tuple(float(v) for v in exact)
    assert all(isfinite(v) and 0 <= v <= 1 for v in point), point
    assert all(v < r for v, r in zip(point, REFERENCE)), point
    return point
