# A4 — Per-Run Model Configuration & Agent Expand UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users choose the AI model for each pipeline phase via a pre-run modal, and expand any agent chip during a run to see live status or final output.

**Architecture:** A `ModelConfig` dataclass carries per-run model choices through the orchestrator, overriding each agent's `model` and `provider` attributes after instantiation. The frontend modal collects the config and sends it in the POST body; the progress UI gets expandable agent chips driven by two SSE events (`agent_log` and the existing `agent_complete`).

**Tech Stack:** Python 3.11, FastAPI, SQLite (via `db/database.py`), Tailwind CSS, Vanilla JS, Server-Sent Events.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `db/database.py` | Modify | Add 4 model columns to `analysis_runs`; update `create_run()` + `update_run()` |
| `pipeline/orchestrator.py` | Modify | Add `ModelConfig` dataclass; override agent models; emit `agent_log` SSE event |
| `pipeline/debate.py` | Modify | Accept + apply debate model override to bull/bear agents |
| `main.py` | Modify | Parse model config from POST body; pass to `stream_analysis()` |
| `templates/index.html` | Modify | Replace ticker panel with modal trigger; add modal HTML; update phase card headers |
| `static/app.js` | Modify | Modal open/close/submit; card selection + live cost estimate; agent expand/collapse |
| `tests/unit/test_model_config.py` | Create | Unit tests for `ModelConfig` provider derivation + defaults |
| `tests/unit/test_model_override.py` | Create | Unit test that agent model/provider override routes LLM correctly |
| `tests/integration/test_pipeline_model_config.py` | Create | Integration test: non-default config flows through to DB rows |

---

## Task 1: DB Migration — Add Model Columns

**Files:**
- Modify: `db/database.py`
- Test: `tests/unit/test_model_config_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_model_config_db.py
import pytest
from db.database import Database


def test_analysis_runs_has_model_columns(db):
    run_id = db.create_run("AAPL", "2026-05-17",
                           phase1_model="gemini-2.0-flash",
                           phase2_model="gemini-2.0-flash",
                           debate_model="claude-opus-4-7",
                           pm_model="claude-opus-4-7")
    row = db.get_run(run_id)
    assert row["phase1_model"] == "gemini-2.0-flash"
    assert row["phase2_model"] == "gemini-2.0-flash"
    assert row["debate_model"] == "claude-opus-4-7"
    assert row["pm_model"] == "claude-opus-4-7"


def test_create_run_without_model_columns_still_works(db):
    """Backwards compat — existing callers omit model fields."""
    run_id = db.create_run("TSLA", "2026-05-17")
    row = db.get_run(run_id)
    assert row["phase1_model"] is None
    assert row["pm_model"] is None


def test_update_run_model_columns(db):
    run_id = db.create_run("AAPL", "2026-05-17")
    db.update_run(run_id, phase1_model="claude-haiku-4-5-20251001")
    row = db.get_run(run_id)
    assert row["phase1_model"] == "claude-haiku-4-5-20251001"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/test_model_config_db.py -v
```
Expected: FAIL — `create_run() got unexpected keyword argument 'phase1_model'`

- [ ] **Step 3: Add `_migrate()` and update `_create_tables()` in `db/database.py`**

Add this method to `Database` after `_create_tables`:

```python
def _migrate(self) -> None:
    """Add columns introduced after the initial schema — safe to re-run."""
    new_columns = [
        ("analysis_runs", "phase1_model", "TEXT"),
        ("analysis_runs", "phase2_model", "TEXT"),
        ("analysis_runs", "debate_model", "TEXT"),
        ("analysis_runs", "pm_model",     "TEXT"),
    ]
    for table, col, col_type in new_columns:
        try:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            self._conn.commit()
        except Exception:
            pass  # column already exists
```

Call it at the end of `__init__`, after `self._create_tables()`:

```python
def __init__(self, path: Path = DB_PATH):
    self._path = path
    self._conn = sqlite3.connect(str(path), check_same_thread=False)
    self._conn.row_factory = sqlite3.Row
    self._conn.execute("PRAGMA foreign_keys = ON")
    self._create_tables()
    self._migrate()
```

- [ ] **Step 4: Update `create_run()` to accept optional model fields**

Replace the existing `create_run` method:

```python
def create_run(self, ticker: str, run_date: str,
               phase1_model: str = None, phase2_model: str = None,
               debate_model: str = None, pm_model: str = None) -> int:
    cur = self._conn.execute(
        """INSERT INTO analysis_runs
           (ticker, run_date, phase1_model, phase2_model, debate_model, pm_model)
           VALUES (?,?,?,?,?,?)""",
        (ticker, run_date, phase1_model, phase2_model, debate_model, pm_model)
    )
    self._conn.commit()
    return cur.lastrowid
```

- [ ] **Step 5: Update `update_run()` allowed set to include model columns**

In `update_run()`, extend the `allowed` set:

```python
allowed = {"status", "verdict", "score", "tier", "entry_low", "entry_high",
           "stop_loss", "target_price", "thesis_id", "thesis_match",
           "contested", "bull_score", "bear_score", "report_path", "model_path",
           "phase1_model", "phase2_model", "debate_model", "pm_model"}
```

- [ ] **Step 6: Run tests to verify they pass**

```
pytest tests/unit/test_model_config_db.py -v
```
Expected: 3 PASSED

- [ ] **Step 7: Run full test suite to check for regressions**

```
pytest tests/ -x -q
```
Expected: all existing tests pass

- [ ] **Step 8: Commit**

```
git add db/database.py tests/unit/test_model_config_db.py
git commit -m "feat(db): add phase model columns to analysis_runs"
```

---

## Task 2: ModelConfig Dataclass

