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


@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / "fixtures"
