# Congelamento AGE-MOEA e piloto — v1

Configuração experimental congelada em [frozen_config.json](frozen_config.json):

| Parâmetro | Valor |
|---|---:|
| População | 50 |
| Crossover | 0.9 |
| Mutação | 0.3 |
| Orçamento principal | 8000 tentativas completas ao avaliador |
| pymoo | 0.6.2 |

O crossover **foi mantido fixo em 0.9 em todas as células, sem otimização
específica desse parâmetro**. O piloto variou população e mutação. A decisão
usa o critério previamente registrado: rank médio do HV mediano por instância
(1,5), corroborado pelo rank de IGD+ (1,5), com melhor mediana HV em 3/4 entradas.
Três seeds e referências empíricas não demonstram superioridade geral.

O regime continua geracional com último lote eventualmente parcial, duplicatas
permitidas e restrições filtradas nativamente. Toda tentativa inviável também
consome orçamento. Comparações internas usam floats; a frente exportada é
reavaliada e filtrada por objetivos inteiros exatos. Nenhum desses contratos,
operadores ou parâmetros internos foi alterado neste congelamento.

O arquivo congelado é a autoridade para a próxima campanha; os defaults de
`AGEConfig` continuam população 100 e orçamento 10000. É necessário passar
explicitamente população 50, crossover 0.9, mutação 0.3 e orçamento 8000 ao
futuro driver. As seeds finais permanecem reservadas; esta etapa não as executa.

## Parecer e rastreabilidade

O usuário informou release-check independente **aprovado com ressalvas, sem
problemas materiais**. Não foi localizado um relatório separado desse parecer;
o registro distingue essa informação de uma releitura de documento inexistente.
A integridade das evidências e as versões são verificadas nesta preparação.
Ressalvas mantidas: crossover fixo, piloto pequeno, referências empíricas,
seleção por floats, duplicatas e ausência de teste de instalação limpa.
Não foi identificada pendência material nos contratos/evidências verificados.

O piloto original permanece imutável: 72 buscas, 576000 tentativas, seeds
11/29/47, quatro entradas (6 original, 14 derivada, 50 e 250 originais).
`piloto/protocol.json`, `manifest.json`, `audit.json`, `tests.json`, métricas,
relatório e hashes são os registros originais, não reescritos para simular
que o ambiente já estava fixado ou publicado na época do piloto.
`frozen_config.json` liga configuração, fontes, análise e evidências por SHA-256.
O commit definitivo será definido somente após revisão e autorização; não há
hash de commit/tag futuro inventado nestes arquivos.

## Ambiente efetivo

[environment.json](environment.json) captura Python 3.10.12, Linux x86_64/WSL2,
pip e a resolução instalada das dependências do projeto e transitivas ativas.
Pymoo 0.6.2, NumPy 2.2.6 e Numba 0.61.2 coincidem com o ambiente registrado no
protocolo; SciPy 1.15.1 e llvmlite 0.44.0 também estão fixados. As demais versões
são a captura efetiva no congelamento, não uma reconstrução de logs inexistentes.

`requirements.txt` fixa **pymoo==0.6.2**, resolvendo a incompatibilidade com o
runner. SPEA2 e MOEA/D já foram implementados/testados nessa versão. Nenhum
outro intervalo de dependência foi alterado nesta etapa.
[requirements-age-repro.txt](../../../requirements-age-repro.txt) fixa toda a
resolução ativa dos quatro requisitos do projeto, inclusive OR-Tools e
Matplotlib, preservando a possibilidade de executar os métodos existentes.
Nenhum pacote foi instalado ou atualizado nesta preparação.

Em ambiente novo (com Python 3.10.12 já disponibilizado), na raiz do checkout:

```bash
python3.10 -m venv .venv-age-repro
.venv-age-repro/bin/python -m pip install -r requirements-age-repro.txt
.venv-age-repro/bin/python -m pip check
.venv-age-repro/bin/python -m unittest discover -v
```

A instalação limpa ainda não foi executada. O arquivo fixa versões, mas não
contém wheels ou hashes de distribuições; disponibilidade no índice e suporte
à plataforma devem ser verificados. Não se garante igualdade de tempos ou
bytes entre plataformas/toolchains. O ambiente global atual tem uma pendência
alheia ao projeto: `pygobject 3.42.1` requer `pycairo`, ausente. Não é dependência
deste lock e não foi instalado/reparado para ocultar o diagnóstico.

## Arquivamento e Git

Brutos locais e referências são preservados e distribuídos em
`artifacts/age-moea-pilot-v1.tar.gz`, ignorado pelo Git. O pacote também inclui
metadados originais, scripts do piloto, fontes efetivas referenciadas pelo
protocolo, entradas utilizadas, baseline exato de 6 jobs e registros de
congelamento/ambiente. Não inclui resultados da campanha histórica nem caches.
Cada arquivo tem tamanho e SHA-256 no inventário externo e em `INVENTORY.json`
no pacote. Por decisão do projeto, nem o pacote nem os dados brutos serão
publicados como GitHub Release. Consulte [ARCHIVE.md](ARCHIVE.md) para
verificação e reconstrução locais.

Arquivos de implementação, testes, configuração congelada, documentação,
ambiente de reprodução e resultados consolidados do piloto são versionáveis:

- `.gitignore`, `requirements.txt`, `requirements-age-repro.txt`, `README.md`;
- `src/metaheuristics/age.py`, `age_spike.py` e `METAHEURISTICS.md`;
- `tests/test_age.py`, `test_age_spike.py`, `test_age_pilot.py`, `test_age_archive.py`;
- `data/output/age_spike/` (pequenas evidências originais do spike);
- `data/output/age/implementation.md`, `FREEZE.md`, `frozen_config.json`,
  `environment.json`, `archive_pilot.py`, `archive_inventory.json`,
  `archive_manifest.json`, `archive.sha256`, `ARCHIVE.md`,
  `freeze_validation.json`;
- `data/output/age/piloto/`: scripts, relatórios, CSVs consolidados, protocolo,
  emenda/preflight original, manifesto, auditoria, testes e recomendação.

Devem ficar fora do Git: `piloto/runs/`, `piloto/references.json`, `artifacts/`,
ambientes virtuais, caches e logs. A regra de ignore preserva os arquivos locais;
os resultados brutos não são excluídos nem removidos do ambiente de trabalho.
Antes de versionar, conferir `git status`, `git diff --cached --stat` e a ausência
de brutos no índice. A lista acima define o escopo versionável; o pacote e dados
volumosos continuam locais por decisão do projeto.
