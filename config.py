from pathlib import Path
from dotenv import load_dotenv
from typing import Optional
import os
import re

_TICKER_RE = re.compile(r'^[A-Z0-9.\-]{1,12}$')


def sanitize_ticker(ticker: str) -> str:
    """Normalise and validate a ticker symbol for safe use in file paths.

    Raises ValueError for anything that doesn't look like a real ticker so
    callers can return HTTP 400 before the value ever touches the filesystem.
    """
    t = ticker.strip().upper()
    if not _TICKER_RE.match(t):
        raise ValueError(f"Invalid ticker: {ticker!r}")
    return t


def safe_path(base: Path, *parts: str) -> Path:
    """Construct a path under base and verify it doesn't escape via traversal.

    Resolves symlinks before checking containment so that ``../../`` tricks
    are caught even after sanitize_ticker().  Raises ValueError if the
    resolved path is not inside base.
    """
    base_resolved = base.resolve()
    candidate = base_resolved.joinpath(*[str(p) for p in parts]).resolve()
    # relative_to raises ValueError when candidate is not under base_resolved.
    candidate.relative_to(base_resolved)
    return candidate

BASE_DIR = Path(__file__).parent

load_dotenv(BASE_DIR / ".env", override=True)

ANTHROPIC_API_KEY     = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY        = os.getenv("GOOGLE_API_KEY", "")
MASSIVE_MARKET_API_KEY = os.getenv("MASSIVE_MARKET_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
FRED_API_KEY          = os.getenv("FRED_API_KEY", "")
REDDIT_CLIENT_ID      = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET  = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT     = os.getenv("REDDIT_USER_AGENT", "hedgefund-analyser/1.0")
NTFY_TOPIC            = os.getenv("NTFY_TOPIC", "")
_trades_db_raw = os.getenv("DASHBOARD_TRADES_DB_PATH", "")
DASHBOARD_TRADES_DB_PATH = Path(_trades_db_raw) if _trades_db_raw else None

PHASE1_PROVIDER = os.getenv("PHASE1_PROVIDER", "gemini")
PHASE1_MODEL    = os.getenv("PHASE1_MODEL", "gemini-2.0-flash")
PHASE2_PROVIDER = os.getenv("PHASE2_PROVIDER", "gemini")
PHASE2_MODEL    = os.getenv("PHASE2_MODEL", "gemini-2.0-flash")
FALLBACK_PROVIDER = os.getenv("FALLBACK_PROVIDER", "anthropic")
FALLBACK_MODEL    = os.getenv("FALLBACK_MODEL", "claude-haiku-4-5-20251001")
DEBATE_PROVIDER = os.getenv("DEBATE_PROVIDER", "anthropic")
DEBATE_MODEL    = os.getenv("DEBATE_MODEL", "claude-opus-4-7")
PM_PROVIDER     = os.getenv("PM_PROVIDER", "anthropic")
PM_MODEL        = os.getenv("PM_MODEL", "claude-opus-4-7")

CACHE_DIR       = BASE_DIR / "cache"
UPLOADS_DIR     = BASE_DIR / "uploads"
REPORTS_DIR     = BASE_DIR / "reports_output"
LOGS_DIR        = BASE_DIR / "logs"
DEBUG_BUNDLES_DIR = BASE_DIR / "debug" / "bundles"
DB_PATH         = BASE_DIR / "db" / "hedgefund.db"

MASSIVE_MARKET_BASE_URL = "https://api.massive.com"
ALPHA_VANTAGE_BASE_URL  = "https://www.alphavantage.co/query"
SEC_EDGAR_BASE_URL      = "https://data.sec.gov"

def init_dirs() -> None:
    for _d in (CACHE_DIR, UPLOADS_DIR, REPORTS_DIR, LOGS_DIR, DEBUG_BUNDLES_DIR, DB_PATH.parent):
        _d.mkdir(parents=True, exist_ok=True)

init_dirs()
