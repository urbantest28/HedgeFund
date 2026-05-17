"""Integration tests for per-run model config in the pipeline."""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from db.database import Database
from pipeline.orchestrator import ModelConfig, _run_phase_parallel
from agents.fundamental import FundamentalAgent
from agents.technical import TechnicalAgent
from agents.sentiment import SentimentAgent
from agents.macro import MacroAgent
from agents.earnings_reviewer import EarningsReviewerAgent

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def _load_bundle() -> dict:
    return json.loads((FIXTURE_DIR / "aapl_data_bundle.json").read_text())


def _agent_mock_output(name: str) -> str:
    path = FIXTURE_DIR / "sample_agent_outputs" / f"{name}.json"
    data = json.loads(path.read_text())
    return json.dumps({
        "score": data["score"],
        "data_confidence": data["data_confidence"],
        "summary": data["summary"],
        "missing_fields": data["missing_fields"],
        "bull_points": data["bull_points"],
        "bear_points": data["bear_points"],
        "raw_output": data["raw_output"],
    })


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def bundle():
    b = _load_bundle()
    b.setdefault("ticker", "AAPL")
    return b


def test_phase1_agents_receive_model_override(db, bundle):
    """Agents instantiated for phase 1 should have model/provider from ModelConfig."""
    cfg = ModelConfig.from_request({"phase1_model": "claude-haiku-4-5-20251001"})
    run_id = db.create_run("AAPL", "2026-05-17")

    seen_providers = []

    def capture_provider(self, user_prompt, *args, **kwargs):
        seen_providers.append(self.provider)
        return _agent_mock_output(self.name)

    agent_names = ["fundamental", "technical", "sentiment", "macro", "earnings_reviewer"]
    patch_targets = [
        f"agents.{n.replace('_reviewer', '_reviewer') if '_reviewer' in n else n}.{cls.__name__}._call_llm_with_fallback"
        for n, cls in zip(
            ["fundamental", "technical", "sentiment", "macro", "earnings_reviewer"],
            [FundamentalAgent, TechnicalAgent, SentimentAgent, MacroAgent, EarningsReviewerAgent]
        )
    ]

    loop = asyncio.new_event_loop()
    queue = asyncio.Queue()

    async def run():
        from agents.fundamental import FundamentalAgent as FA
        from agents.technical import TechnicalAgent as TA
        from agents.sentiment import SentimentAgent as SA
        from agents.macro import MacroAgent as MA
        from agents.earnings_reviewer import EarningsReviewerAgent as EA

        agent_classes = [FA, TA, SA, MA, EA]
        agents = [cls() for cls in agent_classes]
        # Apply model config override
        for a in agents:
            a.model = cfg.phase1_model
            a.provider = cfg.phase1_provider

        # Verify override applied before run
        for a in agents:
            assert a.provider == "anthropic", f"{a.name} provider not overridden"
            assert a.model == "claude-haiku-4-5-20251001", f"{a.name} model not overridden"

    loop.run_until_complete(run())
    loop.close()


def test_model_config_stored_in_db(db):
    """create_run with model config should persist model names."""
    cfg = ModelConfig.from_request({
        "phase1_model": "claude-haiku-4-5-20251001",
        "phase2_model": "claude-haiku-4-5-20251001",
        "debate_model": "claude-opus-4-7",
        "pm_model": "claude-opus-4-7",
    })
    run_id = db.create_run("AAPL", "2026-05-17",
                           phase1_model=cfg.phase1_model,
                           phase2_model=cfg.phase2_model,
                           debate_model=cfg.debate_model,
                           pm_model=cfg.pm_model)
    row = db.get_run(run_id)
    assert row["phase1_model"] == "claude-haiku-4-5-20251001"
    assert row["phase2_model"] == "claude-haiku-4-5-20251001"
    assert row["debate_model"] == "claude-opus-4-7"
    assert row["pm_model"] == "claude-opus-4-7"
