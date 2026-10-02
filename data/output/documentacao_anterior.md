# Documentação anterior consolidada

Registro histórico: os comandos ativos estão no README.md.

## docs/analise_metodos_exatos.md

# Análise completa dos métodos exatos

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

Comandos: python src/analysis_metrics.py --resume; python src/analyze_results.py; python -m unittest discover -s tests -v; gerarPDF com docs/build_function_guide.py usando runtime com ReportLab. Para continuar um solver incompleto já parado, usar--resume no diretório da rodada; guardar novo orçamento e workers. Não reexecutar launch/run_experiments no mesmo manifesto.


## docs/cpsat.md

# Método exato CP-SAT

O modelo em `src/exact-solutions/cpsat.py` resolve a **mesma região viável e os mesmos dois objetivos** do solver próprio em `custom_exact.py`. Para manter a instalação portátil e sem dependência de um `venv`, o OR-Tools é opcional e tem seu próprio arquivo de requisitos. No Git Bash, na raiz do repositório:

```bash
python -m pip install --user -r requirements-cpsat.txt
python src/exact-solutions/cpsat.py tests/fixtures --time-limit 10 --restart
python src/exact-solutions/cpsat.py data/input/set1/6_2_1439_3_S_1-9.dat --time-limit 60 --workers 8
```

