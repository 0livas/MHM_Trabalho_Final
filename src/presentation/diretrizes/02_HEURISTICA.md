# 02 · Heurística: construção ponderada e inserção ótima de ociosidade

## 1. Sua tarefa

Você vai criar, sozinho nesta sessão, a animação **Heurística: construção ponderada e inserção ótima de ociosidade** da apresentação do trabalho. Leia primeiro `src/presentation/diretrizes/00_GUIA_COMUM.md` e siga-o integralmente; depois leia as fontes abaixo. Entregue `anim_heuristica.py`, `trace_heuristica.py`, `data/trace_heuristica.json` e `ROTEIRO_HEURISTICA.md` em `src/presentation/`, e o player renderizado em `media/heuristica/`. Cenas: `HeuristicaConstrutiva`, `HeuristicaOciosidade`. Outras sessões produzem os demais vídeos ao mesmo tempo: não toque em arquivos compartilhados.


## 2. Fonte da verdade

- `src/heuristics/construtiva/construtiva.py`: `ordenar`, `Avaliador.insercoes`, `construir`, `ajustar_modos`, `pesos`, `executar`.
- `src/heuristics/ociosidade/ociosidade.py`: `programar_maquina`, `CurvaMaquina.reconstruir`, `fronteira_da_base`, `bases_construtivas`, `executar`.
- `README.md`, seção 4. A campanha usa a ociosidade com partidas da construtiva e modos livres.

## 3. Como funciona aqui

**Etapa A, construir.** Três ordens LPT (soma, mínimo e máximo dos tempos entre máquinas) × 11 pesos α = 33 construções. Para cada tarefa, testa **toda** máquina × modo × posição da sequência e escolhe a de menor `α·Cmax/H + (1−α)·TEC/max_cost`, na solução parcial e sem ultrapassar o horizonte. Empate: menor término da máquina, depois menor TEC. Sem espera.

**Etapa B, ajustar modos.** De cada construção de objetivos distintos, troca repetidamente um modo. Prioridade: reduzir TEC sem aumentar Cmax; senão, maior economia de TEC por unidade de Cmax. Todos os passos são candidatos à frente; para quando nenhuma troca economiza.

**Etapa C, inserir ociosidade.** Fixa máquina e ordem das tarefas da frente construtiva (bases repetidas são unidas). Em cada máquina, f(t) é o menor custo de terminar a tarefa atual **exatamente** em t; g(t) é o melhor **até** t. O mínimo acumulado g permite esperar. Os modos também são livres. As curvas das máquinas são somadas para cada teto de Cmax, e as frentes das bases são unidas por dominância.

## 4. Conceito criativo

**Metáfora: encaixar e depois soltar o freio.** Primeira parte: um jogo de encaixe com **sondas fantasmas** que aparecem em cada vaga possível, com uma régua de preço; a vencedora acende. Um dial α, com "tempo" e "energia" nas extremidades, governa as escolhas. Segunda parte: as ordens travam (cadeados nas sequências), mas as barras ficam sobre **molas**, deslizam no tempo e fogem da ponta. Cores `COLORS["construtiva"]` e `COLORS["ociosidade"]`.

## 5. Roteiro por trecho

### 00:00 · `pergunta` (HeuristicaConstrutiva, animação ≈ 8 s)

- **Pergunta:** Dá para achar um bom plano sem testar todos?
- **Na tela:** O plano-base se desmonta e as oito tarefas viram uma fila; cada uma mostra três alturas (soma, mínimo, máximo dos tempos) e a fila se reordena três vezes pelos critérios LPT.
- **Número real:** Ordens reais das três regras.
- **Texto máximo:** "as maiores primeiro"
- **Fala-guia:** Comece pelo mais difícil de encaixar. Mas maior em qual máquina?
- **Transição:** Uma das filas fica ativa.

### 00:25 · `sondas` (HeuristicaConstrutiva, animação ≈ 20 s)

- **Pergunta:** Onde cabe a próxima?
- **Na tela:** A primeira tarefa abre sondas fantasmas em todas as vagas; cada uma projeta sua posição no plano e um par de barras (parcela tempo, parcela energia). A maior cai, a menor encaixa. Câmera lenta para uma tarefa do meio da construção, com uma inserção **entre** duas outras e o deslocamento do sufixo; as demais aceleram.
- **Número real:** Custo f e candidatos reais de uma tarefa; número de opções testadas.
- **Texto máximo:** "máquina × modo × posição"
- **Fala-guia:** Testa todas as vagas e fica com o menor preço combinado.
- **Transição:** A construção termina e vira um ponto.

### 01:00 · `pesos` (HeuristicaConstrutiva, animação ≈ 13 s)

