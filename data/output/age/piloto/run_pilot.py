"""Bounded AGE pilot. Preflight first; immutable solver; resumable sealed runs."""
from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
import time
import warnings
from unittest.mock import patch

import numba
from numba.core.event import install_timer
import numpy as np
import pymoo

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'data/output/final_comparison')]
from normalization import calculate_bounds, REFERENCE
from problem import atomic_json, read_instance, dominates
from schedule import evaluate_schedule
from metaheuristics import age, spea2

OUT = Path(__file__).resolve().parent
SEEDS = (11, 29, 47)
RESERVED = (101, 211, 307, 401, 503, 601, 701, 809, 907, 1009)
INSTANCES = ('set1/6_2_1439_3_S_1-9.dat',
             'set1/14_2_1439_3_S_1-9_derivada.dat',
             'set2/50_10_1439_5_S_1-9.dat', 'set2/250_10_1439_5_S_1-9.dat')
SOURCES = ('src/metaheuristics/age.py', 'src/metaheuristics/spea2.py',
           'src/schedule.py', 'src/problem.py',
           'data/output/final_comparison/normalization.py',
           'data/output/age/piloto/run_pilot.py')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def cells():
    # Rotate configurations per seed and reverse on alternate instance blocks.
    configs = [(p, m) for p in (25, 50, 100) for m in (0.1, 0.3)]
    for i, path in enumerate(INSTANCES):
        for j, seed in enumerate(SEEDS):
            order = configs[j:] + configs[:j]
            if i % 2:
                order = list(reversed(order))
            for population, mutation in order:
                yield path, population, mutation, seed


def diversity(schedules):
    signatures = dict(schedules=set(), allocations=set(), orders=set(), modes=set(), waits=set())
    for schedule in schedules:
        schedule = tuple(tuple(tuple(item) for item in seq) for seq in schedule)
        signatures['schedules'].add(schedule)
        signatures['allocations'].add(tuple(tuple(sorted(j for j, _, _ in seq)) for seq in schedule))
        signatures['orders'].add(tuple(tuple(j for j, _, _ in seq) for seq in schedule))
        signatures['modes'].add(tuple(sorted((j, m) for seq in schedule for j, m, _ in seq)))
        signatures['waits'].add(tuple(sorted((j, w) for seq in schedule for j, _, w in seq)))
    return {k: len(v) for k, v in signatures.items()}


def validate_front(instance, payload):
    if payload['instance_sha256'] != instance.digest:
        raise ValueError('Input hash mismatch')
    keys = []
    for row in payload['front']:
        ev = evaluate_schedule(instance, row['representation'])
        tec = row['tec_exact']
        if (ev.cmax != row['makespan'] or ev.tec_exact != Fraction(tec['numerator'], tec['denominator'])
                or ev.tec_scale != tec['denominator'] or ev.tec_units != tec['numerator']
                or ev.to_result_dict(instance)['schedule'] != row['schedule']):
            raise ValueError('Exported objective/schedule mismatch')
        keys.append(ev.objective_key)
    if not keys or len(keys) != len(set(keys)) or any(dominates(a, b) for a in keys for b in keys):
        raise ValueError('Front empty, duplicated or dominated')
    return keys


def measured_run(path, population, mutation, seed, budget):
    if seed in RESERVED:
        raise ValueError('Reserved seed')
    instance = read_instance(ROOT / 'data/input' / path)
    config = age.AGEConfig(seed=seed, max_evaluations=budget, population_size=population,
                           crossover_probability=0.9, mutation_probability=mutation)
    counts = dict(search=0, post=0)
    final_population = []
    native_final = age._final_front
    compilation = []

    def search(*args, **kwargs):
        counts['search'] += 1
        return evaluate_schedule(*args, **kwargs)

    def post(*args, **kwargs):
        counts['post'] += 1
        return evaluate_schedule(*args, **kwargs)

    def capture(instance_arg, pop):
        final_population.extend(ind.X[0] for ind in pop)
        return native_final(instance_arg, pop)

    started = time.perf_counter()
    with warnings.catch_warnings(), install_timer('numba:compile', compilation.append), \
         patch.object(spea2, 'evaluate_schedule', side_effect=search), \
         patch.object(age, 'evaluate_schedule', side_effect=post), \
         patch.object(age, '_final_front', side_effect=capture):
        warnings.simplefilter('error', RuntimeWarning)
        result = age.run_age(instance, config)
    wall = time.perf_counter() - started
    if not (counts['search'] == result.attempts == result.pymoo_evaluations == budget
            and result.feasible_evaluations + result.rejected_evaluations == budget
            and counts['post'] == result.post_search_validations == population
            and sum(result.evaluation_batches) == budget):
        raise ValueError('Evaluation budget mismatch')
    for schedule in final_population:
        evaluate_schedule(instance, schedule)
    payload = result.to_result_dict()
    keys = validate_front(instance, payload)
    payload['pilot'] = dict(
        independent_search_calls=counts['search'], independent_post_calls=counts['post'],
        independent_population_revalidations=len(final_population),
        independent_front_revalidations=len(keys),
        population_diversity=diversity(final_population),
        front_diversity=diversity([row['representation'] for row in payload['front']]),
        numba_compile_seconds=sum(compilation), wall_run_and_internal_validation_seconds=wall,
        validation_status='valid_exact_unique_nondominated')
    return payload