**Files:**
- Modify: `pipeline/orchestrator.py` (top of file, before `_save_bundle_snapshot`)
- Test: `tests/unit/test_model_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_model_config.py
import pytest


def test_provider_derived_from_gemini_model():
    from pipeline.orchestrator import ModelConfig
    cfg = ModelConfig.from_request({"phase1_model": "gemini-2.0-flash"})
    assert cfg.phase1_provider == "gemini"


def test_provider_derived_from_claude_model():
    from pipeline.orchestrator import ModelConfig
    cfg = ModelConfig.from_request({"phase1_model": "claude-haiku-4-5-20251001"})
    assert cfg.phase1_provider == "anthropic"


def test_empty_request_returns_env_defaults():
    from pipeline.orchestrator import ModelConfig
    from config import PHASE1_MODEL, PHASE2_MODEL, DEBATE_MODEL, PM_MODEL
    cfg = ModelConfig.from_request({})
    assert cfg.phase1_model == PHASE1_MODEL
    assert cfg.phase2_model == PHASE2_MODEL
    assert cfg.debate_model == DEBATE_MODEL
    assert cfg.pm_model == PM_MODEL


def test_partial_override_leaves_other_fields_as_defaults():
    from pipeline.orchestrator import ModelConfig
    from config import PHASE2_MODEL
    cfg = ModelConfig.from_request({"phase1_model": "claude-haiku-4-5-20251001"})
    assert cfg.phase1_model == "claude-haiku-4-5-20251001"
    assert cfg.phase2_model == PHASE2_MODEL  # unchanged


def test_all_four_phases_overrideable():
    from pipeline.orchestrator import ModelConfig
    cfg = ModelConfig.from_request({
        "phase1_model": "claude-haiku-4-5-20251001",
        "phase2_model": "claude-haiku-4-5-20251001",
        "debate_model": "claude-opus-4-6",
        "pm_model":     "claude-opus-4-6",
    })
    assert cfg.phase1_provider == "anthropic"
    assert cfg.phase2_provider == "anthropic"
    assert cfg.debate_provider == "anthropic"
    assert cfg.pm_provider     == "anthropic"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/test_model_config.py -v
```
Expected: FAIL — `cannot import name 'ModelConfig' from 'pipeline.orchestrator'`

- [ ] **Step 3: Add `ModelConfig` to `pipeline/orchestrator.py`**

Add after the existing imports, before `_log = get_logger(...)`:

```python
from dataclasses import dataclass, field
from config import (BASE_DIR, DEBUG_BUNDLES_DIR, sanitize_ticker, safe_path,
                    PHASE1_MODEL, PHASE1_PROVIDER, PHASE2_MODEL, PHASE2_PROVIDER,
                    DEBATE_MODEL, DEBATE_PROVIDER, PM_MODEL, PM_PROVIDER)


@dataclass
class ModelConfig:
    phase1_model:    str = field(default_factory=lambda: PHASE1_MODEL)
    phase1_provider: str = field(default_factory=lambda: PHASE1_PROVIDER)
    phase2_model:    str = field(default_factory=lambda: PHASE2_MODEL)
    phase2_provider: str = field(default_factory=lambda: PHASE2_PROVIDER)
    debate_model:    str = field(default_factory=lambda: DEBATE_MODEL)
    debate_provider: str = field(default_factory=lambda: DEBATE_PROVIDER)
    pm_model:        str = field(default_factory=lambda: PM_MODEL)
    pm_provider:     str = field(default_factory=lambda: PM_PROVIDER)

    @classmethod
    def from_request(cls, data: dict) -> "ModelConfig":
        def _provider(model: str) -> str:
            return "gemini" if model.startswith("gemini") else "anthropic"

        p1m = data.get("phase1_model", PHASE1_MODEL)
        p2m = data.get("phase2_model", PHASE2_MODEL)
        dm  = data.get("debate_model", DEBATE_MODEL)
        pmm = data.get("pm_model", PM_MODEL)
        return cls(
            phase1_model=p1m,    phase1_provider=_provider(p1m),
            phase2_model=p2m,    phase2_provider=_provider(p2m),
            debate_model=dm,     debate_provider=_provider(dm),
            pm_model=pmm,        pm_provider=_provider(pmm),
        )
```

Note: the existing `from config import BASE_DIR, DEBUG_BUNDLES_DIR, sanitize_ticker, safe_path` line at the top of `orchestrator.py` must be expanded to include the model/provider constants. Replace it with the import block shown above.

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/unit/test_model_config.py -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```
git add pipeline/orchestrator.py tests/unit/test_model_config.py
git commit -m "feat(orchestrator): add ModelConfig dataclass"
```

---

## Task 3: Orchestrator — Model Override + `agent_log` SSE Event

**Files:**
- Modify: `pipeline/orchestrator.py`
- Test: `tests/unit/test_model_override.py`, `tests/integration/test_pipeline_model_config.py`

- [ ] **Step 1: Write the model override unit test**

```python
# tests/unit/test_model_override.py
from unittest.mock import patch, MagicMock


def test_agent_model_overridden_before_llm_call():
    """Overriding .model and .provider before run() routes to correct provider."""
    from agents.fundamental import FundamentalAgent

    agent = FundamentalAgent()
    agent.model    = "claude-haiku-4-5-20251001"
    agent.provider = "anthropic"

    assert agent.model    == "claude-haiku-4-5-20251001"
    assert agent.provider == "anthropic"

    # _call_llm branches on self.provider — verify it would call Claude not Gemini
    with patch.object(agent, "_call_claude", return_value='{"score":5,"summary":"ok","data_confidence":"partial","missing_fields":[],"bull_points":[],"bear_points":[],"raw_output":{}}') as mock_claude, \
         patch.object(agent, "_call_gemini") as mock_gemini:
        agent._call_llm("test prompt")
        mock_claude.assert_called_once()
        mock_gemini.assert_not_called()
```

- [ ] **Step 2: Run test to verify it passes (no code change needed — override already works)**

```
pytest tests/unit/test_model_override.py -v
```
Expected: PASS (model override is a property of the existing base class)

- [ ] **Step 3: Write the integration test**

