# 01 · Método exato: programação dinâmica com ε-restrição

## 1. Sua tarefa

Você vai criar, sozinho nesta sessão, a animação **Método exato: programação dinâmica com ε-restrição** da apresentação do trabalho. Leia primeiro `src/presentation/diretrizes/00_GUIA_COMUM.md` e siga-o integralmente; depois leia as fontes abaixo. Entregue `anim_exato.py`, `trace_exato.py`, `data/trace_exato.json` e `ROTEIRO_EXATO.md` em `src/presentation/`, e o player renderizado em `media/exato/`. Cenas: `ExatoEstados`, `ExatoEscada`. Outras sessões produzem os demais vídeos ao mesmo tempo: não toque em arquivos compartilhados.


## 2. Fonte da verdade

- `src/exact_methods/custom_exact_dp.py`: `minimum_makespan`, `Label`, `insert_label`, `next_cheaper`, `best_before`, `EnergyDP.prepare`, `EnergyDP.solve`, `solve_front`.
- `src/presentation/cenario.py`: uso em memória, **sem publicar baseline**. Nunca chame `solve_front` no trace.
- `data/baselines/*_custom_exact_dp.json` e `data/output/experiments/runs/exact_dp/` para o alcance.

## 3. Como funciona aqui

1. `minimum_makespan` percorre subconjuntos e partições usando o modo mais rápido e nenhuma espera. Dá o menor Cmax possível.
2. `prepare` trata **cada máquina separadamente**. Estado: (máquina, subconjunto de tarefas, última tarefa). Cada estado guarda rótulos (término, energia) com ponteiro para o anterior.
3. Estender um rótulo: escolher uma tarefa ausente, somar o setup a partir da última, testar cada modo e cada início permitido.
4. `next_cheaper` evita testar todos os inícios: do início atual pula para o próximo de custo **estritamente menor**. É assim que a espera surge.
5. `insert_label` mantém término crescente e energia decrescente. Um rótulo que termina depois e não gasta menos é recusado; um novo pode remover antigos. Só se comparam rótulos com a mesma última tarefa, pois o setup futuro depende dela.
6. Concluída a máquina, os rótulos do mesmo subconjunto são fundidos, já sem a última tarefa.
7. `solve(epsilon)` escolhe, para cada subconjunto, a menor energia com término ≤ ε e combina partições disjuntas entre as máquinas. Desempata pelo menor Cmax e reconstrói pelos ponteiros.
8. Repetindo para todo ε inteiro até o horizonte, a fronteira fica completa e certificada.

Diferença do artigo base: lá a soma ponderada é resolvida por MILP, e só alcança pontos apoiados (da envoltória convexa). A ε-restrição encontra também os demais.

## 4. Conceito criativo

**Metáfora: a escada do ε.** Uma parede translúcida (ε) anda para a direita sobre o Gantt e, no plano, sobre o eixo Cmax; a cada posição em que o custo melhora, um degrau se solidifica. Antes dela, a construção dos rótulos é uma **árvore que cresce e é podada em tempo real**: cada rótulo é uma ficha luminosa com mini-Gantt. Cor `COLORS["exact_dp"]`. Estados são gavetas; fichas só brigam dentro da mesma gaveta.

## 5. Roteiro por trecho

### 00:00 · `pergunta` (ExatoEstados, animação ≈ 12 s)

- **Pergunta:** Como ter certeza de que não existe plano melhor?
- **Na tela:** O plano de 15 h do quadro-base se embaralha por realocações, trocas e modos, cada vez mais rápido, até virar uma nuvem. Um contador explode (decisões por tarefa × ordens). A nuvem congela e encolhe para uma única máquina vazia.
- **Número real:** Calcule e grave no JSON uma contagem simples e correta, por exemplo os pares máquina × modo por tarefa, 9 elevado a 8, sem ordem nem espera; rotule exatamente o que ela conta.
- **Texto máximo:** "só máquina e modo: 9⁸"
- **Fala-guia:** Testar tudo não é opção. Mas muitos planos têm o mesmo começo.
- **Transição:** A nuvem condensa na faixa da M1.

### 00:30 · `rotulos` (ExatoEstados, animação ≈ 18 s)

- **Pergunta:** O que precisamos lembrar de um plano parcial?
- **Na tela:** Duas tarefas entram na M1; a história se comprime numa ficha (término, energia). A ficha vai para a gaveta {tarefas} · última. A extensão solta três modos como leque e, em um deles, a barra pula direto de antes da ponta para o próximo início mais barato, com o elástico amarelo (`next_cheaper`).
- **Número real:** Término e energia reais de rótulos capturados.
- **Texto máximo:** "término · energia"
- **Fala-guia:** Basta lembrar quais tarefas, qual a última, quando termina e quanto gastou.
- **Transição:** Novas fichas começam a cair na mesma gaveta.

