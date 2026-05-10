# tests/integration/test_sec_edgar.py
import pytest
import responses as resp_lib
from data.sec_edgar import SecEdgarClient


@pytest.fixture
def client():
    return SecEdgarClient()


@resp_lib.activate
def test_get_cik_for_aapl(client):
    resp_lib.add(resp_lib.GET,
        "https://efts.sec.gov/LATEST/search-index",
        json={"hits": {"hits": [{"_source": {"entity_name": "Apple Inc.", "file_date": "2025-11-01",
              "period_of_report": "2025-09-30", "accession_no": "0000320193-25-000001",
              "entity_id": "320193"}}]}})
    result = client.search_filings("AAPL", form_type="10-K")
    assert len(result["filings"]) >= 1
    assert result["source"] == "sec_edgar"


@resp_lib.activate
def test_missing_ticker_returns_empty(client):
    resp_lib.add(resp_lib.GET,
        "https://efts.sec.gov/LATEST/search-index",
        json={"hits": {"hits": []}})
    result = client.search_filings("ZZZZZ", form_type="10-K")
    assert result["filings"] == []


@resp_lib.activate
def test_network_error_returns_empty(client):
    resp_lib.add(resp_lib.GET,
        "https://efts.sec.gov/LATEST/search-index",
        body=ConnectionError("Network down"))
    result = client.search_filings("AAPL", form_type="8-K")
    assert result["filings"] == []
    assert "error" in result
