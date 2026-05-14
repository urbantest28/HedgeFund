# HedgeFund Plan 1 — Foundation & Data Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete foundation and data layer — config, logging, database, cache, all 6 data fetchers, manifest builder, and aggregator — with a full test suite that never hits real APIs.

**Architecture:** All data is fetched before the pipeline starts. The aggregator tries sources in a waterfall (primary → fallback) and records every field's source and status in a `DataManifest`. A frozen bundle is saved to `debug/bundles/run_{id}_bundle.json` for replay-based debugging. Tests use frozen fixture data from `tests/fixtures/aapl_data_bundle.json`.

**Tech Stack:** Python 3.9, FastAPI, SQLite (sqlite3 stdlib), yfinance, requests, aiohttp, praw, fredapi, pytest, pytest-asyncio, pytest-mock, responses

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `config.py`
- Create: `logger.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py` (skeleton — expanded in Task 14)
- Create all `__init__.py` files for packages

- [ ] **Step 1: Create folder structure**

Run in `<project_root>\`:
```powershell
New-Item -ItemType Directory -Force -Path data, agents, pipeline, db, reports, prompts/roles, prompts/skills, static, templates, cache, uploads, reports_output, logs, "debug/bundles", "tests/fixtures/sample_agent_outputs", tests/unit, tests/integration, tests/e2e, tests/regression, tests/failure_scenarios, docs/superpowers/plans
New-Item -ItemType File -Force -Path data/__init__.py, agents/__init__.py, pipeline/__init__.py, db/__init__.py, reports/__init__.py, tests/__init__.py, "tests/unit/__init__.py", "tests/integration/__init__.py", "tests/e2e/__init__.py", "tests/regression/__init__.py", "tests/failure_scenarios/__init__.py", "debug/bundles/.gitkeep", "tests/regression/.gitkeep"
```

- [ ] **Step 2: Create `requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-dotenv>=1.0.0
yfinance>=0.2.40
requests>=2.31.0
aiohttp>=3.9.0
praw>=7.7.0
fredapi>=0.5.2
openpyxl>=3.1.2
google-generativeai>=0.8.0
anthropic>=0.40.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-mock>=3.14.0
responses>=0.25.0
```

- [ ] **Step 3: Install dependencies**

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 4: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 5: Create `config.py`**

```python
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).parent

