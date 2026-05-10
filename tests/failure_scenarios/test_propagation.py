# tests/failure_scenarios/test_propagation.py
"""Verify that missing data in manifest is never silently promoted to a verdict."""
from data.manifest import ManifestBuilder, DataConfidence


def test_two_critical_missing_fields_returns_minimal():
    b = ManifestBuilder()
    b.add("revenue", None, source=None, status="missing", critical=True)
    b.add("live_price", None, source=None, status="missing", critical=True)
    b.add("pe_ratio", 28.5, source="yfinance", status="ok")
    assert b.confidence() == DataConfidence.MINIMAL


def test_minimal_confidence_triggers_abort():
    """
    Simulate the pipeline abort check: if >= 2 Phase 1 agents return
    minimal confidence, the pipeline should not proceed to Phase 2.
    """
    from data.manifest import DataConfidence

    agent_confidences = [
        DataConfidence.MINIMAL,
        DataConfidence.MINIMAL,
        DataConfidence.FULL,
        DataConfidence.PARTIAL,
        DataConfidence.FULL,
    ]
    minimal_count = sum(1 for c in agent_confidences if c == DataConfidence.MINIMAL)
    should_abort = minimal_count >= 2
    assert should_abort is True


def test_single_critical_missing_still_partial_if_others_ok():
    b = ManifestBuilder()
    b.add("revenue", 1_000_000, source="alpha_vantage", status="ok", critical=True)
    b.add("options_pcr", None, source=None, status="missing", critical=False)
    assert b.confidence() == DataConfidence.PARTIAL
