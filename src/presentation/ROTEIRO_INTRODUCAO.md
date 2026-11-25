# Roteiro da introdução

**Escalonamento em máquinas paralelas não relacionadas com tarifa por horário**

**Duração ao vivo** 08:00 · **Cenas** `IntroFabrica`, `ProblemaMaquinas`, `ProblemaSimulacao`

Cada marca indica quando iniciar o trecho. A animação termina antes da fala e o último quadro permanece na tela. Todos os números vêm de uma instância didática, resolvida pela programação dinâmica do projeto. Ela não pertence ao conjunto do artigo.

## 00:00–02:10 · Introdução

### 00:00 · `fabrica`

Imagine uma fábrica com três máquinas, ligada a partir das oito da manhã. O preço da energia não é o mesmo o dia todo: das 18h às 21h vale a tarifa de ponta, aqui três vezes mais cara. [Acompanhe o ponteiro entrar na faixa coral.] As máquinas fazem o mesmo trabalho, mas o custo por hora triplica. Quem planeja a produção escolhe quando gastar essa energia.

### 00:45 · `conflito`

Agora o mesmo conjunto de oito tarefas, em dois planos. O da esquerda termina o mais cedo possível, em 12 horas, mas usa mais o modo normal e processa durante a ponta. O da direita usa modos econômicos e espera a ponta passar. Termina 8 horas depois e custa 41% menos. Nenhum dos dois é melhor em tudo.

### 01:30 · `objetivo`

Cada plano pode ser resumido por dois números: o término da última tarefa, o makespan ou Cmax, e o custo total de energia, o TEC. Assim, um plano inteiro vira um ponto. Queremos os melhores compromissos entre esses extremos. O problema foi proposto por Rego e colaboradores em 2022, nossa referência.

## 02:10–05:10 · O problema

### 02:10 · `nao_relacionadas`

As máquinas são paralelas porque qualquer uma pode executar qualquer tarefa. E são não relacionadas porque não existe uma máquina sempre mais rápida. A tarefa 1 leva 4, 6 ou 3 horas e prefere a M3. A tarefa 2 leva 4, 2 ou 6 e prefere a M2. [Aponte para a tabela.] Não há um fator único que converta uma coluna em outra.

### 02:55 · `modos`

Cada tarefa também escolhe um modo de operação. Na tela, a largura é a duração e a altura é a potência, portanto a área é a energia. O modo rápido encurta a tarefa 5 de 6 para 5 horas, mas sobe de 360 para 450 quilowatts-hora. O econômico leva 8 horas e gasta 288. A duração é arredondada para cima, para um número inteiro de intervalos.

### 03:35 · `setup`

Entre duas tarefas consecutivas há uma preparação, o setup, que depende da máquina e da ordem. Na M1, fazer a tarefa 2 depois da 1 exige duas horas. Invertendo a ordem, uma hora. [Aponte para a célula destacada.] As mesmas tarefas terminam uma hora antes só pela troca.

### 04:05 · `ponta`

O custo depende ainda do instante de início. Deslizando a tarefa no tempo, aparecem os seis casos do artigo: antes da ponta, entrando, atravessando, dentro, saindo e depois. Em cada um, só a parte coral paga a tarifa cara. No fim, uma decisão menos óbvia: esperar. Logo após o setup, a tarefa custaria 198. Aguardando o fim da ponta, custa 90. No modelo, espera e setup não consomem energia, mas atrasam a produção.

## 05:10–08:00 · O problema em execução

### 05:10 · `alocacao`

Vamos juntar tudo. Oito tarefas aguardam na fila. Para cada uma decidimos máquina, posição, modo e espera. É essa tripla, tarefa, modo e espera, em uma sequência por máquina, que nosso código usa como representação. Blocos baixos são modos econômicos, blocos cinza são setups e o contorno amarelo é espera voluntária.

### 06:00 · `execucao`

Executando o plano. As rodas giram enquanto a máquina processa; o relógio corre e o custo acumula. [Espere o cursor chegar à ponta.] Repare que durante boa parte da ponta as máquinas 1 e 3 estão em preparação. A M3 ainda espera uma hora e retoma às 21h. A última tarefa termina às 23h: Cmax de 15 horas e custo de 544,8.

### 06:55 · `compromisso`

Se mudamos o plano, o ponto se move. Para 12 horas o custo sobe a 812,4. Para 20 horas, cai a 478,8. Os oito pontos formam a fronteira de Pareto exata deste exemplo: melhorar um objetivo exige piorar o outro. São oito tarefas e três máquinas; as instâncias do estudo chegam a 750 tarefas e 20 máquinas, e o problema é NP-difícil. Como buscar essa fronteira é o assunto da próxima parte.
