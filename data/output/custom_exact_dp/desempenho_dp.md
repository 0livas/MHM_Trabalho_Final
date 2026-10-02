# Desempenho e ampliação da DP própria

Análise realizada em 02/10/2026. **11 e 12 tarefas concluíram a fronteira; 13 também concluiu; 14 atingiu o orçamento de memória antes da primeira prova de energia.** O teto padrão passa de 12 para 13, com 600 segundos e 1024 MiB. A decisão se apoia nos ensaios abaixo, sem garantir conclusão de qualquer entrada com 13 tarefas.

## Entradas e protocolo

Não existiam entradas originais de 11 e 12 tarefas no set1. Criamos a família aninhada `10…14_2_1439_3_S_1-9_derivada.dat`, a partir de `data/input/set2/50_10_1439_5_S_1-9.dat`: primeiras n tarefas; máquinas originais 0 e 1; modos originais 0, 2 e 4. Processamentos, setups, potências, tarifas e horizonte foram copiados. Velocidades: 1,2 / 1 / 0,8; fatores de potência: 1,5 / 1 / 0,6. São entradas derivadas locais, não instâncias publicadas do artigo. `max_cost` foi preservado como normalizador; comparamos TEC sem normalização.

Cada ensaio iniciou um processo novo, sem retomada, sem outro solver concorrente. Os ensaios de 10–12 precederam o de 13, que precedeu o de 14. Orçamento por ensaio: 600 segundos, 1024 MiB; teto de tarefas ampliado somente para o tamanho ensaiado. Uma medida por tamanho/versão: não há estimativa de variância nem evidência estatística de aceleração.

Máquina: AMD Ryzen 5 3500X, 6 núcleos/6 threads; aproximadamente 16 GiB de RAM; Windows 10.0.26200; Python 3.11.9. A DP usa somente biblioteca padrão. RSS e pico de RSS são do processo inteiro, incluindo Python, imports e alocador; leitura nativa `GetProcessMemoryInfo`. MiB = 2²⁰ bytes. Tempo de parede inclui makespan, opções, tabelas, varredura e gravação; CPU mede o consumo de CPU do processo. Outros aplicativos podem afetar tempo de parede.

Os valores sem arredondamento, hashes das entradas e do código estão em [desempenho.csv](desempenho.csv). Cada linha é uma execução; `elapsed_seconds` dos JSONs pode somar retomadas, enquanto `run_metrics` se refere à chamada atual. Estes ensaios não tiveram retomada.

## Medições após liberar o cache entre epsilons

| n | Parede (s) | CPU (s) | Pico RSS (MiB) | Preparação energia (s) | Rótulos finais | Pico rótulos por máquina | Pontos | Epsilons provados | Estado |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 10 | 24,843 | 23,094 | 98,293 | 18,234 | 101.274 | 355.902 | 114 | 1.328 | Completo |
| 11 | 76,156 | 64,188 | 170,227 | 54,516 | 238.222 | 869.098 | 142 | 1.316 | Completo |
| 12 | 178,859 | 168,875 | 342,254 | 152,500 | 554.988 | 2.133.555 | 175 | 1.298 | Completo |
| 13 | 468,313 | 456,469 | 797,801 | 412,359 | 1.359.092 | 5.521.805 | 252 | 1.252 | Completo |
| 14 | 292,344 | 291,578 | 1.024,016 | 290,359 | Não concluídos | 7.259.055 | 0 | 0 | Limite de memória |

O pico de 14 é 0,016 MiB acima do orçamento: a interrupção é cooperativa. A duração menor de 14 é tempo **até a interrupção**, não tempo para resolver a instância. `retained_subset_labels` não é exportado quando a preparação não conclui. Há um candidato viável de makespan mínimo no JSON de 14; seu custo não foi provado ótimo e não é publicado como baseline.

| n | Cmax mínimo provado | Maior Cmax da fronteira completa | Menor TEC | Arquivo completo |
| --- | ---: | ---: | ---: | --- |
| 10 | 113 | 370 | 54,084186733 | [resultado](10_2_1439_3_S_1-9_derivada.json) |
| 11 | 125 | 451 | 66,260957133 | [resultado](11_2_1439_3_S_1-9_derivada.json) |
| 12 | 143 | 494 | 72,200845133 | [resultado](12_2_1439_3_S_1-9_derivada.json) |
| 13 | 189 | 615 | 89,872011933 | [resultado](13_2_1439_3_S_1-9_derivada.json) |

A varredura cobre todos os inteiros do Cmax mínimo até 1440, inclusive, mesmo quando vários epsilons devolvem o mesmo par. Por exemplo, para n=13, são 1440−189+1 = 1252 subproblemas, mas somente 252 pontos distintos não dominados. Os baselines completos de 6–10 originais e 10–13 derivados estão em `data/baselines/`, com escalonamentos e hashes. 14 não possui baseline completo.

## O que é contado como rótulo

