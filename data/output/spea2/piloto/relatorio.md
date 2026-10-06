# Piloto experimental SPEA2 incremental

Resultados do SPEA2 fornecido pelo pymoo 0.6.2. O piloto foi executado sem baseline na busca. O algoritmo não foi alterado nesta etapa.

## Desenho

Quatro instâncias recuperadas do piloto VNS: 6, 14 (derivada), 50 e 250 jobs; seeds 11/29/47. Sensibilidade de população: 20/50/100 em orçamentos 2.000/8.000. Sensibilidade isolada dos operadores em pop 50 e orçamento 2.000: mutation 0.1/0.5 e crossover 0.6. Controle: crossover 0.9 e mutation 0.3. Regime SPEA2 incremental com `n_offsprings=1`.

Execuções: 108; tentativas totais: 432,000; rejeições: 0; avaliações viáveis: 432,000; `post_search_validations` dos sobreviventes: 5,880; reavaliações independentes da frente neste pós-processamento: 2,636. Soma dos tempos SPEA2: 979.9 s. Taxa de rejeição observada: 0.0%–0.0%.

## Sensibilidade de população e orçamento

Medianas sobre as três seeds. TEC mínimo está registrado por seed no `metrics.csv` como fração exata; a métrica de Cmax e TEC mínimo pode pertencer a soluções distintas.

| Instância | Pop. | Avaliações | Frente med. | Cmax mín. med. | TEC mín. med. | Rejeição med. | s med. | ms/avaliação | Aloc./ordem/modos distintos med. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14_2_1439_3_S_1-9_derivada.dat | 20 | 2000 | 20.0 | 205.0 | 125.272 | 0.0% | 1.42 | 0.71 | 7.0/18.0/18.0 |
| 14_2_1439_3_S_1-9_derivada.dat | 20 | 8000 | 20.0 | 205.0 | 96.703 | 0.0% | 5.69 | 0.71 | 10.0/18.0/15.0 |
| 14_2_1439_3_S_1-9_derivada.dat | 50 | 2000 | 44.0 | 203.0 | 134.880 | 0.0% | 2.00 | 1.00 | 11.0/33.0/35.0 |
| 14_2_1439_3_S_1-9_derivada.dat | 50 | 8000 | 50.0 | 203.0 | 97.408 | 0.0% | 7.97 | 1.00 | 11.0/38.0/42.0 |
| 14_2_1439_3_S_1-9_derivada.dat | 100 | 2000 | 30.0 | 207.0 | 138.707 | 0.0% | 3.22 | 1.61 | 11.0/25.0/29.0 |
| 14_2_1439_3_S_1-9_derivada.dat | 100 | 8000 | 100.0 | 207.0 | 100.873 | 0.0% | 13.45 | 1.68 | 11.0/52.0/84.0 |
| 250_10_1439_5_S_1-9.dat | 20 | 2000 | 11.0 | 371.0 | 2002.458 | 0.0% | 8.76 | 4.38 | 7.0/11.0/10.0 |
| 250_10_1439_5_S_1-9.dat | 20 | 8000 | 10.0 | 368.0 | 1786.843 | 0.0% | 33.03 | 4.13 | 6.0/9.0/10.0 |
| 250_10_1439_5_S_1-9.dat | 50 | 2000 | 8.0 | 365.0 | 1867.071 | 0.0% | 10.80 | 5.40 | 8.0/8.0/8.0 |
| 250_10_1439_5_S_1-9.dat | 50 | 8000 | 14.0 | 362.0 | 1739.157 | 0.0% | 37.38 | 4.67 | 11.0/14.0/14.0 |
| 250_10_1439_5_S_1-9.dat | 100 | 2000 | 13.0 | 367.0 | 1796.914 | 0.0% | 14.13 | 7.06 | 13.0/13.0/13.0 |
| 250_10_1439_5_S_1-9.dat | 100 | 8000 | 20.0 | 349.0 | 1674.095 | 0.0% | 43.94 | 5.49 | 13.0/19.0/20.0 |
| 50_10_1439_5_S_1-9.dat | 20 | 2000 | 14.0 | 69.0 | 328.015 | 0.0% | 2.84 | 1.42 | 7.0/13.0/13.0 |
| 50_10_1439_5_S_1-9.dat | 20 | 8000 | 18.0 | 69.0 | 263.546 | 0.0% | 11.02 | 1.38 | 6.0/17.0/18.0 |
| 50_10_1439_5_S_1-9.dat | 50 | 2000 | 12.0 | 67.0 | 292.720 | 0.0% | 3.63 | 1.82 | 7.0/11.0/11.0 |
| 50_10_1439_5_S_1-9.dat | 50 | 8000 | 19.0 | 67.0 | 242.683 | 0.0% | 13.64 | 1.70 | 6.0/16.0/18.0 |
| 50_10_1439_5_S_1-9.dat | 100 | 2000 | 13.0 | 67.0 | 279.647 | 0.0% | 5.71 | 2.86 | 13.0/13.0/13.0 |
| 50_10_1439_5_S_1-9.dat | 100 | 8000 | 22.0 | 65.0 | 241.102 | 0.0% | 20.96 | 2.62 | 10.0/21.0/22.0 |
| 6_2_1439_3_S_1-9.dat | 20 | 2000 | 20.0 | 94.0 | 134.099 | 0.0% | 1.28 | 0.64 | 5.0/9.0/16.0 |
| 6_2_1439_3_S_1-9.dat | 20 | 8000 | 20.0 | 94.0 | 134.099 | 0.0% | 4.90 | 0.61 | 5.0/7.0/16.0 |
| 6_2_1439_3_S_1-9.dat | 50 | 2000 | 29.0 | 94.0 | 134.099 | 0.0% | 1.98 | 0.99 | 3.0/6.0/22.0 |
| 6_2_1439_3_S_1-9.dat | 50 | 8000 | 39.0 | 94.0 | 134.099 | 0.0% | 7.67 | 0.96 | 4.0/5.0/29.0 |
| 6_2_1439_3_S_1-9.dat | 100 | 2000 | 22.0 | 94.0 | 148.293 | 0.0% | 3.35 | 1.67 | 3.0/6.0/20.0 |
| 6_2_1439_3_S_1-9.dat | 100 | 8000 | 38.0 | 94.0 | 134.099 | 0.0% | 14.52 | 1.81 | 5.0/9.0/28.0 |

