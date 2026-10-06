# Spike mínimo de integração com pymoo

Este documento registra o spike anterior à implementação de `src/metaheuristics/spea2.py`. O SPEA2 já está implementado; apenas MOEA/D continua fora do escopo atual. As conclusões abaixo descrevem o protótipo, não os operadores da implementação final.

Executar da raiz após instalar `requirements.txt`:

```bash
python src/metaheuristics/pymoo_spike.py
```

O spike usa `data/input/set1/6_2_1439_3_S_1-9.dat`; aceita outro caminho de instância como argumento. Não lê baselines e não mede convergência: além do fluxo manual, executa um ciclo mínimo de cada algoritmo para validar a integração.

## O que foi exercitado

`src/metaheuristics/pymoo_spike.py` mantém uma variável customizada de tipo `object`, cujo conteúdo é exatamente `máquina -> [(job, modo, espera), ...]`. O `Sampling` do pymoo retorna uma `Population`; cada indivíduo armazena o schedule em `X[0]`. A `ElementwiseProblem` delega a validação, decodificação e avaliação à API compartilhada `src/schedule.py` e envia os dois objetivos, na ordem `(Cmax, TEC)`, ao campo `F` do indivíduo.

O operador customizado `SwapWithinMachine` troca duas tarefas de uma mesma sequência. Ele percorre as trocas possíveis, descarta as que terminam além do horizonte ou violam as regras e devolve a primeira troca viável. O spike chama o operador pelo fluxo `Mutation.do(problem, population)` e avalia o offspring novamente pelo pymoo. A primeira amostra usa distribuição round-robin e o modo mais rápido por tarefa/máquina; as demais variam deterministicamente o modo de uma tarefa para dar variedade inicial. Não usa dados dos baselines.

O decoder compartilhado usa `Instance.duration`, `energy_scale` e `interval_cost_units` em `src/problem.py`. `generate_choices`, usado pelos exatos, também usa esse helper. A avaliação mantém Cmax inteiro, `tec_units` e escala; pymoo recebe o valor de TEC convertido para `float` em `F`.

Resultado observado com pymoo 0.6.2 no fluxo manual:

```text
seed F=(Cmax=145, TEC=308.333452500)
offspring F=(Cmax=143, TEC=308.333452500)
pymoo offspring F=[143.0, 308.3334525]
algorithms setup OK: SPEA2, MOEAD
MOEA/D_constraints: This implementation of MOEAD does not support any constraints.
over-horizon policy: rejected (Job 0 termina em 1450, além do horizonte 1440)
exact TEC seed=18500007150/60000000; offspring=18500007150/60000000
TEC matches src/problem.py generate_choices for both schedules
```

Os dois schedules do resultado diferem na ordem das tarefas, têm os seis jobs exatamente uma vez, setups e intervalos válidos e todos os términos dentro de `H=1440`. Ambos foram confrontados tarefa a tarefa com as tabelas de `Choice` usadas pelos métodos exatos. **O makespan cai de 145 para 143; o TEC permanece em 308.333452500.**

## Setup e execução real dos algoritmos

Primeiro, `setup()` foi chamado separadamente para SPEA2 e MOEA/D com a variável `object`, o sampler, `CopyCrossover` e `SwapWithinMachine`. Ambos aceitaram os componentes. O teste negativo também reproduziu que MOEA/D lança `AssertionError` quando o problema declara uma restrição; o problema usado no ciclo real mantém `n_ieq_constr=0`.

Depois, `minimize()` executou cada algoritmo com seed 23, população de quatro indivíduos e término configurado em `n_gen=2`. pymoo reportou `n_gen=3` após a inicialização e uma varredura reprodutiva. Os contadores são instrumentação restrita ao spike: `CopyCrossover` e `SwapWithinMachine` contam suas chamadas, `ScheduleProblem` conta avaliações, a sobrevivência customizada de SPEA2 conta seleções ambientais e a subclasse de MOEA/D conta substituições.

Contadores observados em cada ciclo real:

| Algoritmo | Amostras iniciais | Crossover | Mutação | Avaliações | Sobrevivência SPEA2 | Reposições MOEA/D |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPEA2 | 4 | 4 | 4 | 8 | 2 | 0 |
| MOEA/D | 4 | 4 | 4 | 8 | 0 | 4 |

As oito avaliações correspondem a quatro indivíduos iniciais e quatro descendentes. O avaliador decodificou e validou cada um; a população final também foi decodificada novamente e seus `F` comparados com `(Cmax, TEC)`. No ciclo do SPEA2, as duas chamadas de sobrevivência cobrem a população inicial e a ambiental após reprodução. No MOEA/D, as quatro chamadas de reposição cobrem os subproblemas da varredura. O crossover tem dois pais e um descendente (`n_parents=2`); no MOEA/D, a reprodução chamou o crossover e a mutação quatro vezes sem conversão do objeto.

As avaliações de descendentes registradas em `F`, na ordem `(Cmax, TEC)`, foram:

```text
SPEA2: [(145.0, 305.2828035), (145.0, 290.538), (145.0, 290.538), (143.0, 290.538)]
MOEA/D: [(147.0, 290.538), (145.0, 290.538), (145.0, 308.3334525), (145.0, 308.3334525)]
```

`CopyCrossover` continua sendo apenas um operador de passagem: copia o primeiro pai e deixa a variação ao operador de troca. Isso valida a assinatura e o caminho real de reprodução, não recombinação genética. A execução é curta e não mede convergência ou qualidade.

**SPEA2:** execução real aprovada para a integração estrutural demonstrada: amostragem, seleção/reprodução, crossover, mutação, avaliação e sobrevivência completaram sem alteração arquitetural do algoritmo. (`eliminate_duplicates=False`) é usado apenas para evitar que eventuais duplicatas da pequena população do spike interfiram na validação do fluxo de reprodução.

**MOEA/D:** execução real aprovada para a integração estrutural demonstrada: seu fluxo de dois pais chamou os operadores, avaliou descendentes e atualizou vizinhos. A implementação do pymoo rejeita constraints declaradas, como demonstrado separadamente. Portanto, inicialização, cruzamento e mutação futuros precisarão filtrar ou reparar descendentes inviáveis antes da avaliação; a rejeição do operador atual cobre apenas as trocas que ele tenta.

## Limitações

- O tratamento demonstrado é rejeição, não reparo. O decoder levanta `ValueError` para schedule que excede o horizonte; o operador testa movimentos e mantém o pai se não encontrar descendente viável.
- A rejeição não fornece um mecanismo de restrição para MOEA/D. Ela precisa ser aplicada em cada ponto que cria ou modifica indivíduos, inclusive amostragem e cruzamento. Um conjunto de vizinhos que gere poucas alternativas viáveis pode estagnar.
- pymoo armazena `F` como números de ponto flutuante. A avaliação mantém o TEC exato escalado no `Evaluation`, mas SPEA2/MOEA/D comparam o `float` exposto ao framework. A fronteira exportada futuramente deve reter TEC inteiro/escalar e resolver qualquer empate com esse valor exato.
- O operador de demonstração enumera trocas intra-máquina e não cobre realocação, modo ou espera. Não é uma implementação de meta-heurística.

## Recomendação do spike

Manter pymoo como candidato para SPEA2 e MOEA/D. Ambos completaram um ciclo de reprodução real com a variável customizada `object`, sem random keys ou conversão para vetor contínuo. MOEA/D exige que seus operadores mantenham viabilidade sem declarar constraints. Esta aprovação cobre a integração do spike; cruzamentos recombinantes, diversidade de amostragem e política definitiva de inviabilidade seguem fora do escopo.
