# Roteiro de apresentação

**Escalonamento em máquinas paralelas não relacionadas**

**Duração ao vivo** 30:00 · **Idioma** português do Brasil

Os tempos indicam o momento de iniciar cada trecho na apresentação ao vivo. Avance quando o cronômetro chegar à próxima marca. As indicações entre colchetes reservam tempo para a animação, para apontar no gráfico ou para deixar a plateia observar. Os desenhos esquemáticos ensinam o mecanismo. As frentes, tabelas e contagens identificadas por instância vêm dos dados do projeto.

| Cena | Início–fim | Duração | Trechos e início de cada um |
| --- | --- | ---: | --- |
| `Abertura` | 00:00–02:00 | 02:00 | `pergunta` 00:00 · `objetivos` 01:05 |
| `Fundamentos` | 02:00–06:00 | 04:00 | `escalonamento` 02:00 · `formulacao` 03:15 · `pareto` 04:50 |
| `Exatos` | 06:00–09:20 | 03:20 | `cp_sat` 06:00 · `backtracking` 06:55 · `dp` 07:40 · `certificados` 08:35 |
| `Heuristicas` | 09:20–11:50 | 02:30 | `construtiva` 09:20 · `ociosidade` 10:15 · `comparacao` 11:10 |
| `Metaheuristicas` | 11:50–16:30 | 04:40 | `representacao` 11:50 · `spea2` 12:35 · `moead` 13:25 · `age` 14:20 · `vns` 15:15 |
| `Calibracao` | 16:30–19:00 | 02:30 | `protocolo` 16:30 · `busca` 17:10 · `selecionados` 17:40 · `execucao` 18:20 |
| `CasoVNS` | 19:00–22:10 | 03:10 | `instancia` 19:00 · `antes` 19:35 · `depois` 20:30 · `evidencia` 21:25 |
| `Metricas` | 22:10–25:40 | 03:30 | `hv` 22:10 · `purity` 23:20 · `eq36` 24:20 |
| `Resultados` | 25:40–29:00 | 03:20 | `dispersao` 25:40 · `portes` 26:50 · `discussao` 28:05 |
| `Fechamento` | 29:00–30:00 | 01:00 | `conclusao` 29:00 · `referencias` 29:40 |

## 00:00–02:00 · Introdução e objetivos

### 00:00 · `pergunta`

Imagine duas máquinas capazes de executar a mesma tarefa. Em uma delas, o processamento termina mais cedo. Na outra, o mesmo trabalho pode consumir menos energia. Agora acrescente uma tarifa que muda ao longo do dia. Adiantar a tarefa pode liberar a máquina mais cedo, mas também pode colocar o processamento na janela mais cara. Qual plano você escolheria? [Aponte para o ponto mais à esquerda e para o de menor custo.] Para responder, precisamos definir o que queremos dizer com “melhor”.

Rego e colaboradores formularam essa decisão para máquinas paralelas não relacionadas e estudaram o compromisso entre a conclusão da produção e o custo de energia sob tarifas por horário. A expressão “não relacionadas” indica que a duração depende do par tarefa–máquina. A ordem de preferência entre máquinas pode mudar de uma tarefa para outra. A pergunta fica mais interessante quando precisamos programar a fábrica inteira em vez de decidir uma tarefa por vez.

### 01:05 · `objetivos`

O objetivo geral do projeto é comparar quanto diferentes métodos conseguem avançar nos dois objetivos ao resolver as mesmas instâncias. Para isso, primeiro precisamos de uma referência certificada nos casos pequenos. Em seguida, vamos aproveitar a estrutura do problema para construir escalonamentos e investigar o efeito de incluir ociosidade voluntária. Por fim, vamos calibrar métodos de busca e confrontar a qualidade e a regularidade das frentes que eles devolvem.

A apresentação segue essa sequência de perguntas. As linhas de desenvolvimento se sobrepuseram. O histórico registra VNS/VND, SPEA2 e MOEA/D antes das duas heurísticas dedicadas, enquanto AGE-MOEA e a calibração vieram depois. Vamos passar primeiro pelo modelo, que é o ponto em comum entre essas linhas. [Aponte para os dois objetivos antes de avançar.]

