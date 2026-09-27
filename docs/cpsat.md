# Método exato CP-SAT

O modelo em `src/exact-solutions/cpsat.py` resolve a **mesma região viável e os mesmos dois objetivos** do solver próprio em `custom_exact.py`. Para manter a instalação portátil e sem dependência de um `venv`, o OR-Tools é opcional e tem seu próprio arquivo de requisitos. No Git Bash, na raiz do repositório:

```bash
python -m pip install --user -r requirements-cpsat.txt
python src/exact-solutions/cpsat.py tests/fixtures --time-limit 10 --restart
python src/exact-solutions/cpsat.py data/input/set1/6_2_1439_3_S_1-9.dat --time-limit 60 --workers 8
```

O parâmetro `--time-limit` limita **cada chamada** do solver; zero significa sem limite. Cada ponto provado é salvo em `data/output/cpsat/<instância>.json`. `--resume` continua a partir do último limite de custo registrado, embora o solver recomece do início a chamada interrompida. `--restart` reinicia o relatório. Não há dependência de GPU. A [documentação oficial do OR-Tools](https://developers.google.com/optimization/install/python) descreve a instalação do pacote; a versão usada nos testes foi 9.15.

## Variáveis e restrições

Para cada job, máquina e modo, há uma variável binária de presença e um intervalo opcional com início e duração `ceil(processing[j][i]/v[l])`. Exatamente um par máquina/modo é escolhido por job. Intervalos da mesma máquina não se sobrepõem. O custo de cada opção é uma tabela de inteiros exatos indexada pelo início; ela usa `pi`, `lambda`, as tarifas e as janelas de ponta de cada dia, com a mesma escala inteira do backtracking.

Um circuito dirigido por máquina define a sequência dos jobs presentes. Uma aresta `j → k` impõe `início(k) ≥ término(j) + setup[i][j][k]`. Assim, o setup é exigido **entre jobs consecutivos**, sem impor indevidamente `setup[j][k]` a jobs que tenham outro job entre eles. O caso `06_reparable_setup.dat` testa especificamente essa distinção. `Cmax` é o maior término; `TEC` é a soma dos custos de processamento. `max_cost` permanece somente como normalizador na saída, igual ao solver próprio.

## Fronteira de Pareto exata

Cada iteração executa duas otimizações lexicográficas:

1. Com um teto de custo `ε`, prova o menor `Cmax` possível.
2. Com `Cmax` limitado ao ótimo recém-provado, prova o menor `TEC` possível.

O par resultante é não dominado. A iteração seguinte usa `ε = TEC − 1` em unidades inteiras escaladas, sem pular valores por arredondamento. O processo termina quando o próximo modelo é **comprovadamente inviável**. Só então `status=complete` e `pareto_proven=true`. Se uma chamada termina por tempo, `front` contém apenas pontos já provados; `candidate`, se presente, é uma solução viável provisória e **não** é apresentada como ponto provado. O relatório informa o status de cada chamada do solver. Os status `OPTIMAL`, `FEASIBLE`, `INFEASIBLE` e `UNKNOWN` seguem a [definição do CP-SAT](https://developers.google.com/optimization/cp/cp_solver).

## Comparação na instância de seis jobs

As execuções usaram a mesma instância, identificada pelo SHA-256 nos arquivos de `data/baselines/`. O backtracking foi interrompido, enquanto o CP-SAT concluiu a prova da fronteira. Esses tempos medem métodos e critérios de parada diferentes; não são um fator de aceleração controlado.

| Método | Tempo registrado | Resultado naquele ponto |
|---|---:|---|
| Backtracking CPU, antes da poda antecipada de setup | 1.111,18 s | 242.758.339 decisões, 223.388.972 folhas, nenhuma solução viável encontrada |
| CP-SAT, primeira execução, 8 workers, até 15 s por chamada | 50,59 s | Dois pontos provados; busca ainda incompleta |
| CP-SAT, após retomada, 8 workers, até 60 s por chamada | 1.141,53 s acumulados | **43 pontos provados**; 87 chamadas, a última `INFEASIBLE`; fronteira completa |

Os 43 pares `(Cmax, TEC)` exatos estão em `data/baselines/6_2_1439_3_S_1-9_cpsat_complete.json`. O primeiro é `(94, 242,2037755)` e o último `(220, 134,099428)`. Os escalonamentos correspondentes permanecem no relatório detalhado `data/output/cpsat/6_2_1439_3_S_1-9.json` da máquina local. Cada escalonamento foi reavaliado com o parser e as regras compartilhadas em `problem.py`: não há sobreposição, todos os setups são respeitados e os dois objetivos coincidem com os inteiros exatos do relatório.

O solver próprio permanece disponível para validar a modelagem. Os seis casos pequenos em `tests/fixtures/` têm fronteiras completas idênticas nos dois métodos e no oráculo exaustivo dos testes. Execute a bateria com `python -m unittest discover -s tests -v` depois de instalar o OR-Tools. Sem ele, os testes CP-SAT são ignorados, e os testes do solver próprio continuam funcionando.
