# tests/integration/test_fred_client.py
import pytest
from unittest.mock import patch, MagicMock
from data.fred_client import FredClient


@pytest.fixture
def client():
    return FredClient(api_key="test_key")


def test_get_macro_snapshot_returns_all_series(client):
    mock_fred = MagicMock()
    mock_series = MagicMock()
    mock_series.iloc.__getitem__ = MagicMock(return_value=5.33)

    def side_effect(series_id):
        import pandas as pd
        values = {"DFF": 5.33, "CPIAUCSL": 315.2, "GDP": 28000.0, "UNRATE": 3.9}
        return pd.Series([values[series_id]])

    mock_fred.get_series.side_effect = side_effect
    with patch("data.fred_client.Fred", return_value=mock_fred):
        c = FredClient(api_key="test")
        result = c.get_macro_snapshot()
    assert "fed_funds_rate" in result
    assert "cpi" in result
    assert "gdp" in result
    assert "unemployment" in result
    assert result["source"] == "fred"


def test_get_macro_snapshot_handles_failure(client):
    mock_fred = MagicMock()
    mock_fred.get_series.side_effect = Exception("API error")
    with patch("data.fred_client.Fred", return_value=mock_fred):
        c = FredClient(api_key="test")
        result = c.get_macro_snapshot()
    assert result["fed_funds_rate"] is None
    assert result["source"] == "fred"
    assert "error" in result
