# Plan 3: Pipeline + Web UI — Implementation Plan (Retrospective)

> **Retrospective document.** This plan documents what was built in Plan 3. All code shown reflects the actual implementation. Use as a reference when resuming from Plan 4.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the 11 agents from Plans 1–2 into a 4-phase async pipeline with SSE streaming, a Bull/Bear debate loop, daily watchlist price monitoring, and a dark-mode web UI for real-time progress.

**Architecture:** FastAPI serves SSE streams from an async orchestrator that runs Phase 1 (5 agents) and Phase 2 (3 agents) in parallel, Phase 3 as an iterative Bull/Bear debate, and Phase 4 as a single Portfolio Manager verdict. A separate `monitor.py` runs daily (Task Scheduler) to check watchlist prices and push ntfy.sh alerts. The frontend uses a ReadableStream SSE client (not EventSource) to render agent chips, debate cards, and the verdict in real-time.

**Tech Stack:** FastAPI, asyncio, concurrent.futures (thread executor), Server-Sent Events, Tailwind CSS (CDN), vanilla JS ReadableStream, yfinance (live price fetch), ntfy.sh (push alerts), SQLite via `db/database.py`

---

## File Map

| File | Role |
|------|------|
| `main.py` | FastAPI app — exposes all HTTP + SSE endpoints |
| `pipeline/orchestrator.py` | 4-phase runner, SSE queue emitter, abort rule, checkpoint writer |
| `pipeline/debate.py` | Bull/Bear round loop, convergence check, contested flag |
| `pipeline/monitor.py` | Daily watchlist price check + ntfy.sh alerts |
| `templates/index.html` | Dark Tailwind UI — 3 tabs, agent chips, debate feed, verdict card |
| `static/app.js` | SSE client, event handlers, upload flow, table renderers |
| `static/style.css` | Custom component styles (chips, debate cards, score badges) |
| `tests/unit/test_debate_convergence.py` | Unit tests for early-exit and contested logic |
| `tests/failure_scenarios/test_api_failures.py` | API failure handling tests |
| `tests/failure_scenarios/test_propagation.py` | Error propagation tests |
| `tests/e2e/test_data_layer_smoke.py` | Smoke test for data layer integration |

---

## Task 1: FastAPI Application (`main.py`)

**Files:**
- Create: `main.py`

### Endpoints built

| Method | Path | Purpose | Streaming? |
|--------|------|---------|-----------|
| `GET` | `/` | Serves `templates/index.html` | No |
| `POST` | `/analyse` | Start new analysis run | **Yes (SSE)** |
| `POST` | `/resume/{run_id}` | Resume paused run from checkpoint | **Yes (SSE)** |
| `POST` | `/upload/{ticker}/{run_id}` | File upload for paused runs | No |
| `GET` | `/runs` | List last N runs (default 20) | No |
| `GET` | `/runs/{run_id}` | Run detail: outputs, debate, checkpoint, NEEDED.md | No |
| `GET` | `/watchlist` | Watchlist entries (default status="watching") | No |
| `POST` | `/monitor` | Manual watchlist price check trigger | No |

### Key implementation details

- `POST /analyse` accepts `{"ticker": "AAPL"}` JSON body. Calls `stream_analysis(ticker, db)` from orchestrator. Returns `StreamingResponse(media_type="text/event-stream")`.
- `POST /resume/{run_id}` calls `stream_resume(run_id, db)` from orchestrator. Same streaming response.
- `POST /upload/{ticker}/{run_id}` writes files to `uploads/{ticker}/run_{run_id}/`. Returns `{"status": "ok", "files": [...]}`.
- `GET /runs/{run_id}` reads `agent_outputs`, `debate_rounds`, `run_checkpoints` tables and returns them merged with the run record.
- `Database()` is instantiated once at module level (singleton pattern).

- [ ] **Verification:** `uvicorn main:app --reload` starts without error. `curl -X POST http://localhost:8000/analyse -H "Content-Type: application/json" -d '{"ticker":"AAPL"}'` begins an SSE stream.

