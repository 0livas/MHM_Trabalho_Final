# Piloto experimental MOEA/D — síntese provisória

Execução do MOEA/D nativo do pymoo 0.6.2; algoritmo aprovado no release-check mantido sem alterações. Resultados diagnósticos de três seeds, não conclusões estatísticas nem tuning definitivo.

## Desenho e execução

Instâncias: `set1/6_2_1439_3_S_1-9.dat`, `set1/14_2_1439_3_S_1-9_derivada.dat`, `set2/50_10_1439_5_S_1-9.dat` e `set2/250_10_1439_5_S_1-9.dat`; seeds 11/29/47. Grade principal: P=20/50/100 × 2.000/8.000 avaliações. Sensibilidade isolada em P=50/2.000: n_neighbors 5/40 e mating global (probabilidade local 0); controle usa os defaults 20/0,9. Todos os casos mantêm crossover 0,9, mutation 0,3, sampling/crossover/mutation SPEA2, Tchebycheff e `Cmax/H`, `TEC/max_cost`.

Foram executadas 108 buscas principais e 432,000 tentativas, mais 3 confirmações seletivas de 60,000 tentativas (492,000 no total), com 6,030 validações pymoo pós-busca e 1,928 reavaliações independentes das frentes. Rejeições/fallbacks: 0 (0.000%). Cada execução atingiu exatamente seu hard cap. A duração inclui setup e busca e exclui as validações posteriores. Ambiente: Python 3.10.12, NumPy 2.2.6, pymoo 0.6.2; tempo acumulado da grade principal 669.9 s e da confirmação 231.0 s.

## Grade principal por população e orçamento

Cmax e TEC mínimos são extremos separados; `TEC med.` está arredondado para leitura, enquanto `metrics.csv` conserva a fração exata por seed. Diversidade `pop A/O/M/W` conta assinaturas distintas de alocação, ordem, modo e espera na população final. `ms/eval` usa tentativas, inclusive rejeições.

| n | P | Avaliações | Frente med. [min–max] | Cmax mín. med. | TEC mín. med. | s med. | ms/eval | pop A/O/M/W med. |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14 | 20 | 2,000 | 18 [18–19] | 210 | 129.966 | 0.90 | 0.448 | 9/19/16/2 |
| 14 | 20 | 8,000 | 20 [20–20] | 210 | 106.738 | 3.58 | 0.448 | 7/15/18/1 |
| 14 | 50 | 2,000 | 31 [17–33] | 210 | 126.180 | 0.88 | 0.441 | 9/18/30/4 |
| 14 | 50 | 8,000 | 44 [43–48] | 208 | 108.830 | 3.53 | 0.442 | 8/29/37/4 |
| 14 | 100 | 2,000 | 35 [30–38] | 206 | 129.919 | 0.90 | 0.451 | 7/27/35/3 |
| 14 | 100 | 8,000 | 68 [45–69] | 206 | 107.745 | 3.61 | 0.452 | 8/34/63/4 |
| 250 | 20 | 2,000 | 9 [5–11] | 378 | 2135.556 | 8.18 | 4.088 | 8/14/10/2 |
| 250 | 20 | 8,000 | 11 [8–13] | 375 | 2012.086 | 30.34 | 3.792 | 7/16/14/2 |
| 250 | 50 | 2,000 | 9 [8–9] | 376 | 2090.880 | 9.24 | 4.619 | 7/12/11/3 |
| 250 | 50 | 8,000 | 8 [7–8] | 375 | 1935.088 | 31.42 | 3.927 | 6/13/19/3 |
| 250 | 100 | 2,000 | 5 [3–5] | 377 | 2096.976 | 11.09 | 5.545 | 6/11/11/3 |
| 250 | 100 | 8,000 | 11 [10–16] | 374 | 1963.593 | 32.98 | 4.123 | 10/18/19/3 |
| 50 | 20 | 2,000 | 9 [7–12] | 72 | 313.997 | 2.34 | 1.169 | 7/11/13/2 |
| 50 | 20 | 8,000 | 14 [13–17] | 72 | 230.227 | 8.90 | 1.112 | 10/19/18/3 |
| 50 | 50 | 2,000 | 6 [4–7] | 73 | 324.703 | 2.55 | 1.276 | 6/9/15/2 |
| 50 | 50 | 8,000 | 17 [10–18] | 73 | 247.403 | 9.11 | 1.139 | 5/18/27/3 |
| 50 | 100 | 2,000 | 10 [8–14] | 70 | 299.655 | 2.88 | 1.441 | 8/20/23/1 |
| 50 | 100 | 8,000 | 15 [13–17] | 70 | 228.347 | 9.47 | 1.184 | 8/21/25/8 |
| 6 | 20 | 2,000 | 17 [15–18] | 94 | 134.099 | 0.73 | 0.366 | 4/9/12/1 |
| 6 | 20 | 8,000 | 17 [16–19] | 94 | 134.099 | 2.93 | 0.367 | 4/8/13/1 |
| 6 | 50 | 2,000 | 22 [20–22] | 94 | 134.099 | 0.73 | 0.365 | 5/12/17/1 |
| 6 | 50 | 8,000 | 28 [24–29] | 94 | 134.099 | 2.96 | 0.370 | 5/14/20/1 |
| 6 | 100 | 2,000 | 16 [16–26] | 95 | 134.913 | 0.73 | 0.366 | 4/12/17/2 |
| 6 | 100 | 8,000 | 32 [32–35] | 94 | 134.099 | 2.95 | 0.369 | 5/13/28/1 |

