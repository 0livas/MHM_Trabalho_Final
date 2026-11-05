"""Campanha final UPMSP: menu interativo e CLI retomável.

Exemplos (raiz do repositório, Python 3.12)::

    py -3.12 src/experiments/campaign.py                      # menu interativo
    py -3.12 src/experiments/campaign.py --run                # campanha padrão (sem VNS/VND)
    py -3.12 src/experiments/campaign.py --run -a spea2 moead --tiers small medium
    py -3.12 src/experiments/campaign.py --status
    py -3.12 src/experiments/campaign.py --metrics-only
    py -3.12 src/experiments/campaign.py --reset moead:50_10_1439_5_S_1-9.dat
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.config import (ALGORITHMS, ALGORITHM_BY_ID, default_algorithms, vns_calibrated, DEFAULT_BASE_SEED, DEFAULT_OUTPUT, DEFAULT_RUNS,
                                INSTANCES, TIERS, resolve_configuration, select_instances, require_campaign_output)
from experiments.ledger import Ledger
from experiments.runner import Campaign, _fmt, build_tasks, status_dashboard

DEFAULT_ALGORITHMS = default_algorithms()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--run", action="store_true", help="executa/retoma as execuções selecionadas")
    action.add_argument("--status", action="store_true", help="painel de progresso e ETA")
    action.add_argument("--dry-run", action="store_true", help="lista configuração e execuções sem rodar")
    action.add_argument("--metrics-only", action="store_true", help="recalcula PF*, indicadores e testes")
    action.add_argument("--reset", metavar="ALG[:INSTANCIA]", help="apaga o estado de um algoritmo (e instância)")
    parser.add_argument("-a", "--algorithms", nargs="+", choices=[s.id for s in ALGORITHMS],
                        help=f"padrão: {' '.join(DEFAULT_ALGORITHMS)} (vns_vnd entra quando calibrado)")
    parser.add_argument("--include-vns", action="store_true", help="acrescenta vns_vnd à seleção padrão")
    parser.add_argument("--tiers", nargs="+", default=["all"], choices=[*TIERS, "all"])
    parser.add_argument("--instances", nargs="+", help="nomes .dat do registro (filtra as faixas)")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="replicações por meta-heurística")
    parser.add_argument("--base-seed", type=int, default=DEFAULT_BASE_SEED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--exact-time-limit", type=float, default=3600, help="s por instância; 0 sem limite")
    parser.add_argument("--exact-memory-mb", type=float, default=4096)
    parser.add_argument("--exact-max-jobs", type=int, default=13,
                        help="entradas maiores viram TIMEOUT_OR_MEM_LIMIT sem executar")
    parser.add_argument("--budget", type=int, default=10_000,
                        help="max_evaluations comum às meta-heurísticas; 0 usa o orçamento calibrado")
    parser.add_argument("--mh-timeout", type=float, default=900,
                        help="limite rígido (s) por execução de meta-heurística; 0 sem limite")
    parser.add_argument("--heartbeat", type=float, default=2.0, help="intervalo (s) do heartbeat")
    parser.add_argument("--stop-after", type=int, help="para de forma limpa após N execuções nesta sessão")
    parser.add_argument("--simulate-interrupt-after", type=float, help=argparse.SUPPRESS)
    parser.add_argument("--force-config", action="store_true", help="obsoleto; não permite misturar identidades ou configurações")
    parser.add_argument("--yes", action="store_true", help="não pede confirmação no --reset")
    return parser.parse_args(argv)


def exact_options(args):
    return dict(total_seconds=args.exact_time_limit, memory_limit_mib=args.exact_memory_mb,
                max_jobs=args.exact_max_jobs, grace_seconds=300)


def selection(args):
    algorithms = list(args.algorithms or DEFAULT_ALGORITHMS)
    if args.include_vns and "vns_vnd" not in algorithms:
        algorithms.append("vns_vnd")
    order = [s.id for s in ALGORITHMS]
    return sorted(set(algorithms), key=order.index), select_instances(args.tiers, args.instances)


def print_status(args, algorithms, instances):
    ledger = Ledger(args.output_dir)
    base_seed = ledger.state["base_seed"] or args.base_seed
    rows, eta = status_dashboard(ledger, algorithms, instances, args.runs, base_seed)
    print(f"{'Instância':<34}{'Algoritmo':<11}{'ok':>4}{'t/o':>5}{'init':>5}{'falha':>6}{'interr':>7}"
          f"{'pend':>6}{'média':>13}{'ETA':>14}{'RAM pico':>11}")
    for r in rows:
        print(f"{r['instance']:<34}{r['algorithm']:<11}{r['completed']:>4}{r['timeout']:>5}{r['init_failed']:>5}"
              f"{r['failed']:>6}{r['interrupted']:>7}{r['pending']:>6}"
              f"{_fmt(r['mean_s']) if r['mean_s'] is not None else '—':>13}{_fmt(r['eta_s']) if r['eta_s'] is not None else '?':>14}"
              f"{_ram(r['peak_rss_mib']):>11}")
    totals = ledger.totals()
    print(f"\nPendentes: {sum(r['pending'] + r['interrupted'] + r['failed'] for r in rows)} execuções; "
          f"ETA conhecido: {_fmt(eta)} (grupos sem histórico aparecem como '?').")
    print(f"Tempo acumulado ({totals['sessions']} sessões): válido {_fmt(totals['valid_wall_s'])}, "
          f"interrompido {_fmt(totals['interrupted_wall_s'])}, falhas {_fmt(totals['failed_wall_s'])}, "
          f"total {_fmt(totals['total_cumulative_wall_time_s'])}")
    return rows


def _ram(value):
    return f"{value:.0f} MiB" if value is not None else "—"


def dry_run(args, algorithms, instances):
    for algorithm in algorithms:
        config = resolve_configuration(algorithm, exact_options=exact_options(args), budget=args.budget)
        print(f"{algorithm:<10} {config['parameters']}\n{'':<10} fonte: {config['source']} [{config['status']}]")
    for spec in instances:
        ok = spec.path.exists()
        print(f"  [{spec.tier:<6}] {spec.relative:<42} {'ok' if ok else 'AUSENTE'}")
    tasks = build_tasks(algorithms, instances, args.runs, args.base_seed)
    print(f"{len(tasks)} execuções planejadas; seeds MH = {args.base_seed}+k, k=1..{args.runs}")
    return tasks


def run_metrics(args):
    require_campaign_output(args.output_dir)
    from experiments.metrics import compute
    ledger = Ledger(args.output_dir)
    result = compute(args.output_dir, ledger.state)
    print(f"Métricas: {len(result['per_run'])} execuções, {len(result['references'])} instâncias → "
          f"{args.output_dir / 'metrics'}")
    leaks = {k: len(v["dominance_leaks"]) for k, v in result["references"].items() if v["dominance_leaks"]}
    if leaks:
        print(f"ATENÇÃO: pontos não dominados por PF* exata: {leaks}")
    return result


def do_reset(args, target):
    require_campaign_output(args.output_dir)
    algorithm, _, instance = target.partition(":")
    if algorithm not in ALGORITHM_BY_ID:
        raise SystemExit(f"Algoritmo desconhecido: {algorithm}")
    guard = Campaign(args.output_dir, base_seed=args.base_seed,
                     exact_options=exact_options(args), budget=args.budget)
    guard.lock_configurations([algorithm], save=False)
    ledger = guard.ledger
    if not args.yes and input(f"Apagar estado de {target}? Digite 'sim': ").strip().lower() != "sim":
        print("Cancelado.")
        return []
    removed = ledger.reset(algorithm, instance or None)
    print(f"{len(removed)} execuções voltaram a PENDING (histórico preservado em reset_history).")
    return removed


def run_campaign(args, algorithms, instances, argv):
    campaign = Campaign(args.output_dir, base_seed=args.base_seed, heartbeat_seconds=args.heartbeat,
                        exact_options=exact_options(args), mh_timeout=args.mh_timeout or None, budget=args.budget, force_config=args.force_config)
    campaign.simulate_interrupt_after = args.simulate_interrupt_after
    outcome = campaign.run(algorithms, instances, args.runs, stop_after=args.stop_after, argv=argv)
    if outcome["reason"] == "completed":
        run_metrics(args)
    return outcome


# ------------------------------------------------------------------ menu
def _ask(prompt, default=""):
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def menu(args, argv):
    selected = set(selection(args)[0])
    tiers = list(args.tiers)
    while True:
        print("\n=== Campanha UPMSP multiobjetivo ===")
        print("Algoritmos (número alterna):")
        for i, spec in enumerate(ALGORITHMS, 1):
            mark = "x" if spec.id in selected else " "
            note = "  [Hyperparameters Pending - Not Selected by Default]" if spec.id == "vns_vnd" and not vns_calibrated() else ""
            print(f"  {i}. [{mark}] {spec.label}{note}")
        print(f"Faixas: {' '.join(tiers)}   Replicações MH: {args.runs}   Saída: {args.output_dir}")
        print("  r) Retomar/rodar seleção   s) Painel de status   d) Dry-run   m) Recalcular métricas")
        print("  t) Escolher faixas         n) Nº de replicações  x) Reset algoritmo/instância   q) Sair")
        choice = input("> ").strip().lower()
        algorithms = [s.id for s in ALGORITHMS if s.id in selected]
        args.tiers = tiers
        try:
            instances = select_instances(tiers)
            if choice.isdigit() and 1 <= int(choice) <= len(ALGORITHMS):
                selected ^= {ALGORITHMS[int(choice) - 1].id}
            elif choice == "r":
                run_campaign(args, algorithms, instances, argv)
            elif choice == "s":
                print_status(args, algorithms, instances)
            elif choice == "d":
                dry_run(args, algorithms, instances)
            elif choice == "m":
                run_metrics(args)
            elif choice == "t":
                raw = _ask(f"Faixas ({', '.join(TIERS)}, all)", " ".join(tiers)).split()
                select_instances(raw)
                tiers = raw
            elif choice == "n":
                args.runs = int(_ask("Replicações", str(args.runs)))
            elif choice == "x":
                do_reset(args, _ask("ALG[:INSTANCIA.dat]"))
            elif choice == "q":
                return
        except (ValueError, FileNotFoundError) as error:
            print(f"Erro: {error}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    for stream in (sys.stdout, sys.stderr):   # console cp1252 não derruba a campanha por um caractere
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = parse_args(argv)
    if args.runs < 1:
        raise SystemExit("--runs deve ser >= 1")
    algorithms, instances = selection(args)
    if args.status:
        print_status(args, algorithms, instances)
    elif args.dry_run:
        dry_run(args, algorithms, instances)
    elif args.metrics_only:
        run_metrics(args)
    elif args.reset:
        do_reset(args, args.reset)
    elif args.run:
        run_campaign(args, algorithms, instances, argv)
    else:
        menu(args, argv)


if __name__ == "__main__":
    main()
