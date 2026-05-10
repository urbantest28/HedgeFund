import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class EarningsReviewerAgent(BaseAgent):
    name = "earnings_reviewer"
    phase = 1
    role_file = "earnings_reviewer.md"
    skill_files = ["earnings_transcript_analysis.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "earnings": data.get("earnings"),
            "income_statement": data.get("income_statement"),
            "sec_filings": data.get("sec_filings"),
            "analyst_ratings": data.get("analyst_ratings"),
        }
        return f"Analyse this earnings data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
