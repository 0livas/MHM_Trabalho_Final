# Roteiro da calibração

**Optuna/TPE e confirmação**

**Duração ao vivo** 03:00 · **Cenas** `CalibracaoMesa`, `CalibracaoTorneio`

Todos os números estão em `data/trace_calibracao.json`, que só resume arquivos já gravados. O Gantt pequeno é ilustração com a instância didática. O score daqui não é comparável ao hipervolume da campanha, porque a normalização e a referência são outras.

### 00:00 · `botoes`

Cada método tem seus botões. [Aponte as mesas.] Mudar um deles muda o plano que sai; aqui, só uma ilustração. Poucos botões já dão muitas combinações: 125 no VNS, 252 no SPEA2 e no AGE, 7.560 no MOEA/D. Não dá para ouvir tudo. Quem decide é um procedimento, igual para os quatro. Vamos acompanhar a mesa do SPEA2.

### 00:30 · `score`

Uma configuração toca em seis instâncias e três sementes: 18 execuções de 8.000 avaliações, medidas por hipervolume normalizado. [Aponte 14 × 2.] Em cada instância sobra a barra do meio: a mediana abafa o azar. Depois as seis alturas se nivelam: a média dá o mesmo peso às instâncias. Nota desta mixagem: 0,947. Essa escala não é a da campanha.

### 01:00 · `exploracao`

Essa era a configuração de referência. Com ela, são vinte tentativas exploratórias, espalhadas pela grade. [Aponte o xis.] Uma estourou o tempo. E a surpresa: nenhuma superou a referência.

### 01:20 · `tpe`

O TPE separa as boas das demais e tende para onde a razão é alta. [Aponte 0,3.] Simplificamos para uma faixa; o real olha todas em conjunto. Vêm quarenta tentativas. O xis é timeout, as barras são interrupções, e o círculo vazio é sugestão repetida, rejeitada antes de rodar, não poda. No SPEA2, 46 completaram e 14 falharam: dez por tempo, quatro interrompidas. O recorde subiu três degraus.

### 02:00 · `confirmacao`

O comprimento da pista é o orçamento, agora com sementes novas. No VNS, a 32, campeã da busca, lidera em 8 mil. A quinta colocada segue, por uma vaga de diversidade. [Lupa.] Em 20 mil, a 65 passa por centésimos de milésimo, e a 32 para ali. Nos quatro métodos, a recomendada não é a campeã da busca. O SPEA2 começa em 20 mil, com outras sementes, e a 66 vence por pouco.

### 02:40 · `escolhidos`

São estes os valores da campanha: recomendados a 50 mil, rodados com 10 mil. No VNS, o melhor score foi de 0,690 para 0,941 com a nova inicialização. Boas escolhas na grade testada, sem garantia de ótimo.