**Fontes** Rego et al. (2022), DOI `10.7717/peerj-cs.844`. `README.md` e histórico Git, commits `f24ef25`, `b721688`, `e64dffe`, `b607620`, `648ea85`, `5f7410b`, `997910b` e `9004324`.

## 02:00–06:00 · Referencial teórico

### 02:00 · `escalonamento`

Leia o diagrama da esquerda para a direita. Cada faixa é uma máquina e cada bloco representa o processamento ininterrupto de uma tarefa. A largura de um bloco é a duração para aquela máquina e aquele modo. Entre dois blocos pode haver uma preparação, cujo tamanho depende da máquina, da tarefa anterior e da seguinte. Uma troca de ordem muda a preparação que precisamos realizar. O que sobrar entre o fim da preparação e o próximo bloco é espera voluntária.

[Aponte para o início e o fim de um bloco que cruza a faixa cara.] O custo depende dos intervalos que o processamento ocupa. Se ele cruza a fronteira da tarifa, uma parte é paga ao preço de ponta e a outra fora de ponta. A ociosidade pode reduzir a conta ao deslocar o trabalho para uma faixa barata. Ao mesmo tempo, atrasar um bloco pode empurrar o fim da última máquina. É esse possível conflito que vamos medir.

### 03:15 · `formulacao`

O indicador $X_{ijh\ell}$ vale um quando a tarefa $j$ começa no intervalo $h$, na máquina $i$, no modo $\ell$. Cada tarefa tem uma única escolha. A duração é o tempo-base $p_{ji}$ dividido pela velocidade $v_\ell$, arredondado para cima. As tarefas devem terminar dentro do horizonte $H$. Em cada máquina, os blocos não se sobrepõem e separam-se pelo setup entre sucessores imediatos.

[Acompanhe o cálculo de cada objetivo na tela.] O primeiro é $C_{\max}$, o maior término entre as máquinas. Para o custo total, TEC, percorra os intervalos de processamento. Em cada um, multiplique potência, fator do modo, tarifa e duração do intervalo em horas. Some todos os termos. Espera e preparação ocupam tempo no modelo, e o cálculo de energia incide sobre o processamento. O código representa custos em unidades inteiras. Minimizamos os dois objetivos.

O problema é NP-difícil mesmo com um só objetivo em um caso especial. Retire tarifas diferenciadas, setups e modos alternativos, e permita duas máquinas idênticas. Atingir o makespan igual à metade da carga total exige uma partição das tarefas em duas somas iguais. O caso completo ainda decide ordem, modo e instante de início.

### 04:50 · `pareto`

Cada ponto agora representa um escalonamento inteiro. Andar para a esquerda reduz o makespan e andar para baixo reduz o custo. [Aponte para um par dominado.] Um ponto domina outro se é pelo menos tão bom nos dois objetivos e é melhor em pelo menos um. Se um termina antes e o outro custa menos, nenhum dos dois elimina o outro. A fronteira guarda as alternativas que sobrevivem a essa comparação. Dois planos diferentes com o mesmo par de objetivos ocupam o mesmo ponto neste gráfico.

Um método exato procura certificar essa fronteira. Uma heurística explora uma parte do espaço usando a estrutura do escalonamento. Uma meta-heurística direciona uma busca mais ampla por meio de uma população ou de movimentos entre vizinhos. Vamos começar com o que é possível certificar.

**Fontes** `src/problem.py`, `src/schedule.py`, `src/exact_methods/cpsat.py`, `README.md` e formulação de Rego et al. (2022). A especialização para `PARTITION` decorre das restrições quando as duas máquinas têm tempos iguais e o horizonte comporta o limite examinado.

## 06:00–09:20 · Métodos exatos e referência

### 06:00 · `cp_sat`

