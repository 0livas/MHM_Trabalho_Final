# Arquivo local dos resultados do piloto

Por decisão do projeto, os resultados brutos do piloto **não serão publicados
como GitHub Release**. Os arquivos brutos e o pacote compactado são preservados
localmente e ficam fora do Git. Este arquivo descreve apenas a verificação e a
reconstrução local do pacote; não há publicação externa pendente para continuar.

Na raiz do repositório, com os resultados originais presentes:

```bash
python data/output/age/archive_pilot.py build
python data/output/age/archive_pilot.py verify
```

O builder confere os hashes congelados antes de empacotar. Os metadados tar e o
cabeçalho gzip são determinísticos; uma reconstrução na mesma toolchain produz
os mesmos bytes. Um destino existente com conteúdo diferente é recusado. O
builder não executa buscas e não remove nem altera os brutos.

`archive_manifest.json` registra o tamanho e o SHA-256 do pacote;
`archive_inventory.json` lista cada membro de conteúdo com tamanho e hash; e
`archive.sha256` oferece uma verificação simples. O pacote contém uma cópia do
inventário. O pacote e os resultados volumosos permanecem locais e são
explicitamente ignorados pelo Git.

Após clonar, os testes e a execução do solver não dependem do pacote. Para
repetir a análise do piloto, restaure `piloto/runs/` e
`piloto/references.json` a partir do arquivo local, após verificar o hash e o
inventário. Extraia primeiro em diretório temporário e restaure apenas os
arquivos ausentes; não sobreponha snapshots de fontes sem revisão.
