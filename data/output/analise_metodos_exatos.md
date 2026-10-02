# Análise completa dos métodos exatos

**Registro histórico de 01/10/2026.** Resultados e tempos abaixo pertencem ao snapshot indicado. Após a reorganização, nomes/caminhos antigos descrevem a estrutura da época; os comandos ativos estão no [README](../../README.md), as medições novas em [desempenho_dp.md](custom_exact_dp/desempenho_dp.md) e os JSONs históricos em [analise_metodos_exatos.json](analise_metodos_exatos.json). Não há processos antigos de backtracking ativos: os resultados finais e a trajetória foram preservados em `custom_exact/`.

Snapshot: 2026-10-01T00:08:30.738951-03:00 (America/Sao_Paulo). Escopo: implementação 1.

## 1. Conclusão e alcance

As três soluções são razoáveis e exatas para o modelo compartilhado: backtracking próprio com propagação, CP-SAT do OR-Tools e DP própria com epsilon-restrição. A DP de makespan é a primeira etapa da terceira solução. Os métodos próprios usam somente biblioteca padrão. O MILP anterior é complementar e não participa da comparação principal. Exatidão do algoritmo não implica conclusão dentro de qualquer orçamento: o backtracking permanece exponencial e só certifica a fronteira quando termina; as DPs limitam tarefas para evitar execução impraticável.

A eficiência foi demonstrada nas entradas pequenas do set1. CP-SAT e backtracking materializam até O(n*m*o*H) opções individuais; o circuito do CP-SAT usa O(m*n²) arcos, e o fechamento de separações do backtracking custa O(m*n³). Nas entradas grandes, memória e preparação também limitam esses códigos, além da busca combinatória. Não apresentamos as três implementações atuais como soluções práticas para 750 tarefas; as grandes entradas receberam métricas analíticas, não fronteiras exatas inventadas.

Foram removidos apenas artefatos vazios verificados e temporários de apresentação. Entradas, resultados, baselines, testes e checkpoints são necessários às análises e retomadas. Os arquivos complementares MILP e suas dependências têm finalidade histórica explícita.

## 2. Problema, convenções e conformidade com o artigo

Cada tarefa escolhe exatamente uma máquina, modo e início inteiro. Duração = ceil(processing/speed). Tarefas disponíveis em zero, sem preempção e sem setup inicial. Máquinas não relacionadas, setups dependentes da máquina e dos jobs consecutivos. O setup independe do modo. Processamento em [start,end); ponta informada inclusiva é convertida para [peak_start,peak_end+1). H=n_day*(hl+1), portanto H=1440 em set1 e vários dias em set2. Energia somente no processamento; setup e espera não cobram energia. O custo é avaliado com frações/inteiros escalados. max_cost normaliza TEC, sem restringir viabilidade.

Fontes locais: artigo-ideia-mhm-upms.pdf, pp.4-7 e 9-10; Atividade_01___MHM.pdf, pp.2-6. Esses documentos fundamentam o modelo; suas descrições não substituem o pedido do usuário. A imagem só nomeia as entregas e o relatório inicial não contém rubrica completa: as notas dos agentes avaliam a conformidade verificável, sem certificação de critérios pedagógicos não fornecidos.

A Eq.(4) do artigo aplica restrições entre pares e exige desigualdade triangular envolvendo setup e processamento (p.7). Nosso modelo aplica setup entre consecutivos diretamente. Condição suficiente verificada: S_i(a,b) <= S_i(a,v)+min_l d_i(v,l)+S_i(v,b), em trios distintos. Isso assegura que a cadeia de jobs intermediários também satisfaz a separação par-a-par. Nenhuma violação ocorreu nas cinco entradas set1. No set2 a condição não foi verificada; a correção operacional por adjacência independe dela. Não afirmamos reprodução literal daquela formulação nas entradas grandes.

| Tarefas | Trios/máquinas testados | Violações |
| --- | --- | --- |
| 6 | 240 | 0 |
| 7 | 420 | 0 |
| 8 | 672 | 0 |
| 9 | 1008 | 0 |
| 10 | 1440 | 0 |

