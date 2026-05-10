import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class SentimentAgent(BaseAgent):
    name = "sentiment"
    phase = 1
    role_file = "sentiment_analyst.md"
    skill_files = ["sentiment_scoring.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "news": data.get("news"),
            "reddit": data.get("reddit"),
        }
        return f"Analyse this sentiment data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
