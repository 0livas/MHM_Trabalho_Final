"""Aggregate the completed pilot and paired exact-objective front coverage."""
import csv
from collections import defaultdict
from fractions import Fraction
import json
from pathlib import Path
import statistics as s
import sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'src'))
from problem import dominates_or_equals

rows=json.loads((OUT/'metrics.json').read_text())
groups=defaultdict(list)
for row in rows:
    path=OUT/'runs'/f"{Path(row['instance']).stem}_{row['configuration']}_seed{row['seed']}.json"
    points=json.loads(path.read_text())['front']
    assignments=set();sequences=set();modes=set()
    for point in points:
        representation=point['representation']
        assignments.add(tuple(sorted((job,machine) for machine,seq in enumerate(representation) for job,mode,wait in seq)))
        sequences.add(tuple(tuple(item[0] for item in seq) for seq in representation))
        modes.add(tuple(sorted((job,mode) for seq in representation for job,mode,wait in seq)))
    row.update(distinct_assignments=len(assignments),distinct_sequences=len(sequences),distinct_mode_vectors=len(modes))
    groups[row['n'],row['configuration']].append(row)
with (OUT/'diversity.csv').open('w',newline='') as f:
    keys=['n','configuration','seed','front_size','distinct_assignments','distinct_sequences','distinct_mode_vectors','cmax_min','cmax_max','tec_min','tec_max']
    w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)
summary=[]
for (n,configuration),runs in groups.items():
    row=dict(n=n,configuration=configuration,runs=len(runs))
    for key in ['seconds','milliseconds_per_evaluation','evaluations_per_second','front_size','cmax_min','tec_min','rejection_rate','shake_success','shake_failed','vnd_accept','distinct_assignments','distinct_sequences','distinct_mode_vectors','cmax_max','tec_max']:
        vals=[r[key] for r in runs]
        row[key+'_median']=s.median(vals);row[key+'_min']=min(vals);row[key+'_max']=max(vals)
    summary.append(row)
with (OUT/'summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
paired=[]
for row in rows:
    if row['configuration']=='reference':continue
    def front(name):
        path=OUT/'runs'/f"{Path(row['instance']).stem}_{name}_seed{row['seed']}.json"
        return [(p['makespan'],Fraction(p['tec_exact']['numerator'],p['tec_exact']['denominator']))
                for p in json.loads(path.read_text())['front']]
    reference,variant=front('reference'),front(row['configuration'])
    paired.append(dict(n=row['n'],configuration=row['configuration'],seed=row['seed'],
                       variant_covers_reference=sum(any(dominates_or_equals(a,b) for a in variant) for b in reference)/len(reference),
                       reference_covers_variant=sum(any(dominates_or_equals(a,b) for a in reference) for b in variant)/len(variant)))
with (OUT/'paired_coverage.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for row in summary:
    print(f"{row['n']:3} {row['configuration']:15} t={row['seconds_median']:.3f} ms/eval={row['milliseconds_per_evaluation_median']:.3f} front={row['front_size_median']:g}[{row['front_size_min']},{row['front_size_max']}] C={row['cmax_min_median']:g} TEC={row['tec_min_median']:.3f} rej={row['rejection_rate_median']:.1%}")
