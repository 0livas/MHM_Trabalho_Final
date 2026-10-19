# Integração AGE-MOEA

O quarto método do projeto é `src/metaheuristics/age.py`, terceira
meta-heurística baseada em biblioteca. Ele usa **AGEMOEA do pymoo 0.6.2**,
com seleção, normalização geométrica e sobrevivência nativas. Não é AGE-MOEA2.
O spike permanece preservado em `age_spike.py` e `data/output/age_spike/`.
Esta implementação não integra nem altera a campanha experimental concluída.
O [piloto independente](piloto/relatorio.md) posterior está concluído; seus
parâmetros recomendados não alteram os defaults do solver.

## Arquitetura e contratos

- `AGEConfig`: seed, orçamento, população e probabilidades dos operadores.
  Defaults de API preservados: seed 1, 10.000 avaliações, população 100,
  crossover 0,9 e mutação 0,3. A configuração experimental congelada é
  população 50, crossover 0,9, mutação 0,3 e orçamento 8.000; deve ser passada
  explicitamente. Veja [congelamento e ambiente](FREEZE.md).
- `ScheduleProblem`, `SPEA2Trace`, `ScheduleSampling`, `ScheduleCrossover`,
  `ScheduleMutation` e `ParetoSolution` são reutilizados por importação de
  `spea2.py`, sem alterar esse arquivo. Os nomes herdados não implicam execução
  de seleção ou sobrevivência SPEA2.
- A variável `object` contém o Schedule nativo por máquina, com
  `(job, modo, espera)`. O amostrador construtivo gera schedules completos sem
  chamar o avaliador. O cruzamento preserva a unicidade de jobs e recombina
  alocação, ordem, modo e espera; a mutação altera esses mesmos componentes.
- O avaliador comum valida domínio, jobs, setups e horizonte, calculando Cmax
  e TEC. Cruzamento/mutação podem exceder o horizonte: cada tentativa completa
  chama o avaliador exatamente uma vez e consome orçamento, mesmo inviável.
  `G=-1` identifica válidos; `G=1` identifica rejeitados, com F fictício zero
  ignorado pela filtragem nativa. Não há reparo, reamostragem ou fallback.
- A população inicial deve ser integralmente viável e caber no orçamento.
  Falha construtiva é propagada; inicialização inviável é erro explícito.
  Como há N pais viáveis, a sobrevivência nativa sempre dispõe de N candidatos
  viáveis mesmo quando todos os descendentes são rejeitados.

## Orçamento e duplicatas

O driver público `ask/evaluator.eval/tell` executa lotes de tamanho N.
Antes do último `ask`, `n_offsprings` é reduzido ao saldo do orçamento;
nenhum candidato gerado é avaliado e descartado para ajustar o cap.
A configuração é geracional com último lote eventualmente parcial, diferença
metodológica que deve constar de qualquer comparação futura. O driver verifica
que tentativas = contagem pymoo = orçamento, e viáveis + rejeitados = tentativas.
`evaluation_batches` registra os tamanhos reais, incluindo a inicialização.

`eliminate_duplicates=False` evita a eliminação numérica padrão sobre objetos
Schedule e permite consumir exatamente o cap mesmo num espaço já saturado.
Duplicatas podem ocupar a população e cada cópia avaliada custa uma unidade.
Não há cache de objetivos. A frente final remove pares de objetivos duplicados,
mantendo um schedule representativo por par, usando `insert_pareto` comum.
Não se tenta recuperar todos os schedules equivalentes.

## Objetivos e saída

Durante a busca, F = `(float Cmax, float TEC)`; a normalização interna continua
sendo a do AGE-MOEA. Ao final, toda a população é reavaliada, fora do orçamento,
e os objetivos são confrontados exatamente com os floats armazenados.
Divergência ou sobrevivente inviável interrompem a execução sem publicar resultado.
A frente é filtrada e ordenada por `(Cmax, tec_units)` inteiros, incluindo
empates que a conversão para float não distingue. Isso garante não dominância
entre os sobreviventes reavaliados, sem recuperar soluções perdidas durante
seleção por floats nem certificar a frente global.

`AGEResult` mantém o contrato dos demais métodos: `algorithm`, `method`,
versão do pymoo, hash da entrada, parâmetros, motivo de término, orçamento,
avaliações viáveis/rejeitadas, contagem pymoo, `post_search_validations`, tempo,
quantidade de pontos e `front`. Cada ponto inclui objetivos brutos/normalizados,
TEC inteiro/escala, schedule decodificado e representação nativa. Não são
calculados HV/IGD+ nesta camada: eles dependem de referências e protocolo
experimental, como nos demais runners. O tempo cobre inicialização e busca,
excluindo reavaliação final e escrita.

