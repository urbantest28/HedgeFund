#!/usr/bin/env python
"""Replay any past run using its saved data bundle. No API calls made.

Usage:
    python debug/replay_run.py <run_id>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEBUG_BUNDLES_DIR
from logger import get_logger

log = get_logger("replay")


def replay(run_id: int) -> None:
    bundle_path = DEBUG_BUNDLES_DIR / f"run_{run_id}_bundle.json"
    if not bundle_path.exists():
        print(f"[ERROR] Bundle not found: {bundle_path}")
        sys.exit(1)

    bundle = json.loads(bundle_path.read_text())
    ticker = bundle.get("ticker", "UNKNOWN")
    print(f"[replay] Replaying run {run_id} for {ticker}")
    print(f"[replay] Original fetch: {bundle.get('fetched_at')}")
    print(f"[replay] Data confidence: {bundle.get('data_confidence')}")
    print()

    manifest = bundle.get("manifest", {})
    print("=== Data Manifest ===")
    for field, meta in manifest.items():
        status = meta.get("status", "?")
        source = meta.get("source", "?")
        icon = "v" if status == "ok" else ("~" if status == "partial" else "x")
        print(f"  {icon} {field}: {status} (from {source})")

    print()
    print("[replay] Pipeline orchestrator not yet available (Plan 3). Bundle loaded successfully.")
    print(f"[replay] Use 'python debug/run_agent.py <agent_name> {run_id}' to run individual agents.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug/replay_run.py <run_id>")
        sys.exit(1)
    replay(int(sys.argv[1]))
