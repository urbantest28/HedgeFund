# HedgeFund Analyser — Claude Code Reference

## Project Overview
Standalone multi-agent simulated hedge fund. 9 AI agents across 4 phases analyse a stock and produce a scored verdict, HTML report, Excel model, and watchlist entry.

**Design spec:** `ISA Statements/Dashboard/docs/superpowers/specs/2026-05-10-hedgefund-multiagent-design.md`

---

## Stack
- **Backend:** FastAPI + Uvicorn (Python 3.9)
- **Frontend:** HTML + Tailwind CSS (CDN) + Vanilla JS
- **Streaming:** Server-Sent Events (SSE)
- **Database:** SQLite (`src/hedgefund.db`)
- **Excel output:** openpyxl

---

## Model Routing
Never guess which model an agent uses — always check `.env`:

| Phase | Agents | Provider | Model |
|---|---|---|---|
| Phase 1 | Fundamental, Technical, Sentiment, Macro, Earnings | Gemini | gemini-2.0-flash |
| Phase 2 | Risk Manager, Thesis Validator, Financial Modeler | Gemini | gemini-2.0-flash |
| Phase 3 | Bull, Bear | Claude | claude-opus-4-7 |
| Phase 4 | Portfolio Manager | Claude | claude-opus-4-7 |

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
| `pipeline/orchestrator.py` | Phase runner, checkpoint writer |
| `pipeline/debate.py` | Bull/Bear loop, convergence logic |
| `pipeline/monitor.py` | Daily watchlist price check + ntfy alerts |
| `data/aggregator.py` | Pre-fetch all data before pipeline starts |
| `agents/base_agent.py` | Provider router (Gemini / Claude) |
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
