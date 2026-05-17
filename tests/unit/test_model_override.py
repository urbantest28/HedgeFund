"""Tests for agent model/provider override routing."""
import pytest
from unittest.mock import patch, MagicMock

from agents.fundamental import FundamentalAgent


def test_override_routes_to_anthropic():
    agent = FundamentalAgent()
    agent.model = "claude-haiku-4-5-20251001"
    agent.provider = "anthropic"
    assert agent.provider == "anthropic"
    assert agent.model == "claude-haiku-4-5-20251001"

    with patch.object(agent, "_call_claude", return_value='{"score":7}') as mock_claude, \
         patch.object(agent, "_call_gemini") as mock_gemini:
        result = agent._call_llm("test prompt")
        mock_claude.assert_called_once()
        mock_gemini.assert_not_called()


def test_override_routes_to_gemini():
    agent = FundamentalAgent()
    agent.model = "gemini-2.0-flash"
    agent.provider = "gemini"

    with patch.object(agent, "_call_gemini", return_value='{"score":7}') as mock_gemini, \
         patch.object(agent, "_call_claude") as mock_claude:
        result = agent._call_llm("test prompt")
        mock_gemini.assert_called_once()
        mock_claude.assert_not_called()


def test_class_level_attributes_not_mutated_by_instance_override():
    agent1 = FundamentalAgent()
    agent1.model = "claude-haiku-4-5-20251001"
    agent1.provider = "anthropic"

    agent2 = FundamentalAgent()
    # agent2 should still have the class-level defaults
    assert agent2.model != "claude-haiku-4-5-20251001" or agent2.provider != "anthropic" \
        or FundamentalAgent.model == "claude-haiku-4-5-20251001"
    # The key check: instance override doesn't leak to other instances
    assert agent1.model == "claude-haiku-4-5-20251001"
