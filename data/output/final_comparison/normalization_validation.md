# Validação da normalização externa — emenda 1

Bounds calculados para todas as entradas antes de abrir qualquer schedule. Nenhum baseline lido. Escala interna dos algoritmos permanece inalterada; MOEA/D continua Cmax/H e TEC/max_cost.

## Fórmula e prova

dmin_j = min_{máquina,modo: d≤H} ceil(processing/speed). C_LB = max(max_j dmin_j, ceil(sum_j dmin_j/m)); C_UB = H. Qualquer job leva pelo menos dmin_j. Como jobs não sobrepõem por máquina e os setups/esperas são não negativos, sum_j dmin_j ≤ m*Cmax. A restrição do evaluator assegura Cmax≤H.

TEC_LB_units = sum_j min_{máquina,modo,start inteiro; 0≤start≤H-d} cost_units(j,m,l,start). TEC_UB_units = sum_j max das mesmas opções. Todo processamento de qualquer schedule viável é uma dessas opções. Seu custo individual está entre seus extremos; somar preserva ambas as desigualdades. A relaxação ignora coexistência, setups e precedências, mas não altera a fórmula energética nem a discretização. Setup/espera não cobram energia.

cost_units = peak_slots*on_price + (d-peak_slots)*off_price, usando energy_scale e interval_cost_units autoritativos. A função do start é contínua linear por trechos, com breakpoints inteiros a-d,b-d,a,b de cada pico [a,b). Os extremos ocorrem nesses breakpoints ou 0/H-d. A enumeração de todos os horários para cada duração distinta e ambas as ordenações de preços confirmou exatamente esses extremos em todas as entradas planejadas.

C_norm = (Cmax-C_LB)/(H-C_LB). TEC_norm = (tec_units-TEC_LB_units)/(TEC_UB_units-TEC_LB_units). Frações exatas até a conversão final. Denominadores positivos em todas as 17 entradas. HV e IGD+ usam o mesmo espaço. Dominância/deduplicação/coverage seguem Cmax inteiro e tec_units exato. max_cost continua parte da instância e da escala interna do MOEA/D.

## Bounds por instância

| Entrada | C_LB | C_UB | TEC_LB exato | TEC_UB exato | Escala TEC |
|---|---:|---:|---|---|---:|
| 10_2_1439_3_S_1-9.dat | 148 | 1440 | 92988301/500000 | 3612944227/4000000 | 60000000 |
| 6_2_1439_3_S_1-9.dat | 74 | 1440 | 33524857/250000 | 2822536571/4000000 | 60000000 |
| 7_2_1439_3_S_1-9.dat | 104 | 1440 | 367482147/2500000 | 618735621/800000 | 20000000 |
| 8_2_1439_3_S_1-9.dat | 105 | 1440 | 238386429/1250000 | 385223451/400000 | 10000000 |
| 9_2_1439_3_S_1-9.dat | 130 | 1440 | 971639777/5000000 | 4374700083/4000000 | 60000000 |
| 250_10_1439_5_S_1-124.dat | 197 | 4320 | 7117971167/7500000 | 113603575199/4000000 | 120000000 |
| 250_10_1439_5_S_1-9.dat | 193 | 1440 | 6365574593/7500000 | 136546790567/4000000 | 120000000 |
| 250_20_1439_5_S_1-124.dat | 57 | 2880 | 1211850139/1875000 | 4925292173/125000 | 120000000 |
| 250_20_1439_5_S_1-9.dat | 57 | 1440 | 1211850139/1875000 | 4925292173/125000 | 120000000 |
| 50_10_1439_5_S_1-124.dat | 36 | 1440 | 2173692329/15000000 | 27176853089/4000000 | 120000000 |
| 50_10_1439_5_S_1-9.dat | 36 | 1440 | 761968187/5000000 | 866096161/125000 | 120000000 |
| 50_20_1439_5_S_1-124.dat | 17 | 1440 | 354440219/3750000 | 30240208039/4000000 | 120000000 |
| 50_20_1439_5_S_1-9.dat | 17 | 1440 | 354440219/3750000 | 30240208039/4000000 | 120000000 |
| 750_10_1439_5_S_1-124.dat | 585 | 18720 | 46559182589/15000000 | 13485781471/125000 | 120000000 |
| 750_10_1439_5_S_1-9.dat | 583 | 2880 | 20669857921/7500000 | 172523041213/2000000 | 120000000 |
| 750_20_1439_5_S_1-124.dat | 178 | 8640 | 1272733991/750000 | 442348025003/4000000 | 120000000 |
| 750_20_1439_5_S_1-9.dat | 178 | 2880 | 1272733991/750000 | 442348025003/4000000 | 120000000 |

