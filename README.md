# MHM — otimização multiobjetivo

Minimização do makespan (`Cmax`, maior término das tarefas) e do custo total de energia (`TEC`) em máquinas paralelas não relacionadas, com modos de operação, setups entre tarefas consecutivas e tarifas por horário.

Este guia descreve como preparar o ambiente, criar uma entrada, executar os métodos, retomar buscas e consultar os resultados. Execute os comandos a partir da raiz do repositório. Os caminhos com `/` funcionam no PowerShell, Git Bash e terminais Linux/macOS; coloque caminhos com espaços entre aspas.

## Organização e regras do repositório

Este README é a única documentação mantida do código. Instruções de instalação, execução, parâmetros, formatos e limitações devem ser atualizadas aqui; não criar guias `.md` separados por método ou campanha.

**Os algoritmos estão congelados para conferência.** Não alterar suas implementações, operadores, critérios, avaliação, restrições ou parâmetros internos sem autorização explícita para isso. Uma tarefa de organização não autoriza modificar, remover ou deslocar código. Ajustes experimentais usam exclusivamente as opções já expostas pelos executáveis.

| Local | Responsabilidade |
| --- | --- |
| `src/` | Implementações e infraestrutura compartilhada. |
| `tests/` | Verificações automatizadas, incluindo calibração. |
| `data/input/` | Entradas `.dat`, com instâncias derivadas identificadas pelo nome. |
| `data/baselines/` | Referências exatas produzidas pelos solvers. |
| `data/output/<método>/` | Resultados e evidências de execução do método. |
| `data/output/hyperparameters_tuning/<algoritmo>/<estudo>/` | Protocolo, trials e parâmetros escolhidos de uma calibração. |
| `requirements.txt` | Dependências da execução atual. |
| `requirements-age-repro.txt` | Versões específicas para reprodução do ambiente do piloto AGE; não substitui os requisitos atuais. |

Preservar JSONs, CSVs, hashes e protocolos como evidências das execuções. Eles não atualizam automaticamente os padrões dos algoritmos. Usar uma pasta própria para cada estudo e evitar resultados soltos na raiz. Logs, caches, checkpoints e bancos locais seguem as exclusões de `.gitignore`.

Alguns scripts auxiliares de experimentos permanecem em `data/output/` porque testes e protocolos referenciam seus caminhos. Seus arquivos e as evidências numéricas não devem ser reorganizados como se fossem documentos descartáveis. Ferramentas de reconstrução de pacotes antigos que exigem documentos e hashes originais precisam do checkout correspondente ao experimento; a consolidação deste README não redefine esses hashes. Relatórios Markdown que esses scripts gerarem são saídas auxiliares locais, ignoradas pelo Git, e não documentação adicional do projeto.