P=100 aumenta a quantidade de pontos/frontes e diversidade em várias células, com maior custo de replacement; não vence uniformemente. P=20 deixa menos trabalho na população inicial (1% de 2k; 0,25% de 8k), P=50 consome 2,5%/0,625% e P=100 5%/1,25%. P=50 é compromisso provisório entre tamanho de frente, diversidade e custo; 250 tarefas mostra casos em que P=20 ou 100 supera P=50.

## Sensibilidade a orçamento, vizinhança e mating

Coverage é a fração da frente-alvo dominada ou igualada pela outra frente, calculada por objetivos exatos; usa seeds pareadas e não é uma métrica de qualidade global.

| n | P | Coverage 8k por 2k (med.) | Coverage 2k por 8k (med.) |
|---:|---:|---:|---:|
| 6 | 20 | 43.8% | 66.7% |
| 6 | 50 | 41.4% | 95.5% |
| 6 | 100 | 17.1% | 100.0% |
| 14 | 20 | 5.0% | 72.2% |
| 14 | 50 | 2.3% | 88.2% |
| 14 | 100 | 1.5% | 100.0% |
| 50 | 20 | 7.1% | 88.9% |
| 50 | 50 | 5.6% | 75.0% |
| 50 | 100 | 0.0% | 100.0% |
| 250 | 20 | 0.0% | 100.0% |
| 250 | 50 | 0.0% | 100.0% |
| 250 | 100 | 0.0% | 100.0% |

Aumentar de 2k para 8k melhora TEC nas três seeds em 14, 50 e 250 tarefas; em 6 tarefas o TEC já estabilizou. Em 250, Cmax muda pouco e TEC continua a melhorar: P=50 reduz o TEC mínimo em cada seed, de aproximadamente 2.061/2.091/2.108 para 1.799/1.966/1.935. Por isso foi feita confirmação seletiva P=50/20k em três seeds. Cmax mínimo ficou idêntico ao de 8k nas três seeds; TEC mínimo caiu de 2.159e8/2.359e8/2.322e8 para 2.034e8/2.147e8/2.037e8 unidades exatas (~5,8%/9,0%/12,3%). A cobertura da frente 8k pela de 20k foi 87,5%/100%/100%; a frente 20k introduz novos pontos não dominados, sem reduzir schedules/população distintos. Cada execução levou ~76–77 s. É evidência de ganho adicional em TEC para n=250, não motivo para tornar 20k orçamento comum sem comparação pareada equivalente. Detalhes em `confirmation_metrics.csv` e `confirmation_paired.csv`.

Sensibilidade P=50/2k, medianas pareadas sobre quatro instâncias e três seeds:

| Variante | n_neighbors | Prob. local | Frente mediana | Rejeições | Leitura |
|---|---:|---:|---:|---:|---|
| neighbors05 | 5 | 0.9 | 12 | 0 | efeito varia por instância/seed; detalhes pareados em `sensitivity_paired.csv` |
| neighbors40 | 40 | 0.9 | 13 | 0 | efeito varia por instância/seed; detalhes pareados em `sensitivity_paired.csv` |
| mating_global | 20 | 0 | 11.5 | 0 | efeito varia por instância/seed; detalhes pareados em `sensitivity_paired.csv` |

Vizinhança 40 teve queda forte de diversidade/frente em alguns casos de 250 tarefas (1 ponto para seed 11), mas efeito não é consistente em outros tamanhos. Mating global teve frente e TEC piores que o controle em 250 nas três seeds; Cmax foi melhor em duas e pior em uma. Evidência favorece manter a vizinhança 20 e mating local 0,9 como provisórios, sem declarar ótimo.

## Diversidade, rejeições e escala

Não houve rejeições nas 108 execuções naturais; fallback ocorreu zero vezes, inclusive em 250 tarefas. Logo o piloto não observou perda de diversidade atribuível ao fallback. A população mantém em geral diversidade de schedules/modos maior que a frente; ordens e alocações ficam mais restritas nas instâncias grandes. Medianas por execução e por seed estão em `metrics.csv`.

Para P=50/8k, as faixas observadas sobre as três seeds são:

| n | Cmax/H | TEC/max_cost | bins Cmax (5) | bins TEC (5) |
|---:|---:|---:|---|---|
| 6 | 0.065–0.156 | 0.207–0.393 | [11, 9, 3, 0, 6]; [10, 8, 2, 0, 4]; [10, 9, 3, 0, 6] | [15, 4, 7, 1, 2]; [11, 5, 4, 3, 1]; [14, 5, 4, 3, 2] |
| 14 | 0.143–0.369 | 0.087–0.236 | [24, 12, 6, 4, 2]; [19, 14, 6, 3, 2]; [20, 13, 5, 3, 2] | [13, 23, 6, 3, 3]; [15, 20, 3, 3, 3]; [11, 20, 6, 3, 3] |
| 50 | 0.049–0.108 | 0.194–0.379 | [3, 3, 4, 3, 4]; [11, 4, 1, 0, 2]; [2, 3, 4, 0, 1] | [13, 0, 1, 1, 2]; [13, 3, 0, 1, 1]; [8, 1, 0, 0, 1] |
| 250 | 0.256–0.284 | 0.290–0.378 | [2, 1, 3, 0, 2]; [4, 3, 0, 0, 1]; [4, 1, 1, 0, 1] | [4, 2, 0, 0, 2]; [5, 0, 0, 0, 3]; [5, 0, 1, 0, 1] |

As directions distribuem pesos uniformemente, não pontos na frente. No n=50 e n=250, a amplitude observada de TEC/max_cost é cerca de três vezes a de Cmax/H em P=50/8k; isso pode concentrar a scalarização Tchebycheff e não garante cobertura uniforme. Não houve overflow, valores não finitos ou sinais de perda de ordenação; os divisores ficaram inalterados. A diferença de amplitude é limitação metodológica concreta para considerar em análises futuras.

## Comparação pareada preliminar

MOEA/D com P=50 contra SPEA2 (P=50, operadores 0,9/0,3) e VNS/VND (configuração de referência), mesma instância, seed e orçamento. Medianas de três seeds; o TEC por seed exato consta no CSV. Os tempos incluem overhead distinto de cada implementação e não constituem ranking de eficiência isolado.