O parâmetro `--time-limit` limita **cada chamada** do solver; zero significa sem limite. `--total-time-limit` acrescenta orçamento total por execução/instância, incluindo a construção de modelos após iniciar esse orçamento; as verificações são cooperativas. `--workers` e `--seed` controlam e registram a configuração. Cada ponto provado é salvo em `data/output/cpsat/<instância>.json`. `--resume` continua a partir do último limite de custo registrado, embora o solver recomece do início a chamada interrompida. `--restart` reinicia o relatório. Não há dependência de GPU. A [documentação oficial do OR-Tools](https://developers.google.com/optimization/install/python) descreve a instalação do pacote; a versão local usada foi 9.15.6755.

## Variáveis e restrições

Para cada job, máquina e modo, há uma variável binária de presença e um intervalo opcional com início e duração `ceil(processing[j][i]/v[l])`. Exatamente um par máquina/modo é escolhido por job. Intervalos da mesma máquina não se sobrepõem. O custo de cada opção é uma tabela de inteiros exatos indexada pelo início; ela usa `pi`, `lambda`, as tarifas e as janelas de ponta de cada dia, com a mesma escala inteira do backtracking.

Um circuito dirigido por máquina define a sequência dos jobs presentes. Uma aresta `j → k` impõe `início(k) ≥ término(j) + setup[i][j][k]`. Assim, o setup é exigido **entre jobs consecutivos**, sem impor indevidamente `setup[j][k]` a jobs que tenham outro job entre eles. O caso `06_reparable_setup.dat` testa especificamente essa distinção. `Cmax` é o maior término; `TEC` é a soma dos custos de processamento. `max_cost` permanece somente como normalizador na saída, igual ao solver próprio.

## Fronteira de Pareto exata

Cada iteração executa duas otimizações lexicográficas:

1. Com um teto de custo `ε`, prova o menor `Cmax` possível.
2. Com `Cmax` limitado ao ótimo recém-provado, prova o menor `TEC` possível.

O par resultante é não dominado. A iteração seguinte usa `ε = TEC − 1` em unidades inteiras escaladas, sem pular valores por arredondamento. O processo termina quando o próximo modelo é **comprovadamente inviável**. Só então `status=complete` e `pareto_proven=true`. Se uma chamada termina por tempo, `front` contém apenas pontos já provados; `candidate`, se presente, é uma solução viável provisória e **não** é apresentada como ponto provado. O relatório informa o status de cada chamada do solver. Os status `OPTIMAL`, `FEASIBLE`, `INFEASIBLE` e `UNKNOWN` seguem a [definição do CP-SAT](https://developers.google.com/optimization/cp/cp_solver).

Na primeira otimização, sem teto de custo e com objetivo makespan, as tabelas energéticas são adiadas. Isso mantém exatamente a projeção das escolhas viáveis e evita processamento irrelevante. O custo real é calculado das escolhas decodificadas, inclusive para candidato FEASIBLE; o zero auxiliar nunca é publicado como TEC. Todas as chamadas com limite de custo ou objetivo energia mantêm a modelagem completa. A equivalência dos modelos e as guardas são testadas nas seis fixtures. As iterações registram `energy_in_model`, branches, conflitos e bounds; versões anteriores podem não possuir esses campos.

## Comparação na instância de seis jobs

As execuções usaram a mesma instância, identificada pelo SHA-256 nos arquivos de `data/baselines/`. O backtracking foi interrompido, enquanto o CP-SAT concluiu a prova da fronteira. Esses tempos medem métodos e critérios de parada diferentes; não são um fator de aceleração controlado.

| Método | Tempo registrado | Resultado naquele ponto |
|---|---:|---|
| Backtracking CPU, antes da poda antecipada de setup | 1.111,18 s | 242.758.339 decisões, 223.388.972 folhas, nenhuma solução viável encontrada |
| CP-SAT, primeira execução, 8 workers, até 15 s por chamada | 50,59 s | Dois pontos provados; busca ainda incompleta |
| CP-SAT, após retomada, 8 workers, até 60 s por chamada | 1.141,53 s acumulados | **43 pontos provados**; 87 chamadas, a última `INFEASIBLE`; fronteira completa |

Os 43 pares `(Cmax, TEC)` exatos estão em `data/baselines/6_2_1439_3_S_1-9_cpsat_complete.json`. O primeiro é `(94, 242,2037755)` e o último `(220, 134,099428)`. Esse baseline preserva os pares, sem schedules. A execução própria em `data/output/epsilon_exact/6_2_1439_3_S_1-9.json` fornece schedules para os mesmos pares, reavaliados racionalmente. A execução CP-SAT detalhada de sete tarefas também está preservada. O relatório de análise distingue validação de pares e de escalonamentos.

O solver próprio permanece disponível para validar a modelagem. Os seis casos pequenos em `tests/fixtures/` têm fronteiras completas idênticas nos dois métodos e no oráculo exaustivo dos testes. Execute a bateria com `python -m unittest discover -s tests -v` depois de instalar o OR-Tools. Sem ele, os testes CP-SAT são ignorados, e os testes do solver próprio continuam funcionando.


## docs/custom_exact.md

# Solver exato próprio

`src/exact-solutions/custom_exact.py` é um solver exato próprio baseado em backtracking. Ele usa somente a biblioteca padrão do Python. Não lê resultados do CP-SAT, baselines ou soluções prévias: cada execução nova começa com uma fronteira de Pareto vazia.

No Git Bash, a partir da raiz do repositório:

```bash
python src/exact-solutions/custom_exact.py tests/fixtures --time-limit 0 --restart
python src/exact-solutions/custom_exact.py data/input/set1/6_2_1439_3_S_1-9.dat --time-limit 60 --progress-interval 10 --checkpoint-interval 30
python src/exact-solutions/custom_exact.py data/input/set1/6_2_1439_3_S_1-9.dat --resume --time-limit 60
```

`--time-limit 0` remove o limite. `Ctrl+C` e os limites de tempo/decisões salvam o estado em `data/output/custom_exact/`. O relatório mostra `status=complete` e `pareto_proven=true` **somente** após esgotar ou provar dispensável cada ramo. Enquanto isso, a fronteira mostrada é provisória: novos escalonamentos podem remover pontos anteriores. O checkpoint guarda a pilha de backtracking, as posições escolhidas e a fronteira já descoberta; `--resume` continua sem reutilizar resultados de outro método.

## Como a busca funciona

Cada job continua tendo as mesmas opções `X[i,j,h,l]=1` e os custos inteiros definidos em `problem.py`. A diferença é a forma de percorrer a árvore:

1. **Propagação de horários e setups.** Cada domínio é uma máscara de bits. Ao colocar um job, a busca remove dos demais os inícios que sobreporiam o processamento ou violariam a menor separação possível. Essa separação é pré-calculada com Floyd-Warshall: permite qualquer sequência intermediária e inclui a menor duração de cada intermediário. Continua segura mesmo quando uma inserção pode reparar o setup direto. Domínio vazio torna o ramo inviável.
2. **Escolha da próxima decisão.** Seleciona o job com menos opções restantes e testa primeiro as opções com término mais cedo. Isso muda a ordem da busca, **sem excluir** opções válidas, e ajuda a encontrar a primeira solução sem conhecimento prévio.
3. **Setup.** Um conflito entre jobs já escolhidos só é podado quando nenhum job restante poderia caber entre eles e reparar a adjacência. Na folha, o setup entre jobs consecutivos é conferido integralmente.
4. **Arquivo de Pareto.** Cada escalonamento viável encontrado atualiza os pontos não dominados. O arquivo começa vazio.
5. **Limites inferiores seguros.** Para um ramo parcial, `LB_Cmax` usa os términos já fixados e o menor término possível de cada job restante. `LB_TEC` soma o custo já fixado ao menor custo ainda permitido pelo domínio de cada job. Ignorar conflitos entre os jobs restantes torna esses limites otimistas. Um ramo só é podado por dominância se um ponto viável já descoberto for não pior em **ambos** os limites. Portanto, essa poda só entra em ação depois de a própria busca encontrar soluções.

6. **Capacidade das máquinas.** O limite de makespan considera também o processamento total mínimo dividido pelo número de máquinas e o processamento obrigatório em cada máquina. Jobs sem alternativa fora de uma máquina contribuem à carga obrigatória dela. Se essa carga não cabe no horizonte, o ramo é inviável.
7. **Dominância de horários em blocos.** Quando a fronteira muda, os candidatos ainda não visitados de cada nível são filtrados por máscaras de custo e horário. Para cada opção, somam-se seu custo e os mínimos otimistas dos outros jobs. Se um ponto conhecido domina custo e término otimistas, a subárvore é descartada antes de gerar folhas. O contador de combinações cobre esses descartes.

O solver nunca enumera todas as matrizes binárias 4D: escolher uma opção por job já impõe exatamente uma posição `X[i,j,h,l]=1` por tarefa. As podas atuam no produto dessas opções. Não se eliminam indiscriminadamente esperas ou modos lentos: ambos podem reduzir energia.

Essas regras preservam a exatidão. A busca não usa soluções iniciais de heurísticas ou do CP-SAT. Seus limites podem ser fracos em instâncias grandes; `status=incomplete` nunca significa que a fronteira inteira foi provada.

Os novos checkpoints usam `format_version=2`, pois candidatos e propagação mudaram. Checkpoints anteriores são recusados; para essas execuções, use `--restart`. O tempo acumulado agora inclui a preparação de cada retomada.

## Verificação e desempenho observado

Nas seis instâncias pequenas, o solver próprio e o CP-SAT produzem os mesmos valores completos da fronteira que o oráculo exaustivo dos testes. A tabela compara o solver próprio com a execução histórica da força bruta:

| Caso | Decisões da força bruta histórica | Solver próprio anterior | Solver próprio com novas podas |
|---|---:|---:|---:|
| Um job, dois modos | 6 | 6 | 2 |
| Setup assimétrico | 42 | 21 | 6 |
| Máquinas não relacionadas | 56 | 13 | 2 |
| Dois dias | 132 | 28 | 4 |
| Três jobs, máquinas e modos | 2.415 | 76 | 6 |
| Setup reparável por inserção | 110 | 22 | 7 |

No registro anterior de 15 segundos, o solver próprio encontrou 439.970 escalonamentos viáveis e manteve 7 pontos provisórios. Em uma nova execução de 15 segundos com todas as podas, examinou 3.995 decisões e apenas 24 folhas, todas viáveis, mantendo 8 pontos provisórios. Isso demonstra a redução de folhas visitadas, mas não prova aceleração proporcional nem conclusão da instância. Esses tempos não constituem um benchmark controlado. Nenhuma solução do CP-SAT foi carregada; os resultados provisórios ainda podem ser dominados pela fronteira completa.

Execute a bateria de regressão com `python -m unittest discover -s tests -v`. Ela compara a fronteira do solver próprio com uma enumeração exaustiva restrita aos testes e verifica interrupção e retomada.


## docs/epsilon_exact.md

# Programação dinâmica própria e epsilon-restrição

`makespan_dp.py` encontra o menor makespan considerando todas as sequências e partições. Como todas as tarefas estão disponíveis em zero, o setup não depende do modo e energia não integra esse primeiro objetivo, usar o modo mais rápido e retirar ociosidade preserva o ótimo. O limite é de 16 tarefas.

`epsilon_exact.py` usa somente biblioteca padrão. Um estado de máquina é `(subconjunto, último job)`. Os rótulos guardam término e energia. Acabar antes com custo menor ou igual permite esperar e reproduzir qualquer continuação, logo rótulos dominados podem ser excluídos. Últimos jobs só são fundidos após completar a sequência daquela máquina.

Para cada extensão, o primeiro início permitido é considerado. Um início posterior só precisa ser explorado quando a energia cai estritamente. `next_cheaper` encontra esses inícios em tempo linear por grupo máquina/job/modo. O resultado não depende de tarifa de ponta ser maior que fora de ponta.

Depois das tabelas completas, para cada inteiro `epsilon` desde `Cmin` até `H`, uma segunda DP considera todas as partições e minimiza a energia com `Cmax <= epsilon`. Entre empates de energia, escolhe o menor makespan. Soluções repetidas e dominadas são removidas. A varredura completa prova todos os pontos Pareto discretos. Fixar `Cmax = epsilon` poderia introduzir espera e pontos dominados desnecessários.

O horizonte é `n_day*(hl+1)`, com intervalos `[start,end)`. Em set1, `H=1440`. A energia é inteira escalada exatamente; `tec_exact` preserva a fração. O normalizador `max_cost` não é teto de energia.

```bash
python src/exact-solutions/epsilon_exact.py data/input/set1/8_2_1439_3_S_1-9.dat --total-time-limit 300
python src/exact-solutions/epsilon_exact.py data/input/set1/8_2_1439_3_S_1-9.dat --resume --total-time-limit 300
```

A DP de energia é exponencial e limitada a 12 tarefas. A retomada mantém epsilons provados, mas reconstrói as tabelas; ela não salva tabelas parcialmente preparadas. O orçamento é cooperativo, com verificações entre operações. `front` só contém pontos provados da varredura; `candidate` pode guardar a sequência viável inicial sem prova da energia ótima. `pareto_proven=true` exige varrer até `H`.

Na primeira execução de seis tarefas, 1347 epsilons geraram 43 pontos em 22,265 s registrados, exatamente os pares racionais do baseline CP-SAT. Esse tempo histórico não constitui benchmark controlado. As novas execuções, seus parâmetros, estados e hashes estão no relatório de análise.


## docs/epsilon_milp.md

# DP do makespan e varredura MILP

## Execução

Na raiz do projeto:

```bash
python -m pip install -r requirements-milp.txt
python src/exact-solutions/makespan_dp.py data/input/set1
python src/exact-solutions/epsilon_milp.py data/input/set1/6_2_1439_3_S_1-9.dat --time-limit 60 --total-time-limit 300
python src/exact-solutions/epsilon_milp.py data/input/set1/6_2_1439_3_S_1-9.dat --resume --total-time-limit 300
```

O limite padrão é 60 s por chamada e 300 s por instância por execução, incluindo preparação. Zero remove o respectivo limite. O solver recebe o tempo restante da execução, embora preparação, escrita e overhead possam exceder ligeiramente o limite de parede. `--restart` substitui o resultado desse método; `--resume` mantém os valores já provados e repete o primeiro epsilon não resolvido. `--epsilon-max` permite uma varredura menor para experimentos. Nesse caso, `sweep_complete=true` não implica `pareto_proven=true` para o horizonte inteiro.

Os JSONs ficam em `data/output/makespan_dp/` e `data/output/epsilon_milp/`. Os resultados CP-SAT e backtracking não são lidos pelos novos solvers. Entradas com `hl=1439` mantêm 1440 intervalos; o último término admissível é 1440. Os intervalos de processamento são `[start, end)` e o último minuto de ponta declarado em `peak_end` está incluído.

## Etapa própria: programação dinâmica

Sem considerar energia, o modo de menor duração é sempre suficiente. Todas as tarefas estão disponíveis em zero; não há benefício em introduzir ociosidade. Para cada máquina `i`, subconjunto `S` e última tarefa `j`:

```
F(i, {j}, j) = d(i,j)
F(i, S, j) = d(i,j) + min_k [F(i, S-{j}, k) + setup(i,k,j)]
T(i,S) = min_j F(i,S,j); T(i,vazio) = 0
```

Depois, particionam-se as tarefas entre as máquinas, minimizando o máximo dos tempos `T`. A implementação reconstrói um escalonamento. Para duas máquinas a partição custa `O(2^n)`; calcular as sequências custa `O(m n² 2^n)`. Para mais máquinas a partição geral custa `O(m 3^n)`. O método tem limite explícito de 16 tarefas e destina-se ao `set1`; não deve ser usado no `set2` de até 750 tarefas. Ele não depende de desigualdade triangular dos setups.

## Etapa de biblioteca: MILP com SciPy/HiGHS

Para cada epsilon inteiro, do makespan mínimo até o horizonte, resolve-se:

```
min TEC
sujeito a: alocação única, sequência, setups e término de cada tarefa <= epsilon.
```

O custo de cada máquina/modo em função do início é pré-calculado com inteiros exatos. Sequências consecutivas de inícios cujo custo é afim são agrupadas. Para cada segmento `[a,b]`, uma binária `z` indica sua seleção e uma variável inteira `w` representa o início: `a*z <= w <= b*z`. O custo é `slope*w + intercept*z`. Exatamente um segmento de máquina/modo é escolhido por tarefa. A compressão é exata para todos os horários inteiros; não é uma aproximação das tarifas.

Arcos binários representam o sucessor imediato em cada máquina. Restrições de entrada/saída formam um caminho por máquina, que pode estar vazia. Cada arco ativo impõe `start(k) >= end(j) + setup(i,j,k)`. Durações positivas impedem ciclos entre tarefas. O big-M é `epsilon + setup(i,j,k)`. Assim, exige-se setup somente entre tarefas consecutivas, inclusive em entradas sem desigualdade triangular.

A energia é minimizada com `mip_rel_gap=0`. SciPy/HiGHS usa ponto flutuante e tolerâncias numéricas: não é um certificado de aritmética racional. A solução retornada é reconstruída e reavaliada com os inteiros exatos do projeto; são verificados alocação, sobreposição, setups, teto de makespan e energia. Para aceitar otimalidade, o bound deve também excluir a unidade inteira de custo imediatamente inferior, com margem de 0,25 na escala reduzida pelo MDC. Resultados com limite de tempo ou bound insuficiente são candidatos, não pontos provados.

O teto de energia da solução anterior é válido no epsilon seguinte e ajuda a limitar o MILP. Não há fixação da solução anterior nem relaxamento das variáveis inteiras.

## Fronteira, varredura e término

`sweep` tem uma linha para cada epsilon resolvido, inclusive nos platôs. O campo `makespan` é o término real da solução, que pode ser menor que epsilon. `front` mantém apenas pares não dominados e um escalonamento por par. Varredura inteira e consecutiva garante que nenhum makespan inteiro possível foi pulado. Se um solver interrompe, a execução para naquele epsilon; a retomada não pula o valor pendente.

Há uma redução adicional com prova: a soma do menor custo individual de cada tarefa é um limite inferior global de energia. Se uma solução viável atinge essa soma, todo epsilon maior permite a mesma solução e nenhum deles pode reduzir o custo. O programa registra cada epsilon restante com `proof=global_energy_lower_bound`, sem resolver MILPs redundantes. Os demais têm `proof=milp_optimal`. Número de linhas da varredura e número de chamadas ao solver podem diferir.

Uma interrupção preserva `candidate` quando houver solução viável, mas ela não é inserida em `front`. `pareto_proven=true` exige a varredura inteira até o horizonte, ou uma instância demonstrada inviável pela DP. O relatório registra tempos, limites, gaps, status, escala e hash da entrada.

## Testes e gráficos

```bash
python -m unittest discover -s tests -v
python -m pip install -r requirements-plot.txt
python src/plot_pareto.py
```

Os testes comparam a DP e cada epsilon do MILP com a enumeração exaustiva em seis instâncias, incluindo tarifas de dois dias e setup reparável por inserção. Também verificam reconstrução, máquinas adicionais, horizonte inviável, compressão de custos, resultado parcial e retomada. Os testes CP-SAT são opcionais e exigem `requirements-cpsat.txt`.

Referência da API: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html

## Verificação na instância oficial de seis tarefas

A execução local concluiu a varredura de 94 até 1440: 1347 limites registrados, 127 chamadas MILP (94 a 220) e 1220 limites certificados pelo limite inferior global de energia. Os 43 pares objetivos coincidiram exatamente, usando inteiros, com o baseline CP-SAT completo. O menor makespan foi 94 e a energia mínima 134,099428, atingida pela primeira vez em 220. Os escalonamentos estão no JSON local de saída. Isso verifica essa instância; não estabelece desempenho para os demais arquivos.
