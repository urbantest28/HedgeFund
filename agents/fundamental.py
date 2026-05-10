import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class FundamentalAgent(BaseAgent):
    name = "fundamental"
    phase = 1
    role_file = "fundamental_analyst.md"
    skill_files = ["financial_ratio_analysis.md", "dcf_valuation.md", "relative_valuation.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "fundamentals": data.get("fundamentals"),
            "income_statement": data.get("income_statement"),
            "balance_sheet": data.get("balance_sheet"),
            "cash_flow": data.get("cash_flow"),
            "peers": data.get("peers"),
            "live_price": data.get("live_price"),
            "analyst_ratings": data.get("analyst_ratings"),
        }
        return f"Analyse this fundamental data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