---

## Task 2: Pipeline Orchestrator (`pipeline/orchestrator.py`)

**Files:**
- Create: `pipeline/orchestrator.py`
- Create: `pipeline/__init__.py`

### Constants

```python
PHASE1_AGENT_CLASSES = [
    FundamentalAgent, TechnicalAgent, SentimentAgent,
    MacroAgent, EarningsReviewerAgent
]
PHASE2_AGENT_CLASSES = [
    RiskManagerAgent, ThesisValidatorAgent, FinancialModelerAgent
]
```

### Key functions

**`_save_bundle_snapshot(run_id, bundle)`**
- Writes `debug/bundles/run_{run_id}_bundle.json` for post-mortem inspection.

**`_run_agent_async(agent, bundle, run_id, loop)`**
- Wraps synchronous `agent.run(bundle, run_id)` in `loop.run_in_executor(None, ...)` so all agents in a phase can run truly in parallel without blocking the async event loop.
- Returns the agent result dict.

**`_run_phase_parallel(agent_classes, bundle, run_id, db, loop, queue, phase)`**
- Creates one agent instance per class.
- Gathers all `_run_agent_async` calls with `asyncio.gather()`.
- As each completes: saves result to `agent_outputs` table, puts `agent_complete` event on SSE queue.
- Returns `list[dict]` of all agent results.

**`_build_summaries(results)`**
- Transforms agent result list into `{agent_name: {score, summary, data_confidence, bull_points, bear_points}}`.
- Keyed by `agent_name` for easy bundle lookup.

**`_run_pipeline(ticker, run_id, db, queue, transcript_path=None)`** *(async)*

```
1. DataAggregator(db).fetch_all(ticker) → bundle
   emit: fetch_start, fetch_complete

2. Phase 1: _run_phase_parallel(PHASE1_AGENT_CLASSES, ...)
   emit: phase_start, agent_complete ×5, phase_complete
   ABORT CHECK: if len([r for r in results if r["data_confidence"] == "minimal"]) >= 2:
       set run status="failed", emit abort event, return

3. bundle["phase1_summaries"] = _build_summaries(phase1_results)

4. Phase 2: _run_phase_parallel(PHASE2_AGENT_CLASSES, ...)
   emit: phase_start, agent_complete ×3, phase_complete

5. bundle["phase2_summaries"] = _build_summaries(phase2_results)

6. Phase 3 (debate):
   emit: phase_start
   async for event in run_debate(bundle, run_id, db, loop):
       await queue.put(event)   # debate_round events forwarded directly
   emit: phase_complete

7. Phase 4 (PM):
   pm = PortfolioManagerAgent()
   result = await _run_agent_async(pm, bundle, run_id, loop)
   emit: phase_start, agent_complete, verdict, complete
   DB updates: analysis_runs (verdict, score, tier, entry/stop/target)
   If verdict == "WATCHLIST" and score > 0: insert watchlist row
```

**`stream_analysis(ticker, db, transcript_path=None)`** *(async generator)*
- Creates `analysis_runs` row (status="running").
- Creates `asyncio.Queue()`.
- Spawns `asyncio.create_task(_run_pipeline(...))`.
- Loops `await queue.get()` — yields each item as `data: {json}\n\n` SSE string.
- Terminates when `None` sentinel is received from queue.

**`stream_resume(run_id, db)`** *(async generator)*
- Reads checkpoint from `run_checkpoints` table.
- Re-fetches bundle snapshot from `debug/bundles/`.
- Calls `_run_pipeline` from the last completed phase.

### SSE event payload shapes