O artigo admite a discretização em minutos no modelo, mas seus experimentos exatos usam sizeD=144, intervalos de dez minutos, onze pesos alpha=0,0.1,...,1 e limite 800*n*ln(m) segundos por peso (p.10). As execuções publicadas usaram C++/Gurobi7.0.2 e i7-4510U/16GB/Ubuntu19.10 (p.13). Usamos Python, minuto, epsilon-restrição e outro hardware. Comparações diretas de tempos, cardinalidade ou HV não medem uma reprodução equivalente. Soma ponderada pode perder pontos não suportados, portanto ter mais pontos não prova superioridade isoladamente. As tabelas/figuras do artigo são referência metodológica; reproduzi-las numericamente exige converter dados, grade, unidades, normalização e protocolo, com novos hashes.

## 3. Por que os três algoritmos são corretos

Backtracking: uma opção por tarefa já impõe as regras one-hot, e o domínio só inclui términos dentro de H. A propagação exclui sobreposição e separação mínima impossível. O fechamento de caminhos usa processamento mínimo dos intermediários e é otimista, inclusive para setups não triangulares. Uma lacuna só é excluída por setup irreparável se nenhum job futuro couber nela. Limites de carga e custo ignoram restrições adicionais e são inferiores seguros. Dominância usa apenas soluções viáveis encontradas pela própria busca, sem sementes dos outros métodos. Checkpoints preservam a pilha exata.

CP-SAT: intervalos opcionais, AddExactlyOne e AddNoOverlap modelam alocação e processamento. Um circuito por máquina representa consecutivos e permite máquina vazia. AddElement avalia o custo inteiro por início. A cada rodada minimiza makespan, depois energia com makespan <= ótimo encontrado; ambos precisam de OPTIMAL para arquivar o ponto. Decrementar a energia escalada em uma unidade exige melhora estrita sem erro de float. INFEASIBLE no próximo teto prova ausência de solução mais barata; não invalida as soluções anteriores. FEASIBLE e UNKNOWN deixam apenas candidato sem prova. O limite total, workers, seed, conflitos e branches agora são registrados; orçamento é cooperativo e pode ser ultrapassado por preparação/operação indivisível.

DP própria: para makespan isolado, modo mais rápido e ausência de espera são suficientes. A recorrência por máquina/subconjunto/último encontra a melhor sequência e a partição minimiza o máximo. Para energia, guarda todos os rótulos não dominados (end,TEC) de cada estado com último job. Um rótulo anterior e mais barato pode esperar e imitar qualquer continuação, por isso domina com segurança. Para o mesmo modo, um início posterior de custo igual ou maior também é dominado; next_cheaper salta apenas esses casos. Últimos jobs só se fundem quando a máquina terminou. A partição considera todos os subconjuntos disjuntos para cada epsilon. Limites:16 tarefas makespan,12 energia, com reconstrução das tabelas ao retomar.

Por que Cmax<=epsilon: epsilon é orçamento de prazo. Se a solução ótima de energia termina antes, ela continua admissível e não precisa de espera artificial. Minimizar energia para todos os tetos inteiros Cmin..H e manter os pares não dominados recupera toda fronteira discreta. Pontos repetidos são normais. A varredura DP faz todos os epsilons; CP-SAT usa epsilon no custo e salta entre pontos via otimizações lexicográficas.

## 4. Quantas possibilidades existem e quanto as regras reduzem

B=n*m*H*o células binárias: uma matriz irrestrita tem 2^B possibilidades. Isso inclui muitas matrizes sem sentido, como nenhum ou vários inícios para a mesma tarefa. Ao impor exatamente uma escolha por tarefa, o espaço torna-se A=(m*H*o)^n. Ao exigir término válido individual, D_j=sum_(i,l) max(0,H-d_jil+1); D=produto_j D_j. Nenhum dos três métodos enumera as 2^B matrizes. Células de início inválido equivalem a bits fixados em zero, não a jobs removidos.