## Validação de schedules

| Origem | Entrada | Runs | Schedules | C_norm min–max | TEC_norm min–max |
|---|---|---:|---:|---|---|
| moead | 14_2_1439_3_S_1-9_derivada.dat | 27 | 838 | 0.025216706–0.327817179 | 0.009236973–0.213310262 |
| moead | 6_2_1439_3_S_1-9.dat | 27 | 557 | 0.014641288–0.112737921 | 0.000000000–0.211881885 |
| moead | 250_10_1439_5_S_1-9.dat | 30 | 249 | 0.138732959–0.199679230 | 0.025419144–0.046967030 |
| moead | 50_10_1439_5_S_1-9.dat | 27 | 284 | 0.020655271–0.101139601 | 0.009585569–0.052511953 |
| preserved_final | 250_10_1439_5_S_1-9.dat | 1 | 5 | 0.987971131–0.996792302 | 0.177471426–0.220053579 |
| spea2 | 14_2_1439_3_S_1-9_derivada.dat | 27 | 1159 | 0.024428684–0.378250591 | 0.001203591–0.208545792 |
| spea2 | 6_2_1439_3_S_1-9.dat | 27 | 730 | 0.014641288–0.111273792 | 0.000000000–0.199596830 |
| spea2 | 250_10_1439_5_S_1-9.dat | 27 | 349 | 0.123496391–0.226944667 | 0.022938527–0.046492460 |
| spea2 | 50_10_1439_5_S_1-9.dat | 27 | 398 | 0.020655271–0.093304843 | 0.011941756–0.042377542 |
| vns_vnd | 14_2_1439_3_S_1-9_derivada.dat | 27 | 323 | 0.051221434–0.686367218 | 0.024871332–0.258118450 |
| vns_vnd | 6_2_1439_3_S_1-9.dat | 27 | 247 | 0.016105417–0.107613470 | 0.000000000–0.199596830 |
| vns_vnd | 250_10_1439_5_S_1-9.dat | 27 | 121 | 0.987971131–1.000000000 | 0.196152103–0.239648147 |
| vns_vnd | 50_10_1439_5_S_1-9.dat | 27 | 226 | 0.174501425–0.430911681 | 0.078906758–0.234384849 |

Todos os schedules reavaliados estão em [0,1]². Portanto (1.05,1.05) é estritamente pior nas duas coordenadas, inclusive quando uma coordenada vale 1. Assertions verificam frações exatas, finitude, [0,1] e dominância estrita do reference point antes de cada cálculo geométrico.

## Aperto e precisão

Os extremos individuais podem não coexistir, portanto os bounds são relaxações e não ótimos globais. Um limite superior obtido somando escolhas caras pode ser frouxo, sobretudo em máquinas heterogêneas; isso comprime distâncias geométricas. Não se escolheu ou ajustou nenhum bound pelos resultados. A validade vale para qualquer solução viável. A validação dos pilotos é um diagnóstico de precisão, não tuning de escala. O menor passo inteiro normalizado de energia excede 100 ULPs de float em 1 em todas as entradas, preservando resolução suficiente antes das operações geométricas. Valores por entrada no JSON. Frentes observadas com spans estreitos podem representar diversidade limitada; não há colapso numérico devido à conversão.

## Emenda ao protocolo

Original: HV/IGD+ em Cmax/H e TEC/max_cost, reference (1.05,1.05). A primeira run revelou max_cost não ser upper bound de TEC; interrupção imediata após uma run, zero baselines lidos e zero métricas comparativas calculadas. Só a normalização externa é emendada, antes de retomar as outras 464 runs. Algoritmos, parâmetros, seeds, budgets e ordem não mudam. A primeira run será preservada byte a byte e não repetida. O histórico original permanece em history/original_protocol/.
