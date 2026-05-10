from fredapi import Fred
from typing import Any, Optional
from config import FRED_API_KEY
from logger import get_logger

log = get_logger("fred")


class FredClient:
    def __init__(self, api_key: str = FRED_API_KEY):
        self._api_key = api_key

    def get_macro_snapshot(self) -> dict:
        try:
            fred = Fred(api_key=self._api_key)
            errors: list = []

            def _latest(series_id: str) -> Optional[float]:
                try:
                    s = fred.get_series(series_id)
                    return float(s.iloc[-1])
                except Exception as e:
                    errors.append(f"{series_id}: {e}")
                    return None

            result = {
                "fed_funds_rate": _latest("DFF"),
                "cpi":            _latest("CPIAUCSL"),
                "gdp":            _latest("GDP"),
                "unemployment":   _latest("UNRATE"),
                "source": "fred",
            }
            if errors:
                result["error"] = "; ".join(errors)
            log.info(f"FRED snapshot — rate:{result['fed_funds_rate']} "
                     f"cpi:{result['cpi']} gdp:{result['gdp']}")
            return result
        except Exception as e:
            log.warning(f"FRED macro_snapshot failed: {e}")
            return {"fed_funds_rate": None, "cpi": None, "gdp": None,
                    "unemployment": None, "source": "fred", "error": str(e)}

    def get_series_history(self, series_id: str, observation_start: str = "2020-01-01") -> dict:
        try:
            fred = Fred(api_key=self._api_key)
            s = fred.get_series(series_id, observation_start=observation_start)
            records = [{"date": str(d.date()), "value": float(v)}
                       for d, v in s.items() if v == v]  # skip NaN
            return {"series_id": series_id, "records": records, "source": "fred"}
        except Exception as e:
            log.warning(f"FRED get_series({series_id}) failed: {e}")
            return {"series_id": series_id, "records": [], "source": "fred", "error": str(e)}