```python
# agent_complete
{"event": "agent_complete", "agent": "fundamental", "phase": 1,
 "score": 7, "data_confidence": "full", "status": "complete", "duration_ms": 4200}

# debate_round — forwarded directly from debate.py
{"event": "debate_round", "round": 1, "bull_conviction": 8,
 "bear_conviction": 5, "gap": 3,
 "bull_argument": "...(500 chars max)...",
 "bear_argument": "...(500 chars max)..."}

# verdict
{"event": "verdict", "verdict": "WATCHLIST", "tier": "Strong Buy", "score": 2,
 "entry_low": 171.50, "entry_high": 175.00, "stop_loss": 163.00,
 "target_price": 210.00,
 "expected_returns": {"bear": {"1m": -3, "3m": -8, "12m": -15},
                      "base": {"1m": 4, "3m": 12, "12m": 28},
                      "bull": {"1m": 8, "3m": 22, "12m": 45}},
 "reasoning": "...", "key_risks": [...], "key_catalysts": [...],
 "contested": false}
```

- [ ] **Verification:** `python debug/replay_run.py {run_id}` replays a completed run without hitting real APIs.

---

## Task 3: Debate Loop (`pipeline/debate.py`)

**Files:**
- Create: `pipeline/debate.py`

### Constants

```python
MAX_ROUNDS = 4
CONSENSUS_GAP = 2
```

### `run_debate(bundle, run_id, db, loop)` *(async generator)*

```python
async def run_debate(bundle, run_id, db, loop):
    bull = BullAgent()
    bear = BearAgent()
    bear_prev_argument = None
    bull_prev_argument = None
    transcript = []

    for round_num in range(1, MAX_ROUNDS + 1):
        # Bull goes first
        bull_result = await _run_agent_async(bull, bundle, run_id, loop,
                                              extra={"bear_argument": bear_prev_argument,
                                                     "round_number": round_num})
        bull_conviction = bull_result["conviction"]
        bull_argument = bull_result["argument"]

        # Bear responds
        bear_result = await _run_agent_async(bear, bundle, run_id, loop,
                                              extra={"bull_argument": bull_argument,
                                                     "round_number": round_num})
        bear_conviction = bear_result["conviction"]
        bear_argument = bear_result["argument"]

        gap = abs(bull_conviction - bear_conviction)
        round_data = {
            "round": round_num,
            "bull_argument": bull_argument[:500],
            "bear_argument": bear_argument[:500],
            "bull_conviction": bull_conviction,
            "bear_conviction": bear_conviction,
            "gap": gap
        }
        transcript.append(round_data)
        db.save_debate_round(run_id, round_num, bull_argument, bear_argument,
                             bull_conviction, bear_conviction)

        yield {"event": "debate_round", **round_data}

        if gap <= CONSENSUS_GAP:
            break  # Early consensus

        bear_prev_argument = bear_argument
        bull_prev_argument = bull_argument

    contested = gap > CONSENSUS_GAP
    dominant_score = max(bull_conviction, bear_conviction)

    bundle["debate_transcript"] = transcript
    bundle["debate_contested"] = contested
    bundle["debate_dominant_score"] = dominant_score

    yield {"event": "debate_complete",
           "contested": contested,
           "rounds": len(transcript),
           "bull_score": bull_conviction,
           "bear_score": bear_conviction}
```

**Bull/Bear agent contract** — these agents use `run_round()` not `run()`:

```python
# bull.run_round(bundle, run_id, round_number, bear_argument) → dict
{"argument": str, "conviction": int}  # conviction 1–10
```

- [ ] **Verification:** `pytest tests/unit/test_debate_convergence.py -v` — tests early exit at gap ≤ 2, contested=True when gap > 2 after 4 rounds.

---

## Task 4: Watchlist Monitor (`pipeline/monitor.py`)

**Files:**
- Create: `pipeline/monitor.py`

### `_fetch_live_price(ticker)` → `Optional[float]`

```python
def _fetch_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        price = t.fast_info.get("last_price")
        if price:
            return float(price)
        # Fallback: 1-day history
        hist = t.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        log.warning(f"[hf:monitor] Price fetch failed for {ticker}: {e}")
    return None
```

### `_send_alert(ticker, title, body)` → `None`

```python
def _send_alert(ticker, title, body):
    requests.post(
        "https://ntfy.sh/your-ntfy-topic",
        data=body.encode("utf-8"),
        headers={"Title": title, "Priority": "high", "Tags": "chart_with_upwards_trend"},
        timeout=10
    )
```

