"""Tests for model config columns on analysis_runs."""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from db.database import Database


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    return Database(path)


def test_analysis_runs_has_model_columns(db):
    cur = db._conn.execute("PRAGMA table_info(analysis_runs)")
    columns = {row[1] for row in cur.fetchall()}
    assert "phase1_model" in columns
    assert "phase2_model" in columns
    assert "debate_model" in columns
    assert "pm_model" in columns


def test_create_run_without_model_columns_still_works(db):
    run_id = db.create_run("AAPL", "2026-05-17")
    assert isinstance(run_id, int)
    row = db.get_run(run_id)
    assert row["ticker"] == "AAPL"
    assert row["phase1_model"] is None
    assert row["phase2_model"] is None
    assert row["debate_model"] is None
    assert row["pm_model"] is None


def test_update_run_model_columns(db):
    run_id = db.create_run("TSLA", "2026-05-17")
    db.update_run(run_id,
                  phase1_model="claude-haiku-4-5-20251001",
                  phase2_model="gemini-2.0-flash",
                  debate_model="claude-opus-4-7",
                  pm_model="claude-opus-4-7")
    row = db.get_run(run_id)
    assert row["phase1_model"] == "claude-haiku-4-5-20251001"
    assert row["phase2_model"] == "gemini-2.0-flash"
    assert row["debate_model"] == "claude-opus-4-7"
    assert row["pm_model"] == "claude-opus-4-7"
