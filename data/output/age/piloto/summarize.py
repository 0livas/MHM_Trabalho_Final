"""Post-search validation and AGE-only pilot indicators; no historical outputs written."""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
import csv
import json
from pathlib import Path
import statistics
import sys

import numpy as np
from pymoo.indicators.hv import HV
from pymoo.indicators.igd_plus import IGDPlus
from scipy.stats import rankdata

from run_pilot import OUT, ROOT, INSTANCES, digest, diversity, validate_front
from normalization import normalize, REFERENCE
from problem import atomic_json, read_instance, dominates
from schedule import evaluate_schedule, schedule_from_result_rows


def pareto(rows):
    unique = {(r['makespan'], r['tec_exact']['numerator']): r for r in rows}
    result, best = [], None
    for key in sorted(unique):
        if best is None or key[1] < best:
            result.append(unique[key])
            best = key[1]
    return result


def points(front, bounds):
    return np.asarray([normalize(r['makespan'], r['tec_exact']['numerator'], bounds) for r in front])


def indicators(front, reference, bounds):
    p, r = points(front, bounds), points(reference, bounds)
    return float(HV(ref_point=np.array(REFERENCE))(p)), float(IGDPlus(r)(p))


def csv_write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    manifest = json.loads((OUT / 'manifest.json').read_text())
    frozen = json.loads((OUT / 'protocol.json').read_text())
    if manifest['status'] != 'searches_complete' or len(manifest['runs']) != 72:
        raise ValueError('References cannot be read before all searches complete')
    if manifest['protocol_sha256'] != digest(OUT / 'protocol.json'):
        raise ValueError('Protocol hash changed')
    for path, expected in frozen['source_sha256'].items():
        if digest(ROOT / path) != expected:
            raise ValueError('Frozen source changed')
    for path, expected in frozen['input_sha256'].items():
        if digest(ROOT / 'data/input' / path) != expected:
            raise ValueError('Frozen input changed')
    runs, unions = [], defaultdict(list)
    for entry in manifest['runs']:
        path = OUT / entry['file']
        if digest(path) != entry['sha256']:
            raise ValueError('Result hash changed')
        data = json.loads(path.read_text())
        instance_path = next(p for p in INSTANCES if Path(p).name == data['instance'])
        instance = read_instance(ROOT / 'data/input' / instance_path)
        if data['pilot_protocol_sha256'] != manifest['protocol_sha256']:
            raise ValueError('Result protocol mismatch')
        validate_front(instance, data)
        if not (data['attempts'] == data['pymoo_evaluations'] == data['budget'] == 8000
                and data['feasible_evaluations'] + data['rejected_evaluations'] == 8000
                and sum(data['evaluation_batches']) == 8000
                and data['pilot']['independent_search_calls'] == 8000
                and data['pilot']['independent_post_calls'] == data['population_size']
                and data['post_search_validations'] == data['population_size']
                and data['pilot']['independent_population_revalidations'] == data['population_size']
                and data['points'] == len(data['front'])):
            raise ValueError('Budget validation failed')
        unions[instance_path].extend(data['front'])
        runs.append((entry['file'], instance_path, data))
    actual_cells = {(p, d['population_size'], d['run_parameters']['mutation_probability'],
                     d['run_parameters']['seed']) for _,p,d in runs}
    if actual_cells != {tuple(cell) for cell in frozen['order']}:
        raise ValueError('Missing or unexpected planned cells')
    # No official/cross-algorithm results or reserved seeds enter these references.
    references = {}
    for p in INSTANCES:
        if p == INSTANCES[0]:
            path = ROOT / 'data/baselines/6_2_1439_3_S_1-9_custom_exact_dp.json'
            data = json.loads(path.read_text())
            if not (data['pareto_proven'] and data['status'] == 'complete'):
                raise ValueError('Baseline not proven')
            instance = read_instance(ROOT / 'data/input' / p)
            converted = []
            for original in data['front']:
                schedule = schedule_from_result_rows(instance, original['schedule'])
                ev = evaluate_schedule(instance, schedule)
                if ev.cmax != original['makespan'] or ev.tec_units != original['tec_exact']['numerator'] or ev.tec_scale != original['tec_exact']['denominator']:
                    raise ValueError('Exact baseline objective mismatch')
                row = ev.to_result_dict(instance)
                row['representation'] = schedule
                converted.append(row)
            data['front'] = converted
            validate_front(instance, data)
            ref = dict(type='exact', source=str(path.relative_to(ROOT)), sha256=digest(path), front=data['front'])
            exact_keys = [(r['makespan'], r['tec_exact']['numerator']) for r in data['front']]
            if any(dominates((r['makespan'], r['tec_exact']['numerator']), e)
                   for r in unions[p] for e in exact_keys):
                raise ValueError('AGE front dominates exact baseline')
        else:
            ref = dict(type='empirical_AGE_pilot_only_not_proven', front=pareto(unions[p]))
        ref['points'] = len(ref['front'])
        references[p] = ref
    atomic_json(OUT / 'references.json', references)
    rows = []
    for filename, path, data in runs:
        config = data['run_parameters']
        bounds = frozen['indicator_bounds'][path]
        hv, igd = indicators(data['front'], references[path]['front'], bounds)
        pts = points(data['front'], bounds)
        row = dict(instance=path, configuration=f"p{config['population_size']}_m{config['mutation_probability']}",
            seed=config['seed'], population=config['population_size'], mutation=config['mutation_probability'],
            hv=hv, igd_plus=igd, front_size=data['points'],
            feasible=data['feasible_evaluations'], rejected=data['rejected_evaluations'],
            rejection_rate=data['rejected_evaluations']/8000,
            seconds=data['elapsed_seconds'], numba_compile_seconds=data['pilot']['numba_compile_seconds'],
            ms_per_evaluation=1000*data['elapsed_seconds']/8000,
            cmax_min=min(r['makespan'] for r in data['front']),
            tec_min=min(r['tec_exact']['numerator']/r['tec_exact']['denominator'] for r in data['front']),
            tec_min_exact=str(min(Fraction(r['tec_exact']['numerator'], r['tec_exact']['denominator']) for r in data['front'])),
            cmax_span=float(np.ptp(pts[:,0])), tec_span=float(np.ptp(pts[:,1])),
            independent_front_revalidations=len(data['front']),
            independent_population_revalidations=data['pilot']['independent_population_revalidations'],
            reference_type=references[path]['type'], result_file=filename)
        row.update({f'population_{k}': v for k, v in data['pilot']['population_diversity'].items()})
        row.update({f'front_{k}': v for k, v in data['pilot']['front_diversity'].items()})
        rows.append(row)
    if len({(r['instance'], r['configuration'], r['seed']) for r in rows}) != 72:
        raise ValueError('Repeated/missing cells')
    for path in INSTANCES:
        for seed in frozen['seeds']:
            group = [r for r in rows if r['instance']==path and r['seed']==seed]
            for r, rank in zip(group, rankdata([-r['hv'] for r in group])):
                r['hv_seed_rank'] = float(rank)
    csv_write(OUT / 'metrics.csv', rows)
    summaries = []
    for path in INSTANCES:
        for pop in frozen['populations']:
            for mut in frozen['mutations']:
                group = [r for r in rows if r['instance']==path and r['population']==pop and r['mutation']==mut]
                summary = dict(instance=path, population=pop, mutation=mut)
                for key in ('hv','igd_plus','front_size','seconds','rejection_rate','population_schedules',
                            'population_allocations','population_orders','population_modes','population_waits',
                            'front_allocations','front_orders','front_modes','front_waits',
                            'cmax_span','tec_span','hv_seed_rank'):
                    values = [r[key] for r in group]
                    summary.update({f'{key}_median': statistics.median(values),
                                    f'{key}_min': min(values), f'{key}_max': max(values),
                                    f'{key}_q1': float(np.quantile(values,.25)),
                                    f'{key}_q3': float(np.quantile(values,.75))})
                summaries.append(summary)
        group = [s for s in summaries if s['instance']==path]
        for s, rank, igd_rank in zip(group, rankdata([-s['hv_median'] for s in group]),
                                    rankdata([s['igd_plus_median'] for s in group])):
            s.update(hv_instance_rank=float(rank), igd_instance_rank=float(igd_rank))
    csv_write(OUT / 'summary.csv', summaries)
    recommendations = []
    for pop in frozen['populations']:
        for mut in frozen['mutations']:
            group = [s for s in summaries if s['population']==pop and s['mutation']==mut]
            paired = [r for r in rows if r['population']==pop and r['mutation']==mut]
            recommendations.append(dict(population=pop, mutation=mut,
                mean_hv_instance_rank=statistics.mean(s['hv_instance_rank'] for s in group),
                mean_igd_instance_rank=statistics.mean(s['igd_instance_rank'] for s in group),
                mean_hv_seed_rank=statistics.mean(r['hv_seed_rank'] for r in paired),
                median_seconds=statistics.median(r['seconds'] for r in paired)))
    recommendations.sort(key=lambda r:(r['mean_hv_instance_rank'],r['mean_igd_instance_rank'],r['population'],r['mutation']))
    csv_write(OUT / 'configuration_ranks.csv', recommendations)
    chosen = recommendations[0]
    recommendation = dict(population_size=chosen['population'], mutation_probability=chosen['mutation'],
        crossover_probability=.9, max_evaluations=8000,
        regime='generational_with_partial_final_batch', eliminate_duplicates=False,
        criterion=frozen['selection_rule'], rankings=recommendations,
        status='pilot_recommendation_no_solver_default_changes',
        protocol_sha256=digest(OUT/'protocol.json'), summary_sha256=digest(OUT/'summary.csv'))
    atomic_json(OUT / 'recommendation.json', recommendation)
    pre = json.loads((OUT/'preflight.json').read_text())
    total_seconds = sum(r['seconds'] for r in rows)
    envelope_note = ('O envelope operacional foi ampliado de 60 para 90 min antes da primeira busca completa, sem mudar a matriz (evidências originais e emenda preservadas). '
                     if (OUT/'preflight_amendment.json').exists() else 'Envelope operacional: 90 minutos. ')
    text = ['# Piloto AGE-MOEA', '',
        f"Recomendação: **população {chosen['population']}, crossover 0,9, mutação {chosen['mutation']} e 8.000 avaliações**. "
        'Regime geracional, duplicatas permitidas e filtragem exata final. Defaults do solver não foram alterados.', '',
        '## Protocolo', '',
        '72 buscas: 25/50/100 × mutação 0,1/0,3 × seeds 11/29/47 × quatro entradas. '
        'Crossover 0,9; 576.000 tentativas. As seeds finais 101/211/307/401/503/601/701/809/907/1009 não foram utilizadas. '
        'Entradas: 6 original, 14 derivada (explicitamente), 50 e 250 originais, preservando o recorte dos pilotos anteriores. '
        'Sem comparações entre algoritmos ou acesso aos resultados oficiais.', '',
        'A matriz e o critério foram fixados antes das buscas em `protocol.json`: menor rank médio de HV mediano '
        'por instância; desempate por rank IGD+, população e mutação menores. Ordem determinística com rotação '
        'de configurações. Fontes, entradas, ambiente e outputs têm hashes.', '',
        'HV usa reference (1,05; 1,05). A normalização externa reutiliza, somente por importação, os limites '
        'individuais exatos derivados da entrada de `final_comparison/normalization.py`, com assertions [0,1]², '
        'sem clipping e sem alterar escalas internas. IGD+ usa frente exata em 6 jobs e união Pareto exata de '
        'todas as frentes deste piloto nas outras três entradas, construída somente após as 72 buscas. '
        'Essas referências empíricas são limitadas e favorecem configurações que contribuem para a própria união.', '',
        '## Resultados e estabilidade', '',
        '| População | Mutação | Rank médio HV | Rank médio IGD+ | Rank médio HV por seed |',
        '|---:|---:|---:|---:|---:|']
    for r in recommendations:
        text.append(f"| {r['population']} | {r['mutation']} | {r['mean_hv_instance_rank']:.3f} | {r['mean_igd_instance_rank']:.3f} | {r['mean_hv_seed_rank']:.3f} |")
    text += ['', 'Configuração recomendada, medianas e faixas de três seeds:', '',
             '| Jobs | HV mediana [min–max] | IGD+ mediana | Frente mediana | Schedules distintos na população | Tempo mediano (s) |',
             '|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        if s['population']==chosen['population'] and s['mutation']==chosen['mutation']:
            n=Path(s['instance']).name.split('_')[0]
            text.append(f"| {n} | {s['hv_median']:.6f} [{s['hv_min']:.6f}–{s['hv_max']:.6f}] | {s['igd_plus_median']:.6f} | {s['front_size_median']:g} | {s['population_schedules_median']:g} | {s['seconds_median']:.2f} |")
    selected = [r for r in rows if r['population']==chosen['population'] and r['mutation']==chosen['mutation']]
    hv_wins = sum(s['population']==chosen['population'] and s['mutation']==chosen['mutation'] and
                  s['hv_median']==max(q['hv_median'] for q in summaries if q['instance']==s['instance']) for s in summaries)
    seed_wins = sum(r['hv']==max(q['hv'] for q in rows if q['instance']==r['instance'] and q['seed']==r['seed']) for r in selected)
    text += ['', f'A escolha obteve a melhor mediana de HV em {hv_wins}/4 entradas e o maior HV em {seed_wins}/12 blocos instância/seed (empates incluídos). '
             f"Seu rank por seed variou de {min(r['hv_seed_rank'] for r in selected):g} a {max(r['hv_seed_rank'] for r in selected):g}; não implica vitória uniforme.",
             '', '`metrics.csv` conserva resultados por seed, amplitudes normalizadas e diversidade de alocação, '
             'ordem, modo e espera na população e frente. `summary.csv` apresenta mediana, quartis, mínimo e máximo. '
             'O critério usa ranks por instância, evitando somar HV bruto entre instâncias. Sem testes de significância '
             'ou declaração de superioridade geral com somente três seeds.', '',
             '## Preflight, custo e Numba', '',
             f"Preflight: 9 buscas × 400 = 3.600 avaliações; estimativa conservadora {pre['estimated_pilot_search_seconds']/60:.1f} min, "
             f"margem 2× = {pre['conservative_allowance_seconds']/60:.1f} min. " + envelope_note +
             f"Soma real dos timers de busca: {total_seconds:.2f} s ({total_seconds/60:.2f} min).", '',
             f"No par frio/quente idêntico do preflight: {pre['observations'][0]['seconds']:.3f}s / {pre['observations'][1]['seconds']:.3f}s; "
             f"compilação medida por evento `numba:compile`: {pre['observations'][0]['compile_seconds']:.3f}s / {pre['observations'][1]['compile_seconds']:.3f}s. "
             'Os resultados exatos foram idênticos. Outras assinaturas podem compilar depois. '
             f"Na campanha sequencial em processo único foram registrados {sum(r['numba_compile_seconds'] for r in rows):.3f}s de compilação total. "
             'Timers incluem inicialização e instrumentação, excluem validações finais e escrita; não representam tempo puro de algoritmo. Sem isolamento exclusivo de CPU. '
             'Numba é obrigatório; não houve atualização de dependências.', '',
             '## Validação e limitações', '',
             f"72/72 buscas completas, todas com 8.000 chamadas reais independentes ao avaliador e contagem pymoo idêntica. "
             f"Viáveis: {sum(r['feasible'] for r in rows):,}; rejeitadas: {sum(r['rejected'] for r in rows):,}. "
             f"Revalidações internas pós-busca: {sum(d['post_search_validations'] for _,_,d in runs):,}; "
             f"revalidações independentes da população: {sum(r['independent_population_revalidations'] for r in rows):,}; "
             f"da frente exportada: {sum(r['independent_front_revalidations'] for r in rows):,} por passagem de análise. "
             'Todas as frentes têm schedules válidos, TEC inteiro/escala e Cmax consistentes, sem pares duplicados ou dominados.', '',
             'Nesta matriz, 8.000 é divisível por 25/50/100: nenhum lote parcial foi necessário; esse contrato permanece '
             'coberto pelos testes do solver. Duplicatas avaliadas consomem orçamento e podem limitar diversidade. '
             'A seleção nativa continua usando floats e o filtro exato posterior não recupera pontos perdidos. '
             'Limites externos podem comprimir diferenças de TEC; IGD+ empírico não certifica convergência à frente ótima. '
             'Uma entrada por escala, incluindo uma derivada, não caracteriza todo o benchmark.', '',
             '## Reprodução', '', '```bash',
             'python data/output/age/piloto/run_pilot.py preflight',
             'python data/output/age/piloto/run_pilot.py run',
             'python data/output/age/piloto/summarize.py',
             'python -m unittest discover -v', '```', '',
             'O preflight recusa sobrescrever evidência existente; para repetir do zero, use uma cópia do repositório '
             'sem os artefatos gerados do piloto. A etapa `run` retoma apenas resultados compatíveis com o protocolo, '
             'sem reexecutar células concluídas. Hashes do runtime e fontes precisam coincidir; tempos variam entre máquinas. '
             'Qualquer erro técnico interrompe a campanha; não altera o solver nem fabrica métricas.', '',
             'Recomendação preliminar no recorte avaliado. Para a futura comparação, congelar explicitamente esses '
             'parâmetros e protocolo em uma campanha nova, com seeds reservadas e referências consistentes, '
             'sem incorporar estes dados de tuning ao teste final. Nenhuma comparação oficial foi executada.']
    test_path = OUT/'tests.json'
    if test_path.exists():
        tested = json.loads(test_path.read_text())
        text += ['', f"Validação automatizada: {tested['tests_run']} testes aprovados pela suíte completa; "
                 'inclui os cinco testes específicos dos scripts de piloto e os contratos do AGE-MOEA. '
                 'Comandos e hashes registrados em `tests.json`.']
    (OUT/'relatorio.md').write_text('\n'.join(text)+'\n')
    audit = dict(status='validated', runs=72, search_evaluations=576000,
        source_sha256=frozen['source_sha256'],
        analysis_sha256=digest(Path(__file__)), protocol_sha256=digest(OUT/'protocol.json'),
        output_sha256={p.name:digest(p) for p in (OUT/'metrics.csv',OUT/'summary.csv',
            OUT/'configuration_ranks.csv',OUT/'recommendation.json',OUT/'references.json',OUT/'relatorio.md')})
    if test_path.exists():
        audit['tests_sha256'] = digest(test_path)
    atomic_json(OUT/'audit.json',audit)
    print(json.dumps(recommendation,indent=2))


if __name__ == '__main__':
    main()
