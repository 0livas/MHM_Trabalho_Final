# MHM — otimização multiobjetivo

Minimização do makespan e do custo de energia em máquinas paralelas não relacionadas, com modos de operação, setups entre tarefas consecutivas e tarifas por horário. O projeto contém métodos exatos, uma infraestrutura comum de representação/avaliação, VNS/VND multiobjetivo manual e o spike de integração pymoo; MOEA/D e SPEA2 ainda não estão implementados.

```
data/
  input/set1/               # entradas pequenas e derivadas identificadas
  input/set2/               # entradas originais grandes
  baselines/                # fronteiras completas para comparação futura
  output/
    custom_exact/           # backtracking, resultado e checkpoint
    custom_exact_dp/        # DP própria, resultado e desempenho.csv
    cpsat/                   # OR-Tools
    plots/                   # gráficos
    ...                      # relatórios e métricas já calculados
src/
  exact_methods/
    custom_exact.py
    custom_exact_dp.py
    cpsat.py
  schedule.py               # representação, decoder, validação e avaliação comuns
  heuristics/                # reservado para implementação 2
  metaheuristics/            # VNS/VND manual e spike pymoo
  problem.py                # leitura, regras e custo compartilhados
  plot_pareto.py
tests/                       # unittest da infraestrutura e do VNS/VND
requirements.txt
```

Instale as dependências uma vez, na raiz do projeto:

```powershell
python -m pip install -r requirements.txt
```

Execute um método passando o arquivo de entrada. `--restart` substitui a execução anterior daquele método e entrada:

```powershell
python src/exact_methods/custom_exact_dp.py data/input/set1/6_2_1439_3_S_1-9.dat --restart
python src/exact_methods/cpsat.py data/input/set1/6_2_1439_3_S_1-9.dat --restart --workers 4 --total-time-limit 300
python src/exact_methods/custom_exact.py data/input/set1/6_2_1439_3_S_1-9.dat --restart --time-limit 300
python src/plot_pareto.py
```

Cada método salva automaticamente em `data/output/<algoritmo>/<entrada>.json`. Os scripts também aceitam uma pasta de entradas; o orçamento é por arquivo. Os métodos próprios usam somente a biblioteca padrão do Python. OR-Tools é a dependência do CP-SAT, Matplotlib desenha os gráficos e pymoo é usado pelo spike experimental de integração. Execute `python -m unittest discover -v` para validar a infraestrutura comum e o VNS/VND.

O VNS/VND multiobjetivo manual está em `src/metaheuristics/vns_vnd.py`. Por padrão, ele usa 10.000 avaliações e seed 1, cria schedules iniciais próprios e se recusa a sobrescrever um resultado anterior. Para uma execução curta:

```powershell
python src/metaheuristics/vns_vnd.py data/input/set1/6_2_1439_3_S_1-9.dat --seed 1 --max-evaluations 500
```

Os limites de candidatos por vizinhança e de tentativas de shaking também são configuráveis por argumentos CLI. A frente aproximada e os metadados da execução são salvos em `data/output/vns_vnd/<entrada>.json`; use `--overwrite` para substituir esse arquivo explicitamente. Cada ponto contém `tec_exact`, o schedule decodificado compatível com os resultados existentes e a representação por máquina usada pelo algoritmo. A saída não certifica a frente global.

Para retomar uma execução existente, substitua `--restart` por `--resume`. O backtracking precisa do resultado e do `.checkpoint.json`; a DP preserva os epsilons já provados e reconstrói suas tabelas. Checkpoints, caches, arquivos temporários, logs e configurações locais do editor são ignorados pelo Git. Os resultados JSON, CSV, Markdown, PDF e PNG são mantidos.

O output histórico do CP-SAT de seis tarefas é um resumo completo dos pares provados, sem os escalonamentos originais. Ele serve para comparação/plotagem; para recalculá-lo, use `--restart`.

O `custom_exact_dp.py` incorpora o cálculo do makespan mínimo. Depois minimiza energia com `Cmax <= epsilon`, para cada inteiro do mínimo até `H = n_day * (hl+1)`. No set1, o término máximo é 1440. Duração = `ceil(processing/speed)`; intervalos de processamento são `[start,end)`. Tarefas estão disponíveis em zero, sem preempção ou setup inicial. Espera e setup não cobram energia. `max_cost` só normaliza o custo.

Para medir desempenho:

```powershell
python src/exact_methods/custom_exact_dp.py data/input/set1/12_2_1439_3_S_1-9_derivada.dat --profile --restart --total-time-limit 600 --memory-limit-mb 1024
```

`--profile` acrescenta uma linha por execução ao `desempenho.csv` da DP: tempo, pico de RSS, transições, rótulos e hash do código. Os padrões são **13 tarefas, 600 segundos e 1024 MiB**. `--max-jobs` permite experimentar um teto maior explicitamente. Os limites são cooperativos: tempo/RSS são verificados periodicamente durante a preparação de energia e entre epsilons, podendo ultrapassar o orçamento entre verificações. A etapa inicial de makespan e a geração de opções não são interrompidas por esses limites. `0` desativa um limite de tempo ou memória.

As entradas com `_derivada` foram extraídas de `50_10_1439_5_S_1-9.dat`: primeiras n tarefas, máquinas 0 e 1, modos originais 0, 2 e 4 (velocidades 1,2 / 1 / 0,8). Processamentos, setups, potências, tarifas e horizonte vêm dessa fonte. Não são instâncias publicadas no artigo. O normalizador `max_cost` foi preservado; as medições usam TEC sem normalização. Veja [desempenho da DP](data/output/custom_exact_dp/desempenho_dp.md).

Uma fronteira completa da DP publica automaticamente um baseline em `data/baselines/<entrada>_custom_exact_dp.json`, com hash da entrada, objetivos exatos e escalonamentos. `status=complete` e `pareto_proven=true` distinguem referências ótimas de resultados provisórios. Para futuras heurísticas, compare apenas resultados da mesma entrada e discretização.

O [esboço de representação](data/output/representacao_solucao.md) descreve sequências por máquina, modos e esperas. Inclui uma [figura de evolução genética](data/output/plots/representacao_genetico.png), com pais, cruzamento, mutação e seleção Pareto, e explica os valores usados. É uma ilustração, sem implementação das etapas 2 e 3.

Os resultados anteriores foram consolidados em [analise_metodos_exatos.json](data/output/analise_metodos_exatos.json), com frontes repetidas armazenadas uma única vez por referência. O [relatório anterior](data/output/relatorio_completo_metodos_exatos.pdf) e a [documentação histórica](data/output/documentacao_anterior.md) preservam a análise original; seus nomes de funções e caminhos descrevem a estrutura da época. Os geradores de análise/PDF, a versão MILP complementar e os logs antigos foram removidos. A comparação com o artigo continua metodológica: seus experimentos exatos usam intervalos de dez minutos e pesos de soma ponderada, enquanto usamos minutos e epsilon-restrição.
