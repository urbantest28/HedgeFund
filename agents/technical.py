import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class TechnicalAgent(BaseAgent):
    name = "technical"
    phase = 1
    role_file = "technical_analyst.md"
    skill_files = ["chart_pattern_recognition.md", "momentum_indicators.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "ohlcv": data.get("ohlcv"),
            "live_price": data.get("live_price"),
        }
        return f"Analyse this technical data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
