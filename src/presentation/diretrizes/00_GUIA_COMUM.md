# Guia comum das animações da metodologia

Leia este guia inteiro antes do arquivo da sua animação. Ele vale para todas as sessões, que trabalham em paralelo na mesma pasta.

## 1. Contexto

O projeto escalona tarefas em máquinas paralelas não relacionadas, com modos de operação, setups dependentes da sequência e tarifa de ponta, minimizando `Cmax` (término da última tarefa) e `TEC` (custo total de energia). A referência é Rego et al. (2022). A apresentação segue o artigo `documentacao/main.tex`.

A introdução animada já existe e define o padrão: `introducao.py` (cenas), `fabrica.py` (componentes), `visual.py` (paleta e texto), `cenario.py` (dados), todos em `src/presentation/`. **Assista a ela ou renderize-a antes de começar**: o público acabou de vê-la e já conhece máquinas, modos, setup, ponta, espera e o plano Cmax × TEC. Não explique isso de novo.

```bash
.venv/bin/python src/presentation/apresentar.py --deck introducao --render --quality l
```

## 2. Trabalho em paralelo

| Deck | Diretriz | Cenas (nomes obrigatórios) | Fala |
|---|---|---|---|
| `exato` | `01_METODO_EXATO.md` | `ExatoEstados`, `ExatoEscada` | 3:00 |
| `heuristica` | `02_HEURISTICA.md` | `HeuristicaConstrutiva`, `HeuristicaOciosidade` | 3:00 |
| `vns` | `03_VNS_VND.md` | `VnsPartida`, `VnsDescida`, `VnsBusca` | 3:30 |
| `spea2` | `04_SPEA2.md` | `Spea2Arena`, `Spea2Operadores`, `Spea2Busca` | 3:30 |
| `moead` | `05_MOEAD.md` | `MoeadLeque`, `MoeadVizinhos`, `MoeadBusca` | 3:00 |
| `age` | `06_AGE_MOEA.md` | `AgeCamadas`, `AgeGeometria`, `AgeBusca` | 3:00 |
| `calibracao` | `07_CALIBRACAO.md` | `CalibracaoMesa`, `CalibracaoTorneio` | 3:00 |

Cada sessão cria **somente** estes arquivos, em `src/presentation/`:

- `anim_<deck>.py`: as cenas. O prefixo evita que `spea2.py`, por exemplo, seja importado no lugar do algoritmo.
- `trace_<deck>.py` e `data/trace_<deck>.json`: captura dos dados reais.
- `ROTEIRO_<DECK>.md`: a fala, com o deck em maiúsculas.
- `media/<deck>/`: saída do render, ignorada pelo Git.

Não edite `fabrica.py`, `visual.py`, `introducao.py`, `apresentar.py`, `player.html`, `README.md`, `.gitignore`, as diretrizes, nem os algoritmos e parâmetros em `src/`. Os decks já estão registrados em `apresentar.py`. Se faltar um componente, crie-o no seu `anim_<deck>.py`. Não faça commit e não use worktree: parte da base pode não estar commitada. Não apague saídas de outros decks.

## 3. Linguagem visual herdada

- Estenda `CenaContinua` (`fabrica.py`). Use `abrir`, `beat`, `base`, `hold`. Defina `chapter`, `number` e `total` (número de cenas do deck). O rodapé padrão cita a instância didática; se a cena mostrar outros dados, troque o texto dele.
- Reutilize `Eixo`, `EIXO`, `maquina`, `curva_tarifa`, `relogio`, `medidor`, `rotulo`, `estado`, `plano`, `custo_ate`, `CORES` e, de `visual.py`, `axes`, `dots`, `staircase`, `formula`, `text`, `left`, `pos`, `pt`.
- Instância `data/didatica.dat`: T1–T8, M1–M3, ponta 18h–21h. A fronteira exata está em `data/didatica.json`: 8 pontos, de (12 h; $ 812,4) a (20 h; $ 478,8).
- Significados fixos: cor = tarefa; largura = duração; **altura da barra = potência do modo**; bloco cinza fino = setup; contorno amarelo = espera; faixa coral = ponta; dourado = fronteira de referência; cinza = descartado.
- Cor de cada método: `visual.COLORS` (`exact_dp`, `construtiva`, `ociosidade`, `vns_vnd`, `spea2`, `moead`, `age`). Use-a nas partículas, trilhas e feixes do método, nunca para pintar tarefas.
- **Quadro-base** (primeiro e último quadro de cada deck, para emendar os vídeos): `base()` com o Gantt do plano de 15 h (`plano(15)`) à esquerda e o plano Cmax × TEC à direita, `axes` com `center=(5.02, .35)`, `width=2.75`, `height=2.7`. No último quadro, o Gantt mostra uma solução encontrada pelo método e o plano mostra a frente dele sobre a exata esmaecida. Antes do título, o primeiro quadro tem só o ponto do plano de 15 h.
- Escolha os limites dos eixos pelos dados do trace. Nenhum ponto pode ser cortado em silêncio.

