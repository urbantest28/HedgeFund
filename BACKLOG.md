# HedgeFund Analyser — Feature Backlog

Priority labels: `P1` high-impact, `P2` medium, `P3` nice-to-have

---

## Data & Inputs

| # | Priority | Feature | Notes |
|---|----------|---------|-------|
| D1 | P1 | **Reddit credentials recovery** | Update `.env` with new `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT` (script-type app). Current 401 returns 0 posts on every run. |
| D2 | P2 | **Additional macro indicators** | Expand FRED pulls: CPI, PCE, unemployment rate, yield curve (10Y–2Y spread). Feed into Macro Analyst prompt. |
| D3 | P2 | **Insider transactions feed** | Pull SEC Form 4 filings (OpenInsider API or EDGAR) to add insider buy/sell signal to Fundamental Analyst. |
| D4 | P2 | **Options flow data** | Integrate put/call ratio and unusual options activity (e.g. Unusual Whales or CBOE). New data node in aggregator, new skill in Sentiment. |
| D5 | P3 | **Earnings call transcript ingestion** | Fetch transcript text (Seeking Alpha or Motley Fool scrape) and supply it to Earnings Reviewer instead of relying solely on structured EPS data. |
| D6 | P3 | **Short interest data** | Pull short float %, days-to-cover from Finviz or SEC. Add to Technical Analyst context. |

---

## Agent & Pipeline

| # | Priority | Feature | Notes |
|---|----------|---------|-------|
| A1 | P1 | **Multi-ticker batch queue** | Accept a list of tickers; run analyses sequentially with a job queue. Show queue status in the UI. Useful for sector sweeps. |
| A2 | P2 | **Sector / peer comparison** | After individual analysis, run a lightweight cross-ticker scoring pass against 3–5 peers. Adds relative valuation context to the PM verdict. |
| A3 | P2 | **Configurable debate rounds** | Expose `MAX_DEBATE_ROUNDS` as a UI slider (currently hardcoded). Allow 1–5 rounds depending on how contested the thesis is. |
| A4 | P2 | **Agent model A/B harness** | Let user switch Phase 1/2 agents between Gemini Flash and Gemini Pro (or Claude Haiku vs Sonnet) and compare score outputs side-by-side. |
| A5 | P3 | **Confidence-weighted aggregation** | Weight Phase 1 agent scores by their `confidence` field before passing to Phase 2, rather than treating all scores equally. |
| A6 | P3 | **Prompt tuning UI** | Simple web editor for files in `prompts/roles/` and `prompts/skills/` so prompts can be tweaked without touching the filesystem. |

---

## Outputs & Reports

| # | Priority | Feature | Notes |
|---|----------|---------|-------|
| O1 | P1 | **Excel model output** | Generate an `.xlsx` per run: DCF tab, comparables tab, assumptions tab, summary dashboard. `openpyxl` is already installed. |
| O2 | P2 | **PDF export** | One-click PDF of the HTML report (WeasyPrint or Playwright headless print). |
| O3 | P2 | **Multi-run comparison view** | Side-by-side table in the Runs tab: ticker, date, verdict, composite score, entry/stop/target. Sortable columns. |
| O4 | P3 | **Performance tracking** | After a watchlist entry is closed, record the actual return vs. the PM's price target. Show a running scorecard of verdict accuracy. |
| O5 | P3 | **Report sharing link** | Generate a signed URL (or static HTML export) so a report can be sent to someone without them running the server. |

---

## Monitoring & Alerts

| # | Priority | Feature | Notes |
|---|----------|---------|-------|
| M1 | P1 | **Live price streaming** | Replace daily poll with a WebSocket or SSE feed (yfinance `download` with `period="1d"` and `interval="1m"`). Push price updates to the Watchlist tab in real time. |
| M2 | P2 | **Alert channel options** | Add Slack webhook and email (SMTP) as alternatives to ntfy.sh. Configured per watchlist entry. |
| M3 | P2 | **Volume spike alert** | Trigger alert if intraday volume exceeds 2× 30-day average — useful for early momentum detection. |
| M4 | P3 | **Re-analyse trigger** | When a watchlist stock hits a configurable drift threshold (e.g. ±15% from entry price), automatically queue a fresh analysis run. |

---

## UI & Developer Experience

| # | Priority | Feature | Notes |
|---|----------|---------|-------|
| U1 | P2 | **Dark mode** | Toggle between light and dark Tailwind theme. Persist preference in `localStorage`. |
| U2 | P2 | **Ticker autocomplete** | As user types in the analyse input, suggest matching tickers from a cached symbol list (e.g. NASDAQ/NYSE symbols JSON). |
| U3 | P2 | **Run history search & filter** | Filter Runs tab by verdict (BUY/HOLD/AVOID), date range, or composite score. Currently a flat list. |
| U4 | P3 | **Keyboard shortcuts** | `Cmd+K` / `Ctrl+K` command palette to navigate tabs and start a run without reaching for the mouse. |
| U5 | P3 | **Mobile-responsive layout** | Watchlist and Runs tabs are usable on mobile; the Analyse tab SSE stream needs a condensed card layout. |

---

## Infrastructure & Testing

| # | Priority | Feature | Notes |
|---|----------|---------|-------|
| I1 | P2 | **Backtesting mode** | Given a ticker and historical date, replay analysis using data snapshotted at that point in time. Useful for validating agent logic against known outcomes. |
| I2 | P2 | **Docker Compose setup** | Containerise FastAPI + SQLite so the app is one-command deployable. Add `docker-compose.yml` and `Dockerfile`. |
| I3 | P2 | **CI test pipeline** | GitHub Actions workflow: run `pytest tests/ -x` on every push to `main` and every PR. Currently no automated CI. |
| I4 | P3 | **Rate limit dashboard** | Track API quota usage (Alpha Vantage calls/day, Gemini tokens/min) in the DB. Surface warnings in the UI before a run hits a wall. |
| I5 | P3 | **Structured logging to file** | Persist `[hf:{module}]` log lines to a rotating file (`logs/run_{id}.log`) so past runs are inspectable without a debug bundle. |