O CP-SAT do OR-Tools considera intervalos opcionais para cada tarefa, máquina e modo. Ele escolhe exatamente um intervalo por tarefa, evita sobreposição e usa um circuito para identificar sucessores e aplicar os setups. O custo do bloco é consultado em uma tabela pelo início. [Siga o ponto no plano dos objetivos.] Sob um teto de energia, o driver primeiro prova o menor makespan e em seguida o menor TEC para aquele makespan. Depois exige um custo estritamente menor, baixando o teto em uma unidade da escala inteira. Cada ponto exige duas etapas ótimas. Quando o próximo teto é provado inviável, a fronteira está completa.

### 06:55 · `backtracking`

O backtracking próprio vê a busca como uma árvore. Escolhe a tarefa com menos opções restantes e abre ramos para máquina, início e modo. A propagação elimina horários que entram em conflito. [Aponte para dois ramos que desaparecem.] Uma poda pode provar inviabilidade. Outra pode mostrar que, mesmo com limites otimistas de tempo e energia, aquele ramo não melhora uma solução já conhecida. A folha verifica a sequência efetiva, pois duas tarefas que agora parecem adjacentes ainda podem receber uma terceira entre elas. Se a busca é interrompida, sua frente é provisória.

### 07:40 · `dp`

A programação dinâmica própria reaproveita soluções parciais que chegam à mesma máquina, ao mesmo subconjunto de tarefas e à mesma última tarefa. Compare dois rótulos desse estado. Se um termina antes e custa menos ou igual, ele pode esperar e imitar qualquer continuação do outro. [Observe um rótulo permanecer e o outro desaparecer.] A última tarefa faz parte do estado porque determina o próximo setup. A DP encontra o makespan mínimo, combina partições disjuntas entre máquinas e minimiza o custo para cada teto inteiro de makespan até o horizonte. O número de subconjuntos ainda cresce exponencialmente com a quantidade de tarefas.

### 08:35 · `certificados`

Na comparação histórica com seis tarefas, CP-SAT e DP encontraram os mesmos 43 pontos certificados. O backtracking registrava 14 pontos provisórios. Na entrada original de dez tarefas, a DP fechou 97 pontos, e o CP-SAT havia provado seis antes de parar com `UNKNOWN`. [Deixe os estados visíveis por alguns segundos.] Esses resultados justificam a DP como referência nas entradas em que ela completou a certificação. Na campanha de nove entradas, isso ocorreu nas instâncias de seis e de dez tarefas. Para ampliar a escala, vamos abrir mão da prova global e explorar a estrutura do problema.

**Se perguntarem pelos tempos**, naquele registro histórico, a DP levou 22,27 segundos na instância de seis tarefas, e CP-SAT levou 1.141,53 segundos. O backtracking ainda produzia uma frente provisória aos 4.095,25 segundos. Refira-se a esses registros e aos seus orçamentos ao comparar tempos. Na campanha principal, a DP tem teto de 13 tarefas, 3.600 segundos e 4.096 MiB por instância. A classificação operacional `TIMEOUT_OR_MEM_LIMIT` também abrange casos excluídos pelo limite de tamanho.

**Fontes** `src/exact_methods/{cpsat,custom_exact,custom_exact_dp}.py`, `data/output/analise_metodos_exatos.json` e `data/output/experiments/runs/exact_dp/`. Os registros exatos históricos e a campanha têm orçamentos e tempos próprios.

## 09:20–11:50 · Heurísticas

### 09:20 · `construtiva`

A primeira heurística constrói uma solução por inserções. Começa pelas tarefas longas. Como a duração muda por máquina, o código experimenta três ordens, pela soma, pelo mínimo e pelo máximo dos tempos-base. [Acompanhe uma tarefa em mais de uma posição.] Para cada tarefa, máquina, modo e posição, mede o makespan e o custo da solução parcial. O peso alfa combina $C_{\max}/H$ e $\mathrm{TEC}/\mathrm{max\_cost}$. A varredura de onze pesos dá mais voz ora ao prazo, ora ao custo. Ao final, cada troca de modo aceita reduz o TEC. Se houver aumento de makespan, a escolha prioriza maior economia por unidade de atraso. A construção restringe a espera voluntária a zero.

