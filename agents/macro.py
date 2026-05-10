import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class MacroAgent(BaseAgent):
    name = "macro"
    phase = 1
    role_file = "macro_analyst.md"
    skill_files = ["macro_regime_analysis.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "macro": data.get("macro"),
            "fundamentals": {
                "sector": data.get("fundamentals", {}).get("sector"),
                "industry": data.get("fundamentals", {}).get("industry"),
                "international_revenue_pct": data.get("fundamentals", {}).get("international_revenue_pct"),
            },
        }
        return f"Analyse this macro data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
