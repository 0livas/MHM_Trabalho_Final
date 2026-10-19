# MHM — otimização multiobjetivo

Minimização do makespan (`Cmax`, maior término das tarefas) e do custo total de energia (`TEC`) em máquinas paralelas não relacionadas, com modos de operação, setups entre tarefas consecutivas e tarifas por horário.

Este guia descreve como preparar o ambiente, criar uma entrada, executar os métodos, retomar buscas e consultar os resultados. Execute os comandos a partir da raiz do repositório. Os caminhos com `/` funcionam no PowerShell, Git Bash e terminais Linux/macOS; coloque caminhos com espaços entre aspas.

## 1. Preparar o ambiente

Use Python 3.10 ou superior, em uma versão compatível com as dependências de `requirements.txt`. Não é obrigatório criar um ambiente virtual.

```bash
python --version
python -m pip install -r requirements.txt
```

Use o mesmo executável `python` para instalar e executar. Se o seu sistema usa `python3`, substitua `python` nos comandos. A instalação é feita uma vez; execute-a novamente quando mudar o arquivo de requisitos.

| Componente | Dependência |
| --- | --- |
| Backtracking, DP própria, VNS/VND e heurísticas (construtiva e de ociosidade) | Biblioteca padrão do Python |
| CP-SAT | OR-Tools |
| SPEA2, MOEA/D e AGE-MOEA | pymoo 0.6.2 (AGE-MOEA também requer Numba) |
| Gráficos | Matplotlib |

Os métodos são independentes: não é necessário executar um método exato antes de iniciar uma meta-heurística. As fronteiras exatas são referências para avaliar resultados depois das buscas.

```text
src/
  exact_methods/     # custom_exact.py, custom_exact_dp.py e cpsat.py
  metaheuristics/    # vns_vnd.py, spea2.py, moead.py, age.py e spikes pymoo
  heuristics/
    construtiva/     # heurística construtiva ponderada + ajuste de modos e grafico.py
    ociosidade/      # inserção ótima de ociosidade (DP de tempos e modos) e grafico.py
  problem.py         # leitura da entrada e regras/custos compartilhados
  schedule.py        # representação, decodificação, validação e avaliação
  plot_pareto.py      # gráficos dos resultados salvos
data/
  input/set1/        # instâncias pequenas originais e derivadas identificadas
  input/set2/        # instâncias originais grandes
  baselines/         # fronteiras exatas completas
  output/            # resultados por método, gráficos e relatórios
tests/               # testes da infraestrutura e das meta-heurísticas
requirements.txt
```

## 2. Escolher ou criar uma entrada `.dat`

Todos os métodos leem o mesmo formato por meio de `src/problem.py`. Você pode usar, por exemplo, `data/input/set1/6_2_1439_3_S_1-9.dat`, ou criar seu próprio arquivo em `data/input/personalizados/`.

Salve como texto UTF-8 com extensão `.dat` (não `.dat.txt`). Os nomes dos campos e sua ordem são obrigatórios. Valores podem ser separados por espaços, tabulações e quebras de linha; linhas vazias são permitidas. Use ponto decimal, como `1.2`, e não vírgula. Não inclua comentários, títulos de matrizes, separadores, vírgulas entre colunas ou textos como `&#x9;`: o parser lê todos os tokens como dados.

### Campos, dimensões e ordem

| Campo | Quantidade de valores | Significado e requisitos |
| --- | --- | --- |
| `n` | 1 inteiro positivo | Número de tarefas/jobs. |
| `m` | 1 inteiro positivo | Número de máquinas. |
| `n_day` | 1 inteiro positivo | Número de dias. |
| `hl` | 1 inteiro não negativo | Último índice de intervalo de um dia. Há `hl + 1` intervalos por dia. |
| `o` | 1 inteiro positivo | Número de modos de operação. |
| `rate_in_peak` | 1 número não negativo | Tarifa de energia durante a ponta. |
| `rate_off_peak` | 1 número não negativo | Tarifa fora da ponta. |
| `max_cost` | 1 número positivo | Normalizador de TEC; não é um teto de custo nem uma restrição de viabilidade. |
| `peak_start` | `n_day` inteiros | Primeiro intervalo de ponta de cada dia, em índices absolutos. |
| `peak_end` | `n_day` inteiros | Último intervalo de ponta de cada dia, inclusive, em índices absolutos. |
| `v` | `o` números positivos | Velocidade de cada modo. |
| `lambda` | `o` números não negativos | Fator de potência/consumo de cada modo; não é peso de otimização multiobjetivo. |
| `pi` | `m` números não negativos | Potência de cada máquina. |
| `processing` | `n × m` inteiros positivos | Linha = tarefa; coluna = máquina; duração base em intervalos. |
| `setup` | `m × n × n` inteiros não negativos | Uma matriz `n × n` por máquina; linha = tarefa anterior; coluna = próxima tarefa. |

