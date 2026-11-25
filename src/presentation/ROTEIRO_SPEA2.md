# Roteiro do SPEA2 incremental

**Meta-heurística SPEA2 incremental: a arena de influência**

**Duração ao vivo** 03:30 · **Cenas** `Spea2Arena`, `Spea2Operadores`, `Spea2Busca`

Cada marca indica quando iniciar o trecho; o último quadro permanece na tela. Todos os números vêm de `data/trace_spea2.json`: uma execução real de `run_spea2` na instância didática, com população 12, cruzamento 0,7, mutação 0,5, 1.012 avaliações e seed 20525. É uma demonstração, com eventos escolhidos por serem didáticos; não mede a qualidade do método nem representa um caso típico. Os parâmetros da campanha aparecem só no fim.

### 00:00 · `populacao`

Cada ponto é um plano inteiro. O primeiro nasce de um LPT aleatório: as tarefas longas na frente, um sorteio dentro da janela azul e o encaixe que termina mais cedo. [Aponte para a janela.] Repetimos isso e temos doze planos. [Espere os Gantts caírem.] Alguns terminam antes, outros gastam menos. Como comparar?

### 00:25 · `forca`

De cada plano sai uma seta para todo plano que ele domina. Este domina nove: força nove. Este outro, quatro. Agora invertemos. [Aponte para a linha d'água.] O plano marcado é dominado por cinco. Cada um despeja nele a própria força: nove, oito, sete, cinco e quatro. Peso 33. [Espere tudo afundar.] Forte é quem domina muitos; fraco é quem carrega muito peso. Só dois boiam, com peso zero: ninguém os domina.

### 01:00 · `densidade`

Os dois empatam. Desempata o espaço livre. Na régua do algoritmo, uma hora vale uma unidade de custo. [A arena vira uma agulha.] A bolha vai até o quarto vizinho: 63 contra 129. Quem está mais sozinho vale mais. Reabrindo, vira faixa: manda o custo. Estes dois são os mais próximos. Dois duelos escolhem os pais.

### 01:25 · `cruzamento`

Para cada tarefa, uma moeda escolhe o pai, e o filho herda dele máquina, modo e espera. [Acompanhe as moedas.] Em que ordem? Na M1, T1 e T8 disputam o lugar. Somamos as posições nos dois pais: dois a dois. Um pequeno ruído decide: 2,14 contra 2,21, e a T8 vai antes. O filho, com 1.011, custa menos que os dois pais no mesmo prazo. Sem cruzamento, ele começaria como cópia de um pai.

### 02:00 · `mutacoes`

Um dado de cinco faces. Inserção: a T3 vai para o começo e o custo cai de 1.011 para 951. Realocação: a T5 muda de máquina e a T2 escapa da ponta. Troca: T3 e T7 cruzam. Modo: a T7 respira, mais baixa e mais larga. Espera: o elástico atrasa a T4; termina depois e custa menos. Na última, a espera empurra a T1 para além das 24 horas. Inviável: perde para qualquer viável, e a avaliação foi gasta.

### 02:35 · `expulsao`

Volta o filho do cruzamento: treze para doze vagas. Ele domina onze e despeja onze em cada. O mais pesado, com 58, sai. Na avaliação 676, ninguém domina ninguém: sai o mais apertado. [Aponte para as cartas.] Duas duplas de gêmeos empatam em zero. No segundo vizinho, 33,7 é menor que 115,2. Sai um gêmeo das 19 horas.

### 03:00 · `busca`

Agora do começo, um descendente por rodada. [Acompanhe o contador.] Pontos entram, pontos fogem, e a nuvem desce e se espalha. Não há arquivo externo: a frente sai da própria população final. Aqui, dez pontos em azul; em dourado, a fronteira exata, como referência. Um deles volta a ser plano: 15 horas, 638,4. Na campanha: população 200, cruzamento 0,7, mutação 0,5, dez mil avaliações.
