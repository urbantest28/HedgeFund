import json
import pytest
from unittest.mock import patch
from agents.base_agent import BaseAgent, _extract_json, _load_prompt


class ConcreteAgent(BaseAgent):
    name = "test_agent"
    phase = 1
    role_file = "fundamental_analyst.md"
    skill_files = ["financial_ratio_analysis.md"]
    provider = "gemini"
    model = "gemini-2.0-flash"


def test_extract_json_plain():
    raw = '{"score": 7, "data_confidence": "full"}'
    result = _extract_json(raw)
    assert result["score"] == 7


def test_extract_json_with_markdown_fences():
    raw = '```json\n{"score": 8, "data_confidence": "partial"}\n```'
    result = _extract_json(raw)
    assert result["score"] == 8


def test_extract_json_with_plain_fences():
    raw = '```\n{"score": 5}\n```'
    result = _extract_json(raw)
    assert result["score"] == 5


def test_extract_json_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        _extract_json("not valid json")


def test_load_prompt_combines_role_and_skills():
    text = _load_prompt("fundamental_analyst.md", ["financial_ratio_analysis.md"])
    assert "Fundamental Analyst" in text
    assert "Financial Ratio Analysis" in text


def test_load_prompt_role_only():
    text = _load_prompt("macro_analyst.md", [])
    assert "Macro Analyst" in text


def test_agent_run_returns_complete_on_success(aapl_bundle):
    agent = ConcreteAgent()
    mock_output = json.dumps({
        "score": 7,
        "data_confidence": "full",
        "summary": "Test summary",
        "missing_fields": [],
        "bull_points": ["good point"],
        "bear_points": ["bad point"],
        "raw_output": {"pe_ratio": 28.5}
    })
    with patch.object(agent, "_call_llm", return_value=mock_output):
        result = agent.run(aapl_bundle, run_id=1)

    assert result["status"] == "complete"
    assert result["score"] == 7
    assert result["agent"] == "test_agent"
    assert result["phase"] == 1
    assert result["duration_ms"] >= 0


def test_agent_run_retries_on_failure_then_succeeds(aapl_bundle):
    agent = ConcreteAgent()
    mock_output = json.dumps({
        "score": 6, "data_confidence": "partial", "summary": "retry ok",
        "missing_fields": [], "bull_points": [], "bear_points": [], "raw_output": {}
    })
    call_count = 0

    def side_effect(user_prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("temporary LLM error")
        return mock_output

    with patch.object(agent, "_call_llm", side_effect=side_effect):
        result = agent.run(aapl_bundle, run_id=1)

    assert call_count == 2
    assert result["status"] == "complete"


def test_agent_run_returns_failed_after_two_failures(aapl_bundle):
    agent = ConcreteAgent()
    with patch.object(agent, "_call_llm", side_effect=ValueError("persistent error")):
        result = agent.run(aapl_bundle, run_id=1)

    assert result["status"] == "failed"
    assert result["score"] is None
    assert result["data_confidence"] == "minimal"


def test_agent_run_handles_malformed_json(aapl_bundle):
    agent = ConcreteAgent()
    with patch.object(agent, "_call_llm", return_value="not json at all"):
        result = agent.run(aapl_bundle, run_id=1)

    assert result["status"] == "failed"