| n | B | A (one-hot) | D (individual) | Redução A→D |
| --- | --- | --- | --- | --- |
| 6 | 51840 | 4.15989e+23 | 3.41058e+23 | 18.012652% |
| 7 | 60480 | 3.59414e+27 | 2.78368e+27 | 22.549458% |
| 8 | 69120 | 3.10534e+31 | 2.37053e+31 | 23.662802% |
| 9 | 77760 | 2.68301e+35 | 1.93713e+35 | 27.800159% |
| 10 | 86400 | 2.31812e+39 | 1.60468e+39 | 30.776579% |

O total F de escalonamentos que respeitam TODAS as regras é contado exatamente no set1, antes de qualquer dominância. DP de contagem C_i[S,last,end]: para anexar job j/modo l com término e, somar C_i[S,last,t] para t <= e-d_jil-S_i(last,j). Prefixos calculam essa soma. O estado vazio tem término0 e contagem1, sem setup inicial. Somar últimos/términos produz A_i(S); somar produtos A_i(S_i) sobre todas as partições disjuntas produz F. Modos distintos contam como opções distintas, mesmo com mesmo tempo/custo. Uma atribuição tem ordem única na máquina porque durações são positivas e não há sobreposição. Nenhum rótulo é descartado por dominância nessa contagem.

Verificação combinatória: para sequência/modos fixos, k jobs e carga L (processamentos+setups), a máquina admite binom(H-L+k,k) vetores de inícios, se L<=H. Esses vetores distribuem a espera antes e entre jobs; cauda livre fecha a contagem. Não há prova de ótimo por conhecer F: o melhor par ainda depende da energia.

| n | Sem sobreposição (exato) | Com setups F (exato) | Redução D→F |
| --- | --- | --- | --- |
| 6 | 2.04352e+23 | 1.93838e+23 | 43.165560% |
| 7 | 1.23514e+27 | 1.13661e+27 | 59.168594% |
| 8 | 8.70586e+30 | 7.81995e+30 | 67.011830% |
| 9 | 4.80383e+34 | 4.16595e+34 | 78.494247% |
| 10 | 2.69980e+38 | 2.25761e+38 | 85.931116% |

Inteiros completos, não arredondados, estão em search_space.json e search_space.csv. As razões de redução usam D como denominador na segunda tabela e A na primeira. Os testes conferem a contagem com enumeração nas seis fixtures, incluindo setups reparáveis e dois dias.

No set2, a contagem exata exponencial não foi executada. Calculamos A e D exatamente e um teto U para F usando pares disjuntos (0,1),(2,3),... sem sobreposição: escolhas em máquinas diferentes são compatíveis; na mesma máquina contamos analiticamente as duas ordens. Para inícios x em [0,A-1], y em [0,B-1], y>=x+g: t=min(A,max(0,B-g)); count=t*(B-g)-t*(t-1)/2. Multiplicar contagens de pares disjuntos (e o job restante, se houver) dá U. Ignorar setups e interações entre pares só amplia o conjunto, logo F<=U<=D. A redução reportada é pelo menos1-U/D, não uma estimativa de F. O teto depende do pareamento fixo declarado; não é necessariamente o melhor limite possível.

