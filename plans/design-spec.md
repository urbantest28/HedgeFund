# HedgeFund Multi-Agent Analyser — Design Spec
**Date:** 2026-05-10  
**Status:** Approved for implementation  
**Project location:** `<project_root>\`

---

## 1. Overview

A standalone simulated hedge fund that analyses a stock through 9 specialised AI agents, validates the trade against existing investment theses, runs a Bull vs Bear debate, and produces a final verdict, HTML report, Excel financial model, and watchlist entry. Designed for future integration with the ISA Portfolio Dashboard.

**Trigger:** Local web UI — user enters a ticker, clicks Analyse, watches live progress.  
**Output:** Score (1–5), expected returns, HTML report, Excel model, watchlist entry in `hedgefund.db`.  
**Integration path:** Standalone now; watchlist schema mirrors `trades.db` for easy future import.

---

## 2. Tech Stack

| Component | Technology | Cost |
|---|---|---|
| Backend | FastAPI + Uvicorn | Free |
| Frontend | HTML + Tailwind CSS (CDN) + Vanilla JS | Free |
| Streaming | Server-Sent Events (SSE) via FastAPI | Free |
| Parallel execution | Python asyncio | Free |
| LLM — mechanical tasks | Google Gemini 2.0 Flash API | Free (1,500 req/day) |
| LLM — reasoning tasks | Anthropic Claude Opus 4.7 API | ~£0.25–0.35/run |
| Database | SQLite (`hedgefund.db`) | Free |
| Excel output | openpyxl | Free |
| Phone alerts | ntfy.sh | Free |
| Scheduled monitor | Windows Task Scheduler | Free |

**Why FastAPI over Flask:** async-native, SSE streaming and parallel asyncio agents work without threading hacks.

---

## 3. LLM Routing

Model assignment is configurable in `.env` — switching provider requires no code changes.

| Phase | Agents | Provider | Model | Reason |
|---|---|---|---|---|
| Phase 1 | Fundamental, Technical, Sentiment, Macro, Earnings | Gemini | gemini-2.0-flash | Structured data extraction — Gemini capable enough, free |
| Phase 2 | Risk Manager, Thesis Validator, Financial Modeler | Gemini | gemini-2.0-flash | Structured analysis — Gemini capable enough, free |
| Phase 3 | Bull, Bear | Claude | claude-opus-4-7 | Argumentation, counter-reasoning — quality matters |
| Phase 4 | Portfolio Manager | Claude | claude-opus-4-7 | Complex synthesis, final verdict — quality matters |

**Estimated cost per full run:** ~£0.25–0.35 (Opus calls only).

---

## 4. The 4-Phase Pipeline

```
Phase 1 ── parallel ──────────────────────────────────────────────
  [Fundamental]  [Technical]  [Sentiment]  [Macro]  [Earnings]
         ↓              ↓           ↓           ↓         ↓
Phase 2 ── parallel ──────────────────────────────────────────────
       [Risk Manager]    [Thesis Validator]    [Financial Modeler]
                   ↓              ↓                    ↓
Phase 3 ── debate loop ───────────────────────────────────────────
                Bull Agent ↔ Bear Agent
                max 4 rounds | conviction score 1–10 per round
                ends: gap ≤ 2 (consensus) OR max rounds (contested)
                              ↓
Phase 4 ── final verdict ─────────────────────────────────────────
                       Portfolio Manager
                              ↓
         Score (1–5) + Expected Returns + Report + Watchlist Entry