**Navegação:** [ambiente](#1-preparar-o-ambiente) · [entradas](#2-escolher-ou-criar-uma-entrada-dat) · [exatos](#3-executar-os-métodos-exatos) · [heurísticas](#4-executar-as-heurísticas) · [meta-heurísticas](#5-executar-as-meta-heurísticas) · [calibração](#56-calibrar-as-meta-heurísticas-com-optuna) · [lotes e opções](#6-executar-uma-pasta-e-consultar-opções) · [resultados](#7-ler-resultados-e-gerar-gráficos) · [testes](#8-validar-a-instalação-e-tratar-erros-comuns)

## 1. Preparar o ambiente

Use Python 3.10 ou superior, em uma versão compatível com as dependências de `requirements.txt`. Não é obrigatório criar um ambiente virtual.

```bash
python --version
python -m pip install -r requirements.txt
```

Use o mesmo executável `python` para instalar e executar. Se o seu sistema usa `python3`, substitua `python` nos comandos. A instalação é feita uma vez; execute-a novamente quando mudar o arquivo de requisitos.

`requirements-age-repro.txt` registra o ambiente específico do piloto AGE (Python 3.10.12/Linux), descrito em [environment.json](data/output/age/environment.json). Ele não é um comando nem substitui a instalação acima. Reproduzir aquele ambiente exige uma instalação separada e compatível; as versões fixadas não garantem os mesmos tempos ou bytes em outra plataforma.

| Componente | Dependência |
| --- | --- |
| Backtracking, DP própria, VNS/VND e heurísticas (construtiva e de ociosidade) | Biblioteca padrão do Python |
| CP-SAT | OR-Tools |
| SPEA2, MOEA/D e AGE-MOEA | pymoo 0.6.2 (AGE-MOEA também requer Numba) |
| Calibração | Optuna/TPE e threadpoolctl |
| Gráficos | Matplotlib |

Os métodos são independentes: não é necessário executar um método exato antes de iniciar uma meta-heurística. As fronteiras exatas são referências para avaliar resultados depois das buscas.

```text
src/
  exact_methods/     # custom_exact.py, custom_exact_dp.py e cpsat.py
  hyperparameters_tuning/ # main.py, common.py e adaptadores dos quatro métodos
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
tests/               # infraestrutura, heurísticas, meta-heurísticas e calibração
requirements.txt
```

## 2. Escolher ou criar uma entrada `.dat`

Todos os métodos leem o mesmo formato por meio de `src/problem.py`. Você pode usar, por exemplo, `data/input/set1/6_2_1439_3_S_1-9.dat`, ou criar seu próprio arquivo em `data/input/personalizados/`.

A família `10…14_2_1439_3_S_1-9_derivada.dat` foi extraída de `set2/50_10_1439_5_S_1-9.dat`: primeiras n tarefas, máquinas 0 e 1 e modos originais 0, 2 e 4. Tarifas, horizonte, potências e normalizador foram preservados. São entradas locais derivadas, não instâncias originais publicadas; a de dez tarefas derivada é diferente da original de dez tarefas.

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

Os certificados dos métodos exatos se referem a essas regras e à discretização da entrada. Para comparar com tabelas do artigo, iguale também discretização, convenção de setup, unidades, normalização e procedimento de construção da frente; nomes de instâncias semelhantes e um gráfico no mesmo formato não demonstram reprodução numérica equivalente.

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

### Representação computacional de uma solução

Em `src/schedule.py`, `Schedule` é uma tupla de sequências, uma por máquina; cada operação é a tripla `(job, modo, espera)`. A lista externa tem exatamente `m` posições, inclusive para máquinas vazias. Cada job deve aparecer exatamente uma vez; modo e job devem pertencer aos domínios da entrada, e espera deve ser inteira e não negativa.

Para a entrada didática acima, uma representação possível é:

```python
schedule = (
    ((0, 0, 0), (2, 1, 2)),  # máquina 0: tarefa 0, depois tarefa 2
    ((1, 0, 0),),             # máquina 1: tarefa 1
)
```

Na máquina 0, a tarefa 0 começa em 0 e termina em 2. A tarefa 2 começa em `2 + setup[0][0][2] + 2 = 6` e termina em 7, pois seu modo 1 tem velocidade 2. Na máquina 1, a tarefa 1 ocupa `[0,2)`. Portanto, `Cmax=7`. A espera 2 é **adicional ao setup**, não um instante absoluto. Para a primeira tarefa, início = espera; para as demais, início = término anterior + setup + espera.

`evaluate_schedule` decodifica e valida a representação, retornando `cmax`, `tec_units`, `tec_scale` e as operações. `schedule_from_result_rows` converte as linhas `schedule` de um resultado: ordena por máquina/início e recupera a espera residual. O campo `x_nonzero` representa as posições ativas de `X[i,j,h,l]`, com máquina `i`, job `j`, início `h` e modo `l`; não é necessário construir um tensor denso.

A representação permite reconstruir qualquer escalonamento viável do modelo, inclusive com ociosidade. Ela não garante que um operador produza uma solução viável: uma alteração pode ultrapassar `H` e precisa ser reavaliada. Dois schedules com os mesmos objetivos representam um único ponto da frente; o filtro guarda um representante, não todas as soluções equivalentes.

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

**Por que a redução de estados preserva a solução:** a etapa inicial de makespan usa modos de menor duração e ausência de espera, suficientes para minimizar somente esse objetivo. A etapa de energia considera modos e esperas. Seu estado é `(máquina, subconjunto de tarefas, última tarefa)`; cada rótulo guarda término, energia e predecessor para reconstrução. Dentro do mesmo estado, um rótulo que termina antes e custa menos ou igual pode esperar e imitar qualquer continuação do outro. Por isso o outro pode ser descartado. Rótulos de estados com últimas tarefas diferentes não são intercambiáveis durante as extensões, pois seus setups futuros diferem.

`next_cheaper` considera o primeiro início permitido e salta, para a mesma tarefa/modo, para horários de custo estritamente menor. Um horário posterior de custo igual ou maior já é dominado pelo anterior. Após preparar as máquinas, outra DP combina todas as partições disjuntas de tarefas para cada epsilon, minimizando TEC e desempatando pelo menor makespan. O teto é `Cmax <= epsilon`, não uma obrigação de terminar exatamente nele. Reutilizar estados evita repetir continuações equivalentes; não significa enumerar previamente todos os schedules viáveis.

No perfil, `transitions` conta extensões efetivamente examinadas na preparação de energia; `inserted_labels` conta inserções acumuladas, `rejected_labels` as recusadas e `removed_labels` rótulos substituídos por melhores. `peak_active_state_labels` é o pico por máquina antes da fusão dos estados; `retained_subset_labels` conta as listas finais após essa fusão. Esses contadores não são quantidades de schedules completos nem medem sozinhos a memória: referências a predecessores também mantêm objetos vivos. Consulte RSS e os limites registrados. `elapsed_seconds` pode acumular retomadas; `run_metrics` descreve a chamada atual.

### 3.2 CP-SAT do OR-Tools

```bash
python src/exact_methods/cpsat.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/cpsat --workers 4 --seed 1 --time-limit 60 --total-time-limit 300
```

O código externo limita TEC e chama o CP-SAT para provar o menor makespan e, depois, o menor TEC para esse makespan. Após provar um ponto, reduz o teto de TEC em uma unidade inteira escalada.

O modelo usa intervalos opcionais por tarefa/máquina/modo, `AddExactlyOne` para a escolha única, `AddNoOverlap` por máquina e `AddCircuit` para definir os sucessores imediatos e seus setups. `AddElement` consulta a tabela de custo por início. A primeira minimização de makespan sem teto de energia pode omitir essa tabela; o custo publicado é recalculado do schedule.

O tratamento multiobjetivo é uma sequência de otimizações lexicográficas com epsilon-restrição, implementada no driver. As duas etapas precisam retornar `OPTIMAL` para publicar o ponto. Depois, `TEC_units - 1` exige melhora estrita: uma unidade escalada não significa uma unidade monetária inteira. `INFEASIBLE` no teto seguinte encerra a fronteira; `FEASIBLE` ou `UNKNOWN` não certificam a etapa. A preparação e a busca são CPU; o modelo recusa custo escalado acima de int64.

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

Uma execução nova começa com frente vazia, sem carregar baselines ou soluções de outro método. Cada tarefa escolhe uma opção `(máquina, início, modo)`, já com término dentro de `H`. Máscaras de bits representam os horários ainda permitidos. A busca escolhe a tarefa com menos opções e prioriza términos mais cedo; isso ordena a exploração sem excluir alternativas.

A propagação usa uma separação mínima otimista, calculada por Floyd–Warshall com a menor duração dos possíveis intermediários. Assim, não exige prematuramente o setup direto entre tarefas que ainda podem deixar de ser consecutivas. Uma lacuna com setup incompatível só é eliminada antecipadamente quando não cabe tarefa intermediária; a folha verifica os setups consecutivos completos. Limites inferiores de custo, término e carga permitem podar um ramo se um ponto viável já descoberto for não pior nos dois objetivos, mesmo perante esses limites otimistas. A dominância também filtra candidatos em blocos quando a frente muda.

O progresso mede cobertura de subárvores do produto de opções, incluindo combinações descartadas sem execução. A razão é atribuída à primeira poda aplicada; não é uma decomposição causal das melhorias. Cobertura não é percentual da fronteira descoberta e não permite extrapolar linearmente o tempo restante. Podas por inviabilidade eliminam schedules impossíveis; podas por dominância também podem eliminar schedules viáveis que não melhorariam a frente.

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

Cada ponto do JSON registra a `origem`: regra, α e passo do ajuste. Em empate na construção ponderada, prevalecem o menor término da máquina e depois o menor TEC. No ajuste, uma redução de TEC sem aumento de Cmax tem prioridade. Cada troca aceita reduz estritamente o custo, e o procedimento termina quando não há troca admissível que economize energia.

A construção não realoca tarefas já inseridas para outra máquina; o ajuste posterior revê somente os modos e reduz TEC. Sem espera voluntária, soluções que dependem de adiar tarefas ficam fora de seu alcance. A varredura de pesos é gulosa e não garante os ótimos ponderados nem todos os pontos da fronteira. A implementação mantém custos/términos por máquina e prefixos de tarifa para evitar recálculos completos a cada sondagem.

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

A heurística aceita **um arquivo por chamada**. Para cada sequência de partida, a DP custa O(tarefas × horizonte × modos) por máquina; várias sequências distintas repetem esse trabalho. Com modos livres, partidas que diferem apenas nos modos são deduplicadas.

Para a sequência fixa de uma máquina, `f_i(t)` é o menor custo até a tarefa `i` terminando exatamente em `t`, e `g_i(t)` é o menor custo terminando até `t`. A transição combina o custo do processamento com `g_{i-1}(t - duração - setup)`, minimizando sobre os modos permitidos. Esse mínimo acumulado admite espera. As curvas das máquinas são somadas para cada limite de Cmax; as sequências de partida são unidas pelo filtro de Pareto. A certificação vale para as sequências consideradas, não para todas as alocações e ordens do problema.

As configurações principais das heurísticas são as descritas acima: 11 pesos e três ordens na construtiva; partidas da construtiva e modos livres na ociosidade. `--pesos`, `--base` e `--modos-fixos` permitem estudos de sensibilidade ou variantes, que devem ser identificados nos resultados. As heurísticas são determinísticas e não precisam de replicações por seed.

Para usar o resultado da seção 4.1 como partida e isolar apenas o efeito da espera:

```bash
python src/heuristics/ociosidade/ociosidade.py data/input/set1/6_2_1439_3_S_1-9.dat --base data/output/manual/heuristica_construtiva/6_2_1439_3_S_1-9.json --modos-fixos --output-dir data/output/manual/ociosidade_modos_fixos
```

O JSON de partida precisa ter `front` e um `schedule` completo em cada ponto; um resumo apenas com pares de objetivos não serve. O código confere o hash quando ele está presente e revalida os schedules; se o hash estiver ausente, confira a procedência. Ganhos com modos livres não podem ser atribuídos exclusivamente à espera, pois a DP também pode melhorar os modos.

## 5. Executar as meta-heurísticas

Os comandos abaixo são execuções curtas de demonstração. Os métodos criam suas próprias soluções iniciais e produzem frentes aproximadas, sem certificação global. Usam sequências por máquina no formato `(tarefa, modo, espera)`. A posição define a ordem, e a espera é acrescentada após o setup. O avaliador compartilhado verifica tarefas, máquinas, modos, setups e horizonte e calcula os dois objetivos.

### 5.1 VNS/VND manual

```bash
python src/metaheuristics/vns_vnd.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/vns_vnd_seed1 --seed 1 --max-evaluations 500
```

O método combina busca local VND e perturbações VNS, mantendo uma frente não dominada. As cinco vizinhanças alteram modo, espera, posição na mesma máquina, alocação entre máquinas e troca de tarefas. Uma melhoria por dominância faz o VND voltar à primeira vizinhança.

O padrão é 10.000 avaliações e seed 1. Também aceita `--initial-solutions`, `--max-candidates-per-neighborhood` e `--shaking-attempts`. O orçamento conta avaliações, não segundos. Uma falha de construção inicial não prova inviabilidade da instância.

Os padrões dessas três opções são, respectivamente, 4, 100 e 20. O arquivo Pareto mantém alternativas incomparáveis encontradas, embora o avanço local do VND exija melhoria por dominância. O limite de candidatos vale por chamada à vizinhança; não equivale a explorar todos os vizinhos possíveis.

### 5.2 SPEA2 via pymoo

```bash
python src/metaheuristics/spea2.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/spea2_seed1 --seed 1 --max-evaluations 500 --population-size 50
```

A seleção do SPEA2 usa dominância, força das soluções e densidade. Os operadores próprios recombinam e alteram máquina, sequência, modo e espera. A execução é incremental: o pymoo gera um descendente por iteração; não equivale ao regime geracional clássico. O orçamento deve ser pelo menos o tamanho da população. Candidatos inviáveis também consomem avaliações. O survival usa `SPEA2Survival(normalize=False)` para evitar divisão por amplitude zero. `--crossover-probability` e `--mutation-probability` controlam os operadores.

Essa escolha mantém a densidade sensível às unidades brutas de Cmax e TEC. Candidatos inviáveis recebem `G=1` e viáveis `G=-1`; os objetivos fictícios dos rejeitados não são exportados como soluções. Duplicatas são permitidas e contam como tentativas. Os padrões são população 100, 10.000 avaliações, crossover 0,9, mutação 0,3 e seed 1.

### 5.3 MOEA/D via pymoo

```bash
python src/metaheuristics/moead.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/moead_seed1 --seed 1 --max-evaluations 500 --population-size 50 --n-neighbors 10
```

Usa MOEA/D nativo, directions uniformes, Tchebycheff e escala `Cmax/H`, `TEC/max_cost`. Configure `2 <= n_neighbors <= population_size` e orçamento suficiente para avaliar a população inicial. O driver `ask/tell` respeita o cap de tentativas inclusive em varreduras incompletas. Descendentes inviáveis consomem uma tentativa e são substituídos por cópias viáveis já avaliadas. Também aceita `--prob-neighbor-mating`, `--crossover-probability` e `--mutation-probability`.

Há uma direção por indivíduo; direções uniformes distribuem pesos, sem garantir distribuição uniforme de pontos na frente. O ideal é atualizado com soluções avaliadas pela própria busca. O fallback copia um indivíduo da população corrente, sem nova avaliação; não é reparo nem uma tentativa viável adicional, e pode reduzir diversidade. A inicialização precisa produzir uma população viável. Os padrões são população 100, vizinhos 20, probabilidade local 0,9, crossover 0,9, mutação 0,3, 10.000 avaliações e seed 1. AGE e MOEA/D exigem pymoo 0.6.2 em suas verificações de versão.

### 5.4 AGE-MOEA via pymoo

```bash
python src/metaheuristics/age.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/age_seed1 --seed 1 --max-evaluations 500 --population-size 50
```

O AGE-MOEA usa `AGEMOEA` do pymoo 0.6.2, com seleção, normalização geométrica e sobrevivência nativas. Reutiliza o amostrador e os operadores de schedules de `spea2.py`; isso não executa a seleção do SPEA2. A busca é geracional, com descendentes em lotes do tamanho da população e último lote reduzido ao saldo do orçamento. Duplicatas são permitidas e cada tentativa, inclusive inviável, consome avaliação. Não há reparo ou fallback de descendentes. A população inicial precisa ser viável.

Os padrões do solver são seed 1, população 100, 10.000 avaliações, crossover 0,9 e mutação 0,3. A frente final é reavaliada e filtrada por objetivos inteiros exatos, embora a seleção interna da biblioteca use floats. O executável aceita um arquivo por chamada. Parâmetros recomendados por uma calibração precisam ser passados explicitamente; não substituem esses padrões automaticamente.

### 5.5 Repetições e orçamento

A seed inicializa a sequência pseudoaleatória usada na construção inicial e nas decisões posteriores da busca. Seeds são replicações experimentais, não soluções prontas nem parâmetros a otimizar.

As meta-heurísticas usam `--overwrite` para substituir um resultado existente; não oferecem a retomada `--resume` dos métodos exatos. Para repetir com outra seed, mude **a seed e o diretório de saída**. Apenas mudar a seed não muda automaticamente o nome do arquivo.

```bash
python src/metaheuristics/spea2.py data/input/set1/6_2_1439_3_S_1-9.dat --output-dir data/output/manual/spea2_seed2 --seed 2 --max-evaluations 500 --population-size 50
```

SPEA2, MOEA/D e AGE-MOEA reavaliam os sobreviventes ao final: `post_search_validations` registra essas verificações fora do orçamento da busca. Encerrar as avaliações não prova que a fronteira aproximada é ótima.

Nesses três métodos, a frente exportada vem da população final, não de um arquivo ilimitado com todos os pontos já visitados. A filtragem inteira final garante não dominância entre os sobreviventes, mas não recupera soluções perdidas pela seleção em float. Duplicatas na população podem reduzir diversidade. Os timers de busca desses runners incluem inicialização e busca, excluindo validação final e escrita; no AGE, a compilação inicial do Numba pode afetar a primeira execução. Compare tempos com o mesmo protocolo, ambiente e tratamento desse custo.

### 5.6 Calibrar as meta-heurísticas com Optuna

O calibrador varia somente os parâmetros que os arquivos atuais de
`src/metaheuristics/` já aceitam. As implementações, operadores, avaliação de
makespan/energia, setups e horizonte permanecem intactos. Abra o menu:

```bash
python src/hyperparameters_tuning/main.py
```

Escolha MOEA/D, SPEA2 incremental, AGE-MOEA ou VNS/VND e CPU sequencial ou paralela.
`main.py` centraliza a interface; há um arquivo de calibração por algoritmo e
`common.py` compartilha métrica, Optuna/TPE, processos e persistência. As
bibliotecas estão no `requirements.txt` da raiz.

| Parâmetro nativo | Algoritmos | Valores padrão |
|---|---|---|
| `population_size` | MOEA/D, SPEA2, AGE | 20, 50, 100, 150, 200, 300 |
| `max_evaluations` | Todos (só no modo `effort`) | 2000, 4000, 8000, 12000, 20000 |
| `n_neighbors` | MOEA/D | 2, 5, 10, 15, 20 |
| `prob_neighbor_mating` | MOEA/D | 0; 0,25; 0,5; 0,75; 0,9; 1 |
| `crossover_probability` | MOEA/D, SPEA2, AGE | 0,2; 0,4; 0,6; 0,7; 0,9; 1 |
| `mutation_probability` | MOEA/D, SPEA2, AGE | 0,01; 0,05; 0,1; 0,2; 0,3; 0,5; 0,7 |
| `initial_solutions` | VNS/VND | 1, 2, 4, 8, 16 |
| `max_candidates_per_neighborhood` | VNS/VND | 10, 25, 50, 100, 200 |
| `shaking_attempts` | VNS/VND | 1, 5, 10, 20, 40 |

Cada campo tem pelo menos cinco valores. A grade cobre exatamente os campos dos
Config atuais, exceto `seed`: seeds são replicações, mantidas iguais para todas
as configurações. O número de vizinhos é passado diretamente em `n_neighbors`,
sem converter uma fração. A grade padrão é compatível com todas as populações.
Método de crossover, método de mutação, movimentos por mutação, passo de espera e
gerações não são opções expostas pelas implementações atuais e não são calibrados.
Escolhas fixas de cada variante estão registradas no protocolo.

Existem dois regimes para os quatro algoritmos:

- `--budget-mode evaluations --max-evaluations 8000` (padrão): mantém esse limite
  igual para todas as configurações e varia os demais parâmetros, comparando
  qualidade com o mesmo orçamento de tentativas.
- `--budget-mode effort`: também varia `max_evaluations`. O score não penaliza
  tempo, então o TPE tende a escolher o maior limite. Foi o que aconteceu nos
  estudos v4: o MOEA/D escolheu 20000. Use apenas por opção explícita.

O protocolo v5 segue a decisão do grupo após a orientação do professor:
**60 trials, 6 entradas (duas por porte), 8000 avaliações fixas e 3 seeds**,
seguido de uma **fase de confirmação** em orçamentos maiores (abaixo). Nos
estudos v4, as dez entradas de 6–14 tarefas davam HV entre 0,95 e 0,98 para
quase qualquer configuração e pouco discriminavam. Também por isso
`population_size` ganhou 300 e `mutation_probability` ganhou 0,7: os melhores
trials v4 ficaram no limite superior da grade.

```bash
python src/hyperparameters_tuning/main.py --algorithm moead --workers 4
python src/hyperparameters_tuning/main.py --algorithm spea2 --workers 4 --trial-timeout 900
python src/hyperparameters_tuning/main.py --algorithm age --budget-mode effort --workers 4
python src/hyperparameters_tuning/main.py --algorithm moead --list-space
```

`--trial-timeout SEGUNDOS` é um limite de segurança por trial; o menu sugere
900 s (15 min). Ele é verificado antes de cada execução (entrada × seed), sem
interromper uma execução em andamento. Um trial que excede o limite vira FAIL e
a campanha continua. O critério de comparação continua sendo o número de
avaliações, que não depende da máquina; o tempo serve apenas para descartar
configurações inviáveis na prática. O valor fica no protocolo.

`--list-space` mostra os valores sem iniciar uma campanha. `--search-space
minha_grade.json` aceita um objeto JSON com exatamente as chaves da grade do
algoritmo e listas de valores. Grades focadas podem ter menos de cinco níveis.
Todas as populações precisam caber no menor limite da grade no modo effort; em
avaliações fixas, populações maiores que o limite são removidas. Todo valor de
`n_neighbors` deve caber na menor população restante. Para testar mais de 20
vizinhos, aumente também a menor população da grade personalizada. Combinações
incompatíveis são recusadas antes de criar um estudo, sem truncar valores.

O limite de avaliações é um controle de esforço já existente nos métodos. Não
se impõe uma quantidade de gerações por fora: SPEA2 mantém um descendente por
passo depois da inicialização; AGE usa lotes de tamanho P e MOEA/D percorre os P
subproblemas. O último lote/varredura pode ser parcial. Gerações registradas nos
resultados são apenas métricas derivadas do consumo. VNS pode terminar antes do
limite quando não há movimentos avaliáveis. Rejeições contam como tentativas.

As entradas padrão são duas por porte: pequenas `6_2_1439_3_S_1-9` e
`14_2_1439_3_S_1-9_derivada`; médias `50_10_1439_5_S_1-9` e `50_20_1439_5_S_1-9`;
grandes `250_10_1439_5_S_1-9` e `250_20_1439_5_S_1-9`. As seeds são 11/29/47.
Use `--inputs arquivo.dat pasta` e `--seeds 11,29,47` para selecionar outros
casos. Caminhos relativos são resolvidos na raiz do projeto; conteúdos idênticos
duplicados são recusados. Cada trial avalia uma configuração em todas as entradas
e seeds. Com os padrões, são 60 × 6 × 3 = 1080 buscas por algoritmo, com
8000 tentativas cada, além das validações finais. Pelos tempos dos estudos v4,
isso dá cerca de 7–9 min por trial e 2–2,5 h com 4 workers. A primeira proposta usa valores de referência compatíveis com a grade: P=100, E=8000, n_neighbors=20, acasalamento/crossover=0,9,
mutação=0,3; VNS começa com 4 soluções, 100 candidatos e 20 tentativas de shaking.
O TPE possui dez trials iniciais antes da modelagem adaptativa e explora somente
uma parte da grade, sem garantir a melhor configuração global.

A configuração escolhida é generalista para o conjunto da campanha: maximiza a
média entre instâncias do hipervolume mediano entre seeds. Os objetivos são
normalizados em [0,1] com limites individuais exatos derivados somente da entrada,
relaxando setups e conflitos para obter esses limites. Extremos de custo por
horário são calculados nas bordas das tarifas e do domínio. Eixos constantes
viram zero e valores fora dos limites causam erro. A referência é (1,05;1,05),
com HV dividido por 1,05². Cada instância recebe o mesmo peso. Esse escore não
altera o avaliador nem a normalização interna dos algoritmos.

Não há leitura de baselines ou resultados da comparação final, nem pruning.
Falha conhecida da construção inicial recebe HV zero naquele par instância/seed;
é registrada e não prova inviabilidade da entrada. Erro técnico falha o trial e
encerra a campanha. A recomendação é provisória: valide em seeds e instâncias
reservadas, preferencialmente com orçamento comum. As entradas padrão já
participaram de análises anteriores e não são um conjunto de teste independente.

Resultados em `data/output/hyperparameters_tuning/<algoritmo>/<nome>/`:

- `protocol.json`: entradas, hashes, grade, escolhas fixas e versões.
- `study.sqlite3`: histórico Optuna para retomada, ignorado pelo Git.
- `trials.csv`: parâmetros, esforço, score e estados COMPLETE/FAIL.
- `best_parameters.json`: campos diretamente reutilizáveis no Config nativo.
- `trials/trial_*.json`: evidência por entrada/seed, tempo, avaliações e frente.
- `confirmation/`, `confirmation.csv` e `confirmation.json`: fase de confirmação.

```bash
python src/hyperparameters_tuning/main.py --algorithm moead --workers 4 --trials 80 --resume
```

`--trials` é o total desejado, incluindo configurações completas ou falhas. O
protocolo é v5 e o nome padrão é `<algoritmo>_tpe_v5`.
Código, dados, seeds, grade, workers e dependências precisam coincidir para
retomar; escolha outro estudo ao mudar o protocolo. O checkpoint é por trial:
a população ou busca dentro de uma tentativa interrompida não é salva. Trials
órfãos viram FAIL na retomada. Faça backup da pasta inteira do estudo.

O coordenador é o único escritor SQLite e uma trava impede duas campanhas na
mesma pasta. Workers executam trials em processos CPU, limitando threads numéricas.
Resultados de cada lote são entregues ao Optuna na ordem do trial. A RNG do TPE
usa sampler_seed + número do trial, sem reiniciar a sequência na retomada.
Alterar workers ou interromper um lote pode mudar a sequência adaptativa;
processos já iniciados podem precisar concluir antes do programa fechar.

**Fase 2: confirmação em vários orçamentos.** O TPE compara configurações sob
um único limite (8000). Para verificar se a escolha se mantém com mais esforço e
quanto o HV ainda cresce (convergência), reavalie as melhores configurações
distintas nas mesmas entradas e seeds do protocolo:

```bash
python src/hyperparameters_tuning/main.py confirm --algorithm moead --top 5 --budgets 8000,20000,50000 --workers 4
```

O banco Optuna é apenas lido. O comando recusa rodar se o código ou as entradas
mudaram desde a calibração. Cada par configuração × orçamento é salvo em
`confirmation/trial_<n>_E<orçamento>.json`; repetir o comando continua de onde
parou. `confirmation.json` traz o score por orçamento, o ranking em cada
orçamento, o ganho de HV entre orçamentos consecutivos e `recommended`: o
primeiro colocado no maior orçamento. Com os padrões, custa cerca de 1,5 h com
4 workers, porque 50000 avaliações custam cerca de 6× o de 8000.

A opção GPU informa que está indisponível; `--device gpu` recusa a execução.
Os algoritmos usam objetos Python e avaliação CPU. Optuna ou Ray não convertem
operadores para CUDA. O paralelismo oferecido é entre configurações, com possível
aumento de memória; buscas muito curtas podem não acelerar.

### 5.7 Consultar e aplicar uma calibração salva

A evidência de cada estudo está no próprio diretório de resultados: `protocol.json` define o experimento; `trials.csv` resume os trials; `trials/trial_*.json` contém as frentes e métricas; `best_parameters.json` identifica a configuração selecionada, seu score e o trial correspondente.

Há estudos salvos de [AGE-MOEA](data/output/hyperparameters_tuning/age/age_tpe/best_parameters.json) e [MOEA/D](data/output/hyperparameters_tuning/moead/moead_tpe/best_parameters.json). Eles usam o **protocolo v4 antigo**: 30 trials, 12 entradas e modo `effort`. Ficam como histórico e foram substituídos pelo protocolo v5 (seção 5.6). Não os trate como defaults do código.

Em um estudo v5 com confirmação, prefira `recommended.solver_config` de `confirmation.json` ao `best_parameters.json` da busca. Verifique em `ranking` se o primeiro colocado muda com o orçamento.

Para aplicar uma configuração, copie os campos de `solver_config` para as opções do solver: por exemplo, `population_size` corresponde a `--population-size`, e `max_evaluations` a `--max-evaluations`. Acrescente a entrada, uma seed de avaliação e um diretório de saída próprio. Os solvers não leem `best_parameters.json` automaticamente. A retomada da calibração também precisa do banco SQLite local; os JSONs e CSVs, sozinhos, não reconstituem o histórico Optuna.

## 6. Executar uma pasta e consultar opções

Os três exatos, VNS/VND, SPEA2, MOEA/D e a heurística construtiva aceitam um arquivo ou uma pasta; AGE-MOEA e a heurística de ociosidade aceitam um arquivo por chamada. Em uma pasta, processam os arquivos `*.dat` diretamente nela, em ordem, sem busca recursiva. O orçamento se aplica a cada arquivo. Exemplo com sua pasta de testes:

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
python src/hyperparameters_tuning/main.py --help
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

**Limitação atual da legenda:** o plotador geral lê os JSONs das meta-heurísticas, mas pode rotulá-los como “parcial; pontos provados”. Esse texto não certifica esses pontos: as duas heurísticas, VNS/VND, SPEA2, MOEA/D e AGE-MOEA produzem frentes aproximadas. Consulte o método e `pareto_proven` no JSON ao interpretar o gráfico.

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

### 7.3 Consultar experimentos e interpretar indicadores

Os diretórios abaixo contêm evidências de execuções específicas. Seus parâmetros, versões e tempos pertencem aos respectivos protocolos; não redefinem os padrões dos executáveis nem substituem uma nova execução.

| Evidência existente | Onde consultar |
| --- | --- |
| Medições da DP, limites, memória e rótulos | [desempenho.csv](data/output/custom_exact_dp/desempenho.csv) e `run_metrics` dos resultados da DP. |
| Piloto VNS/VND | [manifest.json](data/output/vns_vnd/piloto/manifest.json), [summary.csv](data/output/vns_vnd/piloto/summary.csv), `paired_coverage.csv`, `profiles.json` e `neighborhood_diagnostics.json` no mesmo diretório. |
| Piloto SPEA2 | [manifest.json](data/output/spea2/piloto/manifest.json), [summary.csv](data/output/spea2/piloto/summary.csv), `operator_sensitivity.csv` e `baseline_6_jobs.csv`. |
| Piloto MOEA/D | [manifest.json](data/output/moead/piloto/manifest.json), [summary.csv](data/output/moead/piloto/summary.csv), `sensitivity_paired.csv` e `confirmation_paired.csv`. |
| Piloto e configuração congelada AGE | [protocol.json](data/output/age/piloto/protocol.json), [recommendation.json](data/output/age/piloto/recommendation.json), [frozen_config.json](data/output/age/frozen_config.json) e [summary.csv](data/output/age/piloto/summary.csv). |
| Comparação salva de VNS/VND, SPEA2 e MOEA/D | [manifest.json](data/output/final_comparison/manifest.json), [summary.csv](data/output/final_comparison/summary.csv), [run_outcomes.csv](data/output/final_comparison/run_outcomes.csv), [statistical_tests.json](data/output/final_comparison/statistical_tests.json) e `figures/`. |
| Calibração Optuna | Diretórios e aplicação descritos na seção 5.7; não confundir esses estudos com os pilotos. |

Os pilotos usam quatro entradas (6 original, 14 derivada, 50 e 250 originais) e seeds 11/29/47. Isso é diferente das seis entradas padrão atuais do calibrador. A comparação salva em `final_comparison` abrange somente VNS/VND, SPEA2 e MOEA/D; não inclui AGE. Seu experimento A usa 13 entradas originais, dez seeds e 8.000 tentativas; B usa quatro entradas de 750 tarefas, cinco seeds e 2.000 tentativas; C usa uma entrada de 250 tarefas, cinco seeds e 20.000 tentativas. B e C são análises separadas de escala e orçamento. Consulte os outcomes de falha de inicialização; ausência de frente nessas células não prova inviabilidade.

**Indicadores:** HV maior indica maior área dominada até o ponto de referência, desde que escala e referência sejam as mesmas. IGD+ menor indica menor distância à frente de referência, que pode ser apenas uma união empírica de soluções encontradas, sem prova de ótimo. Coverage `C(A,B)` é a fração de pontos de B dominados ou igualados por A; não é simétrica. Menores Cmax e TEC de uma frente podem pertencer a schedules diferentes. Cardinalidade da frente, rapidez e um extremo isolado não determinam qualidade multiobjetivo.

A normalização externa dos indicadores é distinta das escalas internas dos solvers. Em `final_comparison/normalization.py`, seja `dmin_j` a menor duração individual admissível da tarefa j:

```text
C_LB = max(max_j dmin_j, ceil(sum_j dmin_j / m))
C_UB = H
TEC_LB = soma dos menores custos individuais admissíveis de cada tarefa
TEC_UB = soma dos maiores custos individuais admissíveis de cada tarefa
C_normalizado = (Cmax - C_LB) / (C_UB - C_LB)
TEC_normalizado = (TEC - TEC_LB) / (TEC_UB - TEC_LB)
```

Os custos e limites energéticos usam a mesma escala inteira. As opções individuais consideram máquina, modo e início; ignorar conflitos entre tarefas produz limites válidos, mas possivelmente frouxos. Extremos temporais são calculados nas bordas das tarifas e do domínio. A referência é `(1,05; 1,05)` e valores fora de `[0,1]²` causam erro, sem truncamento. O normalizador da comparação recusa denominadores degenerados; o calibrador em `src/hyperparameters_tuning/common.py` trata eixos constantes como zero. O calibrador ainda divide HV por `1,05²`; portanto seu score não é diretamente o HV bruto das tabelas dos pilotos/comparação. As validações e os limites por entrada estão em [normalization_validation.json](data/output/final_comparison/normalization_validation.json).

Compare resultados com a mesma entrada/hash, discretização, orçamento e definição de métrica. Baselines completos podem verificar pares exatos após a busca; resumos sem schedules não permitem validar escalonamentos. Referências empíricas favorecem os métodos que contribuíram para sua construção e não certificam convergência global. Limites frouxos podem comprimir diferenças geométricas. Nas análises estatísticas da comparação, a unidade é a instância (mediana entre seeds), não cada seed como problema independente; as conclusões se restringem à campanha correspondente.

**Reprodução dos auxiliares:** os scripts `run_pilot.py`/`summarize*.py` nas pastas de pilotos e `run_final.py`/`analyze_final.py` em `final_comparison` usam destinos e protocolos próprios. Não são substitutos genéricos das CLIs das seções 3–6. Exigem os brutos, versões e hashes compatíveis; um clone pode não conter os arquivos ignorados. `analyze_final.py --publish` substitui análises após arquivar as anteriores. Repetições dessas campanhas devem ocorrer em uma cópia compatível, preservando as evidências existentes.

O pacote local AGE é identificado por [archive_manifest.json](data/output/age/archive_manifest.json), [archive_inventory.json](data/output/age/archive_inventory.json) e `archive.sha256`. Quando o pacote estiver disponível, sua verificação é:

```bash
python data/output/age/archive_pilot.py verify
```

O pacote e os brutos AGE são locais, não publicados como Release, e não são necessários para executar o solver. O comando `build` exige também os documentos originais removidos na consolidação e seus hashes: **não funciona diretamente neste checkout sem recuperar o snapshot correspondente**. Ao restaurar um pacote, verifique hash/inventário e extraia primeiro fora do repositório; não sobreponha fontes atuais. Manifestos preservam hashes de documentos da época e não foram reescritos para ocultar essa dependência.

## 8. Validar a instalação e tratar erros comuns

```bash
python -m unittest discover -v
```

A suíte atual cobre representação/avaliação, VNS/VND, SPEA2, MOEA/D, AGE-MOEA, as duas heurísticas, normalização e calibração. Não há uma bateria específica de regressão dos três solvers exatos na suíte atual.

Alguns testes da campanha em `data/output/final_comparison/` dependem de `fcntl` (Unix); o Windows não fornece esse módulo. Verificações de arquivo congelado também exigem os hashes do snapshot correspondente. Essas limitações são distintas dos testes dos solvers atuais.

Para verificar somente as heurísticas:

```bash
python -m unittest tests.test_heuristica_construtiva tests.test_heuristica_ociosidade -v
```

Os protótipos de integração ainda presentes em `src/metaheuristics/` podem ser exercitados separadamente:

```bash
python src/metaheuristics/pymoo_spike.py data/input/set1/6_2_1439_3_S_1-9.dat
python src/metaheuristics/age_spike.py data/input/set1/10_2_1439_3_S_1-9.dat --seed 23 --population-size 8 --budget 41 --offspring-size 8
python -m unittest tests.test_age_spike tests.test_age tests.test_moead tests.test_spea2 -v
```

Esses spikes verificam a integração e imprimem diagnósticos; não são execuções de qualidade dos solvers finais. Em particular, o crossover de passagem do spike pymoo não descreve a recombinação dos runners atuais. Números de testes aprovados em manifestos antigos correspondem àquele snapshot; execute a suíte atual para verificar seu ambiente.

| Mensagem/situação | Como proceder |
| --- | --- |
| `can't open file` | Execute na raiz, confira o caminho e use `/` no Git Bash. |
| `ModuleNotFoundError` de dependência externa | Instale `requirements.txt` com o mesmo Python que executa o script. |
| `ModuleNotFoundError: fcntl` em scripts de campanha | Esse módulo é de Unix; execute a ferramenta correspondente em ambiente compatível. |
| `Esperado '...'`, `Faltam valores` ou dados adicionais | Confira a ordem dos campos e as dimensões dos vetores/matrizes; remova comentários. |
| Ponta fora do respectivo dia | Use índices absolutos e fim inclusivo dentro do dia correspondente. |
| Job não cabe no horizonte | Revise processamento, velocidades e `H`; nenhuma opção individual coube. |
| Checkpoint/resultado não encontrado com `--resume` | Inicie uma execução nova ou aponte para o diretório onde está o salvamento compatível. |
| Resultado já existe | Use outro `--output-dir`, `--resume` nos exatos ou substitua conscientemente com `--restart`/`--overwrite`. |
| DP limitada a 13 tarefas | Use uma entrada menor; `--max-jobs` é uma ampliação experimental, com custo exponencial. |
| `incomplete` por tempo/memória | Consulte o motivo, ajuste o orçamento e retome quando suportado. Isso não prova inviabilidade. |
