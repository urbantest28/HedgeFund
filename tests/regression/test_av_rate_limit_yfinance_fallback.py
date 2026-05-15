"""
Regression: run_13 NVDA - balance_sheet and cash_flow returned empty because
Alpha Vantage rate-limited calls 2 and 3 in a back-to-back sequence, and the
committed aggregator had no fallback. Fix: yfinance fallback + caching.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from data.aggregator import DataAggregator
from data.cache_manager import CacheManager, CacheTier


AV_RATE_LIMITED = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": True}
AV_OK           = {"annual": [{"date": "2025-01-01", "totalRevenue": "100000"}],
                   "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
YF_BALANCE      = {"annual": [{"date": "2025-01-01", "TotalAssets": "500000"}],
                   "quarterly": [], "source": "yfinance", "rate_limited": False}
YF_CASHFLOW     = {"annual": [{"date": "2025-01-01", "FreeCashFlow": "80000"}],
                   "quarterly": [], "source": "yfinance", "rate_limited": False}


@pytest.fixture
def aggregator(tmp_path):
    yf = MagicMock()
    yf.get_price.return_value       = {"price": 235.8, "source": "yfinance"}
    yf.get_fundamentals.return_value = {"pe_ratio": 48.1, "source": "yfinance"}
    yf.get_ohlcv.return_value       = {"records": [{"Close": 235.8}], "source": "yfinance"}
    yf.get_balance_sheet.return_value = YF_BALANCE
    yf.get_cash_flow.return_value     = YF_CASHFLOW
    yf.get_sector_peers.return_value  = []

    av = MagicMock()
    av.get_income_statement.return_value = AV_OK
    av.get_balance_sheet.return_value    = AV_RATE_LIMITED
    av.get_cash_flow.return_value        = AV_RATE_LIMITED
    av.get_earnings.return_value         = {"quarterly": [{"date": "2025-01-01"}],
                                            "annual": [], "source": "alpha_vantage",
                                            "rate_limited": False}

    mm = MagicMock()
    mm.get_snapshot.return_value       = {"price": None, "source": "massive_market"}
    mm.get_news.return_value           = {"articles": [], "source": "massive_market"}
    mm.get_analyst_ratings.return_value = {}

    fred = MagicMock()
    fred.get_macro_snapshot.return_value = {"fed_funds_rate": 3.63, "source": "fred"}

    reddit = MagicMock()
    reddit.get_posts.return_value = {"posts": [], "total_posts": 0,
                                     "positive_count": 0, "negative_count": 0,
                                     "source": "reddit"}

    edgar = MagicMock()
    edgar.search_filings.return_value = {"filings": [{"form": "10-K"}], "source": "sec_edgar"}

    cache = CacheManager(cache_dir=tmp_path, db=None)
    db    = MagicMock()

    return DataAggregator(yf=yf, mm=mm, av=av, fred=fred, reddit=reddit,
                          edgar=edgar, cache=cache, db=db,
                          debug_dir=tmp_path / "bundles")


def test_balance_sheet_falls_back_to_yfinance_when_av_rate_limited(aggregator):
    bundle = aggregator.fetch("NVDA", run_id=99)
    bs = bundle["data"]["balance_sheet"]
    assert bs["source"] == "yfinance", "Should fall back to yfinance when AV is rate-limited"
    assert bs["annual"], "Should have balance sheet data from yfinance"
    assert bundle["manifest"]["balance_sheet"]["status"] == "ok"


def test_cash_flow_falls_back_to_yfinance_when_av_rate_limited(aggregator):
    bundle = aggregator.fetch("NVDA", run_id=99)
    cf = bundle["data"]["cash_flow"]
    assert cf["source"] == "yfinance", "Should fall back to yfinance when AV is rate-limited"
    assert cf["annual"], "Should have cash flow data from yfinance"
    assert bundle["manifest"]["cash_flow"]["status"] == "ok"


def test_income_statement_not_affected(aggregator):
    bundle = aggregator.fetch("NVDA", run_id=99)
    inc = bundle["data"]["income_statement"]
    assert inc["source"] == "alpha_vantage"
    assert inc["annual"]
    assert bundle["manifest"]["income_statement"]["status"] == "ok"


def test_successful_fallback_data_is_cached(aggregator, tmp_path):
    aggregator.fetch("NVDA", run_id=99)
    cache = CacheManager(cache_dir=tmp_path, db=None)
    assert cache.get("NVDA", "balance_sheet") is not None, "balance_sheet should be cached after yfinance fallback"
    assert cache.get("NVDA", "cash_flow") is not None, "cash_flow should be cached after yfinance fallback"


def test_manifest_shows_ok_for_fallback_fields(aggregator):
    bundle = aggregator.fetch("NVDA", run_id=99)
    assert bundle["manifest"]["balance_sheet"]["status"] == "ok"
    assert bundle["manifest"]["cash_flow"]["status"] == "ok"