A ordem dos modos em `v` e `lambda` deve coincidir. A ordem das máquinas em `pi`, nas colunas de `processing` e nos blocos de `setup` também deve coincidir. Nos resultados, os índices de tarefas, máquinas e modos começam em **zero**.

Em `setup`, escreva primeiro todas as linhas da máquina 0, depois todas as linhas da máquina 1, e assim por diante. Não escreva rótulos entre os blocos. Use zero na diagonal: ela corresponde à transição de uma tarefa para ela mesma, que não ocorre em uma solução. A matriz pode ser assimétrica: `setup[i][j][k]` não precisa ser igual a `setup[i][k][j]`.

### Tempo, energia e horários de ponta

- Horizonte total: `H = n_day * (hl + 1)`.
- Duração da tarefa `j`, na máquina `i`, no modo `l`: `ceil(processing[j][i] / v[l])`.
- Um processamento ocupa `[start, end)`, com `end = start + duração` e `end <= H`.
- O setup exige `start_próxima >= end_anterior + setup[i][anterior][próxima]` entre tarefas consecutivas da mesma máquina.
- Todas as tarefas estão disponíveis em zero; não há preempção nem setup inicial. Espera e setup não cobram energia no modelo implementado.
- O custo de um intervalo de processamento é `pi[i] * lambda[l] * tarifa * 24 / (hl + 1)`. Use unidades coerentes, por exemplo potência em kW e tarifa em moeda/kWh. O código mantém os custos como inteiros escalados para comparar valores exatos.

**Como interpretar a unidade de tempo:** o programa divide cada dia de 24 horas em `hl + 1` partes iguais. Os valores de `processing`, `setup`, início e término são expressos em quantidades dessas partes, chamadas de intervalos. Portanto, `hl` define a resolução do dia; ele não é a duração de uma tarefa nem um limite em horas.

| Valor de `hl` | Intervalos em um dia | Duração de um intervalo | Uma tarefa com duração efetiva 3 ocupa |
| --- | ---: | --- | --- |
| `1439` | 1440 | 1 minuto | 3 minutos |
| `143` | 144 | 10 minutos | 30 minutos |
| `11` | 12 | 2 horas | 6 horas |

O código usa `24 / (hl + 1)` apenas para converter a duração de um intervalo em horas ao calcular energia: potência em kW multiplicada pelo tempo em horas resulta em kWh. Por exemplo, uma máquina de 2 kW, com fator de potência 1, funcionando durante 3 intervalos de 2 horas consome `2 × 1 × 6 = 12 kWh`; o custo depende da tarifa em cada intervalo.

O exemplo pequeno abaixo usa `hl=11` para ter poucos horários possíveis e facilitar o acompanhamento da execução. Isso representa um dia dividido em blocos de duas horas, **não um horizonte de 12 minutos**. Para criar testes com resolução de um minuto, mantenha `hl=1439` e reduza inicialmente o número de tarefas/máquinas. Se mudar a resolução de uma instância existente, converta também processamentos, setups e horários de ponta; copiar os mesmos números muda a duração física do problema, e arredondamentos podem alterar os resultados.

Há uma janela de ponta obrigatória por dia. Para o dia `d`, contado a partir de zero, deve valer:

```text
d * (hl + 1) <= peak_start[d] <= peak_end[d] < (d + 1) * (hl + 1)
```

Exemplo com dois dias de 1440 intervalos: ponta das 18h às 21h corresponde a `peak_start 1080 2520` e `peak_end 1259 2699`. O segundo dia usa índices absolutos, não novamente `1080 1259`. Para simular tarifa constante, mantenha janelas válidas e use tarifas iguais dentro e fora da ponta.

### Exemplo completo para copiar

