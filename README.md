# MHM_Trabalho_Final

Trabalho de otimização multiobjetivo para escalonamento em máquinas paralelas não relacionadas, com modos de operação, setups dependentes da sequência e tarifa de energia variável. O repositório está organizado para reunir métodos exatos, heurísticos e meta-heurísticos; atualmente, os métodos exatos estão implementados.

Os métodos exatos disponíveis são o [solver próprio](src/exact-solutions/custom_exact.py), que combina backtracking, propagação de domínios e podas seguras, e o [modelo CP-SAT](src/exact-solutions/cpsat.py), baseado no OR-Tools. Ambos leem as mesmas instâncias e usam as definições compartilhadas em [problem.py](src/exact-solutions/problem.py). Consulte [docs/custom_exact.md](docs/custom_exact.md) e [docs/cpsat.md](docs/cpsat.md) para execução e detalhes.

A enumeração exaustiva permanece apenas como oráculo em instâncias pequenas de teste. O resultado histórico da execução de força bruta na instância oficial está preservado em `data/baselines/`.
