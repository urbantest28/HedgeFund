import requests
from typing import Any, Optional, Dict
from config import ALPHA_VANTAGE_API_KEY, ALPHA_VANTAGE_BASE_URL
from logger import get_logger

log = get_logger("alpha_vantage")


class AlphaVantageClient:
    def __init__(self, api_key: str = ALPHA_VANTAGE_API_KEY):
        self._key = api_key

    def _get(self, params: dict) -> Optional[dict]:
        params["apikey"] = self._key
        try:
            r = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=15)
            if not r.ok:
                return None
            return r.json()
        except Exception as e:
            log.warning(f"Alpha Vantage error {params.get('function')}: {e}")
            return None

    def _is_rate_limited(self, data: Optional[dict]) -> bool:
        if not data:
            return False
        return "Note" in data or "Information" in data

    def get_income_statement(self, ticker: str) -> dict:
        data = self._get({"function": "INCOME_STATEMENT", "symbol": ticker})
        if self._is_rate_limited(data):
            log.warning(f"Alpha Vantage rate limit hit for {ticker} income statement")
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": True}
        if not data:
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
        return {"annual": data.get("annualReports", []),
                "quarterly": data.get("quarterlyReports", []),
                "source": "alpha_vantage", "rate_limited": False}

    def get_balance_sheet(self, ticker: str) -> dict:
        data = self._get({"function": "BALANCE_SHEET", "symbol": ticker})
        if self._is_rate_limited(data):
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": True}
        if not data:
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
        return {"annual": data.get("annualReports", []),
                "quarterly": data.get("quarterlyReports", []),
                "source": "alpha_vantage", "rate_limited": False}

    def get_cash_flow(self, ticker: str) -> dict:
        data = self._get({"function": "CASH_FLOW", "symbol": ticker})
        if self._is_rate_limited(data):
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": True}
        if not data:
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
        return {"annual": data.get("annualReports", []),
                "quarterly": data.get("quarterlyReports", []),
                "source": "alpha_vantage", "rate_limited": False}

    def get_earnings(self, ticker: str) -> dict:
        data = self._get({"function": "EARNINGS", "symbol": ticker})
        if self._is_rate_limited(data):
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": True}
        if not data:
            return {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
        return {"annual": data.get("annualEarnings", []),
                "quarterly": data.get("quarterlyEarnings", []),
                "source": "alpha_vantage", "rate_limited": False}