```

**Abort rule:** if 2 or more Phase 1 agents return `data_confidence: minimal`, the pipeline halts before Phase 2. No watchlist entry written. Report shows exactly which data fields failed.

**Contested rule:** if Bull/Bear gap > 2 after 4 rounds → `contested: true`. Portfolio Manager still runs. Watchlist entry tagged `⚠ Contested`.

---

## 5. Agents

### Phase 1 — Data Analysts (Gemini 2.0 Flash)

**Fundamental Analyst**  
Analyses financial health from historical data. Calculates intrinsic value via DCF, compares vs peers via relative valuation. Peers auto-selected from yfinance sector/industry classification by market cap (top 3–5).  
Skills: `financial_ratio_analysis`, `dcf_valuation`, `relative_valuation`

**Technical Analyst**  
Reads price history, identifies trend, support/resistance, momentum signals. Outputs suggested entry zones based on technicals.  
Skills: `chart_pattern_recognition`, `momentum_indicators`

**Sentiment Analyst**  
Analyses news articles and Reddit posts. Identifies trending posts, post volume acceleration, recurring themes, notable DD posts. Outputs sentiment breakdown and social momentum signals.  
Skills: `sentiment_scoring`

**Macro Analyst**  
Assesses rate environment, inflation, GDP trend, sector rotation signals, FX exposure if applicable.  
Skills: `macro_regime_analysis`

**Earnings Reviewer**  
Compares most recent quarter EPS and revenue vs analyst estimates. Reviews last 4 quarters beat/miss history. Analyses guidance language. If earnings call transcript available (via SEC EDGAR 8-K Exhibit 99.1, Alpha Vantage, or manual upload), extracts management tone, hedging language, Q&A pushback, and any narrative/numbers discrepancy.  
Skills: `earnings_transcript_analysis`

### Phase 2 — Assessment (Gemini 2.0 Flash)

**Risk Manager**  
Uses Phase 1 outputs to calculate suggested position size, stop-loss rationale, max drawdown, correlation with existing holdings (reads `trades.db` read-only via `DASHBOARD_TRADES_DB_PATH`).  
Skills: `position_sizing`, `financial_ratio_analysis`

**Thesis Validator**  
Checks stock against active theses in `trades.db`. Pass conditions: (A) ticker directly listed in a thesis, OR (B) stock sector/theme aligns with an active thesis theme. Reports match type. Conflicts noted.  
Skills: `thesis_matching`

**Financial Modeler**  
Builds a 3-statement model (Income Statement, Balance Sheet, Cash Flow) with 3–5 year projections. Outputs DCF summary (base/bull/bear scenario, discount rate, terminal growth rate, intrinsic value range). Calculates expected return ranges for 6m, 1y, 2y, 5y, 10y horizons. Saves Excel file to `reports_output/TICKER_YYYYMMDD_model.xlsx`.  
Skills: `dcf_valuation`, `financial_ratio_analysis`

### Phase 3 — Debate (Claude Opus 4.7)

**Bull Agent**  
Argues the strongest possible case FOR buying, drawing from all Phase 1 and Phase 2 outputs. Must engage directly with Bear's counterarguments each round. May only concede a point if evidence is overwhelming. Outputs argument text + conviction score (1–10) per round.  
Skills: `sentiment_scoring`, `debate_protocol`

**Bear Agent**  
Argues the strongest possible case AGAINST buying. Challenges optimistic assumptions, surfaces downside risks. Same round structure as Bull. Outputs argument text + conviction score (1–10) per round.  
Skills: `sentiment_scoring`, `debate_protocol`

**Debate loop logic:**
- Each round: Bull argues → Bear responds → scores recorded
- After each round: if `abs(bull_score - bear_score) <= 2` → consensus, debate ends early
- After round 4: if gap > 2 → `contested: true`, dominant score noted, debate ends
- Full transcript passed to Portfolio Manager

### Phase 4 — Verdict (Claude Opus 4.7)

**Portfolio Manager**  
Receives summaries (≤150 words each) from all 8 agents plus full debate transcript. Audits data confidence scores first — any `minimal` agent flagged prominently. Synthesises into final verdict.

Outputs:
- **Score 1–5:** 1=Strong Buy, 2=Buy, 3=Neutral, 4=Sell, 5=Strong Sell
- **Verdict:** `WATCHLIST` or `AVOID`
- **Tier:** `core` / `satellite` / `conviction`
- **Entry range, stop-loss, target price**
- **Expected returns:** 6m / 1y / 2y / 5y / 10y (range, bear→bull)
- **Linked thesis** (from Thesis Validator output)
- **Key risks** and **key catalysts to watch**
- **Suggested review date**
- **Contested flag** if applicable

---

## 6. Prompt Architecture

```
prompts/
├── roles/                          # Identity, responsibilities, guardrails, output schema
│   ├── fundamental_analyst.md
│   ├── technical_analyst.md
│   ├── sentiment_analyst.md
│   ├── macro_analyst.md
│   ├── earnings_reviewer.md
│   ├── risk_manager.md
│   ├── thesis_validator.md
│   ├── financial_modeler.md
│   ├── bull.md
│   ├── bear.md
│   └── portfolio_manager.md
│
└── skills/                         # HOW to do specific techniques (shared across agents)
    ├── financial_ratio_analysis.md
    ├── dcf_valuation.md
    ├── relative_valuation.md
    ├── chart_pattern_recognition.md
    ├── momentum_indicators.md
    ├── sentiment_scoring.md
    ├── macro_regime_analysis.md
    ├── position_sizing.md
    ├── thesis_matching.md
    ├── earnings_transcript_analysis.md
    └── debate_protocol.md