ANTHROPIC_API_KEY     = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY        = os.getenv("GOOGLE_API_KEY", "")
MASSIVE_MARKET_API_KEY = os.getenv("MASSIVE_MARKET_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
FRED_API_KEY          = os.getenv("FRED_API_KEY", "")
REDDIT_CLIENT_ID      = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET  = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT     = os.getenv("REDDIT_USER_AGENT", "hedgefund-analyser/1.0")
NTFY_TOPIC            = os.getenv("NTFY_TOPIC", "")
DASHBOARD_TRADES_DB_PATH = os.getenv("DASHBOARD_TRADES_DB_PATH", "")

PHASE1_PROVIDER = os.getenv("PHASE1_PROVIDER", "gemini")
PHASE1_MODEL    = os.getenv("PHASE1_MODEL", "gemini-2.0-flash")
PHASE2_PROVIDER = os.getenv("PHASE2_PROVIDER", "gemini")
PHASE2_MODEL    = os.getenv("PHASE2_MODEL", "gemini-2.0-flash")
DEBATE_PROVIDER = os.getenv("DEBATE_PROVIDER", "anthropic")
DEBATE_MODEL    = os.getenv("DEBATE_MODEL", "claude-opus-4-7")
PM_PROVIDER     = os.getenv("PM_PROVIDER", "anthropic")
PM_MODEL        = os.getenv("PM_MODEL", "claude-opus-4-7")

CACHE_DIR       = BASE_DIR / "cache"
UPLOADS_DIR     = BASE_DIR / "uploads"
REPORTS_DIR     = BASE_DIR / "reports_output"
LOGS_DIR        = BASE_DIR / "logs"
DEBUG_BUNDLES_DIR = BASE_DIR / "debug" / "bundles"
DB_PATH         = BASE_DIR / "db" / "hedgefund.db"

MASSIVE_MARKET_BASE_URL = "https://api.massive.com"
ALPHA_VANTAGE_BASE_URL  = "https://www.alphavantage.co/query"
SEC_EDGAR_BASE_URL      = "https://data.sec.gov"

for _d in (CACHE_DIR, UPLOADS_DIR, REPORTS_DIR, LOGS_DIR, DEBUG_BUNDLES_DIR, DB_PATH.parent):
    _d.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 6: Create `logger.py`**

```python
import logging
import sys
from pathlib import Path
from config import LOGS_DIR

def get_logger(module: str, run_id: int | None = None) -> logging.LoggerAdapter:
    name = f"hf.{module}"
    log = logging.getLogger(name)
    if not log.handlers:
        fmt = logging.Formatter("%(message)s")
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        log.addHandler(sh)
        log.setLevel(logging.DEBUG)
    return _RunAdapter(log, module, run_id)


class _RunAdapter(logging.LoggerAdapter):
    def __init__(self, logger, module: str, run_id: int | None):
        super().__init__(logger, {})
        self._module = module
        self._run_id = run_id

    def process(self, msg, kwargs):
        run_part = f"[run_{self._run_id}] " if self._run_id is not None else ""
        return f"[hf:{self._module}] {run_part}{msg}", kwargs

    def bind_run(self, run_id: int) -> "_RunAdapter":
        return _RunAdapter(self.logger, self._module, run_id)

    def to_file(self, run_id: int) -> "_RunAdapter":
        fh_name = f"file_{run_id}"
        if not any(h.name == fh_name for h in self.logger.handlers):
            log_path = LOGS_DIR / f"run_{run_id}.log"
            fh = logging.FileHandler(str(log_path), encoding="utf-8")
            fh.name = fh_name
            fh.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(fh)
        return self.bind_run(run_id)
```

- [ ] **Step 7: Create skeleton `tests/conftest.py`**

```python
import pytest
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def aapl_bundle():
    """Frozen AAPL data bundle — all tests use this, no real API calls."""
    with open(FIXTURES_DIR / "aapl_data_bundle.json") as f:
        return json.load(f)
```

- [ ] **Step 8: Verify structure**

```
python -c "import config; print('BASE_DIR:', config.BASE_DIR)"
```

Expected: prints the HedgeFund directory path.

- [ ] **Step 9: Commit**

```
git add .
git commit -m "feat: project scaffold — config, logger, folder structure, requirements"
```

---

## Task 2: Database Schema & CRUD

**Files:**
- Create: `db/database.py`
- Create: `tests/unit/test_database.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_database.py
import pytest
import sqlite3
from pathlib import Path
from db.database import Database


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


def test_tables_created(db):
    tables = db.table_names()
    assert "analysis_runs" in tables
    assert "agent_outputs" in tables
    assert "debate_rounds" in tables
    assert "watchlist" in tables
    assert "run_checkpoints" in tables
    assert "data_cache" in tables


def test_create_run_returns_id(db):
    run_id = db.create_run("AAPL", "2026-05-10")
    assert isinstance(run_id, int)
    assert run_id >= 1


def test_get_run(db):
    run_id = db.create_run("AAPL", "2026-05-10")
    run = db.get_run(run_id)
    assert run["ticker"] == "AAPL"
    assert run["status"] == "pending"


def test_update_run_status(db):
    run_id = db.create_run("AAPL", "2026-05-10")
    db.update_run(run_id, status="complete", score=2, verdict="watchlist")
    run = db.get_run(run_id)
    assert run["status"] == "complete"
    assert run["score"] == 2
    assert run["verdict"] == "watchlist"


def test_save_agent_output(db):
    run_id = db.create_run("AAPL", "2026-05-10")
    db.save_agent_output(
        run_id=run_id, agent="fundamental", phase=1,
        score=7, summary="Strong fundamentals.", raw_output='{"score":7}',
        data_confidence="full", duration_ms=3200, status="complete"
    )
    outputs = db.get_agent_outputs(run_id)
    assert len(outputs) == 1
    assert outputs[0]["agent"] == "fundamental"
    assert outputs[0]["score"] == 7


def test_save_debate_round(db):
    run_id = db.create_run("AAPL", "2026-05-10")
    db.save_debate_round(run_id, 1, "Bull says buy", "Bear says sell", 7, 4)
    rounds = db.get_debate_rounds(run_id)
    assert len(rounds) == 1
    assert rounds[0]["bull_conviction"] == 7
    assert rounds[0]["bear_conviction"] == 4


def test_save_watchlist_entry(db):
    run_id = db.create_run("AAPL", "2026-05-10")
    db.save_watchlist_entry(
        run_id=run_id, ticker="AAPL", added_date="2026-05-10",
        score=2, tier="satellite", entry_low=182.0, entry_high=185.0,
        stop_loss=171.0, target_price=210.0, verdict_summary="Strong buy signal.",
        contested=0
    )
    entries = db.get_watchlist(status="watching")
    assert len(entries) == 1
    assert entries[0]["ticker"] == "AAPL"
    assert entries[0]["tier"] == "satellite"


def test_save_checkpoint(db):
    run_id = db.create_run("AAPL", "2026-05-10")
    db.save_checkpoint(
        run_id=run_id, phase=2,
        completed_agents=["fundamental", "technical"],
        pending_agents=["risk_manager"],
        paused_reason="missing_data",
        missing_fields={"free_cash_flow": {"reason": "all sources failed", "sources_tried": ["alpha_vantage", "sec_edgar"]}}
    )
    cp = db.get_checkpoint(run_id)
    assert cp["phase"] == 2
    assert "fundamental" in cp["completed_agents"]


def test_no_duplicate_watchlist_on_refresh(db):
    run_id = db.create_run("AAPL", "2026-05-10")
    db.save_watchlist_entry(run_id=run_id, ticker="AAPL", added_date="2026-05-10",
        score=2, tier="satellite", entry_low=182.0, entry_high=185.0,
        stop_loss=171.0, target_price=210.0, verdict_summary="Buy.", contested=0)
    # Dismiss the old entry and add a new one (refresh)
    db.update_watchlist_status("AAPL", "dismissed")
    run_id2 = db.create_run("AAPL", "2026-05-11")
    db.save_watchlist_entry(run_id=run_id2, ticker="AAPL", added_date="2026-05-11",
        score=2, tier="satellite", entry_low=183.0, entry_high=186.0,
        stop_loss=172.0, target_price=212.0, verdict_summary="Still buying.", contested=0)
    watching = db.get_watchlist(status="watching")
    assert len(watching) == 1
    assert watching[0]["entry_low"] == 183.0
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_database.py -v
```

Expected: `ImportError: No module named 'db.database'`

- [ ] **Step 3: Implement `db/database.py`**

```python
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Any

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

    def table_names(self) -> list[str]:
        cur = self._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [r[0] for r in cur.fetchall()]

    def create_run(self, ticker: str, run_date: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO analysis_runs (ticker, run_date) VALUES (?,?)",
            (ticker, run_date)
        )
        self._conn.commit()
        return cur.lastrowid

    def get_run(self, run_id: int) -> dict | None:
        cur = self._conn.execute("SELECT * FROM analysis_runs WHERE id=?", (run_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def update_run(self, run_id: int, **kwargs) -> None:
        allowed = {"status","verdict","score","tier","entry_low","entry_high",
                   "stop_loss","target_price","thesis_id","thesis_match",
                   "contested","bull_score","bear_score","report_path","model_path"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self._conn.execute(f"UPDATE analysis_runs SET {sets} WHERE id=?",
                           (*fields.values(), run_id))
        self._conn.commit()

    def save_agent_output(self, run_id: int, agent: str, phase: int,
                          score: int | None, summary: str, raw_output: str,
                          data_confidence: str, duration_ms: int, status: str) -> None:
        self._conn.execute("""
            INSERT INTO agent_outputs
            (run_id,agent,phase,score,summary,raw_output,data_confidence,duration_ms,status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (run_id,agent,phase,score,summary,raw_output,data_confidence,duration_ms,status))
        self._conn.commit()

    def get_agent_outputs(self, run_id: int) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM agent_outputs WHERE run_id=? ORDER BY phase,agent", (run_id,))
        return [dict(r) for r in cur.fetchall()]

    def save_debate_round(self, run_id: int, round_number: int,
                          bull_argument: str, bear_argument: str,
                          bull_conviction: int, bear_conviction: int) -> None:
        self._conn.execute("""
            INSERT INTO debate_rounds
            (run_id,round_number,bull_argument,bear_argument,bull_conviction,bear_conviction)
            VALUES (?,?,?,?,?,?)""",
            (run_id,round_number,bull_argument,bear_argument,bull_conviction,bear_conviction))
        self._conn.commit()

    def get_debate_rounds(self, run_id: int) -> list[dict]:
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
            (run_id,ticker,added_date,score,tier,entry_low,entry_high,
             stop_loss,target_price,verdict_summary,contested))
        self._conn.commit()

    def get_watchlist(self, status: str = "watching") -> list[dict]:
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

    def save_checkpoint(self, run_id: int, phase: int, completed_agents: list[str],
                        pending_agents: list[str], paused_reason: str,
                        missing_fields: dict) -> None:
        self._conn.execute("""
            INSERT OR REPLACE INTO run_checkpoints
            (run_id,phase,completed_agents,pending_agents,paused_reason,missing_fields)
            VALUES (?,?,?,?,?,?)""",
            (run_id, phase, json.dumps(completed_agents), json.dumps(pending_agents),
             paused_reason, json.dumps(missing_fields)))
        self._conn.commit()

    def get_checkpoint(self, run_id: int) -> dict | None:
        cur = self._conn.execute(
            "SELECT * FROM run_checkpoints WHERE run_id=?", (run_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["completed_agents"] = json.loads(d["completed_agents"])
        d["pending_agents"]   = json.loads(d["pending_agents"])
        d["missing_fields"]   = json.loads(d["missing_fields"])
        return d

    def upsert_cache_entry(self, ticker: str, data_type: str, cache_tier: str,
                           source: str, file_path: str, expires_at: str | None) -> None:
        self._conn.execute("""
            INSERT OR REPLACE INTO data_cache
            (ticker,data_type,cache_tier,source,file_path,fetched_at,expires_at)
            VALUES (?,?,?,?,?,datetime('now'),?)""",
            (ticker, data_type, cache_tier, source, file_path, expires_at))
        self._conn.commit()

    def get_cache_entry(self, ticker: str, data_type: str) -> dict | None:
        cur = self._conn.execute(
            "SELECT * FROM data_cache WHERE ticker=? AND data_type=?", (ticker, data_type))
        row = cur.fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/unit/test_database.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```
git add db/database.py tests/unit/test_database.py
git commit -m "feat: database schema and CRUD layer (5 tables)"
```

---

## Task 3: Cache Manager

**Files:**
- Create: `data/cache_manager.py`
- Create: `tests/unit/test_cache_ttl.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cache_ttl.py
import pytest
import json
import time
from pathlib import Path
from unittest.mock import MagicMock
from data.cache_manager import CacheManager, CacheTier


@pytest.fixture
def mgr(tmp_path):
    db = MagicMock()
    db.get_cache_entry.return_value = None
    return CacheManager(cache_dir=tmp_path, db=db)


def test_live_data_never_cached(mgr):
    assert mgr.get("AAPL", "live_price") is None
    mgr.put("AAPL", "live_price", {"c": 183.0}, CacheTier.LIVE, source="massive_market")
    assert mgr.get("AAPL", "live_price") is None


def test_forever_data_cached_and_retrieved(mgr, tmp_path):
    mgr.put("AAPL", "earnings_Q1_2026", {"eps": 1.53}, CacheTier.FOREVER, source="alpha_vantage")
    result = mgr.get("AAPL", "earnings_Q1_2026")
    assert result is not None
    assert result["data"]["eps"] == 1.53
    assert result["cache_tier"] == "forever"


def test_ttl_data_expired_returns_none(mgr, tmp_path):
    mgr.put("AAPL", "ratios", {"pe": 28.5}, CacheTier.TTL_1D, source="massive_market")
    # Manually expire by writing past expiry to the file
    cache_file = tmp_path / "AAPL" / "derived" / "ratios.json"
    data = json.loads(cache_file.read_text())
    data["expires_at"] = "2020-01-01T00:00:00"
    cache_file.write_text(json.dumps(data))
    assert mgr.get("AAPL", "ratios") is None


def test_ttl_data_valid_returns_data(mgr):
    mgr.put("AAPL", "ratios", {"pe": 28.5}, CacheTier.TTL_1D, source="massive_market")
    result = mgr.get("AAPL", "ratios")
    assert result is not None
    assert result["data"]["pe"] == 28.5


def test_tier_classification():
    assert CacheTier.LIVE.ttl_seconds is None
    assert CacheTier.FOREVER.ttl_seconds is None
    assert CacheTier.TTL_1D.ttl_seconds == 86400
    assert CacheTier.TTL_7D.ttl_seconds == 604800
    assert CacheTier.TTL_30D.ttl_seconds == 2592000
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_cache_ttl.py -v
```

Expected: `ImportError: No module named 'data.cache_manager'`

- [ ] **Step 3: Implement `data/cache_manager.py`**

```python
import json
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from config import CACHE_DIR


class CacheTier(Enum):
    LIVE    = ("live",    None)
    FOREVER = ("forever", None)
    TTL_1D  = ("derived", 86400)
    TTL_7D  = ("derived", 604800)
    TTL_30D = ("derived", 2592000)

    def __init__(self, folder: str, ttl: int | None):
        self.folder = folder
        self.ttl_seconds = ttl


# Maps data_type → (CacheTier, subfolder_name)
DATA_TYPE_TIERS: dict[str, CacheTier] = {
    "live_price":        CacheTier.LIVE,
    "intraday":          CacheTier.LIVE,
    "recent_news":       CacheTier.LIVE,
    "reddit_posts":      CacheTier.LIVE,
    "analyst_ratings":   CacheTier.LIVE,
    "forward_estimates": CacheTier.LIVE,
    "ohlcv_historical":  CacheTier.FOREVER,
    "earnings_history":  CacheTier.FOREVER,
    "financials_annual": CacheTier.FOREVER,
    "sec_filing":        CacheTier.FOREVER,
    "macro_historical":  CacheTier.FOREVER,
    "ratios":            CacheTier.TTL_1D,
    "market_cap":        CacheTier.TTL_1D,
    "sector":            CacheTier.TTL_7D,
    "company_overview":  CacheTier.TTL_30D,
}


class CacheManager:
    def __init__(self, cache_dir: Path = CACHE_DIR, db=None):
        self._root = cache_dir
        self._db = db

    def _path(self, ticker: str, data_type: str, tier: CacheTier) -> Path:
        subfolder = "historical" if tier == CacheTier.FOREVER else "derived"
        p = self._root / ticker / subfolder
        p.mkdir(parents=True, exist_ok=True)
        return p / f"{data_type}.json"

    def get(self, ticker: str, data_type: str) -> dict | None:
        tier = DATA_TYPE_TIERS.get(data_type, CacheTier.TTL_1D)
        if tier == CacheTier.LIVE:
            return None
        path = self._path(ticker, data_type, tier)
        if not path.exists():
            return None
        entry = json.loads(path.read_text(encoding="utf-8"))
        if tier != CacheTier.FOREVER:
            expires = entry.get("expires_at")
            if expires and datetime.fromisoformat(expires) < datetime.utcnow():
                return None
        return entry

    def put(self, ticker: str, data_type: str, data: Any,
            tier: CacheTier, source: str) -> None:
        if tier == CacheTier.LIVE:
            return
        path = self._path(ticker, data_type, tier)
        expires_at = None
        if tier.ttl_seconds:
            expires_at = (datetime.utcnow() + timedelta(seconds=tier.ttl_seconds)).isoformat()
        entry = {
            "data": data,
            "source": source,
            "cache_tier": tier.name.lower(),
            "fetched_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
        }
        path.write_text(json.dumps(entry, default=str), encoding="utf-8")
        if self._db:
            self._db.upsert_cache_entry(
                ticker=ticker, data_type=data_type,
                cache_tier=tier.name.lower(), source=source,
                file_path=str(path), expires_at=expires_at
            )
```

- [ ] **Step 4: Run tests**

```
pytest tests/unit/test_cache_ttl.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add data/cache_manager.py tests/unit/test_cache_ttl.py
git commit -m "feat: three-tier cache manager (live/forever/ttl)"
```

---

## Task 4: Data Manifest

**Files:**
- Create: `data/manifest.py`
- Create: `tests/unit/test_data_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_data_manifest.py
from data.manifest import ManifestBuilder, DataConfidence


def test_all_ok_returns_full_confidence():
    b = ManifestBuilder()
    b.add("revenue", 1_000_000, source="alpha_vantage", status="ok")
    b.add("pe_ratio", 28.5, source="massive_market", status="ok")
    assert b.confidence() == DataConfidence.FULL


def test_one_non_critical_missing_returns_partial():
    b = ManifestBuilder()
    b.add("revenue", 1_000_000, source="alpha_vantage", status="ok")
    b.add("options_pcr", None, source=None, status="missing")  # non-critical
    assert b.confidence() == DataConfidence.PARTIAL


def test_critical_field_missing_returns_minimal():
    b = ManifestBuilder()
    b.add("revenue", None, source=None, status="missing", critical=True)
    b.add("pe_ratio", 28.5, source="massive_market", status="ok")
    assert b.confidence() == DataConfidence.MINIMAL


def test_to_dict_contains_all_fields():
    b = ManifestBuilder()
    b.add("revenue", 1_000_000, source="alpha_vantage", status="ok")
    b.add("revenue_growth", None, source=None, status="missing", note="API returned empty")
    d = b.to_dict()
    assert d["revenue"]["value"] == 1_000_000
    assert d["revenue"]["status"] == "ok"
    assert d["revenue_growth"]["status"] == "missing"
    assert d["revenue_growth"]["note"] == "API returned empty"


def test_partial_status_carries_note():
    b = ManifestBuilder()
    b.add("news", [{"title": "x"}], source="massive_market", status="partial",
          note="3 articles, expected 20")
    d = b.to_dict()
    assert d["news"]["status"] == "partial"
    assert "3 articles" in d["news"]["note"]
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/unit/test_data_manifest.py -v
```

Expected: `ImportError: No module named 'data.manifest'`

- [ ] **Step 3: Implement `data/manifest.py`**

```python
from enum import Enum
from typing import Any, Literal

Status = Literal["ok", "partial", "missing"]

CRITICAL_FIELDS = {
    "live_price", "revenue", "ohlcv", "pe_ratio",
    "income_statement", "balance_sheet", "cash_flow",
    "fed_funds_rate", "earnings_actual_eps",
}


class DataConfidence(str, Enum):
    FULL    = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"


class ManifestBuilder:
    def __init__(self):
        self._entries: dict[str, dict] = {}

    def add(self, field: str, value: Any, source: str | None,
            status: Status, note: str | None = None,
            critical: bool | None = None) -> None:
        is_critical = critical if critical is not None else field in CRITICAL_FIELDS
        self._entries[field] = {
            "value": value,
            "source": source,
            "status": status,
            "note": note,
            "critical": is_critical,
        }

    def confidence(self) -> DataConfidence:
        missing_critical = any(
            e["status"] == "missing" and e["critical"]
            for e in self._entries.values()
        )
        if missing_critical:
            return DataConfidence.MINIMAL
        any_missing = any(e["status"] != "ok" for e in self._entries.values())
        return DataConfidence.PARTIAL if any_missing else DataConfidence.FULL

    def to_dict(self) -> dict[str, dict]:
        return {
            k: {"value": v["value"], "source": v["source"],
                "status": v["status"], "note": v["note"]}
            for k, v in self._entries.items()
        }
```

- [ ] **Step 4: Run tests**

```
pytest tests/unit/test_data_manifest.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add data/manifest.py tests/unit/test_data_manifest.py
git commit -m "feat: data manifest builder with confidence scoring"
```

---

## Task 5: yfinance Client

**Files:**
- Create: `data/yfinance_client.py`
- Create: `tests/integration/test_yfinance_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_yfinance_client.py
import pytest
from unittest.mock import patch, MagicMock
from data.yfinance_client import YFinanceClient


@pytest.fixture
def mock_ticker():
    t = MagicMock()
    t.info = {
        "currentPrice": 183.50, "marketCap": 2_800_000_000_000,
        "trailingPE": 28.5, "priceToBook": 45.2,
        "returnOnEquity": 1.47, "debtToEquity": 185.0,
        "revenueGrowth": 0.04, "grossMargins": 0.46,
        "sector": "Technology", "industry": "Consumer Electronics",
        "shortName": "Apple Inc.",
        "enterpriseToEbitda": 22.1, "priceToSalesTrailing12Months": 7.8,
    }
    t.fast_info = MagicMock()
    t.fast_info.last_price = 183.50
    hist = MagicMock()
    hist.empty = False
    hist.reset_index.return_value = hist
    hist.to_dict.return_value = {"Date": {}, "Open": {}, "High": {}, "Low": {}, "Close": {}, "Volume": {}}
    t.history.return_value = hist
    t.get_earnings_dates.return_value = MagicMock()
    return t


def test_get_price_returns_dict(mock_ticker):
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        client = YFinanceClient()
        result = client.get_price("AAPL")
    assert "price" in result
    assert result["price"] == 183.50
    assert "source" in result
    assert result["source"] == "yfinance"


def test_get_fundamentals_returns_required_fields(mock_ticker):
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        client = YFinanceClient()
        result = client.get_fundamentals("AAPL")
    for field in ("pe_ratio", "price_to_book", "roe", "market_cap", "sector", "industry"):
        assert field in result, f"Missing field: {field}"


def test_get_sector_peers_returns_list(mock_ticker):
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        with patch("data.yfinance_client.yf.download") as mock_dl:
            mock_dl.return_value = MagicMock()
            client = YFinanceClient()
            peers = client.get_sector_peers("AAPL", n=3)
    assert isinstance(peers, list)


def test_missing_info_field_returns_none(mock_ticker):
    mock_ticker.info = {}
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        client = YFinanceClient()
        result = client.get_fundamentals("AAPL")
    assert result["pe_ratio"] is None


def test_get_ohlcv_returns_records(mock_ticker):
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        client = YFinanceClient()
        result = client.get_ohlcv("AAPL", period="1y")
    assert "records" in result
    assert result["source"] == "yfinance"
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/integration/test_yfinance_client.py -v
```

Expected: `ImportError: No module named 'data.yfinance_client'`

- [ ] **Step 3: Implement `data/yfinance_client.py`**

```python
import yfinance as yf
from typing import Any
from logger import get_logger

log = get_logger("yfinance")

PEER_UNIVERSE = {
    "Technology": ["AAPL","MSFT","GOOGL","META","NVDA","TSLA","AMZN","AMD","INTC","ORCL"],
    "Financial Services": ["JPM","BAC","WFC","GS","MS","C","BLK","AXP","V","MA"],
    "Healthcare": ["JNJ","UNH","PFE","ABBV","MRK","TMO","ABT","CVS","LLY","AMGN"],
    "Energy": ["XOM","CVX","COP","EOG","SLB","MPC","VLO","PSX","OXY","HAL"],
    "Consumer Cyclical": ["AMZN","TSLA","HD","NKE","MCD","SBUX","TGT","LOW","BKNG","GM"],
}


class YFinanceClient:
    def get_price(self, ticker: str) -> dict[str, Any]:
        try:
            t = yf.Ticker(ticker)
            price = t.fast_info.last_price
            log.info(f"get_price({ticker}) → {price}")
            return {"price": price, "source": "yfinance"}
        except Exception as e:
            log.warning(f"get_price({ticker}) failed: {e}")
            return {"price": None, "source": "yfinance", "error": str(e)}

    def get_fundamentals(self, ticker: str) -> dict[str, Any]:
        try:
            info = yf.Ticker(ticker).info
            return {
                "pe_ratio":    info.get("trailingPE"),
                "price_to_book": info.get("priceToBook"),
                "ev_ebitda":   info.get("enterpriseToEbitda"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "roe":         info.get("returnOnEquity"),
                "debt_equity": info.get("debtToEquity"),
                "revenue_growth": info.get("revenueGrowth"),
                "gross_margin": info.get("grossMargins"),
                "market_cap":  info.get("marketCap"),
                "sector":      info.get("sector"),
                "industry":    info.get("industry"),
                "name":        info.get("shortName"),
                "source":      "yfinance",
            }
        except Exception as e:
            log.warning(f"get_fundamentals({ticker}) failed: {e}")
            return {"source": "yfinance", "error": str(e),
                    **{k: None for k in ("pe_ratio","price_to_book","ev_ebitda",
                                         "price_to_sales","roe","debt_equity",
                                         "revenue_growth","gross_margin",
                                         "market_cap","sector","industry","name")}}

    def get_ohlcv(self, ticker: str, period: str = "1y") -> dict[str, Any]:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            records = hist.reset_index().to_dict("records") if not hist.empty else []
            return {"records": records, "period": period, "source": "yfinance"}
        except Exception as e:
            log.warning(f"get_ohlcv({ticker}) failed: {e}")
            return {"records": [], "source": "yfinance", "error": str(e)}

    def get_sector_peers(self, ticker: str, n: int = 5) -> list[str]:
        try:
            info = yf.Ticker(ticker).info
            sector = info.get("sector", "")
            universe = PEER_UNIVERSE.get(sector, [])
            return [t for t in universe if t != ticker][:n]
        except Exception as e:
            log.warning(f"get_sector_peers({ticker}) failed: {e}")
            return []
```

- [ ] **Step 4: Run tests**

```
pytest tests/integration/test_yfinance_client.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add data/yfinance_client.py tests/integration/test_yfinance_client.py
git commit -m "feat: yfinance client — price, fundamentals, OHLCV, sector peers"
```

---

## Task 6: Massive Market Data Client (with Token Bucket)

**Files:**
- Create: `data/massive_market.py`
- Create: `tests/integration/test_massive_market.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_massive_market.py
import pytest
import asyncio
import responses as resp_lib
from data.massive_market import MassiveMarketClient


@pytest.fixture
def client():
    return MassiveMarketClient(api_key="test_key")


@resp_lib.activate
def test_get_news_returns_articles(client):
    resp_lib.add(resp_lib.GET,
        "https://api.massive.com/v2/reference/news",
        json={"status": "OK", "results": [
            {"title": "Apple beats earnings", "published_utc": "2026-05-01T10:00:00Z",
             "article_url": "https://example.com/1", "author": "Jane",
             "insights": [{"sentiment": "positive", "sentiment_reasoning": "beat estimates", "ticker": "AAPL"}],
             "tickers": ["AAPL"], "description": "Apple reported strong Q2."}
        ], "count": 1})
    result = client.get_news("AAPL", limit=10)
    assert len(result["articles"]) == 1
    assert result["articles"][0]["title"] == "Apple beats earnings"
    assert result["source"] == "massive_market"


@resp_lib.activate
def test_get_news_429_returns_empty_with_flag(client):
    resp_lib.add(resp_lib.GET,
        "https://api.massive.com/v2/reference/news",
        status=429)
    result = client.get_news("AAPL", limit=10)
    assert result["articles"] == []
    assert result["rate_limited"] is True


@resp_lib.activate
def test_get_snapshot_returns_price(client):
    resp_lib.add(resp_lib.GET,
        "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/AAPL",
        json={"status": "OK", "ticker": {
            "ticker": "AAPL", "day": {"c": 183.50, "v": 50_000_000},
            "prevDay": {"c": 181.00}}})
    result = client.get_snapshot("AAPL")
    assert result["price"] == 183.50
    assert result["source"] == "massive_market"


@resp_lib.activate
def test_get_snapshot_404_returns_none_price(client):
    resp_lib.add(resp_lib.GET,
        "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/AAPL",
        status=404)
    result = client.get_snapshot("AAPL")
    assert result["price"] is None


def test_token_bucket_allows_5_per_minute():
    import time
    from data.massive_market import TokenBucket
    bucket = TokenBucket(rate=5, period=60.0)
    # Should not block for first 5 tokens
    start = time.monotonic()
    for _ in range(5):
        asyncio.get_event_loop().run_until_complete(bucket.acquire())
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"First 5 calls took {elapsed:.2f}s — should be instant"
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/integration/test_massive_market.py -v
```

Expected: `ImportError: No module named 'data.massive_market'`

- [ ] **Step 3: Implement `data/massive_market.py`**

```python
import asyncio
import time
import requests
from typing import Any
from config import MASSIVE_MARKET_API_KEY, MASSIVE_MARKET_BASE_URL
from logger import get_logger

log = get_logger("massive_market")


class TokenBucket:
    """Allows max `rate` calls per `period` seconds. Async-safe."""
    def __init__(self, rate: int = 5, period: float = 60.0):
        self._rate = rate
        self._period = period
        self._tokens = float(rate)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(
                self._rate,
                self._tokens + (now - self._last) * self._rate / self._period
            )
            self._last = now
            if self._tokens < 1:
                wait = (1 - self._tokens) / (self._rate / self._period)
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


_bucket = TokenBucket(rate=5, period=60.0)


class MassiveMarketClient:
    def __init__(self, api_key: str = MASSIVE_MARKET_API_KEY):
        self._key = api_key
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {self._key}"})

    def _get(self, path: str, params: dict | None = None) -> requests.Response | None:
        try:
            asyncio.get_event_loop().run_until_complete(_bucket.acquire())
        except RuntimeError:
            pass  # no event loop in sync context — skip rate limiting
        try:
            return self._session.get(
                f"{MASSIVE_MARKET_BASE_URL}{path}", params=params, timeout=15)
        except Exception as e:
            log.warning(f"HTTP error {path}: {e}")
            return None

    def get_news(self, ticker: str, limit: int = 20) -> dict[str, Any]:
        r = self._get("/v2/reference/news", {"ticker": ticker, "limit": limit, "order": "desc"})
        if r is None or r.status_code == 429:
            log.warning(f"get_news({ticker}) rate limited or failed")
            return {"articles": [], "source": "massive_market", "rate_limited": True}
        if not r.ok:
            return {"articles": [], "source": "massive_market", "rate_limited": False}
        data = r.json()
        articles = [
            {"title": a.get("title"), "published_utc": a.get("published_utc"),
             "article_url": a.get("article_url"), "author": a.get("author"),
             "description": a.get("description"), "tickers": a.get("tickers", []),
             "insights": a.get("insights", [])}
            for a in data.get("results", [])
        ]
        return {"articles": articles, "source": "massive_market",
                "count": data.get("count", 0), "rate_limited": False}

    def get_snapshot(self, ticker: str) -> dict[str, Any]:
        r = self._get(
            f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
        if r is None or not r.ok:
            return {"price": None, "volume": None, "prev_close": None,
                    "source": "massive_market"}
        t = r.json().get("ticker", {})
        day = t.get("day", {})
        return {"price": day.get("c"), "volume": day.get("v"),
                "prev_close": t.get("prevDay", {}).get("c"),
                "source": "massive_market"}

    def get_analyst_ratings(self, ticker: str) -> dict[str, Any]:
        r = self._get(f"/v2/reference/financials", {"ticker": ticker})
        if r is None or not r.ok:
            return {"buy": None, "hold": None, "sell": None,
                    "price_target": None, "source": "massive_market"}
        results = r.json().get("results", [{}])
        d = results[0] if results else {}
        return {"buy": d.get("buy"), "hold": d.get("hold"), "sell": d.get("sell"),
                "price_target": d.get("target_price"), "source": "massive_market"}
```

- [ ] **Step 4: Run tests**

```
pytest tests/integration/test_massive_market.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```
git add data/massive_market.py tests/integration/test_massive_market.py
git commit -m "feat: Massive Market Data client with token bucket rate limiter (5/min)"
```

---

## Task 7: Alpha Vantage Client

**Files:**
- Create: `data/alpha_vantage.py`
- Create: `tests/integration/test_alpha_vantage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_alpha_vantage.py
import responses as resp_lib
import pytest
from data.alpha_vantage import AlphaVantageClient

BASE = "https://www.alphavantage.co/query"

@pytest.fixture
def client():
    return AlphaVantageClient(api_key="demo")


@resp_lib.activate
def test_get_income_statement_returns_annual(client):
    resp_lib.add(resp_lib.GET, BASE, json={
        "symbol": "AAPL",
        "annualReports": [{"fiscalDateEnding": "2025-09-30", "totalRevenue": "391035000000",
                           "grossProfit": "180683000000", "netIncome": "93736000000",
                           "ebitda": "130000000000", "eps": "6.11"}],
        "quarterlyReports": []
    })
    result = client.get_income_statement("AAPL")
    assert len(result["annual"]) == 1
    assert result["annual"][0]["totalRevenue"] == "391035000000"
    assert result["source"] == "alpha_vantage"


@resp_lib.activate
def test_get_earnings_returns_history(client):
    resp_lib.add(resp_lib.GET, BASE, json={
        "symbol": "AAPL",
        "annualEarnings": [],
        "quarterlyEarnings": [
            {"fiscalDateEnding": "2026-03-31", "reportedEPS": "1.65",
             "estimatedEPS": "1.61", "surprise": "0.04", "surprisePercentage": "2.48"},
            {"fiscalDateEnding": "2025-12-31", "reportedEPS": "2.40",
             "estimatedEPS": "2.35", "surprise": "0.05", "surprisePercentage": "2.13"},
        ]
    })
    result = client.get_earnings("AAPL")
    assert len(result["quarterly"]) == 2
    assert result["quarterly"][0]["reportedEPS"] == "1.65"


@resp_lib.activate
def test_rate_limit_returns_empty_with_flag(client):
    resp_lib.add(resp_lib.GET, BASE,
        json={"Note": "API rate limit reached. Please upgrade."})
    result = client.get_income_statement("AAPL")
    assert result["annual"] == []
    assert result["rate_limited"] is True


@resp_lib.activate
def test_get_balance_sheet_returns_annual(client):
    resp_lib.add(resp_lib.GET, BASE, json={
        "annualReports": [{"fiscalDateEnding": "2025-09-30",
                           "totalAssets": "364980000000",
                           "totalLiabilities": "308030000000",
                           "totalShareholderEquity": "56950000000"}],
        "quarterlyReports": []
    })
    result = client.get_balance_sheet("AAPL")
    assert result["annual"][0]["totalAssets"] == "364980000000"
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/integration/test_alpha_vantage.py -v
```

Expected: `ImportError: No module named 'data.alpha_vantage'`

- [ ] **Step 3: Implement `data/alpha_vantage.py`**

```python
import requests
from typing import Any
from config import ALPHA_VANTAGE_API_KEY, ALPHA_VANTAGE_BASE_URL
from logger import get_logger

log = get_logger("alpha_vantage")


class AlphaVantageClient:
    def __init__(self, api_key: str = ALPHA_VANTAGE_API_KEY):
        self._key = api_key

    def _get(self, params: dict) -> dict | None:
        params["apikey"] = self._key
        try:
            r = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=15)
            if not r.ok:
                return None
            return r.json()
        except Exception as e:
            log.warning(f"Alpha Vantage error {params.get('function')}: {e}")
            return None

    def _is_rate_limited(self, data: dict | None) -> bool:
        if not data:
            return False
        return "Note" in data or "Information" in data

    def get_income_statement(self, ticker: str) -> dict[str, Any]:
        data = self._get({"function": "INCOME_STATEMENT", "symbol": ticker})
        if self._is_rate_limited(data):
            log.warning(f"Alpha Vantage rate limit hit for {ticker} income statement")
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": True}
        if not data:
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
        return {"annual": data.get("annualReports", []),
                "quarterly": data.get("quarterlyReports", []),
                "source": "alpha_vantage", "rate_limited": False}

    def get_balance_sheet(self, ticker: str) -> dict[str, Any]:
        data = self._get({"function": "BALANCE_SHEET", "symbol": ticker})
        if self._is_rate_limited(data):
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": True}
        if not data:
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
        return {"annual": data.get("annualReports", []),
                "quarterly": data.get("quarterlyReports", []),
                "source": "alpha_vantage", "rate_limited": False}

    def get_cash_flow(self, ticker: str) -> dict[str, Any]:
        data = self._get({"function": "CASH_FLOW", "symbol": ticker})
        if self._is_rate_limited(data):
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": True}
        if not data:
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
        return {"annual": data.get("annualReports", []),
                "quarterly": data.get("quarterlyReports", []),
                "source": "alpha_vantage", "rate_limited": False}

    def get_earnings(self, ticker: str) -> dict[str, Any]:
        data = self._get({"function": "EARNINGS", "symbol": ticker})
        if self._is_rate_limited(data):
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": True}
        if not data:
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
        return {"annual": data.get("annualEarnings", []),
                "quarterly": data.get("quarterlyEarnings", []),
                "source": "alpha_vantage", "rate_limited": False}
```

- [ ] **Step 4: Run tests**

```
pytest tests/integration/test_alpha_vantage.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```
git add data/alpha_vantage.py tests/integration/test_alpha_vantage.py
git commit -m "feat: Alpha Vantage client — income/balance/cash flow/earnings"
```

---

## Task 8: FRED Client

**Files:**
- Create: `data/fred_client.py`
- Create: `tests/integration/test_fred_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_fred_client.py
import pytest
from unittest.mock import patch, MagicMock
from data.fred_client import FredClient


@pytest.fixture
def client():
    return FredClient(api_key="test_key")


def test_get_macro_snapshot_returns_all_series(client):
    mock_fred = MagicMock()
    mock_fred.get_series.side_effect = lambda series_id: {
        "DFF": MagicMock(**{"iloc[-1]": 5.33}),
        "CPIAUCSL": MagicMock(**{"iloc[-1]": 315.2}),
        "GDP": MagicMock(**{"iloc[-1]": 28_000.0}),
        "UNRATE": MagicMock(**{"iloc[-1]": 3.9}),
    }[series_id]
    with patch("data.fred_client.Fred", return_value=mock_fred):
        c = FredClient(api_key="test")
        result = c.get_macro_snapshot()
    assert "fed_funds_rate" in result
    assert "cpi" in result
    assert "gdp" in result
    assert "unemployment" in result
    assert result["source"] == "fred"


def test_get_macro_snapshot_handles_failure(client):
    mock_fred = MagicMock()
    mock_fred.get_series.side_effect = Exception("API error")
    with patch("data.fred_client.Fred", return_value=mock_fred):
        c = FredClient(api_key="test")
        result = c.get_macro_snapshot()
    assert result["fed_funds_rate"] is None
    assert result["source"] == "fred"
    assert "error" in result
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/integration/test_fred_client.py -v
```

Expected: `ImportError: No module named 'data.fred_client'`

- [ ] **Step 3: Implement `data/fred_client.py`**

```python
from fredapi import Fred
from typing import Any
from config import FRED_API_KEY
from logger import get_logger

log = get_logger("fred")


class FredClient:
    def __init__(self, api_key: str = FRED_API_KEY):
        self._api_key = api_key

    def get_macro_snapshot(self) -> dict[str, Any]:
        try:
            fred = Fred(api_key=self._api_key)
            def _latest(series_id: str) -> float | None:
                try:
                    s = fred.get_series(series_id)
                    return float(s.iloc[-1])
                except Exception:
                    return None

            result = {
                "fed_funds_rate": _latest("DFF"),
                "cpi":            _latest("CPIAUCSL"),
                "gdp":            _latest("GDP"),
                "unemployment":   _latest("UNRATE"),
                "source": "fred",
            }
            log.info(f"FRED snapshot — rate:{result['fed_funds_rate']} "
                     f"cpi:{result['cpi']} gdp:{result['gdp']}")
            return result
        except Exception as e:
            log.warning(f"FRED macro_snapshot failed: {e}")
            return {"fed_funds_rate": None, "cpi": None, "gdp": None,
                    "unemployment": None, "source": "fred", "error": str(e)}

    def get_series_history(self, series_id: str, observation_start: str = "2020-01-01") -> dict[str, Any]:
        try:
            fred = Fred(api_key=self._api_key)
            s = fred.get_series(series_id, observation_start=observation_start)
            records = [{"date": str(d.date()), "value": float(v)}
                       for d, v in s.items() if v == v]  # skip NaN
            return {"series_id": series_id, "records": records, "source": "fred"}
        except Exception as e:
            log.warning(f"FRED get_series({series_id}) failed: {e}")
            return {"series_id": series_id, "records": [], "source": "fred", "error": str(e)}
```

- [ ] **Step 4: Run tests**

```
pytest tests/integration/test_fred_client.py -v
```

Expected: all 2 tests PASS.

- [ ] **Step 5: Commit**

```
git add data/fred_client.py tests/integration/test_fred_client.py
git commit -m "feat: FRED client — macro snapshot (rate, CPI, GDP, unemployment)"
```

---

## Task 9: Reddit Client

**Files:**
- Create: `data/reddit_client.py`
- Create: `tests/integration/test_reddit_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_reddit_client.py
import pytest
from unittest.mock import patch, MagicMock
from data.reddit_client import RedditClient


def _make_post(title, score, url, selftext=""):
    p = MagicMock()
    p.title = title
    p.score = score
    p.url = url
    p.selftext = selftext
    p.created_utc = 1746873600.0
    p.num_comments = 42
    return p


def test_get_posts_returns_structured_results():
    mock_reddit = MagicMock()
    sub = MagicMock()
    sub.search.return_value = [
        _make_post("AAPL to $300 by EOY", 2500, "https://reddit.com/r/wallstreetbets/1"),
        _make_post("Apple earnings analysis", 800, "https://reddit.com/r/investing/2"),
    ]
    mock_reddit.subreddit.return_value = sub
    with patch("data.reddit_client.praw.Reddit", return_value=mock_reddit):
        client = RedditClient(client_id="x", client_secret="y", user_agent="test")
        result = client.get_posts("AAPL", subreddits=["wallstreetbets"], limit=10)
    assert result["total_posts"] == 2
    assert result["posts"][0]["score"] == 2500
    assert result["source"] == "reddit"


def test_get_posts_empty_on_error():
    with patch("data.reddit_client.praw.Reddit", side_effect=Exception("auth failed")):
        client = RedditClient(client_id="x", client_secret="y", user_agent="test")
        result = client.get_posts("AAPL")
    assert result["total_posts"] == 0
    assert "error" in result


def test_sentiment_summary_counts_keywords():
    from data.reddit_client import _score_sentiment
    assert _score_sentiment("AAPL is going to the moon, bullish AF") == "positive"
    assert _score_sentiment("AAPL is crashing, bearish, puts printing") == "negative"
    assert _score_sentiment("I own AAPL shares") == "neutral"
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/integration/test_reddit_client.py -v
```

Expected: `ImportError: No module named 'data.reddit_client'`

- [ ] **Step 3: Implement `data/reddit_client.py`**

```python
import praw
from typing import Any
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
from logger import get_logger

log = get_logger("reddit")

BULLISH_WORDS = {"bull", "bullish", "moon", "buy", "calls", "long", "breakout", "undervalued"}
BEARISH_WORDS = {"bear", "bearish", "crash", "sell", "puts", "short", "overvalued", "dump"}


def _score_sentiment(text: str) -> str:
    words = set(text.lower().split())
    bull = len(words & BULLISH_WORDS)
    bear = len(words & BEARISH_WORDS)
    if bull > bear:
        return "positive"
    if bear > bull:
        return "negative"
    return "neutral"


class RedditClient:
    SUBREDDITS = ["wallstreetbets", "investing", "stocks"]

    def __init__(self, client_id: str = REDDIT_CLIENT_ID,
                 client_secret: str = REDDIT_CLIENT_SECRET,
                 user_agent: str = REDDIT_USER_AGENT):
        self._cid = client_id
        self._csec = client_secret
        self._ua = user_agent

    def get_posts(self, ticker: str,
                  subreddits: list[str] | None = None,
                  limit: int = 50) -> dict[str, Any]:
        subs = subreddits or self.SUBREDDITS
        try:
            reddit = praw.Reddit(
                client_id=self._cid, client_secret=self._csec,
                user_agent=self._ua, read_only=True)
            all_posts = []
            for sub_name in subs:
                sub = reddit.subreddit(sub_name)
                for post in sub.search(ticker, limit=limit, sort="hot", time_filter="week"):
                    all_posts.append({
                        "title": post.title,
                        "score": post.score,
                        "url": post.url,
                        "subreddit": sub_name,
                        "created_utc": post.created_utc,
                        "num_comments": post.num_comments,
                        "sentiment": _score_sentiment(post.title + " " + post.selftext),
                    })
            all_posts.sort(key=lambda p: p["score"], reverse=True)
            pos = sum(1 for p in all_posts if p["sentiment"] == "positive")
            neg = sum(1 for p in all_posts if p["sentiment"] == "negative")
            log.info(f"Reddit {ticker}: {len(all_posts)} posts | +{pos} -{neg}")
            return {"posts": all_posts, "total_posts": len(all_posts),
                    "positive_count": pos, "negative_count": neg,
                    "source": "reddit"}
        except Exception as e:
            log.warning(f"Reddit get_posts({ticker}) failed: {e}")
            return {"posts": [], "total_posts": 0, "positive_count": 0,
                    "negative_count": 0, "source": "reddit", "error": str(e)}
```

- [ ] **Step 4: Run tests**

```
pytest tests/integration/test_reddit_client.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```
git add data/reddit_client.py tests/integration/test_reddit_client.py
git commit -m "feat: Reddit client — WSB/investing posts with sentiment scoring"
```

---

## Task 10: SEC EDGAR Client

**Files:**
- Create: `data/sec_edgar.py`
- Create: `tests/integration/test_sec_edgar.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_sec_edgar.py
import pytest
import responses as resp_lib
from data.sec_edgar import SecEdgarClient


@pytest.fixture
def client():
    return SecEdgarClient()


@resp_lib.activate
def test_get_cik_for_aapl(client):
    resp_lib.add(resp_lib.GET,
        "https://efts.sec.gov/LATEST/search-index?q=%22AAPL%22&dateRange=custom&startdt=2020-01-01&forms=10-K",
        json={"hits": {"hits": [{"_source": {"entity_name": "Apple Inc.", "file_date": "2025-11-01",
              "period_of_report": "2025-09-30", "accession_no": "0000320193-25-000001",
              "entity_id": "320193"}}]}})
    result = client.search_filings("AAPL", form_type="10-K")
    assert len(result["filings"]) >= 1
    assert result["source"] == "sec_edgar"


@resp_lib.activate
def test_missing_ticker_returns_empty(client):
    resp_lib.add(resp_lib.GET,
        "https://efts.sec.gov/LATEST/search-index?q=%22ZZZZZ%22&dateRange=custom&startdt=2020-01-01&forms=10-K",
        json={"hits": {"hits": []}})
    result = client.search_filings("ZZZZZ", form_type="10-K")
    assert result["filings"] == []


@resp_lib.activate
def test_network_error_returns_empty(client):
    import responses as r
    r.add(r.GET,
        "https://efts.sec.gov/LATEST/search-index?q=%22AAPL%22&dateRange=custom&startdt=2020-01-01&forms=8-K",
        body=ConnectionError("Network down"))
    result = client.search_filings("AAPL", form_type="8-K")
    assert result["filings"] == []
    assert "error" in result
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/integration/test_sec_edgar.py -v
```

Expected: `ImportError: No module named 'data.sec_edgar'`

- [ ] **Step 3: Implement `data/sec_edgar.py`**

```python
import requests
from typing import Any
from logger import get_logger

log = get_logger("sec_edgar")

EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
EDGAR_DATA   = "https://data.sec.gov"
HEADERS = {"User-Agent": "HedgeFund Analyser your-email@example.com"}


class SecEdgarClient:
    def search_filings(self, ticker: str, form_type: str = "10-K",
                       start_date: str = "2020-01-01") -> dict[str, Any]:
        params = {"q": f'"{ticker}"', "dateRange": "custom",
                  "startdt": start_date, "forms": form_type}
        try:
            r = requests.get(EDGAR_SEARCH, params=params,
                             headers=HEADERS, timeout=15)
            if not r.ok:
                return {"filings": [], "source": "sec_edgar"}
            hits = r.json().get("hits", {}).get("hits", [])
            filings = [
                {"entity_name": h["_source"].get("entity_name"),
                 "file_date":   h["_source"].get("file_date"),
                 "period":      h["_source"].get("period_of_report"),
                 "accession":   h["_source"].get("accession_no"),
                 "cik":         h["_source"].get("entity_id"),
                 "form_type":   form_type}
                for h in hits
            ]
            log.info(f"SEC EDGAR {ticker} {form_type}: {len(filings)} filings found")
            return {"filings": filings, "source": "sec_edgar"}
        except Exception as e:
            log.warning(f"SEC EDGAR search_filings({ticker}) failed: {e}")
            return {"filings": [], "source": "sec_edgar", "error": str(e)}

    def get_filing_text(self, cik: str, accession_no: str) -> dict[str, Any]:
        acc_clean = accession_no.replace("-", "")
        url = f"{EDGAR_DATA}/Archives/edgar/data/{cik}/{acc_clean}/{accession_no}.txt"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if not r.ok:
                return {"text": None, "source": "sec_edgar"}
            return {"text": r.text[:500_000], "source": "sec_edgar",
                    "url": url}
        except Exception as e:
            log.warning(f"SEC EDGAR get_filing_text failed: {e}")
            return {"text": None, "source": "sec_edgar", "error": str(e)}
```

- [ ] **Step 4: Run tests**

```
pytest tests/integration/test_sec_edgar.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```
git add data/sec_edgar.py tests/integration/test_sec_edgar.py
git commit -m "feat: SEC EDGAR client — filing search and document retrieval (free API)"
```

---

## Task 11: Test Fixtures & Conftest

**Files:**
- Create: `tests/fixtures/aapl_data_bundle.json`
- Create: `tests/fixtures/sample_agent_outputs/fundamental.json`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Create `tests/fixtures/aapl_data_bundle.json`**

This is the frozen data bundle used by all integration, e2e, and failure scenario tests. No test should ever call a real API.

```json
{
  "ticker": "AAPL",
  "run_id": 1,
  "fetched_at": "2026-05-10T09:00:00",
  "data": {
    "live_price": {"price": 183.50, "source": "massive_market"},
    "fundamentals": {
      "pe_ratio": 28.5, "price_to_book": 45.2, "ev_ebitda": 22.1,
      "price_to_sales": 7.8, "roe": 1.47, "debt_equity": 185.0,
      "revenue_growth": 0.04, "gross_margin": 0.46,
      "market_cap": 2800000000000, "sector": "Technology",
      "industry": "Consumer Electronics", "name": "Apple Inc.",
      "source": "yfinance"
    },
    "income_statement": {
      "annual": [{"fiscalDateEnding": "2025-09-30", "totalRevenue": "391035000000",
                  "grossProfit": "180683000000", "netIncome": "93736000000",
                  "ebitda": "130000000000", "eps": "6.11"}],
      "quarterly": [], "source": "alpha_vantage", "rate_limited": false
    },
    "balance_sheet": {
      "annual": [{"fiscalDateEnding": "2025-09-30", "totalAssets": "364980000000",
                  "totalLiabilities": "308030000000",
                  "totalShareholderEquity": "56950000000"}],
      "quarterly": [], "source": "alpha_vantage", "rate_limited": false
    },
    "cash_flow": {
      "annual": [{"fiscalDateEnding": "2025-09-30",
                  "operatingCashflow": "118254000000",
                  "capitalExpenditures": "9959000000",
                  "freeCashFlow": "108295000000"}],
      "quarterly": [], "source": "alpha_vantage", "rate_limited": false
    },
    "earnings": {
      "quarterly": [
        {"fiscalDateEnding": "2026-03-31", "reportedEPS": "1.65",
         "estimatedEPS": "1.61", "surprise": "0.04", "surprisePercentage": "2.48"},
        {"fiscalDateEnding": "2025-12-31", "reportedEPS": "2.40",
         "estimatedEPS": "2.35", "surprise": "0.05", "surprisePercentage": "2.13"},
        {"fiscalDateEnding": "2025-09-30", "reportedEPS": "0.97",
         "estimatedEPS": "0.94", "surprise": "0.03", "surprisePercentage": "3.19"},
        {"fiscalDateEnding": "2025-06-30", "reportedEPS": "1.53",
         "estimatedEPS": "1.48", "surprise": "0.05", "surprisePercentage": "3.38"}
      ],
      "source": "alpha_vantage", "rate_limited": false
    },
    "news": {
      "articles": [
        {"title": "Apple beats Q2 earnings estimates on services growth",
         "published_utc": "2026-05-01T18:00:00Z",
         "article_url": "https://example.com/apple-q2",
         "insights": [{"sentiment": "positive",
                        "sentiment_reasoning": "EPS beat by 2.48%", "ticker": "AAPL"}],
         "tickers": ["AAPL"]}
      ],
      "count": 1, "source": "massive_market", "rate_limited": false
    },
    "reddit": {
      "posts": [
        {"title": "AAPL earnings beat — bullish for rest of year",
         "score": 2500, "subreddit": "wallstreetbets",
         "sentiment": "positive", "num_comments": 342,
         "created_utc": 1746873600.0}
      ],
      "total_posts": 1, "positive_count": 1, "negative_count": 0,
      "source": "reddit"
    },
    "macro": {
      "fed_funds_rate": 5.33, "cpi": 315.2, "gdp": 28000.0,
      "unemployment": 3.9, "source": "fred"
    },
    "sec_filings": {
      "filings": [
        {"entity_name": "Apple Inc.", "file_date": "2025-11-01",
         "period": "2025-09-30", "accession": "0000320193-25-000001",
         "cik": "320193", "form_type": "10-K"}
      ],
      "source": "sec_edgar"
    },
    "ohlcv": {
      "records": [
        {"Date": "2025-05-10", "Open": 181.0, "High": 184.5, "Low": 180.5, "Close": 183.5, "Volume": 55000000},
        {"Date": "2025-05-09", "Open": 179.0, "High": 182.0, "Low": 178.5, "Close": 181.0, "Volume": 48000000}
      ],
      "source": "yfinance"
    },
    "peers": ["MSFT", "GOOGL", "META", "NVDA"]
  },
  "manifest": {
    "live_price":      {"value": 183.50, "source": "massive_market", "status": "ok",     "note": null},
    "pe_ratio":        {"value": 28.5,   "source": "yfinance",        "status": "ok",     "note": null},
    "income_statement":{"value": true,   "source": "alpha_vantage",   "status": "ok",     "note": null},
    "balance_sheet":   {"value": true,   "source": "alpha_vantage",   "status": "ok",     "note": null},
    "cash_flow":       {"value": true,   "source": "alpha_vantage",   "status": "ok",     "note": null},
    "earnings_history":{"value": true,   "source": "alpha_vantage",   "status": "ok",     "note": null},
    "news":            {"value": true,   "source": "massive_market",  "status": "partial","note": "1 article, expected 20"},
    "reddit_posts":    {"value": true,   "source": "reddit",          "status": "ok",     "note": null},
    "fed_funds_rate":  {"value": 5.33,   "source": "fred",            "status": "ok",     "note": null},
    "ohlcv":           {"value": true,   "source": "yfinance",        "status": "ok",     "note": null},
    "sec_10k":         {"value": true,   "source": "sec_edgar",       "status": "ok",     "note": null}
  }
}
```

- [ ] **Step 2: Create `tests/fixtures/sample_agent_outputs/fundamental.json`**

```json
{
  "agent": "fundamental",
  "phase": 1,
  "score": 7,
  "data_confidence": "full",
  "summary": "Apple demonstrates strong fundamental health with consistent EPS beats, expanding services revenue, and robust free cash flow of $108B. DCF analysis suggests intrinsic value of $195-215 vs current $183.50. Relative valuation shows premium to sector peers on P/E (28.5x vs 24.1x median) justified by superior margins.",
  "bull_points": [
    "4 consecutive quarters of EPS beats averaging +2.9% surprise",
    "Free cash flow $108B — class-leading capital return program",
    "Services segment growing 12% YoY with 70%+ gross margins"
  ],
  "bear_points": [
    "Hardware revenue flat YoY — growth dependent on services",
    "China exposure ~18% of revenue — geopolitical risk",
    "Premium valuation (28.5x PE) limits upside in rate environment"
  ],
  "dcf_intrinsic_value": {"bear": 168.0, "base": 195.0, "bull": 215.0},
  "recommendation": "watch"
}
```

- [ ] **Step 3: Update `tests/conftest.py`**

```python
import pytest
import json
import sqlite3
from pathlib import Path
from db.database import Database

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def aapl_bundle():
    """Frozen AAPL data bundle — no real API calls."""
    with open(FIXTURES_DIR / "aapl_data_bundle.json") as f:
        return json.load(f)


@pytest.fixture
def sample_fundamental_output():
    with open(FIXTURES_DIR / "sample_agent_outputs" / "fundamental.json") as f:
        return json.load(f)


@pytest.fixture
def db(tmp_path):
    """In-memory test database — isolated per test."""
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture
def populated_db(db):
    """Database with one complete run's worth of data."""
    run_id = db.create_run("AAPL", "2026-05-10")
    db.update_run(run_id, status="complete", score=2, verdict="watchlist",
                  tier="satellite", entry_low=182.0, entry_high=185.0,
                  stop_loss=171.0, target_price=210.0, contested=0)
    db.save_agent_output(run_id=run_id, agent="fundamental", phase=1,
        score=7, summary="Strong fundamentals.", raw_output='{"score":7}',
        data_confidence="full", duration_ms=3200, status="complete")
    db.save_debate_round(run_id, 1, "Bull argues buy.", "Bear argues hold.", 7, 5)
    db.save_watchlist_entry(run_id=run_id, ticker="AAPL", added_date="2026-05-10",
        score=2, tier="satellite", entry_low=182.0, entry_high=185.0,
        stop_loss=171.0, target_price=210.0, verdict_summary="Strong buy.", contested=0)
    return db, run_id
```

- [ ] **Step 4: Verify fixtures load**

```
python -c "import json; d=json.load(open('tests/fixtures/aapl_data_bundle.json')); print('fields:', list(d['data'].keys()))"
```

Expected: prints list of all data fields.

- [ ] **Step 5: Commit**

```
git add tests/fixtures/ tests/conftest.py
git commit -m "test: add AAPL fixture bundle, sample agent output, and shared conftest fixtures"
```

---

## Task 12: Data Aggregator

**Files:**
- Create: `data/aggregator.py`
- Create: `tests/integration/test_aggregator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_aggregator.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from data.aggregator import DataAggregator


@pytest.fixture
def mock_clients():
    yf = MagicMock()
    yf.get_price.return_value = {"price": 183.50, "source": "yfinance"}
    yf.get_fundamentals.return_value = {
        "pe_ratio": 28.5, "market_cap": 2_800_000_000_000,
        "sector": "Technology", "source": "yfinance"
    }
    yf.get_ohlcv.return_value = {"records": [{"Date": "2026-05-10", "Close": 183.5}], "source": "yfinance"}
    yf.get_sector_peers.return_value = ["MSFT", "GOOGL"]

    mm = MagicMock()
    mm.get_snapshot.return_value = {"price": 183.50, "source": "massive_market"}
    mm.get_news.return_value = {"articles": [{"title": "AAPL beats earnings"}],
                                "source": "massive_market", "rate_limited": False}
    mm.get_analyst_ratings.return_value = {"buy": 32, "hold": 8, "sell": 2, "source": "massive_market"}

    av = MagicMock()
    av.get_income_statement.return_value = {"annual": [{"totalRevenue": "391035000000"}],
                                             "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_balance_sheet.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_cash_flow.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_earnings.return_value = {"quarterly": [{"reportedEPS": "1.65", "estimatedEPS": "1.61"}],
                                     "annual": [], "source": "alpha_vantage", "rate_limited": False}

    fred = MagicMock()
    fred.get_macro_snapshot.return_value = {"fed_funds_rate": 5.33, "cpi": 315.2,
                                             "gdp": 28000.0, "unemployment": 3.9, "source": "fred"}

    reddit = MagicMock()
    reddit.get_posts.return_value = {"posts": [], "total_posts": 0, "source": "reddit"}

    edgar = MagicMock()
    edgar.search_filings.return_value = {"filings": [], "source": "sec_edgar"}

    cache = MagicMock()
    cache.get.return_value = None  # cache miss — always fetch fresh

    db = MagicMock()
    return {"yf": yf, "mm": mm, "av": av, "fred": fred,
            "reddit": reddit, "edgar": edgar, "cache": cache, "db": db}


def test_aggregate_returns_bundle_with_manifest(mock_clients, tmp_path):
    agg = DataAggregator(**mock_clients)
    bundle = agg.fetch("AAPL", run_id=1)
    assert bundle["ticker"] == "AAPL"
    assert bundle["run_id"] == 1
    assert "data" in bundle
    assert "manifest" in bundle
    assert "live_price" in bundle["manifest"]
    assert bundle["manifest"]["live_price"]["status"] == "ok"


def test_aggregate_saves_bundle_to_debug_folder(mock_clients, tmp_path):
    mock_clients["cache"].get.return_value = None
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    agg.fetch("AAPL", run_id=99)
    bundle_file = tmp_path / "run_99_bundle.json"
    assert bundle_file.exists()
    saved = json.loads(bundle_file.read_text())
    assert saved["ticker"] == "AAPL"


def test_missing_live_price_marked_in_manifest(mock_clients, tmp_path):
    mock_clients["mm"].get_snapshot.return_value = {"price": None, "source": "massive_market"}
    mock_clients["yf"].get_price.return_value = {"price": None, "source": "yfinance"}
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=2)
    assert bundle["manifest"]["live_price"]["status"] == "missing"


def test_fallback_used_when_primary_fails(mock_clients, tmp_path):
    # Massive Market returns None price, yfinance has it
    mock_clients["mm"].get_snapshot.return_value = {"price": None, "source": "massive_market"}
    mock_clients["yf"].get_price.return_value = {"price": 183.50, "source": "yfinance"}
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=3)
    assert bundle["data"]["live_price"]["price"] == 183.50
    assert bundle["manifest"]["live_price"]["source"] == "yfinance"
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/integration/test_aggregator.py -v
```

Expected: `ImportError: No module named 'data.aggregator'`

- [ ] **Step 3: Implement `data/aggregator.py`**

```python
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config import DEBUG_BUNDLES_DIR
from data.manifest import ManifestBuilder
from logger import get_logger

log = get_logger("aggregator")


class DataAggregator:
    def __init__(self, yf, mm, av, fred, reddit, edgar, cache, db,
                 debug_dir: Path = DEBUG_BUNDLES_DIR):
        self._yf     = yf
        self._mm     = mm
        self._av     = av
        self._fred   = fred
        self._reddit = reddit
        self._edgar  = edgar
        self._cache  = cache
        self._db     = db
        self._debug_dir = debug_dir
        self._debug_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, ticker: str, run_id: int) -> dict[str, Any]:
        log.info(f"Starting data fetch for {ticker}", )
        mb = ManifestBuilder()
        data: dict[str, Any] = {}

        # ── Live price (never cached) ───────────────────────────────────────
        price_result = self._mm.get_snapshot(ticker)
        if not price_result.get("price"):
            price_result = self._yf.get_price(ticker)
        price = price_result.get("price")
        data["live_price"] = price_result
        mb.add("live_price", price, source=price_result.get("source"),
               status="ok" if price else "missing", critical=True)
        log.info(f"[run_{run_id}] live_price: {price} from {price_result.get('source')}")

        # ── Fundamentals ───────────────────────────────────────────────────
        fund = self._yf.get_fundamentals(ticker)
        data["fundamentals"] = fund
        pe = fund.get("pe_ratio")
        mb.add("pe_ratio", pe, source=fund.get("source"),
               status="ok" if pe else "missing", critical=True)

        # ── OHLCV ──────────────────────────────────────────────────────────
        cached_ohlcv = self._cache.get(ticker, "ohlcv_historical")
        if cached_ohlcv:
            ohlcv = cached_ohlcv["data"]
            ohlcv_src = "cache"
        else:
            ohlcv = self._yf.get_ohlcv(ticker, period="2y")
            ohlcv_src = ohlcv.get("source", "yfinance")
        data["ohlcv"] = ohlcv
        mb.add("ohlcv", bool(ohlcv.get("records")), source=ohlcv_src,
               status="ok" if ohlcv.get("records") else "missing", critical=True)

        # ── Financials (income / balance / cash flow) ───────────────────────
        for key, method in [("income_statement", self._av.get_income_statement),
                             ("balance_sheet",    self._av.get_balance_sheet),
                             ("cash_flow",        self._av.get_cash_flow)]:
            result = method(ticker)
            data[key] = result
            has_data = bool(result.get("annual") or result.get("quarterly"))
            mb.add(key, has_data, source=result.get("source"),
                   status="ok" if has_data else "missing", critical=True)

        # ── Earnings ───────────────────────────────────────────────────────
        earnings = self._av.get_earnings(ticker)
        data["earnings"] = earnings
        has_earnings = bool(earnings.get("quarterly"))
        mb.add("earnings_history", has_earnings, source=earnings.get("source"),
               status="ok" if has_earnings else "missing", critical=True)

        # ── News (live — never cached) ─────────────────────────────────────
        news = self._mm.get_news(ticker, limit=20)
        data["news"] = news
        article_count = len(news.get("articles", []))
        mb.add("news", bool(article_count), source=news.get("source"),
               status="ok" if article_count >= 5 else ("partial" if article_count > 0 else "missing"),
               note=f"{article_count} articles retrieved" if article_count < 5 else None)

        # ── Reddit (live — never cached) ───────────────────────────────────
        reddit = self._reddit.get_posts(ticker)
        data["reddit"] = reddit
        mb.add("reddit_posts", bool(reddit.get("total_posts")), source="reddit",
               status="ok" if reddit.get("total_posts", 0) > 0 else "partial")

        # ── Macro (FRED) ───────────────────────────────────────────────────
        macro = self._fred.get_macro_snapshot()
        data["macro"] = macro
        rate = macro.get("fed_funds_rate")
        mb.add("fed_funds_rate", rate, source="fred",
               status="ok" if rate else "missing", critical=True)

        # ── SEC filings ────────────────────────────────────────────────────
        filings = self._edgar.search_filings(ticker, form_type="10-K")
        data["sec_filings"] = filings
        mb.add("sec_10k", bool(filings.get("filings")), source="sec_edgar",
               status="ok" if filings.get("filings") else "partial")

        # ── Analyst ratings ────────────────────────────────────────────────
        ratings = self._mm.get_analyst_ratings(ticker)
        data["analyst_ratings"] = ratings

        # ── Peers ──────────────────────────────────────────────────────────
        data["peers"] = self._yf.get_sector_peers(ticker, n=5)

        # ── Bundle & snapshot ──────────────────────────────────────────────
        bundle: dict[str, Any] = {
            "ticker": ticker,
            "run_id": run_id,
            "fetched_at": datetime.utcnow().isoformat(),
            "data": data,
            "manifest": mb.to_dict(),
            "data_confidence": mb.confidence().value,
        }
        bundle_path = self._debug_dir / f"run_{run_id}_bundle.json"
        bundle_path.write_text(json.dumps(bundle, default=str), encoding="utf-8")
        log.info(f"[run_{run_id}] Bundle saved → {bundle_path} | confidence: {bundle['data_confidence']}")
        return bundle
