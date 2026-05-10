from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).parent

ANTHROPIC_API_KEY     = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY        = os.getenv("GOOGLE_API_KEY", "")
MASSIVE_MARKET_API_KEY = os.getenv("MASSIVE_MARKET_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
FRED_API_KEY          = os.getenv("FRED_API_KEY", "")
REDDIT_CLIENT_ID      = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET  = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT     = os.getenv("REDDIT_USER_AGENT", "hedgefund-analyser/1.0")
NTFY_TOPIC            = os.getenv("NTFY_TOPIC", "")
DASHBOARD_TRADES_DB_PATH = os.getenv("DASHBOARD_TRADES_DB_PATH", "")

PHASE1_PROVIDER = os.getenv("PHASE1_PROVIDER", "gemini")
PHASE1_MODEL    = os.getenv("PHASE1_MODEL", "gemini-2.0-flash")
PHASE2_PROVIDER = os.getenv("PHASE2_PROVIDER", "gemini")
PHASE2_MODEL    = os.getenv("PHASE2_MODEL", "gemini-2.0-flash")
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

for _d in (CACHE_DIR, UPLOADS_DIR, REPORTS_DIR, LOGS_DIR, DEBUG_BUNDLES_DIR, DB_PATH.parent):
    _d.mkdir(parents=True, exist_ok=True)
