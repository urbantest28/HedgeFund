# tests/unit/test_cache_ttl.py
import pytest
import json
import time
from pathlib import Path
from unittest.mock import MagicMock
from data.cache_manager import CacheManager, CacheTier


@pytest.fixture
def mgr(tmp_path):
    db = MagicMock()
    db.get_cache_entry.return_value = None
    return CacheManager(cache_dir=tmp_path, db=db)


def test_live_data_never_cached(mgr):
    assert mgr.get("AAPL", "live_price") is None
    mgr.put("AAPL", "live_price", {"c": 183.0}, CacheTier.LIVE, source="massive_market")
    assert mgr.get("AAPL", "live_price") is None


def test_forever_data_cached_and_retrieved(mgr, tmp_path):
    mgr.put("AAPL", "earnings_Q1_2026", {"eps": 1.53}, CacheTier.FOREVER, source="alpha_vantage")
    result = mgr.get("AAPL", "earnings_Q1_2026")
    assert result is not None
    assert result["data"]["eps"] == 1.53
    assert result["cache_tier"] == "forever"


def test_ttl_data_expired_returns_none(mgr, tmp_path):
    mgr.put("AAPL", "ratios", {"pe": 28.5}, CacheTier.TTL_1D, source="massive_market")
    # Manually expire by writing past expiry to the file
    cache_file = tmp_path / "AAPL" / "derived" / "ratios.json"
    data = json.loads(cache_file.read_text())
    data["expires_at"] = "2020-01-01T00:00:00"
    cache_file.write_text(json.dumps(data))
    assert mgr.get("AAPL", "ratios") is None


def test_ttl_data_valid_returns_data(mgr):
    mgr.put("AAPL", "ratios", {"pe": 28.5}, CacheTier.TTL_1D, source="massive_market")
    result = mgr.get("AAPL", "ratios")
    assert result is not None
    assert result["data"]["pe"] == 28.5


def test_tier_classification():
    assert CacheTier.LIVE.ttl_seconds is None
    assert CacheTier.FOREVER.ttl_seconds is None
    assert CacheTier.TTL_1D.ttl_seconds == 86400
    assert CacheTier.TTL_7D.ttl_seconds == 604800
    assert CacheTier.TTL_30D.ttl_seconds == 2592000
