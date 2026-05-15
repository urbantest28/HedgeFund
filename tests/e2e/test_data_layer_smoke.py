# tests/e2e/test_data_layer_smoke.py
"""
End-to-end smoke test for the data layer using only the frozen AAPL bundle.
Verifies all components work together from fixture input to bundle output.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from data.aggregator import DataAggregator
from data.manifest import DataConfidence
from db.database import Database


def test_full_data_layer_pipeline_with_fixture(aapl_bundle, tmp_path):
    """
    Given: all clients return data matching the frozen AAPL fixture
    When: aggregator.fetch() is called
    Then: bundle is complete, manifest has no critical missing fields,
          bundle is saved to debug folder, DB cache entry can be written
    """
    yf = MagicMock()
    yf.get_price.return_value = aapl_bundle["data"]["live_price"]
    yf.get_fundamentals.return_value = aapl_bundle["data"]["fundamentals"]
    yf.get_ohlcv.return_value = aapl_bundle["data"]["ohlcv"]
    yf.get_sector_peers.return_value = aapl_bundle["data"]["peers"]

    mm = MagicMock()
    mm.get_snapshot.return_value = aapl_bundle["data"]["live_price"]
    mm.get_news.return_value = aapl_bundle["data"]["news"]
    mm.get_analyst_ratings.return_value = aapl_bundle["data"]["analyst_ratings"]

    av = MagicMock()
    av.get_income_statement.return_value = aapl_bundle["data"]["income_statement"]
    av.get_balance_sheet.return_value = aapl_bundle["data"]["balance_sheet"]
    av.get_cash_flow.return_value = aapl_bundle["data"]["cash_flow"]
    av.get_earnings.return_value = aapl_bundle["data"]["earnings"]

    fred = MagicMock()
    fred.get_macro_snapshot.return_value = aapl_bundle["data"]["macro"]

    reddit = MagicMock()
    reddit.get_posts.return_value = aapl_bundle["data"]["reddit"]

    edgar = MagicMock()
    edgar.search_filings.return_value = aapl_bundle["data"]["sec_filings"]

    insider = MagicMock()
    insider.get_transactions.return_value = {"transactions": [], "source": "openinsider"}

    cache = MagicMock()
    cache.get.return_value = None

    db = MagicMock()

    agg = DataAggregator(yf=yf, mm=mm, av=av, fred=fred,
                         reddit=reddit, edgar=edgar, insider=insider,
                         cache=cache, db=db, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=1)

    # Bundle structure
    assert bundle["ticker"] == "AAPL"
    assert bundle["run_id"] == 1
    assert "data" in bundle
    assert "manifest" in bundle

    # All critical fields present and not missing
    critical_fields = ["live_price", "pe_ratio", "income_statement",
                       "balance_sheet", "cash_flow", "earnings_history",
                       "fed_funds_rate", "ohlcv"]
    for field in critical_fields:
        assert field in bundle["manifest"], f"Critical field missing from manifest: {field}"
        assert bundle["manifest"][field]["status"] != "missing", \
            f"Critical field {field} has status 'missing'"

    # Confidence is not minimal
    assert bundle["data_confidence"] != DataConfidence.MINIMAL.value

    # Debug bundle was saved
    bundle_file = tmp_path / "run_1_bundle.json"
    assert bundle_file.exists()
    saved = json.loads(bundle_file.read_text())
    assert saved["ticker"] == "AAPL"
