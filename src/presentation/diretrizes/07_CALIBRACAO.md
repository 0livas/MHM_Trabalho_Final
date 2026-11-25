# 07 · Calibração: Optuna/TPE e confirmação

## 1. Sua tarefa

Você vai criar, sozinho nesta sessão, a animação **Calibração: Optuna/TPE e confirmação** da apresentação do trabalho. Leia primeiro `src/presentation/diretrizes/00_GUIA_COMUM.md` e siga-o integralmente; depois leia as fontes abaixo. Entregue `anim_calibracao.py`, `trace_calibracao.py`, `data/trace_calibracao.json` e `ROTEIRO_CALIBRACAO.md` em `src/presentation/`, e o player renderizado em `media/calibracao/`. Cenas: `CalibracaoMesa`, `CalibracaoTorneio`. Outras sessões produzem os demais vídeos ao mesmo tempo: não toque em arquivos compartilhados.


**Este deck não executa novas calibrações.** O trace só lê os CSV e JSON abaixo e grava um resumo conferível.

## 2. Fonte da verdade

- `src/hyperparameters_tuning/common.py`, `main.py`, `confirm.py` e os adaptadores `spea2.py`, `moead.py`, `age.py`, `vns_vnd.py`.
- `data/output/hyperparameters_tuning/` com os estudos `age/age_tpe_v6`, `moead/moead_tpe_v6`, `spea2/spea2_tpe_v6_pedro`, `vns_vnd/vns_vnd_tpe_v6` e `vns_vnd/vns_vnd_tpe_v7`: `protocol.json`, `trials.csv`, `best_parameters.json`, `confirmation.csv`, `confirmation.json`.
- `README.md`, seção 5.6.
- Manifestos da campanha: `data/output/experiments/experiment_manifest.json` (SPEA2, MOEA/D, AGE) e `data/output/experiments_vns_new/experiment_manifest.json` (VNS revisto).

## 3. Como funciona aqui

**Fase 1.** Até 60 trials por algoritmo: 20 exploratórios e 40 por TPE multivariado. Cada trial avalia **uma configuração** em 6 instâncias (2 pequenas, 2 médias, 2 grandes) × 3 seeds (11, 29, 47) com 8000 avaliações: 18 execuções. O score é a média, entre instâncias, da mediana entre seeds do HV normalizado por limites tirados apenas da entrada, com referência (1,05; 1,05) dividida por 1,05².

**Fase 2.** Os melhores candidatos distintos são reavaliados nas mesmas instâncias, com seeds novas e orçamentos de 8000, 20000 e 50000, promovendo parte deles a cada etapa. A recomendada é a primeira no maior orçamento.

| Método | Grade | Vencedor do TPE (score, 8000) | Recomendada na confirmação |
|---|---|---|---|
| SPEA2 | população, cruzamento, mutação: 252 | trial 51: 150 / 0,9 / 0,7 (0,9481) | trial 66: **200 / 0,7 / 0,5** |
| MOEA/D | população, vizinhos, acasalamento, cruzamento, mutação: 7560 | trial 41: 300 / 15 / 0,9 / 0,9 / 0,7 (0,9441) | trial 44: **300 / 10 / 0,9 / 0,9 / 0,7** |
| AGE-MOEA | população, cruzamento, mutação: 252 | trial 55: 100 / 1,0 / 0,5 (0,9478) | trial 43: **100 / 0,9 / 0,7** |
| VNS/VND (v7) | partidas, candidatos, shake: 125 | trial 32: 16 / 10 / 1 (0,9408) | trial 65: **16 / 25 / 20** |

## 4. Conceito criativo

**Metáfora: mesa de som e torneio.** Os parâmetros são faixas deslizantes de uma mesa; cada trial é uma **mixagem** cujo volume é o score. O TPE ouve o que soou bem e pende os botões para essa região. Depois as melhores mixagens viram faixas de corrida: o comprimento da pista é o orçamento. Cor por método (`COLORS`), usada apenas nas faixas e pontos.

Neste deck o Gantt abre e fecha, como no quadro-base, mas o centro é a mesa: um plano muda de aparência conforme a configuração muda, como **ilustração** identificada, sem números.

## 5. Roteiro por trecho

### 00:00 · `botoes` (CalibracaoMesa, animação ≈ 12 s)

- **Pergunta:** Quem decide o volume de cada botão?
- **Na tela:** O Gantt do quadro-base encolhe e vira a tela de um osciloscópio. Quatro mesas (VNS, SPEA2, MOEA/D, AGE) se erguem com as faixas reais dos parâmetros e seus degraus.
- **Número real:** Tamanhos 125, 252, 7560 e 252; calculados a partir de `protocol.json` e conferidos com `best_parameters.json`.
- **Texto máximo:** nome dos parâmetros
- **Fala-guia:** Poucos botões já dão milhares de combinações.
- **Transição:** A câmera foca uma mesa.

### 00:30 · `score` (CalibracaoMesa, animação ≈ 15 s)