```

**Skills injection map:**

| Agent | Role file | Skills injected |
|---|---|---|
| Fundamental | `fundamental_analyst.md` | `financial_ratio_analysis`, `dcf_valuation`, `relative_valuation` |
| Technical | `technical_analyst.md` | `chart_pattern_recognition`, `momentum_indicators` |
| Sentiment | `sentiment_analyst.md` | `sentiment_scoring` |
| Macro | `macro_analyst.md` | `macro_regime_analysis` |
| Earnings | `earnings_reviewer.md` | `earnings_transcript_analysis` |
| Risk Manager | `risk_manager.md` | `position_sizing`, `financial_ratio_analysis` |
| Thesis Validator | `thesis_validator.md` | `thesis_matching` |
| Financial Modeler | `financial_modeler.md` | `dcf_valuation`, `financial_ratio_analysis` |
| Bull | `bull.md` | `sentiment_scoring`, `debate_protocol` |
| Bear | `bear.md` | `sentiment_scoring`, `debate_protocol` |
| Portfolio Manager | `portfolio_manager.md` | all skills |

`base_agent.py` loads and concatenates role + skills files at runtime. Updating any `.md` file takes effect on next run — no code changes required.

**Hard guardrail in every role.md:**
> "Always read your `data_manifest` before reasoning. For any field with `status: missing`, explicitly state the gap and reduce your score accordingly. Never infer or estimate missing data silently."

---

## 7. Data Sources & Redundancy

### Pre-fetch aggregator
All data fetched **before the pipeline starts**. Agents receive a static data bundle — no live API calls during agent execution. Massive Market Data rate-limited via token bucket (max 5 calls/min, calls queue rather than fail).

### Redundancy waterfall per data type

| Data type | Primary | Fallback 1 | Fallback 2 | Fallback 3 |
|---|---|---|---|---|
| Prices / OHLCV | Massive Market Data | yfinance | — | — |
| Fundamentals (ratios, P/E) | Massive Market Data | Alpha Vantage | yfinance | Manual upload |
| Income / Balance / Cash Flow | Alpha Vantage | SEC EDGAR | yfinance | Manual upload |
| Earnings vs estimates | Massive Market Data | Alpha Vantage | yfinance | — |
| Earnings call transcript | SEC EDGAR (8-K) | Alpha Vantage | Manual upload | — |
| News & sentiment | Massive Market Data | — | — | — |
| SEC filings (10-K / 10-Q) | SEC EDGAR (free) | Manual upload | — | — |
| Macro (rates, CPI, GDP) | FRED | — | — | — |
| Reddit sentiment | Reddit API | — | — | — |
| Peer financials | yfinance | Alpha Vantage | — | — |

**SEC EDGAR:** official free API at `data.sec.gov` — no key required.

### API free tier summary

| API | Free limit | Expected calls/run | Headroom |
|---|---|---|---|
| yfinance | Unlimited | ~0 (local lib) | Unlimited |
| Massive Market Data | Subscription, 5/min | 2–3 | Comfortable |
| Alpha Vantage | 25 req/day | 2–3 | ~8 runs/day |
| FRED | Unlimited | 1–2 | Unlimited |
| Reddit API | Free (read-only) | 1 | Generous |
| SEC EDGAR | Unlimited | 1–2 | Unlimited |
| Gemini 2.0 Flash | 1,500 req/day | ~8 | ~185 runs/day |
| ntfy.sh | Unlimited | 1 alert/day | Unlimited |

### Data manifest
Every agent receives a `data_manifest` alongside its data payload:
```json
{
  "revenue_ttm":    { "value": 385000000, "source": "alpha_vantage", "status": "ok" },
  "free_cash_flow": { "value": null,       "source": null,            "status": "missing" },
  "recent_news":    { "value": [...],      "source": "massive_market", "status": "partial",
                      "note": "3 articles retrieved, expected 20" }
}
```
Status values: `ok` | `partial` | `missing`  
Data confidence: `full` (all fields ok) | `partial` (1–2 non-critical missing) | `minimal` (critical fields missing)

---

## 8. Caching

Three tiers — the key principle: **historical facts that cannot change are cached forever; live data is never cached.**

### Tier 1 — Never cache (always fetch live)
Live price, intraday data, recent news (last 48h), Reddit posts, analyst ratings, forward earnings estimates.

### Tier 2 — Cache forever (immutable historical facts)
Past earnings (filed quarters), historical OHLCV (closed trading days), SEC filings (10-K/10-Q), historical income/balance/cashflow statements, historical FRED macro readings.

### Tier 3 — Cache with TTL
Market cap / P/E / EV/EBITDA (24h), sector/industry classification (7 days), company overview (30 days).

```
cache/
└── AAPL/
    ├── historical/          # Tier 2 — immutable, cached forever
    │   ├── ohlcv_2024.json
    │   ├── earnings_Q1_2026.json
    │   ├── financials_FY2025.json
    │   └── sec_10K_2025.pdf
    └── derived/             # Tier 3 — TTL-based
        ├── ratios.json      # TTL: 24h
        └── overview.json    # TTL: 30 days
