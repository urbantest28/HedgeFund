# tests/failure_scenarios/test_api_failures.py
"""Verify that API failures trigger fallback chain, not crashes."""
import pytest
from unittest.mock import MagicMock
from data.aggregator import DataAggregator


def _make_aggregator(tmp_path, **overrides):
    defaults = {
        "yf":     MagicMock(**{"get_price.return_value": {"price": 183.5, "source": "yfinance"},
                               "get_fundamentals.return_value": {"pe_ratio": 28.5, "source": "yfinance"},
                               "get_ohlcv.return_value": {"records": [{"Close": 183.5}], "source": "yfinance"},
                               "get_sector_peers.return_value": ["MSFT"]}),
        "mm":     MagicMock(**{"get_snapshot.return_value": {"price": 183.5, "source": "massive_market"},
                               "get_news.return_value": {"articles": [], "source": "massive_market", "rate_limited": False},
                               "get_analyst_ratings.return_value": {"buy": 10, "source": "massive_market"}}),
        "av":     MagicMock(**{"get_income_statement.return_value": {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False},
                               "get_balance_sheet.return_value": {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False},
                               "get_cash_flow.return_value": {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False},
                               "get_earnings.return_value": {"quarterly": [], "annual": [], "source": "alpha_vantage", "rate_limited": False}}),
        "fred":   MagicMock(**{"get_macro_snapshot.return_value": {"fed_funds_rate": 5.33, "source": "fred"}}),
        "reddit": MagicMock(**{"get_posts.return_value": {"posts": [], "total_posts": 0, "source": "reddit"}}),
        "edgar":  MagicMock(**{"search_filings.return_value": {"filings": [], "source": "sec_edgar"}}),
        "insider": MagicMock(**{"get_transactions.return_value": {"transactions": [], "source": "openinsider"}}),
        "cache":  MagicMock(**{"get.return_value": None}),
        "db":     MagicMock(),
    }
    defaults.update(overrides)
    return DataAggregator(**defaults, debug_dir=tmp_path)


def test_massive_market_down_falls_back_to_yfinance_for_price(tmp_path):
    mm = MagicMock(**{"get_snapshot.return_value": {"price": None, "source": "massive_market"},
                      "get_news.return_value": {"articles": [], "source": "massive_market", "rate_limited": False},
                      "get_analyst_ratings.return_value": {"buy": None, "source": "massive_market"}})
    yf = MagicMock(**{"get_price.return_value": {"price": 183.50, "source": "yfinance"},
                      "get_fundamentals.return_value": {"pe_ratio": 28.5, "source": "yfinance"},
                      "get_ohlcv.return_value": {"records": [{"Close": 183.5}], "source": "yfinance"},
                      "get_sector_peers.return_value": []})
    agg = _make_aggregator(tmp_path, mm=mm, yf=yf)
    bundle = agg.fetch("AAPL", run_id=10)
    assert bundle["data"]["live_price"]["price"] == 183.50
    assert bundle["manifest"]["live_price"]["source"] == "yfinance"
    assert bundle["manifest"]["live_price"]["status"] == "ok"


def test_all_price_sources_fail_marks_critical_missing(tmp_path):
    mm = MagicMock(**{"get_snapshot.return_value": {"price": None, "source": "massive_market"},
                      "get_news.return_value": {"articles": [], "source": "massive_market", "rate_limited": False},
                      "get_analyst_ratings.return_value": {"buy": None, "source": "massive_market"}})
    yf = MagicMock(**{"get_price.return_value": {"price": None, "source": "yfinance"},
                      "get_fundamentals.return_value": {"pe_ratio": None, "source": "yfinance"},
                      "get_ohlcv.return_value": {"records": [], "source": "yfinance"},
                      "get_sector_peers.return_value": []})
    agg = _make_aggregator(tmp_path, mm=mm, yf=yf)
    bundle = agg.fetch("AAPL", run_id=11)
    assert bundle["manifest"]["live_price"]["status"] == "missing"
    assert bundle["data_confidence"] == "minimal"


def test_fred_failure_does_not_abort_run(tmp_path):
    fred = MagicMock(**{"get_macro_snapshot.return_value":
                        {"fed_funds_rate": None, "source": "fred", "error": "timeout"}})
    agg = _make_aggregator(tmp_path, fred=fred)
    bundle = agg.fetch("AAPL", run_id=12)
    assert "macro" in bundle["data"]
    assert bundle["manifest"]["fed_funds_rate"]["status"] == "missing"
