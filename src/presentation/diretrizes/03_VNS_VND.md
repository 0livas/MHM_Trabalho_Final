# 03 · Meta-heurística VNS/VND multiobjetivo

## 1. Sua tarefa

Você vai criar, sozinho nesta sessão, a animação **Meta-heurística VNS/VND multiobjetivo** da apresentação do trabalho. Leia primeiro `src/presentation/diretrizes/00_GUIA_COMUM.md` e siga-o integralmente; depois leia as fontes abaixo. Entregue `anim_vns.py`, `trace_vns.py`, `data/trace_vns.json` e `ROTEIRO_VNS.md` em `src/presentation/`, e o player renderizado em `media/vns/`. Cenas: `VnsPartida`, `VnsDescida`, `VnsBusca`. Outras sessões produzem os demais vídeos ao mesmo tempo: não toque em arquivos compartilhados.


## 2. Fonte da verdade

- `src/metaheuristics/vns_vnd.py`: `_random_greedy_schedule`, `NEIGHBORHOODS`, `_wait_moves`, `_candidate_schedules`, `VNSVND._evaluate`, `_origin`, `_vnd`, `_shake`, `run`.
- `VNSVND.trace` já registra os eventos `evaluation`, `rejected`, `origin`, `shake_neighborhood`, `shake_success`, `shake_failed`, `vnd_neighborhood`, `vnd_accept`, `archive_expansion`.
- Não use `vns_vnd_original.py`, exceto como contraste histórico de uma frase.

## 3. Como funciona aqui

1. **Partida (LPT aleatório).** Ordena pela menor duração possível, decrescente; sorteia uma entre as ⌈√r⌉ primeiras (r restantes); escolhe máquina e modo de menor término, com desempate aleatório; sem espera. A construção pode falhar, caso em que outra é tentada.
2. **Arquivo de Pareto** ilimitado: todo escalonamento viável avaliado tenta entrar.
3. **Origem:** entre os pontos do arquivo menos explorados, sorteia um.
4. **Shake em Nk:** sorteia movimentos da vizinhança k sobre a origem, até achar um viável (máximo `shaking_attempts`). Não exige melhora.
5. **VND a partir dele:** N1 modo → N2 espera → N3 inserção na mesma máquina → N4 realocação → N5 troca de quaisquer duas tarefas. Examina até `max_candidates_per_neighborhood` vizinhos por visita. O **primeiro que domina** o corrente é aceito e o VND **volta a N1**; sem melhora, passa à próxima.
6. Se shake ou VND expandiu o arquivo, o shake volta a N1 **sobre a mesma origem**; senão tenta N(k+1). Fim da varredura: nova origem.
7. Inviável é rejeitado, mas consome avaliação. Para no orçamento ou se não houver movimento avaliável.

N2 usa esperas de ±1, zero e alvos ligados às bordas da tarifa e dos dias. Campanha nova: 16 partidas, 25 candidatos por vizinhança, 20 tentativas de shake, 10.000 avaliações.

## 4. Conceito criativo

**Metáfora: o explorador e as cinco portas.** Um explorador luminoso carrega um plano por um corredor vertical de cinco portas (N1 a N5), cada uma com um ícone do movimento. O shake é um terremoto que o lança a outro ponto. O VND é um **elevador**: sobe uma porta quando não acha melhora e **despenca para N1** quando acha. O arquivo é um mapa com bandeiras. Cor `COLORS["vns_vnd"]`. Layout de detalhe: elevador estreito à esquerda do plano Cmax × TEC ou sobre a faixa de tarifa; o Gantt permanece legível. As operações (modo, espera, inserção, troca e realocação) usam a coreografia do guia.

## 5. Roteiro por trecho

### 00:00 · `partida` (VnsPartida, animação ≈ 18 s)

- **Pergunta:** Por onde começar a explorar?
- **Na tela:** As tarefas viram uma fila por dificuldade. Uma janela dourada de ⌈√r⌉ pulsa sobre os primeiros; um dado escolhe; a tarefa voa à máquina/modo de término mais cedo, com sondas fracas nas outras. A janela encolhe conforme a fila acaba. Repita em 4× para quatro partidas.
- **Número real:** Janelas ⌈√8⌉ = 3 até 1 e quatro partidas reais.
- **Texto máximo:** "janela ⌈√r⌉"
- **Fala-guia:** Quase guloso, com sorte suficiente para variar.
- **Transição:** Quatro planos viram bandeiras.

### 00:35 · `arquivo` (VnsPartida, animação ≈ 12 s)

- **Pergunta:** O que vale a pena guardar?
- **Na tela:** Bandeiras caem no mapa; as dominadas tombam. A origem é escolhida pelo contador de visitas: a bandeira menos visitada acende o farol.
- **Número real:** Arquivo inicial real.
- **Texto máximo:** "menos explorada"
- **Fala-guia:** Guarda quem ninguém domina e visita quem foi esquecido.
- **Transição:** A câmera entra no plano da origem.

### 01:00 · `shake` (VnsDescida, animação ≈ 13 s)

