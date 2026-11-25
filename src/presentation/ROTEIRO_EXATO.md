# Roteiro do método exato

**Programação dinâmica com ε-restrição**

**Duração ao vivo** 03:00 · **Cenas** `ExatoEstados`, `ExatoEscada`

Números de `data/trace_exato.json`, calculados na instância didática. O alcance vem de `data/baselines/` e da campanha. A fronteira é exata para a discretização da entrada.

### 00:00 · `pergunta`

Como ter certeza de que não existe plano melhor? [Acompanhe o contador.] Só de máquina e modo são nove opções por tarefa. Com oito tarefas, 43 milhões, sem contar ordem nem espera. Testar tudo não é opção. Mas muitos planos têm o mesmo começo, e é isso que o método aproveita, uma máquina de cada vez. Os planos da abertura são sorteados, só para ilustrar.

### 00:30 · `rotulos`

De um começo, basta lembrar quais tarefas, qual a última, quando termina e quanto gastou. [Aponte para a ficha.] Duas tarefas na M3: seis horas, 120. Para continuar, testamos cada modo. E cada início? Não é preciso. [Acompanhe a bola.] Começar às 15h pega uma hora de ponta. Os próximos inícios custam igual ou mais, até o das 21h. O algoritmo pula direto para lá: assim nasce a espera.

### 01:05 · `poda`

Dois começos na mesma gaveta: mesmas tarefas, mesma última. Um termina antes e gasta menos. Qualquer continuação da perdedora, a vencedora imita, no mesmo instante, por menos. A perdedora some com todos os seus descendentes. Se a última muda, não se comparam, pois o preparo seguinte pode mudar, como nesta instância do conjunto. [Aguarde a chuva.] São 47.438 transições, que não são planos completos: 29.263 recusadas, 18.175 inseridas, das quais 10.334 saem depois. Ao fim de cada máquina, as gavetas do mesmo conjunto se fundem.

### 01:45 · `particao`

Cada máquina já sabe seu melhor custo para qualquer conjunto. Falta repartir as tarefas. Com teto de 12 horas, tudo na M3 não cabe. A divisão mais barata de todas também não. [Aponte para a régua.] Dos 256 conjuntos possíveis para a M3, só três admitem um plano. O melhor custa 812,4. Os ponteiros reconstroem esse plano de trás para frente.

### 02:15 · `epsilon`

E se permitirmos uma hora a mais? O teto, chamado épsilon, anda de 12 a 24 horas, e para cada um temos o menor custo provado. Em 19 e de 21 a 24, nada melhora. São oito degraus, os mesmos da introdução. O artigo base usa soma ponderada por MILP, que só alcança pontos apoiados na envoltória convexa. O épsilon encontra também os demais.

### 02:45 · `limite`

Cada tarefa extra dobra os conjuntos. Temos nove fronteiras certificadas, de seis a treze tarefas. Treze é um limite configurado, não teórico. É a régua dos outros métodos, quando cabe.