Alert message format:
```
Title: "HedgeFund Alert — AAPL"
Body:  "ENTRY ZONE — Current: $172.30 | Zone: $171–$175 | Stop: $163 | Target: $210"
```

### `run_monitor(db=None)` → `dict`

```python
{
    "checked": int,   # number of watchlist entries checked
    "alerted": int,   # number of alerts sent
    "errors": int,    # number of price fetch failures
    "run_at": str     # ISO timestamp
}
```

Logic:
```
for each "watching" entry in watchlist:
    price = _fetch_live_price(ticker)
    if price is None: errors += 1; continue
    if entry.alert_sent == 1: continue
    if price <= entry.stop_loss:
        _send_alert(ticker, "STOP LOSS", ...)
        db.mark_alert_sent(entry.id)
        alerted += 1
    elif entry.entry_low <= price <= entry.entry_high:
        _send_alert(ticker, "ENTRY ZONE", ...)
        db.mark_alert_sent(entry.id)
        alerted += 1
    elif price >= entry.target_price:
        _send_alert(ticker, "TARGET REACHED", ...)
        db.mark_alert_sent(entry.id)
        alerted += 1
    checked += 1
```

Run standalone: `python -m pipeline.monitor`

- [ ] **Verification:** `pytest tests/unit/test_monitor.py -v` with mocked yfinance + mocked requests.post.

---

## Task 5: Web UI — HTML (`templates/index.html`)

**Files:**
- Create: `templates/index.html`

### Layout

Dark-mode, Tailwind CDN. Three tabs at the top: **Analyse**, **Watchlist**, **Runs**.

### Analyse Tab — complete DOM structure

```
#pane-analyse
  ├── Input panel
  │     ├── #ticker-input (maxlength=10, uppercase)
  │     ├── #analyse-btn "Analyse"
  │     └── Help text "Analysis takes 3–5 minutes"
  │
  └── Live progress panel (hidden until run starts)
        ├── Run header card
        │     ├── #run-ticker  (bold ticker display)
        │     ├── #run-id-badge  ("run #N")
        │     └── #run-status-badge  (Running / Complete / Failed)
        │
        ├── Phase 1 card — "Phase 1 — Data Analysts (Gemini)"
        │     ├── #p1-status
        │     └── #p1-agents  (5-col chip grid)
        │
        ├── Phase 2 card — "Phase 2 — Assessment (Gemini)"
        │     ├── #p2-status
        │     └── #p2-agents  (3-col chip grid)
        │
        ├── Phase 3 card — "Phase 3 — Bull vs Bear Debate (Claude Opus)"
        │     ├── #p3-status
        │     ├── #debate-feed  (scrollable, max-h-96)
        │     └── #debate-summary  (hidden until debate_complete)
        │
        ├── Phase 4 card — "Phase 4 — Portfolio Manager (Claude Opus)"
        │     ├── #p4-status
        │     └── #pm-output  (PM reasoning text)
        │
        ├── #verdict-card  (hidden until verdict event)
        │     ├── Verdict label + tier + #verdict-score badge
        │     ├── Entry: #verdict-entry  Stop: #verdict-stop  Target: #verdict-target
        │     ├── #verdict-returns  (3×4 table: Horizon | Bear | Base | Bull)
        │     ├── #verdict-reasoning
        │     ├── #verdict-risks  (bulleted, red)
        │     ├── #verdict-catalysts  (bulleted, green)
        │     └── #verdict-contested  (yellow warning, hidden unless contested=true)
        │
        ├── #abort-card  (hidden until abort event)
        │     ├── #abort-reason
        │     └── failed agents list
        │
        └── #upload-zone  (hidden; shown when run paused)
              ├── "⏸ Run Paused — Data Required"
              ├── #needed-md  (NEEDED.md content)
              ├── #drop-area  (drag-drop + click-to-browse)
              └── #resume-btn  "Resume Run" (disabled until files uploaded)
```

### Watchlist Tab (`#pane-watchlist`)

