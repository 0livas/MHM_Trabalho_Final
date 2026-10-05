"""Reproduce the bounded VNS pilot; never supplies baselines to the solver."""
from pathlib import Path
import cProfile
import csv
from fractions import Fraction
import hashlib
import io
import json
import platform
import pstats
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'src/metaheuristics')]
from problem import read_instance, dominates, insert_pareto
from schedule import evaluate_schedule
from vns_vnd import VNSConfig, VNSVND

OUT = Path(__file__).resolve().parent
SEEDS = (11, 29, 47)
INSTANCES = (
    'set1/6_2_1439_3_S_1-9.dat',
    'set1/14_2_1439_3_S_1-9_derivada.dat',
    'set2/50_10_1439_5_S_1-9.dat',
    'set2/250_10_1439_5_S_1-9.dat',
)
CONFIGS = {
    'reference': (4, 100, 20, 2000),
    'initial_1': (1, 100, 20, 2000),
    'initial_12': (12, 100, 20, 2000),
    'candidates_25': (4, 25, 20, 2000),
    'candidates_250': (4, 250, 20, 2000),
    'shake_1': (4, 100, 1, 2000),
    'shake_50': (4, 100, 50, 2000),
    'budget_500': (4, 100, 20, 500),
    'budget_8000': (4, 100, 20, 8000),
}

def metric(instance, name, result):
    for sol in result.front:
        assert evaluate_schedule(instance, sol.schedule).objective_key == sol.key
    keys = [s.key for s in result.front]
    assert len(set(keys)) == len(keys)
    assert not any(dominates(a,b) for a in keys for b in keys)
    config = result.config
    row = dict(instance=instance.path.name, instance_sha256=instance.digest,
               n=instance.n, m=instance.m, configuration=name, seed=config.seed,
               initial_solutions=config.initial_solutions,
               neighborhood_candidate_limit=config.max_candidates_per_neighborhood,
               shaking_attempts=config.shaking_attempts, max_evaluations=config.max_evaluations,
               evaluations=result.evaluations, feasible=result.feasible_evaluations,
               rejected=result.rejected_evaluations,
               rejection_rate=result.rejected_evaluations/result.evaluations,
               seconds=result.elapsed_seconds, evaluations_per_second=result.evaluations/result.elapsed_seconds,
               milliseconds_per_evaluation=result.elapsed_seconds*1000/result.evaluations,
               front_size=len(keys), cmax_min=min(k[0] for k in keys), cmax_max=max(k[0] for k in keys),
               tec_min=float(min(s.evaluation.tec_exact for s in result.front)),
               tec_max=float(max(s.evaluation.tec_exact for s in result.front)),
               stop_reason=result.stop_reason)
    events=Counter(e['event'] for e in result.trace)
    row.update(shake_success=events['shake_success'], shake_failed=events['shake_failed'],
               vnd_accept=events['vnd_accept'], archive_insertions=sum(e.get('archive_inserted',False) for e in result.trace))
    # Baseline is loaded ONLY after run() completed, solely for diagnostics.
    baseline_path=ROOT/'data/baselines'/f'{instance.path.stem}_custom_exact_dp.json'
    if baseline_path.exists():
        baseline=json.loads(baseline_path.read_text(encoding='utf-8-sig'))
        assert baseline['instance_sha256']==instance.digest
        assert baseline['status']=='complete' and baseline['pareto_proven']
        exact=[(p['makespan'],Fraction(p['tec_exact']['numerator'],p['tec_exact']['denominator'])) for p in baseline['front']]
        approx=[(s.evaluation.cmax,s.evaluation.tec_exact) for s in result.front]
        equals=sum(p in exact for p in approx)
        conflicts=sum(any(dominates(p,e) for e in exact) for p in approx)
        row.update(baseline_points=len(exact), baseline_equal=equals,
                   baseline_strictly_dominated=sum(any(dominates(e,p) for e in exact) for p in approx),
                   baseline_coverage=equals/len(exact), intersection_fraction=equals/len(approx),
                   baseline_conflicts=conflicts)
        assert conflicts==0, 'Approximate point dominates a proven baseline'
    return row

def main():
    (OUT/'runs').mkdir(exist_ok=True)
    if (OUT/'metrics.csv').exists():
        raise SystemExit('Pilot already exists; use a separate directory rather than silently overwriting.')
    manifest=dict(python=sys.version, platform=platform.platform(), seeds=SEEDS,
                  instances=INSTANCES, configurations=CONFIGS,
                  source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                      ('src/metaheuristics/vns_vnd.py','src/schedule.py','src/problem.py')},
                  timing='Sequential execution; elapsed_seconds covers run() only; input reading, final validation and JSON writing excluded.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    rows=[]
    for path in INSTANCES:
        instance=read_instance(ROOT/'data/input'/path)
        for name,(initial,candidates,shaking,budget) in CONFIGS.items():
            for seed in SEEDS:
                result=VNSVND(instance,VNSConfig(seed,budget,initial,candidates,shaking)).run()
                row=metric(instance,name,result); rows.append(row)
                file=OUT/'runs'/f'{instance.path.stem}_{name}_seed{seed}.json'
                file.write_text(json.dumps(result.to_result_dict(),indent=2)+'\n')
                (OUT/'metrics.json').write_text(json.dumps(rows,indent=2)+'\n')
                print(f'{instance.n:3} {name:15} seed={seed} t={result.elapsed_seconds:.3f} front={len(result.front)} reject={row["rejection_rate"]:.1%}',flush=True)
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with (OUT/'metrics.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    profiles=[]
    for path in INSTANCES:
        instance=read_instance(ROOT/'data/input'/path)
        profile=cProfile.Profile(); profile.enable()
        result=VNSVND(instance,VNSConfig(11,1000,4,100,20)).run()
        profile.disable()
        stream=io.StringIO();stats=pstats.Stats(profile,stream=stream).sort_stats('cumulative');stats.print_stats(35)
        (OUT/f'profile_{instance.n}.txt').write_text(stream.getvalue())
        for (file,line,function),(primitive,calls,exclusive,cumulative,callers) in stats.stats.items():
            if file.endswith(('vns_vnd.py','schedule.py','problem.py')):
                profiles.append(dict(n=instance.n,file=Path(file).name,line=line,function=function,
                                     calls=calls,exclusive_seconds=exclusive,cumulative_seconds=cumulative,
                                     profiled_total_seconds=stats.total_tt))
    (OUT/'profiles.json').write_text(json.dumps(profiles,indent=2)+'\n')

if __name__=='__main__': main()