Crie a pasta `data/input/personalizados/` e salve o conteúdo abaixo como `data/input/personalizados/3_2_11_2_demo.dat`. São três tarefas, duas máquinas, dois modos e um dia de 12 intervalos. É uma instância didática local, não uma entrada do artigo.

```text
n 3
m 2
n_day 1
hl 11
o 2
rate_in_peak 3
rate_off_peak 1
max_cost 100

peak_start
6

peak_end
8

v
1 2

lambda
1 3

pi
2 3

processing
2 3
3 2
2 2

setup
0 1 2
2 0 1
1 2 0

0 2 1
1 0 2
2 1 0
```

Nesse exemplo, `processing[0][1]=3`: a tarefa 0 leva três intervalos na máquina 1 com velocidade 1, ou `ceil(3/2)=2` com velocidade 2. No primeiro bloco de setup, `setup[0][0][2]=2`: se a tarefa 2 sucede imediatamente a tarefa 0 na máquina 0, são necessários dois intervalos de separação.

Confira a leitura antes de executar uma busca:

```bash
python -c "import sys; sys.path.insert(0, 'src'); from problem import read_instance; x = read_instance('data/input/personalizados/3_2_11_2_demo.dat'); print('Entrada lida:', x.n, 'tarefas,', x.m, 'maquinas,', x.modes, 'modos, H =', x.horizon)"
```

A saída esperada é `Entrada lida: 3 tarefas, 2 maquinas, 2 modos, H = 12`. Isso verifica formato e valores básicos; não prova que todas as tarefas cabem juntas respeitando os setups.

Para testar seu arquivo, substitua o caminho da entrada nos comandos das próximas seções. O nome é livre: as dimensões vêm do conteúdo. Use nomes distintos para experimentos distintos, pois o nome do JSON de saída deriva do nome do `.dat`.

## 3. Executar os métodos exatos

Os exemplos abaixo usam a entrada oficial de seis tarefas e diretórios `data/output/manual/<método>/`, para manter os relatórios dessas execuções separados dos resultados existentes. Na primeira execução, não use `--resume`. Se o destino já existir, escolha outro `--output-dir`, retome ou use `--restart` para substituir a execução anterior.

### 3.1 Programação dinâmica própria

```bash
python src/exact_methods/custom_exact_dp.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/custom_exact_dp --total-time-limit 600 --memory-limit-mb 1024 --profile
```

A DP calcula o makespan mínimo e minimiza TEC sob `Cmax <= epsilon`, para cada inteiro até `H`. Ela reutiliza tabelas de estados e retém alternativas não dominadas de término/energia.

- `--total-time-limit 600`: orçamento de tempo por execução/instância; `0` desativa.
- `--memory-limit-mb 1024`: orçamento de RSS em MiB; `0` desativa.
- `--max-jobs 13`: teto padrão de tarefas. Alterá-lo permite iniciar entradas maiores, sem garantir viabilidade computacional.
- `--epsilon-max K`: encerra a varredura em `K`. Se `K < H`, não certifica a fronteira completa.
- `--profile`: registra tempo, memória, transições, rótulos e hash do código em `desempenho.csv`, no diretório de saída.

Os limites de tempo/memória são cooperativos. A preparação de energia os verifica periodicamente e a varredura os verifica entre epsilons. Makespan inicial, geração inicial de opções e uma partição em andamento podem ultrapassar o orçamento antes da próxima verificação.

Ao concluir a fronteira, a DP também grava `data/baselines/<entrada>_custom_exact_dp.json`, mesmo com `--output-dir` personalizado. Esse baseline usa o nome da entrada e pode substituir um baseline anterior com esse nome. Inclui hash da entrada, objetivos e escalonamentos.

### 3.2 CP-SAT do OR-Tools

```bash
python src/exact_methods/cpsat.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/cpsat --workers 4 --seed 1 --time-limit 60 --total-time-limit 300
```

O código externo limita TEC e chama o CP-SAT para provar o menor makespan e, depois, o menor TEC para esse makespan. Após provar um ponto, reduz o teto de TEC em uma unidade inteira escalada.

- `--time-limit 60`: limite de **cada chamada** ao CP-SAT, não da fronteira inteira; `0` desativa.
- `--total-time-limit 300`: orçamento da execução/instância; `0` desativa. A preparação inicial de opções ocorre antes desse relógio. Construção de modelo e verificações cooperativas podem ultrapassar o orçamento.
- `--workers 4`: workers de CPU; não ativa GPU.
- `--seed 1`: semente registrada na execução. Com múltiplos workers, ela não garante trajetória/tempo idênticos entre execuções.

