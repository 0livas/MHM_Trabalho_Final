"""Frozen sequential campaign. Never reads exact/empirical reference fronts.

Run: python data/output/final_comparison/run_final.py
Resume uses the same command; a methodological stop cannot be bypassed.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import fcntl
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np
import pymoo

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / 'src'))
import schedule as shared
from problem import atomic_json, dominates, read_instance
from metaheuristics import vns_vnd, spea2, moead
from normalization import calculate_bounds, normalize_exact, normalize

SEEDS = [101, 211, 307, 401, 503, 601, 701, 809, 907, 1009]
ALGORITHMS = ['vns_vnd', 'spea2', 'moead']
TARGET = 'data/input/set2/250_10_1439_5_S_1-9.dat'
CHECKPOINT = '40bf609ccddb092acb32f856e19b67418b52613e'
FROZEN = {
    'vns_vnd': dict(initial_solutions=4, max_candidates_per_neighborhood=25, shaking_attempts=20),
    'spea2': dict(population_size=50, crossover_probability=0.9, mutation_probability=0.3),
    'moead': dict(population_size=50, n_neighbors=20, prob_neighbor_mating=0.9,
                  crossover_probability=0.9, mutation_probability=0.3),
}
SOURCES = ['src/metaheuristics/vns_vnd.py', 'src/metaheuristics/spea2.py',
           'src/metaheuristics/moead.py', 'src/schedule.py', 'src/problem.py']


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def seal(payload):
    copy = {k: v for k, v in payload.items() if k != 'artifact_sha256'}
    return sha256(json.dumps(copy, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False).encode()).hexdigest()


def inventory():
    # Headers suffice for inventory: avoid loading 750-job quadratic setup matrices.
    rows = []
    for p in sorted((ROOT / 'data/input').rglob('*.dat')):
        t = p.read_text(encoding='utf-8-sig').split()
        rows.append(dict(path=str(p.relative_to(ROOT)), sha256=digest(p), n=int(t[1]),
                         m=int(t[3]), horizon=int(t[5])*(int(t[7])+1),
                         max_cost=t[t.index('max_cost')+1],
                         classification='derived' if '_derivada' in p.stem else 'original'))
    return rows


def plan(rows):
    originals = [r for r in rows if r['classification'] == 'original']
    a = sorted([r for r in originals if r['n'] <= 250],
               key=lambda r: (r['path'] != TARGET, r['n'], r['path']))
    b = sorted([r for r in originals if r['n'] == 750], key=lambda r: r['path'])
    target = next(r for r in originals if r['path'] == TARGET)
    specs, block = [], 0
    for experiment, instances, seeds, budget in [('A', a, SEEDS, 8000),
                                               ('B', b, SEEDS[:5], 2000),
                                               ('C', [target], SEEDS[:5], 20000)]:
        for row in instances:
            for seed in seeds:
                offset = block % 3
                order = ALGORITHMS[offset:] + ALGORITHMS[:offset]
                for algorithm in order:
                    specs.append(dict(experiment=experiment, instance=row['path'],
                        instance_sha256=row['sha256'], algorithm=algorithm, seed=seed,
                        budget=budget, block=block, order_in_block=order,
                        file=f"runs/{experiment}__{Path(row['path']).stem}__{algorithm}__b{budget}__s{seed}.json"))
                block += 1
    return specs


def configuration(spec):
    cls = {'vns_vnd': vns_vnd.VNSConfig, 'spea2': spea2.SPEA2Config,
           'moead': moead.MOEADConfig}[spec['algorithm']]
    return cls(seed=spec['seed'], max_evaluations=spec['budget'], **FROZEN[spec['algorithm']])


def validate(payload, spec, instance, bounds=None):
    if bounds is None:
        bounds = calculate_bounds(instance)
    if bounds["instance_sha256"] != instance.digest:
        raise ValueError("Normalization bounds instance hash mismatch")
    if payload.get('artifact_sha256') != seal(payload):
        raise ValueError('Corrupted/unsealed run artifact')
    if payload['experiment_spec'] != spec or payload['instance_sha256'] != instance.digest:
        raise ValueError('Run identity/hash mismatch')
    if payload['run_parameters'] != configuration(spec).as_dict():
        raise ValueError('Frozen configuration mismatch')
    if payload['source_sha256'] != {p: digest(ROOT / p) for p in SOURCES}:
        raise ValueError('Source hash mismatch')
    budget = spec['budget']
    if not payload['attempts'] == payload['evaluations'] == budget:
        raise ValueError('Budget mismatch')
    if payload['feasible_evaluations'] + payload['rejected_evaluations'] != budget:
        raise ValueError('Feasible/rejected accounting mismatch')
    if payload.get('pymoo_evaluations', budget) != budget:
        raise ValueError('Pymoo accounting mismatch')
    counts = payload['independent_evaluator_calls']
    if counts['search'] != budget or counts['post_search'] != payload['post_search_validations']:
        raise ValueError('Independent evaluator accounting mismatch')
    keys, violations = [], []
    for i, row in enumerate(payload['front']):
        evaluation = shared.evaluate_schedule(instance, row['representation'])
        expected = Fraction(row['tec_exact']['numerator'], row['tec_exact']['denominator'])
        if (evaluation.cmax != row['makespan'] or evaluation.tec_exact != expected
                or evaluation.tec_units != row['tec_exact']['numerator']
                or evaluation.tec_scale != row['tec_exact']['denominator']):
            raise ValueError('Exact final objectives mismatch')
        if evaluation.to_result_dict(instance)['schedule'] != row['schedule']:
            raise ValueError('Decoded schedule mismatch')
        keys.append(evaluation.objective_key)
        c, e = normalize_exact(evaluation.cmax, evaluation.tec_units, bounds)
        normalize(evaluation.cmax, evaluation.tec_units, bounds)
        if c >= Fraction(21, 20) or e >= Fraction(21, 20):
            violations.append(dict(front_index=i, cmax=evaluation.cmax,
                tec_units=evaluation.tec_units, tec_scale=evaluation.tec_scale,
                tec_exact=str(evaluation.tec_exact), cmax_norm_exact=str(c),
                tec_norm_exact=str(e), cmax_norm=float(c), tec_norm=float(e)))
    if not keys or len(keys) != len(set(keys)) or payload['points'] != len(keys):
        raise ValueError('Empty/duplicated/inconsistent final front')
    if any(dominates(a, b) for a in keys for b in keys if a != b):
        raise ValueError('Final front is not exactly nondominated')
    return violations


def execute(spec, instance):
    module = {'vns_vnd': vns_vnd, 'spea2': spea2, 'moead': moead}[spec['algorithm']]
    counts = {'search': 0, 'post_search': 0}
    phase = 'search'
    raw = shared.evaluate_schedule
    def counted(instance_arg, schedule_arg):
        counts[phase] += 1
        return raw(instance_arg, schedule_arg)
    with ExitStack() as stack:
        # Wrap existing evaluator bindings, preserving every return value/exception.
        for binding in [shared, vns_vnd, spea2, moead]:
            stack.enter_context(patch.object(binding, 'evaluate_schedule', counted))
        if spec['algorithm'] != 'vns_vnd':
            native_final = module._final_front
            def final(instance_arg, population):
                nonlocal phase
                phase = 'post_search'
                return native_final(instance_arg, population)
            stack.enter_context(patch.object(module, '_final_front', final))
        config = configuration(spec)
        result = (vns_vnd.VNSVND(instance, config).run() if spec['algorithm'] == 'vns_vnd'
                  else module.run_spea2(instance, config) if spec['algorithm'] == 'spea2'
                  else module.run_moead(instance, config))
    payload = result.to_result_dict()
    payload.update(experiment_spec=spec, attempts=payload['evaluations'],
                   post_search_validations=payload.get('post_search_validations', 0),
                   independent_evaluator_calls=counts,
                   source_sha256={p: digest(ROOT / p) for p in SOURCES})
    payload['artifact_sha256'] = seal(payload)
    return payload



def outcome_path(spec):
    return OUT / 'outcomes' / (Path(spec['file']).stem + '.json')


def completed_outcome(spec, payload):
    return dict(status='completed', experiment_spec=spec, algorithm=spec['algorithm'],
        instance=spec['instance'], instance_sha256=spec['instance_sha256'], seed=spec['seed'],
        frozen_parameters=configuration(spec).as_dict(), planned_max_evaluations=spec['budget'],
        initialization_success=True, run_completed=True, failure_stage=None, failure_reason=None,
        initialization_attempts=None, search_attempts=payload['attempts'],
        feasible_evaluations=payload['feasible_evaluations'], rejected_evaluations=payload['rejected_evaluations'],
        post_search_validations=payload['post_search_validations'], elapsed_seconds=payload['elapsed_seconds'],
        algorithm_source_sha256=payload['source_sha256'][f"src/metaheuristics/{spec['algorithm']}.py"],
        run_file=spec['file'], run_file_sha256=digest(OUT/spec['file']),
        materialized_utc=utc(), provenance='manifest-indexed completed run; original result JSON preserved')


def initialization_failure_outcome(spec, *, initialization_attempts, elapsed_seconds,
                                   failure_reason, source_sha256, occurred_utc, provenance):
    if spec['algorithm'] != 'vns_vnd' or initialization_attempts < 1:
        raise ValueError('Initialization failure schema mismatch')
    return dict(status='initialization_failed', experiment_spec=spec, algorithm=spec['algorithm'],
        instance=spec['instance'], instance_sha256=spec['instance_sha256'], seed=spec['seed'],
        frozen_parameters=configuration(spec).as_dict(), planned_max_evaluations=spec['budget'],
        initialization_success=False, run_completed=False, failure_stage='initialization',
        failure_reason=failure_reason, initialization_attempts=initialization_attempts,
        search_attempts=0, feasible_evaluations=0, rejected_evaluations=0,
        post_search_validations=0, elapsed_seconds=elapsed_seconds,
        algorithm_source_sha256=source_sha256['src/metaheuristics/vns_vnd.py'],
        source_sha256=source_sha256, occurred_utc=occurred_utc, materialized_utc=utc(),
        provenance=provenance, quality_metrics=dict(hv=None,igd_plus=None,cmax_min=None,tec_min=None,front_size=None))


def seal_outcome(payload):
    payload.pop('outcome_sha256',None)
    payload['outcome_sha256'] = sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),
                                                    ensure_ascii=False).encode()).hexdigest()
    return payload


def persist_outcome(spec, outcome, manifest, manifest_path):
    target=outcome_path(spec)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        prior=json.loads(target.read_text())
        if prior != outcome:
            raise FileExistsError(f'Outcome exists with different content: {target}')
    else:
        seal_outcome(outcome)
        atomic_json(target,outcome)
    filehash=digest(target)
    prior=manifest.setdefault('cell_outcomes',{}).get(spec['file'])
    entry=dict(status=outcome['status'],outcome_file=str(target.relative_to(OUT)),
               outcome_file_sha256=filehash)
    if prior and prior != entry:
        raise ValueError('Outcome registry conflicts with preserved cell outcome')
    manifest['cell_outcomes'][spec['file']]=entry
    atomic_json(manifest_path,manifest)


def validate_outcome(payload,spec,manifest):
    expected=payload.get('outcome_sha256')
    check=dict(payload);check.pop('outcome_sha256',None)
    actual=sha256(json.dumps(check,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    if expected != actual or payload.get('experiment_spec') != spec:
        raise ValueError('Outcome checksum/identity mismatch')
    if payload.get('planned_max_evaluations') != spec['budget']:
        raise ValueError('Outcome budget mismatch')
    status=payload['status']
    if status=='completed':
        run=OUT/spec['file']
        if not run.is_file() or digest(run)!=payload['run_file_sha256']:
            raise ValueError('Completed outcome points to missing/changed run')
        if payload['search_attempts'] != spec['budget'] or payload['run_completed'] is not True:
            raise ValueError('Completed outcome does not satisfy hard cap')
    elif status=='initialization_failed':
        if not (payload['failure_stage']=='initialization' and payload['search_attempts']==0
                and payload['feasible_evaluations']==0 and payload['rejected_evaluations']==0
                and payload['run_completed'] is False and payload['initialization_success'] is False):
            raise ValueError('Initialization failure has contaminated search accounting')
    elif status=='execution_failed':
        if payload['run_completed'] is not False:
            raise ValueError('Invalid technical failure outcome')
    else:
        raise ValueError(f'Unknown cell outcome: {status}')
    return status


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Linux flock prevents concurrent campaigns; lock stays outside tracked artifacts.
    with open('/tmp/mhm-final-comparison.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_campaign()


def run_campaign():
    sources = {p: digest(ROOT / p) for p in SOURCES}
    checkpoint_hashes = {p: sha256(subprocess.check_output(
        ['git', 'show', f'{CHECKPOINT}:{p}'], cwd=ROOT)).hexdigest() for p in SOURCES}
    normalized_sources = {p: sha256((ROOT / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in SOURCES}
    if normalized_sources != checkpoint_hashes:
        raise ValueError('Authoritative checkpoint differs; refusing searches')
    rows = inventory()
    specs = plan(rows)
    scripts = {p.name: digest(p) for p in [Path(__file__), OUT / 'analyze_final.py',
        OUT / 'normalization.py', OUT / 'validate_normalization.py', OUT / 'summarize_blocked.py',
        OUT / 'record_initialization_failure.py']}
    identity = dict(checkpoint=CHECKPOINT, source_sha256=sources,
                    checkpoint_source_sha256=checkpoint_hashes, git_normalized_source_sha256=normalized_sources, inventory=rows,
                    frozen_parameters=FROZEN, seeds=SEEDS, execution_order=specs,
                    script_sha256=scripts, reference_point=[1.05, 1.05])
    path = OUT / 'manifest.json'
    if path.exists():
        manifest = json.loads(path.read_text())
        if any(manifest.get(k) != v for k, v in identity.items()):
            raise ValueError('Protocol/source/script changed; refusing resume')
    else:
        if (OUT / 'runs').exists() and any((OUT / 'runs').iterdir()):
            raise ValueError('Unindexed artifacts; refusing overwrite')
        cpu = next((line.split(':', 1)[1].strip() for line in
                    Path('/proc/cpuinfo').read_text().splitlines()
                    if line.startswith('model name')), platform.processor())
        manifest = dict(**identity, status='running', started_utc=utc(),
            git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            environment=dict(python=sys.version, pymoo=pymoo.__version__, numpy=np.__version__,
                             platform=platform.platform(), cpu=cpu),
            expected_runs=len(specs), expected_attempts=sum(s['budget'] for s in specs),
            completed_runs={}, sessions=[], baseline_reads=[],
            order_policy='A: target first, then n/path; B: path; C: target. Rotate by block modulo 3.',
            budget_contract='complete evaluator attempts; infeasible count; post-search separate',
            memory_policy='not measured: same-process RSS high-water mark is not per-run comparable',
            normalizer_definition='H is feasibility horizon; max_cost is a positive input scalar, not an enforced TEC upper bound')
        atomic_json(path, manifest)
    if not manifest.get('protocol_amendments') or not manifest.get('indicator_bounds'):
        raise ValueError('Validated instance-bound amendment required before resume')
    validation_path = OUT / 'normalization_validation.json'
    if digest(validation_path) != manifest['normalization_validation_sha256']:
        raise ValueError('Pre-resume normalization validation changed')
    # Detect unexpected/incomplete artifacts before new searches.
    expected_files = {s['file'] for s in specs}
    if (OUT / 'runs').exists():
        actual = {str(p.relative_to(OUT)) for p in (OUT / 'runs').iterdir()}
        if actual - expected_files:
            raise ValueError(f'Unexpected/incomplete artifacts: {sorted(actual - expected_files)}')
    outcome_dir=OUT/'outcomes'; outcome_dir.mkdir(exist_ok=True)
    expected_outcomes={str(outcome_path(s).relative_to(OUT)) for s in specs}
    actual_outcomes={str(p.relative_to(OUT)) for p in outcome_dir.glob('*.json')}
    if actual_outcomes-expected_outcomes:
        raise ValueError(f'Unexpected outcome artifacts: {sorted(actual_outcomes-expected_outcomes)}')
    # Materialize outcomes for the completed historical runs without rerunning or rewriting them.
    for spec in specs:
        if spec['file'] in manifest['completed_runs'] and spec['file'] not in manifest.get('cell_outcomes',{}):
            data=json.loads((OUT/spec['file']).read_text())
            if digest(OUT/spec['file']) != manifest['completed_runs'][spec['file']]:
                raise ValueError('Completed result hash changed while materializing outcome')
            validate(data,spec,read_instance(ROOT/spec['instance']),manifest['indicator_bounds'][spec['instance']])
            persist_outcome(spec,completed_outcome(spec,data),manifest,path)
    if manifest['status'] not in ('running','searches_complete'):
        raise ValueError(f"Campaign status is not resumable: {manifest['status']}")
    started = time.monotonic()
    session = dict(started_utc=utc(), runs_executed=0, initialization_failures=0, outcomes_materialized=0)
    manifest['sessions'].append(session)
    current = None
    try:
        for spec in specs:
            current = spec
            output = OUT / spec['file']
            if spec['file'] not in manifest.get('cell_outcomes',{}) and outcome_path(spec).exists():
                # Recover an atomically published outcome whose manifest update was interrupted.
                orphan=json.loads(outcome_path(spec).read_text())
                validate_outcome(orphan,spec,manifest)
                if orphan['status']=='completed':
                    if spec['file'] not in manifest['completed_runs']:
                        raise ValueError('Orphan completed outcome has no completed run index')
                persist_outcome(spec,orphan,manifest,path)
            if spec['file'] in manifest.get('cell_outcomes',{}):
                entry=manifest['cell_outcomes'][spec['file']]
                outcome_file=OUT/entry['outcome_file']
                if not outcome_file.is_file() or digest(outcome_file)!=entry['outcome_file_sha256']:
                    raise ValueError('Indexed outcome is missing/corrupt')
                outcome=json.loads(outcome_file.read_text())
                if validate_outcome(outcome,spec,manifest)!=entry['status']:
                    raise ValueError('Indexed outcome status mismatch')
                if entry['status']=='completed':
                    if spec['file'] not in manifest['completed_runs']:
                        raise ValueError('Completed outcome missing completed run index')
                    data=json.loads(output.read_text())
                    instance=read_instance(ROOT/spec['instance'])
                    validate(data,spec,instance,manifest['indicator_bounds'][spec['instance']])
                continue
            if not output.exists() and spec['file'] in manifest['completed_runs']:
                raise ValueError('Indexed completed artifact is missing')
            instance = read_instance(ROOT / spec['instance'])
            bounds = manifest['indicator_bounds'][spec['instance']]
            if calculate_bounds(instance) != bounds:
                raise ValueError('Recomputed deterministic bounds mismatch')
            if output.exists():
                payload = json.loads(output.read_text())
                violations = validate(payload, spec, instance, bounds)
                old_hash = manifest['completed_runs'].get(spec['file'])
                if old_hash and old_hash != digest(output):
                    raise ValueError('Completed artifact file hash changed')
            else:
                begin = utc()
                run_started = time.monotonic()
                try:
                    payload = execute(spec, instance)
                except Exception as error:
                    elapsed = time.monotonic()-run_started
                    known_initialization = (spec['algorithm']=='vns_vnd' and isinstance(error,RuntimeError)
                        and str(error)=='Inicialização aleatória não encontrou schedule completo')
                    if known_initialization:
                        outcome=initialization_failure_outcome(spec,initialization_attempts=max(20,FROZEN['vns_vnd']['initial_solutions']*50),
                            elapsed_seconds=elapsed,failure_reason=str(error),source_sha256=sources,occurred_utc=utc(),
                            provenance='current official invocation; known VNS initializer failure; no evaluator call')
                        # Search evaluator is never reached in this exact failure branch.
                        persist_outcome(spec,outcome,manifest,path)
                        session['initialization_failures'] += 1
                        print(f"[{len(manifest['cell_outcomes'])}/{len(specs)}] {spec['file']} status=initialization_failed init_attempts={outcome['initialization_attempts']} search_attempts=0 t={elapsed:.2f}s",flush=True)
                        continue
                    outcome=dict(status='execution_failed',experiment_spec=spec,algorithm=spec['algorithm'],
                        instance=spec['instance'],instance_sha256=spec['instance_sha256'],seed=spec['seed'],
                        frozen_parameters=configuration(spec).as_dict(),planned_max_evaluations=spec['budget'],
                        initialization_success=None,run_completed=False,failure_stage='execution',failure_reason=str(error),
                        initialization_attempts=None,search_attempts=None,feasible_evaluations=None,rejected_evaluations=None,
                        post_search_validations=None,elapsed_seconds=elapsed,occurred_utc=utc(),source_sha256=sources,
                        algorithm_source_sha256=sources[f"src/metaheuristics/{spec['algorithm']}.py"],quality_metrics=None)
                    outcome['provenance']='unexpected technical exception; cell stopped for investigation'
                    persist_outcome(spec,outcome,manifest,path)
                    session['execution_failures']=session.get('execution_failures',0)+1
                    manifest.update(status='blocked_error',error=dict(type=type(error).__name__,message=str(error),run=spec,detected_utc=utc()))
                    break
                payload['started_utc'] = begin
                payload['finished_utc'] = utc()
                payload['artifact_sha256'] = seal(payload)
                # Validate exact objectives/accounting before publication; reference failure
                # preserves a valid completed run, never excludes it for poor performance.
                violations = validate(payload, spec, instance, bounds)
                if output.exists():
                    raise FileExistsError(output)
                atomic_json(output, payload)
                session['runs_executed'] += 1
            manifest['completed_runs'][spec['file']] = digest(output)
            outcome=completed_outcome(spec,payload)
            persist_outcome(spec,outcome,manifest,path)
            if violations:
                manifest.update(status='blocked_methodology', incompatibility=dict(
                    reason='Valid final point outside the frozen HV reference point',
                    run=spec, reference_point=[1.05, 1.05], points=violations,
                    detected_utc=utc()))
            atomic_json(path, manifest)
            print(f"[{len(manifest['completed_runs'])}/{len(specs)}] {spec['file']} "
                  f"attempts={payload['attempts']} front={payload['points']} "
                  f"seconds={payload['elapsed_seconds']:.3f}", flush=True)
            if violations:
                print('STOP: HV reference incompatibility. No more searches or baseline reads.', flush=True)
                break
        if len(manifest.get('cell_outcomes',{})) == len(specs) and manifest['status'] == 'running':
            manifest.update(status='searches_complete', searches_finished_utc=utc())
        elif manifest['status']=='blocked_error':
            raise RuntimeError('Campaign paused after recording an unexpected execution_failed outcome')
    except Exception as error:
        if manifest.get('status') != 'blocked_error':
            manifest.update(status='blocked_error', error=dict(type=type(error).__name__,
                             message=str(error), run=current, detected_utc=utc()))
        raise
    finally:
        session.update(finished_utc=utc(), elapsed_seconds=time.monotonic()-started)
        manifest['completed_count'] = len(manifest['completed_runs'])
        manifest['outcome_count'] = len(manifest.get('cell_outcomes',{}))
        manifest['initialization_failed_count'] = sum(v['status']=='initialization_failed' for v in manifest.get('cell_outcomes',{}).values())
        manifest['execution_failed_count'] = sum(v['status']=='execution_failed' for v in manifest.get('cell_outcomes',{}).values())
        manifest['completed_attempts'] = sum(s['budget'] for s in specs if s['file'] in manifest['completed_runs'])
        manifest['global_elapsed_seconds'] = sum(s['elapsed_seconds'] for s in manifest['sessions'])
        manifest['wall_span_seconds'] = (datetime.now(timezone.utc)-datetime.fromisoformat(manifest['started_utc'])).total_seconds()
        atomic_json(path, manifest)


if __name__ == '__main__':
    main()
