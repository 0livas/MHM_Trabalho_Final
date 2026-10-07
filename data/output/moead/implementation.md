# MOEA/D com pymoo 0.6.2

Implementação em `src/metaheuristics/moead.py`, preparada para release-check independente e piloto posterior. Não há tuning, NSGA-II, consulta a baseline, método exato ou mudança em SPEA2/VNS/VND. O algoritmo instanciado é exatamente `pymoo.algorithms.moo.moead.MOEAD`, sem subclasse ou reimplementação de suas equações.

## Investigação da API instalada

A implementação instalada, versão 0.6.2, foi inspecionada com `inspect.getsource`: `MOEAD`, `NeighborhoodSelection`, `default_decomp`, `LoopwiseAlgorithm`, `Algorithm.ask/tell/advance`, `Evaluator`, `Decomposition`, `Tchebicheff` e `UniformReferenceDirectionFactory`.

- `pop_size = len(ref_dirs)`. A implementação aceita `n_neighbors`, `prob_neighbor_mating`, `decomposition` e operadores customizados.
- As directions uniformes de Das–Dennis, com dois objetivos e `n_partitions = P-1`, são exatamente P pontos `(i/(P-1), 1-i/(P-1))`, incluindo os dois extremos. Não dependem da seed.
- A vizinhança é calculada por distância euclidiana entre directions: `np.argsort(cdist(...), kind="quicksort")[:, :n_neighbors]`. Inclui o próprio subproblema. Empates seguem a ordenação do pymoo/NumPy instalada; as versões são registradas no audit.
- Para cada subproblema, em ordem aleatória por varredura, `NeighborhoodSelection` escolhe dois pais distintos na vizinhança com a probabilidade configurada; no outro ramo, escolhe na população inteira. Por isso exigimos `2 <= n_neighbors <= P` e `P >= 2`.
- `_next` chama mating para um descendente e faz `yield` desse indivíduo. O ideal point é atualizado ao receber seus objetivos; `_replace` substitui os vizinhos cujo valor de decomposition é estritamente maior que o do descendente. Todos os vizinhos elegíveis podem ser substituídos.
- Não se configura `n_offsprings` como no SPEA2 incremental: o MOEA/D já produz um candidato por subproblema. Uma varredura completa avalia P descendentes.
- `_setup` faz `assert not problem.has_constraints()`. O trecho de replacement com constraints é apenas código comentado. A integração não declara `G` nem usa penalidade.
- Para dois objetivos, `default_decomp` retorna `Tchebicheff()`. A fórmula é o máximo dos desvios absolutos do ideal/utopian point multiplicados pelos pesos. Não há divisão por amplitude nem normalização automática. Selecionamos essa decomposition explicitamente, com `eps=0.0`.

## Plano implementado e organização

1. Reutilizar a representação/evaluator comuns e importar diretamente os componentes já validados do SPEA2.
2. Criar um `ElementwiseProblem` sem constraints e com escala fixa da instância.
3. Adaptar somente o hook de avaliação do `Evaluator` para rejeição com fallback viável em cache.
4. Dirigir o MOEA/D por `ask`, avaliação e `tell`, parando literalmente pelo contador de tentativas.
5. Reavaliar a população final e exportar Pareto exato; testar e instrumentar execuções reais pequenas.

Importam-se `ScheduleSampling`, `ScheduleCrossover`, `ScheduleMutation`, `_as_schedule` e o simples payload `ParetoSolution` de `spea2.py`. Não se importa nem chama a classe de problema, o runner, survival ou seleção SPEA2. O SPEA2 fica intacto. A importação dos operadores de seu módulo é uma dependência de organização, não da lógica de busca; evitou uma refatoração dos componentes publicados.

O sampling é o LPT randomizado existente, com checks locais de horizonte e sem avaliações completas, retries, baseline ou solver exato. Se a construção falhar para outra instância, a execução aborta claramente; o construtor não é uma prova de viabilidade para instâncias arbitrárias. Crossover combina atribuições, modos e waits dos dois pais e seus ranks de sequência. Mutation continua oferecendo modo, wait, inserção, swap e realocação.

## Escala e precisão

O pymoo recebe `F = (Cmax/H, float(tec_exact/max_cost))`. A divisão de energia ocorre como fração exata antes de uma única conversão para float. `H` e `max_cost` são constantes do arquivo de entrada, positivas, conhecidas antes da busca. Seus valores são registrados, incluindo numerador/denominador de `max_cost`. A escolha foi confirmada pelo usuário e segue a normalização já exposta pelo projeto.

