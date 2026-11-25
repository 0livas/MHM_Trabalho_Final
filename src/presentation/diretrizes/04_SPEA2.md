# 04 · Meta-heurística SPEA2 incremental

## 1. Sua tarefa

Você vai criar, sozinho nesta sessão, a animação **Meta-heurística SPEA2 incremental** da apresentação do trabalho. Leia primeiro `src/presentation/diretrizes/00_GUIA_COMUM.md` e siga-o integralmente; depois leia as fontes abaixo. Entregue `anim_spea2.py`, `trace_spea2.py`, `data/trace_spea2.json` e `ROTEIRO_SPEA2.md` em `src/presentation/`, e o player renderizado em `media/spea2/`. Cenas: `Spea2Arena`, `Spea2Operadores`, `Spea2Busca`. Outras sessões produzem os demais vídeos ao mesmo tempo: não toque em arquivos compartilhados.


## 2. Fonte da verdade

- `src/metaheuristics/spea2.py`: `_random_schedule`, `ScheduleProblem`, `ScheduleCrossover`, `ScheduleMutation`, `run_spea2`.
- pymoo 0.6.2, `pymoo/algorithms/moo/spea2.py`: `SPEA2Survival`, `_truncation_candidate`, `spea_binary_tournament`.

## 3. Como funciona aqui

1. **População inicial** por LPT aleatório (janela ⌈√r⌉, menor término).
2. **Força** S(i): quantos i domina. **Aptidão bruta** R(i): soma das forças de quem domina i. Menor é melhor; não dominados têm R = 0.
3. **Densidade** D = 1/(σk + 2): σk é a distância ao vizinho de índice k = ⌊√(tamanho do conjunto)⌋ na lista ordenada, com k contado a partir de zero e a própria solução excluída. Aptidão final = R + D.
4. **Distâncias em unidades brutas**: `normalize=False`. Como o TEC tem escala maior que Cmax, ele domina a distância.
5. **Torneio binário** pela aptidão; cada pai vence um duelo.
6. **Cruzamento** (um filho). Para cada tarefa, sorteia um pai e herda dele máquina, modo e espera. A ordem em cada máquina é dada pela soma das posições nos dois pais mais ruído em [0; 0,5).
7. **Mutação** com probabilidade, sorteando uma de cinco: modo; espera (±1 ou ±3, nunca negativa); inserção na mesma máquina; troca de duas tarefas quaisquer; realocação para outra máquina.
8. **Um descendente por passo.** P + 1 disputam P vagas. Todos os não dominados ficam primeiro; se faltarem, completa pela aptidão; se sobrarem, remove repetidamente aquele cujo vetor ordenado de distâncias é lexicograficamente menor.
9. Inviável consome avaliação e recebe violação positiva; perde para viáveis. A frente vem da população final.

Campanha: população 200, cruzamento 0,7, mutação 0,5, 10.000 avaliações.

## 4. Conceito criativo

**Metáfora: a arena de influência.** Cada plano é um lutador em uma arena, no próprio plano Cmax × TEC. Cada dominância é uma seta que carrega **peso**: a força do dominador desaba sobre o dominado, que afunda com a massa acumulada. Na elite, o critério muda: quem está mais **espremido** perde lugar. Um único desafiante entra por rodada. Cor `COLORS["spea2"]`. As operações (modo, espera, inserção, troca e realocação) usam a coreografia do guia.

## 5. Roteiro por trecho

### 00:00 · `populacao` (Spea2Arena, animação ≈ 12 s)

- **Pergunta:** Como comparar planos que ganham em coisas diferentes?
- **Na tela:** 12 planos nascem por LPT aleatório, cada um um mini-Gantt que cai na arena e vira ponto. Ao passar o foco em um ponto, seu Gantt abre no painel e volta.
- **Número real:** População real da demonstração.
- **Texto máximo:** "12 planos"
- **Fala-guia:** Cada ponto é um plano inteiro.
- **Transição:** As setas começam.

### 00:25 · `forca` (Spea2Arena, animação ≈ 18 s)

- **Pergunta:** Quem vence quem?
- **Na tela:** Setas saem de cada dominador aos dominados; conte uma por uma (S), com o número crescendo no ponto. Depois a direção inverte: cada seta despeja a força como blocos sobre o dominado, e o ponto afunda (R). Os sem blocos flutuam e acendem.
- **Número real:** S e R reais de três planos.
- **Texto máximo:** "S" e "R"
- **Fala-guia:** Forte é quem domina muitos. Fraco é quem carrega muito peso.
- **Transição:** A câmera fica nos flutuantes.

### 01:00 · `densidade` (Spea2Arena, animação ≈ 12 s)

