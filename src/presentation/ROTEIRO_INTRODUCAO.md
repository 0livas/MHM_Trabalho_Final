# Roteiro da introdução

**Escalonamento em máquinas paralelas não relacionadas com tarifa por horário**

**Duração ao vivo** 11:30 · **Cenas** `IntroFabrica`, `ProblemaMaquinas`, `ProblemaSimulacao`, `ObjetivosECaminhos`

Cada marca indica quando iniciar o trecho. A animação termina antes da fala e o último quadro permanece na tela. Todos os números vêm de uma instância didática, resolvida pela programação dinâmica do projeto. Ela não pertence ao conjunto do artigo.


## 00:00–01:30 · Introdução

### 00:00 · `fabrica`

Imagine uma fábrica com três máquinas, ligada a partir das oito da manhã. O preço da energia não é o mesmo o dia todo: das 18h às 21h vale a tarifa de ponta, aqui três vezes mais cara. [Acompanhe o ponteiro entrar na faixa coral.] As máquinas fazem o mesmo trabalho, mas o custo por hora triplica. Quem planeja a produção escolhe quando gastar essa energia.

### 00:30 · `conflito`

Agora o mesmo conjunto de oito tarefas, em dois planos. O da esquerda termina o mais cedo possível, em 12 horas, mas usa mais o modo normal e processa durante a ponta. O da direita usa modos econômicos e espera a ponta passar. Termina 8 horas depois e custa 41% menos. Nenhum dos dois é melhor em tudo.

### 01:00 · `objetivo`

Cada plano pode ser resumido por dois números: o término da última tarefa, o makespan ou Cmax, e o custo total de energia, o TEC. Assim, um plano inteiro vira um ponto. Queremos os melhores compromissos entre esses extremos. O problema foi proposto por Rego e colaboradores em 2022, nossa referência.

## 01:30–05:35 · O problema

### 01:30 · `nao_relacionadas`

As máquinas são paralelas porque qualquer uma pode executar qualquer tarefa. E são não relacionadas porque não existe uma máquina sempre mais rápida. A tarefa 1 leva 4, 6 ou 3 horas e prefere a M3. A tarefa 2 leva 4, 2 ou 6 e prefere a M2. [Aponte para a tabela.] Não há um fator único que converta uma coluna em outra. [Pausa.] Agora considere somente essas duas tarefas no modo normal. Colocamos as duas na M3, com a preparação entre elas, enquanto a M2 fica livre. Ao levar T2 para M2, sua duração muda e as duas máquinas passam a trabalhar em paralelo. O término do conjunto recua. Este é um exemplo parcial de alocação; não é ainda uma solução das oito tarefas. A máquina mais rápida para uma tarefa não define sozinha o melhor plano completo.

### 03:25 · `modos`

Cada tarefa também escolhe um modo de operação. Na tela, a largura é a duração e a altura é a potência, portanto a área é a energia. O modo rápido encurta a tarefa 5 de 6 para 5 horas, mas sobe de 360 para 450 quilowatts-hora. O econômico leva 8 horas e gasta 288. A duração é arredondada para cima, para um número inteiro de intervalos.

### 04:05 · `setup`

Entre duas tarefas consecutivas há uma preparação, o setup, que depende da máquina e da ordem. Na M1, fazer a tarefa 2 depois da 1 exige duas horas. Invertendo a ordem, uma hora. [Aponte para a célula destacada.] As mesmas tarefas terminam uma hora antes só pela troca.

### 04:40 · `ponta`

O custo depende ainda do instante de início. Deslizando a tarefa no tempo, aparecem os seis casos do artigo: antes da ponta, entrando, atravessando, dentro, saindo e depois. Em cada um, só a parte coral paga a tarifa cara. No fim, uma decisão menos óbvia: esperar. Logo após o setup, a tarefa custaria 198. Aguardando o fim da ponta, custa 90. No modelo, espera e setup não consomem energia, mas atrasam a produção.

## 05:10–11:00 · O problema em execução

### 05:35 · `alocacao`

Vamos juntar tudo. Oito tarefas aguardam na fila. Para cada uma decidimos máquina, posição, modo e espera. É essa tripla, tarefa, modo e espera, em uma sequência por máquina, que nosso código usa como representação. Blocos baixos são modos econômicos, blocos cinza são setups e o contorno amarelo é espera voluntária.

