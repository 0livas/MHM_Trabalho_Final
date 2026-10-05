# Piloto experimental VNS/VND — parâmetros provisórios

Foram executadas **108 buscas sequenciais, 270.000 avaliações**, com 218,963 s somados de tempo de busca. Nenhuma alteração foi feita no algoritmo, evaluator, dependências ou baselines. Todas as soluções finais foram reavaliadas, os objetivos exatos reproduzidos e as frentes verificadas quanto a dominância/duplicação. Não ocorreram conflitos com o baseline completo.

Ambiente: Python 3.10.12, Linux/WSL, Intel Core i5-14450HX. Versões e hashes dos três arquivos autoritativos estão em [manifest.json](manifest.json). As medições são `elapsed_seconds` de `run()`: incluem inicialização, avaliação, arquivo e trace; excluem leitura da instância, revalidação posterior e escrita JSON. As execuções perfiladas são separadas e não entram nas tabelas de tempo. São medições locais, sem isolamento de CPU, não benchmarks portáveis.

## Desenho experimental

| n | m | Instância | Papel |
|---:|---:|---|---|
| 6 | 2 | `set1/6_2_1439_3_S_1-9.dat` | Pequena; baseline completo de 43 pontos |
| 14 | 2 | `set1/14_2_1439_3_S_1-9_derivada.dat` | Maior set1 disponível; derivada, sem baseline completo correspondente |
| 50 | 10 | `set2/50_10_1439_5_S_1-9.dat` | Original maior, 5 modos |
| 250 | 10 | `set2/250_10_1439_5_S_1-9.dat` | Original grande, 5 modos; carga próxima do horizonte |

Triagem com 100 avaliações/seed 11: aproximadamente 0,011 / 0,019 / 0,090 / 0,356 s nas quatro instâncias. Isso permitiu incluir 250 tarefas sem tornar o piloto impraticável. As entradas de 750 tarefas não foram executadas: não eram necessárias para este piloto e o profiling já identificou crescimento quadrático na validação de sobreposição. Não se deve extrapolar a tabela como efeito puro de n: máquinas, modos, processamentos e setups também variam entre instâncias.

Seeds fixas: **11, 29, 47** em todas as configurações. Nove configurações, cada uma nas quatro instâncias e três seeds. As mudanças são isoladas em relação à referência; não há grade combinatória nem combinação otimizada. A biblioteca padrão executa o algoritmo pela mesma API usada pelo CLI. Baselines só são carregados após `run()` terminar.

| Configuração | Iniciais | Candidatos/chamada | Tentativas shaking | Avaliações |
|---|---:|---:|---:|---:|
| reference | 4 | 100 | 20 | 2,000 |
| initial_1 | 1 | 100 | 20 | 2,000 |
| initial_12 | 12 | 100 | 20 | 2,000 |
| candidates_25 | 4 | 25 | 20 | 2,000 |
| candidates_250 | 4 | 250 | 20 | 2,000 |
| shake_1 | 4 | 100 | 1 | 2,000 |
| shake_50 | 4 | 100 | 50 | 2,000 |
| budget_500 | 4 | 100 | 20 | 500 |
| budget_8000 | 4 | 100 | 20 | 8,000 |

O nome do limite no código/CLI é `max_candidates_per_neighborhood` / `--max-candidates-per-neighborhood`; `neighborhood_candidate_limit` é apenas o nome da coluna experimental. Mesma seed permite comparação pareada, mas mudanças em inicialização e amostragem também alteram o consumo da RNG; não representam trajetórias idênticas com apenas um efeito causal isolado.

## Resultados consolidados

Medianas de três seeds; o tamanho da frente inclui seu intervalo mínimo–máximo. Cmax mínimo e TEC mínimo podem pertencer a soluções diferentes. Tempo e rejeição não devem ser usados como substitutos de qualidade. A tabela completa por seed, incluindo parâmetros, avaliações viáveis/rejeitadas, spreads e hashes, está em [metrics.csv](metrics.csv), com cópia [JSON](metrics.json).

