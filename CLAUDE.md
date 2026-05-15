# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Standalone multi-agent simulated hedge fund. 9 AI agents across 4 phases analyse a stock and produce a scored verdict, HTML report, and watchlist entry.

**Design spec:** `docs/specs/2026-05-10-hedgefund-multiagent-design.md`

---

## Commands

```bash
# Install dependencies (use venv at ./venv)
pip install -r requirements.txt

# Start the server (port 8000)
uvicorn main:app --reload

# Run all tests
pytest tests/ -x

# Run a single test file
pytest tests/unit/test_cache_ttl.py -v

# Run a single test function
pytest tests/unit/test_cache_ttl.py::test_specific_function -v
```

---

## Stack
- **Backend:** FastAPI + Uvicorn (Python 3.11)
- **Frontend:** HTML + Tailwind CSS (CDN) + Vanilla JS
- **Streaming:** Server-Sent Events (SSE)
- **Database:** SQLite at `db/hedgefund.db`
- **Cache:** File-based JSON at `cache/{ticker}/historical/` and `cache/{ticker}/derived/`

---

## Model Routing
All provider/model settings live in `.env` — `config.py` shows the full list of env var names. Never hardcode a model; always read from config.

| Phase | Agents | Default provider | Default model |
|---|---|---|---|
| Phase 1 | Fundamental, Technical, Sentiment, Macro, Earnings | Gemini | gemini-2.0-flash |
| Phase 2 | Risk Manager, Thesis Validator, Financial Modeler | Gemini | gemini-2.0-flash |
| Phase 3 | Bull, Bear | Claude | claude-opus-4-7 |
| Phase 4 | Portfolio Manager | Claude | claude-opus-4-7 |

**Gemini quota fallback:** If any Phase 1/2 Gemini agent hits a 429, `BaseAgent._call_llm_with_fallback()` automatically retries with `FALLBACK_MODEL` (defaults to `claude-haiku-4-5-20251001`). This is transparent to the orchestrator.

---

## Architecture: Data Flow

Every run follows a strict sequence in `pipeline/orchestrator.py`:

```
1. DataAggregator.fetch(ticker, run_id)   → frozen bundle dict + debug snapshot
2. Phase 1: 5 agents run in parallel      → scores saved to DB
3. Phase 2: 3 agents run in parallel      → scores saved to DB
4. Phase 3: Bull/Bear debate loop (≤4 rounds, early exit on consensus gap ≤2)
5. Phase 4: Portfolio Manager produces final verdict
6. ReportGenerator builds HTML + saves watchlist entry to DB
```

All agents receive the **full bundle** — they are responsible for reading only what they need. The bundle also contains a `data_manifest` dict that records `status` (ok/partial/missing) and `source` for every field. Agents are instructed (via prompt guardrails) to check this manifest before reasoning and to reduce their score for missing fields.

---

## Architecture: Agent Contract

Every agent subclasses `BaseAgent` and declares:
```python
name: str          # e.g. "fundamental"
phase: int         # 1–4
role_file: str     # filename in prompts/roles/
skill_files: list  # filenames in prompts/skills/
provider: str      # "gemini" or "anthropic"
model: str         # read from config
```

`BaseAgent.run()` returns a fixed dict:
```python
{"agent", "run_id", "phase", "score", "summary", "data_confidence",
 "missing_fields", "bull_points", "bear_points", "raw_output",
 "duration_ms", "status"}
```

`status` is always `"complete"` or `"failed"`. A failed agent still returns this shape with `score: None` and `data_confidence: "minimal"` — the pipeline never crashes on a single agent failure.

---

## Architecture: Cache System

`CacheManager` (in `data/cache_manager.py`) uses a tiered file-based JSON cache:

| Tier | TTL | Examples |
|---|---|---|
| `LIVE` | Never cached | live price, news, reddit |
| `FOREVER` | Indefinite | OHLCV history, financials, SEC filings, insider transactions |
| `TTL_1D` | 24 hours | fundamentals, fed funds rate |
| `TTL_7D` / `TTL_30D` | Longer | sector info, company overview |

Cache files land at `cache/{ticker}/historical/` (FOREVER) or `cache/{ticker}/derived/` (TTL). The aggregator always checks the cache before making an API call.

---

## Architecture: Adding a New Data Source

Follow this pattern (used for every existing client):