- **Pergunta:** Entre dois igualmente bons, quem sobra?
- **Na tela:** Bolhas crescem a partir de cada ponto até tocar o k-ésimo vizinho. As bolhas são **achatadas** de acordo com a escala bruta, mostrando por que TEC pesa mais. Dois pontos muito juntos ficam vermelhos.
- **Número real:** k e σk reais.
- **Texto máximo:** "espaço livre"
- **Fala-guia:** Quem está sozinho vale mais. E a régua aqui é a do custo.
- **Transição:** Dois pontos entram no duelo.

### 01:25 · `cruzamento` (Spea2Operadores, animação ≈ 20 s)

- **Pergunta:** Como dois pais viram um filho?
- **Na tela:** Os Gantts dos pais ficam acima e abaixo; cada tarefa tem uma moeda que escolhe o pai; seu bloco viaja para o filho com máquina, modo e espera. Duas tarefas colidem na mesma máquina: réguas com posição A + posição B + ruído decidem a ordem. O filho se reacomoda com setups novos.
- **Número real:** Pais, sorteios e soma das posições reais do trace.
- **Texto máximo:** "moeda por tarefa"
- **Fala-guia:** Ele herda pedaços, e a ordem é a média do que os pais queriam.
- **Transição:** Um dado de cinco faces rola.

### 02:00 · `mutacoes` (Spea2Operadores, animação ≈ 25 s)

- **Pergunta:** E se os pais não bastarem?
- **Na tela:** O dado para em cada face: respiração, elástico, inserção, troca em arco, realocação. Cada uma com um caso real **antes e depois**, o ponto movendo e o Gantt todo se ajustando. Inclua um inviável e sua avaliação contada.
- **Número real:** Cinco mutações reais da mesma execução, com Cmax/TEC.
- **Texto máximo:** nome do operador
- **Fala-guia:** Cinco maneiras de surpreender.
- **Transição:** O filho volta à arena.

### 02:35 · `expulsao` (Spea2Busca, animação ≈ 12 s)

- **Pergunta:** Entrou um: quem sai?
- **Na tela:** O filho cai na arena; são P + 1. Se houver dominados, o mais pesado afunda e sai. Em outro caso real, todos são não dominados: as distâncias são comparadas como cartas abertas (primeiro vizinho, empate, segundo) e o mais apertado é empurrado para fora.
- **Número real:** Um evento de cada tipo, do trace.
- **Texto máximo:** "P + 1 → P"
- **Fala-guia:** Um entra, um sai.
- **Transição:** Acelera.

### 03:00 · `busca` (Spea2Busca, animação ≈ 15 s)

- **Pergunta:** O que acontece depois de mil rodadas?
- **Na tela:** Centenas de rodadas em segundos: partículas entram, fogem e a nuvem desce e se espalha até a frente. Contador. A frente vem da população e o melhor vira o Gantt.
- **Número real:** Evolução por avaliações e frente final.
- **Texto máximo:** "campanha: 200 · 0,7 · 0,5"
- **Fala-guia:** A arena aprende a se espalhar.
- **Transição:** Quadro-base final.

## 6. Momento uau

**O peso das setas.** As setas de dominância se convertem em massas sobre os pontos dominados, afundando-os num único movimento físico; em seguida a câmera muda de critério e a bolha mais apertada é expulsa.

## 7. Dados

No processo do trace, substitua `spea2.ScheduleCrossover`, `spea2.ScheduleMutation` e `spea2.SPEA2Survival` por subclasses que chamam `super()` e gravam entradas e saídas. A mutação identifica a operação comparando antes e depois (não há registro interno). Cuidado: a mutação é calculada para todos e só depois aplicada com a probabilidade; registre **somente** a que sobreviveu, comparando o filho avaliado. Em sobrevivência, guarde S, R, D, a lista de sobreviventes e o removido. Demonstração: P = 12–30, cruzamento 0,7, mutação 0,5.

Para o cruzamento, não há como ver a moeda: reproduza com o mesmo RNG apenas fora da execução, ou deduza a origem comparando o filho com os pais (ambíguo se iguais); use um caso em que a dedução seja única.

## 8. Armadilhas de fidelidade

- Não existe arquivo externo do SPEA2 clássico: há uma população de tamanho P e um descendente por passo.
- Não desenhe distâncias normalizadas.
- Duplicatas são permitidas. Objetivos duplicados geram distância zero.
- A seta de força não é distância; R é soma das forças dos **dominadores**.
- Com cruzamento não aplicado, o filho começa como cópia de um pai, e ainda pode sofrer mutação.
- A frente final vem da população; não é um arquivo histórico ilimitado.
- A fórmula e o k são os do pymoo 0.6.2.

## 9. Aceite específico

Além do aceite comum do guia:

- [ ] S, R e D mostrados em objetos e números reais.
- [ ] As cinco mutações aparecem com antes/depois.
- [ ] Há um evento de remoção por dominância e um por aperto.
- [ ] A escala bruta das distâncias está visível.

Render final: `.venv/bin/python src/presentation/apresentar.py --deck spea2 --render --quality m`
