# Roteiro da heurística

**Construção ponderada e inserção ótima de ociosidade**

**Duração ao vivo** 03:00 · **Cenas** `HeuristicaConstrutiva`, `HeuristicaOciosidade`

Cada marca indica quando iniciar o trecho; o último quadro permanece na tela. Os números vêm de `data/trace_heuristica.json`, calculado na instância didática. As heurísticas são determinísticas: não há população nem seed.

### 00:00 · `pergunta`

Dá para achar um bom plano sem testar todos? Comece pelo mais difícil de encaixar. Mas a maior tarefa, em qual máquina? [Aponte as três colunas.] Usamos três filas: soma, maior e menor tempo. A ordem muda: pela soma, a T5 abre a fila; pelo menor tempo, a T3.

### 00:25 · `sondas`

A T3 experimenta toda vaga: máquina, modo e posição. São nove opções, e cada uma tem um preço: uma parcela de tempo, outra de energia. As caras caem, a menor encaixa. [Espere a T2.] Agora são 27. Vence uma vaga entre a T7 e a T3, por 0,616: a T3 corre para a direita. Ninguém troca de máquina depois de inserido. Foram 156 opções até virar um ponto: 13 horas, 867.

### 01:00 · `pesos`

O dial α diz quanto o tempo vale. De 1 a 0, o mesmo procedimento refaz o plano. Olhe o fim: só energia, o custo dá 586,8. Com 0,2, dava 543,6! O guloso não volta atrás. Três filas e onze pesos: 33 construções, só 17 objetivos distintos.

### 01:25 · `modos`

Agora a ordem não muda, só os modos. A T7 economiza 52,8 por hora, mas vence a T5: 30, sem atrasar ninguém. Cada passo é candidato: 63 soluções, contando as partidas. A frente vai de 12 horas, 864, a 16 horas, 543,6. [Aponte os cadeados.] Trancamos as sequências.

### 01:50 · `soltar`

A ordem fica, o relógio solta. Adiar a T2 não ajuda: na ponta, custa 36 a mais; depois dela, nada economiza e atrasa o término. Já a T8 e a T6 esperam uma hora e a ponta esvazia: de 568,8 em 15 horas para 504 em 16. Com os mesmos modos: foi só a espera.

### 02:15 · `curvas`

Quem escolhe os instantes, e também os modos, é uma programação dinâmica por máquina. A coluna f termina exatamente em t: na ponta, sobe a 108. A cortina g, o melhor até t, fica em 43,2: nunca sobe. A próxima parte de g, com setup. Para cada teto, somamos as máquinas: nascem os degraus.

### 02:40 · `confronto`

A frente da construtiva é puxada, com espera e modos livres. De 14 a 17 horas, coincide com a exata. Em 12 e 13 faltam 51,6; 18 e 20, não alcança. É o melhor tempo para duas sequências. A limitação são as ordens.
