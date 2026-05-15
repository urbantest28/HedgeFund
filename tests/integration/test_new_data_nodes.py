"""Smoke tests verifying D2/D3/D6 data nodes appear correctly in the bundle."""
import pytest
from unittest.mock import MagicMock
from data.aggregator import DataAggregator


@pytest.fixture
def full_mock_clients(tmp_path):
    yf = MagicMock()
    yf.get_price.return_value = {"price": 183.50, "source": "yfinance"}
    yf.get_fundamentals.return_value = {
        "pe_ratio": 28.5, "sector": "Technology", "source": "yfinance",
        "short_interest": {"short_float_pct": 0.12, "days_to_cover": 6.2,
                           "shares_short": 200_000_000},
    }
    yf.get_ohlcv.return_value = {"records": [{"Date": "2026-05-10", "Close": 183.5}], "source": "yfinance"}
    yf.get_sector_peers.return_value = []

    mm = MagicMock()
    mm.get_snapshot.return_value = {"price": 183.50, "source": "massive_market"}
    mm.get_news.return_value = {"articles": [], "source": "massive_market", "rate_limited": False}
    mm.get_analyst_ratings.return_value = {"source": "massive_market"}

    av = MagicMock()
    av.get_income_statement.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_balance_sheet.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_cash_flow.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_earnings.return_value = {"quarterly": [], "annual": [], "source": "alpha_vantage", "rate_limited": False}

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
    cache.get.return_value = None

    db = MagicMock()
    return DataAggregator(yf=yf, mm=mm, av=av, fred=fred, reddit=reddit,
                          edgar=edgar, insider=insider, cache=cache,
                          db=db, debug_dir=tmp_path)


def test_d2_macro_data_in_bundle(full_mock_clients):
    bundle = full_mock_clients.fetch("AAPL", run_id=200)
    macro = bundle["data"]["macro"]
    assert macro["pce"] == 21000.0
    assert macro["yield_curve_spread"] == -0.60


def test_d3_insider_transactions_in_bundle(full_mock_clients):
    bundle = full_mock_clients.fetch("AAPL", run_id=201)
    insider = bundle["data"]["insider_transactions"]
    assert insider["source"] == "openinsider"
    assert len(insider["transactions"]) == 1
    assert insider["transactions"][0]["officer_name"] == "Cook Timothy D"


def test_d6_short_interest_in_fundamentals(full_mock_clients):
    bundle = full_mock_clients.fetch("AAPL", run_id=202)
    si = bundle["data"]["fundamentals"]["short_interest"]
    assert si["short_float_pct"] == 0.12
    assert si["days_to_cover"] == 6.2


def test_all_three_nodes_in_manifest(full_mock_clients):
    bundle = full_mock_clients.fetch("AAPL", run_id=203)
    manifest = bundle["manifest"]
    assert manifest["short_interest"]["status"] == "ok"
    assert manifest["insider_transactions"]["status"] == "ok"
    assert "fed_funds_rate" in manifest  # macro uses existing key


def test_insider_partial_when_no_transactions(tmp_path):
    """Empty insider activity is partial, not missing — valid for many stocks."""
    yf = MagicMock()
    yf.get_price.return_value = {"price": 50.0, "source": "yfinance"}
    yf.get_fundamentals.return_value = {
        "pe_ratio": 15.0, "sector": "Energy", "source": "yfinance",
        "short_interest": {"short_float_pct": None, "days_to_cover": None, "shares_short": None},
    }
    yf.get_ohlcv.return_value = {"records": [], "source": "yfinance"}
    yf.get_sector_peers.return_value = []
    mm = MagicMock()
    mm.get_snapshot.return_value = {"price": 50.0, "source": "massive_market"}
    mm.get_news.return_value = {"articles": [], "source": "massive_market", "rate_limited": False}
    mm.get_analyst_ratings.return_value = {"source": "massive_market"}
    av = MagicMock()
    av.get_income_statement.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_balance_sheet.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_cash_flow.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_earnings.return_value = {"quarterly": [], "annual": [], "source": "alpha_vantage", "rate_limited": False}
    fred = MagicMock()
    fred.get_macro_snapshot.return_value = {"fed_funds_rate": 5.33, "cpi": 315.2, "gdp": 28000.0,
                                             "unemployment": 3.9, "pce": 21000.0,
                                             "yield_curve_spread": -0.60, "source": "fred"}
    reddit = MagicMock()
    reddit.get_posts.return_value = {"posts": [], "total_posts": 0, "source": "reddit"}
    edgar = MagicMock()
    edgar.search_filings.return_value = {"filings": [], "source": "sec_edgar"}
    insider = MagicMock()
    insider.get_transactions.return_value = {"transactions": [], "source": "openinsider"}
    cache = MagicMock()
    cache.get.return_value = None
    db = MagicMock()

    agg = DataAggregator(yf=yf, mm=mm, av=av, fred=fred, reddit=reddit,
                         edgar=edgar, insider=insider, cache=cache,
                         db=db, debug_dir=tmp_path)
    bundle = agg.fetch("XOM", run_id=204)
    assert bundle["manifest"]["insider_transactions"]["status"] == "partial"