| n | Configuração | Viáveis/rejeitadas (med.) | Tempo s | Aval./s | Rejeição | Frente med. [min–max] | Cmax mín. | TEC mín. |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 6 | reference | 1579/421 | 0.193 | 10344 | 21.1% | 10 [4–11] | 119 | 146.505 |
| 6 | initial_1 | 1521/479 | 0.190 | 10510 | 23.9% | 8 [5–13] | 120 | 137.964 |
| 6 | initial_12 | 1566/434 | 0.188 | 10659 | 21.7% | 7 [7–15] | 104 | 151.606 |
| 6 | candidates_25 | 1767/233 | 0.196 | 10195 | 11.7% | 11 [7–13] | 119 | 146.505 |
| 6 | candidates_250 | 1569/431 | 0.189 | 10566 | 21.6% | 8 [7–11] | 115 | 146.505 |
| 6 | shake_1 | 1592/408 | 0.194 | 10321 | 20.4% | 10 [4–11] | 119 | 146.505 |
| 6 | shake_50 | 1573/427 | 0.193 | 10338 | 21.3% | 10 [4–11] | 119 | 146.505 |
| 6 | budget_500 | 394/106 | 0.049 | 10169 | 21.2% | 7 [6–9] | 135 | 170.313 |
| 6 | budget_8000 | 6298/1702 | 0.783 | 10213 | 21.3% | 14 [7–17] | 115 | 134.099 |
| 14 | reference | 1582/418 | 0.281 | 7113 | 20.9% | 13 [8–14] | 276 | 162.953 |
| 14 | initial_1 | 1584/416 | 0.282 | 7082 | 20.8% | 14 [14–16] | 282 | 147.004 |
| 14 | initial_12 | 1613/387 | 0.294 | 6794 | 19.4% | 14 [10–16] | 276 | 147.004 |
| 14 | candidates_25 | 1727/273 | 0.295 | 6791 | 13.7% | 12 [11–23] | 264 | 139.089 |
| 14 | candidates_250 | 1353/647 | 0.271 | 7391 | 32.4% | 11 [5–11] | 291 | 201.635 |
| 14 | shake_1 | 1569/431 | 0.284 | 7046 | 21.6% | 13 [4–14] | 276 | 162.953 |
| 14 | shake_50 | 1568/432 | 0.289 | 6932 | 21.6% | 13 [3–14] | 276 | 162.953 |
| 14 | budget_500 | 364/136 | 0.069 | 7290 | 27.2% | 10 [6–11] | 299 | 201.635 |
| 14 | budget_8000 | 6402/1598 | 1.133 | 7060 | 20.0% | 13 [13–17] | 254 | 136.677 |
| 50 | reference | 1763/237 | 1.448 | 1381 | 11.8% | 6 [5–17] | 425 | 1189.667 |
| 50 | initial_1 | 1738/262 | 1.448 | 1381 | 13.1% | 8 [8–16] | 419 | 1120.216 |
| 50 | initial_12 | 1719/281 | 1.472 | 1358 | 14.1% | 14 [3–20] | 375 | 1114.859 |
| 50 | candidates_25 | 1747/253 | 1.438 | 1391 | 12.7% | 6 [6–10] | 412 | 973.583 |
| 50 | candidates_250 | 2000/0 | 1.482 | 1350 | 0.0% | 2 [1–2] | 453 | 1497.565 |
| 50 | shake_1 | 1727/273 | 1.425 | 1404 | 13.7% | 5 [2–10] | 425 | 1200.788 |
| 50 | shake_50 | 1765/235 | 1.436 | 1393 | 11.8% | 9 [9–16] | 405 | 1204.461 |
| 50 | budget_500 | 500/0 | 0.382 | 1310 | 0.0% | 10 [6–14] | 425 | 1317.883 |
| 50 | budget_8000 | 6854/1146 | 5.774 | 1385 | 14.3% | 7 [3–11] | 410 | 794.591 |
| 250 | reference | 1214/786 | 4.594 | 435 | 39.3% | 4 [3–9] | 1431 | 7904.474 |
| 250 | initial_1 | 1161/839 | 4.462 | 448 | 41.9% | 3 [3–4] | 1438 | 8060.810 |
| 250 | initial_12 | 1475/525 | 5.193 | 385 | 26.2% | 6 [4–7] | 1431 | 7658.767 |
| 250 | candidates_25 | 1118/882 | 4.421 | 452 | 44.1% | 4 [3–4] | 1431 | 7865.664 |
| 250 | candidates_250 | 1371/629 | 4.974 | 402 | 31.4% | 4 [4–7] | 1431 | 7904.474 |
| 250 | shake_1 | 1208/792 | 4.672 | 428 | 39.6% | 3 [3–7] | 1431 | 7904.474 |
| 250 | shake_50 | 1307/693 | 4.634 | 432 | 34.6% | 4 [4–5] | 1431 | 7904.474 |
| 250 | budget_500 | 370/130 | 1.323 | 378 | 26.0% | 4 [3–4] | 1431 | 7904.474 |
| 250 | budget_8000 | 4037/3963 | 16.229 | 493 | 49.5% | 5 [3–7] | 1431 | 7827.152 |

