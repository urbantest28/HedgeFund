import json
import time
from agents.base_agent import BaseAgent, _extract_json
from config import DEBATE_PROVIDER, DEBATE_MODEL
from logger import get_logger

_log = get_logger("bear")


class BearAgent(BaseAgent):
    name = "bear"
    phase = 3
    role_file = "bear.md"
    skill_files = ["sentiment_scoring.md", "debate_protocol.md"]
    provider = DEBATE_PROVIDER
    model = DEBATE_MODEL

    def run_round(self, bundle: dict, run_id: int, round_number: int,
                  bull_argument: str = "") -> dict:
        """Run one debate round. Returns round-level result dict."""
        agent_log = _log.bind_run(run_id)
        t0 = time.monotonic()

        agent_summaries = {}
        agent_summaries.update(bundle.get("phase1_summaries", {}))
        agent_summaries.update(bundle.get("phase2_summaries", {}))

        context = f"Agent summaries from all prior phases:\n{json.dumps(agent_summaries, default=str)}\n\n"
        if bull_argument:
            context += f"Bull's argument (Round {round_number}):\n{bull_argument}\n\n"
        context += f"This is Round {round_number}. {'Counter this opening argument.' if round_number == 1 else 'Continue your counter-argument.'}"

        agent_log.info(f"Bear round {round_number} started")
        try:
            raw = self._call_llm(context)
            parsed = _extract_json(raw)
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.info(f"Bear round {round_number} | conviction: {parsed.get('conviction')} | duration: {duration_ms}ms")
            return {
                "round": round_number,
                "agent": "bear",
                "run_id": run_id,
                "argument": parsed.get("argument", ""),
                "conviction": parsed.get("conviction", 5),
                "concessions": parsed.get("concessions", []),
                "status": "complete",
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.error(f"Bear round {round_number} failed: {e}")
            return {
                "round": round_number,
                "agent": "bear",
                "run_id": run_id,
                "argument": f"[Bear agent failed: {e}]",
                "conviction": 5,
                "concessions": [],
                "status": "failed",
            }

    def run(self, bundle: dict, run_id: int) -> dict:
        raise NotImplementedError("Use run_round() for debate agents")