```

Live price is always fetched first. If live fetch fails, run continues but report flags `⚠ Live price unavailable — using last known price from [date]`.

---

## 9. Database Schema (`hedgefund.db`)

```sql
-- Every analysis run
CREATE TABLE analysis_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    run_date        TEXT NOT NULL,
    status          TEXT NOT NULL,      -- 'complete' | 'failed' | 'contested' | 'paused'
    verdict         TEXT,               -- 'watchlist' | 'avoid'
    score           INTEGER,            -- 1-5
    tier            TEXT,
    entry_low       REAL,
    entry_high      REAL,
    stop_loss       REAL,
    target_price    REAL,
    thesis_id       INTEGER,
    thesis_match    TEXT,               -- 'ticker' | 'sector' | null
    contested       INTEGER DEFAULT 0,
    bull_score      INTEGER,
    bear_score      INTEGER,
    report_path     TEXT,
    model_path      TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- One row per agent per run
CREATE TABLE agent_outputs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES analysis_runs(id),
    agent           TEXT NOT NULL,
    phase           INTEGER NOT NULL,
    score           INTEGER,
    summary         TEXT,               -- capped at 150 words for PM context
    raw_output      TEXT,               -- full JSON stored separately
    data_confidence TEXT,               -- 'full' | 'partial' | 'minimal'
    duration_ms     INTEGER,
    status          TEXT NOT NULL       -- 'complete' | 'failed' | 'skipped'
);

-- Debate transcript
CREATE TABLE debate_rounds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES analysis_runs(id),
    round_number    INTEGER NOT NULL,
    bull_argument   TEXT,
    bear_argument   TEXT,
    bull_conviction INTEGER,
    bear_conviction INTEGER
);

-- Watchlist entries
CREATE TABLE watchlist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES analysis_runs(id),
    ticker          TEXT NOT NULL,
    added_date      TEXT NOT NULL,
    score           INTEGER,
    tier            TEXT NOT NULL,
    entry_low       REAL,
    entry_high      REAL,
    stop_loss       REAL,
    target_price    REAL,
    verdict_summary TEXT,
    contested       INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'watching',  -- 'watching' | 'promoted' | 'dismissed'
    alert_sent      INTEGER DEFAULT 0,
    notes           TEXT
);

-- Resume checkpoints
CREATE TABLE run_checkpoints (
    run_id          INTEGER NOT NULL REFERENCES analysis_runs(id),
    phase           INTEGER NOT NULL,
    completed_agents TEXT NOT NULL,     -- JSON list
    pending_agents  TEXT NOT NULL,      -- JSON list
    paused_reason   TEXT NOT NULL,      -- 'missing_data' | 'api_limit' | 'token_limit'
    missing_fields  TEXT NOT NULL,      -- JSON: field → {reason, sources_tried}
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Cache index
CREATE TABLE data_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    data_type       TEXT NOT NULL,
    cache_tier      TEXT NOT NULL,      -- 'forever' | 'ttl'
    source          TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    fetched_at      TEXT NOT NULL,
    expires_at      TEXT               -- null for tier-forever entries
);
```

---

## 10. Resume Failed Runs & Manual Upload

When a run is paused (missing data, API limit, token limit, network dropout), the pipeline:
1. Writes current state to `run_checkpoints`
2. Sets `analysis_runs.status = 'paused'`
3. Creates `uploads/TICKER/run_{id}/NEEDED.md` with exact instructions

**NEEDED.md (auto-generated):**
```
HedgeFund Analyser — Data Required
Run: AAPL | 2026-05-10 | Run ID: 42
Status: PAUSED — missing data

