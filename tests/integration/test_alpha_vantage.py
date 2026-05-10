# tests/integration/test_alpha_vantage.py
import responses as resp_lib
import pytest
from data.alpha_vantage import AlphaVantageClient

BASE = "https://www.alphavantage.co/query"

@pytest.fixture
def client():
    return AlphaVantageClient(api_key="demo")


@resp_lib.activate
def test_get_income_statement_returns_annual(client):
    resp_lib.add(resp_lib.GET, BASE, json={
        "symbol": "AAPL",
        "annualReports": [{"fiscalDateEnding": "2025-09-30", "totalRevenue": "391035000000",
                           "grossProfit": "180683000000", "netIncome": "93736000000",
                           "ebitda": "130000000000", "eps": "6.11"}],
        "quarterlyReports": []
    })
    result = client.get_income_statement("AAPL")
    assert len(result["annual"]) == 1
    assert result["annual"][0]["totalRevenue"] == "391035000000"
    assert result["source"] == "alpha_vantage"


@resp_lib.activate
def test_get_earnings_returns_history(client):
    resp_lib.add(resp_lib.GET, BASE, json={
        "symbol": "AAPL",
        "annualEarnings": [],
        "quarterlyEarnings": [
            {"fiscalDateEnding": "2026-03-31", "reportedEPS": "1.65",
             "estimatedEPS": "1.61", "surprise": "0.04", "surprisePercentage": "2.48"},
            {"fiscalDateEnding": "2025-12-31", "reportedEPS": "2.40",
             "estimatedEPS": "2.35", "surprise": "0.05", "surprisePercentage": "2.13"},
        ]
    })
    result = client.get_earnings("AAPL")
    assert len(result["quarterly"]) == 2
    assert result["quarterly"][0]["reportedEPS"] == "1.65"


@resp_lib.activate
def test_rate_limit_returns_empty_with_flag(client):
    resp_lib.add(resp_lib.GET, BASE,
        json={"Note": "API rate limit reached. Please upgrade."})
    result = client.get_income_statement("AAPL")
    assert result["annual"] == []
    assert result["rate_limited"] is True


@resp_lib.activate
def test_get_balance_sheet_returns_annual(client):
    resp_lib.add(resp_lib.GET, BASE, json={
        "annualReports": [{"fiscalDateEnding": "2025-09-30",
                           "totalAssets": "364980000000",
                           "totalLiabilities": "308030000000",
                           "totalShareholderEquity": "56950000000"}],
        "quarterlyReports": []
    })
    result = client.get_balance_sheet("AAPL")
    assert result["annual"][0]["totalAssets"] == "364980000000"