### 10:15 · `ociosidade`

A segunda heurística parte das sequências que a construtiva encontrou. As tarefas continuam na mesma máquina e na mesma ordem. Agora podemos mover os blocos no tempo e escolher seus modos. [Mostre o bloco deslizar para fora da ponta, preservando os vizinhos.] Uma programação dinâmica por máquina calcula o menor custo para terminar em cada instante. O mínimo acumulado até um instante anterior permite esperar. Para cada limite de makespan, soma-se o melhor custo das máquinas. A combinação fornece a fronteira ótima **para aquela alocação e sequência**. A união das sequências de partida fornece a frente da heurística.

### 11:10 · `comparacao`

Em seis tarefas, a construtiva entregou 14 pontos, a ociosidade entregou 41 e a frente exata tem 43. [Compare as curvas e deixe a plateia acompanhar a legenda.] Repare na proximidade dos pontos. A ociosidade da campanha pôde ajustar esperas e modos, o que explica por que as frentes diferem dentro das mesmas sequências. Para rever ordem e alocação, precisamos de outros movimentos de busca.

**Se perguntarem pelos indicadores antes da seção de métricas**, a construtiva recuperou 6 dos 43 pontos certificados e a ociosidade recuperou 20. Os hipervolumes respectivos foram 0,9361 e 0,9630, com a mesma referência da DP (0,9817). Os pontos coincidentes e a área dominada medem aspectos diferentes.

**Fontes** `src/heuristics/{construtiva/construtiva,ociosidade/ociosidade}.py`, `data/output/heuristica_construtiva/`, `data/output/experiments/runs/ociosidade/` e `data/baselines/`.

## 11:50–16:30 · Cinco implementações meta-heurísticas

### 11:50 · `representacao`

Para descrever um candidato, cada máquina tem uma sequência de triplas. A tripla registra tarefa, modo e espera após a preparação. [Acompanhe o bloco da tarefa 2 indo para a linha da M2.] Essa representação permite modificar o plano sem enumerar todos os horários. Uma mudança pode violar o horizonte, de modo que os candidatos passam pelo avaliador comum. Os três métodos populacionais compartilham operadores para schedules, mas cada método usa um critério próprio para selecionar quem continua na população.

### 12:35 · `spea2`

No SPEA2, a força de um ponto vem de quantos outros ele domina. A qualidade bruta de um candidato acumula a força dos que o dominam. [Siga as setas de dominância.] Pontos que sofrem dominância de vizinhos fortes perdem prioridade. A densidade permite distinguir regiões cheias e esparsas. Neste projeto, a sobrevivência usa as unidades brutas de makespan e TEC, o que importa para a interpretação de distância. A versão é incremental: depois da inicialização, entra um descendente por iteração. A frente exportada vem dos sobreviventes da população final.

### 13:25 · `moead`

O MOEA/D distribui pesos entre vários subproblemas. Siga uma direção: ela privilegia um compromisso entre distância ao ideal em tempo e distância ao ideal em energia. O desempenho escalar usa a decomposição de Tchebycheff, com os objetivos na escala $C_{\max}/H$ e $\mathrm{TEC}/\mathrm{max\_cost}$. Uma solução é cotejada com subproblemas vizinhos. [Aponte a direção destacada e suas vizinhas.] As direções ficam uniformemente espaçadas no espaço de pesos. A distribuição de pontos no plano dos objetivos depende da forma da frente. Uma tentativa inviável conta no orçamento e pode dar lugar a uma cópia viável já avaliada, o que tende a reduzir diversidade se acontecer com frequência.

### 14:20 · `age`

O AGE-MOEA estima a geometria da primeira camada não dominada após normalizar seus objetivos. [Acompanhe a curva mudar com os pontos extremos.] Essa forma orienta as noções de proximidade e separação usadas pela sobrevivência. O mecanismo busca preservar bons compromissos em diferentes regiões da frente. A implementação usa o AGE nativo do `pymoo` e troca candidatos em lotes de tamanho igual à população, com o último lote limitado ao orçamento restante. Os schedules sobreviventes são reavaliados no fim e filtrados com o custo em unidades inteiras.

