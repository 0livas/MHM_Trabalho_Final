# Roteiro da meta-heurística VNS/VND multiobjetivo

**Duração ao vivo** 03:30 · **Cenas** `VnsPartida`, `VnsDescida`, `VnsBusca`

Demonstração na instância didática, seed 6653, escolhida por conter os eventos mostrados; não é um caso típico. Os números vêm de `data/trace_vns.json`.

### 00:00 · `partida`

O VNS precisa de planos iniciais. Ordenamos as tarefas pela menor duração possível, da mais longa para a mais curta. [Aponte para a janela dourada.] Uma janela de raiz de r, arredondada para cima, marca as primeiras: três no começo, uma no fim. O dado escolhe uma delas, e a tarefa vai para a máquina e o modo de término mais cedo. Quase guloso, com sorte suficiente para variar. Repetimos quatro vezes: quatro partidas reais.

### 00:35 · `arquivo`

O que guardar? Só quem ninguém domina. Das quatro partidas, duas ficam de pé e duas tombam. Para escolher a origem, olhamos quem foi menos explorado. Aqui as duas têm zero visitas, então o sorteio decide. [Aponte para o farol.] Sai o plano de 14 horas.

### 01:00 · `shake`

O shake é um tremor: um movimento sorteado sobre a origem. Ele não procura melhora, procura novidade. Na vizinhança de espera, o primeiro sorteio passa do horizonte. É rejeitado, mas a avaliação conta. O seguinte é viável e pior, e serve assim mesmo. Depois, outro tremor em N1 leva à descida que vamos acompanhar.

### 01:30 · `portas`

O VND é um elevador com cinco portas. Na primeira, o modo: duas mudanças melhoram o plano e ele continua em N1. Agora nada mais ajuda ali. N2 mexe na espera, encostando a tarefa na borda da ponta: o custo cai de 888 para 828, mas o Cmax sobe de 15 para 21 horas. Não domina. N3 insere na mesma máquina. N4 realoca para outra. N5 troca duas tarefas. São cinco jeitos de mexer no mesmo plano, da mais leve à mais ampla. Em cada porta examinamos uma amostra de até 25 vizinhos. [Aponte para o ponto verde.] Em N5, um candidato domina: 13 horas e 828.

### 02:20 · `reinicio`

Melhorou? Recomeça do movimento mais simples. [Aponte para a cabine.] De N5, despenca para N1. Depois de N3. Depois de N5 de novo. No fim, nenhuma porta melhora, e o elevador sai pelo topo.

### 02:45 · `busca`

E se o candidato não domina, mas também não é dominado? Voltamos à avaliação 17: ele entra no mapa, mas o plano corrente não muda. Como o mapa cresceu, o shake recomeça em N1, sobre a mesma origem. Há duas formas de ganhar: descer ou ampliar o mapa. Em 1.532 avaliações, 233 foram rejeitadas.

### 03:15 · `fecho`

Seis planos na frente. O compromisso mostrado termina em 15 horas e custa 568,8. Na campanha: 16 partidas, 25 candidatos, 20 tentativas e 10 mil avaliações. Pouca memória, muito movimento.
