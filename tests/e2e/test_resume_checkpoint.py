"""End-to-end test of `stream_resume` — verifies that when the checkpoint says
Phase 1 is complete, the resumed pipeline skips Phase 1 and continues from
Phase 2.
"""
import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from pipeline.orchestrator import stream_resume

FIXTURES = Path(__file__).parent.parent / "fixtures"
SAMPLES = FIXTURES / "sample_agent_outputs"


def _load(name: str) -> dict:
    with open(SAMPLES / f"{name}.json") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_resume_from_phase2_checkpoint(tmp_path, monkeypatch):
    """Run paused after Phase 1 → resume → completes from Phase 2 onwards."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr("reports.generator.REPORTS_DIR", reports_dir)

    with open(FIXTURES / "aapl_data_bundle.json") as f:
        bundle = json.load(f)

    phase1_results = [_load(n) for n in
                      ["fundamental", "technical", "sentiment", "macro",
                       "earnings_reviewer"]]
    phase2_results = [_load(n) for n in
                      ["risk_manager", "thesis_validator", "financial_modeler"]]
    bull_result = _load("bull")
    bear_result = _load("bear")
    pm_result = _load("portfolio_manager")

    # Write the bundle snapshot to a path the resume logic can read.
    bundle_path = tmp_path / "run_7_bundle.json"
    with open(bundle_path, "w") as f:
        json.dump(bundle, f)

    db = MagicMock()
    db.get_run.return_value = {"id": 7, "run_id": 7, "ticker": "AAPL",
                                "status": "paused"}
    # Checkpoint in the richer shape the test contract describes.
    db.get_checkpoint.return_value = {
        "completed_phase": 1,
        "phase1_results": phase1_results,
        "bundle_path": str(bundle_path),
    }
    db.get_agent_outputs.return_value = []
    db.get_debate_rounds.return_value = []

    # Track which phases _run_phase_parallel was called for.
    phase_calls = []

    async def mock_phase(agent_classes, *args, **kwargs):
        names = [c.__name__ for c in agent_classes]
        phase_calls.append(names)
        if any("Fundamental" in n for n in names):
            return phase1_results
        return phase2_results

    mock_bull = MagicMock()
    mock_bull.run_round = MagicMock(return_value=bull_result)
    mock_bear = MagicMock()
    mock_bear.run_round = MagicMock(return_value=bear_result)

    mock_pm = MagicMock()
    mock_pm.run = MagicMock(return_value=pm_result)

    with patch("pipeline.orchestrator._run_phase_parallel",
               side_effect=mock_phase), \
         patch("pipeline.orchestrator.PortfolioManagerAgent",
               return_value=mock_pm), \
         patch("pipeline.debate.BullAgent", return_value=mock_bull), \
         patch("pipeline.debate.BearAgent", return_value=mock_bear), \
         patch("pipeline.orchestrator._save_bundle_snapshot"), \
         patch("pipeline.orchestrator.DataAggregator") as MockAgg:
        # If DataAggregator is invoked at all, that means Phase 1 ran — fail
        # loudly rather than silently returning a bundle.
        MockAgg.side_effect = AssertionError(
            "DataAggregator was instantiated during resume — Phase 1 re-ran"
        )

        events = []
        async for sse_line in stream_resume(7, db):
            events.append(sse_line)

    # Phase 1 should NOT have been re-run.
    phase1_re_run = any(
        any("Fundamental" in n for n in call) for call in phase_calls
    )
    assert not phase1_re_run, (
        f"Phase 1 was re-run; should resume from Phase 2. Calls: {phase_calls}"
    )

    # Phase 2 SHOULD have run.
    phase2_ran = any(
        any("RiskManager" in n for n in call) for call in phase_calls
    )
    assert phase2_ran, f"Phase 2 did not run. Calls: {phase_calls}"

    # Parse SSE events.
    event_types = []
    parsed = []
    for line in events:
        assert line.startswith("data: "), f"bad SSE line: {line!r}"
        data = json.loads(line[len("data: "):].rstrip())
        parsed.append(data)
        if isinstance(data, dict) and "event" in data:
            event_types.append(data["event"])

    # The pipeline completed: verdict + complete events present.
    assert "verdict" in event_types, f"events: {event_types}"
    assert "complete" in event_types, f"events: {event_types}"
    assert "error" not in event_types, f"events: {event_types}"
    assert "abort" not in event_types, f"events: {event_types}"

    # Resume start event carries the start_phase.
    resume_evt = next(
        (e for e in parsed if e.get("event") == "run_resume"), None
    )
    assert resume_evt is not None
    assert resume_evt.get("start_phase") == 2