### 15:15 · `vns`

As versões original e revisada de VNS/VND trabalham com um arquivo de Pareto. O VNS sorteia uma origem entre os pontos menos explorados e aplica uma perturbação, o *shaking*. O VND tenta melhorar localmente o candidato percorrendo cinco vizinhanças. Observe que cada movimento mexe em uma parte diferente do escalonamento. Podemos trocar modo, mudar a espera, inserir dentro da mesma máquina, realocar para outra máquina ou trocar duas tarefas.

[Dê tempo para observar dois movimentos.] Ao encontrar um vizinho que domina o candidato corrente, o VND aceita o movimento e volta à primeira vizinhança. O arquivo aceita também novas alternativas incomparáveis, e a expansão do arquivo reinicia a sequência de perturbações. A diferença relevante entre as duas versões vem antes dessa busca: como construir os schedules iniciais que abastecem o arquivo. Vamos chegar a ela depois de entender a calibração e a execução.

**Fontes** `src/metaheuristics/{spea2,moead,age,vns_vnd_original,vns_vnd}.py`, `src/schedule.py` e `README.md`, seções 5.1 a 5.5.

## 16:30–19:00 · Calibração e execução

### 16:30 · `protocolo`

Os ensaios pequenos davam hipervolumes altos para muitas configurações. A calibração passou a usar duas instâncias por porte: pequeno, médio e grande. Cada trial usa seis instâncias, três sementes e oito mil avaliações por busca. O TPE do Optuna propõe novas combinações. O escore calcula a mediana de HV dividido por $1{,}05^2$ entre sementes e depois a média entre instâncias. [Percorra os três números da tela.] Os limites de normalização vêm das entradas.

### 17:10 · `busca`

As grades mostram os controles de cada método. [Aponte para população, vizinhos e partidas.] Depois, a confirmação reavalia as melhores configurações com novas sementes e promove algumas a orçamentos maiores. AGE, MOEA/D e VNS v7 passam por 8, 20 e 50 mil avaliações. A confirmação do SPEA2 registra 20 e 50 mil.

**Se perguntarem pelo efeito da confirmação**, todos os trials recomendados no orçamento de 50 mil diferem dos melhores trials a oito mil nos estudos correspondentes. Em sequência, AGE mudou de 55 para 43, MOEA/D de 41 para 44, SPEA2 de 51 para 66 e VNS v7 de 32 para 65. São recomendações entre as configurações avaliadas pelo protocolo.

### 17:40 · `selecionados`

A tabela mostra o que efetivamente entrou no manifesto da campanha. Compare, por exemplo, a população 100 de AGE com a população 300 do MOEA/D. No SPEA2, a configuração confirmada usa população 200. As duas campanhas de VNS/VND usam 16 partidas e 20 tentativas de perturbação. O limite de candidatos muda de 10 na original para 25 na revisada. O manifesto registra que os 25 vieram de uma recomendação obtida com o inicializador antigo, enquanto o código da segunda campanha já usa o novo inicializador. [Aponte para os identificadores dos trials e para a condição provisória.]

### 18:20 · `execucao`

Em cada uma das nove instâncias, a campanha planejou uma execução da DP e uma de ociosidade, determinísticas no protocolo. CP-SAT, backtracking e construtiva têm registros próprios. Cada implementação meta-heurística teve 30 réplicas com orçamento de dez mil avaliações. [Leia as linhas da tabela.] As sementes 1001 a 1030 permitem parear réplicas entre os métodos. Os registros guardam o estado de cada execução e se houve frente.

**Fontes** `src/hyperparameters_tuning/{main,common,confirm}.py`, `data/output/hyperparameters_tuning/**/{protocol,best_parameters,confirmation}.json`, `data/output/{experiments,experiments_vns_new}/experiment_manifest.json` e `src/experiments/{config,runner}.py`.