Para rodar sem os limites de tempo, use `--time-limit 0 --total-time-limit 0`. O orçamento de 300 segundos do exemplo pode encerrar com fronteira parcial.

### 3.3 Backtracking próprio

```bash
python src/exact_methods/custom_exact.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/custom_exact --time-limit 300 --progress-interval 60 --checkpoint-interval 60
```

O backtracking propaga restrições e usa limites inferiores e dominância. Os pontos encontrados são provisórios até o esgotamento da busca. Se o limite de tempo for atingido antes de esgotar a busca, o resultado será parcial.

- `--time-limit 300`: orçamento da execução por instância; `0` desativa.
- `--progress-interval 60`: intervalo entre mensagens de progresso, em segundos.
- `--checkpoint-interval 60`: intervalo entre salvamentos, em segundos.
- `--max-decisions N`: limite opcional de decisões da chamada atual.

### 3.4 Retomar ou reiniciar

Use o mesmo caminho de entrada e o mesmo diretório de saída da execução anterior:

```bash
python src/exact_methods/custom_exact_dp.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/custom_exact_dp --resume --total-time-limit 600 --profile
python src/exact_methods/cpsat.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/cpsat --resume --workers 4 --seed 1 --time-limit 60 --total-time-limit 300
python src/exact_methods/custom_exact.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/custom_exact --resume --time-limit 300 --progress-interval 60 --checkpoint-interval 60
```

| Método | Arquivo necessário para retomar | O que é retomado |
| --- | --- | --- |
| DP | JSON de resultado compatível | Epsilons já provados; as tabelas internas são reconstruídas. |
| CP-SAT | JSON de resultado compatível | Pontos provados e próximo teto de custo; a chamada interrompida recomeça. |
| Backtracking | `.checkpoint.json` compatível | Pilha de decisões e fronteira descoberta; o relatório é gravado novamente. |

`--restart` começa do zero e substitui os arquivos da execução; não use junto com `--resume`. Alterar o conteúdo da entrada torna o resultado/checkpoint anterior incompatível. `Ctrl+C` é tratado pelos métodos exatos nas etapas de busca protegidas; espere o programa encerrar e confirme os arquivos antes de retomar. Uma interrupção durante preparação fora desses trechos pode deixar apenas o último salvamento disponível. Não execute dois processos escrevendo no mesmo destino.

## 4. Executar as heurísticas

As duas heurísticas são determinísticas: não têm população, iterações de busca nem aleatoriedade, e a mesma entrada sempre gera a mesma fronteira.

### 4.1 Heurística construtiva

```bash
python src/heuristics/construtiva/construtiva.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/heuristica_construtiva
```

É uma heurística, não uma meta-heurística: não tem população, iterações de busca nem aleatoriedade, e a mesma entrada sempre produz a mesma fronteira. Usa a modelagem de `src/problem.py` e o formato de solução de `src/schedule.py`, sem espera voluntária. A frente final é revalidada por `evaluate_schedule`. A fronteira sai de três etapas:

1. **Construção gulosa ponderada** (generalização do Algoritmo 3 do artigo): para um peso α, cada tarefa é inserida na combinação máquina × modo × posição que minimiza `α·Cmax/H + (1−α)·TEC/max_cost` na solução parcial, sem ultrapassar o horizonte. As tarefas entram em ordem LPT. Como as máquinas são não relacionadas, são usadas três regras: soma, mínimo e máximo dos tempos da tarefa nas máquinas.
2. **Varredura de pesos:** α ∈ {0; 0,1; …; 1}, o mesmo conjunto D do método de soma ponderada do artigo (Algoritmo 1). Cada par regra × α gera uma solução.
3. **Ajuste guloso de modos:** a partir de cada solução construída distinta, troca repetidamente o modo da tarefa com maior economia de TEC por unidade de Cmax acrescentada. Cada passo é registrado, até que nenhuma troca reduza o TEC.

As soluções não dominadas formam a fronteira.

