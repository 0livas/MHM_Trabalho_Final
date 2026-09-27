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

1. **Propagação de horários.** Cada domínio de inícios possíveis é uma máscara de bits. Ao colocar um job em uma máquina, a busca remove dos demais jobs dessa máquina os inícios que sobreporiam o processamento. Se algum job ficar sem opção, descarta o ramo.
2. **Escolha da próxima decisão.** Seleciona o job com menos opções restantes e testa primeiro as opções com término mais cedo. Isso muda a ordem da busca, **sem excluir** opções válidas, e ajuda a encontrar a primeira solução sem conhecimento prévio.
3. **Setup.** Um conflito entre jobs já escolhidos só é podado quando nenhum job restante poderia caber entre eles e reparar a adjacência. Na folha, o setup entre jobs consecutivos é conferido integralmente.
4. **Arquivo de Pareto.** Cada escalonamento viável encontrado atualiza os pontos não dominados. O arquivo começa vazio.
5. **Limites inferiores seguros.** Para um ramo parcial, `LB_Cmax` usa os términos já fixados e o menor término possível de cada job restante. `LB_TEC` soma o custo já fixado ao menor custo ainda permitido pelo domínio de cada job. Ignorar conflitos entre os jobs restantes torna esses limites otimistas. Um ramo só é podado por dominância se um ponto viável já descoberto for não pior em **ambos** os limites. Portanto, essa poda só entra em ação depois de a própria busca encontrar soluções.

Essas regras preservam a exatidão. A busca não usa soluções iniciais de heurísticas ou do CP-SAT. Seus limites podem ser fracos em instâncias grandes; `status=incomplete` nunca significa que a fronteira inteira foi provada.

## Verificação e desempenho observado

Nas seis instâncias pequenas, o solver próprio e o CP-SAT produzem os mesmos valores completos da fronteira que o oráculo exaustivo dos testes. A tabela compara o solver próprio com a execução histórica da força bruta:

| Caso | Decisões da força bruta | Decisões do solver próprio |
|---|---:|---:|
| Um job, dois modos | 6 | 6 |
| Setup assimétrico | 42 | 21 |
| Máquinas não relacionadas | 56 | 13 |
| Dois dias | 132 | 28 |
| Três jobs, máquinas e modos | 2.415 | 76 |
| Setup reparável por inserção | 110 | 22 |

Em uma execução **nova de 15 segundos** da instância oficial de seis jobs, o solver próprio encontrou 439.970 escalonamentos viáveis e manteve 7 pontos não dominados **provisórios**. Esses números não são comparáveis diretamente aos 43 pontos provados pelo CP-SAT; o solver próprio ainda não concluiu a instância oficial. Nenhuma solução do CP-SAT foi carregada nessa execução. O relatório integral do CP-SAT foi usado apenas depois, para verificar que os pontos provisórios eram viáveis e não contradiziam a fronteira completa.

Execute a bateria de regressão com `python -m unittest discover -s tests -v`. Ela compara a fronteira do solver próprio com uma enumeração exaustiva restrita aos testes e verifica interrupção e retomada.