## 4. Coreografia comum dos operadores

O público deve reconhecer o mesmo movimento em todos os vídeos.

| Operador | Movimento |
|---|---|
| Trocar (swap) | As duas barras saem da faixa, cruzam em arcos opostos e encaixam. Setups e tarefas seguintes se reacomodam depois. |
| Realocar | A barra salta para outra faixa; a lacuna fecha e as vizinhas do destino abrem espaço. A largura muda no ar, porque a duração depende da máquina. |
| Inserir | A barra sobe, desliza por cima das vizinhas, que correm para o lado, e desce. |
| Modo | A barra respira: mais baixa e larga (econômico) ou mais alta e estreita (rápido). |
| Espera | Um elástico amarelo estica entre o setup e a barra. |
| Inviável | O Gantt treme, a barra cruza a linha do horizonte, racha e some. O contador de avaliações sobe mesmo assim. |
| Aceito | Pulso verde na barra; o ponto salta no plano e deixa rastro. |

Toda mudança no Gantt deve mover o ponto correspondente **no mesmo instante**. Tarefas posteriores à alterada se deslocam de verdade, com os inícios reavaliados. Anime em três tempos: antecipação (0,3 s), ação (0,8–1,2 s), consequência (setups, vizinhas e ponto, 0,6 s).

## 5. Direção criativa

1. **Pergunta antes da resposta.** Cada trecho abre com uma tensão visível, e a resposta é um movimento.
2. **Mostre, depois nomeie.** O termo técnico aparece quando o público já viu o que ele faz.
3. **Uma metáfora por método**, mantida do início ao fim. Ela explica o mecanismo; se não explicar, corte.
4. **Um foco por quadro.** Esmaeça o resto para 15–25%.
5. **Ritmo contrastante.** Câmera lenta na primeira ocorrência do mecanismo, normal na segunda, e dezenas de repetições em poucos segundos na terceira. Contador de avaliações sempre visível na aceleração.
6. **Silêncio.** Pare 0,5–1 s depois de um evento importante.
7. **Continuidade.** Objetos se transformam (`Transform`, `ReplacementTransform`, `ValueTracker`); não somem para reaparecer. Um número que o público viu nascer deve viajar até onde será usado.
8. **Câmera com propósito.** Para zoom, amplie um `VGroup` ou use uma câmera móvel numa classe própria; volte sempre à visão geral.
9. **Pouco texto.** No máximo cerca de 12 palavras por quadro além de título, rótulos e números. A explicação vai na fala.
10. **Surpresa.** Pelo menos um momento em que o palpite óbvio do público falha.

Proibido: listas de tópicos, trecho feito só de `FadeIn` de texto, pseudocódigo corrido, fórmula sem objeto em movimento ligado a cada termo, efeito que não represente nada.

**Teste do som desligado:** alguém que assista sem narração deve conseguir dizer o que o método faz. **Teste da foto:** todo trecho deve ter um quadro que, congelado, explique a ideia.

## 6. Dados reais

- `trace_<deck>.py` executa o código do projeto **sem alterar arquivos** e grava o JSON. Instrumente em memória: subclasses que chamam `super()`, substituição de atributos do módulo dentro do processo de captura, ou `sys.settrace`, como em `trace_vns.py`. A instrumentação não pode consumir números aleatórios.
- Compare a execução instrumentada com uma normal de mesma seed: as frentes devem ser idênticas.
- Cada escalonamento exibido é reavaliado por `evaluate_schedule` e salvo com máquina, tarefa, modo, setup, espera, início, término, Cmax e TEC. `plano()` em `cenario.py` mostra como montar os blocos, mas recebe linhas de resultado; para representações nativas use `evaluate_schedule(...).operations`.
- As cenas só leem o JSON. Nenhum resultado é digitado na cena ou na fala sem constar do JSON.
- Inclua `--check`, que recalcula e compara. Registre seed, parâmetros e versões no JSON.
- Pode variar a seed para achar um evento didático (por exemplo, uma troca que domina o plano atual). Guarde a seed, mostre-a no rodapé e não apresente o caso como típico.
- A demonstração usa população pequena (12–30) e poucas avaliações. Identifique-a como **demonstração**. Os parâmetros da campanha aparecem separados e rotulados como **campanha**.
- Não compare a qualidade dos métodos a partir da instância didática: ela serve para explicar.

