import asyncio
import time
import requests
from typing import Any, Optional, Dict
from config import MASSIVE_MARKET_API_KEY, MASSIVE_MARKET_BASE_URL
from logger import get_logger

log = get_logger("massive_market")


class TokenBucket:
    """Allows max `rate` calls per `period` seconds. Async-safe."""
    def __init__(self, rate: int = 5, period: float = 60.0):
        self._rate = rate
        self._period = period
        self._tokens = float(rate)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(
                self._rate,
                self._tokens + (now - self._last) * self._rate / self._period
            )
            self._last = now
            if self._tokens < 1:
                wait = (1 - self._tokens) / (self._rate / self._period)
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


_bucket = TokenBucket(rate=5, period=60.0)


class MassiveMarketClient:
    def __init__(self, api_key: str = MASSIVE_MARKET_API_KEY):
        self._key = api_key
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {self._key}"})

    def _get(self, path: str, params: Optional[Dict] = None):
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(_bucket.acquire())
        except Exception:
            pass  # skip rate limiting if event loop cannot be used
        try:
            return self._session.get(
                f"{MASSIVE_MARKET_BASE_URL}{path}", params=params, timeout=15)
        except Exception as e:
            log.warning(f"HTTP error {path}: {e}")
            return None

    def get_news(self, ticker: str, limit: int = 20) -> dict:
        r = self._get("/v2/reference/news", {"ticker": ticker, "limit": limit, "order": "desc"})
        if r is None or r.status_code == 429:
            log.warning(f"get_news({ticker}) rate limited or failed")
            return {"articles": [], "source": "massive_market", "rate_limited": True}
        if not r.ok:
            return {"articles": [], "source": "massive_market", "rate_limited": False}
        data = r.json()
        articles = [
            {"title": a.get("title"), "published_utc": a.get("published_utc"),
             "article_url": a.get("article_url"), "author": a.get("author"),
             "description": a.get("description"), "tickers": a.get("tickers", []),
             "insights": a.get("insights", [])}
            for a in data.get("results", [])
        ]
        return {"articles": articles, "source": "massive_market",
                "count": data.get("count", 0), "rate_limited": False}

    def get_snapshot(self, ticker: str) -> dict:
        r = self._get(
            f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
        if r is None or not r.ok:
            return {"price": None, "volume": None, "prev_close": None,
                    "source": "massive_market"}
        t = r.json().get("ticker", {})
        day = t.get("day", {})
        return {"price": day.get("c"), "volume": day.get("v"),
                "prev_close": t.get("prevDay", {}).get("c"),
                "source": "massive_market"}

    def get_analyst_ratings(self, ticker: str) -> dict:
        r = self._get("/v2/reference/financials", {"ticker": ticker})
        if r is None or not r.ok:
            return {"buy": None, "hold": None, "sell": None,
                    "price_target": None, "source": "massive_market"}
        results = r.json().get("results", [{}])
        d = results[0] if results else {}
        return {"buy": d.get("buy"), "hold": d.get("hold"), "sell": d.get("sell"),
                "price_target": d.get("target_price"), "source": "massive_market"}