A DP de energia prepara estados por máquina, subconjunto de tarefas e última tarefa. Um rótulo guarda término, energia e referência ao predecessor para reconstrução. Um estado pode manter várias alternativas: uma termina antes e outra consome menos. A dominância descarta alternativas que não ajudam nenhuma continuação do mesmo estado; espera permite uma alternativa anterior reproduzir um horário posterior quando necessário.

| n | Transições | Inserções acumuladas | Rejeições de inserção | Rótulos removidos por dominância |
| --- | ---: | ---: | ---: | ---: |
| 10 | 6.749.427 | 1.721.026 | 5.028.401 | 1.125.035 |
| 11 | 19.477.824 | 4.772.662 | 14.705.162 | 3.254.837 |
| 12 | 54.650.043 | 12.492.577 | 42.157.466 | 8.693.060 |
| 13 | 158.346.606 | 32.115.991 | 126.230.615 | 22.124.602 |
| 14, parcial | 114.782.208 | 24.711.894 | 90.070.314 | 17.452.840 |

`transitions` conta tentativas de extensão por uma tarefa/modo na preparação; não conta todos os horários descartados implicitamente pela busca nos prefixos de tarifa, nem o trabalho da DP de makespan/partição por epsilon. `inserted_labels` é acumulativo; inclui rótulos removidos depois. `rejected_labels` conta candidatos cuja inserção falhou por dominância/igualdade. `removed_labels` conta rótulos substituídos após uma inserção melhor. Nestes ensaios, inseridos + rejeitados = transições.

`peak_active_state_labels` é o maior somatório dos rótulos nos estados (subconjunto, última tarefa) **de uma máquina durante sua preparação**. Não é o total de objetos Python vivos nem a soma dos picos de todas as máquinas. `machine_state_labels` registra os tamanhos finais antes da fusão de estados. `retained_subset_labels` é a soma das listas finais por subconjunto de todas as máquinas, depois de fundir as últimas tarefas. Referências de predecessor podem manter ancestrais vivos; nenhum desses contadores mede sozinho a memória do processo. RSS é a medida usada para decidir o orçamento.

De 11 para 12, os rótulos finais multiplicaram por 2,33, as transições por 2,81, RSS por 2,01 e tempo de parede por 2,35. De 12 para 13, rótulos finais multiplicaram por 2,45, transições por 2,90, RSS por 2,33 e tempo por 2,62. Isso justifica aumentar uma tarefa por vez; não permite extrapolar precisamente para outra família de instâncias. Um custo de estado por rótulo único também não pode ser deduzido dividindo RSS pelo contador final.

## Correção da retenção de memória

O combinador de máquinas usava uma função recursiva com `lru_cache` para cada epsilon. Sua referência recursiva formava um ciclo; tabelas de epsilons anteriores podiam permanecer até a coleta de lixo. Ao terminar a reconstrução, agora esvaziamos o cache e desligamos a referência recursiva, inclusive quando não há solução. Isso libera resultados de partição que o próximo epsilon não usa; as tabelas de energia continuam compartilhadas.

| n | Parede antes → depois (s) | Pico RSS antes → depois (MiB) | Situação anterior → posterior |
| --- | --- | --- | --- |
| 10 | 25,219 → 24,843 | 120,203 → 98,293 | Completo → completo, 114 pontos |
| 11 | 67,313 → 76,156 | 300,215 → 170,227 | Completo → completo, 142 pontos |
| 12 | 192,360 → 178,859 | 1.024,918 → 342,254 | Interrompido em 1058 epsilons → completo em 1298 |

As contagens de transições e rótulos na preparação permaneceram iguais. As fronteiras completas de 10 e 11 coincidiram exatamente antes/depois. Em 12, o ensaio anterior já havia encontrado 175 pontos, mas não havia concluído a varredura; o posterior certificou 175 pontos. A queda observada de memória em 12 foi aproximadamente 66,6%. O tempo de 11 aumentou; não apresentamos a mudança como aceleração universal. As comparações de 12 abrangem execuções de durações diferentes, pois uma foi interrompida.

Hashes do código medido: antes `7527b85dc354944bed37808ad1f7037369c84319746fbef2511e52d8dd5d36da`; após a correção `faebde9a91db3a4981f8991a7317ed7fe4f524cc3f5528bfb0b099061c0e4a10`. Depois dos ensaios, somente os padrões foram ajustados para 13/600/1024; código entregue `aee35f5f71362a4529d84ebf78e94d3a71e0c025905757ce0dc0c1a5ccc473d9`. Os parâmetros efetivos dos ensaios já eram 600 s/1024 MiB.

## Uso e decisão de ampliação

Executar da raiz: `python src/exact_methods/custom_exact_dp.py data/input/set1/13_2_1439_3_S_1-9_derivada.dat --profile --restart`. Para repetir o ensaio de 14, acrescentar `--max-jobs 14`. Não ampliar automaticamente ao set2: 50–750 tarefas estão muito além da escala medida. O usuário pode definir outro orçamento explicitamente; não foi demonstrada a conclusão de 14 com 2 GiB, nem foi testado 15.