### Custo e diversidade por tamanho — referência, 2.000 avaliações

| n | ms/avaliação | Frente med. | Alocações distintas med. | Sequências distintas med. | Vetores de modos distintos med. | Cmax mín.–máx. (medianas) | TEC mín.–máx. (medianas) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 0.097 | 10 | 2 | 2 | 8 | 119–208 | 146.505–200.332 |
| 14 | 0.141 | 13 | 2 | 2 | 8 | 276–326 | 162.953–185.193 |
| 50 | 0.724 | 6 | 1 | 2 | 6 | 425–435 | 1189.667–1373.212 |
| 250 | 2.297 | 4 | 2 | 3 | 4 | 1431–1440 | 7904.474–8132.722 |

O custo médio completo por avaliação cresce de 0,097 ms para 2,297 ms entre 6 e 250 tarefas (~24 vezes). Até 250 tarefas o custo absoluto permanece viável: 8.000 avaliações levaram 16,205–17,565 s. A taxa de rejeição pode reduzir o tempo médio porque a validação encerra antes; tempo menor não significa evaluator mais eficiente. A frente tem diversidade principalmente de modos nas instâncias de 6–50 tarefas; em 250, a diversidade e o spread de Cmax permanecem pequenos. Quantidade de pontos, isoladamente, não comprova qualidade ou convergência.

## Efeito dos hiperparâmetros

- **Iniciais (1/4/12):** uma única inicial piorou o Cmax mediano em 250 (1438 contra 1431) e o TEC (8060,810 contra 7904,474). Doze iniciais melhoraram vários extremos nas maiores: em 50, Cmax 375 contra 425 e TEC 1114,859 contra 1189,667; em 250, TEC 7658,767 e rejeição 26,2% contra 39,3%, mas tempo 5,193 contra 4,594 s. O ganho não é uniforme: em 6 o TEC mediano piora, e as frentes de 50 frequentemente são incomparáveis entre si. Não há base para declarar 12 universalmente melhor.
- **Candidatos (25/100/250):** 25 oferece melhor exploração inicial em vários casos. Em comparação pareada, cobre por dominância fraca uma fração média de 100% / 77% / 93% / 81% da frente da referência em n=6/14/50/250; a referência cobre 73% / 18% / 11% / 17% da frente com limite 25. As duas métricas incluem igualdade e não são teste estatístico. O limite 250 é claramente pior em 14 e 50 neste orçamento: a referência cobre 100% de suas frentes nas três seeds. Não há evidência de necessidade de crescer o limite com n. Em 250, 25 aumenta rejeição para 44,1%, ainda com tempo semelhante e TEC mediano um pouco menor. A comparação dos limites foi feita somente a 2.000 avaliações.
- **Shaking (1/20/50):** efeitos pequenos ou inconsistentes nos objetivos. Em 6 as frentes são idênticas nas seeds pareadas; em 50, 50 tentativas melhora o Cmax mediano, mas piora TEC frente à referência. Na referência a 2.000 avaliações houve somente 3 shakings bem-sucedidos por seed em n=6, e 1 em n=14/50/250. O VND consome a maior parte do orçamento. Aumentar o teto de tentativas não significa executá-las todas; a RNG também pode seguir outra trajetória. O piloto não demonstra ganho robusto de 50 nem que 1 seja suficiente quando o shaking for mais exercitado.
- **Orçamento (500/2.000/8.000):** a frente de 8.000 cobre 100% da frente de 2.000 nas comparações pareadas das quatro instâncias, como esperado para prefixos da mesma busca com arquivo elitista. Há melhorias visíveis nos dois extremos em 6/14/50, especialmente TEC em 50 (1317,883 → 1189,667 → 794,591). Em 250, Cmax mediano permanece 1431, e TEC melhora modestamente (7904,474 → 7904,474 → 7827,152); rejeição sobe para 49,5%. O tamanho da frente pode diminuir porque pontos antigos são dominados/removidos. Não há evidência de convergência nem motivo para gastar cegamente orçamentos maiores em 250.

