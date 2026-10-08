"""Compute instance-only bounds first, then independently validate pilot schedules."""
from collections import defaultdict
from fractions import Fraction
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT/'src'))
from problem import read_instance, energy_scale, interval_cost_units, atomic_json
from schedule import evaluate_schedule
from normalization import calculate_bounds, energy_extrema, normalize, normalize_exact, METHOD
from run_final import digest, utc


def main():
    manifest = json.loads((OUT/'history/original_protocol/manifest.json').read_text())
    planned = sorted({s['instance'] for s in manifest['execution_order']})
    bounds = {}
    # ALL planned bounds are calculated before any solution artifact is read.
    for path in planned:
        instance = read_instance(ROOT/path)
        bounds[path] = calculate_bounds(instance)
        print('BOUND', path, bounds[path]['C_LB'], bounds[path]['TEC_LB_exact'], bounds[path]['TEC_UB_exact'], flush=True)
    # Auxiliary derived pilot input; excluded from final experiment.
    auxiliary = 'data/input/set1/14_2_1439_3_S_1-9_derivada.dat'
    aux_bounds = calculate_bounds(read_instance(ROOT/auxiliary))
    all_bounds = {**bounds, auxiliary:aux_bounds}
    # Exhaustive independent time enumeration for every distinct duration in each
    # planned instance. Overlap extrema depend on d; nonnegative prices can have
    # either ordering, both of which are checked explicitly.
    exhaustive = {}
    for path in planned:
        instance = read_instance(ROOT/path)
        ds = sorted({instance.duration(j,m,l) for j in range(instance.n)
                     for m in range(instance.m) for l in range(instance.modes)
                     if instance.duration(j,m,l) <= instance.horizon})
        for d in ds:
            for on, off in [(1,0),(0,1)]:
                observed = [interval_cost_units(instance,s,s+d,on,off)
                            for s in range(instance.horizon-d+1)]
                assert energy_extrema(instance,d,on,off)==(min(observed),max(observed))
        exhaustive[path] = dict(durations=len(ds), price_orderings=2, status='exact_equal')
    # Frozen scales above; now validate all published pilot run fronts and existing final run.
    files = []
    for algorithm in ['vns_vnd','spea2','moead']:
        files.extend((algorithm,p) for p in sorted((ROOT/f'data/output/{algorithm}/piloto/runs').glob('*.json')))
    files.extend(('preserved_final',OUT/s) for s in manifest['completed_runs'])
    grouped = defaultdict(lambda:dict(runs=0,schedules=0,low=[1.,1.],high=[0.,0.]))
    hashes = {}
    for algorithm, path in files:
        data = json.loads(path.read_text())
        name = data['instance']
        instance_path = next(p for p in all_bounds if Path(p).name==name)
        # Reuse instance only across consecutive runs of same input.
        if 'instance' not in locals() or str(instance.path.relative_to(ROOT)) != instance_path:
            instance = read_instance(ROOT/instance_path)
        assert data['instance_sha256']==instance.digest
        b = all_bounds[instance_path]
        row = grouped[(algorithm,instance_path)]
        row['runs'] += 1
        hashes[str(path.relative_to(ROOT))]=digest(path)
        for item in data['front']:
            ev = evaluate_schedule(instance,item['representation'])
            assert ev.cmax==item['makespan']
            assert ev.tec_exact==Fraction(item['tec_exact']['numerator'],item['tec_exact']['denominator'])
            assert ev.tec_scale==b['tec_scale']
            point=normalize(ev.cmax,ev.tec_units,b)
            row['schedules']+=1
            row['low']=[min(a,v) for a,v in zip(row['low'],point)]
            row['high']=[max(a,v) for a,v in zip(row['high'],point)]
    results=[dict(algorithm=a,instance=p,**v) for (a,p),v in sorted(grouped.items())]
    # Report numerical resolution conservatively, solely from bounds. No scales
    # selected from the observed fronts. Theoretical integer step vs float ULP.
    import math
    resolution = {p:dict(cmax_one_unit=1/(b['C_UB']-b['C_LB']),
        tec_one_unit=1/(b['TEC_UB_units']-b['TEC_LB_units']),
        tec_steps_per_ulp_at_one=(1/(b['TEC_UB_units']-b['TEC_LB_units']))/math.ulp(1.0))
        for p,b in bounds.items()}
    assert all(v['tec_steps_per_ulp_at_one'] > 100 for v in resolution.values())
    output=dict(status='passed',method=METHOD,computed_before_reading_solutions=True,
        completed_utc=utc(),bounds=bounds,auxiliary_pilot_bounds={auxiliary:aux_bounds},
        exhaustive_time_enumeration=exhaustive,validation=results,
        artifact_sha256=hashes,reference_point=[1.05,1.05],
        float_resolution=resolution,baseline_reads=0)
    atomic_json(OUT/'normalization_validation.json',output)
    report=['# Validação da normalização externa — emenda 1','',
        'Bounds calculados para todas as entradas antes de abrir qualquer schedule. Nenhum baseline lido. '
        'Escala interna dos algoritmos permanece inalterada; MOEA/D continua Cmax/H e TEC/max_cost.','',
        '## Fórmula e prova','',
        'dmin_j = min_{máquina,modo: d≤H} ceil(processing/speed). '
        'C_LB = max(max_j dmin_j, ceil(sum_j dmin_j/m)); C_UB = H. '
        'Qualquer job leva pelo menos dmin_j. Como jobs não sobrepõem por máquina e os setups/esperas '
        'são não negativos, sum_j dmin_j ≤ m*Cmax. A restrição do evaluator assegura Cmax≤H.','',
        'TEC_LB_units = sum_j min_{máquina,modo,start inteiro; 0≤start≤H-d} cost_units(j,m,l,start). '
        'TEC_UB_units = sum_j max das mesmas opções. Todo processamento de qualquer schedule viável '
        'é uma dessas opções. Seu custo individual está entre seus extremos; somar preserva ambas '
        'as desigualdades. A relaxação ignora coexistência, setups e precedências, mas não altera '
        'a fórmula energética nem a discretização. Setup/espera não cobram energia.','',
        'cost_units = peak_slots*on_price + (d-peak_slots)*off_price, usando energy_scale e '
        'interval_cost_units autoritativos. A função do start é contínua linear por trechos, com '
        'breakpoints inteiros a-d,b-d,a,b de cada pico [a,b). Os extremos ocorrem nesses breakpoints '
        'ou 0/H-d. A enumeração de todos os horários para cada duração distinta e ambas as '
        'ordenações de preços confirmou exatamente esses extremos em todas as entradas planejadas.','',
        'C_norm = (Cmax-C_LB)/(H-C_LB). TEC_norm = (tec_units-TEC_LB_units)/(TEC_UB_units-TEC_LB_units). '
        'Frações exatas até a conversão final. Denominadores positivos em todas as 17 entradas. '
        'HV e IGD+ usam o mesmo espaço. Dominância/deduplicação/coverage seguem Cmax inteiro e '
        'tec_units exato. max_cost continua parte da instância e da escala interna do MOEA/D.','',
        '## Bounds por instância','',
        '| Entrada | C_LB | C_UB | TEC_LB exato | TEC_UB exato | Escala TEC |',
        '|---|---:|---:|---|---|---:|']
    for p,b in bounds.items():
        report.append(f"| {Path(p).name} | {b['C_LB']} | {b['C_UB']} | {b['TEC_LB_exact']} | {b['TEC_UB_exact']} | {b['tec_scale']} |")
    report+=['','## Validação de schedules','',
             '| Origem | Entrada | Runs | Schedules | C_norm min–max | TEC_norm min–max |',
             '|---|---|---:|---:|---|---|']
    for r in results:
        report.append(f"| {r['algorithm']} | {Path(r['instance']).name} | {r['runs']} | {r['schedules']} | "
            f"{r['low'][0]:.9f}–{r['high'][0]:.9f} | {r['low'][1]:.9f}–{r['high'][1]:.9f} |")
    report+=['','Todos os schedules reavaliados estão em [0,1]². Portanto (1.05,1.05) é '
        'estritamente pior nas duas coordenadas, inclusive quando uma coordenada vale 1. '
        'Assertions verificam frações exatas, finitude, [0,1] e dominância estrita do reference point '
        'antes de cada cálculo geométrico.','', '## Aperto e precisão','',
        'Os extremos individuais podem não coexistir, portanto os bounds são relaxações e não ótimos '
        'globais. Um limite superior obtido somando escolhas caras pode ser frouxo, sobretudo em '
        'máquinas heterogêneas; isso comprime distâncias geométricas. Não se escolheu ou ajustou '
        'nenhum bound pelos resultados. A validade vale para qualquer solução viável. A validação '
        'dos pilotos é um diagnóstico de precisão, não tuning de escala. O menor passo inteiro '
        'normalizado de energia excede 100 ULPs de float em 1 em todas as entradas, preservando '
        'resolução suficiente antes das operações geométricas. Valores por entrada no JSON. '
        'Frentes observadas com spans estreitos podem representar diversidade limitada; não '
        'há colapso numérico devido à conversão.','',
        '## Emenda ao protocolo','',
        'Original: HV/IGD+ em Cmax/H e TEC/max_cost, reference (1.05,1.05). A primeira run revelou '
        'max_cost não ser upper bound de TEC; interrupção imediata após uma run, zero baselines '
        'lidos e zero métricas comparativas calculadas. Só a normalização externa é emendada, '
        'antes de retomar as outras 464 runs. Algoritmos, parâmetros, seeds, budgets e ordem '
        'não mudam. A primeira run será preservada byte a byte e não repetida. O histórico '
        'original permanece em history/original_protocol/.']
    (OUT/'normalization_validation.md').write_text('\n'.join(report)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
