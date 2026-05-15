# tests/integration/test_aggregator.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from data.aggregator import DataAggregator


@pytest.fixture
def mock_clients():
    yf = MagicMock()
    yf.get_price.return_value = {"price": 183.50, "source": "yfinance"}
    yf.get_fundamentals.return_value = {
        "pe_ratio": 28.5, "market_cap": 2_800_000_000_000,
        "sector": "Technology", "source": "yfinance",
        "short_interest": {"short_float_pct": 0.043,
                           "days_to_cover": 2.1,
                           "shares_short": 95_000_000},
    }
    yf.get_ohlcv.return_value = {"records": [{"Date": "2026-05-10", "Close": 183.5}], "source": "yfinance"}
    yf.get_sector_peers.return_value = ["MSFT", "GOOGL"]

    mm = MagicMock()
    mm.get_snapshot.return_value = {"price": 183.50, "source": "massive_market"}
    mm.get_news.return_value = {"articles": [{"title": "AAPL beats earnings"}],
                                "source": "massive_market", "rate_limited": False}
    mm.get_analyst_ratings.return_value = {"buy": 32, "hold": 8, "sell": 2, "source": "massive_market"}

    av = MagicMock()
    av.get_income_statement.return_value = {"annual": [{"totalRevenue": "391035000000"}],
                                             "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_balance_sheet.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_cash_flow.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_earnings.return_value = {"quarterly": [{"reportedEPS": "1.65", "estimatedEPS": "1.61"}],
                                     "annual": [], "source": "alpha_vantage", "rate_limited": False}

    fred = MagicMock()
    fred.get_macro_snapshot.return_value = {
        "fed_funds_rate": 5.33, "cpi": 315.2, "gdp": 28000.0,
        "unemployment": 3.9, "pce": 21000.0, "yield_curve_spread": -0.60,
        "source": "fred",
    }

    reddit = MagicMock()
    reddit.get_posts.return_value = {"posts": [], "total_posts": 0, "source": "reddit"}

    edgar = MagicMock()
    edgar.search_filings.return_value = {"filings": [], "source": "sec_edgar"}

    insider = MagicMock()
    insider.get_transactions.return_value = {
        "transactions": [
            {"date": "2026-05-01", "officer_name": "Cook Timothy D",
             "title": "CEO", "transaction_type": "buy",
             "shares": 5000, "price_per_share": 183.50, "value": 917500.0},
        ],
        "source": "openinsider",
    }

    cache = MagicMock()
    cache.get.return_value = None  # cache miss — always fetch fresh

    db = MagicMock()
    return {"yf": yf, "mm": mm, "av": av, "fred": fred,
            "reddit": reddit, "edgar": edgar, "insider": insider,
            "cache": cache, "db": db}


def test_aggregate_returns_bundle_with_manifest(mock_clients, tmp_path):
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=1)
    assert bundle["ticker"] == "AAPL"
    assert bundle["run_id"] == 1
    assert "data" in bundle
    assert "manifest" in bundle
    assert "live_price" in bundle["manifest"]
    assert bundle["manifest"]["live_price"]["status"] == "ok"


def test_aggregate_saves_bundle_to_debug_folder(mock_clients, tmp_path):
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    agg.fetch("AAPL", run_id=99)
    bundle_file = tmp_path / "run_99_bundle.json"
    assert bundle_file.exists()
    saved = json.loads(bundle_file.read_text())
    assert saved["ticker"] == "AAPL"


def test_missing_live_price_marked_in_manifest(mock_clients, tmp_path):
    mock_clients["mm"].get_snapshot.return_value = {"price": None, "source": "massive_market"}
    mock_clients["yf"].get_price.return_value = {"price": None, "source": "yfinance"}
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=2)
    assert bundle["manifest"]["live_price"]["status"] == "missing"


def test_fallback_used_when_primary_fails(mock_clients, tmp_path):
    # Massive Market returns None price, yfinance has it
    mock_clients["mm"].get_snapshot.return_value = {"price": None, "source": "massive_market"}
    mock_clients["yf"].get_price.return_value = {"price": 183.50, "source": "yfinance"}
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=3)
    assert bundle["data"]["live_price"]["price"] == 183.50
    assert bundle["manifest"]["live_price"]["source"] == "yfinance"


def test_insider_transactions_in_bundle(mock_clients, tmp_path):
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=10)
    assert "insider_transactions" in bundle["data"]
    txns = bundle["data"]["insider_transactions"]["transactions"]
    assert len(txns) == 1
    assert txns[0]["transaction_type"] == "buy"
    assert bundle["manifest"]["insider_transactions"]["status"] == "ok"


def test_short_interest_in_manifest(mock_clients, tmp_path):
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=11)
    assert "short_interest" in bundle["manifest"]
    assert bundle["manifest"]["short_interest"]["status"] == "ok"