## 19:00–22:10 · Caso crítico do VNS/VND

### 19:00 · `instancia`

O arquivo `750_10_1439_5_S_1-9.dat` contém 750 tarefas, dez máquinas e cinco modos. São dois dias de 1.440 intervalos de um minuto, para um horizonte de 2.880 intervalos. A ponta acontece das 18h às 21h de cada dia, com tarifa 0,47753, ante 0,32282 fora da ponta. [Mostre a repetição das faixas de tarifa.] A construção examina até 50 combinações máquina–modo por tarefa. O desafio é preservar capacidade para as tarefas que ainda não entraram.

### 19:35 · `antes`

Na versão original, a ordem das tarefas era embaralhada. Para a próxima tarefa, a construção listava as extensões viáveis no fim de cada máquina, com o setup e a duração do modo, e sorteava uma delas uniformemente. Assim, uma escolha podia consumir mais folga do que outra, embora ambas fossem viáveis naquele instante. [Mostre o replay da primeira tentativa com a semente 1001.] Após 516 alocações, a tarefa 108, de índice 107 no código, terminaria no mínimo no minuto 2.889. O horizonte termina no minuto 2.880. Sem extensão viável para aquela tarefa, a construção descartou o plano parcial. Com 16 partidas solicitadas, a campanha original permitia até 800 tentativas de construção. As 30 execuções na instância terminaram em `INIT_FAILED`, antes das avaliações de busca.

### 20:30 · `depois`

O inicializador revisado calcula, para cada tarefa, a sua menor duração entre todas as máquinas e modos. Ele ordena da maior dificuldade para a menor. A próxima tarefa é sorteada entre as primeiras da lista, em uma janela de tamanho $\lceil\sqrt{\text{tarefas restantes}}\rceil$. A janela preserva variação entre sementes e favorece a entrada antecipada das tarefas difíceis. Para escolher máquina e modo, a construção toma o menor término viável, incluindo o setup. O desempate continua aleatório. Assim, ela contém o crescimento dos términos enquanto ainda há tarefas por programar. [Mostre a folga no replay.] A mesma semente 1001 completou a primeira construção, com makespan de 1.169 minutos. Uma tentativa que ficar sem extensão continua podendo falhar.

### 21:25 · `evidencia`

Com a semente 1001, o original falhou na inicialização. A revisão construiu 16 partidas distintas em 16 tentativas, completou dez mil avaliações e devolveu oito pontos. [Compare as duas linhas da tabela.] Na campanha, foram 30 falhas na versão original e 30 conclusões na revisão. O limite de candidatos do VND também mudou. Ele só entra depois da construção e pode afetar a qualidade da frente devolvida.

**Fontes** `data/input/set2/750_10_1439_5_S_1-9.dat`, `src/problem.py`, diff entre `src/metaheuristics/vns_vnd_original.py` e `vns_vnd.py`, commit `35f4330`, `src/presentation/trace_vns.py` e `run_01.json` da instância nas duas campanhas.

## 22:10–25:40 · Métricas

### 22:10 · `hv`

Cada ponto projeta um retângulo até a referência. O hipervolume é a área da união desses retângulos. [Mostre os dois contornos e depois a área preenchida.] Cada sobreposição conta uma vez. Melhorar os objetivos amplia a área de um ponto. Outro compromisso pode cobrir uma região adicional. Assim, a área responde à posição dos pontos e à extensão da frente.

Na mesma instância, todas as execuções usam a escala da campanha original, calculada pelo ideal e pelo nadir, e a referência 1,1 em cada eixo. Quando a frente fica fora da caixa útil, o hipervolume é zero mesmo com uma frente viável. [Deixe a plateia localizar a caixa no gráfico.] A calibração tem sua própria escala e seus próprios escores.

**Se perguntarem por um objetivo constante**, o código usa divisor um quando ideal e nadir coincidem naquele eixo.

### 23:20 · `purity`

