"""End-to-end test of the full 4-phase pipeline against frozen AAPL fixtures.

No real API calls, no real LLM calls. Verifies:
  - All key SSE events emitted (fetch_complete, 4 phase_complete, verdict, complete)
  - No abort
  - HTML report file actually generated on disk
  - Watchlist entry written (verdict is WATCHLIST in fixture)
"""
import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from pipeline.orchestrator import stream_analysis

FIXTURES = Path(__file__).parent.parent / "fixtures"
SAMPLES = FIXTURES / "sample_agent_outputs"


def _load(name: str) -> dict:
    with open(SAMPLES / f"{name}.json") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_full_pipeline_aapl(tmp_path, monkeypatch):
    """Full pipeline against frozen AAPL fixture — all phases complete,
    report generated, watchlist entry written."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr("reports.generator.REPORTS_DIR", reports_dir)

    with open(FIXTURES / "aapl_data_bundle.json") as f:
        bundle = json.load(f)

    db = MagicMock()
    db.create_run.return_value = 1
    db.get_agent_outputs.return_value = []
    db.get_debate_rounds.return_value = []

    phase1_results = [_load(n) for n in
                      ["fundamental", "technical", "sentiment", "macro", "earnings_reviewer"]]
    phase2_results = [_load(n) for n in
                      ["risk_manager", "thesis_validator", "financial_modeler"]]
    bull_result = _load("bull")
    bear_result = _load("bear")
    pm_result = _load("portfolio_manager")

    async def mock_phase(agent_classes, *args, **kwargs):
        names = [c.__name__ for c in agent_classes]
        if any("Fundamental" in n for n in names):
            return phase1_results
        return phase2_results

    # Bull/Bear agents in the debate are instantiated and their run_round() is
    # called via loop.run_in_executor. Patch the classes so run_round is a sync
    # MagicMock returning the fixture payload.
    mock_bull = MagicMock()
    mock_bull.run_round = MagicMock(return_value=bull_result)
    mock_bear = MagicMock()
    mock_bear.run_round = MagicMock(return_value=bear_result)

    # PortfolioManagerAgent is instantiated inside the orchestrator and invoked
    # via loop.run_in_executor(None, pm.run, ...) — patch the class.
    mock_pm = MagicMock()
    mock_pm.run = MagicMock(return_value=pm_result)

    with patch("pipeline.orchestrator.DataAggregator") as MockAgg, \
         patch("pipeline.orchestrator._run_phase_parallel", side_effect=mock_phase), \
         patch("pipeline.orchestrator.PortfolioManagerAgent", return_value=mock_pm), \
         patch("pipeline.debate.BullAgent", return_value=mock_bull), \
         patch("pipeline.debate.BearAgent", return_value=mock_bear), \
         patch("pipeline.orchestrator._save_bundle_snapshot"):
        MockAgg.return_value.fetch_all = MagicMock(return_value=bundle)

        events = []
        async for sse_line in stream_analysis("AAPL", db):
            events.append(sse_line)

    # Parse SSE events
    event_types = []
    parsed = []
    for line in events:
        assert line.startswith("data: "), f"bad SSE line: {line!r}"
        data = json.loads(line[len("data: "):].rstrip())
        parsed.append(data)
        if isinstance(data, dict) and "event" in data:
            event_types.append(data["event"])

    # Key event assertions
    assert "run_start" in event_types
    assert "fetch_complete" in event_types
    # Phases 1-3 emit phase_complete; Phase 4 (PM) does not — it emits
    # agent_complete + verdict + complete instead.
    assert event_types.count("phase_complete") == 3, \
        f"expected 3 phase_complete events, got {event_types.count('phase_complete')}: {event_types}"
    assert "report_ready" in event_types
    assert "verdict" in event_types
    assert "complete" in event_types
    assert "abort" not in event_types
    assert "error" not in event_types

    # Verdict payload should reflect fixture
    verdict_evt = next(e for e in parsed if e.get("event") == "verdict")
    assert verdict_evt["verdict"] == "WATCHLIST"
    assert verdict_evt["tier"] == "satellite"

    # Report file actually written
    reports = list(reports_dir.glob("AAPL_*.html"))
    assert len(reports) == 1, f"expected 1 report, got {reports}"
    assert reports[0].stat().st_size > 0

    # Watchlist entry written
    db.save_watchlist_entry.assert_called_once()
