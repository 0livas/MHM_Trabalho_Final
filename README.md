# MHM_Trabalho_Final

Trabalho de otimização multiobjetivo para escalonamento em máquinas paralelas não relacionadas, com modos de operação, setups dependentes da sequência e tarifa de energia variável. O repositório reúne as implementações dos métodos exato, heurístico e meta-heurístico.

O primeiro método disponível é uma enumeração exaustiva por backtracking da variável binária `X[i,j,h,l]`. A documentação de uso, dos objetivos e dos limites práticos está em [docs/forca_bruta.md](docs/forca_bruta.md).

O segundo método exato usa CP-SAT com ε-restrição para provar pontos da fronteira de Pareto. Sua modelagem, execução e comparação com o backtracking estão em [docs/cpsat.md](docs/cpsat.md). O backtracking permanece disponível para comparação e validação em instâncias pequenas.

