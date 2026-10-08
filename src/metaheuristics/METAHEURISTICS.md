# Meta-heurísticas

Esta parte do projeto é responsável pela resolução aproximada do problema multiobjetivo de escalonamento, considerando simultaneamente:

- minimização do makespan (`Cmax`);
- minimização do custo total de energia (`TEC`).

Foram implementadas e avaliadas três meta-heurísticas:

1. VNS/VND multiobjetivo;
2. SPEA2;
3. MOEA/D.

Os três métodos utilizam a mesma representação de solução e o mesmo avaliador, permitindo uma comparação consistente entre eles.

---

## Representação da solução

Uma solução é representada por máquina:

```text
máquina -> [(job, modo, espera), ...]
```

Cada operação define:

- o job executado;
- o modo de operação;
- uma espera opcional antes do processamento.

A posição do job na lista define sua sequência na máquina.

A espera é importante porque pode ser vantajoso atrasar uma tarefa para evitar períodos de tarifa de energia mais cara.

O avaliador compartilhado calcula:

- tempos de início e término;
- setups dependentes da sequência;
- makespan;
- custo de energia;
- viabilidade da solução.

---

# 1. VNS/VND multiobjetivo

Arquivo principal:

```text
src/metaheuristics/vns_vnd.py
```

Foi implementado manualmente.

O método mantém uma frente de soluções não dominadas e combina:

- VND para busca local;
- VNS para diversificação por shaking.

As principais vizinhanças utilizadas são:

| Vizinhança | Alteração |
|---|---|
| N1 | mudança do modo de operação |
| N2 | alteração da espera |
| N3 | inserção de job na mesma máquina |
| N4 | realocação entre máquinas |
| N5 | troca de jobs |

O VND procura uma melhoria por dominância Pareto. Quando encontra uma melhoria, volta para a primeira vizinhança.

O VNS utiliza as mesmas famílias de movimentos para gerar perturbações e escapar de regiões locais.

### Configuração final

```text
soluções iniciais = 4
máximo de candidatos por vizinhança = 25
tentativas de shaking = 20
```

---

# 2. SPEA2

Arquivo principal:

```text
src/metaheuristics/spea2.py
```

Foi utilizado o SPEA2 do `pymoo 0.6.2`, adaptado para trabalhar diretamente com a representação de schedules do projeto.

O SPEA2 é um algoritmo evolutivo multiobjetivo.

A seleção considera:

- dominância;
- strength;
- raw fitness;
- densidade entre soluções.

Foi usada uma variante incremental:

```text
n_offsprings = 1
```

Isso permite controlar exatamente o número de avaliações realizadas.

Os operadores de cruzamento e mutação trabalham diretamente sobre schedules, podendo alterar:

- máquina;
- sequência;
- modo;
- espera.

### Configuração final

```text
população = 50
crossover = 0.9
mutation = 0.3
```

---

# 3. MOEA/D

Arquivo principal:

```text
src/metaheuristics/moead.py
```

Foi utilizado o MOEA/D nativo do `pymoo 0.6.2`.

Diferentemente do SPEA2, que trabalha diretamente com dominância, o MOEA/D decompõe o problema multiobjetivo em vários subproblemas.

Foi usada decomposição:

```text
Tchebycheff
```

com direções de referência distribuídas entre os dois objetivos.

Internamente, os objetivos são escalados como:

```text
Cmax / H
TEC / max_cost
```

Essa escala é utilizada somente pelo funcionamento interno do MOEA/D.

### Configuração final

```text
população / reference directions = 50
n_neighbors = 20
probabilidade de mating local = 0.9
crossover = 0.9
mutation = 0.3
```

---

# Escolha dos parâmetros

Antes da comparação final, foram realizados experimentos piloto independentes para cada método.

Os pilotos avaliaram parâmetros como:

- tamanho da população;
- quantidade de soluções iniciais;
- tamanho das vizinhanças;
- intensidade de shaking;
- probabilidades de crossover e mutation;
- diferentes orçamentos de avaliações.

Após os pilotos, os parâmetros foram congelados.

Nenhum método foi retunado depois de observar os resultados da comparação final.

---

# Comparação final

O experimento principal utilizou:

```text
13 instâncias
3 meta-heurísticas
10 seeds
8.000 avaliações por execução
```

Total:

```text
390 buscas no experimento principal
```

