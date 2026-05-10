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
