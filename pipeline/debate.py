"""Bull/Bear debate loop — Phase 3."""
import asyncio
from typing import AsyncGenerator

from agents.bull import BullAgent
from agents.bear import BearAgent
from db.database import Database
from logger import get_logger

MAX_ROUNDS = 4
CONSENSUS_GAP = 2

_log = get_logger("debate")


async def run_debate(
    bundle: dict,
    run_id: int,
    db: Database,
    loop: asyncio.AbstractEventLoop,
) -> AsyncGenerator[dict, None]:
    """
    Async generator yielding SSE-ready event dicts.
    Runs up to MAX_ROUNDS; ends early on consensus (gap <= CONSENSUS_GAP).
    """
    bull = BullAgent()
    bear = BearAgent()
    agent_log = _log.bind_run(run_id)

    transcript: list[dict] = []
    bull_argument = ""
    bear_argument = ""
    final_bull_conviction = 5
    final_bear_conviction = 5
    contested = False

    for round_num in range(1, MAX_ROUNDS + 1):
        agent_log.info(f"Debate round {round_num} started")

        # Bull goes first each round
        bull_result = await loop.run_in_executor(
            None, lambda r=round_num, ba=bear_argument: bull.run_round(bundle, run_id, r, ba)
        )
        bull_argument = bull_result["argument"]
        bull_conviction = bull_result["conviction"]

        # Bear responds
        bear_result = await loop.run_in_executor(
            None, lambda r=round_num, ba=bull_argument: bear.run_round(bundle, run_id, r, ba)
        )
        bear_argument = bear_result["argument"]
        bear_conviction = bear_result["conviction"]

        final_bull_conviction = bull_conviction
        final_bear_conviction = bear_conviction

        gap = abs(bull_conviction - bear_conviction)
        agent_log.info(
            f"Round {round_num} | Bull: {bull_conviction} | Bear: {bear_conviction} | gap: {gap}"
        )

        # Save to DB
        db.save_debate_round(
            run_id=run_id,
            round_number=round_num,
            bull_argument=bull_argument,
            bear_argument=bear_argument,
            bull_conviction=bull_conviction,
            bear_conviction=bear_conviction,
        )

        round_entry = {
            "round": round_num,
            "bull_argument": bull_argument,
            "bear_argument": bear_argument,
            "bull_conviction": bull_conviction,
            "bear_conviction": bear_conviction,
            "gap": gap,
        }
        transcript.append(round_entry)

        event = {
            "event": "debate_round",
            "round": round_num,
            "bull_conviction": bull_conviction,
            "bear_conviction": bear_conviction,
            "gap": gap,
            "bull_argument": bull_argument[:500],  # truncated for SSE
            "bear_argument": bear_argument[:500],
        }
        yield event

        if gap <= CONSENSUS_GAP:
            contested = False
            agent_log.info(f"Consensus at Round {round_num} | gap: {gap}")
            break
    else:
        gap = abs(final_bull_conviction - final_bear_conviction)
        if gap > CONSENSUS_GAP:
            contested = True
            agent_log.info(f"Contested after {MAX_ROUNDS} rounds | gap: {gap}")

    dominant_score = (
        final_bull_conviction if final_bull_conviction >= final_bear_conviction
        else final_bear_conviction
    )

    yield {
        "event": "debate_complete",
        "contested": contested,
        "rounds": len(transcript),
        "bull_score": final_bull_conviction,
        "bear_score": final_bear_conviction,
        "dominant_score": dominant_score,
    }

    # Attach full transcript and debate metadata to bundle for PM
    bundle["debate_transcript"] = transcript
    bundle["debate_contested"] = contested
    bundle["debate_dominant_score"] = dominant_score