Table columns: **Ticker** | **Score** | **Tier** | **Entry Zone** | **Stop** | **Target** | **Added** | **Status**

- Ticker cell: bold uppercase + ⚠ if `contested=true`
- Score cell: `.score-badge` (1–5, colour-coded)
- Stop: red text. Target: green text.

### Runs Tab (`#pane-runs`)

Table columns: **ID** | **Ticker** | **Date** | **Status** | **Verdict** | **Score**

- [ ] **Verification:** Open `http://localhost:8000` in browser — three tabs visible, dark background, Tailwind styles loaded.

---

## Task 6: Web UI — JavaScript (`static/app.js`)

**Files:**
- Create: `static/app.js`

### Global state

```js
let currentRunId = null;
let activeSource = null;   // active ReadableStream reader (for cleanup)
```

### SSE connection (ReadableStream, not EventSource)

```js
async function openStream(url, body) {
    if (activeSource) activeSource.cancel();
    const resp = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body)
    });
    const reader = resp.body.getReader();
    activeSource = reader;
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
            if (line.startsWith("data: ")) {
                try {
                    const ev = JSON.parse(line.slice(6));
                    handleEvent(ev);
                } catch (_) {}
            }
        }
    }
}
```

### Event router `handleEvent(ev)`

| `ev.event` | Handler |
|-----------|---------|
| `run_start` / `run_resume` | Set `currentRunId = ev.run_id`; update `#run-id-badge` |
| `fetch_start` | Set `#p1-status` = "Fetching data…" |
| `fetch_complete` | Set `#p1-status` = "Data ready" |
| `phase_start` | `onPhaseStart(ev.phase, ev.agents)` |
| `agent_complete` | `onAgentComplete(ev)` |
| `phase_complete` | `onPhaseComplete(ev.phase)` |
| `debate_round` | `onDebateRound(ev)` |
| `debate_complete` | `onDebateComplete(ev)` |
| `verdict` | `onVerdict(ev)` |
| `complete` | `onComplete()` |
| `abort` | `onAbort(ev)` |
| `error` | `showError(ev.message)` |

### Key handler implementations

**`onPhaseStart(phase, agents)`**
- Shows phase card, sets status to spinner "Running…"
- For phase 1/2: renders empty `.agent-chip` elements (one per agent name) in `#p1-agents` / `#p2-agents`

**`onAgentComplete(ev)`**
- Finds chip by `ev.agent` name, removes pulse animation
- Sets chip colour: green=complete, red=failed, amber=partial confidence
- Sets chip score text

**`onDebateRound(ev)`**
- Appends a `.debate-round` card to `#debate-feed`:
  ```
  Round N — Gap: X
  🐂 Bull (conviction: N): "argument text..."
  🐻 Bear (conviction: N): "argument text..."
  ```
- Auto-scrolls feed to bottom

**`onDebateComplete(ev)`**
- Shows `#debate-summary`: "Converged in N rounds" or "Contested (N rounds)"

**`onVerdict(ev)`**
- Populates all `#verdict-*` elements
- Border colour: green if `ev.verdict === "WATCHLIST"`, red if `"AVOID"`
- Renders `.returns-table`: rows = [1m, 3m, 12m], columns = [Bear, Base, Bull]
- Shows `#verdict-contested` warning if `ev.contested === true`
- Unhides `#verdict-card`

**`onAbort(ev)`**
- Populates `#abort-reason` and lists failed agents
- Unhides `#abort-card`

### Upload flow

```js
async function uploadFiles(files) {
    for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        await fetch(`/upload/${ticker}/${currentRunId}`, {method: "POST", body: form});
    }
    document.getElementById("resume-btn").disabled = false;
}

// Resume button click:
document.getElementById("resume-btn").onclick = async () => {
    await openStream(`/resume/${currentRunId}`, {});
};
```

### Table renderers

**`loadWatchlist()`** — GET `/watchlist` → renders HTML table into `#watchlist-table`

**`loadRuns()`** — GET `/runs` → renders HTML table into `#runs-table`

### Utility functions