| n | Orçamento | Algoritmo | Frente med. | Cmax mín. med. | TEC mín. med. | Tempo med. (s) | ms/eval med. | Rejeição med. |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 14 | 2,000 | moead | 31 | 210 | 126.180 | 0.88 | 0.441 | 0.0% |
| 14 | 2,000 | spea2 | 44 | 203 | 134.880 | 2.00 | 0.998 | 0.0% |
| 14 | 2,000 | vns | 13 | 276 | 162.953 | 0.28 | 0.141 | 20.9% |
| 14 | 8,000 | moead | 44 | 208 | 108.830 | 3.53 | 0.442 | 0.0% |
| 14 | 8,000 | spea2 | 50 | 203 | 97.408 | 7.97 | 0.997 | 0.0% |
| 14 | 8,000 | vns | 13 | 254 | 136.677 | 1.13 | 0.142 | 20.0% |
| 250 | 2,000 | moead | 9 | 376 | 2090.880 | 9.24 | 4.619 | 0.0% |
| 250 | 2,000 | spea2 | 8 | 365 | 1867.071 | 10.80 | 5.400 | 0.0% |
| 250 | 2,000 | vns | 4 | 1431 | 7904.474 | 4.59 | 2.297 | 39.3% |
| 250 | 8,000 | moead | 8 | 375 | 1935.088 | 31.42 | 3.927 | 0.0% |
| 250 | 8,000 | spea2 | 14 | 362 | 1739.157 | 37.38 | 4.673 | 0.0% |
| 250 | 8,000 | vns | 5 | 1431 | 7827.152 | 16.23 | 2.029 | 49.5% |
| 50 | 2,000 | moead | 6 | 73 | 324.703 | 2.55 | 1.276 | 0.0% |
| 50 | 2,000 | spea2 | 12 | 67 | 292.720 | 3.63 | 1.817 | 0.0% |
| 50 | 2,000 | vns | 6 | 425 | 1189.667 | 1.45 | 0.724 | 11.8% |
| 50 | 8,000 | moead | 17 | 73 | 247.403 | 9.11 | 1.139 | 0.0% |
| 50 | 8,000 | spea2 | 19 | 67 | 242.683 | 13.64 | 1.705 | 0.0% |
| 50 | 8,000 | vns | 7 | 410 | 794.591 | 5.77 | 0.722 | 14.3% |
| 6 | 2,000 | moead | 22 | 94 | 134.099 | 0.73 | 0.365 | 0.0% |
| 6 | 2,000 | spea2 | 29 | 94 | 134.099 | 1.98 | 0.991 | 0.0% |
| 6 | 2,000 | vns | 10 | 119 | 146.505 | 0.19 | 0.097 | 21.1% |
| 6 | 8,000 | moead | 28 | 94 | 134.099 | 2.96 | 0.370 | 0.0% |
| 6 | 8,000 | spea2 | 39 | 94 | 134.099 | 7.67 | 0.959 | 0.0% |
| 6 | 8,000 | vns | 14 | 115 | 134.099 | 0.78 | 0.098 | 21.3% |

MOEA/D fica entre VNS/VND e SPEA2 em tempo por avaliação na maior parte das células. Qualidade varia por instância: em 50/250 tarefas SPEA2 frequentemente acha menor Cmax, enquanto MOEA/D mantém desempenho competitivo em TEC e tamanho de frente. VNS/VND tem menos custo por avaliação, mas nos 250 jobs seus extremos são limitados pelo horizonte e rejeição mais alta. Isso é diagnóstico, não uma conclusão de algoritmo vencedor. Dados pareados completos: `comparison_paired.csv` e `comparison_summary.csv`.

## Baseline exato de 6 tarefas

Baseline completo de 43 pontos lido apenas depois das buscas; nenhum ponto aproximado dominou o baseline. Entre as frentes das 27 execuções de seis tarefas (grade principal mais sensibilidades), 229 ocorrências de pontos coincidiram exatamente com a frente e 328 foram dominadas por ela; zero conflitos. Contagens por execução estão em `metrics.csv`.

## Decisão provisória

Usar P=50, n_neighbors=20, mating local 0,9, crossover 0,9, mutation 0,3, Tchebycheff e escala aprovada para comparação inicial. Orçamento comum recomendado: 8.000 tentativas; 2.000 serve para triagem. P=100 é alternativa quando tamanho de frente/diversidade pesa mais, especialmente em n=14/50, e P=20 reduz custo por avaliação. Não há evidência de bug ou motivo para alterar o MOEA/D antes dos experimentos finais. A confirmação de 20k é seletiva e não altera o orçamento comum.

Riscos: três seeds e uma instância por escala não sustentam inferência estatística; referências uniformes não equilibram automaticamente amplitudes efetivas; o piloto não avaliou hipervolume nem convergência global.

Artefatos: `manifest.json`, `metrics.csv`, `summary.csv`, `paired_coverage.csv`, `sensitivity_paired.csv`, `comparison_paired.csv`, `comparison_summary.csv`, `summary.json`, `runs/` e os scripts `run_pilot.py`, `run_confirmation.py` e `summarize_pilot.py`.