### 06:20 · `execucao`

Executando o plano. As rodas giram enquanto a máquina processa; o relógio corre e o custo acumula. [Espere o cursor chegar à ponta.] Repare que durante boa parte da ponta as máquinas 1 e 3 estão em preparação. A M3 ainda espera uma hora e retoma às 21h. A última tarefa termina às 23h: Cmax de 15 horas e custo de 544,8.

### 07:00 · `compromisso`

Se mudamos o plano, o ponto se move. Para 12 horas o custo sobe a 812,4. Para 20 horas, cai a 478,8. Os oito pontos formam a fronteira de Pareto exata deste exemplo: melhorar um objetivo exige piorar o outro. São oito tarefas e três máquinas; as instâncias do estudo chegam a 750 tarefas e 20 máquinas, e o problema é NP-difícil. Antes de conhecer os métodos, vamos distinguir o maior término dentro de um plano da minimização entre planos.


## 07:40–11:30 · Objetivos e caminhos de solução

### 07:40 · `maior_termino`

Observe o término de cada máquina. Uma fica pronta antes, outra depois. A produção inteira só terminou quando a última máquina concluiu sua última tarefa. É por isso que calculamos o máximo dos términos: esse número é o Cmax. [Acompanhe cada marca e espere o destaque dourado.] Mas nosso objetivo é minimizar esse número entre planos diferentes. O máximo define a medida dentro de um plano; o mínimo define a busca por um plano melhor. Não estamos maximizando o tempo de produção.

### 08:30 · `minimizar`

Cada ponto representa um plano completo. Primeiro olhe apenas para o eixo horizontal: mover para a esquerda significa terminar antes. [Pausa.] Agora olhe para o vertical: mover para baixo significa pagar menos energia. [Pausa.] Queremos minimizar ambos. O extremo mais rápido e o extremo mais barato não são o mesmo plano. É por isso que guardamos alternativas de compromisso. Mais adiante, podemos maximizar um indicador de qualidade da frente, como o hipervolume. Isso não muda os dois objetivos do problema: Cmax e TEC continuam sendo minimizados.

### 09:15 · `dominancia`

Partimos do plano de menor custo deste exemplo e atrasamos o último processamento em uma hora. Ele continua fora da ponta, cabe no horizonte e custa o mesmo, mas termina depois. Portanto, o plano anterior é melhor em tempo e não pior em custo: domina o plano atrasado. [Pausa antes de apagar o brilho.] Os pontos dourados, por sua vez, oferecem compromissos que não eliminam uns aos outros. Esta é a fronteira exata da instância didática; não é um resultado para todas as instâncias industriais.

### 10:00 · `caminhos`

Como encontrar esses planos? Primeiro, os métodos exatos: nosso backtracking com propagação, nossa programação dinâmica e o CP-SAT do OR-Tools. Eles procuram também uma prova; se uma execução para antes de concluir, a fronteira pode continuar provisória. Depois, duas heurísticas: uma constrói sequências por escolhas ponderadas; a outra otimiza modos e esperas para a alocação e a sequência recebidas. Por fim, quatro meta-heurísticas: VNS/VND, SPEA2, MOEA/D e AGE-MOEA exploram novas alternativas. Todos são avaliados pelas mesmas restrições e pelos mesmos cálculos de tempo e energia. Nas próximas partes acompanharemos suas decisões. A calibração e os experimentos mostrarão como comparar as frentes produzidas.

## Orientações de fala e limites

As marcas são tempos de fala ao vivo. Os trechos deixam o último quadro visível para a explicação; não há áudio gravado. Os movimentos iniciais de alocação são mais lentos, e cada duração permanece visível antes da escolha. Use as pausas para apontar para a máquina e depois para a célula correspondente na matriz.

A instância didática tem intervalos de uma hora, começa às 8h e utiliza tarifa de ponta três vezes maior. Ela não é uma instância do artigo e não demonstra desempenho típico dos algoritmos. Cada comparação de duração fixa o modo normal. Energia é potência multiplicada pelo tempo; custo é energia multiplicada pela tarifa de cada intervalo. Setup e espera ocupam tempo, mas não acrescentam consumo ao TEC implementado. A primeira cena com todas as máquinas ligadas é uma ilustração da tarifa, não um escalonamento das oito tarefas.