```js
const escHtml = s => s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const fmtNum = n => n?.toLocaleString("en-US") ?? "—";
const fmtAgentName = id => ({
    fundamental: "Fundamental", technical: "Technical",
    sentiment: "Sentiment", macro: "Macro",
    earnings_reviewer: "Earnings", risk_manager: "Risk",
    thesis_validator: "Thesis", financial_modeler: "Fin. Model",
    bull: "Bull", bear: "Bear", portfolio_manager: "PM"
}[id] ?? id);
```

- [ ] **Verification:** In browser, submit "AAPL" — agent chips appear and animate during Phase 1. Debate cards render round-by-round. Verdict card appears with correct colours.

---

## Task 7: Web UI — CSS (`static/style.css`)

**Files:**
- Create: `static/style.css`

### Colour tokens

```css
:root {
    --surface: #0f1117;
    --card: #1a1d27;
    --border: #2a2d3a;
    --accent: #6366f1;
    --success: #22c55e;
    --danger: #ef4444;
    --warn: #f59e0b;
}
```

### Component definitions

**`.tab-btn`** — inactive tab: transparent bg, muted text; active: `var(--accent)` border-bottom, white text.

**`.agent-chip`** — `background: var(--card)`, `border: 1px solid var(--border)`, `border-radius: 8px`, `padding: 8px`, `font-size: 0.75rem`, `text-align: center`. Running state adds `animation: pulse-border 1.5s infinite`.

```css
@keyframes pulse-border {
    0%, 100% { border-color: var(--border); }
    50%       { border-color: var(--accent); }
}
```

**`.debate-round`** — `background: var(--card)`, `border-left: 3px solid var(--accent)`, `padding: 12px`, `margin-bottom: 8px`, `border-radius: 4px`.

**`.score-badge`** — circular, 32px × 32px, centred text. Colour map:
- score-1: `background: #16a34a` (dark green — Strong Buy)
- score-2: `background: #22c55e` (green — Buy)
- score-3: `background: #f59e0b` (amber — Hold)
- score-4: `background: #ef4444` (red — Avoid)
- score-5: `background: #7f1d1d` (dark red — Strong Avoid)

**`.returns-table`** — `border-collapse: collapse`, `width: 100%`. `td, th`: `padding: 4px 8px`, `font-size: 0.75rem`. Header row: muted text. Positive values: green. Negative values: red.

**`.data-table`** — full-width, `border-collapse: collapse`. `tbody tr:hover { background: var(--card); }`. `th`: left-aligned, muted, `font-size: 0.7rem`, uppercase.

**`.spinner`** — 16px × 16px border-circle, `animation: spin 0.7s linear infinite`.

```css
@keyframes spin {
    to { transform: rotate(360deg); }
}
```

- [ ] **Verification:** Agent chips pulse amber while running; turn green/red on complete. Score badges render correct colours. Debate cards have left accent border.

---

## Task 8: Tests

**Files:**
- Create: `tests/unit/test_debate_convergence.py`
- Create: `tests/failure_scenarios/test_api_failures.py`
- Create: `tests/failure_scenarios/test_propagation.py`
- Create: `tests/e2e/test_data_layer_smoke.py`

### `test_debate_convergence.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from pipeline.debate import run_debate, MAX_ROUNDS, CONSENSUS_GAP

BUNDLE = {"ticker": "AAPL", "phase1_summaries": {}, "phase2_summaries": {}}

def make_round_result(conviction):
    return {"argument": "test argument " * 10, "conviction": conviction}

@pytest.mark.asyncio
async def test_early_exit_on_consensus():
    """Debate exits after round where gap <= CONSENSUS_GAP."""
    responses = [make_round_result(8), make_round_result(7)]  # gap=1, consensus
    with patch("pipeline.debate._run_agent_async", side_effect=responses):
        rounds = [ev async for ev in run_debate(BUNDLE.copy(), 1, MagicMock(), None)]
    debate_rounds = [r for r in rounds if r["event"] == "debate_round"]
    assert len(debate_rounds) == 1
    complete = next(r for r in rounds if r["event"] == "debate_complete")
    assert complete["contested"] is False