| Opção | Padrão | Significado |
| --- | ---: | --- |
| `--pesos` | 11 | Quantidade de valores de α, igualmente espaçados em [0, 1]. |
| `--output-dir` | `data/output/heuristica_construtiva` | Diretório do JSON. |
| `--overwrite` | desligado | Substitui um resultado existente. |

Cada ponto do JSON registra a `origem`: regra, α e passo do ajuste. Tempos de referência: menos de 0,1 s no set1, cerca de 1 s com 50 tarefas, 17 s com 250 tarefas e 20 máquinas e 145 s com 750 tarefas e 20 máquinas. Consulte a [documentação da heurística](src/heuristics/construtiva/heuristica.md).

### 4.2 Heurística de inserção ótima de ociosidade

```bash
python src/heuristics/ociosidade/ociosidade.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/heuristica_ociosidade
```

É uma heurística de decomposição que primeiro sequencia e depois programa no tempo. A alocação e a ordem das tarefas em cada máquina vêm de soluções de partida e ficam fixas: por padrão, a fronteira da heurística construtiva. Para essa sequência, uma programação dinâmica por máquina escolhe de forma **ótima** os instantes de início e os modos, inclusive com espera voluntária, sem regra gulosa.

A espera compensa quando atrasar uma tarefa para depois da ponta troca slots caros por baratos, porque espera e setup não consomem energia. Para cada limite de Cmax, o menor TEC é a soma das curvas das máquinas. Isso dá a fronteira exata da sequência fixa, e a fronteira final é a união não dominada de todas as sequências.

| Opção | Padrão | Significado |
| --- | ---: | --- |
| `--base` | heurística construtiva | JSON de resultado de qualquer método do repositório, de onde saem as sequências de partida. |
| `--modos-fixos` | desligado | Mantém os modos de partida e otimiza só as esperas. |
| `--output-dir` | `data/output/heuristica_ociosidade` | Diretório do JSON. |
| `--overwrite` | desligado | Substitui um resultado existente. |

A heurística aceita **um arquivo por chamada**. O custo é proporcional a tarefas × horizonte × modos por máquina. Tempos de referência, sem contar a construtiva que gera as partidas: menos de 0,3 s no set1 e cerca de 20 s com 250 tarefas. Com 750 tarefas e 20 máquinas, são 246 s no total, já incluindo a construtiva. Consulte a [documentação da heurística](src/heuristics/ociosidade/heuristica.md).

## 5. Executar as meta-heurísticas

Os comandos abaixo são execuções curtas de demonstração. Os métodos criam suas próprias soluções iniciais e produzem frentes aproximadas, sem certificação global. Os detalhes da implementação estão em [METAHEURISTICS.md](src/metaheuristics/METAHEURISTICS.md).

### 5.1 VNS/VND manual

```bash
python src/metaheuristics/vns_vnd.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/vns_vnd_seed1 --seed 1 --max-evaluations 500
```

O padrão é 10.000 avaliações e seed 1. Também aceita `--initial-solutions`, `--max-candidates-per-neighborhood` e `--shaking-attempts`. O orçamento conta avaliações, não segundos. Uma falha de construção inicial não prova inviabilidade da instância.

### 5.2 SPEA2 via pymoo

```bash
python src/metaheuristics/spea2.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/spea2_seed1 --seed 1 --max-evaluations 500 --population-size 50
```

A execução é incremental: o pymoo gera um descendente por iteração; não equivale ao regime geracional clássico. O orçamento deve ser pelo menos o tamanho da população. Candidatos inviáveis também consomem avaliações. O survival usa `SPEA2Survival(normalize=False)` para evitar divisão por amplitude zero. `--crossover-probability` e `--mutation-probability` controlam os operadores.

### 5.3 MOEA/D via pymoo

```bash
python src/metaheuristics/moead.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/moead_seed1 --seed 1 --max-evaluations 500 --population-size 50 --n-neighbors 10
```

Usa MOEA/D nativo, directions uniformes, Tchebycheff e escala `Cmax/H`, `TEC/max_cost`. Configure `2 <= n_neighbors <= population_size` e orçamento suficiente para avaliar a população inicial. O driver `ask/tell` respeita o cap de tentativas inclusive em varreduras incompletas. Descendentes inviáveis consomem uma tentativa e são substituídos por cópias viáveis já avaliadas. Também aceita `--prob-neighbor-mating`, `--crossover-probability` e `--mutation-probability`.

