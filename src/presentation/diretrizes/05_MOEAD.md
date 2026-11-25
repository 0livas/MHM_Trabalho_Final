# 05 · Meta-heurística MOEA/D

## 1. Sua tarefa

Você vai criar, sozinho nesta sessão, a animação **Meta-heurística MOEA/D** da apresentação do trabalho. Leia primeiro `src/presentation/diretrizes/00_GUIA_COMUM.md` e siga-o integralmente; depois leia as fontes abaixo. Entregue `anim_moead.py`, `trace_moead.py`, `data/trace_moead.json` e `ROTEIRO_MOEAD.md` em `src/presentation/`, e o player renderizado em `media/moead/`. Cenas: `MoeadLeque`, `MoeadVizinhos`, `MoeadBusca`. Outras sessões produzem os demais vídeos ao mesmo tempo: não toque em arquivos compartilhados.


## 2. Fonte da verdade

- `src/metaheuristics/moead.py`: `reference_directions`, `ScheduleProblem`, `FeasibleEvaluator`, `run_moead`.
- pymoo 0.6.2, `pymoo/algorithms/moo/moead.py`: `_next`, `_replace`, `NeighborhoodSelection`; `pymoo/decomposition/tchebicheff.py`.
- Operadores em `src/metaheuristics/spea2.py` (amostragem, cruzamento e mutação são os mesmos).

## 3. Como funciona aqui

1. **P direções uniformes**, uma por indivíduo: pares de pesos (w, 1 − w).
2. **Vizinhança:** as T direções mais próximas, incluindo a própria.
3. **Medida:** objetivos escalados por constantes da entrada (`Cmax/H`, `TEC/max_cost`); valor de Tchebycheff = maior das diferenças ao ponto ideal multiplicadas pelos pesos. Menor é melhor.
4. Em cada varredura, percorre os subproblemas em **ordem aleatória**.
5. Para o subproblema k, com probabilidade 0,9 os dois pais saem da vizinhança; senão, de toda a população. O filho sofre cruzamento e talvez mutação.
6. Avaliado, atualiza o **ideal** (menor de cada objetivo) e substitui **todos os vizinhos cujo valor de Tchebycheff ele melhora**, ao mesmo tempo.
7. Inviável consome avaliação e é trocado por **cópia de um indivíduo viável sorteado da população**; não é reparo.
8. A frente vem da população final, refiltrada com objetivos inteiros exatos.

Campanha: P = 300, T = 10, 0,9 / cruzamento 0,9 / mutação 0,7, 10.000 avaliações.

## 4. Conceito criativo

**Metáfora: o leque de holofotes e o coral de vizinhos.** Cada indivíduo é um holofote com uma direção de peso, abrindo um leque a partir do ponto ideal. Cada um procura o plano que mais o ilumina; os vizinhos se ouvem e copiam. Os raios próximos formam um **coral**, cuja nota soa quando um filho melhora várias vozes. Cor `COLORS["moead"]`. O leque fica no plano Cmax × TEC; o Gantt mostra o plano do holofote em foco. As operações (modo, espera, inserção, troca e realocação) usam a coreografia do guia.

## 5. Roteiro por trecho

### 00:00 · `direcoes` (MoeadLeque, animação ≈ 14 s)

- **Pergunta:** E se dividíssemos uma pergunta difícil em muitas fáceis?
- **Na tela:** O ponto do plano de 15 h se abre em um leque de 15 feixes, do tempo puro à energia pura. Cada feixe recebe um plano inicial de LPT aleatório.
- **Número real:** 15 pesos e planos da demonstração.
- **Texto máximo:** "um peso, um plano"
- **Fala-guia:** Cada feixe quer uma coisa diferente.
- **Transição:** Um feixe é destacado.

### 00:30 · `medida` (MoeadLeque, animação ≈ 16 s)

- **Pergunta:** Como cada feixe mede um plano?
- **Na tela:** O ideal é uma estrela no canto dos menores valores. A partir dela, duas réguas (tempo e custo) crescem, multiplicadas pelos pesos; a **maior** acende e define o valor. O feixe muda de peso e a régua vencedora troca. Contornos em L passam pelo plano.
- **Número real:** Valores reais de Tchebycheff de dois planos para um peso.
- **Texto máximo:** "a maior das duas"
- **Fala-guia:** Quem define a nota é o pior lado, ponderado.
- **Transição:** O feixe chama os vizinhos.

### 01:00 · `pais` (MoeadVizinhos, animação ≈ 16 s)