| Entrada | H | D | Teto U | Redução mínima D→U |
| --- | --- | --- | --- | --- |
| 50_10_1439_5_S_1-124 | 1440 | 1.32969e+242 | 1.12052e+242 | 15.730856% |
| 50_10_1439_5_S_1-9 | 1440 | 1.32962e+242 | 1.12049e+242 | 15.728763% |
| 50_20_1439_5_S_1-124 | 1440 | 1.44073e+257 | 1.32025e+257 | 8.362035% |
| 50_20_1439_5_S_1-9 | 1440 | 1.44073e+257 | 1.32025e+257 | 8.362035% |
| 250_10_1439_5_S_1-9 | 1440 | 3.08241e+1210 | 1.27144e+1210 | 58.751667% |
| 250_10_1439_5_S_1-124 | 4320 | 2.22858e+1332 | 1.66186e+1332 | 25.429250% |
| 250_20_1439_5_S_1-9 | 1440 | 6.03873e+1285 | 3.89751e+1285 | 35.458118% |
| 250_20_1439_5_S_1-124 | 2880 | 9.12605e+1362 | 7.33616e+1362 | 19.612907% |
| 750_10_1439_5_S_1-9 | 2880 | 1.22907e+3863 | 3.29767e+3862 | 73.169360% |
| 750_10_1439_5_S_1-124 | 18720 | 3.89680e+4477 | 3.18623e+4477 | 18.234816% |
| 750_20_1439_5_S_1-9 | 2880 | 6.82852e+4088 | 3.52842e+4088 | 48.328228% |
| 750_20_1439_5_S_1-124 | 8640 | 3.11347e+4450 | 2.49959e+4450 | 19.717019% |

O expoente de 2^B é preservado sem materializar esse inteiro enorme. Alguns produtos D têm mais de4300 dígitos; a exportação local permite esses inteiros. Casas científicas das tabelas servem para apresentação; CSV/JSON preservam o valor exato. Os horizontes multi-dia são calculados dos dados, sem inferir H pelo1439 no nome.

## 5. Resultados, certificações e eficiência observada

| Entrada | Método | Status | Pontos | Tempo s | ε da DP | HV/HV completo |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | cp_sat_epsilon_constraint | complete | 43 | 1141.529 | 0 | 1.000000 |
| 10 | cp_sat_epsilon_constraint | incomplete | 6 | 630.546 | 0 | 0.834634 |
| 8 | cp_sat_epsilon_constraint | incomplete | 16 | 630.344 | 0 | 0.916513 |
| 9 | cp_sat_epsilon_constraint | incomplete | 14 | 630.735 | 0 | 0.894408 |
| 6 | custom_exact_propagation | incomplete | 14 | 4095.250 | 0 | 0.791837 |
| 7 | custom_exact_propagation | incomplete | 17 | 3780.281 | 0 | 0.890563 |
| 10 | epsilon_exact_dp | complete | 97 | 103.391 | 1271 | 1.000000 |
| 7 | epsilon_exact_dp | complete | 41 | 40.875 | 1317 | 1.000000 |
| 8 | epsilon_exact_dp | complete | 57 | 54.844 | 1310 | 1.000000 |
| 9 | epsilon_exact_dp | complete | 86 | 62.453 | 1290 | 1.000000 |
| 7 | cp_sat_epsilon_constraint | complete | 41 | 1260.203 | 0 | 1.000000 |
| 6 | epsilon_exact_dp | complete | 43 | 22.265 | 1347 | 1.000000 |

A coluna epsilon da DP conta apenas os tetos de makespan resolvidos nessa varredura. Zero no CP-SAT não indica falta de prova: ele percorre limites de custo e certifica os pontos por outra enumeração.

Tempos são registrados localmente, com execuções concorrentes; não publicamos speedup controlado. Baselines históricos podem ter outro contexto. A execução CP-SAT histórica de6 levou1141,529s (~19,0min),87 chamadas e43 pontos completos. O backtracking histórico com apenas poda de sobreposição levou1111,176s (~18,5min), examinou223.388.972 folhas candidatas e encontrou zero escalonamentos válidos devido aos setups; terminou pelo orçamento, não provou inviabilidade. A DP própria histórica de6 concluiu43 pontos em22,265s. São observações, não um confronto de desempenho com protocolo igual.

As contagens e estados atuais foram verificadas racionalmente. O custo foi reavaliado a partir de potência, modo, tarifa e duração, junto com unicidade dos jobs, intervalos, horizonte e setups. Fronteiras completas da mesma entrada devem coincidir exatamente; pontos provados parciais devem pertencer à referência completa quando ela existe. Epsilons da DP devem ser contínuos e sua energia deve coincidir com o ótimo da referência. Baselines sem escalonamento são referências de pares, não recebem validação de schedule inexistente.

