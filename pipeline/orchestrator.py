"""
Async pipeline orchestrator.

Runs the 4-phase hedge fund pipeline, emitting SSE events via an async queue.
Call `stream_analysis()` from the FastAPI endpoint; it returns an async generator
of JSON-serialisable event dicts.
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from agents.fundamental import FundamentalAgent
from agents.technical import TechnicalAgent
from agents.sentiment import SentimentAgent
from agents.macro import MacroAgent
from agents.earnings_reviewer import EarningsReviewerAgent
from agents.risk_manager import RiskManagerAgent
from agents.thesis_validator import ThesisValidatorAgent
from agents.financial_modeler import FinancialModelerAgent
from agents.portfolio_manager import PortfolioManagerAgent
from data.aggregator import DataAggregator
from db.database import Database
from pipeline.debate import run_debate
from config import BASE_DIR, DEBUG_BUNDLES_DIR
from logger import get_logger

_log = get_logger("orchestrator")

PHASE1_AGENT_CLASSES = [
    FundamentalAgent,
    TechnicalAgent,
    SentimentAgent,
    MacroAgent,
    EarningsReviewerAgent,
]
PHASE2_AGENT_CLASSES = [
    RiskManagerAgent,
    ThesisValidatorAgent,
    FinancialModelerAgent,
]


def _save_bundle_snapshot(run_id: int, bundle: dict) -> None:
    path = DEBUG_BUNDLES_DIR / f"run_{run_id}_bundle.json"
    path.write_text(json.dumps(bundle, default=str), encoding="utf-8")


async def _run_agent_async(agent_instance, bundle: dict, run_id: int,
                           loop: asyncio.AbstractEventLoop) -> dict:
    return await loop.run_in_executor(None, agent_instance.run, bundle, run_id)


async def _run_phase_parallel(
    agent_classes: list,
    bundle: dict,
    run_id: int,
    db: Database,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue,
    phase: int,
) -> list[dict]:
    """Run a list of agent classes in parallel, emit events, save outputs to DB."""
    agents = [cls() for cls in agent_classes]
    agent_log = _log.bind_run(run_id)
    agent_log.info(f"Phase {phase} started | agents: {[a.name for a in agents]}")
    await queue.put({
        "event": "phase_start",
        "phase": phase,
        "agents": [a.name for a in agents],
    })

    tasks = [_run_agent_async(a, bundle, run_id, loop) for a in agents]
    results = []

    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.append(result)

        db.save_agent_output(
            run_id=run_id,
            agent=result["agent"],
            phase=result["phase"],
            score=result["score"],
            summary=result["summary"],
            raw_output=json.dumps(result["raw_output"], default=str),
            data_confidence=result["data_confidence"],
            duration_ms=result["duration_ms"],
            status=result["status"],
        )

        await queue.put({
            "event": "agent_complete",
            "phase": phase,
            "agent": result["agent"],
            "score": result["score"],
            "data_confidence": result["data_confidence"],
            "status": result["status"],
        })
        agent_log.info(
            f"Phase {phase} | {result['agent']} complete "
            f"| score: {result['score']} | confidence: {result['data_confidence']}"
        )

    return results


def _build_summaries(results: list[dict]) -> dict:
    return {
        r["agent"]: {
            "score": r["score"],
            "summary": r["summary"],
            "data_confidence": r["data_confidence"],
            "missing_fields": r["missing_fields"],
            "bull_points": r["bull_points"],
            "bear_points": r["bear_points"],
            "raw_output": r["raw_output"],
        }
        for r in results
    }


async def _run_pipeline(
    ticker: str,
    run_id: int,
    db: Database,
    queue: asyncio.Queue,
    transcript_path: Optional[Path] = None,
) -> None:
    """Full 4-phase pipeline. Posts events to queue; puts a sentinel when done."""
    loop = asyncio.get_event_loop()
    agent_log = _log.bind_run(run_id)
    t_start = time.monotonic()

    try:
        # ── Fetch data ───────────────────────────────────────────────────────────
        await queue.put({"event": "fetch_start", "ticker": ticker})
        agent_log.info(f"Fetching data for {ticker}")
        aggregator = DataAggregator(ticker, run_id)
        bundle = await loop.run_in_executor(None, aggregator.fetch_all)
        bundle["ticker"] = ticker

        if transcript_path and transcript_path.exists():
            bundle["earnings_transcript_path"] = str(transcript_path)

        _save_bundle_snapshot(run_id, bundle)
        await queue.put({"event": "fetch_complete", "ticker": ticker,
                         "fields": len(bundle)})

        # ── Phase 1 ──────────────────────────────────────────────────────────────
        phase1_results = await _run_phase_parallel(
            PHASE1_AGENT_CLASSES, bundle, run_id, db, loop, queue, phase=1
        )

        # Abort rule: 2+ agents with minimal confidence
        minimal_agents = [r["agent"] for r in phase1_results
                          if r["data_confidence"] == "minimal"]
        if len(minimal_agents) >= 2:
            agent_log.warning(f"Abort — minimal confidence: {minimal_agents}")
            db.update_run(run_id, status="failed")
            await queue.put({
                "event": "abort",
                "reason": "2+ Phase 1 agents returned minimal data confidence",
                "agents": minimal_agents,
            })
            return

        bundle["phase1_summaries"] = _build_summaries(phase1_results)
        await queue.put({
            "event": "phase_complete",
            "phase": 1,
            "duration_ms": int((time.monotonic() - t_start) * 1000),
        })

        # ── Phase 2 ──────────────────────────────────────────────────────────────
        phase2_results = await _run_phase_parallel(
            PHASE2_AGENT_CLASSES, bundle, run_id, db, loop, queue, phase=2
        )
        bundle["phase2_summaries"] = _build_summaries(phase2_results)
        await queue.put({
            "event": "phase_complete",
            "phase": 2,
            "duration_ms": int((time.monotonic() - t_start) * 1000),
        })

        # ── Phase 3 — Debate ─────────────────────────────────────────────────────
        await queue.put({"event": "phase_start", "phase": 3, "agents": ["bull", "bear"]})
        debate_gen = run_debate(bundle, run_id, db, loop)
        debate_meta = {}
        async for event in debate_gen:
            await queue.put(event)
            if event["event"] == "debate_complete":
                debate_meta = event

        db.update_run(
            run_id,
            bull_score=debate_meta.get("bull_score"),
            bear_score=debate_meta.get("bear_score"),
            contested=1 if debate_meta.get("contested") else 0,
        )
        await queue.put({"event": "phase_complete", "phase": 3,
                         "duration_ms": int((time.monotonic() - t_start) * 1000)})

        # ── Phase 4 — Portfolio Manager ──────────────────────────────────────────
        await queue.put({"event": "phase_start", "phase": 4,
                         "agents": ["portfolio_manager"]})
        pm = PortfolioManagerAgent()
        pm_result = await loop.run_in_executor(None, pm.run, bundle, run_id)

        db.save_agent_output(
            run_id=run_id,
            agent=pm_result["agent"],
            phase=pm_result["phase"],
            score=pm_result["score"],
            summary=pm_result["summary"],
            raw_output=json.dumps(pm_result["raw_output"], default=str),
            data_confidence=pm_result["data_confidence"],
            duration_ms=pm_result["duration_ms"],
            status=pm_result["status"],
        )
        await queue.put({
            "event": "agent_complete",
            "phase": 4,
            "agent": "portfolio_manager",
            "score": pm_result["score"],
            "data_confidence": pm_result["data_confidence"],
            "status": pm_result["status"],
        })

        raw = pm_result["raw_output"]
        verdict = raw.get("verdict", "AVOID").upper()
        score = pm_result["score"]
        tier = raw.get("tier", "satellite")
        entry_low = raw.get("entry_low") or raw.get("entry_range", {}).get("low")
        entry_high = raw.get("entry_high") or raw.get("entry_range", {}).get("high")
        stop_loss = raw.get("stop_loss")
        target_price = raw.get("target_price")
        contested = debate_meta.get("contested", False)

        db.update_run(
            run_id,
            status="contested" if contested and verdict == "WATCHLIST" else
                   ("complete" if verdict == "WATCHLIST" else "failed"),
            verdict=verdict.lower(),
            score=score,
            tier=tier,
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=stop_loss,
            target_price=target_price,
        )

        # Write watchlist entry if verdict is WATCHLIST
        if verdict == "WATCHLIST" and score:
            db.save_watchlist_entry(
                run_id=run_id,
                ticker=ticker,
                added_date=datetime.now().strftime("%Y-%m-%d"),
                score=score,
                tier=tier,
                entry_low=entry_low or 0.0,
                entry_high=entry_high or 0.0,
                stop_loss=stop_loss or 0.0,
                target_price=target_price or 0.0,
                verdict_summary=pm_result["summary"][:500],
                contested=1 if contested else 0,
            )
            agent_log.info(f"Watchlist entry written | ticker: {ticker} | score: {score} | tier: {tier}")

        total_ms = int((time.monotonic() - t_start) * 1000)
        await queue.put({
            "event": "verdict",
            "score": score,
            "verdict": verdict,
            "tier": tier,
            "contested": contested,
            "entry_low": entry_low,
            "entry_high": entry_high,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "reasoning": pm_result["summary"],
            "expected_returns": raw.get("expected_returns"),
            "key_risks": raw.get("key_risks", []),
            "key_catalysts": raw.get("key_catalysts", []),
            "review_date": raw.get("review_date"),
        })
        await queue.put({
            "event": "complete",
            "run_id": run_id,
            "duration_ms": total_ms,
        })
        agent_log.info(f"Pipeline complete | duration: {total_ms}ms | verdict: {verdict} | score: {score}")

    except Exception as exc:
        _log.bind_run(run_id).error(f"Pipeline error: {exc}")
        db.update_run(run_id, status="failed")
        await queue.put({"event": "error", "message": str(exc)})
    finally:
        await queue.put(None)  # sentinel


async def stream_analysis(
    ticker: str,
    db: Database,
    transcript_path: Optional[Path] = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator yielding SSE-formatted strings.
    Creates a run, starts the pipeline task, streams events until done.
    """
    run_id = db.create_run(ticker, datetime.now().strftime("%Y-%m-%d"))
    db.update_run(run_id, status="running")

    queue: asyncio.Queue = asyncio.Queue()
    asyncio.create_task(_run_pipeline(ticker, run_id, db, queue, transcript_path))

    # Emit the run_id first so the frontend can track it
    yield f"data: {json.dumps({'event': 'run_start', 'run_id': run_id, 'ticker': ticker})}\n\n"

    while True:
        event = await queue.get()
        if event is None:
            break
        yield f"data: {json.dumps(event, default=str)}\n\n"


