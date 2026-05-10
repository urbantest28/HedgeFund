#!/usr/bin/env python
"""Run a single agent in isolation against a frozen data bundle.

Usage:
    python debug/run_agent.py <agent_name> <run_id>

Agent names: fundamental, technical, sentiment, macro, earnings_reviewer,
             risk_manager, thesis_validator, financial_modeler,
             bull, bear, portfolio_manager
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEBUG_BUNDLES_DIR

AGENT_MAP = {
    "fundamental":      ("agents.fundamental",       "FundamentalAgent"),
    "technical":        ("agents.technical",         "TechnicalAgent"),
    "sentiment":        ("agents.sentiment",         "SentimentAgent"),
    "macro":            ("agents.macro",             "MacroAgent"),
    "earnings_reviewer":("agents.earnings_reviewer", "EarningsReviewerAgent"),
    "risk_manager":     ("agents.risk_manager",      "RiskManagerAgent"),
    "thesis_validator": ("agents.thesis_validator",  "ThesisValidatorAgent"),
    "financial_modeler":("agents.financial_modeler", "FinancialModelerAgent"),
    "bull":             ("agents.bull",              "BullAgent"),
    "bear":             ("agents.bear",              "BearAgent"),
    "portfolio_manager":("agents.portfolio_manager", "PortfolioManagerAgent"),
}


def run_agent(agent_name: str, run_id: int) -> None:
    bundle_path = DEBUG_BUNDLES_DIR / f"run_{run_id}_bundle.json"
    if not bundle_path.exists():
        print(f"[ERROR] Bundle not found: {bundle_path}")
        sys.exit(1)

    bundle = json.loads(bundle_path.read_text())

    if agent_name not in AGENT_MAP:
        print(f"[ERROR] Unknown agent: {agent_name}")
        print(f"Valid agents: {', '.join(AGENT_MAP)}")
        sys.exit(1)

    module_path, class_name = AGENT_MAP[agent_name]
    import importlib
    module = importlib.import_module(module_path)
    AgentClass = getattr(module, class_name)
    agent = AgentClass()

    print(f"[run_agent] Running {agent_name} against run_{run_id} bundle")
    print(f"[run_agent] Ticker: {bundle.get('ticker')} | Data confidence: {bundle.get('data_confidence')}")
    print()

    if agent_name in ("bull", "bear"):
        result = agent.run_round(bundle, run_id=run_id, round_number=1, bear_argument="")
    else:
        result = agent.run(bundle, run_id=run_id)

    print("=== Agent Output ===")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python debug/run_agent.py <agent_name> <run_id>")
        sys.exit(1)
    run_agent(sys.argv[1], int(sys.argv[2]))