Agora reunimos, por instância, os pontos distintos das duas campanhas para ver quais sobrevivem à dominância. A primeira camada dá $P^*$. Em seis e dez tarefas, ela coincide com a fronteira certificada pela DP. Nos demais casos, ela é empírica. [Aponte para a interseção.] A convenção de *Purity* do protótipo divide o número de pontos de uma execução que coincidem com $P^*$ pelo tamanho de $P^*$. A métrica responde quanto da referência foi recuperado por esta execução. Duas execuções podem recuperar o mesmo ponto e receber crédito por ele. Uma aproximação pode cobrir uma área importante no hipervolume e ainda assim coincidir com poucos pares exatos da referência.

### 24:20 · `eq36`

Na Equação 3.6 de Miranda, primeiro reunimos os pontos distintos de todas as frentes. [Remova a primeira camada e deixe aparecer a segunda.] Os pontos não dominados recebem posição um. Removemos todos juntos e repetimos o processo no que sobrou. $R_p$ é a posição da camada do ponto $p$. $R^*$ é o número total de camadas mais um. Para cada $p$ da frente $F$, a diferença $R^*-R_p$ dá mais crédito às camadas de cima. Dividimos a soma pelo número de pontos da frente. Assim, a equação dá o crédito médio por ponto. Um valor maior coloca os pontos mais perto das primeiras camadas, para a mesma instância e o mesmo conjunto reunido. Frente vazia fica sem valor, pois não há pontos para calcular a média.

**Fontes** `src/experiments/metrics.py`, cena original `src/presentation/cebola.py`, `data/output/experiments/metrics/reference_fronts.json` e Miranda (2025), p. 39, Equação 3.6.

## 25:40–29:00 · Resultados e discussão

### 25:40 · `dispersao`

Leia cada linha como um par algoritmo–instância. Cada observação vem de uma execução com frente. A média resume o nível típico e o desvio-padrão amostral, quando há pelo menos duas observações, mostra a variação entre execuções. Mínimo e máximo mostram os extremos observados. Mediana e amplitude interquartil ajudam a ver onde se concentra a metade central. [Compare a dispersão de dois métodos no gráfico e siga as três métricas pelo painel.] Uma observação determinística tem média, mínimo e máximo iguais. O desvio amostral fica em branco. A quantidade de resultados válidos acompanha cada indicador.

### 26:50 · `portes`

Leia cada comparação dentro da mesma instância. Em dez tarefas, a ociosidade alcança HV de 1,0366, próximo de 1,0455 da DP, embora não recupere nenhum dos 97 pares exatos. Os números mostram que proximidade geométrica e coincidência exata podem contar histórias diferentes. [Aponte para os portes exibidos.] Entre as meta-heurísticas, SPEA2 obteve a maior média de HV em seis tarefas. AGE liderou em dez, quatorze e nas duas instâncias de 50 e de 250 tarefas. A ociosidade produziu o maior HV observado dos 14 aos 750, sob o orçamento e as referências desta campanha. Como a heurística ajudou a construir as referências empíricas, esse resultado descreve o conjunto observado. O mecanismo de esperar e rever modos em sequências bem construídas é uma explicação plausível, a ser testada com modos fixos e orçamentos maiores.

### 28:05 · `discussao`

Na instância de 750 tarefas e dez máquinas, as quatro meta-heurísticas que completaram ficaram com HV e *Purity* iguais a zero sob a referência utilizada. Mesmo assim, a Eq. 3.6 revelou diferenças entre as camadas que atingiram. As médias foram cerca de 75,9 para AGE e 13,4 para VNS revisado. [Mostre a posição dos pontos e relembre a caixa do HV.] A construção revisada resolveu o gargalo de obter uma frente, e o desempenho relativo dela depende da escala, da referência e dos parâmetros da busca. Para separar qualidade inicial de convergência, precisaríamos acompanhar as frentes ao longo de avaliações sucessivas. O resultado final também pode perder compromissos visitados anteriormente nos métodos que exportam somente a população sobrevivente.

