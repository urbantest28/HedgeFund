# HedgeFund Analyser

A standalone multi-agent simulated hedge fund that analyses stocks through 9 specialised AI agents and produces a scored verdict, HTML report, Excel financial model, and watchlist entry.

## Pipeline

```
Phase 1 (parallel): Fundamental | Technical | Sentiment | Macro | Earnings Reviewer
Phase 2 (parallel): Risk Manager | Thesis Validator | Financial Modeler
Phase 3 (debate):   Bull Agent ↔ Bear Agent  (Claude Opus 4.7)
Phase 4:            Portfolio Manager         (Claude Opus 4.7)
                          ↓
         Score 1-5 + Expected Returns + HTML Report + Watchlist Entry
```

## Setup

### 1. Clone and create virtual environment
```bash
git clone https://github.com/urbantest28/HedgeFund.git
cd HedgeFund
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API keys
```bash
copy .env.example .env
# Edit .env with your API keys — see .env.example for descriptions
```

**Required API keys:**
- `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com)
- `GOOGLE_API_KEY` — [aistudio.google.com](https://aistudio.google.com) (free tier)
- `MASSIVE_MARKET_API_KEY` — your existing subscription
- `ALPHA_VANTAGE_API_KEY` — [alphavantage.co](https://alphavantage.co) (free tier)
- `FRED_API_KEY` — [fred.stlouisfed.org/docs/api](https://fred.stlouisfed.org/docs/api/api_key.html) (free)
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (free, create a "script" app)
- `NTFY_TOPIC` — choose any unique name, subscribe in the [ntfy app](https://ntfy.sh)

### 3. Run
```bash
python main.py
# Open http://localhost:8000 in your browser
```

## Reports

After every successful analysis, an HTML report is automatically saved to `reports_output/TICKER_YYYYMMDD.html`. Open the file directly in a browser, or request regeneration via `GET /report/{run_id}` against the running server.

## Daily Watchlist Monitor

`pipeline/monitor.py` checks live prices for all watchlist entries against entry zones, stop losses, and target prices. When triggered, an ntfy.sh alert is pushed.

**Install daily Windows scheduled task:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_monitor_task.ps1
```

Runs daily at 16:30 local time. Logs go to `logs/monitor_task.log`.

**Verify or trigger manually:**

```powershell
schtasks /Query /TN HedgeFundWatchlistMonitor /V /FO LIST
schtasks /Run /TN HedgeFundWatchlistMonitor
```

**Uninstall:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_monitor_task.ps1
```

## Debugging
See `CLAUDE.md` for the full debugging workflow including `replay_run.py`, `run_agent.py`, and `inspect_run.py`.

## Design Spec
Full design document at `ISA Statements/Dashboard/docs/superpowers/specs/2026-05-10-hedgefund-multiagent-design.md`