- **Pergunta:** De quem vem o próximo plano?
- **Na tela:** O feixe k acende; os T vizinhos formam o coral. Dois pais saem dele; o Gantt mistura os dois (cruzamento) e sofre uma **realocação** ou troca de modo. Em um caso, o sorteio escapa da vizinhança e os pais vêm de longe. A ordem dos feixes é aleatória: mostre três pulos.
- **Número real:** Pais e filho reais.
- **Texto máximo:** "vizinhos, 90% das vezes"
- **Fala-guia:** Planos com pesos parecidos trocam ideias.
- **Transição:** O filho se aproxima do leque.

### 01:40 · `cascata` (MoeadVizinhos, animação ≈ 22 s)

- **Pergunta:** Um filho pode servir a quantos?
- **Na tela:** Primeiro o ideal pode se mover e todas as réguas se recalibram. Depois o filho percorre os vizinhos: cada feixe melhorado **muda de plano ao mesmo tempo**, como teclas de piano acendendo em cascata; feixes não melhorados piscam cinza. Os Gantts em miniatura se convertem no filho.
- **Número real:** Evento real com vários vizinhos substituídos, e a quantidade.
- **Texto máximo:** "substitui todos que melhora"
- **Fala-guia:** Uma boa ideia se espalha pela vizinhança.
- **Transição:** Um filho inviável aparece.

### 02:15 · `inviavel` (MoeadVizinhos, animação ≈ 9 s)

- **Pergunta:** E quando o plano não cabe?
- **Na tela:** O Gantt racha no horizonte; o contador sobe; o filho se dissolve e vira a **cópia** de um plano já conhecido, sorteado na população. A nota da cópia não melhora ninguém por ser nova: ela compete como qualquer outra.
- **Número real:** Evento de rejeição real.
- **Texto máximo:** "conta, mas vira cópia"
- **Fala-guia:** A tentativa se gasta, o plano volta a ser um conhecido.
- **Transição:** Acelera.

### 02:35 · `busca` (MoeadBusca, animação ≈ 15 s)

- **Pergunta:** O que nasce de quinze pedidos?
- **Na tela:** Varreduras aceleradas: feixes trocam de plano, o ideal desce, os pontos deslizam pelo leque até a frente. Contador de avaliações. Alguns feixes compartilham o mesmo plano, e isso é mostrado.
- **Número real:** Evolução e frente final.
- **Texto máximo:** "campanha: 300 · 10"
- **Fala-guia:** Muitas perguntas simples, uma frente.
- **Transição:** Quadro-base final.

## 6. Momento uau

**A cascata.** Um filho real atualiza a vizinhança inteira de uma só vez: os feixes acendem em sequência rápida (0,08 s cada) e os Gantts em miniatura viram o mesmo plano. Se a demonstração não tiver um evento com ao menos três substituições, aumente a execução ou varie a seed.

## 7. Dados

Em memória, use uma subclasse de `pymoo.algorithms.moo.moead.MOEAD` que sobrescreve `_replace` (chamando `super()`) e a substitua em `moead.MOEAD` (atributo do módulo) só no trace. Grave ideal antes/depois, vizinhança, valores de decomposição antes/depois, índices trocados, pais e filho. Para o cruzamento e a mutação, as mesmas subclasses do SPEA2. Os pais são definidos em `NeighborhoodSelection._do`, também substituível. Demonstração: P = 15, T = 5 (reforce que a campanha é outra). Rejeições: subclasse do avaliador ou comparação do contador `trace.rejected`.

## 8. Armadilhas de fidelidade

- Não há arquivo externo nem normalização por máximo e mínimo da população: a escala é fixa (`H`, `max_cost`).
- O vizinho da lista inclui a própria direção.
- `n_neighbors` é o T; uma substituição pode atingir até T indivíduos.
- Direções uniformes não garantem pontos uniformes na frente.
- O fallback não é reparo, não avalia de novo e não é uma solução melhor. Não mostre o filho rachado virar o melhor.
- Tchebycheff é a forma clássica (pesos × diferença); não apresente como soma ponderada.
- A população final pode ter planos repetidos: não há eliminação de duplicatas.

## 9. Aceite específico

Além do aceite comum do guia:

- [ ] O maior dos dois lados está explícito.
- [ ] Ideal dinâmico aparece antes da substituição.
- [ ] Uma substituição em cascata real, com contagem.
- [ ] Cópia do inviável diferente de reparo.

Render final: `.venv/bin/python src/presentation/apresentar.py --deck moead --render --quality m`