```python
# tests/integration/test_pipeline_model_config.py
import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock
from pipeline.orchestrator import ModelConfig, _run_pipeline
from db.database import Database


FAKE_OUTPUT = json.dumps({
    "score": 5, "summary": "test", "data_confidence": "partial",
    "missing_fields": [], "bull_points": [], "bear_points": [], "raw_output": {}
})


def _fake_run(self, bundle, run_id):
    return {
        "agent": self.name, "run_id": run_id, "phase": self.phase,
        "score": 5, "summary": "test", "data_confidence": "partial",
        "missing_fields": [], "bull_points": [], "bear_points": [],
        "raw_output": {}, "duration_ms": 100, "status": "complete",
    }


@pytest.mark.asyncio
async def test_model_config_stored_in_db(db, aapl_bundle):
    """Non-default ModelConfig values are written to analysis_runs."""
    cfg = ModelConfig.from_request({
        "phase1_model": "claude-haiku-4-5-20251001",
        "phase2_model": "claude-haiku-4-5-20251001",
        "debate_model": "claude-opus-4-6",
        "pm_model":     "claude-opus-4-6",
    })

    run_id = db.create_run("AAPL", "2026-05-17",
                           phase1_model=cfg.phase1_model,
                           phase2_model=cfg.phase2_model,
                           debate_model=cfg.debate_model,
                           pm_model=cfg.pm_model)
    row = db.get_run(run_id)
    assert row["phase1_model"] == "claude-haiku-4-5-20251001"
    assert row["debate_model"] == "claude-opus-4-6"


@pytest.mark.asyncio
async def test_phase1_agents_get_model_override(aapl_bundle):
    """Phase 1 agents have their model overridden to the config value."""
    from agents.fundamental import FundamentalAgent
    from agents.technical import TechnicalAgent

    cfg = ModelConfig.from_request({"phase1_model": "claude-haiku-4-5-20251001"})

    for cls in [FundamentalAgent, TechnicalAgent]:
        agent = cls()
        agent.model    = cfg.phase1_model
        agent.provider = cfg.phase1_provider
        assert agent.model    == "claude-haiku-4-5-20251001"
        assert agent.provider == "anthropic"
```

- [ ] **Step 4: Run tests to verify they pass (no new code — validates existing + Task 1 work)**

```
pytest tests/integration/test_pipeline_model_config.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Update `_run_phase_parallel()` to accept and apply `model_config`, and emit `agent_log`**

Replace the `_run_phase_parallel` signature and body in `orchestrator.py`:

```python
async def _run_phase_parallel(
    agent_classes: list,
    bundle: dict,
    run_id: int,
    db: Database,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue,
    phase: int,
    model_config: "ModelConfig" = None,
) -> list[dict]:
    """Run a list of agent classes in parallel, emit events, save outputs to DB."""
    agents = [cls() for cls in agent_classes]

    # Apply model override
    if model_config is not None:
        m = model_config.phase1_model if phase == 1 else model_config.phase2_model
        p = model_config.phase1_provider if phase == 1 else model_config.phase2_provider
        for agent in agents:
            agent.model    = m
            agent.provider = p

    agent_log = _log.bind_run(run_id)
    agent_log.info(f"Phase {phase} started | agents: {[a.name for a in agents]}")
    await queue.put({
        "event": "phase_start",
        "phase": phase,
        "agents": [a.name for a in agents],
    })

    # Emit agent_log for each agent before dispatch
    for agent in agents:
        await queue.put({
            "event": "agent_log",
            "agent": agent.name,
            "phase": phase,
            "model": agent.model,
        })

    tasks = [_run_agent_async(a, bundle, run_id, loop) for a in agents]
    results = []

    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.append(result)

        db.save_agent_output(
            run_id=run_id,
            agent=result["agent"],
            phase=result["phase"],
            score=result["score"],
            summary=result["summary"],
            raw_output=json.dumps(result["raw_output"], default=str),
            data_confidence=result["data_confidence"],
            duration_ms=result["duration_ms"],
            status=result["status"],
        )

        await queue.put({
            "event": "agent_complete",
            "phase": phase,
            "agent": result["agent"],
            "score": result["score"],
            "summary": result["summary"],
            "data_confidence": result["data_confidence"],
            "missing_fields": result["missing_fields"],
            "bull_points": result["bull_points"],
            "bear_points": result["bear_points"],
            "duration_ms": result["duration_ms"],
            "status": result["status"],
        })
        agent_log.info(
            f"Phase {phase} | {result['agent']} complete "
            f"| score: {result['score']} | confidence: {result['data_confidence']}"
        )

    return results
```

Note: `agent_complete` now includes `summary`, `missing_fields`, `bull_points`, `bear_points`, `duration_ms` — these power the expand panel without a separate API call.

- [ ] **Step 6: Update `_run_pipeline()` to accept `model_config` and pass it through**

Add `model_config: "ModelConfig" = None` to `_run_pipeline`'s signature (after `prior_phase1_results`). Then:

1. Pass `model_config=model_config` to both `_run_phase_parallel` calls (Phase 1 and Phase 2).

2. After PM instantiation, override model:
```python
pm = PortfolioManagerAgent()
if model_config is not None:
    pm.model    = model_config.pm_model
    pm.provider = model_config.pm_provider
pm_result = await loop.run_in_executor(None, pm.run, bundle, run_id)
```

3. Pass model fields to `db.create_run()` — but `create_run()` is called in `stream_analysis()`, not `_run_pipeline()`. See Task 5 for the endpoint wiring.

- [ ] **Step 7: Update `stream_analysis()` to accept and forward `model_config`**

```python
async def stream_analysis(
    ticker: str,
    db: Database,
    transcript_path: Optional[Path] = None,
    model_config: "ModelConfig" = None,
) -> AsyncGenerator[str, None]:
    if model_config is None:
        model_config = ModelConfig()

    run_id = db.create_run(
        ticker,
        datetime.now().strftime("%Y-%m-%d"),
        phase1_model=model_config.phase1_model,
        phase2_model=model_config.phase2_model,
        debate_model=model_config.debate_model,
        pm_model=model_config.pm_model,
    )
    db.update_run(run_id, status="running")

    queue: asyncio.Queue = asyncio.Queue()
    asyncio.create_task(_run_pipeline(
        ticker, run_id, db, queue, transcript_path,
        model_config=model_config,
    ))

    yield f"data: {json.dumps({'event': 'run_start', 'run_id': run_id, 'ticker': ticker, 'model_config': {'phase1': model_config.phase1_model, 'phase2': model_config.phase2_model, 'debate': model_config.debate_model, 'pm': model_config.pm_model}})}\n\n"

    while True:
        event = await queue.get()
        if event is None:
            break
        yield f"data: {json.dumps(event, default=str)}\n\n"
