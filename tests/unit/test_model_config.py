"""Tests for ModelConfig dataclass."""
import pytest

from pipeline.orchestrator import ModelConfig
from config import PHASE1_MODEL, PHASE2_MODEL, DEBATE_MODEL, PM_MODEL


def test_provider_gemini_derived():
    cfg = ModelConfig.from_request({"phase1_model": "gemini-2.0-flash"})
    assert cfg.phase1_provider == "gemini"


def test_provider_anthropic_derived():
    cfg = ModelConfig.from_request({"phase1_model": "claude-haiku-4-5-20251001"})
    assert cfg.phase1_provider == "anthropic"


def test_empty_request_uses_env_defaults():
    cfg = ModelConfig.from_request({})
    assert cfg.phase1_model == PHASE1_MODEL
    assert cfg.phase2_model == PHASE2_MODEL
    assert cfg.debate_model == DEBATE_MODEL
    assert cfg.pm_model == PM_MODEL


def test_partial_override_only_changes_specified_phase():
    cfg = ModelConfig.from_request({"phase1_model": "claude-haiku-4-5-20251001"})
    assert cfg.phase1_model == "claude-haiku-4-5-20251001"
    assert cfg.phase1_provider == "anthropic"
    assert cfg.phase2_model == PHASE2_MODEL
    assert cfg.debate_model == DEBATE_MODEL
    assert cfg.pm_model == PM_MODEL


def test_all_four_phases_overrideable():
    cfg = ModelConfig.from_request({
        "phase1_model": "claude-haiku-4-5-20251001",
        "phase2_model": "claude-haiku-4-5-20251001",
        "debate_model": "claude-opus-4-6-20250514",
        "pm_model": "claude-opus-4-6-20250514",
    })
    assert cfg.phase1_model == "claude-haiku-4-5-20251001"
    assert cfg.phase1_provider == "anthropic"
    assert cfg.phase2_model == "claude-haiku-4-5-20251001"
    assert cfg.phase2_provider == "anthropic"
    assert cfg.debate_model == "claude-opus-4-6-20250514"
    assert cfg.debate_provider == "anthropic"
    assert cfg.pm_model == "claude-opus-4-6-20250514"
    assert cfg.pm_provider == "anthropic"
