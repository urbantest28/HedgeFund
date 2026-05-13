import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pipeline.orchestrator import _run_pipeline


@pytest.mark.asyncio
async def test_report_generated_after_pipeline_complete(tmp_path):
    """Successful pipeline run triggers ReportGenerator.generate()."""
    queue = asyncio.Queue()
    db = MagicMock()
    db.get_agent_outputs.return_value = []
    db.get_debate_rounds.return_value = []

    pm_result = {"agent": "portfolio_manager", "phase": 4, "score": 2,
                 "status": "complete", "data_confidence": "full",
                 "raw_output": {"verdict": "WATCHLIST", "tier": "Buy",
                                "entry_low": 170.0, "entry_high": 175.0,
                                "stop_loss": 160.0, "target_price": 200.0,
                                "reasoning": "...", "key_risks": [],
                                "key_catalysts": [], "expected_returns": {}},
                 "summary": "", "duration_ms": 100,
                 "bull_points": [], "bear_points": [], "missing_fields": []}

    with patch("pipeline.orchestrator.ReportGenerator") as MockGen, \
         patch("pipeline.orchestrator.DataAggregator") as MockAgg, \
         patch("pipeline.orchestrator._run_phase_parallel") as mock_phase, \
         patch("pipeline.orchestrator.run_debate") as mock_debate, \
         patch("pipeline.orchestrator._run_agent_async", new=AsyncMock(return_value=pm_result)):
        MockAgg.return_value.fetch_all = MagicMock(return_value={"ticker": "AAPL"})
        mock_phase.side_effect = [
            [{"agent": f"a{i}", "phase": 1, "score": 7, "data_confidence": "full",
              "status": "complete", "summary": "", "duration_ms": 100,
              "bull_points": [], "bear_points": [], "missing_fields": [],
              "raw_output": {}} for i in range(5)],
            [{"agent": f"b{i}", "phase": 2, "score": 7, "data_confidence": "full",
              "status": "complete", "summary": "", "duration_ms": 100,
              "bull_points": [], "bear_points": [], "missing_fields": [],
              "raw_output": {}} for i in range(3)]
        ]
        async def empty_debate(*args, **kwargs):
            return
            yield  # make it an async generator
        mock_debate.return_value = empty_debate()

        await _run_pipeline("AAPL", 1, db, queue, None)

    MockGen.return_value.generate.assert_called_once()