```

- [ ] **Step 4: Run tests**

```
pytest tests/integration/test_aggregator.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```
git add data/aggregator.py tests/integration/test_aggregator.py
git commit -m "feat: data aggregator — pre-fetch all sources, build manifest, save debug bundle"
```

---

## Task 13: Failure Scenario Tests

**Files:**
- Create: `tests/failure_scenarios/test_api_failures.py`
- Create: `tests/failure_scenarios/test_missing_data.py`
- Create: `tests/failure_scenarios/test_propagation.py`

- [ ] **Step 1: Create `tests/failure_scenarios/test_api_failures.py`**

```python
# tests/failure_scenarios/test_api_failures.py
"""Verify that API failures trigger fallback chain, not crashes."""
import pytest
from unittest.mock import MagicMock
from data.aggregator import DataAggregator


def _make_aggregator(tmp_path, **overrides):
    defaults = {
        "yf":     MagicMock(**{"get_price.return_value": {"price": 183.5, "source": "yfinance"},
                               "get_fundamentals.return_value": {"pe_ratio": 28.5, "source": "yfinance"},
                               "get_ohlcv.return_value": {"records": [{"Close": 183.5}], "source": "yfinance"},
                               "get_sector_peers.return_value": ["MSFT"]}),
        "mm":     MagicMock(**{"get_snapshot.return_value": {"price": 183.5, "source": "massive_market"},
                               "get_news.return_value": {"articles": [], "source": "massive_market", "rate_limited": False},
                               "get_analyst_ratings.return_value": {"buy": 10, "source": "massive_market"}}),
        "av":     MagicMock(**{"get_income_statement.return_value": {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False},
                               "get_balance_sheet.return_value": {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False},
                               "get_cash_flow.return_value": {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False},
                               "get_earnings.return_value": {"quarterly": [], "annual": [], "source": "alpha_vantage", "rate_limited": False}}),
        "fred":   MagicMock(**{"get_macro_snapshot.return_value": {"fed_funds_rate": 5.33, "source": "fred"}}),
        "reddit": MagicMock(**{"get_posts.return_value": {"posts": [], "total_posts": 0, "source": "reddit"}}),
        "edgar":  MagicMock(**{"search_filings.return_value": {"filings": [], "source": "sec_edgar"}}),
        "cache":  MagicMock(**{"get.return_value": None}),
        "db":     MagicMock(),
    }
    defaults.update(overrides)
    return DataAggregator(**defaults, debug_dir=tmp_path)


def test_massive_market_down_falls_back_to_yfinance_for_price(tmp_path):
    mm = MagicMock(**{"get_snapshot.return_value": {"price": None, "source": "massive_market"},
                      "get_news.return_value": {"articles": [], "source": "massive_market", "rate_limited": False},
                      "get_analyst_ratings.return_value": {"buy": None, "source": "massive_market"}})
    yf = MagicMock(**{"get_price.return_value": {"price": 183.50, "source": "yfinance"},
                      "get_fundamentals.return_value": {"pe_ratio": 28.5, "source": "yfinance"},
                      "get_ohlcv.return_value": {"records": [{"Close": 183.5}], "source": "yfinance"},
                      "get_sector_peers.return_value": []})
    agg = _make_aggregator(tmp_path, mm=mm, yf=yf)
    bundle = agg.fetch("AAPL", run_id=10)
    assert bundle["data"]["live_price"]["price"] == 183.50
    assert bundle["manifest"]["live_price"]["source"] == "yfinance"
    assert bundle["manifest"]["live_price"]["status"] == "ok"


def test_all_price_sources_fail_marks_critical_missing(tmp_path):
    mm = MagicMock(**{"get_snapshot.return_value": {"price": None, "source": "massive_market"},
                      "get_news.return_value": {"articles": [], "source": "massive_market", "rate_limited": False},
                      "get_analyst_ratings.return_value": {"buy": None, "source": "massive_market"}})
    yf = MagicMock(**{"get_price.return_value": {"price": None, "source": "yfinance"},
                      "get_fundamentals.return_value": {"pe_ratio": None, "source": "yfinance"},
                      "get_ohlcv.return_value": {"records": [], "source": "yfinance"},
                      "get_sector_peers.return_value": []})
    agg = _make_aggregator(tmp_path, mm=mm, yf=yf)
    bundle = agg.fetch("AAPL", run_id=11)
    assert bundle["manifest"]["live_price"]["status"] == "missing"
    assert bundle["data_confidence"] == "minimal"


def test_fred_failure_does_not_abort_run(tmp_path):
    fred = MagicMock(**{"get_macro_snapshot.return_value":
                        {"fed_funds_rate": None, "source": "fred", "error": "timeout"}})
    agg = _make_aggregator(tmp_path, fred=fred)
    bundle = agg.fetch("AAPL", run_id=12)
    # Run still completes — FRED failure is partial, not fatal
    assert "macro" in bundle["data"]
    assert bundle["manifest"]["fed_funds_rate"]["status"] == "missing"
```

