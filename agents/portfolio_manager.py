import json
import time
from agents.base_agent import BaseAgent, _extract_json
from config import PM_PROVIDER, PM_MODEL
from logger import get_logger

_log = get_logger("pm")

AGENT_WEIGHTS = {
    "fundamental": 0.20,
    "technical": 0.15,
    "sentiment": 0.10,
    "macro": 0.10,
    "earnings_reviewer": 0.15,
    "risk_manager": 0.10,
    "thesis_validator": 0.10,
    "financial_modeler": 0.10,
}


class PortfolioManagerAgent(BaseAgent):
    name = "portfolio_manager"
    phase = 4
    role_file = "portfolio_manager.md"
    skill_files = [
        "financial_ratio_analysis.md", "dcf_valuation.md", "relative_valuation.md",
        "chart_pattern_recognition.md", "momentum_indicators.md", "sentiment_scoring.md",
        "macro_regime_analysis.md", "position_sizing.md", "thesis_matching.md",
        "earnings_transcript_analysis.md", "debate_protocol.md",
    ]
    provider = PM_PROVIDER
    model = PM_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        summaries = {}
        for phase_key in ("phase1_summaries", "phase2_summaries"):
            summaries.update(bundle.get(phase_key, {}))

        context = {
            "ticker": bundle.get("ticker"),
            "agent_weights": AGENT_WEIGHTS,
            "agent_summaries": summaries,
            "debate_transcript": bundle.get("debate_transcript", []),
            "debate_contested": bundle.get("debate_contested", False),
            "debate_dominant_score": bundle.get("debate_dominant_score"),
            "financial_modeler_returns": summaries.get("financial_modeler", {}).get("raw_output", {}).get("expected_returns"),
            "risk_manager_stop": summaries.get("risk_manager", {}).get("raw_output", {}).get("stop_loss"),
            "thesis_match": summaries.get("thesis_validator", {}).get("raw_output"),
        }
        return f"Synthesise all agent summaries and debate transcript into a final verdict. Respond with the required JSON:\n\n{json.dumps(context, default=str)}"

    def run(self, bundle: dict, run_id: int) -> dict:
        agent_log = _log.bind_run(run_id)
        t0 = time.monotonic()
        user_prompt = self._build_user_prompt(bundle)

        agent_log.info(f"PM synthesis started | provider: {self.provider} | model: {self.model}")
        try:
            raw_text = self._call_llm(user_prompt)
            parsed = _extract_json(raw_text)
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.info(
                f"PM complete | score: {parsed.get('score')} | verdict: {parsed.get('verdict')} "
                f"| tier: {parsed.get('tier')} | duration: {duration_ms}ms"
            )
            return {
                "agent": "portfolio_manager",
                "run_id": run_id,
                "phase": 4,
                "score": parsed.get("score"),
                "summary": parsed.get("reasoning", "")[:600],
                "data_confidence": "full",
                "missing_fields": [],
                "bull_points": [],
                "bear_points": [],
                "raw_output": parsed,
                "duration_ms": duration_ms,
                "status": "complete",
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.error(f"PM failed: {e}")
            return {
                "agent": "portfolio_manager",
                "run_id": run_id,
                "phase": 4,
                "score": None,
                "summary": f"Portfolio Manager failed: {e}",
                "data_confidence": "minimal",
                "missing_fields": [],
                "bull_points": [],
                "bear_points": [],
                "raw_output": {"error": str(e)},
                "duration_ms": duration_ms,
                "status": "failed",
            }