def protocol():
    if set(SEEDS) & set(RESERVED):
        raise ValueError('Reserved seed overlap')
    return dict(
        seeds=list(SEEDS), reserved_seeds=list(RESERVED), instances=list(INSTANCES),
        populations=[25, 50, 100], mutations=[0.1, 0.3], crossover=0.9,
        budget=8000, expected_runs=72, expected_search_evaluations=576000,
        source_sha256={p: digest(ROOT / p) for p in SOURCES},
        input_sha256={p: digest(ROOT / 'data/input' / p) for p in INSTANCES},
        indicator_bounds={p: calculate_bounds(read_instance(ROOT / 'data/input' / p)) for p in INSTANCES},
        reference_point=REFERENCE,
        reference_policy='After all searches: exact 6-job baseline, otherwise exact Pareto union of AGE pilot fronts only',
        selection_rule='Mean rank of per-instance median HV; IGD+ mean rank as tie breaker, then smaller population and mutation; report ranges/IQR and seed ranks',
        runtime=dict(python=sys.version, numpy=np.__version__, pymoo=pymoo.__version__,
                     numba=numba.__version__, platform=platform.platform()),
        order=list(cells()))


def preflight():
    target = OUT / 'preflight.json'
    if target.exists():
        raise FileExistsError(target)
    frozen = protocol()
    atomic_json(OUT / 'protocol.json', frozen)
    observations = []
    # Same process cold/warm pair; neither contributes to pilot references.
    for path in INSTANCES:
        for pop in (25, 100):
            repeats = 2 if path == INSTANCES[0] and pop == 25 else 1
            for repeat in range(repeats):
                row = measured_run(path, pop, .3, 11, 400)
                observations.append(dict(instance=path, population=pop, repeat=repeat,
                    seconds=row['elapsed_seconds'], compile_seconds=row['pilot']['numba_compile_seconds'],
                    attempts=row['attempts'], points=row['points'],
                    signature=sha256(json.dumps(row['front'], sort_keys=True).encode()).hexdigest()))
                print(f"preflight {path} P={pop} rep={repeat}: {row['elapsed_seconds']:.3f}s "
                      f"JIT={row['pilot']['numba_compile_seconds']:.3f}s", flush=True)
    if observations[0]['signature'] != observations[1]['signature']:
        raise ValueError('Cold/warm result differs')
    estimate = 0.
    for path in INSTANCES:
        rates = [max(0., o['seconds'] - o['compile_seconds']) / 400
                 for o in observations if o['instance'] == path]
        estimate += max(rates) * 8000 * 18
    atomic_json(target, dict(observations=observations, total_search_evaluations=3600,
        estimated_pilot_search_seconds=estimate, conservative_allowance_seconds=estimate*2,
        estimation='Worst warmed 400-evaluation rate per instance times 18*8000; 2x allowance; excludes analysis and assumes stable rate',
        protocol_sha256=digest(OUT / 'protocol.json')))


def run():
    frozen = json.loads((OUT / 'protocol.json').read_text())
    if json.loads(json.dumps(protocol())) != frozen:
        raise ValueError('Protocol/source/runtime changed after preflight')
    pre = json.loads((OUT / 'preflight.json').read_text())
    if pre['protocol_sha256'] != digest(OUT / 'protocol.json'):
        raise ValueError('Preflight protocol mismatch')
    if pre['conservative_allowance_seconds'] > 5400:
        raise RuntimeError('Preflight exceeds 90-minute cost envelope; revise design explicitly')
    manifest = dict(status='running', protocol_sha256=digest(OUT / 'protocol.json'), runs=[])
    (OUT / 'runs').mkdir(exist_ok=True)
    for i, (path, pop, mutation, seed) in enumerate(cells(), 1):
        target = OUT / 'runs' / f'{Path(path).stem}__p{pop}_m{mutation}__s{seed}.json'
        try:
            if target.exists():
                data = json.loads(target.read_text())
                expected = age.AGEConfig(seed, 8000, pop, .9, mutation).as_dict()
                if data['run_parameters'] != expected or data['pilot_protocol_sha256'] != manifest['protocol_sha256']:
                    raise ValueError('Existing result does not match frozen pilot')
                validate_front(read_instance(ROOT / 'data/input' / path), data)
            else:
                data = measured_run(path, pop, mutation, seed, 8000)
                data['pilot_protocol_sha256'] = manifest['protocol_sha256']
                atomic_json(target, data)
        except Exception as error:
            manifest.update(status='interrupted', error=repr(error), failed_cell=[path,pop,mutation,seed])
            atomic_json(OUT / 'manifest.json', manifest)
            raise
        manifest['runs'].append(dict(file=str(target.relative_to(OUT)), sha256=digest(target)))
        atomic_json(OUT / 'manifest.json', manifest)
        print(f"[{i}/72] {path} P={pop} m={mutation} s={seed}: "
              f"{data['elapsed_seconds']:.2f}s points={data['points']}", flush=True)
    manifest.update(status='searches_complete', evaluations=sum(8000 for _ in manifest['runs']))
    atomic_json(OUT / 'manifest.json', manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['preflight', 'run'])
    args = parser.parse_args()
    {'preflight': preflight, 'run': run}[args.stage]()