### 01:05 · `poda` (ExatoEstados, animação ≈ 22 s)

- **Pergunta:** E se dois começos chegarem ao mesmo lugar?
- **Na tela:** Duas fichas na mesma gaveta se encaram em miniplano término × energia. A que termina antes e não gasta mais **imita** a continuação da outra: mostre as duas continuando com a mesma tarefa, a perdedora nunca à frente; a perdedora racha. Depois mostre fichas com última tarefa diferente: a parede da gaveta impede a briga, porque o setup seguinte muda. Acelere: a chuva.
- **Número real:** 47.438 transições, 29.263 recusas, 18.175 inserções (10.334 removidas depois).
- **Texto máximo:** "mesma gaveta, mesma comparação"
- **Fala-guia:** O plano perdedor some com todos os seus descendentes.
- **Transição:** As fichas sobreviventes empilham-se em três colunas, uma por máquina.

### 01:45 · `particao` (ExatoEscada, animação ≈ 15 s)

- **Pergunta:** Quem fica com cada tarefa?
- **Na tela:** Oito tarefas repartidas em três bandejas; as curvas das três máquinas correspondem ao subconjunto da bandeja. Tarefas saltam entre bandejas e os custos somam ao vivo até travar na melhor partição. O Gantt se reconstrói de trás para frente pelos ponteiros.
- **Número real:** Partição e custos de um ε real, por exemplo 12.
- **Texto máximo:** "Σ energia ≤ ε"
- **Fala-guia:** Cada máquina já sabe seu melhor custo para qualquer conjunto.
- **Transição:** A parede ε surge no término 12.

### 02:15 · `epsilon` (ExatoEscada, animação ≈ 20 s)

- **Pergunta:** E se permitirmos uma hora a mais?
- **Na tela:** A parede ε avança de 12 até 24 h. A cada passo o Gantt se transforma e, se o TEC cai, um degrau cai no plano com som visual (onda). Em 19 e de 21 a 24 nada melhora: a parede passa, pulsa cinza e não gera degrau.
- **Número real:** Os oito pontos de `didatica.json`.
- **Texto máximo:** "ε = 12 … 24 h"
- **Fala-guia:** Um teto por vez, com o menor custo provado sob cada um.
- **Transição:** A escada completa acende.

### 02:45 · `limite` (ExatoEscada, animação ≈ 9 s)

- **Pergunta:** Até onde isso vai?
- **Na tela:** Cada tarefa extra dobra o número de gavetas: uma parede 2ⁿ cresce e fecha a tela em 13. Nove selos de certificado aparecem no pé.
- **Número real:** 9 baselines com 6 a 13 tarefas, de 41 a 252 pontos; acima de 13 o método é recusado na campanha (`max_jobs`).
- **Texto máximo:** "certificado até 13 tarefas"
- **Fala-guia:** É a régua dos outros métodos, quando cabe.
- **Transição:** Volta ao quadro-base com a escada dourada.

## 6. Momento uau

**A chuva de rótulos.** Milhares de partículas descem; as dominadas viram cinza e desaparecem; as vivas tomam as gavetas, e o contador corre até 47.438. Não desenhe uma partícula por transição: use um fator de amostragem declarado.

## 7. Dados

Reimplemente a captura com um wrapper de `insert_label` no módulo (substituição em memória) para registrar, **com amostragem**, (estado, término, energia, aceito, removidos); e `solve` por ε com partição e escalonamento. Guarde também `stats`. Confirme que as fronteiras e as estatísticas são iguais às da execução sem wrapper. Para a partição, reconstrua a atribuição pelo escalonamento de `solve`.

## 8. Armadilhas de fidelidade

- A busca por energia **não** usa só os modos mais rápidos; isso vale apenas para o makespan mínimo.
- Rótulos de últimas tarefas diferentes não se dominam na extensão; a fusão só ocorre ao fim da máquina.
- 10.334 são rótulos inseridos e depois removidos; não some com as 29.263 recusas para concluir quantos sobraram. `retained_subset_labels` é a contagem após a fusão.
- Transições não são escalonamentos completos.
- A DP é o método de referência, mas o projeto também tem CP-SAT e backtracking próprios: cite-os em uma frase, no máximo.
- O limite de 13 tarefas é padrão configurável, não fronteira teórica. Não afirme que 14 é impossível.
- A fronteira é exata para a discretização da entrada.

## 9. Aceite específico

Além do aceite comum do guia:

- [ ] Os oito pontos e apenas eles viram degraus.
- [ ] A regra das gavetas (mesma última tarefa) está visível.
- [ ] A espera nasce do salto para um início mais barato.
- [ ] Contagens iguais a `EnergyDP.stats`.

Render final: `.venv/bin/python src/presentation/apresentar.py --deck exato --render --quality m`
