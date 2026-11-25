# 06 · Meta-heurística AGE-MOEA

## 1. Sua tarefa

Você vai criar, sozinho nesta sessão, a animação **Meta-heurística AGE-MOEA** da apresentação do trabalho. Leia primeiro `src/presentation/diretrizes/00_GUIA_COMUM.md` e siga-o integralmente; depois leia as fontes abaixo. Entregue `anim_age.py`, `trace_age.py`, `data/trace_age.json` e `ROTEIRO_AGE.md` em `src/presentation/`, e o player renderizado em `media/age/`. Cenas: `AgeCamadas`, `AgeGeometria`, `AgeBusca`. Outras sessões produzem os demais vídeos ao mesmo tempo: não toque em arquivos compartilhados.

**Pré-requisito:** o AGE-MOEA do pymoo exige `numba`, ausente do `.venv` quando esta diretriz foi escrita. Verifique com `.venv/bin/python -c "import numba"`; se faltar, `.venv/bin/python -m pip install "numba>=0.61,<1"` (versão já prevista no `requirements.txt`) e relate a instalação.


## 2. Fonte da verdade

- `src/metaheuristics/age.py`: `run_age`, lotes, `_final_front`.
- pymoo 0.6.2, `pymoo/algorithms/moo/age.py`: `AGEMOEASurvival._do`, `survival_score`, `compute_geometry`, `find_corner_solutions`, `normalize`, `pairwise_distances`.
- Operadores em `src/metaheuristics/spea2.py`.

## 3. Como funciona aqui

1. **População** de P planos (LPT aleatório). **Geracional:** cada lote cria P filhos; o último é menor se o orçamento não fechar. Todos são avaliados, e depois pais e filhos (2P) disputam P vagas.
2. **Pais** por torneio de posto e escore. Filhos por cruzamento e mutação do projeto (mesmos do SPEA2). Duplicatas são permitidas; inviáveis consomem avaliação e são filtrados na sobrevivência, quando há viáveis suficientes.
3. **Camadas:** ordenação não dominada em frentes 0, 1, 2…
4. **Extremos:** na primeira frente, acha os cantos e normaliza com eles (plano pelos extremos; se falhar, pelo máximo).
5. **Geometria:** o ponto da frente mais próximo da diagonal diz a curvatura. p = ln(n) / ln(1 / média das coordenadas desse ponto), n = 2; p ≤ 0,1 ou indefinido vira 1, e acima de 20 vira 20. p < 1 é curva para dentro da reta, p = 1 reta, p > 1 para fora.
6. **Escore da frente 0:** extremos recebem infinito; os outros entram um por vez: o de maior soma das distâncias aos **dois selecionados mais próximos**, na norma Lp, cada distância dividida pela norma Lp do próprio ponto (combina proximidade ao ideal e diversidade).
7. **Outras camadas:** 1 / distância Lp ao ideal. A última que não cabe é cortada pelos maiores escores.
8. A frente final vem da população, reavaliada e filtrada por objetivos inteiros.

Campanha: população 100, cruzamento 0,9, mutação 0,7, 10.000 avaliações.

## 4. Conceito criativo

**Metáfora: a membrana que descobre a forma da frente.** Uma película luminosa (a curva de nível de Lp) **respira**, de losango a círculo a quase quadrado, até abraçar os planos da primeira camada. Camadas são cebolas translúcidas que descascam. Cor `COLORS["age"]`. As operações (modo, espera, inserção, troca e realocação) usam a coreografia do guia. Foco em **inserção** e **espera**.

## 5. Roteiro por trecho

### 00:00 · `lote` (AgeCamadas, animação ≈ 14 s)

- **Pergunta:** Um plano por vez, ou uma turma inteira?
- **Na tela:** P planos enchem uma esteira; as máquinas do fundo recebem duplas (cruzamento) e um filho sai, com inserção ou espera. Em vez de entrar um por vez, a turma inteira desce junto: pais + filhos, 2P na arena. Contraste discreto com o método de um por rodada.
- **Número real:** Tamanho de P e um filho real.
- **Texto máximo:** "P pais + P filhos"
- **Fala-guia:** Geração inteira de uma vez.
- **Transição:** As 2P bolinhas se ordenam.

### 00:30 · `camadas` (AgeCamadas, animação ≈ 14 s)

- **Pergunta:** Quem passa primeiro?
- **Na tela:** Camadas não dominadas se descolam como cascas, da primeira para fora. Cada casca entra inteira enquanto houver vaga; a casca que não cabe é partida.
- **Número real:** Camadas e tamanhos reais.
- **Texto máximo:** "casca por casca"
- **Fala-guia:** Primeiro os melhores, por camada.
- **Transição:** A primeira casca fica e o resto esmaece.