MISSING:
  ✗ 10-K Annual Report (FY2025)
    Reason: Massive Market Data rate limit reached, SEC EDGAR timeout
    Get it from: https://www.sec.gov → search AAPL → Annual Reports → 10-K FY2025
    Or: Apple Investor Relations → SEC Filings
    Drop file into: uploads/AAPL/run_42/
    Accepted formats: .pdf, .txt

Once files are uploaded, click [Resume Run] in the UI.
```

**Upload folder structure:**
```
uploads/
└── AAPL/
    └── run_42/
        ├── NEEDED.md           ← auto-generated
        └── 10K_FY2025.pdf      ← user drops here
```

The UI shows paused runs with a `⏸ Awaiting Data` badge, inline `NEEDED.md` content, and a drag-and-drop upload zone. `[Resume Run]` activates once required files are present. Pipeline restarts from the last completed agent checkpoint — not from scratch.

**Token limit mid-run:** pipeline saves state, resumes on next run with context trimmed to summaries only.

---

## 11. Watchlist Price Monitor & Phone Alerts

**`pipeline/monitor.py`** — runs daily via Windows Task Scheduler.

Checks every `status = 'watching'` entry in the watchlist against live price (always fetched fresh — never cached). Triggers ntfy.sh alert for:
- Entry zone hit: `current_price` falls within `entry_low–entry_high`
- Stop-loss breach: `current_price` falls below `stop_loss`
- Target hit: `current_price` reaches `target_price`

**Alert format:**
```
Title: HedgeFund Alert — AAPL
Body:  Entry zone hit — Current: $183.20 | Zone: $182–185 | Stop: $171 | Target: $210
```

`alert_sent` flag in watchlist prevents duplicate alerts for the same condition.

---

## 12. Report Structure (`reports_output/TICKER_YYYYMMDD.html`)

### Section 1 — Cover
Ticker, exchange, sector, analysis date, run duration, current price, market cap. Final score (1–5) and verdict displayed prominently.

### Section 2 — Data Quality
Every data field with source, status, fallbacks triggered, cache hits. Missing fields called out explicitly.

### Section 3 — Phase 1 Agent Reports
Each agent: score (X/10), data confidence, summary, bull points, bear points.
- **Fundamental:** ratios, DCF intrinsic value range, peer comparison table
- **Earnings:** EPS/revenue vs estimates, 4-quarter beat/miss history, guidance assessment, transcript highlights if available
- **Technical:** trend, support/resistance, RSI/MACD, suggested entry zones
- **Sentiment:** news breakdown, top 5 headlines with links, Reddit spotlight (trending posts, volume trend, notable DD)
- **Macro:** rate environment, inflation, sector tailwinds/headwinds

### Section 4 — Phase 2 Reports
- **Risk Manager:** position size %, stop-loss rationale, max drawdown, correlation with existing holdings
- **Thesis Validator:** matched thesis, match type, alignment score, conflicts
- **Financial Model:** 5-year projection table, DCF summary (base/bull/bear), `[Download Excel →]` button

### Section 5 — The Debate (full transcript)
Round-by-round: Bull argument, Bear argument, conviction scores. Conviction chart across rounds. Final result line: consensus or contested.

### Section 6 — Portfolio Manager Verdict
Full reasoning narrative. Agent weighting explanation. Score 1–5 with label. Expected returns table (6m/1y/2y/5y/10y, bear→bull range). Key risks. Key catalysts. Suggested review date.

### Section 7 — Additional Intelligence
- **Analyst Consensus:** buy/hold/sell distribution, median target vs current, target range
- **Upcoming Catalysts:** next earnings date, product launches, regulatory decisions
- **Insider Activity:** recent Form 4 filings (buying/selling) via SEC EDGAR
- **Short Interest:** % of float shorted
- **Options Sentiment:** put/call ratio if available
- **Reddit Spotlight:** trending posts with upvotes, post volume trend, sentiment breakdown

### Section 8 — Historical Fund Performance
(Populates over time) — past watchlist entries from this fund: score given, verdict, outcome (target hit / stopped out / dismissed), accuracy rate.

---

## 13. File Structure

```
HedgeFund/
├── main.py                     # FastAPI app, SSE endpoint, upload handler
├── .env                        # All keys + model config
├── requirements.txt
│
├── data/
│   ├── aggregator.py           # Orchestrates all fetchers, builds data bundle + manifest
│   ├── yfinance_client.py
│   ├── massive_market.py       # Token bucket rate limiter (5/min)
│   ├── alpha_vantage.py
│   ├── fred_client.py
│   ├── reddit_client.py
│   └── sec_edgar.py
│
├── agents/
│   ├── base_agent.py           # Provider router: Gemini or Claude based on .env
│   ├── fundamental.py
│   ├── technical.py
│   ├── sentiment.py
│   ├── macro.py
│   ├── earnings_reviewer.py
│   ├── risk_manager.py
│   ├── thesis_validator.py
│   ├── financial_modeler.py    # Also writes Excel via openpyxl
│   ├── bull.py
│   ├── bear.py
│   └── portfolio_manager.py
│
├── pipeline/
│   ├── orchestrator.py         # Phase runner, SSE emitter, checkpoint writer
│   ├── debate.py               # Bull/Bear loop, convergence, contested logic
│   └── monitor.py              # Daily watchlist price check + ntfy alerts
│
├── db/
│   └── database.py             # hedgefund.db schema + CRUD
│
├── reports/
│   └── generator.py            # HTML report builder
│
├── prompts/
│   ├── roles/                  # 11 role .md files
│   └── skills/                 # 11 skill .md files
│
├── static/
│   ├── style.css
│   └── app.js                  # SSE listener, progress bars, debate feed, upload handler
│
├── templates/
│   └── index.html              # Tailwind CDN, dark theme
│
├── cache/
│   └── {TICKER}/
│       ├── historical/
│       └── derived/
│
├── uploads/
│   └── {TICKER}/
│       └── run_{id}/
│           └── NEEDED.md
│
├── reports_output/             # HTML reports + Excel models
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/               # Frozen API responses — tests never hit real APIs
│   ├── unit/                   # Pure logic tests
│   ├── integration/            # Mocked HTTP + LLM
│   ├── e2e/                    # Full pipeline with fixture data
│   ├── regression/             # One test per fixed bug
│   └── failure_scenarios/      # Redundancy waterfall, propagation prevention
│
├── debug/
│   ├── bundles/                # Frozen data bundle per run (run_{id}_bundle.json)
│   ├── replay_run.py           # Replay any run_id — no API calls
│   ├── run_agent.py            # Run one agent in isolation
│   └── inspect_run.py          # Pretty-print all logs/outputs for a run_id
│
├── logs/
│   └── run_{id}.log            # One structured log file per run
│
└── CLAUDE.md                   # Debugging workflow, log patterns, model routing reference
```

---

## 14. Environment Variables (`.env`)

```
# Anthropic
ANTHROPIC_API_KEY=

