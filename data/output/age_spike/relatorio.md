# Spike AGE-MOEA

## Conclusão

**AGE-MOEA é tecnicamente adequado para implementação completa**, no escopo
verificado: schedules nativos, dois objetivos, restrições de viabilidade e
orçamento literal. Isto não aprova sua inclusão na campanha nem demonstra
qualidade competitiva. Nenhum método existente, protocolo, métrica ou resultado
experimental oficial foi alterado.

## API e integração

Ambiente: **pymoo 0.6.2**, numba **0.61.2**, sem instalação ou atualização.
A [documentação oficial 0.6.2](https://pymoo.org/algorithms/moo/age.html)
e o código instalado de `pymoo.algorithms.moo.age` foram inspecionados.
Foi usado `AGEMOEA`, não AGE-MOEA2. Seleção por torneio e
`AGEMOEASurvival` permanecem nativos, sem substituições ou correções locais.

`src/metaheuristics/age_spike.py` reutiliza por importação o `ScheduleProblem`,
amostrador construtivo, cruzamento recombinante e mutação do SPEA2.
A variável `object` contém o `Schedule` original; o avaliador compartilhado
fornece `F=(Cmax, TEC)` sem escala adicional. Candidatos inválidos recebem
`G=1`, válidos `G=-1`; os objetivos fictícios dos inválidos são filtrados pela
sobrevivência nativa, sem reparo ou substituição por pais.

O driver público `ask/evaluator.eval/tell` usa lotes geracionais, reduzindo
`n_offsprings` antes do último `ask` para o saldo do orçamento. Não descarta
avaliações nem faz avaliações ocultas em operadores. Duplicatas não são
eliminadas (a eliminação numérica padrão não é apropriada ao objeto Schedule);
cada candidato submetido, inclusive repetido ou inviável, consome uma unidade.
A população inicial exige orçamento >= população. Reavaliações finais são
separadas e não alimentam a busca. O spike verifica cada sobrevivente contra
seu `F` armazenado, preservando também TEC inteiro e escala nos JSONs.

## Configuração e evidências

Seed 23, população 8, orçamento 41, lote nominal 8, crossover 0,9,
mutação 0,3. Instâncias originais, sem sufixo `_derivada`:

| Instância | Avaliações compartilhadas / pymoo | Viáveis / rejeitadas | Descendentes distintos da população inicial* | Sobreviventes novos* | Revalidações |
|---|---:|---:|---:|---:|---:|
| Set1 `10_2_1439_3_S_1-9.dat` | 41 / 41 | 41 / 0 | 30 | 6 | 8 |
| Set2 `50_10_1439_5_S_1-9.dat` | 41 / 41 | 41 / 0 | 27 | 5 | 8 |

*Contagem de indivíduos, não de schedules únicos. Lotes: `[8,8,8,8,8,1]`.
As duas execuções foram repetidas com resultados idênticos, incluindo schedules,
objetivos e contadores. Cruzamento, mutação e sobrevivência foram instrumentados
nos testes, confirmando o ciclo evolutivo real. Todos os sobreviventes são
válidos e seus objetivos coincidem exatamente com a reavaliação.
Os arquivos [set1.json](set1.json) e [set2.json](set2.json) contêm hashes das
entradas, parâmetros, representações completas e objetivos exatos; são evidências
do spike, não frentes oficiais ou certificados de otimalidade.

Validação: **4 testes do spike e 103 testes totais aprovados**.

Testes adicionais: orçamento 8 (somente inicialização); regime incremental
com orçamento 11 e lotes `[8,1,1,1]`; rejeição de orçamento insuficiente;
9 descendentes artificialmente inviáveis em orçamento 17 (8 avaliações viáveis,
9 rejeitadas, população final viável); sobrevivência com objetivos duplicados,
eixos constantes e ambos constantes, sem NaN ou RuntimeWarning.
Scores infinitos para extremos são intencionais na biblioteca.

## Reprodução

Na raiz do projeto, com as dependências instaladas:

```bash
python -m unittest tests.test_age_spike -v
python src/metaheuristics/age_spike.py data/input/set1/10_2_1439_3_S_1-9.dat
python src/metaheuristics/age_spike.py data/input/set2/50_10_1439_5_S_1-9.dat
python -m unittest discover -v
```

A CLI imprime JSON e não escreve arquivos da campanha. Os valores padrão são
os da tabela; `--offspring-size 1` testa a variante incremental.

## Limitações

- O último lote parcial modifica o regime geracional clássico; uma implementação
  completa deve documentar essa escolha. A variante incremental é outra opção
  pública, mas metodologicamente diferente. O cap exato foi demonstrado em ambas.
- O AGE-MOEA foi concebido para muitos objetivos; funcionar com dois não implica
  vantagem neste problema. Não houve tuning, piloto ou comparação de qualidade.
- A biblioteca seleciona por floats; TEC exato fica na reavaliação. Empates e
  filtragem de uma futura frente exportada devem respeitar os inteiros exatos.
- Duplicatas podem ocupar a população. O spike valida sobreviventes, sem criar
  arquivo de frente Pareto ou acrescentar métricas experimentais.
- A inicialização construtiva herdada pode falhar em outras instâncias; não há
  promessa de viabilidade universal. Os casos degenerados testados não cobrem
  todas as possibilidades numéricas, tamanhos ou seeds.
- O módulo AGE-MOEA importa numba obrigatoriamente. Ele está disponível neste
  ambiente, mas não é declarado diretamente em `requirements.txt`; uma instalação
  limpa deve verificar essa disponibilidade antes de uma implementação completa.
- A integração está deliberadamente restrita ao pymoo 0.6.2; revalidar ao atualizar.