### 5.4 AGE-MOEA via pymoo

```bash
python src/metaheuristics/age.py data/input/set1/10_2_1439_3_S_1-9.dat --seed 23 --max-evaluations 41 --population-size 8
```

O AGE-MOEA usa o algoritmo nativo do pymoo 0.6.2, a representação compartilhada de schedules e os operadores de variação existentes. O orçamento conta tentativas inviáveis e aceita um lote final parcial; duplicatas podem ocorrer durante a busca. A frente exportada é reavaliada e deduplicada por objetivos exatos. A configuração congelada para a próxima comparação é população 50, crossover 0,9, mutação 0,3 e 8.000 avaliações. O crossover ficou fixo no piloto, sem otimização específica. Os resultados brutos do piloto permanecem locais e não serão publicados como GitHub Release. Consulte o [piloto](data/output/age/piloto/relatorio.md), o [congelamento](data/output/age/FREEZE.md) e a [documentação de integração](data/output/age/implementation.md).

### 5.5 Repetições e orçamento

As meta-heurísticas usam `--overwrite` para substituir um resultado existente; não oferecem a retomada `--resume` dos métodos exatos. Para repetir com outra seed, mude **a seed e o diretório de saída**. Apenas mudar a seed não muda automaticamente o nome do arquivo.

```bash
python src/metaheuristics/spea2.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/spea2_seed2 --seed 2 --max-evaluations 500 --population-size 50
```

SPEA2, MOEA/D e AGE-MOEA reavaliam os sobreviventes ao final: `post_search_validations` registra essas verificações fora do orçamento da busca. Encerrar as avaliações não prova que a fronteira aproximada é ótima.

## 6. Executar uma pasta e consultar opções

Os três exatos, VNS/VND, SPEA2, MOEA/D e a heurística construtiva aceitam um arquivo ou uma pasta; a heurística de ociosidade aceita um arquivo por chamada. Em uma pasta, processam os arquivos `*.dat` diretamente nela, em ordem, sem busca recursiva. O orçamento se aplica a cada arquivo. Exemplo com sua pasta de testes:

```bash
python src/exact_methods/custom_exact_dp.py data/input/personalizados --output-dir data/output/manual/meus_testes_dp --total-time-limit 60
```

Uma entrada que exceda limites ou produza erro pode encerrar o lote. Não use a DP em todo o set2: seu teto padrão é 13 tarefas e o set2 começa em 50. Para descobrir todos os parâmetros de cada executável:

```bash
python src/exact_methods/custom_exact_dp.py --help
python src/exact_methods/cpsat.py --help
python src/exact_methods/custom_exact.py --help
python src/metaheuristics/vns_vnd.py --help
python src/metaheuristics/spea2.py --help
python src/metaheuristics/moead.py --help
python src/metaheuristics/age.py --help
python src/heuristics/construtiva/construtiva.py --help
python src/heuristics/ociosidade/ociosidade.py --help
```

## 7. Ler resultados e gerar gráficos

### 7.1 Arquivos de resultado e plotagem geral

Por padrão, cada método grava `data/output/<método>/<nome_da_entrada>.json`; `--output-dir` altera o diretório. O backtracking também grava `<nome_da_entrada>.checkpoint.json`. Esses checkpoints são ignorados pelo Git: um clone normalmente não contém o estado necessário para retomar o backtracking.

| Resultado | Interpretação |
| --- | --- |
| Exato com `status=complete` e `pareto_proven=true` | Busca/prova concluída para o modelo e a entrada. Uma instância comprovadamente inviável pode ter fronteira vazia. |
| Exato com `status=incomplete` | A fronteira global ainda não foi provada. Leia `stop_reason`. |
| `front` do backtracking incompleto | Pontos provisórios; podem ser dominados posteriormente. |
| `front` parcial de CP-SAT ou DP | Pontos certificados pelas otimizações já concluídas; a lista completa pode estar faltando. |
| `candidate` | Solução viável sem a prova necessária para publicá-la como ponto ótimo. |
| Saída das meta-heurísticas | Frente aproximada; o encerramento do orçamento não é prova de Pareto global. |

`tec_exact` preserva o custo como numerador/denominador; `tec` é a representação decimal. `schedule` descreve tarefa, máquina, modo, início e término. Os arquivos também identificam a entrada por hash. Compare somente a mesma entrada/discretização. `max_cost` não garante que `TEC/max_cost` seja menor ou igual a 1.

