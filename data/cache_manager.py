import json
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from config import CACHE_DIR


class CacheTier(Enum):
    LIVE    = ("live",    None)
    FOREVER = ("forever", None)
    TTL_1D  = ("derived", 86400)
    TTL_7D  = ("derived", 604800)
    TTL_30D = ("derived", 2592000)

    def __init__(self, folder: str, ttl: Optional[int]):
        self.folder = folder
        self.ttl_seconds = ttl


DATA_TYPE_TIERS = {
    "live_price":        CacheTier.LIVE,
    "intraday":          CacheTier.LIVE,
    "recent_news":       CacheTier.LIVE,
    "reddit_posts":      CacheTier.LIVE,
    "analyst_ratings":   CacheTier.LIVE,
    "forward_estimates": CacheTier.LIVE,
    "ohlcv_historical":  CacheTier.FOREVER,
    "earnings_history":  CacheTier.FOREVER,
    "financials_annual": CacheTier.FOREVER,
    "income_statement":  CacheTier.FOREVER,
    "balance_sheet":     CacheTier.FOREVER,
    "cash_flow":         CacheTier.FOREVER,
    "sec_filing":        CacheTier.FOREVER,
    "macro_historical":  CacheTier.FOREVER,
    "ratios":            CacheTier.TTL_1D,
    "market_cap":        CacheTier.TTL_1D,
    "sector":            CacheTier.TTL_7D,
    "company_overview":  CacheTier.TTL_30D,
}


class CacheManager:
    def __init__(self, cache_dir: Path = CACHE_DIR, db=None):
        self._root = cache_dir
        self._db = db

    def _path(self, ticker: str, data_type: str, tier: CacheTier) -> Path:
        subfolder = "historical" if tier == CacheTier.FOREVER else "derived"
        p = self._root / ticker / subfolder
        p.mkdir(parents=True, exist_ok=True)
        return p / f"{data_type}.json"

    def get(self, ticker: str, data_type: str) -> Optional[dict]:
        tier = DATA_TYPE_TIERS.get(data_type)
        if tier == CacheTier.LIVE:
            return None

        # If tier is known, check its specific subfolder only.
        # If tier is unknown, search both subfolders (handles ad-hoc data_types
        # stored with an explicit tier via put()).
        candidates = []
        if tier is not None:
            candidates = [tier]
        else:
            candidates = [CacheTier.FOREVER, CacheTier.TTL_1D]

        for candidate_tier in candidates:
            path = self._path(ticker, data_type, candidate_tier)
            if not path.exists():
                continue
            entry = json.loads(path.read_text(encoding="utf-8"))
            if candidate_tier != CacheTier.FOREVER:
                expires = entry.get("expires_at")
                if expires and datetime.fromisoformat(expires) < datetime.utcnow():
                    continue
            return entry
        return None

    def put(self, ticker: str, data_type: str, data: Any,
            tier: CacheTier, source: str) -> None:
        if tier == CacheTier.LIVE:
            return
        path = self._path(ticker, data_type, tier)
        expires_at = None
        if tier.ttl_seconds:
            expires_at = (datetime.utcnow() + timedelta(seconds=tier.ttl_seconds)).isoformat()
        entry = {
            "data": data,
            "source": source,
            "cache_tier": tier.name.lower(),
            "fetched_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
        }
        path.write_text(json.dumps(entry, default=str), encoding="utf-8")
        if self._db:
            self._db.upsert_cache_entry(
                ticker=ticker, data_type=data_type,
                cache_tier=tier.name.lower(), source=source,
                file_path=str(path), expires_at=expires_at
            )