Início de um trace, executado da raiz:

```python
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]                  # src/
from problem import read_instance, energy_scale
from schedule import evaluate_schedule
from metaheuristics import spea2                   # sempre pelo pacote
instance = read_instance(HERE / "data" / "didatica.dat")
```

## 7. Roteiro

`ROTEIRO_<DECK>.md` usa exatamente `### MM:SS · \`trecho\`` antes de cada fala. Os trechos vêm na ordem das seções renderizadas e com os nomes dados na diretriz. A primeira marca é `00:00`, elas são crescentes e cada animação dura menos que o intervalo até a próxima (o launcher confere). Planeje animação em 50–75% do tempo de fala. Calcule cerca de 130 palavras por minuto, em português falado, com indicações `[entre colchetes]` do que apontar.

## 8. Lições técnicas

- Manim 0.22.1 em `.venv`. Não há LaTeX: use `formula()` (MathText) e `rotulo()`. `DecimalNumber`, `Tex` e `MathTex` falham.
- Para números que mudam, use `always_redraw` com `rotulo` e valores arredondados.
- `hold()` falha se algo sair de |x| ≤ 6,9 ou −3,91 ≤ y ≤ 3,94. Chame-o ao fim de cada trecho.
- `ValueTracker` guarda o valor na coordenada x; o `hold` de `CenaContinua` já o remove. Recrie a animação pelo mesmo objeto depois.
- Não acrescente filhos a um `VGroup` que já está na cena: eles podem sobrar após `FadeOut`. Use um grupo separado.
- Objeto com updater não deve sofrer `Transform`; troque-o antes por uma cópia com `clear_updaters()`.
- `Transform` entre textos de tamanhos diferentes embaralha letras no meio. Prefira sair/entrar rápido ou um contador.
- Remova nomes não usados das importações, mas rode antes de confiar.
- Para muitas partículas, use um único `VGroup` de `Dot` e reduza `run_time`; evite centenas de updaters.
- Uma cena começa no quadro final da anterior. Faça uma função construtora usada pelas duas.

## 9. Render e revisão

```bash
.venv/bin/python src/presentation/trace_<deck>.py
.venv/bin/python src/presentation/trace_<deck>.py --check
.venv/bin/python -m manim -ql --save_sections --media_dir /tmp/<deck> --progress_bar none -v WARNING src/presentation/anim_<deck>.py <Cena>
.venv/bin/python src/presentation/apresentar.py --deck <deck> --render --quality m
```

Faça no mínimo duas rodadas de revisão visual. Gere uma folha de contato e **olhe as imagens**: sobreposição, texto cortado, restos do trecho anterior, rótulo desatualizado durante transições.

```python
# folha.py saida.png N video...   (N quadros por vídeo)
import av, sys
from PIL import Image
out, n, frames = sys.argv[1], int(sys.argv[2]), []
for video in sys.argv[3:]:
    all_ = list(av.open(video).decode(video=0))
    frames += [all_[round((len(all_) - 1) * (k + 1) / n)].to_image().resize((640, 360)) for k in range(n)]
sheet = Image.new("RGB", (1920, 360 * ((len(frames) + 2) // 3)))
for i, frame in enumerate(frames):
    sheet.paste(frame, (640 * (i % 3), 360 * (i // 3)))
sheet.save(out)
```

## 10. Aceite comum

- [ ] Só os arquivos exclusivos do deck foram criados (`git status`).
- [ ] `--check` passa e a execução instrumentada é idêntica à normal.
- [ ] Render em 720p e player sem erro; nomes de cenas e trechos conferem.
- [ ] Todo número na tela e na fala está no JSON ou nos arquivos citados.
- [ ] Nenhuma armadilha de fidelidade da diretriz foi cometida.
- [ ] Nenhum trecho parece slide; há um momento memorável e testes de som e foto passam.
- [ ] Primeiro e último quadros seguem o quadro-base.
- [ ] Relate o que não foi verificado.