Para plotar somente as novas execuções dos exemplos:

```bash
python src/plot_pareto.py data/output/manual --output-dir data/output/manual/plots
```

Para escolher dois resultados específicos:

```bash
python src/plot_pareto.py data/output/manual/custom_exact_dp/6_2_1439_3_S_1-9.json data/output/manual/cpsat/6_2_1439_3_S_1-9.json --output-dir data/output/manual/plots
```

Acrescente `--show` para abrir os gráficos. Sem caminhos, `python src/plot_pareto.py` procura resultados em `data/baselines/` e `data/output/`. A plotagem não executa solvers. Ela agrupa por nome/hash da entrada e método, preferindo resultado completo; entre resultados de mesma categoria, prefere o mais recente. Para visualizar separadamente várias seeds do mesmo método, passe cada resultado em comandos separados com diretórios de gráficos diferentes.

**Limitação atual da legenda:** o plotador geral lê os JSONs das meta-heurísticas, mas pode rotulá-los como “parcial; pontos provados”. Esse texto não certifica esses pontos: a heurística construtiva, VNS/VND, SPEA2 e MOEA/D produzem frentes aproximadas. Consulte o método e `pareto_proven` no JSON ao interpretar o gráfico.

### 7.2 Gráficos das heurísticas

O script abaixo **executa a heurística** e salva um PNG com a frente obtida (azul) sobre a fronteira exata da DP (vermelho), no formato da Fig. 9A do artigo. Ele não salva o JSON dessa execução.

```bash
python src/heuristics/construtiva/grafico.py data/input/set1/6_2_1439_3_S_1-9.dat --output data/output/manual/plots/heuristica_construtiva.png
```

A referência é procurada em `data/baselines/<entrada>_custom_exact_dp.json`. Se ela não existir, o gráfico mostra apenas a frente da heurística; a DP não é executada. Confirme que o baseline corresponde ao conteúdo da entrada, pois o script o seleciona pelo nome do arquivo. Sem `--output`, salva em `data/output/heuristica_construtiva/pareto_<entrada>.png`. Um PNG existente no destino é substituído.

Para a heurística de ociosidade, o gráfico mostra três fronteiras: a exata (vermelho), a da construtiva usada como partida (cinza) e a obtida após a inserção de ociosidade (azul). Sem `--output`, salva em `data/output/heuristica_ociosidade/pareto_<entrada>.png`.

```bash
python src/heuristics/ociosidade/grafico.py data/input/set1/6_2_1439_3_S_1-9.dat --output data/output/manual/plots/heuristica_ociosidade.png
```

## 8. Validar a instalação e tratar erros comuns

```bash
python -m unittest discover -v
```

A suíte atual cobre representação/avaliação, VNS/VND, SPEA2, MOEA/D, AGE-MOEA, as duas heurísticas e normalização. Não há uma bateria específica de regressão dos três solvers exatos na suíte atual.

Para verificar somente as heurísticas:

```bash
python -m unittest tests.test_heuristica_construtiva tests.test_heuristica_ociosidade -v
```

| Mensagem/situação | Como proceder |
| --- | --- |
| `can't open file` | Execute na raiz, confira o caminho e use `/` no Git Bash. |
| `ModuleNotFoundError` | Instale `requirements.txt` com o mesmo Python que executa o script. |
| `Esperado '...'`, `Faltam valores` ou dados adicionais | Confira a ordem dos campos e as dimensões dos vetores/matrizes; remova comentários. |
| Ponta fora do respectivo dia | Use índices absolutos e fim inclusivo dentro do dia correspondente. |
| Job não cabe no horizonte | Revise processamento, velocidades e `H`; nenhuma opção individual coube. |
| Checkpoint/resultado não encontrado com `--resume` | Inicie uma execução nova ou aponte para o diretório onde está o salvamento compatível. |
| Resultado já existe | Use outro `--output-dir`, `--resume` nos exatos ou substitua conscientemente com `--restart`/`--overwrite`. |
| DP limitada a 13 tarefas | Use uma entrada menor; `--max-jobs` é uma ampliação experimental, com custo exponencial. |
| `incomplete` por tempo/memória | Consulte o motivo, ajuste o orçamento e retome quando suportado. Isso não prova inviabilidade. |