### 01:00 · `extremos` (AgeGeometria, animação ≈ 11 s)

- **Pergunta:** Em que escala medir?
- **Na tela:** Os dois cantos da primeira casca são fisgados como pinos; a régua normaliza o quadro por eles e a casca se encaixa no quadrado unitário. Mostre os números antigos virando 0 e 1.
- **Número real:** Extremos e normalização reais.
- **Texto máximo:** "extremos fixam a régua"
- **Fala-guia:** A frente define a própria unidade.
- **Transição:** A diagonal surge.

### 01:25 · `membrana` (AgeGeometria, animação ≈ 20 s)

- **Pergunta:** Qual é a curvatura desta frente?
- **Na tela:** A diagonal varre; o ponto mais próximo brilha e sua média mede p. A membrana respira: p = 0,5, 1, 2, enquanto a curva de nível se alinha ao ponto. Trava no p real, com vibração. Em um segundo instante, com outra geração, p muda.
- **Número real:** p real em duas gerações do trace.
- **Texto máximo:** "p = …"
- **Fala-guia:** Não supomos a forma. A frente informa.
- **Transição:** A membrana vira régua.

### 02:00 · `escore` (AgeGeometria, animação ≈ 16 s)

- **Pergunta:** Quem merece ficar?
- **Na tela:** Os extremos valem infinito e se acendem. Cada candidato mede a distância aos dois vizinhos escolhidos, pela régua curva; o de maior nota entra; o próximo recalcula. A lista **cresce**. Camadas seguintes mostram a distância ao ideal.
- **Número real:** Ordem de entrada e escores reais.
- **Texto máximo:** "longe dos já escolhidos"
- **Fala-guia:** Espaço próprio e proximidade, na mesma régua.
- **Transição:** Acelera.

### 02:35 · `busca` (AgeBusca, animação ≈ 14 s)

- **Pergunta:** E depois de muitas turmas?
- **Na tela:** Gerações rápidas: cascas, membrana respirando a cada uma, nuvem descendo. Um inviável some, mas conta no lote. O último lote parcial é mostrado se existir. O melhor compromisso vira o Gantt.
- **Número real:** Evolução e frente final; contagem de lotes.
- **Texto máximo:** "campanha: 100 · 0,9 · 0,7"
- **Fala-guia:** A membrana aprende a forma.
- **Transição:** Quadro-base final.

## 6. Momento uau

**A membrana respirando.** Um `ValueTracker` p conduz a curva |x|^p + |y|^p = c, que muda de losango a círculo em um único plano contínuo, tocando o ponto mais próximo da diagonal. A mudança entre duas gerações acontece na mesma sequência.

## 7. Dados

No trace, substitua `pymoo.algorithms.moo.age.AGEMOEASurvival` por uma subclasse que sobrescreve `_do` e `survival_score`, chama `super()` e grava frentes, p, normalização, extremos e escores (chame `AGEMOEASurvival.compute_geometry` só para conferir o p, sem alterar o RNG). Substituir antes de importar/construir `AGEMOEA`, pois a classe é lida do módulo no construtor. Cópias dos arrays: `survival_score` pode modificar a matriz recebida. Cruzamento e mutação como no SPEA2, registrando só o que foi aplicado. Demonstração: P = 12–24, cruzamento 0,9, mutação 0,7, seed registrada; procure uma geração com uma inserção ou espera real cujo efeito seja visível. Para o lote parcial, escolha `max_evaluations` não múltiplo de P e registre `evaluation_batches`.

## 8. Armadilhas de fidelidade

- Não é NSGA-II com outra distância de multidão: a distância depende de p.
- O escore é da frente 0; as demais camadas usam a distância ao ideal.
- p = 1 quando o cálculo falha ou p ≤ 0,1; p no máximo 20. Se um caso real cair aí, diga.
- A normalização é pelos extremos da **primeira frente**, não pelos da população.
- Um candidato é selecionado pela soma das duas distâncias aos já selecionados, não pela maior distância a todos.
- Todos os descendentes do lote são avaliados antes da seleção.
- A compilação do Numba pode pesar na primeira execução.

## 9. Aceite específico

Além do aceite comum do guia:

- [ ] p e sua mudança entre gerações vêm do trace.
- [ ] A membrana usa a fórmula e passa pelo ponto de referência.
- [ ] Camadas e corte parcial mostrados com dados reais.
- [ ] Lote parcial e inviável tratados corretamente.

Render final: `.venv/bin/python src/presentation/apresentar.py --deck age --render --quality m`