Os limites de tempo/memória são cooperativos, verificados durante a preparação de energia a cada bloco de transições e entre epsilons. Não são limites impostos pelo sistema operacional. O cálculo inicial do makespan e a geração inicial de opções não são interrompidos por eles; uma partição de um epsilon ou uma gravação também pode ultrapassar o instante de verificação. O teto de tarefas evita iniciar por acidente entradas muito maiores. Retomar energia incompleta reconstrói suas tabelas; ampliar o orçamento é necessário quando a preparação já excede o anterior.

Uma execução completa prova os mínimos de energia para Cmax ≤ epsilon e, pela varredura e desempate por makespan, certifica a fronteira do **modelo/discretização implementados**. Interrupção preserva somente o que já foi provado e eventuais candidatos viáveis. Não certifica fronteira completa e não produz baseline. Comparação direta com números do artigo requer igualar instância, discretização e protocolo de obtenção dos pontos.

## Verificação e limpeza

A reorganização foi conferida com oito casos pequenos independentes (seeds 321–328), tarifas variadas e setups não triangulares: enumeração direta de 79.515 atribuições, com as fronteiras dos três métodos coincidentes. A fronteira original de seis tarefas da DP manteve seus 43 pontos. Foram reavaliados 869 escalonamentos no snapshot intermediário, calculando duração/energia com frações diretamente dos dados. O revisor independente conferiu adicionalmente os 683 escalonamentos dos baselines derivados de 10–13: tarefas únicas, horizonte, setups, makespan, custo exato e não dominância. Viabilidade e consistência dessas verificações não substituem a prova de completude do algoritmo.

O esboço [da representação](../representacao_solucao.md) inclui cinco alternativas didáticas com objetivos recalculados, pais, cruzamento de modos, mutação e seleção. Nenhuma heurística/metaheurística foi implementada. Os geradores dessa figura, relatórios e verificações foram retirados após manter os resultados. Não há Python/JSON na raiz; há cinco Python em `src` (três métodos, regras comuns, plotagem), um requirements e pastas futuras com `.gitkeep`. `.vscode` é configuração local ignorada e não integra o repositório; caches, logs e temporários também são ignorados.

Ao finalizar a limpeza, reavaliamos 1122 escalonamentos atuais, incluindo o candidato de 14, com frações e regras diretamente dos dados; todos foram válidos e puderam ser reconstruídos por sequências, modos e esperas residuais não negativas. Esses totais incluem soluções distintas de métodos diferentes; não somam novamente suas cópias nos baselines. O candidato de 14 tem Cmax mínimo 196, mas energia sem prova de otimalidade.

Resultados históricos foram consolidados, sem perder as métricas antigas, em `data/output/analise_metodos_exatos.json` e `documentacao_anterior.md`. O PDF e gráficos históricos permanecem como resultados; instruções atuais estão no README. Baselines antigos incompletos saíram da pasta de referências e permanecem no agregado histórico. O CP-SAT completo de seis tarefas foi movido para sua pasta de outputs; preserva seus 43 pares provados, sem inventar escalonamentos que não existiam nesse resumo.

## Avaliação em três rodadas com dois agentes

Os agentes `lean_structure_review` (A) e `benchmark_visual_review` (B) avaliaram a conformidade da entrega com a solicitação, em inspeções independentes e sem alterações no projeto. As notas são avaliações da entrega; não constituem prova matemática nem equivalem a uma nota atribuída pela disciplina.

| Rodada | Agente A | Agente B | Média | Providência |
| --- | ---: | ---: | ---: | --- |
| 1 | 8,3 | 8,4 | 8,35 | Corrigidas as pendências antes da rodada 2 |
| 2 | 9,7 | 9,7 | 9,70 | Sem correção material indicada; conferência final na rodada 3 |
| 3 | 9,7 | 9,7 | 9,70 | Entrega conforme, sem pendências materiais |

Na primeira rodada faltavam remover helpers/caches da raiz, produzir este relatório e a figura genética, retirar baselines incompletos da pasta de referências, gerar os novos plots e identificar comandos antigos como históricos. Todos esses pontos foram corrigidos. Na segunda, os dois agentes conferiram estrutura, padrões e evidências de desempenho; visualizaram a figura e recalcularam seus objetivos/dominâncias. Mantiveram a ressalva já documentada sobre uma medição por tamanho e uma única família derivada, sem problema material restante.

Na terceira rodada, ambos repetiram a conferência da entrega final e mantiveram 9,7/10, sem pendências materiais. A conferência de estrutura confirmou ausência de helpers, caches, logs e arquivos avulsos de verificação; a de desempenho/visual confirmou a parada correta de 14, a representação e seus cinco pares numéricos. A média final 9,70 supera o limiar de 9 definido pelo usuário. O detalhe opcional da moeda na linha de tarifa da figura não altera valores: R1/kWh e R3/kWh indicam R$ 1/kWh e R$ 3/kWh, explicitados no documento da representação.