| Tarefas | Cmax mínimo | Maior Cmax Pareto | Menor TEC | Pontos completos |
| --- | --- | --- | --- | --- |
| 6 | 94 | 220 | 134.099428000 | 43 |
| 7 | 124 | 329 | 146.992858800 | 41 |
| 8 | 131 | 215 | 190.709143200 | 57 |
| 9 | 151 | 352 | 194.327955400 | 86 |
| 10 | 170 | 415 | 185.976602000 | 97 |

Limitação experimental adicional: nas cinco entradas set1, a primeira ponta começa no intervalo 1080 e todos os pontos da fronteira completa terminam antes dele. Assim, a troca entre makespan e TEC observada nesses casos decorre de máquinas, modos e durações, sob tarifa fora de ponta; esses dados não evidenciam um ganho por adiar processamento para outra tarifa. A implementação de tarifa variável é exercitada pelas fixtures e testes adversariais, inclusive ponta antecipada e preços invertidos. Os dados grandes com múltiplos dias exigiriam outro orçamento/escala de resolução para avaliar esse efeito em experimentos oficiais. Isso não invalida as fronteiras pequenas nem autoriza atribuir seus ganhos à tarifa de ponta.

HV usa o mesmo ponto estrutural por entrada: R_C=H+1; R_E=1+sum_j max_(i,l)[d_jil*pi_i*lambda_l*max_tarifa*24/slots_per_day]. Isso é pior que toda solução viável e independe do método. O HV é calculado racionalmente em2D; HV/HV_completo mede área relativa sob esse RP fixo, não uma probabilidade de sucesso. O RP do artigo para6,(250,239.91), não domina nosso ponto(94,242.2037755), portanto não reutilizamos seusHV sem adequar protocolo e referência.

## 6. O que o backtracking efetivamente reduziu

| n | Tempo s | Decisões | Folhas | Pontos provisórios | Cobertura D |
| --- | --- | --- | --- | --- | --- |
| 6 | 4095.2 | 1066682 | 69 | 14 | 0.002446192600% |
| 7 | 3780.3 | 3617571 | 118 | 17 | 0.002602440925% |

Para cada ramo eliminado, o contador usa o produto das quantidades originais dos jobs restantes. Isso representa subárvores brutas disjuntas da árvore adaptativa, incluindo opções que outras regras também rejeitariam. A atribuição do motivo é a primeira poda aplicada, não uma decomposição causal única. Identidade validada: cobertura=folhas+propagação+setup irreparável+dominância. O trabalho real é o número de decisões e folhas efetivamente examinadas. Dominância pode eliminar soluções viáveis que não acrescentam um ponto melhor; não é uma regra de inviabilidade. Toda poda depende do prefixo e da fronteira encontrada; a ordem pode alterar a eficiência.

| n | Combinações cobertas por regras | Combinações cobertas por dominância | Ainda não cobertas | Pontos dominados por referência |
| --- | --- | --- | --- | --- |
| 6 | 909775111847624596 | 7433180618770943553 | 341050481749058534399942 | 14 |
| 7 | 7421133951002765764387 | 65022718222023310867111 | 2783616188019182065310697664 | 17 |

Mesmo podando bilhões de combinações, o restante do produto continua gigantesco. Backtracking evita matrizes binárias inválidas desde a representação, mas uma árvore de inícios por minuto contém muitas permutações, atribuições e esperas. Limites inferiores separados de custo/makespan podem ser muito otimistas e o percurso inicial pode encontrar soluções longe dos extremos. Cobertura não indica percentual do Pareto, não permite extrapolar linearmente o tempo restante e não certifica completude. Não chamamos seus pontos provisórios de pontos Pareto globais.