1. **Create `data/{name}_client.py`** — single public method returning a dict with a `"source"` key and graceful error return on failure.
2. **Add to `DataAggregator.__init__`** — new constructor param, stored as `self._{name}`.
3. **Add fetch block in `DataAggregator.fetch()`** — check cache → call client → store to cache → `data[key] = result`.
4. **Add manifest entry** — `mb.add(key, bool(value), source=..., status="ok"|"partial"|"missing")`.
5. **Add `{name}` to `pipeline/orchestrator.py`** — import, construct, and pass to `DataAggregator(...)`.
6. **Update the target agent's prompt** — add the new field to `raw_output` schema and a responsibility bullet.

---

## Debugging Workflow

**Every bug should be fixed using this exact loop — do not scan the whole codebase first.**

### Step 1 — Get the run_id
The run_id is shown in the UI during every analysis and printed at the top of every report. The user should always provide it when reporting a bug.

### Step 2 — Inspect the run
```
python debug/inspect_run.py {run_id}
```
Shows: data manifest (what was fetched, from where, what failed), each agent's score/summary/confidence, debate transcript, final verdict, any errors.

### Step 3 — Replay the run
```
python debug/replay_run.py {run_id}
```
Replays the exact run using the frozen data bundle saved at `debug/bundles/run_{id}_bundle.json`. No API calls made. Reproduces the bug in under 2 minutes.

### Step 4 — Isolate the failing component
```
python debug/run_agent.py {agent_name} {run_id}
# Examples:
python debug/run_agent.py fundamental 42
python debug/run_agent.py debate 42
python debug/run_agent.py portfolio_manager 42
```

### Step 5 — Fix, verify, test
```
python debug/run_agent.py {agent_name} {run_id}   # confirm agent fix
python debug/replay_run.py {run_id}               # confirm full pipeline fix
pytest tests/ -x                                  # confirm no regressions
```

### Step 6 — Add regression test + commit
Add a test to `tests/regression/` named after the bug. Never skip this step.
```
git add . && git commit -m "fix: {description}" && git push
```

---

## Log Format
Every log line follows this exact format:
```
[hf:{module}] [run_{id}] {message} | {key}: {value}
```

Filter all logs for a specific run:
```
Select-String "\[run_42\]" logs\run_42.log
```

Key module names: `aggregator`, `cache`, `pipeline`, `debate`, `pm`, `fundamental`, `technical`, `sentiment`, `macro`, `earnings`, `risk`, `thesis`, `modeler`, `bull`, `bear`, `monitor`, `report`

---

## Data Bundle Snapshots
Every run saves a frozen copy of all fetched data to `debug/bundles/run_{id}_bundle.json` before the pipeline starts. This is what `replay_run.py` uses. Never delete these — they are the primary debugging tool.

---

## Regression Test Rule
Every fixed bug gets a test in `tests/regression/` named descriptively:
```
tests/regression/test_{bug_description}.py
```
These are never deleted. Before marking any bug as fixed, the regression test must pass.

---

## Key Files
| File | Purpose |
|---|---|
| `main.py` | FastAPI app, SSE endpoint, upload handler |
| `config.py` | All env vars and directory paths — single source of truth |
| `pipeline/orchestrator.py` | Phase runner, checkpoint writer |
| `pipeline/debate.py` | Bull/Bear loop, convergence logic (`MAX_ROUNDS=4`, `CONSENSUS_GAP=2`) |
| `pipeline/monitor.py` | Daily watchlist price check + ntfy alerts |
| `data/aggregator.py` | Pre-fetch all data before pipeline starts |
| `data/cache_manager.py` | File-based tiered cache (LIVE/FOREVER/TTL) |
| `agents/base_agent.py` | Provider router, retry logic, Gemini→Haiku fallback |
| `db/database.py` | hedgefund.db schema + CRUD |
| `reports/generator.py` | HTML report builder |
| `debug/replay_run.py` | Replay any run_id |
| `debug/run_agent.py` | Run one agent in isolation |
| `debug/inspect_run.py` | Pretty-print run summary |

---

## Prompt Files
- `prompts/roles/` — agent identity, responsibilities, guardrails, output schema
- `prompts/skills/` — shared analytical techniques injected per agent
- Editing a `.md` file takes effect immediately on next run — no code changes needed

---

## Branch Strategy
- `main` — stable, tested only
- `feat/*` — one branch per implementation phase
- `fix/run{id}-{description}` — bug fix branches (include run_id when fixing a specific reported bug)
