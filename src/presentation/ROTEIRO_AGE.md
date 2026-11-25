# Roteiro do AGE-MOEA

**Meta-heurística AGE-MOEA: a membrana que descobre a forma da frente**

**Duração ao vivo** 03:00 · **Cenas** `AgeCamadas`, `AgeGeometria`, `AgeBusca`

Demonstração na instância didática: população 16, 329 avaliações, cruzamento 0,9, mutação 0,7, seed 1235, escolhida por conter eventos didáticos. Os números vêm de `data/trace_age.json`. Não é um caso típico nem uma comparação de qualidade.

### 00:00 · `lote`

No SPEA2, entrava um filho por rodada. Aqui entra a turma inteira: 16 pais e 16 filhos. [Aponte para os Gantts pequenos.] Dois pais cruzam e cada tarefa herda suas decisões de um deles. A mutação põe três horas de espera antes da T4: o custo cai de 936 para 840. Noutro filho, a T7 é inserida depois da T2. Todos são avaliados antes da seleção.

### 00:30 · `camadas`

Trinta e dois planos disputam 16 vagas. A primeira casca, com seis planos, ninguém domina. Entra inteira. Depois entram outras duas, de quatro. Sobram duas vagas para quatro planos. [Aponte para os zeros.] Seria natural esperar uma nota de desempate, mas nesta versão do pymoo a camada cortada ainda vale zero para todos. Decide a ordem interna da lista. Os demais nem chegam a ser ordenados.

### 01:00 · `extremos`

Horas e dinheiro não se comparam diretamente. O AGE-MOEA fisga os dois extremos da primeira casca, não da população. De 12 a 22 horas vira de zero a um. De 661,2 a 915, também. A própria frente define a unidade.

### 01:25 · `membrana`

Agora, a forma. O plano interno mais próximo da diagonal tem coordenadas com média 0,574. [Acompanhe a membrana.] Com p igual a um, ela é reta. Menor que um, curva para dentro; maior, para fora. Ela trava em p igual a 1,25. Repare nas gerações: na geração 20, a frente mudou, a média caiu para 0,306, e p caiu para 0,59. Não supomos a forma. A frente informa.

### 02:00 · `escore`

De volta à geração 3, a membrana vira régua. Os extremos recebem infinito. Cada candidato soma a distância aos dois escolhidos mais próximos, e cada distância é dividida pela norma do escolhido. Vence 21 horas, com 1,77. As notas são refeitas e entra o próximo. Assim a lista cresce, longe dos já escolhidos. As camadas seguintes usam o inverso da distância a um ponto de referência: aqui, todas perto de 0,0015. Na cortada, zero.

### 02:35 · `busca`

Repetindo, a membrana muda a cada geração e a nuvem desce. [Aponte para o quadrado coral.] Este filho passa do horizonte de 24 horas e some, mas a avaliação é contada. O último lote tem só nove. Um compromisso final: 16 horas e 669. Na campanha: população 100, cruzamento 0,9 e mutação 0,7.