# Google Gemini
GOOGLE_API_KEY=

# Massive Market Data
MASSIVE_MARKET_API_KEY=

# Alpha Vantage
ALPHA_VANTAGE_API_KEY=

# FRED
FRED_API_KEY=

# Reddit
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=hedgefund-analyser/1.0

# ntfy.sh
NTFY_TOPIC=your-hedge-fund-alerts

# Dashboard integration (read-only)
DASHBOARD_TRADES_DB_PATH=<isa_project>\Dashboard\src\trades.db

# Model routing
PHASE1_PROVIDER=gemini
PHASE1_MODEL=gemini-2.0-flash
PHASE2_PROVIDER=gemini
PHASE2_MODEL=gemini-2.0-flash
DEBATE_PROVIDER=anthropic
DEBATE_MODEL=claude-opus-4-7
PM_PROVIDER=anthropic
PM_MODEL=claude-opus-4-7
```

---

## 15. Error Handling

**Data fetch failure:** waterfall to next source → if all fail, field marked `missing` in manifest → agent flags gap explicitly, reduces score → if 2+ Phase 1 agents return `minimal`, pipeline aborts.

**Agent failure (Claude/Gemini error or malformed JSON):** retry once → on second failure, marked `failed` in `agent_outputs`, pipeline continues with warning → Portfolio Manager notes which agents failed.

**Debate non-convergence:** max 4 rounds, gap > 2 → `contested: true` → PM runs anyway → watchlist entry tagged `⚠ Contested`.

**API rate limit:** token bucket queues Massive Market Data calls rather than failing → other sources fetched in parallel while waiting.

**Run paused (missing data / token limit / network dropout):** checkpoint saved → `NEEDED.md` generated → UI shows resume UI with upload zone → pipeline restarts from last completed agent.

---

## 16. Testing Strategy

### Philosophy
Every component is testable in isolation. Tests never hit real APIs — all external calls use frozen fixture data. A failing run always produces enough context to replay and isolate the bug without reading the whole codebase.

### Test Structure

```
tests/
├── conftest.py                     # Shared fixtures: DB setup, frozen data bundle, mock clients
├── fixtures/
│   ├── aapl_data_bundle.json       # Frozen API responses for AAPL (used across all tests)
│   ├── sample_debate.json          # Sample Bull/Bear debate transcript
│   └── sample_agent_outputs/
│       ├── fundamental.json
│       ├── technical.json
│       ├── sentiment.json
│       ├── macro.json
│       ├── earnings_reviewer.json
│       ├── risk_manager.json
│       ├── thesis_validator.json
│       ├── financial_modeler.json
│       ├── bull.json
│       ├── bear.json
│       └── portfolio_manager.json
├── unit/                           # Pure logic, no I/O, no mocks needed
│   ├── test_cache_ttl.py           # TTL expiry logic, tier classification
│   ├── test_debate_convergence.py  # Gap ≤ 2 → consensus, max rounds → contested
│   ├── test_data_manifest.py       # Manifest generation, status propagation
│   ├── test_score_calculation.py   # 1-5 score derivation from agent scores
│   └── test_report_structure.py    # HTML report sections present, no missing fields
├── integration/                    # Component + dependency (mocked HTTP + LLM)
│   ├── test_data_fetchers.py       # Each fetcher: correct schema, 429 retry, empty response, fallback trigger
│   ├── test_agents.py              # Each agent: parses LLM output, handles malformed JSON, respects manifest
│   ├── test_pipeline_phases.py     # Phase sequencing, parallel execution, abort on 2× minimal
│   └── test_watchlist_db.py        # DB writes, duplicate detection, refresh mode, alert_sent flag
├── e2e/                            # Full pipeline with frozen fixture data
│   ├── test_full_run_aapl.py       # Complete run: all 4 phases, report generated, watchlist entry written
│   └── test_resume_checkpoint.py   # Pause mid-Phase 2 → upload fixture file → resume → completes
├── regression/                     # One test per fixed bug — never deleted
│   └── .gitkeep                    # Populated as bugs are fixed
└── failure_scenarios/
    ├── test_api_failures.py        # Massive Market 429 → fallback chain completes
    ├── test_missing_data.py        # 2× minimal agents → pipeline aborts, no watchlist write
    ├── test_agent_failures.py      # Claude/Gemini error → retry → marked failed → PM notes it
    └── test_propagation.py         # Missing field in manifest does NOT silently propagate to verdict

