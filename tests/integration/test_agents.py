"""Integration tests for all agents — mocks LLM, never hits real APIs."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from agents.fundamental import FundamentalAgent
from agents.technical import TechnicalAgent
from agents.sentiment import SentimentAgent
from agents.macro import MacroAgent
from agents.earnings_reviewer import EarningsReviewerAgent
from agents.risk_manager import RiskManagerAgent
from agents.thesis_validator import ThesisValidatorAgent
from agents.financial_modeler import FinancialModelerAgent
from agents.bull import BullAgent
from agents.bear import BearAgent
from agents.portfolio_manager import PortfolioManagerAgent


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sample_agent_outputs"


def _mock_llm_output(agent_name: str) -> str:
    path = FIXTURE_DIR / f"{agent_name}.json"
    data = json.loads(path.read_text())
    # For PM and standard agents return the full fixture as LLM text
    # For debate agents (bull/bear) the fixture IS the round output, return just the inner fields
    if agent_name in ("bull", "bear"):
        return json.dumps({"argument": data["argument"], "conviction": data["conviction"], "concessions": data["concessions"]})
    if agent_name == "portfolio_manager":
        # PM's run() calls _extract_json on LLM text then does parsed.get("score")
        # so we include score alongside the raw_output fields
        pm_payload = {"score": data["score"], **data["raw_output"]}
        return json.dumps(pm_payload)
    return json.dumps({
        "score": data["score"],
        "data_confidence": data["data_confidence"],
        "summary": data["summary"],
        "missing_fields": data["missing_fields"],
        "bull_points": data["bull_points"],
        "bear_points": data["bear_points"],
        "raw_output": data["raw_output"],
    })


# ── Phase 1 agents ──────────────────────────────────────────────────────────

def test_fundamental_agent_complete(aapl_bundle):
    agent = FundamentalAgent()
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("fundamental")):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"
    assert result["phase"] == 1
    assert result["score"] is not None
    assert len(result["summary"]) > 0


def test_technical_agent_complete(aapl_bundle):
    agent = TechnicalAgent()
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("technical")):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"
    assert result["phase"] == 1


def test_sentiment_agent_complete(aapl_bundle):
    agent = SentimentAgent()
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("sentiment")):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"


def test_macro_agent_complete(aapl_bundle):
    agent = MacroAgent()
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("macro")):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"


def test_earnings_reviewer_complete(aapl_bundle):
    agent = EarningsReviewerAgent()
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("earnings_reviewer")):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"


# ── Phase 2 agents ──────────────────────────────────────────────────────────

def test_risk_manager_complete(aapl_bundle):
    agent = RiskManagerAgent()
    bundle = {**aapl_bundle, "phase1_summaries": {
        "fundamental": {"score": 7, "summary": "Good fundamentals"},
        "technical": {"score": 7, "summary": "Bullish setup"},
    }}
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("risk_manager")):
        result = agent.run(bundle, run_id=1)
    assert result["status"] == "complete"
    assert result["phase"] == 2


def test_thesis_validator_complete(aapl_bundle):
    agent = ThesisValidatorAgent()
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("thesis_validator")):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"


def test_financial_modeler_writes_excel(aapl_bundle, tmp_path, monkeypatch):
    import agents.financial_modeler as fm_mod
    monkeypatch.setattr(fm_mod, "REPORTS_DIR", tmp_path)
    agent = FinancialModelerAgent()
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("financial_modeler")):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"
    from pathlib import Path
    model_path = result["raw_output"].get("model_path")
    assert model_path is not None
    assert Path(model_path).exists()


# ── Phase 3 debate agents ───────────────────────────────────────────────────

def test_bull_agent_round_1(aapl_bundle):
    agent = BullAgent()
    bundle = {**aapl_bundle, "phase1_summaries": {}, "phase2_summaries": {}}
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("bull")):
        result = agent.run_round(bundle, run_id=1, round_number=1, bear_argument="")
    assert result["status"] == "complete"
    assert result["round"] == 1
    assert result["agent"] == "bull"
    assert isinstance(result["conviction"], int)


def test_bear_agent_round_1(aapl_bundle):
    agent = BearAgent()
    bundle = {**aapl_bundle, "phase1_summaries": {}, "phase2_summaries": {}}
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("bear")):
        result = agent.run_round(bundle, run_id=1, round_number=1, bull_argument="Some bull argument")
    assert result["status"] == "complete"
    assert result["round"] == 1


def test_debate_agents_raise_on_run(aapl_bundle):
    import pytest
    bull = BullAgent()
    bear = BearAgent()
    with pytest.raises(NotImplementedError):
        bull.run(aapl_bundle, run_id=1)
    with pytest.raises(NotImplementedError):
        bear.run(aapl_bundle, run_id=1)


# ── Phase 4 portfolio manager ───────────────────────────────────────────────

def test_portfolio_manager_complete(aapl_bundle):
    agent = PortfolioManagerAgent()
    bundle = {
        **aapl_bundle,
        "phase1_summaries": {"fundamental": {"score": 7, "summary": "ok", "raw_output": {}}},
        "phase2_summaries": {"risk_manager": {"score": 7, "summary": "ok", "raw_output": {"stop_loss": 171}}},
        "debate_transcript": [],
        "debate_contested": False,
        "debate_dominant_score": None,
    }
    with patch.object(agent, "_call_llm", return_value=_mock_llm_output("portfolio_manager")):
        result = agent.run(bundle, run_id=1)
    assert result["status"] == "complete"
    assert result["phase"] == 4
    assert result["score"] in range(1, 6)


# ── Cross-agent: manifest compliance ────────────────────────────────────────

def test_all_phase1_agents_return_minimal_on_empty_bundle():
    minimal_bundle = {
        "ticker": "FAKE",
        "run_id": 99,
        "data": {},
        "manifest": {
            "live_price": {"value": None, "source": None, "status": "missing", "note": None},
            "pe_ratio": {"value": None, "source": None, "status": "missing", "note": None},
        },
        "data_confidence": "minimal",
    }
    minimal_output = json.dumps({
        "score": 2,
        "data_confidence": "minimal",
        "summary": "Critical data missing.",
        "missing_fields": ["live_price", "pe_ratio"],
        "bull_points": [],
        "bear_points": [],
        "raw_output": {}
    })
    for AgentClass in [FundamentalAgent, TechnicalAgent, MacroAgent]:
        agent = AgentClass()
        with patch.object(agent, "_call_llm", return_value=minimal_output):
            result = agent.run(minimal_bundle, run_id=99)
        assert result["data_confidence"] == "minimal", f"{AgentClass.name} didn't return minimal"