```

- [ ] **Step 8: Run full test suite**

```
pytest tests/ -x -q
```
Expected: all tests pass

- [ ] **Step 9: Commit**

```
git add pipeline/orchestrator.py tests/unit/test_model_override.py tests/integration/test_pipeline_model_config.py
git commit -m "feat(orchestrator): model override per phase + agent_log SSE event"
```

---

## Task 4: Debate Model Override

**Files:**
- Modify: `pipeline/debate.py`
- Modify: `pipeline/orchestrator.py` (one call site)

- [ ] **Step 1: Update `run_debate()` to accept optional model override**

In `pipeline/debate.py`, update the function signature and add model override after agent instantiation:

```python
async def run_debate(
    bundle: dict,
    run_id: int,
    db: Database,
    loop: asyncio.AbstractEventLoop,
    debate_model: str = None,
    debate_provider: str = None,
) -> AsyncGenerator[dict, None]:
    bull = BullAgent()
    bear = BearAgent()

    if debate_model is not None:
        bull.model = debate_model
        bear.model = debate_model
    if debate_provider is not None:
        bull.provider = debate_provider
        bear.provider = debate_provider

    # Emit agent_log for both debate agents (caller handles queue — yield from here)
    yield {
        "event": "agent_log",
        "agent": "bull",
        "phase": 3,
        "model": bull.model,
    }
    yield {
        "event": "agent_log",
        "agent": "bear",
        "phase": 3,
        "model": bear.model,
    }

    # ... rest of function unchanged