```

### Fixture data strategy
`tests/fixtures/aapl_data_bundle.json` is a complete frozen snapshot of every API response for AAPL. All tests import this rather than hitting real APIs. When a new data field is added, the fixture is updated once and all tests benefit. Fixtures are committed to the repository.

### Regression test rule
Every bug that reaches production gets a regression test in `tests/regression/` named after what broke:
```
tests/regression/
├── test_debate_contested_flag_missing_when_round4_tie.py
├── test_watchlist_duplicate_on_refresh.py
└── ...
```
This file is never deleted. Before declaring any bug fixed, the regression test must pass.

---

## 17. Debugging Infrastructure

### The problem being solved
Without structured debugging, every bug report triggers a full codebase scan to understand context. This section ensures any bug can be replicated in under 2 minutes with a single command.

### Structured logging format
Every log line follows this exact format — consistent across all modules:
```
[hf:{module}] [run_{id}] {message} | {key}: {value} | {key}: {value}
```

Examples:
```
[hf:aggregator]  [run_42] Fetching AAPL — Massive Market Data (prices)
[hf:cache]       [run_42] HIT historical/earnings_Q1_2026.json (immutable)
[hf:cache]       [run_42] MISS derived/ratios.json (expired 2h ago) → fetching
[hf:fundamental] [run_42] Gemini call started | tokens_in: 2847
[hf:fundamental] [run_42] Gemini call complete | score: 7 | confidence: partial | duration: 3.2s
[hf:manifest]    [run_42] free_cash_flow: MISSING (all sources failed)
[hf:pipeline]    [run_42] Phase 1 complete | agents: 5/5 | duration: 18.4s
[hf:debate]      [run_42] Round 1 | Bull: 6 | Bear: 7 | gap: 1 — converging
[hf:debate]      [run_42] Consensus at Round 2 | final gap: 1
[hf:pm]          [run_42] Final score: 2 (Buy) | verdict: WATCHLIST | tier: satellite
```

One log file per run: `logs/run_{id}.log`. Finding all logs for a run: `grep "[run_42]" logs/run_42.log`.

### Debug folder

```
debug/
├── replay_run.py      # Replay any past run using its saved data bundle
├── run_agent.py       # Run a single agent in isolation with frozen data
└── inspect_run.py     # Pretty-print all logs, agent outputs, debate for a run_id
```

**`replay_run.py`** — the most important debug tool:
```
python debug/replay_run.py 42
```
Loads the exact data bundle saved during run 42, re-executes the full pipeline with the same inputs, and writes a new log. No API calls made. Reproduces the bug in under 2 minutes.

**`run_agent.py`** — isolate a single agent:
```
python debug/run_agent.py fundamental 42
python debug/run_agent.py debate 42
```
Runs one agent against run 42's frozen data bundle. Used to confirm a fix before running the full pipeline.

**`inspect_run.py`** — human-readable summary of any run:
```
python debug/inspect_run.py 42
```
Prints: data manifest (what was fetched, from where, what failed), each agent's score and summary, debate transcript with conviction scores, final verdict, any errors flagged.

### Data bundle snapshot
Every run saves its complete input data to `debug/bundles/run_{id}_bundle.json` before the pipeline starts. This is the frozen snapshot that `replay_run.py` uses. It contains every field from every API source, the data manifest, and the cache state at run time. Stored indefinitely — never auto-deleted.

```
debug/
└── bundles/
    ├── run_42_bundle.json
    └── run_43_bundle.json