Foram iniciadas duas retomadas independentes,6 e7 tarefas, com10800 segundos adicionais cada. Partiram dos próprios checkpoints, com375s e60s acumulados. Relatórios/checkpoints são copiados para a nova rodada e gravados a cada minuto; manifestos amostram evolução. Se o processo ainda estiver ativo no snapshot, as três horas são orçamento solicitado, não tempo já realizado. Manifestos possuem PIDs, horáriosUTC e status. Não se deve iniciar nova rodada sobre os mesmos arquivos enquanto esses processos estiverem ativos. Os dados de convergence.csv permitem avaliar HV e cardinalidade ao longo do tempo, com referência fixa.

## 7. Validação e auditorias independentes

A primeira auditoria matemática executou 13 testes do projeto com todas as bibliotecas presentes e 80 novos casos adversariais (seeds 1701..1780), 3 jobs, 1..3 máquinas, 2 modos e H entre 3 e 8. Sessenta casos tinham setups não triangulares e 24 eram inviáveis. Um oráculo independente enumerou 971.013 atribuições e calculou energia por slot sem o gerador compartilhado: as três soluções coincidiram; a DP foi verificada em cada epsilon. Após incluir métricas, recuperação de gravação e projeção do CP-SAT, 19 testes passaram integralmente. As quatro primeiras DPs pararam por PermissionError transitório do Windows durante os.replace; foram retomadas do último epsilon salvo após adicionar retry limitado, sem apagar o JSON anterior. Manifestos mantêm tentativas falhas e retomadas. Novas verificações e notas finais ficam em docs/avaliacoes_agentes.json.

Segunda rodada: conformidade 9,5/10, algoritmos 9,7/10 e experimentos 9,4/10. Os três agentes superaram o limiar solicitado. A auditoria matemática confirmou 160 contagens em 80 casos por sequências/modos e binomial, 80 tetos de pares por enumeração e os inteiros de ausência de sobreposição e viabilidade da entrada real de seis tarefas por procedimento independente. A auditoria experimental verificou 12 resultados e 413 schedules em seu snapshot, além de 58 amostras de HV não decrescente. Resultados posteriores ao snapshot desses agentes são validados pelo mesmo script; não são atribuídos retroativamente às auditorias.

Primeira rodada: conformidade8,4/10, algoritmos9,5/10, experimentos8,2/10. Correções: README/fluxo próprio, limites total/seed/branches CP-SAT, motivo de parada na retomada, contagem viável exata e limites grandes, CSVs com denominadores, referênciasHV válidas, metadados/convergência, novas entradas e validação racional. Essas alterações preservam as podas já corretas; modificar um algoritmo apenas para obter nota maior não seria justificável sem uma falha matemática ou gargalo demonstrado.

## 8. Reprodutibilidade, limpeza e próximos usos

Máquina: AMD Ryzen5 3500X,6cores/6threads, Windows10.0.26200; Python3.11.9, OR-Tools9.15.6755, Matplotlib3.10.3. SciPy1.16.0 é dependência apenas do experimento MILP antigo. ReportLab é usado no PDF. Manifestos preservam versões e comandos; results_summary.json preserva hashes dos códigos, e cada resultado possui hash do input. Horários fonte sãoUTC; o snapshot do relatório usaAmerica/Sao_Paulo.

Artefatos de análise: search_space.json/csv, results_summary.json/results.csv, convergence.csv, plots por entrada, manifestos, logs e checkpoints. O PDF agrega análise e catálogo de funções. Os arquivos temporários de renderização não constituem evidência experimental e podem ser removidos depois da inspeção visual. A rubrica completa da disciplina e uma reprodução convertida para a grade do artigo permanecem limites do alcance, não evidências de correção pendentes.

Os geradores, testes, logs e pastas de rodadas mencionados neste snapshot foram retirados na reorganização. Os comandos de execução atuais estão no [README](../../README.md). Baselines completos ficam em `data/baselines/`; resultados e checkpoints retomáveis em `data/output/<algoritmo>/`. Conteúdos de antigos `search_space.json`, `results_summary.json`, manifestos e `docs/avaliacoes_agentes.json` foram consolidados em [analise_metodos_exatos.json](analise_metodos_exatos.json), com seus caminhos originais como chaves. O PDF anterior foi preservado como documento histórico.
