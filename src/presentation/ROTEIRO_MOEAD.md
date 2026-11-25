# Roteiro do MOEA/D

**Meta-heurística MOEA/D: o leque de holofotes e o coral de vizinhos**

**Duração ao vivo** 03:00 · **Cenas** `MoeadLeque`, `MoeadVizinhos`, `MoeadBusca`

Cada marca indica quando iniciar o trecho. O último quadro permanece na tela até a próxima marca. Os números vêm de `data/trace_moead.json`: uma **demonstração** com 15 feixes, 5 vizinhos, seed 320 e 615 avaliações na instância didática. A seed foi escolhida por conter uma cascata completa; não é um caso típico. Os parâmetros da **campanha** aparecem só no fim.

### 00:00 · `direcoes`

Queremos equilibrar tempo e energia. E se, em vez de uma pergunta difícil, fizermos quinze fáceis? [O leque se abre.] Cada feixe é um peso, do tempo puro à energia pura, e quer uma coisa diferente. Cada um recebe um plano inicial, montado pelo LPT aleatório. O menor tempo e o menor custo encontrados formam o ponto ideal. [Aponte a estrela.] O leque passa a partir dele.

### 00:30 · `medida`

Como um feixe mede um plano? Duas réguas saem do ideal, tempo e custo, com escala fixa e multiplicadas pelos pesos. A maior das duas é a nota, o valor de Tchebycheff. Menor é melhor. Com pesos iguais, A vale 0,0625 e B vale 0,0570: vence B. [Espere o feixe girar.] Com peso maior no custo, os mesmos planos se invertem, e A vence.

### 01:00 · `pais`

As teclas são os feixes. A ordem de visita é sorteada. [Primeiro pulo destacado.] Em 90% das vezes, os pais são vizinhos; aqui o sorteio escapou e eles vieram de longe. [Segundo pulo.] Aqui vieram da vizinhança, mas ninguém melhorou. [Terceiro pulo.] Agora, com calma: o coral tem cinco feixes, incluindo o próprio. Dois deles são os pais. Cada tarefa herda de um dos dois. Depois, a mutação realoca a T3 da M3 para a M1. O anel vazio ainda não foi avaliado.

### 01:40 · `cascata`

Avaliado, o filho tem 15 horas e custo de 864. Primeiro, o ideal desce até esse custo, e todas as notas dos vizinhos são recalculadas. Só então o filho é comparado, em verde, com cada um. [Faça silêncio durante a cascata.] Cinco de cinco: um único filho substitui a vizinhança inteira, no mesmo passo. Uma boa ideia se espalha. Nem sempre é assim: no evento seguinte, são três de cinco.

### 02:15 · `inviavel`

E quando o plano não cabe? A T2 muda de máquina, empurra a T8 e ultrapassa as 24 horas. A avaliação conta, a de número 96. O filho some, e no lugar entra a cópia de um plano sorteado na população. Não é reparo: a cópia compete como qualquer outra. Aqui, não substituiu ninguém.

### 02:35 · `busca`

Acelerando, os pontos descem até a frente. [Pausa no ponto cinza.] Surpresa: o plano de custo 543,6, o menor da execução, moveu o ideal, mas nenhum dos cinco vizinhos o guardou. Não há arquivo externo. No fim, quinze feixes guardam onze planos; os não dominados formam a frente, com cinco pontos. Na campanha: 300 feixes, 10 vizinhos, 10.000 avaliações.