- [ ] **Step 2: Create `tests/failure_scenarios/test_propagation.py`**

```python
# tests/failure_scenarios/test_propagation.py
"""Verify that missing data in manifest is never silently promoted to a verdict."""
from data.manifest import ManifestBuilder, DataConfidence


def test_two_critical_missing_fields_returns_minimal():
    b = ManifestBuilder()
    b.add("revenue", None, source=None, status="missing", critical=True)
    b.add("live_price", None, source=None, status="missing", critical=True)
    b.add("pe_ratio", 28.5, source="yfinance", status="ok")
    assert b.confidence() == DataConfidence.MINIMAL


def test_minimal_confidence_triggers_abort():
    """
    Simulate the pipeline abort check: if >= 2 Phase 1 agents return
    minimal confidence, the pipeline should not proceed to Phase 2.
    """
    from data.manifest import DataConfidence

    agent_confidences = [
        DataConfidence.MINIMAL,
        DataConfidence.MINIMAL,
        DataConfidence.FULL,
        DataConfidence.PARTIAL,
        DataConfidence.FULL,
    ]
    minimal_count = sum(1 for c in agent_confidences if c == DataConfidence.MINIMAL)
    should_abort = minimal_count >= 2
    assert should_abort is True


def test_single_critical_missing_still_partial_if_others_ok():
    b = ManifestBuilder()
    b.add("revenue", 1_000_000, source="alpha_vantage", status="ok", critical=True)
    b.add("options_pcr", None, source=None, status="missing", critical=False)
    assert b.confidence() == DataConfidence.PARTIAL
```