**Se perguntarem pela diferença de HV entre AGE e SPEA2**, a campanha histórica registra teste de soma de postos com ajuste de Holm por instância. Em seis tarefas, o valor ajustado foi 0,5543. Foi inferior a 0,05 em dez, quatorze, nas duas instâncias de 50 e nas duas de 250 tarefas. Nas gigantes, o HV das duas meta-heurísticas ficou em zero. Para *Purity* e Eq. 3.6, este roteiro usa estatísticas descritivas.

**Fontes** dois manifestos de campanha e respectivos `runs/`, métricas por execução e apêndice tabular da apresentação.

## 29:00–30:00 · Conclusão e referências

### 29:00 · `conclusao`

Nos casos em que a certificação coube no orçamento, a DP forneceu a fronteira de referência. Em escala maior, aproveitar o preço por horário e a flexibilidade de modos tornou a ociosidade um comparador forte. No VNS/VND, preservar folga na construção viabilizou a busca nas 30 repetições da instância que antes falhava. O próximo experimento pode manter os parâmetros de busca iguais entre inicializadores, medir a trajetória de qualidade em mais orçamentos e testar os resultados em instâncias que não participaram da calibração.

### 29:40 · `referencias`

O artigo de Rego e colaboradores é a base da formulação. A métrica de camadas vem de Miranda. As referências para os mecanismos e para as bibliotecas aparecem na tela e ficam disponíveis abaixo. [Mantenha a tela de referências visível até 30:00.]

- Rego, M. F., Pinto, J. C. E. M., Cota, L. P. e Souza, M. J. F. (2022). *A mathematical formulation and an NSGA-II algorithm for minimizing the makespan and energy cost under time-of-use electricity price in an unrelated parallel machine scheduling*. PeerJ Computer Science, 8, e844. [DOI](https://doi.org/10.7717/peerj-cs.844)
- Miranda, E. G. R. (2025). *Um arcabouço para otimização de saídas de emergência de ambientes utilizando autômatos celulares e algoritmos de otimização multiobjetivo*. Universidade Federal de São João del-Rei, p. 39, Eq. 3.6.
- Zitzler, E., Laumanns, M. e Thiele, L. (2001). *SPEA2: Improving the Strength Pareto Evolutionary Algorithm*. ETH Zürich, relatório TIK 103. [DOI](https://doi.org/10.3929/ethz-a-004284029)
- Zhang, Q. e Li, H. (2007). *MOEA/D: A Multiobjective Evolutionary Algorithm Based on Decomposition*. IEEE Transactions on Evolutionary Computation, 11(6), 712–731. [DOI](https://doi.org/10.1109/TEVC.2007.892759)
- Panichella, A. (2019). *An Adaptive Evolutionary Algorithm Based on Non-Euclidean Geometry for Many-objective Optimization*. GECCO. [DOI](https://doi.org/10.1145/3321707.3321839)
- Mladenović, N. e Hansen, P. (1997). *Variable neighborhood search*. Computers & Operations Research, 24(11), 1097–1100. [DOI](https://doi.org/10.1016/S0305-0548(97)00031-2)
- Blank, J. e Deb, K. (2020). *pymoo: Multi-Objective Optimization in Python*. IEEE Access, 8, 89497–89509. O projeto usa `pymoo` 0.6.2. [DOI](https://doi.org/10.1109/ACCESS.2020.2990567)
- Akiba, T. et al. (2019). *Optuna: A Next-generation Hyperparameter Optimization Framework*. ACM KDD. [Artigo](https://arxiv.org/abs/1907.10902)
- Bibliotecas de otimização e visualização. [OR-Tools/CP-SAT](https://developers.google.com/optimization/cp/cp_solver), [Manim Community 0.22.1](https://docs.manim.community/en/stable/changelog/0.22.1-changelog.html), [Numba](https://numba.readthedocs.io/) e [Matplotlib MathText](https://matplotlib.org/stable/users/explain/text/mathtext.html). As versões instaladas nas campanhas constam dos manifestos.
