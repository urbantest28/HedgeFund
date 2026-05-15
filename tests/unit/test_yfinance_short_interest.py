import pytest
from unittest.mock import patch, MagicMock
from data.yfinance_client import YFinanceClient


def _make_client_with_info(info: dict) -> dict:
    with patch("data.yfinance_client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = info
        client = YFinanceClient()
        result = client.get_fundamentals("AAPL")
    return result


def test_get_fundamentals_includes_short_interest_fields():
    info = {
        "trailingPE": 28.5,
        "shortPercentOfFloat": 0.043,
        "shortRatio": 2.1,
        "sharesShort": 95_000_000,
    }
    result = _make_client_with_info(info)
    assert "short_interest" in result
    assert result["short_interest"]["short_float_pct"] == 0.043
    assert result["short_interest"]["days_to_cover"] == 2.1
    assert result["short_interest"]["shares_short"] == 95_000_000


def test_get_fundamentals_short_interest_null_when_missing():
    info = {"trailingPE": 28.5}  # no short interest fields
    result = _make_client_with_info(info)
    assert result["short_interest"]["short_float_pct"] is None
    assert result["short_interest"]["days_to_cover"] is None
    assert result["short_interest"]["shares_short"] is None


def test_get_fundamentals_error_includes_short_interest_null():
    with patch("data.yfinance_client.yf.Ticker", side_effect=Exception("timeout")):
        client = YFinanceClient()
        result = client.get_fundamentals("AAPL")
    assert "short_interest" in result
    assert result["short_interest"]["short_float_pct"] is None
