"""Post-search exact validation, geometric metrics and instance-block statistics.

References are read only after every planned search is complete. --publish
explicitly archives existing analysis outputs before publishing replacements.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from fractions import Fraction
import csv
import json
import os
from pathlib import Path
import shutil
import time

os.environ.setdefault('MPLCONFIGDIR','/tmp/mhm-final-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy import stats
from pymoo.indicators.hv import HV
from pymoo.indicators.igd_plus import IGDPlus

from run_final import OUT, ROOT, SOURCES, digest, utc, validate
from normalization import calculate_bounds, normalize, normalize_exact, REFERENCE
from problem import atomic_json, read_instance, dominates, energy_scale
from schedule import evaluate_schedule, schedule_from_result_rows

ALGORITHMS = ['vns_vnd','spea2','moead']
COLORS = ['#b25b28','#2469a5','#2b855a']


def diversity(front):
    a,o,m,w=set(),set(),set(),set()
    for row in front:
        rep=row['representation']
        a.add(tuple(tuple(sorted(j for j,_,_ in seq)) for seq in rep))
        o.add(tuple(tuple(j for j,_,_ in seq) for seq in rep))
        m.add(tuple(sorted((j,mode) for seq in rep for j,mode,_ in seq)))
        w.add(tuple(sorted((j,wait) for seq in rep for j,_,wait in seq)))
    return dict(allocations=len(a),orders=len(o),modes=len(m),waits=len(w))


def key(row):
    return int(row['makespan']), int(row['tec_exact']['numerator'])


def pareto(rows):
    # Exact minimization; equal objectives deduplicated before any float conversion.
    unique={key(r):r for r in rows}
    front=[]
    best=None
    for k in sorted(unique):
        if best is None or k[1]<best:
            front.append(unique[k]);best=k[1]
    return front


def coverage(a,b):
    if not b: raise ValueError('Coverage target is empty')
    return sum(any(x[0]<=y[0] and x[1]<=y[1] for x in a) for y in b)/len(b)


def points(front,bounds):
    # normalize includes explicit assertions for finite, <=1, and reference dominance.
    return np.asarray([normalize(*key(r),bounds) for r in front],dtype=float)


def hv(front,bounds):
    p=points(front,bounds)
    assert np.all(np.isfinite(p)) and np.all((p>=0)&(p<=1))
    assert np.all(p<np.asarray(REFERENCE))
    return float(HV(ref_point=np.asarray(REFERENCE))(p))


def export_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    if not fields: fields=['status']
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)


def check_front(instance,front):
    evaluated=[]
    for row in front:
        schedule=row.get('representation')
        if schedule is None:
            schedule=schedule_from_result_rows(instance,row['schedule'])
        ev=evaluate_schedule(instance,schedule)
        exact=Fraction(row['tec_exact']['numerator'],row['tec_exact']['denominator'])
        if ev.cmax!=row['makespan'] or ev.tec_exact!=exact:
            raise ValueError('Reference exact objective mismatch')
        payload=ev.to_result_dict(instance)
        payload['representation']=schedule
        evaluated.append(payload)
    if len({key(r) for r in evaluated})!=len(evaluated):
        raise ValueError('Reference objectives duplicated')
    if len(pareto(evaluated))!=len(evaluated):
        raise ValueError('Reference is not nondominated')
    return evaluated


def reference_fronts(manifest,unions,staging):
    # Called only after all runs have been revalidated. No baseline reader in runner.
    assert manifest['status']=='searches_complete'
    assert len(manifest['cell_outcomes'])==manifest['expected_runs']
    exact={}; reads=[]
    planned=set(p for _,p in unions)
    # Discover canonical baselines now, not during a search.
    for path in sorted((ROOT/'data/baselines').glob('*.json')):
        data=json.loads(path.read_text())
        reads.append(dict(path=str(path.relative_to(ROOT)),sha256=digest(path),read_utc=utc()))
        if data.get('status')!='complete' or data.get('pareto_proven') is not True:
            continue
        baseline_instance=Path(str(data['instance']).replace('\\','/')).name
        matching=[p for p in planned if Path(p).name==baseline_instance]
        if not matching: continue
        p=matching[0];instance=read_instance(ROOT/p)
        if data['instance_sha256']!=instance.digest: raise ValueError('Baseline input hash mismatch')
        front=check_front(instance,data['front'])
        points(front,manifest['indicator_bounds'][p])
        if p in exact and {key(r) for r in exact[p]['front']}!={key(r) for r in front}:
            raise ValueError('Conflicting complete proven baselines')
        exact[p]=dict(front=front,type='exact',source=str(path.relative_to(ROOT)),sha256=digest(path))
    references={}
    empirical_dir=staging/'empirical_reference_fronts';empirical_dir.mkdir()
    for (experiment,p),rows in sorted(unions.items()):
        if p in exact:
            references[(experiment,p)]=exact[p]
            continue
        instance=read_instance(ROOT/p)
        # Re-evaluate union schedules before exact dedup/Pareto filtering.
        evaluated=[]
        for row in rows:
            ev=evaluate_schedule(instance,row['representation'])
            if ev.objective_key!=key(row): raise ValueError('Union re-evaluation mismatch')
            payload=ev.to_result_dict(instance);payload['representation']=row['representation']
            evaluated.append(payload)
        front=pareto(evaluated)
        name=f'{experiment}__{Path(p).stem}.json'
        payload=dict(type='empirical_not_proven_optimal',experiment=experiment,instance=p,
            instance_sha256=instance.digest,front=front,points=len(front),
            construction='all final fronts, all algorithms/seeds of this experiment; re-evaluate, exact dedup, exact Pareto')
        atomic_json(empirical_dir/name,payload)
        references[(experiment,p)]=dict(front=front,type='empirical',source=f'empirical_reference_fronts/{name}')
    return references,exact,reads


def statistical_tests(summary):
    output=dict(primary_metric='HV',unit='instance',blocks=13,seeds_per_cell=10,
        alpha=0.05,aggregation='median per algorithm/instance over 10 seeds',
        primary_experiment='A',secondary_metric='IGD+',scipy=scipy.__version__,metrics={})
    for metric in ['hv','igd_plus']:
        lookup={(r['instance'],r['algorithm']):r['median'] for r in summary
                if r['experiment']=='A' and r['metric']==metric}
        instances=sorted({p for p,a in lookup})
        if len(instances)!=13: raise ValueError('Incomplete instance blocks')
        arrays=[np.asarray([lookup[(p,a)] for p in instances]) for a in ALGORITHMS]
        if np.all(np.asarray(arrays)==arrays[0]):
            statistic,pvalue=0.,1.
        else:
            test=stats.friedmanchisquare(*arrays);statistic,pvalue=float(test.statistic),float(test.pvalue)
        result=dict(friedman=dict(statistic=statistic,p_value=pvalue,
            kendall_W=statistic/(len(instances)*(len(ALGORITHMS)-1)),
            method='asymptotic chi-square; 13 instance blocks, 3 algorithms; interpret cautiously'),pairwise=[])
        if pvalue<0.05:
            for i in range(3):
                for j in range(i+1,3):
                    difference=arrays[i]-arrays[j]
                    nonzero=difference[difference!=0]
                    if not len(nonzero): stat,p=0.,1.;effect=0.
                    else:
                        test=stats.wilcoxon(arrays[i],arrays[j],zero_method='wilcox',alternative='two-sided',method='auto')
                        stat,p=float(test.statistic),float(test.pvalue)
                        ranks=stats.rankdata(np.abs(nonzero),method='average')
                        effect=float((ranks[nonzero>0].sum()-ranks[nonzero<0].sum())/ranks.sum())
                    result['pairwise'].append(dict(a=ALGORITHMS[i],b=ALGORITHMS[j],
                        statistic=stat,p_value=p,rank_biserial=effect,nonzero_blocks=len(nonzero),
                        median_paired_difference=float(np.median(difference)),
                        effect_sign='positive: metric a > b; HV higher is better, IGD+ lower is better'))
            ordered=sorted(result['pairwise'],key=lambda r:r['p_value']);previous=0.
            for index,row in enumerate(ordered):
                adjusted=max(previous,min(1.,row['p_value']*(len(ordered)-index)))
                row.update(p_holm=adjusted,significant_holm=adjusted<0.05);previous=adjusted
        output['metrics'][metric]=result
    return output


def figures(metrics,summary,run_fronts,references,staging):
    directory=staging/'figures';directory.mkdir()
    instances=sorted({r['instance'] for r in metrics if r['experiment']=='A'},key=lambda p:(int(Path(p).name.split('_')[0]),p))
    labels=[Path(p).stem.replace('_1439_','_') for p in instances]
    fig,ax=plt.subplots(figsize=(9,4))
    arrays=[[r['median'] for r in summary if r['experiment']=='A' and r['metric']=='hv' and r['algorithm']==a] for a in ALGORITHMS]
    ax.boxplot(arrays,tick_labels=ALGORITHMS,showmeans=True)
    ax.set(ylabel='HV (mediana de 10 seeds por instância)',title='Experimento A — 13 blocos de instâncias; 8.000 tentativas')
    ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(directory/'hv_A.png',dpi=160);plt.close(fig)
    lookup={(r['instance'],r['algorithm']):r['median'] for r in summary if r['experiment']=='A' and r['metric']=='hv'}
    matrix=np.asarray([[lookup[(p,a)] for a in ALGORITHMS] for p in instances])
    fig,ax=plt.subplots(figsize=(7,7));im=ax.imshow(matrix,aspect='auto',cmap='viridis')
    ax.set_xticks(range(3),ALGORITHMS);ax.set_yticks(range(len(instances)),labels)
    for i,vals in enumerate(matrix):
        ranks=stats.rankdata(-vals)
        for j,v in enumerate(vals):ax.text(j,i,f'{v:.4f} (#{ranks[j]:g})',ha='center',va='center',color='white' if v<.6 else 'black')
    ax.set_title('Experimento A — HV mediano e rank por instância');fig.colorbar(im,ax=ax,label='HV')
    fig.tight_layout();fig.savefig(directory/'hv_instance_ranking.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4))
    for a,color in zip(ALGORITHMS,COLORS):
        for experiment,marker in [('A','o'),('B','^')]:
            rows=[r for r in metrics if r['algorithm']==a and r['experiment']==experiment]
            for n in sorted({r['n'] for r in rows}):
                values=[r['elapsed_seconds'] for r in rows if r['n']==n]
                ax.scatter([n]*len(values),values,color=color,marker=marker,s=13,alpha=.3)
                ax.scatter(n,np.median(values),color=color,marker=marker,s=70,
                    label=f'{a}: {experiment}, '+('8k' if experiment=='A' else '2k') if n==min(r['n'] for r in rows) else None)
    ax.set(xscale='log',yscale='log',xlabel='jobs (tarifas, máquinas e horizontes também variam)',ylabel='tempo de busca (s)',title='Runtime local — A e B com budgets distintos')
    ax.legend(fontsize=8);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(directory/'runtime_by_size.png',dpi=160);plt.close(fig)
    selected=[('A','data/input/set1/6_2_1439_3_S_1-9.dat'),
              ('A','data/input/set2/50_10_1439_5_S_1-9.dat'),
              ('A','data/input/set2/250_10_1439_5_S_1-9.dat'),
              ('B','data/input/set2/750_10_1439_5_S_1-9.dat')]
    for experiment,p in selected:
        fig,ax=plt.subplots(figsize=(7,4))
        for a,color in zip(ALGORITHMS,COLORS):
            union=pareto([r for (e,path,algo,seed),rows in run_fronts.items()
                          if e==experiment and path==p and algo==a for r in rows])
            # Exact filtered union of completed seeds only; failures have no Pareto point.
            xs=[r['makespan'] for r in union];ys=[float(Fraction(r['tec_exact']['numerator'],r['tec_exact']['denominator'])) for r in union]
            planned=10 if experiment=='A' else 5
            completed=sum(1 for (e,path,algo,seed) in run_fronts if e==experiment and path==p and algo==a)
            label=(f'{a}: união Pareto de {completed}/{planned} seeds concluídas' if completed
                   else f'{a}: N/A, 0/{planned} inicializadas')
            if union:
                ax.plot(xs,ys,'.-',label=label,color=color)
            else:
                ax.plot([],[],label=label,color=color)
        reference=references[(experiment,p)];front=reference['front']
        ax.plot([r['makespan'] for r in front],[float(Fraction(r['tec_exact']['numerator'],r['tec_exact']['denominator'])) for r in front],
            'k--',alpha=.6,label='frente exata' if reference['type']=='exact' else 'empirical reference front (não ótima)')
        ax.set(xlabel='Cmax inteiro',ylabel='TEC',title=f'{experiment}: {Path(p).stem}\nUniões das seeds, filtradas por Pareto exato')
        ax.legend(fontsize=8);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(directory/f'pareto_{experiment}_{Path(p).stem}.png',dpi=160);plt.close(fig)


def report(manifest,metrics,summary,tests,exact_metrics,staging,outcomes,execution_summary):
    lookup={(r['experiment'],r['instance'],r['algorithm'],r['metric']):r for r in summary}
    def med(e,p,a,k):return lookup[(e,p,a,k)]['median']
    text=['# Comparação final VNS/VND, SPEA2 e MOEA/D','',
        'Campanha sequencial com parâmetros congelados no checkpoint 40bf609. '
        'Os resultados separam qualidade multiobjetivo, robustez, custo e escala; não se escolhe '
        'vencedor pelo tamanho da frente, um extremo ou uma única instância.','',
        '## Inventário e protocolo','',
        '22 entradas: 17 originais e 5 derivadas (_derivada). A usa 13 originais de até 250 jobs '
        '× 3 algoritmos × 10 seeds × 8.000 tentativas = 390 runs e 3.120.000 tentativas. '
        'B usa as 4 originais de 750 jobs × 3 algoritmos × 5 seeds × 2.000 = 60 runs/120.000 tentativas. '
        'C usa 250_10_1439_5_S_1-9 × 3 algoritmos × 5 seeds × 20.000 = 15 runs/300.000 tentativas. '
        f"Plano total: 465 células; ao fim {sum(r['status']=='completed' for r in outcomes)} buscas concluídas e "
        f"{sum(r['status']=='initialization_failed' for r in outcomes)} falhas de inicialização, com "
        f"{sum(r['search_attempts'] or 0 for r in outcomes):,} tentativas completas ao evaluator. "
        'B/C não entram na inferência global de A.','',
        '| Entrada | Jobs | Máquinas | Classe |', '|---|---:|---:|---|']
    for r in manifest['inventory']:text.append(f"| {r['path']} | {r['n']} | {r['m']} | {r['classification']} |")
    text+=['','Seeds A: 101,211,307,401,503,601,701,809,907,1009; B/C: primeiras cinco. '
        'VNS: initial_solutions=4, max_candidates_per_neighborhood=25, shaking_attempts=20. '
        'SPEA2: population_size=50, crossover_probability=.9, mutation_probability=.3, incremental '
        '(n_offsprings=1), normalize=False. MOEA/D: population_size=50 (50 directions), '
        'n_neighbors=20, prob_neighbor_mating=.9, crossover_probability=.9, mutation_probability=.3, '
        'Tchebycheff original. Ordem por bloco gira deterministicamente; lista integral no manifesto.','',
        '## Emendas metodológicas e reprodução','',
        'O protocolo original usava Cmax/H e TEC/max_cost no HV/IGD+. A primeira run (VNS, seed101, '
        '250_10_1439_5_S_1-9, 8k) revelou TEC/max_cost>1.05 e foi interrompida imediatamente. '
        'Nesse momento somente uma run havia terminado; nenhum baseline havia sido lido e nenhuma '
        'métrica comparativa calculada. O histórico original foi preservado. A emenda 1 foi definida '
        'e validada antes da run2; não modificou algoritmos, seeds, operadores, budgets ou ordem. '
        'A primeira run foi preservada byte a byte e não repetida.','',
        'A segunda emenda registra a retomada, a falha oficial VNS/VND em '
        '750_10_1439_5_S_1-9/seed 101 (200 construções, zero chamadas ao evaluator), a causa raiz '
        'confirmada independentemente como limitação do inicializador congelado e a decisão de manter '
        'o checkpoint 40bf609. O outcome foi materializado posteriormente do manifesto e diagnóstico '
        'oficial preservado, sem reexecução ou uso de /tmp. A célula conta como tentativa oficial; '
        'as demais células B seguem uma vez, na ordem congelada. Falhas iguais são outcomes; erros '
        'técnicos inesperados interrompem a campanha.','',
        'A escala EXTERNA dos indicadores usa C=(Cmax-C_LB)/(H-C_LB) e '
        'E=(tec_units-TEC_LB_units)/(TEC_UB_units-TEC_LB_units). C_LB=max(max_j dmin_j, '
        'ceil(sum_j dmin_j/m)). TEC_LB/UB somam os menores/maiores custos individuais entre '
        'todas as opções de máquina/modo/start inteiro no horizonte. A prova, tabela de bounds '
        'e validação de 327 runs piloto estão em [normalization_validation.md](normalization_validation.md). '
        'Todos os bounds são exatos e derivados só da entrada. Assertions garantem [0,1]² e '
        'dominância estrita pelo reference (1.05,1.05) antes de HV. IGD+ usa o mesmo espaço. '
        'max_cost permanece no diagnóstico e na escala INTERNA Cmax/H, TEC/max_cost do MOEA/D.','',
        'Dominância, coverage e deduplicação usam (Cmax inteiro, tec_units exato). '
        'Cada tentativa completa ao evaluator, incluindo inviáveis, conta; as contagens independentes '
        'confirmaram attempts==budget. Validações internas pós-busca e reavaliações independentes '
        'ficam separadas. Todas as frentes/schedules finais foram reavaliadas, confirmando '
        'viabilidade, objetivos exatos, unicidade e não dominância. Referências foram lidas/construídas '
        'somente após os outcomes terminais das 465 células planejadas. Empirical fronts são uniões reavaliadas e filtradas por '
        'Pareto exato de todos os algoritmos/seeds do mesmo experimento, não referências ótimas.','',
        f"Início: {manifest['started_utc']}; fim das buscas: {manifest['searches_finished_utc']}. "
        f"Duração ativa global das sessões: {manifest['global_elapsed_seconds']:.2f} s; "
        f"soma de timers de busca: {sum(r['elapsed_seconds'] for r in metrics):.2f} s. "
        'Timers nativos incluem inicialização e busca, excluem validação final/escrita. '
        'Instrumentação de contagem adiciona overhead não quantificado. Memória não medida '
        '(RSS máximo do processo seria acumulado). Ambiente e hashes de código, entradas, '
        'scripts, bounds e outputs no manifesto; checkpoint conferido com normalização Git de EOL.','',
        'Reprodução: `python data/output/final_comparison/run_final.py`; retomada verifica artefatos '
        'e não repete runs completas. Análise: `python data/output/final_comparison/analyze_final.py '
        '--publish` (arquiva explicitamente resultados anteriores). Caches/logs ficam fora do '
        'repositório. Testes/py_compile/diff registrados em checks_amendment.json e final_checks.json.','',
        '## Qualidade, robustez, extremos e custo por instância','',
        '### Capacidade de inicialização no Experimento B','',
        'Sob o inicializador e protocolo congelados, VNS/VND não conseguiu inicializar determinadas '
        'instâncias/seeds de 750 jobs. Isso não prova inviabilidade geral; nessas células não há '
        'evidência sobre qualidade de busca. A qualidade agregada considera somente runs concluídas.','',
        '| Instância | Algoritmo | Planejadas | Concluídas | Falhas de inicialização | Taxa | N qualidade |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in execution_summary:
        if r['experiment']=='B':
            text.append(f"| {Path(r['instance']).name} | {r['algorithm']} | {r['planned_runs']} | {r['runs_completed']} | {r['initialization_failures']} | {r['completion_rate']:.0%} | {r['quality_metric_denominator']} |")
    text+=['',
        'summary.csv contém mediana, Q1, Q3, min e max por algoritmo/instância para todos os '
        'indicadores (10 seeds em A; 5 em B/C); quartis interpolados linearmente. '
        'metrics.csv e normalized_metrics.csv preservam cada run. Extremos Cmax/TEC são separados.','',
        '| Exp. | Entrada | Algoritmo | HV med. [Q1,Q3] | IGD+ med. | Cmax mín. med. | TEC mín. med. | Frente med. | Tempo s med. | Rejeição med. |',
        '|---|---|---|---|---:|---:|---:|---:|---:|---:|']
    for e,p,a in sorted({(r['experiment'],r['instance'],r['algorithm']) for r in execution_summary}):
        count=next(r['quality_metric_denominator'] for r in execution_summary if (r['experiment'],r['instance'],r['algorithm'])==(e,p,a))
        if count==0:
            text.append(f"| {e} | {Path(p).name} | {a} | N/A — initialization_failed | N/A | N/A | N/A | N/A | N/A | N/A |")
            continue
        h=lookup[(e,p,a,'hv')]
        text.append(f"| {e} | {Path(p).name} | {a} (n={count}) | {h['median']:.6f} [{h['q1']:.6f},{h['q3']:.6f}] | "
            f"{med(e,p,a,'igd_plus'):.6f} | {med(e,p,a,'cmax_min'):g} | {med(e,p,a,'tec_min'):.3f} | "
            f"{med(e,p,a,'front_size'):g} | {med(e,p,a,'elapsed_seconds'):.3f} | {med(e,p,a,'rejection_rate'):.2%} |")
    text+=['','## Inferência do Experimento A','',
        'Unidade: instância; três medianas de HV por instância, com 13 blocos. Seeds não são '
        'problemas independentes. Friedman global, Wilcoxon signed-rank somente se significativo, '
        'Holm nas três comparações e correlação rank-biserial pareada. IGD+ é confirmação secundária '
        'com família de comparações separada. P-values do Friedman são assintóticos e devem '
        'ser interpretados com cautela com 13 blocos; isto não estima superioridade em todo benchmark.']
    for metric,result in tests['metrics'].items():
        f=result['friedman']
        text+=['',f"{metric}: Friedman χ²={f['statistic']:.6f}, p={f['p_value']:.6g}, Kendall W={f['kendall_W']:.6f}."]
        for pair in result['pairwise']:
            text.append(f"- {pair['a']} vs {pair['b']}: p={pair['p_value']:.6g}, Holm={pair['p_holm']:.6g}, "
                f"rank-biserial={pair['rank_biserial']:.6f}, diferença mediana={pair['median_paired_difference']:.6f}. "
                f"{'Diferença significativa após Holm.' if pair['significant_holm'] else 'Sem diferença significativa após Holm.'}")
    text+=['','## Comparações pareadas e baselines','',
        'paired_comparisons.csv alinha instância+seed+budget, reporta HV/IGD+/extremos/tamanho/tempo/rejeição '
        'dos dois algoritmos e ambas as direções C(A,B)/C(B,A). Coverage é a fração da frente alvo '
        'fracamente dominada (inclui igualdade), não um indicador simétrico.','',
        'exact_baseline_metrics.csv contém coincidências exatas, pontos estritamente dominados pela '
        'frente exata, possíveis conflitos (devem ser zero), HV exato, HV_alg/HV_exato, IGD+ exato '
        'e coverage nos dois sentidos. Baselines complete+pareto_proven são carregados somente após '
        'as buscas e têm hash conferido. Nenhum aproximado dominou estritamente um ponto '
        'de baseline complete+pareto_proven; caso contrário a análise teria parado.','',
        '| Entrada | Algoritmo | Iguais med. | Dominados med. | HV_alg/HV_exato med. | IGD+ exato med. |',
        '|---|---|---:|---:|---:|---:|']
    for p,a in sorted({(r['instance'],r['algorithm']) for r in exact_metrics}):
        rs=[r for r in exact_metrics if r['instance']==p and r['algorithm']==a]
        text.append(f"| {Path(p).name} | {a} | {np.median([r['equal_points'] for r in rs]):g} | "
            f"{np.median([r['strictly_dominated_points'] for r in rs]):g} | "
            f"{np.median([r['hv_ratio'] for r in rs]):.6f} | {np.median([r['igd_plus'] for r in rs]):.6f} |")
    text+=['','## Escalabilidade e profundidade','',
        'B mede 750 jobs a 2k tentativas: custo por tentativa, rejeição e diversidade estão em '
        'summary.csv. Não extrapolar tempo de A a B sem considerar budgets, tarifas, máquinas '
        'e horizonte. B não participa dos testes de A. C compara 20k com as mesmas cinco seeds '
        'de A/8k, sem redefinir budget principal. budget_depth_comparisons.csv registra ganhos '
        'de HV/IGD+ e coverage bidirecional por algoritmo/seed; referências empíricas distintas '
        'por experimento tornam IGD+ entre budgets um diagnóstico com referências distintas. '
        'HV é diretamente comparável por ter mesmos bounds e reference point.','',
        '| Algoritmo | ΔHV 20k−8k med. | Melhorou HV | Tempo 20k/8k med. |',
        '|---|---:|---:|---:|']
    target='data/input/set2/250_10_1439_5_S_1-9.dat'
    for a in ALGORITHMS:
        pairs=[]
        for seed in [101,211,307,401,503]:
            x=next(r for r in metrics if r['experiment']=='A' and r['instance']==target and r['algorithm']==a and r['seed']==seed)
            y=next(r for r in metrics if r['experiment']=='C' and r['algorithm']==a and r['seed']==seed)
            pairs.append((y['hv']-x['hv'],y['elapsed_seconds']/x['elapsed_seconds']))
        text.append(f"| {a} | {np.median([d for d,t in pairs]):.6f} | {sum(d>0 for d,t in pairs)}/5 | {np.median([t for d,t in pairs]):.3f} |")
    text+=['','## Figuras','',
        '![HV A](figures/hv_A.png)','![Medianas/ranks](figures/hv_instance_ranking.png)',
        '![Tempo](figures/runtime_by_size.png)','![Conclusão B](figures/initialization_success_B.png)']
    for e,p in [('A','6_2_1439_3_S_1-9'),('A','50_10_1439_5_S_1-9'),('A','250_10_1439_5_S_1-9'),('B','750_10_1439_5_S_1-9')]:
        text.append(f'![Frentes {p}](figures/pareto_{e}_{p}.png)')
    wins=defaultdict(int)
    for p in {r['instance'] for r in metrics if r['experiment']=='A'}:
        vals={a:med('A',p,a,'hv') for a in ALGORITHMS};best=max(vals.values())
        for a,v in vals.items():
            if v==best:wins[a]+=1
    text+=['','## Limitações e conclusão sustentada','',
        'Melhor HV mediano por instância de A (empates contados): '+', '.join(f'{a}: {wins[a]}/13' for a in ALGORITHMS)+'. '
        'A inferência acima distingue diferenças sustentadas de ordenações apenas descritivas. '
        'A robustez deve ser lida pelos IQRs/faixas, não apenas pela mediana. Tempos refletem '
        'implementações e overheads distintos, não eficiência isolada do operador.','',
        'Qualidade multiobjetivo: HV e IGD+ caracterizam o compromisso entre os dois objetivos, '
        'com coverage pareada e extremos como diagnósticos. A normalização a priori é válida '
        'mas seus limites individuais podem ser frouxos, comprimindo TEC e afetando o peso '
        'geométrico relativo no HV/IGD+. Não se substituiu a escala por extremos observados. '
        'Nas instâncias sem baseline exato, IGD+ usa referência empírica limitada aos algoritmos/seeds, sem garantia de ótima.','',
        'SPEA2 é incremental, não geracional clássico, e normalize=False torna a densidade '
        'sensível às unidades originais. MOEA/D usa escala interna fixa Cmax/H e TEC/max_cost; '
        'directions uniformes não garantem cobertura uniforme, e fallback de inviabilidade '
        'pode afetar exploração mesmo se não ocorrer. VNS/VND busca por arquivo Pareto e '
        'rejeições inviáveis podem consumir parte substancial do budget. Esses fatores ajudam '
        'a interpretar diferenças por classe/tamanho e impedem atribuir todos os efeitos '
        'ao nome abstrato do algoritmo.','',
        'Os resultados de B e C são secundários: verificam custo/escala e sensibilidade ao '
        'budget, não substituem a comparação A. Nenhum ranking universal é inferido de '
        'pontos extras, um extremo isolado, rapidez ou uma única entrada. Nenhum algoritmo '
        'foi modificado ou retunado, e não houve commit/push.']
    (staging/'relatorio.md').write_text('\n'.join(text)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    manifest=json.loads((OUT/'manifest.json').read_text())
    if manifest['status']!='searches_complete' or len(manifest.get('cell_outcomes',{}))!=manifest['expected_runs']:
        raise ValueError('Every planned cell must have a terminal outcome before any references or comparative metrics')
    if any(v['status']=='execution_failed' for v in manifest['cell_outcomes'].values()):
        raise ValueError('Technical execution_failed outcomes require investigation')
    for p,h in manifest['source_sha256'].items():
        if digest(ROOT/p)!=h:raise ValueError('Source changed')
    for p,h in manifest['script_sha256'].items():
        if digest(OUT/p)!=h:raise ValueError('Script changed')
    for r in manifest['inventory']:
        if digest(ROOT/r['path'])!=r['sha256']:raise ValueError('Input changed')
    # All revalidation occurs before baselines. These structures contain only final run fronts.
    payloads={};unions=defaultdict(list);run_fronts={};n_revalidated=0;outcomes=[]
    instance=None
    for spec in manifest['execution_order']:
        entry=manifest['cell_outcomes'][spec['file']]
        opath=OUT/entry['outcome_file']
        if digest(opath)!=entry['outcome_file_sha256']:raise ValueError('Outcome hash changed')
        outcome=json.loads(opath.read_text())
        from run_final import validate_outcome
        status=validate_outcome(outcome,spec,manifest)
        outcomes.append(dict(experiment=spec['experiment'],instance=spec['instance'],algorithm=spec['algorithm'],seed=spec['seed'],
            planned_max_evaluations=spec['budget'],status=status,initialization_success=outcome['initialization_success'],
            run_completed=outcome['run_completed'],failure_stage=outcome.get('failure_stage'),
            failure_reason=outcome.get('failure_reason'),initialization_attempts=outcome.get('initialization_attempts'),
            search_attempts=outcome.get('search_attempts'),feasible_evaluations=outcome.get('feasible_evaluations'),
            rejected_evaluations=outcome.get('rejected_evaluations'),elapsed_seconds=outcome.get('elapsed_seconds'),
            quality_status='valid_front' if status=='completed' else 'N/A — '+status,outcome_file=entry['outcome_file']))
        if status!='completed':
            continue
        path=OUT/spec['file']
        if digest(path)!=manifest['completed_runs'][spec['file']]:raise ValueError('Run hash changed')
        data=json.loads(path.read_text())
        if instance is None or instance.digest!=spec['instance_sha256']:instance=read_instance(ROOT/spec['instance'])
        bounds=manifest['indicator_bounds'][spec['instance']]
        if calculate_bounds(instance)!=bounds:raise ValueError('Bound recomputation mismatch')
        if validate(data,spec,instance,bounds):raise ValueError('Reference violation')
        payloads[spec['file']]=data
        unions[(spec['experiment'],spec['instance'])].extend(data['front'])
        run_fronts[(spec['experiment'],spec['instance'],spec['algorithm'],spec['seed'])]=data['front']
        n_revalidated+=len(data['front'])
    import tempfile
    # Complete analysis staged outside repository; publish only after all checks succeed.
    with tempfile.TemporaryDirectory(prefix='mhm-final-analysis-') as temp:
        staging=Path(temp)
        references,exact,reads=reference_fronts(manifest,unions,staging)
        metrics=[];normalized_points=[];exact_metrics=[]
        inventory={r['path']:r for r in manifest['inventory']}
        for spec in manifest['execution_order']:
            if spec['file'] not in payloads:
                continue
            data=payloads[spec['file']];front=data['front'];p=spec['instance'];b=manifest['indicator_bounds'][p]
            reference=references[(spec['experiment'],p)];refpoints=points(reference['front'],b)
            hv_value=hv(front,b);igd=float(IGDPlus(refpoints)(points(front,b)))
            tec=min(Fraction(r['tec_exact']['numerator'],r['tec_exact']['denominator']) for r in front)
            row=dict(experiment=spec['experiment'],instance=p,algorithm=spec['algorithm'],seed=spec['seed'],
                max_evaluations=spec['budget'],n=inventory[p]['n'],m=inventory[p]['m'],instance_sha256=spec['instance_sha256'],
                attempts=data['attempts'],feasible_evaluations=data['feasible_evaluations'],
                rejected_evaluations=data['rejected_evaluations'],rejection_rate=data['rejected_evaluations']/data['attempts'],
                post_search_validations=data['post_search_validations'],independent_front_revalidations=len(front),
                elapsed_seconds=data['elapsed_seconds'],ms_per_attempt=1000*data['elapsed_seconds']/data['attempts'],
                front_size=len(front),cmax_min=min(r['makespan'] for r in front),tec_min_exact=str(tec),tec_min=float(tec),
                **diversity(front),hv=hv_value,igd_plus=igd,reference_type=reference['type'],reference_source=reference['source'],
                result_file=spec['file'])
            metrics.append(row)
            for index,r in enumerate(front):
                c,e=normalize_exact(*key(r),b)
                normalized_points.append(dict(experiment=spec['experiment'],instance=p,algorithm=spec['algorithm'],seed=spec['seed'],
                    max_evaluations=spec['budget'],front_index=index,cmax=key(r)[0],tec_units=key(r)[1],
                    tec_scale=b['tec_scale'],cmax_norm_exact=str(c),tec_norm_exact=str(e),cmax_norm=float(c),tec_norm=float(e),
                    cmax_h_diagnostic=r['makespan']/b['C_UB'],tec_max_cost_diagnostic=float(Fraction(key(r)[1],b['tec_scale'])/Fraction(inventory[p]['max_cost']))))
            if p in exact:
                reference_keys={key(r) for r in exact[p]['front']};approx=[key(r) for r in front]
                conflicts=[q for q in approx if any(dominates(q,r) for r in reference_keys)]
                if conflicts:raise ValueError(f'Approximation dominates complete proven baseline: {spec} {conflicts}')
                exact_hv=hv(exact[p]['front'],b)
                exact_metrics.append(dict(experiment=spec['experiment'],instance=p,algorithm=spec['algorithm'],seed=spec['seed'],
                    equal_points=sum(q in reference_keys for q in approx),
                    strictly_dominated_points=sum(any(dominates(r,q) for r in reference_keys) for q in approx),
                    apparent_dominating_points=len(conflicts),baseline_points=len(reference_keys),hv_exact=exact_hv,
                    hv_algorithm=hv_value,hv_ratio=hv_value/exact_hv,igd_plus=igd,
                    C_algorithm_exact=coverage(approx,reference_keys),C_exact_algorithm=coverage(reference_keys,approx)))
        summary=[]
        names=['hv','igd_plus','front_size','cmax_min','tec_min','elapsed_seconds','ms_per_attempt',
               'feasible_evaluations','rejected_evaluations','rejection_rate','allocations','orders','modes','waits']
        groups=defaultdict(list)
        for r in metrics:groups[(r['experiment'],r['instance'],r['algorithm'])].append(r)
        for (e,p,a),rows in sorted(groups.items()):
            expected=10 if e=='A' else 5
            group_outcomes=[r for r in outcomes if (r['experiment'],r['instance'],r['algorithm'])==(e,p,a)]
            if len(group_outcomes)!=expected or len(rows)!=sum(r['status']=='completed' for r in group_outcomes):
                raise ValueError('Outcome/quality denominator mismatch')
            for name in names:
                values=[r[name] for r in rows]
                summary.append(dict(experiment=e,instance=p,algorithm=a,metric=name,seeds=len(rows),planned_runs=expected,
                    completion_rate=len(rows)/expected,median=float(np.median(values)),q1=float(np.quantile(values,.25)),q3=float(np.quantile(values,.75)),
                    minimum=min(values),maximum=max(values)))
        paired=[];by_spec={(r['experiment'],r['instance'],r['seed'],r['algorithm']):r for r in metrics}
        for e,p,seed in sorted({(r['experiment'],r['instance'],r['seed']) for r in outcomes}):
            for i,a in enumerate(ALGORITHMS):
                for b in ALGORITHMS[i+1:]:
                    sa=next(r['status'] for r in outcomes if (r['experiment'],r['instance'],r['algorithm'],r['seed'])==(e,p,a,seed))
                    sb=next(r['status'] for r in outcomes if (r['experiment'],r['instance'],r['algorithm'],r['seed'])==(e,p,b,seed))
                    x=by_spec.get((e,p,seed,a));y=by_spec.get((e,p,seed,b))
                    budget=next(r['planned_max_evaluations'] for r in outcomes if (r['experiment'],r['instance'],r['algorithm'],r['seed'])==(e,p,a,seed))
                    row=dict(experiment=e,instance=p,seed=seed,max_evaluations=budget,a=a,b=b,status_a=sa,status_b=sb)
                    if x and y:
                        row.update(C_A_B=coverage([key(r) for r in run_fronts[(e,p,a,seed)]],[key(r) for r in run_fronts[(e,p,b,seed)]]),
                                   C_B_A=coverage([key(r) for r in run_fronts[(e,p,b,seed)]],[key(r) for r in run_fronts[(e,p,a,seed)]]))
                    else:
                        row.update(C_A_B='N/A — initialization_failed' if sa!='completed' else None,
                                   C_B_A='N/A — initialization_failed' if sb!='completed' else None)
                    for metric in ['hv','igd_plus','cmax_min','tec_min','tec_min_exact','front_size','elapsed_seconds','rejected_evaluations','rejection_rate']:
                        row[f'{metric}_a']=x[metric] if x else f'N/A — {sa}';row[f'{metric}_b']=y[metric] if y else f'N/A — {sb}'
                    paired.append(row)
        depth=[];target='data/input/set2/250_10_1439_5_S_1-9.dat'
        for a in ALGORITHMS:
            for seed in [101,211,307,401,503]:
                x=by_spec[('A',target,seed,a)];y=by_spec[('C',target,seed,a)]
                ka=[key(r) for r in run_fronts[('A',target,a,seed)]];kc=[key(r) for r in run_fronts[('C',target,a,seed)]]
                depth.append(dict(instance=target,algorithm=a,seed=seed,hv_8000=x['hv'],hv_20000=y['hv'],hv_gain=y['hv']-x['hv'],
                    igd_plus_8000=x['igd_plus'],igd_plus_20000=y['igd_plus'],reference_note='experiment-specific empirical references',
                    C_20k_8k=coverage(kc,ka),C_8k_20k=coverage(ka,kc),seconds_8000=x['elapsed_seconds'],seconds_20000=y['elapsed_seconds']))
        tests=statistical_tests(summary)
        export_csv(staging/'metrics.csv',metrics)
        export_csv(staging/'run_outcomes.csv',outcomes)
        outcome_groups=defaultdict(list)
        for o in outcomes:outcome_groups[(o['experiment'],o['instance'],o['algorithm'])].append(o)
        execution_summary=[]
        for (e,p,a),rows in sorted(outcome_groups.items()):
            complete=sum(r['status']=='completed' for r in rows)
            failed=sum(r['status']=='initialization_failed' for r in rows)
            execution_summary.append(dict(experiment=e,instance=p,algorithm=a,planned_runs=len(rows),runs_completed=complete,
                initialization_failures=failed,execution_failures=sum(r['status']=='execution_failed' for r in rows),
                completion_rate=complete/len(rows),quality_metric_denominator=complete,
                initialization_attempts=sum(r['initialization_attempts'] or 0 for r in rows),
                search_attempts=sum(r['search_attempts'] or 0 for r in rows)))
        export_csv(staging/'execution_summary.csv',execution_summary)
        export_csv(staging/'normalized_metrics.csv',[{k:r[k] for k in ['experiment','instance','algorithm','seed','max_evaluations','hv','igd_plus','reference_type','reference_source']} for r in metrics])
        export_csv(staging/'normalized_points.csv',normalized_points)
        export_csv(staging/'exact_baseline_metrics.csv',exact_metrics)
        export_csv(staging/'paired_comparisons.csv',paired)
        export_csv(staging/'budget_depth_comparisons.csv',depth)
        export_csv(staging/'summary.csv',summary)
        atomic_json(staging/'statistical_tests.json',tests)
        atomic_json(staging/'validation.json',dict(status='passed',planned_outcomes=len(outcomes),
            outcomes_by_status={k:sum(r['status']==k for r in outcomes) for k in ['completed','initialization_failed','execution_failed']},runs_revalidated=len(metrics),
            final_schedules_revalidated=n_revalidated,all_budgets_confirmed=True,all_hashes_confirmed=True,
            all_objectives_feasible_exact_unique_nondominated=True,all_normalized_points_in_unit_square=True,
            reference_point=REFERENCE,baseline_reads_after_all_searches=True,baseline_reads=reads,
            exact_instances=list(exact),empirical_fronts=sum(r['type']=='empirical' for r in references.values())))
        figures(metrics,summary,run_fronts,references,staging)
        execdir=staging/'figures';fig,ax=plt.subplots(figsize=(9,4))
        br=[r for r in execution_summary if r['experiment']=='B']
        labels=[Path(r['instance']).stem+'\n'+r['algorithm'] for r in br]
        ax.bar(range(len(br)),[r['completion_rate'] for r in br],color=[COLORS[ALGORITHMS.index(r['algorithm'])] for r in br])
        ax.set_xticks(range(len(br)),labels,rotation=55,ha='right');ax.set(ylim=(0,1.05),ylabel='runs concluídas / planejadas',title='Experimento B — capacidade de conclusão (5 seeds)')
        for i,r in enumerate(br):ax.text(i,r['completion_rate']+.02,f"{r['runs_completed']}/{r['planned_runs']}",ha='center',fontsize=8)
        fig.tight_layout();fig.savefig(execdir/'initialization_success_B.png',dpi=160);plt.close(fig)
        report(manifest,metrics,summary,tests,exact_metrics,staging,outcomes,execution_summary)
        if not args.publish:raise ValueError('Analysis validated; use --publish for explicit archived replacement')
        archive=OUT/'history'/('analysis_before_'+str(time.time_ns()));archive.mkdir()
        for p in staging.iterdir():
            target_path=OUT/p.name
            if target_path.exists():shutil.move(str(target_path),archive/p.name)
            shutil.copytree(p,target_path) if p.is_dir() else shutil.copyfile(p,target_path)
        manifest.update(analysis_completed_utc=utc(),baseline_reads=reads,analysis_environment=dict(scipy=scipy.__version__,matplotlib=matplotlib.__version__),
            analysis_artifact_sha256={str(p.relative_to(OUT)):digest(p) for p in OUT.rglob('*') if p.is_file() and
                ('history' not in p.relative_to(OUT).parts) and p.name not in ['manifest.json'] and '__pycache__' not in p.parts})
        atomic_json(OUT/'manifest.json',manifest)
        print(json.dumps(tests,indent=2))
        print(f'Published analysis: {len(metrics)} runs, {n_revalidated} exact final revalidations; {len(exact)} exact references.')


if __name__=='__main__':main()