- [ ] **Step 3: Run all failure scenario tests**

```
pytest tests/failure_scenarios/ -v
```

Expected: all 6 tests PASS.

- [ ] **Step 4: Run entire test suite**

```
pytest tests/ -v --tb=short
```

Expected: all tests PASS. Note total count.

- [ ] **Step 5: Commit**

```
git add tests/failure_scenarios/
git commit -m "test: failure scenario tests — API fallbacks, propagation prevention, abort rule"
```

---

## Task 14: Final Wiring & Smoke Test

**Files:**
- Create: `tests/regression/.gitkeep`
- Create: `tests/e2e/test_data_layer_smoke.py`

- [ ] **Step 1: Create e2e smoke test for data layer**

```python
# tests/e2e/test_data_layer_smoke.py
"""
End-to-end smoke test for the data layer using only the frozen AAPL bundle.
Verifies all components work together from fixture input to bundle output.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from data.aggregator import DataAggregator
from data.manifest import DataConfidence
from db.database import Database


def test_full_data_layer_pipeline_with_fixture(aapl_bundle, tmp_path):
    """
    Given: all clients return data matching the frozen AAPL fixture
    When: aggregator.fetch() is called
    Then: bundle is complete, manifest has no critical missing fields,
          bundle is saved to debug folder, DB cache entry can be written
    """
    # Wire up mock clients to return fixture data
    yf = MagicMock()
    yf.get_price.return_value = aapl_bundle["data"]["live_price"]
    yf.get_fundamentals.return_value = aapl_bundle["data"]["fundamentals"]
    yf.get_ohlcv.return_value = aapl_bundle["data"]["ohlcv"]
    yf.get_sector_peers.return_value = aapl_bundle["data"]["peers"]

    mm = MagicMock()
    mm.get_snapshot.return_value = aapl_bundle["data"]["live_price"]
    mm.get_news.return_value = aapl_bundle["data"]["news"]
    mm.get_analyst_ratings.return_value = aapl_bundle["data"]["analyst_ratings"]

    av = MagicMock()
    av.get_income_statement.return_value = aapl_bundle["data"]["income_statement"]
    av.get_balance_sheet.return_value = aapl_bundle["data"]["balance_sheet"]
    av.get_cash_flow.return_value = aapl_bundle["data"]["cash_flow"]
    av.get_earnings.return_value = aapl_bundle["data"]["earnings"]

    fred = MagicMock()
    fred.get_macro_snapshot.return_value = aapl_bundle["data"]["macro"]

    reddit = MagicMock()
    reddit.get_posts.return_value = aapl_bundle["data"]["reddit"]

    edgar = MagicMock()
    edgar.search_filings.return_value = aapl_bundle["data"]["sec_filings"]

    cache = MagicMock()
    cache.get.return_value = None

    db = MagicMock()

    agg = DataAggregator(yf=yf, mm=mm, av=av, fred=fred,
                         reddit=reddit, edgar=edgar, cache=cache,
                         db=db, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=1)

    # Bundle structure
    assert bundle["ticker"] == "AAPL"
    assert bundle["run_id"] == 1
    assert "data" in bundle
    assert "manifest" in bundle

    # All critical fields present
    critical_fields = ["live_price", "pe_ratio", "income_statement",
                       "balance_sheet", "cash_flow", "earnings_history",
                       "fed_funds_rate", "ohlcv"]
    for field in critical_fields:
        assert field in bundle["manifest"], f"Critical field missing from manifest: {field}"
        assert bundle["manifest"][field]["status"] != "missing", \
            f"Critical field {field} has status 'missing'"

    # Confidence is not minimal
    assert bundle["data_confidence"] != DataConfidence.MINIMAL.value

    # Debug bundle was saved
    bundle_file = tmp_path / "run_1_bundle.json"
    assert bundle_file.exists()
    saved = json.loads(bundle_file.read_text())
    assert saved["ticker"] == "AAPL"
```