## Execução e dependências

```bash
python -m pip install -r requirements.txt
python src/metaheuristics/age.py data/input/set1/10_2_1439_3_S_1-9.dat --seed 23 --max-evaluations 41 --population-size 8
python src/metaheuristics/age.py data/input/set2/50_10_1439_5_S_1-9.dat --seed 23 --max-evaluations 41 --population-size 8
python -m unittest tests.test_age -v
python -m unittest discover -v
```

A CLI também aceita uma pasta `.dat` (orçamento por arquivo), diretório de
saída e probabilidades dos operadores. Salva em `data/output/age/<entrada>.json`;
não sobrescreve sem `--overwrite`. Para preservar seeds diferentes, forneça
`--output-dir` distinto por execução. Não há retomada de busca.

`numba` é import obrigatório do módulo AGE-MOEA no pymoo 0.6.2 e por isso foi
adicionado a `requirements.txt`. Nenhuma dependência foi instalada ou atualizada
nesta etapa. Ambiente validado: pymoo 0.6.2 e numba 0.61.2. No congelamento,
`requirements.txt` foi alinhado ao runner com `pymoo==0.6.2`, versão também
usada pelos métodos existentes. As versões efetivas e transitivas estão em
`environment.json` e `requirements-age-repro.txt`; este runner continua
rejeitando outra versão até revalidação. Fonte da API: código instalado e
[documentação oficial 0.6.2](https://pymoo.org/algorithms/moo/age.html), já
verificados no spike.

## Validação e limites

Os testes executam Set1 original `10_2_1439_3_S_1-9.dat` e Set2 original
`50_10_1439_5_S_1-9.dat`, seed 23, população 8, orçamento 41, com repetição
idêntica de frente, schedules, metadados e contadores (exceto tempo).
Instrumentam cruzamento, mutação, sobrevivência e chamadas reais ao avaliador;
verificam frente exata, representação exportada, orçamento inicial/alinhado/
parcial, inviáveis forçados, duplicatas, colisões float, configuração inválida,
falha de inicialização, divergência final, escrita e CLI sem sobrescrita.
Resultado da validação: **9 testes específicos aprovados; suíte completa com
112 testes aprovados**, incluindo os métodos existentes e os 4 testes do spike.
Os casos degenerados de sobrevivência continuam cobertos pelos testes do spike.

A inicialização não garante sucesso para qualquer instância; falhas são
explícitas. A busca usa floats e pode perder distinções exatas. Duplicatas podem
reduzir diversidade. O custo da normalização/sobrevivência e da compilação inicial
do numba precisa ser considerado em comparações por tempo. Não foi validada uma
instalação limpa nem realizado teste de escala em toda a coleção nesta etapa.

## Piloto independente concluído

O [piloto](piloto/relatorio.md) executou 72 buscas (576.000 avaliações), com
populações 25/50/100, mutação 0,1/0,3, crossover 0,9, seeds 11/29/47 e
orçamento 8.000 nas quatro entradas de 6, 14 derivada, 50 e 250 jobs.
A recomendação é **população 50, crossover 0,9, mutação 0,3**, mantendo o
regime geracional e a política de duplicatas. Configuração e justificativa
estão em [recommendation.json](piloto/recommendation.json).

A escolha obteve rank médio 1,5 em HV e IGD+ por instância e a melhor mediana
HV em 3/4 entradas. Não foi uniformemente superior nas seeds. O relatório
registra referências, diversidade, validações e compilação inicial do Numba.
A suíte completa passou com 117 testes. Nenhum algoritmo foi alterado durante
o piloto; a comparação oficial com quatro métodos ainda não foi executada.

A configuração foi registrada em [frozen_config.json](frozen_config.json), sem
alterar o runner ou repetir buscas. Crossover 0,9 foi fixo em todo o piloto,
sem otimização específica. Consulte [FREEZE.md](FREEZE.md) e [ARCHIVE.md](ARCHIVE.md)
para ambiente, versionamento e verificação do arquivo local. Os brutos não
serão publicados como GitHub Release. Para a próxima campanha, usar as seeds
reservadas e manter os dados de tuning separados do teste final.