As mesmas instâncias, seeds e orçamento de avaliações foram utilizados para os três métodos.

O Hypervolume (HV) foi utilizado como principal indicador de qualidade multiobjetivo.

Quanto maior o HV, melhor a combinação entre convergência e cobertura da frente Pareto.

O IGD+ foi utilizado como indicador complementar.

---

# Resultado principal

No experimento principal, a ordenação observada foi:

| Método | Rank médio no HV | Instâncias com maior mediana de HV |
|---|---:|---:|
| SPEA2 | 1 | 13 |
| MOEA/D | 2 | 0 |
| VNS/VND | 3 | 0 |

O SPEA2 apresentou a maior mediana de Hypervolume nas 13 instâncias avaliadas.

A diferença também foi avaliada estatisticamente.

### Friedman

```text
χ² = 26
p = 2.26 × 10⁻⁶
```

### Wilcoxon + correção de Holm

As três comparações par-a-par permaneceram significativas:

```text
p ajustado = 0.000732
```

Portanto, dentro da campanha experimental realizada, houve evidência estatística de diferença entre os três métodos.

Isso não significa que o SPEA2 seja universalmente superior para qualquer instância do problema.

---

# Experimento de escalabilidade

Também foram testadas instâncias com 750 jobs.

SPEA2 e MOEA/D completaram todas as execuções planejadas.

O VNS/VND completou normalmente três das quatro instâncias de 750 jobs.

Na instância:

```text
750_10_1439_5_S_1-9.dat
```

o VNS/VND falhou na inicialização nas cinco seeds utilizadas.

A investigação mostrou que:

- a instância é viável;
- o problema não estava no avaliador;
- o inicializador do VNS escolhe máquina e modo aleatoriamente;
- essas escolhas acumulam carga excessiva;
- as máquinas ficam próximas do horizonte antes dos 750 jobs serem inseridos.

Como os algoritmos já estavam congelados para o experimento final, o inicializador não foi alterado posteriormente.

As cinco falhas foram registradas como resultado de escalabilidade, sem inventar soluções ou métricas de qualidade.

---

# Experimento com orçamento maior

Também foi realizada uma comparação na instância de 250 jobs utilizando:

```text
8.000 avaliações
vs.
20.000 avaliações
```

Nas cinco seeds avaliadas:

- os três métodos melhoraram o Hypervolume com 20.000 avaliações;
- o menor custo de energia também melhorou nas cinco seeds dos três métodos.

Isso indica que ainda existia ganho com maior profundidade de busca nessa instância.

Entretanto, 8.000 avaliações continuou sendo o orçamento oficial da comparação principal.

---

# Validação

Ao final da campanha foram obtidos:

```text
465 células experimentais
460 buscas completas
5 falhas de inicialização documentadas
3.530.000 avaliações
8.676 soluções finais reavaliadas
```

Todas as soluções finais das buscas completas foram verificadas novamente quanto a:

- viabilidade;
- makespan;
- custo de energia exato;
- duplicação;
- dominância Pareto.

Também foram utilizadas cinco frentes Pareto exatas disponíveis para instâncias pequenas.

Nenhuma solução aproximada apresentou inconsistência em relação a essas frentes.

A comparação final passou por uma revisão independente e foi classificada como:

```text
APPROVED WITH MINOR NOTES
```

sem falhas materiais nos resultados ou na análise estatística.

---

# Arquivos principais

```text
src/metaheuristics/vns_vnd.py
src/metaheuristics/spea2.py
src/metaheuristics/moead.py

data/output/vns_vnd/piloto/
data/output/spea2/piloto/
data/output/moead/piloto/

data/output/final_comparison/relatorio.md
data/output/final_comparison/metrics.csv
data/output/final_comparison/summary.csv
data/output/final_comparison/statistical_tests.json
data/output/final_comparison/figures/
```

## Resumo

A parte de meta-heurísticas do projeto está concluída.

Foram implementadas três abordagens diferentes:

- VNS/VND: busca por vizinhanças;
- SPEA2: algoritmo evolutivo baseado em dominância e densidade;
- MOEA/D: decomposição do problema multiobjetivo.

Na campanha experimental realizada, o SPEA2 apresentou o melhor desempenho multiobjetivo global, seguido pelo MOEA/D e pelo VNS/VND.

Os resultados devem ser interpretados dentro das instâncias, parâmetros, seeds e orçamentos avaliados.
