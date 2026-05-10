import json
from agents.base_agent import BaseAgent
from config import PHASE2_PROVIDER, PHASE2_MODEL, DASHBOARD_TRADES_DB_PATH


class RiskManagerAgent(BaseAgent):
    name = "risk_manager"
    phase = 2
    role_file = "risk_manager.md"
    skill_files = ["position_sizing.md", "financial_ratio_analysis.md"]
    provider = PHASE2_PROVIDER
    model = PHASE2_MODEL

    def _get_existing_holdings(self) -> list[dict]:
        """Read existing holdings from dashboard trades.db (read-only)."""
        if not DASHBOARD_TRADES_DB_PATH or not DASHBOARD_TRADES_DB_PATH.exists():
            return []
        import sqlite3
        try:
            conn = sqlite3.connect(str(DASHBOARD_TRADES_DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT ticker, value FROM trades WHERE status='open' LIMIT 20"
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "live_price": data.get("live_price"),
            "ohlcv": data.get("ohlcv"),
            "phase1_summaries": bundle.get("phase1_summaries", {}),
            "existing_holdings": self._get_existing_holdings(),
        }
        return f"Assess risk and position sizing for this stock and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