@pytest.mark.asyncio
async def test_contested_after_max_rounds():
    """Contested=True when gap > CONSENSUS_GAP after all rounds."""
    responses = [make_round_result(9), make_round_result(3)] * MAX_ROUNDS
    with patch("pipeline.debate._run_agent_async", side_effect=responses):
        rounds = [ev async for ev in run_debate(BUNDLE.copy(), 1, MagicMock(), None)]
    complete = next(r for r in rounds if r["event"] == "debate_complete")
    assert complete["contested"] is True
    assert complete["rounds"] == MAX_ROUNDS

@pytest.mark.asyncio
async def test_max_rounds_not_exceeded():
    """Never runs more than MAX_ROUNDS rounds."""
    responses = [make_round_result(9), make_round_result(1)] * (MAX_ROUNDS + 5)
    with patch("pipeline.debate._run_agent_async", side_effect=responses):
        rounds = [ev async for ev in run_debate(BUNDLE.copy(), 1, MagicMock(), None)]
    debate_rounds = [r for r in rounds if r["event"] == "debate_round"]
    assert len(debate_rounds) <= MAX_ROUNDS
```

### `test_api_failures.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from pipeline.monitor import run_monitor, _fetch_live_price

def test_fetch_live_price_returns_none_on_exception():
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.fast_info = {}
        mock_ticker.return_value.history.side_effect = Exception("network error")
        result = _fetch_live_price("AAPL")
    assert result is None

def test_run_monitor_counts_errors_on_bad_price():
    db = MagicMock()
    db.get_watchlist.return_value = [
        {"id": 1, "ticker": "AAPL", "alert_sent": 0,
         "stop_loss": 150.0, "entry_low": 170.0, "entry_high": 175.0,
         "target_price": 210.0}
    ]
    with patch("pipeline.monitor._fetch_live_price", return_value=None):
        result = run_monitor(db)
    assert result["errors"] == 1
    assert result["alerted"] == 0
```

### `test_propagation.py`

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pipeline.orchestrator import _run_pipeline
import asyncio

@pytest.mark.asyncio
async def test_abort_fires_on_two_minimal_confidence():
    """Pipeline aborts when 2+ Phase 1 agents return data_confidence=minimal."""
    minimal_result = {"agent": "test", "phase": 1, "score": 1,
                      "data_confidence": "minimal", "status": "complete",
                      "summary": "", "duration_ms": 100,
                      "bull_points": [], "bear_points": [], "missing_fields": []}
    full_result = {**minimal_result, "data_confidence": "full", "score": 7}

    phase1_results = [minimal_result, minimal_result, full_result, full_result, full_result]

    queue = asyncio.Queue()
    db = MagicMock()
    db.save_agent_output = MagicMock()
    db.update_run_status = MagicMock()

    with patch("pipeline.orchestrator.DataAggregator") as MockAgg, \
         patch("pipeline.orchestrator._run_phase_parallel", return_value=phase1_results):
        MockAgg.return_value.fetch_all = AsyncMock(return_value={"ticker": "TEST"})
        await _run_pipeline("TEST", 1, db, queue, None)

    events = []
    while not queue.empty():
        events.append(await queue.get())

    event_types = [e["event"] for e in events if e is not None and isinstance(e, dict)]
    assert "abort" in event_types
    db.update_run_status.assert_called_with(1, "failed")
```

- [ ] **Verification:** `pytest tests/unit/test_debate_convergence.py tests/failure_scenarios/ -v` — all tests pass.

---

## Final Verification

```powershell
# 1. All unit tests pass (86 tests, no real API calls)
pytest tests/ --ignore=tests/e2e -q

# 2. Server starts
uvicorn main:app --reload

# 3. UI loads
# Open http://localhost:8000 in browser
# Tab navigation works, dark theme renders

# 4. Run analysis (requires real API keys in .env)
# Enter "AAPL" → Analyse
# Agent chips animate → debate cards appear → verdict card renders
```