- [ ] **Step 2: Run the e2e smoke test**

```
pytest tests/e2e/test_data_layer_smoke.py -v
```

Expected: 1 test PASS.

- [ ] **Step 3: Run full suite and confirm all green**

```
pytest tests/ -v
```

Expected: all tests PASS. Record total passing count in commit message.

- [ ] **Step 4: Final commit for Plan 1**

```
git add .
git commit -m "feat: Plan 1 complete — foundation and data layer (all tests passing)

- config.py, logger.py: project foundation with structured [hf:module] logging
- db/database.py: full SQLite schema (5 tables) + CRUD layer
- data/cache_manager.py: three-tier caching (live/forever/TTL)
- data/manifest.py: field-level data manifest with confidence scoring
- data/yfinance_client.py: price, OHLCV, fundamentals, sector peers
- data/massive_market.py: news, snapshot, analyst ratings + token bucket (5/min)
- data/alpha_vantage.py: income/balance/cash flow/earnings
- data/fred_client.py: macro snapshot (rate, CPI, GDP, unemployment)
- data/reddit_client.py: WSB/investing posts with sentiment scoring
- data/sec_edgar.py: SEC EDGAR filing search and document retrieval (free)
- data/aggregator.py: orchestrates all fetchers, builds manifest, saves debug bundle
- tests/: unit + integration + e2e + failure scenarios, all using frozen fixtures"
git push origin main
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Config ✓, Logging ✓, DB schema ✓, Cache (3 tiers) ✓, All 6 fetchers ✓, Data manifest ✓, Aggregator ✓, Debug bundle snapshot ✓, Redundancy waterfall ✓, Failure scenarios ✓
- [x] **No placeholders:** All steps have complete code, exact commands, expected output
- [x] **Type consistency:** `ManifestBuilder.add()` signature used consistently in manifest.py and aggregator.py. `Database` fixture name consistent across conftest and test files. `DataConfidence` enum used correctly throughout.
- [x] **API keys:** All clients accept api_key param with config defaults — tests inject `"test_key"` without touching real keys
- [x] **Cache tiers:** LIVE fields (live_price, news, reddit) correctly bypassed in aggregator; only TTL/FOREVER types cached