- **Pergunta:** Como sair de onde já estamos?
- **Na tela:** Terremoto: a origem sofre um movimento aleatório de N1, depois um de outra vizinhança. O ponto pode **piorar**. Mostre um inviável: a barra cruza o horizonte, racha, a avaliação conta, e outro sorteio resolve.
- **Número real:** Eventos `shake_*` reais.
- **Texto máximo:** "pode piorar"
- **Fala-guia:** O tremor não procura melhora. Procura novidade.
- **Transição:** O explorador cai no elevador, em N1.

### 01:30 · `portas` (VnsDescida, animação ≈ 30 s)

- **Pergunta:** Qual mudança ajuda?
- **Na tela:** Percorra as cinco portas uma a uma, cada uma com um movimento real em câmera lenta: respiração (modo), elástico (espera nas bordas da ponta), salto na fila (inserção), salto de faixa (realocação), arco cruzado (troca). Para cada, três candidatos fantasmas no plano.
- **Número real:** Ao menos um candidato real por vizinhança; mostre Cmax e TEC antes e depois.
- **Texto máximo:** nome da porta
- **Fala-guia:** Cinco jeitos de mexer no mesmo plano, da mais leve à mais ampla.
- **Transição:** Um candidato de uma porta alta acende.

### 02:20 · `reinicio` (VnsDescida, animação ≈ 15 s)

- **Pergunta:** E quando uma mudança melhora?
- **Na tela:** O candidato domina: sombra retangular no plano, pulso verde. O elevador **despenca para N1**. Repita três vezes, cada vez mais rápido, e depois mostre a subida sem melhora até N5 e a saída.
- **Número real:** Sequência real de `vnd_accept` com as vizinhanças.
- **Texto máximo:** "volta a N1"
- **Fala-guia:** Melhorou? Recomeça do movimento mais simples.
- **Transição:** A câmera abre para o mapa.

### 02:45 · `busca` (VnsBusca, animação ≈ 18 s)

- **Pergunta:** E se ninguém domina, mas é novo?
- **Na tela:** Candidato incomparável: não vira corrente, mas ganha bandeira; o shake reinicia em N1 na mesma origem. Depois, acelere a busca inteira: rastros, bandeiras nascendo e tombando, contador de avaliações e de rejeições.
- **Número real:** Evolução do arquivo por avaliação; rejeições totais.
- **Texto máximo:** "entra no mapa"
- **Fala-guia:** Há duas formas de ganhar: descer ou ampliar o mapa.
- **Transição:** A frente estabiliza.

### 03:15 · `fecho` (VnsBusca, animação ≈ 6 s)

- **Pergunta:** O que encontramos?
- **Na tela:** O melhor compromisso vira o Gantt; a frente surge sobre a exata. Selo da campanha.
- **Número real:** Frente da demonstração; 16/25/20 e 10.000 na campanha.
- **Texto máximo:** "campanha: 16 · 25 · 20"
- **Fala-guia:** Pouca memória, muito movimento.
- **Transição:** Quadro-base final.

## 6. Momento uau

**O elevador.** Três melhorias reais em seguida: cada uma arremessa a cabine de N3, N4 ou N5 até N1 num único plano, com o ponto descendo e a barra mudando no Gantt, em sincronia. Se a seed não tiver três, procure outra e registre.

## 7. Dados

Subclasse de `VNSVND` que sobrescreve `_evaluate` para guardar o escalonamento de cada avaliação e cruza com `trace`. Guarde também as fases do shake e do VND (subclasse de `_shake`/`_vnd` chamando `super`). Config da demonstração sugerida: 4 partidas, 25 candidatos, 20 shakes, 400–1500 avaliações, seed registrada. Em N2, identifique a espera pelo par antes/depois. Para o mapeamento operação → movimento, compare o escalonamento com o corrente.

## 8. Armadilhas de fidelidade

- O VND só aceita quem **domina** o corrente; incomparável entra no arquivo, mas não vira corrente.
- É primeira melhoria sobre uma amostra, não a melhor de toda a vizinhança.
- Reiniciar o VND em N1 e reiniciar o shake em N1 são eventos diferentes (dominância versus expansão do arquivo).
- Shake e VND usam as mesmas cinco vizinhanças; o shake não aceita por qualidade.
- `_origin` sorteia entre os **menos explorados**, não escolhe o melhor.
- Se um ponto sair do arquivo, sua contagem de visitas não aparece no sorteio; não invente memória além de `explored_origins`.
- A tela `VNSVND.trace` não guarda escalonamentos; capture-os.

## 9. Aceite específico

Além do aceite comum do guia:

- [ ] As cinco vizinhanças aparecem com movimentos distintos e reais.
- [ ] O retorno a N1 por dominância e o reinício por expansão são visualmente diferentes.
- [ ] Aparece um inviável que conta avaliação.
- [ ] Um candidato incomparável entra no arquivo sem virar corrente.

Render final: `.venv/bin/python src/presentation/apresentar.py --deck vns --render --quality m`