Os valores de cobertura pareada por seed estão em [paired_coverage.csv](paired_coverage.csv). Definição: C(A,B) = fração de pontos de B para os quais existe um ponto de A que domina ou iguala, usando Cmax inteiro e TEC como fração exata. Não usa pesos nem soma dos objetivos.

## Baseline — somente pós-busca

O baseline de 6 tarefas tem 43 pontos, `status=complete` e `pareto_proven=true`. O SHA256 da instância foi confirmado em cada execução (`c27aafe109609de23235d989af5593c4ebdf9faaa365649ab21ec4a8c3f07cc4`). As comparações usam frações exatas, sem decisões por float. Todas as 27 execuções dessa instância ficaram iguais ou estritamente dominadas pela frente exata; **zero pontos aproximados dominam qualquer ponto do baseline**. Nenhum baseline foi consultado durante a busca.

| Configuração | Pontos iguais (seeds 11/29/47) | Estritamente dominados (11/29/47) | Cobertura do baseline mediana | Interseção/frente aproximada mediana |
|---|---|---|---:|---:|
| reference | 2/1/4 | 8/3/7 | 4.65% | 25.00% |
| initial_1 | 4/2/5 | 4/3/8 | 9.30% | 40.00% |
| initial_12 | 4/0/0 | 3/15/7 | 0.00% | 0.00% |
| candidates_25 | 2/3/4 | 11/4/7 | 6.98% | 36.36% |
| candidates_250 | 1/1/4 | 7/6/7 | 2.33% | 14.29% |
| shake_1 | 2/1/4 | 8/3/7 | 4.65% | 25.00% |
| shake_50 | 2/1/4 | 8/3/7 | 4.65% | 25.00% |
| budget_500 | 0/0/0 | 9/6/7 | 0.00% | 0.00% |
| budget_8000 | 6/1/8 | 11/6/6 | 13.95% | 35.29% |

Em 8.000 avaliações a cobertura é 2,33%–18,60% conforme seed (6/1/8 pontos iguais nas seeds 11/29/47), ainda limitada. Não existe baseline completo correspondente às outras três entradas escolhidas; seus ganhos são relativos às buscas do piloto, não distâncias ao ótimo.

## Gargalos e inviabilidade

Profiling `cProfile` separado: referência, seed 11, 1.000 avaliações por instância. Percentuais são tempos cumulativos divididos pelo cumulativo de `run`; chamadas aninhadas não devem ser somadas. O profiler altera o custo absoluto e estas porcentagens são diagnósticas.

| n | evaluate_schedule | energy_scale | overlaps_any | duration |
|---:|---:|---:|---:|---:|
| 6 | 93.5% | 52.3% | 3.1% | 10.7% |
| 14 | 94.3% | 34.8% | 6.0% | 16.2% |
| 50 | 95.8% | 50.3% | 8.4% | 13.0% |
| 250 | 95.7% | 14.2% | 35.4% | 17.3% |

O evaluator domina o custo (93%–96% no perfil). `energy_scale` é recalculado em toda avaliação e representa ~35%–52% nas instâncias de até 50 tarefas. Em 250 o principal bloco individual passa a ser `overlaps_any` (~35%); o perfil registra 21.805.625 verificações do gerador de pares em 1.000 avaliações. O código em `src/problem.py` compara pares mesmo em máquinas diferentes, explicando o crescimento quadrático. Há evidência concreta para priorizar uma medição/otimização isolada dessa validação caso se avancem para 750 tarefas; os tempos atuais não exigem essa mudança para prosseguir com os experimentos até 250. Nenhum cache ou otimização foi aplicado.

Diagnóstico adicional de trace, referência/seed 11/2.000 avaliações: em 250, N1 teve 482 rejeições/1580 avaliações (30,5%), N2 375/400 (93,8%), N3 7/15 (46,7%); N4/N5 não foram alcançadas antes do orçamento terminar. Em 50, N1 recebeu 1253 avaliações, N2 500 (237 rejeitadas), N3 239 e N4 apenas 3. As rejeições são violações do horizonte, e refletem também a composição de vizinhanças visitadas. Dados completos: [neighborhood_diagnostics.json](neighborhood_diagnostics.json). Esse diagnóstico usa somente uma seed, não deve ser generalizado como distribuição universal.

