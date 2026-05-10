import json
import time
from agents.base_agent import BaseAgent, _extract_json
from config import DEBATE_PROVIDER, DEBATE_MODEL
from logger import get_logger

_log = get_logger("bull")


class BullAgent(BaseAgent):
    name = "bull"
    phase = 3
    role_file = "bull.md"
    skill_files = ["sentiment_scoring.md", "debate_protocol.md"]
    provider = DEBATE_PROVIDER
    model = DEBATE_MODEL

    def run_round(self, bundle: dict, run_id: int, round_number: int,
                  bear_argument: str = "") -> dict:
        """Run one debate round. Returns round-level result dict."""
        agent_log = _log.bind_run(run_id)
        t0 = time.monotonic()

        agent_summaries = {}
        agent_summaries.update(bundle.get("phase1_summaries", {}))
        agent_summaries.update(bundle.get("phase2_summaries", {}))

        context = f"Agent summaries from all prior phases:\n{json.dumps(agent_summaries, default=str)}\n\n"
        if bear_argument:
            context += f"Bear's previous argument (Round {round_number - 1}):\n{bear_argument}\n\n"
        context += f"This is Round {round_number}. Make your {'opening argument' if round_number == 1 else 'response'}."

        agent_log.info(f"Bull round {round_number} started")
        try:
            raw = self._call_llm(context)
            parsed = _extract_json(raw)
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.info(f"Bull round {round_number} | conviction: {parsed.get('conviction')} | duration: {duration_ms}ms")
            return {
                "round": round_number,
                "agent": "bull",
                "run_id": run_id,
                "argument": parsed.get("argument", ""),
                "conviction": parsed.get("conviction", 5),
                "concessions": parsed.get("concessions", []),
                "status": "complete",
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.error(f"Bull round {round_number} failed: {e}")
            return {
                "round": round_number,
                "agent": "bull",
                "run_id": run_id,
                "argument": f"[Bull agent failed: {e}]",
                "conviction": 5,
                "concessions": [],
                "status": "failed",
            }

    def run(self, bundle: dict, run_id: int) -> dict:
        raise NotImplementedError("Use run_round() for debate agents")
