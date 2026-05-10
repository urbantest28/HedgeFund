import json
from agents.base_agent import BaseAgent
from config import PHASE2_PROVIDER, PHASE2_MODEL, DASHBOARD_TRADES_DB_PATH


def _load_active_theses() -> list[dict]:
    """Load active investment theses from dashboard trades.db (read-only)."""
    if not DASHBOARD_TRADES_DB_PATH or not DASHBOARD_TRADES_DB_PATH.exists():
        return []
    import sqlite3
    try:
        conn = sqlite3.connect(str(DASHBOARD_TRADES_DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, name, tickers, themes, sectors FROM theses WHERE status='active' LIMIT 20"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


class ThesisValidatorAgent(BaseAgent):
    name = "thesis_validator"
    phase = 2
    role_file = "thesis_validator.md"
    skill_files = ["thesis_matching.md"]
    provider = PHASE2_PROVIDER
    model = PHASE2_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "fundamentals": {
                "sector": data.get("fundamentals", {}).get("sector"),
                "industry": data.get("fundamentals", {}).get("industry"),
            },
            "active_theses": _load_active_theses(),
            "phase1_summaries": bundle.get("phase1_summaries", {}),
        }
        return f"Validate thesis alignment for this stock and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