O alto descarte em N2 da instância de 250 e a ausência de exploração de N4/N5 justificam investigação experimental futura de geração de esperas/controle do VND. **Não provam que reparo seja a melhor solução**, nem que o algoritmo esteja incorreto. Antes de reparo sofisticado, é mais informativo comparar orçamento maior e taxa de rejeição por família em mais seeds. Não há bug identificado neste piloto.

## Recomendações provisórias

| Parâmetro | Recomendação | Evidência/limite |
|---|---:|---|
| initial_solutions | 4 | Referência equilibrada; 12 é uma alternativa de diversificação promissora em maiores, mas não uniforme entre seeds/objetivos. |
| neighborhood_candidate_limit | 25 | Configuração efetivamente testada com 4 iniciais/20 tentativas; bom resultado relativo nas quatro entradas a 2.000 avaliações, sem precisar crescer com n. Manter 100 como controle em orçamento maior. |
| shaking_attempts | 20 | Preservar teto atual até mais shakings serem exercitados; 50 não demonstrou benefício robusto. |

Esses valores são recomendações do relatório: **os padrões do algoritmo continuam 4/100/20**. A combinação sugerida 4/25/20 foi medida a 2.000 avaliações, mas não a 8.000; confirmar esse par de limites (25 versus 100) no orçamento futuro antes de congelar padrões. Não combinar automaticamente 12 iniciais e limite 25 como se essa combinação tivesse sido testada.

- **500 avaliações:** smoke test/triagem, inadequado como experimento de qualidade; cobertura exata zero em n=6 nas três seeds.
- **2.000 avaliações:** piloto rápido de sensibilidade e validação; útil para custo, mas frequentemente restrito ao primeiro VND nas maiores.
- **8.000 avaliações:** primeiro orçamento comum recomendado para comparações futuras entre meta-heurísticas; foi medido e ainda melhora as frentes. Faixa medida de tempo: <1 s em 6, ~1,13 s em 14, ~5,8 s em 50 e ~16–18 s em 250.
- **20.000 avaliações:** próximo ponto de confirmação, ainda não executado. Projeção linear aproximada: 2 s / 3 s / 14–15 s / 40–50 s nas quatro entradas. Não é evidência de ganho; parar de ampliar se a melhora por seed continuar pequena, especialmente Cmax em 250. Um experimento comparativo pode usar 8.000 e 20.000 com os mesmos orçamentos em todos os métodos.

Três seeds são suficientes apenas para sinal preliminar. O piloto cobre quatro entradas, mas uma por tamanho, sem intervalos de confiança ou teste de significância. A instância de 14 é derivada e não substitui diversidade de entradas originais. Não foram medidos outros regimes de tarifa (1–124), 20 máquinas ou 750 tarefas. Recomenda-se ampliar seeds e entradas no experimento final; não inferir qualidade global pelo tamanho da frente ou por extremos isolados. Não há hypervolume: não foi introduzido indicador complexo para este piloto.

**Decisão:** não há evidência que exija alterar o algoritmo antes de seguir. Há hotspots comprovados no evaluator e um problema experimental de baixa exploração do VNS sob orçamento curto nas maiores. Registrar esses pontos e validar orçamentos/limites antes de decidir sobre otimização, geração de candidatos ou reparo. Não houve tuning definitivo.

## Reprodução e artefatos

Executados: `PYTHONDONTWRITEBYTECODE=1 python data/output/vns_vnd/piloto/run_pilot.py`, `.../summarize.py` e `.../diagnostics.py`. O runner recusa repetir silenciosamente um piloto que já tem `metrics.csv`; para uma nova campanha, use outra pasta. Scripts e resultados completos permanecem em [runs/](runs/), além de [summary.csv](summary.csv), [diversity.csv](diversity.csv), [profiles.json](profiles.json) e `profile_{6,14,50,250}.txt`. Os JSONs preservam TEC exato e schedules, sem copiar baselines para a inicialização. O tempo dos scripts de análise não compõe o tempo de busca.
