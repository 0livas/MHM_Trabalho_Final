"""Build an offline comparison dashboard from preserved experiment evidence."""
from pathlib import Path
import csv, json, sys, statistics, re, hashlib, argparse, logging
from collections import defaultdict
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from problem import read_instance, energy_scale
from experiments.metrics import normalize, hypervolume_2d, igd_plus, igd, gd, spacing, spread, epsilon_additive
OUT = ROOT / 'data/output/dashboard'
OUT.mkdir(exist_ok=True)

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))
def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def name(s): return Path(s.replace('\\','/')).name.removesuffix('.dat')
@lru_cache(None)
def scale_for(ins):
    return energy_scale(read_instance(next((ROOT/'data/input').rglob(ins+'.dat'))))[0]
def nd(points):
    best=float('inf'); result=[]
    for x,y in sorted(set(map(tuple,points))):
        if y<best: result.append([x,y]); best=y
    return result
def export(p, rs):
    keys=list(dict.fromkeys(k for r in rs for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rs)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--article',type=Path,help='PDF do artigo, para extrair ou atualizar a transcrição')
    args=parser.parse_args()
    article_text=OUT/'artigo_extraido.txt'
    if args.article:
        from pypdf import PdfReader
        logging.getLogger('pypdf').setLevel(logging.ERROR)
        article_text.write_text('\n'.join(p.extract_text() for p in PdfReader(args.article).pages),encoding='utf-8')
    if not article_text.exists():raise SystemExit('Forneça --article com o caminho do PDF na primeira geração.')
    campaigns=[]; audit=[]; allrows=[]
    for folder in ['experiments','experiments_vns_new']:
        base=ROOT/'data/output'/folder
        metric=base/'metrics/per_run_metrics.csv'
        if not metric.exists(): continue
        rr=rows(metric); fronts=defaultdict(list); runs=defaultdict(list)
        for r in rr:
            ins=name(r['instance']); alg=r['algorithm']; key=(ins,alg)
            p=base/'runs'/alg/ins/f"run_{int(r['run_id']):02d}.json"
            if not p.exists(): continue
            d=read(p)
            instfiles=list((ROOT/'data/input').rglob(ins+'.dat'))
            if not instfiles: continue
            scale=scale_for(ins)
            pts=d.get('points',[])
            if not isinstance(pts,list): continue
            fronts[key]+= [[x,y/scale] for x,y in pts]
            runs[key].append(dict(seed=r['seed'],points=[[x,y/scale] for x,y in pts],status=d.get('status'),proven=d.get('pareto_proven',False),wall_s=d.get('wall_seconds'),source=str(p.relative_to(ROOT))))
        summary=[]
        for r in rows(base/'metrics/summary.csv'):
            z=dict(campanha=folder,instancia=name(r.pop('instance')),algoritmo=r.pop('algorithm'),**r)
            evidence=runs.get((z['instancia'],z['algoritmo']),[])
            z['situacao']='; '.join(f'{st}: {sum(e.get("status")==st for e in evidence)}' for st in sorted({e.get('status','não registrado') for e in evidence}))
            z['execucoes_com_fronteira']=sum(bool(e['points']) for e in evidence)
            if int(z.get('n',0))==1:z['std']=None
            summary.append(z)
        allrows+=summary
        campaigns.append(dict(id=folder,label={'experiments':'Campanha de 30 repetições','experiments_vns_new':'Campanha VNS revisado'}[folder],summary=summary,series=[dict(instance=k[0],algorithm=k[1],points=nd(v),runs=runs[k]) for k,v in fronts.items()],note='HV com referência (1,1; 1,1), normalização ideal/nadir de PF*. União não dominada das repetições; não representa uma execução típica. Tempos e demais métricas são por execução.'))
    if len(campaigns)==2:
        original, corrected=campaigns
        refs=read(ROOT/'data/output/experiments/metrics/reference_fronts.json')
        joint=[]; jointsummary=[dict(r,campanha='comparacao_vns') for r in original['summary']]
        for s in corrected['series']:
            s=dict(s,algorithm='vns_vnd_new');joint.append(s)
            ref=refs[s['instance']+'.dat'];scale=scale_for(s['instance'])
            ideal=[ref['ideal'][0],ref['ideal'][1]/scale];nadir=[ref['nadir'][0],ref['nadir'][1]/scale]
            reference=normalize([[x,y/scale] for x,y in ref['points']],ideal,nadir)
            vv=defaultdict(list)
            for r in s['runs']:
                if not r['points']:continue
                a=normalize(r['points'],ideal,nadir)
                for m,v in [('HV',hypervolume_2d(a)),('IGD',igd(a,reference)),('IGD_plus',igd_plus(a,reference)),('GD',gd(a,reference)),('EPS_add',epsilon_additive(a,reference)),('Spacing',spacing(a)),('Spread',spread(a,reference)),('NDS',len(a)),('wall_s',r['wall_s'])]:
                    if v is not None:vv[m].append(v)
            for m,v in vv.items():jointsummary.append(dict(campanha='comparacao_vns',instancia=s['instance'],algoritmo='vns_vnd_new',metric=m,n=len(v),mean=statistics.mean(v),std=statistics.stdev(v) if len(v)>1 else None,median=statistics.median(v),best=max(v) if m in ['HV','NDS'] else min(v),worst=min(v) if m in ['HV','NDS'] else max(v)))
        campaigns.insert(0,dict(id='comparacao_vns',label='Comparação conjunta • dois VNS/VND • referência comum',series=original['series']+joint,summary=jointsummary,note='Referência fixa da campanha original para todos os métodos, inclusive VNS/VND corrigido. Indicadores da versão corrigida recalculados no mesmo espaço. Pontos fora da caixa não contribuem ao HV. Resultados originais preservados nos protocolos separados.'))
        allrows+=jointsummary
    base=ROOT/'data/output/final_comparison'
    if (base/'metrics.csv').exists():
        rr=rows(base/'metrics.csv'); pr=rows(base/'normalized_points.csv'); fronts=defaultdict(list); runs=defaultdict(lambda:defaultdict(list))
        for r in pr:
            k=(r['experiment'],name(r['instance']),r['algorithm'])
            pt=[float(r['cmax']),int(r['tec_units'])/int(r['tec_scale'])]
            fronts[k].append(pt);runs[k][r['seed']].append(pt)
        for experiment in sorted({r['experiment'] for r in rr}):
            summary=[]
            grouped=defaultdict(list)
            for r in rr:
                if r['experiment']!=experiment:continue
                for m in ['hv','igd_plus','elapsed_seconds','front_size','cmax_min','tec_min','rejection_rate','attempts']:
                    if r.get(m):grouped[(name(r['instance']),r['algorithm'],m)].append(float(r[m]))
            for (ins,alg,m),v in grouped.items():
                summary.append(dict(campanha='final_'+experiment,instancia=ins,algoritmo=alg,metric=m,n=len(v),mean=statistics.mean(v),std=statistics.stdev(v) if len(v)>1 else None,median=statistics.median(v),best=min(v),worst=max(v)))
            allrows+=summary
            budgets=sorted({r['max_evaluations'] for r in rr if r['experiment']==experiment})
            campaigns.append(dict(id='final_'+experiment,label='Comparação final • '+experiment+' • '+', '.join(budgets)+' avaliações',summary=summary,series=[dict(instance=k[1],algorithm=k[2],points=nd(v),runs=[dict(seed=s,points=pts) for s,pts in runs[k].items()]) for k,v in fronts.items() if k[0]==experiment],note='Orçamento: '+', '.join(budgets)+' avaliações. HV com limites a priori e referência (1,05; 1,05). IGD+ usa referência exata quando disponível; nas demais instâncias, referência empírica. Protocolos finais não são intercambiáveis com a campanha de 30 repetições.'))
    # Supplement individual local outputs, kept in a separate evidence cohort.
    series=[]; summary=[]
    for method in ['custom_exact','custom_exact_dp','cpsat','heuristica_construtiva','heuristica_ociosidade']:
        for p in sorted((ROOT/'data/output'/method).glob('*.json')):
            d=read(p); front=d.get('front',[])
            if not front or not isinstance(front,list) or not isinstance(front[0],dict):continue
            pts=[[r['makespan'],r['tec']] for r in front]
            ins=name(d.get('instance',p.stem)); alg=method
            series.append(dict(instance=ins,algorithm=alg,points=nd(pts),proven=d.get('pareto_proven',False),source=str(p.relative_to(ROOT)),runs=[]))
            for m,v in [('wall_s',d.get('elapsed_seconds')),('NDS',len(nd(pts))),('Cmax_min',min(x for x,y in pts)),('TEC_min',min(y for x,y in pts))]:
                if v is not None:summary.append(dict(campanha='individuais',instancia=ins,algoritmo=alg,metric=m,n=1,mean=v,std=None,median=v,best=v,worst=v))
    allrows+=summary
    campaigns.append(dict(id='individuais',label='Exatos e heurísticas • arquivos individuais',series=series,summary=summary,note='Arquivos individuais, sem agregação com campanhas de outros protocolos. Ausência de repetição não significa variância zero. Pareto comprovado indicado por série.'))
    baselines=[]
    for p in sorted((ROOT/'data/baselines').glob('*.json')):
        d=read(p)
        if d.get('pareto_proven') and d.get('front'):
            baselines.append(dict(instance=name(d['instance']),algorithm='custom_exact_dp',points=[[r['makespan'],r['tec']] for r in d['front']],proven=True,source=str(p.relative_to(ROOT)),runs=[]))
    # Published tables, transcribed from the supplied PDF; no invented coordinates.
    text=article_text.read_text(encoding='utf-8')
    article=[]
    small=[('6',6406.67,250,239.91),('7',15918.87,400,260.68),('8',3338.29,260,302.58),('9',22256.33,440,357.69),('10',31789.09,500,370.68)]
    t7=text.split('Table 7 RPDHV and runtime')[1].split('Table 8')[0]
    t8=text.split('Table 8 HCC and runtime')[1].split('Rego et al.')[0]
    for i,(n,hv,x,y) in enumerate(small,1):
        vals=[float(v.replace(',','')) for v in re.search(r'^'+str(i)+r' (.+)$',t7,re.M)[1].split()]
        h=[float(v.replace(',','')) for v in re.search(r'^'+str(i)+r' (.+)$',t8,re.M)[1].split()]
        common=dict(instancia=n+'_2_1439_3_S_1-9',HV_ref=hv,RP_Cmax=x,RP_TEC=y,n=30)
        article.append(dict(**common,algoritmo='NSGA-II',RPD_min=vals[0],RPD_max=vals[1],RPD_media=vals[2],RPD_dp=vals[3],tempo_s=vals[4],HCC_media=h[2],HCC_dp=h[3]))
        article.append(dict(**{**common,'n':None},algoritmo='Gurobi (soma ponderada)',n_execucoes='não informado como replicações',RPD_UB=vals[5],tempo_s=vals[6],HCC_UB=h[5]))
    t9=text.split('Table 9 Reference set data')[1].split('Table 10')[0]
    t10=text.split('Table 10 RPDHV and runtime')[1].split('Note:')[0]
    t11=text.split('Table 11 HCC and runtime')[1].split('Note:')[0]
    for line in t9.splitlines():
        match=re.match(r'^(\d+) (\d+_\S+) .+? ([\d,]+) \(([\d,]+); ([\d,.]+)\)',line)
        if not match:continue
        i,ins,hv,x,y=match.groups();v=[float(q.replace(',','')) for q in re.search(r'^'+i+r' (.+)$',t10,re.M)[1].split()];h=[float(q.replace(',','')) for q in re.search(r'^'+i+r' (.+)$',t11,re.M)[1].split()]
        for a,alg in enumerate(['MOGA','NSGA-I','NSGA-II']):
            article.append(dict(instancia=ins,algoritmo=alg,n=30,HV_ref=float(hv.replace(',','')),RP_Cmax=float(x.replace(',','')),RP_TEC=float(y.replace(',','')),RPD_min=v[4*a],RPD_max=v[4*a+1],RPD_media=v[4*a+2],RPD_dp=v[4*a+3],tempo_s=v[-1],HCC_min=h[4*a],HCC_max=h[4*a+1],HCC_media=h[4*a+2],HCC_dp=h[4*a+3]))
    for c in campaigns:
        if c['id'] not in ['comparacao_vns','experiments','experiments_vns_new']:continue
        folder='experiments_vns_new' if c['id']=='experiments_vns_new' else 'experiments'
        refs=read(ROOT/'data/output'/folder/'metrics/reference_fronts.json')
        extra=[]
        for r in c['summary']:
            if r['metric']!='HV':continue
            ref=refs[r['instancia']+'.dat']
            hvref=hypervolume_2d(normalize(ref['points'],ref['ideal'],ref['nadir']))
            z=dict(r,metric='RPD_HV_pct',HV_referencia=hvref)
            for field in ['mean','median','best','worst']:
                if z.get(field) is not None:z[field]=100*(hvref-float(z[field]))/hvref
            for field in ['std','iqr']:
                if z.get(field) is not None:z[field]=100*float(z[field])/hvref
            extra.append(z)
        c['summary']+=extra;allrows+=extra
    export(OUT/'metricas_completas.csv',allrows);export(OUT/'artigo_tabelas_6_a_11.csv',article)
    analysis=[
        'Nas instâncias pequenas originais de seis e dez tarefas, o método exato por programação dinâmica fornece as fronteiras comprovadas e os maiores hipervolumes da campanha de 30 repetições. Para seis tarefas, ele também apresenta tempo favorável: cerca de 0,97 s, diante de 7,94 s do AGE-MOEA e 61,65 s do SPEA2. Entre as meta-heurísticas, SPEA2 tem pequena vantagem média em HV nessa instância; para dez tarefas, AGE-MOEA lidera esse grupo. A heurística de ociosidade se destaca no compromisso entre qualidade e tempo: em dez tarefas, alcança HV médio de 1,0366 em 0,15 s, próximo do exato, cujo HV é 1,0455 e o tempo é 29,74 s. Esses resultados não estabelecem significância estatística por si só.',
        'Na instância derivada de 14 tarefas e nas instâncias testadas de 50 e 250 tarefas, a heurística de ociosidade apresenta o maior HV observado na campanha original. AGE-MOEA lidera as meta-heurísticas nessas instâncias, seguido em geral por SPEA2; MOEA/D é competitivo na instância de 50 tarefas e dez máquinas, mas perde qualidade relativa nas demais. SPEA2 exige mais tempo que AGE-MOEA nos casos examinados. A ausência de fronteira exata comprovada nesses tamanhos limita a conclusão à qualidade relativa às referências empíricas, sem demonstrar proximidade do ótimo global.',
        'As duas versões do VNS/VND foram preservadas porque o construtor original falhava na primeira instância giant, 750_10_1439_5_S_1-9. A versão corrigida conclui execuções nessa instância. Com a referência da campanha original aplicada a ambas, a correção também melhora o HV médio nas instâncias de seis, dez, 50 e 250 tarefas, enquanto a derivada de 14 tarefas apresenta redução. Ainda assim, a versão corrigida permanece atrás da heurística de ociosidade e das melhores meta-heurísticas nesses casos. Nas instâncias giant, seu HV permanece zero na caixa de referência comum, apesar de produzir soluções: isso indica ausência de contribuição dentro dessa caixa, e não ausência de soluções viáveis. Uma falha de inicialização é um resultado distinto de uma execução concluída com HV zero.',
        'Nas duas instâncias de 750 tarefas presentes na campanha, a heurística de ociosidade é o único método com HV positivo na referência original e oferece o melhor desempenho observado por esse critério. Os tempos maiores refletem o crescimento do problema, e não devem ser confundidos com prova de qualidade. As comparações finais com outros orçamentos e limites a priori devem ser lidas separadamente: uma classificação de algoritmos vale para o protocolo, instância e orçamento que a originaram, sem permitir extrapolação automática para toda a família.',
        'No artigo de Rego et al. (2022), o NSGA-II supera MOGA e NSGA-I em qualidade de HV nas instâncias grandes, admitindo empates nos números arredondados publicados, e apresenta melhor HCC em parte majoritária dos casos. Nas pequenas, ele também supera o conjunto produzido pelo Gurobi com soma ponderada em qualidade e tempo. Essa comparação não contradiz o desempenho do nosso exato: a soma ponderada pode deixar de recuperar pontos não suportados, enquanto a programação dinâmica busca uma fronteira completa quando a comprovação é obtida. Não é possível declarar nossos algoritmos superiores ao NSGA-II do artigo apenas por confrontar seus HVs, pois referências, normalizações, ambientes e protocolos diferem. O PDF apresenta curvas de exemplos, não coordenadas de todas as fronteiras, e não há HCC local disponível para uma comparação numérica direta.'
    ]
    (OUT/'analise.txt').write_text('\n\n'.join(analysis),encoding='utf-8')
    outcomes=[]
    for c in campaigns:
        for s in c['series']:
            statuses=defaultdict(int)
            for r in s.get('runs',[]):statuses[r.get('status','não registrado')]+=1
            if statuses:outcomes.append(dict(campanha=c['id'],instancia=s['instance'],algoritmo=s['algorithm'],**statuses))
    export(OUT/'execucoes.csv',outcomes)
    unified=allrows+[dict(campanha='artigo',**r) for r in article]
    export(OUT/'tabela_unificada.csv',unified)
    data=dict(campaigns=campaigns,baselines=baselines,article=article,analysis=analysis,outcomes=outcomes)
    provenance=[]
    for folder in ['experiments','experiments_vns_new','final_comparison']:
        for p in sorted((ROOT/'data/output'/folder).rglob('*.csv')):
            if 'metrics' in str(p.parent) or p.parent.name=='final_comparison':
                provenance.append(dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    (OUT/'fontes.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    assert len(article)==46
    for c in campaigns:
        for s in c['series']:
            assert nd(s['points'])==s['points'],(c['id'],s['instance'],s['algorithm'])
    (OUT/'dados.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    template=(ROOT/'src/dashboard_template.html').read_text(encoding='utf-8')
    (OUT/'index.html').write_text(template.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/')),encoding='utf-8')
    print(json.dumps(dict(campaigns=len(campaigns),series=sum(len(c['series']) for c in campaigns),metrics=len(allrows),article_rows=len(article),baselines=len(baselines))))
if __name__=='__main__':main()
