# Piloto AGE-MOEA

Recomendação: **população 50, crossover 0,9, mutação 0.3 e 8.000 avaliações**. Regime geracional, duplicatas permitidas e filtragem exata final. Defaults do solver não foram alterados.

## Protocolo

72 buscas: 25/50/100 × mutação 0,1/0,3 × seeds 11/29/47 × quatro entradas. Crossover 0,9; 576.000 tentativas. As seeds finais 101/211/307/401/503/601/701/809/907/1009 não foram utilizadas. Entradas: 6 original, 14 derivada (explicitamente), 50 e 250 originais, preservando o recorte dos pilotos anteriores. Sem comparações entre algoritmos ou acesso aos resultados oficiais.

A matriz e o critério foram fixados antes das buscas em `protocol.json`: menor rank médio de HV mediano por instância; desempate por rank IGD+, população e mutação menores. Ordem determinística com rotação de configurações. Fontes, entradas, ambiente e outputs têm hashes.

HV usa reference (1,05; 1,05). A normalização externa reutiliza, somente por importação, os limites individuais exatos derivados da entrada de `final_comparison/normalization.py`, com assertions [0,1]², sem clipping e sem alterar escalas internas. IGD+ usa frente exata em 6 jobs e união Pareto exata de todas as frentes deste piloto nas outras três entradas, construída somente após as 72 buscas. Essas referências empíricas são limitadas e favorecem configurações que contribuem para a própria união.

## Resultados e estabilidade

| População | Mutação | Rank médio HV | Rank médio IGD+ | Rank médio HV por seed |
|---:|---:|---:|---:|---:|
| 50 | 0.3 | 1.500 | 1.500 | 2.167 |
| 100 | 0.3 | 2.500 | 2.250 | 2.250 |
| 100 | 0.1 | 3.500 | 3.500 | 3.667 |
| 25 | 0.3 | 4.250 | 4.750 | 4.250 |
| 50 | 0.1 | 4.500 | 4.500 | 3.833 |
| 25 | 0.1 | 4.750 | 4.500 | 4.833 |

Configuração recomendada, medianas e faixas de três seeds:

| Jobs | HV mediana [min–max] | IGD+ mediana | Frente mediana | Schedules distintos na população | Tempo mediano (s) |
|---:|---:|---:|---:|---:|---:|
| 6 | 1.083078 [1.082903–1.083078] | 0.000421 | 39 | 41 | 2.10 |
| 14 | 1.051711 [1.050639–1.052822] | 0.002685 | 44 | 45 | 2.63 |
| 50 | 1.068819 [1.064997–1.070874] | 0.000830 | 28 | 34 | 8.28 |
| 250 | 0.936580 [0.932113–0.944411] | 0.002487 | 27 | 42 | 31.82 |

A escolha obteve a melhor mediana de HV em 3/4 entradas e o maior HV em 5/12 blocos instância/seed (empates incluídos). Seu rank por seed variou de 1 a 5; não implica vitória uniforme.

`metrics.csv` conserva resultados por seed, amplitudes normalizadas e diversidade de alocação, ordem, modo e espera na população e frente. `summary.csv` apresenta mediana, quartis, mínimo e máximo. O critério usa ranks por instância, evitando somar HV bruto entre instâncias. Sem testes de significância ou declaração de superioridade geral com somente três seeds.

## Preflight, custo e Numba

Preflight: 9 buscas × 400 = 3.600 avaliações; estimativa conservadora 41.8 min, margem 2× = 83.7 min. O envelope operacional foi ampliado de 60 para 90 min antes da primeira busca completa, sem mudar a matriz (evidências originais e emenda preservadas). Soma real dos timers de busca: 818.39 s (13.64 min).

No par frio/quente idêntico do preflight: 1.471s / 0.108s; compilação medida por evento `numba:compile`: 1.356s / 0.000s. Os resultados exatos foram idênticos. Outras assinaturas podem compilar depois. Na campanha sequencial em processo único foram registrados 1.458s de compilação total. Timers incluem inicialização e instrumentação, excluem validações finais e escrita; não representam tempo puro de algoritmo. Sem isolamento exclusivo de CPU. Numba é obrigatório; não houve atualização de dependências.

## Validação e limitações

72/72 buscas completas, todas com 8.000 chamadas reais independentes ao avaliador e contagem pymoo idêntica. Viáveis: 576,000; rejeitadas: 0. Revalidações internas pós-busca: 4,200; revalidações independentes da população: 4,200; da frente exportada: 2,145 por passagem de análise. Todas as frentes têm schedules válidos, TEC inteiro/escala e Cmax consistentes, sem pares duplicados ou dominados.

Nesta matriz, 8.000 é divisível por 25/50/100: nenhum lote parcial foi necessário; esse contrato permanece coberto pelos testes do solver. Duplicatas avaliadas consomem orçamento e podem limitar diversidade. A seleção nativa continua usando floats e o filtro exato posterior não recupera pontos perdidos. Limites externos podem comprimir diferenças de TEC; IGD+ empírico não certifica convergência à frente ótima. Uma entrada por escala, incluindo uma derivada, não caracteriza todo o benchmark.

## Reprodução

```bash
python data/output/age/piloto/run_pilot.py preflight
python data/output/age/piloto/run_pilot.py run
python data/output/age/piloto/summarize.py
python -m unittest discover -v
```

O preflight recusa sobrescrever evidência existente; para repetir do zero, use uma cópia do repositório sem os artefatos gerados do piloto. A etapa `run` retoma apenas resultados compatíveis com o protocolo, sem reexecutar células concluídas. Hashes do runtime e fontes precisam coincidir; tempos variam entre máquinas. Qualquer erro técnico interrompe a campanha; não altera o solver nem fabrica métricas.

Recomendação preliminar no recorte avaliado. Para a futura comparação, congelar explicitamente esses parâmetros e protocolo em uma campanha nova, com seeds reservadas e referências consistentes, sem incorporar estes dados de tuning ao teste final. Nenhuma comparação oficial foi executada.

Validação automatizada: 117 testes aprovados pela suíte completa; inclui os cinco testes específicos dos scripts de piloto e os contratos do AGE-MOEA. Comandos e hashes registrados em `tests.json`.
