"""
Failure scenario tests for agent-level failures.

Per design-spec §15:
  Agent failure (Claude/Gemini error or malformed JSON):
    retry once -> on second failure, marked `failed` in `agent_outputs`,
    pipeline continues with warning -> Portfolio Manager notes which
    agents failed.
"""
import json
from unittest.mock import patch

import pytest

from agents.base_agent import BaseAgent
from pipeline.orchestrator import _build_summaries


class DummyAgent(BaseAgent):
    name = "dummy"
    phase = 1
    # Reuse a real prompt file so __init__ (which loads it from disk) succeeds.
    role_file = "fundamental_analyst.md"
    skill_files = []
    provider = "gemini"
    model = "gemini-2.0-flash"


VALID_OUTPUT = json.dumps({
    "score": 7,
    "data_confidence": "full",
    "summary": "ok",
    "missing_fields": [],
    "bull_points": [],
    "bear_points": [],
    "raw_output": {},
})


def test_agent_retries_once_on_first_failure():
    """First LLM call raises; retry succeeds — final status is complete."""
    agent = DummyAgent()
    call_count = {"n": 0}

    def flaky(user_prompt):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("transient LLM error")
        return VALID_OUTPUT

    with patch.object(agent, "_call_llm", side_effect=flaky):
        result = agent.run({"ticker": "TEST"}, run_id=1)

    assert call_count["n"] == 2, "must retry exactly once on first failure"
    assert result["status"] == "complete"
    assert result["score"] == 7


def test_agent_marked_failed_after_second_failure():
    """Both attempts raise — agent returns status=failed with score=None."""
    agent = DummyAgent()

    with patch.object(agent, "_call_llm", side_effect=RuntimeError("permanent error")):
        result = agent.run({"ticker": "TEST"}, run_id=1)

    assert result["status"] == "failed"
    assert result["score"] is None
    assert result["data_confidence"] == "minimal"
    assert "permanent error" in result["summary"]


def test_agent_marked_failed_on_persistent_malformed_json():
    """Malformed JSON on both attempts -> status=failed (covers parse failures)."""
    agent = DummyAgent()

    with patch.object(agent, "_call_llm", return_value="this is not json"):
        result = agent.run({"ticker": "TEST"}, run_id=1)

    assert result["status"] == "failed"
    assert result["score"] is None


def test_agent_does_not_retry_more_than_once():
    """Failure -> retry -> failure must NOT trigger a third attempt."""
    agent = DummyAgent()
    call_count = {"n": 0}

    def always_fail(user_prompt):
        call_count["n"] += 1
        raise RuntimeError("nope")

    with patch.object(agent, "_call_llm", side_effect=always_fail):
        agent.run({"ticker": "TEST"}, run_id=1)

    assert call_count["n"] == 2, "expected exactly 2 calls (1 attempt + 1 retry)"


def test_build_summaries_propagates_failed_status_to_pm():
    """_build_summaries must surface status so the Portfolio Manager sees failures."""
    failed_result = {
        "agent": "fundamental",
        "phase": 1,
        "score": None,
        "data_confidence": "minimal",
        "status": "failed",
        "summary": "Agent failed: LLM error",
        "duration_ms": 5000,
        "bull_points": [],
        "bear_points": [],
        "missing_fields": [],
        "raw_output": {"error": "LLM error"},
    }
    ok_result = {
        "agent": "technical",
        "phase": 1,
        "score": 6,
        "data_confidence": "full",
        "status": "complete",
        "summary": "fine",
        "duration_ms": 1000,
        "bull_points": [],
        "bear_points": [],
        "missing_fields": [],
        "raw_output": {},
    }

    summaries = _build_summaries([failed_result, ok_result])

    assert "fundamental" in summaries
    assert summaries["fundamental"]["status"] == "failed"
    assert summaries["technical"]["status"] == "complete"