- **Pergunta:** Como dar nota a uma configuração?
- **Na tela:** Uma mixagem toca em seis instâncias × três seeds: 18 pequenos medidores. Em cada instância, as três barras colapsam na **mediana**; as seis medianas colapsam na média. O ponto do score pula no gráfico.
- **Número real:** Dados de um trial real (`trials/trial_*.json` ou `trials.csv`).
- **Texto máximo:** "mediana · média"
- **Fala-guia:** A mediana abafa o azar; a média dá o mesmo peso às instâncias.
- **Transição:** Vinte mixagens nascem.

### 01:00 · `exploracao` (CalibracaoMesa, animação ≈ 11 s)

- **Pergunta:** Por onde começar sem saber nada?
- **Na tela:** Vinte pontos caem espalhados na mesa, com scores como volume. Marque a primeira sugestão, igual à configuração de referência do protocolo.
- **Número real:** 20 exploratórios (`proposal_source`).
- **Texto máximo:** "20 explorações"
- **Fala-guia:** Ouvir um pouco de tudo antes de concluir.
- **Transição:** Uma névoa surge.

### 01:20 · `tpe` (CalibracaoMesa, animação ≈ 18 s)

- **Pergunta:** Onde tentar agora?
- **Na tela:** Duas nuvens (bons e ruins) em uma faixa; o TPE pende para a razão entre elas. 40 pontos caem na região promissora; ondas laterais mostram duplicatas rejeitadas e um timeout que se apaga. O recorde sobe em degraus.
- **Número real:** Evolução real do melhor score por trial; SPEA2 46 completos e 14 falhas (10 timeout, 4 interrupções).
- **Texto máximo:** "40 por TPE"
- **Fala-guia:** O método aprende o que soa bem.
- **Transição:** Os melhores viram corredores.

### 02:00 · `confirmacao` (CalibracaoTorneio, animação ≈ 20 s)

- **Pergunta:** O melhor treino vence a corrida longa?
- **Na tela:** Pista em três trechos (8.000, 20.000, 50.000). Em cada um os corredores andam com o HV (score), com troca de posição e eliminação real. O vencedor do treino perde a liderança e o recomendado cruza primeiro. SPEA2 começa em 20.000 (sua pista é diferente).
- **Número real:** Rankings reais de `confirmation.json`.
- **Texto máximo:** "8 mil · 20 mil · 50 mil"
- **Fala-guia:** Quem brilha em 8 mil não necessariamente brilha em 50 mil.
- **Transição:** O pódio forma as quatro configurações.

### 02:40 · `escolhidos` (CalibracaoTorneio, animação ≈ 9 s)

- **Pergunta:** O que a campanha recebeu?
- **Na tela:** As quatro faixas se ajustam aos valores recomendados e disparam em direção à linha da campanha, com outra régua: 10.000 avaliações. VNS v6 (0,690) e v7 (0,941) aparecem lado a lado, com a inicialização LPT como a diferença.
- **Número real:** Valores do manifesto; scores v6/v7.
- **Texto máximo:** "recomendadas a 50 mil, rodadas com 10 mil"
- **Fala-guia:** As regras da corrida e da campanha não são iguais, e é bom dizer.
- **Transição:** Quadro-base final.

## 6. Momento uau

**A corrida de orçamentos.** As faixas correm e **trocam de posição** ao passar de 8 mil para 20 mil e 50 mil; o campeão da primeira etapa é ultrapassado em câmera lenta.

## 7. Dados

`trace_calibracao.py` lê os estudos e grava `data/trace_calibracao.json`: grade, trials (número, estado, `proposal_source`, score, parâmetros), a evolução do recorde, a agregação por instância de um trial escolhido (a partir de seu `trials/trial_*.json`) e os rankings, orçamentos e scores de `confirmation.csv`/`confirmation.json`. Guarde hashes dos arquivos lidos. O `--check` recalcula e compara. Não leia nem escreva `study.sqlite3`.

## 8. Armadilhas de fidelidade

- O score da calibração **não** é comparável ao HV da campanha (normalização e referência diferentes).
- `PRUNED` é sugestão duplicada, não poda por desempenho (o protocolo declara `pruning: false`).
- SPEA2: 46 completos e 14 falhas; é o único com falhas. Não chame todas de timeout.
- SPEA2 confirmou a partir de 20.000 e com seeds 101, 103, 107, 109, 113; os outros, a partir de 8.000, com 101–105.
- Em **todos os quatro** o campeão do TPE é diferente do recomendado. Se mostrar só um, não diga que é exceção.
- As recomendações vêm de 50.000 avaliações; a campanha usou 10.000.
- Parte das instâncias da calibração também está na campanha (por exemplo `50_10_1439_5_S_1-9`): não chame de validação independente.
- O status do VNS na campanha aparece como `provisional_inherited_pre_lpt` no manifesto, embora os valores coincidam com os da recomendação v7. Mencione apenas se a fala entrar em detalhe.
- v6 → v7 do VNS não isola apenas a inicialização: diga "com a nova inicialização", não "por causa dela".
- Não chame configuração de ótima.

## 9. Aceite específico

Além do aceite comum do guia:

- [ ] Todos os números do JSON conferem com os arquivos originais.
- [ ] Mediana e média são distinguidas por movimento.
- [ ] A troca de posição na confirmação é real e em escala.
- [ ] Estados PRUNED, FAIL e COMPLETE são diferentes na tela.

Render final: `.venv/bin/python src/presentation/apresentar.py --deck calibracao --render --quality m`