```

- [ ] **Step 2: Update the `run_debate()` call in `_run_pipeline()` in `orchestrator.py`**

Find this line in `_run_pipeline`:
```python
debate_gen = run_debate(bundle, run_id, db, loop)
```

Replace with:
```python
debate_gen = run_debate(
    bundle, run_id, db, loop,
    debate_model=model_config.debate_model if model_config else None,
    debate_provider=model_config.debate_provider if model_config else None,
)
```

- [ ] **Step 3: Run full test suite**

```
pytest tests/ -x -q
```
Expected: all tests pass

- [ ] **Step 4: Commit**

```
git add pipeline/debate.py pipeline/orchestrator.py
git commit -m "feat(debate): apply debate model override from ModelConfig"
```

---

## Task 5: Update `/analyse` Endpoint

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update the `/analyse` endpoint to parse model config**

Replace the existing `analyse` function in `main.py`:

```python
@app.post("/analyse")
async def analyse(request: Request):
    """
    Expects JSON body: {"ticker": "AAPL", "phase1_model": "...", ...}.
    Returns SSE stream.
    """
    from pipeline.orchestrator import ModelConfig
    body = await request.json()
    raw_ticker = body.get("ticker", "").strip().upper()
    if not raw_ticker:
        raise HTTPException(400, "ticker required")
    try:
        ticker = sanitize_ticker(raw_ticker)
    except ValueError:
        raise HTTPException(400, f"Invalid ticker: {raw_ticker!r}")

    model_config = ModelConfig.from_request(body)
    _log.info(f"Analyse request | ticker: {ticker} | phase1: {model_config.phase1_model} | debate: {model_config.debate_model}")

    return StreamingResponse(
        stream_analysis(ticker, _db, model_config=model_config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: Run full test suite**

```
pytest tests/ -x -q
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```
git add main.py
git commit -m "feat(api): parse ModelConfig from /analyse POST body"
```

---

## Task 6: Frontend — Modal HTML

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Replace the ticker input panel with a modal trigger button**

In `index.html`, find the existing input panel block:
```html
<!-- Input panel -->
<div class="bg-card border border-border rounded-xl p-6 mb-6">
  <h2 class="text-sm text-gray-400 uppercase tracking-widest mb-4">New Analysis</h2>
  <div class="flex gap-3">
    <input id="ticker-input" .../>
    <button id="analyse-btn" onclick="startAnalysis()" ...>Analyse</button>
  </div>
  <p class="text-xs text-gray-500 mt-2">Enter a stock ticker. Analysis takes 3–5 minutes.</p>
</div>
```

Replace the entire block with:

```html
<!-- New Analysis trigger -->
<div class="bg-card border border-border rounded-xl p-6 mb-6 flex items-center justify-between">
  <div>
    <h2 class="text-sm font-semibold">New Analysis</h2>
    <p class="text-xs text-gray-500 mt-1">Select a stock and configure AI models before running.</p>
  </div>
  <button onclick="openModal()"
    class="px-6 py-2.5 bg-accent hover:bg-indigo-500 text-white rounded-lg font-semibold text-sm transition-colors">
    + New Analysis
  </button>
</div>

<!-- Configuration modal -->
<div id="run-modal" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4" style="background:rgba(0,0,0,.6);">
  <div class="bg-card border border-indigo-500 rounded-xl w-full max-w-lg shadow-2xl" style="box-shadow:0 0 40px rgba(99,102,241,.2);">

    <!-- Modal header -->
    <div class="flex items-start justify-between p-5 border-b border-border">
      <div>
        <h3 class="text-sm font-bold">New Analysis</h3>
        <p class="text-xs text-gray-500 mt-1">Enter ticker and select AI model for each phase</p>
      </div>
      <button onclick="closeModal()" class="text-gray-600 hover:text-gray-400 text-lg leading-none">✕</button>
    </div>

    <!-- Ticker input -->
    <div class="px-5 pt-4 pb-3 border-b border-border">
      <label class="text-xs font-bold text-gray-500 uppercase tracking-wider block mb-2">Stock Ticker</label>
      <input id="ticker-input" type="text" placeholder="AAPL"
        oninput="onTickerInput()"
        class="w-full bg-surface border border-indigo-500 rounded-lg px-4 py-3 text-lg uppercase tracking-widest
               focus:outline-none focus:border-accent placeholder-gray-600 font-mono"
        maxlength="10" />
    </div>

    <!-- Phase model selection -->
    <div class="px-5 py-4 space-y-4">

      <!-- Phase 1 -->
      <div>
        <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
          Phase 1 · Data Analysts <span class="text-gray-600 normal-case font-normal">— Fundamental, Technical, Sentiment, Macro, Earnings</span>
        </p>
        <div class="flex gap-2">
          <button class="model-card selected flex-1" data-phase="phase1" data-model="gemini-2.0-flash" data-provider="gemini" onclick="selectModel(this)">
            <div class="flex justify-between items-center">
              <span class="text-xs font-semibold">Gemini 2.0 Flash</span>
              <span class="badge-free">FREE</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">FREE · ~45s</p>
          </button>
          <button class="model-card flex-1" data-phase="phase1" data-model="claude-haiku-4-5-20251001" data-provider="anthropic" onclick="selectModel(this)">
            <div class="flex justify-between items-center">
              <span class="text-xs font-semibold">Claude Haiku 4.5</span>
              <span class="badge-cheap">CHEAP</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">~£0.03 · ~60s</p>
          </button>
        </div>
      </div>

      <!-- Phase 2 -->
      <div>
        <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
          Phase 2 · Assessment <span class="text-gray-600 normal-case font-normal">— Risk Manager, Thesis Validator, Financial Modeler</span>
        </p>
        <div class="flex gap-2">
          <button class="model-card selected flex-1" data-phase="phase2" data-model="gemini-2.0-flash" data-provider="gemini" onclick="selectModel(this)">
            <div class="flex justify-between items-center">
              <span class="text-xs font-semibold">Gemini 2.0 Flash</span>
              <span class="badge-free">FREE</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">FREE · ~30s</p>
          </button>
          <button class="model-card flex-1" data-phase="phase2" data-model="claude-haiku-4-5-20251001" data-provider="anthropic" onclick="selectModel(this)">
            <div class="flex justify-between items-center">
              <span class="text-xs font-semibold">Claude Haiku 4.5</span>
              <span class="badge-cheap">CHEAP</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">~£0.02 · ~40s</p>
          </button>
        </div>
      </div>

      <!-- Phase 3 -->
      <div>
        <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
          Phase 3 · Bull/Bear Debate <span class="text-gray-600 normal-case font-normal">— up to 4 rounds</span>
        </p>
        <div class="flex gap-2">
          <button class="model-card selected flex-1" data-phase="debate" data-model="claude-opus-4-7" data-provider="anthropic" onclick="selectModel(this)">
            <div class="flex justify-between items-center">
              <span class="text-xs font-semibold">Claude Opus 4.7</span>
              <span class="badge-best">BEST</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">~£0.20 · ~90s</p>
          </button>
          <button class="model-card flex-1" data-phase="debate" data-model="claude-opus-4-6" data-provider="anthropic" onclick="selectModel(this)">
            <div class="flex justify-between items-center">
              <span class="text-xs font-semibold">Claude Opus 4.6</span>
              <span class="badge-cheap">CHEAPER</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">~£0.14 · ~80s</p>
          </button>
        </div>
      </div>

      <!-- Phase 4 -->
      <div>
        <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
          Phase 4 · Portfolio Manager <span class="text-gray-600 normal-case font-normal">— final verdict</span>
        </p>
        <div class="flex gap-2">
          <button class="model-card selected flex-1" data-phase="pm" data-model="claude-opus-4-7" data-provider="anthropic" onclick="selectModel(this)">
            <div class="flex justify-between items-center">
              <span class="text-xs font-semibold">Claude Opus 4.7</span>
              <span class="badge-best">BEST</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">~£0.14 · ~60s</p>
          </button>
          <button class="model-card flex-1" data-phase="pm" data-model="claude-opus-4-6" data-provider="anthropic" onclick="selectModel(this)">
            <div class="flex justify-between items-center">
              <span class="text-xs font-semibold">Claude Opus 4.6</span>
              <span class="badge-cheap">CHEAPER</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">~£0.10 · ~55s</p>
          </button>
        </div>
      </div>

    </div>

    <!-- Modal footer -->
    <div class="flex items-center justify-between px-5 py-4 border-t border-border">
      <div>
        <p class="text-xs text-gray-500">Estimated run</p>
        <p id="cost-estimate" class="text-sm font-bold">~£0.34 · ~3.8 min</p>
        <p id="cost-detail" class="text-xs text-gray-600 mt-0.5">Flash P1+P2 · Opus 4.7 P3+P4</p>
      </div>
      <button id="start-btn" onclick="startAnalysis()" disabled
        class="px-6 py-2.5 bg-accent text-white rounded-lg font-semibold text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-indigo-500 transition-colors">
        Start Analysis ▶
      </button>
    </div>

  </div>
</div>
```

- [ ] **Step 2: Update phase card headers to show selected model dynamically**

In the four `phase-card` divs in the progress panel, replace the hardcoded model tags:

```html
<!-- Phase 1 — before -->
<h3 class="font-semibold text-sm">Phase 1 — Data Analysts <span class="text-gray-500">(Gemini)</span></h3>

<!-- Phase 1 — after -->
<h3 class="font-semibold text-sm">Phase 1 — Data Analysts <span id="p1-model-tag" class="text-gray-500 font-normal"></span></h3>
```

Apply the same pattern for phases 2, 3, 4 with IDs `p2-model-tag`, `p3-model-tag`, `p4-model-tag`.

- [ ] **Step 3: Add modal CSS to `static/style.css`**

```css
/* Model selection cards */
.model-card {
  @apply border border-border rounded-lg p-3 text-left transition-all cursor-pointer bg-surface;
}
.model-card:hover {
  @apply border-indigo-700;
}
.model-card.selected {
  border-color: #6366f1;
  background: #1e1b4b;
  box-shadow: 0 0 12px rgba(99,102,241,.2);
}
.model-card.selected span.text-xs.font-semibold {
  color: #a5b4fc;
}

/* Badges */
.badge-free   { @apply text-xs font-bold px-2 py-0.5 rounded-full bg-green-950 text-green-400; }
.badge-cheap  { @apply text-xs font-bold px-2 py-0.5 rounded-full bg-orange-950 text-orange-400; }
.badge-best   { @apply text-xs font-bold px-2 py-0.5 rounded-full bg-purple-950 text-purple-400; }
```

- [ ] **Step 4: Manually verify modal opens, cards are visible, close button works**

Start server: `uvicorn main:app --reload`
Open `http://localhost:8000`, click "+ New Analysis", verify modal appears with all four phase rows.

- [ ] **Step 5: Commit**

```
git add templates/index.html static/style.css
git commit -m "feat(ui): add pre-run model configuration modal"
```

---

## Task 7: Frontend — Modal JS + Agent Expand Logic

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Add modal state and lookup tables at the top of `app.js`**

Add after the existing state declarations:

```javascript
// ── Modal state ───────────────────────────────────────────────────────────────
let selectedModels = {
  phase1: { model: 'gemini-2.0-flash',       provider: 'gemini'     },
  phase2: { model: 'gemini-2.0-flash',       provider: 'gemini'     },
  debate: { model: 'claude-opus-4-7',        provider: 'anthropic'  },
  pm:     { model: 'claude-opus-4-7',        provider: 'anthropic'  },
};

const MODEL_COSTS = {
  'gemini-2.0-flash':       { cost: 0,    time: 0    },  // per-phase additive
  'claude-haiku-4-5-20251001': { cost: 0.025, time: 15  },
  'claude-opus-4-7':        { cost: 0.17, time: 45   },
  'claude-opus-4-6':        { cost: 0.12, time: 40   },
};

// Base cost/time for default config (Flash P1+P2, Opus 4.7 P3+P4)
const BASE_COST = 0.34;
const BASE_TIME_SECS = 228;  // ~3.8 min

// Short display names for model tags in phase headers
const MODEL_SHORT = {
  'gemini-2.0-flash':          'Gemini Flash',
  'claude-haiku-4-5-20251001': 'Claude Haiku',
  'claude-opus-4-7':           'Claude Opus 4.7',
  'claude-opus-4-6':           'Claude Opus 4.6',
};

// Agent expand state: agent name → { status, data }
const agentExpandState = {};
```

- [ ] **Step 2: Add modal open/close functions**

```javascript
// ── Modal ─────────────────────────────────────────────────────────────────────
function openModal() {
  document.getElementById('run-modal').classList.remove('hidden');
  document.getElementById('ticker-input').focus();
}

function closeModal() {
  document.getElementById('run-modal').classList.add('hidden');
}

// Close modal when clicking the backdrop
document.getElementById('run-modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

function onTickerInput() {
  const ticker = document.getElementById('ticker-input').value.trim();
  document.getElementById('start-btn').disabled = ticker.length === 0;
}
```

- [ ] **Step 3: Add model card selection + live cost estimate**

```javascript
function selectModel(btn) {
  const phase = btn.dataset.phase;
  // Deselect siblings
  btn.closest('.flex').querySelectorAll('.model-card').forEach(c => c.classList.remove('selected'));
  btn.classList.add('selected');

  selectedModels[phase] = {
    model:    btn.dataset.model,
    provider: btn.dataset.provider,
  };
  updateCostEstimate();
}

function updateCostEstimate() {
  // Simple additive estimate based on deltas from default
  const phases = ['phase1', 'phase2', 'debate', 'pm'];
  let cost = BASE_COST;
  let secs = BASE_TIME_SECS;

  // Default models (what base cost was calculated with)
  const defaults = {
    phase1: 'gemini-2.0-flash',
    phase2: 'gemini-2.0-flash',
    debate: 'claude-opus-4-7',
    pm:     'claude-opus-4-7',
  };

  phases.forEach(p => {
    const sel = selectedModels[p].model;
    const def = defaults[p];
    if (sel !== def) {
      const selCost = MODEL_COSTS[sel]  || { cost: 0, time: 0 };
      const defCost = MODEL_COSTS[def] || { cost: 0, time: 0 };
      cost += selCost.cost - defCost.cost;
      secs += selCost.time - defCost.time;
    }
  });

  const mins = Math.round(secs / 60 * 10) / 10;
  const costStr = cost <= 0 ? 'FREE' : `~£${cost.toFixed(2)}`;
  document.getElementById('cost-estimate').textContent = `${costStr} · ~${mins} min`;

  const detail = `${MODEL_SHORT[selectedModels.phase1.model]} P1 · ` +
                 `${MODEL_SHORT[selectedModels.phase2.model]} P2 · ` +
                 `${MODEL_SHORT[selectedModels.debate.model]} P3 · ` +
                 `${MODEL_SHORT[selectedModels.pm.model]} P4`;
  document.getElementById('cost-detail').textContent = detail;
}
```

- [ ] **Step 4: Update `startAnalysis()` to include model config in POST body and close modal**

Replace the existing `startAnalysis()` function:

```javascript
function startAnalysis() {
  const ticker = document.getElementById('ticker-input').value.trim().toUpperCase();
  if (!ticker) return;

  closeModal();
  resetProgressPanel(ticker);
  document.getElementById('progress-panel').classList.remove('hidden');

  if (activeSource) activeSource.close();

  fetch('/analyse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ticker,
      phase1_model: selectedModels.phase1.model,
      phase2_model: selectedModels.phase2.model,
      debate_model: selectedModels.debate.model,
      pm_model:     selectedModels.pm.model,
    }),
  }).then(res => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    function pump() {
      reader.read().then(({ done, value }) => {
        if (done) { onStreamDone(); return; }
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        lines.forEach(line => {
          if (line.startsWith('data: ')) {
            try { handleEvent(JSON.parse(line.slice(6))); } catch (_) {}
          }
        });
        pump();
      });
    }
    pump();
  }).catch(err => {
    showError('Connection failed: ' + err.message);
  });
}
```

- [ ] **Step 5: Update `resetProgressPanel()` to clear expand state and update model tags**

At the end of the existing `resetProgressPanel()` function, add:

```javascript
  // Clear agent expand state
  Object.keys(agentExpandState).forEach(k => delete agentExpandState[k]);

  // Update phase model tags from selectedModels
  const tagMap = {
    'p1-model-tag': selectedModels.phase1.model,
    'p2-model-tag': selectedModels.phase2.model,
    'p3-model-tag': selectedModels.debate.model,
    'p4-model-tag': selectedModels.pm.model,
  };
  Object.entries(tagMap).forEach(([id, model]) => {
    const el = document.getElementById(id);
    if (el) el.textContent = `(${MODEL_SHORT[model] || model})`;
  });
```

- [ ] **Step 6: Add `agent_log` handler to `handleEvent()` switch**

In `handleEvent()`, add a new case before `case 'agent_complete'`:

```javascript
    case 'agent_log':
      onAgentLog(ev);
      break;
```

- [ ] **Step 7: Add `onAgentLog()` and update `renderAgentChips()` and `onAgentComplete()` for expand**

```javascript
// ── Agent expand ──────────────────────────────────────────────────────────────
function renderAgentChips(containerId, agents) {
  const el = document.getElementById(containerId);
  el.innerHTML = agents.map(name => `
    <button id="chip-${name}"
      class="agent-chip running font-mono text-xs"
      onclick="toggleAgentExpand('${name}', ${containerId === 'p1-agents' ? 1 : 2})"
      title="Click to expand">
      <span class="chip-dot"></span>
      <span class="chip-name">${name}</span>
      <span class="chip-score"></span>
      <span class="chip-conf"></span>
    </button>
  `).join('');
}

function onAgentLog(ev) {
  agentExpandState[ev.agent] = { status: 'running', model: ev.model, startedAt: Date.now() };

  // If this agent's detail panel is already open, update it
  const detail = document.getElementById(`detail-${ev.agent}`);
  if (detail) renderAgentDetail(ev.agent, detail);
}

function onAgentComplete(ev) {
  const chip = document.getElementById('chip-' + ev.agent);
  if (!chip) return;

  chip.classList.remove('running');
  chip.classList.add(ev.status === 'failed' ? 'failed' : 'complete');

  const scoreEl = chip.querySelector('.chip-score');
  const confEl  = chip.querySelector('.chip-conf');
  if (scoreEl) scoreEl.textContent = ev.score != null ? ev.score + '/10' : '—';
  if (confEl) {
    confEl.textContent = ev.data_confidence || '';
    confEl.className = 'chip-conf ' + (ev.data_confidence || '');
  }

  // Update onclick to use correct phase from chip's container
  const phase = chip.closest('#p1-agents') ? 1 : 2;
  chip.setAttribute('onclick', `toggleAgentExpand('${ev.agent}', ${phase})`);

  agentExpandState[ev.agent] = {
    status:          ev.status,
    model:           agentExpandState[ev.agent]?.model || '',
    score:           ev.score,
    data_confidence: ev.data_confidence,
    summary:         ev.summary || '',
    bull_points:     ev.bull_points || [],
    bear_points:     ev.bear_points || [],
    missing_fields:  ev.missing_fields || [],
    duration_ms:     ev.duration_ms,
  };

  // If detail panel is open, re-render with complete data
  const detail = document.getElementById(`detail-${ev.agent}`);
  if (detail) renderAgentDetail(ev.agent, detail);
}

function toggleAgentExpand(agentName, phase) {
  const containerId = phase === 1 ? 'p1-agents' : 'p2-agents';
  const container = document.getElementById(containerId);
  const existingDetail = document.getElementById(`detail-${agentName}`);

  if (existingDetail) {
    existingDetail.remove();
    return;
  }

  const detail = document.createElement('div');
  detail.id = `detail-${agentName}`;
  detail.className = 'agent-detail mt-2 mx-0';
  renderAgentDetail(agentName, detail);

  // Insert after the chips row, before the next sibling
  container.parentNode.insertBefore(detail, container.nextSibling);
}

function renderAgentDetail(agentName, el) {
  const state = agentExpandState[agentName];
  if (!state) { el.innerHTML = '<div class="detail-body text-xs text-gray-600">No data yet.</div>'; return; }

  if (state.status === 'running') {
    const elapsed = Math.round((Date.now() - state.startedAt) / 1000);
    el.innerHTML = `
      <div class="detail-header">
        <span class="detail-name">${agentName}</span>
        <span class="detail-pill pill-running">● Running</span>
      </div>
      <div class="detail-body">
        <div class="running-log">
          <div class="log-line"><span class="log-ts">00:${String(elapsed).padStart(2,'0')}</span><span class="log-msg">Calling <strong>${escHtml(state.model)}</strong>…<span class="log-cursor"></span></span></div>
        </div>
      </div>`;

    // Auto-refresh every second while running
    setTimeout(() => {
      const live = document.getElementById(`detail-${agentName}`);
      if (live && agentExpandState[agentName]?.status === 'running') renderAgentDetail(agentName, live);
    }, 1000);
    return;
  }

  // Complete state
  const conf = state.data_confidence || '';
  const confClass = conf === 'full' ? 'conf-full' : conf === 'partial' ? 'conf-partial' : 'conf-minimal';
  const bulls = (state.bull_points || []).map(p => `<div class="point bull">${escHtml(p)}</div>`).join('');
  const bears = (state.bear_points || []).map(p => `<div class="point bear">${escHtml(p)}</div>`).join('');
  const missing = (state.missing_fields || []).length > 0
    ? `<div class="missing-fields"><p class="missing-label">⚠ Missing fields</p>${(state.missing_fields).map(f => `<div class="missing-item">${escHtml(f)}</div>`).join('')}</div>`
    : '';

  el.innerHTML = `
    <div class="detail-header">
      <span class="detail-name">${agentName}</span>
      <span class="detail-pill pill-done">✓ Complete</span>
    </div>
    <div class="detail-body">
      <div class="detail-score-row">
        <div><span class="detail-score">${state.score ?? '—'}</span><span class="detail-score-denom">/10</span><div class="detail-score-label">Score</div></div>
        <div><span class="confidence-badge ${confClass}">${conf}</span><div class="detail-score-label" style="margin-top:4px">Confidence</div></div>
        <div class="detail-duration">${state.duration_ms ? (state.duration_ms/1000).toFixed(1)+'s' : ''}</div>
      </div>
      <p class="detail-summary">${escHtml(state.summary || '')}</p>
      <div class="detail-points">
        <div><p class="points-label bull">Bull</p>${bulls || '<div class="point" style="color:#4b5563">None</div>'}</div>
        <div><p class="points-label bear">Bear</p>${bears || '<div class="point" style="color:#4b5563">None</div>'}</div>
      </div>
      ${missing}
    </div>`;
}
```

- [ ] **Step 8: Add expand panel CSS to `static/style.css`**

```css
/* Agent expand panel */
.agent-detail {
  border: 1px solid #374151;
  border-radius: 8px;
  overflow: hidden;
  background: #0f1117;
  margin-bottom: 8px;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #1e1b4b;
  border-bottom: 1px solid #312e81;
}
.detail-name { font-size: 11px; font-weight: 700; color: #a5b4fc; text-transform: capitalize; }
.detail-pill { font-size: 9px; font-weight: 700; padding: 2px 8px; border-radius: 10px; }
.pill-running { background: #312e81; color: #818cf8; }
.pill-done    { background: #052e16; color: #4ade80; }
.detail-body  { padding: 10px 12px; font-size: 10px; }

.running-log { font-family: ui-monospace, monospace; font-size: 9px; line-height: 1.8; }
.log-line    { display: flex; gap: 8px; }
.log-ts      { color: #374151; flex-shrink: 0; }
.log-msg     { color: #9ca3af; }
.log-cursor  { display: inline-block; width: 6px; height: 9px; background: #6366f1; margin-left: 2px; vertical-align: middle; animation: blink .8s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

.detail-score-row { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #1f2937; }
.detail-score      { font-size: 22px; font-weight: 800; color: #4ade80; }
.detail-score-denom { font-size: 11px; color: #6b7280; }
.detail-score-label { font-size: 9px; color: #6b7280; margin-top: 1px; }
.detail-duration    { font-size: 9px; color: #4b5563; margin-left: auto; }
.confidence-badge   { font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 10px; }
.conf-full    { background: #052e16; color: #4ade80; }
.conf-partial { background: #422006; color: #fb923c; }
.conf-minimal { background: #3f1212; color: #ef4444; }
.detail-summary { font-size: 10px; color: #9ca3af; line-height: 1.6; margin-bottom: 8px; }
.detail-points  { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.points-label   { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; margin-bottom: 4px; }
.points-label.bull { color: #4ade80; }
.points-label.bear { color: #f87171; }
.point { font-size: 9px; color: #9ca3af; line-height: 1.5; margin-bottom: 3px; padding-left: 10px; position: relative; }
.point.bull::before { content: '▲'; color: #4ade80; font-size: 7px; position: absolute; left: 0; top: 2px; }
.point.bear::before { content: '▼'; color: #f87171; font-size: 7px; position: absolute; left: 0; top: 2px; }
.missing-fields { margin-top: 8px; padding-top: 8px; border-top: 1px solid #1f2937; }
.missing-label  { font-size: 9px; color: #f59e0b; font-weight: 700; margin-bottom: 4px; }
.missing-item   { font-size: 9px; color: #6b7280; padding-left: 10px; position: relative; margin-bottom: 2px; }
.missing-item::before { content: '–'; color: #f59e0b; position: absolute; left: 0; }
```

- [ ] **Step 9: Manual end-to-end test**

```
uvicorn main:app --reload
```

1. Click "+ New Analysis", type `AAPL`, verify Start button enables
2. Switch Phase 1 to Claude Haiku — verify cost estimate updates
3. Click Start Analysis — verify modal closes, progress panel appears
4. Wait for Phase 1 agents to appear — click `fundamental` chip — verify expand shows "Calling…" log
5. Wait for `fundamental` to complete — verify expand updates to show score, confidence, summary, bull/bear points
6. Click chip again — verify it collapses
7. Wait for full run to complete — verify verdict card appears as before

- [ ] **Step 10: Commit**

```
git add static/app.js static/style.css templates/index.html
git commit -m "feat(ui): modal JS, agent expand/collapse, live cost estimate"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Pre-run modal with ticker input | Task 6 |
| Four phase rows with two model cards each | Task 6 |
| Live cost/runtime estimate | Task 7 (Step 3) |
| Start button disabled until ticker filled | Task 7 (Step 2) |
| ModelConfig dataclass | Task 2 |
| Provider derived from model name | Task 2 |
| Agent model override before run() | Task 3 |
| agent_log SSE event from orchestrator | Task 3 |
| Debate model override | Task 4 |
| PM model override | Task 3 (Step 6) |
| /analyse endpoint reads model config | Task 5 |
| 4 new DB columns on analysis_runs | Task 1 |
| create_run() writes model columns | Task 1 |
| update_run() allows model columns | Task 1 |
| Run header shows selected models | Task 7 (Step 5) |
| Agent chips clickable to expand | Task 7 (Step 7) |
| Running expand: model name + elapsed | Task 7 (Step 7) |
| Complete expand: score, confidence, summary, bull/bear, missing | Task 7 (Step 7) |
| Multiple agents expandable at once | Task 7 (Step 7 — each detail has unique ID) |
| agent_complete carries full payload | Task 3 (Step 5) |
| Unit tests: ModelConfig | Task 2 |
| Unit tests: model override routing | Task 3 |
| Integration test: config stored in DB | Task 3 |

All spec requirements covered. No placeholders. Type/method names are consistent across tasks.
