import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import DEBUG_BUNDLES_DIR
from data.manifest import ManifestBuilder
from logger import get_logger

log = get_logger("aggregator")


class DataAggregator:
    def __init__(self, yf, mm, av, fred, reddit, edgar, cache, db,
                 debug_dir: Path = DEBUG_BUNDLES_DIR):
        self._yf     = yf
        self._mm     = mm
        self._av     = av
        self._fred   = fred
        self._reddit = reddit
        self._edgar  = edgar
        self._cache  = cache
        self._db     = db
        self._debug_dir = debug_dir
        self._debug_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, ticker: str, run_id: int) -> dict:
        log.info(f"Starting data fetch for {ticker}")
        mb = ManifestBuilder()
        data = {}

        # ── Live price (never cached) ──────────────────────────────────────
        price_result = self._mm.get_snapshot(ticker)
        if not price_result.get("price"):
            price_result = self._yf.get_price(ticker)
        price = price_result.get("price")
        data["live_price"] = price_result
        mb.add("live_price", price, source=price_result.get("source"),
               status="ok" if price else "missing", critical=True)
        log.info(f"[run_{run_id}] live_price: {price} from {price_result.get('source')}")

        # ── Fundamentals ──────────────────────────────────────────────────
        fund = self._yf.get_fundamentals(ticker)
        data["fundamentals"] = fund
        pe = fund.get("pe_ratio")
        mb.add("pe_ratio", pe, source=fund.get("source"),
               status="ok" if pe else "missing", critical=True)

        # ── OHLCV ─────────────────────────────────────────────────────────
        cached_ohlcv = self._cache.get(ticker, "ohlcv_historical")
        if cached_ohlcv:
            ohlcv = cached_ohlcv["data"]
            ohlcv_src = "cache"
        else:
            ohlcv = self._yf.get_ohlcv(ticker, period="2y")
            ohlcv_src = ohlcv.get("source", "yfinance")
        data["ohlcv"] = ohlcv
        mb.add("ohlcv", bool(ohlcv.get("records")), source=ohlcv_src,
               status="ok" if ohlcv.get("records") else "missing", critical=True)

        # ── Financials (income / balance / cash flow) ──────────────────────
        for key, method in [("income_statement", self._av.get_income_statement),
                             ("balance_sheet",    self._av.get_balance_sheet),
                             ("cash_flow",        self._av.get_cash_flow)]:
            result = method(ticker)
            data[key] = result
            has_data = bool(result.get("annual") or result.get("quarterly"))
            mb.add(key, has_data, source=result.get("source"),
                   status="ok" if has_data else "missing", critical=True)

        # ── Earnings ──────────────────────────────────────────────────────
        earnings = self._av.get_earnings(ticker)
        data["earnings"] = earnings
        has_earnings = bool(earnings.get("quarterly"))
        mb.add("earnings_history", has_earnings, source=earnings.get("source"),
               status="ok" if has_earnings else "missing", critical=True)

        # ── News (live — never cached) ─────────────────────────────────────
        news = self._mm.get_news(ticker, limit=20)
        data["news"] = news
        article_count = len(news.get("articles", []))
        mb.add("news", bool(article_count), source=news.get("source"),
               status="ok" if article_count >= 5 else ("partial" if article_count > 0 else "missing"),
               note=f"{article_count} articles retrieved" if article_count < 5 else None)

        # ── Reddit (live — never cached) ──────────────────────────────────
        reddit = self._reddit.get_posts(ticker)
        data["reddit"] = reddit
        mb.add("reddit_posts", bool(reddit.get("total_posts")), source="reddit",
               status="ok" if reddit.get("total_posts", 0) > 0 else "partial")

        # ── Macro (FRED) ──────────────────────────────────────────────────
        macro = self._fred.get_macro_snapshot()
        data["macro"] = macro
        rate = macro.get("fed_funds_rate")
        mb.add("fed_funds_rate", rate, source="fred",
               status="ok" if rate else "missing", critical=True)

        # ── SEC filings ───────────────────────────────────────────────────
        filings = self._edgar.search_filings(ticker, form_type="10-K")
        data["sec_filings"] = filings
        mb.add("sec_10k", bool(filings.get("filings")), source="sec_edgar",
               status="ok" if filings.get("filings") else "partial")

        # ── Analyst ratings ───────────────────────────────────────────────
        ratings = self._mm.get_analyst_ratings(ticker)
        data["analyst_ratings"] = ratings

        # ── Peers ─────────────────────────────────────────────────────────
        data["peers"] = self._yf.get_sector_peers(ticker, n=5)

        # ── Build bundle & save snapshot ──────────────────────────────────
        bundle = {
            "ticker": ticker,
            "run_id": run_id,
            "fetched_at": datetime.utcnow().isoformat(),
            "data": data,
            "manifest": mb.to_dict(),
            "data_confidence": mb.confidence().value,
        }
        bundle_path = self._debug_dir / f"run_{run_id}_bundle.json"
        bundle_path.write_text(json.dumps(bundle, default=str), encoding="utf-8")
        log.info(f"[run_{run_id}] Bundle saved -> {bundle_path} | confidence: {bundle['data_confidence']}")
        return bundle
