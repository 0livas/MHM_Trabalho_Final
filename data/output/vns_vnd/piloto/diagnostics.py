"""Attribute reference-run evaluations to neighborhoods without modifying VNS."""
from collections import Counter
import json
from pathlib import Path
import sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'src/metaheuristics')]
from problem import read_instance
from vns_vnd import VNSConfig,VNSVND
manifest=json.loads((OUT/'manifest.json').read_text())
rows=[]
for path in manifest['instances']:
    instance=read_instance(ROOT/'data/input'/path)
    result=VNSVND(instance,VNSConfig(11,2000,4,100,20)).run()
    phase='initial'; family='initial'; counter=Counter()
    for event in result.trace:
        if event['event']=='shake_neighborhood':phase='shake';family=event['name']
        elif event['event']=='vnd_neighborhood':phase='vnd';family=event['name']
        elif event['event'] in ('evaluation','rejected'):
            counter[phase,family,'evaluations']+=1
            counter[phase,family,'rejected']+=event['event']=='rejected'
    for phase,family in sorted(set((p,f) for p,f,_ in counter)):
        count=counter[phase,family,'evaluations'];rejected=counter[phase,family,'rejected']
        rows.append(dict(n=instance.n,seed=11,phase=phase,neighborhood=family,
                         evaluations=count,rejected=rejected,rejection_rate=rejected/count))
(OUT/'neighborhood_diagnostics.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