### Leitura preliminar

* A população 20 deixa mais avaliações para evolução, enquanto 100 gasta 5% do orçamento de 2.000 ou 1,25% de 8.000 na população inicial, e aumenta o custo por avaliação devido à seleção/survival. As frentes frequentemente se aproximam do tamanho da população, em especial na instância derivada; pop 20 pode truncar a diversidade representável. Pop 50 é um compromisso provisório a confirmar pelas métricas pareadas, sem evidência de ótimo.
* A frente tende a aumentar entre os orçamentos maiores, mas os extremos variam por seed. A tabela pareada abaixo mede cobertura fraca da frente de 2.000 pela de 8.000 e quantas seeds melhoram cada extremo; a frente pode diminuir por survival limitado à população.
* Rejeição: nesta grade, os candidatos completos observados foram viáveis (taxa zero). Sampling construtivo e operadores não geraram inviabilidade observável nestas entradas/configurações; isso não prova taxa zero em outras instâncias ou seeds.
* Operadores: as mudanças observadas variam por instância e seed. Nenhuma das três variantes teve vantagem consistente suficiente para substituir os valores atuais; não se selecionou configuração por uma seed isolada.
* Não se viu colapso geral de diversidade: há variação de alocação, ordem e modos nas frentes. Ainda assim, a densidade/truncamento de `normalize=False` usa as unidades originais e a escala de TEC é numericamente maior que Cmax. Isso continua sendo risco metodológico; o piloto não instrumentou contribuições dimensionais do fitness e não permite concluir ausência de viés.
* O regime incremental mantém strength/raw fitness/density/tournament/survival do pymoo, mas atualiza a seleção a cada offspring. O piloto não o trata como equivalente ao SPEA2 geracional clássico.

#### Efeito do orçamento por população

