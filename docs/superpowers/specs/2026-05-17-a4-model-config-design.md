# A4 — Per-Run Model Configuration & Agent Expand UI
**Date:** 2026-05-17
**Status:** Approved
**Backlog ref:** A4 (P2) — Agent model A/B harness

---

## Overview

Allow users to select the AI model for each pipeline phase before starting a run, via a pre-run configuration modal. Add expandable agent detail panels to the live pipeline progress UI so users can inspect what each agent is doing in real time and review its output once complete.

This is a single-run configuration feature — no parallel A/B runs, no `.env` modification. Selections apply to one run only and default to current `.env` values.

---

## Model Options Per Phase

| Phase | Option A (default) | Option B |
|---|---|---|
| Phase 1 — Data Analysts (5 agents) | Gemini 2.0 Flash · FREE | Claude Haiku 4.5 · ~£0.03 |
| Phase 2 — Assessment (3 agents) | Gemini 2.0 Flash · FREE | Claude Haiku 4.5 · ~£0.02 |
| Phase 3 — Bull/Bear Debate | Claude Opus 4.7 · ~£0.20 | Claude Opus 4.6 · ~£0.14 |
| Phase 4 — Portfolio Manager | Claude Opus 4.7 · ~£0.14 | Claude Opus 4.6 · ~£0.10 |

Provider is derived from model name: `gemini-*` → gemini, all others → anthropic.

---

## User Flow

1. User navigates to Analyse tab — sees a "New Analysis" button instead of the old ticker+button panel
2. Clicking "New Analysis" opens the configuration modal
3. Modal contains:
   - Ticker input at the top (uppercase, same validation as before)
   - Four phase rows, each with two clickable model cards (GitHub-dark glow style)
   - Live cost/runtime estimate bar that updates client-side on card selection
   - "Start Analysis ▶" button (disabled until ticker non-empty)
4. User clicks Start — modal closes, pipeline starts, progress panel appears
5. During the run, each agent chip in the phase cards is clickable:
   - **Running:** expands to show live log (model called, token count, elapsed time, streaming cursor)
   - **Complete:** expands to show score, confidence, summary, bull/bear points, missing fields
   - Multiple agents can be expanded simultaneously; state persists until manually collapsed
6. Run header sub-line shows selected config: e.g. `"Gemini Flash P1+P2 · Claude Opus 4.7 P3+P4"`

---

## Architecture

### `ModelConfig` dataclass (`pipeline/orchestrator.py`)

```python
@dataclass
class ModelConfig:
    phase1_model: str = PHASE1_MODEL
    phase1_provider: str = PHASE1_PROVIDER
    phase2_model: str = PHASE2_MODEL
    phase2_provider: str = PHASE2_PROVIDER
    debate_model: str = DEBATE_MODEL
    debate_provider: str = DEBATE_PROVIDER
    pm_model: str = PM_MODEL
    pm_provider: str = PM_PROVIDER

    @classmethod
    def from_request(cls, data: dict) -> "ModelConfig":
        """Build from POST body, deriving provider from model name."""
        def provider(model: str) -> str:
            return "gemini" if model.startswith("gemini") else "anthropic"

        p1m = data.get("phase1_model", PHASE1_MODEL)
        p2m = data.get("phase2_model", PHASE2_MODEL)
        dm  = data.get("debate_model", DEBATE_MODEL)
        pmm = data.get("pm_model", PM_MODEL)
        return cls(
            phase1_model=p1m,   phase1_provider=provider(p1m),
            phase2_model=p2m,   phase2_provider=provider(p2m),
            debate_model=dm,    debate_provider=provider(dm),
            pm_model=pmm,       pm_provider=provider(pmm),
        )
```

### Agent model override (orchestrator)

After instantiating each agent class, before calling `agent.run()`:

```python
agent.model    = model_config.phase1_model
agent.provider = model_config.phase1_provider
```

Same pattern for Phase 2, debate agents (bull + bear), and PM. `base_agent.py` requires no changes — `model` and `provider` are already instance-level attributes.

### `/analyse` endpoint (`main.py`)

```python
@app.post("/analyse")
async def analyse(request: Request):
    body = await request.json()
    ticker = sanitize_ticker(body.get("ticker", ""))
    model_config = ModelConfig.from_request(body)
    return StreamingResponse(
        stream_analysis(ticker, _db, model_config=model_config), ...
    )
```

### Database (`db/database.py`)

Four new columns on `analysis_runs`, added via migration-safe `ALTER TABLE`:

```sql
ALTER TABLE analysis_runs ADD COLUMN phase1_model TEXT;
ALTER TABLE analysis_runs ADD COLUMN phase2_model TEXT;
ALTER TABLE analysis_runs ADD COLUMN debate_model TEXT;
ALTER TABLE analysis_runs ADD COLUMN pm_model TEXT;
```

`create_run()` writes these on run creation. `get_run()` returns them automatically (already uses `dict(row)`). Existing rows default to NULL — display falls back to "–" in the UI.

### New SSE event: `agent_log`

Emitted by the **orchestrator** immediately before dispatching each agent to the thread executor (not by `BaseAgent`, which has no SSE queue access):

```json
{"event": "agent_log", "agent": "fundamental", "phase": 1, "model": "gemini-2.0-flash"}
```

The expand panel shows "Calling gemini-2.0-flash…" from this event and tracks elapsed time client-side with a JS timer. No `tokens_in` is available at dispatch time. Duration shown once `agent_complete` arrives. No DB storage needed.

---

## Frontend (`index.html` + `app.js`)

### Modal

- Replaces the existing `bg-card` ticker input panel
- Rendered as a fixed overlay when user triggers it
- Card selection updates a `selectedModels` object in JS
- Cost/time lookup table in `app.js` — no server round-trip
- On submit: POST body includes `ticker` + four model fields

### Agent expand

- Each agent chip rendered as `<button data-agent="fundamental" data-phase="1">`
- Click toggles a `<div class="agent-detail">` immediately below the chips row
- `app.js` listens for `agent_log` SSE events to populate the running log
- `app.js` listens for existing `agent_complete` SSE events to populate the complete view
- `agent_complete` already carries: `agent`, `score`, `data_confidence`, `status` — sufficient for the expand panel header
- Full summary, bull/bear points, missing fields come from a `GET /runs/{run_id}` call made once the run completes (or lazily on first expand of a completed agent)

---

## Testing

**`tests/unit/test_model_config.py`**
- Provider derivation: `gemini-2.0-flash` → gemini, `claude-haiku-4-5-20251001` → anthropic
- `ModelConfig.from_request({})` returns `.env` defaults
- `ModelConfig.from_request({"phase1_model": "claude-haiku-4-5-20251001"})` overrides phase1 only

**`tests/unit/test_model_override.py`**
- Instantiate agent, override `.model` / `.provider`, assert `_call_llm()` routes correctly

**`tests/integration/test_pipeline_model_config.py`**
- Run `_run_pipeline()` with fixture bundle + non-default `ModelConfig`
- Assert `agent_outputs` rows in test DB carry correct model in log / raw_output

---

## Out of Scope

- Parallel A/B runs comparing two model configs
- Persisting per-user model preferences across sessions
- Adding new models beyond the four listed options
- Modifying Phase 3/4 provider (always Anthropic)
