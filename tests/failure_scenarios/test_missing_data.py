import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pipeline.orchestrator import _run_pipeline

@pytest.mark.asyncio
async def test_two_minimal_agents_aborts_pipeline():
    """When 2+ Phase 1 agents return data_confidence=minimal, pipeline emits abort and does not run Phase 2."""
    minimal = {"agent": "test", "phase": 1, "score": 1, "data_confidence": "minimal",
               "status": "complete", "summary": "", "duration_ms": 100,
               "bull_points": [], "bear_points": [], "missing_fields": ["x"],
               "raw_output": {}}
    full = {**minimal, "data_confidence": "full", "score": 7, "missing_fields": []}
    phase1 = [minimal, minimal, full, full, full]

    queue = asyncio.Queue()
    db = MagicMock()
    phase2_called = MagicMock()

    async def mock_phase_parallel(agent_classes, *args, **kwargs):
        if any(c.__name__.startswith("Risk") for c in agent_classes):
            phase2_called()
            return []
        return phase1

    with patch("pipeline.orchestrator.DataAggregator") as MockAgg, \
         patch("pipeline.orchestrator._run_phase_parallel", side_effect=mock_phase_parallel):
        MockAgg.return_value.fetch_all = MagicMock(return_value={"ticker": "TEST"})
        await _run_pipeline("TEST", 1, db, queue, None)

    events = []
    while not queue.empty():
        e = await queue.get()
        if e is not None:
            events.append(e)

    assert any(e.get("event") == "abort" for e in events)
    phase2_called.assert_not_called()
    # Orchestrator marks failed via db.update_run(run_id, status="failed")
    failed_calls = [c for c in db.update_run.call_args_list
                    if c.kwargs.get("status") == "failed"]
    assert failed_calls, f"Expected db.update_run(..., status='failed'); got {db.update_run.call_args_list}"

@pytest.mark.asyncio
async def test_one_minimal_agent_does_not_abort():
    """Single minimal agent does NOT trigger abort."""
    minimal = {"agent": "test", "phase": 1, "score": 1, "data_confidence": "minimal",
               "status": "complete", "summary": "", "duration_ms": 100,
               "bull_points": [], "bear_points": [], "missing_fields": ["x"],
               "raw_output": {}}
    full = {**minimal, "data_confidence": "full", "score": 7, "missing_fields": []}
    phase1 = [minimal, full, full, full, full]

    queue = asyncio.Queue()
    db = MagicMock()
    phase2_called = MagicMock()

    async def mock_phase_parallel(agent_classes, *args, **kwargs):
        if any(c.__name__.startswith("Risk") for c in agent_classes):
            phase2_called()
            return []
        return phase1

    pm_result = {"agent": "portfolio_manager",
                 "raw_output": {"verdict": "AVOID", "score": 4, "tier": "Sell"},
                 "score": 4, "status": "complete", "phase": 4,
                 "data_confidence": "full", "summary": "", "duration_ms": 100,
                 "bull_points": [], "bear_points": [], "missing_fields": []}

    with patch("pipeline.orchestrator.DataAggregator") as MockAgg, \
         patch("pipeline.orchestrator._run_phase_parallel", side_effect=mock_phase_parallel), \
         patch("pipeline.orchestrator.run_debate") as mock_debate, \
         patch("pipeline.orchestrator.PortfolioManagerAgent") as MockPM, \
         patch("pipeline.orchestrator.build_run_data", return_value={}), \
         patch("pipeline.orchestrator.ReportGenerator"):
        MockPM.return_value.run = MagicMock(return_value=pm_result)
        MockAgg.return_value.fetch_all = MagicMock(return_value={"ticker": "TEST"})
        async def empty_debate(*a, **kw):
            return
            yield
        mock_debate.return_value = empty_debate()
        await _run_pipeline("TEST", 1, db, queue, None)

    phase2_called.assert_called_once()
