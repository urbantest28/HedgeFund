from enum import Enum
from typing import Any, Optional

Status = str  # "ok", "partial", or "missing"

CRITICAL_FIELDS = {
    "live_price", "revenue", "ohlcv", "pe_ratio",
    "income_statement", "balance_sheet", "cash_flow",
    "fed_funds_rate", "earnings_actual_eps",
}


class DataConfidence(str, Enum):
    FULL    = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"


class ManifestBuilder:
    def __init__(self):
        self._entries = {}

    def add(self, field: str, value: Any, source: Optional[str],
            status: Status, note: Optional[str] = None,
            critical: Optional[bool] = None) -> None:
        is_critical = critical if critical is not None else field in CRITICAL_FIELDS
        self._entries[field] = {
            "value": value,
            "source": source,
            "status": status,
            "note": note,
            "critical": is_critical,
        }

    def confidence(self) -> DataConfidence:
        missing_critical = any(
            e["status"] == "missing" and e["critical"]
            for e in self._entries.values()
        )
        if missing_critical:
            return DataConfidence.MINIMAL
        any_missing = any(e["status"] != "ok" for e in self._entries.values())
        return DataConfidence.PARTIAL if any_missing else DataConfidence.FULL

    def to_dict(self) -> dict:
        return {
            k: {"value": v["value"], "source": v["source"],
                "status": v["status"], "note": v["note"]}
            for k, v in self._entries.items()
        }
