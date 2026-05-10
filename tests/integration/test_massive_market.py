# tests/integration/test_massive_market.py
import pytest
import asyncio
import responses as resp_lib
from data.massive_market import MassiveMarketClient


@pytest.fixture
def client():
    return MassiveMarketClient(api_key="test_key")


@resp_lib.activate
def test_get_news_returns_articles(client):
    resp_lib.add(resp_lib.GET,
        "https://api.massive.com/v2/reference/news",
        json={"status": "OK", "results": [
            {"title": "Apple beats earnings", "published_utc": "2026-05-01T10:00:00Z",
             "article_url": "https://example.com/1", "author": "Jane",
             "insights": [{"sentiment": "positive", "sentiment_reasoning": "beat estimates", "ticker": "AAPL"}],
             "tickers": ["AAPL"], "description": "Apple reported strong Q2."}
        ], "count": 1})
    result = client.get_news("AAPL", limit=10)
    assert len(result["articles"]) == 1
    assert result["articles"][0]["title"] == "Apple beats earnings"
    assert result["source"] == "massive_market"


@resp_lib.activate
def test_get_news_429_returns_empty_with_flag(client):
    resp_lib.add(resp_lib.GET,
        "https://api.massive.com/v2/reference/news",
        status=429)
    result = client.get_news("AAPL", limit=10)
    assert result["articles"] == []
    assert result["rate_limited"] is True


@resp_lib.activate
def test_get_snapshot_returns_price(client):
    resp_lib.add(resp_lib.GET,
        "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/AAPL",
        json={"status": "OK", "ticker": {
            "ticker": "AAPL", "day": {"c": 183.50, "v": 50_000_000},
            "prevDay": {"c": 181.00}}})
    result = client.get_snapshot("AAPL")
    assert result["price"] == 183.50
    assert result["source"] == "massive_market"


@resp_lib.activate
def test_get_snapshot_404_returns_none_price(client):
    resp_lib.add(resp_lib.GET,
        "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/AAPL",
        status=404)
    result = client.get_snapshot("AAPL")
    assert result["price"] is None


def test_token_bucket_allows_5_per_minute():
    import time
    from data.massive_market import TokenBucket
    bucket = TokenBucket(rate=5, period=60.0)
    # Should not block for first 5 tokens
    start = time.monotonic()
    for _ in range(5):
        asyncio.get_event_loop().run_until_complete(bucket.acquire())
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"First 5 calls took {elapsed:.2f}s — should be instant"