Essas divisões preservam a ordenação de cada objetivo e a dominância matemática. Não consultam ótimos, frente exata, baseline ou estatísticas observadas/futuras. O ideal point é o adaptativo normal do MOEA/D nativo, calculado apenas a partir de soluções viáveis já avaliadas. A frente externa não é uma soma ponderada: é filtrada por `(Cmax, tec_units)` exatos.

`max_cost` é um normalizador da entrada, não uma certificação de amplitude nem garantia de `TEC/max_cost <= 1`. A escala fixa reduz a dependência de unidades, mas não garante amplitudes iguais ou uma distribuição uniforme de soluções na frente. Esse é um aspecto metodológico a avaliar no piloto, sem ajuste nesta etapa. Não se usa min–max por população, evitando divisão por amplitude zero; TEC constante, nulo ou de pequena amplitude continua finito. Directions uniformes cobrem os pesos, não garantem a descoberta dos extremos ótimos.

A evidência anterior de unidades inteiras foi complementada apenas para a nova conversão normalizada: para qualquer schedule viável, `tec_units <= m*H*max(preço_por_slot_em_units)`, pois processamento não se sobrepõe por máquina. Em todas as 22 entradas atuais, o maior limite é 52.563.446.208.000, abaixo de `2**46` e com ampla margem abaixo de `2**51`. Um passo de uma unidade exata é maior que o espaçamento relevante de float64 na razão escalada. Os testes também confrontam duas unidades consecutivas junto ao limite superior de cada entrada. Não há risco prático de colisão/inversão de TEC nesse dataset; isto não é promessa para novos dados arbitrariamente grandes. A exportação e a não dominância final sempre usam inteiros exatos.

## Viabilidade e orçamento

`max_evaluations` é o número de tentativas completas submetidas a `evaluate_schedule`, incluindo schedules que o evaluator rejeita. A população inicial conta integralmente e deve caber no orçamento.

O `ScheduleProblem` incrementa `attempts` imediatamente antes da única chamada completa. Se houver `ScheduleValidationError`, incrementa `rejected` e propaga a exceção, sem produzir `F` ou penalidade. O hook `FeasibleEvaluator._eval` captura essa exceção e copia `X/F` de um indivíduo sorteado uniformemente da população corrente já avaliada. O sorteio usa `algorithm.random_state`; não avalia nem cria um novo schedule. O indivíduo inválido é descartado antes de `tell`, de modo que nem ideal point nem vizinhança recebem seus objetivos. Uma inicialização inválida aborta, pois ainda não existe população viável para fallback.

O `Evaluator.eval` nativo soma uma avaliação para cada candidato original, inclusive aquele substituído pelo fallback. `skip_already_evaluated=False` deixa explícito que cada candidato pedido é uma tentativa, mesmo quando sua representação coincide com alguma anterior. Não há memoização de tentativas de busca nem avaliação duplicada por conversão/adaptação. `attempts = feasible_evaluations + rejected_evaluations = pymoo_evaluations`.

`Algorithm._post_advance` só atualiza a terminação ao fechar a varredura. Portanto usar apenas `minimize(..., termination=("n_eval", cap))` poderia ultrapassar caps não múltiplos. O driver público verifica `attempts < cap` antes de cada `ask`/avaliação; o próprio problema e o hook de batch também têm guards. Depois de cada avaliação, inclusive a última, `tell` aplica o replacement nativo. A busca termina no meio da varredura quando necessário. O generator pode preparar um descendente seguinte que nunca será avaliado; isso não consome uma tentativa completa. Não se consulta `algorithm.opt`, que pode estar desatualizado em uma varredura incompleta: usa-se `algorithm.pop` para a validação final.

Depois da busca, cada um dos P sobreviventes é reavaliado exatamente uma vez, mesmo quando há cópias na população. Essas P chamadas aparecem como `post_search_validations`, não afetam a busca e alimentam a filtragem Pareto exata, com remoção de objetivos duplicados. O tempo reportado mede setup/busca e exclui essas validações posteriores, seguindo a convenção SPEA2.