- **Pergunta:** E se a energia valer mais que o tempo?
- **Na tela:** O dial α gira de 1 a 0: em cada parada o Gantt se reconstrói e o ponto salta, deixando rastro. Em seguida as três filas lançam seus 33 pontos como fogos; muitos coincidem e somem um sobre o outro.
- **Número real:** 33 construções; quantidade de objetivos distintos (calcular).
- **Texto máximo:** "α: tempo ↔ energia"
- **Fala-guia:** O mesmo procedimento, com onze opiniões sobre o que importa.
- **Transição:** Um ponto escolhido aproxima-se.

### 01:25 · `modos` (HeuristicaConstrutiva, animação ≈ 13 s)

- **Pergunta:** Dá para economizar sem mexer na ordem?
- **Na tela:** Uma tarefa que sobra folga respira para econômico e o TEC cai sem mover Cmax; nas seguintes, setas de economia/hora competem. O ponto desce uma escada, passo a passo.
- **Número real:** 63 soluções no caminho (conta o passo 0 de cada partida); frente final (12; 864,0) a (16; 543,6).
- **Texto máximo:** "economia por hora"
- **Fala-guia:** Desacelera primeiro quem não atrasa ninguém.
- **Transição:** Sequências são trancadas com cadeados.

### 01:50 · `soltar` (HeuristicaOciosidade, animação ≈ 14 s)

- **Pergunta:** E se a melhor jogada for não fazer nada?
- **Na tela:** As barras ganham molas, mas a ordem está travada. Uma tarefa que invade a ponta recua e a seguir avança para depois dela; elástico amarelo estica e o contador cai. Anime um caso em que adiar compensa e outro em que não.
- **Número real:** Um plano real antes e depois, com TEC de ambos.
- **Texto máximo:** "a ordem fica, o relógio solta"
- **Fala-guia:** Esperar pode ser mais barato que trabalhar.
- **Transição:** As posições possíveis de uma tarefa viram uma curva.

### 02:15 · `curvas` (HeuristicaOciosidade, animação ≈ 16 s)

- **Pergunta:** Como escolher o melhor instante de cada uma?
- **Na tela:** f(t) nasce como colunas pulsantes sob uma barra que varre os instantes; g(t) desce como cortina de água que nunca sobe. A próxima tarefa parte de g com setup. Para três máquinas, três curvas se **somam** verticalmente enquanto uma linha ε varre e gera degraus.
- **Número real:** Valores de f e g da instância.
- **Texto máximo:** "f: exatamente em t · g: até t"
- **Fala-guia:** A cortina guarda o melhor custo até cada instante.
- **Transição:** A soma vira degraus no plano.

### 02:40 · `confronto` (HeuristicaOciosidade, animação ≈ 8 s)

- **Pergunta:** Quanto a espera rendeu?
- **Na tela:** A frente cinza da construtiva é puxada por molas até a da ociosidade; a exata aparece ao fundo. Onde coincidem, acende. Onde não alcança, surge a lacuna.
- **Número real:** Frentes reais: ociosidade de (12; 864,0) até (17; 493,2); exata até (20; 478,8); 2 sequências distintas.
- **Texto máximo:** "2 sequências"
- **Fala-guia:** O melhor tempo para as ordens dadas. A limitação são as ordens.
- **Transição:** Quadro-base final.

## 6. Momento uau

**O dial e a soltura.** O dial gira e o Gantt se refaz como um mecanismo; logo depois, em um único gesto, os cadeados descem e as barras deslizam, abrindo a ponta como cortina.

## 7. Dados

Trace: por tarefa de uma construção, todas as sondas (`insercoes`), valor f e escolha, reproduzindo o laço de `construir` e conferindo com seu resultado; as 33 construções; o caminho de `ajustar_modos`; uma base, sua curva por máquina de `programar_maquina` (f não é exposto: recalcule e confira `custo_ate`); frentes finais de ambas e a exata. Adicione as duas pastas de heurística ao `sys.path`, pois elas importam entre si como módulos soltos.

## 8. Armadilhas de fidelidade

- O ótimo da ociosidade vale **para as sequências dadas**, não para o problema inteiro.
- A DP de ociosidade também escolhe modos. Não atribua todo o ganho à espera. Se quiser isolar o efeito, rode `modos_fixos=True`, identifique a variante e não a misture com a da campanha.
- As 33 construções não incluem espera; não são todos os pontos da frente.
- A heurística é determinística, sem população e sem seed.
- O primeiro ponto e os outros não são garantidamente ótimos: compare com a exata só nos pontos mostrados. Aqui, 14 a 17 h coincidem com a exata; 12 e 13 h não.
- A construção não volta atrás nem realoca tarefas já inseridas, embora as insira no meio.

## 9. Aceite específico

Além do aceite comum do guia:

- [ ] O público vê opções perdedoras, não só a vencedora.
- [ ] A posição no meio da sequência desloca o sufixo.
- [ ] f e g são distinguidos por movimento.
- [ ] A diferença entre ociosidade e exata aparece e é explicada.

Render final: `.venv/bin/python src/presentation/apresentar.py --deck heuristica --render --quality m`
