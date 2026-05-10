#!/usr/bin/env python
"""Pretty-print all logs, agent outputs, and debate transcript for a run.

Usage:
    python debug/inspect_run.py <run_id>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEBUG_BUNDLES_DIR, LOGS_DIR, DB_PATH


def inspect(run_id: int) -> None:
    bundle_path = DEBUG_BUNDLES_DIR / f"run_{run_id}_bundle.json"
    if bundle_path.exists():
        bundle = json.loads(bundle_path.read_text())
        print(f"{'='*60}")
        print(f"Run {run_id} — {bundle.get('ticker')} — {bundle.get('fetched_at')}")
        print(f"Data confidence: {bundle.get('data_confidence')}")
        print(f"{'='*60}\n")

        manifest = bundle.get("manifest", {})
        print("=== DATA MANIFEST ===")
        for field, meta in manifest.items():
            status = meta.get("status", "?")
            source = meta.get("source", "?")
            icon = "v" if status == "ok" else ("~" if status == "partial" else "x")
            note = f" — {meta['note']}" if meta.get("note") else ""
            print(f"  {icon} {field}: {status} (from {source}){note}")
        print()
    else:
        print(f"[WARN] Bundle not found: {bundle_path}")

    if DB_PATH.exists():
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        runs = conn.execute("SELECT * FROM analysis_runs WHERE id = ?", (run_id,)).fetchall()
        if runs:
            run = dict(runs[0])
            print("=== RUN RECORD ===")
            for k, v in run.items():
                print(f"  {k}: {v}")
            print()

        agents = conn.execute(
            "SELECT agent, phase, score, data_confidence, status, duration_ms, summary "
            "FROM agent_outputs WHERE run_id = ? ORDER BY phase, agent",
            (run_id,)
        ).fetchall()
        if agents:
            print("=== AGENT OUTPUTS ===")
            for a in agents:
                a = dict(a)
                icon = "v" if a["status"] == "complete" else "x"
                print(f"  {icon} [{a['phase']}] {a['agent']}: score={a['score']} | confidence={a['data_confidence']} | {a['duration_ms']}ms")
                print(f"     {str(a['summary'])[:120]}...")
            print()

        debate = conn.execute(
            "SELECT round_number, bull_conviction, bear_conviction, bull_argument, bear_argument "
            "FROM debate_rounds WHERE run_id = ? ORDER BY round_number",
            (run_id,)
        ).fetchall()
        if debate:
            print("=== DEBATE TRANSCRIPT ===")
            for rnd in debate:
                rnd = dict(rnd)
                g = abs(rnd["bull_conviction"] - rnd["bear_conviction"])
                consensus = "CONSENSUS" if g <= 2 else ""
                print(f"  Round {rnd['round_number']} | Bull: {rnd['bull_conviction']} | Bear: {rnd['bear_conviction']} | Gap: {g} {consensus}")
                print(f"    Bull: {str(rnd['bull_argument'])[:150]}...")
                print(f"    Bear: {str(rnd['bear_argument'])[:150]}...")
            print()
        conn.close()

    log_path = LOGS_DIR / f"run_{run_id}.log"
    if log_path.exists():
        print("=== LOG FILE ===")
        lines = log_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            print(f"  {line}")
    else:
        print(f"[INFO] No log file found at {log_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug/inspect_run.py <run_id>")
        sys.exit(1)
    inspect(int(sys.argv[1]))