Fallback é uma política explícita de rejeição com substituição por solução conhecida; pode propagar um indivíduo viável por replacement, reduzir diversidade ou favorecer estagnação quando há muitas rejeições. Não é repair, não implica nova avaliação viável e não deve ser contado como tal. As taxas de rejeição devem ser acompanhadas no piloto.

## Execução e resultados

```bash
python src/metaheuristics/moead.py data/input/set1/6_2_1439_3_S_1-9.dat \
  --seed 11 --population-size 12 --n-neighbors 4 --max-evaluations 61
python -m unittest tests.test_moead -v
python data/output/moead/validate_smoke.py --output-dir /tmp/moead-new-audit
```

A CLI também expõe `--prob-neighbor-mating`, `--crossover-probability`, `--mutation-probability`, `--output-dir` e `--overwrite`. Defaults provisórios: população 100, vizinhos 20, mating 0,9, crossover 0,9 e mutation 0,3. Ao reduzir a população abaixo de 20 é necessário configurar uma vizinhança compatível; não há clipping silencioso.

Saída padrão: `data/output/moead/<instância>.json`. Arquivos existentes são recusados sem autorização explícita via `--overwrite`/`overwrite=True`, conforme a convenção dos runners existentes. Cada saída contém hash da entrada, versão pymoo, parâmetros/seed, decomposition, divisores, directions completas, população/vizinhos, orçamento e cinco contadores, tempo, objetivos exatos, schedule decodificado e representação completa. A execução é intencionalmente restrita ao pymoo 0.6.2: outra versão exige revalidar a integração; não se mudou `requirements.txt`.

## Evidências de validação

`tests/test_moead.py` cobre algoritmo nativo/replacement, directions/população/vizinhança, ramos de mating, reuso dos operadores, sampling viável/diverso/reprodutível, recombinação biparental, quatro dimensões de mutation, rejeição forçada e inicialização inválida, orçamento de inicialização e varreduras parciais, ausência de chamadas completas ocultas/duplicadas, reprodutibilidade inclusive com rejeições, frente exata/exportação, ausência de baseline/exato, escala constante/baixa/nula, proteção contra sobrescrita e resolução float do dataset.

`validation/audit.json` e `validation/runs/` registram os smokes reais instrumentados. O runner realiza três execuções por instância (seed 11, repetição seed 11, seed 29), com 61 tentativas/população 12/vizinhos 4 em 6, 50 e 250 jobs, e apenas inicialização de 4 indivíduos em 750 jobs. Instrumenta os pontos de entrada do evaluator comum, separa busca e pós-busca e captura populações após cada replacement. Essas populações e as frentes exportadas são verificadas somente depois do término. As chamadas adicionais do diagnóstico ficam em `diagnostic_validations_after_run`, separadas dos contadores do algoritmo. O audit registra hashes do código e versões do ambiente.

Esses smokes verificam integração, contabilidade, viabilidade e reprodução; não medem convergência nem certificam frente global. O release-check e o piloto independente permanecem etapas posteriores.

Validação desta implementação: `python -m unittest discover -v` passou os 88 testes (24 específicos de MOEA/D), em 7,171 s. `py_compile` passou para os 16 arquivos Python de `src`, `tests` e do runner de smoke. `git diff --check` e o check de whitespace dos novos arquivos passaram. Nenhum arquivo existente de SPEA2, VNS/VND, evaluator, baseline ou dependências foi alterado.

| Jobs | População | Vizinhos | Tentativas por execução | Viáveis / rejeitadas | Pontos seed 11 / seed 29 | Tempo de busca observado |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | 12 | 4 | 61 | 61 / 0 | 4 / 2 | 0,024–0,027 s |
| 50 | 12 | 4 | 61 | 61 / 0 | 3 / 4 | 0,161–0,185 s |
| 250 | 12 | 4 | 61 | 61 / 0 | 3 / 2 | 0,694–0,747 s |
| 750 | 4 | 2 | 4, somente inicialização | 4 / 0 | 1 / 2 | 0,508–0,541 s |

As execuções naturais curtas não produziram rejeições. A política de rejeição foi exercitada pelos testes que forçam todos os descendentes a exceder H: 31 tentativas = 8 viáveis iniciais + 23 rejeições, com 31 avaliações pymoo e 8 validações posteriores; somente caches viáveis chegaram ao replacement. A instrumentação desses testes confirma 39 chamadas completas totais, sem reavaliação do fallback.
