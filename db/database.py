import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from config import DB_PATH


class Database:
    def __init__(self, path: Path = DB_PATH):
        self._path = path
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            run_date    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            verdict     TEXT,
            score       INTEGER,
            tier        TEXT,
            entry_low   REAL, entry_high  REAL,
            stop_loss   REAL, target_price REAL,
            thesis_id   INTEGER, thesis_match TEXT,
            contested   INTEGER DEFAULT 0,
            bull_score  INTEGER, bear_score INTEGER,
            report_path TEXT, model_path TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS agent_outputs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL REFERENCES analysis_runs(id),
            agent           TEXT NOT NULL,
            phase           INTEGER NOT NULL,
            score           INTEGER,
            summary         TEXT,
            raw_output      TEXT,
            data_confidence TEXT,
            duration_ms     INTEGER,
            status          TEXT NOT NULL DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS debate_rounds (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL REFERENCES analysis_runs(id),
            round_number    INTEGER NOT NULL,
            bull_argument   TEXT,
            bear_argument   TEXT,
            bull_conviction INTEGER,
            bear_conviction INTEGER
        );
        CREATE TABLE IF NOT EXISTS watchlist (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL REFERENCES analysis_runs(id),
            ticker          TEXT NOT NULL,
            added_date      TEXT NOT NULL,
            score           INTEGER,
            tier            TEXT NOT NULL,
            entry_low       REAL, entry_high REAL,
            stop_loss       REAL, target_price REAL,
            verdict_summary TEXT,
            contested       INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'watching',
            alert_sent      INTEGER DEFAULT 0,
            notes           TEXT
        );
        CREATE TABLE IF NOT EXISTS run_checkpoints (
            run_id          INTEGER PRIMARY KEY REFERENCES analysis_runs(id),
            phase           INTEGER NOT NULL,
            completed_agents TEXT NOT NULL,
            pending_agents  TEXT NOT NULL,
            paused_reason   TEXT NOT NULL,
            missing_fields  TEXT NOT NULL,
            created_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS data_cache (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            data_type   TEXT NOT NULL,
            cache_tier  TEXT NOT NULL,
            source      TEXT NOT NULL,
            file_path   TEXT NOT NULL,
            fetched_at  TEXT NOT NULL,
            expires_at  TEXT,
            UNIQUE(ticker, data_type)
        );
        """)
        self._conn.commit()

    def table_names(self) -> list:
        cur = self._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [r[0] for r in cur.fetchall()]

    def create_run(self, ticker: str, run_date: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO analysis_runs (ticker, run_date) VALUES (?,?)",
            (ticker, run_date)
        )
        self._conn.commit()
        return cur.lastrowid

    def get_run(self, run_id: int):
        cur = self._conn.execute("SELECT * FROM analysis_runs WHERE id=?", (run_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def update_run(self, run_id: int, **kwargs) -> None:
        allowed = {"status", "verdict", "score", "tier", "entry_low", "entry_high",
                   "stop_loss", "target_price", "thesis_id", "thesis_match",
                   "contested", "bull_score", "bear_score", "report_path", "model_path"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self._conn.execute(f"UPDATE analysis_runs SET {sets} WHERE id=?",
                           (*fields.values(), run_id))
        self._conn.commit()

    def save_agent_output(self, run_id: int, agent: str, phase: int,
                          score, summary: str, raw_output: str,
                          data_confidence: str, duration_ms: int, status: str) -> None:
        self._conn.execute("""
            INSERT INTO agent_outputs
            (run_id,agent,phase,score,summary,raw_output,data_confidence,duration_ms,status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (run_id, agent, phase, score, summary, raw_output,
             data_confidence, duration_ms, status))
        self._conn.commit()

    def get_agent_outputs(self, run_id: int) -> list:
        cur = self._conn.execute(
            "SELECT * FROM agent_outputs WHERE run_id=? ORDER BY phase,agent", (run_id,))
        rows = []
        for r in cur.fetchall():
            row = dict(r)
            if isinstance(row.get("raw_output"), str):
                try:
                    row["raw_output"] = json.loads(row["raw_output"])
                except (json.JSONDecodeError, TypeError):
                    row["raw_output"] = {}
            rows.append(row)
        return rows

    def save_debate_round(self, run_id: int, round_number: int,
                          bull_argument: str, bear_argument: str,
                          bull_conviction: int, bear_conviction: int) -> None:
        self._conn.execute("""
            INSERT INTO debate_rounds
            (run_id,round_number,bull_argument,bear_argument,bull_conviction,bear_conviction)
            VALUES (?,?,?,?,?,?)""",
            (run_id, round_number, bull_argument, bear_argument,
             bull_conviction, bear_conviction))
        self._conn.commit()

    def get_debate_rounds(self, run_id: int) -> list:
        cur = self._conn.execute(
            "SELECT * FROM debate_rounds WHERE run_id=? ORDER BY round_number", (run_id,))
        return [dict(r) for r in cur.fetchall()]

    def save_watchlist_entry(self, run_id: int, ticker: str, added_date: str,
                              score: int, tier: str, entry_low: float, entry_high: float,
                              stop_loss: float, target_price: float,
                              verdict_summary: str, contested: int) -> None:
        self._conn.execute("""
            INSERT INTO watchlist
            (run_id,ticker,added_date,score,tier,entry_low,entry_high,
             stop_loss,target_price,verdict_summary,contested)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, ticker, added_date, score, tier, entry_low, entry_high,
             stop_loss, target_price, verdict_summary, contested))
        self._conn.commit()

    def get_watchlist(self, status: str = "watching") -> list:
        cur = self._conn.execute(
            "SELECT * FROM watchlist WHERE status=? ORDER BY added_date DESC", (status,))
        return [dict(r) for r in cur.fetchall()]

    def update_watchlist_status(self, ticker: str, status: str) -> None:
        self._conn.execute(
            "UPDATE watchlist SET status=? WHERE ticker=? AND status='watching'",
            (status, ticker))
        self._conn.commit()

    def mark_alert_sent(self, watchlist_id: int) -> None:
        self._conn.execute(
            "UPDATE watchlist SET alert_sent=1 WHERE id=?", (watchlist_id,))
        self._conn.commit()

    def save_checkpoint(self, run_id: int, phase: int, completed_agents: list,
                        pending_agents: list, paused_reason: str,
                        missing_fields: dict) -> None:
        self._conn.execute("""
            INSERT OR REPLACE INTO run_checkpoints
            (run_id,phase,completed_agents,pending_agents,paused_reason,missing_fields)
            VALUES (?,?,?,?,?,?)""",
            (run_id, phase, json.dumps(completed_agents), json.dumps(pending_agents),
             paused_reason, json.dumps(missing_fields)))
        self._conn.commit()

    def get_checkpoint(self, run_id: int):
        cur = self._conn.execute(
            "SELECT * FROM run_checkpoints WHERE run_id=?", (run_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["completed_agents"] = json.loads(d["completed_agents"])
        d["pending_agents"] = json.loads(d["pending_agents"])
        d["missing_fields"] = json.loads(d["missing_fields"])
        return d

    def upsert_cache_entry(self, ticker: str, data_type: str, cache_tier: str,
                           source: str, file_path: str, expires_at) -> None:
        self._conn.execute("""
            INSERT OR REPLACE INTO data_cache
            (ticker,data_type,cache_tier,source,file_path,fetched_at,expires_at)
            VALUES (?,?,?,?,?,datetime('now'),?)""",
            (ticker, data_type, cache_tier, source, file_path, expires_at))
        self._conn.commit()

    def get_cache_entry(self, ticker: str, data_type: str):
        cur = self._conn.execute(
            "SELECT * FROM data_cache WHERE ticker=? AND data_type=?", (ticker, data_type))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_bundle_snapshot(self, run_id: int) -> dict:
        """Load the persisted bundle JSON snapshot for a run, if present."""
        from config import BASE_DIR
        bundles_dir = (BASE_DIR / "debug" / "bundles").resolve()
        path = (bundles_dir / f"run_{int(run_id)}_bundle.json").resolve()
        # Ensure the resolved path stays inside the bundles directory.
        if not str(path).startswith(str(bundles_dir)):
            return {}
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_pm_output(self, run_id: int) -> dict:
        """Return the parsed raw_output dict from the portfolio_manager agent."""
        rows = self.get_agent_outputs(run_id)
        for r in rows:
            if r.get("agent") == "portfolio_manager":
                raw = r.get("raw_output")
                if isinstance(raw, str):
                    try:
                        return json.loads(raw)
                    except Exception:
                        return {}
                return raw or {}
        return {}

    def close(self) -> None:
        self._conn.close()