Cobertura fraca = fração dos pontos de 2.000 dominados ou igualados por algum ponto de 8.000, na mesma seed. `Cmax/TEC melhoraram` conta quantas das três seeds melhoraram cada extremo.

| Instância | Pop. | Cobertura mediana | Seeds Cmax melhor | Seeds TEC melhor | Frente 2k→8k mediana |
|---|---:|---:|---:|---:|---:|
| 14_2_1439_3_S_1-9_derivada.dat | 20 | 75.0% | 1/3 | 3/3 | 20→20 |
| 14_2_1439_3_S_1-9_derivada.dat | 50 | 91.3% | 0/3 | 3/3 | 44→50 |
| 14_2_1439_3_S_1-9_derivada.dat | 100 | 100.0% | 0/3 | 3/3 | 30→100 |
| 250_10_1439_5_S_1-9.dat | 20 | 100.0% | 2/3 | 3/3 | 11→10 |
| 250_10_1439_5_S_1-9.dat | 50 | 100.0% | 2/3 | 3/3 | 8→14 |
| 250_10_1439_5_S_1-9.dat | 100 | 100.0% | 3/3 | 3/3 | 13→20 |
| 50_10_1439_5_S_1-9.dat | 20 | 100.0% | 0/3 | 3/3 | 14→18 |
| 50_10_1439_5_S_1-9.dat | 50 | 100.0% | 0/3 | 3/3 | 12→19 |
| 50_10_1439_5_S_1-9.dat | 100 | 100.0% | 1/3 | 3/3 | 13→22 |
| 6_2_1439_3_S_1-9.dat | 20 | 75.0% | 0/3 | 0/3 | 20→20 |
| 6_2_1439_3_S_1-9.dat | 50 | 100.0% | 0/3 | 1/3 | 29→39 |
| 6_2_1439_3_S_1-9.dat | 100 | 100.0% | 0/3 | 3/3 | 22→38 |

## Operadores

Medianas das três seeds por instância. Controle: pop 50, orçamento 2.000, mutation 0.3 e crossover 0.9.

| Instância | Variante | Frente | Cmax mín. | TEC mín. | Aloc./ordem/modos | s med. |
|---|---|---:|---:|---:|---:|---:|
| 14_2_1439_3_S_1-9_derivada.dat | crossover06 | 40 | 207 | 116.960 | 13/37/38 | 1.97 |
| 14_2_1439_3_S_1-9_derivada.dat | mutation01 | 40 | 208 | 145.698 | 11/25/26 | 1.98 |
| 14_2_1439_3_S_1-9_derivada.dat | mutation05 | 50 | 208 | 112.470 | 11/38/45 | 1.97 |
| 250_10_1439_5_S_1-9.dat | crossover06 | 11 | 365 | 1952.906 | 8/11/11 | 10.21 |
| 250_10_1439_5_S_1-9.dat | mutation01 | 12 | 374 | 1935.539 | 10/12/12 | 10.53 |
| 250_10_1439_5_S_1-9.dat | mutation05 | 12 | 370 | 1830.500 | 10/12/11 | 10.37 |
| 50_10_1439_5_S_1-9.dat | crossover06 | 11 | 67 | 298.968 | 4/9/11 | 3.58 |
| 50_10_1439_5_S_1-9.dat | mutation01 | 12 | 69 | 289.953 | 10/11/10 | 3.64 |
| 50_10_1439_5_S_1-9.dat | mutation05 | 11 | 67 | 274.665 | 6/11/11 | 3.69 |
| 6_2_1439_3_S_1-9.dat | crossover06 | 29 | 94 | 134.099 | 4/9/23 | 1.88 |
| 6_2_1439_3_S_1-9.dat | mutation01 | 17 | 94 | 150.530 | 3/4/17 | 1.82 |
| 6_2_1439_3_S_1-9.dat | mutation05 | 25 | 94 | 134.099 | 4/11/20 | 1.79 |

Resultados exatos pareados por seed em `operator_sensitivity.csv`.

## Baseline exato de 6 jobs (pós-busca)

Baseline completo/provado: 43 pontos. Medianas por configuração/orçamento:

| Configuração | Orçamento | Iguais medianos | Aproximados dominados medianos | Aproximados que dominam baseline (total) |
|---|---:|---:|---:|---:|
| crossover06 | 2000 | 16.0 | 16.0 | 0 |
| mutation01 | 2000 | 2.0 | 15.0 | 0 |
| mutation05 | 2000 | 11.0 | 19.0 | 0 |
| pop100 | 2000 | 3.0 | 19.0 | 0 |
| pop100 | 8000 | 24.0 | 14.0 | 0 |
| pop20 | 2000 | 9.0 | 11.0 | 0 |
| pop20 | 8000 | 12.0 | 8.0 | 0 |
| pop50 | 2000 | 12.0 | 16.0 | 0 |
| pop50 | 8000 | 29.0 | 11.0 | 0 |

Detalhe por seed em `baseline_6_jobs.csv`. Nenhum ponto aproximado dominou um ponto do baseline. O baseline não participou de sampling, seleção, operadores ou término.

## Comparação diagnóstica com VNS/VND

Medianas em pares com mesma instância, seeds 11/29/47 e orçamento. SPEA2 usa pop 50 e operadores controle.

| Instância | Avaliações | SPEA2 frente/Cmax/TEC | SPEA2 s/rejeição | VNS frente/Cmax/TEC | VNS s/rejeição |
|---|---:|---|---|---|---|
| 14_2_1439_3_S_1-9_derivada.dat | 2000 | 44/203/134.880 | 2.00/0.0% | 13/276/162.953 | 0.28/20.9% |
| 14_2_1439_3_S_1-9_derivada.dat | 8000 | 50/203/97.408 | 7.97/0.0% | 13/254/136.677 | 1.13/20.0% |
| 250_10_1439_5_S_1-9.dat | 2000 | 8/365/1867.071 | 10.80/0.0% | 4/1431/7904.474 | 4.59/39.3% |
| 250_10_1439_5_S_1-9.dat | 8000 | 14/362/1739.157 | 37.38/0.0% | 5/1431/7827.152 | 16.23/49.5% |
| 50_10_1439_5_S_1-9.dat | 2000 | 12/67/292.720 | 3.63/0.0% | 6/425/1189.667 | 1.45/11.8% |
| 50_10_1439_5_S_1-9.dat | 8000 | 19/67/242.683 | 13.64/0.0% | 7/410/794.591 | 5.77/14.3% |
| 6_2_1439_3_S_1-9.dat | 2000 | 29/94/134.099 | 1.98/0.0% | 10/119/146.505 | 0.19/21.1% |
| 6_2_1439_3_S_1-9.dat | 8000 | 39/94/134.099 | 7.67/0.0% | 14/115/134.099 | 0.78/21.3% |

`vns_comparison.csv` contém os dados por seed. São medidas preliminares, sem alegação de superioridade. A medição de tempo é local e inclui custos diferentes de algoritmo.

## Configuração e orçamento provisórios

Para a próxima comparação, usar provisionalmente `population_size=50`, `crossover_probability=0.9`, `mutation_probability=0.3`, seeds pareadas e `max_evaluations=8_000`. Pop 20 pode ser incluída como sensibilidade econômica; pop 100 aumenta custo e às vezes a frente disponível, sem ganho consistente suficiente para recomendá-la como padrão. O orçamento 2.000 serve para triagem; 8.000 é mais informativo. O piloto não justifica 20.000 sem uma pergunta aberta específica.

## Validação e artefatos

Todos os 108 arquivos de resultado foram reavaliados novamente pelo evaluator compartilhado (2636 schedules), com TEC exato, viabilidade, unicidade, não dominância e contagem de avaliações igual ao orçamento. Detalhes por execução em `metrics.csv`; agregados em `summary.csv`; operadores em `operator_sensitivity.csv`; comparação VNS em `vns_comparison.csv`; baseline em `baseline_6_jobs.csv`; schedules completos em `runs/`; parâmetros e hashes do runner em `manifest.json`.

A seleção SPEA2 usa `SPEA2Survival(normalize=False)` para evitar divisão por amplitude zero conhecida no pymoo 0.6.2. A densidade em escala bruta favorece distâncias numéricas dominadas por unidades de TEC; permanece risco metodológico e não foi alterada durante o piloto.