async def stream_resume(
    run_id: int,
    db: Database,
) -> AsyncGenerator[str, None]:
    """Resume a paused run from its checkpoint."""
    run = db.get_run(run_id)
    if not run:
        yield f"data: {json.dumps({'event': 'error', 'message': f'Run {run_id} not found'})}\n\n"
        return

    ticker = run["ticker"]
    checkpoint = db.get_checkpoint(run_id)
    if not checkpoint:
        yield f"data: {json.dumps({'event': 'error', 'message': 'No checkpoint found'})}\n\n"
        return

    db.update_run(run_id, status="running")

    # Look for any uploaded files for this run
    upload_dir = BASE_DIR / "uploads" / ticker / f"run_{run_id}"
    transcript_path = next(
        (f for f in upload_dir.glob("*.pdf") if f.name != "NEEDED.md"),
        None
    ) if upload_dir.exists() else None

    queue: asyncio.Queue = asyncio.Queue()
    asyncio.create_task(_run_pipeline(ticker, run_id, db, queue, transcript_path))

    yield f"data: {json.dumps({'event': 'run_resume', 'run_id': run_id, 'ticker': ticker})}\n\n"

    while True:
        event = await queue.get()
        if event is None:
            break
        yield f"data: {json.dumps(event, default=str)}\n\n"
