"""Estado persistente da campanha: checkpoint atômico e log de tempos com fsync."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from problem import atomic_json

TERMINAL = {"COMPLETED", "TIMEOUT_PARTIAL", "TIMEOUT_OR_MEM_LIMIT", "INIT_FAILED"}   # não são reexecutados
STATE_VERSION = 1
LIVE_FIELDS = ["session_id", "run_key", "algorithm", "instance", "tier", "run_id", "seed", "status",
               "start_timestamp", "end_timestamp", "wall_seconds", "cpu_seconds", "peak_rss_mib", "peak_rss_delta_mib", "nds", "evaluations", "raw_size",
               "infeasible", "stop_reason", "error"]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def run_key(algorithm, instance, run_id) -> str:
    return f"{algorithm}|{instance}|{run_id:02d}"


class Ledger:
    def __init__(self, output: Path):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.state_path = self.output / "checkpoint_state.json"
        self.live_path = self.output / "execution_times_live.csv"
        self.heartbeat_path = self.output / "heartbeat.json"
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if self.state.get("version") != STATE_VERSION:
                raise ValueError("checkpoint_state.json de versão incompatível")
        else:
            self.state = dict(version=STATE_VERSION, created=now_iso(), runs={}, sessions=[],
                              configurations={}, base_seed=None)
        self.session = None

    # ---------------------------------------------------------------- persistência
    def save(self):
        atomic_json(self.state_path, self.state)

    def append_live(self, record: dict):
        new = not self.live_path.exists()
        with self.live_path.open("a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=LIVE_FIELDS, extrasaction="ignore")
            if new:
                writer.writeheader()
            writer.writerow({k: record.get(k) for k in LIVE_FIELDS})
            stream.flush()
            os.fsync(stream.fileno())

    def heartbeat(self, payload: dict):
        atomic_json(self.heartbeat_path, dict(payload, updated=now_iso()))

    # ---------------------------------------------------------------- sessões
    def start_session(self, argv):
        for old in self.state["sessions"]:   # processo morto sem passar pelo encerramento
            if old["ended"] is None:
                old.update(end_reason="abrupt_exit (execução em curso perdida; tempo dela não registrado)")
        self.session = dict(id=len(self.state["sessions"]) + 1, started=now_iso(), ended=None, argv=list(argv),
                            pid=os.getpid(), valid_wall_s=0.0, interrupted_wall_s=0.0, failed_wall_s=0.0,
                            runs_completed=0, end_reason="running")
        self.state["sessions"].append(self.session)
        self.save()
        return self.session

    def end_session(self, reason):
        if self.session:
            self.session.update(ended=now_iso(), end_reason=reason)
            self.save()

    # ---------------------------------------------------------------- execuções
    def status_of(self, key):
        entry = self.state["runs"].get(key)
        return entry["status"] if entry else "PENDING"

    def record(self, key, record: dict):
        """Grava uma execução terminada/interrompida: CSV (fsync) e checkpoint atômico."""
        entry = self.state["runs"].setdefault(key, dict(attempts=[]))
        attempt = {k: record.get(k) for k in LIVE_FIELDS if k != "run_key"}
        entry["attempts"].append(attempt)
        entry.update(status=record["status"], algorithm=record["algorithm"], instance=record["instance"],
                     run_id=record["run_id"], seed=record["seed"])
        if record["status"] in TERMINAL:
            entry.update(wall_seconds=record["wall_seconds"], cpu_seconds=record["cpu_seconds"],
                         peak_rss_mib=record.get("peak_rss_mib"),
                         result_file=record.get("result_file"))
        wall = record["wall_seconds"] or 0.0
        bucket = ("valid_wall_s" if record["status"] in TERMINAL else
                  "interrupted_wall_s" if record["status"] == "INTERRUPTED_PARTIAL" else "failed_wall_s")
        if self.session:
            self.session[bucket] += wall
            self.session["runs_completed"] += record["status"] in TERMINAL
        self.append_live(dict(record, run_key=key, session_id=self.session["id"] if self.session else None))
        self.save()

    def reset(self, algorithm=None, instance=None):
        removed = [k for k, v in self.state["runs"].items()
                   if (algorithm is None or v["algorithm"] == algorithm) and (instance is None or v["instance"] == instance)]
        archive = self.state.setdefault("reset_history", [])
        for key in removed:
            archive.append(dict(key=key, reset_at=now_iso(), entry=self.state["runs"].pop(key)))
        if algorithm and not any(v["algorithm"] == algorithm for v in self.state["runs"].values()):
            self.state["configurations"].pop(algorithm, None)
        self.save()
        return removed

    # ---------------------------------------------------------------- totais
    def totals(self):
        sessions = self.state["sessions"]
        valid = sum(s["valid_wall_s"] for s in sessions)
        interrupted = sum(s["interrupted_wall_s"] for s in sessions)
        failed = sum(s["failed_wall_s"] for s in sessions)
        return dict(valid_wall_s=valid, interrupted_wall_s=interrupted, failed_wall_s=failed,
                    total_cumulative_wall_time_s=valid + interrupted + failed, sessions=len(sessions))
