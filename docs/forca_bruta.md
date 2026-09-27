# Enumeração exaustiva multiobjetivo

O backend CPU de `src/exact-solutions/exact.py` usa apenas a biblioteca padrão do Python 3.10 ou superior. Não precisa de ambiente virtual. Execute a partir da raiz do repositório:

```powershell
python src/exact-solutions/exact.py data/input/set1/6_2_1439_3_S_1-9.dat --time-limit 10
```

Sem argumento de entrada, o programa percorre todos os arquivos `.dat` de `data/input/set1`. O limite padrão é de **10 segundos por instância**. Use `--time-limit 0` para não limitar o tempo, `--max-decisions N` para parar após N decisões, `--resume` para continuar do checkpoint e `--restart` para reiniciar. `Ctrl+C` salva o estado da instância em execução e encerra o processamento da pasta. Os intervalos são ajustáveis por `--progress-interval` e `--checkpoint-interval`, em segundos.

Cada decisão escolhe, para um job `j`, exatamente uma posição `X[i,j,h,l]=1`: máquina `i`, instante inicial `h` e modo `l`. Os demais valores desse job são zero. Não se materializa o tensor denso de quatro dimensões. O gerador considera somente escolhas cujo processamento cabe no horizonte; o backtracking descarta imediatamente sobreposições de processamento. Uma violação de setup entre dois jobs já escolhidos só é podada se **nenhum job restante couber no intervalo entre eles**. Caso contrário, um job inserido depois ainda pode alterar a adjacência; o setup é então confirmado na folha. Todas as combinações viáveis são avaliadas; não há poda por dominância durante a busca.

O primeiro objetivo é minimizar o término do último job (*makespan*). O segundo é minimizar o custo de energia de processamento: potência `pi[i]` vezes fator `lambda[l]`, vezes os minutos de processamento dentro e fora da ponta, cada parte multiplicada pela tarifa correspondente e dividida por 60 minutos por hora (equivalente a `24/(hl+1)` nas instâncias diárias). O tempo de processamento é `ceil(processing[j][i]/v[l])`. Os valores decimais são lidos como frações exatas; a comparação de custos na fronteira de Pareto usa inteiros escalados. `max_cost` é usado para informar o custo normalizado, sem impor uma restrição adicional. Os índices no JSON começam em zero, como no código.

Para cada instância, `data/output/bruteforce/` contém um relatório `.json` e um `.checkpoint.json`. O relatório traz as soluções não dominadas encontradas até então, seus objetivos, os elementos não nulos de `X` e o cronograma. Uma solução domina outra se for não pior em ambos os objetivos e melhor em pelo menos um; em caso de objetivos iguais, o arquivo conserva um representante. `status=complete` e `pareto_proven=true` aparecem somente depois de esgotada a busca. Caso contrário, a fronteira é **provisória** e pode até estar vazia. O progresso é a fração do produto cartesiano já coberta, inclusive os ramos descartados por sobreposição; isso não representa a fração de soluções viáveis encontradas.

As instâncias oficiais possuem um espaço combinatório enorme. O limite padrão facilita inspecionar progresso e retomar, mas não promete concluir a prova da fronteira. A busca atual usa uma árvore sequencial; uma evolução adicional poderia dividir a árvore por prefixos independentes. A pilha do backtracking fica no checkpoint.

## GPU opcional

Em máquinas com GPU NVIDIA e driver CUDA, instale CuPy no Python usado para executar o script, por exemplo `python -m pip install --user "cupy-cuda12x[ctk]"` para a família CUDA 12. O pacote é opcional: todas as instâncias continuam executáveis com `--backend cpu` em máquinas sem GPU. A [documentação oficial de instalação do CuPy](https://docs.cupy.dev/en/stable/install.html) lista os pacotes para outras versões de CUDA.

```powershell
python src/exact-solutions/exact.py tests/fixtures --backend gpu --batch-size 4096 --time-limit 0 --restart
```

O backtracking, os checkpoints e a fronteira de Pareto continuam na CPU. A GPU recebe lotes de escolhas para o **último job**, verifica sobreposição e setup, e calcula os dois objetivos. `--batch-size` controla quantas folhas vão por lote. CPU e GPU compartilham o formato de checkpoint, então `--resume` pode até trocar de backend. As contas de custo na GPU usam inteiros de 64 bits; o programa recusa esse backend se um custo puder exceder esse limite. Nos cinco casos abaixo, resultados e contagens da GPU foram comparados com a CPU em uma RTX 4060. Em casos minúsculos, o início do CUDA e a transferência de dados podem tornar a GPU mais lenta. Numa execução de três segundos da instância `6_2_1439_3_S_1-9.dat`, esta máquina examinou cerca de 404 mil decisões em CPU e 3,07 milhões em GPU; ambas permaneceram incompletas e sem solução viável nesse prefixo da busca. Isso mede vazão naquele trecho, não aceleração garantida para toda a instância.

## Quanto o backtracking reduz

O total bruto é o produto do número de escolhas individuais de cada job. Um ramo com sobreposição ou com setup comprovadamente irreparável é impossível; o backtracking deixa de visitar todas as combinações descendentes desse ramo. O relatório registra `overlap_pruned_combinations`, `setup_pruned_combinations` e a soma `backtracking_skipped_combinations`. Quando `status=complete`, `backtracking_reduction_percent = 100 × combinações_podadas / total_bruto`. Se a execução foi interrompida, a redução final ainda é desconhecida; a contagem de combinações podadas é apenas a já observada.

| Caso pequeno | Total bruto | Combinações podadas | Redução | Escalonamentos viáveis | Pontos de Pareto |
|---|---:|---:|---:|---:|---:|
| 01: um job e dois modos | 6 | 0 | 0% | 6 | 2 |
| 02: setup assimétrico | 36 | 6 | 16,67% | 16 | 2 |
| 03: máquinas não relacionadas | 49 | 12 | 24,49% | 37 | 1 |
| 04: dois dias e tarifas de ponta | 121 | 39 | 32,23% | 50 | 1 |
| 05: três jobs, máquinas e modos | 3.375 | 1.941 | 57,51% | 658 | 2 |
| 06: setup reparável por inserção | 125 | 77 | 61,60% | 40 | 2 |

As diferenças entre `total bruto − podadas` e `escalonamentos viáveis` vêm de setups inválidos que só são detectados na folha. A poda não elimina nenhum escalonamento viável. A GPU não altera essa redução; somente avalia lotes mais rapidamente.

Teste da enumeração completa e retomada em uma instância pequena:

```powershell
python -m unittest discover -s tests -v
```

Os seis arquivos `.dat` em `tests/fixtures` seguem o mesmo formato das instâncias oficiais. O sexto caso verifica que um setup aparentemente inválido **não** é podado quando um futuro job ainda pode ser inserido entre os dois jobs. O teste compara a fronteira com uma enumeração independente; quando CuPy e uma GPU estão disponíveis, compara também CPU/GPU e a retomada de checkpoint.