```

### The debugging loop

```
Bug reported: user describes symptom + run_id (visible in UI and report)
        ↓
python debug/inspect_run.py {run_id}
  → read data manifest: was data missing?
  → read agent outputs: which agent has unexpected score/summary?
  → read debate: did conviction scores behave correctly?
        ↓
python debug/run_agent.py {agent_name} {run_id}
  → isolate the failing component
  → read [hf:{module}] log lines for that agent
  → identify root cause (specific file + line)
        ↓
Apply fix
        ↓
python debug/run_agent.py {agent_name} {run_id}   ← confirm agent-level fix
python debug/replay_run.py {run_id}               ← confirm full pipeline fix
pytest tests/ -x                                  ← confirm no regressions
        ↓
Add test to tests/regression/ named after the bug
        ↓
git commit -m "fix: {description}" && git push
```

### CLAUDE.md for the HedgeFund project
The HedgeFund repository will include a `CLAUDE.md` that documents:
- The debugging loop above (so future Claude Code sessions follow it automatically)
- Log filter patterns per module
- How to use `replay_run.py`, `run_agent.py`, `inspect_run.py`
- The regression test rule
- Which agents use Gemini vs Claude (so model routing is never guessed)
- The data bundle snapshot location

This means any future debug session starts with full context — no codebase scan needed.

---

## 18. Repository Setup

**Separate GitHub repository:** `urbantest28/HedgeFund` (new repo, standalone from Dashboard)

**Local path:** `<project_root>\`

**Initialised with:**
- `CLAUDE.md` — debugging workflow, log patterns, model routing reference
- `.env.example` — all required keys listed with descriptions (`.env` gitignored)
- `.gitignore` — ignores `.env`, `cache/`, `debug/bundles/`, `logs/`, `reports_output/`, `uploads/`, `__pycache__/`, `*.db`
- `README.md` — setup instructions, how to run, API key setup guide

**Branch strategy:**
- `main` — stable, tested code only
- `feat/*` — feature branches (one per implementation phase)
- `fix/*` — bug fix branches (include run_id in branch name when fixing a specific reported bug e.g. `fix/run42-debate-contested-flag`)

---

## 19. v2 Features (not in v1)

- **Earnings call audio analysis:** `python analyse.py AAPL --with-audio recording.mp3` — Whisper transcription → Claude tone/sentiment analysis → added as supplementary report section tagged `[AUDIO ENHANCED]`
- **Multi-stock comparison mode:** analyse 2–3 tickers side-by-side, ranked by score
- **YAML agent config:** move `SKILLS_MAP` out of Python into `agents_config.yaml`
- **UI upgrade:** replace Tailwind prototype with a more professional design system
