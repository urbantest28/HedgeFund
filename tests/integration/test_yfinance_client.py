# tests/integration/test_yfinance_client.py
import pytest
from unittest.mock import patch, MagicMock
from data.yfinance_client import YFinanceClient


@pytest.fixture
def mock_ticker():
    t = MagicMock()
    t.info = {
        "currentPrice": 183.50, "marketCap": 2_800_000_000_000,
        "trailingPE": 28.5, "priceToBook": 45.2,
        "returnOnEquity": 1.47, "debtToEquity": 185.0,
        "revenueGrowth": 0.04, "grossMargins": 0.46,
        "sector": "Technology", "industry": "Consumer Electronics",
        "shortName": "Apple Inc.",
        "enterpriseToEbitda": 22.1, "priceToSalesTrailing12Months": 7.8,
    }
    t.fast_info = MagicMock()
    t.fast_info.last_price = 183.50
    hist = MagicMock()
    hist.empty = False
    hist.reset_index.return_value = hist
    hist.to_dict.return_value = {"Date": {}, "Open": {}, "High": {}, "Low": {}, "Close": {}, "Volume": {}}
    t.history.return_value = hist
    t.get_earnings_dates.return_value = MagicMock()
    return t


def test_get_price_returns_dict(mock_ticker):
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        client = YFinanceClient()
        result = client.get_price("AAPL")
    assert "price" in result
    assert result["price"] == 183.50
    assert "source" in result
    assert result["source"] == "yfinance"


def test_get_fundamentals_returns_required_fields(mock_ticker):
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        client = YFinanceClient()
        result = client.get_fundamentals("AAPL")
    for field in ("pe_ratio", "price_to_book", "roe", "market_cap", "sector", "industry"):
        assert field in result, f"Missing field: {field}"


def test_get_sector_peers_returns_list(mock_ticker):
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        with patch("data.yfinance_client.yf.download") as mock_dl:
            mock_dl.return_value = MagicMock()
            client = YFinanceClient()
            peers = client.get_sector_peers("AAPL", n=3)
    assert isinstance(peers, list)


def test_missing_info_field_returns_none(mock_ticker):
    mock_ticker.info = {}
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        client = YFinanceClient()
        result = client.get_fundamentals("AAPL")
    assert result["pe_ratio"] is None


def test_get_ohlcv_returns_records(mock_ticker):
    with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
        client = YFinanceClient()
        result = client.get_ohlcv("AAPL", period="1y")
    assert "records" in result
    assert result["source"] == "yfinance"
